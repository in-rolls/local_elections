"""Apply pinned, source-reviewed district-member context without changing OCR cells."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

import pandas as pd

RAW_FIELDS = (
    "body_raw",
    "category_raw",
    "office_raw",
    "relation_raw",
    "ward_raw",
    "winner_raw",
)
CATEGORIES = {
    "General": ("NONE", False),
    "General Woman": ("NONE", True),
    "S.C.": ("SC", False),
    "S.C. Woman": ("SC", True),
    "B.C.": ("BC", False),
    "B.C. Woman": ("BC", True),
    "S.T.": ("ST", False),
    "S.T. Woman": ("ST", True),
}


def _key(row: dict[str, Any]) -> tuple[str, int, int]:
    return (
        row["source_sha256"],
        int(row["source_page"]),
        int(row["source_row_on_page"]),
    )


def apply_source_district_reviews(
    records: list[dict[str, Any]], out: Path
) -> dict[str, int]:
    """Validate every review before applying any changes to the exported records."""
    out = Path(out).resolve()
    files = sorted(
        out.glob("source_alignment_visual_review_*/district_member_reviews.json")
    )
    if not files:
        return {"rows_reviewed": 0, "raw_cells_modified": 0}
    indexed: dict[tuple[str, int, int], list[dict[str, Any]]] = {}
    for record in records:
        indexed.setdefault(_key(record), []).append(record)
    hashes: dict[Path, str] = {}

    def pin(path: Path, expected: str) -> None:
        resolved = path.resolve()
        if not resolved.is_relative_to(out):
            raise ValueError(
                f"District review evidence escapes export directory: {path}"
            )
        if not isinstance(expected, str) or not re.fullmatch(r"[0-9a-f]{64}", expected):
            raise ValueError(f"Invalid district review evidence hash: {path}")
        if resolved not in hashes:
            hashes[resolved] = hashlib.sha256(resolved.read_bytes()).hexdigest()
        if hashes[resolved] != expected:
            raise ValueError(f"District review evidence hash mismatch: {path}")

    pending = []
    seen = set()
    for path in files:
        payload = path.read_bytes()
        reviews = json.loads(payload)
        findings = json.loads((path.parent / "source_findings.json").read_bytes())
        if not isinstance(reviews, list):
            raise ValueError(f"District reviews must be a list: {path}")
        pin(path.parent / findings["target_evidence_file"], findings["source_sha256"])
        method = findings.get(
            "review_method", "visual_same_printed_page_and_preceding_notification"
        )
        direct_notification = method == "visual_same_page_notification"
        if direct_notification:
            if (
                findings.get("counterpart_evidence_file") is not None
                or findings.get("counterpart_source_sha256") is not None
                or findings.get("counterpart_pages") != []
                or findings.get("notification_heading_source_page")
                != findings["source_page"]
                or not isinstance(findings.get("office_source_raw"), str)
                or not findings["office_source_raw"].strip()
            ):
                raise ValueError(f"Invalid same-page notification evidence: {path}")
        elif method == "visual_same_printed_page_and_preceding_notification":
            pin(
                path.parent / findings["counterpart_evidence_file"],
                findings["counterpart_source_sha256"],
            )
        else:
            raise ValueError(f"Unsupported district review method: {path}")
        review_hash = hashlib.sha256(payload).hexdigest()
        for review in reviews:
            key = _key(review)
            if key in seen or len(indexed.get(key, [])) != 1:
                raise ValueError(f"Duplicate or missing district review target: {key}")
            seen.add(key)
            record = indexed[key][0]
            expected = review["expected_raw"]
            if set(expected) != set(RAW_FIELDS):
                raise ValueError(f"Incomplete district review raw-cell guard: {key}")
            for field in RAW_FIELDS:
                value = expected[field]
                if value is not None and not isinstance(value, str):
                    raise ValueError(f"Invalid expected raw value: {key}, {field}")
                if field not in record or (
                    not pd.isna(record[field])
                    if value is None
                    else pd.isna(record[field]) or record[field] != value
                ):
                    raise ValueError(
                        f"District review raw-cell mismatch: {key}, {field}"
                    )
            ward = review["ward"]
            if type(ward) is not int or ward < 1:
                raise ValueError(f"Invalid district review ward: {key}")
            if review["ward_source_raw"] not in (str(ward), f"{ward} *"):
                raise ValueError(f"District review ward transcription mismatch: {key}")
            if (
                review["office_normalized"] != "ZILA_PARISHAD_MEMBER"
                or review["tier"] != "district_member"
            ):
                raise ValueError(f"Invalid district review office: {key}")
            category = CATEGORIES.get(review["category_source_raw"])
            if (
                category is None
                or type(review["woman_reserved"]) is not bool
                or category != (review["caste_reservation"], review["woman_reserved"])
            ):
                raise ValueError(f"Invalid district review category: {key}")
            if any(
                not isinstance(review[field], str) or not review[field].strip()
                for field in ("district_source_raw", "body_source_raw")
            ):
                raise ValueError(f"Missing district review notification context: {key}")
            number = review["notification_number_source_raw"]
            if not (isinstance(number, str) and number.strip()) and not (
                direct_notification and number is None
            ):
                raise ValueError(f"Missing district review notification number: {key}")
            if (
                review["source_sha256"] != findings["source_sha256"]
                or review["source_page"] != findings["source_page"]
                or review["review_method"] != method
            ):
                raise ValueError(f"District review evidence context mismatch: {key}")
            if direct_notification:
                if (
                    review["counterpart_source_sha256"] is not None
                    or review["counterpart_heading_page"] is not None
                    or review["counterpart_row_page"] is not None
                    or review.get("notification_heading_source_page")
                    != findings["notification_heading_source_page"]
                    or review.get("office_source_raw") != findings["office_source_raw"]
                ):
                    raise ValueError(
                        f"Same-page district review context mismatch: {key}"
                    )
            elif (
                review["counterpart_source_sha256"]
                != findings["counterpart_source_sha256"]
                or review["counterpart_heading_page"]
                not in findings["counterpart_pages"]
                or review["counterpart_row_page"] not in findings["counterpart_pages"]
            ):
                raise ValueError(f"District review counterpart context mismatch: {key}")
            if (
                type(review["winner_cell_blank"]) is not bool
                or review["winner_cell_blank"] != (expected["winner_raw"] is None)
                or review["vacancy_inferred"] is not False
            ):
                raise ValueError(
                    f"Unsupported district review vacancy inference: {key}"
                )
            primary = f"response_{key[0]}-p{key[1]:04d}.json"
            if review["primary_response_file"] != primary:
                raise ValueError(f"District review response identity mismatch: {key}")
            pin(out / primary, review["primary_response_sha256"])
            pending.append((record, review, str(path.relative_to(out)), review_hash))

    cleared = {
        "column_alignment_failed",
        "office_unresolved",
        "ward_unresolved",
        "incoming_body_context_unvalidated",
        "tier_from_inventory_unvalidated",
        "samiti_or_empty_page_source_review_required",
        "category_unresolved",
    }
    for record, review, review_file, review_hash in pending:
        updates = {
            "office_normalized": review["office_normalized"],
            "tier": review["tier"],
            "ward": review["ward"],
            "body_within_page": review["body_source_raw"],
            "caste_reservation": review["caste_reservation"],
            "woman_reserved": review["woman_reserved"],
            "is_seat_record": True,
        }
        for field, value in updates.items():
            record.setdefault(f"{field}_before_district_review", record.get(field))
            record[field] = value
        record["source_district_review_status"] = "applied"
        record["source_district_review_file"] = review_file
        record["source_district_review_sha256"] = review_hash
        for field in (
            "district_source_raw",
            "body_source_raw",
            "ward_source_raw",
            "category_source_raw",
            "winner_cell_blank",
            "notification_number_source_raw",
            "notification_date",
            "counterpart_source_sha256",
            "counterpart_heading_page",
            "counterpart_row_page",
            "review_method",
        ):
            record[f"district_review_{field}"] = review[field]
        flags = set((record.get("quality_flags") or "").split(";")) - cleared - {""}
        flags.update(
            {
                "district_member_context_source_reviewed_raw_preserved",
                "overlapping_source_observation_reconciliation_pending",
            }
        )
        if review["notification_number_source_raw"] is None:
            flags.add("notification_number_source_unresolved")
        record["quality_flags"] = ";".join(sorted(flags))
    return {
        "rows_reviewed": len(pending),
        "source_documents": len(
            {review["source_sha256"] for _, review, _, _ in pending}
        ),
        "blank_winner_cells_preserved": sum(
            review["winner_cell_blank"] for _, review, _, _ in pending
        ),
        "raw_cells_modified": 0,
    }
