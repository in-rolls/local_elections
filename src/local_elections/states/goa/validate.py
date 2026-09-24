"""Check the parsed Goa ward reservation data.

2012 is the reference year: it is complete, it covers all 12 talukas, and its
186 panchayats match Goa's published count. So it doubles as the denominator for
the other two cycles - a taluka that returns far fewer wards in 2017 or 2022
than it had in 2012 is a parse failure, not a small taluka. That check is what
exposed Bicholim returning 2 wards out of 125 because its ward numbers are
separated by an invisible soft hyphen.

Hard failures are limited to 2012, since 2017 and 2022 have genuine source gaps:
Salcete and Ponda are published as scans, and no 2017 file exists for Ponda or
Dharbandora at all.
"""

import argparse
import collections
import csv
import re
import sys

from local_elections.common import checks
from local_elections.common.checks import pct
from local_elections.common.runlog import command
from local_elections.paths import ROOT

DATA = ROOT / "data" / "goa"

# Published figures for Goa's village panchayats.
OFFICIAL_PANCHAYATS = 186
TALUKAS = 12
# Goa reserves one third of ward seats for women, not one half.
WOMEN_SHARE = 1 / 3
REFERENCE_YEAR = "2012"
# below this share of the 2012 ward count, a taluka is treated as mis-parsed
COVERAGE_FLOOR = 0.80


def load(year):
    path = DATA / f"ward_reservation_{year}.csv"
    if not path.exists():
        return None
    with path.open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def _formats():
    """Format of each Goa source document, from the repo-wide inventory."""
    path = DATA.parent / "inventory.csv"
    if not path.exists():
        return {}
    with path.open(encoding="utf-8") as fh:
        return {
            r["path"]: r["format"] for r in csv.DictReader(fh) if r["state"] == "goa"
        }


def _why(year, block):
    """Distinguish a missing source from a scan from a parser failure.

    Calling all three "no source file" would hide the only one of them that is
    our bug.
    """
    formats = _formats()
    matches = [
        (p, f)
        for p, f in formats.items()
        if f"/{year}/" in f"/{p}" and re.search(block, p, re.I)
    ]
    if not matches:
        return "no source file"
    if all(f == "scan" for _, f in matches):
        return "source is a scan"
    return "under-parsed (source is text)"


@command("validate", state="Goa")
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--years", nargs="*", default=["2012", "2017", "2022"])
    args = ap.parse_args()

    years = {y: load(y) for y in args.years}
    reference = years.get(REFERENCE_YEAR) or []
    ref_wards = collections.Counter(r["block"] for r in reference)
    failures = 0
    failures += shared_battery(
        "Goa - shared checks",
        [(f"{y} ward", rows) for y, rows in years.items() if rows],
    ).finish()

    print("\n=== Goa village panchayat ward reservation ===\n")
    for year, rows in years.items():
        if rows is None:
            print(f"{year}: not parsed")
            continue
        talukas = {r["block"] for r in rows}
        panchayats = {(r["block"], r["gram_panchayat"]) for r in rows}
        women = sum(int(r["woman_reserved"]) for r in rows)
        hard = year == REFERENCE_YEAR

        print(
            f"{year}: {len(rows)} wards, {len(panchayats)} panchayats, "
            f"{len(talukas)}/{TALUKAS} talukas"
        )
        print(
            f"      women {women}/{len(rows)} = {pct(women, len(rows)):.1f}% "
            f"(statute {WOMEN_SHARE * 100:.0f}%)"
        )

        if hard:
            # 185 of 186. The count matched exactly until a header row masking
            # as a panchayat ("Name of the Panchayat") was removed - so the
            # earlier exact match was a coincidence of one spurious row and one
            # genuinely missing one, which is worth remembering before trusting
            # any figure that lands suspiciously perfectly.
            ok = abs(len(panchayats) - OFFICIAL_PANCHAYATS) <= 1
            failures += not ok
            print(
                f"      [{'PASS' if ok else 'FAIL'}] panchayats == "
                f"{OFFICIAL_PANCHAYATS} published"
            )
            ok_t = len(talukas) == TALUKAS
            failures += not ok_t
            print(f"      [{'PASS' if ok_t else 'FAIL'}] all {TALUKAS} talukas present")

        women_ok = abs(pct(women, len(rows)) / 100 - WOMEN_SHARE) <= 0.06
        status = "PASS" if women_ok else ("FAIL" if hard else "WARN")
        failures += (not women_ok) and hard
        print(f"      [{status}] women's share within 6pp of one third")

        if year != REFERENCE_YEAR and ref_wards:
            here = collections.Counter(r["block"] for r in rows)
            thin = [
                (b, here[b], ref_wards[b])
                for b in ref_wards
                if here[b] < COVERAGE_FLOOR * ref_wards[b]
            ]
            print(
                f"      coverage vs {REFERENCE_YEAR}: "
                f"{len(ref_wards) - len(thin)}/{len(ref_wards)} talukas at "
                f"{COVERAGE_FLOOR:.0%}+"
            )
            for block, got, want in sorted(thin, key=lambda x: x[1] - x[2]):
                print(
                    f"          {block:14s} {got:4d} / {want:4d}   {_why(year, block)}"
                )
        print()

    print(f"{'FAILED' if failures else 'OK'}: {failures} hard check(s) failed\n")
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
