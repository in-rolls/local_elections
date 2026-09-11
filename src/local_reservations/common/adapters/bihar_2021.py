"""Import the pinned Bihar 2021 release without reinterpreting source evidence."""

import collections
import hashlib
import json

import pyarrow.parquet as pq

from local_reservations.common import normalize

RELEASE = "data/release/2021"
SHA256 = {
    "gp_head_candidates_2021.parquet": (
        "bb04406261f3f6fb66c408b5a497e43150c30f40074aff69a9a6fd1cc31b9fc3"
    ),
    "gp_head_winner_records_2021.parquet": (
        "1702c547d77ec2c41fd16c1de840e07e2c81cc9b709ba049d314bff9aaeb9fc4"
    ),
    "coverage.parquet": (
        "953e66f611d89e7fcb89d04a3e13e4d093ea2a9aac9c6ee64805c7c66a9380cb"
    ),
}
DECLARED = {
    "gp_head_candidates_2021.parquet": 66430,
    "gp_head_winner_records_2021.parquet": 8050,
    "coverage.parquet": 8067,
}
KEY = ["district_id", "block_id", "panchayat_id"]


def read_release(root):
    directory = root / RELEASE
    manifest = json.loads((directory / "MANIFEST.json").read_text())
    if manifest["year"] != 2021 or manifest["source_phase"] != "2021_1":
        raise ValueError("Bihar release is not explicitly dated 2021")
    data = {}
    for info in manifest["files"]:
        name = info["path"]
        if name not in SHA256:
            raise ValueError(f"Undeclared Bihar release table: {name}")
        path = directory / name
        if hashlib.sha256(path.read_bytes()).hexdigest() != SHA256[name]:
            raise ValueError(f"Bihar release checksum changed: {name}")
        if info["sha256"] != SHA256[name]:
            raise ValueError(f"Bihar manifest disagrees with pinned input: {name}")
        table = pq.read_table(path)
        if len(table) != DECLARED[name] or len(table) != info["rows"]:
            raise ValueError(f"Bihar release count changed: {name}")
        if {f.name: str(f.type) for f in table.schema} != info["schema"]:
            raise ValueError(f"Bihar release schema changed: {name}")
        data[name] = table.to_pylist()
    if set(data) != set(SHA256):
        raise ValueError("Incomplete Bihar release manifest")
    return data


def seat_key(row):
    return tuple(row[n] for n in KEY)


def convert(tables):
    grouped = collections.defaultdict(list)
    source = tables["gp_head_candidates_2021.parquet"]
    unique = {(seat_key(r), r["candidate_serial"]) for r in source}
    if len(unique) != len(source):
        raise ValueError("Duplicate Bihar candidacy key")
    winners = tables["gp_head_winner_records_2021.parquet"]
    if [r for r in source if r["elected"] is True] != winners:
        raise ValueError("Bihar winner export differs from source flags")
    for row in source:
        grouped[seat_key(row)].append(row)
    seats = []
    for unit in tables["coverage.parquet"]:
        members = grouped.pop(seat_key(unit), [])
        if len(members) != unit["candidate_records"]:
            raise ValueError("Bihar candidate coverage does not reconcile")
        marked = [r for r in members if r["elected"] is True]
        if len(marked) != unit["winner_records"] or len(marked) > 1:
            raise ValueError("Bihar winner coverage does not reconcile")
        seat = {
            "state": "Bihar",
            "year": "2021",
            "tier": "gp_head",
            "tier_local": "mukhiya",
            "district": unit["district"],
            "block": unit["block"],
            "gram_panchayat": unit["panchayat"],
            "gp_no": str(unit["panchayat_id"]),
            "district_code": str(unit["district_id"]),
            "block_code": str(unit["block_id"]),
            "caste_reservation": "",
            "woman_reserved": "",
            "gender_stated": 0,
            "reservation": "",
            "reservation_raw": "",
            "winner": marked[0]["candidate_name"] if marked else "",
            "winner_basis": "published" if marked else "",
            "winner_status": unit["winner_status"],
            "seat_candidates": len(members),
            "unit_of_observation": "seat_from_candidates",
            "source_path": f"{RELEASE}/"
            + ("gp_head_candidates_2021.parquet" if members else "coverage.parquet"),
            "source_sha256": SHA256[
                "gp_head_candidates_2021.parquet" if members else "coverage.parquet"
            ],
            "source_locator": "/".join(map(str, seat_key(unit))),
            "script": normalize.script_of(
                unit["district"], unit["block"], unit["panchayat"]
            ),
            "seat_members": [],
        }
        for row in members:
            gender = (row["candidate_gender"] or "").strip()
            seat["seat_members"].append(
                {
                    **{k: v for k, v in seat.items() if k != "seat_members"},
                    "candidate_name": row["candidate_name"],
                    "candidate_no": str(row["candidate_serial"]),
                    "candidate_gender": gender,
                    "candidate_woman": {"महिला": 1, "पुरुष": 0}.get(gender, ""),
                    "candidate_age": row["candidate_age"],
                    "candidate_education": "",
                    "votes": row["votes"],
                    "elected": "" if row["elected"] is None else int(row["elected"]),
                    "result": "winner" if row["elected"] is True else "",
                    "source_path": f"{RELEASE}/gp_head_candidates_2021.parquet",
                    "source_url": row["source_url"],
                    "source_sha256": row["source_sha256"],
                    "source_row_number": str(row["source_row"]),
                    "result_source_sha256": row["result_source_sha256"],
                    "result_source_url": row["result_source_url"],
                    "affidavit_url": row["affidavit_url"],
                    "document_id": row["document_id"],
                }
            )
        seats.append(seat)
    if grouped:
        raise ValueError("Bihar candidates outside coverage frame")
    return seats


def slices(root):
    yield {
        "dataset_id": "bihar/gp_head/2021",
        "state": "Bihar",
        "rows": convert(read_release(root)),
        "provenance_level": "dataset",
        "unit_of_observation": "seat_from_candidates",
    }
