"""Preserve page images and raw local OCR for early Tamil Nadu office schedules.

Extraction is not semantic parsing. No village names, categories or office tiers
are inferred from OCR. The 2001 selection ends before the separate ward order.
Each retry has a new directory; prior attempts, including damaged caches, remain.
"""

import argparse
import concurrent.futures
import csv
import datetime as dt
import hashlib
import json
import os
import re
import subprocess
import time
import uuid
from pathlib import Path

import pdfplumber
from PIL import Image

from local_elections.common.runlog import command
from local_elections.paths import ROOT

OUT = ROOT / "data/tn/derived/scans"
MANIFEST = ROOT / "data/source_search/early_heads/source_manifest.csv"
SOURCES = {
    "tn_1_58_1996_401_en": {
        "sha256": "869ffacec087105967d17ee8f072fb417c76aae786d60ef06e63f1c6b88aec07",
        "pages": 114,
        "selected_last": 114,
        "pilot": [1, 3],
    },
    "tn_1_58_2001_636_en": {
        "sha256": "5cc758b6cc8ad025f284276c61ce3f24302890783ea0a0233a6f2d4d76051bf3",
        "pages": 77,
        "selected_last": 18,
        "pilot": [1, 2],
    },
}


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def utc_now():
    return dt.datetime.now(dt.UTC).isoformat()


def write_json(path, data):
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    temporary.replace(path)


def load_sources(manifest=MANIFEST, root=ROOT, specifications=None):
    specs = SOURCES if specifications is None else specifications
    with manifest.open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    sources = []
    for source_id, spec in specs.items():
        matches = [r for r in rows if r["source_id"] == source_id]
        if len(matches) != 1:
            raise ValueError(f"Expected one acquisition manifest row: {source_id}")
        row = matches[0]
        source = root / row["path"]
        if digest(source) != spec["sha256"] or row["sha256"] != spec["sha256"]:
            raise ValueError(f"Source/acquisition hash mismatch: {source_id}")
        with pdfplumber.open(source) as pdf:
            if len(pdf.pages) != spec["pages"]:
                raise ValueError(f"Source page count mismatch: {source_id}")
            bounds = [list(page.bbox) for page in pdf.pages]
        sources.append(
            {
                "source_id": source_id,
                "source_path": str(source),
                "source_url": row["final_url"],
                "source_sha256": spec["sha256"],
                "source_pages": spec["pages"],
                "selected_last": spec["selected_last"],
                "pilot_pages": spec["pilot"],
                "page_bounds": bounds,
                "acquisition_manifest": str(manifest),
                "acquisition_manifest_sha256": digest(manifest),
            }
        )
    return sources


def toolchain(language, dpi, psm):
    if not re.fullmatch(r"[a-z_]+(?:\+[a-z_]+)*", language):
        raise ValueError("Invalid Tesseract language selection")
    languages = subprocess.run(
        ["tesseract", "--list-langs"], capture_output=True, text=True, check=True
    ).stdout
    match = re.search(r'"([^\"]+)"', languages)
    if match is None:
        raise ValueError("Cannot locate installed Tesseract traineddata")
    tessdata = Path(match[1])
    models = {}
    for name in language.split("+"):
        path = tessdata / f"{name}.traineddata"
        models[name] = {"path": str(path), "sha256": digest(path)}
    versions = {}
    for executable, argument in [("tesseract", "--version"), ("pdftoppm", "-v")]:
        result = subprocess.run(
            [executable, argument], capture_output=True, text=True, check=True
        )
        versions[executable] = (result.stdout + result.stderr).strip()
    return {
        "extractor_version": 1,
        "versions": versions,
        "traineddata": models,
        "settings": {
            "language": language,
            "dpi": dpi,
            "psm": psm,
            "oem": 1,
            "OMP_THREAD_LIMIT": "1",
            "rotation_clockwise": 0,
            "render_format": "png",
            "render_grayscale": False,
        },
    }


def page_identity(source, page, engine):
    return {
        "source_sha256": source["source_sha256"],
        "source_page": page,
        "engine": engine,
    }


def cached_page(page_dir, identity):
    pointer = page_dir / "latest.json"
    if not pointer.exists():
        return None
    try:
        metadata = json.loads(pointer.read_text())
        if metadata["identity"] != identity or metadata["status"] != "extracted":
            return None
        artifacts = metadata["artifacts"]
        if set(artifacts) != {"image", "tsv", "text", "stderr"}:
            return None
        for artifact in artifacts.values():
            path = page_dir / artifact["path"]
            if not path.resolve().is_relative_to(page_dir.resolve()):
                return None
            if path.stat().st_size != artifact["bytes"]:
                return None
            if digest(path) != artifact["sha256"]:
                return None
        return metadata
    except (OSError, ValueError, KeyError, TypeError):
        return None


def extract_page(source, page, engine, out=OUT):
    page_dir = out / source["source_id"] / f"page_{page:04d}"
    identity = page_identity(source, page, engine)
    cached = cached_page(page_dir, identity)
    if cached is not None:
        return cached
    attempt = page_dir / "attempts" / uuid.uuid4().hex
    attempt.mkdir(parents=True)
    metadata = {
        "identity": identity,
        "source_url": source["source_url"],
        "source_path": source["source_path"],
        "source_page_bbox": source["page_bounds"][page - 1],
        "started_utc": utc_now(),
        "status": "failed",
        "semantic_status": "raw_extraction_only_not_reservation_records",
        "artifacts": {},
    }
    started = time.monotonic()
    settings = engine["settings"]
    render = [
        "pdftoppm",
        "-f",
        str(page),
        "-l",
        str(page),
        "-r",
        str(settings["dpi"]),
        "-singlefile",
        "-png",
        source["source_path"],
        str(attempt / "source"),
    ]
    ocr = [
        "tesseract",
        str(attempt / "source.png"),
        str(attempt / "ocr"),
        "-l",
        settings["language"],
        "--psm",
        str(settings["psm"]),
        "--oem",
        str(settings["oem"]),
        "tsv",
        "txt",
    ]
    metadata["commands"] = [render, ocr]
    stderr = []
    try:
        for command in (render, ocr):
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=240,
                env={**os.environ, "OMP_THREAD_LIMIT": "1"},
            )
            stderr.append(result.stderr)
            if result.returncode:
                raise RuntimeError(f"Command exited {result.returncode}: {command[0]}")
        with Image.open(attempt / "source.png") as image:
            metadata["image_size"] = list(image.size)
            image.verify()
        text = (attempt / "ocr.txt").read_text()
        with (attempt / "ocr.tsv").open(newline="") as handle:
            words = list(csv.DictReader(handle, delimiter="\t"))
        if not words or "text" not in words[0]:
            raise ValueError("Tesseract TSV missing expected header/page structure")
        metadata["nonempty_word_count"] = sum(bool(w["text"].strip()) for w in words)
        metadata["text_characters"] = len(text)
        metadata["status"] = "extracted"
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as error:
        metadata["error"] = str(error)
    (attempt / "stderr.txt").write_text("\n".join(stderr))
    for kind, name in [
        ("image", "source.png"),
        ("tsv", "ocr.tsv"),
        ("text", "ocr.txt"),
        ("stderr", "stderr.txt"),
    ]:
        path = attempt / name
        if path.exists():
            metadata["artifacts"][kind] = {
                "path": str(path.relative_to(page_dir)),
                "sha256": digest(path),
                "bytes": path.stat().st_size,
            }
    metadata["finished_utc"] = utc_now()
    metadata["elapsed_seconds"] = round(time.monotonic() - started, 3)
    write_json(attempt / "metadata.json", metadata)
    write_json(page_dir / "latest.json", metadata)
    return metadata


def coverage(sources, engine, out):
    rows = []
    for source in sources:
        for page in range(1, source["source_pages"] + 1):
            selected = page <= source["selected_last"]
            directory = out / source["source_id"] / f"page_{page:04d}"
            result = cached_page(directory, page_identity(source, page, engine))
            status = "extracted" if result else "pending_or_invalid_cache"
            if selected and result is None:
                try:
                    latest = json.loads((directory / "latest.json").read_text())
                    if (
                        latest["identity"] == page_identity(source, page, engine)
                        and latest["status"] == "failed"
                    ):
                        status = "failed"
                except (OSError, ValueError, KeyError, TypeError):
                    pass
            if not selected:
                status = "outside_selected_office_section"
            rows.append(
                {
                    "source_id": source["source_id"],
                    "source_sha256": source["source_sha256"],
                    "source_url": source["source_url"],
                    "source_path": source["source_path"],
                    "source_page": page,
                    "selected": selected,
                    "status": status,
                    "page_metadata": str(directory / "latest.json")
                    if selected
                    else None,
                    "semantic_status": "not_parsed",
                }
            )
    return rows


@command("extract", state="Tamil Nadu", method="tesseract_page_ocr")
def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=OUT)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--dpi", type=int, default=300)
    parser.add_argument("--language", default="eng")
    parser.add_argument("--psm", type=int, default=3, choices=range(14))
    parser.add_argument("--pilot", action="store_true")
    args = parser.parse_args()
    if args.workers < 1 or args.dpi < 72:
        parser.error("workers must be positive and dpi at least 72")
    sources = load_sources()
    engine = toolchain(args.language, args.dpi, args.psm)
    args.out.mkdir(parents=True, exist_ok=True)
    write_json(args.out / "sources.json", sources)
    write_json(args.out / "engine.json", engine)
    tasks = [
        (source, page)
        for source in sources
        for page in (
            source["pilot_pages"]
            if args.pilot
            else range(1, source["selected_last"] + 1)
        )
    ]
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {
            pool.submit(extract_page, source, page, engine, args.out): (source, page)
            for source, page in tasks
        }
        for future in concurrent.futures.as_completed(futures):
            source, page = futures[future]
            result = future.result()
            event = {
                "source_id": source["source_id"],
                "page": page,
                "status": result["status"],
                "logged_utc": utc_now(),
            }
            with (args.out / "progress.jsonl").open("a") as handle:
                handle.write(json.dumps(event) + "\n")
            print(json.dumps(event), flush=True)
    rows = coverage(sources, engine, args.out)
    write_json(args.out / "page_audit.json", rows)
    with (args.out / "page_audit.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    write_json(
        args.out / "summary.json",
        {
            "selected_pages": sum(r["selected"] for r in rows),
            "completed_pages": sum(r["status"] == "extracted" for r in rows),
            "pending_or_invalid_pages": sum(
                r["status"] == "pending_or_invalid_cache" for r in rows
            ),
            "failed_pages": sum(r["status"] == "failed" for r in rows),
            "outside_scope_pages": sum(not r["selected"] for r in rows),
            "semantic_records": 0,
        },
    )
    if any(r["status"] == "failed" for r in rows) or (
        not args.pilot and any(r["status"] == "pending_or_invalid_cache" for r in rows)
    ):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
