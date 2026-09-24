"""Parse Goa village panchayat ward reservation, 2012 / 2017 / 2022.

Goa reserves at **ward** level. Its sarpanch is elected indirectly by the ward
members, so unlike Haryana or Jharkhand there is no directly reserved sarpanch
seat to collect - the ward category is the assignment.

The three cycles are published in three different shapes, so there are three
extractors:

  2012  panres_<taluka>.pdf   ruled 8-column table, and the best of the three:
                              it names the *elected* representative and the
                              votes polled alongside the ward category
  2022  list-of-validly-...   ruled 6-column table of nominated candidates,
                              with ward and category fused into one cell
                              ("WARD I (Women)"); several candidates per ward,
                              so rows collapse to one per ward
  2017  <taluka>.pdf          no ruled table at all. The ward number and its
                              category are printed on separate lines either
                              side of the candidate row, so this one is read
                              line by line.

Writes data/goa/ward_reservation_<year>.csv.
"""

import argparse
import collections
import re

import pdfplumber

from local_elections.common import emit
from local_elections.common.normalize import (
    label,
    normalize_reservation,
)
from local_elections.common.runlog import command, get_logger
from local_elections.paths import ROOT

LOGGER = get_logger(__name__)

GOA = ROOT / "data" / "goa"

# Goa's 12 talukas roll up to two districts. Stable, and worth carrying so the
# output has the same district/block shape as the other states.
DISTRICT = {
    "bardez": "North Goa",
    "bicholim": "North Goa",
    "pernem": "North Goa",
    "ponda": "North Goa",
    "sattari": "North Goa",
    "tiswadi": "North Goa",
    "canacona": "South Goa",
    "dharbandora": "South Goa",
    "mormugao": "South Goa",
    "quepem": "South Goa",
    "salcete": "South Goa",
    "sanguem": "South Goa",
}

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
    "votes",
    "unopposed",
    "reservation_raw",
    "script",
    "source_pdf",
]

RE_UNOPPOSED = re.compile(r"^unopp", re.I)

RE_WARD_LINE = re.compile(r"^\s*Ward\s+([IVXLC]+|\d+)\s*$", re.I)
RE_CATEGORY_LINE = re.compile(r"^\s*\(([^)]{1,25})\)\s*$")
# "<sr no> <panchayat> <candidate count> <candidate name>"
RE_BODY_ROW = re.compile(r"^\s*\d+\s+([A-Za-z][A-Za-z .'\-]{1,34}?)\s+\d+\s+\S")
# Every taluka writes the ward differently, and each variant that is not
# handled silently drops that taluka whole rather than erroring:
#   Canacona  "WARD I (Women)"
#   Mormugao  "WARD NO. I (General)"
#   Sanguem   "Ward-I (OBC Women)"
#   Bicholim  "Ward\u00adIV"           - separated by an invisible soft hyphen
#   Pernem    "I (General)"        - no "WARD" keyword at all
SEP = r"[\s\u00ad\u2010\u2011.:\-\u2013\u2014]*"
RE_WARD_AND_CATEGORY = re.compile(
    rf"WARD{SEP}(?:NO\.?)?{SEP}([IVXLC]+|\d+){SEP}\(([^)]{{1,25}})\)", re.I
)
# fallback for the talukas that print only the numeral
RE_BARE_WARD = re.compile(rf"^{SEP}([IVXLC]+|\d+){SEP}\(([^)]{{1,25}})\)")


def clean(cell):
    return re.sub(r"\s+", " ", (cell or "").replace("\n", " ")).strip()


def taluka_of(path, printed):
    """Taluka from the filename, which is more reliable than the page header.

    2012 prints section headers like "BICHOLIM-I" that number sub-areas rather
    than name the taluka, so the filename wins where they disagree.
    """
    stem = path.stem.lower()
    for name in DISTRICT:
        if name in stem:
            return name.title()
    return clean(printed).title()


def row(
    year,
    taluka,
    panchayat,
    ward,
    raw,
    winner="",
    votes="",
    source="",
    path=None,
    page=None,
):
    # A header row that survives shows up only as a duplicate key later - Goa
    # carried three wards for a panchayat called "Name of the Panchayat".
    if emit.is_header_text(panchayat) or emit.is_header_text(taluka):
        return None
    parsed = normalize_reservation(raw)
    if not parsed:
        return None
    caste, woman, script = parsed
    # Goa prints the word in the votes column instead of a count. There is
    # already a column for that fact, and leaving it in votes meant 19 seats
    # were unopposed while `unopposed` was blank on every one of them - so a
    # consumer filtering on the flag found none of them, and anyone reading
    # votes as a number found a word.
    #
    # Matched on the `unopp` stem rather than the whole word: the 2012 gazette
    # spells it "Unopposed" 16 times and "Unoppsoed" 3 times. Anything else
    # non-numeric is left alone deliberately, so build_master's cast fails on it
    # and a new variant is found rather than silently becoming a null.
    unopposed = ""
    if RE_UNOPPOSED.match(str(votes).strip()):
        votes, unopposed = "", 1
    made = {
        "state": "Goa",
        "year": year,
        "district": DISTRICT.get(taluka.lower(), ""),
        "block": taluka,
        "gram_panchayat": panchayat,
        "ward_no": ward,
        "tier": "gp_ward",
        "tier_local": "ward",
        "reservation": label(caste, woman),
        "caste_reservation": caste,
        "woman_reserved": woman,
        "winner": winner,
        "votes": votes,
        "unopposed": unopposed,
        "reservation_raw": clean(raw),
        "script": script,
        "source_pdf": source,
    }
    # Every other state stamps provenance; Goa's parser predates emit.stamp, so
    # its rows could not be traced back to a page. The expectations run flagged
    # exactly that.
    return emit.stamp(made, path, page, ROOT) if path else made


def parse_2012(path):
    """Ruled 8-column table: Sl | Taluka | Panchayat | Ward | Category |
    Elected Representative | Address | Votes.
    """
    taluka = taluka_of(path, "")
    panchayat = None
    out = []
    with pdfplumber.open(str(path)) as pdf:
        for page in pdf.pages:
            for table in page.find_tables():
                for raw in table.extract():
                    cells = [clean(c) for c in raw]
                    if len(cells) < 5:
                        continue
                    if cells[2]:
                        panchayat = cells[2]
                    ward, category = cells[3], cells[4]
                    if (
                        not ward
                        or not category
                        or category.lower().startswith("category")
                    ):
                        continue
                    winner = cells[5] if len(cells) > 5 else ""
                    votes = cells[7] if len(cells) > 7 else ""
                    made = row(
                        "2012",
                        taluka,
                        panchayat or "",
                        ward,
                        category,
                        winner,
                        votes,
                        path.name,
                        path,
                        page.page_number,
                    )
                    if made:
                        out.append(made)
    return out


def parse_2022(path):
    """Ruled 6-column table with ward and category fused: "WARD I (Women)".

    One row per *candidate*, so the same ward repeats; collapsed to one row per
    (panchayat, ward) since the reservation is a property of the ward.
    """
    taluka = taluka_of(path, "")
    panchayat = None
    seen = {}
    with pdfplumber.open(str(path)) as pdf:
        for page in pdf.pages:
            for table in page.find_tables():
                for raw in table.extract():
                    cells = [clean(c) for c in raw]
                    if len(cells) < 3:
                        continue
                    if cells[1]:
                        panchayat = cells[1]
                    match = RE_WARD_AND_CATEGORY.search(cells[2]) or RE_BARE_WARD.match(
                        cells[2]
                    )
                    if not match:
                        continue
                    ward, category = match.group(1), match.group(2)
                    key = (panchayat, ward)
                    if key in seen:
                        continue
                    made = row(
                        "2022",
                        taluka,
                        panchayat or "",
                        ward,
                        category,
                        source=path.name,
                        path=path,
                        page=page.page_number,
                    )
                    if made:
                        seen[key] = made
    return list(seen.values())


def _column_bounds(page):
    """x-range of the "Ward No and Category" and "Panchayat Name" columns.

    Taken from the header words rather than assumed, because the talukas do not
    share a layout.
    """
    words = page.extract_words()
    ward = [w for w in words if w["text"].lower().startswith("ward")]
    panch = [w for w in words if w["text"].lower().startswith("panchayat")]
    cands = [w for w in words if w["text"].lower().startswith("candidates")]
    if not ward or not panch:
        return None
    ward_x = (min(w["x0"] for w in ward) - 6, max(w["x1"] for w in ward) + 42)
    panch_x = (
        min(w["x0"] for w in panch) - 6,
        min(ward_x[0], min(w["x0"] for w in panch) + 90),
    )
    right = min((w["x0"] for w in cands), default=None)
    if right:
        ward_x = (ward_x[0], min(ward_x[1], right - 4))
    return panch_x, ward_x


def _cells_in_column(page, bounds, tolerance=4):
    """Text inside an x-range, grouped into visual rows by y."""
    rows = collections.defaultdict(list)
    for w in page.extract_words():
        if bounds[0] <= w["x0"] < bounds[1]:
            rows[round(w["top"] / tolerance)].append(w)
    return [
        (key * tolerance, " ".join(x["text"] for x in sorted(v, key=lambda w: w["x0"])))
        for key, v in sorted(rows.items())
    ]


# The separator between "Ward" and its numeral is not always a space. Bicholim
# uses a soft hyphen (U+00AD) - invisible in any viewer, and not matched by
# \\s - so requiring whitespace there silently drops the whole taluka.
SEP = r"[\s\u00ad\u2010\u2011.:\-\u2013\u2014]*"
RE_WARD_ANY = re.compile(rf"WARD{SEP}(?:NO\.?)?{SEP}([IVXLC]+|\d+)", re.I)
RE_CATEGORY_ANY = re.compile(r"\(([^)]{1,25})\)")


def parse_2017(path):
    """No ruled table, and no single line layout either.

    Canacona prints the ward on its own line ("Ward VI" / "(ST)"); Pernem prints
    a bare "WARD" and buries "No. I" in the candidate row. Matching on line text
    therefore finds one taluka and silently misses the other, so this reads the
    "Ward No and Category" column by x-position and stitches its fragments back
    together by y - which does not care where the line breaks fall.
    """
    taluka = taluka_of(path, "")
    out, seen = [], set()

    with pdfplumber.open(str(path)) as pdf:
        bounds = next((b for b in (_column_bounds(p) for p in pdf.pages) if b), None)
        if not bounds:
            return out
        panch_x, ward_x = bounds

        for page in pdf.pages:
            wards = _cells_in_column(page, ward_x)
            panchayats = [
                (y, t)
                for y, t in _cells_in_column(page, panch_x)
                if re.search(r"[A-Za-z]{3}", t)
                and not re.match(r"(?i)panchayat|name|sr|no\.?$", t.strip())
            ]

            # a ward entry can straddle two or three y-bands; merge neighbours
            merged, buffer, top = [], "", None
            for y, text in wards:
                if top is not None and y - top > 26:
                    merged.append((top, buffer))
                    buffer, top = "", None
                if top is None:
                    top = y
                buffer = f"{buffer} {text}".strip()
            if buffer:
                merged.append((top, buffer))

            for y, text in merged:
                cat_match = RE_CATEGORY_ANY.search(text)
                # same spread of variants as 2022, including talukas that print
                # the numeral with no "WARD" keyword in front of it
                ward_match = RE_WARD_ANY.search(text) or RE_BARE_WARD.match(text)
                if not ward_match or not cat_match:
                    continue
                above = [t for py, t in panchayats if py <= y + 12]
                panchayat = above[-1] if above else ""
                key = (panchayat, ward_match.group(1))
                if key in seen:
                    continue
                seen.add(key)
                made = row(
                    "2017",
                    taluka,
                    panchayat,
                    ward_match.group(1),
                    cat_match.group(1),
                    source=path.name,
                    path=path,
                    page=page.page_number,
                )
                if made:
                    out.append(made)
    return out


PARSERS = {"2012": parse_2012, "2017": parse_2017, "2022": parse_2022}


def sources(year):
    """The per-taluka documents for a year, skipping gazettes and scans."""
    directory = GOA / year
    skip = (
        "elected-members",
        "resevation",
        "rservation",
        "corigendum",
        "details-pan",
        "sr.-",
        "2223-",
    )
    return [
        p
        for p in sorted(directory.glob("*.pdf"))
        if not any(s in p.name.lower() for s in skip)
    ]


@command("parse", state="Goa")
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", choices=sorted(PARSERS), action="append")
    args = ap.parse_args()
    years = args.year or sorted(PARSERS)

    for year in years:
        rows, skipped = [], []
        for path in sources(year):
            try:
                got = PARSERS[year](path)
            except Exception as exc:
                LOGGER.exception(
                    "Source parse failed",
                    extra={
                        "event": "source_parse_failed",
                        "source_file": path.name,
                        "year": year,
                        "error_type": type(exc).__name__,
                    },
                )
                got = []
            if not got:
                skipped.append(path.name)
            rows += got
            LOGGER.info(
                "Source parsed",
                extra={
                    "event": "source_parsed",
                    "source_file": path.name,
                    "year": year,
                    "source_rows": len(got),
                    "rows": len(rows),
                },
            )

        out = GOA / f"ward_reservation_{year}.csv"
        emit.write(rows, out.with_suffix(""), COLUMNS)

        talukas = {r["block"] for r in rows}
        panchayats = {(r["block"], r["gram_panchayat"]) for r in rows}
        women = sum(r["woman_reserved"] for r in rows)
        print(
            f"{year}: {len(rows)} wards, {len(panchayats)} panchayats, "
            f"{len(talukas)} talukas -> {out.name}"
        )
        print(
            f"      women-reserved {women}/{len(rows)} = "
            f"{women / max(len(rows), 1) * 100:.1f}%"
        )
        share = collections.Counter(r["reservation"] for r in rows)
        print("      " + "  ".join(f"{k}={v}" for k, v in share.most_common()))
        if skipped:
            print(f"      no rows from {len(skipped)}: {skipped}")


if __name__ == "__main__":
    main()
