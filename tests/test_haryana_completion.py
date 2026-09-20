"""Source-bound review decisions and resumable gazette extraction checks."""

import csv
from pathlib import Path

import pandas as pd
import pytest

from local_reservations.tools.parse_haryana_historical import apply_reservation_reviews

BASE = Path(__file__).resolve().parents[1] / "data/source_search/national/haryana"


def review_frame():
    with (BASE / "gap_recovery/reservation_reviews.csv").open() as stream:
        reviews = list(csv.DictReader(stream))
    frame = pd.DataFrame(reviews)[
        ["source_sha256", "source_page", "source_row_on_page", "reservation_raw"]
    ]
    frame[["source_page", "source_row_on_page"]] = frame[
        ["source_page", "source_row_on_page"]
    ].astype(int)
    frame["caste_reservation"] = None
    frame["woman_reserved"] = None
    frame["quality_flags"] = "reservation_unresolved"
    return frame, reviews


def test_reviewed_source_omissions_remain_unknown():
    frame, reviews = review_frame()
    result = apply_reservation_reviews(frame, reviews)
    assert len(result) == 161
    assert result.reservation_raw.equals(frame.reservation_raw)
    complete = result.caste_reservation.notna() & result.woman_reserved.notna()
    assert complete.sum() == 96
    blanks = result.reservation_raw.eq("")
    assert blanks.sum() == 40
    assert (
        result.loc[blanks, ["caste_reservation", "woman_reserved"]].isna().all().all()
    )
    assert (
        result.loc[blanks, "reservation_missing_reason"]
        .eq("not_stated_in_source")
        .all()
    )
    partial = result.reservation_raw.eq("S.C.S")
    assert result.loc[partial, "caste_reservation"].eq("SC").all()
    assert result.loc[partial, "woman_reserved"].isna().all()
    unopposed = result.reservation_raw.eq("Unopposed")
    assert result.loc[unopposed, "caste_reservation"].isna().all()


def test_changed_or_repeated_source_decision_is_rejected():
    frame, reviews = review_frame()
    frame.loc[0, "reservation_raw"] = "Women"
    with pytest.raises(ValueError, match="cell changed"):
        apply_reservation_reviews(frame, reviews)
    frame, reviews = review_frame()
    with pytest.raises(ValueError, match="duplicate or absent"):
        apply_reservation_reviews(frame, reviews + reviews[:1])


def test_samiti_chair_reservations_reconcile_to_printed_totals():
    from local_reservations.tools.parse_haryana_report import parse_chair_reservations

    rows = parse_chair_reservations()
    assert len(rows) == 114
    assert sum(r["woman_reserved"] for r in rows) == 52
    assert sum(r["caste_reservation"] == "SC" for r in rows) == 23
    assert {r["year"] for r in rows} == {2000}
    assert all(r["winner_name_raw"] is None for r in rows)
    barwala = [r for r in rows if r["body_raw"] == "Barwala"]
    assert len(barwala) == 2
    assert {r["caste_reservation"] for r in barwala} == {"NONE", "SC"}
    assert all(r["district_raw"] is None for r in barwala)
    assert len({r["source_bbox"] for r in rows}) == 114


def test_tesseract_literal_quotes_do_not_consume_following_rows(tmp_path):
    import gzip

    from local_reservations.tools.parse_haryana_gazettes import lines_from_tsv

    text = (
        "level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext\n"
        "1\t1\t0\t0\t0\t0\t0\t0\t300\t400\t-1\t\n"
        '5\t1\t1\t1\t1\t1\t10\t20\t5\t10\t80\t"\n'
        "5\t1\t1\t1\t2\t1\t10\t50\t15\t10\t95\tWomen\n"
    )
    path = tmp_path / "words.tsv.gz"
    path.write_bytes(gzip.compress(text.encode()))
    lines, width, height = lines_from_tsv(path)
    assert (width, height) == (300, 400)
    assert [words[0]["text"] for _, words in lines] == ['"', "Women"]


def test_benchmark_counts_wrong_keys_and_duplicate_keys_as_failures():
    from local_reservations.tools.bench_haryana_gazettes import score_candidates

    label = {
        "source_sha256": "sha",
        "source_page": 1,
        "ward": 1,
        "caste": "SC",
        "woman": "true",
    }
    candidate = {
        "source_sha256": "sha",
        "source_page": 1,
        "ward_raw": "1",
        "tier": "district_member",
        "caste_candidate": "SC",
        "woman_candidate": True,
    }
    assert score_candidates([candidate], [label])["correct"] == 1
    assert (
        score_candidates([candidate, candidate], [label])["duplicate_office_key"] == 1
    )
    assert (
        score_candidates([candidate | {"ward_raw": "2"}], [label])["missing_office_key"]
        == 1
    )
    assert (
        score_candidates([candidate | {"woman_candidate": False}], [label])[
            "wrong_category"
        ]
        == 1
    )


def test_honorific_removal_does_not_strip_personal_name_prefixes():
    from local_reservations.tools.audit_haryana_historical import name_key

    assert name_key("SH. RAM SINGH") == "RAMSINGH"
    assert name_key("SHRI RAM SINGH") == "RAMSINGH"
    assert name_key("SHAMSHER") == "SHAMSHER"


def test_ocr_receipt_reuse_checks_bytes_and_preserves_engine_provenance(
    tmp_path, monkeypatch
):
    import json
    import shutil

    from local_reservations.tools import ocr_haryana_gazettes as ocr

    folder = (
        BASE
        / "early_cycles/ocr"
        / "c8f102d6c73e8443a9817930f5ad34bbeffcc1783fa399d021ca6673399d8151"
    )
    receipt = json.loads((folder / "page_0001.tsv.json").read_text())
    target_folder = tmp_path / folder.name
    target_folder.mkdir()
    for name in ["page_0001.tsv.gz", "page_0001.tsv.json"]:
        shutil.copyfile(folder / name, target_folder / name)
    settings = {
        k: receipt[k] for k in ["scale_to", "language", "psm", "tesseract_version"]
    }
    settings["code_sha256"] = "new-receipt-reader"

    def no_reread(*_args, **_kwargs):
        raise RuntimeError("OCR invoked")

    monkeypatch.setattr(ocr.subprocess, "run", no_reread)
    result = ocr.read_page(
        {"sha256": folder.name, "path": "unused.pdf"}, 1, tmp_path, settings
    )
    assert result["output_sha256"] == receipt["output_sha256"]
    assert result["code_sha256"] == receipt["code_sha256"]
    assert result["receipt_parser_sha256"] == "new-receipt-reader"
    (target_folder / "page_0001.tsv.gz").write_bytes(b"corrupt")
    with pytest.raises(RuntimeError, match="OCR invoked"):
        ocr.read_page(
            {"sha256": folder.name, "path": "unused.pdf"}, 1, tmp_path, settings
        )


def test_identical_pdf_cannot_become_offices_in_two_districts():
    from local_reservations.tools.parse_haryana_gazettes import unique_sources

    first = {
        "sha256": "same",
        "url": "hisar",
        "family": "gp_head_and_ward",
        "heading": "HISAR",
        "label": "BARWALA",
    }
    second = first | {"url": "panchkula", "heading": "PANCHKULA"}
    with pytest.raises(ValueError, match="Conflicting index identities"):
        unique_sources([first, second], [])
    rows, aliases = unique_sources(
        [second, first],
        [{"source_sha256": "same", "canonical_url": "hisar", "heading": "HISAR"}],
    )
    assert rows == [first]
    assert len(aliases) == 2
    assert sum(r["is_canonical"] for r in aliases) == 1


def test_vision_response_must_finish_and_preserve_null_cells():
    import json

    from local_reservations.tools.ocr_haryana_members import validate_response

    response = {
        "done": True,
        "done_reason": "stop",
        "response": json.dumps({"rows": [{"ward_raw": "8", "category_raw": None}]}),
    }
    assert validate_response(response) == [{"ward_raw": "8", "category_raw": None}]
    with pytest.raises(ValueError, match="finish normally"):
        validate_response(response | {"done_reason": "length"})
    with pytest.raises(ValueError, match="text or null"):
        validate_response(
            response | {"response": '{"rows":[{"ward_raw":8,"category_raw":null}]}'}
        )


def test_member_review_preserves_source_blank_and_rejects_incomplete_frame():
    from local_reservations.tools.parse_haryana_members import checked_rows

    page = {
        "source_sha256": "pdf",
        "source_page": 2,
        "district_index": "FARIDABAD",
        "printed_ward_keys": [8],
    }
    cell = {
        "source_sha256": "pdf",
        "source_page": 2,
        "district": "FARIDABAD",
        "ward": 8,
        "category_reading": None,
        "caste": None,
        "woman": None,
        "missing_reason": "printed_blank_category",
        "status_text": "Election not held",
    }
    parsed = checked_rows([cell], [page])
    assert parsed[0]["caste_reported"] is None
    assert parsed[0]["woman_reported"] is None
    assert parsed[0]["status_text"] == "Election not held"
    with pytest.raises(ValueError, match="cover the checked page frame"):
        checked_rows([], [page])
    with pytest.raises(ValueError, match="Duplicate or unexpected"):
        checked_rows([cell, cell], [page])
    with pytest.raises(ValueError, match="requires a source reason"):
        checked_rows([cell | {"missing_reason": None}], [page])
    with pytest.raises(ValueError, match="district disagree"):
        checked_rows([cell | {"district": "JHAJJAR"}], [page])


def test_member_model_audit_counts_false_keys_and_source_blank_inventions():
    from local_reservations.tools.parse_haryana_members import compare_model

    cells = [
        {
            "source_sha256": "pdf",
            "source_page": 2,
            "district": "FARIDABAD",
            "ward": 8,
            "caste": None,
            "woman": None,
        }
    ]
    predictions = [
        {
            "source_sha256": "pdf",
            "source_page": 2,
            "ward_raw": "8",
            "category_raw": "Election not held",
        },
        {
            "source_sha256": "pdf",
            "source_page": 2,
            "ward_raw": "1",
            "category_raw": "General",
        },
        {
            "source_sha256": "pdf",
            "source_page": 2,
            "ward_raw": "FARIDABAD",
            "category_raw": "General",
        },
    ]
    scores, _ = compare_model(cells, predictions)
    assert scores["unsupported_text_in_source_blank"] == 1
    assert scores["invalid_predicted_ward"] == 1
    assert scores["extra_predicted_rows"] == 1
    assert scores.get("correct", 0) == 0
    scores, _ = compare_model(cells, [predictions[0] | {"category_raw": None}])
    assert scores["correct_source_blank"] == 1
    scores, _ = compare_model(cells, [predictions[0] | {"source_page": 1}])
    assert scores["missing_office_key"] == 1
    assert scores["extra_predicted_rows"] == 1
