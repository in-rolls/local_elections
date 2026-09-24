"""Apply bounded source reviews to samiti sections in mixed gazette pages."""

import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd

from local_elections.tools.source_identity_reviews import (
    RAW_FIELDS,
    _key,
    _pinned_file,
)


def apply_source_samiti_reviews(records, root: Path):
    """Preserve source observations and separate category readings from authority."""
    root = root.resolve()
    targets = defaultdict(list)
    for record in records:
        targets[_key(record)].append(record)
    seen = set()
    pending = []
    for path in sorted(root.glob("source_samiti_review_*.json")):
        raw = path.read_bytes()
        review = json.loads(raw)
        key = _key(review)
        if key in seen or len(targets[key]) != 1:
            raise ValueError(f"Missing or ambiguous samiti review target: {path.name}")
        seen.add(key)
        expected = review["expected_raw"]
        if set(expected) != RAW_FIELDS:
            raise ValueError("Samiti review requires all six raw preconditions")
        record = targets[key][0]
        for field, value in expected.items():
            if field not in record or (
                not pd.isna(record[field])
                if value is None
                else pd.isna(record[field]) or record[field] != value
            ):
                raise ValueError(f"Samiti precondition failed: {path.name}: {field}")
        flags = set(filter(None, record["quality_flags"].split(";")))
        if "source_confirmed_nonseat_raw_preserved" in flags:
            raise ValueError("Cannot classify a reviewed nonseat as a samiti seat")
        if review["office_normalized"] != "PANCHAYAT_SAMITI_MEMBER":
            raise ValueError("Unsupported samiti office")
        if review["tier"] != "block_member":
            raise ValueError("Samiti member requires the canonical block_member tier")
        ward = review["ward"]
        if type(ward) is not int or ward < 1:
            raise ValueError("Samiti review requires a positive source ward")
        if review["ward_source_raw"] not in {str(ward), f"{ward} *"}:
            raise ValueError("Source ward label does not match the reviewed ward")
        authority = review["category_authority"]
        if authority not in {"printed", "handwritten_amendment_unverified"}:
            raise ValueError("Unknown samiti category authority")
        caste = review["category_source_caste"]
        woman = review["category_source_woman"]
        if caste not in {"NONE", "SC", "ST", "BC"} or type(woman) is not bool:
            raise ValueError("Invalid typed samiti source category")
        for field in ("category_source_raw", "section_source_raw"):
            if not isinstance(review[field], str) or not review[field].strip():
                raise ValueError(f"Samiti review requires source text: {field}")
        printed_text = review["category_printed_raw"]
        if printed_text is None:
            if authority != "handwritten_amendment_unverified":
                raise ValueError(
                    "Printed category authority requires printed source text"
                )
        elif not isinstance(printed_text, str) or not printed_text.strip():
            raise ValueError("Printed category must be source text or explicit null")
        annotation = review.get("category_annotation_raw")
        if authority == "handwritten_amendment_unverified" and (
            not isinstance(annotation, str) or not annotation.strip()
        ):
            raise ValueError("Handwritten amendment requires annotation evidence")
        body = review["body_source_raw"]
        district = review["district_source_raw"]
        if any(
            value is not None and (not isinstance(value, str) or not value.strip())
            for value in (body, district)
        ):
            raise ValueError(
                "Body/district source context must be text or explicit null"
            )
        if type(review["seat_vacant"]) is not bool:
            raise ValueError("Vacancy must be explicitly source reviewed")
        result_status = review.get("result_status_source_raw")
        if result_status is not None and (
            not isinstance(result_status, str)
            or result_status not in {"COUNTING IS STOPED", "COUNTING STOP"}
            or expected["winner_raw"] != result_status
            or review["seat_vacant"]
        ):
            raise ValueError(
                "Counting-stopped status requires matching source text "
                "and is not a vacancy"
            )
        _pinned_file(root, review["evidence_file"], review["evidence_sha256"])
        _pinned_file(
            root, review["primary_response_file"], review["primary_response_sha256"]
        )
        pending.append((record, review, path.name, hashlib.sha256(raw).hexdigest()))
    counts = Counter()
    for record, review, filename, digest in pending:
        printed = review["category_authority"] == "printed"
        corrected = {
            "office_normalized": review["office_normalized"],
            "tier": "block_member",
            "ward": review["ward"],
            "body_within_page": review["body_source_raw"],
            "caste_reservation": review["category_source_caste"] if printed else None,
            "woman_reserved": review["category_source_woman"] if printed else None,
            "is_seat_record": True,
        }
        for field, value in corrected.items():
            previous = record.get(field)
            record[f"{field}_before_samiti_review"] = (
                None if pd.isna(previous) else previous
            )
            record[field] = value
        for field in (
            "category_source_raw",
            "category_printed_raw",
            "category_annotation_raw",
            "category_authority",
            "category_source_caste",
            "category_source_woman",
            "body_source_raw",
            "district_source_raw",
            "section_source_raw",
            "ward_source_raw",
            "seat_vacant",
            "result_status_source_raw",
        ):
            record[f"samiti_{field}"] = review.get(field)
        record["source_samiti_review_status"] = "applied"
        record["source_samiti_review_file"] = filename
        record["source_samiti_review_sha256"] = digest
        flags = set(filter(None, record["quality_flags"].split(";")))
        flags.difference_update(
            {
                "office_unresolved",
                "tier_from_inventory_unvalidated",
                "ward_missing",
                "malformed_ward",
                "column_alignment_failed",
                "samiti_or_empty_page_source_review_required",
            }
        )
        flags.add("samiti_section_source_reviewed_raw_preserved")
        if printed:
            flags.difference_update(
                {"category_unresolved", "column_category_unresolved"}
            )
            flags.add("samiti_printed_category_source_reviewed")
            counts["printed_category_applied"] += 1
        else:
            flags.update(
                {
                    "category_unresolved",
                    "handwritten_category_amendment_requires_authority_review",
                }
            )
            counts["handwritten_category_authority_unresolved"] += 1
        if review["body_source_raw"] is None or review["district_source_raw"] is None:
            flags.add("samiti_body_context_requires_source_review")
            counts["body_context_unresolved"] += 1
        else:
            flags.discard("incoming_body_context_unvalidated")
            flags.add("samiti_body_context_source_reviewed")
            counts["body_context_source_reviewed"] += 1
        if review["seat_vacant"]:
            flags.add("samiti_vacancy_source_reviewed")
            counts["vacant_seats"] += 1
        if review.get("result_status_source_raw") is not None:
            flags.add("counting_stopped_no_declared_winner")
            counts["counting_stopped_no_declared_winner"] += 1
        record["quality_flags"] = ";".join(sorted(flags))
        counts["applied"] += 1
    return dict(counts)
