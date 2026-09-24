"""Read the reviewed 2000 president and samiti-chair reservations in the SEC report.

Page 84 explicitly labels the office reservation and dates the collection to
the March 2000 election cycle. Pages 21-22 explicitly list reservations of the
114 samiti-chair offices. Vice-president tables remain outside this parser.
"""

import argparse
import csv
import json
from pathlib import Path

import pdfplumber
import pyarrow as pa
import pyarrow.parquet as pq

from local_elections.common.runlog import command
from local_elections.paths import ROOT
from local_elections.tools.historical_harvest import checksum

SOURCE = ROOT / "data/source_search/national/haryana/gap_recovery"
REPORT = SOURCE / "raw/f425f720471d64267d6a.pdf"
REPORT_SHA256 = "35d9fc129b10c10b04f7bd12fc2d196971725f50dbf4d067d9c000af0f070116"
REPORT_URL = (
    "https://web.archive.org/web/20160516134602id_/http://secharyana.nic.in/"
    "html/ELECTION%20REPORTS%20PDF/PANCHAYAT%20REPORT%201994-2004.pdf"
)
FIELDS = [
    ("state", pa.string(), "State named in the source."),
    ("year", pa.int64(), "Election cycle stated on page 84 or in page 21 context."),
    ("tier", pa.string(), "zp_head or block_head: the reserved chairperson office."),
    ("district_raw", pa.string(), "Printed district; absent in the samiti list."),
    ("body_raw", pa.string(), "Printed local body name; line breaks retained."),
    ("reservation_raw", pa.string(), "Printed office reservation category."),
    ("caste_reservation", pa.string(), "SC or NONE, referring to the office."),
    ("woman_reserved", pa.bool_(), "Whether the office is reserved for a woman."),
    (
        "winner_name_raw",
        pa.string(),
        "Name and honorific; printed line breaks retained.",
    ),
    ("relation_marker_raw", pa.string(), "Printed S/O, W/O or D/O marker."),
    ("relation_name_raw", pa.string(), "Printed relative name; line breaks retained."),
    ("winner_gender", pa.string(), "Unknown; neither category nor honorific is used."),
    ("source_page", pa.int64(), "One-based PDF page number."),
    ("source_bbox", pa.string(), "JSON [left, top, right, bottom] in PDF points."),
    ("source_path", pa.string(), "Original PDF path relative to the repository."),
    ("source_url", pa.string(), "Archived original acquisition URL."),
    ("source_sha256", pa.string(), "SHA-256 of the complete original PDF."),
    (
        "review_status",
        pa.string(),
        "Page visually reviewed; no independent validation.",
    ),
]
SCHEMA = pa.schema([pa.field(name, kind) for name, kind, _ in FIELDS])


def parse_presidents(path=REPORT):
    if checksum(path) != REPORT_SHA256:
        raise ValueError("Report differs from the visually reviewed source")
    with pdfplumber.open(path) as pdf:
        page = pdf.pages[83]
        text = page.extract_text() or ""
        if "March, 2000" not in text or "PRESIDENTS OF ZILA PARISHADS" not in text:
            raise ValueError("Missing election context on report page 84")
        table = page.find_tables()[0]
        rows = table.extract()
        if "office is" not in rows[0][2]:
            raise ValueError("The category header does not identify office reservation")
        categories = {
            "Gen": ("NONE", False),
            "Gen(w)": ("NONE", True),
            "SC": ("SC", False),
            "SC(w)": ("SC", True),
        }
        records = []
        for cells, row in zip(rows[1:], table.rows[1:], strict=True):
            if not any(cells):
                continue
            district, body, category = cells[:3]
            if not district or not body or category not in categories:
                raise ValueError(f"Unrecognized president row: {cells}")
            caste, woman = categories[category]
            _, top, _, bottom = row.bbox

            def cell_text(left, right):
                return page.crop((left, top, right, bottom)).extract_text() or ""

            records.append(
                {
                    "state": "Haryana",
                    "year": 2000,
                    "tier": "zp_head",
                    "district_raw": district,
                    "body_raw": body,
                    "reservation_raw": category,
                    "caste_reservation": caste,
                    "woman_reserved": woman,
                    "winner_name_raw": cell_text(333, 412),
                    "relation_marker_raw": cell_text(412, 440),
                    "relation_name_raw": cell_text(440, 526),
                    "winner_gender": None,
                    "source_page": 84,
                    "source_bbox": json.dumps([114.9, top, 526, bottom]),
                    "source_path": str(REPORT.relative_to(ROOT)),
                    "source_url": REPORT_URL,
                    "source_sha256": REPORT_SHA256,
                    "review_status": "page_reviewed; independent_review_pending",
                }
            )
    if len(records) != 19 or len({r["district_raw"] for r in records}) != 19:
        raise ValueError("Expected the 19 distinct districts printed on page 84")
    if any(not r["winner_name_raw"] for r in records):
        raise ValueError("Missing a printed president's name")
    return records


def parse_chair_reservations(path=REPORT):
    if checksum(path) != REPORT_SHA256:
        raise ValueError("Report differs from the visually reviewed source")
    with pdfplumber.open(path) as pdf:
        context = pdf.pages[20].extract_text() or ""
        if "March, 2000" not in context or "offices of Chairman" not in context:
            raise ValueError("Missing dated samiti-chair reservation context")
        page = pdf.pages[21]
        table = page.find_tables()[0]
        rows = table.extract()
        expected_headers = [
            "Scheduled\nCastes",
            "Women belonging to the\nScheduled Castes",
            "Women",
            "Unreserved",
        ]
        if rows[0] != expected_headers or rows[-1] != ["14", "09", "43", "48"]:
            raise ValueError("Changed chair reservation headers or printed totals")
        categories = [("SC", False), ("SC", True), ("NONE", True), ("NONE", False)]
        records = []
        counts = [0, 0, 0, 0]
        for values, row in zip(rows[1:-1], table.rows[1:-1], strict=True):
            for column, value in enumerate(values):
                if not value:
                    continue
                caste, woman = categories[column]
                counts[column] += 1
                record = dict.fromkeys(SCHEMA.names)
                record.update(
                    state="Haryana",
                    year=2000,
                    tier="block_head",
                    body_raw=value,
                    reservation_raw=expected_headers[column],
                    caste_reservation=caste,
                    woman_reserved=woman,
                    source_page=22,
                    source_bbox=json.dumps(row.cells[column]),
                    source_path=str(REPORT.relative_to(ROOT)),
                    source_url=REPORT_URL,
                    source_sha256=REPORT_SHA256,
                    review_status="page_reviewed; linkage_review_pending",
                )
                records.append(record)
        if counts != [14, 9, 43, 48]:
            raise ValueError(f"Extracted chair counts disagree with totals: {counts}")
        return records


@command("parse", state="Haryana", vintage="2000_report")
def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=SOURCE.parent / "report_2000")
    args = parser.parse_args()
    records = parse_presidents() + parse_chair_reservations()
    args.out.mkdir(parents=True, exist_ok=True)
    pq.write_table(
        pa.Table.from_pylist(records, schema=SCHEMA), args.out / "seat_rows.parquet"
    )
    with (args.out / "seat_rows.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=SCHEMA.names)
        writer.writeheader()
        writer.writerows(records)
    with (args.out / "data_dictionary.csv").open("w", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["field", "type", "description"])
        writer.writerows(FIELDS)
    (args.out / "schema.json").write_text(
        json.dumps({f.name: str(f.type) for f in SCHEMA}, indent=2) + "\n"
    )
    summary = {
        "rows": len(records),
        "year": 2000,
        "tier_rows": {
            tier: sum(r["tier"] == tier for r in records)
            for tier in ("zp_head", "block_head")
        },
        "women_reserved": sum(r["woman_reserved"] for r in records),
        "sc_reserved": sum(r["caste_reservation"] == "SC" for r in records),
        "release_status": "research staging; independent review pending",
    }
    (args.out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    manifest = {
        "inputs": {
            str(REPORT.relative_to(ROOT)): REPORT_SHA256,
            str(Path(__file__).relative_to(ROOT)): checksum(Path(__file__)),
        },
        "outputs": {
            p.name: checksum(p)
            for p in sorted(args.out.iterdir())
            if p.name != "checksums.json"
        },
    }
    (args.out / "checksums.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(summary))


if __name__ == "__main__":
    main()
