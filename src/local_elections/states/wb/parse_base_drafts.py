"""Publish the acquired 2018 ZP-member drafts separately from final orders.

The legacy parser only exports final orders. This wrapper retains its OCR cache,
adds source-pinned visual repairs for damaged headers and split identifiers,
and exposes every raw gazette page in a ledger. Drafts never replace finals.
"""

import argparse
import collections
import csv
import hashlib
import itertools
import json
import re

import pandas as pd

from local_elections.common.ocr_engine import page_count
from local_elections.common.runlog import command
from local_elections.paths import ROOT
from local_elections.states.wb import parse

BASE = ROOT / "data/wb/derived/base_drafts"
DATA = ROOT / "data/wb/2018"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def district_of(stem):
    """Handle both reservation-X and Draft order of X district filenames."""
    name = re.split(r"draft order of\s+", stem, flags=re.I)[-1]
    if name == stem:
        name = stem.rsplit("-", 1)[-1]
    name = re.sub(r"\s+district$", "", name, flags=re.I).strip()
    return {
        "coochbehar": "Cooch Behar",
        "North 24 Parganas": "North 24 Pgs",
        "South 24 Parganas": "South 24 Pgs",
    }.get(name, name)


def cache_words(path):
    with path.open() as stream:
        rows = list(csv.DictReader(stream, delimiter="\t", quoting=csv.QUOTE_NONE))
    width = int(rows[0]["width"])
    height = int(rows[0]["height"])
    return parse.words_of(path), width, height


def reassign_marks(seats, lines, edges):
    """Reattach marks after restoring omitted identifiers, before deriving axes."""
    for seat in seats:
        seat.update(caste="NONE", woman=0)
    for line in lines:
        for word in line:
            token = word["text"].strip(".,").lower()
            if word["x"] < edges[2]:
                continue
            caste = parse.CASTE_WORDS.get(token)
            woman = token in parse.WOMAN_WORDS and word["x"] >= edges[3]
            if not caste and not woman:
                continue
            above = [seat for seat in seats if seat["y"] <= word["y"] + 12]
            if not above:
                continue
            seat = max(above, key=lambda item: item["y"])
            if caste:
                seat["caste"] = caste
            if woman:
                seat["woman"] = 1
    for seat in seats:
        seat["raw"] = " ".join(
            token
            for token in (
                seat["caste"] if seat["caste"] != "NONE" else "",
                "WOMEN" if seat["woman"] else "",
            )
            if token
        )


def draft_document(path, correction):
    source_hash = digest(path)
    if correction and correction["source_sha256"] != source_hash:
        raise ValueError(f"Visual correction source changed: {path}")
    pages = sorted((parse.CACHE / "draft").glob(f"{path.stem}-*.tsv"))
    centers = correction.get("header_centers_300dpi")
    edges = (
        tuple((left + right) / 2 for left, right in itertools.pairwise(centers))
        if centers
        else next(
            (
                got
                for page in pages
                if (got := parse.column_edges(parse.words_of(page)))
            ),
            None,
        )
    )
    records, ledger = [], []
    for cache in pages:
        page = int(cache.stem.rsplit("-", 1)[-1])
        lines, width, height = cache_words(cache)
        cache_hash = digest(cache)
        expected = correction.get("ocr_sha256", {}).get(str(page))
        if expected and cache_hash != expected:
            raise ValueError(f"Visual correction OCR geometry changed: {cache}")
        seats, _, unreadable, edges = parse.read_page(cache, edges)
        repaired = correction.get("extra_seats", {}).get(str(page), [])
        for extra in repaired:
            if any(int(seat["seat_no"]) == extra["seat_no"] for seat in seats):
                raise ValueError(f"Correction no longer needed: {cache} {extra}")
            anchors = [
                word
                for line in lines
                for word in line
                if re.search(rf"\bZP-?{extra['seat_no']}\b", word["text"], re.I)
            ]
            if len(anchors) != 1:
                raise ValueError(
                    f"Ambiguous repaired identifier anchor: {cache} {extra}"
                )
            seats.append(
                {
                    "y": anchors[0]["y"],
                    "block": extra["block"],
                    "seat_no": str(extra["seat_no"]),
                    "seat_id_printed": extra["seat_id_printed"],
                }
            )
        seats.sort(key=lambda item: item["y"])
        if edges:
            reassign_marks(seats, lines, edges)
        for index, seat in enumerate(seats):
            extra = next(
                (item for item in repaired if item["seat_no"] == int(seat["seat_no"])),
                None,
            )
            flags = ["draft_order", "unreviewed_ocr"]
            if centers:
                flags.append("source_pinned_header_repair")
            if extra:
                flags.append("source_pinned_identifier_repair")
            bottom = seats[index + 1]["y"] if index + 1 < len(seats) else height
            raw = "\n".join(
                " ".join(word["text"] for word in line)
                for line in lines
                if any(seat["y"] - 12 <= word["y"] < bottom - 12 for word in line)
            )
            records.append(
                {
                    "record_id": f"{source_hash}:{page}:{seat['seat_no']}",
                    "state": "West Bengal",
                    "year": 2018,
                    "district": district_of(path.stem),
                    "block": seat["block"],
                    "seat_no": int(seat["seat_no"]),
                    "seat_id_printed": seat["seat_id_printed"],
                    "tier": "zp_member",
                    "stage": "draft",
                    "caste_reservation": (
                        seat["caste"] if seat["caste"] != "NONE" else None
                    ),
                    "women_reserved": True if seat["woman"] else None,
                    "winner_gender": None,
                    "reservation_raw": seat["raw"],
                    "legacy_caste_reading": seat["caste"],
                    "legacy_woman_reading": seat["woman"],
                    "absence_policy": (
                        "OCR absence remains unknown; no verified negatives"
                    ),
                    "source_path": str(path.relative_to(ROOT)),
                    "source_sha256": source_hash,
                    "source_page": page,
                    "source_bbox": [0.0, max(0, seat["y"] - 12), width, bottom],
                    "bbox_units": (
                        "OCR image pixels at 300 dpi; row band to next anchor"
                    ),
                    "ocr_path": str(cache.relative_to(ROOT)),
                    "ocr_sha256": cache_hash,
                    "raw_ocr": raw,
                    "quality_flags": ";".join(flags),
                }
            )
        ledger.append(
            {
                "source_path": str(path.relative_to(ROOT)),
                "source_sha256": source_hash,
                "source_page": page,
                "stage": "draft",
                "ocr_path": str(cache.relative_to(ROOT)),
                "ocr_sha256": cache_hash,
                "parsed_rows": len(seats),
                "status": "parsed_ocr_review_required"
                if seats
                else "no_seat_rows_review",
                "header_edges_300dpi": edges,
                "raw_ocr": "\n".join(
                    " ".join(word["text"] for word in line) for line in lines
                ),
                "unreadable_member_counts": unreadable,
            }
        )
    return records, ledger


def build():
    corrections = json.loads((BASE / "visual_corrections.json").read_text())
    records, pages, sources = [], [], []
    for source in sorted(DATA.rglob("*.pdf")):
        stage = "draft" if source.parent.name == "draft" else "final"
        count = page_count(source)
        if stage == "draft":
            rows, page_rows = draft_document(source, corrections.get(source.name, {}))
            records.extend(rows)
        else:
            rows = parse.rows_for(source.stem, "final", {})
            page_rows = []
            for page in range(1, count + 1):
                cache = parse.CACHE / "final" / f"{source.stem}-{page:02d}.tsv"
                page_rows.append(
                    {
                        "source_path": str(source.relative_to(ROOT)),
                        "source_sha256": digest(source),
                        "source_page": page,
                        "stage": "final",
                        "ocr_path": str(cache.relative_to(ROOT)),
                        "ocr_sha256": digest(cache) if cache.exists() else None,
                        "parsed_rows": sum(row["source_page"] == page for row in rows),
                        "status": "routed_existing_final_csv",
                    }
                )
        seen_pages = {row["source_page"] for row in page_rows}
        for missing in sorted(set(range(1, count + 1)) - seen_pages):
            page_rows.append(
                {
                    "source_path": str(source.relative_to(ROOT)),
                    "source_sha256": digest(source),
                    "source_page": missing,
                    "stage": stage,
                    "parsed_rows": 0,
                    "status": "missing_ocr_review_required",
                }
            )
        pages.extend(page_rows)
        numbers = [int(row["seat_no"]) for row in rows]
        sources.append(
            {
                "source_path": str(source.relative_to(ROOT)),
                "source_sha256": digest(source),
                "district": district_of(source.stem),
                "stage": stage,
                "pages": count,
                "cached_pages": len(seen_pages),
                "parsed_rows": len(rows),
                "seat_number_holes": sorted(
                    set(range(1, max(numbers, default=0) + 1)) - set(numbers)
                ),
                "duplicate_seat_numbers": [
                    key
                    for key, value in collections.Counter(numbers).items()
                    if value > 1
                ],
                "output": (
                    "data/wb/derived/base_drafts/records.csv"
                    if stage == "draft"
                    else "data/wb/zp_member_2018.csv"
                ),
            }
        )
    return records, pages, sources


def write_table(name, rows):
    frame = pd.DataFrame(rows)
    frame.to_parquet(BASE / f"{name}.parquet", index=False)
    (BASE / f"{name}.jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows)
    )
    for column in frame:
        if (
            frame[column]
            .map(lambda value: isinstance(value, (list, tuple, dict)))
            .any()
        ):
            frame[column] = frame[column].map(
                lambda value: json.dumps(value) if value is not None else ""
            )
    frame.to_csv(BASE / f"{name}.csv", index=False)


@command("parse", state="West Bengal", source="base_gazette_drafts")
def main():
    argparse.ArgumentParser(description=__doc__).parse_args()
    BASE.mkdir(parents=True, exist_ok=True)
    rows, pages, sources = build()
    for name, items in (
        ("records", rows),
        ("page_review", pages),
        ("sources", sources),
    ):
        write_table(name, items)
    (BASE / "page_audit.json").write_text(json.dumps(pages, indent=2) + "\n")
    summary = {
        "raw_documents": len(sources),
        "raw_pages": len(pages),
        "draft_documents": sum(row["stage"] == "draft" for row in sources),
        "draft_pages": sum(row["stage"] == "draft" for row in pages),
        "draft_records": len(rows),
        "final_records_existing_output": sum(
            row["parsed_rows"] for row in sources if row["stage"] == "final"
        ),
        "drafts_missing_from_acquired_source_tree": ["Malda"],
        "limitations": (
            "Cached OCR has no original image/settings fingerprint. Current PDF and "
            "TSV hashes pin inputs, not historical OCR provenance. Row number coverage "
            "does not certify names or reservation accuracy. Every draft row requires "
            "review; "
            "blank OCR axes remain unknown. No draft is substituted for a final order."
        ),
    }
    (BASE / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
