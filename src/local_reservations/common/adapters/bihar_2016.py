"""Bihar 2016, from the sibling's re-collection of the archived results form.

The original 2016 scrape kept its rows and nothing else: no document, no page,
no codes, and no statement of which election it covered. The adapter that read
it had to work around all of that - key seats on a ward's printed name because
there was no ward code, fold 651 seats the scrape had captured twice and guess
which reading was later, and declare the year from outside the data.

The sibling has since re-collected the same form and kept every page: 258,095
seats, 644,865 candidate rows and 258,742 saved responses, validated against a
declared schema and compared cell for cell with the original scrape, which
agrees on 644,849 of its 644,958 distinct rows. So none of those workarounds
are needed here. A seat is identified by the codes the form itself uses, the
year is stated in the release manifest, and a row points at the page it came
from.

Two things this still has to get right.

**A seat with no stated reservation is not an unreserved seat.** The form
prints no reservation on a page that answers "Record not Found", and 30,764 of
the 258,095 seats answer that way. They are counted and left out rather than
entering the corpus as open seats.

**A tie that nothing resolves names no winner.** The 2016 form has no winner
flag, so a winner is the uncontested candidate, the one the form marks as
having drawn the lot, or the highest vote. Where two candidates share the top
vote and no lot is marked, the release names nobody and says why in
`winner_note`; 402 seats are in that position and carry no winner here either.

**Twenty-one samiti and zila parishad seat numbers are listed twice**, under
dropdown codes differing only in how the number is padded - "Tardih/01" and
"Tardih/1". In nineteen of them exactly one code carries results and the other
answers "Record not Found", which is what one seat entered twice looks like; in
two, both carry results. Which code is the seat cannot be settled from the form,
so both rows are kept and the corpus's collision ledger records them.

Bihar elects a gram kachahari - a village court - beside the gram panchayat, so
its sarpanch and panch are not this state's gram panchayat head and ward.
"""

import collections
import hashlib
import json

import pyarrow.parquet as pq

from local_reservations.common import normalize
from local_reservations.common.normalize import label

RELEASE = "data/release/2016_panchayat"
SHA256 = {
    "seats.parquet": (
        "5f234dad9afc7603e37aa34401ff4210fee31e6448cb8f94d79737a667d1761c"
    ),
    "candidates.parquet": (
        "0b73373fce5b29292c61399b3308d44b95f850f17127f5c2e6bfef3e162f65ca"
    ),
    "winners.parquet": (
        "1f1712f0a91370cb3db6a4b891d419a60cd81a4a7dbc00c57ea04e4fc14aeb13"
    ),
}
DECLARED = {
    "seats.parquet": 258095,
    "candidates.parquet": 644865,
    "winners.parquet": 210717,
}
# The office the form lists, to the canonical tier and the name Bihar prints.
OFFICES = {
    "ward_member": ("gp_ward", "ward member"),
    "panch": ("kachahari_member", "panch"),
    "mukhiya": ("gp_head", "mukhiya"),
    "sarpanch": ("kachahari_head", "sarpanch"),
    "panchayat_samiti_member": ("block_member", "panchayat samiti member"),
    "zila_parishad_member": ("zp_member", "zila parishad member"),
}
WARD_TIERS = {"gp_ward", "kachahari_member"}
PANCHAYAT_TIERS = {"gp_head", "kachahari_head", "gp_ward", "kachahari_member"}
# Samiti and zila parishad seats are numbered territorial constituencies; a
# mukhiya's or sarpanch's seat is the panchayat itself and carries no number.
NUMBERED_TIERS = {"block_member", "zp_member"}
HEAD_TIERS = {"gp_head", "kachahari_head"}
# How the release says a winner was decided, in this corpus's vocabulary.
BASIS = {
    "uncontested": "uncontested",
    "lot": "lot",
    "top_vote": "argmax_votes",
}
KEY = ["office", "district_code", "block_code", "panchayat_code", "unit_code"]
YEAR = "2016"
STATE = "Bihar"
REPO = "local_elections_bihar"
URL = "https://github.com/in-rolls/local_elections_bihar"


def read_release(root):
    """Every declared table, refused if a byte, a count or a column moved."""
    directory = root / RELEASE
    manifest = json.loads((directory / "MANIFEST.json").read_text())
    if manifest["year"] != 2016:
        raise ValueError("Bihar release is not explicitly dated 2016")
    published = {info["path"]: info for info in manifest["files"]}
    data = {}
    for name, digest in SHA256.items():
        if name not in published:
            raise ValueError(f"Bihar release no longer publishes {name}")
        info = published[name]
        path = directory / name
        if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError(f"Bihar release checksum changed: {name}")
        if info["sha256"] != digest:
            raise ValueError(f"Bihar manifest disagrees with pinned input: {name}")
        table = pq.read_table(path)
        if len(table) != DECLARED[name] or len(table) != info["rows"]:
            raise ValueError(f"Bihar release count changed: {name}")
        # Compared by name and order; the types cannot move without the bytes
        # moving, and the bytes are pinned above.
        if table.schema.names != list(info["schema"]):
            raise ValueError(f"Bihar release columns changed: {name}")
        data[name] = table.to_pylist()
    return data


def seat_key(row):
    return tuple(row[name] for name in KEY)


def text(value):
    return "" if value is None else str(value).strip()


def serial(code):
    """The seat's number off the end of its code.

    Samiti seats are coded by the block they sit in and their number within it,
    "Piprasi/01", so the number has to be taken off the end; every other office
    codes the seat by its number alone. The printed code is kept whole in
    `seat_id_printed`.
    """
    # One samiti code pads its number: "Jehanabad/    10".
    digits = text(code).rsplit("/", 1)[-1].strip().lstrip("0")
    return digits or text(code)


def convert(tables):
    """Seat rows for every office, with the candidates the form listed.

    Returns the rows and the seats left out for want of a stated reservation.
    """
    winners = {}
    for row in tables["winners.parquet"]:
        if seat_key(row) in winners:
            raise ValueError("More than one Bihar winner for a seat")
        winners[seat_key(row)] = row
    members = collections.defaultdict(list)
    for row in tables["candidates.parquet"]:
        members[seat_key(row)].append(row)

    # Seat numbers listed under more than one form code in the same parent; the
    # key cannot tell them apart, so they are flagged rather than merged.
    padded = collections.defaultdict(set)
    for unit in tables["seats.parquet"]:
        tier = OFFICES[unit["office"]][0]
        if tier in NUMBERED_TIERS:
            place = (unit["office"], unit["district_code"], unit["block_code"])
            padded[(*place, serial(unit["unit_code"]))].add(unit["unit_code"])

    seats, unstated = [], collections.Counter()
    seen = set()
    for unit in tables["seats.parquet"]:
        key = seat_key(unit)
        tier, tier_local = OFFICES[unit["office"]]
        stated = text(unit["seat_reservation"])
        if not stated:
            unstated[tier] += 1
            continue
        caste = normalize.caste_of(stated)
        woman = normalize.woman_of(stated)
        if caste is None:
            raise ValueError(f"Bihar reservation not read: {stated!r}")
        # The form reuses one code for two places in a few parents, so the same
        # seat is listed twice under different names and its page can belong to
        # only one of them. The release flags them; the rows enter once.
        if key in seen:
            continue
        seen.add(key)
        contestants = members.get(key, [])
        if len(contestants) != unit["candidate_rows"]:
            raise ValueError(f"Bihar candidate coverage does not reconcile: {key}")
        won = winners.get(key)
        winner_identity = (won["sr_no"], won["row"]) if won else None
        if (
            won
            and sum(
                (row["sr_no"], row["row"]) == winner_identity for row in contestants
            )
            != 1
        ):
            raise ValueError(f"Bihar winner does not identify one candidate: {key}")
        vacant = bool(contestants) and all(
            row["remarks"] == "Vacant" for row in contestants
        )
        seat = {
            "state": STATE,
            "year": YEAR,
            "tier": tier,
            "tier_local": tier_local,
            "district": text(unit["district"]),
            "block": text(unit["block"]),
            # A mukhiya's or sarpanch's seat is the panchayat, so the form
            # names it in the unit column and leaves the panchayat column empty;
            # a ward seat sits inside a named panchayat.
            "gram_panchayat": (
                text(unit["unit"])
                if tier in HEAD_TIERS
                else (text(unit["panchayat"]) if tier in PANCHAYAT_TIERS else "")
            ),
            "gp_no": text(unit["panchayat_code"])
            or (text(unit["unit_code"]) if tier in HEAD_TIERS else ""),
            "ward_no": serial(unit["unit_code"]) if tier in WARD_TIERS else "",
            "ward_name": text(unit["unit"]) if tier in WARD_TIERS else "",
            "seat_no": serial(unit["unit_code"]) if tier in NUMBERED_TIERS else "",
            "caste_reservation": caste,
            "caste_reservation_local": stated,
            # The vocabulary is paired: every category is printed plain and with
            # (महिला), so a plain label states that the seat is not reserved for
            # a woman rather than saying nothing.
            "woman_reserved": int(woman == 1),
            "gender_stated": 1,
            "reservation": label(caste, woman == 1),
            "reservation_raw": stated,
            "winner": text(won["candidate_name"]) if won else "",
            "winner_basis": BASIS[won["winner_basis"]] if won else "",
            "votes": won["votes"] if won else None,
            "vacant": int(vacant),
            "unopposed": int(bool(won) and won["winner_basis"] == "uncontested"),
            "seat_candidates": len(contestants),
            "unit_of_observation": "seat_from_candidates",
            "script": normalize.script_of(
                text(unit["district"]), text(unit["block"]), text(unit["panchayat"])
            ),
            "source_path": f"{RELEASE}/seats.parquet",
            "source_page": "",
            "source_sha256": SHA256["seats.parquet"],
            "source_locator": "/".join(text(part) for part in key),
            "district_code": unit["district_code"],
            "block_code": text(unit["block_code"]),
            "panchayat_code": text(unit["panchayat_code"]),
            "seat_id_printed": text(unit["seat_label"]) or text(unit["unit_code"]),
            "code_repeated": int(bool(unit["code_repeated"])),
            "shared_place_name": int(
                tier in NUMBERED_TIERS
                and len(
                    padded[
                        (
                            unit["office"],
                            unit["district_code"],
                            unit["block_code"],
                            serial(unit["unit_code"]),
                        )
                    ]
                )
                > 1
            ),
            "winner_status": text(unit["winner_note"]) or text(unit["status"]),
            "seat_members": [],
        }
        for row in contestants:
            gender = text(row["gender_raw"])
            seat["seat_members"].append(
                {
                    **{k: v for k, v in seat.items() if k != "seat_members"},
                    "candidate_name": text(row["candidate_name"]),
                    "candidate_no": text(row["sr_no"]),
                    "relation_name": text(row["father_husband_name"]),
                    "candidate_gender": gender,
                    "candidate_woman": {"महिला": 1, "पुरुष": 0}.get(gender, ""),
                    "candidate_age": text(row["age"]),
                    "candidate_caste": text(row["category"]),
                    "candidate_education": text(row["education"]),
                    "party": "",
                    "votes": row["votes"],
                    "elected": (
                        int((row["sr_no"], row["row"]) == winner_identity)
                        if won
                        else ""
                    ),
                    "result": text(row["remarks"]),
                    # Every row names the saved page it was read from, which the
                    # original scrape could not do.
                    "source_path": f"{RELEASE}/candidates.parquet",
                    "source_sha256": SHA256["candidates.parquet"],
                    "source_page_sha256": text(row["page_sha256"]),
                    "source_row_number": text(row["row"]),
                }
            )
        seats.append(seat)
    return seats, unstated


def slices(root):
    rows, unstated = convert(read_release(root))
    by_tier = collections.defaultdict(list)
    for seat in rows:
        by_tier[seat["tier"]].append(seat)
    for tier, seats in by_tier.items():
        yield {
            "dataset_id": f"bihar/{tier}/{YEAR}",
            "state": STATE,
            "rows": seats,
            # A row names the page it came from, and the page is kept.
            "provenance_level": "page",
            "unit_of_observation": "seat_from_candidates",
            "notes": {"seats_without_a_stated_reservation": unstated.get(tier, 0)},
        }
