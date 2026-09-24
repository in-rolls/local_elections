"""Karnataka's 2016 taluk and zilla panchayat members, from the OCR cache.

Two tiers Karnataka contributes nothing to today. Its existing rows are gram
panchayat reservation rosters for 1993-2007, which name no winner by
construction; these name one on every row, and the party as well.

Reading the HTML is `tables.py`, tested on its own. This is everything that is
about Karnataka rather than about tables: where the district and taluk come
from, which office the seat is, and what has to hold before a row is written.

**The place comes from the filename, and that is a decision worth seeing.** The
document's own header states the district and taluk too, but in Kannada and
through the same OCR as everything else - Siruguppa's own name comes back as
"ಸಿದುಗುಪ್ಪ" on one page and "ಸಿರ್ಯಪ್ಪ" on another. The archive path is exact and
was never scanned. So the filename is the source, and what the printed column
can check is whether a document agrees with *itself* - comparing it to the
Latin filename would score near zero however right the document was.

**The seat numbers are the completeness check.** A taluk's constituencies are
numbered consecutively, so a page lost to a bad read shows up as a gap rather
than as a plausibly short table. Four documents currently lose a seat where a
row straddles a page break, and that is reported rather than smoothed over.
"""

import argparse
import collections
import re
import sys

import tables

from local_elections.common import emit
from local_elections.common.runlog import command
from local_elections.paths import ROOT

CACHE = ROOT / "data" / "karnataka" / "ocr"
DOCUMENTS = ROOT / "data" / "karnataka" / "tzp_2016_elected"
OUT = ROOT / "data" / "karnataka"

YEAR = 2016

# The archive names districts as the commission's webmaster did: some
# abbreviated, some by their headquarters, some in a spelling the state has
# since changed. Mapped to the name the Local Government Directory uses, so a
# row joins to the register these are checked against.
DISTRICTS = {
    "bagalakote": "Bagalkot",
    "ballari": "Ballari",
    "belagavi": "Belagavi",
    "bidar": "Bidar",
    "chamarajanagara": "Chamarajanagar",
    "chikkaballapur": "Chikkaballapur",
    "chikkaballapura": "Chikkaballapur",
    "chikkamagalur": "Chikkamagaluru",
    "chikmagaluru": "Chikkamagaluru",
    "chitradurga": "Chitradurga",
    "dk": "Dakshina Kannada",
    "davangere": "Davanagere",
    "dvg": "Davanagere",
    "dharwad": "Dharwad",
    "gadag": "Gadag",
    "hassan": "Hassan",
    "haveri": "Haveri",
    "kalaburagi": "Kalaburagi",
    "kodagu": "Kodagu",
    # the district is Kodagu; Madikeri is its headquarters and also a taluk
    "madikeri": "Kodagu",
    "kolar": "Kolar",
    "koppal": "Koppal",
    "mandya": "Mandya",
    "mysore": "Mysuru",
    "raichur": "Raichur",
    "ramanagara": "Ramanagara",
    "rural": "Bangalore Rural",
    "shivamogga": "Shivamogga",
    "tumkur": "Tumakuru",
    "udupi": "Udupi",
    "uk": "Uttara Kannada",
    "urban": "Bangalore Urban",
    "bangalore": "Bangalore Urban",
    "vijayapura": "Vijayapura",
    "yadgir": "Yadgir",
    "yadagiri": "Yadgir",
}

TIERS = {
    "TP": ("block_member", "taluk panchayat member"),
    "ZP": ("zp_member", "zilla panchayat member"),
}

STEM = re.compile(r"^TZP_Elected_Members_2016_(TP|ZP)_(.+)$")


def place(stem):
    """(office, district, taluk) from an archive filename, or None."""
    match = STEM.match(stem)
    if not match:
        return None
    office, rest = match.groups()
    parts = [p for p in rest.split("_") if p]
    district = DISTRICTS.get(parts[0].lower())
    if district is None:
        return None
    taluk = " ".join(parts[1:]).strip() if len(parts) > 1 else ""
    if office == "ZP":
        # a zilla panchayat's constituencies span the district; there is no
        # taluk, and where the filename carries a second part it is the
        # district's own qualifier - ZP_Bangalore_Urban
        taluk = ""
    return office, district, taluk


def rows_of_document(stem, text):
    """Every seat a document states, before the checks."""
    located = place(stem)
    if located is None:
        return []
    office, district, taluk = located
    tier, tier_local = TIERS[office]
    source = DOCUMENTS / f"{stem}.pdf"
    archive = emit.archived(DOCUMENTS)
    out = []
    for page_no, page in enumerate(text.split("\f"), 1):
        for cells, layout in tables.table_rows(page):
            parsed = tables.reservation(cells[layout["reservation"]])
            if parsed is None:
                continue
            caste, caste_local, woman = parsed
            number, name = tables.seat(cells[layout["seat"]])
            # the four-column form prints no serial; numbered() then has
            # nothing to fall back on, which is correct - that form always
            # carries the constituency number in the seat cell itself
            serial = None
            if "serial" in layout:
                serial, _ = tables.seat(cells[layout["serial"]] + "-")
            printed_party = cells[layout["party"]]
            row = {
                "state": "Karnataka",
                "year": YEAR,
                "tier": tier,
                "tier_local": tier_local,
                "district": district,
                "block": taluk,
                "seat_no": number,
                "ward_name": name,
                "caste_reservation": caste,
                "caste_reservation_local": caste_local,
                "woman_reserved": int(woman),
                "reservation": (
                    f"{caste + ' ' if caste != 'NONE' else ''}"
                    f"{'Woman' if woman else 'Other than Woman'}"
                ),
                "reservation_raw": cells[layout["reservation"]],
                "winner": winner_name(cells[layout["winner"]]),
                "relation_name": winner_relation(cells[layout["winner"]]),
                "winner_address": winner_address(cells[layout["winner"]]),
                "party": tables.party(printed_party),
                "party_local": printed_party,
                "script": "kannada",
                "text_source": "ocr",
                # the taluk the page itself printed, where it has that column,
                # so the filename can be checked rather than trusted
                "taluk_printed": (cells[layout["taluk"]] if "taluk" in layout else ""),
            }
            row["_serial"] = serial
            out.append(emit.stamp(row, source, page_no, ROOT, archive))
    return numbered(out)


def numbered(rows):
    """Fill in the constituency number where the seat cell does not carry one.

    Three layouts, not two. Badami prints a running serial and then the
    constituency as "1-ನೀರಬೂದಿಹಾಳ"; Chamarajanagara prints the constituency
    number in the first column and the bare name in the second. 522 of the
    first 1,500 rows came from the second kind and had no seat number at all -
    which the contiguity check could not see, because it only looked at
    documents that had numbers to check.

    The serial is only adopted where it behaves like a constituency number:
    running 1..N once across the whole document. That test matters because it
    is not always true - Siruguppa restarts its serial at 1 on page 3 while the
    constituency there is 16, and taking the serial for that document would
    have renumbered half a taluk onto seats that already exist.
    """
    if all(r["seat_no"] for r in rows) or not rows:
        return rows
    serials = [r.get("_serial") for r in rows]
    if None not in serials and serials == list(range(1, len(serials) + 1)):
        for row in rows:
            if not row["seat_no"]:
                row["seat_no"] = row["_serial"]
                row["seat_no_from_serial"] = 1
    return rows


# A winner's cell holds up to three things and the gazette marks the joins.
#
#   ಮಲ್ಲಮ್ಮ ಶಿದ್ರಾಮಪ್ಪ ಯತ್ನಟ್ಟಿ <br/> ಸಾ: ಯಂಡಿಗೇರಿ ತಾ: ಬದಾಮಿ
#   ಶುಭಲತಾ ಶೆಟ್ಟಿ  ಕೋಂ ರಘುನಾಥ ಶೆಟ್ಟಿ,  ಮ.ನಂಬ್ರ 1-99, ಗುರುಪುರ
#
# RELATION is who they are named as belonging to - ಬಿನ್ and ತಂದೆ son-of, ಕೋಂ
# and ಗಂಡ wife-of - and the corpus already has relation_name for exactly that.
# Reading it as part of the address was the first mistake here and reading it
# as part of the *name* was the second: it left 296 rows with a winner over the
# 60 characters the dictionary allows, the longest 129.
#
# The line break is tried first because it is the only marker that is always
# right where it appears; the words are the fallback for cells that came back
# without one.
# ಜಿನ್ and ಕಂದ are not words; they are ಬಿನ್ and ಗಂಡ through the same consonant
# confusion that turns ಸೂ into ಕೂ elsewhere in these scans. Listed rather than
# fuzzy-matched because there are four real markers and a token-by-token
# similarity pass would be a lot of machinery for a closed set of six strings.
RELATION = re.compile(r"\s*(?:ಬಿನ್|ಜಿನ್|ತಂದೆ|ತೆಂದೆ|ಕೋಂ|ಗಂಡ|ಕಂದ|ಬಿ\s*[/.]\s*ಒ|ಸಿ\s*[/.]\s*ಒ)\s")
ADDRESS = re.compile(
    r"\s*(?:ಸಾ\s*[:.]|ಮು\s*[:.]|ವಾಸ\s*[:.]|ತಾ\s*[:.]|ಗ್ರಾಮ\b|"
    r"ಮ\s*[.]?\s*ನಂ|ಮನೆ\s*ನಂ|ವಾರ್ಡ್)"
)


def _split(cell):
    """(name, relation, address) from one winner cell."""
    text = tables.clean(cell, keep_breaks=True)
    head, _, tail = text.partition(tables.LINE_BREAK)
    tail = tail.replace(tables.LINE_BREAK, " ")

    parts = ADDRESS.split(head, 1)
    if len(parts) > 1:
        head, tail = parts[0], f"{parts[1]} {tail}"

    parts = RELATION.split(head, 1)
    name = parts[0]
    relation = parts[1] if len(parts) > 1 else ""
    if relation:
        bits = ADDRESS.split(relation, 1)
        if len(bits) > 1:
            relation, tail = bits[0], f"{bits[1]} {tail}"
    return (name.strip(" ,.-"), relation.strip(" ,.-"), tail.strip(" ,.-"))


def winner_name(cell):
    return _split(cell)[0]


def winner_relation(cell):
    return _split(cell)[1]


def winner_address(cell):
    return _split(cell)[2]


def silent_pages(files):
    """(document, page) for every page that produced no row.

    A document that yields nothing is obvious; a page that yields nothing
    inside a document that otherwise parses is not, and both of the readings
    this parser got wrong were on such a page. The OCR already marks a page it
    could not read; this marks a page nobody could parse, which is a different
    failure and just as quiet.
    """
    out = []
    for path in files:
        text = path.read_text(encoding="utf-8")
        for page_no, page in enumerate(text.split("\f"), 1):
            if not tables.table_rows(page):
                out.append((path.stem, page_no, "ocr-unread" in page))
    return out


def gaps(rows):
    """Missing and repeated constituency numbers, per document."""
    by_document = collections.defaultdict(list)
    for row in rows:
        if row.get("seat_no"):
            by_document[row["source_pdf"]].append(row["seat_no"])
    report = {}
    for document, seats in by_document.items():
        highest = max(seats)
        missing = sorted(set(range(1, highest + 1)) - set(seats))
        repeated = [n for n, c in collections.Counter(seats).items() if c > 1]
        if missing or repeated:
            report[document] = (highest, missing, repeated)
    return report


def disagreements(rows):
    """Documents whose pages do not print one taluk name.

    Not a comparison against the filename, which was the first version of this
    and could never have passed: the filename is Latin and the page is Kannada,
    so difflib scores every pair near zero whatever the document says. A check
    that can only fire is worth as little as one that can only pass.

    What the printed column can answer is whether the document agrees with
    itself. Most do - Ballari prints ಬಳ್ಳಾರಿ on all 28 of its rows, Kudligi
    ಕೂಡ್ಲಿಗಿ on all 26. Where they do not, the disagreement is the finding:
    Sandur reads ಸಂಡೂರು and ಸಂದೂರು, one character apart, which is scan noise;
    Hospet reads ಹೊಸಪೇಟೆ and ಕನ್ನಡವೇಚಿ, which is not the same word and is why
    the place is taken from the archive path rather than from the page.
    """
    printed = collections.defaultdict(collections.Counter)
    for row in rows:
        value = tables.clean(row.get("taluk_printed", ""))
        if value:
            printed[row["source_pdf"]][value] += 1
    out = []
    for document, spellings in printed.items():
        if len(spellings) < 2:
            continue
        (main, _), *rest = spellings.most_common()
        for other, count in rest:
            out.append(
                (document, main, other, count, bool(tables.nearest(other, {main: 1})))
            )
    return out


COLUMNS = [
    "state",
    "year",
    "tier",
    "tier_local",
    "district",
    "block",
    "seat_no",
    "ward_name",
    "caste_reservation",
    "caste_reservation_local",
    "woman_reserved",
    "reservation",
    "reservation_raw",
    "winner",
    "relation_name",
    "winner_address",
    "party",
    "party_local",
    "script",
    "text_source",
    "seat_no_from_serial",
]


@command("parse", state="Karnataka", series="taluka_zilla_results")
def main():
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("--only", help="substring of the filename")
    args = ap.parse_args()

    rows = []
    files = sorted(CACHE.glob("TZP_Elected_Members_2016_*.txt"))
    if args.only:
        files = [f for f in files if args.only.lower() in f.name.lower()]
    for path in files:
        rows.extend(rows_of_document(path.stem, path.read_text(encoding="utf-8")))

    # Which of two readings of one seat survives, when they disagree. A row
    # whose party resolved against the fixed list is a row whose cells were
    # read cleanly, so it is better evidence than one that came first.
    def read_cleanly(row):
        return (bool(row["party"]), bool(row["winner"]), bool(row["caste_reservation"]))

    kept, conflicts = tables.dedupe(
        rows,
        key=lambda r: (r["source_pdf"], r["seat_no"]) if r["seat_no"] else None,
        better=read_cleanly,
    )

    # before the column is dropped: kept holds the same objects as rows, so
    # popping first left the check with almost nothing to read and it reported
    # a cheerful "1 of 1"
    clashes = disagreements(rows)
    carrying = len(
        {r["source_pdf"] for r in rows if tables.clean(r.get("taluk_printed", ""))}
    )
    for row in kept:
        row.pop("taluk_printed", None)
        row.pop("_serial", None)
    by_tier = collections.Counter(r["tier"] for r in kept)
    for tier in sorted(by_tier):
        subset = [r for r in kept if r["tier"] == tier]
        stem = OUT / f"{tier}_{YEAR}"
        emit.write(subset, stem, COLUMNS)
        print(f"  {len(subset):>5} rows -> {stem.relative_to(ROOT)}.csv")

    documents = len({r["source_pdf"] for r in kept})
    women = sum(1 for r in kept if r["woman_reserved"])
    named = sum(1 for r in kept if r["winner"])
    partied = sum(1 for r in kept if r["party"])
    print(f"\n{len(kept)} rows from {documents} of {len(files)} documents")
    print(f"  winner named   {named:>5} ({named / max(len(kept), 1):.1%})")
    print(f"  party resolved {partied:>5} ({partied / max(len(kept), 1):.1%})")
    print(
        f"  woman-reserved {women:>5} "
        f"({women / max(len(kept), 1):.1%}; the Act requires 50%)"
    )

    quiet = silent_pages(files)
    total_pages = sum(len(f.read_text(encoding="utf-8").split("\f")) for f in files)
    unread = sum(1 for _, _, was_unread in quiet if was_unread)
    print(
        f"\n{total_pages - len(quiet)} of {total_pages} pages produced rows; "
        f"{len(quiet)} did not ({unread} of those the OCR had already marked "
        f"unread)"
    )
    for stem, page_no, was_unread in quiet[:8]:
        print(
            f"  {stem[-38:]:40s} p{page_no}" + ("  (ocr-unread)" if was_unread else "")
        )
    if len(quiet) > 8:
        print(f"  ... and {len(quiet) - 8} more")

    missing = gaps(kept)
    print(
        f"\nseat numbers contiguous in {documents - len(missing)} of "
        f"{documents} documents"
    )
    for document, (highest, absent, repeated) in sorted(missing.items()):
        print(
            f"  {document[-38:]:40s} 1..{highest}: missing {absent[:8]}"
            + (f" repeated {repeated}" if repeated else "")
        )
    if conflicts:
        print(f"\n{len(conflicts)} seats stated twice with different content:")
        for first, second in conflicts[:5]:
            print(
                f"  seat {first['seat_no']} of {first['source_pdf'][-30:]}: "
                f"{first['winner'][:24]!r} vs {second['winner'][:24]!r}"
            )
    print(
        f"\nprinted taluk agrees with itself in "
        f"{carrying - len({c[0] for c in clashes})} of {carrying} documents "
        f"that print one"
    )
    for document, main, other, count, close in clashes:
        note = "one scan apart" if close else "NOT THE SAME NAME"
        print(f"  {document[-34:]:36s} {main} vs {other} x{count}  ({note})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
