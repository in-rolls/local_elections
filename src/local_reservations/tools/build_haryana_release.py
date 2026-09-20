# ruff: noqa: E501
"""Build the checksum-pinned Haryana release and explicit quarantines.

The modern source is seat-level. The historical source is an occurrence-level
OCR review corpus and is therefore published separately; the two tables must
not be appended or joined as if they shared a row unit.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from local_reservations.paths import ROOT

SIBLING = ROOT.parent / "local_elections_haryana"
MASTER = ROOT / "data/master/master_haryana.parquet"
OBSERVATIONS = ROOT / (
    "data/master/observations/haryana/"
    "6ad3161f4b7c750e4446542bc4cf48dc5acd822c7897c4efeffdfbc56021da34/"
    "seat_rows.parquet"
)
PRIOR_RELEASE = ROOT / (
    "data/source_search/national/haryana/early_cycles/release_readiness/"
    "20260914T032746928819Z"
)
MISSING_HEADINGS = PRIOR_RELEASE / (
    "exceptions_f5bbbf70907e340aa17b9fa7225e1d26971f869b7c7a1a97278b0b5f8990d0df.json"
)
DEFAULT_OUT = ROOT / "data/haryana/release"
BUILDER = Path(__file__).resolve()
ADAPTER = ROOT / "src/local_reservations/common/adapters/haryana.py"
SIBLING_PARSER = SIBLING / "scripts/parse.py"
SIBLING_VALIDATOR = SIBLING / "scripts/validate.py"

EXPECTED = {
    MASTER: "ec5ccc5832f9c086ba6f3764a4cf45892497ba2670f88e25ce51d529a114fccc",
    OBSERVATIONS: "6e4aced101ffd3ded738830dc2a31075f66fa19cabb39637557b3803bcc72218",
    MISSING_HEADINGS: "f5bbbf70907e340aa17b9fa7225e1d26971f869b7c7a1a97278b0b5f8990d0df",
    SIBLING / "data/2016/gp_reservation.csv": (
        "04c29db08e4ee1b851d88c46c75d367f76f1ad9111b8dd0b5d5b7eea558fdb5a"
    ),
    SIBLING / "data/2016/ward_reservation.csv": (
        "13a9dd409a880ae1682abef5812595a378875b7a0820eddfa87e85ba076d2402"
    ),
    SIBLING / "data/2022/gp_reservation.csv": (
        "bd82388b42fa6e4c0975743fb9cc409441844cce4aecd96c8a672d9fb1d6efe5"
    ),
    SIBLING / "data/2022/ward_reservation.csv": (
        "fc67e6e77641fa8130dcb8a6133dde995bddd177b8f3d731796f0e90e230ab1d"
    ),
}

SOURCE_FILES = {
    (2016, "gp_head"): SIBLING / "data/2016/gp_reservation.csv",
    (2016, "gp_ward"): SIBLING / "data/2016/ward_reservation.csv",
    (2022, "gp_head"): SIBLING / "data/2022/gp_reservation.csv",
    (2022, "gp_ward"): SIBLING / "data/2022/ward_reservation.csv",
}

SOURCE_KEY = [
    "year",
    "tier",
    "district",
    "block",
    "source_path",
    "source_notification_raw",
    "source_gp_serial_raw",
    "source_gram_panchayat_raw",
    "source_ward_raw",
]
RAW_COLUMNS = {
    "sr_no": "source_gp_serial_raw",
    "gram_panchayat": "source_gram_panchayat_raw",
    "ward_no": "source_ward_raw",
    "reservation_raw": "source_reservation_raw",
    "winner": "source_winner_raw",
    "father_husband": "source_relation_raw",
    "printings_agree": "source_printings_agree_raw",
    "notification": "source_notification_raw",
    "source_pdf": "source_pdf_raw",
    "script": "source_script_raw",
}

HISTORICAL_MEMBER_TIERS = {
    "gp_ward",
    "block_member",
    "district_member",
    "zp_member",
}

FLAG_CLASSIFICATION = {
    "anchor_corroboration_requires_source_review": "pending_review",
    "bilingual_occurrence_reconciliation_pending": "occurrence_status",
    "body_context_cross_source_reviewed_raw_preserved": "review_provenance",
    "body_serial_in_name": "unresolved_field_defect",
    "body_source_reviewed_raw_preserved": "review_provenance",
    "category_reconciled_by_aligned_column_pass": "resolved_validator_status",
    "category_recovered_by_anchor_audit": "resolved_validator_status",
    "category_source_reviewed_raw_preserved": "review_provenance",
    "category_unresolved": "unresolved_field_defect",
    "column_alignment_failed": "unresolved_field_defect",
    "column_category_unresolved": "unresolved_field_defect",
    "counting_stopped_no_declared_winner": "legitimate_source_status",
    "district_member_context_source_reviewed_raw_preserved": "review_provenance",
    "duplicate_seat_key_within_page": "unresolved_identity_defect",
    "gp_context_chain_cropped_page_margin": "review_provenance",
    "gp_fragment_context_source_reviewed_raw_preserved": "review_provenance",
    "gp_notification_context_source_reviewed": "review_provenance",
    "handwritten_category_amendment_requires_authority_review": "unresolved_authority",
    "incoming_body_context_unvalidated": "pending_review",
    "invalid_control_characters": "raw_source_status",
    "malformed_ward": "unresolved_field_defect",
    "mixed_notification_context_requires_review": "pending_review",
    "notification_number_source_unresolved": "unresolved_provenance",
    "office_category_corroborated_by_unique_name_anchor": "validator_corroboration",
    "office_source_reviewed_raw_preserved": "review_provenance",
    "office_spelling_normalized_raw_preserved": "resolved_validator_status",
    "office_unresolved": "unresolved_field_defect",
    "overlapping_source_observation_reconciliation_pending": "occurrence_status",
    "page_footnote_misattributed_as_winner": "resolved_nonperson_status",
    "printed_vacancy_source_reviewed_raw_preserved": "legitimate_source_status",
    "relation_source_reviewed_raw_preserved": "review_provenance",
    "samiti_body_context_requires_source_review": "unresolved_field_defect",
    "samiti_body_context_source_reviewed": "review_provenance",
    "samiti_or_empty_page_source_review_required": "pending_review",
    "samiti_printed_category_source_reviewed": "review_provenance",
    "samiti_section_source_reviewed_raw_preserved": "review_provenance",
    "samiti_vacancy_source_reviewed": "legitimate_source_status",
    "seat_identity_source_reviewed_raw_preserved": "review_provenance",
    "source_confirmed_nonseat_raw_preserved": "legitimate_nonseat_status",
    "tier_from_inventory_unvalidated": "pending_review",
    "unanchored_fragment": "unresolved_identity_defect",
    "ward_footnote_marker_unreadable": "raw_source_status",
    "ward_missing": "unresolved_field_defect",
    "winner_missing": "field_status_or_defect",
    "winner_not_person_source_reviewed_raw_preserved": "legitimate_nonperson_status",
    "winner_source_reviewed_raw_preserved": "review_provenance",
    "winner_status_semantics_unresolved": "unresolved_status",
}


def checksum(path: Path) -> str:
    """Return the SHA-256 digest of a file."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require_pins() -> None:
    """Refuse to build from a silently changed adjudication baseline."""
    for path, expected in EXPECTED.items():
        got = checksum(path)
        if got != expected:
            raise ValueError(f"Pinned Haryana input changed: {path}: {got}")


def split_flags(value: object) -> set[str]:
    """Read the semicolon-delimited quality annotation."""
    if not isinstance(value, str):
        return set()
    return {item for item in value.split(";") if item}


def printing_classification(tier: str, raw: str) -> str:
    """Classify the sibling's GP-head cross-printing comparison."""
    if raw != "0":
        return "not_disagreeing"
    if tier == "gp_ward":
        return "inherited_gp_head_comparison_not_ward_defect"
    if tier == "gp_head":
        return "gp_head_source_printing_variation_preferred_printing_retained"
    raise ValueError(f"Unexpected Haryana tier: {tier}")


def read_modern() -> pd.DataFrame:
    """Bind source literals to the pooled rows under a row-conservation guard."""
    master = pq.read_table(MASTER).to_pandas()
    parts = []
    for (year, tier), path in SOURCE_FILES.items():
        source = pd.read_csv(path, dtype=str, keep_default_na=False)
        target = master[master.year.eq(year) & master.tier.eq(tier)].reset_index(
            drop=True
        )
        if len(source) != len(target):
            raise ValueError(f"Haryana source/master row count mismatch: {year}/{tier}")
        target["source_csv_row_1based"] = range(1, len(target) + 1)
        for source_name, release_name in RAW_COLUMNS.items():
            if source_name == "ward_no" and tier == "gp_head":
                target[release_name] = ""
            else:
                target[release_name] = source[source_name].to_numpy()
        expected_pdf = target.source_path.str.rsplit("/", n=1).str[-1]
        if not expected_pdf.eq(target.source_pdf_raw).all():
            raise ValueError(f"Haryana source path mismatch: {year}/{tier}")
        for field in ("district", "block", "gram_panchayat", "reservation_raw"):
            source_field = (
                "source_gram_panchayat_raw"
                if field == "gram_panchayat"
                else "source_reservation_raw"
                if field == "reservation_raw"
                else field
            )
            values = (
                source[source_field] if source_field in source else target[source_field]
            )
            left = target[field].fillna("").astype(str).str.strip()
            right = values.fillna("").astype(str).str.strip()
            comparable = (
                source.script.ne("krutidev")
                if field == "gram_panchayat"
                else pd.Series(True, index=source.index)
            )
            if not left[comparable].eq(right[comparable]).all():
                raise ValueError(
                    f"Haryana source/master value mismatch: {year}/{tier}/{field}"
                )
        parts.append(target)
    result = pd.concat(parts, ignore_index=True)
    if len(result) != len(master):
        raise ValueError("Haryana modern row conservation failed")
    result["quality_flags_original"] = result.quality_flags
    result["printing_reconciliation"] = [
        printing_classification(tier, raw)
        for tier, raw in zip(
            result.tier, result.source_printings_agree_raw, strict=True
        )
    ]
    result["release_source_key"] = result[SOURCE_KEY].astype(str).agg("|".join, axis=1)
    duplicate = result.duplicated(SOURCE_KEY, keep=False)
    missing_ward = result.tier.eq("gp_ward") & result.source_ward_raw.eq("")
    reasons = []
    for no_ward, duplicated in zip(missing_ward, duplicate, strict=True):
        row = []
        if no_ward:
            row.append("source_ward_missing")
        if duplicated:
            row.append("source_seat_identity_not_unique")
        reasons.append(";".join(row))
    result["release_quarantine_reason"] = reasons
    result["release_eligible"] = result.release_quarantine_reason.eq("")
    return result


def read_historical() -> tuple[pd.DataFrame, set[tuple[str, int, int]]]:
    """Read the pinned reviewed occurrences and missing-heading exception keys."""
    frame = pq.read_table(OBSERVATIONS).to_pandas()
    payload = json.loads(MISSING_HEADINGS.read_bytes())
    rows = payload["rows"]
    if len(rows) != 32:
        raise ValueError("Missing-heading exception set no longer has 32 rows")
    keys = {
        (row["source_sha256"], row["source_page"], row["source_row_on_page"])
        for row in rows
    }
    if len(keys) != 32:
        raise ValueError("Missing-heading exception keys are not unique")
    return frame, keys


def classify_historical(
    frame: pd.DataFrame, missing_heading_keys: set[tuple[str, int, int]]
) -> pd.DataFrame:
    """Separate reviewed usable occurrences from exceptions and provisional OCR."""
    result = frame.copy()
    identity_reviewed = (
        result.source_samiti_review_status.eq("applied")
        | result.source_district_review_status.eq("applied")
        | result.source_identity_review_status.eq("applied")
    )
    nonseat = result.source_nonseat_review_status.eq("applied")
    keys = list(
        zip(
            result.source_sha256,
            result.source_page.astype(int),
            result.source_row_on_page.astype(int),
            strict=True,
        )
    )
    missing_heading = pd.Series(
        [key in missing_heading_keys for key in keys], index=result.index
    )
    reasons = []
    for index, row in result.iterrows():
        row_reasons = []
        if missing_heading.at[index]:
            row_reasons.append("original_samiti_heading_missing")
        if pd.isna(row.body_within_page):
            row_reasons.append("body_context_missing")
        if pd.isna(row.tier):
            row_reasons.append("tier_missing")
        if row.tier in HISTORICAL_MEMBER_TIERS and pd.isna(row.ward):
            row_reasons.append("member_ward_missing")
        if pd.isna(row.caste_reservation) or pd.isna(row.woman_reserved):
            row_reasons.append("reservation_category_missing_or_unverified")
        reasons.append(";".join(row_reasons))
    result["release_exception_reason"] = reasons
    result["release_reviewed_identity"] = identity_reviewed
    result["release_missing_heading_exception"] = missing_heading
    disposition = pd.Series("provisional_unvalidated", index=result.index)
    disposition.loc[nonseat] = "reviewed_nonseat"
    reviewed_seat = identity_reviewed & ~nonseat
    disposition.loc[reviewed_seat & result.release_exception_reason.ne("")] = (
        "reviewed_unresolved_quarantine"
    )
    disposition.loc[reviewed_seat & result.release_exception_reason.eq("")] = (
        "reviewed_release_occurrence"
    )
    result["release_disposition"] = disposition
    if set(result.loc[missing_heading, "release_disposition"]) != {
        "reviewed_unresolved_quarantine"
    }:
        raise ValueError("Missing-heading rows escaped historical quarantine")
    return result


def flag_reconciliation(frame: pd.DataFrame) -> dict[str, object]:
    """Count every historical annotation by release disposition."""
    counts: dict[str, Counter[str]] = {}
    observed = set()
    for _, row in frame.iterrows():
        for flag in split_flags(row.quality_flags):
            observed.add(flag)
            counts.setdefault(flag, Counter())[row.release_disposition] += 1
    unknown = observed - FLAG_CLASSIFICATION.keys()
    if unknown:
        raise ValueError(f"Unclassified Haryana quality flags: {sorted(unknown)}")
    return {
        "flags": [
            {
                "flag": flag,
                "classification": FLAG_CLASSIFICATION[flag],
                "rows": sum(counts[flag].values()),
                "release_dispositions": dict(sorted(counts[flag].items())),
                "interpretation": (
                    "The flag class describes the annotation; row release is governed by "
                    "source review and required-field completeness. Counts overlap."
                ),
            }
            for flag in sorted(observed)
        ]
    }


def write_parquet(frame: pd.DataFrame, path: Path) -> None:
    """Write a typed Parquet artifact without a pandas index."""
    pq.write_table(pa.Table.from_pandas(frame, preserve_index=False), path)


def file_record(path: Path, root: Path) -> dict[str, object]:
    """Describe a release artifact."""
    return {
        "path": str(path.relative_to(root)),
        "bytes": path.stat().st_size,
        "sha256": checksum(path),
    }


def build(out: Path = DEFAULT_OUT) -> dict[str, object]:
    """Build the Haryana release bundle and return its receipt."""
    require_pins()
    out.mkdir(parents=True, exist_ok=True)
    modern = read_modern()
    historical, missing_heading_keys = read_historical()
    historical = classify_historical(historical, missing_heading_keys)

    modern_clean = modern[modern.release_eligible].copy()
    modern_quarantine = modern[~modern.release_eligible].copy()
    historical_clean = historical[
        historical.release_disposition.eq("reviewed_release_occurrence")
    ].copy()
    historical_quarantine = historical[
        historical.release_disposition.eq("reviewed_unresolved_quarantine")
    ].copy()
    historical_provisional = historical[
        historical.release_disposition.isin(
            ["provisional_unvalidated", "reviewed_nonseat"]
        )
    ].copy()
    printing = modern[modern.source_printings_agree_raw.eq("0")].copy()

    outputs = {
        "modern_seats.parquet": modern_clean,
        "modern_quarantine.parquet": modern_quarantine,
        "historical_reviewed_occurrences.parquet": historical_clean,
        "historical_quarantine.parquet": historical_quarantine,
        "historical_provisional_observations.parquet": historical_provisional,
        "printing_reconciliation.parquet": printing,
    }
    for name, frame in outputs.items():
        write_parquet(frame, out / name)
        reread = pq.read_table(out / name)
        if reread.num_rows != len(frame):
            raise ValueError(f"Parquet row-count round-trip failed: {name}")
        try:
            pd.testing.assert_frame_equal(
                frame.reset_index(drop=True),
                reread.to_pandas(),
                check_dtype=False,
                check_exact=True,
                check_categorical=False,
            )
        except AssertionError as error:
            raise ValueError(f"Parquet value round-trip failed: {name}") from error

    printing_counts = Counter(printing.printing_reconciliation)
    if printing_counts != {
        "inherited_gp_head_comparison_not_ward_defect": 1392,
        "gp_head_source_printing_variation_preferred_printing_retained": 144,
    }:
        raise ValueError(f"Unexpected printing reconciliation: {printing_counts}")
    if len(modern_clean) + len(modern_quarantine) != len(modern):
        raise ValueError("Modern release row conservation failed")
    if modern_clean.duplicated(SOURCE_KEY).any():
        raise ValueError("Modern release source key is not unique")
    if len(historical_clean) + len(historical_quarantine) + len(
        historical_provisional
    ) != len(historical):
        raise ValueError("Historical release row conservation failed")

    reconciliation = flag_reconciliation(historical)
    reconciliation["printing_disagree"] = {
        "total": len(printing),
        "stale_ward_scope_artifacts": printing_counts[
            "inherited_gp_head_comparison_not_ward_defect"
        ],
        "legitimate_gp_head_source_variations": printing_counts[
            "gp_head_source_printing_variation_preferred_printing_retained"
        ],
        "actual_unresolved_defects_from_printing_flag": 0,
        "included_rows": int(printing.release_eligible.sum()),
        "quarantined_for_independent_identity_defects": int(
            (~printing.release_eligible).sum()
        ),
        "proof": [
            "The sibling crosscheck constructs comparisons only from sarpanch rows.",
            "It then copies the GP-level result to all rows sharing PDF and GP serial.",
            "The sibling select_printing retains the Latin-majority, most complete printing.",
            "The sibling validator treats cross-printing disagreement as a non-hard diagnostic; "
            "reservation normalization and block statutory checks remain hard gates.",
        ],
    }
    (out / "flag_reconciliation.json").write_text(
        json.dumps(reconciliation, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    receipt = {
        "schema_version": 1,
        "status": "release_ready_with_explicit_quarantines",
        "row_units": {
            "modern": "one source seat record from the selected 2016/2022 printing",
            "historical": "one source-reviewed 2000 printed occurrence; not a unique-seat denominator",
        },
        "modern": {
            "input_rows": len(modern),
            "included_rows": len(modern_clean),
            "quarantined_rows": len(modern_quarantine),
            "included_by_year_tier": {
                f"{year}/{tier}": int(count)
                for (year, tier), count in modern_clean.groupby(["year", "tier"])
                .size()
                .items()
            },
            "quarantined_by_year_tier": {
                f"{year}/{tier}": int(count)
                for (year, tier), count in modern_quarantine.groupby(["year", "tier"])
                .size()
                .items()
            },
            "quarantine_reasons_overlapping": dict(
                Counter(
                    reason
                    for value in modern_quarantine.release_quarantine_reason
                    for reason in value.split(";")
                    if reason
                )
            ),
            "printing_disagree_reconciliation": reconciliation["printing_disagree"],
        },
        "historical": {
            "input_observations": len(historical),
            "included_source_reviewed_occurrences": len(historical_clean),
            "reviewed_unresolved_quarantine": len(historical_quarantine),
            "missing_heading_quarantine": int(
                historical_quarantine.release_missing_heading_exception.sum()
            ),
            "provisional_or_nonseat_preserved_outside_release": len(
                historical_provisional
            ),
            "provisional_unvalidated": int(
                historical.release_disposition.eq("provisional_unvalidated").sum()
            ),
            "reviewed_nonseat": int(
                historical.release_disposition.eq("reviewed_nonseat").sum()
            ),
            "quarantine_reasons_overlapping": dict(
                Counter(
                    reason
                    for value in historical_quarantine.release_exception_reason
                    for reason in value.split(";")
                    if reason
                )
            ),
        },
        "combined_included_rows_not_a_single_row_unit": len(modern_clean)
        + len(historical_clean),
        "inputs": [
            {"path": str(path), "sha256": checksum(path)}
            for path in [MASTER, OBSERVATIONS, MISSING_HEADINGS, *SOURCE_FILES.values()]
        ],
        "code_provenance": [
            {"path": str(path), "sha256": checksum(path)}
            for path in [BUILDER, ADAPTER, SIBLING_PARSER, SIBLING_VALIDATOR]
        ],
        "policies": {
            "raw_literals": "Preserved in source_*_raw fields and the historical OCR columns.",
            "missing_headings": "INDRI and BABAIN remain candidates/corroboration only; no heading assigned.",
            "printing_disagreement": "Retained as source status in the ledger, not used as a release blocker.",
            "modern_identity": "Quarantine all rows in a duplicated source seat key and all ward rows without a source ward.",
            "historical_scope": "Publish only reviewed, field-complete seat occurrences; preserve automated observations separately.",
        },
        "release_ready": True,
        "limitations": [
            "The modern release excludes ambiguous source identities rather than choosing a winner or ward.",
            "The historical table is occurrence-level and cannot be appended to the modern seat table.",
            "Provisional historical OCR remains evidence, not released reservation assignments.",
        ],
    }
    (out / "release_receipt.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (out / "join_contract.json").write_text(
        json.dumps(
            {
                "left": "modern_seats.parquet",
                "left_rows": len(modern_clean),
                "left_key": SOURCE_KEY,
                "left_key_unique": not modern_clean.duplicated(SOURCE_KEY).any(),
                "right": None,
                "cardinality": "no join performed",
                "historical_append_forbidden": True,
                "reason": "Historical rows are source occurrences, not the modern unique-seat unit.",
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    dictionary = """# Haryana release data dictionary

| artifact | row unit | universe | missing policy | provenance |
|---|---|---|---|---|
| `modern_seats.parquet` | selected-printing seat | 2016/2022 rows with complete, unique source identity | no imputation | pooled master plus checksum-pinned sibling CSV literals |
| `modern_quarantine.parquet` | source row | incomplete or duplicated modern source identity | preserve null/blank literally | same as modern release |
| `historical_reviewed_occurrences.parquet` | printed occurrence | source-reviewed 2000 seat occurrences with body, tier, ward where required, and category | no imputation | frozen review snapshot and source-review hashes |
| `historical_quarantine.parquet` | printed occurrence | reviewed occurrences missing an essential release field | preserve null and reason | frozen review snapshot; includes exactly 32 missing-heading rows |
| `historical_provisional_observations.parquet` | OCR occurrence | unvalidated OCR and reviewed non-seat records | outside release universe | frozen review snapshot |
| `printing_reconciliation.parquet` | modern row carrying source `printings_agree=0` | all 1,536 such rows | status only, no value rewrite | sibling parser comparison plus pooled row provenance |

`source_*_raw` columns are literal sibling CSV fields. Existing modern master
columns remain unchanged. Historical raw OCR fields remain in every partition.
Blank source wards and null historical cells are unknown, not zero.
"""
    (out / "data_dictionary.md").write_text(dictionary, encoding="utf-8")
    ledger = """# Haryana release recode ledger

| derived field | source | definition | count check | reason |
|---|---|---|---|---|
| `printing_reconciliation` | `source_printings_agree_raw`, tier | ward `0` = inherited GP-head comparison; head `0` = retained source variation | 1,392 + 144 = 1,536 | stop a GP-head diagnostic from masquerading as a ward defect |
| `release_source_key` | source provenance and printed identity fields | year, tier, district, block, PDF, notification, GP serial/name, ward | unique in modern release | distinguish same-named printed offices without fuzzy matching |
| `release_quarantine_reason` | source identity fields | blank ward and/or duplicated source seat key | input = included + quarantined | never choose among ambiguous seats |
| `release_disposition` | review status and required fields | reviewed release, reviewed quarantine, reviewed non-seat, or provisional | four-way row conservation | keep occurrence-level validation claims bounded |

No source literal, reservation category, winner, ward, or body heading is recoded.
"""
    (out / "recode_ledger.md").write_text(ledger, encoding="utf-8")

    names = sorted(
        path.name
        for path in out.iterdir()
        if path.name not in {"SHA256SUMS", "artifact_manifest.json"}
    )
    records = [file_record(out / name, out) for name in names]
    (out / "artifact_manifest.json").write_text(
        json.dumps({"schema_version": 1, "files": records}, indent=2) + "\n",
        encoding="utf-8",
    )
    names = sorted(path.name for path in out.iterdir() if path.name != "SHA256SUMS")
    (out / "SHA256SUMS").write_text(
        "".join(f"{checksum(out / name)}  {name}\n" for name in names),
        encoding="ascii",
    )
    return receipt


def main() -> None:
    """Build the local Haryana release."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    print(json.dumps(build(args.out), sort_keys=True))


if __name__ == "__main__":
    main()
