"""Bihar 2021, from the sibling's manifested six-office release.

Until now this adapter took the mukhiya table alone, because that was the only
release the sibling published: 8,067 seats out of 247,671, and not one of them
carrying a reservation, because the mukhiya release held no reservation table.

The sibling now publishes the whole general election - ward member, panch,
mukhiya, sarpanch, samiti member and zila parishad member - with a seat frame
validated against the portal's own district totals, and a seat-reservation
feed. So this reads all six offices and states their reservations.

Two things this has to get right.

**The reservation feed is undated.** It is the portal's 2021-2026 term feed and
its year field is null, which the sibling says in its README rather than
quietly filling in. Reservations are fixed for the term, so the reservation a
seat carries there is the one it was elected under in 2021, and the
by-elections that followed reused it. That is the claim; it is written here
rather than implied, and `reservation_dating` marks every row it applies to.

**The feed and the dated frame agree on the seat, not on the geography.** Join
them on post and unit and all 247,671 seats match; join on district, block,
panchayat and seat number and 12,255 do not, because the upper tiers leave
parts of that path empty. The unit id is the seat's identity here.

Bihar elects a gram kachahari - a village court - beside the gram panchayat,
so sarpanch and panch are not this state's gram panchayat head and ward:
`canon.TIER_BY_STATE` maps them to the kachahari tiers, and POSTS below follows
the same mapping for the portal's post ids.
"""

import collections
import hashlib
import json

import pyarrow.parquet as pq

from local_reservations.common import normalize
from local_reservations.common.normalize import label

RELEASE = "data/release/2021_panchayat"
SHA256 = {
    "seats.parquet": (
        "690f4e18e5e73558bb578f539b1c957c09dd17469b49726f69961c636b3d1fab"
    ),
    "current_reservations.parquet": (
        "a432377012f1d55f5862f44fe3f9f8a4b391b1b215fc44c5d5d626f96dc71073"
    ),
    "winners.parquet": (
        "6ac618e92b7bf9f22a0b95211a8fcdb9d1f605aa870a2d729986cddfe635c217"
    ),
    "candidates.parquet": (
        "3971775d2e2593e7aba39b154e60402a1f619219fd809d0e2de95c01f6fd63ef"
    ),
}
DECLARED = {
    "seats.parquet": 247671,
    "current_reservations.parquet": 247671,
    "winners.parquet": 244475,
    "candidates.parquet": 924708,
}
# The portal's post ids, to the canonical tier and the name Bihar prints.
POSTS = {
    1: ("gp_ward", "ward member"),
    2: ("kachahari_member", "panch"),
    3: ("gp_head", "mukhiya"),
    4: ("kachahari_head", "sarpanch"),
    5: ("block_member", "panchayat samiti member"),
    6: ("zp_member", "zila parishad member"),
}
# Which tiers number a seat inside a panchayat, and which number it inside the
# block or district. A ward row carries a ward number; a samiti or zila
# parishad row carries a territorial constituency number and no panchayat.
WARD_TIERS = {"gp_ward", "kachahari_member"}
PANCHAYAT_TIERS = {"gp_head", "kachahari_head", "gp_ward", "kachahari_member"}
# The sibling's basis for naming a winner, in this corpus's vocabulary. A sole
# nominee with no result records is not a published result and not a vote count.
BASIS = {"result_flag": "published", "sole_candidate": "sole_candidate"}
KEY = ["post_id", "unit_id"]
YEAR = "2021"
STATE = "Bihar"
REPO = "local_elections_bihar"
URL = "https://github.com/in-rolls/local_elections_bihar"


def read_release(root):
    """Every declared table, refused if a byte, a count or a column moved."""
    directory = root / RELEASE
    manifest = json.loads((directory / "MANIFEST.json").read_text())
    if manifest["year"] != 2021 or manifest["phase"] != "2021_1":
        raise ValueError("Bihar release is not explicitly dated 2021")
    if sorted(manifest["offices"]) != sorted(POSTS):
        raise ValueError("Bihar release does not cover the six offices")
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
        # The sibling records its schema in Polars' spelling ("String") and the
        # file reads back in Arrow's ("large_string"), so the columns are
        # compared by name and order. The types cannot move without the bytes
        # moving, and the bytes are pinned above.
        if table.schema.names != list(info["schema"]):
            raise ValueError(f"Bihar release columns changed: {name}")
        data[name] = table.to_pylist()
    return data


def seat_key(row):
    return tuple(row[name] for name in KEY)


def convert(tables):
    """Seat rows for every office, each with its candidates attached."""
    reservations = {seat_key(r): r for r in tables["current_reservations.parquet"]}
    if len(reservations) != len(tables["current_reservations.parquet"]):
        raise ValueError("Duplicate Bihar seat in the reservation feed")
    winners = {}
    for row in tables["winners.parquet"]:
        if seat_key(row) in winners:
            raise ValueError("More than one Bihar winner for a seat")
        winners[seat_key(row)] = row
    members = collections.defaultdict(list)
    for row in tables["candidates.parquet"]:
        members[seat_key(row)].append(row)

    seats = []
    for unit in tables["seats.parquet"]:
        key = seat_key(unit)
        stated = reservations[key]["seat_reservation"] if key in reservations else ""
        if not stated:
            raise ValueError(f"Bihar seat with no reservation feed row: {key}")
        caste = normalize.caste_of(stated)
        woman = normalize.woman_of(stated)
        if caste is None or woman is None:
            raise ValueError(f"Bihar reservation not read: {stated!r}")
        tier, tier_local = POSTS[unit["post_id"]]
        contestants = members.get(key, [])
        # Some candidates appear only in the results and never in the nomination
        # list; the sibling keeps them, flagged, and counts them separately.
        listed = sum(1 for row in contestants if row["in_candidate_list"])
        unlisted = len(contestants) - listed
        if listed != unit["candidate_records"]:
            raise ValueError(f"Bihar candidate coverage does not reconcile: {key}")
        if unlisted != unit["result_only_candidates"]:
            raise ValueError(f"Bihar result-only coverage does not reconcile: {key}")
        won = winners.get(key)
        seat = {
            "state": STATE,
            "year": YEAR,
            "tier": tier,
            "tier_local": tier_local,
            "district": unit["district"],
            "block": unit["block"],
            "gram_panchayat": unit["panchayat"] if tier in PANCHAYAT_TIERS else "",
            "ward_no": str(unit["seat_no"]) if tier in WARD_TIERS else "",
            "seat_no": "" if tier in WARD_TIERS else str(unit["seat_no"]),
            "caste_reservation": caste,
            "caste_reservation_local": stated.strip(),
            "woman_reserved": int(woman == 1),
            "gender_stated": 1,
            "reservation": label(caste, woman == 1),
            "reservation_raw": stated.strip(),
            "winner": (won["winner_name"] or "").strip() if won else "",
            "winner_basis": BASIS[won["winner_basis"]] if won else "",
            "votes": won["votes"] if won else None,
            "vacant": int(unit["status"] == "no_candidates"),
            "unopposed": int(bool(won) and won["winner_basis"] == "sole_candidate"),
            "seat_candidates": len(contestants),
            "unit_of_observation": "seat_from_candidates",
            "script": normalize.script_of(
                unit["district"], unit["block"], unit["panchayat"] or ""
            ),
            "source_path": f"{RELEASE}/seats.parquet",
            "source_page": "",
            "source_sha256": SHA256["seats.parquet"],
            "source_locator": "/".join(map(str, key)),
            # The codes the portal numbers its places by, off the join key and
            # recoverable from master_extras.parquet.
            "district_code": str(unit["district_id"]),
            "block_code": "" if unit["block_id"] is None else str(unit["block_id"]),
            "panchayat_code": (
                "" if unit["panchayat_id"] is None else str(unit["panchayat_id"])
            ),
            "seat_id_printed": str(unit["unit_id"]),
            "winner_status": unit["status"],
            # The reservation is read from the undated 2021-2026 term feed; see
            # the module docstring.
            "reservation_dating": "term_feed_2021_2026",
            "seat_members": [],
        }
        for row in contestants:
            gender = (row["candidate_gender"] or "").strip()
            seat["seat_members"].append(
                {
                    **{k: v for k, v in seat.items() if k != "seat_members"},
                    "candidate_name": (row["candidate_name"] or "").strip(),
                    "candidate_no": str(row["candidate_serial"]),
                    "in_candidate_list": int(bool(row["in_candidate_list"])),
                    "relation_name": (row["guardian_name"] or "").strip(),
                    "candidate_gender": gender,
                    "candidate_woman": {"female": 1, "male": 0}.get(gender, ""),
                    "candidate_age": (
                        ""
                        if row["candidate_age"] is None
                        else str(row["candidate_age"])
                    ),
                    "candidate_education": "",
                    "party": "",
                    "votes": row["votes"],
                    "elected": "" if row["elected"] is None else int(row["elected"]),
                    "result": "winner" if row["elected"] is True else "",
                    "source_path": f"{RELEASE}/candidates.parquet",
                    "source_sha256": row["source_sha256"],
                    "source_url": row["source_url"],
                    "source_row_number": str(row["source_row"]),
                    "affidavit_url": row["affidavit_url"],
                }
            )
        seats.append(seat)
    return seats


def slices(root):
    rows = convert(read_release(root))
    by_tier = collections.defaultdict(list)
    for seat in rows:
        by_tier[seat["tier"]].append(seat)
    for tier, seats in by_tier.items():
        yield {
            "dataset_id": f"bihar/{tier}/{YEAR}",
            "state": STATE,
            "rows": seats,
            # The release keeps the response each row came from, but a row
            # points at a feed rather than a page of a document.
            "provenance_level": "dataset",
            "unit_of_observation": "seat_from_candidates",
        }
