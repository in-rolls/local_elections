"""OCR the named columns of two scanned Pradhan Form 1B orders.

    uv run python -m local_elections.states.wb.pradhan_scans

Nadia 2018 (order 95/PGE'18) and Malda 2013 (order 334/P/PGE'13) are image-only
scans. Whole-page OCR is unusable because of the ruled grid, so each page's
table is rectified, its column rules located, and every cell in the named
columns read on its own - the approach of parse_office_scans, whose grid
helpers this reuses. That module hard-codes the page geometry of the documents
it already reads; these two differ (Malda prints every GP in its own column),
so they are described here instead.

The readings are the evidence and are tracked in scan_cells.csv. The renders
and crops are reproducible from the committed PDFs and are not. Nothing here
decides what a reading means; pradhan_gp.py does that and checks the result
against the totals printed in each order.
"""

import argparse
import csv
import hashlib
import itertools
import subprocess
import sys
import tempfile
from pathlib import Path

import cv2
import numpy as np

from local_elections.common.runlog import command
from local_elections.paths import ROOT
from local_elections.states.wb.parse_office_scans import grid_masks, groups, rectify

SOURCES = ROOT / "data" / "wb" / "gp_source_search" / "historical_expansion"
OUT = ROOT / "data" / "wb" / "derived" / "pradhan_gp"
CELLS = OUT / "scan_cells.csv"

# Column positions are fractions of the rectified table width, measured on
# these pages; `named` maps each read column to its left and right rule.
DOCUMENTS = [
    {
        "district": "Nadia",
        "term": 2018,
        "file": "nadia_FORM_1B_Prodhan_Upa-Prodhan-06032018_29b77844.pdf",
        "sha256": "29b7784487ef",
        "pages": range(1, 7),  # 7-12 are the Upa-Pradhan order
        "rotate": cv2.ROTATE_90_COUNTERCLOCKWISE,
        "scale": 2.0,
        "named": {"caste": (0.566, 0.797), "women": (0.797, 0.998)},
        "rows_from": ("caste", "women", 0.3),
        "row_gap": 12,
        "min_row": 25,
        "margin": (4, 3, 5, 4),
        "cell_scale": 1.0,
    },
    {
        "district": "Malda",
        "term": 2013,
        "file": "malda_Office_Bearer_of_ZP_PS_GP_d4c3b045.pdf",
        "sha256": "d4c3b045a2c1",
        "pages": range(7, 11),  # Pradhan P-1/4 to P-4/4
        "rotate": None,
        "scale": 1.5,
        "named": {
            "all": (0.099, 0.249),
            "caste": (0.660, 0.828),
            "women": (0.828, 0.998),
        },
        "rows_from": ("all", "all", 0.5),
        "row_gap": 6,
        "min_row": 18,
        "margin": (3, 2, 4, 3),
        "cell_scale": 1.5,
    },
]

FIELDS = ["district", "term", "source_file", "page", "row", "y0", "y1", "column"]
FIELDS += ["reading"]


def page_image(pdf, page, directory):
    """The page's embedded scan at its native resolution."""
    subprocess.run(
        ["pdfimages", "-png", "-f", str(page), "-l", str(page), str(pdf), "img"],
        cwd=directory,
        check=True,
    )
    (image,) = sorted(Path(directory).glob("img-*.png"))
    gray = cv2.imread(str(image), cv2.IMREAD_GRAYSCALE)
    image.unlink()
    return gray


def ocr(path):
    return subprocess.run(
        ["tesseract", str(path), "stdout", "--psm", "7"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


def read_page(document, page, workdir):
    gray = page_image(SOURCES / document["file"], page, workdir)
    if document["rotate"] is not None:
        gray = cv2.rotate(gray, document["rotate"])
    scale = document["scale"]
    gray = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    table, _ = rectify(gray)
    height, width = table.shape
    horizontal, vertical = grid_masks(table)
    xs = groups(np.flatnonzero((vertical > 0).sum(axis=0) > height * 0.15))

    def rule(fraction):
        found = min(xs, key=lambda x: abs(x / width - fraction))
        if abs(found / width - fraction) > 0.03:
            raise ValueError(f"page {page}: no column rule near {fraction}")
        return found

    columns = {k: (rule(a), rule(b)) for k, (a, b) in document["named"].items()}
    # a row rule must cross this share of the named columns it is read from
    first, last, share = document["rows_from"]
    left, right = columns[first][0], columns[last][1]
    ys = groups(
        np.flatnonzero(
            (horizontal[:, left:right] > 0).sum(axis=1) > (right - left) * share
        ),
        gap=document["row_gap"],
    )
    top, bottom, inner_left, inner_right = document["margin"]
    clean = table.copy()
    clean[cv2.dilate(horizontal | vertical, np.ones((3, 3), np.uint8)) > 0] = 255
    _, clean = cv2.threshold(clean, 170, 255, cv2.THRESH_BINARY)
    rows = []
    for number, (y0, y1) in enumerate(itertools.pairwise(ys), 1):
        if y1 - y0 < document["min_row"]:
            continue
        for column, (x0, x1) in columns.items():
            crop = cv2.copyMakeBorder(
                clean[y0 + top : y1 - bottom, x0 + inner_left : x1 - inner_right],
                12,
                12,
                12,
                12,
                cv2.BORDER_CONSTANT,
                value=255,
            )
            if document["cell_scale"] != 1.0:
                crop = cv2.resize(
                    crop,
                    None,
                    fx=document["cell_scale"],
                    fy=document["cell_scale"],
                    interpolation=cv2.INTER_CUBIC,
                )
            path = Path(workdir) / "cell.png"
            cv2.imwrite(str(path), crop)
            rows.append(
                {
                    "district": document["district"],
                    "term": document["term"],
                    "source_file": document["file"],
                    "page": page,
                    "row": number,
                    "y0": int(y0),
                    "y1": int(y1),
                    "column": column,
                    "reading": ocr(path),
                }
            )
    return rows


@command("parse", source="wb_pradhan_scans")
def main():
    argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0]).parse_args()
    rows = []
    with tempfile.TemporaryDirectory() as workdir:
        for document in DOCUMENTS:
            pdf = SOURCES / document["file"]
            digest = hashlib.sha256(pdf.read_bytes()).hexdigest()
            if not digest.startswith(document["sha256"]):
                raise ValueError(f"{pdf} is not the acquired source")
            for page in document["pages"]:
                rows.extend(read_page(document, page, workdir))
            print(f"  {document['district']} {document['term']}: read", flush=True)
    OUT.mkdir(parents=True, exist_ok=True)
    with CELLS.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    version = subprocess.run(
        ["tesseract", "--version"], capture_output=True, text=True
    ).stdout.split("\n")[0]
    print(f"{len(rows)} cells ({version}) -> {CELLS.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
