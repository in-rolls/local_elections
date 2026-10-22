"""Independent native-text control audit; does not create pooled source records."""

import csv
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path

import pdfplumber

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "raw/tn_1_58_2011_318_en.pdf"
OUT = ROOT / "tn_review/2011_controls"
OUT.mkdir(exist_ok=True)
EXPECTED_SHA256 = "340e18bc66c484a97c9ea7634f3ba6aa12ab715f2b73745c1d96f1b25bcf3ffd"
if hashlib.sha256(SOURCE.read_bytes()).hexdigest() != EXPECTED_SHA256:
    raise ValueError("Source bytes differ from the audited PDF")
CATEGORY = re.compile(
    r"(?:S\.?\s*[CT]\.?\s*\(?\s*(?:Gen[ae]ral|Wom[ae]n)\s*\)?|Gen[ae]ral\s*\(?\s*Wom[ae]n\s*\)?|Gen[ae]ral)",
    re.I,
)
rows, pages, other, headings = [], [], [], []
with pdfplumber.open(SOURCE) as pdf:
    for pn in range(3, 154):
        page = pdf.pages[pn - 1]
        edges = [e for e in page.edges if e["orientation"] == "v"]
        xlo, xhi = min(e["x0"] for e in edges), max(e["x0"] for e in edges)
        central = [
            e
            for e in edges
            if xlo + 0.4 * (xhi - xlo) < e["x0"] < xlo + 0.6 * (xhi - xlo)
        ]
        midpoint = (
            331.6
            if pn == 77
            else max(central, key=lambda e: e["bottom"] - e["top"])["x0"]
        )
        first = len(rows)
        for side, xmin, xmax in (
            [("single", 0, page.width)]
            if pn == 79
            else [("left", 0, midpoint), ("right", midpoint, page.width)]
        ):
            text = (
                page.crop((xmin, 15, xmax, page.height - 25)).extract_text(
                    x_tolerance=1, y_tolerance=3
                )
                or ""
            )
            (OUT / f"page-{pn}-{side}.txt").write_text(text + "\n")
            patches = {
                (99, "right"): [("5 SC (General)\nOkkarai", "5 Okkarai SC (General)")],
                (100, "right"): [
                    ("11 SC (General)\nThirumangalam", "11 Thirumangalam SC (General)"),
                    ("16 General (Women)\nAthikudi", "16 Athikudi General (Women)"),
                ],
                (127, "right"): [
                    ("General\n30 Thavalaikulam", "30 Thavalaikulam General")
                ],
                (128, "right"): [
                    ("SC (Women)\n2 Pillaiyarkulam", "2 Pillaiyarkulam SC (Women)")
                ],
            }
            for old, new in patches.get((pn, side), []):
                if old not in text:
                    raise ValueError("Reviewed split-line reading no longer matches")
                text = text.replace(old, new)

            for ln, line in enumerate(text.splitlines(), 1):
                record = {"source_page": pn, "side": side, "line": ln, "raw_text": line}
                if "district" in line.lower() or "union" in line.lower():
                    headings.append(record)
                m = re.match(
                    r"^\s*(\d+[A-Za-z.]?)\s+(.+?)\s+(" + CATEGORY.pattern + r")\s*$",
                    line,
                    re.I,
                )
                if pn == 15 and side == "left" and line == "14 Ramakrishnarajupet":
                    rows.append(
                        record
                        | {
                            "serial": "14",
                            "name": "Ramakrishnarajupet",
                            "category": None,
                        }
                    )
                    continue
                if m:
                    rows.append(
                        record | {"serial": m[1], "name": m[2], "category": m[3]}
                    )
                else:
                    other.append(record)
        pages.append(
            {"source_page": pn, "midpoint": midpoint, "parsed_rows": len(rows) - first}
        )
for name, entries in [
    ("rows", rows),
    ("pages", pages),
    ("other_lines", other),
    ("headings", headings),
]:
    (OUT / f"{name}.json").write_text(json.dumps(entries, indent=2) + "\n")
    with (OUT / f"{name}.csv").open("w") as f:
        writer = csv.DictWriter(f, fieldnames=list(entries[0]))
        writer.writeheader()
        writer.writerows(entries)
sys.stdout.write(
    json.dumps(
        {
            "rows": len(rows),
            "categories": Counter(r["category"] for r in rows),
            "other_lines": len(other),
            "pages": len(pages),
            "source_sha256": hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
        },
        indent=2,
    )
)

# Control grouping follows printed reading order and serial restarts, not name matching.
layout_pages = (ROOT / "tn_review/tn_1_58_2011_318_en.txt").read_text().split("\f")
groups, serial_anomalies = [], []
for row in rows:
    pn, serial = row["source_page"], int(row["serial"])
    heading = next(
        (
            h["raw_text"]
            for h in reversed(headings)
            if h["source_page"] == pn
            and h["side"] == row["side"]
            and h["line"] < row["line"]
            and "union" in h["raw_text"].lower()
        ),
        None,
    )
    if serial == 1:
        district = ""
        for earlier_page in range(pn, 2, -1):
            candidates = [
                line.strip()
                for line in layout_pages[earlier_page - 1].splitlines()
                if re.match(r"^\s*[A-Za-z ]+\s+District\s*$", line, re.I)
            ]
            if candidates:
                district = candidates[0]
                break
        if not district or not heading:
            raise ValueError("Missing district or union heading")
        groups.append(
            {
                "group": len(groups) + 1,
                "district": district,
                "union": heading,
                "start_page": pn,
                "rows": [],
            }
        )
    if serial != len(groups[-1]["rows"]) + 1:
        serial_anomalies.append(
            row
            | {
                "expected_position": len(groups[-1]["rows"]) + 1,
                "union": groups[-1]["union"],
            }
        )
    groups[-1]["rows"].append(row)


def canonical_category(category):
    if category is None:
        return "UNKNOWN_BLANK"
    return (
        re.sub(r"[^a-z]", "", category.lower())
        .replace("genaral", "general")
        .replace("woman", "women")
    )


category_counts = Counter(canonical_category(row["category"]) for row in rows)
union_counts, district_counts, duplicate_names = [], {}, []
for group in groups:
    members = group["rows"]
    union_counts.append(
        {k: v for k, v in group.items() if k != "rows"}
        | {
            "end_page": members[-1]["source_page"],
            "rows": len(members),
            "category_counts": dict(
                Counter(canonical_category(row["category"]) for row in members)
            ),
        }
    )
    district = district_counts.setdefault(
        group["district"],
        {
            "district": group["district"],
            "unions": 0,
            "rows": 0,
            "first_page": group["start_page"],
            "last_page": 0,
            "category_counts": Counter(),
        },
    )
    district["unions"] += 1
    district["rows"] += len(members)
    district["last_page"] = members[-1]["source_page"]
    district["category_counts"].update(
        canonical_category(row["category"]) for row in members
    )
    names = Counter(
        re.sub(r"\s+", " ", row["name"]).strip().casefold() for row in members
    )
    for name, count in names.items():
        if count > 1:
            duplicate_names.append(
                {
                    "district": group["district"],
                    "union": group["union"],
                    "name_casefolded": name,
                    "occurrences": count,
                    "rows": [row for row in members if row["name"].casefold() == name],
                }
            )

summary = {
    "source_path": str(SOURCE.relative_to(ROOT.parents[2])),
    "source_sha256": hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
    "source_pdf_pages": list(range(3, 154)),
    "table_pages": 151,
    "printed_row_occurrences": len(rows),
    "union_sections": len(groups),
    "district_sections": len(district_counts),
    "category_counts": dict(category_counts),
    "raw_category_vocabulary": dict(
        Counter(
            row["category"] if row["category"] is not None else "[BLANK]"
            for row in rows
        )
    ),
    "serial_anomalies": serial_anomalies,
    "duplicate_names_within_union": duplicate_names,
    "visually_inspected_diagnostic_pages": [
        6,
        15,
        26,
        27,
        38,
        77,
        79,
        99,
        100,
        125,
        127,
        128,
        143,
        151,
    ],
    "method": (
        "Independent native-text page/side counts; source-pinned layout "
        "repairs in this script. Group sections follow serial1 restarts. "
        "Not an independent name-by-name visual transcription. "
    ),
    "line_number_semantics": (
        "Diagnostic line in repaired side text; raw unmodified side "
        "extraction is retained in page-N-side.txt. Five split-line repairs "
        "are explicit in the script. "
    ),
    "prior_exposure": (
        "Root provided its count and three serial anomalies after initial "
        "independent native count, before final verification. No root "
        "parser outputs were read. "
    ),
}
if (len(rows), len(groups), len(district_counts)) != (12524, 385, 31):
    raise ValueError("Row or grouping control mismatch")
if (len(serial_anomalies), category_counts["UNKNOWN_BLANK"]) != (3, 1):
    raise ValueError("Source anomaly control mismatch")
if len(pages) != 151 or sum(page["parsed_rows"] for page in pages) != len(rows):
    raise ValueError("Page count reconciliation failed")
for filename, entries in [
    ("union_counts", union_counts),
    ("district_counts", list(district_counts.values())),
]:
    (OUT / f"{filename}.json").write_text(json.dumps(entries, indent=2) + "\n")
    with (OUT / f"{filename}.csv").open("w") as f:
        writer = csv.DictWriter(f, fieldnames=list(entries[0]))
        writer.writeheader()
        writer.writerows(entries)
(OUT / "groups.json").write_text(json.dumps(groups, indent=2) + "\n")
(OUT / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
sys.stdout.write(
    json.dumps(
        {
            "rows": len(rows),
            "unions": len(groups),
            "districts": len(district_counts),
            "categories": category_counts,
            "duplicate_names": duplicate_names,
        },
        indent=2,
    )
)
