"""Registration and provenance survive physical relocation of source evidence."""

import csv
import hashlib

import pytest

from local_elections.common import datasets, emit, master, slice_checks, sources
from local_elections.paths import historical_path, relocation_index, resolve_path


def relocated_source(root):
    source = root / "data/andhra_pradesh/raw/notice.pdf"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"retained source bytes")
    ledger = root / "data/relocations.csv"
    with ledger.open("w", newline="") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=["source_repo", "historical_path", "current_path", "sha256"],
        )
        writer.writeheader()
        writer.writerow(
            {
                "source_repo": "local_elections",
                "historical_path": "data/ap/notice.pdf",
                "current_path": "data/andhra_pradesh/raw/notice.pdf",
                "sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
            }
        )
    return source


def test_reparse_preserves_source_identity_and_record_ids(tmp_path):
    source = relocated_source(tmp_path)
    before = {
        "source_repo": "local_elections",
        "source_path": "data/ap/notice.pdf",
        "source_page": 3,
        "state": "Andhra Pradesh",
        "year": "2020",
        "tier": "gp_head",
        "gram_panchayat": "Example",
    }
    after = emit.stamp(dict(before), source, page=3, root=tmp_path)
    assert after["source_path"] == before["source_path"]
    assert master.row_id(after, 0) == master.row_id(before, 0)
    assert resolve_path(before["source_path"], tmp_path) == source
    assert resolve_path(source, tmp_path) == source
    assert historical_path(source, tmp_path) == before["source_path"]


def test_relocations_do_not_change_external_repository_paths(tmp_path):
    relocated_source(tmp_path)
    external = tmp_path.parent / "sibling/data/ap/notice.pdf"
    assert resolve_path(external, tmp_path) == external
    assert historical_path(external, tmp_path) == str(external)


def test_conflicting_relocations_are_rejected(tmp_path):
    relocated_source(tmp_path)
    ledger = tmp_path / "data/relocations.csv"
    with ledger.open("a") as stream:
        stream.write(ledger.read_text().splitlines()[1] + "\n")
    relocation_index.cache_clear()
    with pytest.raises(ValueError, match="Duplicate relocation"):
        resolve_path("data/ap/notice.pdf", tmp_path)


def test_drafts_and_supplemental_tables_cannot_enter_pool(tmp_path, monkeypatch):
    state = tmp_path / "andhra_pradesh"
    release = state / "release"
    release.mkdir(parents=True)
    header = "state,year,tier,reservation,caste_reservation\n"
    for name in ("seats.csv", "supplemental.csv", "unregistered.csv"):
        (release / name).write_text(header)
    discovery = state / "discovery"
    discovery.mkdir()
    (discovery / "draft.csv").write_text(header)
    monkeypatch.setattr(datasets, "DATA", tmp_path)
    monkeypatch.setattr(
        datasets,
        "registry",
        lambda: {
            "andhra_pradesh": {
                "pooled": ["release/seats.csv"],
                "supplemental": ["release/supplemental.csv"],
            }
        },
    )
    assert list(datasets.paths()) == [release / "seats.csv"]
    (release / "seats.csv").unlink()
    with pytest.raises(FileNotFoundError, match="Registered pooled input"):
        list(datasets.paths())


def test_all_registered_tables_exist_and_have_unique_roles():
    for state, specification in datasets.registry().items():
        pooled = set(specification["pooled"])
        supplemental = set(specification["supplemental"])
        assert not pooled & supplemental
        assert all((datasets.DATA / state / p).is_file() for p in pooled | supplemental)


def test_missing_source_identity_stays_missing():
    assert historical_path("") == ""


def test_sibling_provenance_can_use_pinned_tables_and_original_documents(
    tmp_path, monkeypatch
):
    root = tmp_path / "central"
    root.mkdir()
    sibling = tmp_path / "sibling"
    sibling.mkdir()
    cache = tmp_path / "cache"
    cache.mkdir()
    (cache / "seats.parquet").write_bytes(b"pinned table")
    (sibling / "notice.pdf").write_bytes(b"original source")
    monkeypatch.setattr(sources, "pinned_directory", lambda *args: cache)
    rows = [
        {"source_repo": "sibling", "source_path": path}
        for path in ["seats.parquet", "notice.pdf"]
    ]
    data = slice_checks.Slice("Example", "2020", "gp_head", rows, root)
    assert slice_checks.provenance_resolves(data)["status"] == slice_checks.PASS
    (sibling / "notice.pdf").unlink()
    assert slice_checks.provenance_resolves(data)["status"] == slice_checks.FAIL


def test_inventory_excludes_outputs_and_shared_directories(tmp_path, monkeypatch):
    from local_elections.tools import inventory

    for relative in [
        "andhra_pradesh/raw/source.html",
        "andhra_pradesh/discovery/lead.html",
        "andhra_pradesh/interim/reading.csv",
        "andhra_pradesh/release/seats.csv",
        "stats/report.csv",
    ]:
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("retained content")
    monkeypatch.setattr(inventory, "DATA", tmp_path)
    monkeypatch.setattr(datasets, "DATA", tmp_path)
    monkeypatch.setattr(datasets, "registry", lambda: {"andhra_pradesh": {}})
    output = tmp_path / "inventory.csv"
    monkeypatch.setattr("sys.argv", ["inventory", "--out", str(output)])
    inventory.main()
    with output.open() as stream:
        rows = list(csv.DictReader(stream))
    assert {r["path"] for r in rows} == {
        "andhra_pradesh/raw/source.html",
        "andhra_pradesh/discovery/lead.html",
    }
