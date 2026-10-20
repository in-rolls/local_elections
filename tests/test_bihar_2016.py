"""Resolved winners must survive the candidate-level conversion."""

import pytest

from local_elections.common.adapters.bihar_2016 import REVIEWED, RULING, convert


def tables(winner=True):
    key = {
        "office": "mukhiya",
        "district_code": "01",
        "block_code": "001",
        "panchayat_code": None,
        "unit_code": "01",
    }
    unit = dict(
        **key,
        reserved_raw="अनारक्षित",
        candidate_rows=2,
        district="District",
        block="Block",
        panchayat=None,
        unit="Village",
        seat_label="01",
        code_repeated=False,
        winner_note="",
        status="results",
    )
    candidates = [
        dict(
            **key,
            sr_no=1,
            row=i,
            candidate_name=f"Candidate {i}",
            remarks="0",
            candidate_woman_raw="",
            father_husband_name="",
            age=None,
            candidate_caste_raw="",
            education="",
            votes=10,
            page_sha256="source",
        )
        for i in (1, 2)
    ]
    winners = (
        [
            dict(
                **key,
                sr_no=1,
                row=2,
                candidate_name="Candidate 2",
                winner_basis="lot",
                votes=10,
            )
        ]
        if winner
        else []
    )
    return {
        "seats.parquet": [unit],
        "candidates.parquet": candidates,
        "winners.parquet": winners,
    }


def test_winner_uses_row_as_well_as_repeated_serial():
    seats, _ = convert(tables())
    assert [r["elected"] for r in seats[0]["seat_members"]] == [0, 1]
    assert seats[0]["winner"] == "Candidate 2"
    assert seats[0]["winner_basis"] == "lot"


def test_unresolved_tie_leaves_all_elected_flags_unknown():
    seats, _ = convert(tables(winner=False))
    assert [r["elected"] for r in seats[0]["seat_members"]] == ["", ""]


@pytest.mark.parametrize("ambiguous", [False, True])
def test_winner_must_match_exactly_one_candidate(ambiguous):
    inputs = tables()
    inputs["candidates.parquet"][0]["row"] = 2 if ambiguous else 3
    if not ambiguous:
        inputs["candidates.parquet"][1]["row"] = 4
    with pytest.raises(ValueError, match="does not identify one candidate"):
        convert(inputs)


def ruled(serial):
    inputs = tables(winner=False)
    inputs[REVIEWED] = {("mukhiya", "01", "001", "01"): serial}
    return inputs


def test_a_reviewed_ruling_fills_a_seat_the_release_names_no_winner_for():
    seats, _ = convert(ruled(1))
    assert seats[0]["winner"] == "Candidate 1"
    assert seats[0]["winner_basis"] == "argmax_votes"
    assert seats[0]["winner_ruling"] == RULING
    assert seats[0]["votes"] is None
    # both printed rows of the ruled candidate are that one person
    assert [r["elected"] for r in seats[0]["seat_members"]] == [1, 1]


def test_a_ruling_never_overrides_a_release_winner():
    inputs = tables()
    inputs[REVIEWED] = {("mukhiya", "01", "001", "01"): 1}
    with pytest.raises(ValueError, match="rulings applied to 0 of 1"):
        convert(inputs)


def test_a_ruling_naming_no_listed_candidate_stops_the_build():
    with pytest.raises(ValueError, match="names no listed candidate"):
        convert(ruled(9))
