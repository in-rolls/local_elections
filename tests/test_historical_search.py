"""Real-source checks for office categories, column changes and fetch evidence."""

import csv
import json
from pathlib import Path
from typing import ClassVar

import pandas as pd
import pytest

from local_reservations.tools import historical_harvest as harvest
from local_reservations.tools import parse_haryana_historical as parse
from local_reservations.tools import parse_haryana_report as report
from local_reservations.tools.bench_up_history import category, score

FIXTURES = Path(__file__).parent / "fixtures/haryana_historical"
REVIEW_FIXTURES = Path(__file__).parent / "fixtures/haryana_reviews"
REPORT = (
    Path(__file__).resolve().parents[1]
    / "data/source_search/national/haryana/gap_recovery/raw"
    / "f425f720471d64267d6a.pdf"
)


def test_history_benchmark_does_not_reward_filling_unknown_categories():
    assert category(" SC L\n") == "SCL"
    assert category("SC extra") is None
    assert category("-") is None
    readings = [
        {"printed_category": "SC", "recognized_category": "SC"},
        {"printed_category": "SCL", "recognized_category": "SC"},
        {"printed_category": "UR", "recognized_category": None},
        {"printed_category": "-", "recognized_category": "UR"},
        {"printed_category": "-", "recognized_category": None},
    ]
    result = score(readings)
    assert result["correct_printed_categories"] == 1
    assert result["wrong_printed_categories"] == 1
    assert result["abstained_printed_categories"] == 1
    assert result["false_categories_on_missing"] == 1
    assert result["errors_by_printed_category"] == {"SCL": 1, "UR": 1}


def test_categories_do_not_infer_gender_or_replace_unknowns():
    assert parse.reservation("S.C.(Women)") == ("SC", True)
    assert parse.reservation("S.C.") == ("SC", False)
    assert parse.reservation("B.C.(Women)") == ("BC", True)
    assert parse.reservation("Unreserved") == ("NONE", False)
    assert parse.reservation("") == (None, None)
    assert parse.reservation("RESERVED") == (None, None)


def test_main_links_keep_missing_targets_and_district_heading():
    html = '<a href="/nav">Navigation</a><h1>Results</h1><a href="#">share</a>'
    html += '<h2>KARNAL</h2><a href="/404.html">ASSANDH</a>'
    html += '<footer><a href="/footer">Footer</a></footer>'
    links = harvest.links_from_html(html, "https://example.gov.in/")
    assert len(links) == 1
    assert links[0]["heading"] == "KARNAL"
    assert links[0]["url"] == "https://example.gov.in/404.html"


def test_pdf_link_returning_html_is_not_a_document(tmp_path, monkeypatch):
    class Response:
        content = b"<html>not found</html>"
        headers: ClassVar[dict[str, str]] = {"Content-Type": "text/html"}
        status_code = 200
        ok = True
        url = "https://example.gov.in/file.pdf"

    class Session:
        @staticmethod
        def get(*_args, **_kwargs):
            return Response()

    monkeypatch.setattr(harvest.fetch, "session", Session)
    (tmp_path / "raw").mkdir()
    result = harvest.acquire(Response.url, tmp_path, {})
    assert result["status"] == "pdf_link_returned_non_pdf"
    assert (tmp_path / result["path"]).read_bytes() == Response.content
    assert json.loads((tmp_path / "requests.jsonl").read_text())["http_status"] == 200


def test_source_fixtures_match_download_receipts():
    for source in json.loads((FIXTURES / "sources.json").read_text()):
        assert harvest.checksum(FIXTURES / source["fixture"]) == source["sha256"]


def test_badhra_printed_category_typo_preserves_raw_evidence():
    records, _ = parse.parse_document(FIXTURES / "badhra_gp.pdf", "gp_head_and_ward")
    misspelled = [r for r in records if r["reservation_raw"] == "Unreaserved"]
    assert len(misspelled) == 295
    assert all(r["caste_reservation"] == "NONE" for r in misspelled)
    assert all(r["woman_reserved"] is False for r in misspelled)
    assert all("reservation_unresolved" not in r["quality_flags"] for r in misspelled)
    women = [r for r in records if r["reservation_raw"] == "Women"]
    assert women
    assert all(r["woman_reserved"] is True for r in women)
    assert all(r["winner_gender"] is None for r in records)


@pytest.mark.skipif(
    not REPORT.is_file(),
    reason="requires the externally archived Haryana annexure PDF",
)
def test_report_presidents_match_the_reviewed_office_categories():
    records = report.parse_presidents()
    assert len(records) == 19
    assert {r["district_raw"] for r in records if r["woman_reserved"]} == {
        "AMBALA",
        "BHIWANI",
        "FATEHABAD",
        "GURGAON",
        "JIND",
        "KURUKSHETRA",
        "PANCHKULA",
    }
    assert {r["district_raw"] for r in records if r["caste_reservation"] == "SC"} == {
        "FATEHABAD",
        "KAITHAL",
        "KARNAL",
        "KURUKSHETRA",
    }
    assert {r["tier"] for r in records} == {"zp_head"}
    assert {r["year"] for r in records} == {2000}
    assert all(r["winner_gender"] is None for r in records)
    ambala = records[0]
    assert ambala["winner_name_raw"] == "SMT.SUKHVINDE\nR KAUR"
    assert ambala["relation_name_raw"] == "SH.JOGINDER SINGH"
    last = records[-1]
    assert last["district_raw"] == "YAMUNA NAGAR"
    assert last["winner_name_raw"] == "SH.AMI LAL"
    assert last["relation_name_raw"] == "SH.LALA RAM"


def test_report_rejects_an_unreviewed_source(tmp_path):
    path = tmp_path / "report.pdf"
    path.write_bytes(b"changed source")
    with pytest.raises(ValueError, match="differs from the visually reviewed"):
        report.parse_presidents(path)


def test_assandh_gp_head_and_ward_are_distinct():
    records, pages = parse.parse_document(
        FIXTURES / "assandh_gp.pdf", "gp_head_and_ward"
    )
    gp = [r for r in records if r["gram_panchayat_raw"] == "Acchanpur"]
    assert len(gp) == 8
    assert gp[0]["winner_name_raw"] == "Jeeta Ram"
    assert gp[0]["tier"] == "gp_head"
    assert gp[0]["caste_reservation"] == "SC"
    assert gp[0]["woman_reserved"] is False
    assert gp[2]["ward_or_office_raw"] == "2"
    assert gp[2]["winner_name"] == "Premo Devi"
    assert gp[2]["woman_reserved"] is True
    assert gp[2]["unopposed_or_unanimous_mark"] is True
    assert all(r["winner_gender"] is None for r in records)
    assert len(pages) == 13
    assert pages[-1]["status"] == "blank_text_layer"


def test_assandh_samiti_has_thirty_separate_offices():
    records, _ = parse.parse_document(FIXTURES / "assandh_ps.pdf", "block_member")
    assert len(records) == 30
    assert records[0]["winner_name"] == "Phuli Devi"
    assert records[0]["woman_reserved"] is True
    assert records[-1]["winner_name"] == "Bala"
    assert records[-1]["woman_reserved"] is False
    assert {r["tier"] for r in records} == {"block_member"}


@pytest.fixture
def samalkha_review():
    path = REVIEW_FIXTURES / "layout_reviews.csv"
    with path.open() as stream:
        return list(csv.DictReader(stream))


def test_changed_columns_preserve_appended_section_without_assigning_geography(
    samalkha_review,
):
    records, _ = parse.parse_document(
        FIXTURES / "samalkha_gp.pdf", "gp_head_and_ward", samalkha_review
    )
    row = next(
        r
        for r in records
        if r["gram_panchayat_raw"] == "BADHOUR" and r["tier"] == "gp_head"
    )
    assert row["winner_name_raw"] == "CHUHAR SINGH"
    assert row["relation_name_raw"] == "PITAMBAR SINGH"
    assert row["reservation_raw"] == "Unreserved"
    assert "appended_geography_unresolved" in row["quality_flags"]
    assert "ward_cell_contains_extra_text" not in row["quality_flags"]


@pytest.fixture
def section_evidence(samalkha_review):
    left, _ = parse.parse_document(
        FIXTURES / "samalkha_gp.pdf", "gp_head_and_ward", samalkha_review
    )
    right, _ = parse.parse_document(FIXTURES / "raipur_rani_gp.pdf", "gp_head_and_ward")
    path = REVIEW_FIXTURES / "section_reviews.csv"
    with path.open() as stream:
        reviews = list(csv.DictReader(stream))
    frame = pd.DataFrame(
        [r | {"source_sha256": reviews[0]["source_sha256"]} for r in left]
        + [r | {"source_sha256": reviews[0]["evidence_sha256"]} for r in right]
    )
    return frame, reviews


def test_full_section_match_resolves_geography_without_dropping_occurrences(
    section_evidence,
):
    frame, reviews = section_evidence
    result = parse.reconcile_sections(frame, reviews)
    matched = result[result.matched_source_sha256.ne("")]
    assert len(matched) == 354
    assert len(result) == len(frame)
    assert set(matched.section_title_raw) == {"BLOCK RAIPUR RANI, PANCHKULA"}
    assert set(matched.title_raw) == {"BLOCK SAMALKHA, PANIPAT"}
    assert matched.matched_source_page.notna().all()
    assert matched.quality_flags.str.contains("cross_document_section_repeat").all()
    assert not matched.quality_flags.str.contains("appended_geography_unresolved").any()
    assert result.winner_name_raw.equals(frame.winner_name_raw)
    assert result.reservation_raw.equals(frame.reservation_raw)


def test_one_changed_category_prevents_section_geography_assignment(section_evidence):
    frame, reviews = section_evidence
    index = frame.index[frame.source_sha256.eq(reviews[0]["evidence_sha256"])][0]
    frame.loc[index, "reservation_raw"] = "Women"
    with pytest.raises(ValueError, match="no longer matches"):
        parse.reconcile_sections(frame, reviews)
