"""Transliterate the corpus's Indic names into Latin, as a stage of its own.

    uv run --with "indicate>=0.10" python -m local_elections.tools.transliterate
    uv run --with "indicate>=0.10" python -m local_elections.tools.transliterate --check
    make transliterate-muse CAP=10   # also the scripts indicate has no model for

Two fifths of this corpus is not in Latin script - 328,539 rows of Devanagari,
4,366 of Kannada - so those names cannot be searched, joined, or compared
against any external register. This turns them into something a reader outside
the source language can use.

**Why a stage and not a step inside a parser.** Kruti Dev decoding happens
inline in Jharkhand's parser, and that is exactly why `script` had to be
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
the committed OCR caches.

**Why a table and not a column.** Names repeat: 328,539 Devanagari rows hold
158,931 distinct strings. Keying on the string rather than the row means the
work is done once per name, the output is diffable, and a correction to one
name fixes every row that carries it.

`indicate`'s offline PyTorch backend is used rather than its LLM one, and the
reason is reproducibility rather than cost: it is deterministic - the same
input gives the same output across runs, checked - where an LLM is not, and a
non-deterministic stage cannot sit behind a manifest.

indicate has offline models only for Hindi and Punjabi. Tamil, Kannada,
Telugu, Malayalam, Gujarati and Bengali names, and the Devanagari ones the
model still misreads, go to Muse Spark (muse-spark-1.3-contributor) with
`--muse-cap`, through museclient, which caches every request and refuses one
that would pass the cap. The committed table is what makes that reproducible:
each reading is made once, and its `method` names the model and the prompt's
hash.

Nothing here replaces what a source printed. `winner` stays as the gazette set
it; the Latin form travels beside it, the way party_local sits beside party.
"""

import argparse
import collections
import csv
import hashlib
import re
import sys
import unicodedata
from concurrent.futures import ThreadPoolExecutor

import pyarrow.parquet as pq

from local_elections.common.runlog import command, get_logger
from local_elections.paths import ROOT

LOGGER = get_logger(__name__)

OUT = ROOT / "data" / "transliteration"

# The columns worth reading in Latin: who won, and where.
COLUMNS = ["winner", "gram_panchayat", "block", "district", "ward_name"]

SCRIPTS = {
    "devanagari": re.compile(r"[ऀ-ॿ]"),
    "bengali": re.compile(r"[ঀ-৿]"),
    "gurmukhi": re.compile(r"[਀-੿]"),
    "gujarati": re.compile(r"[઀-૿]"),
    "tamil": re.compile(r"[஀-௿]"),
    "telugu": re.compile(r"[ఀ-౿]"),
    "kannada": re.compile(r"[ಀ-೿]"),
    "malayalam": re.compile(r"[ഀ-ൿ]"),
}
# the scripts indicate has an offline model for, and its name for each
INDICATE = {"devanagari": "hindi", "gurmukhi": "punjabi"}
# what the prompt calls each script's names
LANGUAGE = {
    "devanagari": "Hindi (Devanagari)",
    "bengali": "Bengali or Assamese",
    "gurmukhi": "Punjabi (Gurmukhi)",
    "gujarati": "Gujarati",
    "tamil": "Tamil",
    "telugu": "Telugu",
    "kannada": "Kannada",
    "malayalam": "Malayalam",
}

MUSE_WORKDIR = ROOT / "dist" / "muse_transliteration"
MUSE_BATCH = 40
MUSE_THREADS = 16
MUSE_PROMPT = """You romanize names from Indian local election records: people \
who won seats, and the villages, wards and blocks they won them in. The names \
are printed in {language} script.

For each input, write it in Latin letters the way it is usually spelled in \
English, as in a voter list or a newspaper: lower case, no diacritics, words \
separated by single spaces. Keep every word, initials included (a \
one-letter initial becomes that letter), and write a number that is part of \
a name in digits ("ward 3", "kim 2"). Leave out brackets and punctuation. If \
the input holds no name at all, return an empty string.

Return one result per input id."""
MUSE_SCHEMA = {
    "type": "object",
    "properties": {
        "results": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "integer"},
                    "latin": {"type": "string"},
                },
                "required": ["id", "latin"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["results"],
    "additionalProperties": False,
}
MUSE_PROMPT_SHA = hashlib.sha256((MUSE_PROMPT + str(MUSE_SCHEMA)).encode()).hexdigest()[
    :12
]

FIELDS = ["script", "source", "latin", "method", "suspect"]
# What made the readings already in the tables. The model is indicate's offline
# one (engine="model"), but the run did not record the package version.
UNRECORDED = "indicate model; version not recorded"

# What the source cell carries besides the name: a serial number the gazette
# printed in the same box, a bullet, a stray rule character or dash (322 names
# ending in an en or em dash came back empty), a line break where
# two people share a cell.
LEADING = re.compile(
    "^[\\s\\-\u2013\u2014.,;:#*()\\[\\]|/\\\\0-9\"\u201c\u201d\u2018\u2019'`]+"
)
TRAILING = re.compile(
    "[\\s\\-\u2013\u2014.,;:#*()\\[\\]|/\\\\\"\u201c\u201d\u2018\u2019'`]+$"
)

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
    # A Latin reading is letters, spaces and the digits the source printed (a
    # ward number, "કીમ-૨" as "kim 2"). An extra digit or a diacritic means the
    # model was handed something it could not read as a name - 1,732 came back
    # holding a "0" from the gazette's abbreviation mark, and the word count was
    # right on every one of them, so counting words alone said they were fine.
    if len(re.findall(r"[0-9]", latin)) > len(re.findall(r"\d", clean(source))):
        return "digit in the reading"
    if re.search(r"[^\x00-\x7f]", latin):
        return "non-ascii in the reading"
    # words are runs holding a letter: "०" (an abbreviation mark) and "-" are
    # not words a reading can lose
    want = sum(1 for w in clean(source).split() if any(c.isalpha() for c in w))
    got = sum(1 for w in latin.split() if any(c.isalpha() for c in w))
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
        return {
            r["source"]: (r["latin"], r.get("method") or UNRECORDED)
            for r in csv.DictReader(fh)
        }


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
                    "latin": table[source][0],
                    "method": table[source][1],
                    "suspect": suspect(source, table[source][0]),
                }
            )
    return path


def transliterate(script, missing, client=None, batch=256):
    """Latin forms for strings we do not already hold.

    indicate's offline model first, where it has one, since it is
    deterministic. What it has no model for, or still reads badly, goes to Muse
    Spark when a client is given and is otherwise left for a decision.
    """
    out = {}
    if script in INDICATE:
        out = by_indicate(script, missing, batch)
    rest = [m for m in missing if m not in out or suspect(m, out[m][0])]
    if client is not None and rest:
        for source, reading in by_muse(client, script, rest).items():
            if source not in out or not suspect(source, reading[0]):
                out[source] = reading
    return out


def by_indicate(script, missing, batch):
    try:
        import indicate
    except ImportError:
        sys.exit(
            "indicate is not installed. Run this with "
            "`uv run --with 'indicate>=0.10' python -m "
            "local_elections.tools.transliterate`"
        )
    from importlib.metadata import version

    language = INDICATE[script]
    method = f"indicate {version('indicate')} model"
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
        readings = indicate.transliterate_batch(
            [n for _, n in keep], source=language, engine=["model"]
        )
        for (source, _), latin in zip(keep, readings, strict=True):
            out[source] = (latin.strip(), method)
        # indicate's word lookup ahead of the model reads what the model alone
        # gets wrong - अली as "0lī", नाई as "0nai" - and on a 1,500-name sample
        # cleaned 564 of 1,500 suspect readings and broke none. It is a second
        # choice, not the first, because it also maps names onto English words
        # (कसावा as "cassava") and respells a quarter of clean readings.
        retry = [(s, n) for s, n in keep if suspect(s, out[s][0])]
        if retry:
            second = indicate.transliterate_batch(
                [n for _, n in retry], source=language, engine=["lookup", "model"]
            )
            for (source, _), latin in zip(retry, second, strict=True):
                if not suspect(source, latin.strip()):
                    out[source] = (latin.strip(), f"{method} after lookup")
        LOGGER.info(
            "Transliteration batch completed",
            extra={
                "event": "transliteration_batch_completed",
                "script": script,
                "completed": min(start + batch, len(ordered)),
                "total": len(ordered),
            },
        )
    return out


def ascii_latin(text):
    """Lower case, diacritics stripped, single spaces."""
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", text).strip().lower()


def by_muse(client, script, missing):
    """{source: (latin, method)} from Muse Spark, MUSE_BATCH names a request."""
    method = f"{client.model} reasoning=low prompt={MUSE_PROMPT_SHA}"
    prompt = MUSE_PROMPT.format(language=LANGUAGE[script])
    asked = [(s, clean(s)) for s in sorted(missing)]
    asked = [(s, n) for s, n in asked if n]
    batches = [asked[i : i + MUSE_BATCH] for i in range(0, len(asked), MUSE_BATCH)]

    def one(batch):
        listing = "\n".join(f"{i}\t{name}" for i, (_, name) in enumerate(batch))
        try:
            return client.complete(
                [
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": f"id\tname\n{listing}"},
                ],
                schema=MUSE_SCHEMA,
                name="romanize",
                max_completion_tokens=8000,
                reasoning_effort="low",
            )
        except Exception as error:  # a failed batch is counted, not fatal
            return error

    def take(batch, answer):
        got = {r["id"]: r["latin"] for r in answer["results"]}
        for i, (source, _) in enumerate(batch):
            if i in got:
                out[source] = (ascii_latin(got[i]), method)

    out, failed, retry = {}, 0, []
    with ThreadPoolExecutor(MUSE_THREADS) as pool:
        for number, (batch, answer) in enumerate(
            zip(batches, pool.map(one, batches), strict=True), 1
        ):
            if isinstance(answer, Exception):
                failed += 1
                LOGGER.warning(
                    "Muse batch failed",
                    extra={"event": "muse_batch_failed", "error": str(answer)[:300]},
                )
                if type(answer).__name__ == "BudgetError":
                    return out
                retry.append(batch)
                continue
            take(batch, answer)
            if number % 25 == 0 or number == len(batches):
                print(
                    f"  {script}: {number} of {len(batches)} requests; "
                    f"{failed} failed; {client.spend()}",
                    flush=True,
                )
        # A failed request ran out of output: it reasoned past the limit, or
        # fell into repeating one reading down a run of similar sorted names.
        # Each half is a smaller, different request, so it is not the cached
        # failure again. Once only; what still fails stays unread.
        halves = [h for b in retry for h in (b[: len(b) // 2], b[len(b) // 2 :]) if h]
        for batch, answer in zip(halves, pool.map(one, halves), strict=True):
            if not isinstance(answer, Exception):
                take(batch, answer)
    print(f"  {script}: {failed} failed, {len(retry)} retried in halves", flush=True)
    return out


@command("transform", artifact="name_transliteration")
def main():
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument(
        "--check", action="store_true", help="report what is missing and write nothing"
    )
    ap.add_argument("--limit", type=int, help="stop after N new strings")
    ap.add_argument(
        "--muse-cap",
        type=float,
        help="send what indicate cannot read to Muse Spark, up to this many USD",
    )
    ap.add_argument("--scripts", nargs="*", help="only these scripts")
    args = ap.parse_args()
    client = None
    if args.muse_cap:
        from museclient import Client

        client = Client(args.muse_cap, MUSE_WORKDIR)

    found = strings_in_master()
    for script in sorted(found):
        if args.scripts and script not in args.scripts:
            continue
        held = load(script)
        # an empty or suspect reading is a failure to read: try it again
        missing = sorted(
            found[script] - {k for k, v in held.items() if not suspect(k, v[0])}
        )
        print(
            f"{script}: {len(found[script]):,} distinct in the corpus, "
            f"{len(held):,} already transliterated, {len(missing):,} to do"
        )
        if args.check or not missing:
            continue
        if args.limit:
            missing = missing[: args.limit]
        held.update(transliterate(script, missing, client))
        # only keep what the corpus still contains, so a name that leaves the
        # data does not linger in the table forever
        held = {k: v for k, v in held.items() if k in found[script]}
        path = save(script, held)
        print(f"  wrote {len(held):,} rows -> {path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
