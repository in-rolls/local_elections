"""Reference aggregates retain source units, missing values and contradictions."""

import json
import shutil

import pytest

from local_reservations.paths import ROOT
from local_reservations.states.wb.parse_reference_tables import (
    SOURCES,
    additional_sources,
    check_equality,
    deduplicate_purba,
    numeric,
    parse_bardhaman,
    parse_birbhum,
    parse_purba,
)


def reference_source(district):
    index_path = ROOT / "data/wb/derived/native/index.json"
    if not index_path.exists():
        pytest.skip("Acquired reference PDFs are unavailable")
    filename = next(k for k, v in SOURCES.items() if v[0] == district)
    index = json.loads(index_path.read_text())
    source = dict(next(s for s in index if s["source_path"].endswith("/" + filename)))
    source["district"] = district
    return source, json.loads((ROOT / source["cache"]).read_text())


@pytest.mark.parametrize("raw", [None, "", "—", "1 4", "four"])
def test_unknown_counts_remain_unknown(raw):
    assert numeric(raw) is None


def test_numeric_does_not_rewrite_duplicate_digits():
    assert numeric("14") == 14
    assert numeric("1144") == 1144
    assert numeric("4.75") == 4.75


def test_purba_deduplication_uses_character_position():
    source, original = reference_source("Purba Medinipur")
    cleaned = deduplicate_purba(source)
    rows = parse_purba(source, cleaned)
    assert cleaned["characters_after"] < cleaned["characters_before"]
    assert cleaned["extra_attrs"] == []
    assert [json.loads(r["counts_json"])["members"] for r in rows] == [
        60,
        4,
        14,
        25,
    ]
    assert all(r["year"] is None for r in rows)
    assert all(r["record_kind"] == "district_membership_composition" for r in rows)
    assert all(r["source_sha256"] == source["sha256"] for r in rows)
    assert len(original["pages"]) == 1
    assert "Ex-Officio" in rows[1]["selection_basis_printed"]


def test_birbhum_elected_members_are_not_reservations():
    source, record = reference_source("Birbhum")
    rows = parse_birbhum(source, record)
    assert len(rows) == 4
    assert json.loads(rows[0]["counts_json"])["gp_seats"] == 2258
    assert all(
        r["record_kind"] == "elected_members_by_recorded_caste_and_sex"
        for r in rows[1:]
    )
    gp_counts = json.loads(rows[1]["counts_json"])
    assert gp_counts["male_total"] == 1414
    assert gp_counts["female_total"] == 844
    assert all(not r["quality_flags"] for r in rows)


def test_components_check_does_not_impute_unknown():
    row = {
        "counts_json": json.dumps({"male": 3, "female": None, "total": 8}),
        "quality_flags": "blank_or_unread_count",
        "review_status": "needs_review",
    }
    check_equality(row, ["male", "female"], "total")
    assert row["quality_flags"] == "blank_or_unread_count"
    row["counts_json"] = json.dumps({"male": 3, "female": 2, "total": 8})
    check_equality(row, ["male", "female"], "total")
    assert "printed_components_mismatch" in row["quality_flags"]


def test_book_retains_printed_conflicts_and_distinguishes_years_and_units():
    source, record = reference_source("Bardhaman")
    rows = parse_bardhaman(source, record)
    assert len(record["pages"]) == 107
    assert len(rows) == 379
    conflicts = [
        r for r in rows if "conflicting_printed_block_totals" in r["quality_flags"]
    ]
    assert len(conflicts) == 2
    assert {r["block_printed"].casefold() for r in conflicts} == {"barabani"}
    assert {json.loads(r["counts_json"])["sc_women"] for r in conflicts} == {1, 2}
    assert all(r["tier"] == "panchayat_samiti" for r in conflicts)
    district_totals = [
        r for r in rows if r["record_kind"] == "district_reservation_totals"
    ]
    assert len(district_totals) == 3
    assert all(r["block_printed"] is None for r in district_totals)
    assert all(
        r["year"] == (2003 if "election_results" in r["record_kind"] else 2008)
        for r in rows
    )
    assert not any("office" in r["record_kind"] for r in rows)
    assert all(json.loads(r["source_table_bbox"]) for r in rows)
    assert all(json.loads(r["raw_cells"]) for r in rows)


def test_additional_inventory_distinguishes_manual_maps_and_unrelated_paper():
    if not (ROOT / "data/wb/vintage_search/artifact_index.csv").exists():
        pytest.skip("Acquired reference index is unavailable")
    sources = additional_sources()
    assert len(sources) == 11
    assert sum(s["reference_kind"] == "block_map" for s in sources) == 2
    assert sum("unrelated_mexico" in s["reference_kind"] for s in sources) == 1
    assert sum(s["reference_year"] == 2022 for s in sources) == 1
    assert all(s["district"] is None for s in sources)


def test_additional_native_extraction_retains_words_tables_and_resumes(
    tmp_path, monkeypatch
):
    from local_reservations.states.wb import parse_reference_tables as reference

    source, _ = reference_source("Birbhum")
    shutil.copyfile(ROOT / source["source_path"], tmp_path / "reference.pdf")
    source["source_path"] = "reference.pdf"
    monkeypatch.setattr(reference, "ROOT", tmp_path)
    monkeypatch.setattr(reference, "OUT", tmp_path / "derived")
    result = reference.extract_additional(source)
    assert result["expected_pages"] == 1
    assert len(result["pages"]) == 1
    assert len(result["pages"][0]["tables"]) == 4
    assert all(
        {"text", "x0", "x1", "top", "bottom"} <= word.keys()
        for word in result["pages"][0]["words"]
    )

    def forbid_reader(*args, **kwargs):
        raise AssertionError("Completed source cache must be reused")

    monkeypatch.setattr(reference.pdfplumber, "open", forbid_reader)
    assert reference.extract_additional(source) == result
