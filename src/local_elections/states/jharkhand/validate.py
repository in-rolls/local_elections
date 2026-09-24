"""Check the parsed Jharkhand reservation data.

The important distinction this draws is between the two reasons a district is
missing:

  * its documents are scans, so nothing can be read without OCR - a source
    ceiling, not a defect in the parser;
  * its documents are text and still produced nothing - our bug.

Conflating the two would make the parser look finished when it is not, which is
how the first pass looked fine at 10 of 24 districts.
"""

import argparse
import csv
import re
import subprocess
import sys

from local_elections.common import checks
from local_elections.common.runlog import command
from local_elections.paths import ROOT

DATA = ROOT / "data" / "jharkhand"
SOURCE = DATA / "2015"

# Published figures for the 2015 Jharkhand panchayat election.
OFFICIAL = {"mukhiya": 4345, "panchayat_samiti": 5423, "zila_parishad": 545}
# Jharkhand reserves half of all seats for women.
WOMEN_SHARE = 0.50
TIERS = ["mukhiya", "panchayat_samiti", "ward_member", "zila_parishad"]

RE_MUKHIYA_TOKEN = "eqf[k;k"


def load(tier):
    path = DATA / f"{tier}_reservation_2015.csv"
    if not path.exists():
        return None
    with path.open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def formats():
    path = DATA.parent / "inventory.csv"
    if not path.exists():
        return {}
    with path.open(encoding="utf-8") as fh:
        return {
            r["path"]: r["format"]
            for r in csv.DictReader(fh)
            if r["state"] == "jharkhand"
        }


def _mentions_mukhiya(path):
    """True if the post token survives text extraction from this document."""
    try:
        text = subprocess.run(
            ["pdftotext", "-layout", str(path), "-"],
            capture_output=True,
            text=True,
            timeout=90,
        ).stdout
    except (subprocess.SubprocessError, OSError):
        return False
    return RE_MUKHIYA_TOKEN in text


@command("validate", state="Jharkhand")
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--verbose", action="store_true")
    ap.parse_args()

    failures = 0
    failures += shared_battery(
        "Jharkhand - shared checks", [(t, load(t) or []) for t in TIERS]
    ).finish()
    print("\n=== Jharkhand panchayat reservation, 2015 ===\n")

    folders = sorted(p.name for p in SOURCE.iterdir() if p.is_dir())
    fmt = formats()

    for tier in TIERS:
        rows = load(tier)
        if rows is None:
            print(f"{tier}: not parsed")
            continue
        districts = {r["district"] for r in rows}
        women = sum(int(r["woman_reserved"]) for r in rows)
        share = 100.0 * women / max(len(rows), 1)
        target = OFFICIAL.get(tier)

        line = (
            f"{tier:18s} {len(rows):6d} seats  "
            f"{len(districts):2d}/{len(folders)} districts  women {share:4.1f}%"
        )
        if target:
            line += f"   {100.0 * len(rows) / target:5.1f}% of {target} published"
        print(line)

        ok = abs(share / 100 - WOMEN_SHARE) <= 0.04
        failures += not ok
        print(
            f"      [{'PASS' if ok else 'FAIL'}] women's share within 4pp of "
            f"{WOMEN_SHARE:.0%}"
        )

    # which districts are missing, and whose fault is it
    rows = load("mukhiya") or []
    have = {r["district"] for r in rows}
    print("\ndistricts with no mukhiya rows:")
    for folder in folders:
        pretty = re.sub(r"^\s*\d+\s*[.)]?\s*", "", folder)
        pretty = re.sub(r"\b(MUKHIYA|PSS|GPS|ZP)\b", "", pretty, flags=re.I)
        pretty = " ".join(re.sub(r"[()&]", " ", pretty).split()).title()
        if pretty in have:
            continue
        docs = [p for p in fmt if p.startswith(f"jharkhand/2015/{folder}/")]
        readable = [p for p in docs if fmt[p] == "digital-text"]
        # "has text" is not the same as "has mukhiya text": a district can hold
        # ten readable files that are all Panchayat Samiti or ward-member lists,
        # with its mukhiya list the one document that happens to be a scan.
        # Only a district whose mukhiya text we can read and still fail to parse
        # is our bug.
        with_post = [p for p in readable if _mentions_mukhiya(DATA.parent / p)]
        verdict = (
            "PARSER GAP" if with_post else "source ceiling (mukhiya list is a scan)"
        )
        print(
            f"   {pretty:22s} {len(docs):3d} docs, {len(readable):3d} text, "
            f"{len(with_post):3d} with mukhiya text  -> {verdict}"
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
