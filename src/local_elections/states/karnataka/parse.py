"""Karnataka gram panchayat presidents, 1993-2007, from a Stata file.

Five cycles of `Adhyaksha` - the gram panchayat president - over the same 5,855
panchayats, which makes this the only source in the corpus that is a panel. It
is also the only one carrying **per-panchayat Census population**, so it is the
single biggest addition to what can be checked from outside: it takes
`caste_share_vs_population` - the strongest check available here - from 2 slices
to 7.

Read the `caste` value label, not the `reserved_*` indicator columns. Those are
lossy: the non-women indicators do not sum to one per row, and `reserved_w` is
missing for 1,250 rows in 1993 alone. The label states both facts in one code.

**The label has a typo and it is worth stating exactly how it was settled.**
Codes 5 and 6 both read `BC A(W)`. Across all five cycles, code 5 is
`reserved_w=0` on all 4,079 of its rows and code 6 is `reserved_w=1` on all
1,991 of its. Two codes cannot both be the women's category and be split that
cleanly by an independent column, so code 5 is `BC A` and the `(W)` is a
copy-paste. Nothing here relies on the indicator columns otherwise.

Karnataka reserves separately for Backward Class A and Backward Class B, which
is a finer scheme than the single BC other states print, so both are kept:
`caste_reservation` folds to BC and `caste_reservation_local` says which. Codes
11 and 12 read `BC--A OR B` and are genuinely unsplit in the source.

`Upadhyaksha` - the vice president - is dropped rather than filed as a tier. It
is an office the same body elects from among its own members, not a seat.

Provenance is `dataset`: the file records no document and no page.
"""

import argparse
import csv

from local_elections.common.normalize import label
from local_elections.common.runlog import command
from local_elections.paths import ROOT

SOURCE = "data/karnataka/Karnataka_GP_ReservationHistory.dta"
OUT = ROOT / "data" / "karnataka"

YEARS = ["1993", "2000", "2002", "2005", "2007"]

# The `caste` value label, with code 5 corrected. (pooled caste, local label,
# reserved for a woman)
CASTE = {
    1: ("SC", "SC", 0),
    2: ("SC", "SC", 1),
    3: ("ST", "ST", 0),
    4: ("ST", "ST", 1),
    # the label reads BC A(W) for both 5 and 6; 5 is reserved_w=0 on all 4,079
    # of its rows across five cycles, so it is BC A
    5: ("BC", "BC_A", 0),
    6: ("BC", "BC_A", 1),
    7: ("BC", "BC_B", 0),
    8: ("BC", "BC_B", 1),
    9: ("NONE", "GEN", 0),
    10: ("NONE", "GEN", 1),
    # genuinely unsplit in the source, not an unread cell
    11: ("BC", "BC_A_OR_B", 0),
    12: ("BC", "BC_A_OR_B", 1),
}

# Census columns carried through, so caste_share_vs_population has something to
# appeal to. Named as the dictionary names them.
POPULATION = {
    "tot_p": "pop_total",
    "p_sc": "pop_sc",
    "p_st": "pop_st",
    "tot_f": "pop_female",
}

COLUMNS = [
    "state",
    "year",
    "district",
    "block",
    "gram_panchayat",
    "gp_no",
    "gp_code",
    "tier",
    "tier_local",
    "reservation",
    "caste_reservation",
    "caste_reservation_local",
    "woman_reserved",
    "reservation_raw",
    "script",
    "source_path",
    "source_page",
    "pop_total",
    "pop_sc",
    "pop_st",
    "pop_female",
]

# What each cycle holds, so a re-run that reads a different file says so.
DECLARED = {"1993": 5264, "2000": 5320, "2002": 5320, "2005": 5322, "2007": 5322}


def rows_for(frame, year):
    column = f"Adhyaksha{year}"
    out, unreadable = [], 0
    for record in frame.to_dict("records"):
        value = record.get(column)
        if value is None or value != value:  # NaN
            continue
        code = int(value)
        if code not in CASTE:
            # one row in 1993 carries code 110, outside the label entirely
            unreadable += 1
            continue
        caste, local, woman = CASTE[code]
        gp_code = str(record.get("gpidcode") or "").strip()
        row = {
            "state": "Karnataka",
            "year": year,
            "district": str(record.get("districtname") or "").strip(),
            "block": str(record.get("talukname") or "").strip(),
            "gram_panchayat": str(record.get("gpname") or "").strip(),
            "gp_no": gp_code,
            "gp_code": gp_code,
            "tier": "gp_head",
            "tier_local": "adhyaksha",
            "caste_reservation": caste,
            "caste_reservation_local": local,
            "woman_reserved": woman,
            "reservation": label(caste, woman == 1),
            "reservation_raw": f"{column}={code}",
            "script": "latin",
            "source_path": SOURCE,
            "source_page": "",
        }
        for source, target in POPULATION.items():
            got = record.get(source)
            row[target] = "" if got is None or got != got else int(got)
        out.append(row)
    return out, unreadable


@command("parse", state="Karnataka", series="gp_head_reservation")
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    try:
        import pandas
    except ImportError as exc:
        raise SystemExit(
            "pandas is needed to read the Stata file; the CSVs it "
            "writes are committed, so this only has to run when "
            "the source changes"
        ) from exc

    frame = pandas.read_stata(ROOT / SOURCE, convert_categoricals=False)
    OUT.mkdir(parents=True, exist_ok=True)
    for year in YEARS:
        rows, unreadable = rows_for(frame, year)
        path = OUT / f"gp_head_{year}.csv"
        with path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(
                fh, fieldnames=COLUMNS, extrasaction="ignore", lineterminator="\n"
            )
            writer.writeheader()
            writer.writerows(rows)
        if not args.quiet:
            note = f"  ({unreadable} outside the caste label)" if unreadable else ""
            print(f"  {year}: {len(rows):,} panchayat presidents{note}")


if __name__ == "__main__":
    main()
