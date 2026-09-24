"""Measure the Jharkhand parse against a recorded baseline.

    uv run python -m local_elections.states.jharkhand.bench --record    # store
    what the code does now
    ...make a change...
    uv run python -m local_elections.states.jharkhand.bench             # print the
    gates

Written because this branch's OCR change passed every check it had and still
shipped a 1,094-row regression into a tier nobody was watching. The gates that
found it were run by hand, after the fact, on snapshots kept in /tmp. A baseline
that lives in a scratch directory is a baseline that disagrees with the next
session.

Three splits, fixed here so they cannot drift:

  DIAGNOSE    documents opened and read while forming a hypothesis. They may be
              stared at, so an improvement here is not evidence of anything.
  VALIDATE    scanned documents never inspected. This is where a recovery has
              to show up.
  REGRESSION  the digital-text documents, which no OCR change touches. They are
              the collateral-damage guard: every parser rule here runs through
              code the whole corpus shares, so a rule tuned on a scan can break
              a district that was already correct. Nothing here may move.

Metrics are soundness, not fill. A row counts only when its seat identity is
*complete for its tier* - a panchayat samiti seat has no gram panchayat and
demanding one scored four correct pages at zero the first time this was
measured. Removing a wrong value is therefore neutral, replacing it with a right
one is a gain, and inventing a plausible wrong one is a loss.

`coverage_distance` scores closeness to the published seat count rather than
coverage itself, because coverage is a ratio with a target of 1.0 and overshoot
is not success: the mukhiya file this replaces read 102% of the gram panchayats
Jharkhand has, which is not 2% better than perfect, it is impossible. A gate on
raw coverage rewards the inflation and rejects the fix.
"""

import argparse
import collections
import csv
import json
import pathlib
import sys

from local_elections.common import canon
from local_elections.common.runlog import command
from local_elections.paths import ROOT

JH = ROOT / "data" / "jharkhand"
BASELINE = ROOT / "data" / "stats" / "jharkhand_bench.json"

TIERS = ("mukhiya", "panchayat_samiti", "ward_member", "zila_parishad")

# Published figures, the same ones validate.py holds. A seat count is the only
# external truth available here; everything else is the parse marking its own
# homework.
PUBLISHED = {"mukhiya": 4345, "panchayat_samiti": 5423, "zila_parishad": 545}

DIAGNOSE = {
    "CHATRA MUKHIYA PSS GPS ZP.pdf",
    "LATEHAR MUKHIYA PSS GPS ZP.pdf",
    "KODERMA MUKHIYA PSS GPS ZP.pdf",
}

NO_PANCHAYAT = ("panchayat_samiti", "zila_parishad")


def scanned():
    """Documents whose published rows come from the model, by filename.

    Not "documents that have been OCR'd" - every document has now, and defining
    the split that way emptied it the moment the last one finished, so the gate
    that guards against collateral damage silently guarded nothing.

    The question the splits need is which reader a document's rows come from,
    which is the one parse.model_read_it asks: twenty-nine documents render as
    Latin because their Kruti Dev is neither embedded nor installed, the model
    transcribes the wreckage, and their rows still come from the text layer.
    Those are what an OCR change cannot touch, so those are REGRESSION.
    """
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "jh_parse", pathlib.Path(__file__).resolve().parent / "parse.py"
    )
    parse = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(parse)
    return {
        p.stem + ".pdf" for p in (JH / "ocr").glob("*.txt") if parse.model_read_it(p)
    }


def rows():
    out = []
    for tier in TIERS:
        path = JH / f"{tier}_reservation_2015.csv"
        if not path.exists():
            continue
        with path.open(encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                row["_tier"] = tier
                out.append(row)
    return out


def split_of(row, ocr):
    pdf = pathlib.Path(row.get("source_pdf", "")).name
    if pdf in DIAGNOSE:
        return "DIAGNOSE"
    return "VALIDATE" if pdf in ocr else "REGRESSION"


def complete(row):
    """Does this row identify a seat, given what its tier has to identify?"""
    tier = row["_tier"]
    number = row.get("ward_no" if tier == "ward_member" else "seat_no")
    if not (number or "").strip():
        return False
    if tier in NO_PANCHAYAT:
        return bool(
            (row.get("block_no") or "").strip() or (row.get("block") or "").strip()
        )
    return bool(canon.unit_name(row)) and bool((row.get("block_no") or "").strip())


def measure():
    ocr = scanned()
    all_rows = rows()
    by_split = collections.defaultdict(list)
    for row in all_rows:
        by_split[split_of(row, ocr)].append(row)

    out = {"splits": {}, "tiers": {}}
    for split, subset in sorted(by_split.items()):
        per_tier = collections.Counter(r["_tier"] for r in subset)
        out["splits"][split] = {
            "rows": len(subset),
            "complete": sum(1 for r in subset if complete(r)),
            "complete_share": round(
                sum(1 for r in subset if complete(r)) / max(len(subset), 1), 4
            ),
            "by_tier": dict(per_tier),
        }

    for tier in TIERS:
        subset = [r for r in all_rows if r["_tier"] == tier]
        entry = {"rows": len(subset)}
        # Mukhiya only, and the restriction is the whole point: a gram panchayat
        # elects one head, so a district holding more heads than panchayats has
        # rows that cannot all be real. A panchayat elects many ward members, so
        # the same arithmetic on ward_member reports 16,200 and means nothing -
        # a number that cannot indicate a defect is decoration, and decoration
        # that a gate reads can only fire spuriously.
        #
        # Counted as rows sharing one seat identifier, which took three goes to
        # get right. Rows-minus-distinct-*names* called two genuinely different
        # panchayats an impossibility - Giridih prints नीमाडीह in block 01 and
        # again in block 05 - and reported 160. Rows-minus-distinct-*identifiers*
        # charged every row that states no identifier as a duplicate of every
        # other and reported 53. The true count is 1. A gate that cannot tell 1
        # from 160 is not evidence, and both wrong versions were mine.
        if tier == "mukhiya":
            per_district = collections.defaultdict(collections.Counter)
            for row in subset:
                seat = (row.get("seat_id_raw") or "").strip()
                if seat:
                    per_district[row.get("district", "")][seat] += 1
            entry["impossible_excess"] = sum(
                n - 1
                for seats in per_district.values()
                for n in seats.values()
                if n > 1
            )
        if tier in PUBLISHED and subset:
            coverage = len(subset) / PUBLISHED[tier]
            entry["coverage"] = round(coverage, 4)
            entry["coverage_distance"] = round(abs(coverage - 1.0), 4)
        out["tiers"][tier] = entry
    return out


def gates(before, after):
    """The four gates, as pass/fail lines. Returns True when all hold."""
    lines, ok = [], True

    def gate(name, good, detail):
        nonlocal ok
        ok = ok and good
        lines.append(f"  [{'PASS' if good else 'FAIL'}] {name:<34} {detail}")

    for split in ("DIAGNOSE", "VALIDATE"):
        b = before["splits"].get(split, {})
        a = after["splits"].get(split, {})
        was, now = b.get("complete_share", 0), a.get("complete_share", 0)
        label = "in-sample" if split == "DIAGNOSE" else "out-of-sample"
        gate(
            f"{label} ({split})", now >= was - 0.001, f"complete {was:.1%} -> {now:.1%}"
        )

    b = before["splits"].get("REGRESSION", {})
    a = after["splits"].get("REGRESSION", {})
    same = b.get("rows") == a.get("rows") and b.get("complete") == a.get("complete")
    gate(
        "no degradation (REGRESSION)",
        same,
        f"{b.get('rows', 0):,} rows/{b.get('complete', 0):,} complete -> "
        f"{a.get('rows', 0):,}/{a.get('complete', 0):,}"
        + ("" if same else "  <- digital-text documents must not move"),
    )

    for tier, entry in after["tiers"].items():
        was = before["tiers"].get(tier, {})
        if "coverage_distance" not in entry or "coverage_distance" not in was:
            continue
        gate(
            f"closeness to published ({tier})",
            entry["coverage_distance"] <= was["coverage_distance"] + 0.001,
            f"|coverage-1| {was['coverage_distance']:.3f} -> "
            f"{entry['coverage_distance']:.3f} "
            f"(coverage {was.get('coverage', 0):.1%} -> {entry['coverage']:.1%})",
        )

    for tier, entry in after["tiers"].items():
        was = before["tiers"].get(tier, {}).get("impossible_excess")
        if was is None:
            continue
        gate(
            f"impossible rows ({tier})",
            entry["impossible_excess"] <= was,
            f"{was:,} -> {entry['impossible_excess']:,}",
        )
    return ok, lines


@command("validate", state="Jharkhand", expectation_set="parser_benchmark")
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--record",
        action="store_true",
        help="store the current measurement as the baseline",
    )
    args = ap.parse_args()

    now = measure()
    if args.record:
        BASELINE.parent.mkdir(parents=True, exist_ok=True)
        BASELINE.write_text(
            json.dumps(now, indent=1, sort_keys=True) + "\n", encoding="utf-8"
        )
        print(f"baseline -> {BASELINE.relative_to(ROOT)}")
        for split, entry in sorted(now["splits"].items()):
            print(
                f"  {split:<11} {entry['rows']:>7,} rows  "
                f"{entry['complete_share']:>6.1%} complete"
            )
        return 0

    if not BASELINE.exists():
        print(f"no baseline at {BASELINE.relative_to(ROOT)}; run with --record first")
        return 2
    before = json.loads(BASELINE.read_text(encoding="utf-8"))
    ok, lines = gates(before, now)
    print("\n".join(lines))
    print(
        f"\n{'OK' if ok else 'FAILED'}: "
        f"{sum(1 for line_ in lines if '[FAIL]' in line_)} gate(s) failed"
    )
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
