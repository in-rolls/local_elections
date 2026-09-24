"""Parse Jammu & Kashmir panchayat reservation, 2010 / 2016 / 2018.

J&K calls the gram panchayat a *halqa* and its wards *panch constituencies*, so
the two tiers here are `sarpanch` (halqa level) and `ward` (panch level).

Each year is laid out differently, so columns are located from the header row
rather than by fixed index:

  2016  15 columns, and the richest source in this project: district, block,
        halqa, panch ward, SC/ST/OC populations and percentages, and **two**
        reservation columns - one for the panch ward, one for the sarpanch of
        the halqa. So 2016 yields both tiers, and carries the populations that
        the allocation was based on, which makes the rule auditable.
  2010  4-6 columns: S.No, halqa, panch number/name, and either one combined
        reservation cell or separate SC/ST/Women flags. Ward tier only. The
        PDFs are extracted first by extract_2010.py; this parser reads JSONL.
  2018   9 columns: district and block numbers and names, halqa, panch, and one
        reservation column. Ward tier only.

The holdings are ad-hoc - mixed granularity, inconsistent filenames, 2016
covering part of Jammu division and 2018 part of Kashmir - so what matters here
is honest coverage accounting, not clever parsing. validate.py does that.

Writes data/jk/{ward,sarpanch}_reservation_<year>.{csv,jsonl}.
"""

import argparse
import collections
import json
import re

import pdfplumber

from local_elections.common import canon, emit
from local_elections.common.normalize import (
    label,
    normalize_reservation,
    script_of,
)
from local_elections.common.runlog import command, get_logger
from local_elections.paths import ROOT
from local_elections.states.jk import extract_2010, extract_2016

LOGGER = get_logger(__name__)

JK = ROOT / "data" / "jk"

# These are held, but their digital layers are not clean tables. Ghagwal has
# only a header table; Poonch's characters and cells drift across columns; and
# Ramnagar's panchayat names collapse to fragments such as "2" and "K G j".
# Keeping them out is a coverage decision, not a parser failure.
EXCLUDED_2010 = {
    "Ghagwal.pdf": "only the header page has an extractable table",
    "Poonch.pdf": "character spacing and row alignment corrupt names and marks",
    "Ramnagar .pdf": "panchayat names collapse into character fragments",
}

COLUMNS = [
    "state",
    "year",
    "district",
    "district_declared",
    "block_no",
    "block",
    "gp_no",
    "halqa",
    "gp_identity_from_page_text",
    "ward_no",
    "ward_name",
    "tier",
    "tier_local",
    "reservation",
    "caste_reservation",
    "woman_reserved",
    "listing_scope",
    "pop_sc",
    "pop_st",
    "pop_oc",
    "pop_total",
    "reservation_raw",
    "script",
]

# What each year's documents actually list. 2010 and 2016 are full rosters -
# they carry "Un Reserved" and "Open" rows - but the 2018 files are titled
# "Reservation of SC/ST/women & ST for panch constituencies" and contain *only
# the reserved wards*. Treating that as a roster implies 82% of J&K wards are
# women-reserved, which is an artefact of the document, not a finding. Any
# denominator computed from 2018 is wrong unless this column is respected.
LISTING_SCOPE = {"2010": "all_seats", "2016": "all_seats", "2018": "reserved_only"}

# header text that leaks into the data when a header row is not skipped
HEADER_NOISE = {
    "name of district",
    "district name",
    "name of block",
    "block name",
    "name of halqa",
    "district",
    "block",
}


def clean(cell):
    return re.sub(r"\s+", " ", (cell or "").replace("\n", " ")).strip()


def district_from_title(text):
    """2016 and 2018 print "... in respect of District Doda" above the table."""
    for name in DISTRICT_ROSTER:
        if re.search(
            rf"\b(?:district|distrist)\s+{re.escape(name)}\b", text or "", re.I
        ):
            return name
    return ""


# Jammu & Kashmir's districts as they stood in 2010. A closed list, which is
# what makes the district readable at all: the 2010 documents spell the word
# before it at least four ways - DISTRICT, Distrist, ISTRICT with the D lost to
# the scan, and sometimes nothing but a comma - so the word is matched by edit
# distance and the name that follows against this roster. Free-text capture was
# tried first and returned "JAMMU Name" and "REASI ANNEXURE".
DISTRICT_ROSTER = [
    "Jammu",
    "Samba",
    "Kathua",
    "Udhampur",
    "Reasi",
    "Rajouri",
    "Poonch",
    "Doda",
    "Ramban",
    "Kishtwar",
    "Anantnag",
    "Kulgam",
    "Pulwama",
    "Shopian",
    "Srinagar",
    "Budgam",
    "Ganderbal",
    "Bandipora",
    "Baramulla",
    "Kupwara",
    "Leh",
    "Kargil",
]

# Eight of the 2010 blocks name no district anywhere in their document. These
# come from outside the corpus and are marked as such rather than presented as
# something the page said - see the district_declared column.
DISTRICT_OF_BLOCK = {
    "dachhan": "Kishtwar",
    "marwah": "Kishtwar",
    "padder": "Kishtwar",
    "warwan": "Kishtwar",
    "inderbal": "Kishtwar",
    "nagsani": "Kishtwar",
    "gool": "Ramban",
    "ramsoo": "Ramban",
}

_WORD = re.compile(r"\b([A-Za-z]{5,9})\b")


def _distance(a, b):
    previous = list(range(len(b) + 1))
    for i, x in enumerate(a, 1):
        current = [i]
        for j, y in enumerate(b, 1):
            current.append(
                min(previous[j] + 1, current[j - 1] + 1, previous[j - 1] + (x != y))
            )
        previous = current
    return previous[-1]


def district_from_document(text):
    """The district a 2010 document names, or "" if it names none.

    Prefers the name that follows a district-ish word; falls back to any roster
    name on the page, which is safe because these are district-level documents
    and the roster names are distinctive.
    """
    flat = re.sub(r"\s+", " ", text or "")
    for found in _WORD.finditer(flat):
        if _distance(found.group(1).upper(), "DISTRICT") <= 2:
            after = flat[found.end() : found.end() + 30]
            for name in DISTRICT_ROSTER:
                if re.match(r"\W{0,3}" + name, after, re.I):
                    return name
    for name in DISTRICT_ROSTER:
        if re.search(r"\b" + name + r"\b", flat, re.I):
            return name
    return ""


def block_from_filename(path):
    """2010 names each file for its block. Verified rather than assumed: on the
    2,236 rows where the page also states a block, the two agree every time.
    """
    return re.sub(r"[()]", "", path.stem).strip()


WARD_PREFIX = re.compile(r"^\s*([IVX]+|\d+)\s*[.)-]?\s*(.*)$", re.I)


def split_ward(value):
    """Split the combined 2010 ``number and name`` cell."""
    found = WARD_PREFIX.match(clean(value))
    if not found:
        return "", ""
    return found.group(1).upper(), found.group(2).strip()


def clean_ward_no(value):
    """Remove extraction punctuation without turning a ward name into a number."""
    value = clean(value).upper().strip("`'\".,;:()[]{}")
    return value if re.fullmatch(r"[IVX]+|\d+", value) else ""


def split_numbered_name(value):
    """Split a printed panchayat value such as ``1. Badhole``."""
    found = re.match(r"^\s*(\d+)\s*[.)-]\s*(.+)$", clean(value))
    return (found.group(1), found.group(2).strip()) if found else ("", clean(value))


def recover_group_from_page_text(text, block, ward_no, ward_name):
    """Recover a spanning GP cell that table extraction left empty.

    Some 2016 pages visibly print the next panchayat across a merged cell, but
    pdfplumber returns ``None`` for that cell. The same words remain in the
    page text. The caller tries the known wards in a buffered GP group and
    marks the resulting group in the output.
    """

    def words(value):
        return r"\s+".join(re.escape(part) for part in clean(value).split())

    if not ward_no or not ward_name:
        return "", ""
    ward = rf"\b{re.escape(ward_no)}\b\s+{words(ward_name)}\b"
    lines = [clean(raw_line) for raw_line in (text or "").splitlines()]
    for line in lines:
        found = re.search(rf"^(?P<prefix>.*?)\s+{ward}", line, re.I)
        if not found:
            continue
        prefix = clean(found.group("prefix"))
        block_found = list(re.finditer(words(block), prefix, re.I))
        if block_found:
            prefix = clean(prefix[block_found[-1].end() :])
        numbered = re.match(r"^(\d+)\s+(.+)$", prefix)
        if numbered:
            return numbered.group(1), clean(numbered.group(2))
        if prefix and not prefix.isdigit():
            return "", prefix

    # A vertically centred spanning cell can land on the same text line as a
    # later ward's name while its ward number lands on the following line.
    # The text between the block and that known ward name is then exactly the
    # missing panchayat identity.
    for line in lines:
        block_found = list(re.finditer(words(block), line, re.I))
        name_found = re.search(words(ward_name), line, re.I)
        if not block_found or not name_found:
            continue
        block_end = block_found[-1].end()
        if name_found.start() <= block_end:
            continue
        between = clean(line[block_end : name_found.start()])
        between = re.sub(rf"^\b{re.escape(ward_no)}\b\s*", "", between, flags=re.I)
        numbered = re.match(r"^(\d+)\s+(.+)$", between)
        if numbered:
            return numbered.group(1), clean(numbered.group(2))
        if between and not between.isdigit():
            return "", between
    return "", ""


def normalize_2010_reservation(raw):
    """Read a 2010 mark, including the source's blank open-seat convention.

    These are complete ward rosters headed ``Reserved for`` or ``Whether
    reserved``.  A blank or punctuation-only cell therefore states that the
    ward is not reserved; it is not a missing observation.  The raw cell stays
    untouched in ``reservation_raw`` so the inference remains auditable.
    """
    parsed = normalize_reservation(raw)
    if parsed:
        return parsed
    letters = re.sub(r"[^a-z]", "", raw.lower())
    aliases = {
        "rsc": ("SC", 0),
        "rst": ("ST", 0),
        "rw": ("NONE", 1),
        "woemn": ("NONE", 1),
        "wonen": ("NONE", 1),
    }
    if letters in aliases:
        caste, woman = aliases[letters]
        return caste, woman, script_of(raw)
    if not re.sub(r"[\s.*…_\-]", "", raw or ""):
        return "NONE", 0, script_of(raw or "")
    return None


def layout_2010(table):
    """Identify one of the source's three 2010 table layouts."""
    if not table:
        return None
    width = max(len(row) for row in table)
    if width == 4:
        return "combined_single"
    if width == 6:
        return "combined_three_flags"
    if width != 5:
        return None
    first = [clean(cell).lower() for cell in table[0]]
    first += [""] * (5 - len(first))
    if "reserv" in first[3] and not first[4]:
        return "combined_two_flags"
    return "split_single"


def reservation_from_flags(raw_values, categories):
    """Combine separately printed caste and women dummy columns."""
    caste = "NONE"
    woman = 0
    unknown = []
    for raw, category in zip(raw_values, categories, strict=True):
        if not re.sub(r"[\s.*…_\-]", "", raw or ""):
            continue
        parsed = normalize_reservation(raw)
        if not parsed:
            unknown.append(raw)
            continue
        found_caste, found_woman, _ = parsed
        if category == "woman":
            if found_woman:
                woman = 1
            else:
                unknown.append(raw)
        elif found_caste == category:
            caste = category
        else:
            unknown.append(raw)
    if unknown:
        return None, unknown
    return (caste, woman, script_of(*raw_values)), []


def carry(values, index, current):
    """Read a column that is only printed on the first row of each group.

    Header text must be rejected *here*, not when the row is emitted. The
    header row is read before the guard sees it, so its text lands in the
    carried-forward variable and every subsequent row inherits it - which is
    how 1,398 J&K 2018 rows ended up in a district called "Name of District"
    even with a guard on the emit.
    """
    if index is None or index >= len(values):
        return current
    value = values[index]
    if not value or emit.is_header_text(value):
        return current
    return value


def map_columns(table_rows):
    """Locate each field by reading the header, not by fixed index.

    2016 alone ships three layouts - 15, 16 and 18 columns - and they disagree
    on where everything sits. Doda leads with the district, Kathua leads with a
    serial number, Batote puts the block second. Hard-coding indices read the
    serial number as the district and produced 33 districts for a state that
    has 22.

    Headers wrap across two or three rows, so the first few rows are joined
    column-wise before matching.
    """

    # A spanning title row ("Pyt-wise/Block-wise Reservation of SC/ST/Women
    # Panches & Sarpanches...") occupies column 0 with every other cell empty.
    # Joining it into the header puts "reserv" and "sc" in column 0, so the
    # serial-number column gets mapped as the reservation column. Only rows
    # with several filled cells are real header rows.
    def is_number_row(row):
        """The row of column numbers ("2 3 4 5 ...") sits under the header and
        would otherwise be joined into it, leaving every header ending in a
        digit so that suffix matches like "...sc" never fire.
        """
        filled = [clean(c) for c in row if clean(c)]
        return bool(filled) and all(c.isdigit() for c in filled)

    # The numeric row is not just noise to skip - it marks where the header
    # ends. Without that boundary the first data row gets joined in as header
    # ("... of panch sc 90"), and then no suffix match fires.
    boundary = next((i for i, r in enumerate(table_rows[:8]) if is_number_row(r)), None)
    limit = boundary if boundary is not None else 4

    def is_header_row(row):
        filled = [clean(cell).lower() for cell in row if clean(cell)]
        if len(filled) < 3:
            return False
        words = " ".join(filled)
        header_words = (
            "reserv",
            "district",
            "block",
            "panchayat",
            "panch ward",
            "panch constituenc",
            "panches",
            "population",
            "category",
            "constituenc",
            "halqa",
            "percentage",
            "%age",
        )
        subheaders = {
            "sc",
            "st",
            "oc",
            "ot",
            "other",
            "total",
            "ofsc",
            "ofst",
            "ofother",
        }
        normalized = {re.sub(r"[^a-z]+", "", value) for value in filled}
        return any(word in words for word in header_words) or normalized <= subheaders

    candidates = [
        i for i in range(min(limit, len(table_rows))) if is_header_row(table_rows[i])
    ]
    header_rows = [table_rows[i] for i in candidates]
    if not header_rows:
        return None
    header_depth = (
        (boundary + 1)
        if boundary is not None
        else ((candidates[-1] + 1) if candidates else 0)
    )
    width = max(len(r) for r in header_rows)
    joined = []
    for i in range(width):
        parts = [clean(r[i]) for r in header_rows if i < len(r)]
        joined.append(" ".join(p for p in parts if p).lower())
    compact = [re.sub(r"[^a-z0-9%]+", "", head) for head in joined]

    if not any("reserv" in h for h in joined):
        return None

    def find(*needles, exclude=()):
        for i, head in enumerate(compact):
            if any(n in head for n in needles) and not any(x in head for x in exclude):
                return i
        return None

    reservations = [i for i, h in enumerate(joined) if "reserv" in h]

    ward_no = find(
        "constituencyno",
        "constiuencyno",
        "constituencynumber",
        "wardno",
        "panchno",
    )
    ward_name = find(
        "constituencyname", "wardname", "panchname", exclude=("panchayat",)
    )
    ward_combined = False
    if ward_no is None:
        ward_hint = find(
            "numberandnameofpanch",
            "numbernameofpanch",
            "noandnameofpanch",
            "nonameofpanch",
            "noandname",
        )
        area = find("areaincluded", "village", "mohallaincluded")
        if ward_hint is not None:
            if area == ward_hint + 1 and ward_hint > 0 and not compact[ward_hint - 1]:
                # Udhampur's spanning label is attached to the name column;
                # the number is the blank-labelled column immediately before.
                ward_no, ward_name = ward_hint - 1, ward_hint
            elif area == ward_hint + 1:
                # Gool prints number and name in one cell ("I. Soker").
                ward_no = ward_name = ward_hint
                ward_combined = True
            else:
                # Doda, Batote and Jammu split a spanning label over two cells.
                ward_no, ward_name = ward_hint, ward_hint + 1

    halqa_no = find("pytno", "panchayatno", "halqano")
    halqa = find(
        "halqa",
        "panchayatname",
        "pytname",
        "nameofhalqua",
        "nameofpanchayat",
        "nameofthepanchayat",
    )
    if halqa is not None and (
        "noandname" in compact[halqa] or "nonameofhalqa" in compact[halqa]
    ):
        halqa_no = halqa
        halqa += 1
    mapping = {
        "district": find("districtname", "district", exclude=("districtno",)),
        "block": find("blockname", "nameofblock", "block", exclude=("blockno",)),
        "block_no": find("blockno"),
        "halqa_no": halqa_no,
        "halqa": halqa,
        "ward_no": ward_no,
        "ward_name": ward_name,
        "ward_combined": ward_combined,
        # first reservation column is the panch ward, second the sarpanch
        "ward_res": reservations[0] if reservations else None,
        "sarpanch_res": reservations[1] if len(reservations) > 1 else None,
        # The population block is a sub-header "SC | ST | OC | Total", but each
        # cell joins with its group title ("Category wise population ... SC"),
        # so an equality test never fires. Match the triple by suffix instead,
        # and take the first one - the second is the *percentage* block.
        "pop_sc": next(
            (
                i
                for i in range(len(joined) - 2)
                if compact[i].endswith("sc")
                and compact[i + 1].endswith("st")
                and compact[i + 2].endswith(("oc", "ot", "other"))
                and "%" not in joined[i]
                and "percent" not in joined[i]
                and "%age" not in joined[i]
            ),
            None,
        ),
    }
    mapping["header_depth"] = header_depth
    return mapping if mapping["ward_res"] is not None else None


def parse_mapped(path, year):
    """Read a document whose columns are located from its own header."""
    rows = []
    # 2010 names its files by block or tehsil and has no district column at all,
    # so the filename is the only place that information exists.
    district, block, halqa = "", path.stem.strip(), ""
    mapping = None
    with pdfplumber.open(str(path)) as pdf:
        for page in pdf.pages:
            district = district_from_title(page.extract_text() or "") or district
            for table in page.find_tables():
                extracted = [[clean(c) for c in r] for r in table.extract()]
                # Only the first page repeats the header. Recomputing the
                # mapping per table therefore returned None from page two
                # onwards and silently dropped every page but the first.
                found_here = map_columns(extracted)
                mapping = found_here or mapping
                if not mapping:
                    continue
                # drop the rows that *are* the header, or "Name of District"
                # ends up recorded as a district and the header's explanatory
                # sentence as a reservation value
                body = (
                    extracted[found_here["header_depth"] :] if found_here else extracted
                )
                for cells in body:

                    def cell(key):
                        i = mapping.get(key)
                        return cells[i] if i is not None and i < len(cells) else ""

                    # the district column often holds a serial number instead;
                    # only accept something with letters in it
                    found = cell("district")
                    if (
                        found
                        and re.search(r"[A-Za-z]{3}", found)
                        and not emit.is_header_text(found)
                    ):
                        district = found
                    for name, value in (
                        ("block", cell("block")),
                        ("halqa", cell("halqa")),
                    ):
                        if value and not emit.is_header_text(value):
                            if name == "block":
                                block = value
                            else:
                                halqa = value

                    ward_no, ward_name = cell("ward_no"), cell("ward_name")
                    if not ward_no or not re.match(r"^[IVXLC]+$|^\d+$", ward_no):
                        continue
                    base = {
                        "state": "Jammu & Kashmir",
                        "year": year,
                        "district": district,
                        "block": block,
                        "halqa": halqa,
                        "listing_scope": LISTING_SCOPE.get(year, "all_seats"),
                        "pop_sc": "",
                        "pop_st": "",
                        "pop_oc": "",
                        "pop_total": "",
                    }
                    sc = mapping.get("pop_sc")
                    if sc is not None and sc + 3 < len(cells):
                        base.update(
                            pop_sc=cells[sc],
                            pop_st=cells[sc + 1],
                            pop_oc=cells[sc + 2],
                            pop_total=cells[sc + 3],
                        )

                    for key, tier in (
                        ("ward_res", "ward"),
                        ("sarpanch_res", "sarpanch"),
                    ):
                        raw = cell(key)
                        parsed = normalize_reservation(raw)
                        if not parsed:
                            continue
                        caste, woman, script = parsed
                        rows.append(
                            emit.stamp(
                                dict(
                                    base,
                                    ward_no=ward_no if tier == "ward" else "",
                                    ward_name=ward_name if tier == "ward" else "",
                                    tier=canon.tier_of(tier, "Jammu & Kashmir"),
                                    tier_local=tier,
                                    reservation=label(caste, woman),
                                    caste_reservation=caste,
                                    woman_reserved=woman,
                                    reservation_raw=raw,
                                    script=script,
                                ),
                                path,
                                page.page_number,
                                ROOT,
                            )
                        )
    return rows


def parse_2016_records(records, diagnostics=None):
    """Parse 2016 page records without crossing the extraction boundary.

    Panchayat and block cells span several ward rows. PDF table extraction may
    attach a spanning cell to the middle row rather than the first, so rows are
    buffered to the printed ``Total`` boundary before the group identity is
    assigned. Streaming carry-forward would put the first half of a panchayat
    under the preceding panchayat while still producing plausible rows.
    """
    rows = []
    source_pdf = ""
    district = document_block_no = document_block = ""
    mapping = None
    group = None
    skipped_identity = collections.Counter()
    skipped_identity_groups = collections.Counter()

    def flush_group():
        nonlocal group
        if not group or not group["wards"]:
            group = None
            return

        if not (group["gp_no"] or group["halqa"]):
            for ward in group["wards"]:
                gp_no, halqa = recover_group_from_page_text(
                    ward["page_text"],
                    group["block"],
                    ward["ward_no"],
                    ward["ward_name"],
                )
                if gp_no or halqa:
                    group["gp_no"] = gp_no
                    group["halqa"] = halqa
                    group["gp_identity_from_page_text"] = "1"
                    break

        if not (group["gp_no"] or group["halqa"]):
            skipped_identity[group["source_pdf"]] += len(group["wards"])
            skipped_identity_groups[group["source_pdf"]] += 1
            group = None
            return

        if not group["district"] or not group["block"]:
            group = None
            return

        base = {
            "state": "Jammu & Kashmir",
            "year": "2016",
            "district": group["district"],
            "district_declared": "",
            "block_no": group["block_no"],
            "block": group["block"],
            "gp_no": group["gp_no"],
            "halqa": group["halqa"],
            "gp_identity_from_page_text": group["gp_identity_from_page_text"],
            "listing_scope": LISTING_SCOPE["2016"],
        }
        for ward in group["wards"]:
            parsed = normalize_reservation(ward["ward_res"])
            if not parsed:
                continue
            caste, woman, script = parsed
            rows.append(
                emit.stamp(
                    dict(
                        base,
                        ward_no=ward["ward_no"],
                        ward_name=ward["ward_name"],
                        tier="gp_ward",
                        tier_local="ward",
                        reservation=label(caste, woman),
                        caste_reservation=caste,
                        woman_reserved=woman,
                        pop_sc=ward["pop_sc"],
                        pop_st=ward["pop_st"],
                        pop_oc=ward["pop_oc"],
                        pop_total=ward["pop_total"],
                        reservation_raw=ward["ward_res"],
                        script=script,
                    ),
                    ward["path"],
                    ward["source_page"],
                    ROOT,
                )
            )

        sarpanch = next(
            (
                ward
                for ward in group["wards"]
                if normalize_reservation(ward["sarpanch_res"])
            ),
            None,
        )
        if sarpanch:
            caste, woman, script = normalize_reservation(sarpanch["sarpanch_res"])
            rows.append(
                emit.stamp(
                    dict(
                        base,
                        ward_no="",
                        ward_name="",
                        tier="gp_head",
                        tier_local="sarpanch",
                        reservation=label(caste, woman),
                        caste_reservation=caste,
                        woman_reserved=woman,
                        pop_sc="",
                        pop_st="",
                        pop_oc="",
                        pop_total="",
                        reservation_raw=sarpanch["sarpanch_res"],
                        script=script,
                    ),
                    sarpanch["path"],
                    sarpanch["source_page"],
                    ROOT,
                )
            )
        group = None

    for record in records:
        if record["source_pdf"] != source_pdf:
            flush_group()
            source_pdf = record["source_pdf"]
            district = document_block_no = document_block = ""
            mapping = None

        district = district_from_title(record.get("page_text", "")) or district
        for table in record.get("tables", []):
            extracted = [[clean(cell) for cell in row] for row in table]
            found_here = map_columns(extracted)
            mapping = found_here or mapping
            if not mapping:
                continue
            body = extracted[found_here["header_depth"] :] if found_here else extracted
            for cells in body:

                def cell(key):
                    index = mapping.get(key)
                    return (
                        cells[index] if index is not None and index < len(cells) else ""
                    )

                if any(
                    re.sub(r"[^a-z]", "", value.lower()) == "total" for value in cells
                ):
                    flush_group()
                    continue

                ward_no = cell("ward_no")
                ward_name = cell("ward_name")
                if mapping.get("ward_combined"):
                    ward_no, ward_name = split_ward(ward_no)
                ward_no = clean_ward_no(ward_no)

                found_district = cell("district")
                if (
                    not district
                    and found_district
                    and re.search(r"[A-Za-z]{3}", found_district)
                ):
                    district = found_district
                found_block_no = cell("block_no")
                found_block = cell("block")
                found_gp_no = cell("halqa_no")
                embedded_no, found_halqa = split_numbered_name(cell("halqa"))
                found_gp_no = found_gp_no or embedded_no

                explicit_new_group = bool(
                    group
                    and group["wards"]
                    and (
                        (
                            found_block
                            and group["block"]
                            and found_block != group["block"]
                        )
                        or (
                            found_gp_no
                            and group["gp_no"]
                            and found_gp_no != group["gp_no"]
                        )
                        or (
                            found_halqa
                            and group["halqa"]
                            and found_halqa != group["halqa"]
                        )
                    )
                )
                if explicit_new_group:
                    flush_group()

                if group is None:
                    group = {
                        "district": district,
                        "block_no": found_block_no or document_block_no,
                        "block": found_block or document_block,
                        "gp_no": found_gp_no,
                        "halqa": found_halqa,
                        "gp_identity_from_page_text": "",
                        "source_pdf": source_pdf,
                        "wards": [],
                    }
                if found_block_no:
                    group["block_no"] = document_block_no = found_block_no
                if found_block and not emit.is_header_text(found_block):
                    group["block"] = document_block = found_block
                if found_gp_no:
                    group["gp_no"] = found_gp_no
                if found_halqa and not emit.is_header_text(found_halqa):
                    group["halqa"] = found_halqa

                if not ward_no:
                    continue

                population = mapping.get("pop_sc")
                pop = ["", "", "", ""]
                if population is not None and population + 3 < len(cells):
                    pop = cells[population : population + 4]
                group["wards"].append(
                    {
                        "ward_no": ward_no.upper(),
                        "ward_name": ward_name,
                        "ward_res": cell("ward_res"),
                        "sarpanch_res": cell("sarpanch_res"),
                        "pop_sc": pop[0],
                        "pop_st": pop[1],
                        "pop_oc": pop[2],
                        "pop_total": pop[3],
                        "page_text": record.get("page_text", ""),
                        "path": ROOT / record["source_path"],
                        "source_page": record["source_page"],
                    }
                )

    flush_group()
    if diagnostics is not None:
        diagnostics["skipped_identity_rows"] = dict(skipped_identity)
        diagnostics["skipped_identity_groups"] = dict(skipped_identity_groups)
    if skipped_identity:
        LOGGER.warning(
            "Groups without a recoverable panchayat identity were excluded",
            extra={
                "event": "groups_excluded_missing_identity",
                "year": "2016",
                "sources": dict(skipped_identity),
                "groups": dict(skipped_identity_groups),
                "rows": sum(skipped_identity.values()),
            },
        )
    return rows


def parse_2010_records(records):
    """Parse source-faithful 2010 page records without opening a PDF.

    Most held documents split ward number and ward name across two columns.
    Eleven use a clean four-column form with both values in one cell.  Both
    layouts are read here, after extraction, and every printed ward is kept.
    """
    rows = []
    source_pdf = ""
    district = block = halqa = ""
    district_declared = ""
    seen_sources = set()
    unknown_marks = collections.Counter()
    layout = None

    for record in records:
        if record["source_pdf"] != source_pdf:
            source_pdf = record["source_pdf"]
            if source_pdf in EXCLUDED_2010:
                continue
            path = ROOT / record["source_path"]
            block = block_from_filename(path)
            halqa = ""
            district = district_from_document(record.get("page_text", ""))
            district_declared = ""
            layout = None

        if source_pdf in EXCLUDED_2010:
            continue

        if not district:
            inferred = DISTRICT_OF_BLOCK.get(block.lower(), "")
            if inferred:
                district = inferred
                district_declared = "1"

        for table in record.get("tables", []):
            layout = layout_2010(table) or layout
            if not layout:
                continue
            for raw_cells in table:
                cells = [clean(cell) for cell in raw_cells]
                expected_width = {
                    "combined_single": 4,
                    "combined_three_flags": 6,
                    "combined_two_flags": 5,
                    "split_single": 5,
                }[layout]
                if len(cells) != expected_width:
                    continue
                if cells in (["1", "2", "3", "4"], ["1", "2", "3", "", "4"]):
                    continue

                halqa_index = 1
                ward_index = 2
                combined = layout != "split_single"
                if combined:
                    ward_no, ward_name = split_ward(cells[ward_index])
                else:
                    ward_no = clean(cells[ward_index])
                    ward_name = clean(cells[ward_index + 1])
                if not ward_no or not re.fullmatch(r"[IVXLC]+|\d+", ward_no, re.I):
                    continue

                # Rows of printed column numbers sit immediately under many
                # headers. They look like a ward until all cells are viewed.
                filled = [cell for cell in cells if cell]
                if filled and all(
                    re.fullmatch(r"[IVXLC\d\s]+", cell, re.I) for cell in filled
                ):
                    continue

                found_halqa = cells[halqa_index]
                same_as_above = re.sub(r"[^a-z]", "", found_halqa.lower()) == "do"
                if (
                    found_halqa
                    and not same_as_above
                    and not emit.is_header_text(found_halqa)
                ):
                    halqa = found_halqa
                if not halqa:
                    continue

                if layout == "combined_three_flags":
                    raw_values = [(raw_cells[index] or "") for index in (3, 4, 5)]
                    reservation_raw = json.dumps(raw_values, ensure_ascii=False)
                    parsed, unknown = reservation_from_flags(
                        raw_values, ("SC", "ST", "woman")
                    )
                elif layout == "combined_two_flags":
                    raw_values = [(raw_cells[index] or "") for index in (3, 4)]
                    reservation_raw = json.dumps(raw_values, ensure_ascii=False)
                    parsed, unknown = reservation_from_flags(
                        raw_values, ("ST", "woman")
                    )
                else:
                    reservation_index = 3 if layout == "combined_single" else 4
                    reservation_raw = raw_cells[reservation_index] or ""
                    parsed = normalize_2010_reservation(reservation_raw)
                    unknown = [] if parsed else [reservation_raw]
                if not parsed:
                    for value in unknown:
                        unknown_marks[clean(value)] += 1
                    continue
                caste, woman, script = parsed
                path = ROOT / record["source_path"]
                rows.append(
                    emit.stamp(
                        {
                            "state": "Jammu & Kashmir",
                            "year": "2010",
                            "district": district,
                            "district_declared": district_declared,
                            "block": block,
                            "halqa": halqa,
                            "ward_no": ward_no.upper(),
                            "ward_name": ward_name,
                            "tier": "gp_ward",
                            "tier_local": "ward",
                            "reservation": label(caste, woman),
                            "caste_reservation": caste,
                            "woman_reserved": woman,
                            "listing_scope": LISTING_SCOPE["2010"],
                            "pop_sc": "",
                            "pop_st": "",
                            "pop_oc": "",
                            "pop_total": "",
                            "reservation_raw": reservation_raw,
                            "script": script,
                        },
                        path,
                        record["source_page"],
                        ROOT,
                    )
                )
                seen_sources.add(source_pdf)

    if unknown_marks:
        LOGGER.warning(
            "Unrecognized reservation marks",
            extra={
                "event": "reservation_marks_unrecognized",
                "year": "2010",
                "marks": dict(unknown_marks),
                "rows": sum(unknown_marks.values()),
            },
        )
    return rows, seen_sources, unknown_marks


def fill_place(rows, path):
    """Give a document's rows the block and district the document itself names.

    2010's files have no district column at all and a block column that is
    printed on only a third of the rows, so both were left blank: 6,888 rows
    with no district and 5,104 with no block, out of 7,340. Neither is missing
    from the documents - the block is the filename and the district is in the
    title - so neither needed to stay blank.

    A value already read from the page always wins; this only fills what is
    empty.
    """
    if not rows:
        return
    block = block_from_filename(path)
    district = ""
    try:
        with pdfplumber.open(str(path)) as pdf:
            district = district_from_document(pdf.pages[0].extract_text() or "")
    except Exception:
        district = ""
    declared = ""
    if not district:
        district = DISTRICT_OF_BLOCK.get(block.lower(), "")
        declared = "1" if district else ""

    for row in rows:
        if not (row.get("block") or "").strip():
            row["block"] = block
        # A district read off the page still has to be a district. 344 rows
        # carried "vide Order No." - the tail of an order reference that landed
        # in the column - and it survived because it was not blank. The roster
        # is closed, so anything outside it is boilerplate, not a place.
        current = (row.get("district") or "").strip()
        if current and not any(current.lower() == d.lower() for d in DISTRICT_ROSTER):
            current = ""
        if not current:
            row["district"] = district
            row["district_declared"] = declared
        else:
            row["district"] = current


def parse_generic(path, year, layout):
    """2010 and 2018: one reservation column, ward tier only.

    `layout` gives the column index of each field; -1 means the field is not
    printed and has to come from the page title.
    """
    rows = []
    district = block = halqa = ""
    with pdfplumber.open(str(path)) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            district = district_from_title(text) or district
            for table in page.find_tables():
                for raw in table.extract():
                    cells = [clean(c) for c in raw]
                    if len(cells) <= layout["reservation"]:
                        continue
                    district = carry(cells, layout.get("district"), district)
                    block = carry(cells, layout.get("block"), block)
                    halqa = carry(cells, layout.get("halqa"), halqa)
                    ward_no = cells[layout["ward_no"]]
                    ward_name = (
                        cells[layout["ward_name"]]
                        if layout.get("ward_name") is not None
                        else ""
                    )
                    parsed = normalize_reservation(cells[layout["reservation"]])
                    if not parsed or not ward_no:
                        continue
                    caste, woman, script = parsed
                    rows.append(
                        emit.stamp(
                            {
                                "state": "Jammu & Kashmir",
                                "year": year,
                                "district": district,
                                "block": block,
                                "halqa": halqa,
                                "ward_no": ward_no,
                                "ward_name": ward_name,
                                "tier": "gp_ward",
                                "tier_local": "ward",
                                "reservation": label(caste, woman),
                                "caste_reservation": caste,
                                "woman_reserved": woman,
                                "listing_scope": LISTING_SCOPE.get(year, "all_seats"),
                                "pop_sc": "",
                                "pop_st": "",
                                "pop_oc": "",
                                "pop_total": "",
                                "reservation_raw": cells[layout["reservation"]],
                                "script": script,
                            },
                            path,
                            page.page_number,
                            ROOT,
                        )
                    )
    return rows


LAYOUTS = {
    # S.No | Halqa | Panch no | Panch name | Reservation
    "2010": {"halqa": 1, "ward_no": 2, "ward_name": 3, "reservation": 4},
    # District no | District | Block no | Block | Halqa no | Halqa | Panch no |
    # Panch name | Reservation
    "2018": {
        "district": 1,
        "block": 3,
        "halqa": 5,
        "ward_no": 6,
        "ward_name": 7,
        "reservation": 8,
    },
}


@command("parse", state="Jammu and Kashmir")
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", action="append", choices=["2010", "2016", "2018"])
    args = ap.parse_args()
    years = args.year or ["2010", "2016", "2018"]

    for year in years:
        directory = JK / year
        if not directory.exists():
            continue
        rows, empty, failed = [], [], []
        if year == "2010":
            records = extract_2010.load()
            rows, seen_sources, _ = parse_2010_records(records)
            empty = sorted(
                path.name
                for path in directory.glob("*.pdf")
                if path.name not in seen_sources
            )
            counts = collections.Counter(row["source_pdf"] for row in rows)
            for source_file, source_rows in sorted(counts.items()):
                LOGGER.info(
                    "Source parsed",
                    extra={
                        "event": "source_parsed",
                        "source_file": source_file,
                        "year": year,
                        "source_rows": source_rows,
                        "rows": len(rows),
                    },
                )
        elif year == "2016":
            rows = parse_2016_records(extract_2016.load())
            counts = collections.Counter(row["source_pdf"] for row in rows)
            empty = sorted(
                path.name for path in directory.glob("*.pdf") if path.name not in counts
            )
            for source_file, source_rows in sorted(counts.items()):
                LOGGER.info(
                    "Source parsed",
                    extra={
                        "event": "source_parsed",
                        "source_file": source_file,
                        "year": year,
                        "source_rows": source_rows,
                        "rows": len(rows),
                    },
                )
        else:
            for path in sorted(directory.glob("*.pdf")):
                try:
                    got = parse_mapped(path, year)
                    if not got and year in LAYOUTS:
                        # fall back to fixed indices for the years whose tables
                        # carry no usable header
                        got = parse_generic(path, year, LAYOUTS[year])
                except Exception as exc:
                    failed.append((path.name, type(exc).__name__))
                    got = []
                if not got:
                    empty.append(path.name)
                fill_place(got, path)
                rows += got
                LOGGER.info(
                    "Source parsed",
                    extra={
                        "event": "source_parsed",
                        "source_file": path.name,
                        "year": year,
                        "source_rows": len(got),
                        "rows": len(rows),
                    },
                )

        by_tier = collections.defaultdict(list)
        for row in rows:
            by_tier[row["tier_local"]].append(row)
        for tier, subset in sorted(by_tier.items()):
            stem = JK / f"{tier}_reservation_{year}"
            csv_path, _ = emit.write(subset, stem, COLUMNS)
            women = sum(r["woman_reserved"] for r in subset)
            districts = {r["district"] for r in subset if r["district"]}
            print(
                f"{year} {tier:9s} {len(subset):6d} seats  "
                f"{len(districts):2d} districts  "
                f"women {women / max(len(subset), 1) * 100:4.1f}%  "
                f"-> {csv_path.name}"
            )
        if empty:
            print(
                f"     no rows from {len(empty)} of "
                f"{len(list(directory.glob('*.pdf')))} files"
            )
        if failed:
            print(f"     unreadable: {failed[:4]}")


if __name__ == "__main__":
    main()
