"""Parse the reviewed Assam 2025 extraction into complete seat tables.

The parser consumes JSONL written by :mod:`extract_2025`; it never opens a PDF.
Charaideo supplies a complete GP summary and lists reserved seats. Kamrup
Metropolitan supplies a complete row for every office and ward. Both become
district-aware left tables and complete seat universes.
"""

import collections
import json

from local_elections.common import emit
from local_elections.common.normalize import label, script_of
from local_elections.common.runlog import command, get_logger
from local_elections.paths import ROOT
from local_elections.states.assam import (
    controls_2025,
    extract_2025,
    parse_scan_2025,
)

LOGGER = get_logger(__name__)

DATA = ROOT / "data" / "assam"
SOURCE = extract_2025.SOURCE
ARCHIVE = emit.archived(SOURCE.parent)
SOURCES = {
    "Charaideo": extract_2025.SOURCE,
    "Kamrup Metropolitan": extract_2025.KAMRUP_METROPOLITAN_SOURCE,
}

ROSTER_COLUMNS = [
    "state",
    "year",
    "district",
    "block",
    "zilla_parishad_constituency",
    "gram_panchayat",
    "serial",
    "ward_count",
    "sc_reserved_ward_count",
    "st_reserved_ward_count",
    "women_reserved_ward_count",
    "women_reserved_wards",
    "sc_women_wards",
    "st_women_wards",
    "sc_open_wards",
    "st_open_wards",
    "count_basis",
    "script",
]
SEAT_COLUMNS = [
    "state",
    "year",
    "district",
    "block",
    "body",
    "gram_panchayat",
    "ward_no",
    "ward_name",
    "tier",
    "tier_local",
    "reservation",
    "caste_reservation",
    "woman_reserved",
    "reservation_raw",
    "listing_scope",
    "script",
    "sc_reserved_ward_count",
    "st_reserved_ward_count",
    "women_reserved_ward_count",
]
DIAGNOSTIC_COLUMNS = [
    "kind",
    "office",
    "reason",
    "gp_serial",
    "anchalik_panchayat_raw",
    "anchalik_panchayat",
    "gram_panchayat_raw",
    "gram_panchayat",
    "reservation_raw",
]

TIER_LOCAL = {
    "gp_ward": "Gaon Panchayat Ward Member",
    "gp_head": "Gaon Panchayat President",
    "gp_vice_head": "Gaon Panchayat Vice-President",
    "block_member": "Anchalik Panchayat Member",
    "block_head": "Anchalik Panchayat President",
    "block_vice_head": "Anchalik Panchayat Vice-President",
    "zp_member": "Zilla Parishad Member",
}


def _load(path):
    if not path.exists():
        raise RuntimeError(f"missing extraction {path}; run make assam-2025-extract")
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def extracted():
    """Return the reviewed Charaideo extraction."""
    return _load(extract_2025.GP_ROSTER), _load(extract_2025.OFFICE_ASSIGNMENTS)


def kamrup_metropolitan_extracted():
    """Return the Kamrup Metropolitan roster, offices, and wards."""
    return (
        _load(extract_2025.KAMRUP_METROPOLITAN_GP_ROSTER),
        _load(extract_2025.KAMRUP_METROPOLITAN_OFFICES),
        _load(extract_2025.KAMRUP_METROPOLITAN_WARDS),
    )


def _stamp(row, page, district="Charaideo", source=None):
    return emit.stamp(
        row,
        source or SOURCES[district],
        page,
        root=ROOT,
        archive=ARCHIVE,
    )


def roster_rows(records):
    """One row per GP: the complete left table requested by the source."""
    rows = []
    for record in records:
        row = {
            "state": "Assam",
            "year": 2025,
            "district": record["district"],
            "block": record["anchalik_panchayat"],
            "zilla_parishad_constituency": record["zilla_parishad_constituency"],
            "gram_panchayat": record["gram_panchayat"],
            "serial": record["serial"],
            "ward_count": record["ward_count"],
            "sc_reserved_ward_count": record["sc_reserved_ward_count"],
            "st_reserved_ward_count": record["st_reserved_ward_count"],
            "women_reserved_ward_count": len(record["women_reserved_wards"]),
            "women_reserved_wards": ",".join(map(str, record["women_reserved_wards"])),
            "sc_women_wards": ",".join(map(str, record["sc_women_wards"])),
            "st_women_wards": ",".join(map(str, record["st_women_wards"])),
            "sc_open_wards": ",".join(map(str, record["sc_open_wards"])),
            "st_open_wards": ",".join(map(str, record["st_open_wards"])),
            "count_basis": "printed_gp_summary",
            "script": "latin",
        }
        rows.append(_stamp(row, record["source_page"], record["district"]))
    return rows


def _base(
    tier,
    *,
    district="Charaideo",
    block="",
    body="",
    gp="",
    ward_no: str | int = "",
    ward_name="",
):
    return {
        "state": "Assam",
        "year": 2025,
        "district": district,
        "block": block,
        "body": body,
        "gram_panchayat": gp,
        "ward_no": ward_no,
        "ward_name": ward_name,
        "tier": tier,
        "tier_local": TIER_LOCAL[tier],
        "listing_scope": "all_seats",
        "script": "latin",
    }


def _reserve(row, caste, woman, raw, page, source=None):
    row.update(
        {
            "reservation": label(caste, woman),
            "caste_reservation": caste,
            "woman_reserved": woman,
            "reservation_raw": raw,
        }
    )
    return _stamp(row, page, row["district"], source)


def ward_rows(records):
    """All 360 GP wards, including the identifiable unreserved complement."""
    rows = []
    for record in records:
        women = set(record["women_reserved_wards"])
        caste_women = {
            **dict.fromkeys(record["sc_women_wards"], "SC"),
            **dict.fromkeys(record["st_women_wards"], "ST"),
        }
        caste_open = {
            **dict.fromkeys(record["sc_open_wards"], "SC"),
            **dict.fromkeys(record["st_open_wards"], "ST"),
        }
        for ward in range(1, record["ward_count"] + 1):
            woman = int(ward in women)
            caste = caste_women.get(ward, caste_open.get(ward, "NONE"))
            if caste != "NONE":
                raw = f"Ward No. {ward} ({caste} {'Women' if woman else 'Open'})"
            elif woman:
                raw = "Reservation for Women"
            else:
                raw = ""
            row = _base(
                "gp_ward",
                block=record["anchalik_panchayat"],
                body=record["gram_panchayat"],
                gp=record["gram_panchayat"],
                ward_no=ward,
            )
            row.update(
                {
                    "sc_reserved_ward_count": record["sc_reserved_ward_count"],
                    "st_reserved_ward_count": record["st_reserved_ward_count"],
                    "women_reserved_ward_count": len(women),
                }
            )
            rows.append(_reserve(row, caste, woman, raw, record["source_page"]))
    return rows


def kamrup_metropolitan_roster_rows(gps, wards):
    """Build the 20-GP left table from the printed roster and ward rows."""
    by_gp = collections.defaultdict(list)
    for ward in wards:
        by_gp[(ward["anchalik_panchayat"], ward["gram_panchayat"])].append(ward)
    rows = []
    for record in gps:
        key = (record["anchalik_panchayat"], record["gram_panchayat"])
        gp_wards = by_gp[key]
        women = [ward for ward in gp_wards if ward["woman_reserved_raw"]]
        sc = [ward for ward in gp_wards if ward["caste_reservation_raw"] == "SC"]
        st = [ward for ward in gp_wards if ward["caste_reservation_raw"] == "ST"]
        row = {
            "state": "Assam",
            "year": 2025,
            "district": record["district"],
            "block": record["anchalik_panchayat"],
            "zilla_parishad_constituency": "",
            "gram_panchayat": record["gram_panchayat"],
            "serial": record["serial"],
            "ward_count": record["ward_count"],
            "sc_reserved_ward_count": len(sc),
            "st_reserved_ward_count": len(st),
            "women_reserved_ward_count": len(women),
            "women_reserved_wards": ",".join(str(ward["ward_no"]) for ward in women),
            "sc_women_wards": ",".join(
                str(ward["ward_no"]) for ward in sc if ward["woman_reserved_raw"]
            ),
            "st_women_wards": ",".join(
                str(ward["ward_no"]) for ward in st if ward["woman_reserved_raw"]
            ),
            "sc_open_wards": ",".join(
                str(ward["ward_no"]) for ward in sc if not ward["woman_reserved_raw"]
            ),
            "st_open_wards": ",".join(
                str(ward["ward_no"]) for ward in st if not ward["woman_reserved_raw"]
            ),
            "count_basis": "derived_from_complete_printed_ward_table",
            "script": "latin",
        }
        rows.append(_stamp(row, record["source_page"], record["district"]))
    return rows


def kamrup_metropolitan_ward_rows(records):
    """Parse the 200 explicitly labelled ward rows without opening the PDF."""
    rows = []
    counts = collections.defaultdict(lambda: collections.Counter())
    for record in records:
        key = (record["anchalik_panchayat"], record["gram_panchayat"])
        counts[key]["women"] += record["woman_reserved_raw"]
        counts[key][record["caste_reservation_raw"]] += 1
    for record in records:
        key = (record["anchalik_panchayat"], record["gram_panchayat"])
        row = _base(
            "gp_ward",
            district=record["district"],
            block=record["anchalik_panchayat"],
            body=record["gram_panchayat"],
            gp=record["gram_panchayat"],
            ward_no=record["ward_no"],
            ward_name=record["village_name_raw"],
        )
        row.update(
            {
                "sc_reserved_ward_count": counts[key]["SC"],
                "st_reserved_ward_count": counts[key]["ST"],
                "women_reserved_ward_count": counts[key]["women"],
            }
        )
        rows.append(
            _reserve(
                row,
                record["caste_reservation_raw"],
                record["woman_reserved_raw"],
                record["reservation_raw"],
                record["source_page"],
            )
        )
    return rows


def kamrup_metropolitan_office_rows(records):
    """Parse complete, explicitly labelled AP, GP, and ZP office tables."""
    rows_by_tier = collections.defaultdict(list)
    for record in records:
        tier = record["office"]
        block = record["anchalik_panchayat"]
        seat = record["seat"]
        if tier.startswith("gp_"):
            row = _base(
                tier,
                district=record["district"],
                block=block,
                body=seat,
                gp=seat,
            )
        elif tier == "block_member":
            row = _base(
                tier,
                district=record["district"],
                block=block,
                body=f"{block} Anchalik Panchayat",
                gp=seat,
            )
        elif tier.startswith("block_"):
            row = _base(
                tier,
                district=record["district"],
                block=block,
                body=f"{block} Anchalik Panchayat",
            )
        else:
            row = _base(
                tier,
                district=record["district"],
                body="Kamrup Metropolitan Zilla Parishad",
                ward_name=seat,
            )
        rows_by_tier[tier].append(
            _reserve(
                row,
                record["caste_reservation_raw"],
                record["woman_reserved_raw"],
                record["reservation_raw"],
                record["source_page"],
            )
        )
    return rows_by_tier


def scan_roster_rows(parsed):
    """Build a GP left table from one complete OCR ward table."""
    by_gp = collections.defaultdict(list)
    for ward in parsed["wards"]:
        by_gp[ward["gp_serial"]].append(ward)

    rows = []
    for gp in parsed["gps"]:
        wards = by_gp[gp["serial"]]
        women = [ward for ward in wards if ward["woman_reserved_raw"]]
        sc = [ward for ward in wards if ward["caste_reservation_raw"] == "SC"]
        st = [ward for ward in wards if ward["caste_reservation_raw"] == "ST"]
        row = {
            "state": "Assam",
            "year": 2025,
            "district": parsed["district"],
            "block": "",
            "zilla_parishad_constituency": "",
            "gram_panchayat": gp["gram_panchayat"],
            "serial": gp["serial"],
            "ward_count": len(wards),
            "sc_reserved_ward_count": len(sc),
            "st_reserved_ward_count": len(st),
            "women_reserved_ward_count": len(women),
            "women_reserved_wards": ",".join(str(ward["ward_no"]) for ward in women),
            "sc_women_wards": ",".join(
                str(ward["ward_no"]) for ward in sc if ward["woman_reserved_raw"]
            ),
            "st_women_wards": ",".join(
                str(ward["ward_no"]) for ward in st if ward["woman_reserved_raw"]
            ),
            "sc_open_wards": ",".join(
                str(ward["ward_no"]) for ward in sc if not ward["woman_reserved_raw"]
            ),
            "st_open_wards": ",".join(
                str(ward["ward_no"]) for ward in st if not ward["woman_reserved_raw"]
            ),
            "count_basis": "derived_from_complete_printed_ward_table",
            "script": "latin",
        }
        rows.append(
            _stamp(
                row,
                gp["source_page"],
                parsed["district"],
                parsed["source"],
            )
        )
    return rows


def reserved_scan_roster_rows(parsed):
    """Build a GP left table without inventing unprinted open wards."""
    by_gp = collections.defaultdict(list)
    for ward in parsed["wards"]:
        by_gp[ward["gp_serial"]].append(ward)

    rows = []
    for gp in parsed["gps"]:
        wards = by_gp[gp["serial"]]
        women = [ward for ward in wards if ward["woman_reserved_raw"]]
        sc = [ward for ward in wards if ward["caste_reservation_raw"] == "SC"]
        st = [ward for ward in wards if ward["caste_reservation_raw"] == "ST"]
        row = {
            "state": "Assam",
            "year": 2025,
            "district": parsed["district"],
            "block": gp["anchalik_panchayat"],
            "zilla_parishad_constituency": "",
            "gram_panchayat": gp["gram_panchayat"],
            "serial": gp["serial"],
            "ward_count": "",
            "sc_reserved_ward_count": len(sc),
            "st_reserved_ward_count": len(st),
            "women_reserved_ward_count": len(women),
            "women_reserved_wards": ",".join(str(ward["ward_no"]) for ward in women),
            "sc_women_wards": ",".join(
                str(ward["ward_no"]) for ward in sc if ward["woman_reserved_raw"]
            ),
            "st_women_wards": ",".join(
                str(ward["ward_no"]) for ward in st if ward["woman_reserved_raw"]
            ),
            "sc_open_wards": ",".join(
                str(ward["ward_no"]) for ward in sc if not ward["woman_reserved_raw"]
            ),
            "st_open_wards": ",".join(
                str(ward["ward_no"]) for ward in st if not ward["woman_reserved_raw"]
            ),
            "count_basis": "derived_from_printed_reserved_rows_only",
            "script": "latin",
        }
        rows.append(
            _stamp(
                row,
                gp["source_page"],
                parsed["district"],
                parsed["source"],
            )
        )
    return rows


def reserved_scan_rows(parsed):
    """Emit only the identifiable reserved rows printed in one scan."""
    rows_by_tier = collections.defaultdict(list)
    by_gp = collections.defaultdict(list)
    for ward in parsed["wards"]:
        by_gp[ward["gp_serial"]].append(ward)

    for record in parsed["wards"]:
        gp_wards = by_gp[record["gp_serial"]]
        row = _base(
            "gp_ward",
            district=parsed["district"],
            block=record["anchalik_panchayat"],
            body=record["gram_panchayat"],
            gp=record["gram_panchayat"],
            ward_no=record["ward_no"],
        )
        row["listing_scope"] = "reserved_only"
        row.update(
            {
                "sc_reserved_ward_count": sum(
                    ward["caste_reservation_raw"] == "SC" for ward in gp_wards
                ),
                "st_reserved_ward_count": sum(
                    ward["caste_reservation_raw"] == "ST" for ward in gp_wards
                ),
                "women_reserved_ward_count": sum(
                    ward["woman_reserved_raw"] for ward in gp_wards
                ),
            }
        )
        rows_by_tier["gp_ward"].append(
            _reserve(
                row,
                record["caste_reservation_raw"],
                record["woman_reserved_raw"],
                record["reservation_raw"],
                record["source_page"],
                parsed["source"],
            )
        )

    for record in parsed["offices"]:
        tier = record["office"]
        block = record["anchalik_panchayat"]
        if tier in {"gp_head", "gp_vice_head"}:
            row = _base(
                tier,
                district=parsed["district"],
                block=block,
                body=record["gram_panchayat"],
                gp=record["gram_panchayat"],
            )
        elif tier == "block_member":
            row = _base(
                tier,
                district=parsed["district"],
                block=block,
                body=f"{block} Anchalik Panchayat",
                gp=record["gram_panchayat"],
            )
        elif tier in {"block_head", "block_vice_head"}:
            row = _base(
                tier,
                district=parsed["district"],
                block=block,
                body=f"{block} Anchalik Panchayat",
            )
        else:
            row = _base(
                tier,
                district=parsed["district"],
                body=f"{parsed['district']} Zilla Parishad",
                ward_name=f"{record['seat_serial']} No. {record['seat']} ZPC",
            )
        row["listing_scope"] = "reserved_only"
        rows_by_tier[tier].append(
            _reserve(
                row,
                record["caste_reservation_raw"],
                record["woman_reserved_raw"],
                record["reservation_raw"],
                record["source_page"],
                parsed["source"],
            )
        )
    return rows_by_tier


def reserved_scan_diagnostics(parsed):
    """Attach source provenance to rejected or reconciled source readings."""
    return [
        _stamp(
            dict(record),
            record["source_page"],
            parsed["district"],
            parsed["source"],
        )
        for record in parsed.get("diagnostics", [])
    ]


def scan_rows(parsed):
    """Build complete canonical seat universes from one parsed OCR cache."""
    rows_by_tier = collections.defaultdict(list)
    by_gp = collections.defaultdict(list)
    for record in parsed["wards"]:
        by_gp[record["gp_serial"]].append(record)

    for record in parsed["wards"]:
        gp_wards = by_gp[record["gp_serial"]]
        row = _base(
            "gp_ward",
            district=parsed["district"],
            body=record["gram_panchayat"],
            gp=record["gram_panchayat"],
            ward_no=record["ward_no"],
            ward_name=record["ward_name"],
        )
        row["script"] = script_of(record["gram_panchayat"], record["ward_name"])
        row.update(
            {
                "sc_reserved_ward_count": sum(
                    ward["caste_reservation_raw"] == "SC" for ward in gp_wards
                ),
                "st_reserved_ward_count": sum(
                    ward["caste_reservation_raw"] == "ST" for ward in gp_wards
                ),
                "women_reserved_ward_count": sum(
                    ward["woman_reserved_raw"] for ward in gp_wards
                ),
            }
        )
        rows_by_tier["gp_ward"].append(
            _reserve(
                row,
                record["caste_reservation_raw"],
                record["woman_reserved_raw"],
                record["reservation_raw"],
                record["source_page"],
                parsed["source"],
            )
        )

    assignments = {
        (record["office"], record["gp_serial"]): record for record in parsed["offices"]
    }
    default_pages = {}
    for tier in ("block_member", "gp_head", "gp_vice_head"):
        pages = [
            record["source_page"]
            for record in parsed["offices"]
            if record["office"] == tier
        ]
        if not pages:
            raise ValueError(
                f"{parsed['district']} source contains no {tier} office assignment"
            )
        default_pages[tier] = pages[0]
    for tier in ("block_member", "gp_head", "gp_vice_head"):
        for gp in parsed["gps"]:
            assignment = assignments.get((tier, gp["serial"]))
            caste = assignment["caste_reservation_raw"] if assignment else "NONE"
            woman = assignment["woman_reserved_raw"] if assignment else 0
            raw = assignment["reservation_raw"] if assignment else ""
            page = assignment["source_page"] if assignment else default_pages[tier]
            gp_wards = by_gp[gp["serial"]]
            if tier == "block_member":
                row = _base(
                    tier,
                    district=parsed["district"],
                    gp=gp["gram_panchayat"],
                )
            else:
                row = _base(
                    tier,
                    district=parsed["district"],
                    body=gp["gram_panchayat"],
                    gp=gp["gram_panchayat"],
                )
            row.update(
                {
                    "sc_reserved_ward_count": sum(
                        ward["caste_reservation_raw"] == "SC" for ward in gp_wards
                    ),
                    "st_reserved_ward_count": sum(
                        ward["caste_reservation_raw"] == "ST" for ward in gp_wards
                    ),
                    "women_reserved_ward_count": sum(
                        ward["woman_reserved_raw"] for ward in gp_wards
                    ),
                }
            )
            rows_by_tier[tier].append(
                _reserve(
                    row,
                    caste,
                    woman,
                    raw,
                    page,
                    parsed["source"],
                )
            )

    for tier, reserved_key in (
        ("block_head", "block_head_reserved"),
        ("block_vice_head", "block_vice_reserved"),
    ):
        for block in parsed["blocks"]:
            woman = int(block == parsed[reserved_key])
            row = _base(
                tier,
                district=parsed["district"],
                block=block,
                body=f"{block} Anchalik Panchayat",
            )
            rows_by_tier[tier].append(
                _reserve(
                    row,
                    "NONE",
                    woman,
                    "Women" if woman else "",
                    1,
                    parsed["source"],
                )
            )

    for number in range(1, parsed["zp_total"] + 1):
        name = parsed["reserved_zps"].get(number)
        woman = int(name is not None)
        seat = f"{number} No. {name} ZPC" if name else f"{number} No. ZPC"
        row = _base(
            "zp_member",
            district=parsed["district"],
            body=f"{parsed['district']} Zilla Parishad",
            ward_name=seat,
        )
        rows_by_tier["zp_member"].append(
            _reserve(
                row,
                "NONE",
                woman,
                "Women" if woman else "",
                1,
                parsed["source"],
            )
        )
    return rows_by_tier


def _assignments(records):
    index = {}
    for record in records:
        key = (
            record["office"],
            record["anchalik_panchayat"],
            record["seat"],
        )
        if key in index:
            raise RuntimeError(f"duplicate explicit Assam office assignment: {key}")
        index[key] = record
    return index


def office_rows(gps, assignments):
    """Complete office universes, using explicit reservations plus complements."""
    index = _assignments(assignments)
    by_block = collections.defaultdict(list)
    for gp in gps:
        by_block[gp["anchalik_panchayat"]].append(gp)

    universes = {
        "gp_head": [(gp["anchalik_panchayat"], gp["gram_panchayat"], gp) for gp in gps],
        "gp_vice_head": [
            (gp["anchalik_panchayat"], gp["gram_panchayat"], gp) for gp in gps
        ],
        "block_member": [
            (gp["anchalik_panchayat"], gp["gram_panchayat"], gp) for gp in gps
        ],
        "block_head": [(block, block, None) for block in by_block],
        "block_vice_head": [(block, block, None) for block in by_block],
        "zp_member": [
            ("", zpc, None)
            for zpc in dict.fromkeys(gp["zilla_parishad_constituency"] for gp in gps)
        ],
    }
    default_page = {
        "zp_member": 2,
        "block_head": 5,
        "block_vice_head": 5,
        "gp_head": 7,
        "gp_vice_head": 7,
    }
    rows_by_tier = collections.defaultdict(list)
    for tier, seats in universes.items():
        for block, seat, gp_record in seats:
            assignment = index.get((tier, block, seat))
            caste = assignment["caste_reservation_raw"] if assignment else "NONE"
            woman = assignment["woman_reserved_raw"] if assignment else 0
            raw = assignment["reservation_raw"] if assignment else ""
            if tier.startswith("gp_"):
                row = _base(tier, block=block, body=seat, gp=seat)
            elif tier == "block_member":
                row = _base(
                    tier,
                    block=block,
                    body=f"{block} Anchalik Panchayat",
                    gp=seat,
                )
            elif tier.startswith("block_"):
                row = _base(
                    tier,
                    block=block,
                    body=f"{block} Anchalik Panchayat",
                )
            else:
                row = _base(
                    tier,
                    body="Charaideo Zilla Parishad",
                    ward_name=seat,
                )
            if gp_record:
                row.update(
                    {
                        "sc_reserved_ward_count": gp_record["sc_reserved_ward_count"],
                        "st_reserved_ward_count": gp_record["st_reserved_ward_count"],
                        "women_reserved_ward_count": len(
                            gp_record["women_reserved_wards"]
                        ),
                    }
                )
            page = (
                assignment["source_page"]
                if assignment
                else (
                    3
                    if tier == "block_member" and block in {"Sonari", "Sapekhati"}
                    else 4
                    if tier == "block_member"
                    else default_page[tier]
                )
            )
            rows_by_tier[tier].append(_reserve(row, caste, woman, raw, page))
    return rows_by_tier


def build_rows():
    gps, assignments = extracted()
    roster = roster_rows(gps)
    rows = office_rows(gps, assignments)
    rows["gp_ward"] = ward_rows(gps)
    kamrup_gps, kamrup_offices, kamrup_wards = kamrup_metropolitan_extracted()
    roster.extend(kamrup_metropolitan_roster_rows(kamrup_gps, kamrup_wards))
    kamrup_rows = kamrup_metropolitan_office_rows(kamrup_offices)
    kamrup_rows["gp_ward"] = kamrup_metropolitan_ward_rows(kamrup_wards)
    for tier, tier_rows in kamrup_rows.items():
        rows[tier].extend(tier_rows)
    for parsed in parse_scan_2025.cached_extractions():
        if parsed["listing_scope"] == "reserved_only":
            roster.extend(reserved_scan_roster_rows(parsed))
            parsed_rows = reserved_scan_rows(parsed)
        else:
            roster.extend(scan_roster_rows(parsed))
            parsed_rows = scan_rows(parsed)
        for tier, tier_rows in parsed_rows.items():
            rows[tier].extend(tier_rows)
    return roster, rows


@command("parse", state="Assam", source_id="assam_sec_pri_reservation_2025")
def main():
    extract_2025.verify_source()
    roster, rows_by_tier = build_rows()
    emit.write(roster, DATA / "gp_roster_2025", ROSTER_COLUMNS)
    diagnostics = []
    for parsed in parse_scan_2025.cached_extractions():
        diagnostics.extend(reserved_scan_diagnostics(parsed))
    emit.write(
        diagnostics,
        DATA / "2025_extracted" / "scan_parse_diagnostics",
        DIAGNOSTIC_COLUMNS,
    )
    for tier, expected in controls_2025.TOTAL_EXPECTED_ROWS.items():
        rows = rows_by_tier[tier]
        if len(rows) != expected:
            raise RuntimeError(f"{tier}: parsed {len(rows)} rows; expected {expected}")
        emit.write(rows, DATA / f"{tier}_reservation_2025", SEAT_COLUMNS)
        LOGGER.info(
            "Assam tier parsed",
            extra={
                "event": "tier_parsed",
                "district": "multiple",
                "tier": tier,
                "rows": len(rows),
            },
        )
    total = sum(map(len, rows_by_tier.values()))
    print(f"Assam 2025: {len(roster)} GPs and {total} stated seat rows")


if __name__ == "__main__":
    main()
