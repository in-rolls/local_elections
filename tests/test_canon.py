"""The canonical vocabulary, and the assumptions the pooled table rests on.

These are not style checks. Each one guards a way of silently pooling two
different things, which is the failure this repository keeps meeting: the row
counts stay plausible whichever way it goes.
"""

import pytest

from local_elections.common import canon, datasets, dictionary

# --------------------------------------------------------------- the tiers


def test_bihar_sarpanch_is_not_a_panchayat_head():
    """The single most expensive mapping in the corpus.

    Bihar's Sarpanch heads the gram kachahari, a village court; its gram
    panchayat head is the Mukhiya. 7,849 panchayats hold both contests and the
    winner differs in 99.8% of them. Pool Bihar's sarpanch with Haryana's and a
    national count of panchayat heads gains 7,849 seats that are not panchayat
    heads, with nothing to flag it.
    """
    assert canon.tier_of("sarpanch", "Bihar") == "kachahari_head"
    assert canon.tier_of("panch", "Bihar") == "kachahari_member"
    assert canon.tier_of("mukhiya", "Bihar") == "gp_head"


@pytest.mark.parametrize(
    "state", ["Haryana", "Rajasthan", "Andhra Pradesh", "Jammu & Kashmir"]
)
def test_sarpanch_is_a_panchayat_head_everywhere_else(state):
    assert canon.tier_of("sarpanch", state) == "gp_head"


def test_the_same_office_under_two_names_pools():
    """Jharkhand calls the panchayat's ward member a ward_member and everyone
    else calls it a ward. Same seat, and it has to land in one bucket."""
    assert canon.tier_of("ward", "Goa") == canon.tier_of("ward_member", "Jharkhand")


def test_an_unknown_office_is_not_guessed():
    """None is a real answer. Defaulting an unrecognised office to gp_head is
    how a village court gets counted as a panchayat."""
    assert canon.tier_of("chairperson", "Kerala") is None
    assert canon.tier_of("", "Goa") is None


def test_every_mapping_lands_on_a_declared_tier():
    mapped = set(canon.TIER_OF_LOCAL.values()) | set(canon.TIER_BY_STATE.values())
    assert mapped <= set(canon.TIER)


def test_rural_and_urban_partition_the_tiers():
    assert set(canon.TIER) == canon.RURAL_TIERS | canon.URBAN_TIERS
    assert not canon.RURAL_TIERS & canon.URBAN_TIERS


def test_assam_president_and_vice_president_are_distinct_offices():
    assert canon.tier_of("Gaon Panchayat President", "Assam") == "gp_head"
    assert canon.tier_of("Gaon Panchayat Vice-President", "Assam") == "gp_vice_head"
    assert (
        canon.tier_of("Anchalik Panchayat Vice-President", "Assam") == "block_vice_head"
    )


def test_every_tier_in_the_data_is_canonical_and_maps_back():
    """Read against the shipped files, so a parser writing an unmapped tier
    fails here rather than turning up as a hole in the pooled table."""
    for path, rows in datasets.parsed():
        for row in rows:
            assert row["tier"] in canon.TIER, f"{path.name}: {row['tier']!r}"
            local = row.get("tier_local", "")
            assert local, f"{path.name}: tier_local is blank"
            assert canon.tier_of(local, row["state"]) == row["tier"], (
                f"{path.name}: {local!r} in {row['state']} should map to "
                f"{row['tier']!r}"
            )
            break


def test_no_local_name_maps_to_two_tiers_within_a_state():
    seen = {}
    for _, rows in datasets.parsed():
        for row in rows:
            key = (row["state"], row.get("tier_local", ""))
            if key in seen:
                assert seen[key] == row["tier"], (
                    f"{key} -> {seen[key]} and {row['tier']}"
                )
            else:
                seen[key] = row["tier"]


# ------------------------------------------------------------ caste schemes


def test_kerala_reserving_no_backward_class_seat_is_lawful():
    """Kerala reserves no BC seat in local bodies, so zero BC rows is the law
    rather than a parsing failure - and Goa suddenly showing zero would be a
    failure. The scheme is what makes the two distinguishable."""
    assert "BC" not in canon.allowed_castes("Kerala")
    assert "BC" in canon.allowed_castes("Goa")


def test_every_state_in_the_data_declares_a_caste_scheme():
    for _, rows in datasets.parsed():
        assert canon.caste_scheme(rows[0]["state"]), rows[0]["state"]


def test_observed_categories_stay_inside_the_declared_scheme():
    for path, rows in datasets.parsed():
        allowed = canon.allowed_castes(rows[0]["state"])
        seen = {r["caste_reservation"] for r in rows}
        assert seen <= allowed, f"{path.name}: {seen - allowed}"


# ------------------------------------------------- the panchayat name column


def test_the_alias_family_is_read_from_the_dictionary():
    """It was a hardcoded list in checks.py and a docstring in dictionary.py,
    which is two places to disagree. canon reads the dictionary."""
    assert "halqa" in canon.UNIT_COLUMNS
    assert canon.UNIT_COLUMNS[0] == "gram_panchayat"


def test_unit_name_reads_whichever_column_the_state_used():
    assert canon.unit_name({"gram_panchayat": "Agali"}) == "Agali"
    assert canon.unit_name({"halqa": "Kupwara A"}) == "Kupwara A"
    assert canon.unit_name({"district": "X"}) == ""


def test_two_names_in_one_row_raises():
    """The coalesce assumes exactly one is ever populated. If two were, it would
    silently prefer one and drop the other, and nobody would see which - so this
    is the one place the assumption is enforced rather than trusted."""
    with pytest.raises(ValueError, match=r"\w"):
        canon.unit_name({"gram_panchayat": "Agali", "halqa": "Kupwara A"})


def test_no_shipped_row_names_the_panchayat_twice():
    for _path, rows in datasets.parsed():
        for row in rows:
            canon.unit_name(row)


def test_every_alias_resolves_and_is_not_itself_required():
    """The alias branch in expectations.py was unreachable because every alias
    was also a declared column, so BY_NAME always matched first. Keep it
    reachable: an alias must name a real column and must not be required."""
    for alias, canonical in dictionary.ALIAS_OF.items():
        assert canonical in dictionary.BY_NAME, f"{alias} -> {canonical}"
        spec = dictionary.BY_NAME.get(alias)
        assert not (spec and spec.get("required")), alias
