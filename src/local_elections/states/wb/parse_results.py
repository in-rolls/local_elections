"""Parse cached Alipurduar GP result cells into seats and candidates.

Outputs are review-stage Parquet, CSV and JSONL under data/wb/derived/.
No row enters the pooled reservation corpus through this parser. Conflicting
numeric readings stay null; printed winners are retained even when tied.
"""

import argparse
import collections
import csv
import hashlib
import json
import re
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from local_elections.common.runlog import command
from local_elections.paths import ROOT

OUT = ROOT / "data/wb/derived/alipurduar_2018"
BLOCKS = {
    "APD-I": "Alipurduar-I",
    "APD-II": "Alipurduar-II",
    "FALAKATA": "Falakata",
    "KALCHINI": "Kalchini",
    "KUMARGRAM": "Kumargram",
    "MDT": "Madarihat-Birpara",
}
PARTIES = {
    "AITC",
    "BJP",
    "IND",
    "INC",
    "CPI",
    "CPI(M)",
    "RSP",
    "AIFB",
    "BSP",
    "SUCI(C)",
    "CPIM",
    "JMM",
}
RESERVATIONS = {"SC", "SCW", "ST", "STW", "BC", "BCW", "W", "UR"}
DETAIL_PAGES = {
    "APD-I IIA.PDF": (1, 20),
    "APD-II GP IIA.PDF": (1, 15),
    "FALAKATA GP IIA.PDF": (1, 29),
    "KALCHINI GP  IA AND IIA.PDF": (2, 18),
    "KUMAR GP IA AND IIA.PDF": (2, 15),
    "A1B1C1A2B2C2.PDF": (4, 20),
}

OTHER_DETAIL_PAGES = {
    "ps_member": {
        "ANX-IB.PDF": (2, 12),
        "APD-II PS IB AND IIB.PDF": (2, 5),
        "Falakata IIB.PDF": (1, 5),
        "KALCHINI PS IB AND IIB.PDF": (2, 4),
        "KUMAR PS IB AND IIB.PDF": (2, 2),
        "KUMAR PS IB AND IIB PART1.PDF": (1, 2),
        "KUMAR PS IB AND IIB PART2.PDF": (1, 2),
        "KUMAR PS IB AND IIB PART3.PDF": (1, 1),
        "A1B1C1A2B2C2.PDF": (21, 23),
    },
    "zp_member": {
        "ANX-IIC.PDF": (1, 2),
        "APD-II ZP IC AND IIC.PDF": (2, 2),
        "Anex_II_C.PDF": (1, 4),
        "FALAKATA ZP IIC.PDF": (1, 1),
        "KAL ZP IIC.PDF": (1, 1),
        "KALCHINI ZP IC AND IIC.PDF": (2, 2),
        "KUMAR ZP IC AND IIC.PDF": (2, 2),
        "A1B1C1A2B2C2.PDF": (24, 24),
    },
}


def text(value):
    return " ".join(value.split()).strip("|_ ")


def integer(value):
    value = value.strip().strip("|.,() ").replace(",", "")
    return int(value) if re.fullmatch(r"\d+", value) else None


def choose(cell, kind="text"):
    if cell is None:
        return None, ["missing_cell"]
    readings = [cell["original"], cell["clean"]]
    confidences = [cell["original_confidence"], cell["clean_confidence"]]
    if "column_text" in cell:
        readings.append(cell["column_text"])
        confidences.append(cell["column_confidence"])
    if kind == "integer":
        values = [integer(r) for r in readings]
        valid = [v for v in values if v is not None]
        if len(set(valid)) > 1:
            return None, ["readers_disagree"]
        if not valid:
            return None, ["unread_numeric"]
        return valid[0], ["single_reader"] if len(valid) == 1 else []
    readings = [text(r) for r in readings]
    selected = next((i for i in reversed(range(len(readings))) if readings[i]), 0)
    value = readings[selected]
    flags = ["readers_disagree"] if len({r.upper() for r in readings}) > 1 else []
    confidence = confidences[selected]
    if confidence is not None and confidence < 60:
        flags.append("low_ocr_confidence")
    return value, flags


def at(cells, column, y):
    return next(
        (c for c in cells if c["column"] == column and c["bbox"][1] < y < c["bbox"][3]),
        None,
    )


def category(raw):
    value = re.sub(r"[^A-Z]", "", (raw or "").upper())
    value = {
        "WW": "W",
        "GENERAL": "UR",
        "UNRESERVED": "UR",
        "WOMAN": "W",
        "WOMEN": "W",
        "STWOMAN": "STW",
        "STWOMEN": "STW",
        "SCWOMAN": "SCW",
        "SCWOMEN": "SCW",
        "SCHEDULETRIBE": "ST",
        "SCHEDULETRIBEWOMEN": "STW",
        "SCHEDULECASTE": "SC",
        "SCHEDULECASTEWOMEN": "SCW",
        "SCHEDULEDTRIBES": "ST",
        "SCHEDULEDTRIBE": "ST",
        "SCHEDULEDCASTES": "SC",
        "SCHEDULEDCASTE": "SC",
        "SCHEDULEDTRIBESWOMEN": "STW",
        "SCHEDULEDTRIBESWOMAN": "STW",
        "SCHEDULEDCASTESWOMEN": "SCW",
        "SCHEDULEDCASTESWOMAN": "SCW",
    }.get(value, value)
    if value not in RESERVATIONS:
        return None, None, None
    caste = value.removesuffix("W") or "UR"
    return value, caste, int(value.endswith("W"))


def name_key(value):
    return re.sub(r"[^A-Z0-9]", "", (value or "").upper())


def source_row_id(record, box):
    return hashlib.sha256(
        json.dumps([record["source_sha256"], record["source_page"], box]).encode()
    ).hexdigest()[:20]


def seat_number(identity):
    if not identity or integer(identity) is not None:
        return None, None
    numeric = re.search(r"[-/]\s*(\d+)\s*$", identity)
    if numeric:
        return int(numeric[1]), "arabic_suffix"
    roman = re.search(r"/\s*([IVXLCDM]+)\s*$", identity.upper())
    if not roman or not re.fullmatch(
        r"M{0,3}(CM|CD|D?C{0,3})(XC|XL|L?X{0,3})(IX|IV|V?I{0,3})", roman[1]
    ):
        return None, None
    values = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}
    numbers = [values[c] for c in roman[1]]
    total = sum(
        -v if i + 1 < len(numbers) and v < numbers[i + 1] else v
        for i, v in enumerate(numbers)
    )
    return total, "roman_suffix"


def join_seat_fragments(cells, record):
    """Join blank fragments where diagonal scan marks fail the table's row alignment."""
    from local_elections.states.wb.extract_results import cell_text

    bands = sorted((c for c in cells if c["column"] == 2), key=lambda c: c["bbox"][1])
    far_edges = [
        [edge for c in cells if c["column"] == col for edge in c["bbox"][1:4:2]]
        for col in [10, 11]
    ]
    merged = []
    count = 0
    for band in bands:
        if merged:
            previous = merged[-1]
            boundary = band["bbox"][1]
            aligned = any(
                any(abs(edge - boundary) <= 10 for edge in edges) for edges in far_edges
            )
            blank = any(
                not text(cell.get("original", ""))
                and not text(cell.get("column_text", ""))
                and (
                    not text(cell.get("clean", ""))
                    or (cell.get("clean_confidence") or 0) < 30
                )
                for cell in [previous, band]
            )
            if blank and not aligned and abs(previous["bbox"][3] - boundary) <= 8:
                box = [*previous["bbox"][:3], band["bbox"][3]]
                combined = {
                    "column": 2,
                    "bbox": box,
                    "geometry_basis": "aligned_far_columns",
                }
                for source, field, confidence in [
                    ("words_original", "original", "original_confidence"),
                    ("words_clean", "clean", "clean_confidence"),
                    ("words_column", "column_text", "column_confidence"),
                ]:
                    combined[field], combined[confidence] = cell_text(
                        record.get(source, []), box
                    )
                merged[-1] = combined
                count += 1
                continue
        merged.append(band)
    return [c for c in cells if c["column"] != 2] + merged, count


def parse_page(record, tier="gp_member"):
    words = record["words_clean"]
    cells = record["cells"]
    x_edges = list(record["x_edges"])
    column_edges = list(record["column_y_edges"])
    trimmed = 0
    leading_trimmed = 0
    if tier != "gp_member" and len(x_edges) == 14:
        first = " ".join(c["original"] for c in cells if c["column"] == 0)
        if not any(ch.isalnum() for ch in first):
            cells = [{**c, "column": c["column"] - 1} for c in cells if c["column"]]
            x_edges.pop(0)
            column_edges.pop(0)
            leading_trimmed = 1
    # Scanner borders can form cells, but have no table header or body text.
    while len(x_edges) > 11:
        trailing = [c for c in cells if c["column"] == len(column_edges) - 1]
        content = " ".join(c["original"] for c in trailing)
        if any(ch.isalnum() for ch in content):
            break
        column_edges.pop()
        x_edges.pop()
        trimmed += 1
    if trimmed:
        cells = [c for c in cells if c["column"] < len(column_edges)]
    empty_columns = {
        col
        for col, edges in enumerate(column_edges)
        if not edges and x_edges[col + 1] - x_edges[col] < 25
    }
    if empty_columns:
        cells = [
            {
                **c,
                "column": c["column"] - sum(col < c["column"] for col in empty_columns),
            }
            for c in cells
            if c["column"] not in empty_columns
        ]
        x_edges = [x for i, x in enumerate(x_edges) if i not in empty_columns]
        column_edges = [e for i, e in enumerate(column_edges) if i not in empty_columns]
    offset = 0
    if len(x_edges) in {11, 12}:
        headers = [
            re.sub(
                r"[^A-Z]",
                "",
                " ".join(
                    c["original"] + " " + c["clean"] + " " + c.get("column_text", "")
                    for c in cells
                    if c["column"] == col
                ).upper(),
            )
            for col in [0, 1]
        ]
        if (
            len(x_edges) == 11
            and "CONSTITUENC" in headers[0]
            and "RESERVATION" in headers[1]
        ):
            offset = 2
        elif (
            len(x_edges) == 12 and "GRAM" in headers[0] and "CONSTITUENC" in headers[1]
        ):
            offset = 1
        elif tier == "ps_member" and len(x_edges) == 12:
            identities = " ".join(c["original"] for c in cells if c["column"] == 1)
            if re.search(r"/\s*PS\s*-\s*\d", identities, re.IGNORECASE):
                offset = 1
        if offset:
            cells = [{**c, "column": c["column"] + offset} for c in cells]
    mapped_zp = False
    if tier == "zp_member" and len(x_edges) == 12:
        mapping = {0: 0, 1: 2, 2: 3, 3: 7, 4: 4, 5: 5, 6: 6, 7: 8, 8: 9, 9: 10, 10: 11}
        cells = [{**c, "column": mapping[c["column"]]} for c in cells]
        mapped_zp = True
    titles = " ".join(
        w["text"]
        for w in words
        if w["y"] < (record["column_y_edges"][0][0] if record["column_y_edges"] else 0)
    ).upper()
    block = next(
        (BLOCKS[p] for p in Path(record["source_path"]).parts if p in BLOCKS), ""
    )
    audit = {
        "source_path": record["source_path"],
        "source_page": record["source_page"],
        "columns": len(x_edges) - 1,
        "trailing_non_table_columns": trimmed,
        "missing_leading_columns": offset,
        "empty_narrow_columns_removed": len(empty_columns),
        "source_sha256": record["source_sha256"],
        "office_scope": "outside_gp_detail",
        "title": titles,
        "status": "not_gp_detail",
        "seat_rows": 0,
        "candidate_rows": 0,
        "rejected_bands": [],
    }
    scopes = DETAIL_PAGES if tier == "gp_member" else OTHER_DETAIL_PAGES[tier]
    scope = scopes.get(Path(record["source_path"]).name)
    if not scope or not scope[0] <= record["source_page"] <= scope[1]:
        return [], [], audit
    audit["office_scope"] = tier
    if tier != "gp_member":
        audit["zp_columns_remapped"] = mapped_zp
        audit["leading_non_table_columns"] = leading_trimmed
    if not cells:
        audit["status"] = "grid_unresolved"
        return [], [], audit
    if len(x_edges) + offset != 13 and not mapped_zp:
        audit["status"] = "gp_layout_unresolved"
        return [], [], audit
    if tier != "gp_member":
        cells, recovered = recover_identity_bands(cells, record)
        audit["identity_bands_from_reservation_geometry"] = recovered
    cells, joined = join_seat_fragments(cells, record)
    audit["joined_constituency_fragments"] = joined
    seats, candidates = [], []
    for band in [c for c in cells if c["column"] == 2]:
        top, bottom = band["bbox"][1], band["bbox"][3]
        middle = (top + bottom) / 2
        serial_cell = at(cells, 0, middle)
        serial, _ = choose(serial_cell, "integer")
        if serial_cell and (
            abs(serial_cell["bbox"][1] - top) > 8
            or abs(serial_cell["bbox"][3] - bottom) > 8
        ):
            serial = None
        identity, id_flags = choose(band)
        identity_readings = [
            text(band.get(k, "")) for k in ["original", "clean", "column_text"]
        ]
        parsed_numbers = {seat_number(value)[0] for value in identity_readings}
        parsed_numbers.discard(None)
        number, number_basis = seat_number(identity)
        if len(parsed_numbers) > 1:
            number, number_basis = None, None
            id_flags.append("numeric_readers_disagree")
        elif (
            parsed_numbers
            and number is None
            and sum(seat_number(value)[0] is not None for value in identity_readings)
            >= 2
        ):
            number = next(iter(parsed_numbers))
            number_basis = "alternate_reader_suffix"
            id_flags.append("alternate_reader_suffix")
        is_header = any("CONSTITUENC" in value.upper() for value in identity_readings)
        has_identity = not is_header and any(
            re.search(r"[A-Za-z]{3,}.*[/]", value) for value in identity_readings
        )
        if is_header or (number is None and not has_identity):
            if (
                identity not in {"3", ""}
                and "CONSTITUENC" not in (identity or "").upper()
            ):
                audit["rejected_bands"].append(
                    {
                        "bbox": band["bbox"],
                        "serial": serial,
                        "identity": identity,
                        "reason": "constituency_id_unresolved",
                    }
                )
            continue
        flags = ["seat_id:" + f for f in id_flags]
        if number is None:
            flags.append("seat_id:number_unresolved")
        if offset:
            flags.append("layout:missing_leading_columns")
        row = {
            "row_id": source_row_id(record, band["bbox"]),
            "state": "West Bengal",
            "year": 2018,
            "district": "Alipurduar",
            "block": block,
            "tier": tier,
            "serial_printed": serial,
            "seat_id_printed": identity,
            "seat_id_readings": json.dumps(identity_readings, ensure_ascii=False),
            "seat_no": number,
            "seat_no_basis": number_basis,
            "source_path": record["source_path"],
            "source_page": record["source_page"],
            "source_sha256": record["source_sha256"],
            "source_bbox": json.dumps(band["bbox"]),
        }
        for field, col, kind in [
            ("gram_panchayat", 1, "text"),
            ("reservation_raw", 3, "text"),
            ("electors", 4, "integer"),
            ("votes_polled", 5, "integer"),
            ("votes_rejected", 6, "integer"),
            ("winner_name", 10, "text"),
            ("winner_party", 11, "text"),
        ]:
            value, issues = choose_in_band(cells, col, top, bottom, kind)
            row[field] = value
            flags.extend(field + ":" + issue for issue in issues)
        row["gram_panchayat_printed"] = row["gram_panchayat"]
        row["gram_panchayat_basis"] = "gp_column"
        if not row["gram_panchayat"] and "/" in identity:
            row["gram_panchayat"] = identity.split("/", 1)[0].strip()
            row["gram_panchayat_basis"] = "constituency_prefix"
        if not row["gram_panchayat"]:
            flags.append("gram_panchayat:missing")
        row["reservation"], row["caste_reservation"], row["woman_reserved"] = category(
            row["reservation_raw"]
        )
        if row["reservation"] is None:
            flags.append("reservation:unresolved")
        if tier != "gp_member":
            row["geographic_label_raw"] = row["gram_panchayat_printed"]
            row["gram_panchayat"] = None
            row["gram_panchayat_printed"] = None
            row["gram_panchayat_basis"] = f"not_identified_for_{tier}_constituency"
            flags = [flag for flag in flags if not flag.startswith("gram_panchayat:")]
        current = []
        for c in cells:
            if c["column"] != 7:
                continue
            cy = (c["bbox"][1] + c["bbox"][3]) / 2
            if not top < cy < bottom:
                continue
            candidate, issues = choose(c)
            party, party_issues = choose(at(cells, 8, cy))
            votes, vote_issues = choose(at(cells, 9, cy), "integer")
            if not candidate and not party and votes is None:
                continue
            cf = (
                ["name:" + f for f in issues]
                + ["party:" + f for f in party_issues]
                + ["votes:" + f for f in vote_issues]
            )
            party = party.upper() if party else None
            if not candidate:
                cf.append("name:missing")
            if party not in PARTIES:
                cf.append("party:unrecognized")
            current.append(
                {
                    "seat_row_id": row["row_id"],
                    "candidate_row_id": source_row_id(record, c["bbox"]),
                    "candidate_name": candidate,
                    "party": party,
                    "votes": votes,
                    "source_path": record["source_path"],
                    "source_page": record["source_page"],
                    "source_sha256": record["source_sha256"],
                    "source_bbox": json.dumps(c["bbox"]),
                    "quality_flags": ";".join(sorted(set(cf))),
                }
            )
        row["candidate_count"] = len(current)
        observed = [c["votes"] for c in current]
        row["candidate_votes_sum"] = (
            sum(observed) if observed and None not in observed else None
        )
        checks = check_seat(row, current)
        flags.extend(checks)
        if any(c["quality_flags"] for c in current):
            flags.append("candidate_cells:review")
        row["quality_flags"] = ";".join(sorted(set(flags)))
        row["review_status"] = "needs_review" if flags else "automated_checks_passed"
        seats.append(row)
        candidates.extend(current)
    assigned = {c["candidate_row_id"] for c in candidates}
    audit["unassigned_candidate_bands"] = []
    for cell in cells:
        if cell["column"] != 7 or source_row_id(record, cell["bbox"]) in assigned:
            continue
        cy = (cell["bbox"][1] + cell["bbox"][3]) / 2
        party_cell = at(cells, 8, cy)
        party, _ = choose(party_cell)
        if (party or "").upper() not in PARTIES:
            continue
        audit["unassigned_candidate_bands"].append(
            {
                "candidate_row_id": source_row_id(record, cell["bbox"]),
                "candidate_cell": cell,
                "party_cell": party_cell,
                "votes_cell": at(cells, 9, cy),
                "reason": "seat_band_unresolved_or_page_continuation",
            }
        )
    audit["seat_numbers_unresolved"] = sum(r["seat_no"] is None for r in seats)
    audit.update(
        status="parsed" if seats else "gp_rows_unresolved",
        seat_rows=len(seats),
        candidate_rows=len(candidates),
    )
    return seats, candidates, audit


def recover_identity_bands(cells, record):
    """Recover missing PS/ZP identity ruling only from explicit printed identities."""
    from local_elections.states.wb.extract_results import cell_text

    identities = [cell for cell in cells if cell["column"] == 2]
    if not identities:
        return cells, 0
    left, right = identities[0]["bbox"][::2]
    recovered = []
    for reservation in [cell for cell in cells if cell["column"] == 3]:
        top, bottom = reservation["bbox"][1::2]
        if any(
            top < cell["bbox"][3] - 8 and bottom > cell["bbox"][1] + 8
            for cell in identities
        ):
            continue
        box = [left, top, right, bottom]
        cell = {"column": 2, "bbox": box, "geometry_basis": "reservation_column_row"}
        for stream, value, confidence in [
            ("words_original", "original", "original_confidence"),
            ("words_clean", "clean", "clean_confidence"),
            ("words_column", "column_text", "column_confidence"),
        ]:
            cell[value], cell[confidence] = cell_text(record[stream], box)
        if any(
            re.search(r"/\s*(PS|ZP)\s*[-/]\s*\d", cell[key], re.IGNORECASE)
            for key in ["original", "clean", "column_text"]
        ):
            recovered.append(cell)
    return cells + recovered, len(recovered)


def choose_in_band(cells, column, top, bottom, kind):
    """Read the seat field even when the form rules it at candidate-row height."""
    overlapping = [
        c
        for c in cells
        if c["column"] == column
        and top - 10 <= (c["bbox"][1] + c["bbox"][3]) / 2 <= bottom + 10
    ]
    if not overlapping:
        return choose(at(cells, column, (top + bottom) / 2), kind)
    populated = [
        c
        for c in overlapping
        if any(text(c.get(k, "")) for k in ["original", "clean", "column_text"])
    ]
    if not populated:
        return choose(at(cells, column, (top + bottom) / 2), kind)
    readings = [choose(c, kind) for c in populated]
    flags = sorted({flag for _, issues in readings for flag in issues})
    if kind == "integer":
        if "readers_disagree" in flags:
            return None, flags
        values = {value for value, _ in readings if value is not None}
        if len(values) > 1:
            return None, sorted({*flags, "readers_disagree"})
        return next(iter(values), None), flags
    values = [value for value, _ in readings if value]
    if len({v.upper() for v in values}) > 1:
        flags.append("multiple_field_cells")
    return max(values, key=len, default=""), flags


def check_seat(row, candidates):
    failures = []
    polled, rejected, electors = (
        row.get(k) for k in ["votes_polled", "votes_rejected", "electors"]
    )
    total = row.get("candidate_votes_sum")
    if None not in [polled, rejected, total] and total + rejected != polled:
        failures.append("votes:accounting_mismatch")
    if (
        None not in [polled, rejected, electors]
        and not 0 <= rejected <= polled <= electors
    ):
        failures.append("votes:impossible_range")
    winners = [
        c
        for c in candidates
        if name_key(c["candidate_name"]) == name_key(row["winner_name"])
    ]
    if len(winners) != 1:
        failures.append("winner:not_uniquely_matched")
    else:
        winner = winners[0]
        if winner["party"] != (row["winner_party"] or "").upper():
            failures.append("winner:party_mismatch")
        votes = [c["votes"] for c in candidates if c["votes"] is not None]
        if winner["votes"] is not None and votes and winner["votes"] < max(votes):
            failures.append("winner:below_maximum")
    return failures


def write_table(rows, stem):
    if not rows:
        raise ValueError(f"Refusing empty output: {stem}")
    table = pa.Table.from_pylist(rows)
    pq.write_table(table, stem.with_suffix(".parquet"))
    if not pq.read_table(stem.with_suffix(".parquet")).equals(table):
        raise ValueError("Parquet round trip changed values")
    with stem.with_suffix(".jsonl").open("w") as out:
        for row in rows:
            out.write(json.dumps(row, ensure_ascii=False) + "\n")
    with stem.with_suffix(".csv").open("w", newline="") as out:
        writer = csv.DictWriter(out, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def archive_scope(record):
    name, page = Path(record["source_path"]).name, record["source_page"]
    for tier, scopes in [("gp_member", DETAIL_PAGES), *OTHER_DETAIL_PAGES.items()]:
        if name in scopes and scopes[name][0] <= page <= scopes[name][1]:
            return tier, "candidate_detail"
    if name in {"A1B1C1A2B2C2.PDF", "FALAKATA GP PS ZP IA IB AND IC.PDF"}:
        return {1: "gp_member", 2: "ps_member", 3: "zp_member"}[
            page
        ], "consolidated_results"
    if name in {"ANX-IC.PDF", "Anex_I_C.PDF"} or "ZP" in name:
        tier = "zp_member"
    elif name == "ANX-IB.PDF" or "PS" in name or "Rectified IB" in name:
        tier = "ps_member"
    else:
        tier = "gp_member"
    return tier, "consolidated_results"


def parse_consolidated(record, tier):
    """Read counts only under identifiable party headers; retain all other cells."""
    cells = record["cells"]
    parties = PARTIES | {"NCP"}
    headers = []
    for cell in cells:
        readings = [
            text(cell.get(key, "")).upper().strip("|_ .")
            for key in ["original", "clean", "column_text"]
        ]
        matching = {value for value in readings if value in parties}
        if len(matching) == 1:
            headers.append((next(iter(matching)), cell))
    if not headers:
        return [], {
            "status": "summary_cells_only",
            "recognized_party_columns": 0,
            "reason": "party_headers_or_grid_unresolved",
        }
    # Body rows follow the party-name header, not the rotated administrative labels.
    anchor = max(
        headers,
        key=lambda pair: len(
            [
                c
                for c in cells
                if c["column"] == pair[1]["column"]
                and c["bbox"][1] >= pair[1]["bbox"][3] - 8
            ]
        ),
    )[1]
    bands = [
        c
        for c in cells
        if c["column"] == anchor["column"] and c["bbox"][1] >= anchor["bbox"][3] - 8
    ]
    counts = []
    for band in bands:
        top, bottom = band["bbox"][1], band["bbox"][3]
        middle = (top + bottom) / 2
        aligned = [at(cells, col, middle) for col in range(len(record["x_edges"]) - 1)]
        if not any(choose(cell, "integer")[0] is not None for cell in aligned):
            continue
        label_cells = [cell for cell in aligned[:2] if cell]
        row_label = " | ".join(choose(cell)[0] or "" for cell in label_cells)
        for party, header in headers:
            cell = at(cells, header["column"], middle)
            value, flags = choose(cell, "integer")
            if cell is None:
                continue
            counts.append(
                {
                    "row_id": source_row_id(record, cell["bbox"]),
                    "state": "West Bengal",
                    "district": "Alipurduar",
                    "year": 2018,
                    "tier": tier,
                    "record_kind": "consolidated_party_count",
                    "block": next(
                        (
                            BLOCKS[p]
                            for p in Path(record["source_path"]).parts
                            if p in BLOCKS
                        ),
                        None,
                    ),
                    "row_label_raw": row_label,
                    "is_printed_total_row": "TOTAL" in row_label.upper(),
                    "party": party,
                    "declared_elected": value,
                    "source_path": record["source_path"],
                    "source_page": record["source_page"],
                    "source_sha256": record["source_sha256"],
                    "source_bbox": json.dumps(cell["bbox"]),
                    "header_bbox": json.dumps(header["bbox"]),
                    "header_cell_raw": json.dumps(header, ensure_ascii=False),
                    "count_cell_raw": json.dumps(cell, ensure_ascii=False),
                    "review_status": "needs_review",
                    "quality_flags": ";".join(["partial_party_column_mapping", *flags]),
                }
            )
    return counts, {
        "status": "summary_party_counts_partial" if counts else "summary_cells_only",
        "recognized_party_columns": len(headers),
        "party_count_records": len(counts),
        "reason": "Other-party columns and administrative totals retained as raw cells",
    }


def write_archive_extensions(records):
    seats = {tier: [] for tier in OTHER_DETAIL_PAGES}
    candidates = {tier: [] for tier in OTHER_DETAIL_PAGES}
    cells, summaries, audits = [], [], []
    for record in records:
        tier, kind = archive_scope(record)
        if tier == "gp_member" and kind == "candidate_detail":
            continue
        for cell in record["cells"]:
            cells.append(
                {
                    "row_id": source_row_id(record, cell["bbox"]),
                    "source_path": record["source_path"],
                    "source_page": record["source_page"],
                    "source_sha256": record["source_sha256"],
                    "tier": tier,
                    "record_kind": kind,
                    "source_column": cell["column"],
                    "source_bbox": json.dumps(cell["bbox"]),
                    "dpi": record["dpi"],
                    "rotation_clockwise": record["rotation_clockwise"],
                    "deskew_degrees": record["deskew_degrees"],
                    "cell_readings_raw": json.dumps(cell, ensure_ascii=False),
                    "review_status": "source_cells_pending_semantic_review",
                }
            )
        if kind == "candidate_detail":
            ss, cc, audit = parse_page(record, tier)
            for candidate in cc:
                candidate["tier"] = tier
            seats[tier].extend(ss)
            candidates[tier].extend(cc)
        else:
            values, audit = parse_consolidated(record, tier)
            summaries.extend(values)
        audits.append(
            {
                **audit,
                "source_path": record["source_path"],
                "source_sha256": record["source_sha256"],
                "source_page": record["source_page"],
                "tier": tier,
                "record_kind": kind,
                "source_cells": len(record["cells"]),
            }
        )
    for tier in seats:
        stem = tier.removesuffix("_member")
        if seats[tier]:
            write_table(seats[tier], OUT / (stem + "_seats"))
        if candidates[tier]:
            write_table(candidates[tier], OUT / (stem + "_candidates"))
    if summaries:
        write_table(summaries, OUT / "consolidated_party_counts")
    write_table(cells, OUT / "archive_cells")
    (OUT / "archive_page_audit.json").write_text(json.dumps(audits, indent=2) + "\n")
    report = {
        "pages": len(audits),
        "raw_cells": len(cells),
        "seats_by_tier": {tier: len(rows) for tier, rows in seats.items()},
        "candidates_by_tier": {tier: len(rows) for tier, rows in candidates.items()},
        "consolidated_party_count_records": len(summaries),
        "page_status": dict(collections.Counter(a["status"] for a in audits)),
        "limitations": [
            "Review-stage records; duplicate district and block versions "
            "remain source-separated.",
            "Consolidated totals are not named seats; blank counts and "
            "numerical disagreement stay null.",
            "Every detected cell retained, including layouts "
            "without semantic recovery.",
        ],
    }
    (OUT / "archive_parse_report.json").write_text(json.dumps(report, indent=2) + "\n")
    return report


@command("parse", state="West Bengal", source="alipurduar_2018")
def main():
    from local_elections.states.wb.extract_results import SOURCE, VERSION, page_count

    ap = argparse.ArgumentParser()
    ap.add_argument("--cache", type=Path, default=OUT / "ocr")
    args = ap.parse_args()
    seats, candidates, pages, records = [], [], [], []
    expected = {
        (str(path.relative_to(ROOT)), page)
        for path in SOURCE.rglob("*")
        if path.suffix.lower() == ".pdf"
        for page in range(1, page_count(path) + 1)
    }
    observed = set()
    hashes = {}
    for cache in sorted(args.cache.glob("*.json")):
        record = json.loads(cache.read_text())
        if record["version"] != VERSION:
            raise ValueError(f"Stale OCR cache: {cache}; resume extraction first")
        path = record["source_path"]
        if path not in hashes:
            hashes[path] = hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
        if hashes[path] != record["source_sha256"]:
            raise ValueError(f"OCR source changed: {path}")
        key = (path, record["source_page"])
        if key in observed:
            raise ValueError(f"Duplicate source page: {key}")
        observed.add(key)
        records.append(record)
        a, b, c = parse_page(record)
        seats.extend(a)
        candidates.extend(b)
        pages.append(c)
    if expected != observed:
        raise ValueError(
            f"OCR page coverage differs: missing={expected - observed}, "
            f"extra={observed - expected}"
        )
    seats.sort(
        key=lambda r: (
            r["block"],
            r["source_path"],
            r["source_page"],
            r["seat_no"] or 0,
        )
    )
    duplicates = collections.Counter(
        (r["block"], name_key(r["gram_panchayat"]), r["seat_no"])
        for r in seats
        if r["seat_no"] is not None
    )
    for row in seats:
        if row["seat_no"] is not None and (
            duplicates[(row["block"], name_key(row["gram_panchayat"]), row["seat_no"])]
            > 1
        ):
            row["quality_flags"] += ";seat_key:duplicate"
            row["review_status"] = "needs_review"
    write_table(seats, OUT / "gp_seats")
    write_table(candidates, OUT / "gp_candidates")
    (OUT / "page_audit.json").write_text(
        json.dumps(pages, ensure_ascii=False, indent=2) + "\n"
    )
    report = {
        "pages_seen": len(pages),
        "pages_expected": len(expected),
        "gp_detail_pages_expected": sum(b - a + 1 for a, b in DETAIL_PAGES.values()),
        "ocr_version": VERSION,
        "page_status": dict(collections.Counter(r["status"] for r in pages)),
        "seats": len(seats),
        "candidates": len(candidates),
        "unassigned_candidate_bands": sum(
            len(page.get("unassigned_candidate_bands", [])) for page in pages
        ),
        "seat_numbers_unresolved": sum(r["seat_no"] is None for r in seats),
        "by_block": dict(collections.Counter(r["block"] for r in seats)),
        "review_status": dict(collections.Counter(r["review_status"] for r in seats)),
        "flags": dict(
            collections.Counter(
                f for r in seats for f in r["quality_flags"].split(";") if f
            )
        ),
        "quality_claim": (
            "Review-stage extraction; passing automated checks "
            "is not verified accuracy."
        ),
    }
    (OUT / "parse_report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    print(json.dumps(write_archive_extensions(records), indent=2))


if __name__ == "__main__":
    main()
