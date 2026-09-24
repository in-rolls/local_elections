"""Regressions pinned to the acquired 2018 draft gazette scans."""

import json

import pytest

from local_elections.states.wb import parse_base_drafts as parser


@pytest.fixture(scope="module")
def drafts():
    corrections = json.loads((parser.BASE / "visual_corrections.json").read_text())
    rows = []
    for source in sorted((parser.DATA / "draft").glob("*.pdf")):
        got, _ = parser.draft_document(source, corrections.get(source.name, {}))
        rows.extend(got)
    return rows


@pytest.mark.parametrize(
    ("stem", "district"),
    [
        ("1343-SEC-Draft order of Murshidabad district", "Murshidabad"),
        ("1331-SEC-draft reservation-coochbehar", "Cooch Behar"),
        ("1349-SEC-draft reservation-South 24 Parganas", "South 24 Pgs"),
    ],
)
def test_distinct_filename_patterns(stem, district):
    assert parser.district_of(stem) == district


def test_recovered_header_does_not_drop_entire_district(drafts):
    rows = [row for row in drafts if row["district"] == "Dakshin Dinajpur"]
    assert len(rows) == 18
    first = next(row for row in rows if row["seat_no"] == 1)
    assert first["block"] == "Kushmandi"
    assert first["women_reserved"] is True
    assert first["caste_reservation"] is None


def test_split_south_24_identifiers_keep_distinct_categories(drafts):
    rows = {row["seat_no"]: row for row in drafts if row["district"] == "South 24 Pgs"}
    assert len(rows) == 81
    assert rows[56]["block"] == "Diamond Harbour-I"
    assert rows[56]["caste_reservation"] is None
    assert rows[57]["caste_reservation"] == "BC"
    assert rows[57]["women_reserved"] is True
    assert rows[58]["caste_reservation"] == "SC"
    assert rows[58]["women_reserved"] is None
    assert rows[59]["caste_reservation"] == "BC"


def test_restored_anchor_prevents_women_marker_leaking_to_previous_seat(drafts):
    rows = {
        row["seat_no"]: row for row in drafts if row["district"] == "Purba Bardhaman"
    }
    assert rows[28]["caste_reservation"] == "SC"
    assert rows[28]["women_reserved"] is None
    assert rows[29]["women_reserved"] is True
    assert rows[29]["seat_id_printed"] == "Burdwan-I ZP-29"


def test_unread_axes_and_draft_stage_cannot_become_final_or_winner(drafts):
    assert len(drafts) == 787
    assert len({row["record_id"] for row in drafts}) == len(drafts)
    assert {row["stage"] for row in drafts} == {"draft"}
    assert all(row["winner_gender"] is None for row in drafts)
    assert {row["women_reserved"] for row in drafts} == {True, None}
    assert {row["caste_reservation"] for row in drafts} <= {"SC", "ST", "BC", None}


def test_visual_repair_rejects_changed_source():
    source = next((parser.DATA / "draft").glob("1339-*.pdf"))
    with pytest.raises(ValueError, match="source changed"):
        parser.draft_document(source, {"source_sha256": "different"})


def test_visual_repair_rejects_changed_ocr_geometry():
    source = next((parser.DATA / "draft").glob("1339-*.pdf"))
    corrections = json.loads((parser.BASE / "visual_corrections.json").read_text())
    correction = corrections[source.name]
    correction["ocr_sha256"]["1"] = "different"
    with pytest.raises(ValueError, match="OCR geometry changed"):
        parser.draft_document(source, correction)
