"""Gujarat OCR, geography, and reservation contracts."""

import pytest
from PIL import Image, ImageDraw

from local_elections.common import dictionary, reference
from local_elections.states.gujarat import controls, geography, ocr, parse


def test_every_held_filename_has_a_declared_geography():
    for path in ocr.harvest.OUT.glob("*.pdf"):
        tier = "zp_member" if path.name.startswith("zp_member_") else "block_member"
        district, body = geography.places(path.name, tier)
        assert district
        assert body


def test_every_held_source_has_an_independent_control():
    district = {path.name for path in ocr.harvest.OUT.glob("zp_member_*.pdf")}
    taluka = {path.name for path in ocr.harvest.OUT.glob("block_member_*.pdf")}
    assert district == set(controls.DISTRICT_CATEGORY_COUNTS)
    assert taluka == set(controls.TALUKA_CATEGORY_COUNTS)


def test_category_controls_sum_to_the_row_controls():
    for categories, rows in (
        (controls.DISTRICT_CATEGORY_COUNTS, controls.DISTRICT_ROW_COUNTS),
        (controls.TALUKA_CATEGORY_COUNTS, controls.TALUKA_ROW_COUNTS),
    ):
        assert {
            source: sum(counts.values()) for source, counts in categories.items()
        } == rows


def test_shared_expectations_match_the_source_controls():
    totals = {
        "zp_member": sum(controls.DISTRICT_ROW_COUNTS.values()),
        "block_member": sum(controls.TALUKA_ROW_COUNTS.values()),
    }
    for tier, total in totals.items():
        assert dictionary.ROW_BANDS[("Gujarat", tier)] == (total, total)
        assert reference.published("Gujarat", "2020", tier)["total"] == total
        assert reference.document_stage("Gujarat", "2020", tier) == "pre_poll"


def test_direct_download_times_do_not_become_archive_capture_timestamps():
    path = next(iter(sorted(ocr.OCR.glob("*.jsonl"))))
    rows = parse.read(path, parse.source_manifest())
    assert rows
    assert all(row["source_url"] for row in rows)
    assert {row["source_capture"] for row in rows} == {""}


def test_reviewed_gujarati_categories_round_trip():
    for category, (caste, woman) in parse.CATEGORIES.items():
        raw, matched, got_caste, got_woman, score = parse.reservation_of(category)
        assert raw == category
        assert matched == category
        assert (got_caste, got_woman) == (caste, woman)
        assert score == 1


def test_spacing_and_table_rules_do_not_change_a_category():
    raw, category, caste, woman, score = parse.reservation_of("| સામાન્ય   સ્ત્રી |")
    assert raw == "| સામાન્ય   સ્ત્રી |"
    assert category == "સામાન્ય સ્ત્રી"
    assert (caste, woman) == ("NONE", 1)
    assert score == 1


def test_the_best_of_multiple_ocr_readings_is_retained():
    raw, category, caste, woman, score = parse.reservation_of(
        "જાતિ rl અનુસૂચિત", "અનુસૂચિતજાતિસ્ત્રી"
    )
    assert raw == "અનુસૂચિતજાતિસ્ત્રી"
    assert category == "અનુસૂચિત જાતિ સ્ત્રી"
    assert (caste, woman) == ("SC", 1)
    assert score == 1


def test_name_selection_drops_table_rules_and_keeps_the_richer_reading():
    assert parse.best_name("| ભવાલડી", "ભુવાલડી") == "ભુવાલડી"
    assert parse.best_name("| અસલાલી", "અસલાલી") == "અસલાલી"


def test_name_selection_rejects_a_full_tsv_dump():
    assert parse.best_name("5\t1\t40\tઅનામત", "ઉના *") == "ઉના"


def test_row_boundaries_exclude_the_numbered_header_interval():
    image = Image.new("L", (1000, 1000), "white")
    draw = ImageDraw.Draw(image)
    for y in [200, 260, 320, 380, 440, 500, 560, 620, 680, 740, 800, 860, 920]:
        draw.line((100, y, 960, y), fill="black", width=3)
    assert ocr.row_boundaries(image) == [
        260,
        320,
        380,
        440,
        500,
        560,
        620,
        680,
        740,
        800,
        860,
        920,
    ]


def test_row_boundaries_respect_layout_specific_header_rules():
    image = Image.new("L", (1000, 1000), "white")
    draw = ImageDraw.Draw(image)
    for y in [200, 260, 320, 380, 440, 500, 560, 620, 680, 740, 800, 860, 920]:
        draw.line((100, y, 960, y), fill="black", width=3)
    assert ocr.row_boundaries(image, header_lines_to_drop=3) == [
        380,
        440,
        500,
        560,
        620,
        680,
        740,
        800,
        860,
        920,
    ]


def test_every_tier_layout_names_a_declared_grid():
    assert set(ocr.TIER_LAYOUTS) == {"zp_member", "block_member"}
    assert all(
        layout in ocr.LAYOUTS
        for layouts in ocr.TIER_LAYOUTS.values()
        for layout in layouts
    )


def test_block_topology_detection_uses_the_actual_grid_rules():
    image = Image.new("L", (1000, 1000), "white")
    draw = ImageDraw.Draw(image)
    ratios = [0.15, 0.21, 0.32, 0.40, 0.53, 0.63, 0.74, 0.94]
    for ratio in ratios:
        draw.line((ratio * 1000, 150, ratio * 1000, 850), fill="black", width=3)
    layout = ocr.detect_layout(image, "block_member")
    assert layout["lines"] == pytest.approx(ratios, abs=0.002)
    assert layout["columns"]["seat_no_raw"] == pytest.approx((0.32, 0.40), abs=0.002)
    assert layout["columns"]["reservation_raw"] == pytest.approx(
        (0.74, 0.94), abs=0.002
    )
    assert layout["maximum_row_gap"] == 140


def test_reviewed_assignment_summary_sources_have_every_controlled_seat():
    for source, specs in ocr.ASSIGNMENT_SUMMARY_ROWS.items():
        assert {spec[1] for spec in specs} == set(
            range(1, controls.DISTRICT_ROW_COUNTS[source] + 1)
        )


def test_reviewed_name_readings_are_source_script():
    assert len(ocr.REVIEWED_NAME_READINGS) == 5
    assert all(
        parse.compact(reading) == reading
        for reading in ocr.REVIEWED_NAME_READINGS.values()
    )
