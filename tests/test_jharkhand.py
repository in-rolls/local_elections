"""Jharkhand's compound seat identifier, pinned to real gazette strings.

The last column of a Jharkhand notification is not a name. It is the district,
the block, the gram panchayat and the constituency number run together:

    XV cksdkjks@08 pkl@18 lruiqj@izk0fu0{ks0 la0&12

Reading it whole cost more than it looked. `block` came out 52-100% blank when
the block is right there in the string; ward rows carried no ward number at all;
and 121 rows collided on a seat key that was nothing but a roman numeral.

Nothing here raised an error before - the column was simply a long opaque
string, and in a corpus that is legacy-font mojibake nobody would look twice.
Every case below is copied out of a notification.
"""

import pytest

from local_elections.common import parsers

jharkhand = parsers.load("jharkhand")
fill_block_names = jharkhand.fill_block_names
split_seat_id = jharkhand.split_seat_id


# ----------------------------------------------------------- ward member


def test_block_and_panchayat_both_named():
    """Bokaro prints every part, separated by spaces after each number."""
    got = split_seat_id(
        "XV cksdkjks@08 pkl@18 lruiqj@izk0fu0{ks0 la0&12", "ward_member"
    )
    assert got["district_roman"] == "XV"
    assert (got["block_no"], got["block"]) == ("08", "pkl")
    assert (got["gp_no"], got["gram_panchayat"]) == ("18", "lruiqj")
    assert got["seat_no"] == "12"


def test_block_given_only_as_a_number():
    """Lohardaga names the panchayat but gives the block as a bare number, so
    the block name has to come from elsewhere - see fill_block_names."""
    got = split_seat_id("XVII yksgjnxk@5@10@ck?kk&¼01½", "ward_member")
    assert (got["block_no"], got["gp_no"]) == ("5", "10")
    assert got["gram_panchayat"] == "ck?kk"
    assert got["seat_no"] == "01"
    assert "block" not in got


def test_roman_numeral_trails_the_string():
    """East Singhbhum puts the district's index at the end, not the front."""
    got = split_seat_id("iwohZ flga Hkwe@05@02@cMk[kq'khZ XXIV - (04)", "ward_member")
    assert got["district_roman"] == "XXIV"
    assert got["gram_panchayat"] == "cMk[kq'khZ"
    assert got["seat_no"] == "04"


BRACKETS = [
    ("XV cksdkjks@01 xksfe;k@14 ifygkjh@izk0fu0{ks0 la0&09", "09"),
    ("XVII yksgjnxk@5@10@ck?kk&¼01½", "01"),
    ("VIII nos ?kj@3@3@igkfj;k ¼9½", "9"),
    ("iwohZ flga Hkwe@05@03@tksfM+lk XXIV -(09)", "09"),
    ("XXIV iwohZ flagHkwe@05@07@cudkVh - (02)", "02"),
]


@pytest.mark.parametrize(("raw", "expected"), BRACKETS)
def test_the_number_survives_every_bracket_style(raw, expected):
    """Five typesetters, five ways of bracketing the same number."""
    assert split_seat_id(raw, "ward_member")["seat_no"] == expected


# ------------------------------------------------- the tier decides the name


def test_same_shape_means_block_at_samiti_level():
    got = split_seat_id("I x<+ok@01@[kjkSa/kh&¼01½", "panchayat_samiti")
    assert (got["block_no"], got["block"]) == ("01", "[kjkSa/kh")
    assert got["seat_no"] == "01"
    assert "gram_panchayat" not in got


def test_same_shape_means_panchayat_at_ward_level():
    """Identical layout, one tier down, and the trailing name is a different
    thing. This is why split_seat_id has to be told the tier."""
    got = split_seat_id("I x<+ok@01@[kjkSa/kh&¼01½", "ward_member")
    assert got["gram_panchayat"] == "[kjkSa/kh"
    assert "block" not in got


def test_zila_parishad_names_only_the_district():
    """A zila parishad constituency is numbered across the whole district, so
    there is no block or panchayat in it to find."""
    got = split_seat_id("XIV /kuckn & ¼ 1 ½", "zila_parishad")
    assert got["seat_no"] == "1"
    assert "block" not in got
    assert "gram_panchayat" not in got


def test_mukhiya_identifier_is_only_a_name():
    assert split_seat_id("lq.Mh", "mukhiya")["gram_panchayat"] == "lq.Mh"


def test_nothing_is_invented_from_a_bare_roman_numeral():
    """121 Lohardaga rows extract as "XVII" and nothing else, because on those
    pages that column is drawn as 40 embedded images - the text is simply not in
    the document. The district's index is all there is, and blank is the honest
    answer for the rest; only OCR can close it."""
    got = split_seat_id("XVII", "ward_member")
    assert got["district_roman"] == "XVII"
    assert not {"block", "block_no", "gram_panchayat", "gp_no", "seat_no"} & set(got)


def test_empty_input_yields_nothing():
    assert split_seat_id("", "mukhiya") == {}


# -------------------------------------------- joining the block name back on


def test_block_name_joined_from_a_row_that_states_it():
    rows = [
        {
            "district": "Bokaro",
            "block_no": "08",
            "block": "pkl",
            "block_from": "identifier",
        },
        {"district": "Bokaro", "block_no": "08", "block": "", "block_from": ""},
    ]
    filled, ambiguous = fill_block_names(rows)
    assert (filled, ambiguous) == (1, 0)
    assert rows[1]["block"] == "pkl"


def test_page_header_blocks_do_not_seed_the_lookup():
    """The header is read once per page and does not change when a table
    crosses a block boundary mid-page, which is how Dhanbad ended up with three
    different names against block 04. Only blocks stated on the row itself are
    usable, so a header-only value teaches the lookup nothing."""
    rows = [
        {
            "district": "Dhanbad",
            "block_no": "04",
            "block": "fujlk",
            "block_from": "page",
        },
        {"district": "Dhanbad", "block_no": "04", "block": "", "block_from": ""},
    ]
    filled, _ = fill_block_names(rows)
    assert filled == 0
    assert rows[1]["block"] == ""


def test_an_ambiguous_number_fills_nothing():
    rows = [
        {"district": "X", "block_no": "01", "block": "A", "block_from": "identifier"},
        {"district": "X", "block_no": "01", "block": "B", "block_from": "identifier"},
        {"district": "X", "block_no": "01", "block": "", "block_from": ""},
    ]
    filled, ambiguous = fill_block_names(rows)
    assert (filled, ambiguous) == (0, 1)
    assert rows[2]["block"] == ""
