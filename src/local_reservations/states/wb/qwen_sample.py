"""Freeze a stratified, blinded source-cell sample for local vision OCR review."""

import argparse
import csv
import hashlib
import io
import json
import random
import subprocess
import tempfile
from collections import defaultdict
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path

import pdfplumber
from PIL import Image

from local_reservations.common.runlog import command
from local_reservations.paths import ROOT

BASE = ROOT / "data/wb/derived"
OUT = BASE / "qwen_review/expanded"


def read_csv(path):
    with path.open() as handle:
        return list(csv.DictReader(handle))


def source_frame():
    frame = []
    for row in read_csv(BASE / "office_native/cell_review.csv"):
        if not row["tier"].startswith("gp_") or row["heading"] == "True":
            continue
        frame.append(
            {
                "row_id": row["row_id"],
                "source_path": row["source_path"],
                "source_sha256": row["source_sha256"],
                "source_page": int(row["source_page"]),
                "bbox": json.loads(row["source_bbox"]),
                "bbox_units": "PDF points",
                "district": row["district"],
                "year": row["election_year"],
                "stage": row["stage"],
                "tier": row["tier"],
                "axis": "caste" if row["source_column"] == "4" else "women",
                "provisional_kind": "parser_positive"
                if row["category"]
                else "blank_or_unresolved",
                "baseline_reading": row["raw_reading"],
            }
        )
    for row in read_csv(BASE / "office_scans/row_review.csv"):
        if not row["tier"].startswith("gp_") or "block_heading" in row["quality_flags"]:
            continue
        frame.append(
            {
                "row_id": row["record_id"],
                "source_path": "data/wb/" + row["source_file"],
                "source_sha256": row["sha256"],
                "source_page": int(row["page"]),
                "bbox": json.loads(row["bbox"]),
                "bbox_units": row["bbox_coordinate_system"],
                "district": row["district"],
                "year": row["election_year"],
                "stage": row["stage"],
                "tier": row["tier"],
                "axis": row["axis"],
                "provisional_kind": "parser_positive"
                if row["category"]
                else "blank_or_unresolved",
                "baseline_reading": row["raw_reading"],
            }
        )
    return frame


def stratified_sample(frame, size, seed):
    grouped = defaultdict(list)
    fields = ("district", "year", "stage", "tier", "axis", "provisional_kind")
    for row in sorted(frame, key=lambda r: r["row_id"]):
        grouped[tuple(row[k] for k in fields)].append(row)
    rng = random.Random(seed)  # noqa: S311 - reproducible sampling
    keys = sorted(grouped)
    rng.shuffle(keys)
    for rows in grouped.values():
        rng.shuffle(rows)
    if size < len(keys) or size > len(frame):
        raise ValueError(
            "Sample size must cover all nonempty strata without replacement"
        )
    allocated = dict.fromkeys(keys, 0)
    while sum(allocated.values()) < size:
        for key in keys:
            if allocated[key] < len(grouped[key]):
                allocated[key] += 1
                if sum(allocated.values()) == size:
                    break
    result = []
    for key in sorted(keys):
        for row in grouped[key][: allocated[key]]:
            result.append(
                row
                | {
                    "stratum": json.dumps(key),
                    "frame_n": len(grouped[key]),
                    "sample_n": allocated[key],
                    "sampling_weight": len(grouped[key]) / allocated[key],
                }
            )
    rng.shuffle(result)
    return result


@lru_cache(maxsize=8)
def poppler_page(path, page):
    with tempfile.TemporaryDirectory() as tmp:
        stem = Path(tmp) / "page"
        subprocess.run(
            [
                "pdftoppm",
                "-f",
                str(page),
                "-l",
                str(page),
                "-r",
                "360",
                "-singlefile",
                "-png",
                str(path),
                str(stem),
            ],
            check=True,
            capture_output=True,
        )
        with Image.open(stem.with_suffix(".png")) as image:
            return image.copy()


def poppler_crop(path, row):
    image = poppler_page(path, row["source_page"])
    factor = 5 if row["bbox_units"] == "PDF points" else max(image.size) / 1800
    pixel_box = [x * factor for x in row["bbox"]]
    box = [x / 5 for x in pixel_box]
    return image.crop(pixel_box).copy(), box


def ensure_crop(target, key, render):
    """Reuse only pinned crops; verify legacy crops without overwriting them."""
    evidence_path = target.with_suffix(".provenance.json")
    evidence = None
    if evidence_path.exists():
        evidence = json.loads(evidence_path.read_text())
        if evidence["fingerprint"] != key:
            raise ValueError("Frozen crop provenance changed")
        if target.exists():
            if (
                hashlib.sha256(target.read_bytes()).hexdigest()
                != evidence["image_sha256"]
            ):
                raise ValueError("Frozen crop bytes changed")
            return evidence["pdf_bbox"]
    image, box = render()
    encoded = io.BytesIO()
    image.save(encoded, format="PNG")
    data = encoded.getvalue()
    if evidence and hashlib.sha256(data).hexdigest() != evidence["image_sha256"]:
        raise ValueError("Regenerated crop differs from pinned image")
    if target.exists() and target.read_bytes() != data:
        raise ValueError(f"Existing frozen crop differs from source rerender: {target}")
    if not target.exists():
        target.write_bytes(data)
    evidence_path.write_text(
        json.dumps(
            {
                "fingerprint": key,
                "image_sha256": hashlib.sha256(data).hexdigest(),
                "pdf_bbox": box,
                "verified_by": "fresh_source_render_byte_comparison",
            },
            indent=2,
        )
        + "\n"
    )
    return box


@command("extract", state="West Bengal", source="frozen_office_cell_sample")
def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--size", type=int, default=200)
    parser.add_argument("--seed", type=int, default=20260907)
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    frozen = OUT / "sample.json"
    if frozen.exists():
        sample_bytes = frozen.read_bytes()
        sample = json.loads(sample_bytes)
        design = json.loads((OUT / "design.json").read_text())
        if hashlib.sha256(sample_bytes).hexdigest() != design.get("sample_sha256"):
            raise ValueError("Frozen sample hash mismatch; do not silently reuse edits")
        if len(sample) != args.size or design["seed"] != args.seed:
            raise ValueError("Existing frozen sample differs; do not silently resample")
    else:
        excluded = set()
        for path in [
            BASE / "qwen_review/pilot_manifest.json",
            BASE / "qwen_review/highres_manifest.json",
            BASE / "qwen_review/s24_targeted/manifest.json",
        ]:
            if path.exists():
                excluded.update(r["row_id"] for r in json.loads(path.read_text()))
        frame = [r for r in source_frame() if r["row_id"] not in excluded]
        sample = stratified_sample(frame, args.size, args.seed)
        for i, row in enumerate(sample, 1):
            row["sample_id"] = i
        frozen.write_text(json.dumps(sample, indent=2) + "\n")
        (OUT / "design.json").write_text(
            json.dumps(
                {
                    "seed": args.seed,
                    "sample_size": args.size,
                    "eligible_frame_cells": len(frame),
                    "excluded_previous_pilot_cells": len(excluded),
                    "strata": len({r["stratum"] for r in sample}),
                    "allocation": (
                        "Approximately equal allocation to nonempty strata; "
                        "inverse inclusion weights retained"
                    ),
                    "frozen_utc": datetime.now(UTC).isoformat(),
                    "sample_sha256": hashlib.sha256(frozen.read_bytes()).hexdigest(),
                    "scope": (
                        "Acquired GP Pradhan/deputy office cells; excludes "
                        "block/district offices and known block headings. "
                        "Positive/blank strata use parser labels, not gold."
                    ),
                },
                indent=2,
            )
            + "\n"
        )
    manifests = []
    pdfs = {}
    try:
        for row in sample:
            path = ROOT / row["source_path"]
            if path not in pdfs:
                if (
                    hashlib.sha256(path.read_bytes()).hexdigest()
                    != row["source_sha256"]
                ):
                    raise ValueError("Source hash changed")
                pdfs[path] = pdfplumber.open(path)
            target = OUT / f"cell_{row['sample_id']:03d}.png"
            use_poppler = row["source_page"] > len(pdfs[path].pages)
            key = {
                k: row[k]
                for k in (
                    "source_sha256",
                    "source_page",
                    "bbox",
                    "bbox_units",
                )
            } | {
                "dpi": 360,
                "recipe": "source_bbox_v1",
                "renderer": "poppler" if use_poppler else "pdfplumber",
                "pdfplumber_version": pdfplumber.__version__,
                "pillow_version": Image.__version__,
            }
            if use_poppler:
                box = ensure_crop(target, key, lambda: poppler_crop(path, row))
            else:
                page = pdfs[path].pages[row["source_page"] - 1]
                factor = (
                    1
                    if row["bbox_units"] == "PDF points"
                    else max(page.width, page.height) / 1800
                )
                box = [x * factor for x in row["bbox"]]
                box = [
                    max(0, box[0]),
                    max(0, box[1]),
                    min(page.width, box[2]),
                    min(page.height, box[3]),
                ]
                box = ensure_crop(
                    target,
                    key,
                    lambda: (page.crop(box).to_image(resolution=360).original, box),
                )
            manifests.append(
                {
                    "sample_id": row["sample_id"],
                    "row_id": row["row_id"],
                    "image_path": str(target.relative_to(ROOT)),
                    "source_path": row["source_path"],
                    "source_sha256": row["source_sha256"],
                    "source_page": row["source_page"],
                    "source_bbox": json.dumps(box),
                    "axis": row["axis"],
                    "tier": row["tier"],
                    "raster_dpi": 360,
                    "image_sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
                }
            )
            if len(manifests) % 25 == 0:
                print(
                    f"Verified source crop provenance {len(manifests)}/{len(sample)}",
                    flush=True,
                )
    finally:
        for pdf in pdfs.values():
            pdf.close()
    (OUT / "manifest.json").write_text(json.dumps(manifests, indent=2) + "\n")
    for label, subset in [
        ("a", manifests[:100]),
        ("b", manifests[100:]),
        ("overlap_a", manifests[100:110]),
        ("overlap_b", manifests[:10]),
    ]:
        (OUT / f"blind_{label}.json").write_text(json.dumps(subset, indent=2) + "\n")
    print(f"Frozen {len(sample)} cells; blinded manifests and 360dpi crops ready")


if __name__ == "__main__":
    main()
