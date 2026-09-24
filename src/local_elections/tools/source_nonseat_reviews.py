"""Annotate source-confirmed non-seats while retaining raw OCR observations."""

import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd

RAW_FIELDS = {
    "body_raw",
    "ward_raw",
    "winner_raw",
    "relation_raw",
    "office_raw",
    "category_raw",
}
NORMALIZED_FIELDS = (
    "office_normalized",
    "tier",
    "caste_reservation",
    "woman_reserved",
)


def _key(record):
    return (
        record["source_sha256"],
        int(record["source_page"]),
        int(record["source_row_on_page"]),
    )


def _matches(record, expected):
    return all(
        field in record
        and (
            pd.isna(record[field])
            if value is None
            else not pd.isna(record[field]) and record[field] == value
        )
        for field, value in expected.items()
    )


def apply_source_nonseat_reviews(records, root):
    """Apply checksum-pinned reviews, declining changed or ambiguous observations."""
    root = Path(root).resolve()
    reviews = {}
    for path in sorted(root.glob("source_nonseat_review_*.json")):
        raw = path.read_bytes()
        review = json.loads(raw)
        key = _key(review)
        if not re.fullmatch(r"[0-9a-f]{64}", key[0]) or key[1] < 1 or key[2] < 1:
            raise ValueError("Invalid source non-seat identity")
        if key in reviews:
            raise ValueError("Conflicting source non-seat reviews")
        if set(review["expected_raw"]) != RAW_FIELDS:
            raise ValueError("Non-seat review requires all six raw preconditions")
        if review["reason"] not in {
            "footnote",
            "category_fragment",
            "identity_fragment",
            "village_vacancy_summary",
        }:
            raise ValueError("Unsupported source non-seat reason")
        if review["reason"] == "village_vacancy_summary":
            expected = review["expected_raw"]
            body = expected["body_raw"]
            if (
                not isinstance(body, str)
                or not body.strip()
                or expected["winner_raw"] != "VACANT SEATS"
                or any(
                    expected[field] is not None
                    for field in (
                        "ward_raw",
                        "office_raw",
                        "category_raw",
                        "relation_raw",
                    )
                )
            ):
                raise ValueError(
                    "Village vacancy notice must not identify an individual seat"
                )
            primary = (root / review["primary_response_file"]).resolve()
            if not primary.is_relative_to(root):
                raise ValueError(
                    "Vacancy notice primary evidence must remain inside the review root"
                )
            if (
                hashlib.sha256(primary.read_bytes()).hexdigest()
                != review["primary_response_sha256"]
            ):
                raise ValueError("Vacancy notice primary evidence checksum mismatch")
        parent = review.get("attached_source_row_on_page")
        if review["reason"] in {"category_fragment", "identity_fragment"}:
            if type(parent) is not int or parent < 1 or parent == key[2]:
                raise ValueError("Category fragment requires a distinct source parent")
        elif parent is not None:
            raise ValueError(
                "Unattached non-seat review must not attach to a candidate"
            )
        evidence = (root / review["evidence_file"]).resolve()
        if not evidence.is_relative_to(root):
            raise ValueError("Non-seat evidence must remain inside the review root")
        if (
            hashlib.sha256(evidence.read_bytes()).hexdigest()
            != review["evidence_sha256"]
        ):
            raise ValueError("Non-seat review evidence checksum mismatch")
        reviews[key] = (review, path.name, hashlib.sha256(raw).hexdigest())

    if not reviews:
        return {}
    observations = defaultdict(list)
    for record in records:
        observations[_key(record)].append(record)
    counts = Counter()
    for key, (review, filename, digest) in reviews.items():
        targets = observations.get(key, [])
        if not targets:
            counts["nonseat_reviewed_rows_absent_from_export"] += 1
            continue
        if len(targets) != 1:
            raise ValueError("Non-seat review target is not unique")
        record = targets[0]
        valid = _matches(record, review["expected_raw"])
        parent = review.get("attached_source_row_on_page")
        if parent is not None:
            parents = observations.get((key[0], key[1], parent), [])
            valid = valid and len(parents) == 1
            if valid:
                valid = not pd.isna(parents[0].get("winner_raw"))
                valid = valid and bool(parents[0].get("winner_raw"))
        flags = set(filter(None, record["quality_flags"].split(";")))
        record["source_nonseat_review_file"] = filename
        record["source_nonseat_review_sha256"] = digest
        if not valid:
            record["source_nonseat_review_status"] = "precondition_failed"
            flags.add("source_nonseat_review_precondition_failed")
            counts["nonseat_precondition_failed"] += 1
        else:
            for field in NORMALIZED_FIELDS:
                record[f"{field}_before_nonseat_review"] = record.get(field)
                record[field] = None
            record["is_seat_record"] = False
            record["source_nonseat_review_status"] = "applied"
            record["source_nonseat_review_reason"] = review["reason"]
            record["attached_source_row_on_page"] = parent
            flags.discard("column_alignment_failed")
            flags.add("source_confirmed_nonseat_raw_preserved")
            counts["nonseat_applied"] += 1
        record["quality_flags"] = ";".join(sorted(flags))
    counts.setdefault("nonseat_reviewed_rows_absent_from_export", 0)
    return dict(counts)
