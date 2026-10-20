"""Regression tests for checksum-pinned all-office state observations."""

import hashlib
import json
from pathlib import Path

import pyarrow.parquet as pq
import pytest

from local_elections.paths import ROOT

OBSERVATIONS = ROOT / "data/master/observations"
requires_observation_release = pytest.mark.skipif(
    not (OBSERVATIONS / "index.json").is_file(),
    reason="requires materialized full-state observation releases",
)


def verify_snapshot(path: Path) -> None:
    for line in (path / "SHA256SUMS").read_text().splitlines():
        expected, name = line.split("  ", 1)
        assert hashlib.sha256((path / name).read_bytes()).hexdigest() == expected


@requires_observation_release
def test_up_observation_release_contains_all_offices():
    index = json.loads((OBSERVATIONS / "index.json").read_text())
    entry = index["states"]["Uttar Pradesh"]
    assert entry["rows"] == 1423278
    # UP v3.0 publishes one table per office, record kind and election cycle:
    # 67 files over the same 1,423,278 rows its v2.0 release held in 39.
    assert entry["files"] == 67
    path = OBSERVATIONS / entry["path"]
    provenance = json.loads((path / "provenance.json").read_text())
    names = [item["path"].removesuffix(".parquet") for item in provenance["files"]]
    years = {name.split("_", 1)[0] for name in names}
    tables = {name.split("_", 1)[1] for name in names}
    kinds = (
        "seat_reservation",
        "declared_winner",
        "candidate_record",
        "elected_official",
        "reported_official",
        "source_status_notice",
    )
    offices = {
        table.removesuffix("_" + kind)
        for table in tables
        for kind in kinds
        if table.endswith("_" + kind)
    }
    assert len(tables) == 39
    assert len(offices) == 14
    # Ballia's reservation history is the only source reaching back to 1995.
    assert {"1995", "2000"} <= years
    verify_snapshot(path)


@requires_observation_release
def test_haryana_observation_release_preserves_every_partition():
    index = json.loads((OBSERVATIONS / "index.json").read_text())
    entry = index["states"]["Haryana"]
    assert entry["status"] == "release_ready_with_explicit_quarantines"
    assert entry["rows"] == 70592
    assert entry["files"] == 3
    path = OBSERVATIONS / entry["path"]
    provenance = json.loads((path / "provenance.json").read_text())
    rows = {
        item["path"]: pq.ParquetFile(path / item["path"]).metadata.num_rows
        for item in provenance["files"]
    }
    assert rows == {
        "historical_provisional_observations.parquet": 67770,
        "historical_quarantine.parquet": 61,
        "historical_reviewed_occurrences.parquet": 2761,
    }
    verify_snapshot(path)
