"""A clean checkout must contain every declared UP wave."""

import gzip
import hashlib

import pytest

from local_reservations.common.adapters import uttar_pradesh as up


def test_gzip_candidate_input_preserves_values_and_source_ordinals(
    tmp_path, monkeypatch
):
    payload = b'id,name\r\n202725,"A, B"\r\n219438,C\r\n'
    compressed = gzip.compress(payload, mtime=0)
    path = tmp_path / "candidates.csv.gz"
    path.write_bytes(compressed)
    monkeypatch.setitem(
        up.SOURCE_SHA256, "2021", hashlib.sha256(compressed).hexdigest()
    )
    rows = up.read(path, "2021", 2)
    assert rows == [
        {"id": "202725", "name": "A, B", "source_row_number": "1"},
        {"id": "219438", "name": "C", "source_row_number": "2"},
    ]


def test_gzip_candidate_input_rejects_a_changed_hash(tmp_path, monkeypatch):
    path = tmp_path / "candidates.csv.gz"
    path.write_bytes(gzip.compress(b"id,name\n202725,A\n", mtime=0))
    monkeypatch.setitem(up.SOURCE_SHA256, "2021", "0" * 64)
    with pytest.raises(SystemExit, match="published input hash changed"):
        up.read(path, "2021", 1)


@pytest.mark.parametrize("year", ["2005", "2010", "2015", "2021"])
def test_missing_declared_wave_fails_instead_of_disappearing(tmp_path, year):
    with pytest.raises(FileNotFoundError):
        up.read(tmp_path / "missing.csv", year, up.DECLARED[year])
