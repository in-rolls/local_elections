"""Emit verified positive office-reservation marks from Alipurduar's 2018 schedule.

The schedules list a union of caste-reserved and women-reserved offices. Blank
axes and unlisted bodies remain unknown; the printed office universe is a
separate control, never a row-count target. The transcription retains source
spellings and PDF-point row boxes, with embedded OCR retained alongside it.
"""

import collections
import hashlib
import json

import pdfplumber

from local_elections.common.runlog import command
from local_elections.paths import ROOT
from local_elections.states.wb.parse_results import write_table

OUT = ROOT / "data/wb/derived/alipurduar_offices"
EVIDENCE = OUT / "source_transcription.json"
TIERS = {
    "pradhan": "gp_head",
    "upa_pradhan": "gp_deputy_head",
    "sabhapati": "ps_head",
    "sahakari_sabhapati": "ps_deputy_head",
}


def check_controls(evidence):
    report = []
    for control in evidence["controls"]:
        rows = [r for r in evidence["rows"] if r["office"] == control["office"]]
        counts = collections.Counter(r["caste_mark_printed"] for r in rows)
        observed = {
            **{caste: counts[caste] for caste in ["SC", "ST", "BC"]},
            "women": sum(r["women_mark_printed"] == "WOMEN" for r in rows),
        }
        if any(observed[key] != control[key] for key in observed):
            raise ValueError(
                f"Positive office marks differ from source: {control['office']}"
            )
        if len({r["name_printed"] for r in rows}) != len(rows):
            raise ValueError("Duplicate body within office schedule")
        report.append(
            {
                **control,
                "listed_bodies": len(rows),
                "unlisted_bodies_count": control["total_offices"] - len(rows),
                "observed_positive_marks": observed,
                "status": "positive_marks_reconcile",
                "unlisted_body_reservation": "unknown",
            }
        )
    return report


def parse(evidence):
    source = ROOT / evidence["source_path"]
    if hashlib.sha256(source.read_bytes()).hexdigest() != evidence["source_sha256"]:
        raise ValueError("Office source hash changed; re-review transcription")
    controls = check_controls(evidence)
    universes = {c["office"]: c["total_offices"] for c in controls}
    rows = []
    with pdfplumber.open(source) as pdf:
        for mark in evidence["rows"]:
            page = pdf.pages[mark["source_page"] - 1]
            left, top, right, bottom = mark["bbox"]
            raw = {
                field: page.crop((x0, top, x1, bottom)).extract_text() or ""
                for field, x0, x1 in [
                    ("name", left, 420),
                    ("caste", 420, 445),
                    ("women", 455, right),
                ]
            }
            caste = mark["caste_mark_printed"]
            woman = 1 if mark["women_mark_printed"] == "WOMEN" else None
            tier = TIERS[mark["office"]]
            flags = []
            if caste is None:
                flags.append("caste_axis_unstated")
            if woman is None:
                flags.append("women_axis_unstated")
            row_id = hashlib.sha256(
                json.dumps(
                    [evidence["source_sha256"], mark["source_page"], mark["bbox"]]
                ).encode()
            ).hexdigest()[:20]
            rows.append(
                {
                    "row_id": row_id,
                    "state": "West Bengal",
                    "district": "Alipurduar",
                    "year": 2018,
                    "tier": tier,
                    "office": mark["office"],
                    "local_body_name": mark["name_printed"],
                    "gram_panchayat": mark["name_printed"]
                    if tier.startswith("gp_")
                    else None,
                    "block": mark["name_printed"] if tier.startswith("ps_") else None,
                    "name_printed": mark["name_printed"],
                    "caste_mark_printed": caste,
                    "women_mark_printed": mark["women_mark_printed"],
                    "caste_reservation": caste,
                    "woman_reserved": woman,
                    "reservation": (caste or "") + ("W" if woman else ""),
                    "office_universe_printed": universes[mark["office"]],
                    "source_list_scope": "union_of_positive_reserved_offices",
                    "source_path": evidence["source_path"],
                    "source_sha256": evidence["source_sha256"],
                    "source_page": mark["source_page"],
                    "source_bbox": json.dumps(mark["bbox"]),
                    "source_coordinate_system": evidence["coordinate_system"],
                    "embedded_ocr_raw": json.dumps(raw, ensure_ascii=False),
                    "review_status": "visually_transcribed",
                    "review_method": evidence["review_method"],
                    "quality_flags": ";".join(flags),
                }
            )
        page_offices = {m["source_page"]: m["office"] for m in evidence["rows"]}
        page_audit = [
            {
                "source_path": evidence["source_path"],
                "source_sha256": evidence["source_sha256"],
                "source_page": number,
                "office": page_offices.get(number),
                "status": "parsed_named_schedule"
                if number in page_offices
                else "cover_or_enabling_order",
                "rows": sum(r["source_page"] == number for r in rows),
            }
            for number in range(1, len(pdf.pages) + 1)
        ]
    return rows, controls, page_audit


@command("parse", state="West Bengal", source="alipurduar_2018_offices")
def main():
    evidence = json.loads(EVIDENCE.read_text())
    rows, controls, pages = parse(evidence)
    write_table(rows, OUT / "office_reservations")
    report = {
        "rows": len(rows),
        "by_office": dict(collections.Counter(r["office"] for r in rows)),
        "pages_expected": 12,
        "pages_seen": len(pages),
        "source_controls": controls,
        "limitation": (
            "Positive marks only. Blank axes and unlisted offices remain unknown; "
            "no complete office panel is inferred."
        ),
    }
    (OUT / "page_audit.json").write_text(json.dumps(pages, indent=2) + "\n")
    (OUT / "parse_report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
