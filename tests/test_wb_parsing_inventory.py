"""The base gazettes belong in the ledger without fictional native extraction."""

import json

from local_elections.states.wb import parsing_inventory as inventory


def test_base_gazettes_have_complete_ocr_page_coverage():
    sources = inventory.read(inventory.BASE / "base_drafts/sources.csv")
    pages, documents = inventory.build_inventory(
        [], [], inventory.collect_audits(), sources
    )
    assert len(documents) == 39
    assert len(pages) == 181
    assert len({(row["source_sha256"], row["source_page"]) for row in pages}) == 181
    assert all(not row["native_page_extracted"] for row in pages)
    assert all(row["native_text_characters"] == 0 for row in pages)
    assert all(row["base_ocr_state"] == "ocr_cache_evidence" for row in pages)
    assert all(row["inventory_scopes"] == "base_2018_gazettes" for row in pages)
    assert sum(row["stage"] == "draft" for row in pages) == 97
    assert sum(row["stage"] == "final" for row in pages) == 84


def test_duplicate_hash_keeps_both_scopes_and_only_real_native_pages(tmp_path):
    cache = tmp_path / "native.json"
    cache.write_text(
        json.dumps({"expected_pages": 2, "pages": [{"page": 1, "text": "native"}]})
    )
    native = [
        {
            "sha256": "same-pdf",
            "source_path": "data/wb/gp_source_search/alias.pdf",
            "pages": 2,
            "cache": str(cache),
        }
    ]
    base = [
        {
            "source_sha256": "same-pdf",
            "source_path": "data/wb/2018/draft/original.pdf",
            "district": "Example",
            "stage": "draft",
            "pages": "2",
        }
    ]
    audits = {
        ("same-pdf", 2): [
            {"parser": "base_drafts", "status": "parsed", "ocr_sha256": "hash"}
        ]
    }
    pages, documents = inventory.build_inventory([], native, audits, base)
    assert len(documents) == 1
    assert len(pages) == 2
    assert documents[0]["inventory_scopes"] == "base_2018_gazettes;gp_source_search"
    assert len(json.loads(documents[0]["aliases"])) == 2
    assert pages[0]["native_page_extracted"]
    assert not pages[1]["native_page_extracted"]
    assert pages[1]["base_ocr_state"] == "ocr_cache_evidence"


def test_missing_base_ocr_is_not_extraction_evidence():
    base = [
        {
            "source_sha256": "missing-cache",
            "source_path": "data/wb/2018/draft/missing.pdf",
            "district": "Example",
            "stage": "draft",
            "pages": "1",
        }
    ]
    audits = {
        ("missing-cache", 1): [
            {"parser": "base_drafts", "status": "missing_ocr_review_required"}
        ]
    }
    pages, _ = inventory.build_inventory([], [], audits, base)
    assert pages[0]["base_ocr_state"] is None
    assert pages[0]["routing_status"] == "parser_audited"
    assert not pages[0]["native_page_extracted"]


def test_reference_publication_year_is_not_an_election_year(tmp_path):
    reference = {
        "source_sha256": "manual",
        "source_path": "data/wb/manual.pdf",
        "expected_pages": 2,
        "native_cache": str(tmp_path / "not-yet-extracted.json"),
        "document_reference_year": 2022,
        "reference_kind": "election_manual",
    }
    pages, documents = inventory.build_inventory([], [], {}, [], [reference])
    assert len(pages) == 2
    assert documents[0]["inventory_scopes"] == "search_references"
    assert all(row["election_year"] is None for row in pages)
    assert all(row["document_reference_year"] == 2022 for row in pages)
    assert all(not row["native_page_extracted"] for row in pages)


def test_raw_pdf_inventory_includes_uppercase_extensions(tmp_path, monkeypatch):
    monkeypatch.setattr(inventory, "ROOT", tmp_path)
    directory = tmp_path / "data/wb"
    directory.mkdir(parents=True)
    (directory / "one.pdf").write_bytes(b"same")
    (directory / "alias.PDF").write_bytes(b"same")
    (directory / "extra.pdf").write_bytes(b"different")
    report = inventory.raw_pdf_coverage([])
    assert report["physical_pdf_paths_on_disk"] == 3
    assert report["unique_pdf_hashes_on_disk"] == 2
    assert set(report["unindexed_pdf_paths"]) == {
        "data/wb/one.pdf",
        "data/wb/alias.PDF",
        "data/wb/extra.pdf",
    }
