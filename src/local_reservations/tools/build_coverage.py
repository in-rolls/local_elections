"""Generate the coverage table in README.md, and check that its links work.

The readme is the index of record for this whole family of repos, and it has
drifted twice already: Haryana sat blank after being built, `data/karnatka/` was
a typo nobody caught, and ten states had raw documents on disk while their rows
said nothing. A hand-maintained index will drift again, so it is generated.

Three sources feed it:

  * **parsed datasets** in `data/<state>/`, identified by their columns rather
    than their filenames - `jharkhand data 2010_reservation_pop_for web.csv` is
    a pre-existing file that matches any sensible filename glob but is not one
    of ours;
  * **raw holdings** from `data/inventory.csv`, so a state with documents but no
    parser reads "raw, unparsed" instead of looking empty;
  * **sibling repos**, for the states that were split out.

Every link is verified: relative paths must exist on disk and http(s) links must
answer 2xx (Harvard Dataverse answers its landing pages with 202). `--check`
exits non-zero on a dead link, so this can gate the index the same way the
validate scripts gate the data.
"""

import argparse
import collections
import csv
import gzip
import re
import sys

import pyarrow.parquet as pq

from local_reservations.paths import ROOT
from local_reservations.states.assam import controls_2025 as assam_controls

DATA = ROOT / "data"
README = ROOT / "README.md"

START, END = "<!-- coverage:start -->", "<!-- coverage:end -->"
SLICE_START, SLICE_END = "<!-- slices:start -->", "<!-- slices:end -->"

from local_reservations.common import (  # noqa: E402 - after DATA, which it needs
    datasets,
    fetch,
    reference,
)
from local_reservations.common.runlog import command  # noqa: E402

# States split into their own repositories.
# States parsed in a repository of their own, with the files that hold the
# parse. The files are named rather than globbed: summing every CSV in a repo
# counted Haryana's download manifest as 187 seats, and would have counted
# quota_raj's copy of Uttar Pradesh - which is byte-identical to
# local_elections_up - as a second Uttar Pradesh.
SIBLINGS = {
    "Haryana": {
        "repo": "local_elections_haryana",
        "years": "2016, 2022",
        "tiers": "gp_head, gp_ward",
        "files": [
            "data/2016/gp_reservation.csv",
            "data/2016/ward_reservation.csv",
            "data/2022/gp_reservation.csv",
            "data/2022/ward_reservation.csv",
        ],
    },
    "Bihar": {
        "repo": "local_elections_bihar",
        "years": "2016, 2021",
        "tiers": "gp_head, gp_ward, block_member, zp_member, kachahari_head, kachahari_member",  # noqa: E501
        "remaining": "2021 mukhiya education and dated reservation linkage incomplete",
        "files": [
            "data/mukhiya.csv",
            "data/release/2021/gp_head_candidates_2021.parquet",
            "data/ward_member.csv",
            "data/sarpanch.csv",
            "data/panch.csv",
            "data/panchayat_samiti_member.csv",
            "data/zila_parishad_member.csv",
        ],
    },
    "Kerala": {
        "repo": "local_elections_kerala",
        "years": "2010, 2015, 2020",
        "tiers": "gp_ward, block_member, zp_member, ulb_ward",
        "files": ["data/lsgi-election-kerala.csv"],
    },
    "Uttar Pradesh": {
        "repo": "local_elections_up",
        "years": "2005, 2010, 2015, 2021",
        "tiers": "gp_head",
        "files": [
            "data/fin/up_gp_sarpanch_2005_fixed_with_transliteration.parquet",
            "data/fin/up_gp_sarpanch_2010_fixed_with_transliteration.parquet",
            "data/fin/up_gp_sarpanch_2015_fixed_with_transliteration.parquet",
            "data/fin/up_gp_sarpanch_2021_fixed_with_transliteration.parquet",
        ],
    },
    "Uttarakhand": {
        "repo": "local_elections_uttarakhand",
        "years": "2008, 2014, 2019",
        "tiers": "gp_head, block_member, zp_member",
        "files": [
            "data/uttarakhand-panchayat-elections.csv",
            "data/uttarakhand-panchayat-elections-haridwar.csv",
        ],
    },
    # The standardized rural panels live with the state's election data;
    # caste_category and female_reserved are already separate columns.
    "Rajasthan": {
        "repo": "local_elections_rajasthan",
        "years": "2005, 2010, 2015, 2020, 2021, 2022",
        "tiers": "gp_head, gp_ward, block_member, zp_member",
        "files": [
            "data/fin/panchayat_samiti_2005_std.parquet",
            "data/fin/panchayat_samiti_2010_std.parquet",
            "data/fin/zila_parishad_2005_std.parquet",
            "data/fin/zila_parishad_2010_std.parquet",
            "data/fin/source_2005_std.parquet",
            "data/fin/source_2010_std.parquet",
            "data/fin/source_2015_std.parquet",
            "data/fin/source_2020_std.parquet",
            "data/ContestingSarpanch.csv.gz",
            "data/WinnerSarpanch.csv.gz",
            "data/WarnWinningPanch.csv.gz",
            "data/StatsNomination.csv.gz",
        ],
        "standardized": "162,502 rural seat events, 68,202 candidates, and "
        "13,473 GP-event nomination summaries are standardized",
        "remaining": "the 2015 Panchayat Samiti book and the 2015 and 2020 "
        "Zila Parishad books remain unparsed; municipal material is held "
        "outside the rural master",
    },
}

# Held here, in someone else's column layout, and nobody has parsed it. This is
# a different thing from SIBLINGS and must not share a label with it: these are
# open work, not coverage already achieved.
LEGACY = {
    "Telangana": ("gram panchayat + ward 2019, municipal 2020-21", "telangana"),
    "West Bengal": ("2018 delimitation-and-reservation gazettes, 20 districts", "wb"),
    "Karnataka": ("gram panchayat head, 1993/2000/2002/2005/2007", "karnataka"),
}

# Urban local bodies only. Not a gap in rural coverage and not open work here -
# the Trivedi Centre holds urban material, and the master is being landed for
# panchayati raj first. Kept visible so "nothing for Maharashtra" is not read as
# "nothing acquired".
URBAN_ONLY = {
    "NCT of Delhi": ("2007, 2012, 2017", "delhi"),
}

# Directory name in data/ -> printed state name.
DIRECTORY_NAMES = {
    "ap": "Andhra Pradesh",
    "jk": "Jammu & Kashmir",
    "wb": "West Bengal",
    "up": "Uttar Pradesh",
    "madhya_pradesh": "Madhya Pradesh",
    "tamil_nadu": "Tamil Nadu",
    "tn": "Tamil Nadu",
    "delhi": "NCT of Delhi",
    "himachal": "Himachal Pradesh",
}

# States with no panchayati raj reservation to collect. Recording why is
# information, not an admission of a gap.
NO_PRI = {
    "Meghalaya": "Sixth Schedule - autonomous district councils, no PRI",
    "Mizoram": "Sixth Schedule - village councils, no PRI",
    "Nagaland": "Article 371A - village councils, no PRI",
}

# A held PDF that is not cited by a parsed row is not automatically missing
# data. It may be an unparsed source series, a draft superseded by a final
# order, an urban document, or a second statement of a seat already parsed.
# Inventory can count those files but cannot decide which case applies, so the
# evidence-backed classification lives here and is printed beside the count.
REMAINING_WORK = {
    "Maharashtra": (
        "Mumbai only: the 1997, 2002 and 2007 BMC councils lack a seat-reservation "
        "roster (2007 has the women's flag as a supplemental file); the ~28,000 "
        "rural gram panchayats are absent entirely"
    ),
    "Andhra Pradesh": (
        "all 13 GP district gazettes are held; 8 are parsed and 5 remain "
        "unparsed; 32 held PDFs cover MPTC, ZPTC, MPP, and MPL tiers and "
        "remain unparsed"
    ),
    "Assam": (
        f"{assam_controls.UNPARSED_DISTRICT_NOTIFICATIONS} held 2025 district "
        "PRI scans remain unparsed"
    ),
    "Chandigarh": (
        "5 held municipal and election-report PDFs need a rural-scope review"
    ),
    "Goa": (
        "the 2017 and 2022 rosters are incomplete; 10 held cycle files are "
        "not linked to parsed rows"
    ),
    "Himachal Pradesh": "1 held scan needs a seat-level scope review and OCR",
    "Jammu & Kashmir": (
        "2016 is parsed from all 25 held PDFs; 13 files from 2010 and 2018 "
        "produce no rows"
    ),
    "Jharkhand": (
        "GP-ward and ZP coverage reaches 11 of 24 districts; 29 rural and 3 "
        "municipal PDFs are not linked to parsed rows"
    ),
    "Karnataka": (
        "244 of 248 unlinked PDFs were reviewed as duplicate reservation "
        "statements or aggregate forms, not missing seats; 4 produce no rows"
    ),
    "Madhya Pradesh": "2 held scans need a seat-level scope review and OCR",
    "Odisha": (
        "the 6 held PDFs are district aggregates, not seat rosters; acquire "
        "seat-level rural data"
    ),
    "Puducherry": (
        "the 2021 panchayat notification is a 60-page scan that needs OCR; "
        "the other held notification is municipal"
    ),
    "Tamil Nadu": (
        "2011 GP-president roster and 2001 amendment operations have separate "
        "source-specific exports; review earlier scans and subsequent amendments; "
        "observed GP-president sex remains unavailable"
    ),
    "Telangana": (
        "the 4 unlinked PDFs are urban reservation orders or election manuals, "
        "not missing rural seats"
    ),
    "West Bengal": (
        "Separate 1998–2023 GP office, ward and results data have source-linked "
        "parsers and review queues ([GP data](data/wb/derived/README.md)); "
        "the final 2018 ZP gazettes "
        "are parsed, while their 19 drafts are not additional final seats"
    ),
}

ALL_STATES = [
    "Andaman & Nicobar Islands",
    "Andhra Pradesh",
    "Arunachal Pradesh",
    "Assam",
    "Bihar",
    "Chandigarh",
    "Chhattisgarh",
    "Dadra & Nagar Haveli and Daman & Diu",
    "Goa",
    "Gujarat",
    "Haryana",
    "Himachal Pradesh",
    "Jammu & Kashmir",
    "Jharkhand",
    "Karnataka",
    "Kerala",
    "Ladakh",
    "Lakshadweep",
    "Madhya Pradesh",
    "Maharashtra",
    "Manipur",
    "Meghalaya",
    "Mizoram",
    "Nagaland",
    "NCT of Delhi",
    "Odisha",
    "Puducherry",
    "Punjab",
    "Rajasthan",
    "Sikkim",
    "Tamil Nadu",
    "Telangana",
    "Tripura",
    "Uttar Pradesh",
    "Uttarakhand",
    "West Bengal",
]


def pretty(directory):
    return DIRECTORY_NAMES.get(directory, directory.replace("_", " ").title())


def unmapped_directories():
    """Directories under data/ whose name does not resolve to a state.

    A directory that fails to map is not an error anywhere - it simply never
    matches, and the state is reported as "not held" while its documents sit on
    disk. That is what happened to Himachal: pretty("himachal") is "Himachal",
    the state is listed as "Himachal Pradesh", and una_2020.pdf was reported as
    nothing acquired. Checked rather than assumed, because the failure is
    silent by construction.
    """
    names = {p.name for p in DATA.iterdir() if p.is_dir()}
    names |= set(raw_holdings())
    # derived output is not a state, and datasets.py is the one place that says so
    names -= datasets.DERIVED
    return sorted(n for n in names if pretty(n) not in ALL_STATES)


def parsed_datasets():
    """Every CSV in data/ that carries our schema, keyed by state name."""
    found = collections.defaultdict(
        lambda: {"years": set(), "tiers": set(), "rows": 0, "dir": None}
    )
    for path, rows in datasets.parsed():
        state = rows[0]["state"] or pretty(path.parent.name)
        entry = found[state]
        entry["dir"] = path.parent.name
        entry["rows"] += len(rows)
        entry["years"] |= {r["year"] for r in rows if r["year"]}
        entry["tiers"] |= {r["tier"] for r in rows if r["tier"]}
    return found


def raw_holdings():
    """States with source documents but no parsed output yet."""
    path = DATA / "inventory.csv"
    if not path.exists():
        return {}
    holdings = collections.defaultdict(lambda: collections.Counter())
    with path.open(encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            holdings[row["state"]][row["format"]] += 1
    return holdings


def unlinked_source_pdfs():
    """Held PDFs not linked from any parsed row, keyed by state directory."""
    inventory = DATA / "inventory.csv"
    if not inventory.exists():
        return {}
    cited = collections.defaultdict(set)
    for path, rows in datasets.parsed():
        cited[path.parent.name] |= {
            row.get("source_path", "") for row in rows if row.get("source_path")
        }
    held = collections.defaultdict(set)
    with inventory.open(encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            if row.get("kind") == "pdf":
                held[row["state"]].add(f"data/{row['path']}")
    return {
        directory: paths - cited.get(directory, set())
        for directory, paths in held.items()
        if paths - cited.get(directory, set())
    }


def sibling_rows(spec):
    """Count the rows in a sibling's named parse files.

    Only the declared files, never a glob: summing every CSV in a repository
    counted Haryana's 187-row download manifest as seats, and would have counted
    quota_raj's byte-identical copy of Uttar Pradesh as a second Uttar Pradesh.

    CSV files are counted as records rather than lines, and Parquet files are
    counted from their footer metadata without loading their columns.
    """
    directory = ROOT.parent / spec["repo"]
    if not directory.exists():
        return "-"
    total, missing = 0, 0
    for relative in spec["files"]:
        path = directory / relative
        if not path.exists():
            missing += 1
            continue
        if path.suffix == ".parquet":
            total += pq.read_metadata(path).num_rows
        elif path.suffix == ".csv" or path.name.endswith(".csv.gz"):
            # Records, not lines. Bihar's addresses contain embedded newlines,
            # so counting lines reported 692,314 where the six files hold
            # 645,605 records, a 7% overstatement printed as a fact.
            csv.field_size_limit(10**7)
            opener = gzip.open if path.name.endswith(".gz") else open
            with opener(
                path,
                "rt",
                encoding="utf-8",
                errors="replace",
                newline="",
            ) as fh:
                total += max(sum(1 for _ in csv.reader(fh)) - 1, 0)
        else:
            raise RuntimeError(f"unsupported sibling data file: {path}")
    note = f"{missing} missing file{'s' if missing != 1 else ''}" if missing else ""
    if not total:
        return note or "0"
    return f"{total:,}" + (f" + {note}" if note else "")


def build_rows():
    parsed = parsed_datasets()
    raw = raw_holdings()
    unlinked = unlinked_source_pdfs()
    by_directory = {v["dir"]: k for k, v in parsed.items() if v["dir"]}

    table = []
    for state in ALL_STATES:
        if state in parsed:
            entry = parsed[state]
            extra = len(unlinked.get(entry["dir"], ()))
            remaining = REMAINING_WORK.get(state, "—")
            if extra and state not in REMAINING_WORK:
                remaining = (
                    f"{extra} held PDFs are not linked to parsed rows; "
                    "see the state readme"
                )
            table.append(
                (
                    state,
                    ", ".join(sorted(entry["tiers"])),
                    ", ".join(sorted(entry["years"])),
                    f"{entry['rows']:,}",
                    "parsed",
                    remaining,
                    f"[data/{entry['dir']}/](data/{entry['dir']}/)",
                )
            )
            continue
        if state in SIBLINGS:
            spec = SIBLINGS[state]
            url = f"https://github.com/in-rolls/{spec['repo']}"
            table.append(
                (
                    state,
                    spec["tiers"],
                    spec["years"],
                    sibling_rows(spec),
                    "parsed",
                    "; ".join(
                        part
                        for part in (
                            spec.get("standardized", ""),
                            spec.get("remaining", "see sibling repository"),
                        )
                        if part
                    ),
                    f"[{spec['repo']}]({url})",
                )
            )
            continue
        if state in LEGACY:
            years, directory = LEGACY[state]
            table.append(
                (
                    state,
                    "-",
                    years,
                    "-",
                    "tables, other layout",
                    "parse the held tables into the common schema",
                    f"[data/{directory}/](data/{directory}/)",
                )
            )
            continue
        if state in URBAN_ONLY:
            years, directory = URBAN_ONLY[state]
            table.append(
                (
                    state,
                    "`ulb_ward`",
                    years,
                    "-",
                    "urban only",
                    "rural data are not held here",
                    f"[data/{directory}/](data/{directory}/)",
                )
            )
            continue
        if state in NO_PRI:
            table.append(
                (state, "-", "-", "-", "not applicable", "none", NO_PRI[state])
            )
            continue

        if state == "Tamil Nadu":
            exports = {
                "2001": "amendments_2001/gp_president_amendment_operations.csv",
                "2011": "heads_2011/gp_president_reservations.csv",
            }
            years = [
                year
                for year, path in exports.items()
                if (DATA / "tn/derived" / path).is_file()
            ]
            if years:
                table.append(
                    (
                        state,
                        "GP-president office / amendment operation",
                        ", ".join(years),
                        "-",
                        "source-specific exports",
                        REMAINING_WORK[state],
                        "[data/tn/](data/tn/); separate from pooled schema",
                    )
                )
                continue

        directory = next(
            (d for d in raw if pretty(d) == state and d not in by_directory), None
        )
        if directory:
            counts = raw[directory]
            text = ", ".join(
                f"{n} {k}"
                for k, n in counts.most_common()
                if k in ("digital-text", "scan", "encoded-text", "mixed", "tabular")
            )
            table.append(
                (
                    state,
                    "-",
                    "-",
                    "-",
                    "no parsed rows",
                    REMAINING_WORK.get(
                        state, "review the held documents and parse any seat rosters"
                    ),
                    f"[data/{directory}/](data/{directory}/) - {text}",
                )
            )
        else:
            table.append(
                (
                    state,
                    "-",
                    "-",
                    "-",
                    "not held",
                    "acquire and assess a seat-level rural source",
                    "-",
                )
            )
    return table


def slices():
    """One entry per state x year x tier - the grain the data actually has.

    The state-level table collapses years into a cell, which reads as though
    Goa's three cycles are comparable. They are not: 2012 is complete and names
    the winner, while 2017 and 2022 are partial nomination lists. Splitting by
    slice puts the caveat next to the number.
    """
    grouped = collections.defaultdict(list)
    directory_of = {}
    for path, rows in datasets.parsed():
        for row in rows:
            key = (row.get("state", ""), row.get("year", ""), row.get("tier", ""))
            grouped[key].append(row)
            directory_of[key] = path.parent.name

    out = []
    for (state, year, tier), rows in sorted(grouped.items()):
        total = len(rows)
        women = sum(1 for r in rows if str(r.get("woman_reserved")) == "1")
        districts = {
            r.get("district") for r in rows if (r.get("district") or "").strip()
        }
        out.append(
            {
                "state": state,
                "year": year,
                "tier": tier,
                "rows": total,
                "women": 100.0 * women / max(total, 1),
                "districts": len(districts),
                "coverage": _coverage(state, year, tier, rows),
                "notes": "; ".join(_notes(state, year, tier, rows, len(districts))),
                "dir": directory_of[(state, year, tier)],
            }
        )
    return out


def _coverage(state, year, tier, rows):
    """Rows against a published total, comparing like with like."""
    spec = reference.published(state, year, tier)
    total = spec.get("total")
    if not total:
        return "—"
    counted = rows
    if spec.get("basis") == "elected":
        # an "elected" figure excludes seats nobody holds
        counted = [r for r in rows if str(r.get("vacant", "")) != "1"]

    # Compare like with like. Goa's 186 counts *panchayats*, and the rows are
    # wards - dividing one by the other reported 797% coverage, which is the
    # same unit error that once made Haryana 2016 look like a 102% over-count.
    unit = spec.get("unit", "seats")
    if unit == "panchayats":
        n = len({(r.get("block"), r.get("gram_panchayat")) for r in counted})
    else:
        n = len(counted)
    return f"{100.0 * n / total:.0f}% of {total:,} {unit}"


def _notes(state, year, tier, rows, districts):
    """Caveats derived from the rows, so they cannot go stale."""
    notes = []
    if not any((r.get("winner") or "").strip() for r in rows):
        notes.append("no winner published")
    if rows and rows[0].get("listing_scope") == "reserved_only":
        notes.append(
            "**reserved seats only** — shares are a property of the "
            "document, not of the state"
        )
    if rows and rows[0].get("script") == "krutidev":
        notes.append("place names not transliterated")

    expected = reference.districts_expected(state, year)
    if expected and districts and districts < expected:
        notes.append(f"partial: {districts} of {expected} districts")

    flags = [r.get("ward_list_complete") for r in rows]
    known = [f for f in flags if f in ("0", "1")]
    if known and len(known) > 0.1 * len(rows):
        share = 100.0 * sum(1 for f in known if f == "1") / len(known)
        notes.append(f"ward list complete for {share:.0f}% of rows with a stated count")
    # the full reasoning, and what would close each gap, lives in WORKLIST.md
    return notes


def render_slices(entries):
    head = (
        "| State | Year | Tier | Rows | Women | Districts | vs published | "
        "Notes | Where |\n|---|---|---|---|---|---|---|---|---|\n"
    )
    body = ""
    for e in entries:
        body += (
            f"| {e['state']} | {e['year']} | `{e['tier']}` | "
            f"{e['rows']:,} | {e['women']:.0f}% | {e['districts']} | "
            f"{e['coverage']} | {e['notes'] or '—'} | "
            f"[data/{e['dir']}/](data/{e['dir']}/) |\n"
        )
    return head + body


def render(table):
    head = (
        "| State | Tier | Years | Rows | Coverage | Remaining work | Where |\n"
        "|---|---|---|---|---|---|---|\n"
    )
    body = "".join("| " + " | ".join(cells) + " |\n" for cells in table)
    return head + body


def links_in(text):
    return re.findall(r"\[[^\]]*\]\(([^)]+)\)", text)


def check_links(text, base=None):
    """Relative paths must exist; http(s) links must answer 200.

    `base` is the directory the links are written relative to - the state
    readmes live a level down, so their `../../SOURCES.md` resolves against
    data/<state>/ and not against the repository root.

    A request that could not be answered is **not** reported as a dead link.
    It used to be: any exception became one, so a rate limit or a timeout read
    as "the state took its gazette down". Those come back as `unanswered` and
    are the caller's to weigh, because a link this run could not check is not
    the same as a link that is gone.
    """
    base = base or ROOT
    dead, unanswered = [], []
    for target in sorted(set(links_in(text))):
        if target.startswith(("http://", "https://")):
            try:
                response = fetch.probe(target, timeout=30)
            except fetch.Unanswered as exc:
                unanswered.append((target, str(exc)))
                continue
            if not 200 <= response.status_code < 300:
                dead.append((target, response.status_code))
        else:
            if not (base / target).resolve().exists():
                dead.append((target, "missing on disk"))
    return dead, unanswered


@command("document", artifact="coverage")
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--check",
        action="store_true",
        help="verify links and exit non-zero if any is dead",
    )
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="print the table without writing README.md",
    )
    args = ap.parse_args()

    unmapped = unmapped_directories()
    if unmapped:
        print(f"  directories that map to no state: {unmapped}")

    table = build_rows()
    rendered = render(table)
    entries = slices()
    rendered_slices = render_slices(entries)

    if args.dry_run:
        print(rendered_slices)
        print(rendered)
    else:
        text = README.read_text(encoding="utf-8")
        for start, end, block_body in (
            (SLICE_START, SLICE_END, rendered_slices),
            (START, END, rendered),
        ):
            block = f"{start}\n\n{block_body}\n{end}"
            if start in text and end in text:
                text = re.sub(
                    re.escape(start) + r".*?" + re.escape(end), block, text, flags=re.S
                )
            else:
                text = text.rstrip() + "\n\n" + block + "\n"
        README.write_text(text, encoding="utf-8")
        print(f"wrote {README} ({len(entries)} slices, {len(table)} states)")

    status = collections.Counter(row[4] for row in table)
    print("  " + "  ".join(f"{k}={v}" for k, v in status.most_common()))

    if args.check:
        dead, unanswered = check_links(README.read_text(encoding="utf-8"))
        for path in sorted(DATA.glob("*/readme.md")):
            more_dead, more_unanswered = check_links(
                path.read_text(encoding="utf-8"), path.parent
            )
            label = path.parent.name
            dead += [(f"{label}/{t}", why) for t, why in more_dead]
            unanswered += [(f"{label}/{t}", why) for t, why in more_unanswered]
        if unanswered:
            # not a failure: a link we could not check is not a link that is
            # gone, and calling it one would put a state's gazette on the
            # dead list because we were asking too fast
            print(f"\n{len(unanswered)} link(s) could not be checked:")
            for target, why in unanswered:
                print(f"   {target}  -> {why}")
        if dead:
            print(f"\n{len(dead)} dead link(s):")
            for target, why in dead:
                print(f"   {target}  -> {why}")
            return 1
        unchecked = f" ({len(unanswered)} unchecked)" if unanswered else ""
        print(f"  all links resolve{unchecked}")
        if unmapped:
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
