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
    assert all(
        r["source_path"] == parse.SHEET_2007 for r in rows_2012 if r["ward_no"] != "172"
    )
    women = sum(r["woman_reserved"] for r in rows_2012)
    assert women == 114
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


def test_ward_172_uses_official_non_women_sc_reservation():
    """The official bilingual ward description overrides the spreadsheet typo."""
    original = {r["WARD NO"]: r for r in parse.sheet_2007()}["172"]
    assert original["Present Reservation"] == "Schedule Caste Women"
    rows = {r["ward_no"]: r for r in parse.rows_2012()}
    row = rows["172"]
    assert row["woman_reserved"] == 0
    assert row["caste_reservation"] == "SC"
    assert row["source_path"] == parse.WARD_172_SOURCE
    assert row["source_page"] == "17"
    wave = parse.deposit_wave(parse.read_tsv(parse.DEPOSIT), "2013")
    assert all(
        str(r["woman_reserved"]) == parse.clean(wave[w]["genderquota"])
        for w, r in rows.items()
    )


def test_2026_gazette_coverage_and_wrapped_vote_rows():
    """All wards reconcile, including three rows whose votes wrap with the party."""
    rows = {r["ward_no"]: r for r in parse.winners_2026()}
    assert set(rows) == {str(i) for i in range(1, 228)}
    assert rows["1"]["votes"] == 7544
    assert rows["143"]["votes"] == 5264
    assert rows["227"]["votes"] == 6131
    assert rows["134"]["source_page"] == rows["140"]["source_page"] == 5
    assert sum(r["woman_reserved"] for r in rows.values()) == 114
    assert rows["1"]["woman_reserved"] == 1
    assert rows["1"]["caste_reservation"] == "OBC"
    assert rows["3"]["woman_reserved"] == 0
    assert rows["53"]["caste_reservation"] == "ST"
    assert rows["227"]["reservation_source_page"] == 9


def test_bhavnani_retains_unclassified_controls_and_full_source():
    from local_elections.states.maharashtra import historical

    d = historical.bhavnani_comparison()
    assert len(d) == 227
    assert d.is_eligible.sum() == 118
    assert d.prior_reserved_woman.isna().sum() == 109
    assert ((~d.is_eligible) & d.reserved_woman.eq(0)).sum() == 33
    selected = d[d.is_eligible]
    assert selected.groupby("prior_reserved_woman").size().to_dict() == {0: 81, 1: 37}
    assert selected.groupby("prior_reserved_woman").winner_woman.sum().to_dict() == {
        0: 3,
        1: 8,
    }
    assert str(d.winner_woman.dtype) == "Int8"
    assert str(d.ward_no.dtype) == "string"


def test_research_profile_sex_requires_independent_identity_match():
    from local_elections.states.maharashtra import historical

    d = historical.recorded_winner_sex()
    assert len(d) == 454
    assert d.groupby("year").winner_woman.count().to_dict() == {2012: 69, 2017: 199}
    assert d.loc[~d.identity_match, "winner_woman"].isna().all()
    assert d.loc[d.profile_woman_raw.eq(""), "winner_woman"].isna().all()
    assert d.loc[d.reserved_woman.eq(1), "winner_woman"].isna().any()
    assert d.profile_year.eq(d.year + 1).all()


def test_historical_parquet_roundtrip_and_contract(tmp_path):
    import json

    import pandas as pd

    from local_elections.states.maharashtra import historical

    tables = historical.build(tmp_path)
    schema = json.loads((tmp_path / "historical_schema.json").read_text())
    for name, expected in tables.items():
        restored = pd.read_parquet(tmp_path / name)
        pd.testing.assert_frame_equal(expected, restored)
        assert schema[name]["rows"] == len(restored)
        assert schema[name]["primary_key"] == ["body", "year", "ward_no"]


@pytest.mark.parametrize(
    "violation", ["duplicate", "null_key", "binary", "eligibility"]
)
def test_historical_contract_rejects_invalid_records(violation):
    import pandas as pd

    from local_elections.states.maharashtra import historical

    d = historical.bhavnani_comparison()
    if violation == "duplicate":
        d = pd.concat([d, d.iloc[[0]]], ignore_index=True)
    elif violation == "null_key":
        d.loc[0, "ward_no"] = None
    elif violation == "binary":
        d.loc[0, "winner_woman"] = 2
    else:
        d.loc[0, "is_eligible"] = not d.loc[0, "is_eligible"]
    with pytest.raises(ValueError, match=r"Incomplete|Invalid|eligibility"):
        historical.validate(d)


def test_historical_verify_detects_output_tampering(tmp_path):
    from local_elections.states.maharashtra import historical

    historical.build(tmp_path)
    assert historical.verify_release(tmp_path)
    path = tmp_path / "bhavnani_comparison_1997_2002.parquet"
    with path.open("ab") as stream:
        stream.write(b"tamper")
    with pytest.raises(ValueError, match="output checksum mismatch"):
        historical.verify_release(tmp_path)
