"""Extract acquired ward schedules without conflating wards and GP offices.

Native Form A schedules retain their printed allocation identifiers and separate
caste/women columns. Scans receive a resumable local OCR attempt on every page;
word boxes and raw text remain evidence, never an automatic unreserved code.
"""

import argparse
import collections
import csv
import hashlib
import io
import json
import os
import re
import subprocess
import tempfile
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from PIL import Image

from local_elections.common.runlog import command
from local_elections.paths import ROOT
from local_elections.states.wb.parse_nadia import number, tidy
from local_elections.states.wb.parse_results import write_table

OUT = ROOT / "data/wb/derived/ward_schedules"
INDEX = ROOT / "data/wb/gp_source_search/manual_entry_index.csv"


def selected(metadata):
    district, year = metadata["district"], metadata["election_year"]
    kind = metadata["content_kind"]
    if (
        district == "South 24 Parganas"
        and "1680-SEC-Gazette_Notification-Delimitation" in metadata.get("file", "")
    ):
        return True
    if district == "Cooch Behar" and year == "2023":
        return kind == "gp_ward_ps_zp_orders"
    if year == "2023":
        return kind in {"gp_ward", "block_member"} or (
            district == "Alipurduar"
            and "publication_of_" in metadata.get("file", "")
            and "delimitation" in metadata.get("file", "")
        )
    if district == "Malda" and year == "2013":
        return True
    if district == "Cooch Behar" and year == "2018":
        return kind == "reservation_or_election_source"
    return (
        district == "Alipurduar"
        and year == "2018"
        and (
            kind == "reservation_orders_mixed_tiers"
            or "CONSTITUENCY" in metadata["file"]
        )
    )


def page_language(digest, page):
    orientation = page_orientation(digest, page)
    if orientation:
        return orientation["ocr_language"]
    evidence = OUT / "language_pilot/verified_page_languages.json"
    if evidence.exists():
        source = json.loads(evidence.read_text()).get(digest, {})
        if page in source.get("pages", []):
            return source["language"]
    return "eng+ben"


def page_orientation(digest, page):
    evidence = OUT / "semantic_review/orientation_audit.json"
    if evidence.exists():
        return next(
            (
                p
                for p in json.loads(evidence.read_text())["pages"]
                if p["source_sha256"] == digest
                and p["source_page"] == page
                and p["review_status"] == "visually_verified_orientation"
            ),
            None,
        )
    return None


def ocr_page(task):
    path, digest, page, *output = task
    language = page_language(digest, page)
    orientation = page_orientation(digest, page)
    rotation = (orientation or {}).get("pre_ocr_rotation_clockwise_degrees", 0)
    directory = (Path(output[0]) if output else OUT) / "ocr" / digest
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / f"{page:04d}.json"
    previous = None
    if target.exists():
        previous = json.loads(target.read_text())
        if (
            previous.get("status") == "extracted"
            and previous.get("language", "eng+ben") == language
            and previous.get("render_rotation_clockwise_degrees", 0) == rotation
            and not any(
                not isinstance(w.get("text"), str)
                or "\n" in (w.get("text") or "")
                or "\t" in (w.get("text") or "")
                for w in previous.get("words", [])
            )
        ):
            return str(target.relative_to(ROOT))
    timeout = 360 if previous and previous.get("status") != "extracted" else 180
    try:
        with tempfile.TemporaryDirectory() as temporary:
            stem = Path(temporary) / "page"
            subprocess.run(
                [
                    "pdftoppm",
                    "-f",
                    str(page),
                    "-l",
                    str(page),
                    "-singlefile",
                    "-scale-to",
                    "2400",
                    "-png",
                    str(ROOT / path),
                    str(stem),
                ],
                check=True,
                capture_output=True,
                timeout=120,
            )
            with Image.open(stem.with_suffix(".png")) as rendered:
                original_size = list(rendered.size)
                if rotation:
                    rotated = rendered.rotate(-rotation, expand=True)
                    rotated.save(stem.with_suffix(".png"))
            process = subprocess.run(
                [
                    "tesseract",
                    str(stem.with_suffix(".png")),
                    "stdout",
                    "-l",
                    language,
                    "--psm",
                    "1",
                    "tsv",
                ],
                check=True,
                capture_output=True,
                text=True,
                timeout=timeout,
                env={**os.environ, "OMP_THREAD_LIMIT": "1"},
            )
            words = list(
                csv.DictReader(
                    io.StringIO(process.stdout), delimiter="\t", quoting=csv.QUOTE_NONE
                )
            )
            record = {
                "source_path": path,
                "source_sha256": digest,
                "source_page": page,
                "method": "tesseract_psm1",
                "language": language,
                "reader_version": 2,
                "tsv_raw": process.stdout,
                "render_scale_to": 2400,
                "render_original_size": original_size,
                "render_rotation_clockwise_degrees": rotation,
                "orientation_evidence": orientation,
                "ocr_timeout_seconds": timeout,
                "status": "extracted",
                "words": words,
                "stderr": process.stderr,
            }
    except (subprocess.SubprocessError, OSError) as exc:
        record = {
            "source_path": path,
            "source_sha256": digest,
            "source_page": page,
            "status": "extraction_failed",
            "error": str(exc),
        }
    if previous is not None:
        record["previous_attempts"] = [
            *previous.get("previous_attempts", []),
            {k: v for k, v in previous.items() if k != "previous_attempts"},
        ]
    temporary = target.with_suffix(f".{os.getpid()}.tmp")
    temporary.write_text(json.dumps(record, ensure_ascii=False) + "\n")
    temporary.replace(target)
    return str(target.relative_to(ROOT))


def allocation(raw):
    match = re.fullmatch(r"(?:.*?[/])?[IVXLCDM]+\s*[-–]\s*(\d+)", tidy(raw), re.I)
    if match:
        return int(match[1])
    return int(tidy(raw)) if re.fullmatch(r"\d+", tidy(raw)) else None


def category(raw, seat, women=False):
    compact = re.sub(r"[\s.()\[\]]", "", raw or "").upper()
    if compact in {"", "-", "--", "NIL"}:
        return (0 if women else "UR"), None
    compact = re.sub(r"^.*?/[IVXLCDM]+-", "", compact)
    compact = compact.replace("-", "").replace("WOMEN", "W").replace("WOMAN", "W")
    match = re.fullmatch(r"(\d*)(SC|ST|BC|OBC|UR)?(W)?", compact)
    if not match or (match[1] and int(match[1]) != seat):
        return None, "reservation_cell_unread"
    if women:
        return (1, None) if match[3] else (None, "women_marker_missing")
    return (match[2], None) if match[2] else (None, "caste_marker_missing")


def parse_native(record, metadata, path):
    rows, audits, summaries = [], [], {}
    gp = block = None
    for page in record["pages"]:
        match = re.search(r"Block\s*[:–-]+\s*([^\n]+)", page["text"], re.I)
        if match:
            block = tidy(match[1])
        page_rows = []
        for ti, table in enumerate(page["tables"], 1):
            header = " ".join(tidy(c) for row in table["rows"][:8] for c in row)
            if not re.search(r"Gram\s+Panchay[ae]t", header, re.I):
                continue
            column_row = next(
                (
                    r
                    for r in table["rows"][:8]
                    if any(
                        tidy(c).replace(" ", "") in {"2(a)", "2a", "(2a)"} for c in r
                    )
                ),
                None,
            )
            if column_row is None:
                continue
            columns = {
                tidy((c or "").split("\n")[-1]).strip("()"): i
                for i, c in enumerate(column_row)
                if tidy((c or "").split("\n")[-1]).strip("()") in {"4", "5", "6"}
            }
            if set(columns) != {"4", "5", "6"}:
                continue
            for ri, raw in enumerate(table["rows"], 1):
                if len(raw) not in {12, 13, 14}:
                    continue
                identity = tidy(raw[6])
                identity_match = re.fullmatch(
                    r"(.+?)\s*/\s*([IVXLCDM]+)(?:\s*-\s*\d+)?", identity, re.I
                )
                if not identity_match:
                    continue
                gp = tidy(identity_match[1])
                allocated_raw = raw[columns["4"]]
                caste_parts = raw[columns["5"] : columns["6"]]
                caste_raw = (
                    caste_parts[0]
                    if len(caste_parts) == 1
                    else " ".join(tidy(c) for c in caste_parts)
                )
                women_raw = raw[columns["6"]]
                seat = allocation(allocated_raw)
                if raw[1] and any(number(c) is not None for c in raw[1:6]):
                    summaries.setdefault(gp, []).append(
                        {
                            "page": page["page"],
                            "raw": raw[1:6],
                            "values": [number(c) for c in raw[1:6]],
                        }
                    )
                flags = []
                if seat is None:
                    flags.append("allocation_unread")
                # None marks a merged continuation cell; a printed blank is ''.
                if (
                    caste_raw is None
                    and women_raw is None
                    and any(
                        r["gram_panchayat"] == gp and r["seat_no"] == seat
                        for r in page_rows
                    )
                ):
                    continue
                caste, cf = category(caste_raw, seat)
                woman, wf = category(women_raw, seat, women=True)
                if cf or wf:
                    flags.extend(filter(None, [cf, wf]))
                if caste_raw is None or women_raw is None:
                    flags.append("merged_reservation_cell_unresolved")
                    caste = None if caste_raw is None else caste
                    woman = None if women_raw is None else woman
                row = {
                    "row_id": hashlib.sha256(
                        json.dumps([record["sha256"], page["page"], ti, ri]).encode()
                    ).hexdigest()[:20],
                    "state": "West Bengal",
                    "district": metadata["district"],
                    "year": int(metadata["election_year"]),
                    "stage": metadata["stage"],
                    "record_kind": "gp_ward_reservation",
                    "block_printed": block,
                    "gram_panchayat": gp,
                    "constituency_area_raw": identity,
                    "seat_no": seat,
                    "allocated_raw": allocated_raw,
                    "caste_raw": caste_raw,
                    "women_raw": women_raw,
                    "caste_reservation": caste,
                    "woman_reserved": woman,
                    "raw_cells": json.dumps(raw, ensure_ascii=False),
                    "source_path": path,
                    "source_sha256": record["sha256"],
                    "source_page": page["page"],
                    "source_table": ti,
                    "source_row": ri,
                    "source_table_bbox": json.dumps(table["bbox"]),
                    "bbox_coordinate_system": "pdf_points_top_left",
                    "bbox_rotation_degrees": 0,
                    "quality_flags": ";".join(flags),
                    "review_status": "needs_review"
                    if flags
                    else "native_fields_parsed",
                }
                page_rows.append(row)
        rows.extend(page_rows)
        audits.append(
            {
                "source_path": path,
                "source_sha256": record["sha256"],
                "source_page": page["page"],
                "district": metadata["district"],
                "year": metadata["election_year"],
                "stage": metadata["stage"],
                "source_page_bbox": [0, 0, page["width"], page["height"]],
                "status": "native_rows_parsed"
                if page_rows
                else "semantic_review_required",
                "rows": len(page_rows),
                "raw_text": page["text"],
                "native_cache": f"data/wb/derived/native/{record['sha256']}.json",
            }
        )
    for gp in {r["gram_panchayat"] for r in rows}:
        subset = [r for r in rows if r["gram_panchayat"] == gp]
        totals = summaries.get(gp, [])
        flags = []
        if not totals or any(v is None for t in totals for v in t["values"]):
            flags.append("printed_totals_unread")
        elif len({tuple(t["values"]) for t in totals}) != 1:
            flags.append("printed_totals_conflict")
        else:
            total, sc, st, bc, women = totals[0]["values"]
            seats = [r["seat_no"] for r in subset]
            if set(seats) != set(range(1, total + 1)) or len(seats) != total:
                flags.append("seat_universe_mismatch")
            actual = [
                sum(r["caste_reservation"] == c for r in subset)
                for c in ["SC", "ST", "BC"]
            ]
            actual.append(sum(r["woman_reserved"] == 1 for r in subset))
            if actual != [sc, st, bc, women]:
                flags.append("reservation_totals_mismatch")
        counts = collections.Counter(
            r["seat_no"] for r in subset if r["seat_no"] is not None
        )
        for row in subset:
            combined = [*filter(None, row["quality_flags"].split(";")), *flags]
            if counts[row["seat_no"]] > 1:
                combined.append("duplicate_seat_key")
            row["quality_flags"] = ";".join(sorted(set(combined)))
            row["printed_totals_raw"] = json.dumps(totals, ensure_ascii=False)
            row["review_status"] = (
                "needs_review" if combined else "source_controls_passed"
            )
    return rows, audits


def parse_other_tiers(record, metadata, path):
    """Read native PS/ZP constituencies as separate electoral units."""
    result = []
    for page in record["pages"]:
        for ti, table in enumerate(page["tables"], 1):
            header = " ".join(tidy(c) for r in table["rows"][:5] for c in r)
            if re.search(r"Panchayat\s+Samit[yi]", header, re.I):
                marker, kind = "PS", "block_ward_reservation"
            elif re.search(r"Zilla\s+Parishad", header, re.I):
                marker, kind = "ZP", "district_ward_reservation"
            else:
                continue
            groups, current = [], None
            for ri, raw in enumerate(table["rows"], 1):
                if len(raw) < 5:
                    continue
                match = re.match(
                    r"(.+?)/\s*" + marker + r"\s*[-–]\s*(\d+|[IVXLCDM]+)(?:\b|$)",
                    tidy(raw[2]),
                    re.I,
                )
                if match:
                    current = {
                        "identity": tidy(raw[2]),
                        "name": tidy(match[1]),
                        "seat": match[2],
                        "rows": [],
                        "row": ri,
                    }
                    groups.append(current)
                if current:
                    current["rows"].append(raw)
            for group in groups:
                number_raw = group["seat"]
                seat = int(number_raw) if number_raw.isdigit() else None
                cells = group["rows"]
                castes = list(dict.fromkeys(r[-2] for r in cells if r[-2] is not None))
                women = list(dict.fromkeys(r[-1] for r in cells if r[-1] is not None))
                flags = []
                caste_raw = castes[0] if len(castes) == 1 else None
                women_raw = women[0] if len(women) == 1 else None
                caste, cf = category(caste_raw, seat)
                woman, wf = category(women_raw, seat, women=True)
                if caste_raw is None:
                    caste, cf = None, "caste_cell_missing_or_conflicting"
                if women_raw is None:
                    woman, wf = None, "women_cell_missing_or_conflicting"
                flags.extend(filter(None, [cf, wf]))
                if seat is None:
                    flags.append("roman_constituency_number_preserved")
                result.append(
                    {
                        "row_id": hashlib.sha256(
                            json.dumps(
                                [
                                    record["sha256"],
                                    page["page"],
                                    ti,
                                    group["row"],
                                    marker,
                                ]
                            ).encode()
                        ).hexdigest()[:20],
                        "state": "West Bengal",
                        "district": metadata["district"],
                        "year": int(metadata["election_year"]),
                        "stage": metadata["stage"],
                        "record_kind": kind,
                        "local_body_printed": group["name"],
                        "constituency_area_raw": group["identity"],
                        "seat_no": seat,
                        "seat_no_raw": number_raw,
                        "caste_raw": caste_raw,
                        "women_raw": women_raw,
                        "caste_reservation": caste,
                        "woman_reserved": woman,
                        "source_path": path,
                        "source_sha256": record["sha256"],
                        "source_page": page["page"],
                        "source_table": ti,
                        "source_row": group["row"],
                        "source_table_bbox": json.dumps(table["bbox"]),
                        "raw_cells": json.dumps(cells, ensure_ascii=False),
                        "quality_flags": ";".join(flags),
                        "review_status": "needs_review"
                        if flags
                        else "native_fields_parsed",
                    }
                )
    return result


def parse_constituency_crosswalk(record, path):
    """Keep polling/GP/PS/ZP links without assigning any reservation category."""
    result = []
    for page in record["pages"]:
        for ti, table in enumerate(page["tables"], 1):
            for ri, raw in enumerate(table["rows"], 1):
                if len(raw) not in {6, 7}:
                    continue
                cells = raw[-6:]
                match = re.fullmatch(r"(.+?)/([IVXLCDM]+)", tidy(cells[2]), re.I)
                if not match:
                    continue
                seat = number(cells[3])
                flags = [] if seat is not None else ["seat_cell_missing_or_merged"]
                if any(re.search(r"\b(?:([A-Za-z])\1){4,}\b", c or "") for c in cells):
                    flags.append("duplicated_native_glyphs")
                result.append(
                    {
                        "state": "West Bengal",
                        "district": "Alipurduar",
                        "year": 2018,
                        "record_kind": "constituency_crosswalk",
                        "gram_panchayat": match[1],
                        "gp_constituency_raw": cells[2],
                        "seat_no": seat,
                        "assembly_part_raw": cells[0],
                        "polling_station_raw": cells[1],
                        "ps_constituency_raw": cells[4],
                        "zp_constituency_raw": cells[5],
                        "source_path": path,
                        "source_sha256": record["sha256"],
                        "source_page": page["page"],
                        "source_table": ti,
                        "source_row": ri,
                        "source_table_bbox": json.dumps(table["bbox"]),
                        "raw_cells": json.dumps(raw, ensure_ascii=False),
                        "quality_flags": ";".join(flags),
                        "review_status": "needs_review"
                        if flags
                        else "native_fields_parsed",
                    }
                )
    return result


def ocr_schedule_type(ocr):
    """Infer table unit from explicit form/header text, then source filename."""
    raw = " ".join(w["text"] for w in ocr.get("words", []) if w.get("text"))
    if re.search(r"FORM\s*[-:\[.]*\s*B(?:[1Il])?\b", raw, re.I):
        return "ps_form_b"
    if re.search(r"FORM\s*[-:\[.]*\s*A(?:[1Il])?\b", raw, re.I):
        return "gp_form_a"
    compact = re.sub(r"\s+", " ", raw)
    if re.search(r"members.{0,120}elected.{0,60}Panchayat\s+Samit[yi]", compact, re.I):
        return "ps_form_b"
    if re.search(r"members.{0,100}elected.{0,60}Gram\s+Panchayat", compact, re.I):
        return "gp_form_a"
    filename = ocr.get("source_path", "").rsplit("/", 1)[-1]
    if re.search(r"(?:form|from)[_ .-]*b", filename, re.I):
        return "ps_form_b"
    if re.search(r"(?:form|from)[_ .-]*a", filename, re.I):
        return "gp_form_a"
    if re.search(r"Zilla\s+Parishad.{0,80}constituenc", compact, re.I):
        return "zp_member_schedule"
    if re.search(r"/P\.?S\.?\s*[-–]\s*\d", raw, re.I):
        return "ps_form_b"
    if re.search(r"[A-Za-z]/[IVXLCDM]+[-–]\d", raw, re.I):
        return "gp_form_a"
    return "unclassified_schedule"


def ocr_column_labels(ocr, words):
    return {
        key: [
            w
            for w in words
            if w["text"].strip("().[]") == key
            and (w["text"] == key or "(" in w["text"] or "[" in w["text"])
        ]
        for key in ["4", "5", "6"]
    }


def schedule_header_triples(ocr, words):
    headers = ocr_column_labels(ocr, words)
    width = max((int(w["left"]) + int(w["width"]) for w in words), default=0)
    return [
        (a, b, c)
        for a in headers["4"]
        for b in headers["5"]
        for c in headers["6"]
        if int(a["left"]) < int(b["left"]) < int(c["left"])
        and (
            all("(" in v["text"] or "[" in v["text"] for v in [a, b, c])
            or (int(a["left"]) > width * 0.4 and int(c["left"]) > width * 0.7)
        )
        and max(int(v["top"]) for v in [a, b, c])
        - min(int(v["top"]) for v in [a, b, c])
        < 25
    ]


def rotate_word_boxes(words, rotation, width, height):
    result = []
    for word in words:
        x, y, w, h = [int(word[k]) for k in ["left", "top", "width", "height"]]
        if rotation == 90:
            xx, yy, ww, hh = height - y - h, x, h, w
        elif rotation == 180:
            xx, yy, ww, hh = width - x - w, height - y - h, w, h
        elif rotation == 270:
            xx, yy, ww, hh = y, width - x - w, h, w
        else:
            xx, yy, ww, hh = x, y, w, h
        result.append(
            {
                **word,
                "left": str(xx),
                "top": str(yy),
                "width": str(ww),
                "height": str(hh),
                "original_bbox": [x, y, x + w, y + h],
            }
        )
    return result


def orient_ocr_words(ocr):
    """Use unique printed column labels; do not infer missing numerical labels."""
    words = [w for w in ocr.get("words", []) if w.get("text", "").strip()]
    width = max((int(w["left"]) + int(w["width"]) for w in words), default=0)
    height = max((int(w["top"]) + int(w["height"]) for w in words), default=0)
    options = []
    for rotation in [0, 90, 180, 270]:
        oriented = rotate_word_boxes(words, rotation, width, height)
        if len(schedule_header_triples(ocr, oriented)) == 1:
            options.append((oriented, rotation))
    return options[0] if len(options) == 1 else (words, None)


def parse_ocr(ocr, metadata):
    """Retain only explicit named constituency/seat anchors and printed codes.

    OCR is a candidate reading. Even a clean category requires review; blank
    scans cannot establish an unreserved designation. Header word coordinates
    identify the caste and women columns independently of the body text.
    """
    if ocr_schedule_type(ocr) in {"ps_form_b", "zp_member_schedule"}:
        return []
    words, rotation = orient_ocr_words(ocr)
    triples = schedule_header_triples(ocr, words)
    if len(triples) != 1:
        return parse_ocr_gp_explicit(ocr, metadata)
    a, b, c = triples[0]
    centers = [int(v["left"]) + int(v["width"]) / 2 for v in [a, b, c]]
    caste_start, women_start = (
        (centers[0] + centers[1]) / 2,
        (centers[1] + centers[2]) / 2,
    )
    anchors = []
    for word in words:
        match = re.fullmatch(
            r"([A-Za-z][A-Za-z.-]*)/([IVXLCDM]+)-(\d+)",
            word["text"].strip("(),\\‘’'"),
            re.I,
        )
        if (
            match
            and int(word["top"]) > int(a["top"])
            and int(word["left"]) < centers[0]
        ):
            anchors.append((word, match[1], int(match[3]), word))
    allocations = []
    names = []
    for word in words:
        if int(word["top"]) <= int(a["top"]):
            continue
        xmid = int(word["left"]) + int(word["width"]) / 2
        match = re.fullmatch(r"([IVXLCDM]+)-(\d+)", word["text"], re.I)
        if match and centers[0] - 50 < xmid < caste_start:
            allocations.append((word, match))
        match = re.fullmatch(
            r"([A-Za-z][A-Za-z.-]*)/([IVXLCDM]+)",
            word["text"].strip("(),\\‘’'"),
            re.I,
        )
        if (
            match
            and xmid < centers[0] - 50
            and not re.fullmatch(r"[IVXLCDM]+", match[1], re.I)
        ):
            names.append((word, match))
    allocations.sort(key=lambda pair: int(pair[0]["top"]))
    for i, (word, allocation_match) in enumerate(allocations):
        y = int(word["top"]) + int(word["height"]) / 2
        previous = int(allocations[i - 1][0]["top"]) if i else int(a["top"])
        following = (
            int(allocations[i + 1][0]["top"]) if i + 1 < len(allocations) else y + 60
        )
        matches = [
            (name_word, name_match)
            for name_word, name_match in names
            if name_match[2].upper() == allocation_match[1].upper()
            and (previous + y) / 2
            <= int(name_word["top"]) + int(name_word["height"]) / 2
            < (following + y) / 2
        ]
        if len(matches) == 1:
            name_word, name_match = matches[0]
            seat = int(allocation_match[2])
            if not any(anchor[1:3] == (name_match[1], seat) for anchor in anchors):
                anchors.append((word, name_match[1], seat, name_word))
    anchors.sort(key=lambda item: int(item[0]["top"]))
    result = []
    for i, (word, gp_name, seat, name_word) in enumerate(anchors):
        y = int(word["top"]) + int(word["height"]) / 2
        previous = int(anchors[i - 1][0]["top"]) if i else int(a["top"])
        following = int(anchors[i + 1][0]["top"]) if i + 1 < len(anchors) else y + 40
        top, bottom = max(previous + 10, y - 20), min(following - 5, y + 30)
        caste_words, women_words = [], []
        for candidate in words:
            xmid = int(candidate["left"]) + int(candidate["width"]) / 2
            ymid = int(candidate["top"]) + int(candidate["height"]) / 2
            if top <= ymid <= bottom:
                if caste_start <= xmid < women_start:
                    caste_words.append(candidate)
                elif xmid >= women_start:
                    women_words.append(candidate)
        caste_raw = " ".join(w["text"] for w in caste_words)
        women_raw = " ".join(w["text"] for w in women_words)
        caste, cf = category(caste_raw, seat)
        woman, wf = category(women_raw, seat, women=True)
        if not re.search(r"SC|ST|BC|UR", re.sub(r"[ .]", "", caste_raw).upper()):
            caste, cf = None, "scanned_caste_unread_or_blank"
        if not re.search(r"W", women_raw, re.I):
            woman, wf = None, "scanned_women_unread_or_blank"
        box = [
            min(int(word["left"]), int(name_word["left"])),
            min(top, int(name_word["top"])),
            max(
                int(w["left"]) + int(w["width"])
                for w in [word, *caste_words, *women_words]
            ),
            bottom,
        ]
        flags = ["ocr_not_independently_verified", *filter(None, [cf, wf])]
        if name_word is not word:
            flags.append("separate_printed_name_and_allocation_joined")
        result.append(
            {
                "row_id": hashlib.sha256(
                    json.dumps(
                        [ocr["source_sha256"], ocr["source_page"], "ocr", i, word]
                    ).encode()
                ).hexdigest()[:20],
                "state": "West Bengal",
                "district": metadata["district"],
                "year": int(metadata["year"]),
                "stage": metadata["stage"],
                "record_kind": "gp_ward_reservation",
                "block_printed": None,
                "gram_panchayat": gp_name,
                "constituency_area_raw": name_word["text"],
                "seat_no": seat,
                "allocated_raw": word["text"],
                "caste_raw": caste_raw,
                "women_raw": women_raw,
                "caste_reservation": caste,
                "woman_reserved": woman,
                "raw_cells": json.dumps(
                    [word, caste_words, women_words, name_word], ensure_ascii=False
                ),
                "source_path": ocr["source_path"],
                "source_sha256": ocr["source_sha256"],
                "source_page": ocr["source_page"],
                "source_table": None,
                "source_row": i + 1,
                "source_table_bbox": json.dumps(box),
                "bbox_coordinate_system": "oriented_rendered_image_pixels",
                "bbox_rotation_degrees": rotation,
                "render_rotation_clockwise_degrees": ocr.get(
                    "render_rotation_clockwise_degrees", 0
                ),
                "printed_totals_raw": None,
                "quality_flags": ";".join(flags),
                "review_status": "needs_review",
            }
        )
    return result


def parse_ocr_gp_explicit(ocr, metadata):
    """Retain explicit name/seat codes when damaged headers prevent geometry.

    The Roman token remains evidence, never an inferred seat number. A bare
    reservation code is joined only to a unique printed GP name for that number
    on the page. Headerless scans never establish an unreserved designation.
    """
    if ocr_schedule_type(ocr) != "gp_form_a":
        return []
    words = [w for w in ocr.get("words", []) if w.get("text", "").strip()]
    identities = collections.defaultdict(list)
    codes = collections.defaultdict(list)
    pattern = re.compile(
        r"([A-Za-z][A-Za-z.-]*)/([IVXLCDM]+)[-–](\d+)"
        r"(?:\((SC|ST|BC|OBC|UR)?(W)?\))?",
        re.I,
    )
    for word in words:
        raw = word["text"].strip(" ,|\\‘’'")
        match = pattern.fullmatch(raw)
        if match and not re.fullmatch(r"[IVXLCDM]+", match[1], re.I):
            seat = int(match[3])
            identities[seat].append((word, match[1]))
            if match[4] or match[5]:
                codes[seat].append((word, (match[4] or "").upper(), bool(match[5])))
        else:
            match = re.fullmatch(r"(\d+)[-–](SC|ST|BC|OBC|UR)?(W|Women)?", raw, re.I)
            if match and (match[2] or match[3]):
                codes[int(match[1])].append(
                    (word, (match[2] or "").upper(), bool(match[3]))
                )
    rows = []
    page_names = {
        name.upper() for entries in identities.values() for _, name in entries
    }
    for seat, entries in identities.items():
        names = {name.upper() for _, name in entries}
        unique_name = len(names) == 1
        matched_codes = [
            code
            for code in codes[seat]
            if len(page_names) == 1 or code[0] in [word for word, _ in entries]
        ]
        castes = {c for _, c, _ in matched_codes if c} if unique_name else set()
        female = unique_name and any(w for _, _, w in matched_codes)
        evidence = [w for w, _ in entries] + [w for w, _, _ in codes[seat]]
        flags = [
            "ocr_not_independently_verified",
            "explicit_gp_identifiers_header_unread",
        ]
        if not unique_name:
            flags.append("conflicting_gp_names_for_same_printed_seat")
        if len(matched_codes) < len(codes[seat]):
            flags.append("multiple_gp_names_on_page_bare_codes_withheld")
        if len(castes) != 1:
            flags.append("caste_missing_or_conflicting")
        if not female:
            flags.append("scanned_women_unread_or_blank")
        box = [
            min(int(w["left"]) for w in evidence),
            min(int(w["top"]) for w in evidence),
            max(int(w["left"]) + int(w["width"]) for w in evidence),
            max(int(w["top"]) + int(w["height"]) for w in evidence),
        ]
        rows.append(
            {
                "row_id": hashlib.sha256(
                    json.dumps(
                        [
                            ocr["source_sha256"],
                            ocr["source_page"],
                            "ocr_gp_explicit",
                            seat,
                        ]
                    ).encode()
                ).hexdigest()[:20],
                "state": "West Bengal",
                "district": metadata["district"],
                "year": int(metadata["year"]),
                "stage": metadata["stage"],
                "record_kind": "gp_ward_reservation",
                "block_printed": None,
                "gram_panchayat": entries[0][1] if unique_name else None,
                "constituency_area_raw": " | ".join(
                    dict.fromkeys(w["text"] for w, _ in entries)
                ),
                "seat_no": seat,
                "allocated_raw": entries[0][0]["text"],
                "caste_raw": " ".join(w["text"] for w, c, _ in codes[seat] if c),
                "women_raw": " ".join(w["text"] for w, _, f in codes[seat] if f),
                "caste_reservation": next(iter(castes)) if len(castes) == 1 else None,
                "woman_reserved": 1 if female else None,
                "raw_cells": json.dumps(evidence, ensure_ascii=False),
                "source_path": ocr["source_path"],
                "source_sha256": ocr["source_sha256"],
                "source_page": ocr["source_page"],
                "source_table": None,
                "source_row": len(rows) + 1,
                "source_table_bbox": json.dumps(box),
                "bbox_coordinate_system": "rendered_image_pixels",
                "render_rotation_clockwise_degrees": ocr.get(
                    "render_rotation_clockwise_degrees", 0
                ),
                "quality_flags": ";".join(flags),
                "review_status": "needs_review",
            }
        )
    return rows


def parse_ocr_ps(ocr, metadata):
    """Read explicit PS identities/codes, including headerless continuations.

    A bare code is used only when its printed number matches a named PS
    constituency on that page. Neither blank cells nor GP area listings
    establish a PS reservation. Conflicting names and codes remain unresolved.
    """
    if ocr_schedule_type(ocr) != "ps_form_b":
        return []
    words = [w for w in ocr.get("words", []) if w.get("text", "").strip()]
    identities = collections.defaultdict(list)
    codes = collections.defaultdict(list)
    pattern = re.compile(
        r"(?:\d+[.])?([A-Za-z][A-Za-z.-]*)/P\.?S\.?[-–]"
        r"(\d+|[IVXLCDM]+)(?:\((SC|ST|BC|OBC|UR)?(W)?\))?",
        re.I,
    )
    for word in words:
        raw = word["text"].strip(" ,\\‘’'")
        match = pattern.fullmatch(raw)
        if match and not re.fullmatch(r"[IVXLCDM]+", match[1], re.I):
            seat = match[2].upper()
            identities[seat].append((word, match[1], not bool(match[3] or match[4])))
            if match[3] or match[4]:
                codes[seat].append((word, (match[3] or "").upper(), bool(match[4])))
            continue
        match = re.fullmatch(r"(\d+)[-–](SC|ST|BC|OBC|UR)?(W)?", raw, re.I)
        if match and (match[2] or match[3]):
            codes[match[1]].append((word, (match[2] or "").upper(), bool(match[3])))
    for seat, entries in identities.items():
        for word, _, _ in entries:
            x, y, width, height = [
                int(word[k]) for k in ["left", "top", "width", "height"]
            ]
            for candidate in words:
                match = re.fullmatch(
                    r"\((SC|ST|BC|OBC|UR)?(W)?\)", candidate["text"], re.I
                )
                if not match or not (match[1] or match[2]):
                    continue
                cx, cy = int(candidate["left"]), int(candidate["top"])
                adjacent = -5 <= cx - (x + width) <= 30 and abs(cy - y) <= height
                below = abs(cx - x) <= 15 and 0 <= cy - (y + height) <= height
                if adjacent or below:
                    codes[seat].append(
                        (candidate, (match[1] or "").upper(), bool(match[2]))
                    )
    result = []
    for seat, entries in identities.items():
        names = {name for _, name, _ in entries}
        castes = (
            {caste for _, caste, _ in codes[seat] if caste}
            if len(names) == 1
            else set()
        )
        female = len(names) == 1 and any(woman for _, _, woman in codes[seat])
        flags = ["ocr_not_independently_verified", "explicit_ps_identifiers_and_codes"]
        if len(names) != 1:
            flags.append("conflicting_or_partial_constituency_names")
        if len(castes) != 1:
            flags.append("caste_missing_or_conflicting")
        if not female:
            flags.append("scanned_women_unread_or_blank")
        evidence = [w for w, _, _ in entries] + [w for w, _, _ in codes[seat]]
        box = [
            min(int(w["left"]) for w in evidence),
            min(int(w["top"]) for w in evidence),
            max(int(w["left"]) + int(w["width"]) for w in evidence),
            max(int(w["top"]) + int(w["height"]) for w in evidence),
        ]
        if not seat.isdigit():
            flags.append("roman_constituency_number_preserved")
        result.append(
            {
                "row_id": hashlib.sha256(
                    json.dumps(
                        [ocr["source_sha256"], ocr["source_page"], "ocr_ps", seat]
                    ).encode()
                ).hexdigest()[:20],
                "state": "West Bengal",
                "district": metadata["district"],
                "year": int(metadata["year"]),
                "stage": metadata["stage"],
                "record_kind": "block_ward_reservation",
                "local_body_printed": next(iter(names)) if len(names) == 1 else None,
                "constituency_area_raw": " | ".join(
                    dict.fromkeys(w["text"] for w, _, _ in entries)
                ),
                "seat_no": int(seat) if seat.isdigit() else None,
                "seat_no_raw": seat,
                "caste_raw": " ".join(
                    w["text"] for w, caste, _ in codes[seat] if caste
                ),
                "women_raw": " ".join(
                    w["text"] for w, _, woman in codes[seat] if woman
                ),
                "caste_reservation": next(iter(castes)) if len(castes) == 1 else None,
                "woman_reserved": 1 if female else None,
                "source_path": ocr["source_path"],
                "source_sha256": ocr["source_sha256"],
                "source_page": ocr["source_page"],
                "source_table": None,
                "source_row": len(result) + 1,
                "source_table_bbox": json.dumps(box),
                "bbox_coordinate_system": "rendered_image_pixels",
                "render_rotation_clockwise_degrees": ocr.get(
                    "render_rotation_clockwise_degrees", 0
                ),
                "raw_cells": json.dumps(evidence, ensure_ascii=False),
                "quality_flags": ";".join(flags),
                "review_status": "needs_review",
            }
        )
    return result


def write_semantic_backlog(pages, gp_rows, other_rows):
    """Separate extraction coverage from candidate and reservation-field coverage."""
    by_page = collections.defaultdict(list)
    for row in [*gp_rows, *other_rows]:
        by_page[(row["source_sha256"], row["source_page"])].append(row)
    baseline_path = OUT / "semantic_backlog_baseline.csv"
    baseline = {}
    if baseline_path.exists():
        with baseline_path.open() as handle:
            baseline = {
                (r["source_sha256"], int(r["source_page"])): r
                for r in csv.DictReader(handle)
            }
    output = []
    nondata_path = OUT / "semantic_review/verified_nondata_pages.json"
    nondata = (
        {
            (p["source_sha256"], p["source_page"]): p
            for p in json.loads(nondata_path.read_text())["pages"]
            if p["review_status"] == "visually_verified_nondata"
        }
        if nondata_path.exists()
        else {}
    )
    groups = collections.defaultdict(collections.Counter)
    for page in pages:
        if not page.get("ocr_cache"):
            continue
        ocr = json.loads((ROOT / page["ocr_cache"]).read_text())
        key = page["source_sha256"], page["source_page"]
        rows = by_page[key]
        gp = [r for r in rows if r["record_kind"] == "gp_ward_reservation"]
        ps = [r for r in rows if r["record_kind"] != "gp_ward_reservation"]
        codes = [
            r
            for r in rows
            if r.get("caste_reservation") is not None
            or r.get("woman_reserved") is not None
        ]
        orientation = page_orientation(*key) or nondata.get(key)
        layout = ocr_schedule_type(ocr)
        verified_nondata = orientation is not None and not orientation.get(
            "contains_ward_table", True
        )
        old = baseline.get(key, {})
        if rows:
            reason = "candidate_rows_require_field_review"
        elif verified_nondata:
            reason = "visually_verified_" + orientation["page_content_type"]
        elif ocr.get("status") != "extracted":
            reason = "ocr_extraction_failed"
        elif layout == "ps_form_b":
            reason = "ps_named_identifier_tokens_missing_split_or_corrupted"
        elif layout == "zp_member_schedule":
            reason = "zp_ocr_semantic_layout_not_implemented"
        elif layout == "gp_form_a":
            words, _ = orient_ocr_words(ocr)
            if schedule_header_triples(ocr, words):
                reason = "gp_name_or_printed_allocation_not_read_or_split"
            else:
                reason = "gp_header_and_explicit_named_seat_readings_insufficient"
        else:
            reason = "unit_and_named_seat_readings_insufficient"
        record = {
            k: page[k]
            for k in [
                "source_path",
                "source_sha256",
                "source_page",
                "district",
                "year",
                "stage",
                "ocr_cache",
            ]
        }
        record.update(
            layout=layout,
            structured_gp_candidates=len(gp),
            structured_other_tier_candidates=len(ps),
            candidates_with_any_reservation_field=len(codes),
            candidates_with_name=sum(
                bool(r.get("gram_panchayat", r.get("local_body_printed"))) for r in rows
            ),
            coverage="candidate_rows"
            if rows
            else "verified_nondata"
            if verified_nondata
            else "raw_only",
            reason=reason,
            reason_evidence="source_visual_review"
            if verified_nondata
            else "reader_diagnostic",
            baseline_coverage=old.get("coverage"),
            baseline_reason=old.get("reason"),
            source_page_link=page["source_path"] + "#page=" + str(page["source_page"]),
            render_rotation_clockwise_degrees=ocr.get(
                "render_rotation_clockwise_degrees", 0
            ),
            language=ocr.get("language", "eng+ben"),
            sample_image=old.get("sample_image", ""),
        )
        output.append(record)
        group = groups[(page["district"], str(page["year"]), layout)]
        group["pages"] += 1
        group[record["coverage"] + "_pages"] += 1
        group["pages_with_any_reservation_field"] += bool(codes)
        group["gp_candidates"] += len(gp)
        group["other_tier_candidates"] += len(ps)
    with (OUT / "semantic_backlog.csv").open("w") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(output[0]))
        writer.writeheader()
        writer.writerows(output)
    summary = {
        "ocr_pages": len(output),
        "coverage": dict(collections.Counter(r["coverage"] for r in output)),
        "pages_with_any_reservation_field": sum(
            r["candidates_with_any_reservation_field"] > 0 for r in output
        ),
        "raw_only_distinct_documents": len(
            {r["source_sha256"] for r in output if r["coverage"] == "raw_only"}
        ),
        "reason_counts": dict(collections.Counter(r["reason"] for r in output)),
        "groups": [
            {"district": k[0], "year": k[1], "layout": k[2], **v}
            for k, v in sorted(groups.items())
        ],
        "page_ledger": str((OUT / "semantic_backlog.csv").relative_to(ROOT)),
        "baseline": str(baseline_path.relative_to(ROOT)),
        "quality_claim": (
            "Candidate coverage is not complete semantic parsing. OCR names/codes "
            "require review; null fields remain unresolved. Raw-only reasons are "
            "parser diagnostics except explicitly source-verified nondata pages."
        ),
    }
    (OUT / "semantic_backlog.json").write_text(json.dumps(summary, indent=2) + "\n")
    return summary


@command("parse", state="West Bengal", source="ward_schedules")
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ocr", action="store_true")
    parser.add_argument("--workers", type=int, default=2)
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    native = {
        r["source_path"]: r
        for r in json.loads((ROOT / "data/wb/derived/native/index.json").read_text())
    }
    rows, other_rows, crosswalk, pages, documents, tasks, seen = (
        [],
        [],
        [],
        [],
        [],
        [],
        set(),
    )
    for metadata in csv.DictReader(INDEX.open()):
        if not selected(metadata) or not metadata["file"].lower().endswith(".pdf"):
            continue
        path = "data/wb/" + metadata["file"]
        digest = metadata["sha256"]
        if hashlib.sha256((ROOT / path).read_bytes()).hexdigest() != digest:
            raise ValueError(f"Source manifest hash differs: {path}")
        if digest in seen:
            documents.append(
                {
                    "source_path": path,
                    "source_sha256": digest,
                    "status": "byte_duplicate",
                }
            )
            continue
        seen.add(digest)
        record = json.loads((ROOT / native[path]["cache"]).read_text())
        parsed, audit = parse_native(record, metadata, path)
        if "alipurduar_CONSTITUENCY" in path:
            crosswalk.extend(parse_constituency_crosswalk(record, path))
        rows.extend(parsed)
        other = parse_other_tiers(record, metadata, path)
        other_rows.extend(other)
        for page in audit:
            page["other_tier_rows"] = sum(
                r["source_page"] == page["source_page"] for r in other
            )
            if page["other_tier_rows"] and not page["rows"]:
                page["status"] = "native_other_tier_rows_parsed"
        pages.extend(audit)
        documents.append(
            {
                "source_path": path,
                "source_sha256": digest,
                "pages": len(audit),
                "rows": len(parsed),
            }
        )
        for page, status in zip(record["pages"], audit, strict=True):
            # Embedded OCR without ruled tables also needs a reader attempt.
            if not page["tables"] and (page["images"] or not page["text"].strip()):
                tasks.append((path, digest, page["page"]))
                status["status"] = "local_ocr_pending"
    if args.ocr:
        with ProcessPoolExecutor(max_workers=args.workers) as pool:
            for i, result in enumerate(pool.map(ocr_page, tasks), 1):
                if i % 25 == 0:
                    print(
                        json.dumps(
                            {
                                "ocr_pages_completed": i,
                                "ocr_pages_total": len(tasks),
                                "cache": result,
                            }
                        ),
                        flush=True,
                    )
    for page in pages:
        target = OUT / "ocr" / page["source_sha256"] / f"{page['source_page']:04d}.json"
        if target.exists():
            ocr = json.loads(target.read_text())
            page["ocr_cache"] = str(target.relative_to(ROOT))
            page["render_rotation_clockwise_degrees"] = ocr.get(
                "render_rotation_clockwise_degrees", 0
            )
            parsed = parse_ocr(ocr, page)
            parsed_other = parse_ocr_ps(ocr, page)
            rows.extend(parsed)
            other_rows.extend(parsed_other)
            page["ocr_rows"] = len(parsed)
            page["ocr_other_tier_rows"] = len(parsed_other)
            page["status"] = (
                "ocr_extracted_semantic_review_required"
                if ocr["status"] == "extracted"
                else "local_ocr_failed"
            )
    for collection in [rows, other_rows]:
        fields = list(dict.fromkeys(key for row in collection for key in row))
        for row in collection:
            for field in fields:
                row.setdefault(field, None)
    write_table(rows, OUT / "gp_seats")
    if other_rows:
        write_table(other_rows, OUT / "other_tier_seats")
    if crosswalk:
        write_table(crosswalk, OUT / "constituency_crosswalk")
    (OUT / "page_audit.json").write_text(
        json.dumps(pages, ensure_ascii=False, indent=2) + "\n"
    )
    (OUT / "document_audit.json").write_text(
        json.dumps(documents, ensure_ascii=False, indent=2) + "\n"
    )
    semantic = write_semantic_backlog(pages, rows, other_rows)
    report = {
        "semantic_coverage": {
            k: v for k, v in semantic.items() if k not in {"groups", "reason_counts"}
        },
        "documents": len(documents),
        "distinct_documents": len(seen),
        "pages": len(pages),
        "rows": len(rows),
        "other_tier_rows": len(other_rows),
        "constituency_crosswalk_rows": len(crosswalk),
        "page_status": dict(collections.Counter(p["status"] for p in pages)),
        "row_review_status": dict(
            collections.Counter(r["review_status"] for r in rows)
        ),
        "quality_claim": (
            "Native field parsing and complete page extraction are not field "
            "accuracy validation. Ward reservations are not GP office reservations."
        ),
    }
    (OUT / "parse_report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
