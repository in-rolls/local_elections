"""The per-slice check catalogue.

The behaviours pinned here are the ones that decide whether a check can catch
anything, rather than the arithmetic inside any one of them.
"""

import pytest

from local_elections.common import checks, master, notes
from local_elections.common import slice_checks as sc

# Slice wants a root; these fixtures never read from it.
ROOT = "."


def make(rows, state="Goa", year="2012", tier="gp_ward"):
    base = {
        "state": state,
        "year": year,
        "tier": tier,
        "tier_local": "ward",
        "caste_reservation": "NONE",
        "woman_reserved": "0",
        "reservation": "Other than Woman",
        "district": "North Goa",
        "block": "Bardez",
        "gram_panchayat": "Anjuna",
        "ward_no": "1",
        "source_path": "readme.md",
        "source_page": "1",
    }
    return sc.Slice(state, year, tier, [dict(base, **r) for r in rows], ROOT)


# ------------------------------------------------------- skip is not a pass


def test_a_skip_is_not_a_pass():
    """The distinction that cost the two largest slices in the repository their
    row-loss check: rows_in_band skipped them for want of a declared band, and
    a skip that reads as a pass is how it went unnoticed for months."""
    got = sc.rows_in_band(make([{}], state="Nowhere"))
    assert got["status"] == sc.SKIP
    assert got["status"] != sc.PASS
    assert "no row band declared" in got["detail"]


def test_a_skipped_declared_check_fails_once_the_slice_is_large():
    big = make([{} for _ in range(sc.SKIP_FLOOR + 1)], state="Nowhere")
    statuses = {c["check_id"]: c["status"] for c in sc.run(big)}
    assert statuses["rows_in_band"] == sc.FAIL


def test_a_small_slice_may_still_skip():
    small = make([{} for _ in range(10)], state="Nowhere")
    statuses = {c["check_id"]: c["status"] for c in sc.run(small)}
    assert statuses["rows_in_band"] == sc.SKIP


def test_an_external_skip_is_never_escalated():
    """A missing published total is a fact about the world, not a rule we
    forgot to declare, so no amount of rows makes it our fault."""
    big = make([{} for _ in range(sc.SKIP_FLOOR + 1)], state="Nowhere")
    got = {c["check_id"]: c for c in sc.run(big)}["coverage_vs_published"]
    assert got["status"] == sc.SKIP


# ------------------------------------------------------------ caste schemes


def test_a_category_outside_the_declared_scheme_fails():
    """Kerala reserves no backward-class seat, so a BC row there is a defect -
    while zero BC rows is the law. Only the declared scheme separates the two."""
    got = sc.caste_scheme_respected(make([{"caste_reservation": "BC"}], state="Kerala"))
    assert got["status"] == sc.FAIL


def test_a_scheme_with_no_backward_class_passes_on_absence():
    got = sc.caste_scheme_respected(make([{"caste_reservation": "SC"}], state="Kerala"))
    assert got["status"] == sc.PASS


# ------------------------------------------------------ the statutory share


def test_a_partial_listing_is_not_measured_against_the_statute():
    """Goa's 2017 file is a nomination-stage listing covering about half the
    wards. Its 27% women is a property of that document, and checking it
    against the one-third floor reports a violation that is not one."""
    got = sc.women_share_vs_statute(make([{}], state="Goa", year="2017"))
    assert got["status"] == sc.SKIP
    assert "partial" in got["detail"]


def test_the_statute_is_measured_only_where_a_gender_was_stated():
    """A code whose gender marker did not survive the scan is unknown, not male,
    but woman_reserved is 0 there by default. Andhra Pradesh's wards read 46.8%
    over every row and 50.9% over the rows whose gender the source states."""
    rows = (
        [{"woman_reserved": "1", "gender_stated": "1"}] * 9
        + [{"woman_reserved": "0", "gender_stated": "1"}] * 9
        + [{"woman_reserved": "0", "gender_stated": "0"}] * 2
    )
    got = sc.women_share_vs_statute(
        make(rows, state="Andhra Pradesh", year="2020", tier="gp_head")
    )
    assert got["observed"] == "50.0%"
    assert got["status"] == sc.PASS
    assert "whose gender the source states" in got["detail"]
    assert "45.0% over all 20" in got["detail"]


def test_no_share_is_estimated_when_too_many_genders_are_unstated():
    """The filter cannot be trusted when much is missing, because the markers
    are not lost at equal rates - Prakasam loses (G) about twice as often as
    (W), so its stated rows read 66% women against a statutory half. Neither
    number estimates the truth, so the slice is not measured."""
    rows = [{"woman_reserved": "1", "gender_stated": "1"}] * 6 + [
        {"woman_reserved": "0", "gender_stated": "0"}
    ] * 4
    got = sc.women_share_vs_statute(
        make(rows, state="Andhra Pradesh", year="2020", tier="gp_head")
    )
    assert got["status"] == sc.SKIP
    assert "not missing at random" in got["detail"]


def test_a_floor_is_not_a_target():
    """ "Not less than one third" is the wording of the 73rd Amendment, so more
    is compliance. Passing the wrong rule turned J&K's 48% into a failure."""
    rows = [{"woman_reserved": "1"}] * 48 + [{"woman_reserved": "0"}] * 52
    got = sc.women_share_vs_statute(make(rows, state="Jammu & Kashmir", year="2010"))
    assert got["status"] == sc.PASS


# ---------------------------------------------------------- internal checks


def test_a_row_naming_the_panchayat_twice_fails():
    got = sc.alias_family_exclusive(make([{"halqa": "Kupwara A"}]))
    assert got["status"] == sc.FAIL


def test_the_label_must_agree_with_the_two_fields_it_summarises():
    got = sc.label_agrees(
        make([{"caste_reservation": "SC", "reservation": "Other than Woman"}])
    )
    assert got["status"] == sc.FAIL


def test_reservation_may_change_between_election_events():
    got = sc.reservation_constant_within_seat(
        make(
            [
                {
                    "unit_of_observation": "seat_from_candidates",
                    "election_type": "General Election",
                    "election_duration": "JAN-MAR 2020",
                },
                {
                    "unit_of_observation": "seat_from_candidates",
                    "election_type": "By Election",
                    "election_duration": "SEP-OCT 2020",
                    "caste_reservation": "SC",
                    "woman_reserved": "1",
                    "reservation": "SC Woman",
                },
            ]
        )
    )
    assert got["status"] == sc.PASS


def test_reservation_must_be_constant_within_one_election_event():
    got = sc.reservation_constant_within_seat(
        make(
            [
                {
                    "unit_of_observation": "seat_from_candidates",
                    "election_type": "General Election",
                    "election_duration": "JAN-MAR 2020",
                },
                {
                    "unit_of_observation": "seat_from_candidates",
                    "election_type": "General Election",
                    "election_duration": "JAN-MAR 2020",
                    "caste_reservation": "SC",
                    "woman_reserved": "1",
                    "reservation": "SC Woman",
                },
            ]
        )
    )
    assert got["status"] == sc.FAIL


def test_two_cycles_in_one_slice_fails():
    got = sc.year_constant(make([{"year": "2012"}, {"year": "2017"}]))
    assert got["status"] == sc.FAIL


def test_a_local_office_name_must_map_to_the_slices_tier():
    got = sc.tier_local_maps_to_one_tier(
        make([{"tier_local": "mukhiya"}], tier="gp_ward")
    )
    assert got["status"] == sc.FAIL


def test_duplicate_seats_are_counted_not_hidden():
    got = sc.seat_key_unique(make([{}, {}, {}]))
    assert got["status"] == sc.WARN
    assert got["observed"] == "3"


def test_named_constituencies_distinguish_upper_tier_seats():
    got = sc.seat_key_unique(
        make(
            [
                {"ward_no": "", "ward_name": "Rani Chapari"},
                {"ward_no": "", "ward_name": "Deepor Beel"},
            ],
            state="Assam",
            year="2025",
            tier="zp_member",
        )
    )
    assert got["status"] == sc.PASS


def test_named_constituencies_use_one_shared_seat_identity():
    sliced = make(
        [
            {"ward_no": "", "ward_name": "Rani Chapari"},
            {"ward_no": "", "ward_name": "Deepor Beel"},
        ],
        state="Assam",
        year="2025",
        tier="zp_member",
    )
    assert sc.seat_key_unique(sliced)["status"] == sc.PASS
    assert notes.seat_key_not_unique(sliced) is None
    report = checks.Report("shared seat identity")
    checks.structural(report, sliced.rows, ROOT)
    assert report.warned == 0
    assert master.seat_key(sliced.rows[0]) != master.seat_key(sliced.rows[1])


def test_repeated_ward_numbers_with_distinct_names_are_distinct_seats():
    sliced = make(
        [
            {"ward_no": "VII", "ward_name": "Chakwa-B"},
            {"ward_no": "VII", "ward_name": "Sesal"},
        ],
        state="Jammu & Kashmir",
        year="2016",
        tier="gp_ward",
    )
    assert sc.seat_key_unique(sliced)["status"] == sc.PASS
    assert master.seat_key(sliced.rows[0]) != master.seat_key(sliced.rows[1])


def test_shared_validator_counts_rows_not_duplicate_groups(capsys):
    sliced = make([{"ward_name": "North"}, {"ward_name": "North"}])
    assert sc.seat_key_unique(sliced)["observed"] == "2"
    assert notes.seat_key_not_unique(sliced)["rows_affected"] == 2
    assert master.seat_key(sliced.rows[0]) == master.seat_key(sliced.rows[1])
    report = checks.Report("shared seat identity")
    checks.structural(report, sliced.rows, ROOT)
    assert report.warned == 1
    assert "2 rows across 1 duplicated keys" in capsys.readouterr().out


def test_source_declared_partial_blanks_do_not_become_parser_warnings():
    rows = [{"ward_name": ""}] * 4 + [{"ward_name": "Majirgaon"}]
    got = sc.blank_share_within_tolerance(
        make(rows, state="Assam", year="2025", tier="gp_ward")
    )
    assert got["status"] == sc.PASS
    assert "Charaideo numbers wards" in got["detail"]


# ----------------------------------------------------- every check declares


@pytest.mark.parametrize("spec", sc.CHECKS, ids=lambda s: s["id"])
def test_every_check_declares_what_it_appeals_to(spec):
    assert spec["appeals_to"] in ("internal", "declared", "external")


def test_at_least_one_check_appeals_outside_our_own_output():
    """An all-internal battery confirms a file agrees with itself, which it
    does whether or not a category was misread."""
    assert any(c["appeals_to"] == "external" for c in sc.CHECKS)
