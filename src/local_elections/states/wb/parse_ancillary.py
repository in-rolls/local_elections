"""Extract election administration tables separately from reservation records.

Polling infrastructure counts have their own printed controls. Nomination,
withdrawal, and administrative notices retain every native/OCR page and line;
uncertain readers cannot create electoral victories or reservation assignments.
"""

import argparse
import collections
import csv
import hashlib
import json
import re
from concurrent.futures import ThreadPoolExecutor

from local_elections.common.runlog import command
from local_elections.paths import ROOT
from local_elections.states.wb.parse_nadia import tidy
from local_elections.states.wb.parse_results import write_table
from local_elections.states.wb.parse_ward_schedules import ocr_page

OUT = ROOT / "data/wb/derived/ancillary"
FIELDS = [
    "main_polling_stations",
    "polling_stations_over_1250_excluding_1400",
    "polling_stations_over_1400_divided_into_two",
    "sectors",
    "single_premises",
    "double_premises",
    "triple_premises",
    "quadruple_premises",
    "total_premises",
    "total_polling_stations",
    "total_electors",
]


def selected(metadata):
    return (
        metadata["district"] == "Alipurduar"
        and metadata["election_year"] == "2018"
        and metadata["content_kind"] == "reservation_or_election_source"
        and "CONSTITUENCY" not in metadata["file"]
    ) or (
        metadata["district"] == "Purulia"
        and metadata["election_year"] == "2013"
        and metadata["content_kind"] == "election_administration_notice"
    )


def count(raw):
    match = re.fullmatch(r"(\d+)(?:\s*\([^()]+\))?", tidy(raw))
    return int(match[1]) if match else None


def parse_polling_infrastructure(record, path):
    rows = []
    for page in record["pages"]:
        for ti, table in enumerate(page["tables"], 1):
            header = " ".join(tidy(c) for r in table["rows"][:2] for c in r)
            if "Total Elector" not in header or "No. of Premises" not in header:
                continue
            for ri, raw in enumerate(table["rows"], 1):
                if len(raw) != 12 or count(raw[1]) is None:
                    continue
                values = [count(c) for c in raw[1:]]
                flags = (
                    [] if all(v is not None for v in values) else ["count_cell_unread"]
                )
                rows.append(
                    {
                        "state": "West Bengal",
                        "district": "Alipurduar",
                        "year": 2018,
                        "record_kind": "polling_infrastructure",
                        "block_printed": tidy(raw[0]),
                        "row_role": "printed_district_total"
                        if tidy(raw[0]).upper() == "TOTAL"
                        else "block",
                        **dict(zip(FIELDS, values, strict=True)),
                        "source_path": path,
                        "source_sha256": record["sha256"],
                        "source_page": page["page"],
                        "source_table": ti,
                        "source_row": ri,
                        "source_table_bbox": json.dumps(table["bbox"]),
                        "raw_cells": json.dumps(raw, ensure_ascii=False),
                        "quality_flags": ";".join(flags),
                        "review_status": "needs_review",
                    }
                )
    totals = [r for r in rows if r["row_role"] == "printed_district_total"]
    blocks = [r for r in rows if r["row_role"] == "block"]
    checks = []
    if len(totals) != 1:
        checks.append("printed_total_missing_or_duplicated")
    elif any(
        any(r[k] is None for r in rows) or sum(r[k] for r in blocks) != totals[0][k]
        for k in FIELDS
    ):
        checks.append("printed_total_mismatch")
    for row in rows:
        flags = sorted(set(filter(None, row["quality_flags"].split(";"))) | set(checks))
        row["quality_flags"] = ";".join(flags)
        row["review_status"] = "needs_review" if flags else "source_controls_passed"
    return rows


def ocr_lines(record):
    groups = collections.defaultdict(list)
    for word in record.get("words", []):
        if word.get("text", "").strip():
            groups[tuple(word[k] for k in ["block_num", "par_num", "line_num"])].append(
                word
            )
    result = []
    for key, words in groups.items():
        box = [
            min(int(w["left"]) for w in words),
            min(int(w["top"]) for w in words),
            max(int(w["left"]) + int(w["width"]) for w in words),
            max(int(w["top"]) + int(w["height"]) for w in words),
        ]
        result.append(
            {
                "reader_line_id": ":".join(key),
                "raw_text": " ".join(w["text"] for w in words),
                "source_bbox": json.dumps(box),
                "bbox_coordinate_system": "rendered_image_pixels",
                "raw_words": json.dumps(words, ensure_ascii=False),
            }
        )
    return result


PARTIES = [
    "AITC",
    "BSP",
    "BJP",
    "CPI",
    "CPI_M",
    "INC",
    "NCP",
    "AIFB",
    "RSP",
    "Others",
    "IND",
]


def parse_candidate_reports(ocr, path):
    """Preserve source report stages; single nominations are not election wins."""
    lines = ocr_lines(ocr)
    tier, rows = None, []
    if "TotalUncontested" in path:
        for line in lines:
            tokens = line["raw_text"].split()
            if not tokens or tokens[0] != "ALIPURDUAR" or len(tokens) != 10:
                continue
            values = [count(t) for t in tokens[1:]]
            for i, unit in enumerate(
                ["gram_panchayat", "panchayat_samiti", "zilla_parishad"]
            ):
                rows.append(
                    {
                        "record_kind": "uncontested_seat_totals_after_withdrawal",
                        "tier": unit,
                        "report_date_raw": None,
                        "row_role": "district_total",
                        "fields": {
                            "total_seats": values[3 * i],
                            "uncontested_seats": values[3 * i + 1],
                            "zero_valid_nomination_seats": values[3 * i + 2],
                        },
                        **line,
                    }
                )
    else:
        kind = (
            "contesting_candidate_totals"
            if "ContestingCandidate" in path
            else "nomination_totals"
            if "finalnomination" in path
            else "withdrawal_totals"
            if "WithdrawalReport" in path
            else None
        )
        if kind is None:
            return []
        for line in lines:
            text = line["raw_text"]
            if re.fullmatch(r"Zilla\s+Parishad", text, re.I):
                tier = "zilla_parishad"
            elif re.fullmatch(r"Panchayat\s+Samit[yi]", text, re.I):
                tier = "panchayat_samiti"
            elif re.fullmatch(r"Gram\s+Panchayat", text, re.I):
                tier = "gram_panchayat"
            match = re.match(r"^(ALIPURDUAR|Total|\d{2}\.\d{2}\.\d{4})\s+(.+)$", text)
            if not match or not tier:
                continue
            raw_values = [
                v.strip("|{}[]") for v in match[2].split() if v.strip("|{}[]")
            ]
            keys = [
                "seats",
                *(
                    ["contesting_seats"]
                    if kind == "contesting_candidate_totals"
                    else []
                ),
                *PARTIES,
                "total_candidates",
            ]
            fields = dict.fromkeys(keys)
            if len(raw_values) == len(keys):
                fields = dict(zip(keys, [count(v) for v in raw_values], strict=True))
            rows.append(
                {
                    "record_kind": kind,
                    "tier": tier,
                    "report_date_raw": match[1] if re.match(r"\d", match[1]) else None,
                    "row_role": "dated_report"
                    if re.match(r"\d", match[1])
                    else "printed_total",
                    "fields": fields,
                    **line,
                }
            )
    for row in rows:
        flags = ["ocr_not_independently_verified"]
        fields = row.pop("fields")
        if any(v is None for v in fields.values()):
            flags.append("count_cell_unread_or_alignment_unresolved")
        elif (
            "total_candidates" in fields
            and sum(fields[p] for p in PARTIES) != fields["total_candidates"]
        ):
            flags.append("party_total_mismatch")
        row.update(
            state="West Bengal",
            district="Alipurduar",
            year=2018,
            source_path=path,
            source_sha256=ocr["source_sha256"],
            source_page=ocr["source_page"],
            counts_json=json.dumps(fields),
            quality_flags=";".join(flags),
            review_status="needs_review",
        )
    return rows


def parse_single_nomination_rows(ocr, path):
    if not any(k in path for k in ["ReportonSingleNIL", "Single_20or_20No"]):
        return []
    rows, tier = [], None
    for line in ocr_lines(ocr):
        raw = line["raw_text"]
        if "PANCHAYAT SAMITI" in raw:
            tier = "panchayat_samiti"
        elif "GRAM PANCHAYAT" in raw:
            tier = "gram_panchayat"
        if not tier or not raw.endswith("Nil"):
            continue
        match = re.search(
            r"([A-Za-z][A-Za-z-]+/(?:PS-)?[IVXLCDM0-9]+-?\d*)(?=\s|$)", raw
        )
        if not match:
            continue
        rows.append(
            {
                "state": "West Bengal",
                "district": "Alipurduar",
                "year": 2018,
                "record_kind": "single_valid_nomination_after_scrutiny",
                "tier": tier,
                "constituency_raw": match[1],
                "no_valid_nomination_column_raw": "Nil",
                "source_path": path,
                "source_sha256": ocr["source_sha256"],
                "source_page": ocr["source_page"],
                "quality_flags": "ocr_not_independently_verified",
                "review_status": "needs_review",
                **line,
            }
        )
    return rows


@command("parse", state="West Bengal", source="ancillary_administration")
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ocr", action="store_true")
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    index = {
        r["source_path"]: r
        for r in json.loads((ROOT / "data/wb/derived/native/index.json").read_text())
    }
    documents, pages, rows, tasks = [], [], [], []
    for metadata in csv.DictReader(
        (ROOT / "data/wb/gp_source_search/manual_entry_index.csv").open()
    ):
        if not selected(metadata):
            continue
        path = "data/wb/" + metadata["file"]
        source = index[path]
        if hashlib.sha256((ROOT / path).read_bytes()).hexdigest() != metadata["sha256"]:
            raise ValueError(f"Source hash differs: {path}")
        record = json.loads((ROOT / source["cache"]).read_text())
        parsed = parse_polling_infrastructure(record, path)
        rows.extend(parsed)
        documents.append(
            {
                "source_path": path,
                "source_sha256": metadata["sha256"],
                "pages": len(record["pages"]),
                "parsed_rows": len(parsed),
            }
        )
        for page in record["pages"]:
            pages.append(
                {
                    "source_path": path,
                    "source_sha256": metadata["sha256"],
                    "source_page": page["page"],
                    "district": metadata["district"],
                    "year": metadata["election_year"],
                    "content_kind": metadata["content_kind"],
                    "status": "native_table_parsed"
                    if parsed
                    else "reference_page_requires_review",
                    "source_page_bbox": [0, 0, page["width"], page["height"]],
                    "raw_text": page["text"],
                    "native_cache": source["cache"],
                }
            )
            if not page["tables"]:
                tasks.append((path, metadata["sha256"], page["page"], str(OUT)))
    if args.ocr:
        with ThreadPoolExecutor(max_workers=2) as pool:
            list(pool.map(ocr_page, tasks))
    lines, candidate_rows, single_rows = [], [], []
    for page in pages:
        cache = OUT / "ocr" / page["source_sha256"] / f"{page['source_page']:04d}.json"
        if not cache.exists():
            continue
        ocr = json.loads(cache.read_text())
        page["ocr_cache"] = str(cache.relative_to(ROOT))
        page["status"] = (
            "ocr_reference_extracted" if ocr["status"] == "extracted" else "ocr_failed"
        )
        candidate_rows.extend(parse_candidate_reports(ocr, page["source_path"]))
        single_rows.extend(parse_single_nomination_rows(ocr, page["source_path"]))
        for line in ocr_lines(ocr):
            lines.append(
                {
                    "source_path": page["source_path"],
                    "source_sha256": page["source_sha256"],
                    "source_page": page["source_page"],
                    "district": page["district"],
                    "year": page["year"],
                    "record_kind": "reference_text_line",
                    "review_status": "not_an_electoral_observation",
                    **line,
                }
            )
    write_table(rows, OUT / "polling_infrastructure")
    if lines:
        write_table(lines, OUT / "reference_lines")
    if candidate_rows:
        write_table(candidate_rows, OUT / "candidate_reports")
    if single_rows:
        write_table(single_rows, OUT / "single_valid_nominations")
    (OUT / "document_audit.json").write_text(
        json.dumps(documents, ensure_ascii=False, indent=2) + "\n"
    )
    (OUT / "page_audit.json").write_text(
        json.dumps(pages, ensure_ascii=False, indent=2) + "\n"
    )
    report = {
        "documents": len(documents),
        "pages": len(pages),
        "polling_infrastructure_rows": len(rows),
        "reference_lines": len(lines),
        "candidate_report_rows": len(candidate_rows),
        "single_valid_nomination_rows": len(single_rows),
        "page_status": dict(collections.Counter(p["status"] for p in pages)),
        "quality_claim": (
            "Reference lines retain reader evidence, not validated electoral "
            "observations. Polling-station counts are not "
            "Panchayat Samiti reservations."
        ),
    }
    (OUT / "parse_report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
