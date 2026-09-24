"""Preserve complete reference books and their aggregate electoral tables.

Block and district totals never become named-GP office reservations. Actual
printed conflicts between the Bardhaman synopsis and block profiles remain
visible. Blank numerical cells remain unknown. Purba Medinipur's overprinted
characters are deduplicated by position, without rewriting digit strings.
"""

import argparse
import collections
import csv
import hashlib
import json
import re
import subprocess
from concurrent.futures import ProcessPoolExecutor

import pdfplumber

from local_elections.common.runlog import command
from local_elections.paths import ROOT
from local_elections.states.wb.parse_nadia import tidy
from local_elections.states.wb.parse_results import write_table
from local_elections.states.wb.parse_ward_schedules import ocr_page

OUT = ROOT / "data/wb/derived/reference_tables"
SOURCES = {
    "paninfo_book08_20110722093353.pdf": ("Bardhaman", 2008),
    "birbhum_2003.pdf": ("Birbhum", 2003),
    (
        "purbamedinipur_Members_20of_20Three_20Tier_20Panchayati_"
        "20Raj_20Bodies_202014.pdf"
    ): (
        "Purba Medinipur",
        None,
    ),
}
PARTIES = ["CPI_M", "CPI", "AIFB", "RSP", "INC", "AITC", "BJP", "CPI_ML", "NCP", "IND"]
RESERVATION_FIELDS = ["seats", "sc", "sc_women", "st", "st_women", "women"]
MAP_PAGES = {5, *range(45, 106, 2)}
ADDITIONAL_REFERENCES = {
    "cc98b56977ce3bed.pdf": "block_map",
    "2a127b4cb67ca020.pdf": "block_map",
    "9cc9cb2f9dc9cc88.pdf": "research_paper",
    "cdff11e9c8a417fa.pdf": "research_chapter",
    "5bcf7014f0f2a3f4.pdf": "unrelated_mexico_research_paper",
    "339b26ca88f6daee.pdf": "research_paper",
    "74ba30419d75cf82.pdf": "environmental_reference_report",
    "3ff045353cd435ee.pdf": "research_paper",
    "eb8356db262b225a.pdf": "research_paper",
    "bb1671a705d56009.pdf": "government_programme_presentation",
}
MANUAL_BLANK_PAGES = {
    4,
    20,
    22,
    24,
    106,
    108,
    260,
    340,
    342,
    354,
    368,
    372,
    376,
    382,
    384,
}
MANUAL_SCAN_PAGES = {410, 411, *range(413, 422)}
ENVIRONMENT_BLANK_PAGES = {2, 8, 10, 14, 22, 26, 32, 403}
ENVIRONMENT_PHOTO_PAGES = {3, 4, 110, 150, 156, 230, 290, 372, 401, 402}


def additional_page_classification(source, page):
    path, number = source["source_path"], page["page"]
    if path.endswith("/PE_Manual_2022_Vol-I.pdf"):
        evidence = "additional_classification/manual_contact.png"
        if number in MANUAL_BLANK_PAGES:
            return "visually_blank_reference_page", evidence
        if number == 383:
            return "reference_section_title", evidence
        if number in MANUAL_SCAN_PAGES:
            return "local_reference_ocr_pending", evidence
    if path.endswith("/74ba30419d75cf82.pdf"):
        evidence = "additional_classification/environment_contact.png"
        if number in ENVIRONMENT_BLANK_PAGES:
            return "visually_blank_reference_page", evidence
        if number in ENVIRONMENT_PHOTO_PAGES:
            return "photograph_reference", evidence
        if number in {1, 404}:
            return "cover_reference", evidence
        if number in {7, 342}:
            return "local_reference_ocr_pending", evidence
    return None, None


def additional_sources():
    index = ROOT / "data/wb/vintage_search/artifact_index.csv"
    sources = []
    for row in csv.DictReader(index.open()):
        filename = row["file"].split("/")[-1]
        if filename not in ADDITIONAL_REFERENCES:
            continue
        sources.append(
            {
                "source_path": "data/wb/vintage_search/" + row["file"],
                "sha256": row["sha256"],
                "district": None,
                "reference_year": 2016 if filename == "74ba30419d75cf82.pdf" else None,
                "reference_kind": ADDITIONAL_REFERENCES[filename],
                "acquisition_kind": row["kind"],
                "acquisition_role": row["role"],
                "source_url": row["url"],
            }
        )
    path = ROOT / "data/wb/PE_Manual_2022_Vol-I.pdf"
    sources.append(
        {
            "source_path": str(path.relative_to(ROOT)),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "district": None,
            "reference_year": 2022,
            "reference_kind": "election_manual_blank_forms_and_rules",
            "source_url": None,
        }
    )
    if len(sources) != 11:
        raise ValueError("The eleven acquired additional references are incomplete")
    return sources


def extract_additional(source):
    """Keep archival text and tables without turning research results into data."""
    if (
        hashlib.sha256((ROOT / source["source_path"]).read_bytes()).hexdigest()
        != source["sha256"]
    ):
        raise ValueError("Reference source hash differs from the source inventory")
    cache = OUT / "native" / (source["sha256"] + ".json")
    source["cache"] = str(cache.relative_to(ROOT))
    if cache.exists():
        return json.loads(cache.read_text())
    pages = []
    page_directory = OUT / "native_pages" / source["sha256"]
    page_directory.mkdir(parents=True, exist_ok=True)
    with pdfplumber.open(ROOT / source["source_path"]) as pdf:
        for number, page in enumerate(pdf.pages, 1):
            page_cache = page_directory / f"{number:04d}.json"
            if page_cache.exists():
                pages.append(json.loads(page_cache.read_text()))
                page.close()
                continue
            pages.append(
                {
                    "page": number,
                    "width": page.width,
                    "height": page.height,
                    "text": page.extract_text() or "",
                    "words": page.extract_words(),
                    "tables": [
                        {"bbox": list(table.bbox), "rows": table.extract()}
                        for table in page.find_tables()
                    ],
                    "images": len(page.images),
                    "characters": len(page.chars),
                }
            )
            temporary = page_cache.with_suffix(".tmp")
            temporary.write_text(json.dumps(pages[-1], ensure_ascii=False) + "\n")
            temporary.replace(page_cache)
            page.close()
            if number % 25 == 0:
                print(
                    json.dumps(
                        {"reference_source": source["source_path"], "page": number}
                    ),
                    flush=True,
                )
    info = subprocess.check_output(
        ["pdfinfo", str(ROOT / source["source_path"])], text=True
    )
    expected = int(re.search(r"Pages:\s*(\d+)", info)[1])
    if expected != len(pages):
        raise ValueError("Native reference page count differs from pdfinfo")
    record = {
        "source_path": source["source_path"],
        "sha256": source["sha256"],
        "method": "pdfplumber_native_text_words_and_tables",
        "pdfplumber_version": pdfplumber.__version__,
        "expected_pages": expected,
        "pages": pages,
    }
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(record, ensure_ascii=False) + "\n")
    return record


def numeric(raw):
    value = tidy(raw)
    if re.fullmatch(r"\d+", value):
        return int(value)
    if re.fullmatch(r"\d+\.\d+", value):
        return float(value)
    return None


def tier(raw):
    return {
        "GP": "gram_panchayat",
        "PS": "panchayat_samiti",
        "ZP": "zilla_parishad",
    }.get(re.sub(r"[.\s]", "", raw or ""))


def provenance(source, page, table, ti, ri, raw):
    return {
        "source_path": source["source_path"],
        "source_sha256": source["sha256"],
        "source_page": page["page"],
        "source_table": ti,
        "source_row": ri,
        "source_table_bbox": json.dumps(table["bbox"]),
        "raw_cells": json.dumps(raw, ensure_ascii=False),
    }


def aggregate(
    source, page, table, ti, ri, raw, kind, year, block, unit, fields, values, checks=()
):
    counts = dict(zip(fields, [numeric(v) for v in values], strict=True))
    flags = list(checks)
    if any(v is None for v in counts.values()):
        flags.append("blank_or_unread_count")
    return {
        **provenance(source, page, table, ti, ri, raw),
        "state": "West Bengal",
        "district": source["district"],
        "year": year,
        "block_printed": block,
        "record_kind": kind,
        "tier": unit,
        "counts_json": json.dumps(counts),
        "quality_flags": ";".join(flags),
        "review_status": "needs_review" if flags else "native_fields_parsed",
    }


def add_check(row, flag):
    row["quality_flags"] = ";".join(
        sorted(set(filter(None, row["quality_flags"].split(";"))) | {flag})
    )
    row["review_status"] = "needs_review"


def check_equality(row, left, right):
    counts = json.loads(row["counts_json"])
    if (
        all(counts.get(k) is not None for k in [*left, right])
        and sum(counts[k] for k in left) != counts[right]
    ):
        add_check(row, "printed_components_mismatch")


def parse_bardhaman(source, record):
    result = []
    for page in record["pages"]:
        match = re.search(r"BLOCK\s*:\s*([^\n]+)", page["text"])
        block = tidy(match[1]) if match else None
        for ti, table in enumerate(page["tables"], 1):
            header = " ".join(tidy(c) for row in table["rows"][:3] for c in row)
            for ri, raw in enumerate(table["rows"], 1):
                row = None
                if (
                    page["page"] in {12, 13, 14}
                    and len(raw) in {8, 12, 16}
                    and numeric(raw[2]) is not None
                ):
                    name = tidy(raw[1] or raw[0])
                    if page["page"] == 12 and len(raw) == 16:
                        fields, values, unit = (
                            RESERVATION_FIELDS,
                            [raw[i] for i in [2, 3, 5, 8, 10, 13]],
                            "zilla_parishad",
                        )
                    elif page["page"] == 13 and len(raw) == 8:
                        fields, values, unit = (
                            RESERVATION_FIELDS,
                            raw[2:],
                            "panchayat_samiti",
                        )
                    elif page["page"] == 14 and len(raw) == 12:
                        fields = [
                            "single_seat_constituencies",
                            "double_seat_constituencies",
                            "constituencies",
                            "seats",
                            "parts",
                            "sc",
                            "sc_women",
                            "st",
                            "st_women",
                            "women",
                        ]
                        values, unit = raw[2:], "gram_panchayat"
                    else:
                        continue
                    row = aggregate(
                        source,
                        page,
                        table,
                        ti,
                        ri,
                        raw,
                        "block_reservation_totals",
                        2008,
                        name,
                        unit,
                        fields,
                        values,
                    )
                elif (
                    block
                    and len(raw) == 7
                    and tier(raw[0])
                    and "Nature of reservation" in header
                ):
                    row = aggregate(
                        source,
                        page,
                        table,
                        ti,
                        ri,
                        raw,
                        "block_reservation_totals",
                        2008,
                        block,
                        tier(raw[0]),
                        RESERVATION_FIELDS,
                        raw[1:],
                    )
                elif len(raw) == 19 and tier(raw[0]) and "2003" in page["text"]:
                    fields = [
                        "seats",
                        "uncontested",
                        "seats_election_held",
                        "sc",
                        "st",
                        "sc_st_women",
                        "women",
                        "reserved_total",
                        *PARTIES,
                    ]
                    row = aggregate(
                        source,
                        page,
                        table,
                        ti,
                        ri,
                        raw,
                        "district_election_results",
                        2003,
                        None,
                        tier(raw[0]),
                        fields,
                        raw[1:],
                    )
                elif (
                    block and len(raw) == 15 and tier(raw[0]) and "2003" in page["text"]
                ):
                    fields = [
                        "seats",
                        "uncontested",
                        "seats_election_held",
                        "contesting_candidates",
                        *PARTIES,
                    ]
                    row = aggregate(
                        source,
                        page,
                        table,
                        ti,
                        ri,
                        raw,
                        "block_election_results",
                        2003,
                        block,
                        tier(raw[0]),
                        fields,
                        raw[1:],
                    )
                elif (
                    block
                    and len(raw) == 7
                    and numeric(raw[0]) is not None
                    and "Non EPIC" in header
                ):
                    fields = [
                        "male",
                        "female",
                        "total",
                        "epic",
                        "non_epic",
                        "image",
                        "non_image",
                    ]
                    row = aggregate(
                        source,
                        page,
                        table,
                        ti,
                        ri,
                        raw,
                        "block_elector_totals",
                        2008,
                        block,
                        None,
                        fields,
                        raw,
                    )
                    for left in [
                        ["male", "female"],
                        ["epic", "non_epic"],
                        ["image", "non_image"],
                    ]:
                        check_equality(row, left, "total")
                elif (
                    page["page"] == 11
                    and len(raw) == 13
                    and numeric(raw[2]) is not None
                ):
                    fields = [
                        "male",
                        "female",
                        "total",
                        "net_inclusion",
                        "epic",
                        "non_epic",
                        "percent_without_epic",
                        "image",
                        "non_image",
                    ]
                    row = aggregate(
                        source,
                        page,
                        table,
                        ti,
                        ri,
                        raw,
                        "block_elector_totals",
                        2008,
                        tidy(raw[1] or raw[0]),
                        None,
                        fields,
                        [*raw[2:9], *raw[11:13]],
                    )
                    check_equality(row, ["male", "female"], "total")
                elif (
                    block
                    and len(raw) == 10
                    and numeric(raw[0]) is not None
                    and "Premises" in header
                ):
                    fields = [
                        "main_polling_stations",
                        "auxiliary_polling_stations",
                        "total_polling_stations",
                        "one_station_premises",
                        "two_station_premises",
                        "three_station_premises",
                        "four_station_premises",
                        "five_station_premises",
                        "six_station_premises",
                        "total_premises",
                    ]
                    row = aggregate(
                        source,
                        page,
                        table,
                        ti,
                        ri,
                        raw,
                        "block_polling_infrastructure",
                        2008,
                        block,
                        None,
                        fields,
                        raw,
                    )
                    check_equality(
                        row,
                        ["main_polling_stations", "auxiliary_polling_stations"],
                        "total_polling_stations",
                    )
                if row:
                    if (row["block_printed"] or "").casefold() == "total":
                        row["block_printed"] = None
                        row["record_kind"] = row["record_kind"].replace(
                            "block_", "district_", 1
                        )
                    if row["record_kind"].endswith("election_results"):
                        check_equality(
                            row, ["uncontested", "seats_election_held"], "seats"
                        )
                        check_equality(row, PARTIES, "seats")
                    result.append(row)
    grouped = collections.defaultdict(list)
    for row in result:
        if row["record_kind"] == "block_reservation_totals":
            grouped[
                (row["tier"], re.sub(r"\s+", "", row["block_printed"].upper()))
            ].append(row)
    for group in grouped.values():
        values = [json.loads(r["counts_json"]) for r in group]
        if any(
            len({v[k] for v in values if v.get(k) is not None}) > 1
            for k in RESERVATION_FIELDS
        ):
            for row in group:
                add_check(row, "conflicting_printed_block_totals")
    return result


def parse_birbhum(source, record):
    result = []
    page = record["pages"][0]
    for ti, table in enumerate(page["tables"], 1):
        for ri, raw in enumerate(table["rows"], 1):
            if not raw or tidy(raw[0]) != "Birbhum":
                continue
            if len(raw) == 7 and ti == 1:
                fields = [
                    "gram_sansads",
                    "gram_panchayats",
                    "gp_seats",
                    "panchayat_samitis",
                    "ps_seats",
                    "zp_seats",
                ]
                row = aggregate(
                    source,
                    page,
                    table,
                    ti,
                    ri,
                    raw,
                    "district_institution_totals",
                    2003,
                    None,
                    None,
                    fields,
                    raw[1:],
                )
            elif len(raw) == 9 and ti in {2, 3, 4}:
                fields = [
                    "male_sc",
                    "male_st",
                    "male_general",
                    "male_total",
                    "female_sc",
                    "female_st",
                    "female_general",
                    "female_total",
                ]
                unit = {
                    2: "gram_panchayat",
                    3: "panchayat_samiti",
                    4: "zilla_parishad",
                }[ti]
                row = aggregate(
                    source,
                    page,
                    table,
                    ti,
                    ri,
                    raw,
                    "elected_members_by_recorded_caste_and_sex",
                    2003,
                    None,
                    unit,
                    fields,
                    raw[1:],
                )
                for sex in ["male", "female"]:
                    check_equality(
                        row,
                        [sex + suffix for suffix in ["_sc", "_st", "_general"]],
                        sex + "_total",
                    )
            else:
                continue
            result.append(row)
    return result


def deduplicate_purba(source):
    with pdfplumber.open(ROOT / source["source_path"]) as pdf:
        page = pdf.pages[0]
        cleaned = page.dedupe_chars(tolerance=1, extra_attrs=())
        tables = [{"bbox": t.bbox, "rows": t.extract()} for t in cleaned.find_tables()]
        return {
            "source_sha256": source["sha256"],
            "method": "pdfplumber.dedupe_chars",
            "tolerance": 1,
            "extra_attrs": [],
            "method_documentation": "https://github.com/jsvine/pdfplumber",
            "characters_before": len(page.chars),
            "characters_after": len(cleaned.chars),
            "visual_control_values": [60, 4, 14, 25],
            "pages": [
                {
                    "page": 1,
                    "width": page.width,
                    "height": page.height,
                    "text": cleaned.extract_text() or "",
                    "tables": tables,
                }
            ],
        }


def parse_purba(source, record):
    result = []
    for page in record["pages"]:
        for ti, table in enumerate(page["tables"], 1):
            for ri, raw in enumerate(table["rows"], 1):
                if len(raw) == 3 and numeric(raw[1]) is not None:
                    row = aggregate(
                        source,
                        page,
                        table,
                        ti,
                        ri,
                        raw,
                        "district_membership_composition",
                        None,
                        None,
                        tidy(raw[0]),
                        ["members"],
                        [raw[1]],
                    )
                    row["selection_basis_printed"] = tidy(raw[2])
                    row["review_status"] = "visual_source_checked"
                    result.append(row)
    return result


@command("parse", state="West Bengal", source="reference_tables")
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ocr", action="store_true")
    parser.add_argument("--workers", type=int, default=1)
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    index = json.loads((ROOT / "data/wb/derived/native/index.json").read_text())
    rows, raw_rows, pages, documents, tasks = [], [], [], [], []
    sources = []
    for filename, (district, year) in SOURCES.items():
        source = dict(
            next(s for s in index if s["source_path"].endswith("/" + filename))
        )
        source["district"] = district
        source["reference_year"] = year
        source["reference_kind"] = "district_electoral_reference"
        sources.append(source)
    sources.extend(additional_sources())
    for source in sources:
        district, year = source["district"], source["reference_year"]
        if (
            hashlib.sha256((ROOT / source["source_path"]).read_bytes()).hexdigest()
            != source["sha256"]
        ):
            raise ValueError("Source hash differs: " + source["source_path"])
        record = (
            json.loads((ROOT / source["cache"]).read_text())
            if district is not None
            else extract_additional(source)
        )
        if district == "Purba Medinipur":
            record = deduplicate_purba(source)
            (OUT / "purba_deduplicated_native.json").write_text(
                json.dumps(record, ensure_ascii=False, indent=2) + "\n"
            )
            parsed = parse_purba(source, record)
        elif district is not None:
            parsed = (
                parse_bardhaman(source, record)
                if district == "Bardhaman"
                else parse_birbhum(source, record)
            )
        else:
            parsed = []
        rows.extend(parsed)
        documents.append(
            {
                "source_path": source["source_path"],
                "source_sha256": source["sha256"],
                "pages": len(record["pages"]),
                "aggregate_records": len(parsed),
                "reference_kind": source["reference_kind"],
                "source_url": source.get("source_url"),
                "native_cache": source["cache"],
                "document_reference_year": source["reference_year"],
            }
        )
        for page in record["pages"]:
            if district == "Bardhaman" and page["page"] in MAP_PAGES:
                status = "map_reference"
            elif district == "Bardhaman" and page["page"] == 1:
                status = "cover_reference"
            elif district == "Bardhaman" and page["page"] in {9, 35, 37}:
                status = "blank_except_page_number"
            elif source["reference_kind"] == "block_map":
                status = "map_reference"
            elif additional_page_classification(source, page)[0]:
                status = additional_page_classification(source, page)[0]
                if status == "local_reference_ocr_pending":
                    tasks.append(
                        (
                            source["source_path"],
                            source["sha256"],
                            page["page"],
                            str(OUT),
                        )
                    )
            elif district is None and len(page["text"].strip()) < 30:
                status = "sparse_reference_page_requires_review"
            else:
                status = (
                    "native_tables_retained"
                    if page["tables"]
                    else "native_text_reference"
                )
            pages.append(
                {
                    "source_path": source["source_path"],
                    "source_sha256": source["sha256"],
                    "source_page": page["page"],
                    "source_page_bbox": [0, 0, page["width"], page["height"]],
                    "district": district,
                    "reference_kind": source["reference_kind"],
                    "document_reference_year": year,
                    "status": status,
                    "aggregate_records": sum(
                        r["source_page"] == page["page"] for r in parsed
                    ),
                    "raw_text": page["text"],
                    "native_cache": source["cache"],
                    "normalized_native_cache": (
                        str((OUT / "purba_deduplicated_native.json").relative_to(ROOT))
                        if district == "Purba Medinipur"
                        else None
                    ),
                    "visual_classification_evidence": (
                        "map_classification_contact.png"
                        if district == "Bardhaman"
                        and status == "map_reference"
                        and page["page"] >= 49
                        else (
                            "page_classification_contact.png"
                            if district == "Bardhaman"
                            and status
                            in {
                                "map_reference",
                                "cover_reference",
                                "blank_except_page_number",
                            }
                            else additional_page_classification(source, page)[1]
                        )
                    ),
                }
            )
            if status in {"map_reference", "cover_reference"}:
                continue
            for ti, table in enumerate(page["tables"], 1):
                for ri, raw in enumerate(table["rows"], 1):
                    if any(tidy(c) for c in raw):
                        raw_rows.append(
                            {
                                **provenance(source, page, table, ti, ri, raw),
                                "district": district,
                                "reference_kind": source["reference_kind"],
                                "document_reference_year": year,
                                "record_kind": "reference_table_row",
                                "review_status": "raw_reference_extraction",
                            }
                        )
    if args.ocr and tasks:
        with ProcessPoolExecutor(max_workers=args.workers) as pool:
            list(pool.map(ocr_page, tasks))
    for page in pages:
        cache = OUT / "ocr" / page["source_sha256"] / f"{page['source_page']:04d}.json"
        if cache.exists():
            ocr = json.loads(cache.read_text())
            page["ocr_cache"] = str(cache.relative_to(ROOT))
            page["status"] = (
                "local_ocr_extracted_reference"
                if ocr["status"] == "extracted"
                else "local_reference_ocr_failed"
            )
    fields = list(dict.fromkeys(k for r in rows for k in r))
    write_table([{k: r.get(k) for k in fields} for r in rows], OUT / "aggregates")
    write_table(raw_rows, OUT / "native_table_rows")
    (OUT / "page_audit.json").write_text(
        json.dumps(pages, ensure_ascii=False, indent=2) + "\n"
    )
    (OUT / "document_audit.json").write_text(
        json.dumps(documents, ensure_ascii=False, indent=2) + "\n"
    )
    (OUT / "source_inventory.json").write_text(
        json.dumps(sources, ensure_ascii=False, indent=2) + "\n"
    )
    (OUT / "additional_sources.json").write_text(
        json.dumps(
            [
                {**d, "expected_pages": d["pages"]}
                for d in documents
                if d["reference_kind"] != "district_electoral_reference"
            ],
            ensure_ascii=False,
            indent=2,
        )
        + "\n"
    )
    report = {
        "documents": len(documents),
        "pages": len(pages),
        "aggregate_records": len(rows),
        "native_table_rows": len(raw_rows),
        "ocr_pages_selected": len(tasks),
        "document_reference_kind": dict(
            collections.Counter(d["reference_kind"] for d in documents)
        ),
        "documents_with_aggregate_quality_flags": len(
            {r["source_sha256"] for r in rows if r["quality_flags"]}
        ),
        "page_status": dict(collections.Counter(r["status"] for r in pages)),
        "record_kind": dict(collections.Counter(r["record_kind"] for r in rows)),
        "quality_flags": dict(
            collections.Counter(
                f for r in rows for f in r["quality_flags"].split(";") if f
            )
        ),
        "quality_claim": (
            "District/block aggregates and reference tables do not establish "
            "named-GP office reservations. Missing counts and printed "
            "contradictions remain explicit."
        ),
    }
    (OUT / "parse_report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
