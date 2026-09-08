"""Export source-pinned visual readings of the 2001 GP-president amendments.

These operations have not been applied to the 1996 base roster. Other tiers
and district-heading changes stay distinct from GP-level row operations.
"""

import argparse
import collections
import csv
import hashlib
import json
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from local_reservations.common.runlog import command
from local_reservations.paths import ROOT

OUT = ROOT / "data/tn/derived/amendments_2001"
SOURCE_SHA = "5cc758b6cc8ad025f284276c61ce3f24302890783ea0a0233a6f2d4d76051bf3"
CATEGORIES = {
    "General": ("UR", False),
    "General (Women)": ("UR", True),
    "SC (General)": ("SC", False),
    "SC (Women)": ("SC", True),
    "ST (General)": ("ST", False),
    "ST (Women)": ("ST", True),
}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_document(readings, source):
    data = json.loads(readings.read_text())
    if data["source_sha256"] != SOURCE_SHA or digest(source) != SOURCE_SHA:
        raise ValueError("Manual readings do not match the audited source PDF")
    for evidence in data.get("page_visual_evidence", []):
        image = ROOT / evidence["image_path"]
        if evidence["source_sha256"] != SOURCE_SHA:
            raise ValueError("Visual evidence source identity mismatch")
        if digest(image) != evidence["image_sha256"]:
            raise ValueError("Visual evidence image hash mismatch")
    return data


def flatten_operations(data):
    """Keep section replacements and serial-addressed changes as operations."""
    rows, sections = [], []
    for group in data["replacement_sections"]:
        section_key = (
            f"{group['clause']}|{group['district_printed']}|{group['union_printed']}"
        )
        section_id = hashlib.sha256(section_key.encode()).hexdigest()[:20]
        if len(group["entries"]) != group["expected_rows"]:
            raise ValueError(f"Replacement section row count differs: {section_key}")
        expected = [str(i) for i in range(1, group["expected_rows"] + 1)]
        if [row["serial_printed"] for row in group["entries"]] != expected:
            raise ValueError(f"Replacement serial sequence differs: {section_key}")
        sections.append(
            {
                "section_id": section_id,
                "clause": group["clause"],
                "district_printed": group["district_printed"],
                "union_printed": group["union_printed"],
                "operation_type": "replace_section",
                "row_count": len(group["entries"]),
                "source_pages": sorted({r["source_page"] for r in group["entries"]}),
            }
        )
        for entry in group["entries"]:
            rows.append(
                {
                    "section_id": section_id,
                    "clause": group["clause"],
                    "district_printed": group["district_printed"],
                    "union_printed": group["union_printed"],
                    "operation_type": "replace_section",
                    **entry,
                }
            )
    rows.extend(data["individual_operations"])
    normalized = []
    for row in rows:
        kind = row["operation_type"]
        name = row["name_printed"]
        if kind not in {"replace_section", "insert", "replace_category"}:
            raise ValueError(f"Unexpected GP operation: {kind}")
        if kind == "replace_category":
            if name is not None or not row.get("target_serial_printed"):
                raise ValueError(
                    "Serial-only category targets must retain unknown names"
                )
            if row.get("old_category_reading") not in CATEGORIES:
                raise ValueError(
                    "Category replacement lacks printed old-category target"
                )
        elif not name:
            raise ValueError("Named replacement or insertion has no source name")
        if kind == "insert" and not row.get("after_serial_printed"):
            raise ValueError("Insertion lacks its printed anchor")
        if not 2 <= row["source_page"] <= 16:
            raise ValueError("GP operation escaped the reviewed GP amendment pages")
        caste, women = CATEGORIES[row["category_reading"]]
        locator = row["source_locator"]
        key = f"{SOURCE_SHA}|{row['source_page']}|{locator}"
        normalized.append(
            {
                "row_id": hashlib.sha256(key.encode()).hexdigest()[:24],
                "state": "Tamil Nadu",
                "document_year": 2001,
                "stage": "amendment",
                "tier": "gp_president",
                "operation_type": kind,
                "section_id": row.get("section_id"),
                "clause": row["clause"],
                "district_printed": row["district_printed"],
                "union_printed": row["union_printed"],
                "serial_printed": row.get("serial_printed"),
                "target_serial_printed": row.get("target_serial_printed"),
                "after_serial_printed": row.get("after_serial_printed"),
                "gp_name_printed": name,
                "old_category_reading": row.get("old_category_reading"),
                "new_category_reading": row["category_reading"],
                "new_reservation_caste": caste,
                "new_reservation_women": women,
                "officeholder_name": None,
                "officeholder_sex": None,
                "source_path": data["source_path"],
                "source_sha256": SOURCE_SHA,
                "source_page": row["source_page"],
                "source_locator": locator,
                "reading_method": "manual_source_visual_transcription",
                "quality_flags": row.get("quality_flags", []),
            }
        )
    if len({r["row_id"] for r in normalized}) != len(normalized):
        raise ValueError("Duplicate source operation locator")
    return normalized, sections


def write_table(path, rows):
    """Use one row schema in both CSV and Parquet, preserving nulls in Parquet."""
    if not rows:
        raise ValueError("No rows to export")
    keys = list(dict.fromkeys(key for row in rows for key in row))
    records = [{key: row.get(key) for key in keys} for row in rows]
    with path.with_suffix(".csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=keys)
        writer.writeheader()
        for row in records:
            writer.writerow(
                {
                    key: json.dumps(value, ensure_ascii=False)
                    if isinstance(value, (list, dict))
                    else value
                    for key, value in row.items()
                }
            )
    pq.write_table(pa.Table.from_pylist(records), path.with_suffix(".parquet"))
    path.with_suffix(".jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in records)
    )


def machine_evidence(root):
    """Pin existing machine OCR independently; never use it as curated values."""
    evidence = []
    base = root / "data/tn/derived/scans/tn_1_58_2001_636_en"
    for page in range(1, 19):
        directory = base / f"page_{page:04d}"
        latest = directory / "latest.json"
        metadata = json.loads(latest.read_text())
        identity = metadata["identity"]
        if identity["source_sha256"] != SOURCE_SHA or identity["source_page"] != page:
            raise ValueError("Machine OCR cache source identity mismatch")
        artifacts = {}
        for kind, record in metadata["artifacts"].items():
            artifact = directory / record["path"]
            if digest(artifact) != record["sha256"]:
                raise ValueError(f"Machine OCR artifact hash mismatch: {artifact}")
            artifacts[kind] = {
                "path": str(artifact.relative_to(root)),
                "sha256": record["sha256"],
            }
        evidence.append(
            {"source_page": page, "identity": identity, "artifacts": artifacts}
        )
    return evidence


def verify_named_review(data, review, reading_hash):
    """Require the independent review to describe these exact named readings."""
    if review["source_sha256"] != SOURCE_SHA:
        raise ValueError("Independent review source mismatch")
    if review["current_canonical_sha256"] != reading_hash:
        raise ValueError("Independent review predates the current manual readings")
    expected_pointers = {
        f"/replacement_sections/{i}/entries/{j}"
        for i, group in enumerate(data["replacement_sections"])
        for j in range(len(group["entries"]))
    } | {
        f"/individual_operations/{i}"
        for i, row in enumerate(data["individual_operations"])
        if row["name_printed"] is not None
    }
    pointers = set()
    for row in review["rows"]:
        pointer = row["row_identifier"]
        if pointer in pointers or not row["visually_checked"]:
            raise ValueError("Duplicate or unreviewed independent-review row")
        if pointer not in expected_pointers or row["source_sha256"] != SOURCE_SHA:
            raise ValueError("Independent review row source identity mismatch")
        pointers.add(pointer)
        entry = data
        for part in pointer.strip("/").split("/"):
            entry = entry[int(part)] if isinstance(entry, list) else entry[part]
        original = row["original_reading"]
        if entry["name_printed"] != row["current_name_reading"]:
            raise ValueError("Named reading differs from independent visual review")
        for key in ("serial_printed", "category_reading", "source_page"):
            if entry[key] != original[key]:
                raise ValueError("Source row value differs from independent review")
    if pointers != expected_pointers or len(pointers) != 451:
        raise ValueError("Independent named-review coverage is incomplete")


def export(readings, source, output, root=ROOT):
    data = read_document(readings, source)
    rows, sections = flatten_operations(data)
    counts = collections.Counter(row["operation_type"] for row in rows)
    if counts != {"replace_section": 434, "insert": 17, "replace_category": 5}:
        raise ValueError("GP operation controls do not reconcile")
    if len(sections) != 16 or len(data["context_operations"]) != 20:
        raise ValueError("Section or context controls do not reconcile")
    output.mkdir(parents=True, exist_ok=True)
    reading_hash = digest(readings)
    review_path = readings.parent / "independent_name_review.json"
    independent_review = json.loads(review_path.read_text())
    verify_named_review(data, independent_review, reading_hash)
    review_hash = digest(review_path)
    for row in rows:
        row["manual_readings_sha256"] = reading_hash
        row["independent_review_sha256"] = review_hash
    write_table(output / "gp_president_amendment_operations", rows)
    for section in sections:
        section.update(
            source_path=data["source_path"],
            source_sha256=SOURCE_SHA,
            manual_readings_sha256=reading_hash,
        )
    write_table(output / "replacement_section_counts", sections)
    contexts = [
        {
            **row,
            "source_path": data["source_path"],
            "source_sha256": SOURCE_SHA,
            "manual_readings_sha256": reading_hash,
        }
        for row in data["context_operations"]
    ]
    write_table(output / "context_operations", contexts)
    page_audit = []
    for page in range(1, 19):
        page_audit.append(
            {
                "source_path": data["source_path"],
                "source_sha256": SOURCE_SHA,
                "source_page": page,
                "gp_row_operations": sum(row["source_page"] == page for row in rows),
                "context_operations": sum(
                    row["source_page"] == page for row in contexts
                ),
                "clauses": [
                    row for row in data["clause_audit"] if page in row["source_pages"]
                ],
                "status": "reviewed_other_tier_excluded"
                if page >= 17
                else "gp_scope_parsed",
            }
        )
    write_table(output / "page_audit", page_audit)
    evidence = machine_evidence(root)
    verification = {
        "source_sha256": SOURCE_SHA,
        "manual_readings_sha256": reading_hash,
        "gp_operations": len(rows),
        "named_gp_operations": sum(row["gp_name_printed"] is not None for row in rows),
        "operation_counts": dict(counts),
        "replacement_sections": len(sections),
        "context_operations": len(contexts),
        "clause_audit": data["clause_audit"],
        "unparsed_gp_clauses": [],
        "unresolved_target_gp_names": 5,
        "unresolved_source_name_readings": 0,
        "independent_named_entries_reviewed": 451,
        "independent_review_sha256": review_hash,
        "applied_to_1996_roster": False,
        "complete_statewide_2001_roster": False,
        "winner_name_or_sex_observed": False,
    }
    (output / "verification.json").write_text(json.dumps(verification, indent=2) + "\n")
    (output / "machine_ocr_provenance.json").write_text(
        json.dumps(evidence, indent=2) + "\n"
    )
    return verification


@command("parse", state="Tamil Nadu", source="gp_president_amendments_2001")
def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--readings", type=Path, default=OUT / "manual_readings.json")
    parser.add_argument(
        "--source",
        type=Path,
        default=ROOT / "data/source_search/early_heads/raw/tn_1_58_2001_636_en.pdf",
    )
    parser.add_argument("--output", type=Path, default=OUT)
    args = parser.parse_args()
    export(args.readings, args.source, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
