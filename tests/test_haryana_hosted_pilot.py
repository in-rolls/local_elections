import hashlib
import json
from types import SimpleNamespace

import pytest

from local_reservations.tools.pilot_haryana_hosted import (
    FIELDS,
    MAX_OUTPUT,
    MAX_REQUEST_USD,
    MODEL,
    payload_for,
    response_rows,
    score_reading,
    submit_one,
    usage_cost,
)


def response(finish="stop"):
    return {
        "choices": [
            {
                "finish_reason": finish,
                "message": {"content": json.dumps({"rows": [dict.fromkeys(FIELDS)]})},
            }
        ],
        "usage": {
            "prompt_tokens": 1000,
            "completion_tokens": 2500,
            "completion_tokens_details": {"reasoning_tokens": 500},
        },
    }


class NoNetwork:
    def post(self, *args, **kwargs):
        pytest.fail("A rejected request must not reach the provider")


def test_cap_stops_before_count_or_generation(tmp_path):
    with pytest.raises(ValueError, match="spending limit"):
        submit_one(NoNetwork(), {}, {"label": "AGROHA"}, tmp_path, 0.01)
    assert not list(tmp_path.iterdir())


def test_ambiguous_prior_attempt_reserves_full_cost_and_cannot_retry(tmp_path):
    attempt = {"reserved_usd": MAX_REQUEST_USD, "status": "outcome_unknown"}
    (tmp_path / "attempt_agroha.json").write_text(json.dumps(attempt))
    with pytest.raises(ValueError, match="no automatic retry"):
        submit_one(NoNetwork(), {}, {"label": "AGROHA"}, tmp_path, 1)
    with pytest.raises(ValueError, match="spending limit"):
        submit_one(NoNetwork(), {}, {"label": "HISAR"}, tmp_path, MAX_REQUEST_USD)


def test_request_count_is_capped_even_with_spending_room(tmp_path):
    for label in ["agroha", "hisar", "rohtak"]:
        (tmp_path / f"attempt_{label}.json").write_text(json.dumps({"reserved_usd": 0}))
    with pytest.raises(ValueError, match="request or spending limit"):
        submit_one(NoNetwork(), {}, {"label": "ASSANDH"}, tmp_path, 1)


def test_validation_request_limit_is_two(tmp_path):
    for label in ["assandh", "kaithal"]:
        (tmp_path / f"attempt_{label}.json").write_text(json.dumps({"reserved_usd": 0}))
    with pytest.raises(ValueError, match="request or spending limit"):
        submit_one(NoNetwork(), {}, {"label": "EXTRA"}, tmp_path, 1, max_requests=2)


def test_thinking_tokens_are_included_in_usage_cost():
    assert usage_cost(response()) == pytest.approx(0.0006)
    value = response()
    value["usage"]["completion_tokens"] = MAX_OUTPUT + 1
    with pytest.raises(ValueError, match="reserved request envelope"):
        usage_cost(value)


def test_truncation_and_inferred_numeric_cells_are_rejected():
    with pytest.raises(ValueError, match="truncated"):
        response_rows(response("length"))
    value = response()
    row = dict.fromkeys(FIELDS)
    row["ward_raw"] = 1
    value["choices"][0]["message"]["content"] = json.dumps({"rows": [row]})
    with pytest.raises(ValueError, match="text or null"):
        response_rows(value)


def test_provider_call_has_durable_reservation_and_is_not_retried(tmp_path):
    calls = []

    def create(url, **kwargs):
        calls.append(kwargs)
        saved = json.loads((tmp_path / "attempt_agroha.json").read_text())
        assert saved["reserved_usd"] == MAX_REQUEST_USD
        raise TimeoutError("simulated lost response")

    client = SimpleNamespace(post=create)
    with pytest.raises(TimeoutError):
        submit_one(client, {}, {"label": "AGROHA"}, tmp_path, 1)
    assert len(calls) == 1
    with pytest.raises(ValueError, match="no automatic retry"):
        submit_one(client, {}, {"label": "AGROHA"}, tmp_path, 1)
    assert len(calls) == 1


def test_scoring_requires_office_and_category_not_just_number_of_rows():
    row = dict.fromkeys(FIELDS)
    row.update(body_raw="BHANA", office_raw="Sarpanch", category_raw="S.C.")
    labels = [
        {
            "body": "BHANA",
            "body_continued_from_previous_page": False,
            "ward": None,
            "office": "Sarpanch",
            "caste": "SC",
            "woman": False,
        }
    ]
    assert score_reading([row], labels, "gp_head_and_ward")["gate_passed"]
    row["office_raw"] = "Panch"
    assert not score_reading([row], labels, "gp_head_and_ward")["gate_passed"]

    row["office_raw"] = "Sarpanch"
    row["ward_raw"] = "unreadable"
    assert not score_reading([row], labels, "gp_head_and_ward")["gate_passed"]
    row["ward_raw"] = None
    row["category_raw"] = "S.C. Woman"
    assert not score_reading([row], labels, "gp_head_and_ward")["gate_passed"]


def test_completed_request_resumes_without_a_second_charge(tmp_path):
    raw = json.dumps(response()).encode()
    (tmp_path / "response_agroha.json").write_bytes(raw)
    saved = {
        "label": "AGROHA",
        "request_sha256": "pinned-request",
        "response_sha256": hashlib.sha256(raw).hexdigest(),
        "status": "response_saved; accuracy_unvalidated",
        "reserved_usd": MAX_REQUEST_USD,
    }
    (tmp_path / "attempt_agroha.json").write_text(json.dumps(saved))
    identity = {"label": "AGROHA", "request_sha256": "pinned-request"}
    assert submit_one(NoNetwork(), {}, identity, tmp_path, 1) == saved
    identity["request_sha256"] = "changed-request"
    with pytest.raises(ValueError, match="no automatic retry"):
        submit_one(NoNetwork(), {}, identity, tmp_path, 1)


@pytest.mark.parametrize(
    "usage",
    [
        None,
        {},
        {"prompt_tokens": True, "completion_tokens": 2},
        {"prompt_tokens": -1, "completion_tokens": 2},
        {"prompt_tokens": 1, "completion_tokens": "2"},
    ],
)
def test_missing_or_invalid_usage_cannot_be_priced_as_zero(usage):
    value = response()
    value["usage"] = usage
    with pytest.raises(ValueError, match="usage metadata"):
        usage_cost(value)


@pytest.mark.parametrize("cap", [float("nan"), float("inf"), -1, 0, 11])
def test_invalid_cap_cannot_authorize_submission(tmp_path, cap):
    with pytest.raises(ValueError, match="spending limit"):
        submit_one(NoNetwork(), {}, {"label": "AGROHA"}, tmp_path, cap)


def test_request_uses_direct_meta_model_and_complete_cell_schema():
    payload = payload_for(b"png-bytes")
    assert payload["model"] == MODEL
    assert not payload["model"].startswith("meta/")
    assert payload["max_completion_tokens"] == MAX_OUTPUT
    assert payload["messages"][0]["content"][1]["image_url"]["url"].startswith(
        "data:image/jpeg;base64,"
    )
    schema = payload["response_format"]["json_schema"]["schema"]
    assert set(schema["properties"]["rows"]["items"]["required"]) == set(FIELDS)


def test_successful_response_is_saved_and_reused(tmp_path):
    calls = []

    def create(url, **kwargs):
        calls.append(kwargs)
        return SimpleNamespace(
            content=json.dumps(response()).encode(),
            raise_for_status=lambda: None,
            json=response,
        )

    client = SimpleNamespace(post=create)
    identity = {"label": "AGROHA", "request_sha256": "fixed"}
    result = submit_one(client, {}, identity, tmp_path, 1)
    assert result["usage_priced_usd"] == pytest.approx(0.0006)
    assert submit_one(NoNetwork(), {}, identity, tmp_path, 1) == result
    assert len(calls) == 1
    second = {"label": "HISAR", "request_sha256": "second"}
    submit_one(client, {}, second, tmp_path, MAX_REQUEST_USD + 0.001)
    assert len(calls) == 2


def test_historical_gemini_evidence_remains_scoreable():
    value = {
        "candidates": [
            {
                "finishReason": "STOP",
                "content": {
                    "parts": [{"text": json.dumps({"rows": [dict.fromkeys(FIELDS)]})}]
                },
            }
        ]
    }
    assert response_rows(value) == [dict.fromkeys(FIELDS)]


@pytest.mark.parametrize("ward", ["1 \x07", "1 *", "1 .", "1"])
def test_trailing_marker_preserves_the_printed_ward(ward):
    row = dict.fromkeys(FIELDS)
    row.update(body_raw="BHANA", ward_raw=ward, category_raw="General")
    truth = [
        {
            "body": "BHANA",
            "body_continued_from_previous_page": False,
            "ward": 1,
            "office": "member",
            "caste": "GEN",
            "woman": False,
        }
    ]
    assert score_reading([row], truth, "block_member")["correct_ward"] == 1
    assert row["ward_raw"] == ward
    row["ward_raw"] = "1\x072"
    assert score_reading([row], truth, "block_member")["malformed_ward_readings"] == 1
