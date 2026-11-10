"""Source-checked 2006-to-2011 ward panel; no effect estimation."""

import collections
import csv
import hashlib
import json
import re

import pyarrow as pa
import pyarrow.parquet as pq
from frictionless import Resource, Schema

from local_elections.common.contract import boolean, flag, integer, text

NAME = "ward_panel_2006_2011"
FIELDS = [
    text("body", "Municipal institution; one ward is the row unit.", required=True),
    text("ward_no", "Ward identifier on the unchanged 2006 geography.", required=True),
    integer(
        "prior_year",
        "Prior general-election cohort, including deferred ward 7.",
        required=True,
        enum=[2006],
    ),
    integer("year", "Outcome general election.", required=True, enum=[2011]),
    text(
        "poll_date_2006",
        "Actual prior poll: December 20, 2006, except ward 7 on January 14, 2007.",
        required=True,
    ),
    text("poll_date_2011", "Actual outcome election date.", required=True),
]
for year in (2006, 2011):
    FIELDS.extend(
        [
            flag(
                f"reserved_woman_{year}",
                (
                    "1 for women-only reservation; 0 for a seat open to both sexes. "
                    "Taken from the pre-election notification, checked against "
                    "results."
                ),
            ),
            text(
                f"reserved_caste_{year}",
                "Seat caste reservation; NONE means no caste reservation, not missing.",
                required=True,
                enum=["NONE", "SC"],
            ),
            text(
                f"reserved_raw_{year}",
                (
                    "Original reservation label in the result table, preserved without "
                    "recoding."
                ),
                required=True,
            ),
            integer(
                f"reserved_source_page_{year}",
                (
                    "One-based PDF page of the pre-election reservation notification "
                    "in the corresponding source report."
                ),
                required=True,
            ),
            text(
                f"source_path_{year}",
                (
                    "Original report path relative to repository root; all page "
                    "references for this year refer here."
                ),
                required=True,
            ),
            text(
                f"source_sha256_{year}",
                "SHA-256 of the complete unchanged source report.",
                required=True,
                pattern="[0-9a-f]{64}",
            ),
        ]
    )
FIELDS.extend(
    [
        text(
            "winner_2011",
            "Printed elected-person name, not the prior winner.",
            required=True,
        ),
        integer(
            "winner_source_page_2011",
            "One-based PDF page of elected-person table.",
            required=True,
        ),
        flag(
            "winner_woman_from_honorific_2011",
            (
                "1 from Smt./Ms.; 0 from Sh. in uniquely linked candidate row. No "
                "name- or quota-based inference. Null if title is not "
                "sex-specific; release requires complete outcomes."
            ),
        ),
        text(
            "winner_honorific_raw_2011",
            "Printed candidate honorific; independent of reservation label.",
            required=True,
            enum=["Sh.", "Smt.", "Ms."],
        ),
        text(
            "winner_candidate_name_raw_2011",
            "Full source candidate-name cell, retaining title and parenthetical text.",
            required=True,
        ),
        text(
            "winner_candidate_no_2011",
            (
                "One-based extracted candidate position within ward; not printed "
                "ballot serial."
            ),
            required=True,
        ),
        text(
            "winner_link_basis_2011",
            (
                "Unique normalized name within ward, with reviewed Modgil/Moudgil "
                "alias only in ward 22."
            ),
            required=True,
        ),
        integer(
            "winner_woman_source_page_2011",
            "One-based PDF page of separately printed candidate honorific.",
            required=True,
        ),
        boolean(
            "is_eligible",
            (
                "True for 2011 seats open to both sexes, including SC seats. No "
                "restriction on winner sex."
            ),
            required=True,
        ),
        text(
            "exclusion_reason",
            "included or reserved_for_women_in_2011.",
            required=True,
            enum=["included", "reserved_for_women_in_2011"],
        ),
        text(
            "caste_transition",
            (
                "Prior-to-current seat caste stratum, e.g. SC_to_NONE. Fixed by "
                "census rankings rather than women's lottery."
            ),
            required=True,
        ),
        integer(
            "population_2001",
            (
                "Total persons from the Deputy Commissioner's 2001 Census ward "
                "figures, reproduced in the 2011 report."
            ),
            required=True,
            minimum=1,
        ),
        integer(
            "population_sc_2001",
            "Scheduled Caste persons from the same table.",
            required=True,
            minimum=0,
        ),
        {
            "name": "population_sc_share_2001",
            "type": "number",
            "description": (
                "SC persons divided by total persons; proportion, not percentage."
            ),
            "constraints": {"required": True, "minimum": 0, "maximum": 1},
        },
        integer(
            "population_sc_rank_2001",
            (
                "Descending SC share rank, using minimum rank for ties. Top five "
                "SC in 2006, next five in 2011; wards 4 and 18 tie at rank 15."
            ),
            required=True,
            minimum=1,
            maximum=26,
        ),
        integer(
            "population_source_page",
            "PDF page 25 of the 2011 report, printed page 23.",
            required=True,
            enum=[25],
        ),
        text(
            "boundary_basis",
            "Signed administration letter confirms unchanged 2006 ward geography.",
            required=True,
        ),
        integer(
            "boundary_source_page",
            "PDF page 15 of the 2011 report, printed page 13.",
            required=True,
            enum=[15],
        ),
        integer(
            "assignment_rule_source_page",
            (
                "PDF page 20 of the 2011 report, printed page 18; scanned signed "
                "letter read visually, applies the October 27, 2006 method to "
                "2011."
            ),
            required=True,
            enum=[20],
        ),
    ]
)
CONTRACT = {
    "description": (
        "One of the 26 unchanged Chandigarh wards, linking 2006 quota "
        "assignment to 2011 outcome; filter is_eligible for the 17 later "
        "non-quota wards."
    ),
    "primaryKey": ["body", "ward_no", "prior_year", "year"],
    "fields": FIELDS,
}
TYPES = {
    "string": pa.string(),
    "integer": pa.int32(),
    "int8": pa.int8(),
    "boolean": pa.bool_(),
    "number": pa.float64(),
}
SCHEMA = pa.schema(
    [
        pa.field(
            f["name"],
            TYPES[f.get("arrow", f["type"])],
            nullable=not f.get("constraints", {}).get("required", False),
        )
        for f in FIELDS
    ]
)


def reservations(year):
    from local_elections.states.chandigarh import parse

    page = {2006: 77, 2011: 26}[year]
    body = parse.pages(parse.REPORTS[year])[page - 1]
    chunks = re.split(r"^\s*([1-4])\.?\s+(?=[A-Z]|\n)", body, flags=re.M)
    groups = {}
    for i in range(1, len(chunks), 2):
        section = int(chunks[i])
        if section == 4:
            continue
        lists = re.findall(r"(?<!\S)(\d+(?:\s*[, &]\s*\d+)+)\s*$", chunks[i + 1], re.M)
        if len(lists) != 1:
            raise ValueError("Ambiguous reservation notification row")
        groups[section] = {int(n) for n in re.findall(r"\d+", lists[0])}
    if {k: len(v) for k, v in groups.items()} != {1: 7, 2: 5, 3: 2}:
        raise ValueError("Incomplete reservation notification")
    if groups[1] & groups[2] or not groups[3] <= groups[2]:
        raise ValueError("Overlapping reservation categories")
    return {
        w: ("SC" if w in groups[2] else "NONE", int(w in groups[1] | groups[3]))
        for w in range(1, 27)
    }


def population():
    from local_elections.states.chandigarh import parse

    rows = {}
    for line in parse.pages(parse.REPORTS[2011])[24].splitlines():
        match = re.fullmatch(r"\s*(\d+)\.\s+([\d,]+)\s+([\d,]+)\s*", line)
        if match:
            ward, total, sc = (int(v.replace(",", "")) for v in match.groups())
            if ward in rows or not 0 <= sc <= total:
                raise ValueError("Invalid population row")
            rows[ward] = {
                "population_2001": total,
                "population_sc_2001": sc,
                "population_sc_share_2001": sc / total,
            }
    if set(rows) != set(range(1, 27)):
        raise ValueError("Incomplete population frame")
    for row in rows.values():
        row["population_sc_rank_2001"] = 1 + sum(
            other["population_sc_2001"] * row["population_2001"]
            > row["population_sc_2001"] * other["population_2001"]
            for other in rows.values()
        )
    return rows


def build_rows(winners):
    from local_elections.states.chandigarh import parse

    prior_rows = [r for r in winners if r["election_year"] == 2006]
    later = [r for r in winners if r["election_year"] == 2011]
    # Check before constructing a dictionary: duplicates must not be overwritten.
    parse.unique_wards(prior_rows, range(1, 27))
    parse.unique_wards(later, range(1, 27))
    prior = {r["ward_no"]: r for r in prior_rows}
    boundary = parse.pages(parse.REPORTS[2011])[14]
    if (
        "2011 would be held on the basis of the existing ward profile" not in boundary
        or "2006/6554" not in boundary
    ):
        raise ValueError("Unchanged-boundary evidence is missing")
    assignments = {year: reservations(year) for year in (2006, 2011)}
    populations = population()
    candidates, _ = parse.candidates_2011()
    hashes = {
        y: hashlib.sha256(p.read_bytes()).hexdigest() for y, p in parse.REPORTS.items()
    }
    rows = []
    for row in sorted(later, key=lambda r: r["ward_no"]):
        w = row["ward_no"]
        before = prior[w]
        for y, source in [(2006, before), (2011, row)]:
            observed = (
                "NONE"
                if source["caste_reservation"] == "GEN"
                else source["caste_reservation"],
                int(source["woman_reserved"]),
            )
            if assignments[y][w] != observed:
                raise ValueError(
                    "Result and independent reservation notification disagree"
                )
            rank = populations[w]["population_sc_rank_2001"]
            expected_sc = rank <= 5 if y == 2006 else 6 <= rank <= 10
            if (observed[0] == "SC") != expected_sc:
                raise ValueError("SC reservation contradicts census ranking")
        if row["winner_sex"] not in {"Male", "Female"}:
            raise ValueError("Missing later winner sex")
        if w == 22 and row["winner_name"] != "Davesh Modgil":
            raise ValueError("Reviewed winner spelling alias changed")
        expected = "Davesh Moudgil" if w == 22 else row["winner_name"]
        matches = [
            c
            for c in candidates
            if c["ward_no"] == w
            and parse.name_key(c["candidate_name"]) == parse.name_key(expected)
        ]
        if len(matches) != 1 or matches[0]["candidate_sex"] != row["winner_sex"]:
            raise ValueError("Winner and candidate honorific disagree")
        candidate = matches[0]
        eligible = not row["woman_reserved"]
        result = {
            "body": row["body"],
            "ward_no": str(w),
            "prior_year": 2006,
            "year": 2011,
            "poll_date_2006": before["poll_date"],
            "poll_date_2011": row["poll_date"],
        }
        for y, source in [(2006, before), (2011, row)]:
            result.update(
                {
                    f"reserved_woman_{y}": assignments[y][w][1],
                    f"reserved_caste_{y}": assignments[y][w][0],
                    f"reserved_raw_{y}": source["reservation_raw"],
                    f"reserved_source_page_{y}": {2006: 77, 2011: 26}[y],
                    f"source_path_{y}": parse.relative(parse.REPORTS[y]),
                    f"source_sha256_{y}": hashes[y],
                }
            )
        result.update(
            {
                "winner_2011": row["winner_name"],
                "winner_source_page_2011": row["source_page"],
                "winner_woman_from_honorific_2011": int(
                    candidate["candidate_sex"] == "Female"
                ),
                "winner_honorific_raw_2011": candidate["honorific_raw"],
                "winner_candidate_name_raw_2011": candidate["candidate_name_raw"],
                "winner_candidate_no_2011": str(candidate["candidate_order"]),
                "winner_link_basis_2011": "reviewed_modgil_moudgil_alias_within_ward"
                if w == 22
                else "unique_normalized_name_within_ward",
                "winner_woman_source_page_2011": candidate["source_page"],
                "is_eligible": eligible,
                "exclusion_reason": "included"
                if eligible
                else "reserved_for_women_in_2011",
                "caste_transition": (
                    f"{assignments[2006][w][0]}_to_{assignments[2011][w][0]}"
                ),
                **populations[w],
                "population_source_page": 25,
                "boundary_basis": "administration_confirms_unchanged_2006_delimitation",
                "boundary_source_page": 15,
                "assignment_rule_source_page": 20,
            }
        )
        rows.append(result)
    validate(pa.Table.from_pylist(rows, schema=SCHEMA))
    return rows


def validate(table):
    if table.schema != SCHEMA:
        raise ValueError("Panel schema differs from declared contract")
    report = Resource(data=table.to_pylist(), schema=Schema(CONTRACT)).validate()
    if not report.valid:
        raise ValueError(str(report.flatten(["type", "message"])))
    rows = table.to_pylist()
    if len(rows) != 26 or {r["ward_no"] for r in rows} != {
        str(n) for n in range(1, 27)
    }:
        raise ValueError("Incomplete panel frame")
    for r in rows:
        for column in (
            "reserved_woman_2006",
            "reserved_woman_2011",
            "winner_woman_from_honorific_2011",
        ):
            if r[column] is None:
                raise ValueError(
                    "Panel requires complete treatment and winner measurements"
                )
        if r["reserved_woman_2006"] and r["reserved_woman_2011"]:
            raise ValueError("Women reservation violates exclusion on rotation")
        if r["is_eligible"] != (r["reserved_woman_2011"] == 0):
            raise ValueError("Eligibility disagrees with current reservation")
        if r["winner_woman_from_honorific_2011"] != int(
            r["winner_honorific_raw_2011"] in {"Smt.", "Ms."}
        ):
            raise ValueError("Honorific measurement changed")
    if collections.Counter(
        r["reserved_woman_2006"] for r in rows if r["is_eligible"]
    ) != {1: 9, 0: 8}:
        raise ValueError("Eligible treatment frame changed")


def write(rows, directory):
    table = pa.Table.from_pylist(rows, schema=SCHEMA)
    validate(table)
    path = directory / f"{NAME}.parquet"
    pq.write_table(table, path, compression="zstd")
    if not table.equals(pq.read_table(path)):
        raise ValueError("Panel Parquet round trip changed values")
    (directory / f"{NAME}.schema.json").write_text(
        json.dumps(CONTRACT, indent=2) + "\n"
    )
    dictionary = directory / "dictionary.csv"
    existing = list(csv.DictReader(dictionary.open())) if dictionary.exists() else []
    with dictionary.open("w", newline="") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=["file", "column", "type", "rows", "nulls", "description"],
        )
        writer.writeheader()
        writer.writerows(r for r in existing if r["file"] != path.name)
        for f in FIELDS:
            writer.writerow(
                {
                    "file": path.name,
                    "column": f["name"],
                    "type": str(SCHEMA.field(f["name"]).type),
                    "rows": len(rows),
                    "nulls": table[f["name"]].null_count,
                    "description": f["description"],
                }
            )
    strata = collections.defaultdict(collections.Counter)
    for row in rows:
        if row["is_eligible"]:
            strata[row["caste_transition"]][str(row["reserved_woman_2006"])] += 1
    audit = {
        "left_universe": "26 outcome-election wards",
        "key": ["body", "ward_no"],
        "cardinality": "1:1",
        "prior_matched": 26,
        "prior_unmatched": 0,
        "later_unmatched": 0,
        "included": 17,
        "excluded_current_women_reserved": 9,
        "missing_outcomes": 0,
        "eligible_by_caste_transition_and_prior_woman": dict(strata),
        "measurement": (
            "Unique within-ward winner/candidate join to printed honorific; "
            "not personal-name inference or quota coding."
        ),
        "source_independence": (
            "Reservation notification and candidate honorific are separate "
            "records within the same official report, not independent "
            "publishers."
        ),
        "assignment": (
            "Sequential women lotteries with no repeat; deterministic SC-share "
            "ranking rotates caste reservation. Unrestricted 9-of-17 "
            "permutations do not represent this mechanism."
        ),
        "outcomes_previously_seen": True,
    }
    (directory / "panel_audit.json").write_text(json.dumps(audit, indent=2) + "\n")
    return {
        "rows": len(rows),
        "columns": {f.name: str(f.type) for f in SCHEMA},
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }
