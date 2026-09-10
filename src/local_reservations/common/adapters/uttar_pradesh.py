"""Uttar Pradesh, from local_elections_up.

Gram panchayat heads for four cycles - 2005, 2010, 2015 and 2021 - and the only
sibling whose rows can claim page-level provenance: the 2010 parse kept both
`original_filename` and `page`, so a row points at the sheet it was read from.
2005 kept the page but not the file, so it is `document`.

Two shapes in one state. 2005 and 2010 are one row per seat with the winner
already on it. 2021 is one row per **candidate** - 373,096 of them over 49,772
panchayats - and it marks विजेता and उपविजेता, so both the winner and the runner
up are stated rather than inferred. It records no vote total, only
`vote_percentage`, so there is no margin: a stated second place with no margin
is the honest shape of that file, and better than turning a percentage back into
a count.

The `_fixed` files are used for 2005 and 2010, not the originals. They carry
`gp_res_status_fin_eng`, the reservation already normalized to English, and
`gp_name_fin`, the panchayat name already cleaned. Reading the raw columns
instead would mean re-solving both problems worse.

Two things worth naming:

`Unknown` is not a category. 1,239 rows in 2005 and 32 in 2010 read that way,
meaning the cell did not survive the scan. They carry no caste and no gender
rather than defaulting to unreserved, and `gender_stated` is 0 for them, so
`quality_flags` says so on every one.

The panchayat is numbered in its own name in 2021 - `1-नन्हेड़ा अल्यारपुर` -
and the number is split off, because a name that carries its serial is
unjoinable to the same panchayat printed without one in 2005 and 2010.
"""

import csv
import hashlib
import io
import json
import pathlib
import re

from local_reservations.common import collapse, normalize
from local_reservations.common.normalize import label

REPO = "local_elections_up"
URL = "https://github.com/in-rolls/local_elections_up"
STATE = "Uttar Pradesh"

SEAT_FILES = {
    "2005": "data/up_gp_sarpanch_2005_fixed.csv",
    "2010": "data/up_gp_sarpanch_2010_fixed.csv",
    "2015": "data/fin/up_gp_sarpanch_2015_fixed_with_transliteration.parquet",
}
CANDIDATE_FILE = ("2021", "data/up_gram_panchayat_pradhan_2021.csv")

DECLARED = {"2005": 51872, "2010": 51861, "2015": 59019, "2021": 373096}

SOURCE_SHA256 = {
    "2015": "2e7cde2ad328d9a7f7d8ad078295e47ef274f48f22b0272a6aaf10ed00cf9b45",
}

# 2021 collapses; the other three are already seat-level records.
SEATS = {"2005": 51872, "2010": 51861, "2015": 59019, "2021": 49772}

WINNER, RUNNER_UP = "विजेता", "उपविजेता"

# The panchayat's serial, printed into its name in 2021 only.
NUMBERED = re.compile(r"^\s*(\d+)\s*-\s*(.*)$")

WOMAN = {"महिला": 1, "पुरुष": 0}


def unnumber(value):
    got = NUMBERED.match(value or "")
    return (got.group(1), got.group(2).strip()) if got else ("", (value or "").strip())


def slices(root):
    root = pathlib.Path(root)
    csv.field_size_limit(10**7)

    for year, relative in sorted(SEAT_FILES.items()):
        rows = read(root / relative, year, DECLARED[year])
        if rows is None:
            continue
        convert = seat_row_2015 if year == "2015" else seat_row
        seats = [convert(r, year, relative) for r in rows]
        for seat, source in zip(seats, rows, strict=True):
            seat["source_row_number"] = source["source_row_number"]
            if year in SOURCE_SHA256:
                seat["source_sha256"] = SOURCE_SHA256[year]
        check(year, len(seats), SEATS[year], "seats")
        yield {
            "dataset_id": f"uttar_pradesh/gp_head/{year}",
            "state": STATE,
            "rows": seats,
            # 2010 kept the file and the page it was read from; 2005 kept only
            # the page, so it can be traced to a document and no further
            "provenance_level": (
                "page"
                if year == "2010"
                else "document"
                if year == "2005"
                else "dataset"
            ),
            "unit_of_observation": "seat",
        }

    year, relative = CANDIDATE_FILE
    rows = read(root / relative, year, DECLARED[year])
    if rows is None:
        return
    candidates = [candidate_row(r, year, relative) for r in rows]
    seats = collapse.to_seats(
        candidates,
        ["_key"],
        winner_field="result",
        winner_value=WINNER,
        runner_up_value=RUNNER_UP,
    )
    check(year, len(seats), SEATS[year], "seats")
    for seat in seats:
        marked = [r for r in seat["seat_members"] if r.get("result") == WINNER]
        if len(marked) > 1:
            seat["winner_markers_conflict"] = 1
            seat["winner_marked_candidate_ids"] = json.dumps(
                [r.get("candidate_no", "") for r in marked]
            )
            for member in seat["seat_members"]:
                member["elected"] = ""
        for row in [seat] + seat["seat_members"]:
            row.pop("_key", None)
    yield {
        "dataset_id": f"uttar_pradesh/gp_head/{year}",
        "state": STATE,
        "rows": seats,
        # the scrape recorded neither a document nor a page
        "provenance_level": "dataset",
        "unit_of_observation": "seat_from_candidates",
    }


def read(path, year, expected):
    if not path.exists():
        if year in SOURCE_SHA256:
            raise FileNotFoundError(f"Required pinned UP release input: {path}")
        return None
    if path.suffix == ".parquet":
        import pyarrow.parquet as pq

        payload = path.read_bytes()
        expected_sha = SOURCE_SHA256.get(year)
        if expected_sha and hashlib.sha256(payload).hexdigest() != expected_sha:
            raise SystemExit(f"{REPO}: {year} published input hash changed: {path}")
        rows = pq.read_table(io.BytesIO(payload)).to_pylist()
    else:
        with path.open(encoding="utf-8", errors="replace") as fh:
            rows = list(csv.DictReader(fh))
    for number, row in enumerate(rows, 1):
        row["source_row_number"] = str(number)
    check(year, len(rows), expected, "records")
    return rows


def check(year, got, expected, what):
    if expected is not None and got != expected:
        raise SystemExit(
            f"{REPO}: {year} holds {got:,} {what}, {expected:,} "
            f"declared - the sibling changed"
        )


def seat_row_2015(row, year, relative):
    """Published seat results; contested/unopposed is not a winner filter."""
    raw = row.get("gp_reservation_status") or ""
    caste = normalize.caste_of(raw)
    woman = None if caste is None else normalize.woman_of(raw)
    winner = (row.get("elected_sarpanch_name") or "").strip()
    return {
        "state": STATE,
        "year": year,
        "tier": "gp_head",
        "tier_local": "pradhan",
        "district": (row.get("district_name") or "").strip(),
        "block": (row.get("block_name") or "").strip(),
        "gp_no": str(row.get("gp_num") or "").strip(),
        "gram_panchayat": (row.get("gp_name") or "").strip(),
        "caste_reservation": caste or "",
        "caste_reservation_local": raw,
        "woman_reserved": "" if caste is None else int(woman == 1),
        "gender_stated": "0" if caste is None else "1",
        "reservation": label(caste, woman == 1) if caste else "",
        "reservation_raw": raw,
        "winner": winner,
        "winner_basis": "published" if winner else "",
        "winner_caste": row.get("candidate_reservation_status") or "",
        "winner_gender": row.get("sex") or "",
        "winner_education": row.get("educational_qualification") or "",
        "relation_name": row.get("father_husband") or "",
        "votes": collapse.votes_of(row.get("valid_votes_received")),
        "vote_percentage": row.get("votes_received_percent") or "",
        "poll_percentage": row.get("voting_percent") or "",
        "unopposed": {"निर्विरोध": 1, "सविरोध": 0}.get(row.get("result"), ""),
        "result_remark": row.get("result") or "",
        "script": normalize.script_of(
            winner, row.get("district_name"), row.get("block_name"), row.get("gp_name")
        ),
        "source_path": relative,
        "source_page": "",
    }


def seat_row(row, year, relative):
    """2005 and 2010: the seat, with its winner already on it."""
    stated = (row.get("gp_res_status_fin_eng") or "").strip()
    # "Unknown" means the cell did not survive the scan. Not a category, and
    # not unreserved.
    caste = None if stated.lower() == "unknown" else normalize.caste_of(stated)
    woman = None if caste is None else normalize.woman_of(stated)
    return {
        "state": STATE,
        "year": year,
        "tier": "gp_head",
        "tier_local": "pradhan",
        "district": (row.get("district_name") or "").strip(),
        "block": (row.get("block_name") or "").strip(),
        "gp_no": (row.get("gp_code") or "").strip(),
        "gram_panchayat": (row.get("gp_name_fin") or row.get("gp_name") or "").strip(),
        "caste_reservation": caste or "",
        "caste_reservation_local": stated,
        "woman_reserved": "" if caste is None else int(woman == 1),
        "gender_stated": "" if caste is None else 1,
        "reservation": label(caste, woman == 1) if caste else "",
        "reservation_raw": (row.get("gp_reservation_status") or "").strip(),
        "winner": (row.get("elected_sarpanch_name") or "").strip(),
        "winner_basis": (
            "published" if (row.get("elected_sarpanch_name") or "").strip() else ""
        ),
        # The winner's *own* category, which the file states beside the seat's
        # and which is not the same fact: they agree on 19,324 of 51,872 rows
        # in 2005. Dropping it would have left this corpus unable to
        # distinguish "a seat reserved for a scheduled caste" from "a
        # scheduled-caste person won", which is most of what these data are
        # for.
        "winner_caste": (
            row.get("candidate_res_status_fin") or row.get("candidate_res_status") or ""
        ).strip(),
        "winner_gender": (row.get("cand_sex_fin") or row.get("sex") or "").strip(),
        "winner_age": (
            row.get("age_fin") or row.get("age_t2") or row.get("age") or ""
        ).strip(),
        "winner_education": (
            row.get("educ_fin_eng") or row.get("educ_fin") or row.get("education") or ""
        ).strip(),
        "relation_name": (row.get("husband_spouse_name") or "").strip(),
        # Read from the row rather than asserted. Hardcoding this shipped
        # 304,689 rows saying the wrong thing - see normalize.script_of.
        "script": normalize.script_of(
            *(
                row.get(k) or ""
                for k in (
                    "elected_sarpanch_name",
                    "gp_name_fin",
                    "gp_name",
                    "district_name",
                    "block_name",
                )
            )
        ),
        "source_path": relative,
        # 2010 names the file each row came from; 2005 gives only a page number,
        # which without a filename identifies nothing on its own
        "source_page": (row.get("page") or "").strip() if year == "2010" else "",
        "gp_code": (row.get("gp_code") or "").strip(),
        "district_code": (row.get("district_code") or "").strip(),
        "block_code": (row.get("block_code") or "").strip(),
        "original_filename": (row.get("original_filename") or "").strip(),
    }


def candidate_row(row, year, relative):
    """2021: one candidate, in the shape `collapse.to_seats` reads."""
    stated = (row.get("reservation") or "").strip()
    caste = normalize.caste_of(stated)
    woman = normalize.woman_of(stated)
    number, panchayat = unnumber(row.get("gram_panchayat"))
    district = (row.get("zila") or "").strip()
    block = (row.get("block") or "").strip()
    return {
        "_key": (district, block, number, panchayat),
        "state": STATE,
        "year": year,
        "tier": "gp_head",
        "tier_local": "pradhan",
        "district": district,
        "block": block,
        "gram_panchayat": panchayat,
        "seat_no": number,
        "caste_reservation": caste or "",
        "caste_reservation_local": stated,
        # The vocabulary is paired - अनारक्षित against महिला, अनुसूचित जाति
        # against अनुसूचित जाति महिला - so a label with no महिला states that the
        # seat is not reserved for a woman.
        "woman_reserved": "" if caste is None else int(woman == 1),
        "gender_stated": "" if caste is None else 1,
        "reservation": label(caste, woman == 1) if caste else "",
        "reservation_raw": stated,
        # Read from the row rather than asserted. Hardcoding this shipped
        # 304,689 rows saying the wrong thing - see normalize.script_of.
        "script": normalize.script_of(district, block, panchayat),
        "source_path": relative,
        "source_page": "",
        # the long form
        "candidate_name": (row.get("candidate_name_2021") or "").strip(),
        "candidate_no": (row.get("id") or "").strip(),
        "source_row_number": row.get("source_row_number", ""),
        "relation_name": (row.get("father_husband_name_2021") or "").strip(),
        "candidate_gender": (row.get("gender_2021") or "").strip(),
        "candidate_woman": WOMAN.get((row.get("gender_2021") or "").strip(), ""),
        "candidate_age": (row.get("age_2021") or "").strip(),
        "candidate_caste": (row.get("caste_2021") or "").strip(),
        "candidate_education": (row.get("education_2021") or "").strip(),
        "party": "",
        # no vote count anywhere in this file, only a share of the poll
        "votes": "",
        "result": (row.get("result") or "").strip(),
        "vote_percentage": (row.get("vote_percentage") or "").strip(),
        "movable_property": (row.get("movable_property") or "").strip(),
        "immovable_property": (row.get("immovable_property") or "").strip(),
        "criminal_history": (row.get("criminal_history_2021") or "").strip(),
    }
