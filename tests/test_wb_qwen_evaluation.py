import hashlib
import json

from PIL import Image

from local_reservations.states.wb.evaluate_qwen import (
    compare,
    find_reading,
    processed_image,
    reading_fields,
    summarize,
)
from local_reservations.tools.wb_qwen_review import PROMPT, fingerprint


def test_cell_comparison_preserves_roman_suffix_errors_and_blank_hallucinations():
    assert reading_fields("RAKHERA-BISPURIA- ST", "caste") == {
        "name": "RAKHERA-BISPURIA",
        "category": "ST",
        "blank": False,
    }
    assert reading_fields("ILOO-JARGO-SC", "caste") == {
        "name": "ILOO-JARGO",
        "category": "SC",
        "blank": False,
    }
    reference = {
        "name": "Gitaldaha-II",
        "category": "SC",
        "blank": False,
        "name_ambiguous": False,
        "category_ambiguous": False,
    }
    result = compare(reading_fields("Gitaldaha-I (SC)", "caste"), reference)
    assert result["name_correct"] is False
    assert result["category_correct"] is True
    blank = reference | {"name": None, "category": None, "blank": True}
    assert compare(reading_fields("Amjhara", "women"), blank)["false_positive_on_blank"]
    assert compare(reading_fields("—", "women"), blank)["whole_cell_correct"]


def test_ambiguous_name_is_excluded_without_discarding_clear_category():
    reference = {
        "name": None,
        "category": "W",
        "blank": False,
        "name_ambiguous": True,
        "category_ambiguous": False,
    }
    result = compare(reading_fields("A name (W)", "women"), reference)
    assert result["name_correct"] is None
    assert result["whole_cell_correct"] is None
    assert result["category_correct"] is True


def test_prediction_lookup_uses_transformed_image_not_cached_source_id(tmp_path):
    Image.new("RGB", (3, 7), "white").save(tmp_path / "crop.png")
    entry = {"image_path": "crop.png", "image_rotation_clockwise": 90}
    image = processed_image(entry, tmp_path)
    key = fingerprint(image, "model", PROMPT)
    digest = hashlib.sha256(json.dumps(key, sort_keys=True).encode()).hexdigest()
    (tmp_path / f"{digest}.json").write_text(
        json.dumps(
            {
                "source": {"sample_id": 999},
                "fingerprint": key,
                "response": {"response": '{"text": ""}'},
            }
        )
    )
    assert (
        find_reading(entry | {"sample_id": 1}, tmp_path, "model", tmp_path)["text"]
        == ""
    )
    assert (
        find_reading(entry | {"sample_id": 2}, tmp_path, "model", tmp_path)["text"]
        == ""
    )
    assert (
        find_reading(
            entry | {"image_rotation_clockwise": 0}, tmp_path, "model", tmp_path
        )
        is None
    )


def test_weighted_metric_uses_eligible_denominator():
    template = {
        "name_correct": None,
        "category_correct": True,
        "blank_correct": True,
        "false_positive_on_blank": None,
        "whole_cell_correct": True,
    }
    rows = [
        template | {"sampling_weight": 1, "name_correct": True},
        template | {"sampling_weight": 9, "name_correct": False},
        template | {"sampling_weight": 100},
    ]
    metric = summarize(rows)["name_correct"]
    assert metric["denominator"] == 2
    assert metric["excluded"] == 1
    assert metric["design_weighted_fraction"] == 0.1


def test_truncated_model_json_is_retained_as_failed_extraction(tmp_path):
    Image.new("RGB", (3, 7), "white").save(tmp_path / "crop.png")
    entry = {"image_path": "crop.png"}
    key = fingerprint(processed_image(entry, tmp_path), "model", PROMPT)
    digest = hashlib.sha256(json.dumps(key, sort_keys=True).encode()).hexdigest()
    (tmp_path / f"{digest}.json").write_text(
        json.dumps(
            {
                "fingerprint": key,
                "response": {"response": '{"text": "unfinished'},
            }
        )
    )
    result = find_reading(entry, tmp_path, "model", tmp_path)
    assert result["parse_error"]
    assert result["text"] == '{"text": "unfinished'


def test_duplicate_ids_cannot_silently_overwrite_a_reference():
    import pytest

    from local_reservations.states.wb.evaluate_qwen import indexed

    with pytest.raises(ValueError, match="duplicate sample ID"):
        indexed([{"sample_id": 1}, {"sample_id": 1}], "gold")
    with pytest.raises(ValueError, match="sample ID"):
        indexed([{"sample_id": True}], "gold")


def test_manifest_links_source_geometry_and_frozen_image(tmp_path):
    import pytest

    from local_reservations.states.wb.evaluate_qwen import validated_manifest

    Image.new("RGB", (3, 7), "white").save(tmp_path / "crop.png")
    source = {
        "sample_id": 1,
        "row_id": "row",
        "source_path": "source.pdf",
        "source_sha256": "source hash",
        "source_page": 1,
        "axis": "women",
        "tier": "gp_head",
        "bbox": [1, 2, 3, 4],
        "bbox_units": "PDF points",
    }
    inference = source | {"image_path": "crop.png"}
    rendered = inference | {
        "image_sha256": hashlib.sha256((tmp_path / "crop.png").read_bytes()).hexdigest()
    }
    got = validated_manifest({1: source}, {1: inference}, {1: rendered}, tmp_path)
    assert got[1]["image_sha256"] == rendered["image_sha256"]
    with pytest.raises(ValueError, match="geometry"):
        validated_manifest(
            {1: source},
            {1: inference | {"bbox": [2, 3, 4, 5]}},
            {1: rendered},
            tmp_path,
        )
    with pytest.raises(ValueError, match="source mismatch"):
        validated_manifest(
            {1: source},
            {1: inference | {"source_page": 2}},
            {1: rendered},
            tmp_path,
        )
    with pytest.raises(ValueError, match="crop changed"):
        validated_manifest(
            {1: source},
            {1: inference},
            {1: rendered | {"image_sha256": "old"}},
            tmp_path,
        )


def test_broad_ambiguity_cannot_be_counted_as_a_known_negative_category():
    from local_reservations.states.wb.evaluate_qwen import canonical_reference

    reference = canonical_reference(
        {
            "name": None,
            "caste_code": None,
            "women_reserved": None,
            "status": "ambiguous",
            "raw_transcription": "[?]",
        }
    )
    scores = compare(reading_fields("Place (SC)", "caste"), reference)
    assert scores["category_correct"] is None
    assert scores["blank_correct"] is None
    assert scores["whole_cell_correct"] is None


def test_sampling_weights_must_match_frozen_allocation():
    import pytest

    from local_reservations.states.wb.evaluate_qwen import validate_weights

    rows = {1: {"stratum": "a", "frame_n": 10, "sample_n": 1, "sampling_weight": 10}}
    design = {"sample_size": 1, "strata": 1, "eligible_frame_cells": 10}
    validate_weights(rows, design)
    rows[1]["sampling_weight"] = 1
    with pytest.raises(ValueError, match="weight mismatch"):
        validate_weights(rows, design)


def test_gold_and_adjudication_require_matching_image_hash():
    import pytest

    from local_reservations.states.wb.evaluate_qwen import validate_reference_image

    manifest = {1: {"image_sha256": "frozen", "axis": "women"}}
    with pytest.raises(ValueError, match="hash missing or changed"):
        validate_reference_image({"sample_id": 1}, manifest)


def test_blank_false_positive_denominator_is_explicitly_valid_response_only():
    row = {
        "sampling_weight": 1,
        "name_correct": None,
        "category_correct": False,
        "blank_correct": False,
        "false_positive_on_blank": None,
        "whole_cell_correct": False,
    }
    metric = summarize([row])["false_positive_on_blank"]
    assert metric["denominator"] == 0
    assert "valid model responses" in metric["denominator_definition"]
