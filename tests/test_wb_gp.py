import copy
import hashlib
import json

import pytest

from local_reservations.paths import ROOT
from local_reservations.states.wb import parse_hooghly, parse_nadia, parse_results


@pytest.mark.parametrize("cached_digest", [None, "0" * 64, "matching"])
def test_native_cache_requires_matching_source_identity(
    tmp_path, monkeypatch, cached_digest
):
    from local_reservations.states.wb import extract_native

    source = tmp_path / "source.pdf"
    source.write_bytes(b"original PDF bytes")
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    cache = tmp_path / f"{digest}.json"
    record = {
        "version": extract_native.VERSION,
        "pages": [{"text": "preserved source text", "tables": []}],
    }
    if cached_digest is not None:
        record["sha256"] = digest if cached_digest == "matching" else cached_digest
    cache.write_text(json.dumps(record))
    before = cache.read_bytes()
    monkeypatch.setattr(extract_native, "ROOT", tmp_path)
    monkeypatch.setattr(extract_native, "OUT", tmp_path)
    monkeypatch.setattr(
        extract_native.subprocess, "check_output", lambda *a, **k: "Pages: 1\n"
    )
    if cached_digest == "matching":
        assert extract_native.extract(source)["sha256"] == digest
    else:
        with pytest.raises(ValueError, match="Native extraction source hash mismatch"):
            extract_native.extract(source)
        assert cache.read_bytes() == before


def test_hooghly_all_source_cells_and_totals():
    content = parse_hooghly.SOURCE.read_text(encoding="cp1252")
    rows, total = parse_hooghly.parse(content)
    assert len(rows) == 210
    assert len({r["block"] for r in rows}) == 18
    assert total[:2] == [2033, 3440]
    assert sum(r["party_counts_cover_declared"] for r in rows) == 93
    assert sum(r["declared_minus_party_counts"] for r in rows) == 1407
    altered = content.replace(">2033<", ">2034<")
    assert altered != content
    with pytest.raises(ValueError, match="Column totals"):
        parse_hooghly.parse(altered)


@pytest.mark.parametrize(
    ("value", "expected"),
    [("11", 11), ("NIL", 0), ("6(Six)", 6), ("", None), ("1/2", None)],
)
def test_native_totals_do_not_guess(value, expected):
    assert parse_nadia.number(value) == expected


def test_multi_seat_reservations_are_assigned_to_the_printed_seat():
    assert parse_nadia.allocated("3,4") == [3, 4]
    assert parse_nadia.reservation("4 S.C.", [3, 4]) == ({4: "SC"}, [])
    assert parse_nadia.reservation("4 SC(W)", [3, 4], women=True) == ({4: "SCW"}, [])
    assert parse_nadia.reservation("SC", [3, 4])[1] == ["reservation_seat_ambiguous"]
    assert parse_nadia.reservation("7 ST", [3, 4])[1]
    assert parse_nadia.reservation("--", [3, 4]) == ({}, [])


def test_native_source_controls_detect_a_missing_seat():
    source = (
        ROOT
        / "data/wb/gp_source_search/historical_expansion"
        / "nadia_Chanduria-II_61a7353a.pdf"
    )
    index = json.loads((ROOT / "data/wb/derived/native/index.json").read_text())
    entry = next(r for r in index if r["source_path"] == str(source.relative_to(ROOT)))
    record = json.loads((ROOT / entry["cache"]).read_text())
    rows, audit = parse_nadia.parse_document(record, entry["source_path"])
    assert len(rows) == 5
    assert audit["checks"] == []
    assert [r["caste_reservation"] for r in rows] == ["SC", "UR", "SC", "SC", "UR"]
    changed = copy.deepcopy(record)
    changed["pages"][0]["tables"][-1]["rows"].pop()
    rows, audit = parse_nadia.parse_document(changed, entry["source_path"])
    assert "seat_universe_mismatch" in audit["checks"]
    assert all(r["review_status"] == "needs_review" for r in rows)


def test_ocr_numeric_disagreement_stays_null():
    cell = {
        "original": "1011",
        "clean": "1011",
        "column_text": "101",
        "original_confidence": 99,
        "clean_confidence": 99,
        "column_confidence": 99,
    }
    assert parse_results.choose(cell, "integer") == (None, ["readers_disagree"])
    cell["column_text"] = ""
    assert parse_results.choose(cell, "integer") == (1011, [])


@pytest.mark.parametrize(
    ("identity", "expected"),
    [
        ("GP/I-1", 1),
        ("GP/XIV", 14),
        ("GP/V1", None),
        ("GP/X]1", None),
        ("GP/XIVI", None),
        ("3", None),
    ],
)
def test_seat_number_does_not_accept_a_broken_roman_numeral(identity, expected):
    assert parse_results.seat_number(identity)[0] == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("ST-WOMAN", "STW"),
        ("Scheduled Tribes Women", "STW"),
        ("Women", "W"),
        ("X", None),
        ("", None),
    ],
)
def test_reservation_labels_do_not_infer_unreserved(value, expected):
    assert parse_results.category(value)[0] == expected


def test_declared_winner_can_win_a_tie():
    row = {
        "electors": 1121,
        "votes_polled": 1011,
        "votes_rejected": 39,
        "candidate_votes_sum": 972,
        "winner_name": "TUSI DAS",
        "winner_party": "AITC",
    }
    candidates = [
        {"candidate_name": "ARPITA ROY", "party": "IND", "votes": 473},
        {"candidate_name": "TUSI DAS", "party": "AITC", "votes": 473},
        {"candidate_name": "PARUL ROY", "party": "BJP", "votes": 26},
    ]
    assert parse_results.check_seat(row, candidates) == []
    row["votes_polled"] = 1001
    assert "votes:accounting_mismatch" in parse_results.check_seat(row, candidates)


def test_candidate_serials_do_not_split_a_constituency():
    caches = ROOT / "data/wb/derived/alipurduar_2018/ocr"
    record = next(
        r
        for p in caches.glob("*.json")
        if "APD-I IIA" in (r := json.loads(p.read_text()))["source_path"]
        and r["source_page"] == 1
    )
    seats, candidates, audit = parse_results.parse_page(record)
    assert audit["status"] == "parsed"
    assert len(seats) == 4
    assert len(candidates) == 13
    assert [r["candidate_count"] for r in seats] == [3, 3, 4, 3]
    assert all(r["serial_printed"] is None for r in seats)
    assert all(r["gram_panchayat"] == "Banchukamari" for r in seats)
    assert "votes:accounting_mismatch" in seats[0]["quality_flags"]
    ps = copy.deepcopy(record)
    ps["source_path"] = str(ROOT / "APD-I/ANX-IB.PDF")
    assert parse_results.parse_page(ps)[2]["status"] == "not_gp_detail"


def test_gp_continuation_pages_and_mixed_document_tiers():
    caches = ROOT / "data/wb/derived/alipurduar_2018/ocr"
    records = [json.loads(p.read_text()) for p in caches.glob("*.json")]
    continuation = next(
        r
        for r in records
        if "KALCHINI GP" in r["source_path"] and r["source_page"] == 3
    )
    assert parse_results.parse_page(continuation)[0]
    ps = next(
        r
        for r in records
        if "A1B1C1A2B2C2" in r["source_path"] and r["source_page"] == 21
    )
    assert not parse_results.parse_page(ps)[0]


def test_native_page_coverage_matches_an_independent_reader():
    index = json.loads((ROOT / "data/wb/derived/native/index.json").read_text())
    assert index
    for source in index:
        record = json.loads((ROOT / source["cache"]).read_text())
        assert source["pages"] == record["expected_pages"] > 0
        assert len(record["pages"]) == record["expected_pages"]


def test_empty_output_cannot_leave_a_previous_table_silently(tmp_path):
    with pytest.raises(ValueError, match="empty"):
        parse_results.write_table([], tmp_path / "table")
