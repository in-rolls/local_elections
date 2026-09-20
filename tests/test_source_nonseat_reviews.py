import hashlib
import json

import pandas as pd
import pytest

from local_reservations.tools.source_nonseat_reviews import (
    NORMALIZED_FIELDS,
    RAW_FIELDS,
    apply_source_nonseat_reviews,
)


@pytest.fixture
def review_case(tmp_path):
    evidence = tmp_path / "source-crop.png"
    evidence.write_bytes(b"unit-test evidence bytes")
    raw = dict.fromkeys(RAW_FIELDS)
    raw["winner_raw"] = "UNOPPOSED FOOTNOTE"
    record = {
        "source_sha256": "a" * 64,
        "source_page": 6,
        "source_row_on_page": 49,
        **raw,
        "office_normalized": "PANCH",
        "tier": "gp_ward",
        "caste_reservation": "NONE",
        "woman_reserved": False,
        "quality_flags": "column_alignment_failed;unanchored_fragment",
    }
    review = {
        "source_sha256": "a" * 64,
        "source_page": 6,
        "source_row_on_page": 49,
        "expected_raw": raw.copy(),
        "reason": "footnote",
        "evidence_file": evidence.name,
        "evidence_sha256": hashlib.sha256(evidence.read_bytes()).hexdigest(),
    }
    return tmp_path, record, review


def write_review(root, review, name="case"):
    (root / f"source_nonseat_review_{name}.json").write_text(json.dumps(review))


def test_preserves_observation_and_raw_cells(review_case):
    root, record, review = review_case
    before = record.copy()
    records = [record]
    write_review(root, review)
    result = apply_source_nonseat_reviews(records, root)
    assert result["nonseat_applied"] == 1
    assert result["nonseat_reviewed_rows_absent_from_export"] == 0
    assert records == [record]
    assert record["is_seat_record"] is False
    for field in RAW_FIELDS:
        assert record[field] == before[field]
    for field in NORMALIZED_FIELDS:
        assert record[field] is None
        assert record[f"{field}_before_nonseat_review"] == before[field]
    assert "column_alignment_failed" not in record["quality_flags"]
    assert "unanchored_fragment" in record["quality_flags"]


@pytest.mark.parametrize("value", [None, float("nan"), pd.NA])
def test_accepts_equivalent_missing_raw_cells(review_case, value):
    root, record, review = review_case
    record["ward_raw"] = value
    write_review(root, review)
    result = apply_source_nonseat_reviews([record], root)
    assert result["nonseat_applied"] == 1
    assert record["ward_raw"] is value


@pytest.mark.parametrize("field", sorted(RAW_FIELDS))
def test_declines_any_raw_mismatch(review_case, field):
    root, record, review = review_case
    record[field] = "CHANGED"
    write_review(root, review)
    result = apply_source_nonseat_reviews([record], root)
    assert result["nonseat_precondition_failed"] == 1
    assert "is_seat_record" not in record
    assert record["tier"] == "gp_ward"
    assert "column_alignment_failed" in record["quality_flags"]


def test_requires_all_raw_preconditions(review_case):
    root, record, review = review_case
    del review["expected_raw"]["body_raw"]
    write_review(root, review)
    with pytest.raises(ValueError, match="all six"):
        apply_source_nonseat_reviews([record], root)


def test_rejects_changed_evidence_before_mutation(review_case):
    root, record, review = review_case
    before = record.copy()
    write_review(root, review)
    (root / review["evidence_file"]).write_bytes(b"changed")
    with pytest.raises(ValueError, match="checksum mismatch"):
        apply_source_nonseat_reviews([record], root)
    assert record == before


def test_rejects_conflicting_reviews(review_case):
    root, record, review = review_case
    write_review(root, review, "one")
    write_review(root, review, "two")
    with pytest.raises(ValueError, match="Conflicting"):
        apply_source_nonseat_reviews([record], root)


def test_requires_unique_target(review_case):
    root, record, review = review_case
    write_review(root, review)
    with pytest.raises(ValueError, match="not unique"):
        apply_source_nonseat_reviews([record, record.copy()], root)


def test_reports_absent_target(review_case):
    root, _, review = review_case
    write_review(root, review)
    result = apply_source_nonseat_reviews([], root)
    assert result["nonseat_reviewed_rows_absent_from_export"] == 1


@pytest.mark.parametrize("parent_present", [True, False])
def test_category_fragment_requires_present_candidate_parent(
    review_case, parent_present
):
    root, record, review = review_case
    review["reason"] = "category_fragment"
    review["attached_source_row_on_page"] = 42
    write_review(root, review)
    parent = {**record, "source_row_on_page": 42, "winner_raw": "PRINTED CANDIDATE"}
    records = [record, parent] if parent_present else [record]
    result = apply_source_nonseat_reviews(records, root)
    assert (
        result["nonseat_applied" if parent_present else "nonseat_precondition_failed"]
        == 1
    )
    assert "is_seat_record" not in parent


def test_no_reviews_do_not_change_records(tmp_path):
    records = [{"untouched": True}]
    assert apply_source_nonseat_reviews(records, tmp_path) == {}
    assert records == [{"untouched": True}]
