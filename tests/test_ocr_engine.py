"""The OCR driver's repair and resume paths, without loading a model.

`engine()` is replaced by a fake, so these run in the parsing interpreter and
in a second rather than needing savitr, Apple Silicon and 61 seconds a page.
What is being tested is the control flow around the model - which pages get
re-read, which get repaired, which get marked - and none of that is the model's
business.
"""

import json
import shutil

import pytest

from local_elections.common import ocr_engine
from local_elections.paths import ROOT

GOOD = "<table><tr><td>ಒಂದು</td><td>ಎರಡು</td></tr></table>"
EMPTY = "<div><img/></div>"
LOOP = "ಕರ್ನಾಟಕ ರಾಜ್ಯಪತ್ರ ಸಂಪಾದಕ " * 30
PROSE_NO_TABLE = "<p>" + " ".join(f"ಪದ{i}" for i in range(40)) + "</p>"
LAYOUT_ONLY = json.dumps([{"label": "Table", "bbox": "170 13 807 570", "count": 2520}])


class FakeEngine:
    """Returns whatever the test queued, and records every image it was given."""

    def __init__(self, replies):
        self.replies = list(replies)
        self.seen = []

    def ocr_image(self, path):
        self.seen.append(path)
        reply = self.replies[min(len(self.seen) - 1, len(self.replies) - 1)]
        return reply, 0


@pytest.fixture
def a_pdf():
    """Any real multi-page PDF in the repo - this exercises pdfinfo and
    pdftoppm for real, which is where a path bug would hide."""
    if not all(shutil.which(command) for command in ("pdfinfo", "pdftoppm")):
        pytest.skip("Poppler CLI is not installed")
    for candidate in sorted((ROOT / "data" / "karnataka").rglob("*.pdf")):
        if ocr_engine.page_count(candidate) >= 3:
            return candidate
    pytest.skip("no multi-page PDF available")


@pytest.fixture
def fake(monkeypatch):
    """Installs a fake engine. Always through monkeypatch - an earlier version
    assigned ocr_engine.engine directly in one test, and because monkeypatch
    records whatever it finds at the moment it is called, the later patch in
    the same test restored the *fake* at teardown and leaked it into the rest
    of the file."""

    def install(replies, cls=None):
        engine = (cls or FakeEngine)(replies)
        monkeypatch.setattr(ocr_engine, "engine", lambda model=None: engine)
        return engine

    return install


# 50, not the production 200. These tests render real pages through pdftoppm so
# a path bug cannot hide, but nothing here looks at a pixel - and at 200 the six
# of them took 222 seconds against 70 for the whole rest of the suite.
DPI = 50


def test_a_page_that_reads_first_time_is_not_retried(a_pdf, fake):
    engine = fake([GOOD])
    text = ocr_engine.ocr(a_pdf, dpi=DPI, deskew=False, progress=False)
    assert len(engine.seen) == ocr_engine.page_count(a_pdf)
    assert "ocr-retry" not in text


def test_a_degenerate_page_is_retried_and_the_repair_is_recorded(a_pdf, fake):
    # first attempt loops, the first crop reads
    engine = fake([LOOP, GOOD])
    text = ocr_engine.ocr(a_pdf, dpi=DPI, deskew=False, progress=False)
    assert "<!-- ocr-retry crop=0.08 -->" in text
    assert "crop8.png" in " ".join(engine.seen), "the retry did not crop"


def test_a_layout_summary_without_cells_is_retried(a_pdf, fake):
    engine = fake([LAYOUT_ONLY, GOOD])
    text = ocr_engine.ocr(a_pdf, dpi=DPI, deskew=False, progress=False)
    assert "<!-- ocr-retry same-image=1 -->" in text
    assert "crop8.png" not in " ".join(engine.seen)


def test_a_page_with_no_table_is_retried_only_where_a_table_is_expected(a_pdf, fake):
    """Hunagund's failure: correct Kannada, healthy variety, no table. Nothing
    about it looks wrong, so only a caller that knows every page is a table can
    catch it."""
    engine = fake([PROSE_NO_TABLE, GOOD])
    plain = ocr_engine.ocr(a_pdf, dpi=DPI, deskew=False, progress=False)
    assert "ocr-retry" not in plain, "retried a page nobody said was a table"

    engine = fake([PROSE_NO_TABLE, GOOD])
    tabular = ocr_engine.ocr(
        a_pdf, dpi=DPI, deskew=False, progress=False, wants_table=True
    )
    assert "<!-- ocr-retry crop=0.08 -->" in tabular
    assert engine.seen


def test_a_page_that_survives_every_retry_is_marked_unread(a_pdf, fake):
    """A blank that is honest about being blank. The alternative - an empty
    page that looks like a page holding no rows - is the failure this whole
    mechanism exists to prevent."""
    engine = fake([EMPTY])
    text = ocr_engine.ocr(a_pdf, dpi=DPI, deskew=False, progress=False)
    assert "<!-- ocr-unread reason=degenerate-after-retries" in text
    pages = ocr_engine.page_count(a_pdf)
    assert len(engine.seen) == pages * (1 + len(ocr_engine.RETRY_CROPS))


def test_an_interrupted_run_resumes_without_rereading(a_pdf, fake, tmp_path):
    """The reason this exists: Jharkhand's largest document is 253 pages, which
    at 61 seconds a page is over four hours in a single file. Resuming per
    document would put all of it at risk of one interruption."""
    partial = tmp_path / "doc.jsonl"
    pages = ocr_engine.page_count(a_pdf)

    class DiesAfterOnePage(FakeEngine):
        def ocr_image(self, path):
            if len(self.seen) >= 1:
                raise KeyboardInterrupt("pretend the run was killed")
            return super().ocr_image(path)

    fake([GOOD], cls=DiesAfterOnePage)
    with pytest.raises(KeyboardInterrupt):
        ocr_engine.ocr(a_pdf, dpi=DPI, deskew=False, progress=False, partial=partial)

    assert partial.exists(), "nothing was written before the interruption"
    saved = [
        json.loads(line) for line in partial.read_text(encoding="utf-8").splitlines()
    ]
    assert [r["page"] for r in saved] == [1]

    resumed = fake([GOOD])
    text = ocr_engine.ocr(a_pdf, dpi=DPI, deskew=False, progress=False, partial=partial)
    assert len(resumed.seen) == pages - 1, "a finished page was read again"
    assert len(text.split("\f")) == pages


def test_a_line_truncated_by_the_kill_costs_one_page_not_the_file(
    a_pdf, fake, tmp_path
):
    partial = tmp_path / "doc.jsonl"
    partial.write_text(
        json.dumps({"page": 1, "text": GOOD})
        + "\n"
        + '{"page": 2, "text": "half a li',  # killed mid-write
        encoding="utf-8",
    )
    engine = fake([GOOD])
    text = ocr_engine.ocr(a_pdf, dpi=DPI, deskew=False, progress=False, partial=partial)
    assert len(engine.seen) == ocr_engine.page_count(a_pdf) - 1
    assert len(text.split("\f")) == ocr_engine.page_count(a_pdf)
