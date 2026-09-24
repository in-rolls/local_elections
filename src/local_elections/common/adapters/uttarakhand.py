"""Uttarakhand, from local_elections_uttarakhand.

Three cycles - 2008, 2014, 2019 - across three rural tiers, in one file plus a
second holding Haridwar alone. The districts do not overlap, so the two are read
together rather than one being preferred.

The file is candidate-level with the seat's result denormalised onto every row:
each candidate carries the winner's name and votes, the runner-up's name and
votes, and the margin, all repeated. That is the shape this repository's wide
and long tables were built for - the seat facts come off any row of the seat,
the candidates are the rows themselves - so nothing has to be inferred here.
`winner_basis` is `published` throughout.

The work is the reservation vocabulary. Uttarakhand abbreviates with a
Devanagari zero where a full stop would go: `अनु0जा0महिला`, `अ0पि0व0महिला`,
`अनु0ज0जा0`. 28 spellings of four categories, and 1,228 rows of them read as no
category at all until `normalize.py` covered them. Two read as the *wrong*
category - `अनु0ज0जाति` is janjati abbreviated, and the jati pattern matched it
first. That fix lives in normalize with the rest of the Devanagari, not here,
because Uttarakhand is not the only state that will print these.

Provenance is `dataset`: the parse recorded no document and no page.
"""

import csv
import pathlib
import re

from local_elections.common import collapse, normalize
from local_elections.common.normalize import label

REPO = "local_elections_uttarakhand"
URL = "https://github.com/in-rolls/local_elections_uttarakhand"
STATE = "Uttarakhand"

# Haridwar is held in its own file and its districts do not appear in the main
# one, so both are read. It also polled in different years - 2010 and 2015
# against the rest of the state's 2008, 2014 and 2019 - so it lands in slices of
# its own rather than being folded into a cycle it did not vote in.
FILES = [
    "data/uttarakhand-panchayat-elections.csv",
    "data/uttarakhand-panchayat-elections-haridwar.csv",
]

DECLARED = {
    "data/uttarakhand-panchayat-elections.csv": 106382,
    "data/uttarakhand-panchayat-elections-haridwar.csv": 10132,
}

POST = "निर्वाचित पद"
TIERS = {
    "प्रधान (ग्राम पंचायत)": ("gp_head", "pradhan"),
    "सदस्‍य (क्षेत्र पंचायत)": ("block_member", "kshetra panchayat sadasya"),
    "सदस्‍य (जिला पंचायत)": ("zp_member", "zila panchayat sadasya"),
}

C = {
    "district": "जनपद",
    "block": "विकास खण्‍ड",
    "panchayat": "ग्राम पंचायत",
    "reservation": "आरक्षण स्थिति",
    "winner": "विजयी प्रत्‍याशी का नाम",
    "winner_votes": "प्राप्‍त मत",
    "runner_up": "प्रथम रनर अप प्रत्‍याशी का नाम",
    "runner_up_votes": "प्राप्‍त मत.1",
    "margin": "मतों का अन्‍तर",
    "block_ward": "क्षेत्र पंचायत वाडॅ",
    "zp_ward": "जिला पंचायत वाडॅ",
    "unopposed": "निर्विरोध निर्वाचित",
    "candidate": "अभ्‍यर्थी का नाम",
    "relation": "पिता/पति का नाम",
    "symbol": "चुनाव चिन्‍ह.2",
    "votes": "प्राप्‍त मत.2",
    "serial": "क्रमांक",
}

# What the two files collapse to, per (year, tier). Declared because a wrong
# seat key produces a plausible number either way.
SEATS = {
    ("2008", "gp_head"): 6368,
    ("2008", "block_member"): 2943,
    ("2008", "zp_member"): 371,
    ("2014", "gp_head"): 6621,
    ("2014", "block_member"): 2885,
    ("2014", "zp_member"): 386,
    ("2019", "gp_head"): 5846,
    ("2019", "block_member"): 2674,
    ("2019", "zp_member"): 347,
    # Haridwar, which polls on its own cycle
    ("2010", "gp_head"): 314,
    ("2010", "block_member"): 219,
    ("2010", "zp_member"): 42,
    ("2015", "gp_head"): 308,
    ("2015", "block_member"): 221,
    ("2015", "zp_member"): 47,
}


def slices(root):
    root = pathlib.Path(root)
    csv.field_size_limit(10**7)

    raw = []
    for relative in FILES:
        path = root / relative
        if not path.exists():
            continue
        with path.open(encoding="utf-8", errors="replace") as fh:
            rows = list(csv.DictReader(fh))
        expected = DECLARED.get(relative)
        if expected is not None and len(rows) != expected:
            raise SystemExit(
                f"{REPO}: {relative} holds {len(rows):,} records, "
                f"{expected:,} declared - the sibling changed"
            )
        raw += [convert(r, relative) for r in rows]

    grouped = {}
    for row in raw:
        if row is None:
            continue
        grouped.setdefault((row["year"], row["tier"]), []).append(row)

    for (year, tier), candidates in sorted(grouped.items()):
        split_shared_names(candidates)
        seats = collapse.to_seats(candidates, ["_key"], vote_field="votes")
        expected = SEATS.get((year, tier))
        if expected is not None and len(seats) != expected:
            raise SystemExit(
                f"{REPO}: {year}/{tier} collapses to {len(seats):,} seats, "
                f"{expected:,} declared - the seat key changed"
            )
        for seat in seats:
            # The result is stated on every row of the seat, so it is read off
            # rather than worked out from the votes.
            seat["winner_basis"] = "published" if seat["winner"] else ""
            for row in [seat] + seat["seat_members"]:
                row.pop("_key", None)
        yield {
            "dataset_id": f"uttarakhand/{tier}/{year}",
            "state": STATE,
            "rows": seats,
            "provenance_level": "dataset",
            "unit_of_observation": "seat_from_candidates",
        }


def split_shared_names(candidates):
    """Two panchayats in one block printed under one name are two panchayats.

    Nine gram panchayat seats - six in 2008, three in 2019 - carry two different
    reservations under a single (district, block, panchayat) key. That is not a
    seat whose reservation changed; it is one name identifying two places, which
    the file gives nothing else to tell apart. They are split on the reservation
    and flagged, rather than merged into a seat that never existed or dropped.

    `collapse.to_seats` would raise on them, which is what it is for. Deciding
    what to do about a conflict is the adapter's job, because only the adapter
    knows what the state's file can and cannot distinguish.
    """
    varies = collapse.varies(candidates, ["_key"])
    if not varies:
        return
    for candidate in candidates:
        if (candidate["_key"],) in varies:
            candidate["_key"] = candidate["_key"] + (
                candidate["caste_reservation"],
                candidate["woman_reserved"],
            )
            candidate["shared_place_name"] = 1


# A block or zila constituency is printed as its number and its name run
# together, and the state prints that four different ways across 10,135 rows:
#
#   7,132   17-गुलडिया / 04. कछियौला   number, separator, name
#   1,395   2 गराली                    number, space, name
#     442   कुणीधार-4                  name, hyphen, number - the order reversed
#       8   18कुण्डादानकोट              number, no separator at all
#      19   पटरानी                     no number anywhere
#
# The whole string used to go into seat_no, which the dictionary declares an
# integer, and into ward_name as well, so the two columns were byte-identical
# and neither was usable as a number.
#
# The order these are tried in matters, and so does giving up. Extracting a
# number is not worth guessing at: seat_no is part of SEAT_FIELDS, so a wrong
# reading does not just mis-number a seat, it merges it with a different one.
CONSTITUENCY = (
    re.compile(r"^\s*(?P<no>\d+)\s*[-.]\s*(?P<name>.+?)\s*$"),
    re.compile(r"^\s*(?P<no>\d+)\s+(?P<name>.+?)\s*$"),
    re.compile(r"^\s*(?P<no>\d+)(?P<name>\D.*?)\s*$"),
    # reversed: the number trails the name. Anchored to the end so the internal
    # zeros of a Devanagari abbreviation - बा0ल0ढनौलासेरा-21 is बा० ल० - cannot
    # be mistaken for it.
    re.compile(r"^\s*(?P<name>.+?)\s*[-–]\s*(?P<no>\d+)\s*$"),
)


def constituency(value):
    for pattern in CONSTITUENCY:
        found = pattern.match(value or "")
        if found:
            return str(int(found.group("no"))), found.group("name")
    return "", (value or "")


def constituency_no(value):
    return constituency(value)[0]


def constituency_name(value):
    return constituency(value)[1]


def convert(row, relative):
    """One candidate, with the seat's stated result carried alongside."""
    post = (row.get(POST) or "").strip()
    if post not in TIERS:
        return None
    tier, tier_local = TIERS[post]
    stated = (row.get(C["reservation"]) or "").strip()
    caste = normalize.caste_of(stated)
    woman = normalize.woman_of(stated)
    district = (row.get(C["district"]) or "").strip()
    block = (row.get(C["block"]) or "").strip()
    panchayat = (row.get(C["panchayat"]) or "").strip()
    block_ward = (row.get(C["block_ward"]) or "").strip()
    zp_ward = (row.get(C["zp_ward"]) or "").strip()
    year = (row.get("Year") or "").strip()
    return {
        "_key": (year, tier, district, block, panchayat, block_ward, zp_ward),
        "state": STATE,
        "year": year,
        "tier": tier,
        "tier_local": tier_local,
        "district": district,
        "block": block,
        # a block or district seat is a numbered ward of that body and has no
        # panchayat, so the ward is the whole of its identity
        "gram_panchayat": panchayat,
        "ward_name": constituency_name(block_ward or zp_ward),
        "seat_no": constituency_no(block_ward or zp_ward),
        "caste_reservation": caste or "",
        "caste_reservation_local": stated,
        # The vocabulary pairs every category with a महिला form, so a label
        # without one states that the seat is not reserved for a woman.
        "woman_reserved": "" if (caste is None and woman is None) else int(woman == 1),
        "gender_stated": "" if (caste is None and woman is None) else 1,
        "reservation": label(caste or "NONE", woman == 1) if stated else "",
        "reservation_raw": stated,
        "script": "devanagari",
        # every candidate row repeats the seat's result
        "winner": (row.get(C["winner"]) or "").strip(),
        "winner_votes": collapse.votes_of(row.get(C["winner_votes"])),
        "runner_up": (row.get(C["runner_up"]) or "").strip(),
        "runner_up_votes": collapse.votes_of(row.get(C["runner_up_votes"])),
        "margin": collapse.votes_of(row.get(C["margin"])),
        "source_path": relative,
        "source_page": "",
        # the long form
        "candidate_name": (row.get(C["candidate"]) or "").strip(),
        "relation_name": (row.get(C["relation"]) or "").strip(),
        "party": (row.get(C["symbol"]) or "").strip(),
        "votes": collapse.votes_of(row.get(C["votes"])),
    }
