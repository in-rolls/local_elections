"""Inventory and package source evidence that the pooled-data manifest omits.

Includes original files and verification derivatives, including ignored images.
Archives use ordinary tar/gzip with deterministic metadata and a member-to-asset
map. The standalone verify_manifest tool can verify either local files or the
archive contents without extracting them.
"""

import argparse
import collections
import gzip
import hashlib
import json
import tarfile
from pathlib import Path

from local_reservations.common.runlog import command
from local_reservations.paths import ROOT
from local_reservations.tools.build_manifest import RELEASE_INPUTS, digest, repo_state

HARYANA_HISTORICAL_INPUT = (
    "data/master/observations/haryana/"
    "6ad3161f4b7c750e4446542bc4cf48dc5acd822c7897c4efeffdfbc56021da34"
)
SCOPES = (
    "data/wb",
    "data/tn",
    "data/source_search/early_heads",
    "data/source_search/national",
    HARYANA_HISTORICAL_INPUT,
)
EXCLUDED_NAMES = (".DS_Store",)
DEFAULT_MANIFEST = ROOT / "SOURCE_MANIFEST.json"


def artifact_role(path):
    if "/derived/" in path:
        return "extraction_or_review_artifact"
    if Path(path).suffix.lower() in (
        ".pdf",
        ".zip",
        ".rar",
        ".dta",
        ".xls",
        ".xlsx",
        ".html",
        ".htm",
        ".body",
    ):
        return "source_or_acquired_response_check_source_inventory"
    return "source_metadata_or_supporting_material"


def inventory(root, scopes, max_bytes):
    if max_bytes < 1:
        raise ValueError("Archive member-size budget must be positive")
    files = []
    seen = set()
    for scope in sorted(scopes):
        directory = root / scope
        if not directory.is_dir() or directory.is_symlink():
            raise ValueError(f"Missing or symbolic-link evidence scope: {scope}")
        for path in sorted(directory.rglob("*")):
            if path.name in EXCLUDED_NAMES:
                continue
            if path.is_symlink():
                raise ValueError(f"Source evidence must not be a symbolic link: {path}")
            if not path.is_file():
                continue
            relative = path.relative_to(root).as_posix()
            if relative in seen:
                raise ValueError(f"Overlapping evidence scopes: {relative}")
            seen.add(relative)
            size = path.stat().st_size
            if size > max_bytes:
                raise ValueError(f"File exceeds asset member budget: {relative}")
            files.append(
                {
                    "path": relative,
                    "sha256": digest(path),
                    "bytes": size,
                    "artifact_role": artifact_role(relative),
                }
            )
    if not files:
        raise ValueError("No source evidence files")
    return sorted(files, key=lambda row: row["path"])


def assign_assets(files, max_bytes):
    number, size = 1, 0
    for row in files:
        if size and size + row["bytes"] > max_bytes:
            number += 1
            size = 0
        row["asset"] = f"source-evidence-{number:03}.tar.gz"
        size += row["bytes"]
    return files


def write_archive(root, directory, name, members):
    target = directory / name
    temporary = target.with_suffix(target.suffix + ".tmp")
    try:
        with (
            temporary.open("wb") as raw,
            gzip.GzipFile(
                filename="", mode="wb", fileobj=raw, mtime=0, compresslevel=6
            ) as gz,
            tarfile.open(fileobj=gz, mode="w|", format=tarfile.PAX_FORMAT) as archive,
        ):
            for row in members:
                source = root / row["path"]
                if (
                    source.stat().st_size != row["bytes"]
                    or digest(source) != row["sha256"]
                ):
                    raise ValueError(f"Evidence changed while packaging: {source}")
                info = tarfile.TarInfo(row["path"])
                info.size = row["bytes"]
                info.mtime = 0
                info.mode = 0o644
                with source.open("rb") as content:
                    archive.addfile(info, content)
        if temporary.stat().st_size >= 2 * 1024**3:
            raise ValueError("Compressed release asset reaches GitHub's 2 GiB limit")
        temporary.replace(target)
    finally:
        temporary.unlink(missing_ok=True)
    return {
        "name": name,
        "bytes": target.stat().st_size,
        "sha256": digest(target),
        "members": len(members),
        "uncompressed_bytes": sum(r["bytes"] for r in members),
    }


def build(root, scopes, max_bytes, archive_dir=None):
    files = assign_assets(inventory(root, scopes, max_bytes), max_bytes)
    assets = []
    grouped = collections.defaultdict(list)
    for row in files:
        grouped[row["asset"]].append(row)
    if archive_dir is not None:
        archive_dir.mkdir(parents=True, exist_ok=True)
        stale = {p.name for p in archive_dir.glob("source-evidence-*.tar.gz")} - set(
            grouped
        )
        if stale:
            raise ValueError(
                "Stale evidence archives; use a clean output directory: "
                f"{sorted(stale)}"
            )
    for name, members in sorted(grouped.items()):
        if archive_dir is None:
            assets.append(
                {
                    "name": name,
                    "members": len(members),
                    "uncompressed_bytes": sum(r["bytes"] for r in members),
                    "status": "not_built",
                }
            )
        else:
            assets.append(write_archive(root, archive_dir, name, members))
    original_inventory = [
        {k: v for k, v in row.items() if k != "asset"} for row in files
    ]
    if inventory(root, scopes, max_bytes) != original_inventory:
        raise ValueError(
            "Evidence inventory changed during packaging; rebuild after writers finish"
        )
    return {
        "manifest_type": "source_evidence",
        "schema_version": 1,
        "scopes": sorted(scopes),
        "excluded_names": list(EXCLUDED_NAMES),
        "max_uncompressed_bytes_per_asset": max_bytes,
        "files": files,
        "assets": assets,
        "totals": {
            "files": len(files),
            "bytes": sum(r["bytes"] for r in files),
            "assets": len(assets),
        },
    }


@command("build", artifact="source_evidence")
def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--archive-dir", type=Path)
    parser.add_argument("--max-mib", type=int, default=512)
    parser.add_argument("--scope", action="append")
    args = parser.parse_args()
    scopes = args.scope or list(SCOPES)
    for scope in scopes:
        path = Path(scope)
        if path.is_absolute() or ".." in path.parts:
            parser.error("Scopes must be repository-relative directories")
    if args.archive_dir:
        for scope in scopes:
            if args.archive_dir.resolve().is_relative_to((ROOT / scope).resolve()):
                parser.error("Archive output must be outside the evidence scopes")
    manifest = build(ROOT, scopes, args.max_mib * 1024**2, args.archive_dir)
    state = repo_state(ROOT, [*RELEASE_INPUTS, ":(exclude)SOURCE_MANIFEST.json"])
    manifest.update(
        built_from_commit=state["commit"],
        dirty=state["dirty"],
        builder_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    )
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.manifest.with_suffix(".tmp")
    temporary.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    temporary.replace(args.manifest)
    print(json.dumps(manifest["totals"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
