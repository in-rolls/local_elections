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

**Every district panchayat row names the wrong district, and that is repaired
here rather than carried.** All 993 `District`-type rows across the three cycles
carry `Thiruvananthapuram` - the scrape wrote the district it started on onto
every one of them. `coverage_vs_published` is what caught it: 1 body against the
14 the commission published. No internal check could have, because the column is
perfectly well-formed.

The 14 district panchayats are still there, in order: the ward numbers restart 13
times. Naming them is done by appealing to something outside the broken column -
each group's ward names are matched against the panchayat tier's own district
labels, which are correct - and every group resolves, to Kerala's canonical
south-to-north order, independently in all three cycles. A group that does not
resolve keeps the value the file gave it and is flagged.

**2005 carries no reservation.** Its file is an unpivoted table whose columns are
`Ward No`, `Elected Members`, `Front` and `Votes`, with header rows left in the
body. There is nothing about reservation in it to parse, which is a property of
the source rather than work outstanding.

Provenance is `dataset`: the scrape recorded no document and no page.
"""

import collections
import csv
import pathlib

from local_elections.common import normalize
from local_elections.common.normalize import label

REPO = "local_elections_kerala"
URL = "https://github.com/in-rolls/local_elections_kerala"
STATE = "Kerala"

FILE = "data/lsgi-election-kerala.csv"
DECLARED = 65296

# `LGI Type` -> (canonical office, the name Kerala prints, the column naming the
# body). The two urban types are declared so they are recognized and excluded by
# name rather than falling through as an unknown office; `canon.RURAL_TIERS`
# drops them and `master_dropped.csv` counts them.
TIERS = {
    "Grama Panchayat": ("gp_ward", "grama panchayat member", "Grama Panchayat"),
    "Block": ("block_member", "block panchayat member", "Block"),
    "District": ("zp_member", "district panchayat member", "District"),
    "Municipality": ("ulb_ward", "municipal councillor", "Municipality"),
    "Corporation": ("ulb_ward", "corporation councillor", "Corporation"),
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
    csv.field_size_limit(10**7)
    with path.open(encoding="utf-8", errors="replace") as fh:
        raw = list(csv.DictReader(fh))
    if len(raw) != DECLARED:
        raise SystemExit(
            f"{REPO}: {FILE} holds {len(raw):,} records, "
            f"{DECLARED:,} declared - the sibling changed"
        )

    name_district(raw)

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


def name_district(raw):
    """Give each district panchayat back its own name.

    Every District-type row says Thiruvananthapuram. The 14 bodies are separated
    by their ward numbers restarting; which body each group is comes from its
    ward names, voted against the districts the panchayat tier records for the
    same places. That column is independent of the broken one and is right.

    A group whose ward names resolve to nothing keeps what the file said and is
    flagged `district_inferred=0`, so a reader can tell a repaired row from an
    unrepaired one.
    """
    by_name = collections.defaultdict(set)
    for row in raw:
        if (row.get("LGI Type") or "").strip() == "Grama Panchayat":
            key = (row.get("Grama Panchayat") or "").strip().upper()
            if key:
                by_name[key].add((row.get("District") or "").strip())

    for year in sorted({(r.get("Year") or "").strip() for r in raw}):
        rows = [
            r
            for r in raw
            if (r.get("LGI Type") or "").strip() == "District"
            and (r.get("Year") or "").strip() == year
        ]
        for group in split_on_restart(rows):
            votes = collections.Counter()
            for row in group:
                found = by_name.get((row.get("Ward Name") or "").strip().upper())
                # only an unambiguous place votes: a ward name that occurs in
                # two districts says nothing about which one this is
                if found and len(found) == 1:
                    votes[next(iter(found))] += 1
            district = votes.most_common(1)[0][0] if votes else ""
            for row in group:
                row["_district"] = district or (row.get("District") or "").strip()
                row["_district_inferred"] = int(bool(district))


def split_on_restart(rows):
    """The rows of one tier, cut where the ward numbering starts over."""
    groups, current, previous = [], [], 0
    for row in rows:
        text = (row.get("Ward No.") or "").strip()
        number = int(text) if text.isdigit() else 0
        if number <= previous and current:
            groups.append(current)
            current = []
        current.append(row)
        previous = number
    if current:
        groups.append(current)
    return groups


def convert(row):
    kind = (row.get("LGI Type") or "").strip()
    if kind not in TIERS:
        return None
    tier, tier_local, body_column = TIERS[kind]
    stated = (row.get("Reservation") or "").strip()
    caste = normalize.caste_of(stated)
    woman = normalize.woman_of(stated)
    # A block or district seat is a numbered ward of that body and names no
    # panchayat; a panchayat ward names one.
    panchayat = (row.get("Grama Panchayat") or "").strip()
    winner = (row.get("Elected Members") or row.get("Name of Member") or "").strip()
    return {
        "state": STATE,
        "year": (row.get("Year") or "").strip(),
        "tier": tier,
        "tier_local": tier_local,
        "district": row.get("_district") or (row.get("District") or "").strip(),
        "block": (row.get("Block") or "").strip(),
        "gram_panchayat": panchayat,
        "ward_no": (row.get("Ward No.") or "").strip(),
        "ward_name": (row.get("Ward Name") or "").strip(),
        "seat_no": "" if panchayat else (row.get("Ward No.") or "").strip(),
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
        "lgi_role": (row.get("Role") or "").strip(),
        # Who was elected. Kerala states all five for every row, and keeping
        # only the party threw away the gender of 65,296 elected members in a
        # corpus whose subject is who reserved seats put in office.
        "winner_gender": (row.get("Female/Male") or "").strip(),
        "winner_age": (row.get("Age") or "").strip(),
        "winner_education": (row.get("Educational Qualification") or "").strip(),
        "winner_occupation": (row.get("Occupation") or "").strip(),
        "winner_marital_status": (row.get("Marital Status") or "").strip(),
        # 0 where the district panchayat's name could not be recovered
        "district_inferred": row.get("_district_inferred", ""),
        "party": (row.get("Party") or "").strip(),
        "body": (row.get(body_column) or "").strip(),
    }
