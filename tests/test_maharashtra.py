"""Contracts for the Mumbai (BMC) parser.

The trap this file guards is a sheet that pairs one council's winners with the
next council's reservation. Every case below pins something that would have
read as plausible had it gone wrong.
"""

import pytest

from local_elections.states.maharashtra import parse

SHEET_PHRASES = {
    "Open": ("NONE", 0, "Other than Woman"),
    "Women": ("NONE", 1, "Woman"),
    "Backward Class": ("BC", 0, "BC Other than Woman"),
    "Backward Class Women": ("BC", 1, "BC Woman"),
    "Schedule Caste": ("SC", 0, "SC Other than Woman"),
    "Schedule Caste Women": ("SC", 1, "SC Woman"),
    # the sheet's one typo: it drops "Caste"; the ST rows spell out "Tribe"
    "Scheduled Women": ("SC", 1, "SC Woman"),
    "Scheduled Tribe": ("ST", 0, "ST Other than Woman"),
    "Scheduled Tribe Women": ("ST", 1, "ST Woman"),
}
DEPOSIT_CODES = {
    "G": ("NONE", 0, "Other than Woman"),
    "W": ("NONE", 1, "Woman"),
    "OBC": ("BC", 0, "BC Other than Woman"),
    "OBC-W": ("BC", 1, "BC Woman"),
    "SC": ("SC", 0, "SC Other than Woman"),
    "SC-W": ("SC", 1, "SC Woman"),
    "ST": ("ST", 0, "ST Other than Woman"),
    "ST-W": ("ST", 1, "ST Woman"),
}


@pytest.mark.parametrize(
    ("stated", "expected"), sorted({**SHEET_PHRASES, **DEPOSIT_CODES}.items())
)
def test_every_printed_reservation_phrase_is_read(stated, expected):
    caste, woman, label = expected
    row = parse.seat("2012", "1", stated, winner="", source_path="x")
    assert (row["caste_reservation"], row["woman_reserved"], row["reservation"]) == (
        caste,
        woman,
        label,
    )
    assert row["reservation_raw"] == stated
    assert row["caste_reservation_local"] == ("OBC" if caste == "BC" else "")


def test_seat_refuses_an_unreadable_phrase():
    with pytest.raises(SystemExit):
        parse.seat("2012", "1", "Reserved", winner="", source_path="x")


def test_a_winner_without_letters_is_blank():
    """Ward 78 in 2017 prints its winner as underscores."""
    row = parse.seat("2017", "78", "W", winner="______ ____ __", source_path="x")
    assert row["winner"] == ""
    assert row["winner_basis"] == ""


def test_winner_basis_follows_the_name():
    named = parse.seat("2017", "1", "W", winner="Tejasvee Ghosalkar", source_path="x")
    assert named["winner_basis"] == "published"
    argmax = parse.seat(
        "2012",
        "1",
        "Open",
        winner="Someone",
        winner_basis="argmax_votes",
        source_path="x",
    )
    assert argmax["winner_basis"] == "argmax_votes"


def test_clean_drops_the_deposits_float_suffix():
    assert parse.clean("2007.0") == "2007"
    assert parse.clean("1.0") == "1"
    assert parse.clean(3.0) == "3"
    assert parse.clean("73.837") == "73.837"
    assert parse.clean(float("nan")) == ""


@pytest.mark.parametrize(
    ("printed", "short"),
    [
        ("shivsena", "SS"),
        ("SENA", "SS"),
        ("Bhartiya Janata Party", "BJP"),
        ("CONG", "INC"),
        ("indian nationalist congress", "NCP"),
        ("Apaksh", "IND"),
        ("Some New Front", "Some New Front"),
    ],
)
def test_party_labels(printed, short):
    assert parse.party_of(printed) == short


def test_the_sheets_reservation_is_filed_under_2012_not_2007():
    """The 2007 sheet's "Present Reservation" is the 2012 draw."""
    rows_2012 = parse.rows_2012()
    assert len(rows_2012) == 227
    assert all(r["year"] == "2012" for r in rows_2012)
    assert all(r["source_path"] == parse.SHEET_2007 for r in rows_2012)
    women = sum(r["woman_reserved"] for r in rows_2012)
    assert women in (114, 115), women  # half, not the 2007 council's third (76)
    seats_2007 = parse.seats_2007(parse.read_tsv(parse.DEPOSIT))
    assert sum(r["woman_reserved"] == "1" for r in seats_2007) == 76
    assert "reservation" not in seats_2007[0]


def test_2017_tie_is_settled_by_the_deposit():
    rows = {r["ward_no"]: r for r in parse.rows_2017(parse.read_tsv(parse.DEPOSIT))}
    assert rows["220"]["winner"].upper() == "ATUL HASMUKHLAL SHAH"
    assert rows["220"]["winner_basis"] == "published"
    assert rows["78"]["winner"] == ""


def test_praja_ratings_carry_the_2018_flag_only():
    rows = parse.praja_ratings(parse.read_tsv(parse.DEPOSIT))
    flagged = {r["survey_year"] for r in rows if r["rating_flags"]}
    assert flagged == {"2018"}
    assert {r["rating_flags"] for r in rows if r["survey_year"] == "2018"} == {
        "satisfaction_inverted"
    }
    assert "rating_roads" in rows[0]
    assert "conditionofroads" not in rows[0]
    assert len(rows) == 1361  # the deposit's one empty ward-8/2014 row is dropped
