"""Contracts for the generated coverage table."""

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from local_elections.common import datasets, notes, slice_checks
from local_elections.tools import build_coverage, build_sources, build_state_readmes


def test_cross_state_search_is_not_a_state(tmp_path, monkeypatch):
    for name in [
        "source_search",
        "integration",
        "stats",
        "transliteration",
        "andhra_pradesh",
        "master",
    ]:
        (tmp_path / name).mkdir()
    monkeypatch.setattr(datasets, "DATA", tmp_path)
    assert {path.name for path in datasets.state_directories()} == {"andhra_pradesh"}
    assert build_coverage.pretty("andhra_pradesh") == "Andhra Pradesh"


def test_integration_receipts_are_excluded_without_hiding_unknown_states(
    tmp_path, monkeypatch
):
    for name in ["integration", "andhra_pradesh", "unknown_state"]:
        (tmp_path / name).mkdir()
    contents = (
        "state,year,tier,reservation,caste_reservation\n"
        "Andhra Pradesh,2020,gp_head,General,NONE\n"
    )
    source = tmp_path / "andhra_pradesh/release/seats.csv"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text(contents)
    (tmp_path / "integration/receipt.csv").write_text(contents)
    monkeypatch.setattr(datasets, "DATA", tmp_path)
    monkeypatch.setattr(build_coverage, "DATA", tmp_path)
    monkeypatch.setattr(
        datasets,
        "registry",
        lambda: {"andhra_pradesh": {"pooled": ["release/seats.csv"]}},
    )
    assert list(datasets.paths()) == [source]
    assert build_coverage.unmapped_directories() == ["unknown_state"]


def test_sibling_states_get_a_pointer_readme(tmp_path, monkeypatch):
    for name in ["source_search", "integration"]:
        (tmp_path / name).mkdir()
    monkeypatch.setattr(build_state_readmes, "DATA", tmp_path)
    monkeypatch.setattr(build_state_readmes, "slices_by_directory", dict)
    monkeypatch.setattr(datasets, "registry", dict)
    monkeypatch.setattr(
        build_state_readmes,
        "SIBLINGS",
        {"odisha": "local_elections_odisha", "telangana": "local_elections_telangana"},
    )
    written = build_state_readmes.build()
    odisha = written[tmp_path / "odisha/readme.md"]
    telangana = written[tmp_path / "telangana/readme.md"]
    assert "[local_elections_odisha](https://github.com/in-rolls/" in odisha
    assert "has no adapter" in odisha
    assert "adapters/telangana.py" in telangana


def test_no_tracked_file_besides_the_readme_in_a_sibling_state():
    assert build_state_readmes.sibling_strays() == []


def test_sibling_parquet_rows_are_counted_from_metadata(tmp_path, monkeypatch):
    sibling = tmp_path / "sibling"
    sibling.mkdir()
    pq.write_table(pa.table({"seat": [1, 2, 3]}), sibling / "seats.parquet")
    monkeypatch.setattr(build_coverage, "ROOT", tmp_path / "local_elections")
    spec = {"repo": "sibling", "files": ["seats.parquet"]}
    assert build_coverage.sibling_rows(spec) == "3"


def test_source_holdings_use_inventory_directory_names(tmp_path, monkeypatch):
    inventory = tmp_path / "inventory.csv"
    inventory.write_text(
        "state,format,pages\nmadhya_pradesh,digital-text,351\n"
        "tamil_nadu,scan,74\ntamil_nadu,digital-text,153\n",
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
    assert "no reservation per GP" in rows["Odisha"][5]
    assert "local_elections_odisha" in rows["Odisha"][6]
    assert "separate exports there, not pooled" in rows["Tamil Nadu"][5]


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
