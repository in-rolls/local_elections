import hashlib
import json
import threading
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import pandas as pd
import pytest

from local_reservations.tools import pilot_haryana_hosted as pilot
from local_reservations.tools import rollout_haryana_hosted as rollout


def completion(rows):
    return {
        "choices": [
            {
                "finish_reason": "stop",
                "message": {"content": json.dumps({"rows": rows})},
            }
        ],
        "usage": {"prompt_tokens": 1000, "completion_tokens": 2500},
    }


@pytest.fixture
def source_review_case(tmp_path, monkeypatch):
    monkeypatch.setattr(rollout, "OUT", tmp_path)
    identity = {"winner_raw": "NAME", "relation_raw": "PARENT", "office_raw": "Panch"}
    key = {"source_sha256": "abc", "source_page": 1, "source_row_on_page": 1}
    review = {
        **key,
        "expected_raw": identity.copy(),
        "office_normalized": "PANCH",
        "caste_reservation": "NONE",
        "woman_reserved": False,
        "category_source_raw": "General",
        "row_alignment_reviewed": True,
    }
    record = {
        **key,
        **identity,
        "category_raw": "unreadable",
        "caste_reservation": None,
        "woman_reserved": None,
        "office_normalized": None,
        "tier": None,
        "ward_raw": "1",
        "quality_flags": "column_alignment_failed;category_unresolved;ward_malformed",
    }
    return tmp_path / "source_office_review_case.json", review, record


@pytest.mark.parametrize(
    ("category", "raw", "woman", "expected"),
    [
        ("NONE", "General", False, "NONE"),
        ("NONE", "General Woman", True, "NONE"),
        ("UR", "General", False, "NONE"),
        ("SC", "SC", False, "SC"),
    ],
)
def test_source_review_accepts_canonical_category(
    source_review_case, category, raw, woman, expected
):
    path, review, record = source_review_case
    review.update(
        caste_reservation=category, category_source_raw=raw, woman_reserved=woman
    )
    path.write_text(json.dumps(review))
    before = record.copy()
    counts = rollout.apply_source_office_reviews([record])
    assert counts["applied"] == 1
    assert counts["reviewed_rows_absent_from_export"] == 0
    assert record["caste_reservation"] == expected
    assert record["woman_reserved"] is woman
    assert record["source_office_review_status"] == "applied"
    assert "column_alignment_failed" not in record["quality_flags"]
    assert "category_unresolved" not in record["quality_flags"]
    assert "ward_malformed" in record["quality_flags"]
    for field, value in before.items():
        if field.endswith("_raw") or field.startswith("source_"):
            assert record[field] == value


@pytest.mark.parametrize(
    ("category", "message"),
    [
        ("INVALID", "Unsupported source-reviewed category"),
        ("SC", "Reviewed category disagrees"),
    ],
)
def test_source_review_rejects_invalid_or_inconsistent_category(
    source_review_case, category, message
):
    path, review, record = source_review_case
    review["caste_reservation"] = category
    path.write_text(json.dumps(review))
    before = record.copy()
    with pytest.raises(ValueError, match=message):
        rollout.apply_source_office_reviews([record])
    assert record == before


@pytest.mark.parametrize(
    ("raw", "category", "woman"),
    [
        ("\u0938\u093e\u092e\u093e\u0928\u094d\u092f", "NONE", False),
        (
            "\u0938\u093e\u092e\u093e\u0928\u094d\u092f \u092e\u0939\u093f\u0932\u093e",
            "NONE",
            True,
        ),
        ("\u092a\u093f\u091b\u0921\u093c\u0940 \u091c\u093e\u0924\u093f", "BC", False),
        (
            "\u0905\u0928\u0941\u0938\u0942\u091a\u093f\u0924 "
            "\u091c\u093e\u0924\u093f \u092e\u0939\u093f\u0932\u093e",
            "SC",
            True,
        ),
    ],
)
def test_source_review_preserves_printed_hindi_category(
    source_review_case, raw, category, woman
):
    path, review, record = source_review_case
    review.update(
        category_source_raw=raw, caste_reservation=category, woman_reserved=woman
    )
    path.write_text(json.dumps(review))
    result = rollout.apply_source_office_reviews([record])
    assert result["applied"] == 1
    assert record["category_source_review_raw"] == raw
    assert record["caste_reservation"] == category
    assert record["woman_reserved"] is woman


@pytest.mark.parametrize("identity", ["winner", "relation"])
def test_source_review_adds_corrected_identity_without_overwriting_raw(
    source_review_case, identity
):
    path, review, record = source_review_case
    original = record[f"{identity}_raw"]
    review[f"{identity}_source_raw"] = "SOURCE CONFIRMED SPELLING"
    path.write_text(json.dumps(review))
    result = rollout.apply_source_office_reviews([record])
    assert result["applied"] == 1
    assert record[f"{identity}_raw"] == original
    assert record[f"{identity}_source_review_raw"] == "SOURCE CONFIRMED SPELLING"
    assert f"{identity}_source_reviewed_raw_preserved" in record["quality_flags"]


@pytest.mark.parametrize("identity", ["winner", "relation"])
@pytest.mark.parametrize("value", [None, "", " ", 1, False])
def test_source_review_rejects_invalid_corrected_identity(
    source_review_case, identity, value
):
    path, review, record = source_review_case
    before = record.copy()
    review[f"{identity}_source_raw"] = value
    path.write_text(json.dumps(review))
    with pytest.raises(ValueError, match="identity must be nonempty text"):
        rollout.apply_source_office_reviews([record])
    assert record == before


def test_source_review_keeps_identity_precondition(source_review_case):
    path, review, record = source_review_case
    review["expected_raw"]["winner_raw"] = "OTHER NAME"
    path.write_text(json.dumps(review))
    counts = rollout.apply_source_office_reviews([record])
    assert counts["precondition_failed"] == 1
    assert record["source_office_review_status"] == "precondition_failed"
    assert record["caste_reservation"] is None
    assert record["office_normalized"] is None
    assert "column_alignment_failed" in record["quality_flags"]


@pytest.mark.parametrize("ward", [None, float("nan"), pd.NA])
def test_source_review_accepts_equivalent_null_ward(source_review_case, ward):
    path, review, record = source_review_case
    review["expected_raw"]["ward_raw"] = None
    review["office_normalized"] = "SARPANCH"
    record["ward_raw"] = ward
    path.write_text(json.dumps(review))
    counts = rollout.apply_source_office_reviews([record])
    assert counts["applied"] == 1
    assert record["ward_raw"] is ward
    assert record["office_normalized"] == "SARPANCH"


@pytest.mark.parametrize(
    ("expected", "actual"), [(None, "1"), (None, ""), ("1", None), ("1", pd.NA)]
)
def test_source_review_rejects_null_value_mismatch(
    source_review_case, expected, actual
):
    path, review, record = source_review_case
    review["expected_raw"]["ward_raw"] = expected
    record["ward_raw"] = actual
    path.write_text(json.dumps(review))
    counts = rollout.apply_source_office_reviews([record])
    assert counts["precondition_failed"] == 1
    assert record["office_normalized"] is None
    assert "column_alignment_failed" in record["quality_flags"]


def test_source_review_rejects_absent_expected_field(source_review_case):
    path, review, record = source_review_case
    review["expected_raw"]["ward_raw"] = None
    del record["ward_raw"]
    path.write_text(json.dumps(review))
    counts = rollout.apply_source_office_reviews([record])
    assert counts["precondition_failed"] == 1


def test_concurrent_requests_reserve_before_network(tmp_path):
    entered, release = threading.Event(), threading.Event()
    calls = []

    def post(*args, **kwargs):
        calls.append(1)
        entered.set()
        assert release.wait(5)
        value = completion([dict.fromkeys(pilot.FIELDS)])
        return SimpleNamespace(
            content=json.dumps(value).encode(),
            json=lambda: value,
            raise_for_status=lambda: None,
        )

    client = SimpleNamespace(post=post)
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(
            pilot.submit_one,
            client,
            {},
            {"label": "first"},
            tmp_path,
            pilot.MAX_REQUEST_USD + 0.001,
        )
        assert entered.wait(5)
        try:
            with pytest.raises(ValueError, match="spending limit"):
                pilot.submit_one(
                    client,
                    {},
                    {"label": "second"},
                    tmp_path,
                    pilot.MAX_REQUEST_USD + 0.001,
                )
        finally:
            release.set()
        first.result()
    assert len(calls) == 1


def test_empty_page_requires_explicit_rollout_handling():
    with pytest.raises(ValueError, match="Missing table rows"):
        pilot.response_rows(completion([]))
    assert pilot.response_rows(completion([]), allow_empty=True) == []


@pytest.mark.parametrize(
    ("office", "family", "expected"),
    [
        ("PANCH", "block_member", "gp_ward"),
        ("SARPANCH", "block_member", "gp_head"),
        ("\u092a\u0902\u091a", "block_member", "gp_ward"),
        ("\u0938\u0930\u092a\u0902\u091a", "block_member", "gp_head"),
        ("", "block_member", "block_member"),
        ("", "gp_head_and_ward", None),
        ("\x07\x07", "block_member", None),
    ],
)
def test_printed_office_overrides_inventory(office, family, expected):
    assert rollout.office_tier(office, family) == expected


@pytest.mark.parametrize("second_page", [2, 3])
def test_export_does_not_silently_fill_cross_page_body(
    tmp_path, monkeypatch, second_page
):
    monkeypatch.setattr(rollout, "OUT", tmp_path)
    frame = []
    for page, body in [(1, "PRINTED BODY"), (second_page, None)]:
        source = {
            "source_sha256": "abc",
            "source_page": str(page),
            "family": "block_member",
        }
        frame.append(source)
        row = dict.fromkeys(pilot.FIELDS)
        row.update(
            body_raw=body, ward_raw=str(page), winner_raw="NAME", category_raw="General"
        )
        raw = json.dumps(completion([row])).encode()
        label = rollout.page_id(source)
        (tmp_path / f"response_{label}.json").write_bytes(raw)
        (tmp_path / f"attempt_{label}.json").write_text(
            json.dumps(
                {
                    "status": "response_saved; accuracy_unvalidated",
                    "response_sha256": hashlib.sha256(raw).hexdigest(),
                    "usage_priced_usd": 0.001,
                    "reserved_usd": pilot.MAX_REQUEST_USD,
                }
            )
        )
    summary = rollout.export(frame)
    assert summary["pages_transcribed"] == 2
    rows = pd.read_parquet(tmp_path / "seat_rows.parquet")
    assert pd.isna(rows.iloc[1].body_within_page)
    assert "incoming_body_context_unvalidated" in rows.iloc[1].quality_flags
    if second_page == 2:
        assert rows.iloc[1].incoming_body_candidate == "PRINTED BODY"
    else:
        assert pd.isna(rows.iloc[1].incoming_body_candidate)
