"""Apply source-pinned seat identity repairs without changing OCR observations."""

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


def _key(record):
    return (
        record["source_sha256"],
        int(record["source_page"]),
        int(record["source_row_on_page"]),
    )


def _pinned_file(root, filename, digest):
    path = (root / filename).resolve()
    if not path.is_relative_to(root):
        raise ValueError("Identity evidence must be inside the source root")
    if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise ValueError("Identity evidence requires a SHA-256 digest")
    if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
        raise ValueError(f"Identity evidence changed: {filename}")


def apply_source_identity_reviews(records, root: Path):
    """Require unique targets, six raw guards, and pinned visual/response evidence."""
    root = root.resolve()
    targets = defaultdict(list)
    for record in records:
        targets[_key(record)].append(record)
    pending = []
    seen = set()
    for path in sorted(root.glob("source_identity_review_*.json")):
        raw = path.read_bytes()
        review = json.loads(raw)
        key = _key(review)
        if (
            not re.fullmatch(r"[0-9a-f]{64}", key[0])
            or key[1] < 1
            or key[2] < 1
            or key in seen
            or len(targets[key]) != 1
        ):
            raise ValueError(f"Ambiguous or invalid identity target: {path.name}")
        seen.add(key)
        expected = review["expected_raw"]
        if set(expected) != RAW_FIELDS:
            raise ValueError("Identity review requires all six raw preconditions")
        record = targets[key][0]
        for field, value in expected.items():
            if field not in record or (
                not pd.isna(record[field])
                if value is None
                else pd.isna(record[field]) or record[field] != value
            ):
                raise ValueError(f"Identity precondition failed: {path.name}: {field}")
        flags = set(filter(None, record["quality_flags"].split(";")))
        kind = review.get("review_kind", "seat_identity")
        if kind == "nonperson_winner":
            corrected = review["corrected"]
            if set(corrected) != {
                "winner_source_review_raw",
                "winner_ocr_text_role",
                "winner_identity_usable",
            }:
                raise ValueError("Unsupported nonperson winner correction fields")
            literal = {
                "page_footnote": (
                    "\u0928\u093f\u0930\u094d\u0935\u093f\u0930\u094b\u0927"
                ),
                "printed_blank_notice": "BLANK",
                "unscoped_vacancy_annotation": "VACANT",
                "printed_vacancy_notice": "VACCANT",
            }.get(corrected["winner_ocr_text_role"])
            if (
                literal is None
                or expected["winner_raw"] != literal
                or corrected["winner_source_review_raw"] is not None
                or corrected["winner_identity_usable"] is not False
                or not pd.isna(record.get("winner_source_review_raw"))
                or "source_confirmed_nonseat_raw_preserved" in flags
            ):
                raise ValueError(
                    "Nonperson review cannot infer or replace a source identity"
                )
            if corrected["winner_ocr_text_role"] == "printed_vacancy_notice" and (
                record.get("office_normalized") != "SARPANCH"
                or not pd.isna(record.get("ward"))
                or not isinstance(expected["body_raw"], str)
                or not expected["body_raw"].strip()
                or expected["body_raw"] != record.get("body_within_page")
                or "office_source_reviewed_raw_preserved" not in flags
            ):
                raise ValueError(
                    "Printed vacancy requires a reviewed GP head and explicit body"
                )
            _pinned_file(root, review["evidence_file"], review["evidence_sha256"])
            _pinned_file(
                root, review["primary_response_file"], review["primary_response_sha256"]
            )
            pending.append(
                (record, corrected, path.name, hashlib.sha256(raw).hexdigest(), kind)
            )
            continue
        if kind != "seat_identity":
            raise ValueError("Unsupported identity review kind")
        if (
            "source_confirmed_nonseat_raw_preserved" in flags
            or record.get("office_normalized") != "PANCH"
            or not {
                "office_source_reviewed_raw_preserved",
                "category_source_reviewed_raw_preserved",
            }.issubset(flags)
        ):
            raise ValueError("Identity repair requires a source-reviewed Panch seat")
        corrected = review["corrected"]
        if set(corrected) != {
            "ward",
            "winner_source_review_raw",
            "ward_source_review_raw",
        }:
            raise ValueError("Unsupported identity correction fields")
        ward = corrected["ward"]
        winner = corrected["winner_source_review_raw"]
        ward_source = corrected["ward_source_review_raw"]
        if (
            type(ward) is not int
            or ward < 1
            or not isinstance(winner, str)
            or not winner.strip()
        ):
            raise ValueError("Identity correction requires a positive ward and winner")
        match = re.fullmatch(r"([1-9][0-9]*)(?: \*)?", ward_source)
        if match is None or int(match.group(1)) != ward:
            raise ValueError("Reviewed ward label disagrees with corrected ward")
        _pinned_file(root, review["evidence_file"], review["evidence_sha256"])
        _pinned_file(
            root, review["primary_response_file"], review["primary_response_sha256"]
        )
        pending.append(
            (record, corrected, path.name, hashlib.sha256(raw).hexdigest(), kind)
        )
    counts = Counter()
    for record, corrected, filename, digest, kind in pending:
        for field, value in corrected.items():
            previous = record.get(field)
            record[f"{field}_before_identity_review"] = (
                None if pd.isna(previous) else previous
            )
            record[field] = value
        record["source_identity_review_file"] = filename
        record["source_identity_review_sha256"] = digest
        flags = set(filter(None, record["quality_flags"].split(";")))
        if kind == "nonperson_winner":
            record["source_identity_review_status"] = "applied_nonperson_winner"
            flags.add("winner_not_person_source_reviewed_raw_preserved")
            if corrected["winner_ocr_text_role"] == "printed_vacancy_notice":
                flags.difference_update(
                    {"winner_missing", "winner_status_semantics_unresolved"}
                )
                flags.add("printed_vacancy_source_reviewed_raw_preserved")
                counts["printed_vacancy"] += 1
            else:
                flags.add("winner_missing")
                if corrected["winner_ocr_text_role"] == "page_footnote":
                    flags.add("page_footnote_misattributed_as_winner")
                else:
                    flags.add("winner_status_semantics_unresolved")
            record["quality_flags"] = ";".join(sorted(flags))
            counts["nonperson_winner"] += 1
            continue
        record["source_identity_review_status"] = "applied"
        flags.difference_update({"ward_missing", "malformed_ward"})
        flags.update(
            {
                "seat_identity_source_reviewed_raw_preserved",
                "winner_source_reviewed_raw_preserved",
            }
        )
        record["quality_flags"] = ";".join(sorted(flags))
        counts["applied"] += 1
    return dict(counts)
