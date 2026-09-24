"""Read every GP-president table in Tamil Nadu Gazette 318 of 2011.

PDF pages 3–153 contain the new GO61 roster. The GO60 amendments on pages 1–2
are a separate source operation, not additional roster rows. Native text is
split using the printed column rules; an empty category remains unknown.
"""

import argparse
import collections
import csv
import hashlib
import itertools
import json
import re
from pathlib import Path

import pdfplumber
import pyarrow as pa
import pyarrow.parquet as pq
from pdfplumber.utils.text import extract_text

from local_elections.common.runlog import command
from local_elections.paths import ROOT

SOURCE = ROOT / "data/source_search/early_heads/raw/tn_1_58_2011_318_en.pdf"
SOURCE_URL = "https://tnrd.tn.gov.in/project/go_files/1_58_2011_318_en.pdf"
OUT = ROOT / "data/tn/derived/heads_2011"
VERSION = 1
UNION = re.compile(
    r"^(.*?)\s*[.]?P(?:ANCHAYAT|ANCHAYT|ANACHAYAT|ANCHYAT)\s+UNION\b", re.I
)
CATEGORIES = {
    "general": ("General", "UR", False),
    "generalwomen": ("General (Women)", "UR", True),
    "scgeneral": ("SC (General)", "SC", False),
    "scwomen": ("SC (Women)", "SC", True),
    "stgeneral": ("ST (General)", "ST", False),
    "stwomen": ("ST (Women)", "ST", True),
}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def relative(path):
    return str(path.relative_to(ROOT))


def reservation(raw):
    """Normalize printed spelling/punctuation, never impute a blank category."""
    key = re.sub(r"[^a-z]", "", raw.lower())
    key = key.replace("genaral", "general").replace("woman", "women")
    if not key:
        return None, None, None
    if key not in CATEGORIES:
        raise ValueError(f"Unrecognized printed category: {raw!r}")
    return CATEGORIES[key]


def union_identity(name, district):
    key = re.sub(r"\s+", "", name.upper())
    # Same page's explicit continuation, audited on PDF143; raw headings remain.
    if district == "TIRUNELVELI" and key == "ALANKULAM":
        key = "ALANGULAM"
    return key


def extract_layout(source):
    pages = []
    with pdfplumber.open(source) as pdf:
        if len(pdf.pages) != 153:
            raise ValueError("Expected 153 source PDF pages")
        for page in pdf.pages[2:]:
            lines = page.extract_text_lines(return_chars=True)
            headers = [
                line
                for line in lines
                if re.fullmatch(r"[0-9.() ]+", line["text"])
                and re.sub(r"[^0-9]", "", line["text"]) in ("123123", "123456", "123")
            ]
            if len(headers) != 1:
                raise ValueError(f"Column header ambiguous on page {page.page_number}")
            header = headers[0]
            y = (header["top"] + header["bottom"]) / 2
            boundaries = sorted(
                {
                    round((r["x0"] + r["x1"]) / 2, 2)
                    for r in page.rects
                    if r["x1"] - r["x0"] < 1.5
                    and r["bottom"] - r["top"] > 2
                    and r["top"] <= y <= r["bottom"]
                }
            )
            if len(boundaries) not in (4, 7):
                raise ValueError(f"Column geometry ambiguous: page {page.page_number}")
            bottom = max(r["bottom"] for r in page.rects)
            columns = []
            for side in range((len(boundaries) - 1) // 3):
                edges = boundaries[side * 3 : side * 3 + 4]
                crop = page.crop((edges[0], header["bottom"] + 1, edges[-1], bottom))
                records = []
                for line_number, line in enumerate(crop.extract_text_lines(), 1):
                    cells = []
                    for left, right in itertools.pairwise(edges):
                        chars = [
                            char
                            for char in line["chars"]
                            if left <= (char["x0"] + char["x1"]) / 2 < right
                        ]
                        cells.append(extract_text(chars).strip())
                    records.append(
                        {
                            "line": line_number,
                            "text": line["text"],
                            "bbox": [
                                line["x0"],
                                line["top"],
                                line["x1"],
                                line["bottom"],
                            ],
                            "cells": cells,
                        }
                    )
                columns.append(records)
            pages.append(
                {
                    "page": page.page_number,
                    "district_headings": [
                        line["text"]
                        for line in lines
                        if re.fullmatch(r".+\s+District", line["text"], re.I)
                    ],
                    "boundaries": boundaries,
                    "columns": columns,
                }
            )
            page.close()
    return pages


def parse_layout(pages, source_sha):
    rows, audits = [], []
    district = ""
    union_name = ""
    union_heading = None
    for page in pages:
        headings = page["district_headings"]
        if headings:
            if len(headings) != 1:
                raise ValueError("Multiple district headings on one source page")
            district = re.sub(r"\s+District$", "", headings[0], flags=re.I).upper()
            union_name = ""
            union_heading = None
        for side, lines in enumerate(page["columns"]):
            side_rows, fragments = [], []
            for line in lines:
                matched = UNION.match(line["text"])
                if matched:
                    union_name = matched[1].strip(" .")
                    union_heading = {"page": page["page"], "column": side + 1, **line}
                    continue
                if re.fullmatch(r"\(?Contd[., ]*\)?", line["text"], re.I):
                    continue
                serial, name, category = line["cells"]
                if serial.isdigit():
                    if not district or not union_name or union_heading is None:
                        raise ValueError(f"Missing geography at page {page['page']}")
                    row = {
                        "source_page": page["page"],
                        "source_column": side + 1,
                        "source_line": line["line"],
                        "district": district,
                        "union_name_raw": union_name,
                        "union_key": union_identity(union_name, district),
                        "union_heading": union_heading,
                        "cells": [serial, name, category],
                        "fragments": [line],
                    }
                    side_rows.append(row)
                elif not serial and bool(name) != bool(category):
                    fragments.append((line, union_identity(union_name, district)))
                elif any(line["cells"]):
                    raise ValueError(f"Unaccounted source line {page['page']}: {line}")
            for fragment, union_key in fragments:
                field = 1 if fragment["cells"][1] else 2
                center = sum(fragment["bbox"][1::2]) / 2
                candidates = []
                for row in side_rows:
                    if row["union_key"] != union_key or row["cells"][field]:
                        continue
                    bbox = row["fragments"][0]["bbox"]
                    distance = abs(center - sum(bbox[1::2]) / 2)
                    if distance <= 8:
                        candidates.append((distance, row))
                if len(candidates) != 1:
                    raise ValueError(f"Ambiguous displaced cell: {fragment}")
                row = candidates[0][1]
                row["cells"][field] = fragment["cells"][field]
                row["fragments"].append(fragment)
            rows.extend(side_rows)
        audits.append(
            {
                "source_page": page["page"],
                "table_columns": len(page["columns"]),
                "office_rows": sum(r["source_page"] == page["page"] for r in rows),
                "unaccounted_lines": 0,
            }
        )
    output = []
    for row in rows:
        serial, name, code = row["cells"]
        if not name:
            raise ValueError(f"Missing GP name at {row['source_page']}")
        category, caste, woman = reservation(code)
        key = (
            f"{source_sha}:{row['source_page']}:"
            f"{row['source_column']}:{row['source_line']}"
        )
        flags = [] if category else ["printed_category_blank"]
        if len(row["fragments"]) > 1:
            flags.append("displaced_native_cell_rejoined_by_geometry")
        bounds = [f["bbox"] for f in row["fragments"]]
        output.append(
            {
                "row_id": hashlib.sha256(key.encode()).hexdigest()[:24],
                "state": "Tamil Nadu",
                "year": 2011,
                "tier": "gp_head",
                "office": "village_panchayat_president",
                "district": row["district"],
                "union_name_raw": row["union_name_raw"],
                "union_key": row["union_key"],
                "gp_name_raw": name,
                "gp_name": " ".join(name.split()),
                "source_serial": serial,
                "reservation_raw": code,
                "reservation": category,
                "caste_reservation": caste,
                "woman_reserved": woman,
                "source_path": relative(SOURCE),
                "source_url": SOURCE_URL,
                "source_sha256": source_sha,
                "source_page": row["source_page"],
                "source_column": row["source_column"],
                "source_line": row["source_line"],
                "source_bbox": json.dumps(
                    [
                        min(b[0] for b in bounds),
                        min(b[1] for b in bounds),
                        max(b[2] for b in bounds),
                        max(b[3] for b in bounds),
                    ]
                ),
                "coordinate_system": "PDF points, top-left origin",
                "raw_fragments": json.dumps(row["fragments"], ensure_ascii=False),
                "union_heading_evidence": json.dumps(row["union_heading"]),
                "notification": "GO61; II(2)/RDPR/396(g-2)/2011",
                "notification_date": "2011-09-09",
                "listing_scope": "named_roster_including_explicit_General",
                "review_status": "native_extracted_structurally_audited",
                "quality_flags": ";".join(flags),
            }
        )
    return output, audits


def serial_audit(rows):
    groups = collections.defaultdict(list)
    for row in rows:
        groups[row["district"], row["union_key"]].append(row)
    issues = []
    for (district, union), group in sorted(groups.items()):
        serials = [int(row["source_serial"]) for row in group]
        duplicates = sorted(
            n for n, count in collections.Counter(serials).items() if count > 1
        )
        missing = sorted(set(range(1, max(serials) + 1)) - set(serials))
        if duplicates or missing or serials != list(range(1, len(serials) + 1)):
            issues.append(
                {
                    "district": district,
                    "union_key": union,
                    "rows": len(group),
                    "duplicate_serials": duplicates,
                    "missing_serials": missing,
                    "source_pages": sorted({r["source_page"] for r in group}),
                }
            )
            for row in group:
                row["quality_flags"] = ";".join(
                    filter(None, [row["quality_flags"], "printed_union_serial_anomaly"])
                )
    return issues


def write_csv(path, rows):
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


@command("parse", state="Tamil Nadu", source="gazette_2011_318_gp_presidents")
def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUT)
    args = parser.parse_args()
    manifest = ROOT / "data/source_search/early_heads/source_manifest.csv"
    sources = list(csv.DictReader(manifest.open()))
    source_record = next(r for r in sources if r["path"] == relative(SOURCE))
    sha = digest(SOURCE)
    if sha != source_record["sha256"]:
        raise ValueError("Source PDF differs from preserved acquisition hash")
    pages = extract_layout(SOURCE)
    rows, pages_audit = parse_layout(pages, sha)
    issues = serial_audit(rows)
    if len(rows) != 12524 or len(pages) != 151:
        raise ValueError("Full-document row/page contract failed")
    if len({r["row_id"] for r in rows}) != len(rows):
        raise ValueError("Duplicate source occurrence keys")
    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "gp_president_reservations.csv", rows)
    table = pa.Table.from_pylist(rows)
    pq.write_table(table, args.output / "gp_president_reservations.parquet")
    if (
        pq.read_table(args.output / "gp_president_reservations.parquet").to_pylist()
        != rows
    ):
        raise ValueError("Parquet roundtrip failed")
    write_csv(args.output / "page_audit.csv", pages_audit)
    (args.output / "native_layout.json").write_text(
        json.dumps(pages, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    counts = collections.Counter((r["district"], r["union_key"]) for r in rows)
    write_csv(
        args.output / "union_counts.csv",
        [
            {"district": d, "union_key": u, "office_rows": n}
            for (d, u), n in sorted(counts.items())
        ],
    )
    write_csv(
        args.output / "category_crosswalk.csv",
        [
            {
                "reservation_raw": raw,
                "reservation": reservation(raw)[0],
                "caste_reservation": reservation(raw)[1],
                "woman_reserved": reservation(raw)[2],
                "office_rows": n,
            }
            for raw, n in sorted(
                collections.Counter(r["reservation_raw"] for r in rows).items()
            )
        ],
    )
    report = {
        "parser_version": VERSION,
        "parser_sha256": digest(Path(__file__)),
        "pdfplumber_version": pdfplumber.__version__,
        "pyarrow_version": pa.__version__,
        "source": source_record,
        "roster_pdf_pages": [3, 153],
        "office_rows": len(rows),
        "districts_as_printed": len({r["district"] for r in rows}),
        "union_groups": len(counts),
        "category_missing": sum(r["reservation"] is None for r in rows),
        "sex_is_office_reservation_not_observed_winner": True,
        "serial_anomalies": issues,
        "limitations": [
            "Names not individually visually verified",
            "No cross-year GP identifier established",
            "GO60 amendments on PDF1–2 remain separate from the GO61 roster",
            "Later amendments and actual election implementation not established",
        ],
    }
    (args.output / "validation.json").write_text(json.dumps(report, indent=2) + "\n")
    print(
        json.dumps(
            {
                k: report[k]
                for k in (
                    "office_rows",
                    "districts_as_printed",
                    "union_groups",
                    "category_missing",
                    "serial_anomalies",
                )
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
