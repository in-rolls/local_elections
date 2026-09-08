"""Regressions from the acquired WB Form 1B schedules."""

import json
from pathlib import Path

import pytest

from local_reservations.states.wb.parse_office_scans import (
    cell_fingerprint,
    parse_reading,
    read_cell,
    select_sources,
    tier_for_page,
)


@pytest.mark.parametrize(
    ("raw", "axis", "name", "category"),
    [
        ("TURTURIKHANDA (ST)", "caste", "TURTURIKHANDA", "ST"),
        ("Gangmuri Joypur SC", "caste", "Gangmuri Joypur", "SC"),
        ("Rajarampur Ghoraikshetra(SC)", "caste", "Rajarampur Ghoraikshetra", "SC"),
        ("Gangmuri Joypur W", "women", "Gangmuri Joypur", "women"),
        ("Dhoradaha-I", "women", "Dhoradaha-I", "women"),
        ("Rydak", "caste", "Rydak", None),
        ("", "women", "", None),
        ("WwW", "women", "", None),
        ("West", "caste", "West", None),
    ],
)
def test_source_reading_semantics(raw, axis, name, category):
    assert parse_reading(raw, axis) == (name, category)


def test_caste_mention_does_not_create_negative_women_or_winner(tmp_path):
    cache = tmp_path / "cell.json"
    reading = {
        "text": "Rajarampur Ghoraikshetra(SC)",
        "min_confidence": 91,
        "words": [],
    }
    crop = tmp_path / "cell.png"
    crop.write_bytes(b"source fixture")
    cache.write_text(
        json.dumps(
            {
                "fingerprint": cell_fingerprint(crop),
                "readings": {"6": reading, "7": reading},
            }
        )
    )
    row = read_cell({"cache_path": str(cache), "crop_path": str(crop), "axis": "caste"})
    assert row["caste_category"] == "SC"
    assert row["women_reserved"] is None
    assert row["winner_gender"] is None


def test_block_heading_cannot_be_a_women_mention(tmp_path):
    cache = tmp_path / "cell.json"
    reading = {"text": "Kumargram Block", "min_confidence": 98, "words": []}
    crop = tmp_path / "cell.png"
    crop.write_bytes(b"source fixture")
    cache.write_text(
        json.dumps(
            {
                "fingerprint": cell_fingerprint(crop),
                "readings": {"6": reading, "7": reading},
            }
        )
    )
    row = read_cell({"cache_path": str(cache), "crop_path": str(crop), "axis": "women"})
    assert row["category"] is None
    assert "block_heading" in row["quality_flags"]


def test_mixed_document_tiers():
    source = {"district": "Cooch Behar"}
    assert tier_for_page(source, 5) == "gp_head"
    assert tier_for_page(source, 6) == "gp_deputy"
    assert tier_for_page(source, 9, 0.84) == "block_head"
    assert tier_for_page(source, 9, 0.93) == "block_deputy"
    assert tier_for_page({"district": "Nadia"}, 5) == "gp_head"
    assert tier_for_page({"district": "Nadia"}, 6) == "gp_deputy"


def test_source_manifest_selects_exact_scanned_scope():
    index = Path("data/wb/gp_source_search/manual_entry_index.csv")
    rows = select_sources(index)
    assert len(rows) == 15
    assert sum(int(r["pages"]) for r in rows) == 50
    assert {r["stage"] for r in rows} == {"draft", "final"}
    assert len({r["sha256"] for r in rows}) == 15


def test_changed_crop_invalidates_cached_reading(tmp_path, monkeypatch):
    from local_reservations.states.wb import parse_office_scans as parser

    crop, cache = tmp_path / "crop.png", tmp_path / "cache.json"
    crop.write_bytes(b"old geometry")
    old = {"text": "Wrong (SC)", "min_confidence": 99, "words": []}
    cache.write_text(
        json.dumps(
            {"fingerprint": cell_fingerprint(crop), "readings": {"6": old, "7": old}}
        )
    )
    crop.write_bytes(b"new geometry")
    calls = []

    def recognize(path, psm):
        calls.append(psm)
        return {"text": "Kohinoor (ST)", "min_confidence": 95, "words": []}

    monkeypatch.setattr(parser, "run_ocr", recognize)
    result = read_cell(
        {"cache_path": str(cache), "crop_path": str(crop), "axis": "caste"}
    )
    assert result["name"] == "Kohinoor"
    assert result["caste_category"] == "ST"
    assert calls == [6, 7]


def frozen_scan_cell(sample_id):
    import csv

    from local_reservations.states.wb import parse_office_scans as parser

    overrides = json.loads((parser.OUT / "cell_overrides.json").read_text())
    correction = next(row for row in overrides if row.get("sample_id") == sample_id)
    with (parser.OUT / "row_review.csv").open() as handle:
        rows = list(csv.DictReader(handle))
    row = next(
        row
        for row in rows
        if row["sha256"] == correction["sha256"]
        and int(row["page"]) == correction["page"]
        and int(row["table_row"]) == correction["table_row"]
        and row["axis"] == correction["axis"]
    )
    row["page"], row["table_row"] = int(row["page"]), int(row["table_row"])
    for field in ("category", "caste_category", "women_reserved"):
        row[field] = row[field] or None
    if "visual_name_ambiguous" in row:
        row["visual_name_ambiguous"] = row["visual_name_ambiguous"] == "True"
    return row, correction


def test_ambiguous_exact_name_retains_clear_women_category_and_original_ocr(tmp_path):
    from local_reservations.states.wb import parse_office_scans as parser

    row, correction = frozen_scan_cell(128)
    (tmp_path / "cell_overrides.json").write_text(json.dumps([correction]))
    original = row["raw_reading"]
    result = parser.annotate_rows([row], tmp_path)[0]
    assert result["raw_reading"] == original
    assert result["name"] is None
    assert result["category"] == "women"
    assert result["women_reserved"] is True
    assert result["name_review_status"] == "unresolved_exact_name"
    assert "visual_exact_name_unresolved" in result["quality_flags"]
    assert result["visual_reference_sample_id"] == 128


def test_visual_blank_clears_ocr_name_without_inventing_negative_reservation(tmp_path):
    from local_reservations.states.wb import parse_office_scans as parser

    row, correction = frozen_scan_cell(2)
    (tmp_path / "cell_overrides.json").write_text(json.dumps([correction]))
    row.update(name="OCR artifact", category="women", women_reserved=True)
    result = parser.annotate_rows([row], tmp_path)[0]
    assert result["name"] is None
    assert result["women_reserved"] is None
    assert result["category"] is None
    assert result["name_review_status"] == "not_a_named_entry"


def test_frozen_reference_rejects_changed_cell_bbox(tmp_path):
    from local_reservations.states.wb import parse_office_scans as parser

    row, correction = frozen_scan_cell(128)
    (tmp_path / "cell_overrides.json").write_text(json.dumps([correction]))
    row["bbox"] = json.dumps([0, 0, 1, 1])
    with pytest.raises(ValueError, match="geometry changed"):
        parser.annotate_rows([row], tmp_path)


def test_frozen_reference_rejects_changed_gold_file(tmp_path):
    from local_reservations.states.wb import parse_office_scans as parser

    row, correction = frozen_scan_cell(128)
    correction["reference_evidence"][0]["gold_sha256"] = "changed"
    (tmp_path / "cell_overrides.json").write_text(json.dumps([correction]))
    with pytest.raises(ValueError, match="reference file changed"):
        parser.annotate_rows([row], tmp_path)
