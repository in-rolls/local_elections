"""Verify complete source archives using isolated evidence trees."""

import hashlib
import io
import json
import subprocess
import sys
import tarfile

import pytest

from local_reservations.paths import ROOT
from local_reservations.tools import build_evidence as build
from local_reservations.tools import verify_manifest as verify


def corpus(tmp_path):
    root = tmp_path / "corpus"
    scope = root / "data/wb"
    scope.mkdir(parents=True)
    (scope / "original.pdf").write_bytes(b"%PDF-original\x00\xff")
    review = scope / "ignored_review"
    review.mkdir()
    (review / "page.png").write_bytes(b"image evidence")
    (scope / ".DS_Store").write_text("not evidence")
    return root


def test_archives_preserve_every_byte_and_are_deterministic(tmp_path):
    root = corpus(tmp_path)
    first = build.build(root, ["data/wb"], 20, tmp_path / "one")
    second = build.build(root, ["data/wb"], 20, tmp_path / "two")
    assert first == second
    assert first["totals"] == {"files": 2, "bytes": 29, "assets": 2}
    assert verify.verify_archives(first, tmp_path / "one") == 2
    assert {f["path"] for f in first["files"]} == {
        "data/wb/original.pdf",
        "data/wb/ignored_review/page.png",
    }


def test_verifier_runs_without_package_and_detects_unlisted_files(tmp_path):
    root = corpus(tmp_path)
    manifest = build.build(root, ["data/wb"], 100)
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest))
    command = [
        sys.executable,
        "-I",
        str(ROOT / "src/local_reservations/tools/verify_manifest.py"),
        "--manifest",
        str(path),
        "--root",
        str(root),
    ]
    good = subprocess.run(command, capture_output=True, text=True, check=False)
    assert good.returncode == 0, good.stdout + good.stderr
    (root / "data/wb/new_source.pdf").write_bytes(b"additional original")
    bad = subprocess.run(command, capture_output=True, text=True, check=False)
    assert bad.returncode == 1
    assert "UNLISTED  data/wb/new_source.pdf" in bad.stdout


def test_missing_and_changed_local_source_fail(tmp_path):
    root = corpus(tmp_path)
    manifest = build.build(root, ["data/wb"], 100)
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest))
    (root / "data/wb/original.pdf").write_bytes(b"tampered")
    (root / "data/wb/ignored_review/page.png").unlink()
    result = subprocess.run(
        [
            sys.executable,
            "-I",
            str(ROOT / "src/local_reservations/tools/verify_manifest.py"),
            "--manifest",
            str(path),
            "--root",
            str(root),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 1
    assert "1 missing, 1 changed" in result.stdout


def test_archive_member_tamper_fails_even_with_updated_container_hash(tmp_path):
    root = corpus(tmp_path)
    archives = tmp_path / "archives"
    manifest = build.build(root, ["data/wb"], 100, archives)
    asset = manifest["assets"][0]
    path = archives / asset["name"]
    with tarfile.open(path, "w:gz") as archive:
        for record in manifest["files"]:
            content = b"X" * record["bytes"]
            member = tarfile.TarInfo(record["path"])
            member.size = len(content)
            archive.addfile(member, io.BytesIO(content))
    asset["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    asset["bytes"] = path.stat().st_size
    with pytest.raises(ValueError, match="member checksum mismatch"):
        verify.verify_archives(manifest, archives)


def test_missing_archive_or_member_is_not_complete(tmp_path):
    root = corpus(tmp_path)
    archives = tmp_path / "archives"
    manifest = build.build(root, ["data/wb"], 20, archives)
    removed = manifest["assets"].pop()
    (archives / removed["name"]).unlink()
    with pytest.raises(ValueError, match="coverage incomplete"):
        verify.verify_archives(manifest, archives)


@pytest.mark.parametrize(
    "name", ["../outside", "/absolute", "a/../../outside", "a\\b", ""]
)
def test_manifest_paths_cannot_leave_root(tmp_path, name):
    with pytest.raises(ValueError, match="Unsafe"):
        verify.safe_path(tmp_path, name)


def test_empty_or_duplicate_manifests_fail(tmp_path):
    with pytest.raises(ValueError, match="nonempty"):
        verify.validate_entries({"files": []}, tmp_path)
    entry = {"path": "a", "sha256": "0" * 64}
    with pytest.raises(ValueError, match="Duplicate"):
        verify.validate_entries({"files": [entry, entry]}, tmp_path)


def test_source_changed_after_inventory_is_not_packaged(tmp_path):
    root = corpus(tmp_path)
    records = build.inventory(root, ["data/wb"], 100)
    (root / "data/wb/original.pdf").write_bytes(b"different bytes")
    with pytest.raises(ValueError, match="changed while packaging"):
        build.write_archive(root, tmp_path, "test.tar.gz", records)
    assert not (tmp_path / "test.tar.gz").exists()
    assert not (tmp_path / "test.tar.gz.tmp").exists()


def test_source_symlinks_and_overlapping_scopes_fail(tmp_path):
    root = corpus(tmp_path)
    with pytest.raises(ValueError, match="Overlapping"):
        build.inventory(root, ["data", "data/wb"], 100)
    (root / "data/wb/link").symlink_to(root / "data/wb/original.pdf")
    with pytest.raises(ValueError, match="symbolic link"):
        build.inventory(root, ["data/wb"], 100)


def test_stale_numbered_assets_cannot_be_certified(tmp_path):
    root = corpus(tmp_path)
    archives = tmp_path / "archives"
    build.build(root, ["data/wb"], 20, archives)
    (root / "data/wb/original.pdf").unlink()
    with pytest.raises(ValueError, match=r"[Ss]tale|[Uu]nlisted"):
        build.build(root, ["data/wb"], 20, archives)


def test_unlisted_archive_is_rejected_by_verifier(tmp_path):
    root = corpus(tmp_path)
    archives = tmp_path / "archives"
    manifest = build.build(root, ["data/wb"], 100, archives)
    (archives / "source-evidence-999.tar.gz").write_bytes(b"obsolete content")
    with pytest.raises(ValueError, match=r"[Ss]tale|[Uu]nlisted"):
        verify.verify_archives(manifest, archives)


def test_same_byte_symlink_replacement_fails(tmp_path):
    root = corpus(tmp_path)
    manifest = build.build(root, ["data/wb"], 100)
    original = root / "data/wb/original.pdf"
    copy = root / "same_bytes.pdf"
    copy.write_bytes(original.read_bytes())
    original.unlink()
    original.symlink_to(copy)
    with pytest.raises(ValueError, match="symbolic link"):
        verify.validate_entries(manifest, root)


def test_new_source_during_packaging_cannot_be_omitted(tmp_path, monkeypatch):
    root = corpus(tmp_path)
    original = build.write_archive

    def concurrent_write(*args):
        result = original(*args)
        (root / "data/wb/new.pdf").write_bytes(b"new source during packaging")
        return result

    monkeypatch.setattr(build, "write_archive", concurrent_write)
    with pytest.raises(ValueError, match=r"changed during|changed while"):
        build.build(root, ["data/wb"], 100, tmp_path / "archives")


def test_make_archive_gate_checks_real_assets(tmp_path):
    root = corpus(tmp_path)
    archives = root / "dist/source-evidence"
    manifest = build.build(root, ["data/wb"], 100, archives)
    (root / "SOURCE_MANIFEST.json").write_text(json.dumps(manifest))
    command = [
        "make",
        "--file",
        str(ROOT / "Makefile"),
        "verify-evidence-archives",
        f"PY={sys.executable}",
    ]
    good = subprocess.run(
        command, cwd=root, capture_output=True, text=True, check=False
    )
    assert good.returncode == 0, good.stdout + good.stderr
    next(archives.glob("*.tar.gz")).unlink()
    missing = subprocess.run(
        command, cwd=root, capture_output=True, text=True, check=False
    )
    assert missing.returncode != 0
