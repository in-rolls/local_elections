"""Haryana release-boundary regression tests."""

from pathlib import Path

import pyarrow.parquet as pq
import pytest

from local_reservations.common.adapters.haryana import convert
from local_reservations.tools.build_haryana_release import (
    build,
    printing_classification,
)

ROOT = Path(__file__).resolve().parents[1]
OBSERVATIONS = ROOT / "data/master/observations"
SIBLING_SOURCE = ROOT.parent / "local_elections_haryana/data/2016/gp_reservation.csv"
requires_full_haryana_release = pytest.mark.skipif(
    not (OBSERVATIONS / "index.json").is_file() or not SIBLING_SOURCE.is_file(),
    reason=(
        "requires materialized observations and the external Haryana source repository"
    ),
)


def source_row(**updates):
    """Return one minimal sibling-format Haryana row."""
    row = {
        "caste_reservation": "NONE",
        "woman_reserved": "0",
        "district": "Karnal",
        "block": "Indri",
        "gram_panchayat": "Test",
        "ward_no": "1",
        "winner": "Person",
        "father_husband": "Relation",
        "vacant": "0",
        "unopposed": "0",
        "reservation_raw": "Unreserved",
        "script": "latin",
        "printings_agree": "0",
        "source_pdf": "test.pdf",
    }
    row.update(updates)
    return row


def test_ward_does_not_inherit_gp_head_printing_disagreement(tmp_path):
    path = tmp_path / "ward_reservation.csv"
    path.parent.joinpath("pdfs").mkdir()
    got = convert(source_row(), "2022", "gp_ward", "ward", path, tmp_path)
    assert got["printings_agree"] == ""
    got = convert(source_row(), "2022", "gp_head", "sarpanch", path, tmp_path)
    assert got["printings_agree"] == "0"


def test_printing_disagreement_scope_is_explicit():
    assert (
        printing_classification("gp_ward", "0")
        == "inherited_gp_head_comparison_not_ward_defect"
    )
    assert printing_classification("gp_head", "0").startswith("gp_head_source")


@requires_full_haryana_release
def test_haryana_release_reconciles_every_row(tmp_path: Path):
    receipt = build(tmp_path)
    assert receipt["release_ready"] is True
    assert receipt["modern"]["input_rows"] == 135073
    assert (
        receipt["modern"]["included_rows"] + receipt["modern"]["quarantined_rows"]
        == 135073
    )
    assert receipt["modern"]["printing_disagree_reconciliation"] == {
        "total": 1536,
        "stale_ward_scope_artifacts": 1392,
        "legitimate_gp_head_source_variations": 144,
        "actual_unresolved_defects_from_printing_flag": 0,
        "included_rows": 1517,
        "quarantined_for_independent_identity_defects": 19,
        "proof": receipt["modern"]["printing_disagree_reconciliation"]["proof"],
    }
    historical = receipt["historical"]
    assert (
        historical["included_source_reviewed_occurrences"]
        + historical["reviewed_unresolved_quarantine"]
        + historical["provisional_or_nonseat_preserved_outside_release"]
        == historical["input_observations"]
        == 70592
    )
    assert historical["missing_heading_quarantine"] == 32
    printing = pq.read_table(tmp_path / "printing_reconciliation.parquet")
    assert printing.num_rows == 1536
