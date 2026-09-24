"""Contracts for the checked Assam table transcription."""

import collections
import csv
import json

import pytest

from local_elections.common import reference
from local_elections.states.assam import (
    controls_2025,
    delimitation_2024,
    extract_2025,
    harvest,
    ocr_2025,
    parse,
    parse_2025,
    parse_hailakandi_2025,
    parse_scan_2025,
)


def test_district_scope_counts_derive_from_one_reviewed_list():
    assert len(controls_2025.PARSED_DISTRICTS) == 4
    assert controls_2025.HELD_DISTRICT_NOTIFICATIONS == 27
    assert controls_2025.UNPARSED_DISTRICT_NOTIFICATIONS == 23
    assert (
        len(controls_2025.PARSED_DISTRICTS)
        + controls_2025.UNPARSED_DISTRICT_NOTIFICATIONS
        == controls_2025.HELD_DISTRICT_NOTIFICATIONS
    )


def test_hailakandi_delimitation_gazettes_use_the_standard_manifest():
    rows = delimitation_2024.verify()
    assert len(rows) == delimitation_2024.EXPECTED_DOCUMENTS
    assert {row["body"] for row in rows} == {
        "Anchalik Panchayat",
        "Development Block",
        "Gaon Panchayat",
        "Zilla Parishad Constituency",
    }


def test_scan_extraction_is_driven_by_the_source_manifest():
    documents = ocr_2025.manifest_documents()
    selected = ocr_2025.select_documents(documents, district="South Salmara-Mankachar")
    assert len(documents) == harvest.EXPECTED_DOCUMENTS
    assert len(selected) == 1
    record, path = selected[0]
    assert record["sha256"] == (
        "e55b6ff2a17dc1589aa9b0fb0c47cbcc7e919de377fd08f00b52b7e7176034a5"
    )
    assert path.name == "south_salmara_reservation.pdf"


def test_scan_extraction_requires_an_explicit_scope():
    with pytest.raises(ValueError, match="pass --district NAME or --all"):
        ocr_2025.select_documents([], district="")


def test_scan_repair_reuses_every_readable_page(tmp_path):
    target = tmp_path / "district.html"
    partial = tmp_path / ".partial" / "district.jsonl"
    target.write_text("page one\f<!-- ocr-unread reason=test -->\fpage three")
    assert ocr_2025.seed_repair(target, partial) == [2]
    records = [json.loads(line) for line in partial.read_text().splitlines()]
    assert records == [
        {"page": 1, "text": "page one"},
        {"page": 3, "text": "page three"},
    ]


def test_one_scan_page_can_be_retried_without_rerunning_the_others(tmp_path):
    target = tmp_path / "district.html"
    partial = tmp_path / ".partial" / "district.jsonl"
    target.write_text("page one\fpage two\fpage three")
    assert ocr_2025.seed_pages(target, partial, [2]) == [2]
    records = [json.loads(line) for line in partial.read_text().splitlines()]
    assert records == [
        {"page": 1, "text": "page one"},
        {"page": 3, "text": "page three"},
    ]


def test_2025_notifications_are_pre_poll_reservation_rosters():
    for tier in (
        "gp_ward",
        "gp_head",
        "gp_vice_head",
        "block_member",
        "block_head",
        "block_vice_head",
        "zp_member",
    ):
        assert reference.document_stage("Assam", "2025", tier) == "pre_poll"


def test_the_harvester_keeps_only_district_reservation_pdfs():
    page = b"""<a href="https://sec.assam.gov.in/pdf/panchayat-election/RESERVATION-GUIDELINES.pdf">guide</a>
    <a href="https://sec.assam.gov.in/pdf/panchayat-election/reservation/Notification%20Reservation%20Sonitpur.pdf">Sonitpur</a>
    <a href="https://sec.assam.gov.in/pdf/panchayat-election/reservation/tinsukia-reservation.pdf">Tinsukia</a>"""
    assert harvest.links_from(page) == [
        "https://sec.assam.gov.in/pdf/panchayat-election/reservation/Notification%20Reservation%20Sonitpur.pdf",
        "https://sec.assam.gov.in/pdf/panchayat-election/reservation/tinsukia-reservation.pdf",
    ]


def test_live_source_names_become_stable_local_names():
    url = (
        "https://sec.assam.gov.in/pdf/panchayat-election/reservation/"
        "Notification%20reservation%20jorhat.pdf"
    )
    assert harvest.local_name(url) == "notification_reservation_jorhat.pdf"
    assert harvest.district_of(url) == "Jorhat"


def test_every_held_2025_source_has_a_district_mapping():
    with harvest.MANIFEST.open(encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    files = {row["file"] for row in rows}
    assert files == set(harvest.DISTRICT_OF_FILE)
    assert {row["district"] for row in rows} == set(harvest.DISTRICT_OF_FILE.values())


def test_the_ward_table_reconciles_to_its_printed_controls():
    records = parse.ward_records()
    assert [record["serial"] for record in records] == list(range(1, 82))
    assert sum(record["ward_count"] for record in records) == 1004
    assert {record["source_page"] for record in records} == {2, 3, 4, 5, 6}


def test_a_ward_appears_in_only_one_reservation_column():
    for record in parse.ward_records():
        wards = [ward for group in record["categories"] for ward in group]
        assert len(wards) == len(set(wards)), record["body"]
        assert len(wards) <= record["ward_count"], record["body"]


def test_only_identified_reserved_wards_are_emitted():
    rows = parse.ward_rows()
    assert len(rows) == 564
    assert sum(row["woman_reserved"] for row in rows) == 497
    assert collections.Counter(row["caste_reservation"] for row in rows) == {
        "NONE": 444,
        "SC": 98,
        "ST": 22,
    }
    assert {row["listing_scope"] for row in rows} == {"reserved_only"}


def test_alphanumeric_ward_identifiers_are_not_renumbered():
    rows = parse.ward_rows()
    north_lakhimpur = {
        row["ward_no"] for row in rows if row["body"] == "North Lakhimpur"
    }
    assert {"2A", "2B", "3A", "3B", "5B", "14D"} <= north_lakhimpur


def test_the_chairperson_table_is_complete_and_joins_to_the_board_roster():
    heads = parse.head_rows()
    assert [row["serial"] for row in heads] == list(range(1, 47))
    assert collections.Counter(row["reservation_raw"] for row in heads) == {
        "Scheduled Tribe": 1,
        "Scheduled Tribe (Woman)": 1,
        "Scheduled Caste": 4,
        "Scheduled Caste (Woman)": 4,
        "Woman": 36,
    }
    boards = {(record["district"], record["body"]) for record in parse.ward_records()}
    assert {(row["district"], row["body"]) for row in heads} <= boards
    assert {row["source_page"] for row in heads} == {7, 8}


def test_every_row_points_to_the_committed_source():
    parse.verify_source()
    for row in parse.ward_rows() + parse.head_rows():
        assert row["source_path"] == str(parse.SOURCE_PATH)
        assert 2 <= row["source_page"] <= 8


def test_charaideo_is_four_blocks_not_one_block():
    records = extract_2025.gp_records()
    assert len(records) == 36
    assert collections.Counter(
        record["anchalik_panchayat"] for record in records
    ) == collections.Counter(controls_2025.BLOCK_GP_COUNTS)


def test_the_gp_left_table_preserves_zero_and_two_counts():
    records = extract_2025.gp_records()
    combinations = collections.Counter(
        (record["sc_reserved_ward_count"], record["st_reserved_ward_count"])
        for record in records
    )
    assert combinations == collections.Counter(
        {(0, 0): 28, (0, 1): 5, (0, 2): 1, (1, 0): 1, (2, 0): 1}
    )
    assert sum(record["sc_reserved_ward_count"] for record in records) == 3
    assert sum(record["st_reserved_ward_count"] for record in records) == 7


def test_charaideo_emits_the_complete_ward_universe():
    rows = parse_2025.ward_rows(extract_2025.gp_records())
    assert len(rows) == 360
    assert {row["listing_scope"] for row in rows} == {"all_seats"}
    assert (
        collections.Counter(
            (row["caste_reservation"], row["woman_reserved"]) for row in rows
        )
        == controls_2025.CATEGORY_COUNTS["gp_ward"]
    )
    by_gp = collections.defaultdict(set)
    for row in rows:
        by_gp[(row["block"], row["gram_panchayat"])].add(row["ward_no"])
    assert len(by_gp) == 36
    assert all(wards == set(range(1, 11)) for wards in by_gp.values())


def test_charaideo_keeps_president_and_vice_president_distinct():
    offices = parse_2025.office_rows(
        extract_2025.gp_records(), extract_2025.office_records()
    )
    for tier, expected in controls_2025.EXPECTED_ROWS.items():
        if tier == "gp_ward":
            continue
        assert len(offices[tier]) == expected
        assert (
            collections.Counter(
                (row["caste_reservation"], row["woman_reserved"])
                for row in offices[tier]
            )
            == controls_2025.CATEGORY_COUNTS[tier]
        )
    assert {row["tier"] for row in offices["gp_head"]} == {"gp_head"}
    assert {row["tier"] for row in offices["gp_vice_head"]} == {"gp_vice_head"}


def test_kamrup_metropolitan_extracts_every_printed_ward_status():
    rows = extract_2025.kamrup_metropolitan_ward_records()
    assert [row["serial"] for row in rows] == list(range(1, 201))
    assert all(row["village_name_raw"] for row in rows)
    assert (
        collections.Counter(
            (row["caste_reservation_raw"], row["woman_reserved_raw"]) for row in rows
        )
        == controls_2025.KAMRUP_METROPOLITAN_CATEGORY_COUNTS["gp_ward"]
    )
    row_139 = rows[138]
    assert row_139["gram_panchayat"] == "Sonapur"
    assert row_139["ward_no"] == 9
    assert row_139["reservation_raw"] == "Unreserved"
    assert row_139["extraction_method"] == "human_checked_from_rendered_page"


def test_kamrup_metropolitan_is_three_blocks_and_twenty_gps():
    gps = extract_2025.kamrup_metropolitan_gp_records()
    assert len(gps) == 20
    assert collections.Counter(
        record["anchalik_panchayat"] for record in gps
    ) == collections.Counter(controls_2025.KAMRUP_METROPOLITAN_BLOCK_GP_COUNTS)


def test_kamrup_metropolitan_gp_cell_applies_to_every_ward_it_spans():
    rows = extract_2025.kamrup_metropolitan_ward_records()
    for start in range(0, 200, 10):
        gp_rows = rows[start : start + 10]
        assert {row["gram_panchayat"] for row in gp_rows} == {
            extract_2025.kamrup_metropolitan_gp_records()[start // 10]["gram_panchayat"]
        }
        assert [row["ward_no"] for row in gp_rows] == list(range(1, 11))


def test_kamrup_metropolitan_office_tables_include_unreserved_rows():
    records = extract_2025.kamrup_metropolitan_office_records()
    rows = parse_2025.kamrup_metropolitan_office_rows(records)
    for tier, expected in controls_2025.KAMRUP_METROPOLITAN_EXPECTED_ROWS.items():
        if tier == "gp_ward":
            continue
        assert len(rows[tier]) == expected
        assert (
            collections.Counter(
                (row["caste_reservation"], row["woman_reserved"]) for row in rows[tier]
            )
            == controls_2025.KAMRUP_METROPOLITAN_CATEGORY_COUNTS[tier]
        )
        assert any(row["reservation_raw"] == "Unreserved" for row in rows[tier])


def test_south_salmara_scan_reconciles_three_independent_ward_tables():
    parsed = parse_scan_2025.extracted("South Salmara-Mankachar")
    assert [gp["serial"] for gp in parsed["gps"]] == list(range(1, 36))
    assert len(parsed["wards"]) == 350
    assert sum(row["woman_reserved_raw"] for row in parsed["wards"]) == 175
    assert sum(bool(row["ward_name"]) for row in parsed["wards"]) == 175
    assert (
        collections.Counter(
            (row["caste_reservation_raw"], row["woman_reserved_raw"])
            for row in parsed["wards"]
        )
        == controls_2025.SOUTH_SALMARA_CATEGORY_COUNTS["gp_ward"]
    )


def test_south_salmara_left_table_retains_zero_caste_counts():
    parsed = parse_scan_2025.extracted("South Salmara-Mankachar")
    rows = parse_2025.scan_roster_rows(parsed)
    assert len(rows) == 35
    assert collections.Counter(
        (row["sc_reserved_ward_count"], row["st_reserved_ward_count"]) for row in rows
    ) == collections.Counter({(0, 0): 26, (1, 0): 7, (0, 1): 2})
    assert {row["block"] for row in rows} == {""}
    assert {row["ward_count"] for row in rows} == {10}
    assert {row["women_reserved_ward_count"] for row in rows} == {5}


def test_south_salmara_offices_use_reserved_lists_and_complete_complements():
    parsed = parse_scan_2025.extracted("South Salmara-Mankachar")
    rows = parse_2025.scan_rows(parsed)
    for tier, expected in controls_2025.SOUTH_SALMARA_EXPECTED_ROWS.items():
        assert len(rows[tier]) == expected
        assert (
            collections.Counter(
                (row["caste_reservation"], row["woman_reserved"]) for row in rows[tier]
            )
            == controls_2025.SOUTH_SALMARA_CATEGORY_COUNTS[tier]
        )
    assert {row["block"] for row in rows["block_member"]} == {""}
    assert {row["block"] for row in rows["block_head"]} == {
        "Mankachar",
        "Fekamari",
    }


def test_south_salmara_missing_office_tier_fails_with_source_context():
    parsed = parse_scan_2025.extracted("South Salmara-Mankachar")
    parsed = {
        **parsed,
        "offices": [
            row for row in parsed["offices"] if row["office"] != "block_member"
        ],
    }
    with pytest.raises(
        ValueError,
        match=r"South Salmara-Mankachar.*block_member",
    ):
        parse_2025.scan_rows(parsed)


def test_hailakandi_dispatches_by_table_shape_and_keeps_reserved_scope():
    parsed = parse_scan_2025.extracted("Hailakandi")
    assert parsed["layout"] == "hailakandi_reserved_rows"
    assert parsed["listing_scope"] == "reserved_only"
    assert len(parsed["gps"]) == 62
    assert len(parsed["wards"]) == 344
    assert collections.Counter(
        gp["anchalik_panchayat"] for gp in parsed["gps"]
    ) == collections.Counter(controls_2025.HAILAKANDI_BLOCK_GP_COUNTS)


def test_hailakandi_printed_rows_are_not_completed_with_invented_open_seats():
    parsed = parse_scan_2025.extracted("Hailakandi")
    roster = parse_2025.reserved_scan_roster_rows(parsed)
    rows = parse_2025.reserved_scan_rows(parsed)
    assert len(roster) == 62
    assert {row["ward_count"] for row in roster} == {""}
    assert {row["count_basis"] for row in roster} == {
        "derived_from_printed_reserved_rows_only"
    }
    for tier, expected in controls_2025.HAILAKANDI_EXPECTED_ROWS.items():
        assert len(rows[tier]) == expected
        assert {row["listing_scope"] for row in rows[tier]} == {"reserved_only"}
        assert (
            collections.Counter(
                (row["caste_reservation"], row["woman_reserved"]) for row in rows[tier]
            )
            == controls_2025.HAILAKANDI_CATEGORY_COUNTS[tier]
        )


def test_hailakandi_source_defects_are_explicit_diagnostics():
    parsed = parse_scan_2025.extracted("Hailakandi")
    assert parsed["diagnostics"] == [
        {
            "kind": "rejected_source_row",
            "office": "gp_head",
            "reason": "GP cell has no identifiable numbered GP",
            "anchalik_panchayat_raw": "4.Algapur",
            "gram_panchayat_raw": "4.Algapur",
            "reservation_raw": "4.Algapur",
            "source_page": 3,
        },
        {
            "kind": "hierarchy_mismatch",
            "office": "gp_head",
            "reason": "reservation row AP disagrees with the ward roster",
            "gp_serial": 45,
            "anchalik_panchayat_raw": "Hailakandi",
            "anchalik_panchayat": "Algapur",
            "gram_panchayat_raw": "Bondukmara Bar Hailakandi",
            "gram_panchayat": "Bondukmara Bar Hailakandi",
            "reservation_raw": "Woman",
            "source_page": 3,
        },
    ]
    gp_one = next(gp for gp in parsed["gps"] if gp["serial"] == 1)
    gp_45 = next(gp for gp in parsed["gps"] if gp["serial"] == 45)
    assert gp_one["gram_panchayat"] == "Mahadebpur"
    assert gp_45["anchalik_panchayat"] == "Algapur"


def test_hailakandi_parser_does_not_open_source_documents(monkeypatch):
    def no_pdf_access(*args, **kwargs):
        raise AssertionError("the parser must read only the OCR cache")

    monkeypatch.setattr(extract_2025.pdfplumber, "open", no_pdf_access)
    parsed = parse_scan_2025.extracted("Hailakandi")
    assert parse_hailakandi_2025.supports(
        ocr_2025.CACHE.joinpath("notification_reservation_hailakandi.html").read_text()
    )
    assert len(parsed["wards"]) == 344


def test_the_parser_reads_the_extraction_boundary(monkeypatch):
    def no_pdf_access(*args, **kwargs):
        raise AssertionError("the parser must not open a PDF")

    monkeypatch.setattr(extract_2025.pdfplumber, "open", no_pdf_access)
    roster, rows = parse_2025.build_rows()
    assert len(roster) == 153
    assert sum(map(len, rows.values())) == 1678
    assert collections.Counter(row["district"] for row in roster) == {
        "Charaideo": 36,
        "Kamrup Metropolitan": 20,
        "South Salmara-Mankachar": 35,
        "Hailakandi": 62,
    }
