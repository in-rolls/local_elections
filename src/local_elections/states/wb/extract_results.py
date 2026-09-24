"""Cache image-based cells for every page of Alipurduar's 2018 results.

The embedded OCR is corrupt on the pilot source. Render the original, detect
its ruling, and retain cell geometry plus three Tesseract readings. This module
extracts evidence; parse_results decides which cells form election records.
"""

import argparse
import csv
import hashlib
import io
import itertools
import json
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from PIL import Image

from local_elections.common.ocr_engine import page_count
from local_elections.common.runlog import command
from local_elections.paths import ROOT

SOURCE = ROOT / "data/wb/gp_source_search/alipurduar_2018_results/extracted"
CACHE = ROOT / "data/wb/derived/alipurduar_2018/ocr"
VERSION = 3


def groups(values, gap=8):
    clustered = []
    for value in values:
        value = int(value)
        if not clustered or value - clustered[-1][-1] > gap:
            clustered.append([value])
        else:
            clustered[-1].append(value)
    return [round(sum(items) / len(items)) for items in clustered]


def deskew(gray):
    import cv2
    import numpy as np

    binary = cv2.threshold(gray, 190, 255, cv2.THRESH_BINARY_INV)[1]
    lines = cv2.HoughLinesP(
        binary, 1, np.pi / 1800, 150, minLineLength=gray.shape[1] // 5, maxLineGap=30
    )
    angles = []
    if lines is not None:
        for x1, y1, x2, y2 in lines.reshape(-1, 4):
            angle = float(np.degrees(np.arctan2(y2 - y1, x2 - x1)))
            if abs(angle) < 5:
                angles.append(angle)
    angle = float(np.median(angles)) if angles else 0.0
    if abs(angle) < 0.05:
        return gray, 0.0
    matrix = cv2.getRotationMatrix2D((gray.shape[1] / 2, gray.shape[0] / 2), angle, 1)
    return cv2.warpAffine(
        gray, matrix, (gray.shape[1], gray.shape[0]), borderValue=255
    ), angle


def ruling(gray):
    import cv2
    import numpy as np

    binary = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY_INV, 51, 10
    )
    horizontal = cv2.morphologyEx(binary, cv2.MORPH_OPEN, np.ones((1, 60), np.uint8))
    vertical = cv2.morphologyEx(binary, cv2.MORPH_OPEN, np.ones((60, 1), np.uint8))
    contours, _ = cv2.findContours(
        cv2.dilate(horizontal | vertical, np.ones((5, 5), np.uint8)),
        cv2.RETR_EXTERNAL,
        cv2.CHAIN_APPROX_SIMPLE,
    )
    choices = []
    for contour in contours:
        x, y, width, height = cv2.boundingRect(contour)
        if width < gray.shape[1] * 0.35 or height < 150:
            continue
        xs = groups(
            np.where((vertical[y : y + height] > 0).sum(axis=0) > height * 0.25)[0]
        )
        xs = [v for v in xs if x <= v <= x + width]
        if len(xs) >= 5:
            choices.append((width * height, x, y, width, height, xs))
    if not choices:
        return [], [], gray
    _, _, y, _, height, xs = max(choices)
    long_rows = groups(np.where((horizontal > 0).sum(axis=1) > gray.shape[1] * 0.5)[0])
    if len(long_rows) >= 3:
        # A scanner frame can join the table contour and inflate its height.
        # Measure vertical support only over the ruled table itself, allowing
        # slight horizontal drift in scanned vertical rules.
        y, bottom = min(long_rows), max(long_rows)
        height = bottom - y + 1
        supported = cv2.dilate(vertical[y : y + height], np.ones((1, 11), np.uint8))
        xs = groups(np.where((supported > 0).sum(axis=0) > height * 0.25)[0])
    columns = []
    for left, right in itertools.pairwise(xs):
        inner = horizontal[y : y + height, left + 8 : right - 8] > 0
        ys = groups(np.where(inner.sum(axis=1) > inner.shape[1] * 0.55)[0] + y)
        columns.append(ys)
    clean = gray.copy()
    clean[cv2.dilate(horizontal | vertical, np.ones((3, 3), np.uint8)) > 0] = 255
    return xs, columns, clean


def read_words(image, psm, tsv_path=None):
    result = subprocess.run(
        ["tesseract", str(image), "stdout", "-l", "eng", "--psm", str(psm), "tsv"],
        check=True,
        capture_output=True,
        text=True,
        timeout=180,
    )
    if tsv_path is not None:
        tsv_path.parent.mkdir(parents=True, exist_ok=True)
        tsv_path.write_text(result.stdout)
    words = []
    for row in csv.DictReader(
        io.StringIO(result.stdout), delimiter="\t", quoting=csv.QUOTE_NONE
    ):
        if row["level"] != "5" or not row["text"].strip():
            continue
        words.append(
            {
                "text": row["text"],
                "x": int(row["left"]) + int(row["width"]) / 2,
                "y": int(row["top"]) + int(row["height"]) / 2,
                "confidence": float(row["conf"]),
            }
        )
    return words


def repair_tsv(cache_path):
    """Re-read only corrupt word streams using the existing image geometry."""
    import cv2

    record = json.loads(cache_path.read_text())
    damaged = [
        field
        for field in ["words_original", "words_clean", "words_column"]
        if any("\t" in word["text"] for word in record[field])
    ]
    if not damaged:
        return record
    evidence = CACHE / "tsv_reader_repair" / cache_path.stem
    evidence.mkdir(parents=True, exist_ok=True)
    backup = evidence / "before.json"
    if not backup.exists():
        backup.write_bytes(cache_path.read_bytes())
    source = ROOT / record["source_path"]
    if hashlib.sha256(source.read_bytes()).hexdigest() != record["source_sha256"]:
        raise ValueError("Source changed before targeted TSV repair")
    with tempfile.TemporaryDirectory() as scratch_dir:
        scratch = Path(scratch_dir)
        rendered = scratch / "page.png"
        subprocess.run(
            [
                "pdftoppm",
                "-r",
                str(record["dpi"]),
                "-f",
                str(record["source_page"]),
                "-singlefile",
                "-png",
                str(source),
                str(rendered.with_suffix("")),
            ],
            check=True,
            capture_output=True,
            timeout=120,
        )
        with Image.open(rendered) as original:
            original.rotate(-record["rotation_clockwise"], expand=True).save(rendered)
        gray = cv2.imread(str(rendered), cv2.IMREAD_GRAYSCALE)
        angle = record["deskew_degrees"]
        if angle:
            matrix = cv2.getRotationMatrix2D(
                (gray.shape[1] / 2, gray.shape[0] / 2), angle, 1
            )
            gray = cv2.warpAffine(
                gray, matrix, (gray.shape[1], gray.shape[0]), borderValue=255
            )
        if gray.shape != (record["height"], record["width"]):
            raise ValueError("Stored OCR coordinate dimensions changed")
        Image.fromarray(gray).save(rendered, dpi=(record["dpi"], record["dpi"]))
        if "words_original" in damaged:
            record["words_original"] = read_words(
                rendered, 4, evidence / "original.tsv"
            )
        if any(field in damaged for field in ["words_clean", "words_column"]):
            _, _, clean = ruling(gray)
            cleaned = scratch / "clean.png"
            Image.fromarray(clean).save(cleaned, dpi=(record["dpi"], record["dpi"]))
            if "words_clean" in damaged:
                record["words_clean"] = read_words(cleaned, 6, evidence / "clean.tsv")
            if "words_column" in damaged:
                damaged_columns = {
                    column
                    for word in record["words_column"]
                    if "\t" in word["text"]
                    for column, (left, right) in enumerate(
                        itertools.pairwise(record["x_edges"])
                    )
                    if left < word["x"] < right
                }
                for column in damaged_columns:
                    left, right = record["x_edges"][column : column + 2]
                    top, bottom = (
                        min(record["column_y_edges"][column]),
                        max(record["column_y_edges"][column]),
                    )
                    cropped = scratch / f"column{column}.png"
                    Image.fromarray(clean).crop(
                        (left + 5, top + 5, right - 5, bottom - 5)
                    ).save(cropped, dpi=(record["dpi"], record["dpi"]))
                    words = read_words(cropped, 6, evidence / f"column{column}.tsv")
                    for word in words:
                        word["x"] += left + 5
                        word["y"] += top + 5
                    record["words_column"] = [
                        word
                        for word in record["words_column"]
                        if not left < word["x"] < right
                    ] + words
        for cell in record["cells"]:
            for field, value_key, confidence_key in [
                ("words_original", "original", "original_confidence"),
                ("words_clean", "clean", "clean_confidence"),
                ("words_column", "column_text", "column_confidence"),
            ]:
                if field in damaged:
                    cell[value_key], cell[confidence_key] = cell_text(
                        record[field], cell["bbox"]
                    )
    record["tsv_reader_repair"] = {
        "reader_version": 2,
        "repaired_streams": damaged,
        "prior_cache_sha256": hashlib.sha256(backup.read_bytes()).hexdigest(),
        "evidence_directory": str(evidence.relative_to(ROOT)),
        "geometry_policy": "preserve_prior_rotation_deskew_grid_and_unaffected_streams",
    }
    if any("\t" in word["text"] for field in damaged for word in record[field]):
        raise ValueError("Embedded TSV still present after repair")
    cache_path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n")
    return record


def cell_text(words, box):
    left, top, right, bottom = box
    selected = [w for w in words if left < w["x"] < right and top < w["y"] < bottom]
    lines = []
    for word in sorted(selected, key=lambda w: (w["y"], w["x"])):
        if not lines or abs(word["y"] - lines[-1][0]["y"]) > 14:
            lines.append([word])
        else:
            lines[-1].append(word)
    text = "\n".join(
        " ".join(w["text"] for w in sorted(line, key=lambda w: w["x"]))
        for line in lines
    )
    confidence = min((w["confidence"] for w in selected), default=None)
    return text, confidence


def extract(path, number, dpi=300, force=False):
    import cv2

    relative = path.relative_to(SOURCE)
    digest = hashlib.sha256(str(relative).encode()).hexdigest()[:12]
    out = CACHE / f"{digest}_{number:03d}.json"
    source_hash = hashlib.sha256(path.read_bytes()).hexdigest()
    if out.exists() and not force:
        prior = json.loads(out.read_text())
        if (prior["version"], prior["source_sha256"], prior["dpi"]) == (
            VERSION,
            source_hash,
            dpi,
        ):
            return prior
    record = {
        "version": VERSION,
        "grid_revision": 2,
        "tsv_quoting": "none",
        "source_path": str(path.relative_to(ROOT)),
        "source_sha256": source_hash,
        "source_page": number,
        "dpi": dpi,
        "engine": subprocess.check_output(
            ["tesseract", "--version"], text=True
        ).splitlines()[0],
    }
    with tempfile.TemporaryDirectory() as scratch:
        scratch = Path(scratch).resolve()
        image = scratch / "page.png"
        subprocess.run(
            [
                "pdftoppm",
                "-r",
                str(dpi),
                "-f",
                str(number),
                "-singlefile",
                "-png",
                str(path),
                str(image.with_suffix("")),
            ],
            check=True,
            capture_output=True,
            timeout=120,
        )
        osd = subprocess.run(
            ["tesseract", str(image), "stdout", "--psm", "0"],
            capture_output=True,
            text=True,
            timeout=120,
        ).stdout
        suggested = 0
        for line in osd.splitlines():
            if line.startswith("Rotate:"):
                suggested = int(line.split(":")[1])
        keywords = {
            "ANNEXURE",
            "PANCHAYAT",
            "ELECTION",
            "RESULTS",
            "GRAM",
            "BJP",
            "AITC",
            "IND",
            "VOTES",
        }
        options = []
        with Image.open(image) as original:
            for turn in dict.fromkeys([0, suggested]):
                trial = scratch / f"turn{turn}.png"
                original.rotate(-turn, expand=True).save(trial, dpi=(dpi, dpi))
                words = read_words(trial, 4)
                score = sum(w["text"].upper().strip(".,|") in keywords for w in words)
                options.append((score, turn, words, trial))
            if max(item[0] for item in options) < 3:
                for turn in {90, 180, 270} - {item[1] for item in options}:
                    trial = scratch / f"turn{turn}.png"
                    original.rotate(-turn, expand=True).save(trial, dpi=(dpi, dpi))
                    words = read_words(trial, 4)
                    score = sum(
                        w["text"].upper().strip(".,|") in keywords for w in words
                    )
                    options.append((score, turn, words, trial))
        score, turn, original_words, image = max(options, key=lambda item: item[0])
        record.update(rotation_clockwise=turn, orientation_score=score, osd=osd)
        gray = cv2.imread(str(image), cv2.IMREAD_GRAYSCALE)
        gray, angle = deskew(gray)
        record["deskew_degrees"] = angle
        if angle:
            image = scratch / "deskew.png"
            Image.fromarray(gray).save(image, dpi=(dpi, dpi))
            original_words = read_words(image, 4)
        xs, columns, clean = ruling(gray)
        clean_path = scratch / "clean.png"
        Image.fromarray(clean).save(clean_path, dpi=(dpi, dpi))
        clean_words = read_words(clean_path, 6)
        record.update(
            width=gray.shape[1],
            height=gray.shape[0],
            x_edges=xs,
            column_y_edges=columns,
            words_original=original_words,
            words_clean=clean_words,
        )
        column_words = []
        if columns:
            for column, (left, right) in enumerate(itertools.pairwise(xs)):
                ys = columns[column]
                if len(ys) < 2 or max(ys) - min(ys) <= 10 or right - left <= 10:
                    continue
                top, bottom = min(ys), max(ys)
                crop = Image.fromarray(clean).crop(
                    (left + 5, top + 5, right - 5, bottom - 5)
                )
                crop_path = scratch / f"column{column}.png"
                crop.save(crop_path, dpi=(dpi, dpi))
                for word in read_words(crop_path, 6):
                    word["x"] += left + 5
                    word["y"] += top + 5
                    column_words.append(word)
        record["words_column"] = column_words
        cells = []
        for column, ys in enumerate(columns):
            for top, bottom in itertools.pairwise(ys):
                box = [xs[column], top, xs[column + 1], bottom]
                first, first_conf = cell_text(original_words, box)
                second, second_conf = cell_text(clean_words, box)
                third, third_conf = cell_text(column_words, box)
                cells.append(
                    {
                        "column": column,
                        "bbox": box,
                        "original": first,
                        "clean": second,
                        "original_confidence": first_conf,
                        "clean_confidence": second_conf,
                        "column_text": third,
                        "column_confidence": third_conf,
                    }
                )
        record["cells"] = cells
        record["status"] = "extracted" if cells else "grid_unresolved"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n")
    return record


@command("extract", state="West Bengal", method="tesseract_grid")
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--match", default="")
    ap.add_argument("--pages", help="comma-separated one-based page numbers")
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--repair-layouts", action="store_true")
    ap.add_argument("--repair-tsv", action="store_true")
    args = ap.parse_args()
    if args.repair_tsv:
        selected = []
        for path in sorted(CACHE.glob("*.json")):
            record = json.loads(path.read_text())
            if args.match not in record["source_path"]:
                continue
            if args.pages and record["source_page"] not in {
                int(page) for page in args.pages.split(",")
            }:
                continue
            selected.append(path)
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            for record in pool.map(repair_tsv, selected):
                if "tsv_reader_repair" in record:
                    print(
                        f"TSV repaired {Path(record['source_path']).name} "
                        f"p{record['source_page']}",
                        flush=True,
                    )
        return
    jobs = []
    for path in sorted(SOURCE.rglob("*")):
        if path.suffix.lower() != ".pdf" or args.match not in str(path):
            continue
        numbers = (
            [int(p) for p in args.pages.split(",")]
            if args.pages
            else range(1, page_count(path) + 1)
        )
        for number in numbers:
            if args.repair_layouts:
                from local_elections.states.wb.parse_results import parse_page

                prior = extract(path, number)
                if parse_page(prior)[2]["status"] not in {
                    "gp_layout_unresolved",
                    "gp_rows_unresolved",
                    "grid_unresolved",
                }:
                    continue
            jobs.append((path, number))
    if not jobs:
        raise SystemExit("No source pages matched")
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        for record in pool.map(
            lambda job: extract(*job, force=args.force or args.repair_layouts), jobs
        ):
            print(
                f"{record['status']} {Path(record['source_path']).name} "
                f"p{record['source_page']} columns={len(record['x_edges']) - 1}",
                flush=True,
            )


if __name__ == "__main__":
    main()
