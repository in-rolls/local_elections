"""Extract reserved-office cells, preserving OCR uncertainty and unknown negatives.

Raster rule geometry also recovers cells omitted by embedded PDF OCR. Every
selected page and every detected cell is logged, including blank and failed cells.
"""

import argparse
import csv
import hashlib
import json
import re
import subprocess
from concurrent.futures import ThreadPoolExecutor
from functools import cache
from itertools import pairwise

import cv2
import numpy as np
import pdfplumber

from local_reservations.common.runlog import command
from local_reservations.paths import ROOT
from local_reservations.states.wb.parse_office_scans import (
    grid_masks,
    groups,
    rectify,
    run_ocr,
)
from local_reservations.states.wb.parse_results import write_table

OUT = ROOT / "data/wb/derived/office_native"
INDEX = ROOT / "data/wb/gp_source_search/manual_entry_index.csv"


def select_sources():
    with INDEX.open() as handle:
        return [
            row
            for row in csv.DictReader(handle)
            if (
                row["district"] == "Purulia"
                and row["content_kind"] in {"gp_head", "gp_deputy"}
            )
            or (
                row["district"] == "Jalpaiguri"
                and row["content_kind"].startswith("gp_head;")
            )
            or (
                row["district"] == "South 24 Parganas"
                and row["content_kind"].startswith("gp_head")
            )
            or (
                row["district"] == "South 24 Parganas"
                and row["content_kind"] == "gp_deputy"
            )
        ]


def tier_for_page(source, page):
    if source["district"] == "Jalpaiguri":
        return {
            1: "gp_head",
            2: "gp_head",
            3: "gp_deputy",
            4: "block_head",
            5: "block_deputy",
        }[page]
    return "gp_deputy" if "upa" in source["file"].lower() else "gp_head"


def parse_reading(raw, column):
    text = re.sub(r"\s+", " ", raw).strip(" |_")
    match = re.search(r"[.\-\s({\[]+(SC|ST|BC|W)[)\]} .J\s]*$", text, re.I)
    marker = match[1].upper() if match else None
    name = text[: match.start()].strip(" .-([") if match else text
    if not re.search(r"[A-Za-z]{2}", name):
        return None, None
    if re.search(r"Block|Scheduled|Panchayats|reserved|Classes|Names of", name, re.I):
        return None, None
    return name, (
        "women" if column == 5 else marker if marker in {"SC", "ST", "BC"} else None
    )


def build_page(page, number, source, sha, directory):
    gray = np.array(page.to_image(resolution=144).original.convert("L"))
    table, transform = rectify(gray)
    horizontal, vertical = grid_masks(table)
    height, width = table.shape
    fractions = {
        "Purulia": (0.65, 0.83),
        "Jalpaiguri": (0.583, 0.79),
        "South 24 Parganas": (0.51, 0.773),
    }[source["district"]]
    if source["district"] == "Jalpaiguri" and number >= 4:
        fractions = (0.64, 0.83) if number == 4 else (0.666, 0.85)
    xs = groups(np.flatnonzero((vertical > 0).sum(axis=0) > height * 0.15))
    bounds = [min(xs, key=lambda x: abs(x / width - q)) for q in fractions] + [
        width - 1
    ]
    if any(abs(bounds[i] / width - fractions[i]) > 0.065 for i in range(2)):
        raise ValueError("Named column boundary missing")
    ys = groups(
        np.flatnonzero(
            (horizontal[:, bounds[0] :] > 0).sum(axis=1) > (width - bounds[0]) * 0.3
        ),
        gap=6,
    )
    if len(ys) < 2:
        raise ValueError("Row rules missing")
    clean = table.copy()
    clean[cv2.dilate(horizontal | vertical, np.ones((3, 3), np.uint8)) > 0] = 255
    clean = cv2.threshold(clean, 180, 255, cv2.THRESH_BINARY)[1]
    cv2.imwrite(str(directory / f"table-{number}.png"), table)
    words = page.extract_words()
    if words:
        centres = np.float32(
            [[[w["x0"] + w["x1"], w["top"] + w["bottom"]]] for w in words]
        )
        centres = cv2.perspectiveTransform(centres, transform)[:, 0, :]
    else:
        centres = []
    inverse = np.linalg.inv(transform)
    start = (
        0
        if source["district"] == "Purulia"
        or (source["district"] == "Jalpaiguri" and number == 2)
        else 2
    )
    block = (
        re.sub(r".*(?:1B_Pradhan_|1B_Upa-Pradhan_)", "", source["file"]).removesuffix(
            ".pdf"
        )
        if source["district"] == "Purulia"
        else None
    )
    rows = []
    for row_no, (y0, y1) in enumerate(pairwise(ys[start:]), 1):
        full = " ".join(
            w["text"] for w, (_, y) in zip(words, centres, strict=True) if y0 < y < y1
        )
        heading = source["district"] == "South 24 Parganas" and bool(
            re.search(r"\bBlock\b", full, re.I)
        )
        if heading:
            block = (
                re.sub(r"\s*Block.*", "", full, flags=re.I).strip()
                if re.search(r"\bBlock\b", full, re.I)
                else None
            )
        for column, (x0, x1) in enumerate(pairwise(bounds), 4):
            raw = " ".join(
                w["text"]
                for w, (x, y) in zip(words, centres, strict=True)
                if x0 < x < x1 and y0 < y < y1
            )
            points = (
                cv2.perspectiveTransform(
                    np.float32([[[x0, y0], [x1, y0], [x1, y1], [x0, y1]]]), inverse
                )[0]
                / 2
            )
            bbox = [
                round(float(points[:, 0].min()), 2),
                round(float(points[:, 1].min()), 2),
                round(float(points[:, 0].max()), 2),
                round(float(points[:, 1].max()), 2),
            ]
            stem = f"cell-v1-{number}-{row_no}-{column}"
            crop = directory / f"{stem}.png"
            cv2.imwrite(
                str(crop),
                cv2.copyMakeBorder(
                    clean[y0 + 3 : y1 - 2, x0 + 4 : x1 - 3],
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
                    "state": "West Bengal",
                    "district": source["district"],
                    "block": block,
                    "election_year": int(source["election_year"]),
                    "tier": tier_for_page(source, number),
                    "stage": source["stage"],
                    "source_path": "data/wb/" + source["file"],
                    "source_sha256": sha,
                    "source_page": number,
                    "source_column": column,
                    "table_row": row_no,
                    "source_bbox": json.dumps(bbox),
                    "bbox_units": "PDF points, top origin",
                    "native_reading": raw,
                    "heading": heading,
                    "crop_path": str(crop.relative_to(ROOT)),
                    "cache_path": str((directory / f"{stem}.json").relative_to(ROOT)),
                    "row_id": hashlib.sha256(
                        f"{sha}:{number}:{column}:{bbox}".encode()
                    ).hexdigest()[:24],
                }
            )
    return rows


@cache
def tesseract_version():
    return subprocess.run(
        ["tesseract", "--version"], capture_output=True, text=True, check=True
    ).stdout.splitlines()[0]


def read_cell(row):
    cache = ROOT / row["cache_path"]
    crop_sha = hashlib.sha256((ROOT / row["crop_path"]).read_bytes()).hexdigest()
    fingerprint = {
        "crop_sha256": crop_sha,
        "language": "eng",
        "psm": [6, 7],
        "format": "tsv",
        "tsv_reader": "quote_none_v1",
        "tesseract_version": tesseract_version(),
    }
    cached = json.loads(cache.read_text()) if cache.exists() else {}
    if cached.get("fingerprint") == fingerprint:
        readings = cached["readings"]
    else:
        readings = {str(psm): run_ocr(ROOT / row["crop_path"], psm) for psm in (6, 7)}
        cache.write_text(
            json.dumps(
                {"fingerprint": fingerprint, "readings": readings}, ensure_ascii=False
            )
        )
    raw = readings["6"]["text"]
    name, category = parse_reading(raw, row["source_column"])
    second = parse_reading(readings["7"]["text"], row["source_column"])
    native = parse_reading(row["native_reading"], row["source_column"])
    flags = ["positive_mentions_only", "ocr_not_certified"]
    if (name, category) != second:
        flags.append("ocr_segmentation_disagreement")
    if (name, category) != native:
        flags.append("native_ocr_disagreement")
    if row["heading"]:
        name, category = None, None
        flags.append("block_heading")
    if not category:
        flags.append("blank_or_unresolved_cell")
    return row | {
        "raw_reading": raw,
        "second_reading": readings["7"]["text"],
        "crop_sha256": crop_sha,
        "ocr_min_confidence": readings["6"]["min_confidence"],
        "office_name_reading": name,
        "gram_panchayat_reading": name if row["tier"].startswith("gp_") else None,
        "caste_reservation": category if category in {"SC", "ST", "BC"} else None,
        "woman_reserved": True if category == "women" else None,
        "category": category,
        "quality_flags": ";".join(flags),
        "review_status": "needs_cell_review",
        "review_note": None,
        "record_kind": "positive_office_reservation_mention"
        if category
        else "blank_or_unresolved_cell",
    }


def apply_block_headers(rows):
    path = OUT / "block_header_review.csv"
    if not path.exists():
        return rows
    with path.open() as handle:
        headers = {
            (r["source_sha256"], int(r["source_page"]), int(r["table_row"])): r
            for r in csv.DictReader(handle)
        }
    groups_by_row = {}
    for row in rows:
        key = (row["source_sha256"], row["source_page"], row["table_row"])
        groups_by_row.setdefault(key, []).append(row)
    seen, current = set(), {}
    for key, cells in groups_by_row.items():
        header = headers.get(key)
        page_key = key[:2]
        if header:
            boxes = [json.loads(c["source_bbox"]) for c in cells]
            union = [
                min(b[0] for b in boxes),
                min(b[1] for b in boxes),
                max(b[2] for b in boxes),
                max(b[3] for b in boxes),
            ]
            if len(cells) != 2 or union != json.loads(header["source_bbox"]):
                raise ValueError("Reviewed block header geometry changed")
            current[page_key] = header["verified_block"]
            seen.add(key)
        for row in cells:
            if page_key in current:
                row["block"] = current[page_key]
                row["block_review_status"] = "visually_reviewed"
            else:
                row["block_review_status"] = "source_filename_or_unreviewed"
            if header:
                row.update(
                    {
                        "heading": True,
                        "office_name_reading": None,
                        "gram_panchayat_reading": None,
                        "category": None,
                        "caste_reservation": None,
                        "woman_reserved": None,
                        "record_kind": "visually_reviewed_block_heading",
                        "review_status": "visually_reviewed_single_reader",
                    }
                )
    if set(headers) != seen:
        raise ValueError("Reviewed block header disappeared")
    return rows


def transcription_evidence(raw, file_hashes):
    try:
        references = json.loads(raw) if raw else []
    except json.JSONDecodeError as error:
        raise ValueError("Invalid transcription evidence_references JSON") from error
    if not isinstance(references, list):
        raise ValueError("Transcription evidence_references must be a JSON list")
    for reference in references:
        if (
            not isinstance(reference, dict)
            or set(reference) != {"path", "sha256"}
            or not isinstance(reference["path"], str)
            or not reference["path"]
            or not isinstance(reference["sha256"], str)
            or not re.fullmatch(r"[0-9a-f]{64}", reference["sha256"])
        ):
            raise ValueError("Invalid transcription evidence reference")
        relative = ROOT / reference["path"]
        evidence_path = relative.resolve()
        if reference["path"].startswith("/") or not evidence_path.is_relative_to(
            ROOT.resolve()
        ):
            raise ValueError("Transcription evidence path must be repository-relative")
        if evidence_path not in file_hashes:
            try:
                file_hashes[evidence_path] = hashlib.sha256(
                    evidence_path.read_bytes()
                ).hexdigest()
            except OSError as error:
                raise ValueError(
                    "Transcription evidence file cannot be read"
                ) from error
        if file_hashes[evidence_path] != reference["sha256"]:
            raise ValueError("Transcription evidence reference hash mismatch")
    return json.dumps(
        references, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )


def apply_transcriptions(rows):
    path = OUT / "source_transcriptions.csv"
    if not path.exists():
        return rows
    with path.open() as handle:
        entries = list(csv.DictReader(handle))
        curated = {r["row_id"]: r for r in entries}
    if len(curated) != len(entries):
        raise ValueError("Duplicate curated source cell")
    file_hashes, evidence_references = {}, {}
    for correction in entries:
        column = int(correction["source_column"])
        allowed = {4: {"SC", "ST", "BC", None}, 5: {"women", None}}
        if (correction["verified_category"] or None) not in allowed.get(column, set()):
            raise ValueError("Transcription category does not match source column")
        evidence_references[correction["row_id"]] = transcription_evidence(
            correction.get("evidence_references"), file_hashes
        )
    seen = set()
    for row in rows:
        correction = curated.get(row["row_id"])
        if correction is None:
            continue
        if any(
            str(row[k]) != correction[k]
            for k in ("source_sha256", "source_bbox", "source_page", "source_column")
        ):
            raise ValueError("Transcription evidence/geometry mismatch")
        seen.add(row["row_id"])
        if correction.get("name_ambiguous") == "True" and correction["verified_name"]:
            raise ValueError("Ambiguous name must not be a resolved identifier")
    if set(curated) != seen:
        raise ValueError("Curated cells disappeared from extraction")
    for row in rows:
        row.setdefault("review_method", None)
        row.setdefault("name_ambiguous", None)
        row.setdefault("candidate_name_readings", None)
        row.setdefault("evidence_references", "[]")
        correction = curated.get(row["row_id"])
        if correction is None:
            continue
        name = correction["verified_name"] or None
        category = correction["verified_category"] or None
        ambiguous = correction.get("name_ambiguous") == "True"
        row.update(
            {
                "office_name_reading": name,
                "gram_panchayat_reading": name
                if row["tier"].startswith("gp_")
                else None,
                "category": category,
                "caste_reservation": category
                if category in {"SC", "ST", "BC"}
                else None,
                "woman_reserved": True if category == "women" else None,
                "review_status": (
                    "visually_reviewed_name_unresolved"
                    if ambiguous
                    else "visually_reviewed_two_agents"
                    if correction["review_method"] == "blinded_two_visual_readers"
                    else "visually_reviewed_single_reader"
                ),
                "review_method": correction["review_method"],
                "evidence_references": evidence_references[row["row_id"]],
                "name_ambiguous": ambiguous,
                "candidate_name_readings": correction.get("candidate_name_readings")
                or None,
                "review_note": correction["review_note"],
                "record_kind": "positive_office_reservation_mention"
                if category
                else "visually_reviewed_blank_cell",
            }
        )
        if ambiguous:
            row["quality_flags"] += ";source_name_ambiguous"
    return rows


def attach_qwen_reviews(rows):
    evidence = {}
    adjudication_path = OUT / "s24_pilot_name_adjudication.json"
    adjudication = (
        json.loads(adjudication_path.read_text()) if adjudication_path.exists() else {}
    )
    for group in ("pilot", "highres", "s24_targeted/readings"):
        for path in sorted(
            (ROOT / "data/wb/derived/qwen_review" / group).glob("*.json")
        ):
            reading = json.loads(path.read_text())
            evidence[reading["source"]["row_id"]] = (path, reading)
    for row in rows:
        row.update(
            {
                "qwen_raw_reading": None,
                "qwen_review_cache": None,
                "qwen_agrees_with_current_reading": None,
                "qwen_disagreement_adjudication": None,
            }
        )
        item = evidence.get(row["row_id"])
        if item is None:
            continue
        path, evidence_row = item
        source = evidence_row["source"]
        if (
            source["source_path"] != row["source_path"]
            or source["source_bbox"] != row["source_bbox"]
        ):
            raise ValueError("Qwen source evidence mismatch")
        body = json.loads(evidence_row["response"]["response"])
        raw = body.get("text", "")
        name, category = parse_reading(raw, row["source_column"])

        def normalized(value):
            return "".join(value.upper().split()) if value else None

        agrees = (normalized(name), category) == (
            normalized(row["office_name_reading"]),
            row["category"],
        )
        row.update(
            {
                "qwen_raw_reading": raw,
                "qwen_review_cache": str(path.relative_to(ROOT)),
                "qwen_agrees_with_current_reading": agrees,
            }
        )
        if not agrees:
            confirmed = (
                adjudication.get("row_id") == row["row_id"]
                and adjudication.get("source_sha256") == row["source_sha256"]
                and adjudication.get("source_bbox") == json.loads(row["source_bbox"])
                and normalized(adjudication.get("exact_printed_name"))
                == normalized(row["office_name_reading"])
                and adjudication.get("category_explicit") == row["category"]
                and not adjudication.get("ambiguous", True)
            )
            if confirmed:
                row["qwen_disagreement_adjudication"] = str(
                    adjudication_path.relative_to(ROOT)
                )
                row["quality_flags"] += ";qwen_disagreement_source_adjudicated"
            else:
                row["quality_flags"] += ";qwen_disagreement_needs_adjudication"
    return rows


def reconcile_controls(mentions):
    path = OUT / "printed_controls.json"
    if not path.exists():
        return
    checks = []
    enumerations = []
    for name in (
        "s24_deputy_independent_audit.json",
        "s24_draft_deputy_independent_audit.json",
    ):
        audit_path = OUT / name
        if audit_path.exists():
            raw = audit_path.read_bytes()
            enumerations.append(
                (audit_path, hashlib.sha256(raw).hexdigest(), json.loads(raw))
            )
    for control in json.loads(path.read_text()):
        source = ROOT / control["source_path"]
        if hashlib.sha256(source.read_bytes()).hexdigest() != control["source_sha256"]:
            raise ValueError("Printed-control source hash changed")
        rows = [
            r
            for r in mentions
            if all(
                r[k] == control[k]
                for k in ("district", "election_year", "tier", "stage")
            )
        ]
        matching_enumeration = None
        extracted = {
            r["row_id"]: (r["office_name_reading"], r["category"]) for r in rows
        }
        for audit_path, audit_sha, enumeration in enumerations:
            if enumeration.get("source_sha256") != control["source_sha256"]:
                continue
            positive = [
                r
                for r in enumeration.get(
                    "observed_positive_cells", enumeration.get("cells", [])
                )
                if r["category_visually_read"] is not None
            ]
            observed = {
                r["row_id"]: (r["name_visually_read"], r["category_visually_read"])
                for r in positive
            }
            if (
                observed
                and len(observed) == len(positive)
                and len(extracted) == len(rows)
                and observed == extracted
                and all(r["source_sha256"] == control["source_sha256"] for r in rows)
                and all(
                    r["name_visually_read"] and not r.get("name_ambiguous", False)
                    for r in positive
                )
            ):
                matching_enumeration = (audit_path, audit_sha)
                break
        for category, expected in control["categories"].items():
            found = [r for r in rows if r["category"] == category]
            checks.append(
                {
                    k: control[k]
                    for k in (
                        "district",
                        "election_year",
                        "tier",
                        "stage",
                        "printed_office_universe",
                        "source_path",
                        "source_sha256",
                        "source_page",
                    )
                }
                | {
                    "category": category,
                    "printed_count": expected,
                    "parsed_positive_mentions": len(found),
                    "difference": len(found) - expected,
                    "visually_reviewed_mentions": sum(
                        r["review_status"].startswith("visually_reviewed")
                        for r in found
                    ),
                    "control_status": "count_agreement_not_name_verification"
                    if len(found) == expected
                    else "source_internal_mismatch_visually_enumerated"
                    if matching_enumeration
                    else "count_mismatch_requires_source_review",
                    "independent_visual_enumeration": (
                        str(matching_enumeration[0].relative_to(ROOT))
                        if matching_enumeration
                        else None
                    ),
                    "independent_visual_enumeration_sha256": (
                        matching_enumeration[1] if matching_enumeration else None
                    ),
                }
            )
    write_table(checks, OUT / "control_reconciliation")


@command("parse", state="West Bengal", source="native_office_schedules")
def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workers", type=int, default=2)
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    rows, audits = [], []
    seen = set()
    for source in select_sources():
        path = ROOT / "data/wb" / source["file"]
        sha = hashlib.sha256(path.read_bytes()).hexdigest()
        if sha in seen:
            continue
        seen.add(sha)
        directory = OUT / "ocr" / sha
        directory.mkdir(parents=True, exist_ok=True)
        with pdfplumber.open(path) as pdf:
            for number, page in enumerate(pdf.pages, 1):
                audit = {
                    "source_path": str(path.relative_to(ROOT)),
                    "source_sha256": sha,
                    "source_page": number,
                }
                try:
                    found = build_page(page, number, source, sha, directory)
                    rows.extend(found)
                    audits.append(
                        audit
                        | {
                            "cells": len(found),
                            "status": "cells_extracted_review_pending",
                            "error": None,
                        }
                    )
                except (ValueError, cv2.error) as error:
                    audits.append(
                        audit
                        | {
                            "cells": 0,
                            "status": "geometry_failure",
                            "error": str(error),
                        }
                    )
    write_table(audits, OUT / "page_audit")
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        parsed = []
        for i, row in enumerate(pool.map(read_cell, rows), 1):
            parsed.append(row)
            if i % 100 == 0:
                print(f"{i}/{len(rows)} cells", flush=True)
    parsed = apply_block_headers(parsed)
    parsed = apply_transcriptions(parsed)
    parsed = attach_qwen_reviews(parsed)
    mentions = [r for r in parsed if r["category"] and r["office_name_reading"]]
    write_table(parsed, OUT / "cell_review")
    write_table(mentions, OUT / "mentions")
    reconcile_controls(mentions)
    pending = sum(row["review_status"] == "needs_cell_review" for row in parsed)
    print(
        f"{len(mentions)} positive mentions; {len(audits)} pages; "
        f"{pending} cells marked needs_cell_review"
    )


if __name__ == "__main__":
    main()
