"""Check each state repository against docs/layout.md.

    python -m local_elections.tools.check_layout            # every sibling
    python -m local_elections.tools.check_layout jharkhand  # one

Reads the sibling checkouts next to this repository (tracked files only) and
reports, per repository: anything directly under data/ that is not a standard
folder, anything under data/release/ that is not a year, linkage/ or inferred/,
folder names that record history rather than contents, and every raw file the
fetch log does not list or lists with the wrong sha256. Exits 1 if any
repository fails.
"""

import argparse
import csv
import gzip
import hashlib
import re
import subprocess
import sys

from local_elections.common import adapters
from local_elections.common.runlog import command
from local_elections.paths import ROOT
from local_elections.tools.build_state_readmes import SIBLINGS

TOP = {
    "raw",
    "reference",
    "manual",
    "extracted",
    "build",
    "release",
    "checks",
    "search_log",
    # collection-first repositories (docs/layout.md): crawls with their own runs
    "collections",
    "MANIFEST.json",
    "README.md",
}
# A year folder, linkage/, inferred/, a table whose rows span elections, or a
# document describing the release.
RELEASE = re.compile(
    r"^(\d{4}|linkage|inferred|[a-z0-9_]+\.parquet"
    r"|MANIFEST\.json|README\.md|CATALOG\.md|DICTIONARY\.md|CHECKSUMS\.sha256)$"
)
# Folder names that say when or how something arrived, not what it is.
HISTORY = {
    "recovery",
    "fin",
    "interim",
    "external",
    "source",
    "sources",
    "processed",
    "original",
    "derived",
    "archives",
    "final",
    "new",
    "old",
    "historical_handoff",
    "unprocessed",
}
VERSIONED = re.compile(r"^v\d+$")
FETCH_COLUMNS = ["path", "url", "sha256", "bytes", "fetched_at_utc", "method"]
METHODS = {"live", "wayback", "request", "manual", "copy", "unknown"}
FETCH_LOG = "data/raw/fetch_log.csv"


def siblings():
    """The state repositories this one pools or points to, where checked out."""
    names = {a.REPO for a in adapters.REGISTRY.values()} | set(SIBLINGS.values())
    return sorted(ROOT.parent / n for n in names if (ROOT.parent / n / ".git").exists())


def tracked(repo):
    out = subprocess.run(
        ["git", "ls-files", "-z", "data"],
        cwd=repo,
        capture_output=True,
        check=True,
    ).stdout
    return [p for p in out.decode().split("\0") if p]


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


PART = re.compile(r"\.part_[a-z]+$")


def stored(repo, path, raw):
    """sha256 of the bytes received as `path`, however they are stored.

    As received, gzipped beside its name (`<path>.gz`), or split into
    `<path>.part_a`, `.part_b`, ... to stay under GitHub's file size limit.
    None when nothing is stored under any of these.
    """
    if path in raw:
        return digest(repo / path)
    if f"{path}.gz" in raw:
        with gzip.open(repo / f"{path}.gz") as stream:
            return hashlib.file_digest(stream, "sha256").hexdigest()
    parts = sorted(f for f in raw if f.startswith(f"{path}.part_") and PART.search(f))
    if parts:
        whole = hashlib.sha256()
        for part in parts:
            whole.update((repo / part).read_bytes())
        return whole.hexdigest()
    return None


def problems(repo):
    files = tracked(repo)
    found = []
    top = {f.split("/")[1] for f in files}
    found += [f"data/{name}: not a standard folder" for name in sorted(top - TOP)]
    released = {f.split("/")[2] for f in files if f.startswith("data/release/")}
    found += [
        f"data/release/{name}: not a year, linkage/, inferred/ or a snake_case table"
        for name in sorted(released)
        if not RELEASE.match(name)
    ]
    folders = {part for f in files for part in f.split("/")[1:-1]}
    found += [
        f"folder named {name!r}: says how it arrived, not what it holds"
        for name in sorted(folders)
        if name.lower() in HISTORY or VERSIONED.match(name.lower())
    ]

    raw = [f for f in files if f.startswith("data/raw/") and f != FETCH_LOG]
    if not raw:
        return found
    log = repo / FETCH_LOG
    if not log.exists():
        return [*found, f"{FETCH_LOG}: missing ({len(raw)} raw files unlisted)"]
    with log.open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        missing = [c for c in FETCH_COLUMNS if c not in (reader.fieldnames or [])]
        if missing:
            return [*found, f"{FETCH_LOG}: lacks columns {missing}"]
        rows = {r["path"]: r for r in reader}
    raw_set = set(raw)
    covered = set()
    for path, row in rows.items():
        if row["method"] not in METHODS:
            found.append(f"{path}: method {row['method']!r} is not one of {METHODS}")
        got = stored(repo, path, raw_set)
        if got is None:
            if not row.get("duplicate_of"):
                found.append(f"{path}: in the fetch log, not tracked")
            continue
        if got != row["sha256"]:
            found.append(f"{path}: sha256 differs from the fetch log")
        covered |= {path, f"{path}.gz"}
        covered |= {f for f in raw_set if f.startswith(f"{path}.part_")}
    found += [f"{path}: not in the fetch log" for path in sorted(raw_set - covered)]
    return found


@command("validate", artifact="layout")
def main():
    parser = argparse.ArgumentParser(description="Check state repository layouts.")
    parser.add_argument("states", nargs="*", help="e.g. jharkhand; default: all")
    args = parser.parse_args()
    repos = siblings()
    if args.states:
        repos = [
            r for r in repos if r.name.removeprefix("local_elections_") in args.states
        ]
    failed = 0
    for repo in repos:
        found = problems(repo)
        failed += bool(found)
        print(f"{'FAIL' if found else 'ok  '} {repo.name} ({len(found)} problems)")
        for line in found[:20]:
            print(f"       {line}")
        if len(found) > 20:
            print(f"       ... {len(found) - 20} more")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
