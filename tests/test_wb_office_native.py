import csv
import hashlib
import json
from copy import deepcopy
from pathlib import Path

import pdfplumber
import pytest

from local_reservations.paths import ROOT
from local_reservations.states.wb import parse_office_native as parser


def curated_rows(tmp_path, monkeypatch, corrections):
    monkeypatch.setattr(parser, "ROOT", tmp_path)
    monkeypatch.setattr(parser, "OUT", tmp_path)
    entries, rows = [], []
    for index, correction in enumerate(corrections):
        source = {
            "row_id": f"cell-{index}",
            "source_sha256": "a" * 64,
            "source_page": "1",
            "source_column": str(correction.get("source_column", 4)),
            "source_bbox": f"[0, {index}, 1, {index + 1}]",
        }
        entries.append(
            source
            | {
                "verified_name": "Example",
                "verified_category": "SC",
                "review_method": "visual_source_review",
                "review_note": "",
                "evidence_references": "",
            }
            | correction
        )
        rows.append(source | {"tier": "gp_head", "quality_flags": "ocr_original"})
    with (tmp_path / "source_transcriptions.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(entries[0]))
        writer.writeheader()
        writer.writerows(entries)
    return rows


@pytest.mark.parametrize(
    ("column", "category"), [(4, "women"), (5, "SC"), (5, "BC"), (4, "UR"), (6, "")]
)
def test_curated_categories_cannot_cross_source_axes(
    tmp_path, monkeypatch, column, category
):
    rows = curated_rows(
        tmp_path,
        monkeypatch,
        [
            {"verified_category": "SC"},
            {"source_column": str(column), "verified_category": category},
        ],
    )
    before = deepcopy(rows)
    with pytest.raises(ValueError, match="category does not match source column"):
        parser.apply_transcriptions(rows)
    assert rows == before


@pytest.mark.parametrize("column", [4, 5])
def test_curated_blank_column_has_no_positive_axis(tmp_path, monkeypatch, column):
    rows = curated_rows(
        tmp_path,
        monkeypatch,
        [
            {
                "source_column": str(column),
                "verified_name": "",
                "verified_category": "",
            }
        ],
    )
    row = parser.apply_transcriptions(rows)[0]
    assert row["caste_reservation"] is None
    assert row["woman_reserved"] is None
    assert json.loads(row["evidence_references"]) == []


def test_evidence_hashes_checked_once_per_path_and_preserved_in_outputs(
    tmp_path, monkeypatch
):
    evidence = tmp_path / "audit.json"
    evidence.write_text('{"source_reading":"Example"}')
    expected = [
        {
            "path": "audit.json",
            "sha256": hashlib.sha256(evidence.read_bytes()).hexdigest(),
        }
    ]
    rows = curated_rows(
        tmp_path,
        monkeypatch,
        [
            {"evidence_references": json.dumps(expected)},
            {
                "source_column": "5",
                "verified_category": "women",
                "evidence_references": json.dumps(expected),
            },
        ],
    )
    original_read = Path.read_bytes
    reads = []

    def counted_read(path):
        if path == evidence:
            reads.append(path)
        return original_read(path)

    monkeypatch.setattr(Path, "read_bytes", counted_read)
    result = parser.apply_transcriptions(rows)
    assert len(reads) == 1
    assert all(json.loads(row["evidence_references"]) == expected for row in result)
    parser.write_table(result, tmp_path / "reviewed")
    with (tmp_path / "reviewed.csv").open() as handle:
        assert all(
            json.loads(row["evidence_references"]) == expected
            for row in csv.DictReader(handle)
        )
    assert all(
        json.loads(json.loads(line)["evidence_references"]) == expected
        for line in (tmp_path / "reviewed.jsonl").read_text().splitlines()
    )
    evidence.write_text('{"source_reading":"Tampered"}')
    with pytest.raises(ValueError, match="evidence reference hash mismatch"):
        parser.apply_transcriptions(rows)
    assert len(reads) == 2


@pytest.mark.parametrize(
    "raw", ["{}", "null", "[{}]", '[{"path":"audit.json"}]', "not-json"]
)
def test_malformed_evidence_references_rejected(tmp_path, monkeypatch, raw):
    rows = curated_rows(tmp_path, monkeypatch, [{"evidence_references": raw}])
    with pytest.raises(ValueError, match="evidence"):
        parser.apply_transcriptions(rows)


def test_reused_evidence_path_still_checks_each_expected_hash(tmp_path, monkeypatch):
    evidence = tmp_path / "audit.json"
    evidence.write_text("evidence")
    sha = hashlib.sha256(evidence.read_bytes()).hexdigest()
    rows = curated_rows(
        tmp_path,
        monkeypatch,
        [
            {
                "evidence_references": json.dumps(
                    [{"path": "audit.json", "sha256": sha}]
                )
            },
            {
                "evidence_references": json.dumps(
                    [{"path": "audit.json", "sha256": "0" * 64}]
                )
            },
        ],
    )
    before = deepcopy(rows)
    with pytest.raises(ValueError, match="evidence reference hash mismatch"):
        parser.apply_transcriptions(rows)
    assert rows == before


def test_visual_corrections_recover_omission_and_remove_signature(
    tmp_path, monkeypatch
):
    selected = {"69c674c94970d93b7cd79adc", "19f1165e9e924f2424889e2e"}
    with (parser.OUT / "source_transcriptions.csv").open() as handle:
        reader = csv.DictReader(handle)
        fields = reader.fieldnames
        corrections = [row for row in reader if row["row_id"] in selected]
    assert len(corrections) == 2
    with (tmp_path / "source_transcriptions.csv").open("w") as handle:
        writer = csv.DictWriter(handle, fields)
        writer.writeheader()
        writer.writerows(corrections)
    monkeypatch.setattr(parser, "OUT", tmp_path)
    rows = [
        {
            key: correction[key]
            for key in (
                "row_id",
                "source_sha256",
                "source_page",
                "source_column",
                "source_bbox",
            )
        }
        | {"tier": "gp_head", "quality_flags": "original_ocr_disagreement"}
        for correction in corrections
    ]
    result = {row["row_id"]: row for row in parser.apply_transcriptions(rows)}
    recovered = result["69c674c94970d93b7cd79adc"]
    assert recovered["office_name_reading"] == "Jangalia"
    assert recovered["woman_reserved"] is True
    assert recovered["caste_reservation"] is None
    signature = result["19f1165e9e924f2424889e2e"]
    assert signature["office_name_reading"] is None
    assert signature["category"] is None
    assert signature["record_kind"] == "visually_reviewed_blank_cell"
    rows[0]["source_bbox"] = "[0, 0, 1, 1]"
    with pytest.raises(ValueError, match="geometry mismatch"):
        parser.apply_transcriptions(rows)


def test_office_columns_preserve_unknown_other_axis():
    assert parser.parse_reading("HENSLA-BC", 4) == ("HENSLA", "BC")
    assert parser.parse_reading("HETGUGUI-W", 5) == ("HETGUGUI", "women")
    assert parser.parse_reading("Chunakhali", 5) == ("Chunakhali", "women")
    assert parser.parse_reading("Chunakhali", 4) == ("Chunakhali", None)
    assert parser.parse_reading("(SC)", 4) == (None, None)
    assert parser.parse_reading("-", 5) == (None, None)
    assert parser.parse_reading("Gosaba Block", 5) == (None, None)


def test_jalpaiguri_printed_office_tiers():
    source = {"district": "Jalpaiguri"}
    assert [parser.tier_for_page(source, p) for p in range(1, 6)] == [
        "gp_head",
        "gp_head",
        "gp_deputy",
        "block_head",
        "block_deputy",
    ]


def test_all_south24_drafts_and_finals_selected():
    selected = [
        r for r in parser.select_sources() if r["district"] == "South 24 Parganas"
    ]
    assert len(selected) == 4
    assert {(r["stage"], parser.tier_for_page(r, 1)) for r in selected} == {
        ("draft", "gp_head"),
        ("draft", "gp_deputy"),
        ("final", "gp_head"),
        ("final", "gp_deputy"),
    }


def test_arsha_source_cells_include_last_row_and_keep_both_axes(tmp_path):
    source = next(
        r for r in parser.select_sources() if r["file"].endswith("1B_Pradhan_Arsha.pdf")
    )
    path = ROOT / "data/wb" / source["file"]
    sha = hashlib.sha256(path.read_bytes()).hexdigest()
    # Geometry crops normally live under ROOT; supply an isolated task directory.
    scratch = ROOT / "data/wb/derived/office_native/test_geometry"
    scratch.mkdir(parents=True, exist_ok=True)
    try:
        with pdfplumber.open(path) as pdf:
            rows = parser.build_page(pdf.pages[0], 1, source, sha, scratch)
        assert len(rows) == 12
        found = [
            parser.parse_reading(r["native_reading"], r["source_column"]) for r in rows
        ]
        assert {v for v in found if v[1]} == {
            ("HENSLA", "BC"),
            ("CHATUHANSA", "women"),
            ("HETGUGUI", "BC"),
            ("HETGUGUI", "women"),
            ("SIRKABAD", "SC"),
            ("MANKIARY", "SC"),
            ("BELDIH", "women"),
        }
        assert {r["block"] for r in rows} == {"Arsha"}
    finally:
        for path in scratch.iterdir():
            path.unlink()
        scratch.rmdir()


def test_brace_glyphs_do_not_drop_printed_caste_marks():
    assert parser.parse_reading("Baishata (BC}", 4) == ("Baishata", "BC")
    assert parser.parse_reading("Ramganga {SC}", 4) == ("Ramganga", "SC")


def test_changed_crop_invalidates_ocr_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(parser, "ROOT", tmp_path)
    crop = tmp_path / "cell.png"
    crop.write_bytes(b"first-image")
    calls = []

    def fake_ocr(path, psm):
        calls.append((path.read_bytes(), psm))
        return {"text": "HENSLA-BC", "min_confidence": 99, "words": []}

    monkeypatch.setattr(parser, "run_ocr", fake_ocr)
    row = {
        "cache_path": "cell.json",
        "crop_path": "cell.png",
        "source_column": 4,
        "native_reading": "HENSLA-BC",
        "heading": False,
        "tier": "gp_head",
    }
    first = parser.read_cell(row)
    assert first["caste_reservation"] == "BC"
    assert first["woman_reserved"] is None
    parser.read_cell(row)
    assert len(calls) == 2
    crop.write_bytes(b"changed-image")
    changed = parser.read_cell(row)
    assert len(calls) == 4
    assert changed["crop_sha256"] != first["crop_sha256"]
    assert changed["review_status"] == "needs_cell_review"


@pytest.mark.parametrize(
    ("stage", "audit_name", "cell_field"),
    [
        ("final", "s24_deputy_independent_audit.json", "observed_positive_cells"),
        ("draft", "s24_draft_deputy_independent_audit.json", "cells"),
    ],
)
def test_source_internal_count_finding_requires_exact_enumerated_rows(
    tmp_path, monkeypatch, stage, audit_name, cell_field
):
    monkeypatch.setattr(parser, "ROOT", tmp_path)
    monkeypatch.setattr(parser, "OUT", tmp_path)
    source = tmp_path / "source.pdf"
    source.write_bytes(b"source")
    sha = hashlib.sha256(source.read_bytes()).hexdigest()
    shared = {
        "district": "Example",
        "election_year": 2018,
        "tier": "gp_deputy",
        "stage": stage,
        "source_path": "source.pdf",
        "source_sha256": sha,
        "source_page": 1,
    }
    (tmp_path / "printed_controls.json").write_text(
        json.dumps(
            [
                shared | {"printed_office_universe": 3, "categories": {"SC": 2}},
            ]
        )
    )
    audit_path = tmp_path / audit_name
    audit_path.write_text(
        json.dumps(
            {
                "source_sha256": sha,
                cell_field: [
                    {
                        "row_id": "a",
                        "name_visually_read": "Name",
                        "category_visually_read": "SC",
                    },
                    {
                        "row_id": "blank",
                        "name_visually_read": None,
                        "category_visually_read": None,
                    },
                ],
            }
        )
    )
    written = []
    monkeypatch.setattr(parser, "write_table", lambda rows, path: written.append(rows))
    row = shared | {
        "row_id": "a",
        "office_name_reading": "Name",
        "category": "SC",
        "review_status": "visually_reviewed_single_reader",
    }
    parser.reconcile_controls([row])
    assert (
        written[-1][0]["control_status"]
        == "source_internal_mismatch_visually_enumerated"
    )
    assert written[-1][0]["independent_visual_enumeration"] == audit_name
    assert (
        written[-1][0]["independent_visual_enumeration_sha256"]
        == hashlib.sha256(audit_path.read_bytes()).hexdigest()
    )
    parser.reconcile_controls([row | {"office_name_reading": "Different"}])
    assert written[-1][0]["control_status"] == "count_mismatch_requires_source_review"
    parser.reconcile_controls([row | {"source_sha256": "different-source"}])
    assert written[-1][0]["control_status"] == "count_mismatch_requires_source_review"
    parser.reconcile_controls([row, row])
    assert written[-1][0]["control_status"] == "count_agreement_not_name_verification"
    audit = json.loads(audit_path.read_text())
    audit[cell_field].append(audit[cell_field][0])
    audit_path.write_text(json.dumps(audit))
    parser.reconcile_controls([row])
    assert written[-1][0]["control_status"] == "count_mismatch_requires_source_review"
