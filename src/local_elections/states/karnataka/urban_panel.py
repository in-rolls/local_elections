"""Build the reviewed Bengaluru 2010–2015 ward panel from retained sources."""

import argparse
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from local_elections.common.runlog import command

NAME = "ward_panel_2010_2015"
BASE = Path("data/karnataka")
MANUAL = BASE / "manual/urban_expansion"
OUTPUT = BASE / "build/urban_expansion"
OPENCITY = Path(
    "data/reference/opencity/bengaluru_bbmp_2015_womens_reservation_seats_results.csv"
)
PAIR_SOURCE = BASE / "raw/urban_expansion/bbmp_reservations_2010_2015.csv"
HONORIFICS = {"ಶ್ರೀ": 0, "ಶ್ರೀಮತಿ": 1, "ಕುಮಾರಿ": 1, "ಡಾ": None}
CASTES = {"NONE", "BC_A", "BC_B", "SC", "ST"}

# Descriptions are the single source for the schema and data dictionary.
FIELDS = [
    ("body", "string", False, "Municipal body; Bengaluru throughout."),
    ("ward_no", "string", False, "Ward identifier on the unchanged 2009 geography."),
    ("prior_year", "int32", False, "Prior election year, 2010."),
    ("year", "int32", False, "Outcome election year, 2015."),
]
for year in (2010, 2015):
    FIELDS.extend(
        [
            (
                f"reserved_woman_{year}",
                "int8",
                False,
                "Women-only seat restriction, read from the reservation cell: 1/0. "
                "2010 winner gazette; 2015 reinstated pre-election notification.",
            ),
            (
                f"reserved_caste_{year}",
                "string",
                False,
                "Seat caste restriction: NONE, BC_A, BC_B, SC, ST. "
                "NONE is an open caste category, not missing.",
            ),
            (
                f"reserved_caste_local_{year}",
                "string",
                False,
                "Kannada caste label; whitespace and hyphenation normalized.",
            ),
            (
                f"reserved_source_path_{year}",
                "string",
                False,
                "Reservation source path relative to this repository.",
            ),
            (
                f"reserved_source_sha256_{year}",
                "string",
                False,
                "SHA-256 of the retained reservation source.",
            ),
            (
                f"reserved_source_page_{year}",
                "int32",
                False,
                "One-based physical PDF page of reservation cell.",
            ),
            (
                f"reserved_woman_opencity_{year}",
                "int8",
                False,
                "Secondary paired-roster women flag, preserved for comparison only.",
            ),
            (
                f"reserved_caste_opencity_{year}",
                "string",
                False,
                "Secondary paired-roster caste category; not canonical assignment.",
            ),
            (
                f"reserved_woman_source_conflict_{year}",
                "bool",
                False,
                "Primary reservation cell and secondary paired-roster flag differ.",
            ),
            (
                f"reserved_caste_source_conflict_{year}",
                "bool",
                False,
                "Primary reservation cell and secondary paired-roster caste differ.",
            ),
        ]
    )
FIELDS.extend(
    [
        (
            "winner_latin_2015",
            "string",
            False,
            "Winner name as printed in the complete OpenCity election return.",
        ),
        ("winner_latin_method_2015", "string", False, "source: printed Latin name."),
        (
            "winner_honorific_raw_2015",
            "string",
            False,
            "Visually reviewed title in the winner gazette; Dr. is not sex-specific.",
        ),
        (
            "winner_woman_from_honorific_2015",
            "int8",
            True,
            "Unadjudicated gazette-title reading: Shri=0, Shrimati/Kumari=1, Dr=null. "
            "Source conflicts remain visible here; use reconciled outcome below.",
        ),
        (
            "winner_woman_opencity_2015",
            "int8",
            False,
            "Explicit election-result Gender column normalized F=1, M=0.",
        ),
        (
            "winner_woman_2015",
            "int8",
            True,
            "Reconciled recorded outcome: explicit Gender corroborated by title, "
            "or explicit Gender with non-sex-specific title. Conflicts are null. "
            "No inference from name or reservation.",
        ),
        (
            "winner_woman_basis_2015",
            "string",
            False,
            "Sources supporting the reconciled outcome or unresolved conflict.",
        ),
        (
            "winner_woman_source_conflict_2015",
            "bool",
            False,
            "Sex-specific gazette title conflicts with explicit secondary Gender.",
        ),
        (
            "winner_source_path_2015",
            "string",
            False,
            "Original winner-gazette path, relative to this repository.",
        ),
        (
            "winner_source_sha256_2015",
            "string",
            False,
            "SHA-256 of the complete retained winner gazette.",
        ),
        (
            "winner_source_page_2015",
            "int32",
            False,
            "One-based physical PDF page of winner title and reservation row.",
        ),
        (
            "reserved_caste_from_results_2015",
            "string",
            False,
            "Caste label printed in winner gazette; may disagree with notification.",
        ),
        (
            "reserved_caste_result_conflict_2015",
            "bool",
            False,
            "2015 winner-gazette caste differs from the pre-election notification.",
        ),
        ("is_eligible", "bool", False, "Later ward is not reserved for women."),
        (
            "has_observed_outcome",
            "bool",
            False,
            "Reconciled outcome is nonmissing, regardless of eligibility.",
        ),
        (
            "boundary_basis",
            "string",
            False,
            "2015 notification references the 15 July 2009 delimitation schedule.",
        ),
    ]
)
SCHEMA = pa.schema(
    [
        pa.field(name, pa.type_for_alias(dtype), nullable=nullable)
        for name, dtype, nullable, _ in FIELDS
    ]
)


def read_csv(path):
    """Read all CSV source cells as strings, retaining empty cells."""
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def sha256(path):
    """Hash retained bytes without modifying them."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def unique_wards(rows, key="ward_no"):
    """Require exactly the 198 source wards, before constructing keyed joins."""
    values = [row[key] for row in rows]
    if len(values) != 198 or set(values) != {str(n) for n in range(1, 199)}:
        raise ValueError("Expected exactly one record for each ward 1–198")
    return {row[key]: row for row in rows}


def source_check(root, rows):
    """Check every source path/hash pair used in human transcriptions."""
    checks = set()
    for row in rows:
        path = Path(row["source"])
        if path.is_absolute() or ".." in path.parts:
            raise ValueError("Source path must be repository-relative")
        checks.add((path.as_posix(), row["source_sha256"]))
    for relative, expected in sorted(checks):
        if sha256(root / relative) != expected:
            raise ValueError(f"Source hash mismatch: {relative}")


def normalized_secondary_assignment(raw):
    """Decode the explicit English reservation label without using outcomes."""
    text = raw.strip()
    woman = int("Women" in text)
    caste = text.replace(" (Women)", "").strip()
    mapping = {
        "General": "NONE",
        "OBC-A": "BC_A",
        "OBC-B": "BC_B",
        "OBC (B)": "BC_B",
        "SC": "SC",
        "ST": "ST",
    }
    if caste not in mapping:
        raise ValueError(f"Unrecognized source reservation: {raw}")
    return woman, mapping[caste]


def reconcile_woman(title, secondary):
    """Preserve each source measurement and null genuinely conflicting outcomes."""
    if title not in HONORIFICS or secondary not in {"F", "M"}:
        raise ValueError("Unrecognized winner title or explicit Gender value")
    title_woman = HONORIFICS[title]
    stated = int(secondary == "F")
    conflict = title_woman is not None and title_woman != stated
    if conflict:
        basis = "unresolved_gazette_title_and_opencity_gender_conflict"
    elif title_woman is None:
        basis = "opencity_explicit_gender; gazette_title_not_sex_specific"
    else:
        basis = "opencity_explicit_gender_and_gazette_honorific_agree"
    return title_woman, stated, None if conflict else stated, conflict, basis


def build_rows(root):
    """Join reviewed reservation and winner cells one-to-one on unchanged ward ID."""
    reservations = read_csv(root / MANUAL / "bbmp_reservations_review.csv")
    winners = read_csv(root / MANUAL / "bbmp_winner_titles_2015.csv")
    corroboration = read_csv(root / MANUAL / "bbmp_winner_title_corroboration.csv")
    source_check(root, reservations + winners + corroboration)
    if len(reservations) != 396 or {r["year"] for r in reservations} != {
        "2010",
        "2015",
    }:
        raise ValueError("Expected both complete reservation years")
    assignment = {
        year: unique_wards([r for r in reservations if r["year"] == str(year)])
        for year in (2010, 2015)
    }
    winner = unique_wards(winners)
    secondary = unique_wards(read_csv(root / OPENCITY), "Ward No")
    secondary_assignment = unique_wards(read_csv(root / PAIR_SOURCE), "Sl No")
    if len(corroboration) != 1 or corroboration[0]["ward_no"] != "132":
        raise ValueError("Unexpected later-title corroboration universe")
    if corroboration[0]["later_name_raw"] != "Shri Dr S Raju":
        raise ValueError("Reviewed ward132 identity changed")
    rows = []
    for ward in sorted(winner, key=int):
        w = winner[ward]
        title, stated, observed, conflict, basis = reconcile_woman(
            w["winner_honorific_raw"], secondary[ward]["Gender"]
        )
        if ward == "132":
            basis += "; matching_2017_18_budget_title_Shri_at_PDF263"
        row = {"body": "Bengaluru", "ward_no": ward, "prior_year": 2010, "year": 2015}
        for year in (2010, 2015):
            a = assignment[year][ward]
            if (
                a["reserved_woman"] not in {"0", "1"}
                or a["reserved_caste"] not in CASTES
            ):
                raise ValueError("Unrecognized primary reservation reading")
            sw, sc = normalized_secondary_assignment(
                secondary_assignment[ward][
                    "2010-15 reservation" if year == 2010 else "Final reservation"
                ]
            )
            row.update(
                {
                    f"reserved_woman_{year}": int(a["reserved_woman"]),
                    f"reserved_caste_{year}": a["reserved_caste"],
                    f"reserved_caste_local_{year}": a["reserved_caste_local"],
                    f"reserved_source_path_{year}": a["source"],
                    f"reserved_source_sha256_{year}": a["source_sha256"],
                    f"reserved_source_page_{year}": int(a["source_pdf_page"]),
                    f"reserved_woman_opencity_{year}": sw,
                    f"reserved_caste_opencity_{year}": sc,
                    f"reserved_woman_source_conflict_{year}": sw
                    != int(a["reserved_woman"]),
                    f"reserved_caste_source_conflict_{year}": sc != a["reserved_caste"],
                }
            )
        if int(w["reserved_woman"]) != row["reserved_woman_2015"]:
            raise ValueError("Notification and result women flags disagree")
        row.update(
            {
                "winner_latin_2015": secondary[ward]["Current corporator Name"],
                "winner_latin_method_2015": "source",
                "winner_honorific_raw_2015": w["winner_honorific_raw"],
                "winner_woman_from_honorific_2015": title,
                "winner_woman_opencity_2015": stated,
                "winner_woman_2015": observed,
                "winner_woman_basis_2015": basis,
                "winner_woman_source_conflict_2015": conflict,
                "winner_source_path_2015": w["source"],
                "winner_source_sha256_2015": w["source_sha256"],
                "winner_source_page_2015": int(w["source_pdf_page"]),
                "reserved_caste_from_results_2015": w["reserved_caste"],
                "reserved_caste_result_conflict_2015": (
                    w["reserved_caste"] != row["reserved_caste_2015"]
                ),
                "is_eligible": row["reserved_woman_2015"] == 0,
                "has_observed_outcome": observed is not None,
                "boundary_basis": (
                    "UDD59MLR2009_2009_07_15; reinstated_2015_notification_PDF2_para3"
                ),
            }
        )
        rows.append(row)
    return rows


def audit_rows(rows):
    """Report coverage, source discrepancies, treatment arms, and support."""
    unique_wards(rows)
    eligible = [r for r in rows if r["is_eligible"]]
    arms = []
    for prior in (0, 1):
        group = [r for r in eligible if r["reserved_woman_2010"] == prior]
        observed = [r for r in group if r["winner_woman_2015"] is not None]
        arms.append(
            {
                "reserved_woman_2010": prior,
                "eligible": len(group),
                "observed": len(observed),
                "women": sum(r["winner_woman_2015"] for r in observed),
                "missing_wards": [
                    r["ward_no"] for r in group if not r["has_observed_outcome"]
                ],
            }
        )
    return {
        "rows": len(rows),
        "eligible": len(eligible),
        "arms": arms,
        "source_title_conflict_wards": [
            r["ward_no"] for r in rows if r["winner_woman_source_conflict_2015"]
        ],
        "non_sex_specific_title_wards": [
            r["ward_no"] for r in rows if r["winner_woman_from_honorific_2015"] is None
        ],
        "result_notification_caste_conflict_wards": [
            r["ward_no"] for r in rows if r["reserved_caste_result_conflict_2015"]
        ],
        "women_reserved_counts": {
            str(y): sum(r[f"reserved_woman_{y}"] for r in rows) for y in (2010, 2015)
        },
        "transitions": {
            f"{a}_to_{b}": sum(
                r["reserved_woman_2010"] == a and r["reserved_woman_2015"] == b
                for r in rows
            )
            for a in (0, 1)
            for b in (0, 1)
        },
        "eligible_prior_caste_support": {
            str(k): v
            for k, v in sorted(
                Counter(
                    (r["reserved_caste_2010"], r["reserved_woman_2010"])
                    for r in eligible
                ).items()
            )
        },
        "interpretation": (
            "Reservation-history comparison; random allocation of women "
            "reservations not established by acquired sources."
        ),
    }


def build(root):
    """Write typed panel, schemas, dictionary, recode ledger, and provenance audit."""
    rows = build_rows(root)
    table = pa.Table.from_pylist(rows, schema=SCHEMA)
    destination = root / OUTPUT
    destination.mkdir(parents=True, exist_ok=True)
    output = destination / f"{NAME}.parquet"
    pq.write_table(table, output, compression="zstd")
    if not pq.read_table(output).equals(table):
        raise ValueError("Parquet round trip changed values or types")
    schema = {
        "name": NAME,
        "primary_key": ["body", "ward_no", "prior_year", "year"],
        "row_unit": "One of 198 unchanged Bengaluru wards; all wards retained.",
        "fields": [
            {"name": n, "type": t, "nullable": null, "description": d}
            for n, t, null, d in FIELDS
        ],
    }
    (destination / f"{NAME}.schema.json").write_text(
        json.dumps(schema, ensure_ascii=False, indent=2) + "\n"
    )
    with (destination / "dictionary.csv").open("w", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["column", "arrow_type", "nullable", "description"])
        writer.writerows(FIELDS)
    ledger = []
    for r in rows:
        for y in (2010, 2015):
            for concept in ("woman", "caste"):
                if r[f"reserved_{concept}_source_conflict_{y}"]:
                    ledger.append(
                        {
                            "ward_no": r["ward_no"],
                            "year": y,
                            "field": f"reserved_{concept}",
                            "source_value": r[f"reserved_{concept}_opencity_{y}"],
                            "selected_value": r[f"reserved_{concept}_{y}"],
                            "rule": (
                                "primary reservation cell over secondary roster; "
                                "source difference retained"
                            ),
                        }
                    )
        if r["reserved_caste_result_conflict_2015"]:
            ledger.append(
                {
                    "ward_no": r["ward_no"],
                    "year": 2015,
                    "field": "reserved_caste",
                    "source_value": r["reserved_caste_from_results_2015"],
                    "selected_value": r["reserved_caste_2015"],
                    "rule": (
                        "pre-election reinstated notification over "
                        "result-gazette caste label"
                    ),
                }
            )
        if r["winner_woman_source_conflict_2015"]:
            ledger.append(
                {
                    "ward_no": r["ward_no"],
                    "year": 2015,
                    "field": "winner_woman",
                    "source_value": (
                        f"gazette={r['winner_woman_from_honorific_2015']};"
                        f"opencity={r['winner_woman_opencity_2015']}"
                    ),
                    "selected_value": None,
                    "rule": "unresolved conflicting source measurements remain missing",
                }
            )
    (destination / "recode_ledger.json").write_text(
        json.dumps(ledger, ensure_ascii=False, indent=2) + "\n"
    )
    sources = {OPENCITY, PAIR_SOURCE}
    sources.update(path.relative_to(root) for path in (root / MANUAL).glob("*.csv"))
    sources.update(
        Path(r[f"reserved_source_path_{y}"]) for r in rows for y in (2010, 2015)
    )
    sources.update(Path(r["winner_source_path_2015"]) for r in rows)
    sources.update(
        BASE / "raw/urban_expansion" / name
        for name in ("bbmp_delimitation_2009.pdf", "bbmp_ward_budget_2017_18.pdf")
    )
    audit = audit_rows(rows)
    audit.update(
        {
            "producer": "python -m local_elections.states.karnataka.urban_panel",
            "inputs": {p.as_posix(): sha256(root / p) for p in sorted(sources)},
            "output_sha256": sha256(output),
            "parquet_round_trip": True,
        }
    )
    (destination / "audit.json").write_text(
        json.dumps(audit, ensure_ascii=False, indent=2) + "\n"
    )
    return audit


@command("process", artifact="urban_panel")
def main():
    """Build relative to a supplied checkout root."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    build(args.root.resolve())


if __name__ == "__main__":
    main()
