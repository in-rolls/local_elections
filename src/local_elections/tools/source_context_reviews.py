"""Apply pinned cross-document body context without rewriting raw cells."""

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


def validate_gp_notification_review(review: dict[str, Any], root: Path) -> None:
    """Require pinned same-page GP context and explicit category authority."""
    root = root.resolve()
    source = review["source_sha256"]
    if not isinstance(source, str) or not re.fullmatch(r"[0-9a-f]{64}", source):
        raise ValueError("GP notification requires a source checksum")
    for field in ("source_page", "source_row_on_page"):
        if type(review[field]) is not int or review[field] < 1:
            raise ValueError("GP notification requires positive source coordinates")
    if set(review["expected_raw"]) != set(RAW_FIELDS) or any(
        value is not None and not isinstance(value, str)
        for value in review["expected_raw"].values()
    ):
        raise ValueError("GP notification must guard all six raw cells")
    context = review["notification_context"]
    if set(context) != {
        "district_source_raw",
        "block_source_raw",
        "body_source_raw",
        "heading_page",
    }:
        raise ValueError("GP notification context is incomplete")
    if (
        type(context["heading_page"]) is not int
        or context["heading_page"] != review["source_page"]
        or any(
            not isinstance(context[field], str) or not context[field].strip()
            for field in ("district_source_raw", "block_source_raw", "body_source_raw")
        )
        or review.get("body_within_page") != context["body_source_raw"]
    ):
        raise ValueError("GP notification must identify same-page body and context")
    offices = {
        "PANCH": {"PANCH", "Panch", "\u092a\u0902\u091a"},
        "SARPANCH": {"SARPANCH", "Sarpanch", "\u0938\u0930\u092a\u0902\u091a"},
    }
    if review.get("office_source_raw") not in offices.get(
        review["office_normalized"], set()
    ):
        raise ValueError("GP notification office transcription disagrees")
    evidence = (root / review["evidence_file"]).resolve()
    if not (
        evidence.is_relative_to(root)
        or evidence.is_relative_to(root.parent.parent / "raw")
    ):
        raise ValueError("GP evidence escapes the source archive")
    if (
        review["evidence_sha256"] != source
        or hashlib.sha256(evidence.read_bytes()).hexdigest() != source
    ):
        raise ValueError("GP notification evidence checksum mismatch")
    primary = f"response_{source}-p{review['source_page']:04d}.json"
    digest = review["primary_response_sha256"]
    if (
        review["primary_response_file"] != primary
        or not isinstance(digest, str)
        or not re.fullmatch(r"[0-9a-f]{64}", digest)
        or hashlib.sha256((root / primary).read_bytes()).hexdigest() != digest
    ):
        raise ValueError("GP notification response checksum mismatch")
    authority = review["category_authority"]
    if authority == "printed":
        if (
            not isinstance(review.get("category_source_raw"), str)
            or not review["category_source_raw"].strip()
        ):
            raise ValueError("Printed GP category requires literal source text")
    elif authority == "handwritten_amendment_unverified":
        if (
            "category_source_raw" in review
            or not {"caste_reservation", "woman_reserved"} <= review.keys()
            or review["caste_reservation"] is not None
            or review["woman_reserved"] is not None
            or not isinstance(review.get("category_annotation_description"), str)
            or not review["category_annotation_description"].strip()
        ):
            raise ValueError("Unverified GP amendments must withhold both typed axes")
    else:
        raise ValueError("Unsupported GP category authority")


def _key(row: dict[str, Any]) -> tuple[str, int, int]:
    return (
        row["source_sha256"],
        int(row["source_page"]),
        int(row["source_row_on_page"]),
    )


def apply_source_context_reviews(
    records: list[dict[str, Any]], root: Path
) -> dict[str, Any]:
    root = root.resolve()
    by_key: dict[tuple[str, int, int], list[dict[str, Any]]] = {}
    for record in records:
        by_key.setdefault(_key(record), []).append(record)
    pinned: set[tuple[Path, str]] = set()

    def pin(value: str, expected: str, *, pdf: bool = False) -> None:
        path = (root / value).resolve()
        allowed = root.parent.parent / "raw" if pdf else root
        if not path.is_relative_to(allowed):
            raise ValueError("Context evidence path escapes its source root")
        identity = (path, expected)
        if identity not in pinned:
            if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
                raise ValueError("Context source evidence changed")
            pinned.add(identity)

    pending = []
    seen = set()
    for path in sorted(root.glob("source_context_review_*.json")):
        raw = path.read_bytes()
        review = json.loads(raw)
        key = _key(review)
        if key in seen or len(by_key.get(key, [])) != 1:
            raise ValueError("Context review target is not unique")
        seen.add(key)
        target = by_key[key][0]
        if set(review["expected_raw"]) != set(RAW_FIELDS):
            raise ValueError("Context review must guard all raw source cells")
        for field, expected in review["expected_raw"].items():
            if field not in target or (
                not pd.isna(target[field])
                if expected is None
                else pd.isna(target[field]) or target[field] != expected
            ):
                raise ValueError(f"Context review raw-cell guard failed: {field}")
        if (
            target.get("tier") != "block_member"
            or target.get("office_normalized") != "PANCHAYAT_SAMITI_MEMBER"
            or target.get("ward") != review["ward"]
            or not isinstance(review["ward"], int)
            or isinstance(review["ward"], bool)
            or review["ward"] < 1
        ):
            raise ValueError("Context review requires an established samiti ward")
        body = review["body_context_raw"]
        district = review["district_context_raw"]
        if not all(isinstance(v, str) and v.strip() for v in (body, district)):
            raise ValueError("Context body and district must be explicit")
        if target.get("body_within_page") not in (None, "", body):
            raise ValueError("Cross-source context conflicts with existing body")
        if review["method"] != "visual_bilingual_sequence":
            raise ValueError("Unrecognized cross-source review method")
        pin(review["primary_response_file"], review["primary_response_sha256"])
        pin(review["evidence_file"], review["evidence_sha256"])
        pin(review["cross_source_pdf"], review["cross_source_sha256"], pdf=True)
        pages = set()
        for evidence in review["cross_source_images"]:
            page = evidence["page"]
            if not isinstance(page, int) or isinstance(page, bool) or page < 1:
                raise ValueError("Invalid cross-source evidence page")
            if page in pages:
                raise ValueError("Duplicate cross-source evidence page")
            pages.add(page)
            pin(evidence["file"], evidence["sha256"])
        body_page = review["cross_source_body_page"]
        notification_page = review["cross_source_notification_page"]
        if (
            not isinstance(body_page, int)
            or not isinstance(notification_page, int)
            or notification_page < 1
            or body_page < notification_page
            or not set(range(notification_page, body_page + 1)) <= pages
        ):
            raise ValueError("Cross-source notification continuity is unpinned")
        flags = target.get("quality_flags", "")
        if isinstance(flags, str):
            flags = set(filter(None, flags.split(";")))
        elif isinstance(flags, list) and all(isinstance(f, str) for f in flags):
            flags = set(flags)
        else:
            raise ValueError("Unrecognized quality-flag representation")
        pending.append(
            (target, review, path.name, hashlib.sha256(raw).hexdigest(), flags)
        )

    for target, review, filename, digest, flags in pending:
        target["body_within_page_before_context_review"] = target.get(
            "body_within_page"
        )
        target["body_within_page"] = review["body_context_raw"]
        target["body_cross_source_review_raw"] = review["body_context_raw"]
        target["district_cross_source_review_raw"] = review["district_context_raw"]
        target["source_context_review_status"] = "cross_source_context_reviewed"
        target["source_context_review_file"] = filename
        target["source_context_review_sha256"] = digest
        target["source_context_cross_source_sha256"] = review["cross_source_sha256"]
        target["source_context_body_page"] = review["cross_source_body_page"]
        target["source_context_notification_page"] = review[
            "cross_source_notification_page"
        ]
        target["source_context_review_method"] = review["method"]
        flags.discard("samiti_body_context_requires_source_review")
        flags.add("body_context_cross_source_reviewed_raw_preserved")
        target["quality_flags"] = ";".join(sorted(flags))
    return {
        "rows_reviewed": len(pending),
        "cross_source_documents": len(
            {review["cross_source_sha256"] for _, review, *_ in pending}
        ),
        "raw_cells_modified": 0,
        "scope": (
            "Body/district context only; "
            "no administrative-code or independent-accuracy claim"
        ),
    }
