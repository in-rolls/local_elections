"""Read scanned WB office schedules as positive reservation mentions.

Run with ``python -m local_reservations.states.wb.parse_office_scans``.
The acquired PDFs remain immutable. Every table cell, including unread/blank
cells, is retained for review. Absence from these schedules is not a negative.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
import subprocess
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
from pathlib import Path

import cv2
import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

from local_reservations.common.runlog import command

BASE = Path("data/wb")
OUT = BASE / "derived/office_scans"


def select_sources(index: Path) -> list[dict]:
    """Select acquired scanned GP, block, and district office sources by scope."""
    with index.open() as handle:
        selected = [
            r
            for r in csv.DictReader(handle)
            if (
                r["district"] in {"Birbhum", "Alipurduar"}
                and r["election_year"] == "2023"
                and r["content_kind"] in {"gp_head", "gp_deputy"}
            )
            or r["file"].endswith("cooch_behar_final_office_reservations.pdf")
            or "nadia_Pradhan_20_" in r["file"]
            or "267-SEC-Form1D-Sabhadhipati" in r["file"]
            or (
                r["district"] == "Alipurduar"
                and r["election_year"] == "2023"
                and r["content_kind"] == "office_or_zp"
                and "publication_of_" not in r["file"]
            )
        ]

    for source in selected:
        if "267-SEC-Form1D-Sabhadhipati" in source["file"]:
            source["stage"] = "final"
            source["notes"] = "Visually verified Form 1D gazette dated 6 March 2018."
    return selected


def groups(values: np.ndarray, gap: int = 5) -> list[int]:
    """Reduce adjacent rule pixels to one line coordinate."""
    if not len(values):
        return []
    return [
        int(np.median(g))
        for g in np.split(values, np.where(np.diff(values) > gap)[0] + 1)
    ]


def grid_masks(gray: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    binary = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY_INV, 31, 15
    )
    horizontal = cv2.morphologyEx(binary, cv2.MORPH_OPEN, np.ones((1, 50), np.uint8))
    vertical = cv2.morphologyEx(binary, cv2.MORPH_OPEN, np.ones((50, 1), np.uint8))
    return horizontal, vertical


def rectify(gray: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Rectify the largest ruled table; fail rather than guess a missing grid."""
    horizontal, vertical = grid_masks(gray)
    mask = cv2.dilate(horizontal | vertical, np.ones((5, 5), np.uint8))
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    contour = cv2.convexHull(max(contours, key=cv2.contourArea))
    points = cv2.approxPolyDP(
        contour, 0.02 * cv2.arcLength(contour, True), True
    ).reshape(-1, 2)
    if len(points) != 4 or cv2.contourArea(contour) < gray.size * 0.04:
        raise ValueError("No reliable four-corner table")
    total, diff = points.sum(axis=1), np.diff(points, axis=1).ravel()
    corners = np.float32(
        [
            points[total.argmin()],
            points[diff.argmin()],
            points[total.argmax()],
            points[diff.argmax()],
        ]
    )
    width = int(
        max(
            np.linalg.norm(corners[1] - corners[0]),
            np.linalg.norm(corners[2] - corners[3]),
        )
    )
    height = int(
        max(
            np.linalg.norm(corners[3] - corners[0]),
            np.linalg.norm(corners[2] - corners[1]),
        )
    )
    transform = cv2.getPerspectiveTransform(
        corners,
        np.float32([[0, 0], [width - 1, 0], [width - 1, height - 1], [0, height - 1]]),
    )
    return cv2.warpPerspective(
        gray, transform, (width, height), borderValue=255
    ), transform


def tier_for_page(source: dict, page: int, row_y: float = 0) -> str:
    if source["district"] == "Nadia":
        return "gp_deputy" if page >= 6 else "gp_head"
    if source["district"] == "Cooch Behar":
        if page <= 5:
            return "gp_head"
        if page <= 8:
            return "gp_deputy"
        return "block_deputy" if row_y >= 0.86 else "block_head"
    return source["content_kind"]


def parse_reading(raw: str, axis: str) -> tuple[str, str | None]:
    """Normalize typography only; never impute a missing reservation category."""
    text = re.sub(r"\s+", " ", raw).strip(" |[]{}_")
    if axis == "women":
        if re.fullmatch(r"W+", text, re.I):
            return "", None
        text = re.sub(r"\s+W+\s*$", "", text, flags=re.I).strip()
        return text, "women" if re.search(r"[A-Za-z]{2}", text) else None
    match = re.search(r"(?:\(\s*|\s+)(SC|ST|BC)\s*\)?[.\s|~\x27‘’]*$", text, flags=re.I)
    if not match:
        return text, None
    return text[: match.start()].strip(" (|"), match.group(1).upper()


def run_ocr(path: Path, psm: int) -> dict:
    result = subprocess.run(
        ["tesseract", str(path), "stdout", "--psm", str(psm), "tsv"],
        capture_output=True,
        text=True,
        check=True,
    )
    words = [
        r
        for r in csv.DictReader(
            io.StringIO(result.stdout), delimiter="\t", quoting=csv.QUOTE_NONE
        )
        if r["text"].strip()
    ]
    return {
        "text": " ".join(r["text"] for r in words),
        "min_confidence": min((float(r["conf"]) for r in words), default=None),
        "words": words,
    }


def build_page(source: dict, page: int, directory: Path) -> tuple[list[dict], dict]:
    image_path = directory / f"highres-{page}.png"
    gray = cv2.imread(str(image_path), cv2.IMREAD_GRAYSCALE)
    table, transform = rectify(gray)
    horizontal, vertical = grid_masks(table)
    height, width = table.shape
    xs = groups(np.flatnonzero((vertical > 0).sum(axis=0) > height * 0.15))
    expected = {
        "Alipurduar": (0.417, 0.797),
        "Birbhum": (0.578, 0.780),
        "Cooch Behar": (0.562, 0.821),
        "Nadia": (0.578, 0.808),
    }[source["district"]]
    if source["district"] == "Cooch Behar" and page == 9:
        expected = (0.622, 0.824)
    bounds = [min(xs, key=lambda x: abs(x / width - q)) for q in expected] + [width - 1]
    if any(abs(bounds[i] / width - expected[i]) > 0.07 for i in range(2)):
        raise ValueError("Named-column boundary not found")
    ys = groups(
        np.flatnonzero(
            (horizontal[:, bounds[0] :] > 0).sum(axis=1) > (width - bounds[0]) * 0.30
        ),
        gap=12,
    )
    if ys and ys[0] > 12:
        ys.insert(0, 0)
    if len(ys) < 3:
        raise ValueError("Insufficient row rules")
    start = 0 if source["district"] == "Nadia" and page in {3, 4, 5, 7} else 2
    clean = table.copy()
    clean[cv2.dilate(horizontal | vertical, np.ones((3, 3), np.uint8)) > 0] = 255
    _, clean = cv2.threshold(clean, 180, 255, cv2.THRESH_BINARY)
    cv2.imwrite(str(directory / f"table-{page}.png"), table)
    inverse = np.linalg.inv(transform)
    rows = []
    for row_no, (y0, y1) in enumerate(
        zip(ys[start:-1], ys[start + 1 :], strict=True), 1
    ):
        for axis, x0, x1 in zip(
            ("caste", "women"), bounds[:-1], bounds[1:], strict=True
        ):
            points = np.float32([[[x0, y0], [x1, y0], [x1, y1], [x0, y1]]])
            points = cv2.perspectiveTransform(points, inverse)[0] / 2
            if source["district"] == "Nadia" and 2 <= page <= 6:
                # Inverse of clockwise rotation; original image height is rotated width.
                points = np.column_stack(
                    [points[:, 1], gray.shape[1] / 2 - points[:, 0]]
                )
            box = [
                round(float(points[:, 0].min()), 2),
                round(float(points[:, 1].min()), 2),
                round(float(points[:, 0].max()), 2),
                round(float(points[:, 1].max()), 2),
            ]
            version = "v5" if source["district"] == "Nadia" and page == 5 else "v4"
            stem = f"{version}-cell-{page}-{row_no}-{axis}"
            crop_path = directory / f"{stem}.png"
            cv2.imwrite(
                str(crop_path),
                cv2.copyMakeBorder(
                    clean[y0 + 4 : y1 - 3, x0 + 5 : x1 - 4],
                    12,
                    12,
                    12,
                    12,
                    cv2.BORDER_CONSTANT,
                    value=255,
                ),
            )
            rows.append(
                {
                    "source_file": source["file"],
                    "sha256": source["sha256"],
                    "source_url": source["source_url"],
                    "archive_url": source["archive_url"],
                    "district": source["district"],
                    "election_year": int(source["election_year"]),
                    "stage": source["stage"],
                    "page": page,
                    "table_row": row_no,
                    "tier": tier_for_page(source, page, ((y0 + y1) / 2) / height),
                    "axis": axis,
                    "bbox": json.dumps(box),
                    "bbox_coordinate_system": (
                        "rendered_original_page_pixels_scale_to_1800"
                    ),
                    "crop_path": str(crop_path),
                    "cache_path": str(directory / f"{stem}.json"),
                    "table_y_fraction": round(((y0 + y1) / 2) / height, 6),
                }
            )
    return rows, {
        "source_file": source["file"],
        "sha256": source["sha256"],
        "page": page,
        "page_kind": "office_schedule",
        "cell_count": len(rows),
        "row_rules": json.dumps(ys),
        "column_rules": json.dumps(bounds),
        "review_status": "layout_visually_inspected_cells_require_review",
    }


@lru_cache(maxsize=1)
def tesseract_version() -> str:
    return subprocess.run(
        ["tesseract", "--version"], capture_output=True, text=True, check=True
    ).stdout.splitlines()[0]


def cell_fingerprint(path: Path) -> dict:
    return {
        "crop_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "tesseract_version": tesseract_version(),
        "psms": [6, 7],
        "language": "eng",
        "tsv_parser": "quote_none_v1",
    }


def read_cell(row: dict) -> dict:
    cache = Path(row["cache_path"])
    crop = Path(row["crop_path"])
    fingerprint = cell_fingerprint(crop)
    payload = json.loads(cache.read_text()) if cache.exists() else {}
    if payload.get("fingerprint") == fingerprint:
        readings = payload["readings"]
    else:
        readings = {str(psm): run_ocr(crop, psm) for psm in (6, 7)}
        cache.write_text(
            json.dumps(
                {"fingerprint": fingerprint, "readings": readings}, ensure_ascii=False
            )
        )
    raw = readings["6"]["text"]
    name, category = parse_reading(raw, row["axis"])
    other_name, other_category = parse_reading(readings["7"]["text"], row["axis"])
    flags = ["ocr_not_certified", "positive_mentions_only"]
    if (name, category) != (other_name, other_category):
        flags.append("ocr_pass_disagreement")
    if (
        readings["6"]["min_confidence"] is not None
        and readings["6"]["min_confidence"] < 75
    ):
        flags.append("low_ocr_confidence")
    if name and category is None:
        flags.append("unresolved_category_or_nondata_cell")
    if not name:
        flags.append("blank_or_unread_cell")
    if re.search(r"\bblock\b", raw, re.I):
        flags.append("block_heading")
        category = None
    if category and not re.search(r"[A-Za-z]{2}", name):
        flags.append("unresolved_name")
        category = None
    return row | {
        "raw_reading": raw,
        "second_reading": readings["7"]["text"],
        "name": name,
        "category": category,
        "min_confidence": readings["6"]["min_confidence"],
        "quality_flags": ";".join(flags),
        "review_status": "pending_cell_review",
        "women_reserved": True if category == "women" else None,
        "caste_category": category if category in {"SC", "ST", "BC"} else None,
        "block": None,
        "winner_gender": None,
    }


def annotate_rows(rows: list[dict], output: Path) -> list[dict]:
    """Apply source-pinned visual corrections and the inspected block headings."""
    override_path = output / "cell_overrides.json"
    if not override_path.exists():
        override_path = OUT / "cell_overrides.json"
    overrides = json.loads(override_path.read_text()) if override_path.exists() else []
    corrections = {
        (r["sha256"], r["page"], r["table_row"], r["axis"]): r for r in overrides
    }
    if len(corrections) != len(overrides):
        raise ValueError("Duplicate source-pinned visual correction keys")
    reference_hashes = {}
    for correction in overrides:
        for evidence in correction.get("reference_evidence", []):
            path = Path(evidence["gold_path"])
            if path not in reference_hashes:
                reference_hashes[path] = hashlib.sha256(path.read_bytes()).hexdigest()
            if reference_hashes[path] != evidence["gold_sha256"]:
                raise ValueError("Frozen visual reference file changed")
    block = None
    current_source = None
    for row in rows:
        if row["sha256"] != current_source:
            current_source, block = row["sha256"], None
        if row["district"] == "Alipurduar" and row["tier"] in {"gp_head", "gp_deputy"}:
            if row["tier"] == "gp_deputy":
                headings = {
                    1: "Kumargram",
                    3: "Alipurduar II",
                    6: "Kalchini",
                    10: "Alipurduar I",
                    14: "Falakata",
                    18: "Madarihat Birpara",
                }
            elif row["page"] == 2:
                headings = {
                    1: "Kumargram",
                    12: "Alipurduar II",
                    22: "Kalchini",
                    31: "Alipurduar I",
                }
            else:
                headings = {1: "Falakata", 9: "Madarihat Birpara"}
            if row["table_row"] in headings:
                expected_block = headings[row["table_row"]]
                if row["axis"] == "caste":
                    raw_prefix = re.sub(r"[^a-z]", "", row["raw_reading"].lower())
                    expected_prefix = expected_block.split()[0].lower()[:5]
                    if (
                        not 0 <= raw_prefix.find(expected_prefix) <= 2
                        or row["category"]
                    ):
                        raise ValueError(
                            "Visually identified block-heading geometry changed"
                        )
                block = expected_block
                row.update(category=None, women_reserved=None, caste_category=None)
                row["quality_flags"] += ";block_heading_visually_identified"
                row["review_status"] = "visually_identified_block_heading"
            row["block"] = block
        row.setdefault("reviewed_reading", None)
        row.setdefault("review_note", None)
        row.setdefault("visual_reference_sample_id", None)
        row.setdefault("visual_reference_evidence", None)
        row.setdefault("visual_name_ambiguous", False)
        key = (row["sha256"], row["page"], row["table_row"], row["axis"])
        if key in corrections:
            correction = corrections[key]
            if json.loads(row["bbox"]) != correction["bbox"]:
                raise ValueError("Visually corrected cell geometry changed")
            if (
                correction.get("bbox_coordinate_system", row["bbox_coordinate_system"])
                != row["bbox_coordinate_system"]
            ):
                raise ValueError("Visually corrected cell coordinate units changed")
            if correction.get("source_file", row["source_file"]) != row["source_file"]:
                raise ValueError("Visually corrected cell source path changed")
            if "exact_name" in correction:
                name, category = (
                    correction["exact_name"],
                    correction["explicit_category"],
                )
                if correction.get("category_ambiguous"):
                    category = None
                if correction.get("blank"):
                    name, category = None, None
                allowed = (
                    {None, "women"}
                    if row["axis"] == "women"
                    else {None, "SC", "ST", "BC"}
                )
                if category not in allowed:
                    raise ValueError(
                        "Visual reference category contradicts source axis"
                    )
                row.update(
                    visual_reference_sample_id=correction["sample_id"],
                    visual_reference_evidence=json.dumps(
                        correction["reference_evidence"]
                    ),
                    visual_name_ambiguous=correction["name_ambiguous"],
                )
            else:
                name, category = parse_reading(correction["reading"], row["axis"])
            row.update(
                name=name,
                category=category,
                women_reserved=True if category == "women" else None,
                caste_category=category if category in {"SC", "ST", "BC"} else None,
                reviewed_reading=correction["reading"],
                review_note=correction["note"],
                review_status="visually_corrected",
            )
            row["quality_flags"] += ";source_pinned_visual_correction"
            if correction.get("name_ambiguous"):
                row["review_status"] = "visually_read_ambiguous_exact_name"
                row["quality_flags"] += ";visual_exact_name_unresolved"
            elif correction.get("blank"):
                row["review_status"] = "visually_reviewed_blank"
                row["quality_flags"] += ";visual_reference_blank"
        row["record_id"] = ":".join(
            str(row[k]) for k in ("sha256", "page", "tier", "table_row", "axis")
        )
        row["name_review_status"] = (
            "visually_read_independent_verification_pending"
            if row["review_status"] in {"visually_transcribed", "visually_corrected"}
            else "unreviewed_ocr"
        )
        if row["visual_name_ambiguous"]:
            row["name_review_status"] = "unresolved_exact_name"
        elif row["review_status"] == "visually_reviewed_blank":
            row["name_review_status"] = "not_a_named_entry"
    return rows


def reconcile(rows: list[dict], output: Path) -> list[dict]:
    """Compare actual named mentions with printed totals without forcing agreement."""
    path = output / "printed_controls.json"
    if not path.exists():
        path = OUT / "printed_controls.json"
    controls = json.loads(path.read_text())
    counts = Counter(
        (r["sha256"], r["tier"], r["category"]) for r in rows if r["category"]
    )
    audit = []
    for control in controls:
        for category in ("SC", "ST", "BC", "women"):
            key = (control["sha256"], control["tier"], category)
            audit.append(
                {
                    "source_file": control["source_file"],
                    "sha256": control["sha256"],
                    "tier": control["tier"],
                    "control_page": control["page"],
                    "category": category,
                    "printed_offices": control["printed_offices"],
                    "printed_reserved": control[category],
                    "extracted_mentions": counts[key],
                    "difference": (
                        counts[key] - control[category]
                        if control[category] is not None
                        else None
                    ),
                    "review_status": "printed_blank_not_a_count"
                    if control[category] is None
                    else "count_reconciled_not_name_accuracy"
                    if counts[key] == control[category]
                    else "printed_control_discrepancy_requires_review",
                }
            )
    mismatches = {(r["sha256"], r["tier"]) for r in audit if r["difference"]}
    for row in rows:
        if (row["sha256"], row["tier"]) in mismatches:
            row["quality_flags"] += ";printed_control_discrepancy"
    return audit


def write_csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=list(rows[0]) if rows else ["source_file"]
        )
        writer.writeheader()
        writer.writerows(rows)


def run(base: Path = BASE, output: Path = OUT, workers: int = 6) -> dict:
    from PIL import Image

    output.mkdir(parents=True, exist_ok=True)
    sources = select_sources(base / "gp_source_search/manual_entry_index.csv")
    (output / "sources.json").write_text(json.dumps(sources, indent=2))
    all_cells, pages, curated_entries = [], [], []
    curated_file = output / "curated_schedules.json"
    if not curated_file.exists():
        curated_file = OUT / "curated_schedules.json"
    curated = json.loads(curated_file.read_text()) if curated_file.exists() else []
    for source in sources:
        original = base / source["file"]
        if hashlib.sha256(original.read_bytes()).hexdigest() != source["sha256"]:
            raise ValueError(f"Source hash mismatch: {original}")
        directory = output / source["sha256"]
        directory.mkdir(exist_ok=True)
        if len(list(directory.glob("page-*.png"))) != int(source["pages"]):
            subprocess.run(
                [
                    "pdftoppm",
                    "-scale-to",
                    "1800",
                    "-png",
                    str(original),
                    str(directory / "page"),
                ],
                check=True,
                capture_output=True,
            )
        if (
            source["content_kind"] == "office_or_zp"
            or "267-SEC-Form1D-Sabhadhipati" in source["file"]
        ):
            entries = [r for r in curated if r["sha256"] == source["sha256"]]
            if not entries:
                raise ValueError(
                    "Missing source-pinned transcription for additional office source"
                )
            curated_entries.extend((source, r) for r in entries)
            for page in range(1, int(source["pages"]) + 1):
                text_cache = directory / f"page-{page}-text.json"
                if not text_cache.exists():
                    text_cache.write_text(
                        json.dumps(run_ocr(directory / f"page-{page}.png", 3))
                    )
                positive = sum(r["page"] == page for r in entries)
                pages.append(
                    {
                        "source_file": source["file"],
                        "sha256": source["sha256"],
                        "page": page,
                        "page_kind": "office_schedule" if positive else "order_cover",
                        "cell_count": positive,
                        "row_rules": "[]",
                        "column_rules": "[]",
                        "review_status": "visually_transcribed_all_positive_names"
                        if positive
                        else "visually_inspected_notice_text_cached",
                    }
                )
            continue
        for page in range(1, int(source["pages"]) + 1):
            cover = page == 1 and source["district"] != "Birbhum"
            if cover:
                pages.append(
                    {
                        "source_file": source["file"],
                        "sha256": source["sha256"],
                        "page": page,
                        "page_kind": "order_cover",
                        "cell_count": 0,
                        "row_rules": "[]",
                        "column_rules": "[]",
                        "review_status": "visually_inspected_no_named_schedule",
                    }
                )
                continue
            image_path = directory / f"highres-{page}.png"
            if not image_path.exists():
                subprocess.run(
                    [
                        "pdftoppm",
                        "-f",
                        str(page),
                        "-l",
                        str(page),
                        "-singlefile",
                        "-scale-to",
                        "3600",
                        "-png",
                        str(original),
                        str(directory / f"full-{page}"),
                    ],
                    check=True,
                    capture_output=True,
                )
                im = Image.open(directory / f"full-{page}.png")
                if source["district"] == "Nadia" and 2 <= page <= 6:
                    im = im.rotate(-90, expand=True)
                im.save(image_path)
            try:
                cells, review = build_page(source, page, directory)
                all_cells.extend(cells)
                pages.append(review)
            except ValueError as exc:
                pages.append(
                    {
                        "source_file": source["file"],
                        "sha256": source["sha256"],
                        "page": page,
                        "page_kind": "unresolved_schedule",
                        "cell_count": 0,
                        "row_rules": "[]",
                        "column_rules": "[]",
                        "review_status": str(exc),
                    }
                )
    with ThreadPoolExecutor(workers) as pool:
        rows = list(pool.map(read_cell, all_cells))
    template = dict.fromkeys(rows[0])
    for source, entry in curated_entries:
        name, category = parse_reading(entry["reading"], entry["axis"])
        row = template | {
            "source_file": source["file"],
            "sha256": source["sha256"],
            "source_url": source["source_url"],
            "archive_url": source["archive_url"],
            "district": None
            if entry["tier"].startswith("district_")
            else source["district"],
            "election_year": int(source["election_year"]),
            "stage": source["stage"],
            "page": entry["page"],
            "table_row": entry["table_row"],
            "tier": entry["tier"],
            "axis": entry["axis"],
            "bbox": json.dumps(entry["bbox"]),
            "bbox_coordinate_system": "rendered_original_page_pixels_scale_to_1800",
            "raw_reading": entry["reading"],
            "name": name,
            "category": category,
            "quality_flags": (
                "positive_mentions_only;visual_transcription_not_independently_verified"
            ),
            "review_status": "visually_transcribed",
            "women_reserved": True if category == "women" else None,
            "caste_category": category if category in {"SC", "ST", "BC"} else None,
            "reviewed_reading": entry["reading"],
            "review_note": entry["note"],
        }
        rows.append(row)
    rows = annotate_rows(rows, output)
    controls = reconcile(rows, output)
    write_csv(output / "control_reconciliation.csv", controls)
    mentions = [r for r in rows if r["category"] is not None]
    write_csv(output / "row_review.csv", rows)
    write_csv(output / "page_review.csv", pages)
    write_csv(output / "mentions.csv", mentions)
    pq.write_table(pa.Table.from_pylist(mentions), output / "mentions.parquet")
    (output / "mentions.jsonl").write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in mentions)
    )
    counts = []
    for source in sources:
        selected = [r for r in mentions if r["sha256"] == source["sha256"]]
        counts.append(
            {
                "source_file": source["file"],
                "sha256": source["sha256"],
                "pages_expected": int(source["pages"]),
                "pages_accounted": sum(p["sha256"] == source["sha256"] for p in pages),
                "positive_mentions": len(selected),
                "categories": json.dumps(
                    dict(Counter(r["category"] for r in selected))
                ),
                "quality_statement": (
                    "Extraction counts are not accuracy; cells await review; "
                    "absence remains unknown."
                ),
            }
        )
    write_csv(output / "source_counts.csv", counts)
    summary = {
        "sources": len(sources),
        "pages": len(pages),
        "cells": len(rows),
        "positive_mentions": len(mentions),
        "unresolved_pages": sum(p["page_kind"] == "unresolved_schedule" for p in pages),
    }
    (output / "summary.json").write_text(json.dumps(summary, indent=2))
    return summary


@command("parse", state="West Bengal", source="scanned_office_schedules")
def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, default=BASE)
    parser.add_argument("--output", type=Path, default=OUT)
    parser.add_argument("--workers", type=int, default=6)
    args = parser.parse_args()
    print(json.dumps(run(args.base, args.output, args.workers)))


if __name__ == "__main__":
    main()
