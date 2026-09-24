"""The candidate-to-seat collapse.

The riskiest transformation here, because it is the only one that changes the
row count by design - so a bug is indistinguishable from correct behaviour by
row count alone. Every case below is a shape that actually occurs in Bihar,
Uttar Pradesh or Uttarakhand.
"""

import pytest

from local_elections.common import collapse


def rows(*specs):
    out = []
    for district, panchayat, caste, woman, votes, name in specs:
        out.append(
            {
                "district": district,
                "gram_panchayat": panchayat,
                "caste_reservation": caste,
                "woman_reserved": woman,
                "valid_vote": votes,
                "candidate_name": name,
            }
        )
    return out


KEY = ["district", "gram_panchayat"]


def test_many_candidates_become_one_seat():
    got = collapse.to_seats(
        rows(
            ("A", "X", "SC", "0", "10", "One"),
            ("A", "X", "SC", "0", "30", "Two"),
            ("A", "X", "SC", "0", "20", "Three"),
        ),
        KEY,
        vote_field="valid_vote",
    )
    assert len(got) == 1
    assert got[0]["seat_candidates"] == 3
    assert got[0]["winner"] == "Two"
    assert got[0]["winner_basis"] == "argmax_votes"
    assert got[0]["unit_of_observation"] == "seat_from_candidates"


def test_a_seat_whose_candidates_disagree_on_reservation_raises():
    """Every candidate for a seat contests the same seat. Two reservations
    under one key means the key is wrong, and picking the majority would hide
    a key that merges two real seats."""
    with pytest.raises(collapse.ReservationVaries):
        collapse.to_seats(
            rows(
                ("A", "X", "SC", "0", "10", "One"), ("A", "X", "NONE", "0", "30", "Two")
            ),
            KEY,
            vote_field="valid_vote",
        )


def test_a_tie_leaves_the_winner_blank():
    """Two people cannot both have won, and a coin toss recorded as fact is
    worse than a gap. Bihar has four of these."""
    got = collapse.to_seats(
        rows(("A", "X", "SC", "0", "30", "One"), ("A", "X", "SC", "0", "30", "Two")),
        KEY,
        vote_field="valid_vote",
    )
    assert got[0]["winner"] == ""
    assert got[0]["winner_basis"] == ""
    assert got[0]["seat_candidates"] == 2


def test_no_recorded_vote_is_not_zero_votes():
    """An uncontested seat and a seat nobody voted in are different things, and
    Bihar writes both. 24 of its seats carry no numeric vote at all."""
    got = collapse.to_seats(
        rows(("A", "X", "SC", "0", "--", "One")), KEY, vote_field="valid_vote"
    )
    assert got[0]["winner"] == ""
    assert collapse.votes_of("--") is None
    assert collapse.votes_of("0") == 0


def test_a_vote_count_with_a_tiebreak_note_still_reads():
    """Bihar writes one seat as "986+1 (BY LOT)"."""
    assert collapse.votes_of("986+1 (BY LOT)") == 986


def test_an_explicit_winner_marker_beats_counting_votes():
    """UP's 2021 file marks the winner, so nothing has to be inferred."""
    marked = rows(
        ("A", "X", "SC", "0", "10", "One"), ("A", "X", "SC", "0", "99", "Two")
    )
    marked[0]["result"] = "विजेता"
    marked[1]["result"] = "उपविजेता"
    got = collapse.to_seats(
        marked,
        KEY,
        vote_field="valid_vote",
        winner_field="result",
        winner_value="विजेता",
    )
    assert got[0]["winner"] == "One"
    assert got[0]["winner_basis"] == "published"


def test_two_marked_winners_fall_back_rather_than_guess():
    marked = rows(
        ("A", "X", "SC", "0", "10", "One"), ("A", "X", "SC", "0", "99", "Two")
    )
    marked[0]["result"] = marked[1]["result"] = "विजेता"
    got = collapse.to_seats(
        marked,
        KEY,
        vote_field="valid_vote",
        winner_field="result",
        winner_value="विजेता",
    )
    assert got[0]["winner"] == "Two"
    assert got[0]["winner_basis"] == "argmax_votes"


def test_seats_stay_separate_when_the_key_distinguishes_them():
    got = collapse.to_seats(
        rows(("A", "X", "SC", "0", "10", "One"), ("B", "X", "NONE", "0", "10", "Two")),
        KEY,
        vote_field="valid_vote",
    )
    assert len(got) == 2


def test_varies_measures_without_raising():
    """For sizing a source before deciding how to treat it - Uttarakhand's nine
    disagreeing seats are a finding to look at, not a reason to refuse a state."""
    got = collapse.varies(
        rows(
            ("A", "X", "SC", "0", "10", "One"),
            ("A", "X", "NONE", "0", "30", "Two"),
            ("A", "Y", "SC", "0", "10", "Three"),
        ),
        KEY,
    )
    assert len(got) == 1
    assert ("A", "X") in got


def test_the_candidate_rows_are_a_table_of_their_own():
    """The long form is not an appendage. Each candidate row carries the place,
    the office and the seat's reservation, so it reads without reconstructing
    the seat first, and `row_id` joins it back to the wide table."""
    from local_elections.common import master

    seats = collapse.to_seats(
        rows(("A", "X", "SC", "0", "10", "One"), ("A", "X", "SC", "0", "30", "Two")),
        KEY,
        vote_field="valid_vote",
    )
    seat = {
        "row_id": "abc123",
        "state": "Bihar",
        "district": "A",
        "gram_panchayat": "X",
        "tier": "gp_head",
        "caste_reservation": "SC",
        "woman_reserved": "0",
    }
    kept = master.candidates(seats[0], seat)
    assert [c["candidate_name"] for c in kept] == ["One", "Two"]
    assert [c["candidate_no"] for c in kept] == ["1", "2"]
    assert {c["row_id"] for c in kept} == {"abc123"}
    assert {c["district"] for c in kept} == {"A"}
    assert {c["caste_reservation"] for c in kept} == {"SC"}
    # every declared column present, and each candidate distinctly identified
    assert all(set(c) == set(master.CANDIDATE_COLUMNS) for c in kept)
    assert len({c["candidate_id"] for c in kept}) == 2


def test_the_seat_states_who_came_second_and_by_how_much():
    """Winner and runner-up are facts about the seat, so they belong in the wide
    table; the full field of candidates is a fact about the contest."""
    seats = collapse.to_seats(
        rows(
            ("A", "X", "SC", "0", "10", "One"),
            ("A", "X", "SC", "0", "30", "Two"),
            ("A", "X", "SC", "0", "25", "Three"),
        ),
        KEY,
        vote_field="valid_vote",
    )
    assert seats[0]["winner"] == "Two"
    assert seats[0]["runner_up"] == "Three"
    assert seats[0]["winner_votes"] == 30
    assert seats[0]["runner_up_votes"] == 25
    assert seats[0]["margin"] == 5
    assert [c["candidate_rank"] for c in seats[0]["seat_members"]] == [3, 1, 2]


def test_a_candidate_with_no_recorded_vote_gets_no_rank():
    """Ranking them last would assert they lost, which the source does not say."""
    seats = collapse.to_seats(
        rows(("A", "X", "SC", "0", "30", "One"), ("A", "X", "SC", "0", "--", "Two")),
        KEY,
        vote_field="valid_vote",
    )
    ranks = {c["candidate_name"]: c["candidate_rank"] for c in seats[0]["seat_members"]}
    assert ranks == {"One": 1, "Two": ""}


def test_a_tie_for_second_leaves_the_runner_up_blank():
    seats = collapse.to_seats(
        rows(
            ("A", "X", "SC", "0", "30", "One"),
            ("A", "X", "SC", "0", "10", "Two"),
            ("A", "X", "SC", "0", "10", "Three"),
        ),
        KEY,
        vote_field="valid_vote",
    )
    assert seats[0]["winner"] == "One"
    assert seats[0]["runner_up"] == ""
    assert seats[0]["margin"] == ""


def test_a_seat_level_source_contributes_no_candidate_rows():
    """Haryana states seats directly. Nothing to keep, and nothing to invent."""
    from local_elections.common import master

    assert master.candidates({"gram_panchayat": "X"}, {"row_id": "abc"}) == []


def test_a_stated_runner_up_needs_no_votes():
    """Uttar Pradesh's 2021 file marks विजेता and उपविजेता and records no vote
    total at all, only a percentage. A stated second place with no margin is
    the honest shape of that - better than turning a share back into a count."""
    marked = rows(
        ("A", "X", "SC", "0", "", "One"),
        ("A", "X", "SC", "0", "", "Two"),
        ("A", "X", "SC", "0", "", "Three"),
    )
    marked[0]["result"] = "विजेता"
    marked[1]["result"] = "उपविजेता"
    got = collapse.to_seats(
        marked,
        KEY,
        winner_field="result",
        winner_value="विजेता",
        runner_up_value="उपविजेता",
    )
    assert got[0]["winner"] == "One"
    assert got[0]["winner_basis"] == "published"
    assert got[0]["runner_up"] == "Two"
    assert got[0]["margin"] == ""
    assert got[0]["seat_candidates"] == 3
