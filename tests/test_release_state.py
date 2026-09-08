"""Release-state checks use isolated repositories, never the held corpus."""

import json
import shutil
import subprocess

import pytest

from local_reservations.tools import release_check


def git(path, *args):
    return subprocess.run(
        ["git", "-C", str(path), *args],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


def commit(path, message):
    git(path, "add", ".")
    git(path, "-c", "commit.gpgsign=false", "commit", "-qm", message)
    return git(path, "rev-parse", "HEAD")


def repository(path):
    path.mkdir()
    git(path, "init", "-q")
    git(path, "config", "user.name", "Release fixture")
    git(path, "config", "user.email", "fixture@example.com")
    (path / "source.txt").write_text("source\n")
    commit(path, "initial")
    return path


@pytest.fixture
def release_tree(tmp_path, monkeypatch):
    root = repository(tmp_path / "corpus")
    sibling = repository(tmp_path / "sibling")
    manifest = {
        "dirty": False,
        "built_from_commit": git(root, "rev-parse", "HEAD"),
        "sibling_repos": [
            {
                "repo": sibling.name,
                "present": True,
                "dirty": False,
                "commit": git(sibling, "rev-parse", "HEAD"),
            }
        ],
        "totals": {"master_rows": 1},
        "files": [{"kind": "master", "states": ["Fixture"]}],
    }
    write_manifest(root, manifest)
    monkeypatch.setattr(release_check, "ROOT", root)
    monkeypatch.setattr(release_check.sys, "argv", ["release-check"])
    return root, sibling, manifest


def write_manifest(root, manifest):
    (root / "MANIFEST.json").write_text(json.dumps(manifest))
    commit(root, "manifest")


def test_clean_pinned_repositories_pass(release_tree, capsys):
    assert release_check.main.__wrapped__() == 0
    assert "Ready to tag" in capsys.readouterr().out


@pytest.mark.parametrize("target", ["root", "sibling"])
@pytest.mark.parametrize("change", ["modified", "untracked", "staged"])
def test_stale_clean_flags_cannot_hide_live_changes(release_tree, target, change):
    root, sibling, _ = release_tree
    path = root if target == "root" else sibling
    name = "new.txt" if change == "untracked" else "source.txt"
    (path / name).write_text("changed\n")
    if change == "staged":
        git(path, "add", name)
    if target == "root":
        assert release_check.dirty_files() == [name]
    assert release_check.main.__wrapped__() == 1


def test_clean_sibling_at_another_commit_fails(release_tree, capsys):
    _, sibling, _ = release_tree
    (sibling / "source.txt").write_text("new source\n")
    live = commit(sibling, "new source")
    assert release_check.main.__wrapped__() == 1
    assert live in capsys.readouterr().out


@pytest.mark.parametrize("pin", [None, "", "not-a-commit"])
def test_missing_or_invalid_sibling_pin_fails(release_tree, pin):
    root, _, manifest = release_tree
    manifest["sibling_repos"][0]["commit"] = pin
    write_manifest(root, manifest)
    assert release_check.main.__wrapped__() == 1


@pytest.mark.parametrize("target", ["root", "sibling"])
def test_non_repository_fails(release_tree, target):
    root, sibling, _ = release_tree
    shutil.rmtree((root if target == "root" else sibling) / ".git")
    assert release_check.main.__wrapped__() == 1


def test_subdirectory_cannot_impersonate_a_sibling_repository(release_tree):
    root, sibling, manifest = release_tree
    nested = sibling / "nested"
    nested.mkdir()
    (nested / "source.txt").write_text("nested\n")
    pin = commit(sibling, "nested source")
    manifest["sibling_repos"][0].update(repo="sibling/nested", commit=pin)
    write_manifest(root, manifest)
    assert release_check.main.__wrapped__() == 1


def test_missing_live_sibling_fails(release_tree):
    _, sibling, _ = release_tree
    shutil.rmtree(sibling)
    assert release_check.main.__wrapped__() == 1


def test_manifest_missing_source_flag_requires_rebuild(release_tree):
    root, _, manifest = release_tree
    manifest["sibling_repos"][0]["present"] = False
    write_manifest(root, manifest)
    assert release_check.main.__wrapped__() == 1


@pytest.mark.parametrize("target", ["root", "sibling"])
def test_recorded_dirty_provenance_requires_rebuild(release_tree, target, capsys):
    root, _, manifest = release_tree
    entry = manifest if target == "root" else manifest["sibling_repos"][0]
    entry["dirty"] = True
    write_manifest(root, manifest)
    assert release_check.main.__wrapped__() == 1
    assert "manifest records" in capsys.readouterr().out


def test_version_only_prints_commands_without_tagging(
    release_tree, monkeypatch, capsys
):
    root, sibling, _ = release_tree
    before = [git(path, "rev-parse", "HEAD") for path in (root, sibling)]
    monkeypatch.setattr(release_check.sys, "argv", ["release-check", "v9.9.9"])
    assert release_check.main.__wrapped__() == 0
    assert "git tag -a v9.9.9" in capsys.readouterr().out
    assert [git(path, "rev-parse", "HEAD") for path in (root, sibling)] == before
    assert git(root, "tag", "--list") == ""
    assert git(root, "status", "--porcelain") == ""


@pytest.mark.parametrize("failure", ["exit", "timeout", "missing_executable"])
def test_git_failures_refuse_release(release_tree, monkeypatch, failure):
    def fail(args, **kwargs):
        if failure == "timeout":
            raise subprocess.TimeoutExpired(args, 60)
        if failure == "missing_executable":
            raise FileNotFoundError("git unavailable")
        return subprocess.CompletedProcess(args, 128, "", "fatal: fixture failure")

    monkeypatch.setattr(release_check.subprocess, "run", fail)
    assert release_check.main.__wrapped__() == 1


def test_unborn_sibling_repository_fails(release_tree):
    _, sibling, _ = release_tree
    shutil.rmtree(sibling / ".git")
    git(sibling, "init", "-q")
    assert release_check.main.__wrapped__() == 1
