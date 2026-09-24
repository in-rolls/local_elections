"""Read the seat identifiers that Jharkhand printed as pictures.

On three pages of the Lohardaga notification the whole seat column is embedded
images rather than text - 40 of them per page - so pdfplumber sees only the
district's roman numeral and 121 rows end up identifying no seat at all. They
are the largest single key collision in the corpus.

The information is not missing. Those images render clean Unicode Devanagari,
easier to read than the Kruti Dev the rest of the state is printed in:

    XVII लोहरदगा /6/1/ अलौदी - (6)
         district  block/gp  panchayat  ward

Koderma is the same defect on a larger scale: pages 30-35 of its notification
carry 33 to 51 images each against 32 to 50 rows that identify nothing, and
every one of those rows reads "VI" because the roman numeral is all the text
layer kept. It was missed here for years because this file used to match a
bespoke regex written against Lohardaga's "/6/1/ अलौदी - (6)", while Koderma
prints the same identifier as "कोडरमा/5/9 – योगियाटिल्हा", with @ and & where
Lohardaga has slashes.

So the identifier is no longer matched here at all. It goes through
`parse.split_seat_id`, the same reader every other path in this state uses,
which already knows all five ways the typesetters bracket a number.

**This used to say the numbers could not be read.** Under tesseract they could
not - "10 comes back as 20, 11 as 2, 12 as 22" - so the ward number was derived
from the document's own ordering, the largest piece of guesswork in this
repository. Surya reads them: a Koderma page returns 48 of 48 identifiers with
the gram panchayat numbers running 8,9,10...23 unbroken. The ordering fallback
is gone, and with it the risk that a row lost to OCR shifts every seat after it.

Writes data/jharkhand/2015/image_seats.csv, which parse.py reads. Cached and
committed, because OCR is slow and its output should be reviewable rather than
regenerated silently on every parse.

Runs under the repository's interpreter, unlike ocr.py: finding the pages needs
pdfplumber and reading them needs the model, and those two cannot share an
interpreter, so the model is reached by handing a directory of rendered pages to
surya_pages.py under savitr's.
"""

import argparse
import csv
import pathlib
import re
import subprocess
import sys
import tempfile

from local_elections.common.runlog import command, get_logger
from local_elections.paths import ROOT
from local_elections.states.jharkhand import parse

LOGGER = get_logger(__name__)

JHARKHAND = ROOT / "data" / "jharkhand" / "2015"
OUT = JHARKHAND / "image_seats.csv"

COLUMNS = [
    "source_pdf",
    "source_page",
    "serial",
    "name_ocr",
    "district_roman",
    "block_no",
    "gp_no",
    "gram_panchayat",
    "ward_no",
    "ward_no_ocr",
]

# The whole page is read, not just the seat column. The serial number in the
# first column is what joins an OCR line back to a parsed row, and the name
# beside it confirms the join - the OCR finds more rows on a page than the
# parser does (38 against 34 on page 22), so matching by position would file
# every seat against the wrong person.
CROP_FROM = 0.0

# A page whose seat column is text runs its words out to about 0.92 of the
# width; one whose column is pictures stops around 0.71, because the text ends
# where the images begin. Measured, not guessed.
TEXT_REACHES = 0.75
DPI = 400


def image_pages(path):
    """Pages whose seat column is drawn rather than typed.

    Identified by the text stopping short of the column: a page with real text
    there runs to the page's right edge, one without stops well before it.
    """
    import pdfplumber

    found = []
    with pdfplumber.open(str(path)) as pdf:
        for number, page in enumerate(pdf.pages, 1):
            words = page.extract_words()
            if not words or not page.images:
                continue
            # Pages 21 and 25 are mixed - some rows typeset, some pasted in as
            # pictures - so their words reach the right edge and the threshold
            # skipped them, leaving 54 rows unidentified. Any page carrying a
            # crop of images is read; the join is on the serial number and
            # confirmed by the name, and only fills rows that named no
            # panchayat, so reading a page that did not need it costs nothing.
            rightmost = max(w["x1"] for w in words)
            if len(page.images) > 5 or rightmost < TEXT_REACHES * page.width:
                found.append((number, page.width))
    return found


def render(path, number, width, into):
    """One page, as a PNG the model can read."""
    left = int(CROP_FROM * width / 72 * DPI)
    stem = into / f"{path.stem}__{number}"
    subprocess.run(
        [
            "pdftoppm",
            "-f",
            str(number),
            "-l",
            str(number),
            "-r",
            str(DPI),
            "-x",
            str(left),
            "-W",
            str(int(width / 72 * DPI) - left),
            "-png",
            "-singlefile",
            str(path),
            str(stem),
        ],
        capture_output=True,
        timeout=300,
    )
    return stem.with_suffix(".png")


def read_page(text):
    """The name and the seat identifier off one OCR'd page.

    Taken from the table structure - first cell and last - rather than by a
    regex over a line. Matching a line is what kept this file Lohardaga-shaped:
    the pattern wanted "/6/1/ अलौदी - (6)" and Koderma prints "@" and "&".
    """
    out = []
    for row in parse.HTML_ROW.findall(text):
        cells = parse.html_cells(row)
        if len(cells) < 2 or not parse.DEVANAGARI.search(cells[-1]):
            continue
        out.append((cells[0], cells[-1]))
    return out


def ocr_all(pages, into):
    """Hand a directory of rendered pages to savitr's uv environment, once.

    A subprocess keeps the Apple-Silicon model stack out of parser-only runs
    and loads the model once for the complete page batch.
    """
    if not pages:
        return
    command = ["uv", "run", "--no-default-groups", "--group", "ocr", "python"]
    done = subprocess.run(
        [
            *command,
            str(pathlib.Path(__file__).parent / "surya_pages.py"),
            str(into),
        ],
        cwd=ROOT,
    )
    if done.returncode:
        sys.exit(f"the OCR environment failed reading {into}")


SERIAL = re.compile(r"^\s*(\d{1,3})\b")


def read(path):
    """Every drawn seat on every image page of one document.

    The tier passed to split_seat_id is "ward_member" because that is the shape
    these pages carry - a panchayat and a bracketed ward number - and because the
    splitter needs a tier to know whether a trailing name is a block or a gram
    panchayat. A row that turns out to be a head is filled by name and its ward
    number is ignored on the other side of the join.
    """
    found = image_pages(path)
    if not found:
        return []
    with tempfile.TemporaryDirectory() as scratch:
        into = pathlib.Path(scratch)
        rendered = {
            number: render(path, number, width, into) for number, width in found
        }
        ocr_all(found, into)
        pages = {
            number: (
                png.with_suffix(".txt").read_text(encoding="utf-8")
                if png.with_suffix(".txt").exists()
                else ""
            )
            for number, png in rendered.items()
        }

    rows = []
    for number, text in sorted(pages.items()):
        for name, identifier in read_page(text):
            seat = parse.split_seat_id(identifier, "ward_member")
            if not seat.get("gram_panchayat"):
                continue
            serial = SERIAL.match(name)
            rows.append(
                {
                    # the serial is a cheaper join key where the page prints one;
                    # where it does not, fill_image_seats falls back to the name
                    "serial": serial.group(1) if serial else "",
                    "name_ocr": re.sub(r"^\s*\d{1,3}[\s.|)]*", "", name).strip(),
                    "district_roman": seat.get("district_roman", ""),
                    "block_no": seat.get("block_no", ""),
                    "gp_no": seat.get("gp_no", ""),
                    "gram_panchayat": seat.get("gram_panchayat", ""),
                    "ward_no": seat.get("seat_no", ""),
                    "ward_no_ocr": seat.get("seat_no", ""),
                    "source_pdf": path.name,
                    "source_page": number,
                }
            )
    return rows


@command("extract", state="Jharkhand", method="seat_ocr")
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf", help="only this document")
    args = ap.parse_args()

    rows = []
    for path in sorted(JHARKHAND.rglob("*.pdf")):
        if args.pdf and args.pdf.lower() not in path.name.lower():
            continue
        try:
            got = read(path)
        except Exception as exc:
            LOGGER.exception(
                "Seat image OCR failed",
                extra={
                    "event": "seat_image_ocr_failed",
                    "source_file": path.name,
                    "error_type": type(exc).__name__,
                },
            )
            continue
        if got:
            print(
                f"  {path.name}: {len(got)} seats from "
                f"{len({r['source_page'] for r in got})} image pages"
            )
            rows += got

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(
            fh, fieldnames=COLUMNS, extrasaction="ignore", lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(rows)
    print(f"\n{len(rows)} seats -> {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
