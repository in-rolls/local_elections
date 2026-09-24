"""Transliterate the corpus's Indic names into Latin, as a stage of its own.

    uv run --with indicate python -m local_elections.tools.transliterate
    uv run --with indicate python -m local_elections.tools.transliterate --check

Two fifths of this corpus is not in Latin script - 328,539 rows of Devanagari,
4,366 of Kannada - so those names cannot be searched, joined, or compared
against any external register. This turns them into something a reader outside
the source language can use.

**Why a stage and not a step inside a parser.** Kruti Dev decoding happens
inline in Jharkhand's parser today, and that is exactly why `script` had to be
corrected mid-parse rather than stated once. Collection, parsing and
transliteration answer different questions - what does the state publish, what
does this document say, and what is that name in Latin - and folding the third
into the second means it cannot be re-run, re-checked or improved on its own.
The pipeline is collect -> parse -> transliterate -> pool.

**Why a committed table and not a build step.** A release pins a SHA-256 for
every file. Transliterating during the build would put a model in the path of
every hash, so a library upgrade would rewrite the corpus without changing a
value - the same argument that pins pyarrow. This writes a lookup table, the
table is committed, and the master build only ever reads it. Same reasoning as
data/jharkhand/ocr/.

**Why a table and not a column.** Names repeat: 328,539 Devanagari rows hold
158,931 distinct strings. Keying on the string rather than the row means the
work is done once per name, the output is diffable, and a correction to one
name fixes every row that carries it.

`indicate`'s offline PyTorch backend is used rather than its LLM one, and the
reason is reproducibility rather than cost: it is deterministic - the same
input gives the same output across runs, checked - where an LLM is not, and a
non-deterministic stage cannot sit behind a manifest.

Nothing here replaces what a source printed. `winner` stays as the gazette set
it; the Latin form travels beside it, the way party_local sits beside party.
"""

import argparse
import collections
import csv
import re
import sys

import pyarrow.parquet as pq

from local_elections.common.runlog import command, get_logger
from local_elections.paths import ROOT

LOGGER = get_logger(__name__)

OUT = ROOT / "data" / "transliteration"

# The columns worth reading in Latin: who won, and where.
COLUMNS = ["winner", "gram_panchayat", "block", "district", "ward_name"]

SCRIPTS = {
    "devanagari": re.compile(r"[ऀ-ॿ]"),
    "kannada": re.compile(r"[ಀ-೿]"),
}

FIELDS = ["script", "source", "latin", "suspect"]

# What the source cell carries besides the name: a serial number the gazette
# printed in the same box, a bullet, a stray rule character, a line break where
# two people share a cell.
LEADING = re.compile("^[\\s\\-.,;:#*()\\[\\]|/\\\\0-9\"\u201c\u201d\u2018\u2019'`]+")
TRAILING = re.compile("[\\s\\-.,;:#*()\\[\\]|/\\\\\"\u201c\u201d\u2018\u2019'`]+$")

# The gazettes abbreviate with a zero rather than a full stop - "प0" for
# प्रखंड, "उ0" for उत्तर, in either the Devanagari digit or the Latin one. The
# model reads it as the digit it is: "06-प0 उधवा दियारा" came back as "0v
# udhavaa diyara". Stripped where it follows a Devanagari letter, which is the
# only place it can be an abbreviation mark rather than a number.
ABBREVIATION = re.compile(r"(?<=[\u0900-\u097f])[0०]")


def clean(text):
    """The name inside a cell, with the packaging removed.

    Feeding the raw cell to the model produced readings that were wrong in ways
    no count could show: a leading dash on "- नयाडीह" invented a "bha" prefix,
    "#पाली महतो" came back as " mahato" with a word gone, and "01-तांतरी उ0"
    came back as " u". The model is given a name because that is what it was
    trained on.
    """
    text = text.replace("\n", " ").replace("\r", " ")
    text = ABBREVIATION.sub("", text)
    text = LEADING.sub("", text)
    text = TRAILING.sub("", text)
    return re.sub(r"\s+", " ", text).strip()


def suspect(source, latin):
    """Whether a reading looks like it lost something.

    Not a correctness check - nothing here can tell a right transliteration
    from a plausible wrong one. It catches the failure that is visible without
    knowing the language: words going missing. A name of three words that comes
    back as one has dropped two, whatever the remaining one says.
    """
    if not latin.strip():
        return "empty"
    # A Latin reading is letters and spaces. A digit or a diacritic in the
    # output means the model was handed something it could not read as a name -
    # 1,732 came back holding a "0" from the gazette's abbreviation mark, and
    # the word count was right on every one of them, so counting words alone
    # said they were fine.
    if re.search(r"[0-9]", latin):
        return "digit in the reading"
    if re.search(r"[^\x00-\x7f]", latin):
        return "non-ascii in the reading"
    want, got = len(clean(source).split()), len(latin.split())
    if got < want:
        return f"lost {want - got} of {want} words"
    return ""


def strings_in_master():
    """{script: {string}} for everything the pooled corpus holds."""
    found = collections.defaultdict(set)
    for path in sorted((ROOT / "data" / "master").glob("master_*.parquet")):
        if path.name == "master_extras.parquet":
            continue
        table = pq.read_table(path)
        for column in COLUMNS:
            if column not in table.column_names:
                continue
            for value in table.column(column).to_pylist():
                if not value:
                    continue
                for script, pattern in SCRIPTS.items():
                    if pattern.search(value):
                        found[script].add(value)
                        break
    return found


def load(script):
    """What has already been transliterated for this script."""
    path = OUT / f"{script}.csv"
    if not path.exists():
        return {}
    with path.open(encoding="utf-8") as fh:
        return {r["source"]: r["latin"] for r in csv.DictReader(fh)}


def save(script, table):
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"{script}.csv"
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader()
        for source in sorted(table):
            writer.writerow(
                {
                    "script": script,
                    "source": source,
                    "latin": table[source],
                    "suspect": suspect(source, table[source]),
                }
            )
    return path


def transliterate(script, missing, batch=256):
    """Latin forms for strings we do not already hold.

    Devanagari goes through indicate's offline model, which is deterministic.
    Kannada has no offline model, so it is left for a decision rather than sent
    to an LLM behind a manifest that promises reproducibility.
    """
    if script != "devanagari":
        return {}
    try:
        from indicate.hindi2english import HindiToEnglish
    except ImportError:
        sys.exit(
            "indicate is not installed. Run this with "
            "`uv run --with indicate python -m "
            "local_elections.tools.transliterate`"
        )
    out = {}
    ordered = sorted(missing)
    for start in range(0, len(ordered), batch):
        chunk = ordered[start : start + batch]
        asked = [clean(c) for c in chunk]
        keep = [
            (source, name) for source, name in zip(chunk, asked, strict=True) if name
        ]
        if not keep:
            continue
        # strict: a batch that comes back a different length than it went in
        # would silently pair names with the wrong readings
        readings = HindiToEnglish.transliterate_batch([n for _, n in keep])
        for (source, _), latin in zip(keep, readings, strict=True):
            out[source] = latin.strip()
        LOGGER.info(
            "Transliteration batch completed",
            extra={
                "event": "transliteration_batch_completed",
                "script": "devanagari",
                "completed": min(start + batch, len(ordered)),
                "total": len(ordered),
            },
        )
    return out


@command("transform", artifact="name_transliteration")
def main():
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument(
        "--check", action="store_true", help="report what is missing and write nothing"
    )
    ap.add_argument("--limit", type=int, help="stop after N new strings")
    args = ap.parse_args()

    found = strings_in_master()
    for script in sorted(found):
        held = load(script)
        missing = sorted(found[script] - set(held))
        print(
            f"{script}: {len(found[script]):,} distinct in the corpus, "
            f"{len(held):,} already transliterated, {len(missing):,} to do"
        )
        if args.check or not missing:
            continue
        if args.limit:
            missing = missing[: args.limit]
        held.update(transliterate(script, missing))
        # only keep what the corpus still contains, so a name that leaves the
        # data does not linger in the table forever
        held = {k: v for k, v in held.items() if k in found[script]}
        path = save(script, held)
        print(f"  wrote {len(held):,} rows -> {path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
