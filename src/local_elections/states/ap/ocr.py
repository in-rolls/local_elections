"""Re-OCR the Andhra Pradesh gazettes, because their embedded text layer is bad.

These PDFs already carry a text layer, but it is itself OCR output and it is
wrong in ways that matter: `5C` for SC, `8c` for BC, `t4` for 14, `72` for 12.
Parsing it means repairing those by hand and hoping the repairs are right.

Re-rendering the page and running Tesseract at `--psm 4` (one column of text of
variable sizes, which is what a wide ruled table is) fixes them at the source:

    embedded   44 Alamuru ALAMURU sc(w) t4 Bc (w) UR (W) SC sc (w) BC ...
    re-OCR     44 Alamuru ALAMURU SC(W) 14 BC(W)  UR(W)  SC sc(w)  BC ...

`--psm 6` is much worse here - it reads the table rules as pipe characters and
garbles the row - so the mode matters more than the engine.

This also unlocks Anantapur, whose PDF has no text layer at all.

Output is cached as data/ap/ocr/<stem>.txt with a form feed between pages, so it
drops straight into the same page-splitting the parser already does, and a
re-parse costs nothing.
"""

import argparse
import csv
import io
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile

from local_elections.common.ocr_engine import page_count
from local_elections.common.runlog import command, get_logger
from local_elections.paths import ROOT

LOGGER = get_logger(__name__)

SOURCE = ROOT / "data" / "ap" / "2020_res_gp"
CACHE = ROOT / "data" / "ap" / "ocr"

DPI = 300
PSM = "4"

# The second pass, and the reason for it.
#
# psm 4 keeps the layout, which the parser reads positionally, and pays for it
# by gluing the table's rules onto the cells: the gender marker comes back as
# "IBC)", "|URW)", "[URW", "JURG)" - the opening bracket read as I, |, [ or J -
# and where the whole marker is lost the parser sees a bare "UR" and cannot
# tell an open seat from one whose marker did not survive. 1,754 ward rows sit
# in that state, and they are not lost at random: Nellore, Prakasam and
# Anantapur mark both the women's and the open seats, so a bare code there is
# unknown rather than male, and a women's share computed over them is biased
# rather than merely noisy.
#
# psm 11 - sparse text, no particular order - reads the same page far more
# cleanly: 229 markers against 62 unreadable ones on the page this was measured
# on. It cannot replace psm 4 because it destroys the layout. So it is used as
# a second opinion, matched back by position.
REPAIR_PSM = "11"

# How close two boxes' centres must be to be the same cell, in pixels at DPI.
# Measured rather than guessed: at 25 the match was unambiguous on every one of
# the 62 candidates - 44 matched exactly one clean token and 18 matched none.
# Nothing matched two, which is the property that makes this safe. A cell that
# finds no clean reading keeps its bare code and stays flagged.
REPAIR_TOLERANCE = 25


CODE = re.compile(r"(UR|SC|ST|BC)", re.I)
MARKED = re.compile(r"(UR|SC|ST|BC)\s*[\(\[{iI|J]\s*([WG])", re.I)


def tokens(image, psm):
    """(left, top, width, height, text) for every word tesseract is sure of."""
    out = subprocess.run(
        ["tesseract", str(image), "-", "--psm", psm, "tsv"],
        capture_output=True,
        text=True,
        errors="replace",
    ).stdout
    found = []
    for row in csv.DictReader(io.StringIO(out), delimiter="\t", quoting=csv.QUOTE_NONE):
        text = (row.get("text") or "").strip()
        conf = row.get("conf") or "-1"
        if text and float(conf) > 0:
            found.append(
                (
                    int(row["left"]),
                    int(row["top"]),
                    int(row["width"]),
                    int(row["height"]),
                    text,
                )
            )
    return found


def repairs(image):
    """{bad token -> clean token} for this page, from the second pass.

    Only where exactly one clean reading sits in the same place. Two candidates
    means the page is ambiguous there and the cell keeps its bare code: a wrong
    marker would assert a gender the document may not state, which is worse
    than the blank it replaces.
    """
    first = [
        t for t in tokens(image, PSM) if CODE.search(t[4]) and not MARKED.search(t[4])
    ]
    if not first:
        return {}
    second = [t for t in tokens(image, REPAIR_PSM) if MARKED.search(t[4])]

    def center(t):
        return t[0] + t[2] / 2, t[1] + t[3] / 2

    out = {}
    for bad in first:
        bx, by = center(bad)
        near = [
            t
            for t in second
            if abs(center(t)[0] - bx) < REPAIR_TOLERANCE
            and abs(center(t)[1] - by) < REPAIR_TOLERANCE
        ]
        if len(near) == 1:
            out[bad[4]] = near[0][4]
    return out


def apply_repairs(text, table):
    """Substitute whole tokens, **without moving anything**.

    Two traps here, and the second one cost a re-run.

    A plain str.replace is not positional: "sc)" would rewrite every occurrence
    on the page including cells the second pass never looked at. So the match
    is bounded on whitespace and on the pipe characters the table rules leave
    behind.

    And the parser reads this text *by character column* - it is a ruled grid
    of twenty ward cells and the column is the ward number. A replacement that
    is longer than what it replaces shifts every cell after it on that line.
    "[URW" -> "UR(W)" is one character wider and "sc)" -> "SC(W)" is two, and
    the first version of this quietly cost Alurupadu three of its eight wards
    while every aggregate - markers found, women's share - moved the right way.
    So a longer repair eats the spaces that follow it, and one that cannot
    (because there is no room) is skipped rather than allowed to shift the row.
    """
    for bad, good in table.items():
        pattern = rf"(?<![^\s|]){re.escape(bad)}( *)(?![^\s|])"

        def fit(match):
            spare = len(match.group(1))
            need = len(good) - len(bad)
            if need > spare:
                return match.group(0)  # no room; leave the cell alone
            return good + " " * (spare - need)

        text = re.sub(pattern, fit, text)
    return text


def ocr_pdf(path, dpi=DPI, psm=PSM):
    """Render each page and OCR it; returns the text, form-feed separated."""
    pages = page_count(path)
    out = []
    with tempfile.TemporaryDirectory() as tmp:
        for page in range(1, pages + 1):
            stem = pathlib.Path(tmp) / f"p{page}"
            subprocess.run(
                [
                    "pdftoppm",
                    "-f",
                    str(page),
                    "-l",
                    str(page),
                    "-r",
                    str(dpi),
                    "-png",
                    str(path),
                    str(stem),
                ],
                capture_output=True,
            )
            images = sorted(pathlib.Path(tmp).glob(f"p{page}-*.png"))
            if not images:
                out.append("")
                continue
            text = subprocess.run(
                ["tesseract", str(images[0]), "-", "--psm", psm],
                capture_output=True,
                text=True,
            ).stdout
            text = apply_repairs(text, repairs(images[0]))
            out.append(text)
            for image in images:
                image.unlink()
            LOGGER.info(
                "OCR page completed",
                extra={
                    "event": "ocr_page_completed",
                    "source_file": path.name,
                    "page": page,
                    "pages": pages,
                },
            )
    return "\f".join(out)


@command("extract", state="Andhra Pradesh", method="ocr")
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh", action="store_true", help="re-OCR cached files")
    ap.add_argument("--only", help="substring of a filename to limit to")
    args = ap.parse_args()

    if not shutil.which("tesseract"):
        sys.exit("tesseract not found - brew install tesseract")

    CACHE.mkdir(parents=True, exist_ok=True)
    for path in sorted(SOURCE.glob("*.pdf")):
        if args.only and args.only not in path.name:
            continue
        target = CACHE / f"{path.stem}.txt"
        if target.exists() and not args.refresh:
            print(f"  {path.name:18s} cached ({target.stat().st_size // 1024} KB)")
            continue
        text = ocr_pdf(path)
        target.write_text(text, encoding="utf-8")
        print(
            f"  {path.name:18s} -> {target.name} "
            f"({len(text.split(chr(12)))} pages, {len(text) // 1024} KB)"
        )


if __name__ == "__main__":
    main()
