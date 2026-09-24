"""Reservation parsing must not invent seat identities or blank scan codes."""

import json
from types import SimpleNamespace

import pytest

from local_elections.states.wb.parse_nadia import allocated, reservation
from local_elections.states.wb.parse_ward_schedules import (
    allocation,
    category,
    parse_native,
    parse_ocr,
    parse_ocr_ps,
    selected,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("1\n8", [1, 8]), ("1,8", [1, 8]), ("1 8", None), ("18", [18])],
)
def test_nadia_seat_delimiters_preserve_ambiguity(raw, expected):
    assert allocated(raw) == expected


def test_bracketed_women_category():
    assert reservation("2[SC(W)]", [2], women=True) == ({2: "SCW"}, [])
    assert reservation("2[SC(W)]", [3], women=True)[1]


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("Gopalpur/XII-13", 13), ("VI-6", 6), ("VVI--66", None), ("", None)],
)
def test_printed_seat_allocations(raw, expected):
    assert allocation(raw) == expected


def test_reservation_seat_must_agree():
    assert category("Gopalpur/XII-13(SC)", 13) == ("SC", None)
    assert category("Gopalpur/XII-13(SC)", 12)[0] is None
    assert category("WOMAN", 12, women=True) == (1, None)


def native_fixture():
    header = [
        "Name of Gram",
        "Gram Panchayat",
        None,
        None,
        None,
        None,
        "Name of constituency",
        None,
        None,
        None,
        "Allocation",
        "Caste",
        "Women",
    ]
    codes = ["1", "2a", "2b", "2c", "2d", "2e", "3", None, None, None, "4", "5", "6"]
    first = [
        "Name",
        "2",
        "1",
        "0",
        "0",
        "1",
        "Name/I",
        "AC",
        "1",
        "1",
        "I-1",
        "1 SC",
        "1 W",
    ]
    continuation = [None] * 6 + ["Name/I", "AC", "2", "2", "I-1", None, None]
    second = [None] * 6 + ["Name/II", "AC", "3", "3", "II-2", "", ""]
    return {
        "sha256": "abc",
        "pages": [
            {
                "page": 1,
                "text": "Block: Sample",
                "width": 800,
                "height": 600,
                "tables": [
                    {
                        "bbox": [0, 0, 800, 600],
                        "rows": [header, codes, first, continuation, second],
                    }
                ],
            }
        ],
    }


def test_native_merged_continuation_and_structural_blank():
    rows, audit = parse_native(
        native_fixture(),
        {"district": "Cooch Behar", "election_year": "2018", "stage": "draft"},
        "source.pdf",
    )
    assert len(rows) == 2
    assert rows[0]["caste_reservation"] == "SC"
    assert rows[1]["caste_reservation"] == "UR"
    assert all(row["review_status"] == "source_controls_passed" for row in rows)
    assert all(
        row["stage"] == "draft" and row["record_kind"] == "gp_ward_reservation"
        for row in rows
    )
    assert json.loads(rows[1]["raw_cells"])[-2:] == ["", ""]
    assert audit[0]["rows"] == 2


def test_native_missing_cell_is_not_unreserved():
    record = native_fixture()
    record["pages"][0]["tables"][0]["rows"][-1][-2] = None
    rows, _ = parse_native(
        record,
        {"district": "Cooch Behar", "election_year": "2018", "stage": "draft"},
        "source.pdf",
    )
    assert rows[-1]["caste_reservation"] is None
    assert rows[-1]["review_status"] == "needs_review"


def test_scan_blank_is_never_unreserved():
    def word(text, x, y):
        return {
            "text": text,
            "left": str(x),
            "top": str(y),
            "width": "10",
            "height": "10",
        }

    ocr = {
        "source_path": "scan.pdf",
        "source_sha256": "hash",
        "source_page": 1,
        "words": [
            word("(4)", 500, 100),
            word("(5)", 600, 100),
            word("(6)", 700, 100),
            word("Name/IV-4", 300, 200),
        ],
    }
    rows = parse_ocr(ocr, {"district": "Alipurduar", "year": "2023", "stage": "final"})
    assert len(rows) == 1
    assert rows[0]["caste_reservation"] is None
    assert rows[0]["woman_reserved"] is None
    assert rows[0]["review_status"] == "needs_review"


def test_selection_does_not_take_office_orders():
    assert not selected(
        {"district": "Alipurduar", "election_year": "2023", "content_kind": "gp_head"}
    )
    assert selected(
        {"district": "Alipurduar", "election_year": "2023", "content_kind": "gp_ward"}
    )


def test_block_reservation_on_merged_constituency_continuation():
    from local_elections.states.wb.parse_ward_schedules import parse_other_tiers

    record = {
        "sha256": "hash",
        "pages": [
            {
                "page": 1,
                "tables": [
                    {
                        "bbox": [0, 0, 900, 600],
                        "rows": [
                            [
                                "Name of Gram",
                                "Panchayat Samiti",
                                "Constituency",
                                "Area",
                                "Part",
                                "Caste",
                                "Women",
                            ],
                            ["Name", "1", "Name/PS-3", "Name/I", "1", None, None],
                            [None, None, None, "Name/II", "2", "3 SC", "3 W"],
                        ],
                    }
                ],
            }
        ],
    }
    rows = parse_other_tiers(
        record,
        {"district": "Cooch Behar", "election_year": "2018", "stage": "draft"},
        "source.pdf",
    )
    assert len(rows) == 1
    assert rows[0]["record_kind"] == "block_ward_reservation"
    assert rows[0]["caste_reservation"] == "SC"
    assert rows[0]["woman_reserved"] == 1
    assert len(json.loads(rows[0]["raw_cells"])) == 2


def test_rotated_scan_preserves_original_word_boxes():
    from local_elections.states.wb.parse_ward_schedules import orient_ocr_words

    words = [
        {"text": text, "left": "100", "top": str(y), "width": "10", "height": "10"}
        for text, y in [("(4)", 500), ("(5)", 400), ("(6)", 300)]
    ]
    oriented, rotation = orient_ocr_words({"words": words})
    assert rotation == 90
    assert [int(w["left"]) for w in oriented] == [0, 100, 200]
    assert oriented[0]["original_bbox"] == [100, 500, 110, 510]


def test_crosswalk_does_not_create_reservation_data():
    from local_elections.states.wb.parse_ward_schedules import (
        parse_constituency_crosswalk,
    )

    record = {
        "sha256": "hash",
        "pages": [
            {
                "page": 1,
                "tables": [
                    {
                        "bbox": [0, 0, 100, 100],
                        "rows": [
                            [
                                "10/1",
                                "Station",
                                "Name/I",
                                "1",
                                "Name/PS-I",
                                "Block/ZP-1",
                            ],
                        ],
                    }
                ],
            }
        ],
    }
    rows = parse_constituency_crosswalk(record, "source.pdf")
    assert len(rows) == 1
    assert rows[0]["gram_panchayat"] == "Name"
    assert rows[0]["record_kind"] == "constituency_crosswalk"
    assert "caste_reservation" not in rows[0]
    assert "woman_reserved" not in rows[0]


def test_language_routing_requires_page_evidence(tmp_path, monkeypatch):
    from local_elections.states.wb import parse_ward_schedules

    monkeypatch.setattr(parse_ward_schedules, "OUT", tmp_path)
    evidence = tmp_path / "language_pilot"
    evidence.mkdir()
    (evidence / "verified_page_languages.json").write_text(
        json.dumps({"source": {"pages": [1], "language": "eng"}})
    )
    assert parse_ward_schedules.page_language("source", 1) == "eng"
    assert parse_ward_schedules.page_language("source", 2) == "eng+ben"
    assert parse_ward_schedules.page_language("unknown", 1) == "eng+ben"


def test_failed_ocr_is_retried_and_failure_history_retained(tmp_path, monkeypatch):
    from local_elections.states.wb import parse_ward_schedules as ward

    monkeypatch.setattr(ward, "ROOT", tmp_path)
    monkeypatch.setattr(ward, "OUT", tmp_path)
    cache = tmp_path / "ocr/source/0001.json"
    cache.parent.mkdir(parents=True)
    failure = {"status": "extraction_failed", "error": "timed out after 180 seconds"}
    cache.write_text(json.dumps(failure))
    calls = []

    def run(args, **kwargs):
        calls.append((args, kwargs))
        if args[0] == "pdftoppm":
            ward.Image.new("RGB", (20, 30)).save(args[-1] + ".png")
        return SimpleNamespace(stdout='text\tleft\n"\t10\n', stderr="")

    monkeypatch.setattr(ward.subprocess, "run", run)
    ward.ocr_page(("source.pdf", "source", 1))
    result = json.loads(cache.read_text())
    assert result["status"] == "extracted"
    assert result["previous_attempts"] == [failure]
    assert result["words"] == [{"text": '"', "left": "10"}]
    assert result["ocr_timeout_seconds"] == 360
    assert calls[1][1]["timeout"] == 360
    assert calls[1][1]["env"]["OMP_THREAD_LIMIT"] == "1"
    ward.ocr_page(("source.pdf", "source", 1))
    assert len(calls) == 2
    monkeypatch.setattr(ward, "page_language", lambda digest, page: "eng")
    ward.ocr_page(("source.pdf", "source", 1))
    result = json.loads(cache.read_text())
    assert len(calls) == 4
    assert result["language"] == "eng"
    assert len(result["previous_attempts"]) == 2
    assert result["previous_attempts"][1]["language"] == "eng+ben"


@pytest.mark.parametrize(
    ("name", "rows"), [("Name/iii,", 1), ("Name/II", 0), ("II/III", 0)]
)
def test_separate_name_and_allocation_require_matching_printed_constituency(name, rows):
    def word(text, x, y):
        return {
            "text": text,
            "left": str(x),
            "top": str(y),
            "width": "20",
            "height": "10",
        }

    ocr = {
        "source_path": "source.pdf",
        "source_sha256": "hash",
        "source_page": 1,
        "words": [
            word("(4)", 500, 100),
            word("(5)", 600, 100),
            word("(6)", 700, 100),
            word(name, 300, 200),
            word("III-3", 500, 200),
            word("3-SC", 600, 200),
            word("3-W", 700, 200),
        ],
    }
    parsed = parse_ocr(
        ocr, {"district": "Alipurduar", "year": "2018", "stage": "final"}
    )
    assert len(parsed) == rows
    if rows:
        assert parsed[0]["gram_panchayat"] == "Name"
        assert parsed[0]["seat_no"] == 3
        assert parsed[0]["allocated_raw"] == "III-3"
        assert parsed[0]["constituency_area_raw"] == name
        assert parsed[0]["caste_reservation"] == "SC"
        assert parsed[0]["woman_reserved"] == 1
        assert parsed[0]["review_status"] == "needs_review"


def ps_words(values):
    return {
        "source_path": "form_b1.pdf",
        "source_sha256": "hash",
        "source_page": 2,
        "words": [
            {
                "text": value,
                "left": "500",
                "top": str(i * 100),
                "width": "100",
                "height": "20",
            }
            for i, value in enumerate(values)
        ],
    }


def test_ps_reader_keeps_units_conflicts_and_missing_women_separate():
    record = ps_words(
        ["Name/PS-2", "2-ST", "2-W", "Name/PS-3", "3-SC", "3-ST", "999-W"]
    )
    metadata = {"district": "Malda", "year": "2013", "stage": "unclassified"}
    rows = parse_ocr_ps(record, metadata)
    assert len(rows) == 2
    assert all(r["record_kind"] == "block_ward_reservation" for r in rows)
    assert rows[0]["seat_no"] == 2
    assert rows[0]["caste_reservation"] == "ST"
    assert rows[0]["woman_reserved"] == 1
    assert rows[1]["caste_reservation"] is None
    assert rows[1]["woman_reserved"] is None
    assert "caste_missing_or_conflicting" in rows[1]["quality_flags"]
    assert parse_ocr(record, metadata) == []


def test_ps_embedded_codes_and_roman_numbers_remain_source_faithful():
    rows = parse_ocr_ps(
        ps_words(["Name/P.S.-2(SCW)", "Name/PS-II"]),
        {"district": "Malda", "year": "2013", "stage": "final"},
    )
    assert rows[0]["caste_reservation"] == "SC"
    assert rows[0]["woman_reserved"] == 1
    assert rows[1]["seat_no"] is None
    assert rows[1]["seat_no_raw"] == "II"
    assert rows[1]["caste_reservation"] is None


@pytest.mark.parametrize("labels", [("4", "5", "6"), ("[4]", "[5]", "[6]")])
def test_gp_reader_accepts_printed_bare_and_bracketed_column_labels(labels):
    words = []
    for text, x, y in [
        *[(v, 500 + i * 100, 100) for i, v in enumerate(labels)],
        ("Name/IV-4", 300, 200),
        ("4-SC", 600, 200),
    ]:
        words.append(
            {"text": text, "left": str(x), "top": str(y), "width": "20", "height": "10"}
        )
    rows = parse_ocr(
        {
            "source_path": "form_a1.pdf",
            "source_sha256": "hash",
            "source_page": 1,
            "words": words,
        },
        {"district": "Malda", "year": "2013", "stage": "final"},
    )
    assert len(rows) == 1
    assert rows[0]["seat_no"] == 4
    assert rows[0]["caste_reservation"] == "SC"


def test_gp_headerless_reader_abstains_on_conflicting_names_and_codes():
    record = ps_words(
        [
            "Alpha/IV-7",
            "Beta/IV-7",
            "7-SC",
            "7-W",
            "Alpha/V-8",
            "8-ST",
            "Alpha/VI-9(ST)",
        ]
    )
    record["source_path"] = "form_a1.pdf"
    rows = parse_ocr(record, {"district": "Malda", "year": 2013, "stage": "final"})
    assert len(rows) == 3
    assert rows[0]["gram_panchayat"] is None
    assert rows[0]["caste_reservation"] is None
    assert rows[0]["woman_reserved"] is None
    assert rows[1]["seat_no"] == 8
    assert rows[1]["caste_reservation"] is None
    assert rows[1]["woman_reserved"] is None
    assert rows[2]["caste_reservation"] == "ST"


def test_page_pinned_rotation_invalidates_cache_and_preserves_attempt(
    tmp_path, monkeypatch
):
    from local_elections.states.wb import parse_ward_schedules as ward

    monkeypatch.setattr(ward, "ROOT", tmp_path)
    monkeypatch.setattr(ward, "OUT", tmp_path)
    evidence = tmp_path / "semantic_review/orientation_audit.json"
    evidence.parent.mkdir()
    evidence.write_text(
        json.dumps(
            {
                "pages": [
                    {
                        "source_sha256": "hash",
                        "source_page": 2,
                        "review_status": "visually_verified_orientation",
                        "ocr_language": "eng",
                        "pre_ocr_rotation_clockwise_degrees": 90,
                    }
                ]
            }
        )
    )
    cache = tmp_path / "ocr/hash/0002.json"
    cache.parent.mkdir(parents=True)
    previous = {"status": "extracted", "language": "eng", "words": []}
    cache.write_text(json.dumps(previous))
    observed = []

    def run(args, **kwargs):
        if args[0] == "pdftoppm":
            ward.Image.new("RGB", (20, 30)).save(args[-1] + ".png")
        else:
            with ward.Image.open(args[1]) as rendered:
                observed.append(rendered.size)
        return SimpleNamespace(stdout="text\tleft\nSC\t10\n", stderr="")

    monkeypatch.setattr(ward.subprocess, "run", run)
    ward.ocr_page(("source.pdf", "hash", 2))
    record = json.loads(cache.read_text())
    assert observed == [(30, 20)]
    assert record["previous_attempts"] == [previous]
    assert record["render_rotation_clockwise_degrees"] == 90
    assert ward.page_orientation("hash", 1) is None
    assert ward.page_language("hash", 1) == "eng+ben"
    ward.ocr_page(("source.pdf", "hash", 2))
    assert len(observed) == 1


@pytest.mark.parametrize(
    "identities",
    [["Alpha/PS-2", "Beta/PS-2", "2-SC", "2-W"], ["Alpha/PS-2", "Beta/PS-2(SCW)"]],
)
def test_ps_reader_withholds_codes_when_plain_or_coded_names_conflict(identities):
    rows = parse_ocr_ps(
        ps_words(identities), {"district": "Malda", "year": 2013, "stage": "final"}
    )
    assert len(rows) == 1
    assert rows[0]["local_body_printed"] is None
    assert rows[0]["caste_reservation"] is None
    assert rows[0]["woman_reserved"] is None
    assert "conflicting_or_partial_constituency_names" in rows[0]["quality_flags"]
