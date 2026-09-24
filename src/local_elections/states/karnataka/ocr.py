"""OCR Karnataka's 2016 taluk and zilla panchayat result notifications.

195 documents, 586 pages, harvested from the Wayback Machine's copy of
karsec.gov.in - 169 taluk panchayats and 26 zilla panchayats. Karnataka
contributes nothing to either tier today; what it has is a gram panchayat
reservation history for 1993-2007, which names no winner by construction.

Every one of them is a photograph. The producer string on all 195 is
`RICOH Aficio MP 5002` - a copier - and pdfplumber extracts zero characters
from page 1 of each, so there is no text layer to prefer and no encoding
question to settle. Surya reads them directly.

**Surya reads Kannada.** Measured on the first page of Badami taluk before
committing to the run: it returned the notification prose and the five-column
table cell by cell, with `<br/>` where the winner's name is stacked above the
address. Its errors are concentrated in a systematic confusion of
sibilants - ಸೂ read as ಕೂ, ಕ್ಷ as ಕ್ನ - which lands mostly on the two closed
vocabularies, the reservation category and the party name. Those canonicalise
against a fixed list. The open field, the winner's name, does not, and its
error rate is what the bench has to measure.

The table is worth more than the tier count suggests. Column 5 is
`ಪ್ರತಿನಿಧಿಸಿದ ರಾಜಕೀಯ ಪಕ್ಷದ ಹೆಸರು` - the party the winner represented - which
almost nothing else in the corpus carries.

Cached to data/karnataka/ocr/<stem>.txt, form-feed separated so page numbers
survive, and committed: the run takes about ten hours on Apple Silicon, so
leaving it out would mean only one machine could rebuild Karnataka.

That ten hours is measured, not estimated. A first estimate of 2.7 came from
timing page 1 of Badami, which is mostly prose over a three-row table; Surya
decodes autoregressively, so a page carrying twenty rows costs several times
as much. 17 seconds a page became 61.

    uv run --no-default-groups --group ocr python \
        -m local_elections.states.karnataka.ocr
"""

import argparse
import os
import sys

from local_elections.common import ocr_engine
from local_elections.common.runlog import command
from local_elections.paths import ROOT

DATA = ROOT / "data" / "karnataka"
CACHE = DATA / "ocr"

# One set of the three. The notifications have no text layer at all - every one
# of the 195 is a copier scan - so Surya reads them directly.
SETS = ["tzp_2016_elected"]

# The other two are held, committed, provenanced, and deliberately not read.
# This is a decision, not an oversight, and it is written here because this is
# the file somebody re-runs when they wonder why the cache is smaller than the
# harvest.
#
# The harvest ranked all three by file count and that was the wrong ranking:
# 211 documents can be worth less than 195, and 33 can be worth nothing at all.
NOT_PARSED = {
    "tzp_2016_reservation": (
        "211 files, 415 pages. Seat-level reservation for the 2016 taluk and "
        "zilla seats - the same seats the elected-member notifications cover, "
        "whose own third column already states the reservation. Reading these "
        "would produce a second opinion on a field we have, not a new one. "
        "About three hours of OCR for a cross-check."
    ),
    "gp_2015": (
        "33 files, 544 pages. Nobody is named anywhere in them. Form-1 counts "
        "nomination papers received, Form-2 those valid after scrutiny, Form-3 "
        "the candidates left in the fray, Form-5 turnout, and the file called "
        "Result.pdf is Form-4 - the final count including unopposed wins, as "
        "district x taluk x 26 numeric columns. 402 of the 544 pages are a "
        "rule book and three officer manuals on top of that.\n"
        "One thing in here is worth knowing about without rediscovering it: "
        "Form-4's per-taluk counts of seats and members elected by category "
        "are the shape of an external denominator, of the kind "
        "plausible_vs_registry wants, and they come from the commission that "
        "ran the election rather than from the LGD register. That is a "
        "different job from parsing seats and nobody should stumble into it."
    ),
}

# The second reason a document goes unread, and not the same as NOT_PARSED
# above: these are individual files inside a set we do read. Procedure, not
# data - a rule book, a returning-officer manual, a presiding-officer manual
# and a general guide to the election. Kept in force because a future run that
# re-enables gp_2015 should still skip them.
SKIP = (
    "Rules_Book",
    "GP_RO_Manual",
    "GP_PRO_Manual",
    "Karnataka_panchayatraj_chunavane",
)

MODEL = os.environ.get("SURYA_MLX_PATH")


@command("extract", state="Karnataka", method="ocr")
def main():
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("--only", help="substring of the filename to OCR")
    ap.add_argument("--force", action="store_true", help="ignore the cache")
    ap.add_argument("--limit", type=int)
    args = ap.parse_args()

    documents = [
        p
        for name in SETS
        for p in sorted((DATA / name).glob("*.pdf"))
        if not any(token in p.name for token in SKIP)
    ]
    if args.only:
        documents = [p for p in documents if args.only.lower() in p.name.lower()]
    if args.limit:
        documents = documents[: args.limit]

    CACHE.mkdir(parents=True, exist_ok=True)
    # One flat cache. Every filename already carries its set - the harvester
    # names files after the archive path they came from - so a stem collision
    # across the three is not possible.
    stems = [p.stem for p in documents]
    assert len(set(stems)) == len(stems), "cache stems are not unique"

    done = skipped = 0
    for path in documents:
        target = CACHE / f"{path.stem}.txt"
        if target.exists() and not args.force:
            skipped += 1
            continue
        # deskew=False: these are flatbed copier scans, all portrait. The
        # orientation pass costs a tesseract call per page and Jharkhand needed
        # it only for one district printed sideways.
        # wants_table: every page of every one of these is a table, so a page
        # that comes back without one has been misread however clean it looks.
        # partial: a page at a time, so an interrupted run costs one page and
        # not one document. Document size stops mattering - the biggest file
        # here is 14 pages, but the same code has to survive a 150-page one.
        partial = CACHE / ".partial" / f"{path.stem}.jsonl"
        text = ocr_engine.ocr(
            path, model=MODEL, deskew=False, wants_table=True, partial=partial
        )
        target.write_text(text, encoding="utf-8")
        partial.unlink(missing_ok=True)
        done += 1

    print(f"{done} read, {skipped} already cached -> {CACHE.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
