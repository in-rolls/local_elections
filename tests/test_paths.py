"""Repository discovery for editable and standalone wheel installations."""

import pytest

from local_elections import paths


def make_repository(directory, name="local-elections"):
    directory.mkdir()
    (directory / "data").mkdir()
    (directory / "pyproject.toml").write_text(f'[project]\nname = "{name}"\n')
    return directory


def test_editable_install_finds_its_repository(tmp_path, monkeypatch):
    monkeypatch.delenv("LOCAL_RESERVATIONS_ROOT", raising=False)
    root = make_repository(tmp_path / "checkout")
    assert paths._resolve_root(root / "src/package/paths.py") == root


def test_installed_wheel_uses_explicit_checkout(tmp_path, monkeypatch):
    root = make_repository(tmp_path / "checkout")
    monkeypatch.setenv("LOCAL_RESERVATIONS_ROOT", str(root))
    monkeypatch.chdir(tmp_path)
    assert paths._resolve_root(tmp_path / "venv/site-packages/paths.py") == root


def test_explicit_checkout_overrides_module_ancestor(tmp_path, monkeypatch):
    first = make_repository(tmp_path / "first")
    second = make_repository(tmp_path / "second")
    monkeypatch.setenv("LOCAL_RESERVATIONS_ROOT", str(second))
    assert paths._resolve_root(first / "src/package/paths.py") == second


@pytest.mark.parametrize("invalid", ["missing", "foreign", "nested", "empty"])
def test_invalid_explicit_root_never_falls_back(tmp_path, monkeypatch, invalid):
    valid = make_repository(tmp_path / "valid")
    foreign = make_repository(tmp_path / "foreign", name="another-project")
    nested = valid / "nested"
    nested.mkdir()
    settings = {
        "missing": str(tmp_path / "missing"),
        "foreign": str(foreign),
        "nested": str(nested),
        "empty": "",
    }
    monkeypatch.setenv("LOCAL_RESERVATIONS_ROOT", settings[invalid])
    with pytest.raises(RuntimeError, match="LOCAL_RESERVATIONS_ROOT"):
        paths._resolve_root(valid / "src/package/paths.py")


def test_unrelated_project_is_not_a_repository(tmp_path, monkeypatch):
    monkeypatch.delenv("LOCAL_RESERVATIONS_ROOT", raising=False)
    foreign = make_repository(tmp_path / "foreign", name="another-project")
    with pytest.raises(RuntimeError, match="LOCAL_RESERVATIONS_ROOT"):
        paths._resolve_root(foreign / "src/package/paths.py")


def test_malformed_project_metadata_is_not_a_repository(tmp_path, monkeypatch):
    monkeypatch.delenv("LOCAL_RESERVATIONS_ROOT", raising=False)
    root = make_repository(tmp_path / "checkout")
    (root / "pyproject.toml").write_text("[broken")
    with pytest.raises(RuntimeError, match="LOCAL_RESERVATIONS_ROOT"):
        paths._resolve_root(root / "src/package/paths.py")
