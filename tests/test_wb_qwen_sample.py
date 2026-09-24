import hashlib
import json
import sys

import pytest
from PIL import Image

from local_elections.states.wb.qwen_sample import ensure_crop, stratified_sample


@pytest.mark.parametrize("change", ["replace", "reorder", "unchanged"])
def test_frozen_sample_hash_is_checked_before_crop_work(tmp_path, monkeypatch, change):
    from local_elections.states.wb import qwen_sample

    source = tmp_path / "source.pdf"
    source.write_bytes(b"preserved source bytes")
    sample = [
        {
            "row_id": name,
            "source_path": source.name,
            "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        }
        for name in ["first", "second"]
    ]
    frozen = tmp_path / "sample.json"
    frozen.write_text(json.dumps(sample))
    (tmp_path / "design.json").write_text(
        json.dumps(
            {
                "seed": 17,
                "sample_sha256": hashlib.sha256(frozen.read_bytes()).hexdigest(),
            }
        )
    )
    if change == "replace":
        sample[0]["row_id"] = "different cell"
    elif change == "reorder":
        sample.reverse()
    frozen.write_text(json.dumps(sample))
    before = frozen.read_bytes()
    monkeypatch.setattr(qwen_sample, "ROOT", tmp_path)
    monkeypatch.setattr(qwen_sample, "OUT", tmp_path)
    monkeypatch.setattr(sys, "argv", ["qwen_sample", "--size", "2", "--seed", "17"])

    def crop_work(*args, **kwargs):
        raise RuntimeError("crop work started")

    monkeypatch.setattr(qwen_sample.pdfplumber, "open", crop_work)
    if change == "unchanged":
        with pytest.raises(RuntimeError, match="crop work started"):
            qwen_sample.main()
    else:
        with pytest.raises(ValueError, match="Frozen sample hash mismatch"):
            qwen_sample.main()
    assert frozen.read_bytes() == before


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
