"""OCR the West Bengal zila parishad gazettes, keeping word positions.

These are scans, and the thing that has to be read off them is *which column a
word sits in*: the caste reservation and the women's reservation are two
separate columns, and a page where they are flattened into a line of text says
"SC Women" for a seat reserved for a scheduled caste woman and "Women" for one
reserved only for a woman - but also "SC" for one reserved only for a scheduled
caste, and nothing at all for an open seat. Reading that as running text works
until a stray word lands between them.

So tesseract is run in TSV mode and the word boxes are kept. `parse.py` decides
columns from the gazette's own `(1) (2) (3) (4) (5)` header markers, which the
commission prints on the first page of every district's table.

Two things learned the hard way elsewhere in this repository and applied here:

- **Pillow drops the DPI when it saves a PNG.** Tesseract then guesses the
  resolution and mis-sizes everything. `pdftoppm` writes the DPI correctly, so
  its output is passed to tesseract untouched rather than being round-tripped
  through Pillow - the round trip is what invalidated a whole earlier finding.
- **`--psm 4`**, single column of variable-size text, which is what a wide ruled
  table actually is. The default segmentation splits these into blocks and
  interleaves the columns.

The cache is committed, so the parse runs without tesseract installed.
"""

import argparse
import subprocess
import sys

from local_elections.common.ocr_engine import page_count
from local_elections.common.runlog import command
from local_elections.paths import ROOT

DATA = ROOT / "data" / "wb" / "2018"
CACHE = ROOT / "data" / "wb" / "ocr"

DPI = "300"


def documents():
    """Every gazette, final and draft, with which printing it is.

    19 of the 20 districts published a draft and a final. Parsing both is what
    makes `printings_agree` possible here, and it is the strongest evidence
    available that a scanned row was read right - two independent scans of two
    independently typeset documents agreeing on the same seat.
    """
    for path in sorted(DATA.glob("*.pdf")):
        yield path, "final"
    for path in sorted((DATA / "draft").glob("*.pdf")):
        yield path, "draft"


def cache_path(path, printing, page):
    return CACHE / printing / f"{path.stem}-{page:02d}.tsv"


def run(path, printing, page, force=False):
    out = cache_path(path, printing, page)
    if out.exists() and not force:
        return False
    out.parent.mkdir(parents=True, exist_ok=True)
    stem = out.with_suffix("")
    subprocess.run(
        [
            "pdftoppm",
            "-r",
            DPI,
            "-png",
            "-f",
            str(page),
            "-l",
            str(page),
            str(path),
            str(stem),
        ],
        check=True,
    )
    # pdftoppm names by page number; with -f == -l it still suffixes
    rendered = sorted(stem.parent.glob(f"{stem.name}-*.png"))
    if not rendered:
        return False
    image = rendered[0]
    got = subprocess.run(
        ["tesseract", str(image), "stdout", "--psm", "4", "tsv"],
        capture_output=True,
        text=True,
    )
    out.write_text(got.stdout, encoding="utf-8")
    image.unlink()
    return True


@command("extract", state="West Bengal", method="ocr")
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    if not DATA.exists():
        raise SystemExit(f"no gazettes at {DATA}")
    done = 0
    for path, printing in documents():
        for page in range(1, page_count(path) + 1):
            if run(path, printing, page, args.force):
                done += 1
        if not args.quiet:
            print(f"  {printing:5} {path.stem[:60]}", flush=True)
    if not args.quiet:
        print(f"  {done} page(s) OCR'd into {CACHE.relative_to(ROOT)}/")


if __name__ == "__main__":
    sys.exit(main())
