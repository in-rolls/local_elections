"""Read dated samiti annexures and district vice-presidents in the held SEC report.

The category header literally refers to the Ward. Keep that reported column
separate from the elected person's category and from the explicit chair-office
reservation list on page 22. Names alone do not establish reservation.
"""

import argparse
import csv
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

import pdfplumber
import pyarrow as pa
import pyarrow.parquet as pq

from local_reservations.common.runlog import command
from local_reservations.paths import ROOT
from local_reservations.tools.audit_haryana_historical import name_key, parse_heads
from local_reservations.tools.historical_harvest import checksum
from local_reservations.tools.parse_haryana_report import (
    REPORT,
    REPORT_SHA256,
    REPORT_URL,
)

HEADS_SHA256 = "351f96725322d8f8da2c7c06c9c5e1ab01d57a64dfd70589aa77a2cb5a5e0142"

FIELDS = {
    "year": (pa.int64(), "March 2000 context on report PDF pages 84-85."),
    "tier": (
        pa.string(),
        "block_head, block_vice_head or zp_vice_head, from the table title.",
    ),
    "district_raw": (pa.string(), "Printed district."),
    "body_raw": (pa.string(), "Printed body, preserving line breaks."),
    "category_column_raw": (
        pa.string(),
        "Reported category under a header referring to Ward; semantics pending.",
    ),
    "winner_name_raw": (
        pa.string(),
        "Elected-person text; VACANT and blanks are preserved.",
    ),
    "person_category_raw": (
        pa.string(),
        "Separate category explicitly reported for the elected person.",
    ),
    "relation_marker_raw": (pa.string(), "Printed relation marker."),
    "relation_name_raw": (pa.string(), "Printed relative name."),
    "source_page": (pa.int64(), "One-based PDF page."),
    "source_bbox": (pa.string(), "JSON row box in PDF points."),
    "raw_cells": (pa.string(), "JSON original table cells."),
    "source_fragments": (
        pa.string(),
        "JSON page, row box and cells, including any cross-page continuation.",
    ),
    "source_sha256": (pa.string(), "Original report SHA-256."),
    "source_url": (pa.string(), "Original archived acquisition URL."),
    "review_status": (
        pa.string(),
        "Primary source review; independent review pending.",
    ),
}


def read_chairs(path=REPORT, *, vice=False):
    if checksum(path) != REPORT_SHA256:
        raise ValueError("Changed source report")
    records = []
    with pdfplumber.open(path) as pdf:
        context = pdf.pages[84].extract_text() or ""
        if "March, 2000" not in context or "Annexure 60 and 61" not in context:
            raise ValueError("Missing dated annexure context")
        for number in range(228, 232) if vice else range(224, 228):
            page = pdf.pages[number - 1]
            tables = page.find_tables()
            if len(tables) != 1 or len(tables[0].columns) != 6:
                raise ValueError("Changed annexure table structure")
            table = tables[0]
            cells = table.extract()
            if number in {224, 228} and "Ward" not in cells[0][2]:
                raise ValueError("Changed reported category header")
            for row_index, (values, row) in enumerate(
                zip(cells, table.rows, strict=True)
            ):
                if not any(values) or values[0] == "District":
                    continue
                if vice and number == 229 and row_index == 0:
                    if values != ["", "TAORU", "", "MOHAMMAD", "", ""]:
                        raise ValueError("Changed cross-page Taoru continuation")
                    previous = records[-1]
                    if (
                        previous["district_raw"] != "GURGAON"
                        or previous["winner_name_raw"] != "SH.AASH"
                    ):
                        raise ValueError("Continuation lost its preceding office")
                    previous["body_raw"] += "\n" + values[1]
                    previous["winner_name_raw"] += "\n" + values[3]
                    fragments = json.loads(previous["source_fragments"])
                    fragments.append(
                        {"page": number, "bbox": row.bbox, "cells": values}
                    )
                    previous["source_fragments"] = json.dumps(fragments)
                    continue
                if not values[0] or not (values[1] or "").startswith("PANCHAYAT"):
                    raise ValueError(f"Unexpected annexure row on page {number}")
                left, top, right, bottom = row.cells[3]
                boundary = 418 if vice else 394
                winner = page.crop((left, top, boundary, bottom)).extract_text() or None
                category = (
                    page.crop((boundary, top, right, bottom)).extract_text() or None
                )
                if category not in {
                    None,
                    "Gen",
                    "Gen(w)",
                    "SC",
                    "SC(w)",
                    "Sc(w)",
                    "BC",
                    "BC(w)",
                }:
                    raise ValueError(
                        f"Unrecognized elected-person category: {category}"
                    )
                records.append(
                    {
                        "year": 2000,
                        "tier": "block_vice_head" if vice else "block_head",
                        "district_raw": values[0],
                        "body_raw": values[1],
                        "category_column_raw": values[2],
                        "winner_name_raw": winner,
                        "person_category_raw": category,
                        "relation_marker_raw": values[4] or None,
                        "relation_name_raw": values[5] or None,
                        "source_page": number,
                        "source_bbox": json.dumps(row.bbox),
                        "raw_cells": json.dumps(values),
                        "source_fragments": json.dumps(
                            [{"page": number, "bbox": row.bbox, "cells": values}]
                        ),
                        "source_sha256": REPORT_SHA256,
                        "source_url": REPORT_URL,
                        "review_status": (
                            "primary_page_review; "
                            "independent_and_category_semantic_review_pending"
                        ),
                    }
                )
    if (
        len(records) != 114
        or len({(r["district_raw"], r["body_raw"]) for r in records}) != 114
    ):
        raise ValueError("Expected 114 distinct printed chair offices")
    return records


def read_district_vice_heads(path=REPORT):
    if checksum(path) != REPORT_SHA256:
        raise ValueError("Changed source report")
    records = []
    with pdfplumber.open(path) as pdf:
        context = pdf.pages[83].extract_text() or ""
        if (
            "March, 2000" not in context
            or "Presidents and Vice-Presidents" not in context
        ):
            raise ValueError("Missing dated district vice-president context")
        page = pdf.pages[84]
        if "VICE-PRESIDENTS OF ZILA PARISHADS" not in (page.extract_text() or ""):
            raise ValueError("Missing district vice-president table title")
        tables = page.find_tables()
        if len(tables) != 1 or len(tables[0].columns) != 4:
            raise ValueError("Changed district vice-president table structure")
        table = tables[0]
        cells = table.extract()
        if "Ward" not in cells[0][2]:
            raise ValueError("Changed district vice-president category header")
        for values, row in zip(cells[1:], table.rows[1:], strict=True):
            if not values[0] or not values[1] or values[2] != "Un-reserved":
                raise ValueError("Unexpected district vice-president row")
            left, top, _, bottom = row.bbox
            right = table.bbox[2]

            def cell_text(start, end):
                return page.crop((start, top, end, bottom)).extract_text() or None

            winner = cell_text(325, 410)
            marker = cell_text(410, 435)
            relative = cell_text(435, right)
            if not winner or not relative or marker not in {"S/O", "W/O"}:
                raise ValueError("Incomplete district vice-president person fields")
            records.append(
                {
                    "year": 2000,
                    "tier": "zp_vice_head",
                    "district_raw": values[0],
                    "body_raw": values[1],
                    "category_column_raw": values[2],
                    "winner_name_raw": winner,
                    "person_category_raw": None,
                    "relation_marker_raw": marker,
                    "relation_name_raw": relative,
                    "source_page": 85,
                    "source_bbox": json.dumps([left, top, right, bottom]),
                    "raw_cells": json.dumps(values),
                    "source_fragments": json.dumps(
                        [
                            {
                                "page": 85,
                                "bbox": [left, top, right, bottom],
                                "cells": values,
                            }
                        ]
                    ),
                    "source_sha256": REPORT_SHA256,
                    "source_url": REPORT_URL,
                    "review_status": (
                        "primary_page_review; "
                        "independent_and_category_semantic_review_pending"
                    ),
                }
            )
    if len(records) != 19 or len({r["district_raw"] for r in records}) != 19:
        raise ValueError("Expected 19 distinct district vice-president offices")
    return records


def body_key(raw):
    return (
        re.sub(r"[^A-Z0-9]", "", raw.upper())
        .removeprefix("PANCHAYATSAMITI")
        .removeprefix("ZILAPARISHAD")
    )


def chair_concordance(chairs, reservations, reviews):
    by_body = defaultdict(list)
    for row in chairs:
        by_body[body_key(row["body_raw"])].append(row)
    aliases = {}
    names = {r["body_raw"] for r in reservations}
    for review in reviews:
        old, new = review["report_body_raw"], review["annexure_body"]
        if old in aliases or old not in names or body_key(new) not in by_body:
            raise ValueError("Changed or duplicate annexure spelling review")
        aliases[old] = new
    output = []
    for row in reservations:
        category = ("SC" if row["caste_reservation"] == "SC" else "Gen") + (
            "(w)" if row["woman_reserved"] == "True" else ""
        )
        matches = by_body[body_key(aliases.get(row["body_raw"], row["body_raw"]))]
        method = "body_name"
        if len(matches) > 1:
            method = "body_and_category_disambiguation"
            matches = [r for r in matches if r["category_column_raw"] == category]
        if len(matches) != 1:
            raise ValueError(f"Unresolved report chair: {row['body_raw']}")
        match = matches[0]
        output.append(
            {
                "report_source_page": row["source_page"],
                "report_source_bbox": row["source_bbox"],
                "report_body_raw": row["body_raw"],
                "annexure_source_page": match["source_page"],
                "annexure_source_bbox": match["source_bbox"],
                "annexure_body_raw": match["body_raw"],
                "district_reported_in_annexure": match["district_raw"],
                "link_method": method,
                "chair_office_category": category,
                "annexure_category_column_raw": match["category_column_raw"],
                "category_agrees": category == match["category_column_raw"],
                "source_sha256": REPORT_SHA256,
                "review_status": "primary_concordance; independent_review_pending",
            }
        )
    if len(
        {(r["annexure_source_page"], r["annexure_source_bbox"]) for r in output}
    ) != len(output):
        raise ValueError("Annexure linkage reused an office")
    return output


def date_archived_offices(heads, chairs):
    output = []
    body_spellings = {
        "BADRA": "BADHRA",
        "BABEN": "BABAIN",
        "SAMPALA": "SAMPLA",
        "KERU": "KAIRU",
        "BHATUKALAN": "BHATTUKALAN",
        "GANNAUR": "GANAUR",
    }
    for row in heads:
        tier = {
            "CHAIRMAN": "block_head",
            "CAHIRMAN": "block_head",
            "VICE-CHAIRMAN": "block_vice_head",
            "VICE-PRESIDENT": "zp_vice_head",
            "PRESIDENT": "zp_head",
        }.get(row["office_raw"])
        if tier is None:
            continue
        key = body_key(row["body_raw"])
        district = name_key(row["district_raw"])
        district_spelling_review = district == "FARIDABA" and key == "FARIDABAD"
        if district_spelling_review:
            district = "FARIDABAD"
        matches = [
            r
            for r in chairs
            if body_key(r["body_raw"]) in {key, body_spellings.get(key, key)}
            and r["tier"] == tier
            and name_key(r["district_raw"]) == district
            and r["winner_name_raw"] not in {None, "", "VACANT"}
            and r["relation_name_raw"]
            and name_key(r["winner_name_raw"]) == name_key(row["winner_name_raw"])
            and name_key(r["relation_name_raw"]) == name_key(row["relation_name_raw"])
        ]
        match = matches[0] if len(matches) == 1 else None
        output.append(
            {
                "archive_source_page": row["source_page"],
                "archive_source_row": row["source_row_on_page"],
                "archive_source_sha256": HEADS_SHA256,
                "office_raw": row["office_raw"],
                "district_raw": row["district_raw"],
                "body_raw": row["body_raw"],
                "winner_name_raw": row["winner_name_raw"],
                "relation_name_raw": row["relation_name_raw"],
                "year_corroborated": 2000 if match else None,
                "annexure_source_page": match["source_page"] if match else None,
                "annexure_source_bbox": match["source_bbox"] if match else None,
                "annexure_source_sha256": REPORT_SHA256 if match else None,
                "body_spelling_review": bool(
                    match and body_key(match["body_raw"]) != key
                ),
                "district_spelling_review": district_spelling_review,
                "status": (
                    "office_district_body_person_relative_match; "
                    "independent_review_pending"
                )
                if match
                else "unmatched; date_unknown",
            }
        )
    return output


@command("parse", state="Haryana", vintage="2000_chair_annexure")
def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out", type=Path, default=REPORT.parents[2] / "report_annexures"
    )
    args = parser.parse_args()
    rows = read_chairs()
    vice_rows = read_chairs(vice=True)
    district_vice_rows = read_district_vice_heads()
    out = args.out
    out.mkdir(exist_ok=True, parents=True)
    base = REPORT.parents[2]
    reservations_path = base / "report_2000/seat_rows.csv"
    report_manifest = base / "report_2000/checksums.json"
    expected = json.loads(report_manifest.read_text())["outputs"]["seat_rows.csv"]
    if checksum(reservations_path) != expected:
        raise ValueError("Changed chair reservation extract")
    with reservations_path.open(newline="") as stream:
        reservation_rows = list(csv.DictReader(stream))
    reservations = [r for r in reservation_rows if r["tier"] == "block_head"]
    reviews_path = out / "chair_name_reviews.csv"
    with reviews_path.open(newline="") as stream:
        reviews = list(csv.DictReader(stream))
    concordance = chair_concordance(rows, reservations, reviews)
    heads_path = base / "gap_recovery/raw/11336814aa4b51ff51a4.pdf"
    if checksum(heads_path) != HEADS_SHA256:
        raise ValueError("Changed archived head roster")
    heads = parse_heads(heads_path).to_dict("records")
    dated = date_archived_offices(
        [r for r in heads if r["office_raw"] not in {"VICE-PRESIDENT", "PRESIDENT"}],
        rows + vice_rows,
    )
    district_dated = date_archived_offices(
        [r for r in heads if r["office_raw"] == "VICE-PRESIDENT"], district_vice_rows
    )
    all_dated = date_archived_offices(
        heads,
        rows
        + vice_rows
        + district_vice_rows
        + [r for r in reservation_rows if r["tier"] == "zp_head"],
    )
    for name, records in [
        ("chair_concordance.csv", concordance),
        ("archive_samiti_dates.csv", dated),
        ("archive_zp_vice_dates.csv", district_dated),
        ("archive_all_head_dates.csv", all_dated),
        ("district_vice_heads.csv", district_vice_rows),
    ]:
        with (out / name).open("w", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(records[0]))
            writer.writeheader()
            writer.writerows(records)
    schema = pa.schema([pa.field(k, v[0]) for k, v in FIELDS.items()])
    (out / "schema.json").write_text(
        json.dumps({k: str(v[0]) for k, v in FIELDS.items()}, indent=2) + "\n"
    )
    pq.write_table(pa.Table.from_pylist(rows, schema=schema), out / "chairs.parquet")
    pq.write_table(
        pa.Table.from_pylist(vice_rows, schema=schema), out / "vice_chairs.parquet"
    )
    pq.write_table(
        pa.Table.from_pylist(district_vice_rows, schema=schema),
        out / "district_vice_heads.parquet",
    )
    with (out / "vice_chairs.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(FIELDS))
        writer.writeheader()
        writer.writerows(vice_rows)
    with (out / "chairs.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(FIELDS))
        writer.writeheader()
        writer.writerows(rows)
    with (out / "data_dictionary.csv").open("w", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["field", "type", "description"])
        writer.writerows((k, *v) for k, v in FIELDS.items())
    summary = {
        "chair_rows": len(rows),
        "vice_chair_rows": len(vice_rows),
        "district_vice_head_rows": len(district_vice_rows),
        "archived_district_vice_offices_dated": sum(
            r["year_corroborated"] is not None for r in district_dated
        ),
        "archived_head_occurrences": len(all_dated),
        "archived_head_occurrences_dated": sum(
            r["year_corroborated"] is not None for r in all_dated
        ),
        "archived_head_dates_unresolved": sum(
            r["year_corroborated"] is None for r in all_dated
        ),
        "reported_category_counts": dict(
            Counter(r["category_column_raw"] for r in rows)
        ),
        "blank_person_names": sum(r["winner_name_raw"] is None for r in rows),
        "vacant_person_text": sum(r["winner_name_raw"] == "VACANT" for r in rows),
        "scope": (
            "Dated samiti and district vice-president rosters; "
            "category header semantics unresolved"
        ),
        "report_concordance_rows": len(concordance),
        "body_name_links_category_agree": sum(
            r["category_agrees"] and r["link_method"] == "body_name"
            for r in concordance
        ),
        "body_category_disambiguated": sum(
            r["link_method"] == "body_and_category_disambiguation" for r in concordance
        ),
        "archived_samiti_offices_dated": sum(
            r["year_corroborated"] is not None for r in dated
        ),
        "dated_by_office": dict(
            Counter(
                r["office_raw"] for r in dated if r["year_corroborated"] is not None
            )
        ),
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    (out / "checksums.json").write_text(
        json.dumps(
            {
                "inputs": {
                    str(p.relative_to(ROOT)): checksum(p)
                    for p in [
                        REPORT,
                        heads_path,
                        reservations_path,
                        report_manifest,
                        reviews_path,
                        Path(__file__),
                    ]
                },
                "outputs": {
                    name: checksum(out / name)
                    for name in [
                        "chairs.csv",
                        "chairs.parquet",
                        "vice_chairs.csv",
                        "vice_chairs.parquet",
                        "district_vice_heads.csv",
                        "district_vice_heads.parquet",
                        "archive_zp_vice_dates.csv",
                        "archive_all_head_dates.csv",
                        "chair_concordance.csv",
                        "archive_samiti_dates.csv",
                        "data_dictionary.csv",
                        "schema.json",
                        "summary.json",
                    ]
                },
            },
            indent=2,
        )
        + "\n"
    )
    print(json.dumps(summary))


if __name__ == "__main__":
    main()
