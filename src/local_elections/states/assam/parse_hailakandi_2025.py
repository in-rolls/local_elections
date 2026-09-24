"""Parse Hailakandi's reserved-only 2025 PRI notification OCR cache.

The notification uses one table layout across thirteen scanned pages.  It
prints reserved seats only.  This module reads the cached table cells and
never opens either the reservation PDF or the supporting delimitation gazette.
"""

import collections
import difflib
import re

from local_elections.states.assam.parse_scan_2025 import tables_of


def _key(value):
    return re.sub(r"[^a-z0-9]", "", value.lower())


def _header(rows):
    return [_key(cell) for cell in rows[0]]


def supports(document):
    """Return whether the OCR cache has Hailakandi's reserved-row layout."""
    return any(
        _header(rows)
        == [
            "nameofanchalikpanchayat",
            "nameofgaonpanchayat",
            "noofward",
            "statusofreservation",
        ]
        for _page, rows in tables_of(document)
    )


def _numbered(value, description):
    match = re.match(r"^\s*(\d+)\s*(?:[-–—.]\s*)?(.+?)\s*$", value)
    if not match or not match.group(2).strip():
        raise ValueError(f"expected numbered {description}, found {value!r}")
    return int(match.group(1)), match.group(2).strip()


def _numbered_gp(value):
    match = re.match(r"^\s*(\d+)\s*[-–—]\s*(.+?)\s*$", value)
    if not match:
        raise ValueError(f"expected numbered GP, found {value!r}")
    return int(match.group(1)), match.group(2).strip()


def _reservation(value):
    upper = value.upper()
    caste = (
        "SC"
        if re.search(r"\bSC\b", upper)
        else "ST"
        if re.search(r"\bST\b", upper)
        else "NONE"
    )
    return caste, int("WOMAN" in upper or "WOMEN" in upper)


def _section_rows(document):
    """Group continuation tables using the headers printed by the source."""
    sections = collections.defaultdict(list)
    ap_office_index = gp_office_index = 0
    current = None
    for page, rows in tables_of(document):
        header = _header(rows)
        is_header = False
        if header == ["noofzpc", "nameofzpc", "statusofreservation"]:
            current = "zp_member"
            is_header = True
        elif header == ["nameofanchalikpanchayat", "statusofreservation"]:
            current = ("block_head", "block_vice_head")[ap_office_index]
            ap_office_index += 1
            is_header = True
        elif header == [
            "nameofanchalikpanchayat",
            "nameofgp",
            "statusofreservation",
        ]:
            current = ("block_member", "gp_head", "gp_vice_head")[gp_office_index]
            gp_office_index += 1
            is_header = True
        elif header == [
            "nameofanchalikpanchayat",
            "nameofgaonpanchayat",
            "noofward",
            "statusofreservation",
        ]:
            current = "gp_ward"
            is_header = True
        if current is None:
            raise RuntimeError(f"unclassified Hailakandi table on page {page}")
        for cells in rows[1:] if is_header else rows:
            sections[current].append({"page": page, "cells": cells})

    if ap_office_index != 2 or gp_office_index != 3:
        raise RuntimeError(
            "Hailakandi table sequence changed: "
            f"AP offices={ap_office_index}, GP offices={gp_office_index}"
        )
    return sections


def _office_gp_candidates(sections):
    candidates = collections.defaultdict(list)
    for tier in ("block_member", "gp_head", "gp_vice_head"):
        for record in sections[tier]:
            cells = record["cells"]
            if len(cells) != 3:
                continue
            try:
                serial, name = _numbered_gp(cells[1])
            except ValueError:
                continue
            candidates[serial].append(name)
    return candidates


def _match_unnumbered_gp(name, numbered_names, candidates):
    available = {
        serial: values
        for serial, values in candidates.items()
        if serial not in numbered_names
    }
    scores = []
    for serial, values in available.items():
        score = max(
            difflib.SequenceMatcher(None, _key(name), _key(value)).ratio()
            for value in values
        )
        scores.append((score, serial))
    scores.sort(reverse=True)
    if not scores or scores[0][0] < 0.85:
        raise RuntimeError(f"unnumbered GP does not join uniquely: {name!r}")
    if len(scores) > 1 and scores[0][0] - scores[1][0] < 0.10:
        raise RuntimeError(
            f"unnumbered GP has an ambiguous name join: {name!r}, {scores[:2]}"
        )
    return scores[0][1]


def _wards_and_gps(sections):
    parsed = []
    numbered_names = collections.defaultdict(list)
    candidates = _office_gp_candidates(sections)
    pending = []
    for record in sections["gp_ward"]:
        cells = record["cells"]
        if len(cells) != 4:
            raise RuntimeError(f"unexpected Hailakandi ward row: {cells!r}")
        block_serial, block = _numbered(cells[0], "Anchalik Panchayat")
        try:
            gp_serial, gp = _numbered_gp(cells[1])
            numbered_names[gp_serial].append(gp)
        except ValueError:
            gp_serial, gp = None, cells[1].strip()
        ward_match = re.fullmatch(r"\s*(\d+)\s*", cells[2])
        if not ward_match:
            raise RuntimeError(f"invalid Hailakandi ward number: {cells!r}")
        ward = {
            "block_serial": block_serial,
            "anchalik_panchayat": block,
            "gp_serial": gp_serial,
            "gram_panchayat": gp,
            "ward_no": int(ward_match.group(1)),
            "reservation_raw": cells[3],
            "source_page": record["page"],
        }
        if gp_serial is None:
            pending.append(ward)
        else:
            parsed.append(ward)

    unnumbered_matches = {}
    for ward in pending:
        name_key = _key(ward["gram_panchayat"])
        if name_key not in unnumbered_matches:
            unnumbered_matches[name_key] = _match_unnumbered_gp(
                ward["gram_panchayat"], numbered_names, candidates
            )
        ward["gp_serial"] = unnumbered_matches[name_key]
        numbered_names[ward["gp_serial"]].append(ward["gram_panchayat"])
        parsed.append(ward)

    gp_rows = collections.defaultdict(list)
    for ward in parsed:
        caste, woman = _reservation(ward["reservation_raw"])
        ward["caste_reservation_raw"] = caste
        ward["woman_reserved_raw"] = woman
        ref = (ward["gp_serial"], ward["ward_no"])
        gp_rows[ward["gp_serial"]].append(ward)
        if (
            sum(
                candidate["ward_no"] == ward["ward_no"]
                for candidate in gp_rows[ward["gp_serial"]]
            )
            > 1
        ):
            raise RuntimeError(f"duplicate Hailakandi reserved ward: {ref}")

    if set(gp_rows) != set(range(1, 63)):
        raise RuntimeError(
            "Hailakandi ward table does not identify all 62 GPs: "
            f"found {sorted(gp_rows)}"
        )

    gps = []
    for serial, wards in sorted(gp_rows.items()):
        blocks = {(ward["block_serial"], ward["anchalik_panchayat"]) for ward in wards}
        if len(blocks) != 1:
            raise RuntimeError(f"GP {serial} appears in multiple APs: {blocks}")
        block_serial, block = blocks.pop()
        names = collections.Counter(_key(ward["gram_panchayat"]) for ward in wards)
        name_key = names.most_common(1)[0][0]
        name = next(
            ward["gram_panchayat"]
            for ward in wards
            if _key(ward["gram_panchayat"]) == name_key
        )
        gps.append(
            {
                "serial": serial,
                "block_serial": block_serial,
                "anchalik_panchayat": block,
                "gram_panchayat": name,
                "source_page": min(ward["source_page"] for ward in wards),
            }
        )
        for ward in wards:
            ward["gram_panchayat"] = name
            ward["anchalik_panchayat"] = block
    return gps, sorted(parsed, key=lambda row: (row["gp_serial"], row["ward_no"]))


def _offices(sections, gps):
    gp_by_serial = {gp["serial"]: gp for gp in gps}
    offices = []
    diagnostics = []
    for tier in ("zp_member", "block_head", "block_vice_head"):
        for record in sections[tier]:
            cells = record["cells"]
            expected = 3 if tier == "zp_member" else 2
            if len(cells) != expected:
                raise RuntimeError(f"unexpected {tier} row: {cells!r}")
            if tier == "zp_member":
                serial_match = re.fullmatch(r"\s*(\d+)\s*", cells[0])
                if not serial_match:
                    raise RuntimeError(f"invalid ZPC number: {cells!r}")
                serial, name = int(serial_match.group(1)), cells[1].strip()
            else:
                serial, name = _numbered(cells[0], tier)
            caste, woman = _reservation(cells[-1])
            offices.append(
                {
                    "office": tier,
                    "seat_serial": serial,
                    "seat": name,
                    "anchalik_panchayat": "" if tier == "zp_member" else name,
                    "caste_reservation_raw": caste,
                    "woman_reserved_raw": woman,
                    "reservation_raw": cells[-1],
                    "source_page": record["page"],
                }
            )

    for tier in ("block_member", "gp_head", "gp_vice_head"):
        for record in sections[tier]:
            cells = record["cells"]
            if len(cells) != 3:
                raise RuntimeError(f"unexpected {tier} row: {cells!r}")
            try:
                gp_serial, raw_gp = _numbered_gp(cells[1])
            except ValueError:
                diagnostics.append(
                    {
                        "kind": "rejected_source_row",
                        "office": tier,
                        "reason": "GP cell has no identifiable numbered GP",
                        "anchalik_panchayat_raw": cells[0],
                        "gram_panchayat_raw": cells[1],
                        "reservation_raw": cells[2],
                        "source_page": record["page"],
                    }
                )
                continue
            gp = gp_by_serial.get(gp_serial)
            if gp is None:
                raise RuntimeError(f"{tier} GP {gp_serial} is outside the ward roster")
            _block_serial, raw_block = _numbered(cells[0], "Anchalik Panchayat")
            if _key(raw_block) != _key(gp["anchalik_panchayat"]):
                diagnostics.append(
                    {
                        "kind": "hierarchy_mismatch",
                        "office": tier,
                        "reason": "reservation row AP disagrees with the ward roster",
                        "gp_serial": gp_serial,
                        "anchalik_panchayat_raw": raw_block,
                        "anchalik_panchayat": gp["anchalik_panchayat"],
                        "gram_panchayat_raw": raw_gp,
                        "gram_panchayat": gp["gram_panchayat"],
                        "reservation_raw": cells[2],
                        "source_page": record["page"],
                    }
                )
            caste, woman = _reservation(cells[2])
            offices.append(
                {
                    "office": tier,
                    "gp_serial": gp_serial,
                    "gram_panchayat": gp["gram_panchayat"],
                    "anchalik_panchayat": gp["anchalik_panchayat"],
                    "caste_reservation_raw": caste,
                    "woman_reserved_raw": woman,
                    "reservation_raw": cells[2],
                    "source_page": record["page"],
                }
            )
    return offices, diagnostics


def parse_document(document):
    """Return source records for every identifiable printed reserved seat."""
    if "<!-- ocr-unread " in document:
        raise RuntimeError("OCR cache contains unread pages; repair extraction first")
    if not supports(document):
        raise RuntimeError("OCR cache is not the Hailakandi reserved-row layout")
    sections = _section_rows(document)
    gps, wards = _wards_and_gps(sections)
    offices, diagnostics = _offices(sections, gps)
    return {
        "layout": "hailakandi_reserved_rows",
        "listing_scope": "reserved_only",
        "gps": gps,
        "wards": wards,
        "offices": offices,
        "diagnostics": diagnostics,
    }
