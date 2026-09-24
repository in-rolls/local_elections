"""West Bengal zila parishad seats, 2018, from the delimitation gazettes.

The smallest state parsed here and the only one with a **draft and a final
printing of the same document for 19 of 20 districts**. Both are parsed and
compared, which is why this is worth doing at its size: two independent scans of
two independently typeset gazettes agreeing on the same seat is the strongest
evidence available that a scanned row was read right, and `printings_agree` is
already a column the master carries and `quality_flags` already reports.

The gazette prints five columns:

    (1) Name of Block
    (2) Number of members to be elected to the Zilla Parishad
    (3) Number, Name and area of the Constituency
    (4) Constituencies reserved for ST/SC/BC persons
    (5) Constituencies reserved for women

Columns (4) and (5) are separate, and that is the whole reason this parser reads
word positions rather than lines of text. Flattened to text, a scheduled-caste
women's seat reads "SC Women", a women's seat reads "Women", a scheduled-caste
seat reads "SC" and an open seat reads as nothing - which works until one stray
word lands between the columns and an open seat silently acquires a caste. The
column boundaries come from the gazette's own `(1) (2) (3) (4) (5)` markers.

**Column (2) is a check the document performs on itself.** It states how many
zila parishad members each block elects. Summed over a district that must equal
the number of constituencies parsed for it, and it is an entirely independent
statement - printed once per block, against constituencies enumerated one by
one. A parser that drops or invents a row fails it.
"""

import argparse
import collections
import csv
import re

from local_elections.common.normalize import label
from local_elections.common.runlog import command
from local_elections.paths import ROOT

CACHE = ROOT / "data" / "wb" / "ocr"
OUT = ROOT / "data" / "wb"
YEAR = "2018"

# "Haldibari / ZP-4", "Mathabhanga-II/ZP-5", "Cooch Behar-II / ZP-11"
#
# Searched anywhere on the line rather than matched against column (3)'s band,
# and that is the one column where position should not decide. The band is
# carried from the page that printed the header, the table shifts by a few
# pixels between pages, and "Chanchal-I / ZP-11" put its number at x=1589
# against a boundary at 1586 - three pixels into column (4), so the seat read
# as "Chanchal-I /" with no number and the row was dropped. Malda lost six
# constituencies that way and the OCR had read every one of them.
#
# Columns (4) and (5) still go by position, because there the meaning *is*
# positional: an empty cell is the fact, and nothing in the text says which
# column a bare "SC" fell in.
SEAT = re.compile(
    r"(?P<block>[A-Za-z][\w .'-]*?)\s*/\s*ZP\s*-\s*"
    r"(?P<number>\d+)\b",
    re.I,
)
MARKER = re.compile(r"^\(([1-5])\)$")
# Column (2) holds a number and nothing else. It used to be matched out of
# columns (1) and (2) joined - `"^(?P<name>[^\d].*?)\s+(?P<count>\d{1,2})$"` -
# which found the count only where the OCR happened to put block and number on
# one line, and read a fifth of what the gazette states. The columns have a
# boundary of their own and the header prints it; use it.
COUNT = re.compile(r"^\d{1,2}$")

# OCR renders these in mixed case often enough that matching is done folded.
CASTE_WORDS = {"sc": "SC", "st": "ST", "bc": "BC", "s.c": "SC", "s.t": "ST"}
WOMAN_WORDS = {"women", "woman", "wornen"}

COLUMNS = [
    "state",
    "year",
    "district",
    "block",
    "seat_no",
    "seat_id_printed",
    "tier",
    "tier_local",
    "reservation",
    "caste_reservation",
    "woman_reserved",
    "reservation_raw",
    "printings_agree",
    "script",
    "source_path",
    "source_page",
]


def words_of(path):
    """Every OCR'd word on a page, with its box, grouped into lines."""
    lines = collections.defaultdict(list)
    with path.open(encoding="utf-8", errors="replace") as fh:
        for row in csv.DictReader(fh, delimiter="\t", quoting=csv.QUOTE_NONE):
            text = (row.get("text") or "").strip()
            if not text or row.get("level") != "5":
                continue
            try:
                left, width = int(row["left"]), int(row["width"])
                top, height = int(row["top"]), int(row["height"])
                key = (int(row["block_num"]), int(row["par_num"]), int(row["line_num"]))
            except (KeyError, ValueError):
                continue
            lines[key].append(
                {"text": text, "x": left + width / 2, "y": top + height / 2}
            )
    return [sorted(v, key=lambda w: w["x"]) for _, v in sorted(lines.items())]


def column_edges(lines):
    """Where columns (4) and (5) begin, from the gazette's own markers.

    Returns None where the page does not print the header, which is every page
    after a district's first: the caller carries the previous page's edges,
    because the table is one table continued rather than a new one.
    """
    for line in lines:
        # The header rule is a line of nothing but the five markers. Merely
        # finding them somewhere on a line matched the order's own prose -
        # "specified in column (1) of the Schedule below ... entries in column
        # (2) ... column (4) and the constituency ... column (5)" - which spans
        # four OCR'd lines of page 1 and put the column boundaries in the middle
        # of a paragraph. Every seat then read as unreserved, and the row count
        # was right.
        marks = [MARKER.match(w["text"]) for w in line]
        if not all(marks) or len(marks) < 5:
            continue
        found = {m.group(1): w["x"] for m, w in zip(marks, line, strict=False)}
        if {"2", "3", "4", "5"} <= set(found):
            return (
                (found["1"] + found["2"]) / 2 if "1" in found else 0,
                (found["2"] + found["3"]) / 2,
                (found["3"] + found["4"]) / 2,
                (found["4"] + found["5"]) / 2,
            )
    return None


def read_page(path, edges):
    """The seats on one page, and the block member counts it states.

    Read as two independent regions rather than as lines of text. A block's
    member count usually sits on a line of its own - "Dubrajpur 2" - with no
    constituency beside it, so anything that only looked at lines carrying a
    seat saw three blocks of twenty and checked the gazette's arithmetic
    against a fifth of what it states.
    """
    lines = words_of(path)
    edges = column_edges(lines) or edges
    seats, members, unreadable, marks = [], [], [], []
    if edges is None:
        return seats, members, unreadable, edges
    block_edge, seat_edge, caste_edge, woman_edge = edges

    for line in lines:
        name = " ".join(w["text"] for w in line if w["x"] < block_edge).strip()
        count = " ".join(
            w["text"] for w in line if block_edge <= w["x"] < seat_edge
        ).strip()
        # The number is found anywhere on the line; the name is taken from
        # column (3). Both halves matter. A margin on the band was tried and is
        # the wrong shape of fix - ZP-11 sat 3px past the boundary and ZP-14
        # sat 94px past it, and every widening is a guess about a table that
        # moves. But reading the *name* off the whole line swept columns (1)
        # and (2) into it and produced "Cooch Behar-I 3 Cooch Behar-I".
        number_word = next(
            (w for w in line if re.match(r"^ZP\s*-?\s*\d+$", w["text"], re.I)), None
        )
        if number_word is not None:
            seat_text = " ".join(
                w["text"] for w in line if seat_edge <= w["x"] <= number_word["x"]
            ).strip()
        else:
            seat_text = " ".join(
                w["text"] for w in line if seat_edge <= w["x"] < caste_edge
            ).strip()
        middle = [w for w in line if caste_edge <= w["x"] < woman_edge]
        right = [w for w in line if w["x"] >= woman_edge]
        # Columns (4) and (5) are kept with the height they were printed at,
        # for the same reason column (2) is. A constituency's cell is several
        # lines - the seat identifier, then the grams that make it up - and the
        # gazette prints the reservation against the *cell*, which lands it on
        # the second line: "Barshal,Lachhmanpur, Ban- SC WOMEN" while the seat
        # is "Gangajalghati /ZP-4" on the line above. Reading them off the
        # seat's own line found none of them, and West Bengal parsed 819 seats
        # with every reservation empty - in a reservation corpus - while the
        # row count and the block structure were exactly right.
        for word in middle + right:
            folded = word["text"].strip(".,").lower()
            if folded in CASTE_WORDS:
                marks.append((word["y"], "caste", CASTE_WORDS[folded]))
            elif folded in WOMAN_WORDS and word["x"] >= woman_edge:
                marks.append((word["y"], "woman", True))

        # Column (2): how many members this block elects, kept with the height
        # it was printed at rather than with the name beside it.
        #
        # Joining on the name does not work and should not be made to: column
        # (1) prints "Alipurduar - II" where column (3) prints "Alipurduar-II",
        # and the OCR gives "Kaliachak-Il" with a capital i. Normalising until
        # those meet would also quietly marry a count to the wrong block, and
        # this check exists to be independent of the enumeration. The gazette
        # states the relationship geometrically - the count is centred against
        # its block's rows - so read it that way.
        if COUNT.match(count):
            middle_y = sum(
                w["y"] for w in line if block_edge <= w["x"] < seat_edge
            ) / max(1, sum(1 for w in line if block_edge <= w["x"] < seat_edge))
            members.append((middle_y, int(count)))
        elif 0 < len(count) <= 3 and name and not name.startswith("("):
            # A count that did not survive the scan, not guessed: Bankura's
            # Indpur reads "Zz" and Indus reads "Z" where the page prints 2,
            # and the only repair certain to be right is the number of
            # constituencies enumerated - the very thing this checks.
            #
            # Bounded by length because column (2) also catches the header on
            # every page: "Number of members to be elected to the Zilla
            # Parishad" is not a damaged digit, and counting it as one reported
            # 390 unreadable blocks in a state that has about 340.
            unreadable.append((name, count))

        got = SEAT.search(seat_text)
        if not got:
            continue
        block = re.sub(r"\s+", " ", got.group("block")).strip()

        seats.append(
            {
                "y": min(w["y"] for w in line),
                "block": block,
                "seat_no": got.group("number"),
                "seat_id_printed": f"{block}/ZP-{got.group('number')}",
                "caste": "NONE",
                "woman": 0,
                "raw": "",
            }
        )
    # Each mark belongs to the last seat printed at or above it: a cell runs
    # from its seat identifier down to the next one.
    seats.sort(key=lambda s: s["y"])
    for y, kind, value in sorted(marks):
        above = [s for s in seats if s["y"] <= y + 12]
        if not above:
            continue
        seat = above[-1]
        if kind == "caste":
            seat["caste"] = value
        else:
            seat["woman"] = 1
    for seat in seats:
        seat["raw"] = " ".join(
            x
            for x in (
                seat["caste"] if seat["caste"] != "NONE" else "",
                "WOMEN" if seat["woman"] else "",
            )
            if x
        )
    return seats, members, unreadable, edges


def read_document(stem, printing):
    directory = CACHE / printing
    pages = sorted(directory.glob(f"{stem}-*.tsv"))
    seats, members, unreadable = [], [], []
    # Seeded from the first page that prints the header, not from None.
    #
    # column_edges reads the boundaries off the gazette's own (1)(2)(3)(4)(5)
    # marker row, and page 1 carries the preamble and never prints it. Carrying
    # edges only forward left page 1 with none, so read_page returned nothing
    # and three districts lost their first two constituencies - Bankura's
    # Saltora/ZP-1 and Saltora/ZP-2 sat in the OCR, read perfectly, and were
    # dropped. Six seats, and all six numbered 1 or 2.
    edges = next((got for path in pages if (got := column_edges(words_of(path)))), None)
    for path in pages:
        page = int(path.stem.rsplit("-", 1)[1])
        got, block_members, bad, edges = read_page(path, edges)
        for seat in got:
            seat["source_page"] = page
        seats += got
        members += [(page, y, n) for y, n in block_members]
        unreadable += bad
    return seats, members, unreadable


def block_key(name):
    """One key for a block however its name was scanned.

    The block name is printed on every one of its constituency rows and does
    not survive identically each time: "Beldanga-II" and "Beldanga -II",
    "Suti-I" and "Suti - I", "Suti - II" and "Suti - Il" with a capital i for
    the second numeral. Each variant became a block of its own, so a block that
    elects three members enumerated one and two and failed the gazette's own
    arithmetic twice over.

    The roman tail is normalized by *length*, not by spelling, which is what
    keeps Suti-I and Suti-II apart while merging Suti-II with Suti-Il. Checked
    across all twenty districts: fifteen blocks merge and no two names whose
    numerals differ are joined.
    """
    key = re.sub(r"\s*-\s*", "-", (name or "").strip())
    key = re.sub(r"[^A-Za-z0-9-]", "", key)
    key = re.sub(r"[Il1]+$", lambda m: "I" * len(m.group()), key)
    return key.lower()


def block_name(name):
    """The block's name as the gazette prints it.

    Verified against the page rather than assumed: Murshidabad page 2 prints
    "Suti-I", "Raghunathganj-I" and "Raghunathganj-II" with no space around the
    hyphen, so "Suti - I" and "Suti - Il" are the scan's doing and tidying them
    is a reading rather than an invention. The slash before the ZP number does
    carry a space in the gazette's own typesetting - "Suti-I/ ZP-11" - which is
    why only the hyphen is touched.
    """
    tidy = re.sub(r"\s*-\s*", "-", (name or "").strip())
    return re.sub(r"[Il1]+$", lambda m: "I" * len(m.group()), tidy)


def members_by_block(seats, members):
    """{block: stated member count}, joined by where the count was printed.

    The gazette centres a block's count against that block's constituency rows,
    so the count belongs to whichever block's rows bracket it on the page. That
    is the relationship the document actually states; the block name in column
    (1) is spelt differently from the one in column (3) often enough that
    matching on it loses a fifth of the counts and would need a normaliser
    generous enough to marry a count to the wrong block.
    """
    out = {}
    for page, y, count in members:
        here = [s for s in seats if s["source_page"] == page]
        if not here:
            continue
        nearest = min(here, key=lambda s: abs(s["y"] - y))
        out.setdefault(block_key(nearest["block"]), count)
    return out


def district_of(stem):
    """The gazette names its district last, after the last dash."""
    return stem.rsplit("-", 1)[-1].strip()


def rows_for(stem, printing, agree):
    seats, _, _ = read_document(stem, printing)
    # One spelling per block in the published rows. The scan gives three names
    # for one place - "Suti-I", "Suti - I" - and the most common is the one the
    # gazette most often printed, so it is the one to keep. block_key decides
    # which names are the same place; this decides what to call it.
    spellings = collections.defaultdict(collections.Counter)
    for seat in seats:
        spellings[block_key(seat["block"])][seat["block"]] += 1
    canonical = {
        key: block_name(names.most_common(1)[0][0]) for key, names in spellings.items()
    }
    out = []
    for seat in seats:
        out.append(
            {
                "state": "West Bengal",
                "year": YEAR,
                "district": district_of(stem),
                "block": canonical.get(block_key(seat["block"]), seat["block"]),
                "seat_no": seat["seat_no"],
                "seat_id_printed": seat["seat_id_printed"],
                "tier": "zp_member",
                "tier_local": "zilla parishad member",
                "caste_reservation": seat["caste"],
                "woman_reserved": seat["woman"],
                "reservation": label(seat["caste"], seat["woman"] == 1),
                "reservation_raw": seat["raw"],
                "printings_agree": agree.get((district_of(stem), seat["seat_no"]), ""),
                "script": "latin",
                "source_path": f"data/wb/{YEAR}/"
                + ("draft/" if printing == "draft" else "")
                + f"{stem}.pdf",
                "source_page": seat["source_page"],
            }
        )
    return out


def agreement():
    """Which seats the draft and the final printing state identically."""
    by_printing = {}
    for printing in ("final", "draft"):
        directory = CACHE / printing
        if not directory.exists():
            continue
        stems = sorted({p.stem.rsplit("-", 1)[0] for p in directory.glob("*.tsv")})
        for stem in stems:
            seats, _, _ = read_document(stem, printing)
            for seat in seats:
                # keyed on the seat number within the district, not on the
                # printed identifier: the block name is OCR'd out of a scan and
                # differs by a character between printings often enough that
                # matching on it found 189 of 813 seats
                key = (district_of(stem), seat["seat_no"])
                by_printing.setdefault(key, {})[printing] = (
                    seat["caste"],
                    seat["woman"],
                )
    out = {}
    for key, got in by_printing.items():
        if len(got) == 2:
            out[key] = int(got["final"] == got["draft"])
    return out


@command("parse", state="West Bengal")
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    if not CACHE.exists():
        raise SystemExit(f"no OCR cache at {CACHE}; run scripts/wb/ocr.py")

    agree = agreement()
    rows, checked, failed = [], 0, []
    stems = sorted({p.stem.rsplit("-", 1)[0] for p in (CACHE / "final").glob("*.tsv")})
    skipped = 0
    # Whether a disagreement means a lost seat or a misfiled one is decided by
    # this: the constituencies are numbered 1..N across a district, so a
    # complete run means nothing is missing however the blocks are attributed.
    seat_numbers = collections.defaultdict(list)
    for stem in stems:
        got = rows_for(stem, "final", agree)
        rows += got
        seat_numbers[district_of(stem)] = [
            int(r["seat_no"]) for r in got if r["seat_no"].isdigit()
        ]
        # the gazette's own arithmetic: each block states how many members it
        # elects, and the constituencies are enumerated separately
        seats, members, unreadable = read_document(stem, "final")
        stated_by_block = members_by_block(seats, members)
        if stated_by_block:
            checked += 1
            # Per block, not summed over the district. A district total hides
            # which block disagrees, and it breaks entirely when one block's
            # count did not survive the scan: the stated side is then short by
            # that block while the enumerated side is not, and every district
            # with one bad digit reads as a parse failure. Bankura had exactly
            # that - "Zz" for Indpur's 2.
            seen = collections.Counter()
            for row in got:
                seen[block_key(row["block"])] += 1
            for block, stated in sorted(stated_by_block.items()):
                counted = seen.get(block)
                if counted is None or stated != counted:
                    failed.append((district_of(stem), block, stated, counted))
            skipped += len(unreadable)

    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"zp_member_{YEAR}.csv"
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(
            fh, fieldnames=COLUMNS, extrasaction="ignore", lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(rows)

    if not args.quiet:
        agreed = sum(1 for r in rows if r["printings_agree"] == 1)
        both = sum(1 for r in rows if r["printings_agree"] != "")
        print(f"  {len(rows):,} zila parishad seats across {len(stems)} districts")
        print(
            f"  {both:,} seats printed twice; {agreed:,} agree "
            f"({100.0 * agreed / both:.1f}%)"
            if both
            else "  no district printed twice"
        )
        if skipped:
            print(
                f"  {skipped} block(s) whose member count did not survive "
                f"the scan; not guessed, and left out of the check below"
            )
        holes = sum(
            len(set(range(1, max(n) + 1)) - set(n)) for n in seat_numbers.values() if n
        )
        if failed:
            print(
                f"  {len(failed)} block(s) where the stated member count and "
                f"the constituencies enumerated disagree - "
                + (
                    "every district's seat numbers still run 1..N with no "
                    "holes, so these are seats filed under the wrong block, "
                    "not seats missing"
                    if not holes
                    else f"and {holes} seat number(s) are missing outright"
                )
            )
            for district, block, stated, counted in failed[:12]:
                print(
                    f"     {district}/{block}: states {stated}, "
                    f"enumerates {counted if counted is not None else 0}"
                )
            if len(failed) > 12:
                print(f"     ... and {len(failed) - 12} more")
        else:
            print(
                "  every block's stated member count matches the "
                "constituencies enumerated for it"
            )


if __name__ == "__main__":
    main()
