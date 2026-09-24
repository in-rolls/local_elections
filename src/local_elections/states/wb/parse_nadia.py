"""Read Nadia 2008 Form A1 native tables, checking seat and reservation totals.

Four-column constituency tables and nine-column combined schedules are
supported. Unsupported layouts and ambiguous cells remain in the audit.
Blank reservation cells mean no reservation only within an identified A1
schedule. A complete schedule must reconcile all four printed GP totals.
"""

import collections
import csv
import hashlib
import json
import re

from local_elections.common.runlog import command
from local_elections.paths import ROOT
from local_elections.states.wb.extract_native import OUT as CACHE
from local_elections.states.wb.parse_results import write_table

OUT = ROOT / "data/wb/derived/nadia_2008"
SOURCE = ROOT / "data/wb/gp_source_search/historical_expansion"


def tidy(value):
    return " ".join((value or "").split())


def number(value):
    value = tidy(value).upper()
    if value in {"NIL", "-", "--", "ZERO"}:
        return 0
    match = re.fullmatch(r"(\d+)(?:\s*\([A-Z ]+\))?", value)
    return int(match[1]) if match else None


def allocated(value):
    value = (value or "").strip()
    if not re.fullmatch(r"\d+(?:[ \t]*[,&\n][ \t]*\d+)*", value):
        return None
    return [int(v) for v in re.findall(r"\d+", value)]


def reservation(value, seats, women=False):
    compact = re.sub(r"[\s.()\[\]\-–—,:/]+", "", (value or "").upper())
    if compact in {"", "NIL", "NONE"}:
        return {}, []
    compact = compact.replace("WOMEN", "W").replace("WOMAN", "W")
    matches = list(re.finditer(r"(\d*)(SCW?|STW?|W)", compact))
    if not matches or "".join(m[0] for m in matches) != compact:
        return {}, ["reservation_cell_unread"]
    result = {}
    for match in matches:
        seat = int(match[1]) if match[1] else seats[0] if len(seats) == 1 else None
        category = match[2]
        if seat not in seats or seat in result:
            return {}, ["reservation_seat_ambiguous"]
        if women and not category.endswith("W"):
            return {}, ["women_marker_missing"]
        if not women and category == "W":
            return {}, ["caste_marker_missing"]
        result[seat] = category
    return result, []


def parse_document(record, path):
    all_text = "\n".join(page["text"] for page in record["pages"])
    block_match = re.search(r"BLOCK\s*[:\-–]*\s*([^\n]+)", all_text, re.I)
    block = tidy(block_match[1]) if block_match else None
    gp_table = any(
        "NAME OF" in tidy(row[0]).upper() and "GRAM" in tidy(row[0]).upper()
        for page in record["pages"]
        for table in page["tables"]
        for row in table["rows"]
        if row
    )
    audit = {
        "source_path": path,
        "source_sha256": record["sha256"],
        "pages": len(record["pages"]),
        "status": "not_identified_gp_schedule",
        "unresolved_rows": [],
        "summaries": [],
    }
    if not gp_table:
        return [], audit
    summaries, rows = [], []
    gp, area = None, None
    for page in record["pages"]:
        for ti, table in enumerate(page["tables"], 1):
            for ri, raw in enumerate(table["rows"], 1):
                source_raw = list(raw)
                if len(raw) == 10:
                    raw = [*raw[:5], tidy(raw[5]) + " " + tidy(raw[6]), *raw[7:]]
                if len(raw) not in {4, 5, 9}:
                    audit["unresolved_rows"].append(
                        {
                            "page": page["page"],
                            "table": ti,
                            "row": ri,
                            "reason": "unsupported_width",
                            "raw": raw,
                        }
                    )
                    continue
                if (
                    len(raw) in {5, 9}
                    and raw[0]
                    and number(raw[0]) is None
                    and all(number(v) is not None for v in raw[1:5])
                ):
                    gp = tidy(raw[0])
                    summary = {
                        "gram_panchayat": gp,
                        "total": number(raw[1]),
                        "sc": number(raw[2]),
                        "st": number(raw[3]),
                        "women": number(raw[4]),
                        "source_page": page["page"],
                    }
                    summaries.append(summary)
                if len(raw) == 5:
                    continue
                cells = raw[-4:]
                seats = allocated(cells[1])
                if not seats or tidy(cells[0]) in {"3", "(3)"}:
                    if (
                        cells[1]
                        and tidy(cells[0]) not in {"3", "(3)"}
                        and "/" in tidy(cells[0])
                    ):
                        audit["unresolved_rows"].append(
                            {
                                "page": page["page"],
                                "table": ti,
                                "row": ri,
                                "reason": "allocated_cell_unread",
                                "raw": source_raw,
                                "bbox": table["bbox"],
                            }
                        )
                    continue
                if cells[0]:
                    area = tidy(cells[0])
                if len(raw) == 9 and tidy(raw[0]) and number(raw[0]) is None:
                    gp = tidy(raw[0])
                issues = []
                if not gp:
                    issues.append("gp_name_missing")
                if not area or "/" not in area:
                    issues.append("constituency_identity_unresolved")
                castes, cf = reservation(cells[2], seats)
                females, wf = reservation(cells[3], seats, women=True)
                issues.extend(cf + wf)
                for seat in seats:
                    flags = list(issues)
                    caste = castes.get(seat, "UR").removesuffix("W")
                    female = females.get(seat, "")
                    if female.startswith(("SC", "ST")) and not female.startswith(caste):
                        flags.append("caste_women_columns_conflict")
                    if castes.get(seat, "").endswith("W") and not female:
                        flags.append("caste_women_columns_conflict")
                    row_id = hashlib.sha256(
                        json.dumps(
                            [record["sha256"], page["page"], ti, ri, seat]
                        ).encode()
                    ).hexdigest()[:20]
                    rows.append(
                        {
                            "row_id": row_id,
                            "record_kind": "gp_ward_reservation",
                            "stage": "verify_per_document",
                            "state": "West Bengal",
                            "district": "Nadia",
                            "year": 2008,
                            "block_printed": block,
                            "gram_panchayat": gp,
                            "seat_no": seat,
                            "constituency_area_raw": area,
                            "allocated_raw": cells[1],
                            "raw_cells": json.dumps(source_raw, ensure_ascii=False),
                            "caste_raw": cells[2],
                            "women_raw": cells[3],
                            "caste_reservation": None if cf else caste,
                            "woman_reserved": None if wf else int(bool(female)),
                            "source_path": path,
                            "source_sha256": record["sha256"],
                            "source_page": page["page"],
                            "source_table": ti,
                            "source_row": ri,
                            "source_table_bbox": json.dumps(table["bbox"]),
                            "quality_flags": ";".join(sorted(set(flags))),
                        }
                    )
    checks = []
    if not summaries:
        checks.append("printed_gp_totals_missing")
    for summary in summaries:
        subset = [r for r in rows if r["gram_panchayat"] == summary["gram_panchayat"]]
        values = [r["seat_no"] for r in subset]
        if sorted(values) != list(range(1, summary["total"] + 1)):
            checks.append("seat_universe_mismatch")
        actual = [
            sum(r["caste_reservation"] == k for r in subset) for k in ["SC", "ST"]
        ]
        actual.append(sum(r["woman_reserved"] == 1 for r in subset))
        if actual != [summary[k] for k in ["sc", "st", "women"]]:
            checks.append("reservation_totals_mismatch")
    if {r["gram_panchayat"] for r in rows} - {s["gram_panchayat"] for s in summaries}:
        checks.append("gp_without_printed_totals")
    if audit["unresolved_rows"]:
        checks.append("unsupported_rows")
    for row in rows:
        flags = sorted(set(filter(None, row["quality_flags"].split(";"))) | set(checks))
        row["quality_flags"] = ";".join(flags)
        row["review_status"] = "needs_review" if flags else "source_controls_passed"
    audit.update(
        status="parsed" if rows else "gp_rows_unresolved",
        summaries=summaries,
        checks=sorted(set(checks)),
        seats=len(rows),
    )
    return rows, audit


@command("parse", state="West Bengal", source="nadia_2008")
def main():
    rows, audits, pages, seen = [], [], [], set()
    for metadata in csv.DictReader((SOURCE / "manifest.csv").open()):
        if (
            metadata["status"] != "downloaded"
            or "PanchayatElection08" not in metadata["url"]
            or not metadata["file"].lower().endswith(".pdf")
        ):
            continue
        digest = metadata["sha256"]
        path = str((SOURCE / metadata["file"]).relative_to(ROOT))
        if hashlib.sha256((ROOT / path).read_bytes()).hexdigest() != digest:
            raise ValueError(f"Source manifest hash differs: {path}")
        if digest in seen:
            audits.append(
                {
                    "source_path": path,
                    "status": "byte_duplicate",
                    "source_sha256": digest,
                }
            )
            continue
        seen.add(digest)
        cache = CACHE / (digest + ".json")
        if not cache.exists():
            audits.append({"source_path": path, "status": "native_extraction_missing"})
            continue
        record = json.loads(cache.read_text())
        parsed, audit = parse_document(record, path)
        for page in record["pages"]:
            count = sum(r["source_page"] == page["page"] for r in parsed)
            pages.append(
                {
                    "source_path": path,
                    "source_sha256": digest,
                    "source_page": page["page"],
                    "source_page_bbox": [0, 0, page["width"], page["height"]],
                    "status": "native_seats_parsed" if count else audit["status"],
                    "rows": count,
                    "native_cache": str(cache.relative_to(ROOT)),
                    "raw_text": page["text"],
                }
            )
        rows.extend(parsed)
        audits.append(audit)
    duplicates = collections.Counter(
        (r["block_printed"], r["gram_panchayat"], r["seat_no"]) for r in rows
    )
    for row in rows:
        if (
            duplicates[(row["block_printed"], row["gram_panchayat"], row["seat_no"])]
            > 1
        ):
            row["quality_flags"] = (row["quality_flags"] + ";duplicate_seat_key").strip(
                ";"
            )
            row["review_status"] = "needs_review"
    OUT.mkdir(parents=True, exist_ok=True)
    write_table(rows, OUT / "gp_seats")
    (OUT / "document_audit.json").write_text(
        json.dumps(audits, ensure_ascii=False, indent=2) + "\n"
    )
    (OUT / "page_audit.json").write_text(
        json.dumps(pages, ensure_ascii=False, indent=2) + "\n"
    )
    report = {
        "pages": len(pages),
        "documents": len(audits),
        "document_status": dict(collections.Counter(a["status"] for a in audits)),
        "seats": len(rows),
        "review_status": dict(collections.Counter(r["review_status"] for r in rows)),
        "quality_claim": (
            "Source controls test completeness and counts, "
            "not field-level accuracy or order finality. Review before use."
        ),
    }
    (OUT / "parse_report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
