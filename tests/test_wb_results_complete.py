import copy
import json
from pathlib import Path

import pytest

from local_reservations.states.wb import parse_results


@pytest.fixture(scope="module")
def result_pages():
    return {
        (Path(record["source_path"]).name, record["source_page"]): record
        for path in (parse_results.OUT / "ocr").glob("*.json")
        if (record := json.loads(path.read_text()))
    }


@pytest.mark.parametrize(
    ("filename", "page", "seats_expected", "candidates_expected"),
    [
        ("APD-II GP IIA.PDF", 12, 8, 21),
        ("FALAKATA GP IIA.PDF", 5, 6, 19),
        ("KALCHINI GP  IA AND IIA.PDF", 18, 2, 5),
    ],
)
def test_rendered_layout_recovery(
    result_pages, filename, page, seats_expected, candidates_expected
):
    seats, candidates, audit = parse_results.parse_page(result_pages[filename, page])
    assert len(seats) == seats_expected
    assert len(candidates) == candidates_expected
    assert audit["office_scope"] == "gp_member"
    assert all(row["source_sha256"] == audit["source_sha256"] for row in seats)


def test_diagonal_scan_marks_do_not_drop_first_candidate(result_pages):
    seats, candidates, audit = parse_results.parse_page(
        result_pages["FALAKATA GP IIA.PDF", 17]
    )
    seat = next(row for row in seats if row["seat_id_printed"] == "JATESWAR II-4")
    names = [
        row["candidate_name"]
        for row in candidates
        if row["seat_row_id"] == seat["row_id"]
    ]
    assert names == ["GOPAL BARMAN", "NIRMAL DAS", "SAMIR BARMAN"]
    assert audit["joined_constituency_fragments"] >= 2


def test_seat_totals_and_winner_can_occupy_first_candidate_subcell(result_pages):
    seats, _, _ = parse_results.parse_page(result_pages["A1B1C1A2B2C2.PDF", 4])
    seat = next(row for row in seats if row["seat_no"] == 2)
    assert (seat["electors"], seat["votes_polled"], seat["votes_rejected"]) == (
        1338,
        1017,
        58,
    )
    assert seat["winner_name"] == "MUNSI MUNDA"
    assert seat["reservation"] == "ST"


def test_conflicting_seat_number_readings_are_retained_as_null(result_pages):
    record = copy.deepcopy(result_pages["APD-I IIA.PDF", 1])
    band = next(c for c in record["cells"] if c["column"] == 2 and "/" in c["original"])
    band.update(
        original="Banchukamari/I-1",
        clean="Banchukamari/II-2",
        column_text="Banchukamari/I-1",
    )
    seats, _, _ = parse_results.parse_page(record)
    seat = next(r for r in seats if json.loads(r["source_bbox"]) == band["bbox"])
    assert seat["seat_no"] is None
    assert "seat_id:numeric_readers_disagree" in seat["quality_flags"]
    assert len(json.loads(seat["seat_id_readings"])) == 3


def test_damaged_header_with_slash_is_not_a_seat(result_pages):
    seats, _, _ = parse_results.parse_page(result_pages["KUMAR GP IA AND IIA.PDF", 11])
    assert not any("CONSTITUENC" in row["seat_id_printed"].upper() for row in seats)
    assert len(seats) == 9


def test_subcell_numeric_conflict_cannot_be_resolved_by_accounting():
    cells = [
        {
            "column": 4,
            "bbox": [0, y, 10, y + 10],
            "original": str(value),
            "clean": str(value),
            "original_confidence": 99,
            "clean_confidence": 99,
        }
        for y, value in [(0, 100), (10, 101)]
    ]
    assert parse_results.choose_in_band(cells, 4, 0, 20, "integer") == (
        None,
        ["readers_disagree"],
    )


def test_all_archive_pages_keep_office_scope(result_pages):
    audits = [parse_results.parse_page(record)[2] for record in result_pages.values()]
    assert len(audits) == 176
    assert sum(a["office_scope"] == "gp_member" for a in audits) == 112
    assert all(
        a["status"] == "parsed" for a in audits if a["office_scope"] == "gp_member"
    )


@pytest.fixture(scope="module")
def office_rows():
    from local_reservations.states.wb import parse_alipurduar_offices

    evidence = json.loads(parse_alipurduar_offices.EVIDENCE.read_text())
    return parse_alipurduar_offices.parse(evidence)


def test_office_positive_axes_do_not_create_an_unlisted_panel(office_rows):
    rows, controls, pages = office_rows
    assert len(rows) == 72
    assert len(pages) == 12
    assert {c["office"]: c["listed_bodies"] for c in controls} == {
        "pradhan": 50,
        "upa_pradhan": 16,
        "sabhapati": 5,
        "sahakari_sabhapati": 1,
    }
    assert all(r["caste_reservation"] in {None, "SC", "ST"} for r in rows)
    assert all(r["woman_reserved"] in {None, 1} for r in rows)
    assert all(c["unlisted_body_reservation"] == "unknown" for c in controls)
    assert all(r["tier"] != "gp_member" for r in rows)


def test_office_axes_are_read_from_the_same_printed_row(office_rows):
    rows, _, _ = office_rows
    selected = {r["name_printed"]: r for r in rows if r["office"] == "pradhan"}
    assert selected["VOLKA BAROBISHA - I"]["reservation"] == "STW"
    assert selected["VOLKA BAROBISHA - II"]["caste_reservation"] is None
    assert selected["CHENGMARI"]["woman_reserved"] is None
    assert selected["GUABARNAGAR"]["reservation"] == "SC"
    assert selected["MAIRADANGA"]["reservation"] == "SCW"
    assert (
        json.loads(selected["TURTURIKHANDA"]["embedded_ocr_raw"])["name"]
        == "TURTURIKHIANDA"
    )


def test_independent_office_controls_detect_a_missing_mark():
    from local_reservations.states.wb import parse_alipurduar_offices

    evidence = json.loads(parse_alipurduar_offices.EVIDENCE.read_text())
    evidence["rows"][0]["women_mark_printed"] = None
    with pytest.raises(ValueError, match="Positive office marks"):
        parse_alipurduar_offices.check_controls(evidence)


def test_archive_tier_scope_never_promotes_ps_or_zp_into_gp(result_pages):
    ps = result_pages["ANX-IB.PDF", 2]
    zp = result_pages["ANX-IIC.PDF", 1]
    assert parse_results.archive_scope(ps) == ("ps_member", "candidate_detail")
    assert parse_results.archive_scope(zp) == ("zp_member", "candidate_detail")
    assert parse_results.parse_page(ps)[0] == []
    assert parse_results.parse_page(zp)[0] == []
    ps_seats = parse_results.parse_page(ps, "ps_member")[0]
    zp_seats = parse_results.parse_page(zp, "zp_member")[0]
    assert len(ps_seats) == 2
    assert {row["seat_no"] for row in zp_seats} == {10, 11}
    assert all(row["gram_panchayat"] is None for row in zp_seats)
    assert all(row["tier"] == "ps_member" for row in ps_seats)


def test_consolidated_counts_are_not_named_seats_or_imputed_zeroes(result_pages):
    record = result_pages["APD-I IA.PDF", 1]
    counts, audit = parse_results.parse_consolidated(record, "gp_member")
    assert audit["status"] == "summary_party_counts_partial"
    assert all(row["record_kind"] == "consolidated_party_count" for row in counts)
    assert {r["declared_elected"] for r in counts if r["party"] == "AITC"} == {93}
    assert all(r["declared_elected"] is None for r in counts if r["party"] == "BSP")


def test_tesseract_quote_is_a_word_not_a_tsv_quote(monkeypatch, tmp_path):
    from types import SimpleNamespace

    from local_reservations.states.wb import extract_results

    raw = (
        "level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext\n"
        '5\t1\t1\t1\t1\t1\t10\t20\t2\t3\t90\t"\n'
        "5\t1\t1\t1\t1\t2\t20\t20\t5\t3\t95\t327\n"
    )
    monkeypatch.setattr(
        extract_results.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(stdout=raw),
    )
    path = tmp_path / "evidence.tsv"
    words = extract_results.read_words(tmp_path / "image.png", 6, path)
    assert [word["text"] for word in words] == ['"', "327"]
    assert words[1]["x"] == 22.5
    assert path.read_text() == raw


@pytest.mark.parametrize(
    ("filename", "page", "serials", "candidates"),
    [
        ("KALCHINI PS IB AND IIB.PDF", 4, set(range(27, 33)), 18),
        ("A1B1C1A2B2C2.PDF", 22, set(range(11, 19)), 24),
        ("Falakata IIB.PDF", 4, {11, 27}, 27),
    ],
)
def test_non_gp_continuation_geometry(
    result_pages, filename, page, serials, candidates
):
    seats, people, audit = parse_results.parse_page(
        result_pages[filename, page], "ps_member"
    )
    assert audit["status"] == "parsed"
    assert {row["seat_no"] for row in seats} == serials
    assert len(people) == candidates
    assert all(row["gram_panchayat"] is None for row in seats)
