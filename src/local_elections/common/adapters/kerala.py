"""Kerala, from local_elections_kerala.

Three cycles - 2010, 2015, 2020 - across the three rural tiers plus the urban
bodies, all in one file, one row per elected seat. Kerala reserves for scheduled
castes and tribes and for women, and for no backward class at all, which is the
law rather than a gap; `canon.CASTE_SCHEME` declares it as `sc_st_only` so a
zero backward-class count passes here and would fail in Goa.

**`Role` is not a tier.** The plan this adapter was written against assumed the
`President` and `Vice President` rows were a gram panchayat head tier whose
reservation might be the office's rather than the ward's. The file settles it:
all 48,514 gram panchayat rows are unique on (year, district, panchayat, ward),
so a President row *is* a ward row - the member elected from ward 8 who also
holds the presidency - and its `Reservation` is that ward's. Reading `Role` as a
tier would both pool an indirectly elected office with directly elected heads
and count 3,670 wards twice. Every row here is the ward it was elected from, and
`Role` goes to the extras, where the presidency stays recoverable.

**The overlapping files resolve exactly.** The standalone 2015 file holds 16,558
rows and the 2015 fix file 5,245; together 21,803, which is precisely what the
combined file holds for 2015. The combined file already incorporates the fix, so
it is the one read and the other two are not.

**Every district panchayat row names the wrong district in the scrape.** All
993 `District`-type rows carry `Thiruvananthapuram`: the scraper wrote the
district it started on onto every one. The sibling repairs it from the order of
the 14 bodies (`district_inferred`, method `district_panchayat_order`), and an
independent route - voting each body's ward names against the panchayat tier's
own district labels - gave the same district for all 993 rows, so the repaired
value is read here.

**2005 carries no reservation.** Its file is an unpivoted table whose columns are
`Ward No`, `Elected Members`, `Front` and `Votes`, with header rows left in the
body. There is nothing about reservation in it to parse, which is a property of
the source rather than work outstanding.

Provenance is `dataset`: the scrape recorded no document and no page.
"""

import pathlib

import pyarrow.parquet as pq

from local_elections.common import normalize
from local_elections.common.normalize import label

REPO = "local_elections_kerala"
URL = "https://github.com/in-rolls/local_elections_kerala"
STATE = "Kerala"

FILE = "data/release/elected_members_2010_2020.parquet"
DECLARED = 65296

# `lgi_type` -> (canonical office, the name Kerala prints, the column naming the
# body). The two urban types are declared so they are recognized and excluded by
# name rather than falling through as an unknown office; `canon.RURAL_TIERS`
# drops them and `master_dropped.csv` counts them.
TIERS = {
    "Grama Panchayat": ("gp_ward", "grama panchayat member", "grama_panchayat_raw"),
    "Block": ("block_member", "block panchayat member", "block_raw"),
    "District": ("zp_member", "district panchayat member", "district_raw"),
    "Municipality": ("ulb_ward", "municipal councillor", "municipality_raw"),
    "Corporation": ("ulb_ward", "corporation councillor", "corporation_raw"),
}

DECLARED_SEATS = {
    ("2010", "gp_ward"): 16641,
    ("2010", "block_member"): 2078,
    ("2010", "zp_member"): 331,
    ("2010", "ulb_ward"): 2557,
    ("2015", "gp_ward"): 15921,
    ("2015", "block_member"): 2062,
    ("2015", "zp_member"): 331,
    ("2015", "ulb_ward"): 3489,
    ("2020", "gp_ward"): 15952,
    ("2020", "block_member"): 2078,
    ("2020", "zp_member"): 331,
    ("2020", "ulb_ward"): 3525,
}


def slices(root):
    path = pathlib.Path(root) / FILE
    if not path.exists():
        return
    raw = [
        {k: "" if v is None else str(v) for k, v in r.items()}
        for r in pq.read_table(path).to_pylist()
    ]
    if len(raw) != DECLARED:
        raise SystemExit(
            f"{REPO}: {FILE} holds {len(raw):,} records, "
            f"{DECLARED:,} declared - the sibling changed"
        )

    grouped = {}
    for row in raw:
        got = convert(row)
        if got is not None:
            grouped.setdefault((got["year"], got["tier"]), []).append(got)

    for (year, tier), rows in sorted(grouped.items()):
        expected = DECLARED_SEATS.get((year, tier))
        if expected is not None and len(rows) != expected:
            raise SystemExit(
                f"{REPO}: {year}/{tier} holds {len(rows):,} rows, "
                f"{expected:,} declared - the parse changed"
            )
        yield {
            "dataset_id": f"kerala/{tier}/{year}",
            "state": STATE,
            "rows": rows,
            "provenance_level": "dataset",
            "unit_of_observation": "seat",
        }


def convert(row):
    kind = (row.get("lgi_type") or "").strip()
    if kind not in TIERS:
        return None
    tier, tier_local, body_column = TIERS[kind]
    stated = (row.get("reserved_raw") or "").strip()
    caste = normalize.caste_of(stated)
    woman = normalize.woman_of(stated)
    # A block or district seat is a numbered ward of that body and names no
    # panchayat; a panchayat ward names one.
    panchayat = (row.get("grama_panchayat_raw") or "").strip()
    winner = (row.get("elected_member_raw") or row.get("member_name_raw") or "").strip()
    inferred = (row.get("district_inferred") or "").strip()
    return {
        "state": STATE,
        "year": (row.get("year") or "").strip(),
        "tier": tier,
        "tier_local": tier_local,
        "district": inferred or (row.get("district_raw") or "").strip(),
        "block": (row.get("block_raw") or "").strip(),
        "gram_panchayat": panchayat,
        "ward_no": (row.get("ward_no_raw") or "").strip(),
        "ward_name": (row.get("ward_name_raw") or "").strip(),
        "seat_no": "" if panchayat else (row.get("ward_no_raw") or "").strip(),
        "caste_reservation": caste or "",
        "caste_reservation_local": stated,
        # The vocabulary is paired - General against Woman, SC against SC Woman
        # - so a label without "Woman" states the seat is not reserved for one.
        "woman_reserved": "" if caste is None else int(woman == 1),
        "gender_stated": "" if caste is None else 1,
        "reservation": label(caste, woman == 1) if caste else "",
        "reservation_raw": stated,
        "winner": winner,
        "winner_basis": "published" if winner else "",
        "script": "latin",
        "source_path": FILE,
        "source_page": "",
        # the presidency is an office the ward member also holds, not a tier
        "lgi_role": (row.get("role_raw") or "").strip(),
        # Who was elected. Kerala states all five for every row, and keeping
        # only the party threw away the gender of 65,296 elected members in a
        # corpus whose subject is who reserved seats put in office.
        "winner_gender": (row.get("winner_woman_raw") or "").strip(),
        "winner_age": (row.get("age_raw") or "").strip(),
        "winner_education": (row.get("education_raw") or "").strip(),
        "winner_occupation": (row.get("occupation_raw") or "").strip(),
        "winner_marital_status": (row.get("marital_status_raw") or "").strip(),
        # 1 where the sibling repaired the scrape's district
        "district_inferred": 1 if inferred else "",
        "party": (row.get("party_raw") or "").strip(),
        "body": (row.get(body_column) or "").strip(),
    }
