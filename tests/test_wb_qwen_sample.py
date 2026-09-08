import pytest
from PIL import Image

from local_reservations.states.wb.qwen_sample import ensure_crop, stratified_sample


def frame():
    return [
        {
            "row_id": f"{district}:{i}",
            "district": district,
            "year": "2018",
            "stage": "final",
            "tier": "gp_head",
            "axis": "caste",
            "provisional_kind": "parser_positive",
        }
        for district, count in [("one", 1), ("small", 5), ("large", 20)]
        for i in range(count)
    ]


def test_stratified_review_sampling_retains_small_strata_and_design_weights():
    sampled = stratified_sample(frame(), 10, 17)
    assert len(sampled) == len({r["row_id"] for r in sampled}) == 10
    assert {r["district"] for r in sampled} == {"one", "small", "large"}
    assert sum(r["sampling_weight"] for r in sampled) == pytest.approx(26)
    assert stratified_sample(list(reversed(frame())), 10, 17) == sampled


def test_sample_cannot_silently_omit_strata_or_sample_with_replacement():
    with pytest.raises(ValueError, match="cover all nonempty strata"):
        stratified_sample(frame(), 2, 17)
    with pytest.raises(ValueError, match="cover all nonempty strata"):
        stratified_sample(frame(), 27, 17)


def test_existing_crop_is_checked_against_source_before_provenance_is_attached(
    tmp_path,
):
    target = tmp_path / "cell.png"
    original = Image.new("RGB", (4, 4), "white")
    original.save(target)
    key = {"source_sha256": "one", "bbox": [0, 0, 4, 4]}
    wrong = Image.new("RGB", (4, 4), "black")
    with pytest.raises(ValueError, match="differs from source rerender"):
        ensure_crop(target, key, lambda: (wrong, key["bbox"]))
    assert not target.with_suffix(".provenance.json").exists()
    assert ensure_crop(target, key, lambda: (original, key["bbox"])) == key["bbox"]
    target.unlink()
    assert ensure_crop(target, key, lambda: (original, key["bbox"])) == key["bbox"]
    assert target.exists()
    with pytest.raises(ValueError, match="provenance changed"):
        ensure_crop(target, key | {"source_sha256": "another"}, lambda: (wrong, []))
    wrong.save(target)
    with pytest.raises(ValueError, match="bytes changed"):
        ensure_crop(target, key, lambda: (wrong, []))
