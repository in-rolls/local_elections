"""Contracts for the source-pinned amendment operations, not a full roster."""

import copy
import json

import pyarrow.parquet as pq
import pytest

from local_elections.states.tn.parse_amendments_2001 import (
    OUT,
    digest,
    flatten_operations,
    read_document,
    verify_named_review,
    write_table,
)


@pytest.fixture
def readings():
    return json.loads((OUT / "manual_readings.json").read_text())


def test_all_gp_clauses_reconcile_and_other_tiers_stay_separate(readings):
    rows, sections = flatten_operations(readings)
    assert len(rows) == 456
    assert len(sections) == 16
    assert sum(row["gp_name_printed"] is not None for row in rows) == 451
    assert {row["tier"] for row in rows} == {"gp_president"}
    assert max(row["source_page"] for row in rows) == 16
    assert {row["clause"] for row in readings["clause_audit"]} == {
        str(i) for i in range(1, 13)
    }
    assert all(row["officeholder_sex"] is None for row in rows)


def test_devakottai_source_fixture_categories_and_page_break(readings):
    rows, _ = flatten_operations(readings)
    devakottai = [row for row in rows if row["clause"] == "3"]
    assert len(devakottai) == 42
    assert devakottai[0]["gp_name_printed"] == "Aravayal"
    assert devakottai[0]["new_reservation_caste"] == "SC"
    assert devakottai[0]["new_reservation_women"] is True
    assert devakottai[27]["source_page"] == 3
    assert devakottai[33]["gp_name_printed"] == "Pudukurichi"
    assert devakottai[-1]["gp_name_printed"] == "Nachangulam"
    assert sum(row["new_reservation_women"] for row in devakottai) == 14
    assert sum(row["new_reservation_caste"] == "SC" for row in devakottai) == 10


def test_insertion_anchor_and_serial_only_target_are_not_roster_records(readings):
    rows, _ = flatten_operations(readings)
    insertion = next(row for row in rows if row["clause"] == "2(b)")
    assert insertion["serial_printed"] == "4.A"
    assert insertion["after_serial_printed"] == "4"
    assert insertion["gp_name_printed"] == "Ikkarai Boluvampatti"
    target = next(row for row in rows if row["clause"] == "2(a)")
    assert target["target_serial_printed"] == "2"
    assert target["gp_name_printed"] is None
    assert target["old_category_reading"] == "General (Women)"
    assert target["new_category_reading"] == "SC (Women)"


def test_source_identity_mismatch_rejected(tmp_path):
    source = tmp_path / "different.pdf"
    source.write_bytes(b"different source")
    with pytest.raises(ValueError, match="audited source PDF"):
        read_document(OUT / "manual_readings.json", source)


def test_replacement_count_and_target_imputation_fail_closed(readings):
    broken = copy.deepcopy(readings)
    broken["replacement_sections"][0]["entries"].pop()
    with pytest.raises(ValueError, match="row count differs"):
        flatten_operations(broken)
    broken = copy.deepcopy(readings)
    broken["individual_operations"][0]["name_printed"] = "Inferred name"
    with pytest.raises(ValueError, match="retain unknown names"):
        flatten_operations(broken)


def test_export_keeps_unknown_names_null_and_reservation_boolean(readings, tmp_path):
    rows, _ = flatten_operations(readings)
    write_table(tmp_path / "operations", rows)
    restored = pq.read_table(tmp_path / "operations.parquet").to_pylist()
    assert sum(row["gp_name_printed"] is None for row in restored) == 5
    assert all(row["officeholder_sex"] is None for row in restored)
    assert all(isinstance(row["new_reservation_women"], bool) for row in restored)
    assert len({row["row_id"] for row in restored}) == 456


def test_independent_review_rejects_changed_reading_and_stale_provenance(readings):
    review = json.loads((OUT / "independent_name_review.json").read_text())
    reading_hash = digest(OUT / "manual_readings.json")
    verify_named_review(readings, review, reading_hash)
    with pytest.raises(ValueError, match="predates"):
        verify_named_review(readings, review, "different")
    changed = copy.deepcopy(review)
    changed["rows"][0]["current_name_reading"] = "Unsupported replacement"
    with pytest.raises(ValueError, match="Named reading differs"):
        verify_named_review(readings, changed, reading_hash)
    changed = copy.deepcopy(review)
    changed["rows"][0]["source_sha256"] = "wrong source"
    with pytest.raises(ValueError, match="row source identity mismatch"):
        verify_named_review(readings, changed, reading_hash)
