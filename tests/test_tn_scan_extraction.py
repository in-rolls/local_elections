"""Exercise preservation, resume and source coverage using disposable fixtures."""

import csv
import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image

from local_elections.states.tn import extract_scans as scans


@pytest.fixture
def source(tmp_path):
    path = tmp_path / "fixture.pdf"
    pages = [Image.new("RGB", (100, 80), "white") for _ in range(3)]
    pages[0].save(path, save_all=True, append_images=pages[1:])
    return {
        "source_id": "fixture",
        "source_path": str(path),
        "source_sha256": scans.digest(path),
        "source_url": "https://example.org/fixture.pdf",
        "source_pages": 3,
        "selected_last": 2,
        "pilot_pages": [1],
        "page_bounds": [[0, 0, 595.2756, 841.8898]] * 3,
    }


@pytest.fixture
def engine():
    return {
        "extractor_version": 1,
        "versions": {"tesseract": "test", "pdftoppm": "test"},
        "traineddata": {"eng": {"sha256": "fixture model"}},
        "settings": {"dpi": 300, "language": "eng", "psm": 3, "oem": 1},
    }


@pytest.fixture
def fake_tools(monkeypatch):
    calls = []

    def run(command, **kwargs):
        calls.append(command)
        assert kwargs["env"]["OMP_THREAD_LIMIT"] == "1"
        if command[0] == "pdftoppm":
            Image.new("RGB", (100, 80), "white").save(command[-1] + ".png")
        else:
            Path(command[2] + ".txt").write_text("Aravayal SC (Women)\n")
            Path(command[2] + ".tsv").write_text(
                "level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\t"
                "left\ttop\twidth\theight\tconf\ttext\n"
                "1\t1\t0\t0\t0\t0\t0\t0\t100\t80\t-1\t\n"
                "5\t1\t1\t1\t1\t1\t10\t10\t50\t10\t90\tAravayal\n"
            )
        return SimpleNamespace(returncode=0, stderr="fixture diagnostic")

    monkeypatch.setattr(scans.subprocess, "run", run)
    return calls


def test_resume_preserves_outputs_without_rerunning(
    source, engine, fake_tools, tmp_path
):
    first = scans.extract_page(source, 1, engine, tmp_path)
    second = scans.extract_page(source, 1, engine, tmp_path)
    assert first == second
    assert len(fake_tools) == 2
    assert first["source_url"] == source["source_url"]
    assert first["identity"]["source_sha256"] == source["source_sha256"]
    assert first["semantic_status"] == "raw_extraction_only_not_reservation_records"
    assert set(first["artifacts"]) == {"image", "text", "tsv", "stderr"}


@pytest.mark.parametrize("artifact", ["image", "text", "tsv", "stderr"])
def test_tamper_reextracts_and_keeps_old_attempt(
    source, engine, fake_tools, tmp_path, artifact
):
    first = scans.extract_page(source, 1, engine, tmp_path)
    directory = tmp_path / "fixture/page_0001"
    path = directory / first["artifacts"][artifact]["path"]
    path.write_bytes(b"corrupted")
    second = scans.extract_page(source, 1, engine, tmp_path)
    assert len(fake_tools) == 4
    assert first["artifacts"]["image"]["path"] != second["artifacts"]["image"]["path"]
    assert path.read_bytes() == b"corrupted"
    assert len(list((directory / "attempts").iterdir())) == 2


def test_changed_model_invalidates_cache(source, engine, fake_tools, tmp_path):
    scans.extract_page(source, 1, engine, tmp_path)
    engine["traineddata"]["eng"]["sha256"] = "new model"
    scans.extract_page(source, 1, engine, tmp_path)
    assert len(fake_tools) == 4


def test_malformed_metadata_invalidates_cache(source, engine, fake_tools, tmp_path):
    scans.extract_page(source, 1, engine, tmp_path)
    directory = tmp_path / "fixture/page_0001"
    (directory / "latest.json").write_text("broken json")
    assert scans.cached_page(directory, scans.page_identity(source, 1, engine)) is None


def test_failed_ocr_keeps_image_and_does_not_resume(
    source, engine, fake_tools, monkeypatch, tmp_path
):
    real_fake = scans.subprocess.run

    def fail(command, **kwargs):
        if command[0] == "tesseract":
            return SimpleNamespace(returncode=1, stderr="OCR failed")
        return real_fake(command, **kwargs)

    monkeypatch.setattr(scans.subprocess, "run", fail)
    result = scans.extract_page(source, 1, engine, tmp_path)
    assert result["status"] == "failed"
    assert scans.coverage([source], engine, tmp_path)[0]["status"] == "failed"
    assert "image" in result["artifacts"]
    assert (
        "OCR failed"
        in (
            tmp_path / "fixture/page_0001" / result["artifacts"]["stderr"]["path"]
        ).read_text()
    )
    assert (
        scans.cached_page(
            tmp_path / "fixture/page_0001", scans.page_identity(source, 1, engine)
        )
        is None
    )


def test_coverage_accounts_for_unselected_pages(source, engine, fake_tools, tmp_path):
    scans.extract_page(source, 1, engine, tmp_path)
    rows = scans.coverage([source], engine, tmp_path)
    assert [r["source_page"] for r in rows] == [1, 2, 3]
    assert [r["status"] for r in rows] == [
        "extracted",
        "pending_or_invalid_cache",
        "outside_selected_office_section",
    ]
    assert all(r["semantic_status"] == "not_parsed" for r in rows)


def test_source_manifest_hash_and_page_guards(source, tmp_path):
    manifest = tmp_path / "manifest.csv"
    row = {
        "source_id": "fixture",
        "path": "fixture.pdf",
        "sha256": source["source_sha256"],
        "final_url": source["source_url"],
    }
    with manifest.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(row))
        writer.writeheader()
        writer.writerow(row)
    specs = {
        "fixture": {
            "sha256": source["source_sha256"],
            "pages": 3,
            "selected_last": 2,
            "pilot": [1],
        }
    }
    loaded = scans.load_sources(manifest, tmp_path, specs)
    assert len(loaded[0]["page_bounds"]) == 3
    specs["fixture"]["pages"] = 4
    with pytest.raises(ValueError, match="page count"):
        scans.load_sources(manifest, tmp_path, specs)
    Path(source["source_path"]).write_bytes(b"changed source")
    with pytest.raises(ValueError, match="hash mismatch"):
        scans.load_sources(manifest, tmp_path, specs)


def test_timeout_recorded(source, engine, monkeypatch, tmp_path):
    def timeout(command, **kwargs):
        raise subprocess.TimeoutExpired(command, 240)

    monkeypatch.setattr(scans.subprocess, "run", timeout)
    result = scans.extract_page(source, 1, engine, tmp_path)
    assert result["status"] == "failed"
    assert "timed out" in result["error"]
    assert (
        json.loads((tmp_path / "fixture/page_0001/latest.json").read_text()) == result
    )
