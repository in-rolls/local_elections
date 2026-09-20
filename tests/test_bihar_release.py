"""The Bihar handoff preserves source flags, missing results and empty seats."""

from pathlib import Path

import pytest

from local_reservations.common.adapters import bihar_2021 as bihar


def tables():
    """Two candidates without a winner flag, plus a panchayat with no records."""
    coverage = [
        {
            "district_id": 1,
            "block_id": 1,
            "panchayat_id": p,
            "district": "A",
            "block": "B",
            "panchayat": str(p),
            "candidate_records": 2 if p == 1 else 0,
            "winner_records": 0,
            "winner_status": "no_winner_flag" if p == 1 else "empty_results",
        }
        for p in [1, 2]
    ]
    candidates = [
        {
            "district_id": 1,
            "block_id": 1,
            "panchayat_id": 1,
            "candidate_serial": i,
            "candidate_name": str(i),
            "candidate_gender": "महिला",
            "candidate_age": 40,
            "votes": 100 if i == 1 else None,
            "elected": False if i == 1 else None,
            "source_url": "https://example.test/candidates",
            "source_sha256": "a",
            "source_row": i,
            "result_source_sha256": "b" if i == 1 else None,
            "result_source_url": "https://example.test/results",
            "affidavit_url": "https://example.test/a.pdf",
            "document_id": f"1_1_1_{i}",
        }
        for i in [1, 2]
    ]
    return {
        "coverage.parquet": coverage,
        "gp_head_candidates_2021.parquet": candidates,
        "gp_head_winner_records_2021.parquet": [],
    }


def test_missing_reservation_and_winner_are_not_inferred():
    seats = bihar.convert(tables())
    assert len(seats) == 2
    assert all(s["winner"] == "" and s["woman_reserved"] == "" for s in seats)
    assert seats[0]["seat_members"][1]["elected"] == ""
    assert seats[1]["seat_candidates"] == 0


def test_duplicate_candidate_cannot_enter_pooled_data():
    data = tables()
    data["gp_head_candidates_2021.parquet"].append(
        data["gp_head_candidates_2021.parquet"][0]
    )
    with pytest.raises(ValueError, match="Duplicate"):
        bihar.convert(data)


def test_missing_release_is_an_error(tmp_path):
    with pytest.raises(FileNotFoundError):
        bihar.read_release(tmp_path)


def test_actual_bihar_release_meets_import_contract():
    root = Path(__file__).resolve().parents[2] / "local_elections_bihar"
    if not root.exists():
        pytest.skip("Bihar state release is not checked out")
    data = bihar.read_release(root)
    seats = bihar.convert(data)
    assert len(seats) == 8067
    assert sum(bool(s["winner"]) for s in seats) == 8050
    assert sum(s["seat_candidates"] for s in seats) == 66430


def test_release_reader_rejects_changed_source_bytes(tmp_path, monkeypatch):
    import hashlib
    import json

    import pyarrow as pa
    import pyarrow.parquet as pq

    directory = tmp_path / bihar.RELEASE
    directory.mkdir(parents=True)
    files = []
    for name in bihar.SHA256:
        table = pa.table({"id": [1]})
        path = directory / name
        pq.write_table(table, path)
        checksum = hashlib.sha256(path.read_bytes()).hexdigest()
        monkeypatch.setitem(bihar.SHA256, name, checksum)
        monkeypatch.setitem(bihar.DECLARED, name, 1)
        files.append(
            {"path": name, "rows": 1, "sha256": checksum, "schema": {"id": "int64"}}
        )
    (directory / "MANIFEST.json").write_text(
        json.dumps({"year": 2021, "source_phase": "2021_1", "files": files})
    )
    assert len(bihar.read_release(tmp_path)) == 3
    with (directory / "gp_head_candidates_2021.parquet").open("ab") as handle:
        handle.write(b"changed")
    with pytest.raises(ValueError, match="checksum changed"):
        bihar.read_release(tmp_path)
