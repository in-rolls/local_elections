"""Build the pooled master from this repository and its siblings.

Everything a consumer needs to group across states, in one declared schema, with
every row still pointing at the page it was read from.

Three things this is careful about, each because getting it wrong would look
like success:

  reconcile()   every input row becomes an output row or a line in
                master_dropped.csv with a reason. It is the only check that can
                catch an adapter silently losing rows, because a row count that
                went down for a good reason and one that went down for a bad
                reason look identical.

  partitioning  one file per state. The pack here is already 1.9 GiB; a single
                master rewritten on every build adds a fresh blob each time even
                when one state changed.

  urban         excluded by canon.RURAL_TIERS and counted, not quietly dropped.
                Kerala ships urban wards in the same file as rural ones, so
                this cannot be done by choosing files.

UP and Rajasthan inputs are checksum-verified against published revisions in
data/sources.json and shared through INDIA_DATA_HOME. Other siblings are read
from ROOT.parent. The producing revision is recorded on every row.
"""

import argparse
import collections
import csv
import subprocess
import sys

import pyarrow as pa
import pyarrow.parquet as pq

from local_reservations.common import adapters, datasets, dictionary, sources
from local_reservations.common import master as M
from local_reservations.common.runlog import command, get_logger
from local_reservations.paths import ROOT

LOGGER = get_logger(__name__)

OUT = ROOT / "data" / "master"


def git_commit(directory, paths=None):
    """The commit these rows came from, and whether it has uncommitted changes.

    A dirty source makes source_commit meaningless - the rows did not come from
    that commit - so it is recorded rather than assumed away.

    `paths` narrows the question from "what is HEAD" to "when did the inputs last
    change", and for this repository that distinction is the difference between a
    build that settles and one that cannot. Stamping HEAD meant every row of the
    six states parsed here changed whenever any commit landed - including the
    commit that recorded the rows themselves, and the manifest rebuild after it.
    `make release-check` could therefore never pass: it rebuilds the master,
    which dirtied the tree it was about to check for cleanliness, and committing
    that dirtied it again.

    Asking when the sources and parsers last changed is also the more useful
    answer. A row says which version of the inputs produced it, rather than which
    unrelated commit happened to be checked out when someone ran the build.
    """
    scope = list(paths or [])
    try:
        if scope:
            sha = subprocess.run(
                ["git", "-C", str(directory), "log", "-1", "--format=%H", "--", *scope],
                capture_output=True,
                text=True,
                timeout=30,
            ).stdout.strip()
        else:
            sha = subprocess.run(
                ["git", "-C", str(directory), "rev-parse", "HEAD"],
                capture_output=True,
                text=True,
                timeout=30,
            ).stdout.strip()
        dirty = subprocess.run(
            ["git", "-C", str(directory), "status", "--porcelain", "--", *scope],
            capture_output=True,
            text=True,
            timeout=60,
        ).stdout.strip()
    except (subprocess.SubprocessError, OSError):
        return "", False
    return (sha[:12] + ("-dirty" if dirty else "")), bool(dirty)


# What a locally parsed row is actually built from: the parsers, and the parsed
# data they wrote. Generated data products are excluded: counting an output as
# an input would put the build back in the loop this scope is here to break.
LOCAL_INPUTS = [
    "src",
    "tests",
    "data",
    ":(exclude)data/master",
    ":(exclude)data/stats",
    ":(exclude)data/expectations_report.csv",
    ":(glob,exclude)data/*/readme.md",
]


def local_slices():
    """The states parsed in this repository."""
    commit, _ = git_commit(ROOT, LOCAL_INPUTS)
    grouped = collections.defaultdict(list)
    for _, rows in datasets.parsed():
        for row in rows:
            grouped[
                (row.get("state", ""), row.get("year", ""), row.get("tier", ""))
            ].append(row)
    for (state, year, tier), rows in sorted(grouped.items()):
        yield {
            "dataset_id": f"{state.lower().replace(' ', '_').replace('&', 'and')}"
            f"/{tier}/{year}",
            "state": state,
            "rows": rows,
            "source_repo": "local_elections",
            "source_commit": commit,
            "provenance_level": "page",
            "unit_of_observation": "seat",
        }


def sibling_slices(only=None):
    for name, adapter in sorted(adapters.REGISTRY.items()):
        if only and name not in only:
            continue
        pinned = sources.resolve(adapter.REPO)
        directory = pinned[0] if pinned else ROOT.parent / adapter.REPO
        if not directory.exists():
            LOGGER.warning(
                "Sibling repository not checked out",
                extra={
                    "event": "sibling_repository_missing",
                    "adapter": name,
                    "repository": adapter.REPO,
                },
            )
            continue
        commit, dirty = (pinned[1], False) if pinned else git_commit(directory)
        if dirty:
            LOGGER.warning(
                "Sibling repository has uncommitted changes",
                extra={
                    "event": "sibling_repository_dirty",
                    "adapter": name,
                    "repository": adapter.REPO,
                },
            )
        for got in adapter.slices(directory):
            yield dict(got, source_repo=adapter.REPO, source_commit=commit)


def sibling_supplemental(only=None):
    """Typed non-seat tables exposed by sibling adapters.

    A GP-level nomination summary is useful data, but it is not a seat and it
    is not a candidate. Keeping it as its own table preserves the source grain
    instead of manufacturing one seat row per aggregate.
    """
    for name, adapter in sorted(adapters.REGISTRY.items()):
        if only and name not in only:
            continue
        build_table = getattr(adapter, "supplemental", None)
        if build_table is None:
            continue
        pinned = sources.resolve(adapter.REPO)
        directory = pinned[0] if pinned else ROOT.parent / adapter.REPO
        if not directory.exists():
            continue
        commit, _ = (pinned[1], False) if pinned else git_commit(directory)
        table = build_table(directory)
        for row in table["rows"]:
            row["source_repo"] = adapter.REPO
            row["source_commit"] = commit
        yield table


def build(only=None):
    rows, extras, dropped, candidates = [], [], [], []
    seen = collections.Counter()
    counts = collections.Counter()
    # Read once. to_master runs 829,628 times and this is 154,700 entries.
    latin = M.transliterations(ROOT)

    for slice_ in list(local_slices()) + list(sibling_slices(only)):
        for row in slice_["rows"]:
            counts["input"] += 1
            got = M.to_master(
                row,
                slice_["dataset_id"],
                slice_["source_repo"],
                slice_["source_commit"],
                slice_["provenance_level"],
                row.get("unit_of_observation")
                or slice_.get("unit_of_observation", "seat"),
                row.get("seat_candidates", ""),
                latin,
            )
            if got is None:
                dropped.append(
                    {
                        "dataset_id": slice_["dataset_id"],
                        "reason": "urban local body, out of scope",
                        "detail": row.get("tier", ""),
                        "source_path": row.get("source_path", ""),
                    }
                )
                counts["urban"] += 1
                continue
            key = got["seat_key"]
            seen[key] += 1
            got["row_id"] = M.row_id(got, seen[key])
            rows.append(got)
            extras += M.extras(row, got["row_id"])
            candidates += M.candidates(row, got)
            counts["output"] += 1

    # computed over the whole master rather than per file, because a seat stated
    # in two states' files would otherwise look unique in both
    for row in rows:
        row["seat_key_unique"] = int(seen[row["seat_key"]] == 1)

    supplemental = list(sibling_supplemental(only))
    return rows, extras, dropped, candidates, supplemental, counts


def reconcile(counts, dropped):
    """Every input row must become an output row or a dropped one.

    The only check that can catch an adapter losing rows quietly: a count that
    fell for a good reason looks exactly like one that fell for a bad one.
    """
    accounted = counts["output"] + len(dropped)
    if accounted != counts["input"]:
        raise SystemExit(
            f"reconcile: {counts['input']:,} rows in, {counts['output']:,} out, "
            f"{len(dropped):,} dropped - {counts['input'] - accounted:,} "
            f"unaccounted for"
        )


def write(rows, extras, dropped, candidates, supplemental):
    OUT.mkdir(parents=True, exist_ok=True)
    by_state = collections.defaultdict(list)
    for row in rows:
        by_state[row["state"]].append(row)

    written = []
    for state, subset in sorted(by_state.items()):
        written.append(
            write_parquet(f"master_{slug_of(state)}.parquet", M.MASTER_COLUMNS, subset)
        )

    by_state = collections.defaultdict(list)
    for row in candidates:
        by_state[row["state"]].append(row)
    for state, subset in sorted(by_state.items()):
        written.append(
            write_parquet(
                f"candidates_{slug_of(state)}.parquet", M.CANDIDATE_COLUMNS, subset
            )
        )

    write_parquet("master_extras.parquet", ["row_id", "column", "value"], extras)

    for table in supplemental:
        written.append(write_parquet(table["name"], table["columns"], table["rows"]))

    # These two stay CSV. Both are under 1 MB and neither is the published
    # product: they exist to be opened by a person chasing a defect, and a
    # format you cannot grep is the wrong one for that.
    for name, columns, data in (
        (
            "master_dropped.csv",
            ["dataset_id", "reason", "detail", "source_path"],
            dropped,
        ),
        (
            "master_key_collisions.csv",
            ["seat_key", "rows", "dataset_id", "row_id"],
            collisions(rows),
        ),
    ):
        with (OUT / name).open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(
                fh, fieldnames=columns, extrasaction="ignore", lineterminator="\n"
            )
            writer.writeheader()
            writer.writerows(data)
    return written


def slug_of(state):
    return state.lower().replace(" ", "_").replace("&", "and")


def write_parquet(name, columns, rows):
    """A published table.

    Not a space optimisation, though it is one. `candidates_bihar.csv` is 208 MB
    and GitHub refuses any file over 100 MB outright, so the corpus could not be
    pushed at all. The reason to prefer parquet over the gzipped CSV it replaces
    is that reading a state table drops from 0.80 s to 0.06 s: these tables exist
    to be grouped across, and a consumer pays that cost every time.

    **Types come from dictionary.py, never from inference.** The dictionary
    already declares what every column is, and it is what `make expect` checks
    against, so a file that types its columns differently would contradict the
    repository's own definition of them. Inference is the thing to avoid, not
    types: it would read a ward number of `07` as the integer 7 in the states
    that print leading zeros and leave it a string in the states that do not,
    and the same column would then have different types in different files.

    Typing buys something CSV cannot express at all: **null is not blank**.
    `woman_reserved` being unknown and `woman_reserved` being false are
    different facts here - that distinction is what `gender_stated` exists to
    protect - and in a CSV they are both the empty string.

    A value that will not cast **stops the build**. That is the whole point: the
    alternative is a silent null, and a seat whose number quietly became missing
    looks exactly like a seat that never had one. Two such columns were found
    the first time this ran - Uttarakhand writing "17-गुलडिया" into `seat_no`
    and Goa writing "Unopposed" into `votes` - and both were real defects in the
    sources' parsers rather than reasons to loosen the type.

    The parquet analogue of gzip's timestamp problem, and the reason
    `requirements.txt` pins pyarrow: two writes of the same table are
    byte-identical, but the footer records `created_by: parquet-cpp-arrow
    version <x>`. Upgrading pyarrow therefore changes every SHA-256 in the
    manifest with no data change, and `make verify` would report the whole
    corpus altered. The manifest records the writer version so that reads as
    what it is rather than as data drift.
    """
    table = pa.table({column: cast(name, column, rows) for column in columns})
    path = OUT / name
    pq.write_table(table, path, compression="zstd")
    return (path, len(rows))


# What the dictionary's declared dtype means in parquet. `enum` becomes a
# dictionary-encoded string, which is what an enum is. `roman_or_integer` stays
# a string because J&K and Goa number wards in Roman numerals. Anything the
# dictionary does not declare - row_id, the provenance columns, the sibling
# commit - is a string.
ARROW_TYPES = {
    "integer": pa.int64(),
    "boolean": pa.bool_(),
    "enum": pa.dictionary(pa.int32(), pa.string()),
}

TRUE, FALSE = {"1", "true", "True", "yes"}, {"0", "false", "False", "no"}


def cast(filename, column, rows):
    """One column, in the type the dictionary declares for it.

    Blank becomes null, which is the point of doing this at all. A value that is
    neither blank nor castable raises: see write_parquet.
    """
    declared = dictionary.BY_NAME.get(column, {}).get("dtype")
    arrow = ARROW_TYPES.get(declared, pa.string())
    values = []
    for row in rows:
        raw = row.get(column, "")
        text = "" if raw is None else str(raw).strip()
        if text == "":
            values.append(None)
        elif arrow == pa.int64():
            if not text.lstrip("-").isdigit():
                raise SystemExit(
                    f"{filename}: {column} is declared {declared} in "
                    f"dictionary.py but holds {text!r}. Fix the parser or the "
                    f"declaration - casting it would silently drop the value."
                )
            values.append(int(text))
        elif arrow == pa.bool_():
            if text not in TRUE and text not in FALSE:
                raise SystemExit(
                    f"{filename}: {column} is declared {declared} in "
                    f"dictionary.py but holds {text!r}."
                )
            values.append(text in TRUE)
        else:
            values.append(text)
    return pa.array(values, type=arrow)


def collisions(rows):
    grouped = collections.defaultdict(list)
    for row in rows:
        grouped[row["seat_key"]].append(row)
    out = []
    for key, subset in grouped.items():
        if len(subset) > 1:
            for row in subset:
                out.append(
                    {
                        "seat_key": key,
                        "rows": len(subset),
                        "dataset_id": row["dataset_id"],
                        "row_id": row["row_id"],
                    }
                )
    return sorted(out, key=lambda r: (-r["rows"], r["seat_key"]))


def render_readme(rows, dropped, candidates, counts, written):
    unique = sum(1 for r in rows if r["seat_key_unique"])
    states = collections.Counter(r["state"] for r in rows)
    tiers = collections.Counter(r["tier"] for r in rows)
    provenance = collections.Counter(r["provenance_level"] for r in rows)
    out = [
        "# The pooled master",
        "",
        "*Generated by `make master`. Edits here are overwritten.*",
        "",
        f"{len(rows):,} seat-event records across {len(states)} states, in one "
        f"declared schema. One file per state; the headers are identical, so "
        f"concatenating them is the whole table.",
        "",
        "## What a row is",
        "",
        "Rows are standardized at seat-event grain. Most sources identify an "
        "event by election year; where a source names general and by-election "
        "periods, those remain separate rather than collapsing repeated elections. "
        f"{unique:,} rows ({unique / max(len(rows), 1):.1%}) have keys that "
        f"identify a distinct seat; the other {len(rows) - unique:,} lack "
        "enough source detail to distinguish every record and are listed in "
        "[master_key_collisions.csv](master_key_collisions.csv) rather than "
        "hidden behind a promise the data does not support.",
        "",
        "| State | Seat events |",
        "|---|---|",
    ]
    for state, n in sorted(states.items()):
        out.append(f"| [{state}](master_{slug_of(state)}.parquet) | {n:,} |")
    out += ["", "| Tier | Seat events |", "|---|---|"]
    for tier, n in tiers.most_common():
        out.append(f"| `{tier}` | {n:,} |")
    out += [
        "",
        "## Reading all seat events",
        "",
        "```python",
        "from pathlib import Path",
        "",
        "import pandas as pd",
        "",
        'master = Path("data/master")',
        "state_files = sorted(",
        "    path",
        '    for path in master.glob("master_*.parquet")',
        '    if path.name != "master_extras.parquet"',
        ")",
        "seats = pd.concat(",
        "    (pd.read_parquet(path) for path in state_files),",
        "    ignore_index=True,",
        ")",
        f"assert len(seats) == {len(rows)}",
        "```",
        "",
        "## Three columns where one would have lost something",
        "",
        "- **`tier` and `tier_local`** — states print the same office under "
        "different names, and worse, the same name means different "
        "offices. Bihar's *sarpanch* heads a village court, not the "
        "panchayat. Group on `tier`; check against a gazette with "
        "`tier_local`.",
        "- **`caste_reservation`, `caste_reservation_local` and "
        "`caste_scheme`** — the fold to `BC` is lossy and is not the same "
        "fold everywhere. Haryana reserves only Block A of its Backward "
        "Classes list and prints `BC_A`; Kerala reserves no backward-class "
        "seat at all, so zero BC rows there is the law rather than a "
        "parsing failure. `caste_scheme` is what makes those "
        "distinguishable.",
        "- **`unit_of_observation` and `seat_candidates`** — some sources "
        "are candidate-level and are collapsed to seats. A row that came "
        "from a collapse says so, with the denominator visible.",
        "",
        "## Before you use it",
        "",
        "`quality_flags` carries what a row cannot be trusted for: "
        "`ocr_repaired`, `gender_not_stated`, `ward_list_incomplete`, "
        "`winner_inferred`, `winner_candidate_ambiguous`, "
        "`winner_category_sex_disagree`, `winner_name_missing`, "
        "`seat_number_inferred`, `reservation_control_disagree`, "
        "`margin_not_below_votes`, `name_untransliterated`, and "
        "`printings_disagree`. "
        "`gender_not_stated` in particular means `woman_reserved=0` is a "
        "default rather than a reading.",
        "",
        "`provenance_level` says how far back a row can be traced:",
        "",
    ]
    for level, n in provenance.most_common():
        meaning = {
            "row": "to the exact source row and page it was read from",
            "page": "to the page it was read from",
            "document": "to a document, but not a page within it",
            "dataset": "to the file it came from and no further",
            "none": "nowhere - the source recorded none",
        }.get(level, "")
        out.append(f"- **{level}** — {n:,} rows, traceable {meaning}")
    out += [
        "",
        "## Companion tables",
        "",
        "Candidate tables keep one row per person who stood and join to the "
        "seat event on `row_id`. They retain non-contact attributes such as "
        "gender, age, caste, education, occupation, marital status and assets; "
        "mobile numbers, email addresses and postal addresses are deliberately "
        "excluded.",
        "",
        "Supplemental tables retain useful source grains that are neither seats "
        "nor candidates. Rajasthan's nomination table, for example, is one row "
        "per gram-panchayat election event.",
        "",
        "## Files",
        "",
        "| File | Rows | What |",
        "|---|---|---|",
    ]
    for path, n in written:
        if path.name.startswith("candidates_"):
            what = "one state, one row per candidate"
        elif path.name.startswith("supplemental_"):
            what = "source-specific table at its declared grain"
        else:
            what = "one state, one row per seat event"
        out.append(f"| [`{path.name}`]({path.name}) | {n:,} | {what} |")
    out += [
        "| [`master_extras.parquet`](master_extras.parquet) | — | the "
        "state-specific columns, long-form as (row_id, column, value), so "
        "the master stays a fixed schema without losing anything |",
        f"| [`master_key_collisions.csv`](master_key_collisions.csv) | "
        f"{len(rows) - unique:,} | rows that do not identify a distinct "
        f"seat |",
        f"| [`master_dropped.csv`](master_dropped.csv) | {len(dropped):,} "
        f"| every input row that did not become an output row, with a "
        f"reason. `make master` fails if these do not add up |",
        "",
        "## Scope",
        "",
        "Rural bodies only for now — urban local bodies are held by the "
        "Trivedi Centre and are filtered by `canon.RURAL_TIERS`, which has "
        "to be a row-level filter because Kerala ships urban wards in the "
        "same file as rural ones.",
        "",
    ]
    return "\n".join(out) + "\n"


@command("build", artifact="master_dataset")
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", nargs="*", help="build only these sibling states")
    args = ap.parse_args()

    rows, extras, dropped, candidates, supplemental, counts = build(args.only)
    reconcile(counts, dropped)
    written = write(rows, extras, dropped, candidates, supplemental)
    (OUT / "readme.md").write_text(
        render_readme(rows, dropped, candidates, counts, written), encoding="utf-8"
    )

    print(f"\n{counts['output']:,} rows -> {OUT.relative_to(ROOT)}/")
    for path, n in written:
        print(f"  {path.name:34} {n:>9,}")
    unique = sum(1 for r in rows if r["seat_key_unique"])
    print(
        f"\n  {counts['input']:,} in, {counts['output']:,} out, "
        f"{len(dropped):,} dropped ({counts['urban']:,} urban)"
    )
    print(
        f"  {unique:,} rows identify a distinct seat "
        f"({unique / max(len(rows), 1):.1%}); "
        f"{len(rows) - unique:,} do not, listed in master_key_collisions.csv"
    )
    print(f"  {len(extras):,} extra values held long-form in master_extras.parquet")
    if candidates:
        print(
            f"  {len(candidates):,} candidate rows in "
            f"candidates_<state>.parquet, joinable to the seat on row_id"
        )
    tiers = collections.Counter(r["tier"] for r in rows)
    print("  " + "  ".join(f"{k}={v:,}" for k, v in tiers.most_common()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
