"""Resolved winners must survive the candidate-level conversion."""

import pytest

from local_reservations.common.adapters.bihar_2016 import convert


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
        seat_reservation="अनारक्षित",
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
            gender_raw="",
            father_husband_name="",
            age=None,
            category="",
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
