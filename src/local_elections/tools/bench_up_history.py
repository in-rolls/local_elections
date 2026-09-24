"""Score category-cell OCR on the labelled Lucknow history-page pilot.

This is a diagnosis benchmark, not an election-data parser. The labels were
transcribed from source page 1 before running cell OCR. It makes no accuracy
claim for unreviewed pages, place names, or the final 2021 reservation order.
"""

import argparse
import csv
import json
import os
import subprocess
import tempfile
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import cv2
import numpy as np

from local_elections.common.runlog import command
from local_elections.paths import ROOT
from local_elections.states.wb.parse_office_scans import (
    grid_masks,
    groups,
    rectify,
)
from local_elections.tools.historical_harvest import checksum

BASE = ROOT / "data/source_search/national/uttar_pradesh"
SOURCE = BASE / "raw/lucknow_81306919.pdf"
SOURCE_SHA256 = "b735f5235f85ed863bd49bda09ed93c78719a759fe1237791c441ab5cd71e50d"
LABELS = BASE / "pilot/labels.csv"
CODES = {"UR", "SC", "SCL", "BC", "BCL", "L"}
YEARS = [1995, 2000, 2005, 2010, 2015, 2021]


def category(raw):
    token = "".join(raw.upper().split())
    return token if token in CODES else None


def score(readings):
    printed = [r for r in readings if r["printed_category"] in CODES]
    missing = [r for r in readings if r["printed_category"] == "-"]
    return {
        "cells": len(readings),
        "printed_categories": len(printed),
        "correct_printed_categories": sum(
            r["recognized_category"] == r["printed_category"] for r in printed
        ),
        "wrong_printed_categories": sum(
            r["recognized_category"] not in {None, r["printed_category"]}
            for r in printed
        ),
        "abstained_printed_categories": sum(
            r["recognized_category"] is None for r in printed
        ),
        "printed_missing": len(missing),
        "false_categories_on_missing": sum(
            r["recognized_category"] is not None for r in missing
        ),
        "errors_by_printed_category": dict(
            Counter(
                r["printed_category"]
                for r in printed
                if r["recognized_category"] != r["printed_category"]
            )
        ),
    }


@command("benchmark", state="Uttar Pradesh", source="Lucknow history pilot")
def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=BASE / "pilot")
    args = parser.parse_args()
    if checksum(SOURCE) != SOURCE_SHA256:
        raise ValueError("Lucknow source differs from the labelled PDF")
    with LABELS.open() as stream:
        labels = list(csv.DictReader(stream))
    expected = {(str(row), str(year)) for row in range(1, 19) for year in YEARS}
    if (
        len(labels) != 108
        or {(r["printed_row"], r["year"]) for r in labels} != expected
        or any(r["source_page"] != "1" or r["split"] != "diagnose" for r in labels)
    ):
        raise ValueError("Expected the labelled 18-row page-1 diagnosis grid")
    args.out.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="up-history-") as temporary:
        prefix = Path(temporary) / "page"
        subprocess.run(
            [
                "pdftoppm",
                "-f",
                "1",
                "-singlefile",
                "-r",
                "300",
                "-gray",
                "-png",
                str(SOURCE),
                str(prefix),
            ],
            check=True,
            capture_output=True,
        )
        gray = cv2.imread(str(prefix.with_suffix(".png")), cv2.IMREAD_GRAYSCALE)
        table, transform = rectify(gray)
        horizontal, vertical = grid_masks(table)
        xs = groups(np.flatnonzero((vertical > 0).sum(axis=0) > table.shape[0] * 0.5))
        ys = groups(np.flatnonzero((horizontal > 0).sum(axis=1) > table.shape[1] * 0.6))
        if len(xs) != 15 or len(ys) != 21:
            raise ValueError(
                f"Unexpected pilot grid: {len(xs)} columns, {len(ys)} rules"
            )
        data_ys = ys[-20:]

        def read_cell(job):
            label, psm = job
            row = int(label["printed_row"]) - 1
            column = 8 + YEARS.index(int(label["year"]))
            left, right = xs[column] + 5, xs[column + 1] - 5
            top, bottom = data_ys[row] + 5, data_ys[row + 1] - 5
            crop = cv2.copyMakeBorder(
                table[top:bottom, left:right],
                10,
                10,
                10,
                10,
                cv2.BORDER_CONSTANT,
                value=255,
            )
            encoded = cv2.imencode(".png", crop)[1].tobytes()
            result = subprocess.run(
                [
                    "tesseract",
                    "stdin",
                    "stdout",
                    "-l",
                    "eng",
                    "--psm",
                    str(psm),
                    "-c",
                    "tessedit_char_whitelist=URSCBL-.",
                    "-c",
                    "load_system_dawg=0",
                    "-c",
                    "load_freq_dawg=0",
                ],
                input=encoded,
                capture_output=True,
                check=True,
                env=os.environ | {"OMP_THREAD_LIMIT": "1"},
            )
            raw = result.stdout.decode().strip()
            return label | {
                "psm": psm,
                "table_bbox": json.dumps([left, top, right, bottom]),
                "ocr_raw": raw,
                "recognized_category": category(raw),
                "stderr": result.stderr.decode(),
            }

        with ThreadPoolExecutor(max_workers=4) as executor:
            readings = list(
                executor.map(read_cell, [(r, psm) for psm in (7, 8) for r in labels])
            )
    with (args.out / "readings.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(readings[0]))
        writer.writeheader()
        writer.writerows(readings)
    report = {
        "scope": "One diagnosis page; no held-out validation or name extraction",
        "source_sha256": SOURCE_SHA256,
        "labels_sha256": checksum(LABELS),
        "benchmark_sha256": checksum(Path(__file__)),
        "geometry_sha256": checksum(
            ROOT / "src/local_elections/states/wb/parse_office_scans.py"
        ),
        "tesseract_version": subprocess.run(
            ["tesseract", "--version"], capture_output=True, text=True, check=True
        ).stdout.splitlines()[0],
        "render_dpi": 300,
        "transform": transform.tolist(),
        "grid_x": xs,
        "grid_y": ys,
        "scores": {
            str(psm): score([r for r in readings if r["psm"] == psm]) for psm in (7, 8)
        },
    }
    (args.out / "benchmark.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report["scores"]))


if __name__ == "__main__":
    main()
