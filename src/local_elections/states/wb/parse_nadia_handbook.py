"""Parse Nadia's 2013 complete GP office synopsis and separate ward counts.

Office codes are mutually exclusive printed statuses, including explicit UR.
The ward tables count member seats and do not identify office reservations.
Source serials distinguish repeated GP names; no block is inferred from order.
"""

import collections
import hashlib
import json
import re
import time

import pdfplumber

from local_elections.common.runlog import command
from local_elections.paths import ROOT
from local_elections.states.wb.parse_results import write_table

SOURCE = ROOT / (
    "data/wb/gp_source_search/historical_expansion/"
    "nadia_Panchayat_20General_20Election_20-_20final_20book_election_202013__"
    "cf50563e.pdf"
)
SHA = "238810badd4a39a733192c9c269ae3cea0171701253e159de32ae912c1211c43"
NATIVE = ROOT / f"data/wb/derived/native/{SHA}.json"
OUT = ROOT / "data/wb/derived/nadia_2013_handbook"
OFFICE_AUDIT = OUT / "full_office_visual_audit.json"
MEMBERSHIP_AUDIT = OUT / "membership_visual_audit.json"
MEMBERSHIP_AUDIT_SHA = (
    "228c0381abce0fa14d3f575f105e9c1bca2ccdb31b57677f7f5be6c2dd66a3d4"
)
OFFICE_AUDIT_SHA = "9fa81bb5b3696b27f851ec8c0a9871dbcbd2ced62fde42043a8b56bbd2b97d30"
CODES = {
    "UR": ("UR", 0),
    "Women": ("UR", 1),
    "SC": ("SC", 0),
    "SCW": ("SC", 1),
    "ST": ("ST", 0),
    "STW": ("ST", 1),
    "OBC": ("OBC", 0),
    "OBCW": ("OBC", 1),
}
WARD_FIELDS = [
    "electors_2012",
    "constituencies_2008",
    "seats_2008",
    "single_seated_constituencies_2013",
    "double_seated_constituencies_2013",
    "constituencies_2013",
    "seats_2013",
    "st_nonwomen_seats",
    "sc_nonwomen_seats",
    "obc_nonwomen_seats",
    "st_women_seats",
    "sc_women_seats",
    "obc_women_seats",
    "women_other_seats",
]


def normalized(text):
    return " ".join(text.split())


def source_fields(page, table_index, row_index, bbox, cells):
    key = [SHA, page, table_index, row_index]
    return {
        "row_id": hashlib.sha256(json.dumps(key).encode()).hexdigest()[:20],
        "source_path": str(SOURCE.relative_to(ROOT)),
        "source_sha256": SHA,
        "source_page": page,
        "source_table": table_index,
        "source_table_row": row_index,
        "source_bbox": json.dumps(bbox),
        "source_coordinate_system": "PDF points, top-left origin",
        "raw_cells": json.dumps(cells, ensure_ascii=False),
    }


def office_row(cells, page, provenance):
    values = [normalized(cell) for cell in cells if cell]
    if not values or not values[0].isdigit():
        return None
    serial = int(values[0])
    name = values[1] if len(values) > 1 else None
    marks = values[2:]
    code = marks[0] if len(marks) == 1 and marks[0] in CODES else None
    caste, woman = CODES[code] if code is not None else (None, None)
    flags = ["block_unstated", "name_not_individually_visually_verified"]
    if code is None:
        flags.append("category_blank" if not marks else "category_conflict_or_unknown")
    return {
        **provenance,
        "state": "West Bengal",
        "district": "Nadia",
        "year": 2013,
        "tier": "gp_head" if page <= 62 else "gp_deputy_head",
        "office": "pradhan" if page <= 62 else "upa_pradhan",
        "source_gp_serial": serial,
        "source_gp_key": f"{SHA}:{serial}",
        "gram_panchayat": name,
        "local_body_name": name,
        "block": None,
        "name_raw": next(
            (cell for cell in cells if cell and normalized(cell) == name), None
        ),
        "reservation_code_raw": ";".join(marks),
        "reservation": "W" if code == "Women" else code,
        "caste_reservation": caste,
        "woman_reserved": woman,
        "source_list_scope": "complete_office_synopsis_with_explicit_UR",
        "review_status": "native_extracted_review_stage",
        "quality_flags": ";".join(flags),
    }


def ward_values(values):
    if len(values) > len(WARD_FIELDS):
        return dict.fromkeys(WARD_FIELDS), ["unexpected_number_of_count_cells"]
    values = [*values, *([None] * (len(WARD_FIELDS) - len(values)))]
    parsed = {
        field: int(value) if value and value.isdigit() else None
        for field, value in zip(WARD_FIELDS, values, strict=True)
    }
    flags = []
    if any(value is None for value in parsed.values()):
        flags.append("count_cells_missing_or_unreadable")
    for target, first, second, multiplier in [
        (
            "constituencies_2013",
            "single_seated_constituencies_2013",
            "double_seated_constituencies_2013",
            1,
        ),
        (
            "seats_2013",
            "single_seated_constituencies_2013",
            "double_seated_constituencies_2013",
            2,
        ),
    ]:
        total, first_value, second_value = (
            parsed[target],
            parsed[first],
            parsed[second],
        )
        if (
            total is not None
            and first_value is not None
            and second_value is not None
            and total != first_value + multiplier * second_value
        ):
            flags.append(f"{target}_accounting_mismatch")
    return parsed, flags


def apply_office_visual_audit(offices, audit_path=OFFICE_AUDIT):
    evidence = audit_path.read_bytes()
    if hashlib.sha256(evidence).hexdigest() != OFFICE_AUDIT_SHA:
        raise ValueError("Frozen Nadia office visual audit changed")
    audit = json.loads(evidence)
    source_path = str(SOURCE.relative_to(ROOT))
    if audit["source_sha256"] != SHA or audit["source_path"] != source_path:
        raise ValueError("Nadia office audit source does not match")
    marks = {row["row_id"]: row for row in audit["rows"]}
    row_ids = [row["row_id"] for row in offices]
    if (
        len(marks) != len(audit["rows"])
        or len(set(row_ids)) != len(row_ids)
        or set(row_ids) != set(marks)
    ):
        raise ValueError("Nadia office audit row coverage changed")
    for row in offices:
        mark = marks[row["row_id"]]
        fields = [
            "source_path",
            "source_sha256",
            "source_page",
            "source_table",
            "source_table_row",
            "source_gp_key",
            "tier",
            "office",
        ]
        code = row["reservation_code_raw"] or None
        expected_reservation = (
            "W"
            if mark["verified_category_raw"] == "Women"
            else mark["verified_category_raw"]
        )
        if (
            any(row[field] != mark[field] for field in fields)
            or row["source_sha256"] != SHA
            or row["source_path"] != source_path
            or json.loads(row["source_bbox"]) != mark["source_bbox"]
            or row["source_gp_serial"] != mark["verified_source_gp_serial"]
            or row["gram_panchayat"] != mark["verified_gram_panchayat"]
            or row["local_body_name"] != mark["verified_gram_panchayat"]
            or normalized(row["name_raw"]) != mark["verified_gram_panchayat"]
            or code != mark["verified_category_raw"]
            or row["reservation"] != expected_reservation
            or row["caste_reservation"] != mark["verified_caste_reservation"]
            or row["woman_reserved"] != mark["verified_woman_reserved"]
            or mark["name_ambiguous"]
            or mark["category_ambiguous"]
        ):
            raise ValueError(f"Nadia office audit mismatch for {row['row_id']}")
    for row in offices:
        row["review_status"] = "full_source_visual_review_single_assistant"
        row["quality_flags"] = ";".join(
            flag
            for flag in row["quality_flags"].split(";")
            if flag != "name_not_individually_visually_verified"
        )
        row["visual_review_path"] = str(OFFICE_AUDIT.relative_to(ROOT))
        row["visual_review_sha256"] = OFFICE_AUDIT_SHA
        row["visual_review_method"] = "single_assistant_nonblinded_source_visual_audit"
    return {
        "path": str(OFFICE_AUDIT.relative_to(ROOT)),
        "sha256": OFFICE_AUDIT_SHA,
        "method": audit["method"],
        "summary": audit["summary"],
        "validated_rows": len(offices),
        "status": "all_source_and_row_pins_match",
        "earlier_sample_path": str((OUT / "visual_review.json").relative_to(ROOT)),
        "earlier_sample_role": (
            "Historical development sample; superseded in scope by the full audit."
        ),
    }


def ward_row(cells, page, provenance):
    values = [normalized(cell) for cell in cells if cell is not None]
    assembly_index = next(
        (i for i, cell in enumerate(values[:2]) if re.search(r"\d\d/\s*\d", cell)),
        None,
    )
    if assembly_index is None:
        return None
    name = values[0] if assembly_index == 1 else None
    counts, flags = ward_values(values[assembly_index + 1 :])
    if name is None:
        flags.append("gp_name_not_printed_on_page")
    return {
        **provenance,
        "state": "West Bengal",
        "district": "Nadia",
        "year": 2013,
        "tier": "gp_member_aggregate",
        "gram_panchayat": name,
        "block": None,
        "assembly_parts_raw": values[assembly_index],
        **counts,
        "source_list_scope": "ward_counts_not_office_status",
        "review_status": "native_extracted_review_stage",
        "quality_flags": ";".join(flags),
    }


def compare_counts(rows, controls):
    comparisons = []
    for control in controls:
        field = control["field"]
        values = [row[field] for row in rows]
        observed = sum(value for value in values if value is not None)
        missing = sum(value is None for value in values)
        comparisons.append(
            {
                **control,
                "observed_nonmissing_sum": observed,
                "missing_rows": missing,
                "status": "incomplete"
                if missing
                else "matches"
                if observed == control["printed_value"]
                else "mismatch",
            }
        )
    return comparisons


def parse_membership(audit_path=MEMBERSHIP_AUDIT):
    """Emit each visually checked GP membership occurrence, without aliases.

    Constituency labels are not unique in the source. Page/table/list positions
    identify occurrences; they never supply a missing administrative identifier.
    """
    if hashlib.sha256(SOURCE.read_bytes()).hexdigest() != SHA:
        raise ValueError("Nadia membership source changed")
    evidence = audit_path.read_bytes()
    if hashlib.sha256(evidence).hexdigest() != MEMBERSHIP_AUDIT_SHA:
        raise ValueError("Frozen Nadia membership audit changed")
    audit = json.loads(evidence)
    if audit["source_sha256"] != SHA or audit["source_path"] != str(
        SOURCE.relative_to(ROOT)
    ):
        raise ValueError("Nadia membership audit source mismatch")
    observed = []
    with pdfplumber.open(SOURCE) as pdf:
        for number in range(71, 75):
            for ti, table in enumerate(pdf.pages[number - 1].find_tables()):
                for ri, (cells, geometry) in enumerate(
                    zip(table.extract(), table.rows, strict=True)
                ):
                    if not ri:
                        continue
                    text = cells[2]
                    membership_bbox = geometry.cells[2]
                    if text is None or membership_bbox is None:
                        raise ValueError("Nadia membership source cell is missing")
                    matches = list(re.finditer(r"(?m)^([^\n]+/ZP-(\d+))\n", text))
                    for ci, match in enumerate(matches):
                        end = (
                            matches[ci + 1].start()
                            if ci + 1 < len(matches)
                            else len(text)
                        )
                        observed.append(
                            {
                                "source_path": str(SOURCE.relative_to(ROOT)),
                                "source_sha256": SHA,
                                "source_page": number,
                                "source_table": ti,
                                "source_table_row": ri,
                                "source_constituency_index": ci,
                                "source_bbox": list(geometry.bbox),
                                "source_membership_cell_bbox": list(membership_bbox),
                                "raw_cells": cells,
                                "raw_constituency_text": text[
                                    match.start() : end
                                ].strip(),
                                "verified_block_printed": cells[0],
                                "verified_zp_constituency_raw": match[1],
                                "verified_zp_number_printed": int(match[2]),
                            }
                        )
    marks = audit["constituencies"]
    if len(marks) != len(observed):
        raise ValueError("Nadia membership constituency coverage changed")
    for row, mark in zip(observed, marks, strict=True):
        if any(mark.get(k) != v for k, v in row.items()):
            raise ValueError("Nadia membership source cell or position changed")
        if not mark["verified_gp_names_printed"] or any(
            not n for n in mark["verified_gp_names_printed"]
        ):
            raise ValueError("Nadia membership audit has an empty GP name")
        raw_compact = re.sub(r"\s+", "", mark["raw_constituency_text"])
        if any(
            re.sub(r"\s+", "", name) not in raw_compact
            for name in mark["verified_gp_names_printed"]
        ):
            raise ValueError("Nadia membership name differs from printed source")
    zp_counts = collections.Counter(
        mark["verified_zp_constituency_raw"] for mark in marks
    )
    rows = []
    for mark in marks:
        for i, name in enumerate(mark["verified_gp_names_printed"]):
            key = [
                SHA,
                mark["source_page"],
                mark["source_table"],
                mark["source_table_row"],
                mark["source_constituency_index"],
                i,
            ]
            rows.append(
                {
                    "row_id": hashlib.sha256(json.dumps(key).encode()).hexdigest()[:20],
                    "state": "West Bengal",
                    "district": "Nadia",
                    "year": 2013,
                    "record_kind": "gp_block_membership",
                    "block_printed": mark["verified_block_printed"],
                    "gram_panchayat_printed": name,
                    "zp_constituency_raw": mark["verified_zp_constituency_raw"],
                    "zp_number_printed": mark["verified_zp_number_printed"],
                    "source_gp_list_position": i,
                    **{
                        k: mark[k]
                        for k in [
                            "source_path",
                            "source_sha256",
                            "source_page",
                            "source_table",
                            "source_table_row",
                            "source_constituency_index",
                            "raw_constituency_text",
                        ]
                    },
                    "source_bbox": json.dumps(mark["source_bbox"]),
                    "source_membership_cell_bbox": json.dumps(
                        mark["source_membership_cell_bbox"]
                    ),
                    "source_coordinate_system": "PDF points, top-left origin",
                    "raw_cells": json.dumps(mark["raw_cells"], ensure_ascii=False),
                    "visual_review_path": str(MEMBERSHIP_AUDIT.relative_to(ROOT)),
                    "visual_review_sha256": MEMBERSHIP_AUDIT_SHA,
                    "review_status": "full_source_visual_review_single_assistant",
                    "quality_flags": "duplicated_zp_label_printed"
                    if zp_counts[mark["verified_zp_constituency_raw"]] > 1
                    else "",
                }
            )
    occurrences = collections.Counter(
        (r["block_printed"], r["gram_panchayat_printed"].casefold()) for r in rows
    )
    name_blocks = collections.defaultdict(set)
    for row in rows:
        name_blocks[row["gram_panchayat_printed"].casefold()].add(row["block_printed"])
    for row in rows:
        flags = list(filter(None, row["quality_flags"].split(";")))
        if (
            occurrences[
                (row["block_printed"], row["gram_panchayat_printed"].casefold())
            ]
            > 1
        ):
            flags.append("duplicate_gp_membership_printed_case_insensitive")
        if len(name_blocks[row["gram_panchayat_printed"].casefold()]) > 1:
            flags.append("same_gp_name_printed_in_multiple_blocks")
        row["quality_flags"] = ";".join(flags)
    report = {
        "rows": len(rows),
        "blocks": len({r["block_printed"] for r in rows}),
        "printed_constituency_occurrences": len(marks),
        "distinct_printed_constituency_labels": len(zp_counts),
        "distinct_block_gp_pairs_case_insensitive": len(occurrences),
        "rows_by_page": dict(collections.Counter(r["source_page"] for r in rows)),
        "rows_by_block": dict(collections.Counter(r["block_printed"] for r in rows)),
        "source_anomalies": audit["source_anomalies"],
        "gp_names_in_multiple_blocks": {
            k: sorted(v) for k, v in name_blocks.items() if len(v) > 1
        },
        "visual_review_path": str(MEMBERSHIP_AUDIT.relative_to(ROOT)),
        "visual_review_sha256": MEMBERSHIP_AUDIT_SHA,
        "limitations": [
            "Every printed occurrence is preserved. Repeated labels do not "
            "define unique geographic keys.",
            "Printed names are not canonicalized, expanded, fuzzy matched, "
            "or corrected.",
            "This membership table does not assign block names to office "
            "synopsis serials. Repeated office GP names cannot be resolved "
            "by row order.",
            "The source list omits Haringhata-I and repeats "
            "Ramnagar-Barachupria-II. No missing GP record is manufactured.",
            "This is a single-assistant, nonblinded source visual audit, "
            "not independent double entry.",
        ],
    }
    return rows, report


def parse():
    if hashlib.sha256(SOURCE.read_bytes()).hexdigest() != SHA:
        raise ValueError("Nadia handbook source changed; re-review page scope")
    native = json.loads(NATIVE.read_text())
    pages_by_number = {page["page"]: page for page in native["pages"]}
    if (
        "Reserved for Prodhan" not in pages_by_number[58]["text"]
        or "Reserved for Upa-Prodhan" not in pages_by_number[63]["text"]
    ):
        raise ValueError("Office synopsis headers changed")
    offices, wards, raw_rows, controls, universes = [], [], [], [], []
    with pdfplumber.open(SOURCE) as pdf:
        for number in [17, 48, *range(49, 68)]:
            for table_index, table in enumerate(pdf.pages[number - 1].find_tables()):
                for row_index, (cells, geometry) in enumerate(
                    zip(table.extract(), table.rows, strict=True)
                ):
                    provenance = source_fields(
                        number, table_index, row_index, geometry.bbox, cells
                    )
                    raw_rows.append(
                        {**provenance, "cell_bboxes": json.dumps(geometry.cells)}
                    )
                    if number == 17 and "Gram Panchayat" in cells:
                        printed_universe = cells[-1]
                        if printed_universe is None:
                            raise ValueError("Printed GP universe count is missing")
                        universes.append(
                            {
                                **provenance,
                                "printed_value": int(printed_universe),
                                "unit": "gram_panchayats",
                            }
                        )
                    if 58 <= number <= 67:
                        row = office_row(cells, number, provenance)
                        if row:
                            offices.append(row)
                    if 49 <= number <= 57:
                        row = ward_row(cells, number, provenance)
                        if row:
                            wards.append(row)
                        compact = [normalized(cell) for cell in cells if cell]
                        if compact and compact[0] == "District Total":
                            values, _ = ward_values(compact[1:])
                            controls.extend(
                                {**provenance, "field": field, "printed_value": value}
                                for field, value in values.items()
                                if value is not None
                            )
                    if number == 48 and table_index == 0:
                        compact = [normalized(cell) for cell in cells if cell]
                        if len(compact) == 3 and compact[1] in {
                            "Total no. of GP Constituency",
                            "Total no of GP Seat",
                        }:
                            field = (
                                "constituencies_2013"
                                if compact[1].endswith("Constituency")
                                else "seats_2013"
                            )
                            controls.append(
                                {
                                    **provenance,
                                    "field": field,
                                    "printed_value": int(compact[2]),
                                }
                            )
    if len(universes) != 1:
        raise ValueError("Independent printed GP universe not found")
    office_visual_review = apply_office_visual_audit(offices)
    universe = universes[0]
    office_checks = []
    for tier in ["gp_head", "gp_deputy_head"]:
        rows = [row for row in offices if row["tier"] == tier]
        serials = [row["source_gp_serial"] for row in rows]
        names = collections.Counter(row["gram_panchayat"] for row in rows)
        office_checks.append(
            {
                "tier": tier,
                "rows": len(rows),
                "unique_source_serials": len(set(serials)),
                "source_universe": universe,
                "universe_count_status": "matches"
                if len(rows) == universe["printed_value"]
                else "mismatch",
                "duplicate_serials": [
                    n for n, count in collections.Counter(serials).items() if count > 1
                ],
                "missing_serials": sorted(
                    set(range(1, universe["printed_value"] + 1)) - set(serials)
                ),
                "repeated_names_retained": {
                    name: count for name, count in names.items() if count > 1
                },
                "category_counts": dict(
                    collections.Counter(row["reservation"] or "unknown" for row in rows)
                ),
            }
        )
    page_audit = []
    for page in native["pages"]:
        number = page["page"]
        office_count = sum(row["source_page"] == number for row in offices)
        ward_count = sum(row["source_page"] == number for row in wards)
        page_audit.append(
            {
                "source_path": str(SOURCE.relative_to(ROOT)),
                "source_sha256": SHA,
                "source_page": number,
                "native_reference": f"{NATIVE.relative_to(ROOT)}#page={number}",
                "native_text_characters": len(page["text"]),
                "native_tables": len(page["tables"]),
                "office_rows": office_count,
                "ward_aggregate_rows": ward_count,
                "status": "parsed_office_synopsis"
                if office_count
                else "parsed_ward_aggregates"
                if ward_count
                else "source_control"
                if number in {17, 48}
                else "native_evidence_only_not_semantically_parsed",
            }
        )
    report = {
        "source_sha256": SHA,
        "office_rows": len(offices),
        "ward_aggregate_rows": len(wards),
        "ward_rows_with_names": sum(row["gram_panchayat"] is not None for row in wards),
        "ward_rows_with_missing_counts": sum(
            any(row[field] is None for field in WARD_FIELDS) for row in wards
        ),
        "office_rows_missing_category": sum(
            row["reservation"] is None for row in offices
        ),
        "office_source_checks": office_checks,
        "office_visual_review": office_visual_review,
        "ward_source_checks": compare_counts(wards, controls),
        "ward_accounting_mismatches": sum(
            "accounting_mismatch" in row["quality_flags"] for row in wards
        ),
        "page_status_counts": dict(
            collections.Counter(page["status"] for page in page_audit)
        ),
        "limitations": [
            "All 374 office rows have a pinned full source visual audit of "
            "serial, name and category. This single-assistant, non-blinded "
            "audit is not human double entry or an independent accuracy study; "
            "original native readings remain retained.",
            "Source serial identifies GP within this synopsis; repeated names "
            "are not deduplicated and blocks are unstated.",
            "Head serial123 Taldaha Majdia has a visibly blank category; "
            "both axes remain unknown.",
            "Ward page49 lacks GP names, and seven page50 rows lack rightmost "
            "count columns in the printed layout.",
            "Ward caste and women counts are mutually exclusive categories per "
            "printed page49 header; never office categories.",
            "Pages outside the scoped tables retain native references, "
            "without a claim of semantic completion.",
        ],
    }
    return offices, wards, raw_rows, page_audit, report


@command("parse", state="West Bengal", source="nadia_2013_handbook")
def main():
    started = time.perf_counter()
    offices, wards, raw_rows, pages, report = parse()
    OUT.mkdir(parents=True, exist_ok=True)
    memberships, membership_report = parse_membership()
    report["gp_block_membership"] = membership_report
    for page in pages:
        count = sum(row["source_page"] == page["source_page"] for row in memberships)
        page["gp_block_membership_rows"] = count
        if count:
            page["status"] = "parsed_source_gp_block_membership"
    report["page_status_counts"] = dict(
        collections.Counter(page["status"] for page in pages)
    )
    for name, rows in [
        ("office_reservations", offices),
        ("ward_aggregates", wards),
        ("source_table_rows", raw_rows),
        ("gp_block_membership", memberships),
    ]:
        write_table(rows, OUT / name)
    report["runtime_seconds"] = round(time.perf_counter() - started, 3)
    for name, value in [("page_audit", pages), ("parse_report", report)]:
        (OUT / f"{name}.json").write_text(
            json.dumps(value, ensure_ascii=False, indent=2) + "\n"
        )
    print(
        json.dumps(
            {
                key: report[key]
                for key in [
                    "office_rows",
                    "ward_aggregate_rows",
                    "office_rows_missing_category",
                    "runtime_seconds",
                ]
            }
        )
    )


if __name__ == "__main__":
    main()
