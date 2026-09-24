"""Parse raw OCR cells from Gujarat's 2020 PRI rotation rosters."""

import collections
import csv
import difflib
import json
import re

from local_elections.common import emit
from local_elections.common.normalize import label
from local_elections.common.runlog import command, get_logger
from local_elections.paths import ROOT
from local_elections.states.gujarat import harvest, ocr

LOGGER = get_logger(__name__)
RECODE_AUDIT = ROOT / "data" / "gujarat" / "reservation_recode_2020.csv"
CATEGORIES = {
    "બિન અનામત સામાન્ય": ("NONE", 0),
    "સામાન્ય સ્ત્રી": ("NONE", 1),
    "સા.શૈ.પછાતવર્ગ": ("BC", 0),
    "સા.શૈ.પછાતવર્ગ સ્ત્રી": ("BC", 1),
    "અનુસૂચિત જાતિ": ("SC", 0),
    "અનુસૂચિત જાતિ સ્ત્રી": ("SC", 1),
    "અનુસૂચિત આદિજાતિ": ("ST", 0),
    "અનુસૂચિત આદિજાતિ સ્ત્રી": ("ST", 1),
}
TRANSLATE_DIGITS = str.maketrans("૦૧૨૩૪૫૬૭૮૯", "0123456789")
COLUMNS = [
    "state",
    "year",
    "district",
    "block",
    "body",
    "seat_no",
    "seat_no_ocr",
    "seat_no_from_order",
    "ward_name",
    "tier",
    "tier_local",
    "reservation",
    "caste_reservation",
    "caste_reservation_local",
    "woman_reserved",
    "reservation_raw",
    "reservation_match_score",
    "sc_rank_ocr",
    "st_rank_ocr",
    "listing_scope",
    "script",
    "text_source",
    "ocr_mean_confidence",
    "source_path",
    "source_page",
    "source_pdf",
    "source_url",
    "source_capture",
]


def compact(value):
    """Normalize OCR spacing and punctuation without translating Gujarati."""
    return re.sub(r"[^઀-૿]+", "", value or "")


def clean_name(value):
    """Remove OCR table rules at a name cell's edges."""
    return re.sub(r"^[^઀-૿0-9૦-૯]+|[^઀-૿0-9૦-૯]+$", "", value or "").strip()


def best_name(*values):
    """Choose the OCR reading retaining the most source-script characters."""
    # A cell reader can occasionally fall back to Tesseract's full TSV dump.
    # Tabs/newlines prove the candidate is not a single source cell, and a
    # page-sized single line is likewise not a place name. Ignore that failed
    # alternative while retaining the other independent OCR reading.
    cleaned = [
        clean_name(value)
        for value in values
        if value and not re.search(r"[\t\r\n]", value) and len(value) <= 200
    ]
    return max(cleaned, key=lambda value: (len(compact(value)), len(value)), default="")


def reservation_of(*raw_values):
    """Return the closest category across source-faithful OCR alternatives."""
    scored = [
        (
            difflib.SequenceMatcher(None, compact(raw), compact(category)).ratio(),
            category,
            raw,
        )
        for raw in raw_values
        if raw
        for category in CATEGORIES
    ]
    score, category, raw = max(scored)
    caste, woman = CATEGORIES[category]
    return raw, category, caste, woman, score


def source_manifest():
    """Index source provenance by held filename."""
    with harvest.MANIFEST.open(encoding="utf-8") as handle:
        return {row["file"]: row for row in csv.DictReader(handle)}


def read(path, sources):
    """Normalize one raw OCR JSONL file into constituency rows."""
    rows = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            raw = json.loads(line)
            matched_raw, category, caste, woman, score = reservation_of(
                raw.get("reservation_raw", ""),
                raw.get("reservation_alt_raw", ""),
                raw.get("reservation_page_raw", ""),
            )
            tier = raw["tier"]
            block = (
                raw["body"]
                if tier == "block_member"
                else best_name(raw.get("block_raw", ""), raw.get("block_page_raw", ""))
            )
            source = sources[raw["source_pdf"]]
            row = {
                "state": "Gujarat",
                "year": "2020",
                "district": raw["district"],
                "block": block,
                "body": raw["body"],
                "seat_no": str(raw["row_order"]),
                "seat_no_ocr": raw.get("seat_no_raw", "").translate(TRANSLATE_DIGITS),
                "seat_no_from_order": 1,
                "ward_name": best_name(
                    raw.get("ward_name_raw", ""),
                    raw.get("ward_name_page_raw", ""),
                    raw.get("ward_name_alt_raw", ""),
                    raw.get("ward_name_reviewed_raw", ""),
                ),
                "tier": tier,
                "tier_local": (
                    "district panchayat member"
                    if tier == "zp_member"
                    else "taluk panchayat member"
                ),
                "reservation": label(caste, woman),
                "caste_reservation": caste,
                "caste_reservation_local": category,
                "woman_reserved": woman,
                "reservation_raw": matched_raw,
                "reservation_match_score": round(score, 4),
                "sc_rank_ocr": raw.get("sc_rank_raw", "").translate(TRANSLATE_DIGITS),
                "st_rank_ocr": raw.get("st_rank_raw", "").translate(TRANSLATE_DIGITS),
                "listing_scope": "all_seats",
                "script": "gujarati",
                "text_source": "ocr",
                "ocr_mean_confidence": raw.get("ocr_mean_confidence", ""),
                "source_url": source["url"],
                # Direct-download retrieval times remain in the source manifest.
                # source_capture is reserved for replayable web-archive captures.
                "source_capture": "",
            }
            rows.append(
                emit.stamp(
                    row,
                    harvest.OUT / raw["source_pdf"],
                    int(raw["source_page"]),
                    ROOT,
                )
            )
    return rows


def write_recode_audit(rows):
    """Write the source-level old-to-new reservation recode cross-tabulation."""
    grouped = collections.defaultdict(list)
    for row in rows:
        key = (
            row["source_pdf"],
            row["tier"],
            row["reservation_raw"],
            row["caste_reservation_local"],
            row["caste_reservation"],
            row["woman_reserved"],
        )
        grouped[key].append(float(row["reservation_match_score"]))
    fields = [
        "source_pdf",
        "tier",
        "reservation_raw",
        "caste_reservation_local",
        "caste_reservation",
        "woman_reserved",
        "count",
        "min_match_score",
    ]
    with RECODE_AUDIT.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for key, scores in sorted(grouped.items()):
            writer.writerow(
                dict(
                    zip(fields[:6], key, strict=True),
                    count=len(scores),
                    min_match_score=round(min(scores), 4),
                )
            )


@command("parse", state="Gujarat")
def main():
    sources = source_manifest()
    by_tier = collections.defaultdict(list)
    for path in sorted(ocr.OCR.glob("*.jsonl")):
        for row in read(path, sources):
            by_tier[row["tier"]].append(row)
    all_rows = []
    for tier, rows in sorted(by_tier.items()):
        all_rows.extend(rows)
        stem = ROOT / "data" / "gujarat" / f"{tier}_reservation_2020"
        emit.write(rows, stem, COLUMNS)
        minimum_match = min(float(row["reservation_match_score"]) for row in rows)
        LOGGER.info(
            "Tier parsed",
            extra={
                "event": "tier_parsed",
                "tier": tier,
                "rows": len(rows),
                "source_documents": len({row["source_pdf"] for row in rows}),
                "minimum_category_match": minimum_match,
            },
        )
        print(
            f"Gujarat 2020 {tier}: {len(rows):,} constituencies; "
            f"minimum category match {minimum_match:.3f}"
        )
    write_recode_audit(all_rows)
    print(f"Reservation recode audit: {RECODE_AUDIT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
