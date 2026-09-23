import io

import pandas as pd
import pytest

from local_elections.states.wb import pradhan_gp
from local_elections.states.wb.pradhan_gp import ORDERS, label, split_suffix


@pytest.fixture(scope="module")
def built():
    return pradhan_gp.build()


def test_parsed_counts_equal_printed_totals(built):
    _, report = built
    for check in report:
        assert check["parsed"] == check["printed"], (check["district"], check["term"])


def test_gp_list_count_equals_printed_offices():
    # the inference that unnamed GPs are unreserved rests on this equality
    gps = pd.read_csv(pradhan_gp.GP_LISTS)
    for (district, term), spec in ORDERS.items():
        count = (
            (gps.mnrega_file_year == term) & (gps.district == spec["mnrega_district"])
        ).sum()
        assert count == spec["printed"]["offices"], district


def test_each_gp_once_and_named_offices_distinct(built):
    table, _ = built
    assert not table.duplicated(["district", "term", "block", "gram_panchayat"]).any()
    named = table[table.named_in_order]
    assert not named.duplicated(["source_file", "source_page", "source_row"]).any()


def test_unnamed_gps_carry_no_quota(built):
    table, _ = built
    unnamed = table[~table.named_in_order]
    assert (unnamed.caste_reservation == "UR").all()
    assert not unnamed.woman_reserved.any()
    assert (unnamed.match == "not_named").all()


def test_complete_listings_name_every_gp(built):
    table, _ = built
    for district, term in [("Malda", 2013), ("Nadia", 2013)]:
        rows = table[(table.district == district) & (table.term == term)]
        assert rows.named_in_order.all(), district


def test_blank_handbook_code_is_the_one_resolved_by_totals(built):
    table, _ = built
    row = table[(table.term == 2013) & (table.gram_panchayat == "TALDAH MAJDIA")]
    assert len(row) == 1
    assert row.caste_reservation.item() == "UR"
    assert not row.woman_reserved.item()


def test_committed_output_is_current(built):
    table, _ = built
    committed = pd.read_csv(pradhan_gp.OUT / "pradhan_gp.csv")
    fresh = pd.read_csv(io.StringIO(table.to_csv(index=False)))
    pd.testing.assert_frame_equal(committed, fresh)


def test_override_reasons_are_given():
    overrides = pd.read_csv(pradhan_gp.OVERRIDES)
    assert overrides.reason.str.len().gt(5).all()


@pytest.mark.parametrize(
    ("printed", "name", "numeral"),
    [
        ("Karimpur-!", "Karimpur", "1"),
        ("Birpur-ll", "Birpur", "2"),
        ("Plassey-t!", "Plassey", "2"),
        ("Narayanpur-H! (BC)", "Narayanpur", "3"),
        ("Baidyapur II", "Baidyapur", "2"),
        ("Tehatta", "Tehatta", ""),
    ],
)
def test_numerals_are_counted_in_strokes(printed, name, numeral):
    assert split_suffix(printed) == (name, numeral)


@pytest.mark.parametrize(
    ("printed", "gram_panchayat", "expected"),
    [
        ("Madhugari (SC)", "MADHUGARI", "exact"),  # case alone is not a difference
        ("Dhoradaha-II (BC)", "DHORADAHA-II", "exact"),
        ("Gopalgunj", "GOPALGANJ", "transliteration"),
        ("UTTAR LAXMIPUR", "UTTAR LAKSHMIPUR", "transliteration"),
        ("Karimpur-!", "KARIMPUR-I", "scan_misread"),
        ("Rashkhali", "RAKHALI", "fuzzy"),
        ("Betai-I", "BETAI-II", "fuzzy"),  # numerals must agree
    ],
)
def test_match_label_compares_the_names(printed, gram_panchayat, expected):
    assert label(printed, gram_panchayat) == expected
