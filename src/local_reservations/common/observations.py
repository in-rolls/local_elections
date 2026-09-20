"""Publish pinned source observations without projecting them onto seat rows."""

import hashlib
import json
import os
import tempfile
from pathlib import Path

import pyarrow.parquet as pq

from local_reservations.common import sources


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def json_bytes(value):
    payload = json.dumps(value, ensure_ascii=True, indent=2, sort_keys=True)
    return (payload + "\n").encode()


def inside(root, relative):
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError(f"Source path escapes its repository: {relative}")
    return path


def copy_checked(source, destination, expected):
    hasher = hashlib.sha256()
    with source.open("rb") as incoming, destination.open("xb") as outgoing:
        while chunk := incoming.read(1024 * 1024):
            hasher.update(chunk)
            outgoing.write(chunk)
    if hasher.hexdigest() != expected:
        raise ValueError(f"Source checksum mismatch: {source}")


def publish_source(root, output, spec):
    pinned = (
        sources.resolve(spec["source_repo"], root=root)
        if (root / "data/sources.json").exists()
        else None
    )
    source_root = pinned[0] if pinned else root.parent / spec["source_repo"]
    manifest_bytes = None
    if "manifest_path" in spec:
        manifest_path = inside(source_root, spec["manifest_path"])
        manifest_bytes = manifest_path.read_bytes()
        if hashlib.sha256(manifest_bytes).hexdigest() != spec["manifest_sha256"]:
            raise ValueError(f"Source manifest checksum mismatch: {manifest_path}")
        manifest = json.loads(manifest_bytes)
        if manifest["status"] != spec["status"]:
            raise ValueError(f"Unexpected source status: {manifest_path}")
        if manifest.get("assignment_usable") is not False:
            raise ValueError("This import requires an explicitly provisional source")
        files = manifest["files"]
        source_base = manifest_path.parent
    else:
        files = spec["files"]
        source_base = source_root
    if not files:
        raise ValueError(f"No observation files declared for {spec['state']}")

    snapshot = hashlib.sha256(json_bytes(spec)).hexdigest()
    target = output / spec["slug"] / snapshot
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".import-", dir=output) as temporary:
        staging = Path(temporary) / "snapshot"
        staging.mkdir()
        published = []
        names = set()
        for item in files:
            name = Path(item["path"]).name
            if not name.endswith(".parquet") or name in names:
                raise ValueError(f"Invalid or repeated observation filename: {name}")
            names.add(name)
            destination = staging / name
            source = inside(source_base, item["path"])
            copy_checked(source, destination, item["sha256"])
            parquet = pq.ParquetFile(destination)
            if parquet.metadata.num_rows != item["rows"]:
                raise ValueError(f"Observation row count mismatch: {source}")
            published.append(
                {
                    **item,
                    "path": name,
                    "source_path": source.relative_to(source_root.resolve()).as_posix(),
                    "bytes": destination.stat().st_size,
                    "schema": {
                        field.name: str(field.type) for field in parquet.schema_arrow
                    },
                }
            )
        if manifest_bytes is not None:
            (staging / "source_manifest.json").write_bytes(manifest_bytes)
        provenance = {
            "format_version": 1,
            "state": spec["state"],
            "source_repo": spec["source_repo"],
            "source_pin": spec,
            "status": spec["status"],
            "assignment_usable": False,
            "row_semantics": spec["row_semantics"],
            "rows": sum(item["rows"] for item in published),
            "files": published,
            "source_paths_relative_to": spec["source_repo"],
            "transformation": "byte-identical copy; no field or row changes",
            "new_paid_api_cost_usd": 0,
        }
        (staging / "provenance.json").write_bytes(json_bytes(provenance))
        checksums = [f"{item['sha256']}  {item['path']}" for item in published]
        if manifest_bytes is not None:
            checksums.append(f"{spec['manifest_sha256']}  source_manifest.json")
        checksums.append(f"{digest(staging / 'provenance.json')}  provenance.json")
        (staging / "SHA256SUMS").write_text(
            "\n".join(checksums) + "\n", encoding="ascii"
        )
        if target.exists():
            for path in staging.iterdir():
                existing = target / path.name
                if not existing.is_file() or digest(existing) != digest(path):
                    raise ValueError(f"Existing immutable snapshot differs: {existing}")
        else:
            staging.rename(target)
    return {
        "state": spec["state"],
        "path": target.relative_to(output).as_posix(),
        "rows": provenance["rows"],
        "files": len(published),
        "bytes": sum(item["bytes"] for item in published),
        "assignment_usable": False,
        "status": spec["status"],
        "source_repo": spec["source_repo"],
    }


def render_readme(entries):
    lines = [
        "# Source observations",
        "",
        "Generated by the pooled-master build from checksum-pinned sources.",
        "These are provisional observations, not additional unique seats.",
        "Do not append them to master or candidate tables: scopes overlap.",
        "No rows in these snapshots are certified for reservation assignment.",
        "",
        "UP keeps separate files for each office and record kind, including",
        "urban offices. Haryana keeps its original OCR schema, non-seat flags,",
        "and unresolved readings. The two state schemas are not interchangeable.",
        "Original compressed Parquet bytes are preserved without re-encoding.",
        "",
        "Each snapshot includes SHA256SUMS and provenance.json. Source paths",
        "inside rows resolve relative to the source repository named there,",
        "not this export directory; *_raw paths retain their original source roots.",
        "UP source_document_role distinguishes originals from intermediate files",
        "and local CSV exports whose original HTTP provenance remains unresolved.",
        "UP also retains its original source manifest,",
        "including source-copy aliases, quality counts and pending adapters.",
        "PDFs, HTML responses and OCR caches remain in their acquisition repositories.",
        "",
        "| State | Observations | Files | Snapshot provenance |",
        "|---|---:|---:|---|",
    ]
    for entry in sorted(entries.values(), key=lambda item: item["state"]):
        lines.append(
            f"| {entry['state']} | {entry['rows']:,} | {entry['files']} | "
            f"[provenance]({entry['path']}/provenance.json) |"
        )
    lines.extend(
        [
            "",
            "Rebuild without rewriting the pooled seat tables:",
            "",
            "```sh",
            "python -m local_reservations.tools.build_master --observations-only",
            "```",
            "",
            "Update observation_sources.json deliberately when adopting a newer",
            "source snapshot. The importer never follows mutable latest pointers.",
            "Checksums establish file integrity, not OCR accuracy or "
            "complete coverage.",
            "",
        ]
    )
    return "\n".join(lines)


def sync(root, master_output, only=None):
    root, master_output = Path(root), Path(master_output)
    config_path = root / "data" / "master" / "observation_sources.json"
    config = json.loads(config_path.read_bytes())
    if config["format_version"] != 1:
        raise ValueError("Unsupported observation source configuration")
    output = master_output / "observations"
    output.mkdir(parents=True, exist_ok=True)
    index_path = output / "index.json"
    entries = (
        json.loads(index_path.read_bytes())["states"] if index_path.exists() else {}
    )
    published = []
    for spec in config["sources"]:
        if only is not None and spec["state"] not in only:
            continue
        entry = publish_source(root, output, spec)
        entries[spec["state"]] = entry
        published.append(entry)
    index = {"format_version": 1, "assignment_usable": False, "states": entries}
    with tempfile.TemporaryDirectory(prefix=".index-", dir=output) as temporary:
        staging = Path(temporary)
        (staging / "index.json").write_bytes(json_bytes(index))
        (staging / "readme.md").write_text(render_readme(entries), encoding="utf-8")
        os.replace(staging / "readme.md", output / "readme.md")
        os.replace(staging / "index.json", index_path)
    return published
