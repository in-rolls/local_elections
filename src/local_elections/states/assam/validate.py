"""Validate Assam's parsed municipal and rural reservation sources."""

import collections
import csv
import sys

from local_elections.common import checks, validation
from local_elections.common import harvest as source_harvest
from local_elections.common.runlog import command
from local_elections.paths import ROOT
from local_elections.states.assam import (
    controls_2025,
    delimitation_2024,
    harvest,
    parse,
    parse_2025,
)

DATA = ROOT / "data" / "assam"
PRINTED_BOARDS = 81
PRINTED_WARDS = 1004
PRINTED_RESERVED_HEADS = 46

PRI_KEYS = {
    "gp_ward": (
        "state",
        "year",
        "tier",
        "district",
        "block",
        "gram_panchayat",
        "ward_no",
    ),
    "gp_head": ("state", "year", "tier", "district", "block", "gram_panchayat"),
    "gp_vice_head": ("state", "year", "tier", "district", "block", "gram_panchayat"),
    "block_member": ("state", "year", "tier", "district", "block", "gram_panchayat"),
    "block_head": ("state", "year", "tier", "district", "block"),
    "block_vice_head": ("state", "year", "tier", "district", "block"),
    "zp_member": ("state", "year", "tier", "district", "ward_name"),
}


def load(name):
    path = DATA / name
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def validate_2025(report):
    """Apply district source controls and hierarchy contracts."""
    parse_2025.extract_2025.verify_source()
    report.section("Charaideo 2025 GP universe")
    all_roster = load("gp_roster_2025.csv")
    roster = [row for row in all_roster if row["district"] == "Charaideo"]
    report.check(
        len(roster) == 36,
        "all GPs from the page-9 left table are present",
        f"{len(roster)} of 36",
    )
    if not roster:
        return

    gp_keys = {(row["block"], row["gram_panchayat"]) for row in roster}
    report.check(
        len(gp_keys) == len(roster),
        "GP keys are unique within Anchalik Panchayat",
        f"{len(gp_keys)} unique keys",
    )
    by_block = collections.Counter(row["block"] for row in roster)
    report.check(
        by_block == collections.Counter(controls_2025.BLOCK_GP_COUNTS),
        "the four AP-level GP counts match the notification",
        str(dict(by_block)),
    )
    combinations = collections.Counter(
        (int(row["sc_reserved_ward_count"]), int(row["st_reserved_ward_count"]))
        for row in roster
    )
    report.check(
        combinations
        == collections.Counter(
            {(0, 0): 28, (0, 1): 5, (0, 2): 1, (1, 0): 1, (2, 0): 1}
        ),
        "printed SC/ST count combinations are preserved, including zeroes and twos",
        str(dict(combinations)),
    )
    report.check(
        sum(int(row["sc_reserved_ward_count"]) for row in roster) == 3
        and sum(int(row["st_reserved_ward_count"]) for row in roster) == 7,
        "GP-level caste counts reconcile to the printed ward totals",
        "SC=3, ST=7",
    )
    report.check(
        {int(row["ward_count"]) for row in roster} == {10}
        and {int(row["women_reserved_ward_count"]) for row in roster} == {5},
        "every GP has ten wards and five women-reserved wards",
        "ward_count=10; women_reserved_ward_count=5",
    )

    report.section("Charaideo 2025 complete seat tables")
    rows_by_tier = {}
    for tier, expected in controls_2025.TOTAL_EXPECTED_ROWS.items():
        rows_by_tier[tier] = validation.apply(
            report,
            validation.DatasetExpectation(
                path=DATA / f"{tier}_reservation_2025.csv",
                state="Assam",
                year="2025",
                tier=tier,
                key=PRI_KEYS[tier],
                expected_rows=expected,
            ),
            ROOT,
        )

    for tier, rows in rows_by_tier.items():
        if not rows:
            continue
        district_rows = [row for row in rows if row["district"] == "Charaideo"]
        got = collections.Counter(
            (row["caste_reservation"], int(row["woman_reserved"]))
            for row in district_rows
        )
        report.check(
            got == controls_2025.CATEGORY_COUNTS[tier],
            f"{tier} category vector matches the printed controls",
            str(dict(got)),
        )
        report.check(
            {row["listing_scope"] for row in district_rows} == {"all_seats"},
            f"{tier} includes its complete stated seat universe",
            "listing_scope=all_seats",
        )

    wards = [
        row for row in rows_by_tier.get("gp_ward", []) if row["district"] == "Charaideo"
    ]
    ward_sets = collections.defaultdict(set)
    for row in wards:
        ward_sets[(row["block"], row["gram_panchayat"])].add(int(row["ward_no"]))
    report.check(
        set(ward_sets) == gp_keys
        and all(wards == set(range(1, 11)) for wards in ward_sets.values()),
        "every roster GP joins to one complete 1-through-10 ward run",
        f"{len(ward_sets)} of {len(gp_keys)} GPs",
    )

    child_gp_keys = set()
    for tier in ("gp_ward", "gp_head", "gp_vice_head", "block_member"):
        child_gp_keys.update(
            (row["block"], row["gram_panchayat"])
            for row in rows_by_tier.get(tier, [])
            if row["district"] == "Charaideo"
        )
    report.check(
        child_gp_keys == gp_keys,
        "all GP-level and APC child rows join to the 36-GP left table",
        f"{len(child_gp_keys)} joined GP keys",
    )

    report.section("Kamrup Metropolitan 2025 GP universe")
    kamrup_roster = [
        row for row in all_roster if row["district"] == "Kamrup Metropolitan"
    ]
    report.check(
        len(kamrup_roster) == 20,
        "all GPs from the AP-member tables are present",
        f"{len(kamrup_roster)} of 20",
    )
    kamrup_gp_keys = {(row["block"], row["gram_panchayat"]) for row in kamrup_roster}
    report.check(
        len(kamrup_gp_keys) == len(kamrup_roster),
        "GP keys are unique within Anchalik Panchayat",
        f"{len(kamrup_gp_keys)} unique keys",
    )
    kamrup_by_block = collections.Counter(row["block"] for row in kamrup_roster)
    report.check(
        kamrup_by_block
        == collections.Counter(controls_2025.KAMRUP_METROPOLITAN_BLOCK_GP_COUNTS),
        "the three AP-level GP counts match the notification",
        str(dict(kamrup_by_block)),
    )
    report.check(
        {row["count_basis"] for row in kamrup_roster}
        == {"derived_from_complete_printed_ward_table"},
        "derived GP reservation counts are distinguished from printed summaries",
        "count_basis=derived_from_complete_printed_ward_table",
    )

    report.section("Kamrup Metropolitan 2025 complete seat tables")
    kamrup_by_tier = {
        tier: [row for row in rows if row["district"] == "Kamrup Metropolitan"]
        for tier, rows in rows_by_tier.items()
    }
    for tier, expected in controls_2025.KAMRUP_METROPOLITAN_EXPECTED_ROWS.items():
        rows = kamrup_by_tier[tier]
        report.check(
            len(rows) == expected,
            f"{tier} row count matches the complete printed table",
            f"{len(rows)} of {expected}",
        )
        got = collections.Counter(
            (row["caste_reservation"], int(row["woman_reserved"])) for row in rows
        )
        report.check(
            got == controls_2025.KAMRUP_METROPOLITAN_CATEGORY_COUNTS[tier],
            f"{tier} category vector matches the printed controls",
            str(dict(got)),
        )
        report.check(
            {row["listing_scope"] for row in rows} == {"all_seats"},
            f"{tier} includes every printed Unreserved and reserved row",
            "listing_scope=all_seats",
        )

    kamrup_wards = kamrup_by_tier["gp_ward"]
    kamrup_ward_sets = collections.defaultdict(set)
    for row in kamrup_wards:
        kamrup_ward_sets[(row["block"], row["gram_panchayat"])].add(int(row["ward_no"]))
    report.check(
        set(kamrup_ward_sets) == kamrup_gp_keys
        and all(wards == set(range(1, 11)) for wards in kamrup_ward_sets.values()),
        "every roster GP joins to one complete 1-through-10 ward run",
        f"{len(kamrup_ward_sets)} of {len(kamrup_gp_keys)} GPs",
    )
    report.check(
        all(row["ward_name"].strip() for row in kamrup_wards),
        "every ward retains its printed village-name cell",
        f"{sum(bool(row['ward_name'].strip()) for row in kamrup_wards)} of 200",
    )
    row_139 = next(
        row
        for row in kamrup_wards
        if row["gram_panchayat"] == "Sonapur" and row["ward_no"] == "9"
    )
    report.check(
        row_139["reservation_raw"] == "Unreserved" and row_139["source_page"] == "9",
        "the rendered-page review recovers ward 139 omitted by embedded text",
        "Sonapur ward 9 = Unreserved, page 9",
    )

    report.section("South Salmara-Mankachar 2025 GP universe")
    south_roster = [
        row for row in all_roster if row["district"] == "South Salmara-Mankachar"
    ]
    report.check(
        len(south_roster) == 35,
        "the complete women-ward table supplies all 35 GPs",
        f"{len(south_roster)} of 35",
    )
    south_gp_keys = {row["gram_panchayat"] for row in south_roster}
    report.check(
        len(south_gp_keys) == len(south_roster),
        "GP names are unique within the district notification",
        f"{len(south_gp_keys)} unique keys",
    )
    report.check(
        {row["block"] for row in south_roster} == {""},
        "GP-to-AP membership is left unset because this source does not print it",
        "block is blank",
    )
    south_combinations = collections.Counter(
        (int(row["sc_reserved_ward_count"]), int(row["st_reserved_ward_count"]))
        for row in south_roster
    )
    report.check(
        south_combinations == collections.Counter({(0, 0): 26, (1, 0): 7, (0, 1): 2}),
        "derived GP caste-count pairs retain every zero",
        str(dict(south_combinations)),
    )
    report.check(
        {int(row["ward_count"]) for row in south_roster} == {10}
        and {int(row["women_reserved_ward_count"]) for row in south_roster} == {5},
        "every GP has ten wards and five printed women-reserved wards",
        "ward_count=10; women_reserved_ward_count=5",
    )

    report.section("South Salmara-Mankachar 2025 complete seat tables")
    south_by_tier = {
        tier: [row for row in rows if row["district"] == "South Salmara-Mankachar"]
        for tier, rows in rows_by_tier.items()
    }
    for tier, expected in controls_2025.SOUTH_SALMARA_EXPECTED_ROWS.items():
        rows = south_by_tier[tier]
        report.check(
            len(rows) == expected,
            f"{tier} row count matches the source-defined universe",
            f"{len(rows)} of {expected}",
        )
        got = collections.Counter(
            (row["caste_reservation"], int(row["woman_reserved"])) for row in rows
        )
        report.check(
            got == controls_2025.SOUTH_SALMARA_CATEGORY_COUNTS[tier],
            f"{tier} category vector matches the printed controls",
            str(dict(got)),
        )
        report.check(
            {row["listing_scope"] for row in rows} == {"all_seats"},
            f"{tier} includes its complete source-defined seat universe",
            "listing_scope=all_seats",
        )

    south_wards = south_by_tier["gp_ward"]
    south_ward_sets = collections.defaultdict(set)
    for row in south_wards:
        south_ward_sets[row["gram_panchayat"]].add(int(row["ward_no"]))
    report.check(
        set(south_ward_sets) == south_gp_keys
        and all(wards == set(range(1, 11)) for wards in south_ward_sets.values()),
        "every GP joins to one complete 1-through-10 ward run",
        f"{len(south_ward_sets)} of {len(south_gp_keys)} GPs",
    )
    report.check(
        sum(bool(row["ward_name"].strip()) for row in south_wards) == 175,
        "all names printed for women-reserved wards are retained",
        "175 named wards",
    )

    report.section("Hailakandi 2025 reserved-seat tables")
    hailakandi_roster = [row for row in all_roster if row["district"] == "Hailakandi"]
    report.check(
        len(hailakandi_roster) == 62,
        "the printed reserved-ward rows identify all 62 GPs",
        f"{len(hailakandi_roster)} of 62",
    )
    hailakandi_gp_keys = {
        (row["block"], row["gram_panchayat"]) for row in hailakandi_roster
    }
    report.check(
        len(hailakandi_gp_keys) == len(hailakandi_roster),
        "GP keys are unique within Anchalik Panchayat",
        f"{len(hailakandi_gp_keys)} unique keys",
    )
    hailakandi_by_block = collections.Counter(row["block"] for row in hailakandi_roster)
    report.check(
        hailakandi_by_block
        == collections.Counter(controls_2025.HAILAKANDI_BLOCK_GP_COUNTS),
        "the five AP-level GP counts match the printed hierarchy",
        str(dict(hailakandi_by_block)),
    )
    report.check(
        {row["ward_count"] for row in hailakandi_roster} == {""}
        and {row["count_basis"] for row in hailakandi_roster}
        == {"derived_from_printed_reserved_rows_only"},
        "the left table does not turn reserved rows into an all-ward universe",
        "ward_count blank; counts are reserved-row only",
    )

    hailakandi_by_tier = {
        tier: [row for row in rows if row["district"] == "Hailakandi"]
        for tier, rows in rows_by_tier.items()
    }
    for tier, expected in controls_2025.HAILAKANDI_EXPECTED_ROWS.items():
        rows = hailakandi_by_tier[tier]
        report.check(
            len(rows) == expected,
            f"{tier} row count matches the identifiable printed rows",
            f"{len(rows)} of {expected}",
        )
        got = collections.Counter(
            (row["caste_reservation"], int(row["woman_reserved"])) for row in rows
        )
        report.check(
            got == controls_2025.HAILAKANDI_CATEGORY_COUNTS[tier],
            f"{tier} category vector matches the printed controls",
            str(dict(got)),
        )
        report.check(
            {row["listing_scope"] for row in rows} == {"reserved_only"},
            f"{tier} does not invent unprinted open seats",
            "listing_scope=reserved_only",
        )

    hailakandi_children = set()
    for tier in ("gp_ward", "gp_head", "gp_vice_head", "block_member"):
        hailakandi_children.update(
            (row["block"], row["gram_panchayat"]) for row in hailakandi_by_tier[tier]
        )
    report.check(
        hailakandi_children == hailakandi_gp_keys,
        "every GP-level child row joins to the 62-GP left table",
        f"{len(hailakandi_children)} joined GP keys",
    )
    gp_45 = next(row for row in hailakandi_roster if row["serial"] == "45")
    report.check(
        gp_45["block"] == "Algapur",
        "GP 45 follows the ward-table and final-gazette hierarchy",
        f"block={gp_45['block']}",
    )
    diagnostics = load("2025_extracted/scan_parse_diagnostics.csv")
    hailakandi_diagnostics = [
        row
        for row in diagnostics
        if row["source_pdf"] == "notification_reservation_hailakandi.pdf"
    ]
    report.check(
        collections.Counter(row["kind"] for row in hailakandi_diagnostics)
        == {"rejected_source_row": 1, "hierarchy_mismatch": 1},
        "the malformed GP row and GP-45 hierarchy conflict remain auditable",
        str(collections.Counter(row["kind"] for row in hailakandi_diagnostics)),
    )


@command("validate", state="Assam", source_id="assam_reservations")
def main():
    wards = load("ward_reservation_2020.csv")
    heads = load("chairperson_reservation_2020.csv")
    if not wards or not heads:
        sys.exit("no parsed Assam data - run make assam first")

    report = checks.Report("Assam municipal-board reservation, 2020")

    held = source_harvest.verify(
        harvest.MANIFEST,
        harvest.OUT,
        {harvest.SOURCE_ID: harvest.EXPECTED_DOCUMENTS},
    )
    report.section("Held 2025 rural source series")
    report.check(
        len(held) == harvest.EXPECTED_DOCUMENTS,
        "all district reservation notifications are held and checksummed",
        f"{len(held)} of {harvest.EXPECTED_DOCUMENTS}",
    )
    delimitation = delimitation_2024.verify()
    report.check(
        len(delimitation) == delimitation_2024.EXPECTED_DOCUMENTS,
        "Hailakandi's final delimitation gazettes are held and checksummed",
        f"{len(delimitation)} of {delimitation_2024.EXPECTED_DOCUMENTS}",
    )

    checks.structural(
        report,
        wards,
        ROOT,
        key=("state", "year", "tier", "district", "body", "ward_no"),
        required=(
            "state",
            "year",
            "tier",
            "body",
            "ward_no",
            "reservation",
            "caste_reservation",
            "woman_reserved",
        ),
    )
    checks.provenance(report, wards, ROOT)
    checks.structural(
        report,
        heads,
        ROOT,
        key=("state", "year", "tier", "district", "body"),
        required=(
            "state",
            "year",
            "tier",
            "body",
            "reservation",
            "caste_reservation",
            "woman_reserved",
        ),
    )
    checks.provenance(report, heads, ROOT)

    report.section("Printed controls")
    records = parse.ward_records()
    report.check(
        len(records) == PRINTED_BOARDS,
        "all board rows transcribed",
        f"{len(records)} of {PRINTED_BOARDS}",
    )
    total = sum(record["ward_count"] for record in records)
    report.check(
        total == PRINTED_WARDS,
        "board totals sum to the notification's grand total",
        f"{total:,} of {PRINTED_WARDS:,}",
    )
    report.check(
        len(heads) == PRINTED_RESERVED_HEADS,
        "all reserved chairperson rows transcribed",
        f"{len(heads)} of {PRINTED_RESERVED_HEADS}",
    )

    too_many = []
    duplicates = []
    for record in records:
        listed = [ward for group in record["categories"] for ward in group]
        if len(listed) > record["ward_count"]:
            too_many.append((record["body"], len(listed), record["ward_count"]))
        if len(listed) != len(set(listed)):
            duplicates.append(record["body"])
    report.check(
        not too_many,
        "reserved wards do not exceed each board's total",
        f"{len(too_many)} boards, e.g. {too_many[:2]}",
    )
    report.check(
        not duplicates,
        "a ward appears in only one reservation column",
        f"{len(duplicates)} boards, e.g. {duplicates[:2]}",
    )

    report.section("Scope")
    scopes = {row["listing_scope"] for row in wards + heads}
    report.check(
        scopes == {"reserved_only"},
        "unlisted open seats are not invented",
        f"listing_scope={sorted(scopes)}",
    )
    women = sum(int(row["woman_reserved"]) for row in wards)
    report.info(
        "women-reserved wards against the printed ward universe",
        f"{women}/{PRINTED_WARDS} = {women / PRINTED_WARDS:.1%}",
    )
    report.info(
        "identified ward rows emitted",
        f"{len(wards):,}; the notification names no identifiers for open wards",
    )

    validate_2025(report)

    return report.finish()


if __name__ == "__main__":
    sys.exit(main())
