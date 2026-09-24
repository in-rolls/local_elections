"""Telangana's 2019 panchayat election, from the commission's result tables.

Two shapes. The sarpanch file is clean: 12,018 elected gram panchayat heads with
the reservation in its own column, in the vocabulary Andhra Pradesh uses -
`UR(G)`, `ST(W)` - which `normalize.CODES` already reads, because the two states
share a commission's house style.

The 30 ward files are **misaligned against their own header**, identically in
all 30, and every one of their 49,823 rows carries the same shift:

    header:   Mandal | Gram Panchayat | Ward   | Category | Name
    holds:    mandal | panchayat      | "Ward" | ward no. | "ST(W) KOUSALYA PAYAM"

So `Ward` holds the literal string "Ward" for every row in every file, the ward
number is in `Category`, and the category is glued to the winner's name in
`Name`. That is read off rather than trusted: all 49,823 names begin with one of
the eight category codes, and all 30 files have exactly one distinct value in
`Ward`. A parser that took the header at its word would file 49,823 wards as
"Ward" and lose the reservation entirely, and nothing about the row count would
look wrong.

The district is in the filename and nowhere in the rows.

These are result notifications, so every row is a winner and `winner_basis` is
`published`. `Status` says whether the seat was contested: 12,977 of the 49,823
wards were unanimous.

Provenance is `dataset`: the tables record no document and no page.
"""

import argparse
import csv
import re

from local_elections.common import normalize
from local_elections.common.normalize import label
from local_elections.common.runlog import command
from local_elections.paths import ROOT

DATA = ROOT / "data" / "telangana"
SARPANCH = "data/telangana/2019_gp_sarpanch.csv"
WARDS = "data/telangana/2019_ward"

YEAR = "2019"

# The category codes both files use, glued to the front of the ward winner's
# name and standing alone in the sarpanch file.
PREFIX = re.compile(r"^(UR|SC|ST|BC)\((G|W)\)\s*(.*)$")

COLUMNS = [
    "state",
    "year",
    "district",
    "block",
    "gram_panchayat",
    "ward_no",
    "tier",
    "tier_local",
    "reservation",
    "caste_reservation",
    "woman_reserved",
    "winner",
    "winner_basis",
    "party",
    "unopposed",
    "reservation_raw",
    "script",
    "source_path",
    "source_page",
]

DECLARED = {"gp_head": 12018, "gp_ward": 49823}


def convert(stated, **rest):
    caste = normalize.caste_of(stated)
    woman = normalize.woman_of(stated)
    row = dict(
        {
            "state": "Telangana",
            "year": YEAR,
            "caste_reservation": caste or "",
            "woman_reserved": "" if caste is None else int(woman == 1),
            "reservation": label(caste, woman == 1) if caste else "",
            "reservation_raw": stated,
            "script": "latin",
            "source_page": "",
        },
        **rest,
    )
    row["winner_basis"] = "published" if str(row.get("winner", "")).strip() else ""
    return row


def sarpanch_rows():
    path = ROOT / SARPANCH
    if not path.exists():
        return []
    with path.open(encoding="utf-8", errors="replace") as fh:
        raw = list(csv.DictReader(fh))
    return [
        convert(
            (r.get("Reserved For") or "").strip(),
            district=(r.get("District") or "").strip(),
            block=(r.get("Mandal Name") or "").strip(),
            gram_panchayat=(r.get("Grampanchayat Name") or "").strip(),
            ward_no="",
            tier="gp_head",
            tier_local="sarpanch",
            winner=(r.get("Name Of The Contesting Candidate") or "").strip(),
            # the elected sarpanch's party, which the ward files do not state
            party=(r.get("Party Affiliation") or "").strip(),
            unopposed="",
            source_path=SARPANCH,
        )
        for r in raw
    ]


def ward_rows():
    directory = ROOT / WARDS
    if not directory.exists():
        return []
    out = []
    for path in sorted(directory.glob("*.csv")):
        # the district is in the filename and in none of the rows
        district = path.stem.replace(f"{YEAR}_ward_", "").strip()
        with path.open(encoding="utf-8", errors="replace") as fh:
            raw = list(csv.DictReader(fh))
        if {(r.get("Ward") or "").strip() for r in raw} != {"Ward"}:
            raise SystemExit(
                f"telangana: {path.name} does not carry the shift every other "
                f"ward file does - re-read the header before parsing it"
            )
        for row in raw:
            got = PREFIX.match((row.get("Name") or "").strip())
            if not got:
                raise SystemExit(
                    f"telangana: {path.name} has a winner name with no "
                    f"category prefix: {row.get('Name')!r}"
                )
            category, gender, winner = got.groups()
            status = (row.get("Status") or "").strip()
            out.append(
                convert(
                    f"{category}({gender})",
                    district=district,
                    block=(row.get("Mandal") or "").strip(),
                    gram_panchayat=(row.get("Gram Panchayat") or "").strip(),
                    # the header calls this Category; it holds the ward number
                    ward_no=(row.get("Category") or "").strip(),
                    tier="gp_ward",
                    tier_local="ward member",
                    winner=winner.strip(),
                    party="",
                    unopposed=int(status.lower() == "unanimous"),
                    source_path=f"{WARDS}/{path.name}",
                )
            )
    return out


@command("parse", state="Telangana")
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    for tier, rows in (("gp_head", sarpanch_rows()), ("gp_ward", ward_rows())):
        if not rows:
            continue
        path = DATA / f"{tier}_{YEAR}.csv"
        with path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(
                fh, fieldnames=COLUMNS, extrasaction="ignore", lineterminator="\n"
            )
            writer.writeheader()
            writer.writerows(rows)
        if not args.quiet:
            print(f"  {tier}: {len(rows):,} seats")


if __name__ == "__main__":
    main()
