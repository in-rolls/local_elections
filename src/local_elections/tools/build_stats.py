"""Stats and checks for every state x year x tier, written where they can be read.

Each state's validate.py prints a report to the terminal and then it is gone.
That is fine while a parser is being written and useless afterwards: there is
nowhere to look up what a slice contains, nothing to diff when a parser changes,
and no way to see that a check was skipped rather than passed.

Writes three files:

    data/stats/slice_stats.csv    what each slice holds
    data/stats/slice_checks.csv   one row per check, with its status
    data/stats/state_stats.csv    the rollup

The stats file is also the regression test for a refactor. Snapshot it, change
the parsers, diff: a harmonisation that only renames things must not move a
single number.
"""

import argparse
import collections
import csv
import sys

from local_elections.common import canon, datasets, reference, slice_checks
from local_elections.common.runlog import command
from local_elections.paths import ROOT

STATS = ROOT / "data" / "stats"

STAT_COLUMNS = [
    "state",
    "year",
    "tier",
    "tier_local",
    "rows",
    "districts",
    "blocks",
    "panchayats",
    "wards",
    "women",
    "women_share",
    "sc_share",
    "st_share",
    "bc_share",
    "none_share",
    "listing_scope",
    "script",
    "blank_district",
    "blank_block",
    "blank_panchayat",
    "blank_ward_no",
    "blank_winner",
    "duplicate_seat_rows",
    "source_documents",
    "source_pages",
    "published_total",
    "published_basis",
    "published_unit",
    "coverage_pct",
    "women_rule",
    "women_rule_value",
    "row_band",
    "files",
]

CHECK_COLUMNS = [
    "state",
    "year",
    "tier",
    "check_id",
    "appeals_to",
    "status",
    "observed",
    "expected",
    "detail",
]


def slices():
    """Group every pooled row by state x year x tier.

    Pooled, not parsed: the checks have to see the sibling states too, or the
    two thirds of the master that comes from adapters is unchecked while the
    report reads as though everything passed.
    """
    grouped = collections.defaultdict(list)
    files = collections.defaultdict(set)
    for dataset_id, rows in datasets.pooled():
        for row in rows:
            key = (row.get("state", ""), row.get("year", ""), row.get("tier", ""))
            grouped[key].append(row)
            files[key].add(dataset_id)
    return grouped, files


def stat_row(state, year, tier, rows, filenames):
    s = slice_checks.Slice(state, year, tier, rows, ROOT)
    n = max(s.n, 1)
    spec = reference.published(state, year, tier)
    kind, value = reference.women_rule(state, year)
    band = slice_checks.dictionary.ROW_BANDS.get((state, tier))

    def blank(column):
        return round(1 - s.filled(column) / n, 4)

    seats = collections.Counter(
        (
            r.get("district", ""),
            r.get("block", ""),
            canon.unit_name(r),
            r.get("ward_no", ""),
            r.get("seat_no", ""),
        )
        for r in rows
    )

    coverage = ""
    if spec.get("total"):
        counted = (
            [r for r in rows if str(r.get("vacant", "")) != "1"]
            if spec.get("basis") == "elected"
            else rows
        )
        got = (
            len({(r.get("block"), canon.unit_name(r)) for r in counted})
            if spec.get("unit") == "panchayats"
            else len(counted)
        )
        coverage = round(100.0 * got / spec["total"], 1)

    return {
        "state": state,
        "year": year,
        "tier": tier,
        "tier_local": ",".join(t for t in s.tier_local if t),
        "rows": s.n,
        "districts": len({r.get("district") for r in rows if r.get("district")}),
        "blocks": len(
            {(r.get("district"), r.get("block")) for r in rows if r.get("block")}
        ),
        "panchayats": len(
            {
                (r.get("district"), r.get("block"), canon.unit_name(r))
                for r in rows
                if canon.unit_name(r)
            }
        ),
        "wards": len({r.get("ward_no") for r in rows if r.get("ward_no")}),
        "women": s.women,
        "women_share": round(s.women / n, 4),
        "sc_share": round(s.share("caste_reservation", "SC"), 4),
        "st_share": round(s.share("caste_reservation", "ST"), 4),
        "bc_share": round(s.share("caste_reservation", "BC"), 4),
        "none_share": round(s.share("caste_reservation", "NONE"), 4),
        "listing_scope": s.scope,
        "script": ",".join(sorted({r.get("script", "") for r in rows})),
        "blank_district": blank("district"),
        "blank_block": blank("block"),
        "blank_panchayat": round(1 - sum(1 for r in rows if canon.unit_name(r)) / n, 4),
        "blank_ward_no": blank("ward_no"),
        "blank_winner": blank("winner"),
        "duplicate_seat_rows": sum(v for v in seats.values() if v > 1),
        "source_documents": len({r.get("source_path") for r in rows}),
        "source_pages": len(
            {(r.get("source_path"), r.get("source_page")) for r in rows}
        ),
        "published_total": spec.get("total") or "",
        "published_basis": spec.get("basis", ""),
        "published_unit": spec.get("unit", ""),
        "coverage_pct": coverage,
        "women_rule": kind or "",
        "women_rule_value": value or "",
        "row_band": f"{band[0]}..{band[1]}" if band else "",
        "files": ";".join(sorted(filenames)),
    }


def write(path, columns, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(
            fh, fieldnames=columns, extrasaction="ignore", lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(rows)


@command("validate", expectation_set="reference_slices")
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    grouped, files = slices()
    stats, checks = [], []
    for (state, year, tier), rows in sorted(grouped.items()):
        stats.append(stat_row(state, year, tier, rows, files[(state, year, tier)]))
        a_slice = slice_checks.Slice(state, year, tier, rows, ROOT)
        for got in slice_checks.run(a_slice):
            checks.append(dict(got, state=state, year=year, tier=tier))

    by_state = collections.defaultdict(list)
    for row in stats:
        by_state[row["state"]].append(row)
    rollup = []
    for state, subset in sorted(by_state.items()):
        total = sum(r["rows"] for r in subset)
        women = sum(r["women"] for r in subset)
        rollup.append(
            {
                "state": state,
                "slices": len(subset),
                "rows": total,
                "years": ",".join(sorted({r["year"] for r in subset})),
                "tiers": ",".join(sorted({r["tier"] for r in subset})),
                "women_share": round(women / max(total, 1), 4),
                "caste_scheme": canon.caste_scheme(state) or "",
            }
        )

    write(STATS / "slice_stats.csv", STAT_COLUMNS, stats)
    write(STATS / "slice_checks.csv", CHECK_COLUMNS, checks)
    write(
        STATS / "state_stats.csv",
        ["state", "slices", "rows", "years", "tiers", "women_share", "caste_scheme"],
        rollup,
    )

    tally = collections.Counter(c["status"] for c in checks)
    print(f"\n{len(stats)} slices, {len(checks)} checks -> {STATS.relative_to(ROOT)}/")
    print("  " + "  ".join(f"{k}={v}" for k, v in sorted(tally.items())))

    hard = [c for c in checks if c["status"] == slice_checks.FAIL]
    if not args.quiet:
        print(f"\n{'status':7} {'state':16} {'yr':5} {'tier':13} {'check':30} observed")
        for c in checks:
            if c["status"] in (slice_checks.FAIL, slice_checks.WARN):
                print(
                    f"{c['status']:7} {c['state'][:16]:16} {c['year']:5} "
                    f"{c['tier'][:13]:13} {c['check_id'][:30]:30} "
                    f"{c['observed'][:40]}"
                )
    print(f"\n{'FAILED' if hard else 'OK'}: {len(hard)} check(s) failed\n")
    return 1 if hard else 0


if __name__ == "__main__":
    sys.exit(main())
