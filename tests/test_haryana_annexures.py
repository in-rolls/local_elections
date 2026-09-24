import json
from pathlib import Path

import pytest

from local_elections.tools.parse_haryana_annexures import (
    body_key,
    chair_concordance,
    date_archived_offices,
    read_chairs,
    read_district_vice_heads,
)

REPORT = (
    Path(__file__).resolve().parents[1]
    / "data/source_search/national/haryana/gap_recovery/raw"
    / "f425f720471d64267d6a.pdf"
)
requires_report = pytest.mark.skipif(
    not REPORT.is_file(),
    reason="requires the externally archived Haryana annexure PDF",
)


@pytest.fixture(scope="module")
def chairs():
    if not REPORT.is_file():
        pytest.skip("requires the externally archived Haryana annexure PDF")
    return read_chairs()


def test_report_separates_person_category_and_reported_column(chairs):
    row = next(r for r in chairs if body_key(r["body_raw"]) == "PATODI")
    assert row["category_column_raw"] == "Gen(w)"
    assert row["person_category_raw"] == "BC(w)"
    assert row["winner_name_raw"] == "SMT.RAJ BALA"
    assert len(chairs) == 114


def test_blank_and_vacant_chair_names_are_preserved(chairs):
    blank = next(r for r in chairs if body_key(r["body_raw"]) == "JIND")
    vacant = next(r for r in chairs if body_key(r["body_raw"]) == "PUNHANA")
    assert blank["winner_name_raw"] is None
    assert vacant["winner_name_raw"] == "VACANT"
    assert blank["person_category_raw"] is vacant["person_category_raw"] is None
    assert blank["category_column_raw"] == vacant["category_column_raw"] == "Gen"


@requires_report
def test_vice_chair_cross_page_continuation_keeps_provenance():
    rows = read_chairs(vice=True)
    row = next(r for r in rows if body_key(r["body_raw"]) == "TAORU")
    assert len(rows) == 114
    assert row["winner_name_raw"] == "SH.AASH\nMOHAMMAD"
    assert row["person_category_raw"] == "Gen"
    assert [f["page"] for f in json.loads(row["source_fragments"])] == [228, 229]
    assert all(r["tier"] == "block_vice_head" for r in rows)


def test_roster_date_requires_same_person_relative_body_and_office(chairs):
    row = chairs[0]
    head = {
        "source_page": 1,
        "source_row_on_page": 1,
        "office_raw": "CHAIRMAN",
        **{
            k: row[k]
            for k in [
                "district_raw",
                "body_raw",
                "winner_name_raw",
                "relation_name_raw",
            ]
        },
    }
    assert date_archived_offices([head], chairs)[0]["year_corroborated"] == 2000
    for field, value in [
        ("winner_name_raw", "Changed"),
        ("relation_name_raw", "Changed"),
        ("body_raw", "Different body"),
        ("office_raw", "VICE-CHAIRMAN"),
    ]:
        changed = head | {field: value}
        assert date_archived_offices([changed], chairs)[0]["year_corroborated"] is None


def test_changed_source_pdf_cannot_reuse_review(tmp_path):
    path = tmp_path / "changed.pdf"
    path.write_bytes(b"changed")
    with pytest.raises(ValueError, match="Changed source report"):
        read_chairs(path)


def test_category_disagreement_is_reported_without_dropping_body_match(chairs):
    row = chairs[0]
    reservation = {
        "body_raw": row["body_raw"],
        "caste_reservation": "SC",
        "woman_reserved": "False",
        "source_page": 22,
        "source_bbox": "[0, 0, 1, 1]",
    }
    changed = row | {"category_column_raw": "Gen"}
    result = chair_concordance([changed], [reservation], [])
    assert result[0]["category_agrees"] is False
    assert result[0]["link_method"] == "body_name"


def test_duplicate_barwala_uses_category_without_claiming_independent_agreement(chairs):
    rows = [r for r in chairs if body_key(r["body_raw"]) == "BARWALA"]
    reservations = [
        {
            "body_raw": "Barwala",
            "caste_reservation": caste,
            "woman_reserved": women,
            "source_page": 22,
            "source_bbox": str(index),
        }
        for index, (caste, women) in enumerate([("SC", "True"), ("UR", "False")])
    ]
    result = chair_concordance(rows, reservations, [])
    assert [r["district_reported_in_annexure"] for r in result] == [
        "HISAR",
        "PANCHKULA",
    ]
    assert all(r["link_method"] == "body_and_category_disambiguation" for r in result)
    with pytest.raises(ValueError, match="reused an office"):
        chair_concordance(rows, [reservations[0], reservations[0]], [])


@requires_report
def test_district_vice_head_columns_preserve_continuations_and_open_border():
    rows = {r["district_raw"]: r for r in read_district_vice_heads()}
    assert len(rows) == 19
    assert rows["KARNAL"]["winner_name_raw"] == "SH.ISHWAR SINGH\nLATHAR"
    assert rows["KARNAL"]["relation_name_raw"] == "SH.CHAMEL\nSINGH"
    assert rows["KAITHAL"]["winner_name_raw"] == "SH.JOGA SINGH @\nJOGI RAM"
    assert rows["KAITHAL"]["relation_name_raw"] == "SH.SANTA SINGH"
    assert rows["YAMUNA NAGAR"]["winner_name_raw"] == "SH.CHANDERPAL"
    assert rows["YAMUNA NAGAR"]["relation_name_raw"] == "SH.AMAR SINGH"
    assert all(r["person_category_raw"] is None for r in rows.values())
    assert all(r["category_column_raw"] == "Un-reserved" for r in rows.values())


@requires_report
def test_vice_president_date_does_not_match_samiti_office():
    row = read_district_vice_heads()[0]
    head = row | {
        "source_row_on_page": 1,
        "office_raw": "VICE-PRESIDENT",
        "body_raw": row["district_raw"],
    }
    assert date_archived_offices([head], [row])[0]["year_corroborated"] == 2000
    wrong = head | {"office_raw": "VICE-CHAIRMAN"}
    assert date_archived_offices([wrong], [row])[0]["year_corroborated"] is None


@requires_report
def test_reviewed_district_typo_requires_corroborating_body():
    row = next(
        r for r in read_district_vice_heads() if r["district_raw"] == "FARIDABAD"
    )
    head = row | {
        "source_row_on_page": 7,
        "office_raw": "VICE-PRESIDENT",
        "district_raw": "FARIDABA",
    }
    result = date_archived_offices([head], [row])[0]
    assert result["year_corroborated"] == 2000
    assert result["district_raw"] == "FARIDABA"
    assert result["district_spelling_review"] is True
    wrong = head | {"body_raw": "ZILA PARISHAD, OTHER"}
    assert date_archived_offices([wrong], [row])[0]["year_corroborated"] is None
