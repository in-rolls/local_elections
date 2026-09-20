"""Contracts for the generated coverage table."""

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from local_reservations.common import datasets, notes, slice_checks
from local_reservations.tools import build_coverage, build_sources, build_state_readmes


def test_cross_state_search_is_not_a_state(tmp_path, monkeypatch):
    for name in ["source_search", "integration", "tn", "tamil_nadu", "master"]:
        (tmp_path / name).mkdir()
    monkeypatch.setattr(datasets, "DATA", tmp_path)
    assert {path.name for path in datasets.state_directories()} == {"tn", "tamil_nadu"}
    assert build_coverage.pretty("tn") == build_coverage.pretty("tamil_nadu")
    assert build_coverage.pretty("tn") == "Tamil Nadu"


def test_integration_receipts_are_excluded_without_hiding_unknown_states(
    tmp_path, monkeypatch
):
    for name in ["integration", "ap", "unknown_state"]:
        (tmp_path / name).mkdir()
    contents = (
        "state,year,tier,reservation,caste_reservation\n"
        "Andhra Pradesh,2020,gp_head,General,NONE\n"
    )
    source = tmp_path / "ap/seats.csv"
    source.write_text(contents)
    (tmp_path / "integration/receipt.csv").write_text(contents)
    monkeypatch.setattr(datasets, "DATA", tmp_path)
    monkeypatch.setattr(build_coverage, "DATA", tmp_path)
    assert list(datasets.paths()) == [source]
    assert build_coverage.unmapped_directories() == ["unknown_state"]


def test_nested_tn_exports_have_separate_coverage_without_pooled_rows(
    tmp_path, monkeypatch
):
    source = tmp_path / "tn/derived/heads_2011/gp_president_reservations.csv"
    source.parent.mkdir(parents=True)
    source.write_text(
        "state,year,tier,reservation,caste_reservation\n"
        "Tamil Nadu,2011,gp_head,General,UR\n"
    )
    monkeypatch.setattr(datasets, "DATA", tmp_path)
    monkeypatch.setattr(build_coverage, "DATA", tmp_path)
    monkeypatch.setattr(build_coverage, "ALL_STATES", ["Tamil Nadu"])
    assert list(datasets.parsed()) == []
    row = build_coverage.build_rows()[0]
    assert row[2:5] == ("2011", "-", "source-specific exports")
    assert "data/tn/" in row[6]


def test_state_readme_dispatch_preserves_nested_tn_guide(tmp_path, monkeypatch):
    guide = tmp_path / "tn/derived/heads_2011/README.md"
    guide.parent.mkdir(parents=True)
    guide.write_text("source-specific guide\n")
    for name in ["source_search", "integration"]:
        (tmp_path / name).mkdir()
    monkeypatch.setattr(build_state_readmes, "DATA", tmp_path)
    monkeypatch.setattr(build_state_readmes, "slices_by_directory", dict)
    monkeypatch.setattr(build_state_readmes, "render_tn", lambda: "overview\n")
    assert build_state_readmes.build() == {tmp_path / "tn/readme.md": "overview\n"}
    assert guide.read_text() == "source-specific guide\n"


def test_sibling_parquet_rows_are_counted_from_metadata(tmp_path, monkeypatch):
    sibling = tmp_path / "sibling"
    sibling.mkdir()
    pq.write_table(pa.table({"seat": [1, 2, 3]}), sibling / "seats.parquet")
    monkeypatch.setattr(build_coverage, "ROOT", tmp_path / "local_reservations")
    spec = {"repo": "sibling", "files": ["seats.parquet"]}
    assert build_coverage.sibling_rows(spec) == "3"


def test_source_holdings_use_inventory_directory_names(tmp_path, monkeypatch):
    inventory = tmp_path / "inventory.csv"
    inventory.write_text(
        "state,format,pages\nmadhya_pradesh,digital-text,351\n"
        "tamil_nadu,scan,74\ntn,digital-text,153\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(build_sources, "INVENTORY", inventory)
    rendered = build_sources.render()
    assert "| Madhya Pradesh | 1 | 0 | 0 | 0 | 351 |" in rendered
    assert "| Tamil Nadu | 1 | 1 | 0 | 0 | 227 |" in rendered


def test_maharashtra_is_parsed_urban_with_its_gaps_named():
    row = next(row for row in build_coverage.build_rows() if row[0] == "Maharashtra")
    assert row[1] == "ulb_ward"
    assert row[2] == "2012, 2017"
    assert row[4] == "parsed"
    assert "lack a seat-reservation roster" in row[5]
    assert "rural gram panchayats are absent" in row[5]


def test_coverage_describes_held_unparsed_pdfs_plainly():
    assam = next(row for row in build_coverage.build_rows() if row[0] == "Assam")
    assert assam[4] == "parsed"
    assert assam[5] == "23 held 2025 district PRI scans remain unparsed"
    ap = next(row for row in build_coverage.build_rows() if row[0] == "Andhra Pradesh")
    assert "all 13 GP district gazettes are held" in ap[5]
    assert "8 are parsed and 5 remain unparsed" in ap[5]


def test_complete_manifest_changes_missing_districts_to_held_unparsed(tmp_path):
    manifest = tmp_path / "data" / "ap" / "2020_res_gp" / "manifest.csv"
    manifest.parent.mkdir(parents=True)
    districts = [f"District {number}" for number in range(1, 14)]
    manifest.write_text(
        "state,year,district\n"
        + "".join(f"Andhra Pradesh,2020,{district}\n" for district in districts),
        encoding="utf-8",
    )
    rows = [{"district": district, "woman_reserved": "0"} for district in districts[:7]]
    a_slice = slice_checks.Slice("Andhra Pradesh", "2020", "gp_head", rows, tmp_path)
    found = notes.districts_missing(a_slice)
    assert found["text"] == "some held districts are unparsed"
    assert "13 of 13 district source PDFs held" in found["detail"]
    assert found["status"] is None


def test_coverage_does_not_call_every_unlinked_pdf_missing_work():
    rows = {row[0]: row for row in build_coverage.build_rows()}
    assert "not missing seats" in rows["Karnataka"][5]
    assert "not additional final seats" in rows["West Bengal"][5]


def test_coverage_names_sources_that_still_have_to_be_acquired():
    rows = {row[0]: row for row in build_coverage.build_rows()}
    assert "acquire seat-level rural data" in rows["Odisha"][5]
    assert "source-specific exports" in rows["Tamil Nadu"][5]


def test_every_parsed_state_with_unlinked_pdfs_has_a_reviewed_classification():
    parsed = build_coverage.parsed_datasets()
    unlinked = build_coverage.unlinked_source_pdfs()
    states = {
        state for state, entry in parsed.items() if unlinked.get(entry["dir"], set())
    }
    assert states <= set(build_coverage.REMAINING_WORK)


def test_sibling_source_record_counts_are_reported():
    rows = {row[0]: row for row in build_coverage.build_rows()}
    assert "local_elections_rajasthan" in rows["Rajasthan"][6]
    required = [
        build_coverage.ROOT.parent / build_coverage.SIBLINGS[state]["repo"]
        for state in ("Rajasthan", "Uttar Pradesh")
    ]
    if not all(path.exists() for path in required):
        pytest.skip("state sibling repositories are not checked out")
    assert rows["Rajasthan"][3] == "255,474"
    assert rows["Uttar Pradesh"][3] == "535,848"
