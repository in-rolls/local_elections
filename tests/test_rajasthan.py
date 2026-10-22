import collections

import pytest

from local_elections.common import canon, reference
from local_elections.common.adapters import rajasthan
from local_elections.paths import ROOT


@pytest.fixture(scope="module")
def sibling():
    path = ROOT.parent / rajasthan.REPO
    if not path.exists():
        pytest.skip("Rajasthan sibling repository is not checked out")
    return path


@pytest.fixture(scope="module")
def slices(sibling):
    return list(rajasthan.slices(sibling))


def test_all_structured_rural_seats_are_adapted(slices):
    counts = collections.Counter(
        (row["tier"], row["year"]) for slice_ in slices for row in slice_["rows"]
    )
    assert counts == collections.Counter(rajasthan.DECLARED_UNITS)
    assert sum(counts.values()) == 162502


def test_panchayat_samiti_result_roster_is_retained(slices):
    rows = [
        row
        for slice_ in slices
        for row in slice_["rows"]
        if row["tier"] == "block_member" and row["year"] == "2010"
    ]
    assert len(rows) == 5273
    assert len(
        {(row["district"], row["block"], row["seat_no"]) for row in rows}
    ) == len(rows)
    assert collections.Counter(row["reservation_raw"] for row in rows) == {
        "GEN": 1378,
        "GENW": 1345,
        "SC": 510,
        "SCW": 423,
        "ST": 454,
        "STW": 372,
        "OBC": 446,
        "OBCW": 345,
    }

    bhim = [
        row
        for row in rows
        if row["district"] == "RAJSAMAND"
        and row["block"] == "BHIM"
        and row["ward_no_raw"] == "17"
    ]
    assert len(bhim) == 1
    assert bhim[0]["seat_no"] == "16"

    contradiction = [row for row in rows if row["winner_category_sex_agree"] == "0"]
    assert len(contradiction) == 1
    assert contradiction[0]["winner"] == "MAGADU"
    assert contradiction[0]["winner_gender"] == "Other than Woman"
    assert contradiction[0]["winner_category_raw"] == "OBCW"


def test_2005_panchayat_samiti_source_exceptions_are_retained(slices):
    assert reference.document_stage("Rajasthan", "2005", "block_member") == "result"
    rows = [
        row
        for slice_ in slices
        for row in slice_["rows"]
        if row["tier"] == "block_member" and row["year"] == "2005"
    ]
    assert len(rows) == 5257
    assert len(
        {(row["district"], row["block"], row["seat_no"]) for row in rows}
    ) == len(rows)
    assert collections.Counter(row["reservation_raw"] for row in rows) == {
        "GEN": 1780,
        "GEN W": 919,
        "SC": 635,
        "SC W": 311,
        "ST": 549,
        "ST W": 256,
        "OBC": 555,
        "OBC W": 252,
    }

    vacancy = [row for row in rows if row["vacant"] == 1]
    assert len(vacancy) == 1
    assert (vacancy[0]["district"], vacancy[0]["block"], vacancy[0]["seat_no"]) == (
        "BARAN",
        "SHAHBAD",
        "11",
    )
    assert not vacancy[0]["winner"]

    control_conflict = [
        row for row in rows if row["reservation_body_control_agree"] == "0"
    ]
    assert len(control_conflict) == 1
    assert control_conflict[0]["reservation_raw"] == "OBC W"

    margin_conflicts = [row for row in rows if row["margin_below_votes"] == "0"]
    assert len(margin_conflicts) == 3


def test_zila_parishad_result_rosters_are_retained(slices):
    assert reference.document_stage("Rajasthan", "2005", "zp_member") == "result"
    assert reference.document_stage("Rajasthan", "2010", "zp_member") == "result"
    rows = [
        row for slice_ in slices for row in slice_["rows"] if row["tier"] == "zp_member"
    ]
    assert collections.Counter(row["year"] for row in rows) == {
        "2005": 1008,
        "2010": 1013,
    }
    assert len({(row["year"], row["district"], row["seat_no"]) for row in rows}) == len(
        rows
    )

    vacancy = [row for row in rows if row["vacant"] == 1]
    assert len(vacancy) == 1
    assert (vacancy[0]["year"], vacancy[0]["district"], vacancy[0]["seat_no"]) == (
        "2005",
        "BARAN",
        "13",
    )

    churu = [row for row in rows if row["district"] == "CHURU"]
    assert len(churu) == 54
    assert {row["ward_no_raw"] for row in churu if row["seat_no"] == "1"} == {"5"}
    assert all(row["ward_no_inferred"] == "1" for row in churu)

    jaipur_two = [
        row
        for row in rows
        if row["year"] == "2005"
        and row["district"] == "JAIPUR"
        and row["seat_no"] == "2"
    ]
    assert len(jaipur_two) == 1
    assert jaipur_two[0]["unopposed"] == "1"
    assert jaipur_two[0]["unopposed_inferred"] == "1"


def test_all_sarpanch_candidates_are_retained(slices):
    heads = [
        row for slice_ in slices for row in slice_["rows"] if row["tier"] == "gp_head"
    ]
    members = [member for row in heads for member in row.get("seat_members", [])]
    assert len(members) == rajasthan.DECLARED[rajasthan.CONTESTING_FILE]
    assert sum(member["result"] == "winner" for member in members) == 11257
    assert all(
        "MobileNo" not in member and "EmailAddress" not in member for member in members
    )
    assert members[0]["candidate_occupation"]
    assert members[0]["candidate_marital_status"]
    ambiguous = [row for row in heads if row.get("winner_candidate_ambiguous")]
    assert len(ambiguous) == 175


def test_result_and_roster_limits_are_explicit(slices):
    heads_2020 = [
        row
        for slice_ in slices
        for row in slice_["rows"]
        if row["tier"] == "gp_head" and row["year"] == "2020"
    ]
    roster_only = [row for row in heads_2020 if not row.get("seat_members")]
    assert {row["gram_panchayat"].upper() for row in roster_only} == {
        "RIBIYA",
        "KALEWA",
        "GOLA KA BAS",
        "SAMBHARIA",
    }
    candidate_only = [
        row
        for slice_ in slices
        for row in slice_["rows"]
        if row["tier"] == "gp_head"
        and row.get("seat_members")
        and not row.get("winner")
    ]
    assert len(candidate_only) == 13
    assert all(row["listing_scope"] == "all_seats" for row in candidate_only)


def test_old_panel_winner_gender_is_not_dropped(slices):
    rows = [
        row
        for slice_ in slices
        for row in slice_["rows"]
        if row["tier"] == "gp_head" and row["year"] == "2015"
    ]
    assert {row["winner_gender"] for row in rows} == {
        "Woman",
        "Other than Woman",
    }


def test_old_panel_printed_gp_name_controls_seat_identity(slices):
    rows = [
        row
        for slice_ in slices
        for row in slice_["rows"]
        if row["tier"] == "gp_head" and row["year"] == "2005"
    ]
    keys = collections.Counter(canon.seat_identity(row) for row in rows)
    collisions = {key: count for key, count in keys.items() if count > 1}
    assert sum(collisions.values()) == 7
    assert len(collisions) == 3

    daulatpura = [
        row
        for row in rows
        if row["district"] == "AJMER"
        and row["block"] == "MASUDA"
        and row["winner"] in {"DESHRAJ", "KARAN SINGH"}
    ]
    assert {row["gram_panchayat"] for row in daulatpura} == {
        "DAULATPURA-I",
        "DAULATPURA-II",
    }
    assert len({row["gram_panchayat_standardized"] for row in daulatpura}) == 1


def test_blank_ward_winners_are_explicitly_vacant(slices):
    rows = [
        row
        for slice_ in slices
        for row in slice_["rows"]
        if row["tier"] == "gp_ward" and not row["winner"]
    ]
    assert len(rows) == 2
    assert all(row["vacant"] == 1 for row in rows)
    assert all(not row["winner_gender"] and not row["winner_caste"] for row in rows)
    assert {row["winner_category_raw"] for row in rows} == {"ST", "ST (Woman)"}


def test_nomination_summaries_keep_their_own_grain(sibling):
    table = rajasthan.supplemental(sibling)
    assert table["name"] == "supplemental_rajasthan_nomination_stats.parquet"
    assert len(table["rows"]) == rajasthan.DECLARED[rajasthan.NOMINATION_FILE]
    assert collections.Counter(
        row["year"] for row in table["rows"]
    ) == collections.Counter(rajasthan.NOMINATION_UNITS)
    assert len({row["row_id"] for row in table["rows"]}) == len(table["rows"])
