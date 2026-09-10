"""Where the repository is, worked out once.

Forty-two modules each computed this for themselves, as
``pathlib.Path(__file__).resolve().parent.parent`` or ``.parent.parent.parent``
depending on how deep they sat. That is duplication with teeth: the count is a
silent assertion about directory depth, so moving a file two levels changes
where it thinks ``data/`` is, and nothing fails loudly - it just resolves to a
directory that does not exist, or worse, one that does.

Found by walking up for the marker rather than by counting, so it survives the
next move as well as this one.

An installed wheel contains code, not the corpus. LOCAL_RESERVATIONS_ROOT may
point to a separate checkout. An invalid explicit root never falls back to a
different repository.
"""

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
    return project.get("project", {}).get("name") == "local-reservations"


def _find_root(start):
    for directory in [start, *start.parents]:
        if _is_repository(directory):
            return directory
    raise RuntimeError(
        f"no repository root above {start}: looked for {_MARKERS}; "
        "set LOCAL_RESERVATIONS_ROOT to a local-reservations checkout"
    )


def _resolve_root(start):
    configured = os.environ.get("LOCAL_RESERVATIONS_ROOT")
    if configured is not None:
        root = pathlib.Path(configured).expanduser().resolve()
        if not configured.strip() or not _is_repository(root):
            raise RuntimeError(
                "LOCAL_RESERVATIONS_ROOT must name a local-reservations checkout "
                "with pyproject.toml and a data directory"
            )
        return root
    return _find_root(start)


ROOT = _resolve_root(pathlib.Path(__file__).resolve())
DATA = ROOT / "data"
