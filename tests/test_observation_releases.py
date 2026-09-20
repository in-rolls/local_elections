"""Regression tests for checksum-pinned all-office state observations."""

import hashlib
import json
from pathlib import Path

import pyarrow.parquet as pq
import pytest

from local_reservations.paths import ROOT

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
    # Uttar Pradesh now comes from its tagged release, which groups the upper
    # tiers as declared winners rather than candidate records: four files where
    # there were five, over the same 1,423,278 rows.
    assert entry["files"] == 39
    path = OBSERVATIONS / entry["path"]
    manifest = json.loads((path / "source_manifest.json").read_text())
    assert len(manifest["offices"]) == 14
    assert {source["id"] for source in manifest["sources"]} >= {
        "ballia_samiti_head_historical_reservations",
        "ballia_zilla_parishad_member_historical_reservations",
    }
    verify_snapshot(path)


@requires_observation_release
def test_haryana_observation_release_preserves_every_partition():
    index = json.loads((OBSERVATIONS / "index.json").read_text())
    entry = index["states"]["Haryana"]
    assert entry["status"] == "release_ready_with_explicit_quarantines"
    assert entry["rows"] == 207201
    assert entry["files"] == 6
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
        "modern_quarantine.parquet": 1202,
        "modern_seats.parquet": 133871,
        "printing_reconciliation.parquet": 1536,
    }
    verify_snapshot(path)
