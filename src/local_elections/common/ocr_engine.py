"""Surya, driven the same way for every state that needs it.

Imported by scripts/<state>/ocr.py. Only the paths and the "does this document
need OCR at all" test are per-state; the rendering, the rotation and the model
are not, and were on their way to being copied a second time.

**Runs in its own uv dependency group.** The model stack is Apple-Silicon-only
and unnecessary for parser-only work, so the OCR environment contains only
what the model needs.

Named `ocr_engine` and not `surya`: this directory goes on sys.path[0], and a
module called `surya` here would shadow the real surya package for savitr.
"""

import json
import logging
import pathlib
import re
import subprocess
import sys
import tempfile

from PIL import Image

LOGGER = logging.getLogger(__name__)

# 200, not the 300 tesseract wanted: Surya's own preprocessing resizes to its
# input resolution, so the extra pixels cost render time and buy nothing.
DPI = 200

# Base Surya, converted to MLX once. NOT savitr's default terse model, which is
# distilled to emit voter rows from electoral rolls and would do exactly that
# to a reservation gazette.
DEFAULT_MODEL = pathlib.Path.home() / "Documents/GitHub/savitr/models/surya-mlx-4bit"

_ENGINE = None


def page_count(path):
    out = subprocess.run(["pdfinfo", str(path)], capture_output=True, text=True).stdout
    for line in out.split("\n"):
        if line.startswith("Pages:"):
            return int(line.split()[1])
    return 0


def rotation(image):
    """How far the page is turned, from Tesseract's own orientation pass.

    Jharkhand's Godda blocks are printed sideways - the content is perfectly
    legible and OCR returned pure noise, because nothing had turned the page
    the right way up. Confidence is checked because the same call returns 1.03
    on a page that is merely a little skewed, and acting on that would rotate a
    good page into a bad one.
    """
    out = subprocess.run(
        ["tesseract", str(image), "stdout", "--psm", "0"],
        capture_output=True,
        text=True,
        errors="replace",
        timeout=300,
    ).stdout
    degrees = confidence = 0.0
    for line in out.split("\n"):
        if line.startswith("Rotate:"):
            degrees = float(line.split(":")[1])
        elif line.startswith("Orientation confidence:"):
            confidence = float(line.split(":")[1])
    return degrees if confidence >= 2.0 else 0.0


def engine(model=None):
    """The Surya model, loaded once. Importing savitr costs seconds and loading
    the weights costs more, so a per-page load would dominate a 600-page run.
    """
    global _ENGINE
    if _ENGINE is None:
        model = pathlib.Path(model or DEFAULT_MODEL)
        try:
            from savitr import MLXSuryaOCR  # pyright: ignore[reportMissingImports]
        except ImportError:
            sys.exit(
                "savitr is not importable. Run this through "
                "`uv run --no-default-groups --group ocr python`."
            )
        if not model.exists():
            sys.exit(
                f"no Surya model at {model}. Convert it once with:\n"
                f"  python -m mlx_vlm convert --hf-path "
                f"datalab-to/surya-ocr-2 --mlx-path {model} -q --q-bits 4"
            )
        _ENGINE = MLXSuryaOCR(str(model))
    return _ENGINE


# How much of the top of the page to cut away on each retry. The model fails
# on some pages in ways that have nothing to do with legibility, and a page it
# will not read whole it often reads once the masthead is gone.
#
# Measured on the four Karnataka pages that produced no table, each of which is
# perfectly readable by eye:
#
#     Mudhol p1      full: 177 words, 17 distinct   crop 32%: 6 rows
#     Jamakhandi p1  full: HTML and JSON interleaved crop 32%: 8 rows
#     HBHalli p1     full: 0 words                  crop 32%: 6 rows
#     Kudligi p1     full: 0 words                  crop  8%: 8 rows
#
# Two different faults, one ladder. Mudhol degenerates into "ಕರ್ನಾಟಕ ರಾಜ್ಯಪತ್ರ
# ಸಂಪಾದಕ" repeated thirty-two times, which is a decoder loop and not a picture
# problem - resolution and contrast do nothing for it, and ocr_image exposes no
# temperature or repetition penalty, so perturbing the input to re-roll the
# sampling is the only lever there is. Kudligi and HBHalli come back empty
# because the layout pass calls the whole page one image, which the ornate
# gazette masthead seems to provoke.
RETRY_CROPS = (0.08, 0.20, 0.32)
LAYOUT_RETRIES = 2


def layout_only(text):
    """True when the model returned region metadata instead of page content."""
    try:
        payload = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return False
    return (
        isinstance(payload, list)
        and bool(payload)
        and all(
            isinstance(region, dict) and {"label", "bbox", "count"} <= set(region)
            for region in payload
        )
    )


def degenerate(text):
    """True when Surya returned something, but not a reading of the page.

    Counting characters does not separate these: the Mudhol loop is 177 words
    and Jamakhandi's malformed run is 1,297. The share of *distinct* words does
    - it was 0.01 to 0.10 on every failing page here and 0.29 to 0.95 on every
    good one, with nothing in between.
    """
    if layout_only(text):
        return True
    if "<table" in text:
        return False
    words = re.sub(r"<[^>]+>", " ", text).split()
    if not words:
        return True
    return len(set(words)) / len(words) < 0.15


def unusable(text, wants_table=False):
    """Whether this page needs another attempt.

    `wants_table` is for document sets where every page is a table, which is
    the only way to catch the quietest failure of the four: Hunagund's first
    page read its letterhead perfectly, in varied and correct Kannada, and
    simply did not see the table underneath it. Nothing about that output looks
    wrong - the word variety is healthy and the characters are right - and a
    parser would have reported the page as holding no rows.
    """
    return degenerate(text) or (wants_table and "<table" not in text)


def ocr(
    path,
    model=None,
    dpi=DPI,
    deskew=True,
    progress=True,
    retry_crops=RETRY_CROPS,
    wants_table=False,
    partial=None,
):
    """Every page of a PDF as Surya's HTML, form-feed separated.

    HTML rather than flattened text, because the table's cell boundaries are
    exactly what a whitespace layout makes the parser guess at.

    A page the model would not read is retried with the top cropped away, and
    a page that needed one carries an `<!-- ocr-retry crop=... -->` marker so
    no row is ever silently the product of a repair. A page that survives the
    whole ladder is marked unread rather than left as a convincing blank.

    `partial` makes a document resumable a page at a time. Callers already skip
    documents whose cache exists, so a killed run costs at most one document -
    but at 61 seconds a page a long one is still several minutes, and a run
    this size will be interrupted. Pages land in a JSON-lines file as they are
    read, flushed to disk each time; a resumed run reads back the ones it has
    and does the rest. A line truncated by the kill fails to parse and its page
    is simply redone.
    """
    done = {}
    if partial and partial.exists():
        for line in partial.read_text(encoding="utf-8").splitlines():
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue  # killed mid-write; that page gets read again
            done[record["page"]] = record["text"]
    handle = None
    if partial:
        partial.parent.mkdir(parents=True, exist_ok=True)
        handle = partial.open("a", encoding="utf-8")

    pages = []
    total = page_count(path)
    for number in range(1, total + 1):
        if number in done:
            pages.append(done[number])
            continue
        with tempfile.TemporaryDirectory() as scratch:
            stem = pathlib.Path(scratch) / "p"
            subprocess.run(
                [
                    "pdftoppm",
                    "-f",
                    str(number),
                    "-l",
                    str(number),
                    "-r",
                    str(dpi),
                    "-png",
                    str(path),
                    str(stem),
                ],
                capture_output=True,
                timeout=300,
            )
            rendered = sorted(pathlib.Path(scratch).glob("p-*.png"))
            if not rendered:
                pages.append("<!-- ocr-unread reason=render-failed -->")
                continue
            page = rendered[0]
            turn = rotation(page) if deskew else 0.0
            if turn:
                with Image.open(page) as image:
                    # The DPI has to be written back. Pillow drops the PNG's
                    # resolution on save, Tesseract then estimates it from the
                    # pixel size, and estimates it wrong: the same Godda page
                    # yields 14 rows with the tag and none without it. Every
                    # earlier attempt at that page failed for this reason and
                    # looked like a limit of the scan.
                    resolution = image.info.get("dpi", (dpi, dpi))
                    image.rotate(-turn, expand=True).save(page, dpi=resolution)

            text, _ = engine(model).ocr_image(str(page))
            bad = unusable(text, wants_table)
            for attempt in range(1, LAYOUT_RETRIES + 1) if layout_only(text) else ():
                text, _ = engine(model).ocr_image(str(page))
                if not unusable(text, wants_table):
                    text = f"<!-- ocr-retry same-image={attempt} -->\n{text}"
                    bad = False
                    break
            for crop in retry_crops if bad else ():
                cropped = pathlib.Path(scratch) / f"crop{int(crop * 100)}.png"
                with Image.open(page) as image:
                    width, height = image.size
                    image.crop((0, int(height * crop), width, height)).save(cropped)
                text, _ = engine(model).ocr_image(str(cropped))
                if not unusable(text, wants_table):
                    text = f"<!-- ocr-retry crop={crop} -->\n{text}"
                    break
            else:
                if bad:
                    text = (
                        "<!-- ocr-unread reason=degenerate-after-retries "
                        f"tried={len(retry_crops)} -->\n{text}"
                    )
            pages.append(text)
        if handle:
            handle.write(json.dumps({"page": number, "text": text}) + "\n")
            handle.flush()
        if progress:
            LOGGER.info(
                "OCR page completed",
                extra={
                    "event": "ocr_page_completed",
                    "source_file": path.name,
                    "page": number,
                    "pages": total,
                },
            )
    if handle:
        handle.close()
    return "\f".join(pages)
