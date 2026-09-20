"""Write a readme into every state directory under data/.

The top-level readme answers "what does this repository hold". It cannot answer
"what is in this directory, where did it come from, and what should I not do
with it" without becoming unreadable, and that is the question someone has who
has landed in data/jk/ from a search result or a file listing.

Everything here is derived from the files themselves - row counts, women's
shares, districts, the source documents each row cites, the caveats. Nothing is
typed in that could drift out of step with the data, which is the same reason
the top-level tables are generated. The one hand-written part is the paragraph
saying what makes each state's sources awkward, in STATE_NOTES, because that is
knowledge about documents rather than a fact derivable from the parsed rows.

Run with `make state-readmes`, or `--check` to fail when a file on disk differs
from what would be generated now.
"""

import argparse
import collections
import csv
import sys

from local_reservations.common import datasets
from local_reservations.common.runlog import command
from local_reservations.paths import ROOT
from local_reservations.states.assam import controls_2025 as assam_controls
from local_reservations.tools import build_coverage as coverage

STATS = DATA_STATS = None

DATA = ROOT / "data"
ASSAM_HELD = assam_controls.HELD_DISTRICT_NOTIFICATIONS
ASSAM_PARSED = len(assam_controls.PARSED_DISTRICTS)
ASSAM_PARSED_LABEL = assam_controls.PARSED_DISTRICT_LABEL
ASSAM_UNPARSED = assam_controls.UNPARSED_DISTRICT_NOTIFICATIONS

# What is awkward about each state's sources. Knowledge about the documents,
# not a fact derivable from the rows, so it is written rather than computed -
# and kept to what a reader needs before using the numbers.
STATE_NOTES = {
    "wb": """The pooled slice covers 2018 Zilla Parishad seats. Separately,
[named Birbhum Pradhan reservation observations](derived/birbhum_reservations/README.md)
cover the 1998 and 2003 terms, with raw codes, year exceptions and source
conflicts preserved. The [reservation gap matrix](vintage_search/README.md)
tracks historical district/cycle coverage. Results without reservation
fields are tabled and do not fill any reservation gap.

A September 2026
source search recovered raw GP reservation documents for Birbhum, Jalpaiguri,
Cooch Behar and Alipurduar for 2023, and historical district sources for
2003, 2008, 2013 and 2018. Alipurduar's 2018 results archive includes GP
candidate votes, winners and constituency reservation status.

[Derived tables](derived/README.md) include named Nadia 2013 Pradhan/deputy
reservations, historical and 2023 office schedules, ward reservations,
Alipurduar results and separate verification aggregates. The
[full page ledger](derived/parsing_inventory/pages.csv) records extraction,
parser coverage and remaining review. Office mentions, member seats and
candidate rows are distinct units; a parsed count does not certify an OCR name.

[The GP source search](gp_source_search.md) links the raw files, source
manifests and manual-entry index. Drafts, final orders, results and aggregate
tables are distinguished there. These acquisitions are not yet included in
the pooled reservation dataset.
""",
    "maharashtra": """Mumbai only. The Brihanmumbai Municipal Corporation has 227
ward seats; two councils are in the schema, `ulb_ward_2012` and `ulb_ward_2017`.

Every file under `mumbai/` arrived as a result table assembled for research, not
as the State Election Commission's reservation roster, and only one of them
states the seat reservation at all: the "Present Reservation" column of
`BMC-2007_raw.xlsx`. **That column is the 2012 draw, not 2007's.** It lists 115
women's seats where the 2007 council had 76 (one third), and it agrees ward for
ward with the deposit's 2012-term flag on 226 of 227 wards (ward 172 differs).
Its "Sitting Corporator" column holds the 2007 winners. So the sheet supplies
the 2012 slice's reservation and the 2007 supplemental file's winners.

The 2017 slice takes its reservation from the replication deposit for
Karekurve-Ramachandra & Lee (2025, *Comparative Political Studies*), Harvard
Dataverse doi:10.7910/DVN/IO9SLQ, CC0, held under `mumbai/dataverse_IO9SLQ/`
with a manifest and checksums. The authors digitised the commission's result
handbooks, so for 2017 the reservation is a secondary source. Winners for 2012
come from a scan transcription (202 of 227 wards named; names are surname-first
and phonetic) and for 2017 from the commission's result export; both are checked
against the deposit's councillor names by the validator.

Supplemental files under `mumbai/` carry no `reservation` column and stay out of
the pooled machinery on purpose: `bmc_seats_2007.csv` (2007 winners with the
women's flag only; caste reservation unknown), `bmc_candidates_<year>.csv` for
1997, 2002, 2012 and 2017, and the Praja Foundation ward-by-wave citizen ratings
of councillors, `praja_ward_ratings_2011_2018.csv`, in which the satisfaction
item is inverted in the 2018 wave and flagged rather than repaired. The 1997 and
2002 councils have no reservation roster here, and rural Maharashtra's ~28,000
gram panchayats are absent entirely.
""",
    "assam": f"""The 2020 notification contains two reservation rosters: wards
and municipal-board chairpersons. It prints only the reserved seats. The ward
table also prints each board's total number of wards, but not the identifiers
of the open wards; those seats are therefore not invented in the output, and
`listing_scope` is `reserved_only` on every row.

The PDF is a scan with a misleading hidden OCR layer. Its 81 ward-summary rows
and 46 chairperson rows are checked transcriptions tied to the committed PDF's
SHA-256, with page provenance on every emitted seat. The board totals reconcile
to the notification's own grand total of 1,004 wards.

The separate `2025_reservation` source series contains {ASSAM_HELD} district PRI
notifications acquired from the Assam State Election Commission.
{ASSAM_PARSED_LABEL} are parsed, not a
statewide claim. Charaideo's 36 GPs span four Anchalik Panchayats; its left table keeps
the printed SC/ST ward counts, including zeroes and twos. Kamrup Metropolitan's
20 GPs span three Anchalik Panchayats; its notification explicitly labels every
office and all 200 named ward rows, including Unreserved seats. South
Salmara-Mankachar adds a complete 35-GP and 350-ward universe; all 175 names
printed for women-reserved wards are retained, while GP-to-AP membership stays
blank because that source does not print the crosswalk. Hailakandi contributes
a 62-GP left table across five Anchalik Panchayats and 459 identifiable reserved
seats. Its notification omits open seats, so those are not invented and its
unknown all-ward counts stay blank. Seven child seat tables contain 1,678 stated
seats across the {ASSAM_PARSED} districts. Acquisition, OCR, parsing, and
validation are separate stages. The remaining {ASSAM_UNPARSED} district PDFs
stay visible as held, unparsed
work. Four supporting final-delimitation gazettes preserve the official AP, GP,
development-block, and ZPC hierarchy used to review Hailakandi.

Some source pages contain administrative contact details; derived election
tables whitelist election fields and do not carry phone numbers or other
incidental personal data.""",
    "ap": """All 13 district GP-reservation gazettes are held. Eight have
passed extraction, parsing, and validation; the other five remain acquired but
unparsed. Acquisition, text extraction/OCR, and parsing are separate stages.
`extract.py` retains usable embedded text, `ocr.py` re-reads scans from 300 DPI
renders, and the parser consumes only those retained artifacts. A newly held
PDF therefore cannot silently enter the published rows merely because its
hidden text contains something category-like.

The source layouts differ. Kurnool is a ruled GP-by-ward table with usable
embedded text. Several earlier districts require positional OCR; they do not
agree on column order, and Krishna itself puts the ward count on opposite sides
of the Sarpanch cell on adjacent pages. Where no line marks the boundary between
the mandal and panchayat, it is recovered from the order of the records.

Kadapa is read from retained word coordinates because the scan is skewed and
its hidden text order does not preserve the table. Its 807 GP rows and 50
mandals are checked against the three abstracts printed in the same gazette.
Pages 56–57 then supply a separate errata layer: all 41 `For` values must agree
with the original table before the `Read as` values are applied. Corrected rows
retain both printed values and the correction page.

Two consequences worth knowing before using this. `ocr_repaired` counts the
mends a row's category cell needed - a wrong mend looks exactly like a right
one, so those rows stay findable rather than being quietly trusted. And
Anantapur states each sarpanch seat twice, in two separately typeset proformas;
the file holds their deduplicated union, `printings` records how many
statements stood behind each row, and `printings_agree` records whether they
said the same thing.""",
    "goa": """Goa publishes ward-level reservation for village panchayats. The
2012 cycle names the winner; 2017 and 2022 are nomination-stage listings and
name nobody, which is a property of the document rather than a gap in the
parse. Ward numbers arrive in five different shapes, including one with a soft
hyphen inside it (`Ward­IV`), so they are normalized rather than read
literally.""",
    "gujarat": """The 2020 rotation orders display Gujarati correctly but their
hidden text layer is a misencoded glyph stream. Acquisition, OCR, and parsing
are separate stages: the raw cell readings remain in `ocr/*.jsonl`, while the
two parsed files standardise only the reservation category and retain the
source-script constituency name.

The holdings contain multiple administrative layers rather than treating a
state as a single table: 16 district-panchayat orders and 29 taluka-panchayat
orders, with district and body recorded in the source manifest. Five
low-contrast constituency cells that neither page-wide nor isolated-cell OCR
could read were transcribed from their rendered source pages and are marked as
reviewed readings in the raw JSONL.""",
    "karnataka": """Two very different sources sit under this state. The
1993-2007 gram panchayat rows come from a Stata file, a reservation history
that names no winner in any cycle because it is a roster rather than a result.
The 2016 taluk and zilla panchayat rows come from 195 notifications harvested
from the web archive's copy of `karsec.gov.in`; every one of them is a copier
scan with no text layer, read with Surya, and they carry the party the winner
represented, which almost nothing else in this corpus does.

**Two further groups of documents were harvested, are committed here, and are
deliberately not parsed.** Saying so is the point of this paragraph: they are
not a gap and nobody needs to look at them again.

`tzp_2016_reservation` is 211 files of seat-level reservation for the same 2016
seats the notifications cover - and the notifications' own third column already
states the reservation, so reading these would produce a second opinion on a
field we have rather than a new field.

`gp_2015` is 33 files in which nobody is named. Form-1 counts nomination papers
received, Form-2 those valid after scrutiny, Form-3 the candidates left in the
fray, Form-5 turnout, and the file called `Result.pdf` is Form-4 - the final
count including unopposed wins, but as district x taluk x 26 numeric columns.
The one thing in it worth knowing about is that those per-taluk counts of seats
and members elected by category are the shape of an external denominator, and
they come from the commission that ran the election rather than from the LGD
register. That is a different job from parsing seats.

Both groups keep their manifests, so any file can be traced to the URL and
capture it came from, and re-read by anyone who disagrees with this.""",
    "jharkhand": """Place names are printed in Kruti Dev, a legacy font
encoding rather than Unicode, and are shipped as they were printed - `script`
says so on every row. They are not transliterated, so joining these to another
source on name will not work without transliterating first.

The filenames do not reliably say which tier a file holds, so tier is decided
from the contents. A third of the PDFs have no ruling lines at all.""",
    "jk": """The holdings are an ad-hoc subset of districts rather than a
corpus, and there is no reliable published total to measure them against, so
no completeness figure is quoted - an invented denominator would be worse than
admitting there is not one.

The 2018 documents list **only the reserved seats**. Their 82% women's share is
a fact about which pages were published, not about J&K, and `listing_scope`
marks every such row. Do not compute shares across it.""",
}

# What each state's own substantive checks appeal to. These are the checks that
# actually catch silent corruption, since every parser bug in this repo produced
# plausible values rather than an error.
STATE_CHECKS = {
    "assam": [
        "the notification's printed 1,004-ward grand total",
        "the printed runs of 81 board rows and 46 chairperson rows",
        "mutual exclusivity of the five ward-reservation columns",
        "Charaideo's printed 36-GP, four-AP, and 360-ward universes",
        "exact source category vectors for all seven Charaideo rural tiers",
        "Kamrup Metropolitan's 20-GP, three-AP, and 200-ward universes",
        "all 200 printed village cells and the rendered-page recovery of ward 139",
        "Hailakandi's 62-GP, five-AP, and 459 identifiable reserved-seat rows",
        "the rejected malformed GP-president row and GP-45 hierarchy conflict",
        "every rural child row joining to its district GP left table",
    ],
    "ap": [
        "the complete 13-document official source manifest and file checksums",
        "Kurnool's complete GP serial sequence from 1 through 972",
        "Kadapa's printed 807-GP/50-mandal controls and all 41 errata rows",
        "each gazette's own FORMAT-I abstract, district by district",
        "agreement between the two proformas that state a seat twice",
        "the share of category cells that needed OCR repair",
    ],
    "goa": [
        "the published count of panchayats that went to poll in 2012",
        "the ward set, compared across the three cycles",
        "per-taluka coverage against 2012, which is complete",
    ],
    "gujarat": [
        "the published eight-category totals for every one of the 45 source orders",
        "the complete 1-through-N constituency sequence in each order",
        "a source-script constituency name and a reviewed category match for every row",
    ],
    "jharkhand": [
        "the published seat totals for each tier",
        "how much of the gap is the source's and how much the "
        "parser's, decided by opening the file",
    ],
    "jk": [
        "SC-reserved wards against SC population, the strongest check available here",
        "the women's share against the one-third floor",
    ],
    "karnataka": [
        "the source-declared GP-head row count in each cycle",
        "reviewed row-count floors for the 2016 OCR outputs",
        "seat-number continuity within each source document",
    ],
    "maharashtra": [
        "227 seats in each council, one per ward",
        "the statutory women's share (one half from 2012) and the 27% Backward "
        "Class share",
        "the 2012 reservation against the deposit's independently digitised flag",
        "winner names against the deposit's councillors for 2012 and 2017",
    ],
    "telangana": [
        "the declared row counts for both 2019 GP tiers",
        "source-backed uniqueness and provenance for every row",
    ],
    "wb": [
        "the reviewed total of 825 zilla-parishad seats",
        "all 20 district gazettes represented",
        "complete, unique district seat runs from 1 through N",
    ],
}

MAKE_TARGET = {
    "ap": "ap",
    "assam": "assam",
    "goa": "goa",
    "gujarat": "gujarat",
    "jharkhand": "jharkhand",
    "jk": "jk",
    "karnataka": "karnataka",
    "maharashtra": "maharashtra",
    "telangana": "telangana",
    "wb": "wb",
}


def stats_rows(name):
    path = DATA / "stats" / name
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


STATUS_MARK = {"pass": "&check;", "warn": "!", "fail": "&cross;", "skip": "&ndash;"}


def render_checks(state):
    """The check grid for one state, from data/stats/slice_checks.csv.

    A skip renders as a dash and never as a tick. That is the whole point: the
    two largest slices in this repository went unchecked for row loss because a
    skip read like a pass.
    """
    rows = [r for r in stats_rows("slice_checks.csv") if r["state"] == state]
    if not rows:
        return []
    slices = sorted({(r["year"], r["tier"]) for r in rows})
    checks = sorted({r["check_id"] for r in rows})
    appeals = {r["check_id"]: r["appeals_to"] for r in rows}
    grid = {(r["year"], r["tier"], r["check_id"]): r for r in rows}

    out = [
        "| Check | Appeals to | " + " | ".join(f"{y} `{t}`" for y, t in slices) + " |",
        "|---|---|" + "---|" * len(slices),
    ]
    for check in checks:
        cells = []
        for year, tier in slices:
            got = grid.get((year, tier, check))
            if not got:
                cells.append("")
                continue
            mark = STATUS_MARK.get(got["status"], got["status"])
            shown = got["observed"][:22]
            cells.append(f"{mark} {shown}".strip())
        out.append(f"| `{check}` | {appeals[check]} | " + " | ".join(cells) + " |")
    out.append("")
    out.append(
        "&check; pass &nbsp; ! warn &nbsp; &cross; fail &nbsp; "
        "&ndash; skipped, meaning no rule is declared for that slice — "
        "which is not the same as passing."
    )
    return out


def render_stats(state):
    rows = [r for r in stats_rows("slice_stats.csv") if r["state"] == state]
    if not rows:
        return []
    out = [
        "| Year | Tier | Rows | Districts | Blocks | Panchayats | "
        "Women | SC | ST | BC | Sources |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in sorted(rows, key=lambda x: (x["year"], x["tier"])):

        def pct(key):
            return f"{float(r[key]) * 100:.0f}%" if r[key] else "—"

        out.append(
            f"| {r['year']} | `{r['tier']}` | {int(r['rows']):,} | "
            f"{r['districts']} | {r['blocks']} | {int(r['panchayats']):,} | "
            f"{pct('women_share')} | {pct('sc_share')} | {pct('st_share')} | "
            f"{pct('bc_share')} | {r['source_documents']} docs, "
            f"{int(r['source_pages']):,} pages |"
        )
    return out


def slices_by_directory():
    grouped = collections.defaultdict(list)
    for entry in coverage.slices():
        grouped[entry["dir"]].append(entry)
    return grouped


def dataset_files(directory):
    """Parsed outputs in this directory, with what each holds."""
    out = []
    for path, rows in datasets.parsed():
        if path.parent.name != directory:
            continue
        out.append(
            {
                "name": path.name,
                "stem": path.stem,
                "rows": len(rows),
                "columns": len(rows[0]),
                "sources": len({r.get("source_path", "") for r in rows}),
            }
        )
    return out


def source_documents(directory):
    """Every document the rows cite, and whether it is actually here."""
    cited, missing = set(), set()
    for path in sorted((DATA / directory).glob("*.csv")):
        with path.open(encoding="utf-8", errors="replace") as fh:
            reader = csv.DictReader(fh)
            if not reader.fieldnames or "source_path" not in reader.fieldnames:
                continue
            for row in reader:
                target = (row.get("source_path") or "").strip()
                if not target:
                    continue
                cited.add(target)
                if not (ROOT / target).exists():
                    missing.add(target)
    return sorted(cited), sorted(missing)


def source_files(directory):
    """Files actually held, not counting the readme this script writes - which
    would otherwise make every directory report one file more than it has.
    """
    return sorted(
        p
        for p in (DATA / directory).rglob("*")
        if p.is_file() and p.name != "readme.md" and not p.name.startswith(".")
    )


def raw_inventory(directory):
    path = DATA / "inventory.csv"
    if not path.exists():
        return collections.Counter(), 0
    kinds, pages = collections.Counter(), 0
    with path.open(encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            if row["state"] != directory:
                continue
            kinds[row["format"]] += 1
            if (row.get("pages") or "").isdigit():
                pages += int(row["pages"])
    return kinds, pages


def source_series(directory):
    """Reviewed source series declared by standard harvest manifests."""
    grouped = collections.Counter()
    for manifest in (DATA / directory).rglob("manifest.csv"):
        with manifest.open(encoding="utf-8", errors="replace") as fh:
            reader = csv.DictReader(fh)
            if not reader.fieldnames or "source_id" not in reader.fieldnames:
                continue
            for row in reader:
                key = (
                    row["source_id"],
                    row["year"],
                    row["government_level"],
                    row["tier"],
                    row["document_format"],
                    row["landing_url"],
                )
                grouped[key] += 1
    return grouped


def render_source_series(directory):
    series = source_series(directory)
    if not series:
        return []
    out = [
        "| Source series | Year | Government level | Tier | Documents | "
        "Format | Landing page |",
        "|---|---|---|---|---|---|---|",
    ]
    for key, count in sorted(series.items()):
        source_id, year, level, tier, document_format, landing = key
        out.append(
            f"| `{source_id}` | {year} | `{level}` | `{tier}` | {count} | "
            f"`{document_format}` | [official source]({landing}) |"
        )
    return out


def render_parsed(directory, state, entries):
    files = dataset_files(directory)
    cited, missing = source_documents(directory)
    kinds, pages = raw_inventory(directory)
    total = sum(e["rows"] for e in entries)
    held_pdfs = {
        str(path.relative_to(ROOT))
        for path in (DATA / directory).rglob("*")
        if path.is_file() and path.suffix.lower() == ".pdf"
    }
    uncited = sorted(held_pdfs - set(cited))

    out = [f"# {state} — local body reservation", ""]
    out.append(
        "*Generated by `make state-readmes`. Edits here are overwritten "
        "— change the data or the generator instead.*"
    )
    out.append("")

    if uncited:
        out.append(
            f"This directory also holds {len(uncited)} source PDF"
            f"{'s' if len(uncited) != 1 else ''} not cited by any "
            "registered output slice. This count does not establish whether "
            "a source has a separately documented supplemental export."
        )
        out.append("")
    out.append(
        f"{total:,} rows across {len(entries)} "
        f"{'slice' if len(entries) == 1 else 'slices'}, parsed from "
        f"{len(cited)} source "
        f"{'document' if len(cited) == 1 else 'documents'} committed "
        f"alongside."
    )
    out.append("")

    out.append("## What is here")
    out.append("")
    out.append("| Year | Tier | Rows | Women | Districts | vs published | Notes |")
    out.append("|---|---|---|---|---|---|---|")
    for e in entries:
        out.append(
            f"| {e['year']} | `{e['tier']}` | {e['rows']:,} | "
            f"{e['women']:.0f}% | {e['districts']} | {e['coverage']} | "
            f"{e['notes'] or '—'} |"
        )
    out.append("")
    out.append(
        "Read the notes before the numbers — several of them say that a "
        "share is a property of which pages were published rather than "
        "of the state."
    )
    out.append("")

    out.append("## Files")
    out.append("")
    out.append(
        "Every file is written twice: `.csv` for a spreadsheet, "
        "`.jsonl` for a reader that should not break when a column is "
        "added."
    )
    out.append("")
    out.append("| File | Rows | Columns | Source documents |")
    out.append("|---|---|---|---|")
    for f in files:
        out.append(
            f"| [`{f['name']}`]({f['name']}) | {f['rows']:,} | "
            f"{f['columns']} | {f['sources']} |"
        )
    out.append("")

    stats = render_stats(state)
    if stats:
        out.append("## Stats")
        out.append("")
        out += stats
        out.append("")
        out.append(
            "Generated by `make stats` into "
            "[../stats/slice_stats.csv](../stats/slice_stats.csv). "
            "Snapshot that file before changing a parser and diff it "
            "after: a change that only renames things must not move a "
            "single number."
        )
        out.append("")

    note = STATE_NOTES.get(directory)
    if note:
        out.append("## About these sources")
        out.append("")
        out.append(note.strip())
        out.append("")

    out.append("## Provenance")
    out.append("")
    out.append(
        "Every row carries `source_path` and `source_page` — the "
        "document it was read from and the page within it. The "
        "documents are committed here, so any row can be checked "
        "against the page it came from without a network round trip. "
        "That mattered repeatedly: nearly every parser bug in this "
        "repository produced plausible wrong values rather than an "
        "error, and opening the page was the only way to settle it."
    )
    out.append("")
    if missing:
        out.append(
            f"⚠️ {len(missing)} cited "
            f"{'document is' if len(missing) == 1 else 'documents are'} "
            f"not on disk: `{missing[0]}`"
            + ("" if len(missing) == 1 else " and others")
        )
    else:
        out.append(f"All {len(cited)} cited documents are present.")
    out.append("")
    if kinds:
        described = ", ".join(f"{n} {k}" for k, n in kinds.most_common())
        out.append(
            f"Inventory for this directory: {described}"
            + (f", {pages:,} pages total." if pages else ".")
        )
        out.append("")

    if uncited:
        groups = collections.Counter(
            str((ROOT / path).relative_to(DATA / directory).parent) for path in uncited
        )
        out.append("## Acquired sources outside the parsed slices")
        out.append("")
        out.append(
            "These held PDFs are not cited by any parsed row. A source "
            "series remains distinct from the state-level status, so "
            "parsed work in one year or government level cannot hide "
            "unparsed holdings in another."
        )
        out.append("")
        for group, count in sorted(groups.items()):
            out.append(f"- `{group}`: {count} PDF{'s' if count != 1 else ''}")
        out.append("")
        series = render_source_series(directory)
        if series:
            out += series
            out.append("")

    out.append("## Reproducing")
    out.append("")
    out.append("```")
    out.append(f"make {MAKE_TARGET.get(directory, directory)}")
    out.append("```")
    out.append("")
    out.append(
        f"Parses from the committed documents and rewrites the files "
        f"above, then runs `src/local_reservations/states/{directory}/validate.py`."
    )
    out.append("")

    grid = render_checks(state)
    checks = STATE_CHECKS.get(directory)
    out.append("## What is checked")
    out.append("")
    out.append(
        "Every state runs a shared battery first — the seat key is "
        "unique, the reservation label agrees with the two fields it "
        "summarises, every `source_path` exists and every "
        "`source_page` falls inside its document. Then this state's own "
        "checks, which are the ones that catch silent corruption "
        "because they appeal to something outside the data:"
    )
    out.append("")
    for check in checks or ["—"]:
        out.append(f"- {check}")
    out.append("")
    if grid:
        out.append("")
        out += grid
        out.append("")
        out.append(
            "Each check declares what it **appeals to**. Only an "
            "external appeal - a published total, a statutory share, a "
            "population - reliably catches silent corruption; an "
            "internal check confirms the file agrees with itself, which "
            "it does whether or not a category was misread."
        )
        out.append("")
    out.append(
        "Column meanings are in [../../DICTIONARY.md](../../DICTIONARY.md). "
        "Expectation violations across every state are triaged into "
        "[../expectations_report.csv](../expectations_report.csv)."
    )
    return "\n".join(out) + "\n"


def render_sibling(directory, state, years, tiers, url, standardized, remaining):
    """A state parsed in its own repository. What sits here is the source
    material it was parsed from, which is worth saying plainly - the directory
    otherwise looks like a state nobody has got to yet.
    """
    kinds, pages = raw_inventory(directory)
    files = source_files(directory)
    name = url.rsplit("/", 1)[-1]
    out = [f"# {state} — local body reservation", ""]
    out.append(
        "*Generated by `make state-readmes`. Edits here are overwritten "
        "— change the data or the generator instead.*"
    )
    out.append("")
    out.append(
        f"**The parsed data for {state} is in "
        f"[{name}]({url})** — {tiers}, {years}. It was split into its "
        f"own repository, so it is counted in the [top-level "
        f"readme](../../README.md) but has no rows here."
    )
    out.append("")
    if files:
        out.append(
            f"What is in this directory is source material: {len(files)} "
            f"{'file' if len(files) == 1 else 'files'}"
            + (
                f", {', '.join(f'{n} {k}' for k, n in kinds.most_common())}"
                + (f", {pages:,} pages" if pages else "")
                if kinds
                else ""
            )
            + "."
        )
    else:
        out.append(
            "Source documents and historical tables are maintained in "
            f"[{name}]({url}). "
            "This directory keeps no duplicate inputs."
        )
    out.append("")
    out.append(
        "The pooled adapter reads the sibling's declared parsed files into "
        "the shared seat and candidate schemas. Files held only in this local "
        "source directory do not enter that adapter automatically."
    )
    if standardized:
        out.append("")
        out.append(f"**Pooled outputs:** {standardized}.")
    if remaining and remaining != "see sibling repository":
        out.append("")
        out.append(f"**Remaining work:** {remaining}.")
    return "\n".join(out) + "\n"


def render_unparsed(directory, state, status, where):
    kinds, pages = raw_inventory(directory)
    files = source_files(directory)
    out = [f"# {state} — local body reservation", ""]
    out.append(
        "*Generated by `make state-readmes`. Edits here are overwritten "
        "— change the data or the generator instead.*"
    )
    out.append("")
    out.append(
        f"**Status: {status}.** Nothing in this directory is in the "
        f"repository's schema yet, so it does not appear in the "
        f"per-slice table in the [top-level readme](../../README.md)."
    )
    out.append("")
    if status == "tables, other layout":
        out.append(
            "The documents or tables are here and nobody has parsed "
            "them into this repository's schema yet. This is open work, "
            "not coverage already achieved - a distinction the old label "
            '"prior work, other schema" blurred, which is how '
            "Rajasthan sat here for months while its parse existed in "
            "another repository."
        )
        out.append("")
        if where:
            out.append(f"Recorded years: {where}.")
            out.append("")
    out.append(f"{len(files)} {'file' if len(files) == 1 else 'files'} on disk.")
    if kinds:
        described = ", ".join(f"{n} {k}" for k, n in kinds.most_common())
        out.append("")
        out.append(
            f"Inventory: {described}" + (f", {pages:,} pages total." if pages else ".")
        )
    series = render_source_series(directory)
    if series:
        out.append("")
        out.append("## Source series")
        out.append("")
        out += series
    out.append("")
    out.append("## What it would take")
    out.append("")
    out.append(
        "See [../../SOURCES.md](../../SOURCES.md) for where this state "
        "publishes its reservation data and what parsing it involves. "
        "A parser lands in `src/local_reservations/states/<state>/parse.py`, writes through "  # noqa: E501
        "`local_reservations/common/emit.py` so every row carries its source "
        "document and page, and is paired with a `validate.py` that "
        "checks the result against something outside the data — a "
        "published total, a statutory share, a population."
    )
    return "\n".join(out) + "\n"


def render_tn():
    """Summarize nested office exports without registering pooled seat rows."""
    directory = DATA / "tn"
    office_path = "derived/heads_2011/gp_president_reservations.csv"
    operations_path = "derived/amendments_2001/gp_president_amendment_operations.csv"
    with (directory / office_path).open(encoding="utf-8", newline="") as source:
        offices = list(csv.DictReader(source))
    with (directory / operations_path).open(encoding="utf-8", newline="") as source:
        operations = list(csv.DictReader(source))
    districts = {row["district"] for row in offices if row["district"]}
    unions = {(row["district"], row["union_key"]) for row in offices}
    unknown = sum(not row["reservation"].strip() for row in offices)
    operation_counts = collections.Counter(row["operation_type"] for row in operations)
    out = [
        "# Tamil Nadu — GP-president reservation sources",
        "",
        "*Generated by `make state-readmes`. Edit the generator or source-specific "
        "guides; this overview is overwritten.*",
        "",
        "These nested exports retain their source units and are separate from "
        "the pooled seat-event schema. They record office reservations and "
        "amendment instructions, not observed presidents or their sex.",
        "",
        "| Source | Row unit | Rows | Guide |",
        "|---|---|---:|---|",
        f"| [2011 CSV]({office_path}) | Named GP-president roster entry | "
        f"{len(offices):,} | [2011 source guide](derived/heads_2011/README.md) |",
        f"| [2001 CSV]({operations_path}) | Amendment operation | "
        f"{len(operations):,} | "
        "[2001 source guide](derived/amendments_2001/README.md) |",
        "",
        f"The 2011 roster covers {len(districts):,} printed districts and "
        f"{len(unions):,} district/union identities. {unknown:,} reservation "
        "cell(s) are blank and remain unknown. Explicit General categories "
        "are retained; no category is inferred from nonlisting.",
        "",
        "The 2001 operations comprise "
        + ", ".join(
            f"{count:,} `{operation}`"
            for operation, count in sorted(operation_counts.items())
        )
        + ". Operations are not a complete GP roster or a count of unique GPs. "
        "They must not be appended to the 2011 roster as additional offices.",
        "",
        "Both guides describe identifiers, source pages, raw readings, "
        "typed exports, verification and remaining uncertainty. Counts here "
        "are read from the two CSV exports each time the overview is generated.",
        "",
        "Original rural gazettes and the historical search are recorded in the "
        "[early-source ledger](../source_search/early_heads/README.md). "
        "[Scan review](derived/scans/review.md) preserves OCR limitations. "
        "Earlier scans and later amendments do not automatically establish "
        "reservation histories or election outcomes.",
        "",
        "[Urban Tamil Nadu holdings](../tamil_nadu/readme.md) are maintained "
        "in their existing directory.",
        "",
    ]
    return "\n".join(out)


def render_delhi():
    """Describe the election-specific winner handoff from its coverage file."""
    with (DATA / "delhi/release/coverage.csv").open(newline="") as source:
        rows = list(csv.DictReader(source))
    out = [
        "# Delhi — municipal winner qualifications",
        "",
        "*Generated by `make state-readmes`. Edit the generator or data.*",
        "",
        "[Winner Parquet](release/winners.parquet) contains one elected ward per year, "
        "with reservation, assembly constituency, education, age and pending cases. "
        "This supplementary winner release is separate from the "
        "pooled seat-event schema.",
        "",
        "| Election | Winners | Linked profiles | Education category "
        "present | Age | Pending cases |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    out.extend(
        "| "
        + " | ".join(
            row[key]
            for key in [
                "year",
                "winners",
                "linked_profiles",
                "education",
                "age",
                "cases",
            ]
        )
        + " |"
        for row in rows
    )
    out += [
        "",
        "Education coverage counts any nonempty source category, including unspecified "
        "categories. Analytical classification can therefore have a "
        "smaller denominator. "
        "Missing profiles remain unknown; conviction tables are "
        "excluded from pending cases.",
        "",
        "Goyal's replication deposit supplies the 2012/2017 winner "
        "rosters and assembly "
        "mapping. OpenCity/Lok Dhaba supplies 2022 winners; the SEC gazette supplies "
        "2022 reservation and assembly identifiers. Individual MyNeta profiles supply "
        "qualifications. Joins require unique year/ward keys and "
        "matching winner parties.",
        "",
        "Run `make delhi` to rebuild offline and `make delhi-harvest`"
        " to resume collection. "
        "[Sources](release/source_manifest.json), [dictionary](release/schema.json), "
        "[release hashes](release/manifest.json), "
        "[profile cache manifest](qualification_audit/fetch_manifest.csv) and "
        "[winner matching audit](release/winner_source_audit.parquet)"
        " retain provenance. "
        "The paper in `quota_elite_quality` reads this typed handoff.",
        "",
    ]
    return "\n".join(out)


def build():
    """Return {path: text} for every state directory."""
    entries = slices_by_directory()
    legacy = {d: (state, years) for state, (years, d) in coverage.LEGACY.items()}
    siblings = {
        state: (
            spec["years"],
            spec["tiers"],
            f"https://github.com/in-rolls/{spec['repo']}",
            spec.get("standardized", ""),
            spec.get("remaining", ""),
        )
        for state, spec in coverage.SIBLINGS.items()
    }

    out = {}
    for directory in sorted(
        p.name for p in DATA.iterdir() if p.is_dir() and p.name not in datasets.DERIVED
    ):
        state = coverage.pretty(directory)
        target = DATA / directory / "readme.md"
        if directory == "delhi":
            out[target] = render_delhi()
        elif directory == "tn":
            out[target] = render_tn()
        elif directory in entries:
            out[target] = render_parsed(directory, state, entries[directory])
        elif directory in legacy:
            name, years = legacy[directory]
            out[target] = render_unparsed(
                directory, name, "tables, other layout", years
            )
        elif state in siblings:
            years, tiers, url, standardized, remaining = siblings[state]
            out[target] = render_sibling(
                directory, state, years, tiers, url, standardized, remaining
            )
        else:
            out[target] = render_unparsed(directory, state, "documents, no parser", "")
    return out


@command("document", artifact="state_readmes")
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--check",
        action="store_true",
        help="fail if any file differs from what would be written",
    )
    args = ap.parse_args()

    written = build()
    stale = []
    for path, text in sorted(written.items()):
        current = path.read_text(encoding="utf-8") if path.exists() else None
        if current == text:
            continue
        stale.append(path.relative_to(ROOT))
        if not args.check:
            path.write_text(text, encoding="utf-8")

    if args.check:
        if stale:
            print(f"{len(stale)} state readme(s) out of date:")
            for path in stale:
                print(f"   {path}")
            return 1
        print(f"  {len(written)} state readmes up to date")
        return 0

    print(f"wrote {len(stale)} of {len(written)} state readmes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
