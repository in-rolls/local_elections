"""Locate the corpus and resolve historical source identities after file moves.

An installed wheel contains code, not the corpus. LOCAL_ELECTIONS_ROOT selects
an explicit checkout; an invalid root never falls back to another repository.
"""

import csv
import functools
import os
import pathlib
import tomllib

_MARKERS = ("pyproject.toml", "data")


def _is_repository(directory):
    project_file = directory / "pyproject.toml"
    if not project_file.is_file() or not (directory / "data").is_dir():
        return False
    try:
        project = tomllib.loads(project_file.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        return False
    return project.get("project", {}).get("name") == "local-elections"


def _find_root(start):
    for directory in [start, *start.parents]:
        if _is_repository(directory):
            return directory
    raise RuntimeError(
        f"no repository root above {start}: looked for {_MARKERS}; "
        "set LOCAL_ELECTIONS_ROOT to a local-elections checkout"
    )


def _resolve_root(start):
    configured = os.environ.get("LOCAL_ELECTIONS_ROOT")
    if configured is not None:
        root = pathlib.Path(configured).expanduser().resolve()
        if not configured.strip() or not _is_repository(root):
            raise RuntimeError(
                "LOCAL_ELECTIONS_ROOT must name a local-elections checkout "
                "with pyproject.toml and a data directory"
            )
        return root
    return _find_root(start)


ROOT = _resolve_root(pathlib.Path(__file__).resolve())
DATA = ROOT / "data"


def _relocations(root):
    """Read historical source identities and their current physical locations."""
    ledger = root / "data" / "relocations.csv"
    if not ledger.exists():
        return {}, {}
    forward, reverse = {}, {}
    with ledger.open(encoding="utf-8", newline="") as stream:
        for row in csv.DictReader(stream):
            if row["source_repo"] != "local_elections":
                continue
            old, new = row["historical_path"], row["current_path"]
            if old in forward or new in reverse:
                raise ValueError(f"Duplicate relocation: {old} -> {new}")
            for value in (old, new):
                path = pathlib.PurePosixPath(value)
                if path.is_absolute() or ".." in path.parts:
                    raise ValueError(f"Invalid relocation path: {value}")
            forward[old] = new
            reverse[new] = old
    return forward, reverse


def resolve_path(path, root=None):
    """Locate retained evidence without changing its historical source identity."""
    root = ROOT if root is None else pathlib.Path(root)
    path = pathlib.Path(path)
    try:
        relative = path.relative_to(root) if path.is_absolute() else path
    except ValueError:
        return path
    forward, _ = relocation_index(root)
    return root / forward.get(relative.as_posix(), relative.as_posix())


def historical_path(path, root=None):
    """Return the original repository-relative identity of a relocated source."""
    if str(path) == "":
        return ""
    root = ROOT if root is None else pathlib.Path(root)
    path = pathlib.Path(path)
    try:
        relative = path.relative_to(root) if path.is_absolute() else path
    except ValueError:
        return str(path)
    _, reverse = relocation_index(root)
    return reverse.get(relative.as_posix(), relative.as_posix())


@functools.lru_cache(maxsize=16)
def relocation_index(root):
    return _relocations(pathlib.Path(root))
