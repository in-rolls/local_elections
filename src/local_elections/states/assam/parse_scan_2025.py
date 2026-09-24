"""Read a cached Assam 2025 OCR document as structured source records.

This module knows table shapes, not district data. The acquisition manifest
selects the source, the cached HTML supplies every seat value, and explicit
reconciliation checks stop a partial or rearranged OCR result from parsing.
"""

import difflib
import html
import re

from local_elections.states.assam import ocr_2025

BENGALI_DIGITS = str.maketrans("০১২৩৪৫৬৭৮৯", "0123456789")


def clean(value):
    """Return plain, whitespace-normalized text from one HTML fragment."""
    value = re.sub(r"<br\s*/?>", " ", value or "", flags=re.I)
    value = re.sub(r"<[^>]+>", " ", value)
    return re.sub(r"\s+", " ", html.unescape(value)).strip()


def tables_of(document):
    """Return ``(page, rows)`` pairs from form-feed-separated OCR HTML."""
    tables = []
    for page_number, page in enumerate(document.split("\f"), start=1):
        for table in re.findall(r"<table[^>]*>(.*?)</table>", page, re.S | re.I):
            rows = []
            for row in re.findall(r"<tr[^>]*>(.*?)</tr>", table, re.S | re.I):
                cells = re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", row, re.S | re.I)
                if cells:
                    rows.append([clean(cell) for cell in cells])
            if rows:
                tables.append((page_number, rows))
    return tables


def _one(tables, predicate, description):
    matches = [table for table in tables if predicate(*table)]
    if len(matches) != 1:
        raise RuntimeError(
            f"expected one {description} table in OCR cache; found {len(matches)}"
        )
    return matches[0]


def _number_name(value):
    match = re.match(r"^\s*(\d+)\s*(?:No\.?\s*)?[-–—.]?\s*(.+?)\s*$", value, re.I)
    if not match:
        raise RuntimeError(f"expected numbered GP cell, found {value!r}")
    return int(match.group(1)), match.group(2).strip().title()


def _ward_refs(value):
    return [
        (int(gp), int(ward)) for gp, ward in re.findall(r"(\d+)\s*/\s*(\d+)", value)
    ]


def _reservation(value):
    upper = value.upper()
    caste = "NONE"
    if re.search(r"\bSC\b", upper):
        caste = "SC"
    elif re.search(r"\bST\b", upper):
        caste = "ST"
    return caste, int("WOMEN" in upper or "WOMAN" in upper)


def _key(value):
    return re.sub(r"[^a-z0-9]", "", value.lower())


def _same_name(left, right):
    return difflib.SequenceMatcher(None, _key(left), _key(right)).ratio() >= 0.85


def _table_header(rows):
    return " ".join(rows[0]).lower()


def _gp_and_ward_tables(tables):
    women_page, women_table = _one(
        tables,
        lambda _page, rows: (
            "gp member constituency (gp no./ward no.)" in _table_header(rows)
            and len(rows) > 30
        ),
        "complete women-reserved ward",
    )
    caste_page, caste_table = _one(
        tables,
        lambda _page, rows: (
            "gp ward member constituency" in _table_header(rows)
            and any("ward no" in cell.lower() for row in rows[1:] for cell in row)
        ),
        "caste-reserved ward",
    )

    gps = []
    women = {}
    for cells in women_table[1:]:
        if len(cells) != 4:
            raise RuntimeError(f"unexpected GP women row shape: {cells!r}")
        serial, name = _number_name(cells[1])
        refs = _ward_refs(cells[2])
        if not refs or {gp for gp, _ in refs} != {serial}:
            raise RuntimeError(f"GP/ward mismatch in women row: {cells!r}")
        gps.append(
            {
                "serial": serial,
                "gram_panchayat": name,
                "source_page": women_page,
            }
        )
        for ref in refs:
            if ref in women:
                raise RuntimeError(f"duplicate women-reserved ward: {ref}")
            women[ref] = {"raw": cells[3], "page": women_page}

    gp_by_serial = {gp["serial"]: gp["gram_panchayat"] for gp in gps}
    if len(gp_by_serial) != len(gps):
        raise RuntimeError("duplicate GP serial in complete ward table")

    caste = {}
    for cells in caste_table[1:]:
        if len(cells) != 4:
            raise RuntimeError(f"unexpected caste ward row shape: {cells!r}")
        gp_serial, gp_name = _number_name(cells[1])
        ward_match = re.search(r"Ward\s*No\.?\s*(\d+)", cells[2], re.I)
        if not ward_match:
            raise RuntimeError(f"missing ward number in caste row: {cells!r}")
        if not _same_name(gp_name, gp_by_serial.get(gp_serial, "")):
            raise RuntimeError(f"GP name mismatch in caste row: {cells!r}")
        ref = (gp_serial, int(ward_match.group(1)))
        if ref in caste:
            raise RuntimeError(f"duplicate caste-reserved ward: {ref}")
        caste[ref] = {"raw": cells[3], "page": caste_page}

    unreserved = {}
    for page, rows in tables:
        for cells in rows:
            if len(cells) != 4 or not _ward_refs(cells[2]):
                continue
            status = cells[3].lower()
            caste_exception = re.search(r"\breserv(?:e|ed)\b.*\b(?:sc|st)\b", status)
            if "unreserved" not in status and not caste_exception:
                continue
            gp_serial, gp_name = _number_name(cells[1])
            if not _same_name(gp_name, gp_by_serial.get(gp_serial, "")):
                raise RuntimeError(f"GP name mismatch in unreserved row: {cells!r}")
            for ref in _ward_refs(cells[2]):
                if ref in unreserved:
                    raise RuntimeError(f"duplicate unreserved ward: {ref}")
                unreserved[ref] = {"raw": "Unreserved", "page": page}

    return gps, women, caste, unreserved


def _assamese_ward_names(document):
    names = {}
    pattern = re.compile(r"^([০-৯0-9]+)\s*\(\s*([০-৯0-9]+)\s*\)\s*(.+)$")
    for page, rows in tables_of(document):
        for cells in rows:
            if len(cells) not in {3, 4}:
                continue
            match = pattern.match(cells[-2])
            if not match:
                continue
            ref = (
                int(match.group(1).translate(BENGALI_DIGITS)),
                int(match.group(2).translate(BENGALI_DIGITS)),
            )
            if ref in names:
                raise RuntimeError(f"duplicate Assamese ward name: {ref}")
            names[ref] = {"name": match.group(3), "page": page}
    return names


def _office_tables(tables, gps):
    gp_by_serial = {gp["serial"]: gp["gram_panchayat"] for gp in gps}
    gp_by_name = {_key(name): (serial, name) for serial, name in gp_by_serial.items()}

    ap_page, ap_table = _one(
        tables,
        lambda _page, rows: "ap member constituency" in _table_header(rows),
        "AP-member reservation",
    )
    head_page, head_table = _one(
        tables,
        lambda page, rows: (
            page == ap_page
            and "name of gp constituency" in _table_header(rows)
            and "seats to be reserved women" in _table_header(rows)
        ),
        "GP-president reservation",
    )
    vice_page, vice_table = _one(
        tables,
        lambda page, rows: (
            page > ap_page
            and "name of gp constituency" in _table_header(rows)
            and "seats to be reserved women" in _table_header(rows)
        ),
        "GP-vice-president reservation",
    )

    offices = []
    for tier, page, rows, numbered in (
        ("block_member", ap_page, ap_table, True),
        ("gp_head", head_page, head_table, True),
        ("gp_vice_head", vice_page, vice_table, False),
    ):
        seen = set()
        for cells in rows[1:]:
            if len(cells) != 4:
                raise RuntimeError(f"unexpected {tier} row shape: {cells!r}")
            if numbered:
                serial, parsed_name = _number_name(cells[1])
                name = gp_by_serial.get(serial)
                if name is None or not _same_name(name, parsed_name):
                    raise RuntimeError(f"GP mismatch in {tier} row: {cells!r}")
            else:
                match = gp_by_name.get(_key(cells[1]))
                if match is None:
                    raise RuntimeError(f"unknown GP in {tier} row: {cells!r}")
                serial, name = match
            if serial in seen:
                raise RuntimeError(f"duplicate GP in {tier} table: {serial}")
            seen.add(serial)
            caste, woman = _reservation(cells[2])
            offices.append(
                {
                    "office": tier,
                    "gp_serial": serial,
                    "gram_panchayat": name,
                    "caste_reservation_raw": caste,
                    "woman_reserved_raw": woman,
                    "reservation_raw": cells[2],
                    "source_page": page,
                }
            )
    return offices


def _district_offices(first_page):
    text = clean(first_page)
    block_match = re.search(
        r"Anchalik Panchayat viz\s*\(1\)\s*(.+?)\s+A\.?P\s*"
        r"\(2\)\s*(.+?)\s+A\.?P",
        text,
        re.I,
    )
    if not block_match:
        raise RuntimeError("could not read the AP universe from the first page")
    blocks = [
        block_match.group(1).strip().title(),
        block_match.group(2).strip().title(),
    ]
    by_key = {_key(block): block for block in blocks}

    head_match = re.search(
        r"➤\s*\d+\s*-\s*(.+?)\s+A\.?P\s+kept reserved for women",
        text,
        re.I,
    )
    vice_match = re.search(r"Women kept for\s+(.+?)\s+AP\s+as", text, re.I)
    if not head_match or not vice_match:
        raise RuntimeError("could not read AP office reservations from the first page")
    head = by_key.get(_key(head_match.group(1)))
    vice = by_key.get(_key(vice_match.group(1)))
    if not head or not vice:
        raise RuntimeError("AP office reservation does not join to AP universe")

    total_match = re.search(r"Total\s+(\d+)\s+number of ZP Member", text, re.I)
    if not total_match:
        raise RuntimeError("could not read the ZP constituency total")
    total = int(total_match.group(1))
    reserved = {
        int(number): name.strip().title()
        for number, name in re.findall(
            r"\(\d+\)\s*(\d+)\s*-\s*No\.?\s*(.+?)\s+ZPC", text, re.I
        )
    }
    if not reserved:
        raise RuntimeError("could not read reserved ZP constituencies")
    return blocks, head, vice, total, reserved


def parse_document(document):
    """Parse one supported district cache and reconcile its complete universe."""
    pages = document.split("\f")
    if any("<!-- ocr-unread " in page for page in pages):
        raise RuntimeError("OCR cache contains unread pages; repair extraction first")
    tables = tables_of(document)
    gps, women, caste, unreserved = _gp_and_ward_tables(tables)
    names = _assamese_ward_names(document)

    gp_serials = {gp["serial"] for gp in gps}
    explicit = set(women) | set(unreserved) | set(caste)
    overlap = set(women) & set(unreserved)
    total_match = re.search(
        r"Total\s+No\s+of\s+Ward\s*=\s*(\d+)", clean(document), re.I
    )
    if not total_match:
        raise RuntimeError("could not read the printed ward total")
    printed_total = int(total_match.group(1))
    ward_sets = {
        gp: {ward for candidate, ward in explicit if candidate == gp}
        for gp in gp_serials
    }
    complete_runs = all(
        wards and wards == set(range(1, max(wards) + 1)) for wards in ward_sets.values()
    )
    if overlap or len(explicit) != printed_total or not complete_runs:
        raise RuntimeError(
            "ward tables do not form one complete universe: "
            f"overlap={sorted(overlap)}, parsed={len(explicit)}, "
            f"printed={printed_total}, complete_runs={complete_runs}"
        )
    universe = explicit
    if set(names) != set(women):
        raise RuntimeError(
            "Assamese ward-name table does not match women-reserved wards: "
            f"names={len(names)}, women={len(women)}"
        )

    wards = []
    gp_names = {gp["serial"]: gp["gram_panchayat"] for gp in gps}
    for ref in sorted(universe):
        caste_raw = caste.get(ref)
        woman = int(ref in women)
        category = _reservation(caste_raw["raw"])[0] if caste_raw else "NONE"
        evidence = caste_raw or women.get(ref) or unreserved[ref]
        wards.append(
            {
                "gp_serial": ref[0],
                "gram_panchayat": gp_names[ref[0]],
                "ward_no": ref[1],
                "ward_name": names.get(ref, {}).get("name", ""),
                "caste_reservation_raw": category,
                "woman_reserved_raw": woman,
                "reservation_raw": caste_raw["raw"] if caste_raw else evidence["raw"],
                "source_page": evidence["page"],
            }
        )

    blocks, head, vice, zp_total, reserved_zps = _district_offices(pages[0])
    return {
        "layout": "south_salmara_complete_tables",
        "listing_scope": "all_seats",
        "gps": gps,
        "wards": wards,
        "offices": _office_tables(tables, gps),
        "blocks": blocks,
        "block_head_reserved": head,
        "block_vice_reserved": vice,
        "zp_total": zp_total,
        "reserved_zps": reserved_zps,
    }


def parse_cached_document(document):
    """Dispatch one OCR cache by its printed table shape."""
    header_text = " ".join(_table_header(rows) for _page, rows in tables_of(document))
    if "gp member constituency (gp no./ward no.)" in header_text:
        return parse_document(document)

    from local_elections.states.assam import parse_hailakandi_2025

    if parse_hailakandi_2025.supports(document):
        return parse_hailakandi_2025.parse_document(document)
    raise RuntimeError("unsupported Assam OCR table layout")


def extracted(district):
    """Load and parse one district selected by the acquisition manifest."""
    selected = ocr_2025.select_documents(
        ocr_2025.manifest_documents(), district=district
    )
    record, source = selected[0]
    cache = ocr_2025.CACHE / f"{source.stem}.html"
    if not cache.exists():
        raise RuntimeError(f"missing OCR cache {cache}; run make assam-2025-ocr")
    parsed = parse_cached_document(cache.read_text(encoding="utf-8"))
    parsed.update({"district": record["district"], "source": source})
    return parsed


def cached_extractions():
    """Parse every manifest document that has a committed OCR cache."""
    parsed = []
    for record, source in ocr_2025.manifest_documents():
        cache = ocr_2025.CACHE / f"{source.stem}.html"
        if not cache.exists():
            continue
        document = parse_cached_document(cache.read_text(encoding="utf-8"))
        document.update({"district": record["district"], "source": source})
        parsed.append(document)
    return parsed
