"""Bihar 2006, from the sibling's release of the SEC's 2006 workbooks.

Two kinds of workbook, and they say different things. The member workbooks
(ward member, panch, samiti, zila parishad; 32 districts, some only in part -
Gaya's ward sheet holds one block) print each seat's reservation: a caste cell
and a महिला/अन्य cell. The mukhiya and sarpanch workbooks profile the winner -
age, education, own category, income - and print no reservation, so those
seats enter with the reservation blank. A blank there means unstated, not open.

The sibling reads the caste cell's 177 spellings with ordered rules and leaves
a cell blank when it names two categories or too little to tell. This adapter
reads every cell again with normalize.caste_of and stops if the two readings
ever disagree; where normalize cannot read a spelling, the sibling's reading
stands.

The mukhiya seat's reservation comes from a second producer, M. R. Sharan's
research file (the sibling's gp_head_reservations.parquet): 8,262 gram
panchayats with English names and no winner. It is not an SEC document and
its origin in SEC records is undocumented, so its rows enter beside the
workbook rows and are not merged into them: a 2006 gram panchayat can
therefore appear twice under gp_head, once with a winner and once with a
reservation. Its EBC is pooled as BC, as Bihar 2011's is, and stays distinct
in caste_reservation_local. Each row's locator is `sharan/<ugp>`, which the
sibling's 2006-2016 seat link names.

The profile workbooks print no year; the sibling dates them to 2006 against
the 2011 winner reports (its build/profile_year_check.py). Every slice is
`partial`.
"""

import hashlib
import json

import pyarrow.parquet as pq

from local_elections.common import normalize
from local_elections.common.normalize import label

RELEASE = "data/release/2006"
SHA256 = {
    "seats.parquet": (
        "796bc5ebf483ad0c559876c246d27a09415d0bd63bafce675c5aa39d83489134"
    ),
    "winner_profiles.parquet": (
        "b9e0ded86b05eb9253421f2a5480e106ac5589007abf172355fbcd83de3afe19"
    ),
    "gp_head_reservations.parquet": (
        "12e8f3c8fa31003db4d1c71a74d5092381865e742dab5c75d107e51fce35b328"
    ),
}
DECLARED = {
    "seats.parquet": 209523,
    "winner_profiles.parquet": 14514,
    "gp_head_reservations.parquet": 8262,
}
YEAR = "2006"
STATE = "Bihar"
OFFICES = {
    "ward_member": ("gp_ward", "ward member"),
    "panch": ("kachahari_member", "panch"),
    "mukhiya": ("gp_head", "mukhiya"),
    "sarpanch": ("kachahari_head", "sarpanch"),
    "panchayat_samiti_member": ("block_member", "panchayat samiti member"),
    "zila_parishad_member": ("zp_member", "zila parishad member"),
}
WARD_TIERS = {"gp_ward", "kachahari_member"}
NUMBERED_TIERS = {"block_member", "zp_member"}
HEAD_TIERS = {"gp_head", "kachahari_head"}
SHARAN_CASTE = {"NONE": "NONE", "SC": "SC", "ST": "ST", "EBC": "BC"}


def read_release(root):
    directory = root / RELEASE
    manifest = json.loads((directory / "MANIFEST.json").read_text())
    published = {item["path"]: item for item in manifest["files"]}
    tables = {}
    for name, expected in SHA256.items():
        path = directory / name
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != expected or published[name]["sha256"] != digest:
            raise ValueError(f"Bihar 2006 release checksum changed: {name} {digest}")
        tables[name] = pq.read_table(path).to_pylist()
        if len(tables[name]) != DECLARED[name]:
            raise ValueError(f"Bihar 2006 {name} holds {len(tables[name]):,} rows")
    return tables


def text(value):
    return "" if value is None else str(value).strip()


def locator(r):
    return f"{r['source_path']}#{r['source_sheet']}!{r['source_row']}"


def caste(r):
    local = text(r["reserved_caste_local"])
    sibling = r["reserved_caste"] or ""
    ours = normalize.caste_of(local) if local else None
    if ours and sibling and ours != sibling:
        raise ValueError(f"Bihar 2006 readings disagree on {local!r}: {sibling}/{ours}")
    return sibling


def convert(r, profile):
    tier, tier_local = OFFICES[r["office"]]
    reserved = caste(r)
    woman = r["reserved_woman"]
    number = "" if r["constituency_no"] is None else str(r["constituency_no"])
    row = {
        "state": STATE,
        "year": YEAR,
        "tier": tier,
        "tier_local": tier_local,
        "district": text(r["district"]),
        "block": text(r["block"]),
        "gram_panchayat": text(r["gram_panchayat"]),
        "ward_no": number if tier in WARD_TIERS else "",
        "ward_name": text(r["constituency_name"]) if tier in WARD_TIERS else "",
        "seat_no": number if tier in NUMBERED_TIERS else "",
        "listing_scope": "partial",
        "caste_reservation": reserved,
        "caste_reservation_local": text(r["reserved_caste_local"]),
        "woman_reserved": "" if woman is None else int(woman),
        "gender_stated": 0 if woman is None else 1,
        "reservation": label(reserved, bool(woman))
        if reserved and woman is not None
        else "",
        "reservation_raw": text(r["reserved_raw"]),
        "winner": text(r["winner"]),
        "winner_basis": "published" if text(r["winner"]) else "",
        "vacant": int(bool(r["vacant"])),
        "script": normalize.script_of(
            text(r["district"]), text(r["block"]), text(r["gram_panchayat"])
        ),
        "source_path": f"{RELEASE}/seats.parquet",
        "source_page": "",
        "source_sha256": SHA256["seats.parquet"],
        "source_locator": locator(r),
        "district_from_file": text(r["district_from_file"]),
    }
    if profile:
        row.update(
            {
                "winner_age": text(profile["winner_age"]),
                "winner_education": text(profile["winner_education_raw"]),
                "winner_occupation": text(profile["winner_occupation_raw"]),
                "winner_caste": text(profile["winner_caste"]),
                "winner_caste_raw": text(profile["winner_caste_raw"]),
                "winner_social_class": text(profile["winner_social_class_raw"]),
                "winner_income_inr": text(profile["winner_income_inr"]),
                "winner_sons": text(profile["winner_sons"]),
                "winner_daughters": text(profile["winner_daughters"]),
            }
        )
    return row


def roster_row(r):
    """A mukhiya seat as Sharan's file states it: place and reservation only."""
    reserved = SHARAN_CASTE[r["reserved_caste"]]
    return {
        "state": STATE,
        "year": YEAR,
        "tier": "gp_head",
        "tier_local": "mukhiya",
        "district": text(r["district"]),
        "block": text(r["block"]),
        "gram_panchayat": text(r["gram_panchayat"]),
        "listing_scope": "partial",
        "caste_reservation": reserved,
        "caste_reservation_local": text(r["reserved_caste"]),
        "woman_reserved": int(r["reserved_woman"]),
        "gender_stated": 1,
        "reservation": label(reserved, bool(r["reserved_woman"])),
        "winner": "",
        "winner_basis": "",
        "vacant": 0,
        "source_path": f"{RELEASE}/gp_head_reservations.parquet",
        "source_page": "",
        "source_sha256": SHA256["gp_head_reservations.parquet"],
        "source_locator": f"sharan/{r['ugp']}",
    }


def slices(root):
    tables = read_release(root)
    profiles = {locator(p): p for p in tables["winner_profiles.parquet"]}
    by_tier = {}
    for r in tables["seats.parquet"]:
        row = convert(r, profiles.get(locator(r)))
        by_tier.setdefault(row["tier"], []).append(row)
    by_tier["gp_head"] += [
        roster_row(r) for r in tables["gp_head_reservations.parquet"]
    ]
    for tier, rows in by_tier.items():
        yield {
            "dataset_id": f"bihar/{tier}/{YEAR}",
            "state": STATE,
            "rows": rows,
            "provenance_level": "row",
            "unit_of_observation": "seat",
        }
