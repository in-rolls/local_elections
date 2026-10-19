"""Telangana sarpanch seats, from local_elections_telangana.

Two elections, both from the State Election Commission's own "Know your
Public Representative - Rural" reports:

- 2019: the elected listing (12,018 seats) with each seat's reservation code.
  It is the same file this repository parsed into data/telangana/, which the
  sibling now supersedes; the in-tree ward slice stays.
- 2025: the per-mandal "Only Elected" and "All Contested" reports (12,735
  GPs, the commission's full count), with reservation, winner and votes. 33
  GPs have no declared result (no nominations, no result, or a court stay):
  their seats carry a reservation and no winner.

Neither year prints the winner's sex. The seat's reservation is a label only
where it reserves the seat for a woman.

Women's seats are half of each category's seats per mandal, rounded down, in
2025 (45.9% statewide); 2019 sits at 50.0%.

The sibling links 2019 seats to 2025 seats by the commission's codes and by
names, and keeps a pair only where the two routes do not dispute it.

Provenance is `page`: every 2019 seat carries its CSV row and every 2025 seat
its saved report page and table row.
"""

import pathlib

import pyarrow.parquet as pq

from local_elections.common.normalize import label

REPO = "local_elections_telangana"
URL = "https://github.com/in-rolls/local_elections_telangana"
STATE = "Telangana"

YEARS = ("2019", "2025")
RESULTS = "data/{year}/sarpanch_results.parquet"
LINKS = {("2019", "2025"): "data/linkage/gp_2019_2025.parquet"}

DECLARED = {
    "data/2019/sarpanch_results.parquet": 12018,
    "data/2025/sarpanch_results.parquet": 12735,
    "data/linkage/gp_2019_2025.parquet": 11464,
}

# This repository's own 2019 sarpanch parse, replaced by the sibling's.
SUPERSEDES = {("Telangana", "2019", "gp_head")}

CASTES = {"SC", "ST", "BC", "NONE"}


def text(value):
    if value is None or value != value:  # None or NaN
        return ""
    if isinstance(value, bool):
        return str(int(value))
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def locator(source_path, source_locator):
    """Where a seat is printed: unique in both years."""
    return f"{text(source_path)}#{text(source_locator)}"


def read(root, relative):
    path = root / relative
    if not path.exists():
        return None
    rows = pq.read_table(path).to_pylist()
    expected = DECLARED.get(relative)
    if expected is not None and len(rows) != expected:
        raise SystemExit(
            f"{REPO}: {relative} holds {len(rows):,} rows, "
            f"{expected:,} declared - the sibling changed"
        )
    return rows


def seat(r):
    caste = text(r.get("caste_reservation"))
    caste = caste if caste in CASTES else ""
    woman = text(r.get("woman_reserved"))
    stated = caste != "" and woman != ""
    raw = text(r.get("reservation_raw"))
    row = {
        "state": STATE,
        "year": text(r.get("year")),
        "tier": "gp_head",
        "tier_local": text(r.get("tier_local")),
        "district": text(r.get("district")),
        "block": text(r.get("block")),
        "gram_panchayat": text(r.get("gram_panchayat")),
        "caste_reservation": caste,
        "caste_reservation_local": raw.split("(")[0],
        "woman_reserved": woman,
        "gender_stated": "1" if woman != "" else "0",
        "reservation": label(caste, woman == "1") if stated else "",
        "reservation_raw": raw,
        "winner": text(r.get("winner")),
        "winner_basis": text(r.get("winner_basis")),
        "script": text(r.get("script")),
        "source_path": text(r.get("source_path")),
        "source_locator": locator(r.get("source_path"), r.get("source_locator")),
    }
    if row["year"] == "2025":
        # the commission's codes; a GP code is unique only within its mandal
        row["gp_no"] = f"{text(r.get('mandal_id'))}/{text(r.get('gp_code'))}"
        row["unopposed"] = text(r.get("unopposed"))
        row["total_valid_votes"] = text(r.get("total_valid_votes"))
    return row


def slices(root):
    root = pathlib.Path(root)
    for year in YEARS:
        results = read(root, RESULTS.format(year=year))
        if results is None:
            continue
        yield {
            "dataset_id": f"telangana/gp_head/{year}",
            "state": STATE,
            "rows": [seat(r) for r in results],
            "provenance_level": "page",
            "unit_of_observation": "seat",
        }


def links(root):
    """The sibling's sarpanch seat links, keyed by both seats' locators."""
    root = pathlib.Path(root)
    for (a, b), relative in LINKS.items():
        rows = read(root, relative)
        if rows is None:
            continue
        for r in rows:
            score = r.get("name_score")
            if score is None or score != score:
                score = r.get("code_name_score")
            yield {
                "from_dataset_id": f"telangana/gp_head/{a}",
                "from_locator": locator(
                    "data/raw/2019/2019_gp_sarpanch.csv", r[f"source_locator_{a}"]
                ),
                "to_dataset_id": f"telangana/gp_head/{b}",
                "to_locator": locator(r[f"source_path_{b}"], r[f"source_locator_{b}"]),
                "link_pass": r["link_basis"],
                "name_score": float(score),
                "source_path": relative,
            }
