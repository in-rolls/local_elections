"""Check the parsed J&K reservation data.

J&K has no reliable published seat total to check against, and its holdings are
an ad-hoc set rather than a complete corpus, so the checks here are about being
honest rather than about hitting a number:

* the women's share is only meaningful for a **full roster**. 2018's documents
  list only the reserved wards, so its 82% women is a property of the document.
  That check is skipped for `listing_scope == reserved_only` rather than
  reported as a failure or, worse, as a finding.
* 2016 carries two reservation columns, so the sarpanch count must be far
  smaller than the ward count. If they are close, column 13 was misread as
  column 12 and every ward is being recorded twice.
* 2016 also carries the SC/ST populations the allocation was based on, so
  SC-reserved wards should sit in places with more SC population than average.
  No other state in this repo lets the allocation rule be checked against its
  own inputs.
"""

import argparse
import collections
import csv
import sys

from local_elections.common import checks
from local_elections.common.checks import pct
from local_elections.common.runlog import command
from local_elections.paths import ROOT
from local_elections.states.jk import extract_2010, extract_2016, parse

JK = ROOT / "data" / "jk"
CONTROLS_2010 = JK / "2010_extracted" / "controls.csv"
CONTROLS_2016 = JK / "2016_extracted" / "controls.csv"

# The 73rd Amendment, and J&K's own Act, reserve "not less than one-third" of
# seats for women. That is a floor, not a target - unlike Haryana's 50%, which
# is an exact split. So this is a one-sided check. 2010 comes out at 48%, which
# is above the floor rather than a parse error: its raw values are all genuine
# women-reserved strings, down to character-spaced ones like "S T W O M E N".
WOMEN_FLOOR = 1 / 3
YEARS = ["2010", "2016", "2018"]


def load(tier, year):
    path = JK / f"{tier}_reservation_{year}.csv"
    if not path.exists():
        return None
    with path.open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def extraction_controls_2010(rows):
    """Reconcile the 2010 cache and parsed rows to frozen document controls."""
    with CONTROLS_2010.open(encoding="utf-8") as source:
        controls = {row["source_pdf"]: row for row in csv.DictReader(source)}
    records = extract_2010.load()
    pages = collections.Counter(record["source_pdf"] for record in records)
    tables = collections.Counter()
    digests = collections.defaultdict(set)
    for record in records:
        tables[record["source_pdf"]] += len(record["tables"])
        digests[record["source_pdf"]].add(record["source_sha256"])
    parsed = collections.Counter(row["source_pdf"] for row in rows)
    districts = collections.defaultdict(set)
    for row in rows:
        districts[row["source_pdf"]].add(row["district"])

    failures = 0
    held = {path.name for path in (JK / "2010").glob("*.pdf")}
    ok = set(controls) == held == set(pages)
    failures += not ok
    print(
        f"      [{'PASS' if ok else 'FAIL'}] controls, held PDFs, and cache "
        f"name the same {len(controls)} documents"
    )

    bad_shape = []
    bad_rows = []
    bad_districts = []
    bad_bytes = []
    for source_pdf, control in controls.items():
        expected_pages = int(control["expected_pages"])
        expected_tables = int(control["expected_tables"])
        if (pages[source_pdf], tables[source_pdf]) != (
            expected_pages,
            expected_tables,
        ):
            bad_shape.append(source_pdf)
        expected_rows = int(control["expected_rows"] or 0)
        if parsed[source_pdf] != expected_rows:
            bad_rows.append(source_pdf)
        if expected_rows and districts[source_pdf] != {control["expected_district"]}:
            bad_districts.append(source_pdf)
        source_path = JK / "2010" / source_pdf
        if digests[source_pdf] != {extract_2010.sha256(source_path)}:
            bad_bytes.append(source_pdf)

    for description, offenders in (
        ("page and table counts match controls", bad_shape),
        ("parsed row counts match controls", bad_rows),
        ("each document stays in its declared district", bad_districts),
        ("cached hashes match the held PDF bytes", bad_bytes),
    ):
        ok = not offenders
        failures += not ok
        print(
            f"      [{'PASS' if ok else 'FAIL'}] {description}"
            + (f"; {offenders[:4]}" if offenders else "")
        )
    return failures


def extraction_controls_2016(wards, heads):
    """Reconcile the 2016 cache and both parsed tiers to frozen controls."""
    with CONTROLS_2016.open(encoding="utf-8") as source:
        controls = {row["source_pdf"]: row for row in csv.DictReader(source)}
    records = extract_2016.load()
    pages = collections.Counter(record["source_pdf"] for record in records)
    tables = collections.Counter()
    digests = collections.defaultdict(set)
    for record in records:
        tables[record["source_pdf"]] += len(record["tables"])
        digests[record["source_pdf"]].add(record["source_sha256"])
    parsed_wards = collections.Counter(row["source_pdf"] for row in wards)
    parsed_heads = collections.Counter(row["source_pdf"] for row in heads)
    districts = collections.defaultdict(set)
    for row in wards + heads:
        districts[row["source_pdf"]].add(row["district"])
    diagnostics = {}
    parse.parse_2016_records(records, diagnostics)

    failures = 0
    held = {path.name for path in (JK / "2016").glob("*.pdf")}
    ok = set(controls) == held == set(pages)
    failures += not ok
    print(
        f"      [{'PASS' if ok else 'FAIL'}] 2016 controls, held PDFs, and "
        f"cache name the same {len(controls)} documents"
    )

    bad_shape = []
    bad_rows = []
    bad_districts = []
    bad_bytes = []
    expected_skipped = {}
    for source_pdf, control in controls.items():
        if (pages[source_pdf], tables[source_pdf]) != (
            int(control["expected_pages"]),
            int(control["expected_tables"]),
        ):
            bad_shape.append(source_pdf)
        if (parsed_wards[source_pdf], parsed_heads[source_pdf]) != (
            int(control["expected_ward_rows"]),
            int(control["expected_head_rows"]),
        ):
            bad_rows.append(source_pdf)
        if districts[source_pdf] != {control["expected_district"]}:
            bad_districts.append(source_pdf)
        source_path = JK / "2016" / source_pdf
        if digests[source_pdf] != {extract_2016.sha256(source_path)}:
            bad_bytes.append(source_pdf)
        skipped = int(control["unparsed_identity_rows"] or 0)
        if skipped:
            expected_skipped[source_pdf] = skipped

    bad_skipped = diagnostics["skipped_identity_rows"] != expected_skipped
    for description, offenders in (
        ("2016 page and table counts match controls", bad_shape),
        ("2016 ward and head row counts match controls", bad_rows),
        ("each 2016 document stays in its declared district", bad_districts),
        ("2016 cached hashes match the held PDF bytes", bad_bytes),
    ):
        ok = not offenders
        failures += not ok
        print(
            f"      [{'PASS' if ok else 'FAIL'}] {description}"
            + (f"; {offenders[:4]}" if offenders else "")
        )
    failures += bad_skipped
    print(
        f"      [{'FAIL' if bad_skipped else 'PASS'}] excluded 2016 identity "
        "gaps match controls"
    )
    return failures


@command("validate", state="Jammu and Kashmir")
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--verbose", action="store_true")
    ap.parse_args()
    failures = 0
    failures += shared_battery(
        "Jammu & Kashmir - shared checks",
        [(f"{y} {t}", load(t, y) or []) for y in YEARS for t in ("sarpanch", "ward")],
    ).finish()

    print("\n=== Jammu & Kashmir panchayat reservation ===\n")

    rows_2010 = load("ward", "2010") or []
    failures += extraction_controls_2010(rows_2010)
    print()

    wards_2016 = load("ward", "2016") or []
    heads_2016 = load("sarpanch", "2016") or []
    failures += extraction_controls_2016(wards_2016, heads_2016)
    print()

    for year in YEARS:
        for tier in ("sarpanch", "ward"):
            rows = load(tier, year)
            if not rows:
                continue
            scope = rows[0].get("listing_scope", "all_seats")
            women = sum(int(r["woman_reserved"]) for r in rows)
            districts = {r["district"] for r in rows if r["district"]}
            files = {r["source_pdf"] for r in rows}
            share = pct(women, len(rows))

            print(
                f"{year} {tier:9s} {len(rows):6d} seats  "
                f"{len(districts):2d} districts  {len(files):2d} files  "
                f"women {share:4.1f}%   [{scope}]"
            )

            if scope == "all_seats":
                # one-sided: at or above the floor, allowing 2pp for rounding
                ok = share / 100 >= WOMEN_FLOOR - 0.02
                failures += not ok
                print(
                    f"      [{'PASS' if ok else 'FAIL'}] women's share at or "
                    f"above the one-third floor"
                )
            else:
                print(
                    "      [SKIP] women's share - this listing carries only "
                    "reserved seats, so the share is a property of the "
                    "document, not of J&K"
                )

        # 2016 prints both tiers; they must not be the same size
        sarpanch, ward = load("sarpanch", year), load("ward", year)
        if sarpanch and ward:
            ratio = len(ward) / max(len(sarpanch), 1)
            ok = ratio >= 2.5
            failures += not ok
            print(
                f"      [{'PASS' if ok else 'FAIL'}] wards per halqa = "
                f"{ratio:.1f} (near 1 would mean the sarpanch column was "
                f"read as the ward column)"
            )

            # the allocation rule, checked against its own inputs
            withpop = [
                r
                for r in ward
                if r.get("pop_total", "").isdigit() and r.get("pop_sc", "").isdigit()
            ]
            if withpop:

                def sc_share(r):
                    return int(r["pop_sc"]) / max(int(r["pop_total"]), 1)

                reserved = [r for r in withpop if r["caste_reservation"] == "SC"]
                other = [r for r in withpop if r["caste_reservation"] != "SC"]
                if reserved and other:
                    a = sum(map(sc_share, reserved)) / len(reserved)
                    b = sum(map(sc_share, other)) / len(other)
                    ok = a > b
                    failures += not ok
                    print(
                        f"      [{'PASS' if ok else 'FAIL'}] SC-reserved wards "
                        f"have higher SC population share ({a:.1%} vs {b:.1%} "
                        f"in {len(reserved)} vs {len(other)} wards)"
                    )
        print()

    files_on_disk = sum(1 for y in YEARS for _ in (JK / y).glob("*.pdf"))
    used = set()
    for year in YEARS:
        for tier in ("sarpanch", "ward"):
            used |= {r["source_pdf"] for r in (load(tier, year) or [])}
    print(f"documents used: {len(used)} of {files_on_disk} on disk")
    print(
        "J&K's holdings are an ad-hoc subset, not a full corpus - see "
        "SOURCES.md; there is no published seat total to measure against."
    )

    print(f"\n{'FAILED' if failures else 'OK'}: {failures} hard check(s) failed\n")
    return 1 if failures else 0


def shared_battery(title, datasets):
    """Structural and provenance checks every state runs, before its own.

    These cannot catch a misread category - only the substantive checks below
    do that - but they catch a shifted column, a lost key, a row counted twice,
    and a row that cannot be traced back to a page.
    """
    report = checks.Report(title)
    for label, rows in datasets:
        if not rows:
            continue
        print(f"\n-- {label}")
        checks.structural(
            report,
            rows,
            ROOT,
            required=(
                "state",
                "year",
                "tier",
                "reservation",
                "caste_reservation",
                "woman_reserved",
            ),
        )
        checks.provenance(report, rows, ROOT)
    return report


if __name__ == "__main__":
    sys.exit(main())
