"""The cross-state vocabulary: what an office is, and what a caste category means.

States print the same office under different names and different offices under
the same name. Pooling on the printed name is therefore not a naming
inconvenience, it is a correctness problem, and it fails silently - the row
counts stay plausible either way.

The one that proves it: **Bihar's "Sarpanch" is not the head of the gram
panchayat.** It heads the *gram kachahari*, the village court, which is a
separate elected body sharing the same geography. Bihar's gram panchayat head is
the Mukhiya. 7,849 panchayats hold both contests, and 88,868 wards hold both a
panch and a ward-member contest. Map Bihar's sarpanch onto Haryana's and a
pooled count of gram panchayat heads gains 7,849 seats that are not gram
panchayat heads at all - a 6% overstatement with nothing anywhere to flag it.

So every row carries two columns: `tier`, the canonical office, and
`tier_local`, the name the state actually printed. Nothing is lost, and anyone
who wants to group by the local vocabulary still can.
"""

import re

from local_elections.common import dictionary

# The canonical offices, with the body each belongs to.
TIER = {
    "gp_head": "head of the gram panchayat",
    "gp_vice_head": "vice-head of the gram panchayat",
    "gp_ward": "member of a gram panchayat ward",
    "block_member": "member of the block-level body",
    "block_head": "head of the block-level body",
    "block_vice_head": "vice-head of the block-level body",
    "zp_member": "member of the district-level body",
    "zp_head": "head of the district-level body",
    # The gram kachahari is a village court, elected alongside the panchayat but
    # not part of it. Bihar is the state in this corpus that elects one.
    "kachahari_head": "head of the gram kachahari (village court)",
    "kachahari_member": "member of the gram kachahari (village court)",
    # Declared so an urban row can be recognized and excluded by name rather
    # than by falling through as unknown.
    "ulb_ward": "member of an urban local body ward",
    "ulb_head": "head of an urban local body",
}

# Printed name -> canonical office, where the name means one thing everywhere.
TIER_OF_LOCAL = {
    "mukhiya": "gp_head",
    "pradhan": "gp_head",
    "ward": "gp_ward",
    "ward_member": "gp_ward",
    "panchayat_samiti": "block_member",
    "panchayat_samiti_member": "block_member",
    "zila_parishad": "zp_member",
    "zila_parishad_member": "zp_member",
    # West Bengal spells it with two Ls, in its own gazettes and its own Act.
    # tier_local records what the state calls the seat, so it keeps the state's
    # spelling and the mapping absorbs the difference.
    "zilla_parishad_member": "zp_member",
    "zila_pramukh": "zp_head",
    # Mumbai's municipal ward member
    "corporator": "ulb_ward",
    # Karnataka's gram panchayat president
    "adhyaksha": "gp_head",
    # Kerala names the body rather than the seat
    "grama_panchayat_member": "gp_ward",
    "block_panchayat_member": "block_member",
    "district_panchayat_member": "zp_member",
    # Assam's notification names the urban body explicitly. Keeping that local
    # name distinguishes these rows from the rural ward and head offices while
    # still giving the pooled layer a canonical urban tier.
    "municipal_board_ward": "ulb_ward",
    "municipal_board_chairperson": "ulb_head",
    # Uttarakhand
    "kshetra_panchayat_sadasya": "block_member",
    "zila_panchayat_sadasya": "zp_member",
    # Karnataka. The taluk panchayat is the block-level body and the zilla
    # panchayat the district-level one; only the names differ from Bihar's
    # panchayat samiti and zila parishad.
    "taluk_panchayat_member": "block_member",
    "zilla_panchayat_member": "zp_member",
    "pradhan_(gram_panchayat)": "gp_head",
    # Assam 2025
    "gaon_panchayat_president": "gp_head",
    "gaon_panchayat_ward_member": "gp_ward",
    "gaon_panchayat_vice_president": "gp_vice_head",
    "gaon_panchayat_vice-president": "gp_vice_head",
    "anchalik_panchayat_president": "block_head",
    "anchalik_panchayat_vice_president": "block_vice_head",
    "anchalik_panchayat_vice-president": "block_vice_head",
    "anchalik_panchayat_member": "block_member",
}

# Printed name -> canonical office, where the state has to decide it. Keep this
# table small: every entry here is a name that means two different things, and
# each one is a chance to pool two different offices together.
TIER_BY_STATE = {
    ("Bihar", "sarpanch"): "kachahari_head",
    ("Bihar", "panch"): "kachahari_member",
    ("Andhra Pradesh", "sarpanch"): "gp_head",
    ("Telangana", "sarpanch"): "gp_head",
    ("Jammu & Kashmir", "sarpanch"): "gp_head",
    ("Haryana", "sarpanch"): "gp_head",
    ("Rajasthan", "sarpanch"): "gp_head",
    ("Rajasthan", "panch"): "gp_ward",
}


# Rural, i.e. panchayati raj. The urban local bodies are out of scope for now -
# the Trivedi Centre holds that material - so the master is built from these and
# what it leaves out is recorded rather than quietly dropped. Kerala ships urban
# wards in the same file as rural ones, so this has to be a row-level filter.
RURAL_TIERS = {
    "gp_head",
    "gp_vice_head",
    "gp_ward",
    "block_member",
    "block_head",
    "block_vice_head",
    "zp_member",
    "zp_head",
    "kachahari_head",
    "kachahari_member",
}
URBAN_TIERS = {"ulb_ward", "ulb_head"}


def is_rural(tier):
    return tier in RURAL_TIERS


def tier_of(local, state):
    """The canonical office for a printed name, or None if it is not known.

    None is a real answer and callers must treat it as one. Guessing that an
    unrecognised office is a gram panchayat head is how Bihar's village court
    would get pooled with everyone else's panchayat.
    """
    # "Ward Member", "ward_member" and "ward member" are one name. Bihar prints
    # them spaced and this table is written with underscores.
    key = re.sub(r"[\s_]+", "_", (local or "").strip().lower())
    if (state, key) in TIER_BY_STATE:
        return TIER_BY_STATE[(state, key)]
    return TIER_OF_LOCAL.get(key)


# Which categories a state reserves for, so that a category never seen is
# checkable rather than merely absent. Kerala reserving no BC seat is the law,
# not a parsing failure; Goa suddenly reserving none would be a parsing failure.
CASTE_SCHEME = {
    "Assam": "sc_st_only",
    "Gujarat": "sc_st_bc",
    "Andhra Pradesh": "sc_st_bc",
    # the same commission's house style as Andhra Pradesh, and the same scheme
    "Telangana": "sc_st_bc",
    "Goa": "sc_st_bc",
    "Jharkhand": "sc_st_bc",
    # Haryana reserves for Block A of the Backward Classes list in panchayats
    # and prints it as BC_A, so the local label is finer than the pooled one.
    "Haryana": "sc_st_bca_only",
    # Mumbai's municipal wards reserve for SC, ST and OBC (27%), printed as OBC.
    "Maharashtra": "sc_st_obc",
    "Bihar": "sc_st_obc",
    "Rajasthan": "sc_st_obc",
    "Uttar Pradesh": "sc_st_obc",
    "Uttarakhand": "sc_st_obc",
    # No backward-class reservation exists in local bodies in either.
    "Karnataka": "sc_st_bca_bcb",
    "Kerala": "sc_st_only",
    "Jammu & Kashmir": "sc_st_only",
    # The 2018 delimitation gazettes head column (4) "Constituencies reserved
    # for ST/SC/BC persons" and print all three.
    "West Bengal": "sc_st_bc",
}

# The pooled categories each scheme can produce.
SCHEME_CATEGORIES = {
    "sc_st_bc": {"SC", "ST", "BC", "NONE"},
    "sc_st_bca_only": {"SC", "ST", "BC", "NONE"},
    "sc_st_obc": {"SC", "ST", "BC", "NONE"},
    "sc_st_only": {"SC", "ST", "NONE"},
    # Karnataka reserves separately for Backward Class A and Backward Class B,
    # which is finer than the single BC other states print. Both fold to BC
    # here and caste_reservation_local says which.
    "sc_st_bca_bcb": {"SC", "ST", "BC", "NONE"},
}


def caste_scheme(state):
    return CASTE_SCHEME.get(state)


def allowed_castes(state):
    """The pooled categories this state's rows may take, or None if unknown."""
    return SCHEME_CATEGORIES.get(CASTE_SCHEME.get(state, ""))


# The panchayat's name arrives under whichever term the state prints. The
# mapping lives in dictionary.py so there is one place that decides it; this
# reads it rather than repeating the list, which is how the two drifted before.
UNIT_COLUMNS = [
    "gram_panchayat",
    *sorted(
        alias
        for alias, canonical in dictionary.ALIAS_OF.items()
        if canonical == "gram_panchayat"
    ),
]


def unit_name(row):
    """The panchayat's name, whatever the source calls the column.

    Raises when a row carries two of them. The whole point of coalescing is that
    exactly one is ever populated; if two were, the coalesce would silently
    prefer one and drop the other, and nobody would see which.
    """
    present = [c for c in UNIT_COLUMNS if (row.get(c) or "").strip()]
    if len(present) > 1:
        raise ValueError(
            f"row names the panchayat in {present}: { {c: row[c] for c in present} }"
        )
    return row.get(present[0], "") if present else ""


SEAT_IDENTITY_FIELDS = (
    "state",
    "year",
    "election_type",
    "election_duration",
    "tier",
    "district",
    "block",
    "body",
    "gp_no",
    "gram_panchayat",
    "ward_no",
    "ward_name",
    "seat_no",
)


def seat_identity(row):
    """The standardized seat key used by the master and every shared check."""
    values = []
    for field in SEAT_IDENTITY_FIELDS:
        value = unit_name(row) if field == "gram_panchayat" else row.get(field, "")
        values.append(str(value or "").strip())
    return tuple(values)
