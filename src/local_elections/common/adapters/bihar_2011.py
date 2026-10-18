"""Bihar 2011, from the sibling's parse of the district Mukhiya winner reports.

These are not a seat roster. They are 23 district reports of elected mukhiyas,
3,973 located, named records out of roughly 8,400 panchayats, and coverage is
uneven - Jamui has 17. So the slice is `partial`, and a panchayat missing here
says nothing about whether it held an election.

Each record prints the seat's reservation and the winner's own sex, and the two
are different facts: a record can read "SC Woman" for the seat and "पुरूष" for
the person. Both are kept as printed. The sibling reads sex from explicit labels
only - महिला, the misspelling महीला, the abbreviations म0 and पु0 - never from a
name, and that reading is what enters winner_gender.

A reservation label the sibling could not map ("आरक्षित", or the office name
printed in the category box) leaves the caste blank rather than unreserved.
Extremely Backward Class is pooled as BC, as Bihar 2016's "अति पिछड़ा वर्ग" is,
and stays distinct in caste_reservation_local.

The record has no form code, so it is located by the sibling's record_id, which
names a printed row rather than a seat. The sibling's links to 2016 are keyed on
it.
"""

import hashlib
import json

import pyarrow.parquet as pq

from local_elections.common import normalize
from local_elections.common.normalize import label

RELEASE = "data/2011/mukhiya_reports"
FILE = "winner_records.parquet"
SHA256 = "3cdb740e116412a27d059df0b42c0dd05523069de636683f7c0d997a73437c56"
DECLARED = 3973
YEAR = "2011"
STATE = "Bihar"
CASTE = {"unreserved": "NONE", "SC": "SC", "ST": "ST", "BC": "BC", "EBC": "BC"}


def read_release(root):
    directory = root / RELEASE
    manifest = json.loads((directory / "MANIFEST.json").read_text())
    path = directory / FILE
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != SHA256:
        raise ValueError(f"Bihar 2011 release checksum changed: {digest}")
    if manifest["files"][FILE] != digest:
        raise ValueError("Bihar 2011 manifest disagrees with pinned input")
    rows = pq.read_table(path).to_pylist()
    if len(rows) != DECLARED:
        raise ValueError(f"Bihar 2011 release holds {len(rows):,} records")
    if {r["election_year"] for r in rows} != {2011}:
        raise ValueError("Bihar 2011 release is not explicitly dated 2011")
    return rows


def text(value):
    return "" if value is None else str(value).strip()


def convert(r):
    local = text(r["reservation_category"])
    caste = CASTE.get(local, "")
    if local and not caste:
        raise ValueError(f"Bihar 2011 reservation not read: {local!r}")
    woman = r["reservation_women"]
    return {
        "state": STATE,
        "year": YEAR,
        "tier": "gp_head",
        "tier_local": "mukhiya",
        "district": text(r["district_raw"]),
        "block": text(r["block_raw"]),
        "gram_panchayat": text(r["panchayat_raw"]),
        "listing_scope": "partial",
        "caste_reservation": caste,
        "caste_reservation_local": local,
        "woman_reserved": "" if woman is None else int(woman),
        "gender_stated": 0 if woman is None else 1,
        "reservation": label(caste, bool(woman)) if caste and woman is not None else "",
        "reservation_raw": text(r["reservation_raw"]),
        "winner": text(r["candidate_name"]),
        "winner_basis": "published",
        "relation_name": text(r["relative_name"]),
        "winner_gender": text(r["gender"]),
        "winner_gender_raw": text(r["gender_raw"]),
        "winner_gender_basis": "seat_record" if text(r["gender_raw"]) else "",
        "winner_caste": text(r["category_raw"]),
        "winner_age": text(r["age"]),
        "winner_education": text(r["education_raw"]),
        "winner_occupation": text(r["occupation_raw"]),
        "script": normalize.script_of(
            text(r["district_raw"]), text(r["block_raw"]), text(r["panchayat_raw"])
        ),
        "source_path": f"{RELEASE}/{FILE}",
        "source_page": text(r["source_page"]),
        "source_sha256": SHA256,
        "source_locator": text(r["record_id"]),
    }


def slices(root):
    yield {
        "dataset_id": f"bihar/gp_head/{YEAR}",
        "state": STATE,
        "rows": [convert(r) for r in read_release(root)],
        "provenance_level": "page",
        "unit_of_observation": "seat",
    }
