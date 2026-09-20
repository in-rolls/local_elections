"""The Bihar handoff preserves source flags, empty seats and stated reservations."""

import hashlib
import json
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from local_reservations.common.adapters import bihar_2021 as bihar


def tables():
    """One contested mukhiya seat, and a ward seat nobody stood for."""
    seats = [
        {
            "post_id": 3,
            "unit_id": "u1",
            "district_id": 1,
            "block_id": 1,
            "panchayat_id": 1,
            "seat_no": 1,
            "district": "A",
            "block": "B",
            "panchayat": "C",
            "candidate_records": 2,
            "result_only_candidates": 0,
            "status": "results",
        },
        {
            "post_id": 1,
            "unit_id": "u2",
            "district_id": 1,
            "block_id": 1,
            "panchayat_id": 1,
            "seat_no": 7,
            "district": "A",
            "block": "B",
            "panchayat": "C",
            "candidate_records": 0,
            "result_only_candidates": 0,
            "status": "no_candidates",
        },
    ]
    reservations = [
        {
            "post_id": 3,
            "unit_id": "u1",
            "seat_reservation": "अनुसूचित जन - जाति  (महिला)",
        },
        {"post_id": 1, "unit_id": "u2", "seat_reservation": "पिछड़ा वर्ग  (अन्य)"},
    ]
    candidates = [
        {
            "post_id": 3,
            "unit_id": "u1",
            "in_candidate_list": True,
            "candidate_serial": i,
            "candidate_name": str(i),
            "guardian_name": "G",
            "candidate_gender": "female",
            "candidate_age": 40,
            "votes": 100 if i == 1 else None,
            "elected": True if i == 1 else None,
            "source_url": "https://example.test/candidates",
            "source_sha256": "a",
            "source_row": i,
            "affidavit_url": "https://example.test/a.pdf",
        }
        for i in [1, 2]
    ]
    winners = [
        {
            "post_id": 3,
            "unit_id": "u1",
            "winner_basis": "result_flag",
            "winner_name": "1",
            "votes": 100,
        }
    ]
    return {
        "seats.parquet": seats,
        "current_reservations.parquet": reservations,
        "winners.parquet": winners,
        "candidates.parquet": candidates,
    }


def test_stated_reservations_are_read_and_empty_seats_kept():
    seats = {s["seat_id_printed"]: s for s in bihar.convert(tables())}
    contested, empty = seats["u1"], seats["u2"]
    assert (contested["caste_reservation"], contested["woman_reserved"]) == ("ST", 1)
    assert contested["reservation"] == "ST Woman"
    assert contested["tier"] == "gp_head"
    assert contested["gram_panchayat"] == "C"
    assert contested["winner"] == "1"
    assert contested["winner_basis"] == "published"
    # A backward-class seat that states "other", not a seat with no gender.
    assert (empty["caste_reservation"], empty["woman_reserved"]) == ("BC", 0)
    assert empty["vacant"] == 1
    assert empty["seat_candidates"] == 0
    # Bihar's panch and ward member sit on the village court and the panchayat.
    assert empty["tier"] == "gp_ward"
    assert empty["ward_no"] == "7"
    assert seats["u1"]["seat_members"][1]["elected"] == ""


def test_a_seat_without_a_stated_reservation_is_an_error():
    data = tables()
    data["current_reservations.parquet"] = data["current_reservations.parquet"][:1]
    with pytest.raises(ValueError, match="no reservation feed row"):
        bihar.convert(data)


def test_candidate_counts_must_reconcile_with_the_seat():
    data = tables()
    data["candidates.parquet"] = data["candidates.parquet"][:1]
    with pytest.raises(ValueError, match="coverage does not reconcile"):
        bihar.convert(data)


def test_missing_release_is_an_error(tmp_path):
    with pytest.raises(FileNotFoundError):
        bihar.read_release(tmp_path)


def test_actual_bihar_release_meets_import_contract():
    root = Path(__file__).resolve().parents[2] / "local_elections_bihar"
    if not root.exists():
        pytest.skip("Bihar state release is not checked out")
    seats = bihar.convert(bihar.read_release(root))
    assert len(seats) == 247671
    assert sum(bool(s["winner"]) for s in seats) == 244475
    assert sum(s["seat_candidates"] for s in seats) == 924708
    # Every seat states a reservation, which the mukhiya-only release could not.
    assert all(s["caste_reservation"] for s in seats)
    assert sum(s["woman_reserved"] for s in seats) == 110964


def test_release_reader_rejects_changed_source_bytes(tmp_path, monkeypatch):
    directory = tmp_path / bihar.RELEASE
    directory.mkdir(parents=True)
    files = []
    for name in bihar.SHA256:
        path = directory / name
        pq.write_table(pa.table({"id": [1]}), path)
        checksum = hashlib.sha256(path.read_bytes()).hexdigest()
        monkeypatch.setitem(bihar.SHA256, name, checksum)
        monkeypatch.setitem(bihar.DECLARED, name, 1)
        files.append(
            {"path": name, "rows": 1, "sha256": checksum, "schema": {"id": "Int64"}}
        )
    (directory / "MANIFEST.json").write_text(
        json.dumps(
            {
                "year": 2021,
                "phase": "2021_1",
                "offices": [1, 2, 3, 4, 5, 6],
                "files": files,
            }
        )
    )
    assert len(bihar.read_release(tmp_path)) == len(bihar.SHA256)
    with (directory / "seats.parquet").open("ab") as handle:
        handle.write(b"changed")
    with pytest.raises(ValueError, match="checksum changed"):
        bihar.read_release(tmp_path)
