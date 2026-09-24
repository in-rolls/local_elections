"""Independent printed controls for parsed Assam 2025 notifications."""

import collections

HELD_DISTRICT_NOTIFICATIONS = 27
PARSED_DISTRICTS = (
    "Charaideo",
    "Kamrup Metropolitan",
    "South Salmara-Mankachar",
    "Hailakandi",
)
UNPARSED_DISTRICT_NOTIFICATIONS = HELD_DISTRICT_NOTIFICATIONS - len(PARSED_DISTRICTS)
PARSED_DISTRICT_LABEL = (
    ", ".join(PARSED_DISTRICTS[:-1]) + f", and {PARSED_DISTRICTS[-1]}"
)
REGISTRY_SCOPE = (
    f"{PARSED_DISTRICT_LABEL} are {len(PARSED_DISTRICTS)} of "
    f"{HELD_DISTRICT_NOTIFICATIONS} held district notifications; the coverage "
    f"table keeps the remaining {UNPARSED_DISTRICT_NOTIFICATIONS} visible as "
    "unparsed work"
)

BLOCK_GP_COUNTS = {"Sonari": 8, "Sapekhati": 11, "Mahmora": 11, "Lakwa": 6}
EXPECTED_ROWS = {
    "gp_ward": 360,
    "gp_head": 36,
    "gp_vice_head": 36,
    "block_member": 36,
    "block_head": 4,
    "block_vice_head": 4,
    "zp_member": 8,
}
CATEGORY_COUNTS = {
    "gp_ward": collections.Counter(
        {
            ("NONE", 0): 176,
            ("NONE", 1): 174,
            ("SC", 0): 1,
            ("SC", 1): 2,
            ("ST", 0): 3,
            ("ST", 1): 4,
        }
    ),
    "gp_head": collections.Counter(
        {("NONE", 0): 18, ("NONE", 1): 16, ("SC", 1): 1, ("ST", 1): 1}
    ),
    "gp_vice_head": collections.Counter(
        {("NONE", 0): 17, ("NONE", 1): 17, ("SC", 1): 1, ("ST", 0): 1}
    ),
    "block_member": collections.Counter({("NONE", 0): 18, ("NONE", 1): 18}),
    "block_head": collections.Counter({("NONE", 0): 2, ("NONE", 1): 2}),
    "block_vice_head": collections.Counter({("NONE", 0): 2, ("NONE", 1): 2}),
    "zp_member": collections.Counter({("NONE", 0): 4, ("NONE", 1): 4}),
}

KAMRUP_METROPOLITAN_BLOCK_GP_COUNTS = {
    "Ramcharani": 5,
    "Chandrapur": 3,
    "Dimoria": 12,
}
KAMRUP_METROPOLITAN_EXPECTED_ROWS = {
    "gp_ward": 200,
    "gp_head": 20,
    "gp_vice_head": 20,
    "block_member": 20,
    "block_head": 3,
    "block_vice_head": 3,
    "zp_member": 6,
}
KAMRUP_METROPOLITAN_CATEGORY_COUNTS = {
    "gp_ward": collections.Counter(
        {
            ("NONE", 0): 83,
            ("NONE", 1): 81,
            ("SC", 0): 10,
            ("SC", 1): 9,
            ("ST", 0): 7,
            ("ST", 1): 10,
        }
    ),
    "gp_head": collections.Counter(
        {
            ("NONE", 0): 8,
            ("NONE", 1): 8,
            ("SC", 0): 1,
            ("SC", 1): 1,
            ("ST", 0): 1,
            ("ST", 1): 1,
        }
    ),
    "gp_vice_head": collections.Counter(
        {
            ("NONE", 0): 9,
            ("NONE", 1): 7,
            ("SC", 0): 1,
            ("SC", 1): 1,
            ("ST", 0): 1,
            ("ST", 1): 1,
        }
    ),
    "block_member": collections.Counter(
        {
            ("NONE", 0): 7,
            ("NONE", 1): 9,
            ("SC", 0): 1,
            ("SC", 1): 1,
            ("ST", 0): 1,
            ("ST", 1): 1,
        }
    ),
    "block_head": collections.Counter({("NONE", 0): 1, ("NONE", 1): 2}),
    "block_vice_head": collections.Counter({("NONE", 0): 1, ("NONE", 1): 2}),
    "zp_member": collections.Counter(
        {("NONE", 0): 2, ("NONE", 1): 2, ("SC", 0): 1, ("ST", 1): 1}
    ),
}

SOUTH_SALMARA_EXPECTED_ROWS = {
    "gp_ward": 350,
    "gp_head": 35,
    "gp_vice_head": 35,
    "block_member": 35,
    "block_head": 2,
    "block_vice_head": 2,
    "zp_member": 4,
}
SOUTH_SALMARA_CATEGORY_COUNTS = {
    "gp_ward": collections.Counter(
        {
            ("NONE", 0): 171,
            ("NONE", 1): 170,
            ("SC", 0): 3,
            ("SC", 1): 4,
            ("ST", 0): 1,
            ("ST", 1): 1,
        }
    ),
    "gp_head": collections.Counter({("NONE", 0): 17, ("NONE", 1): 17, ("SC", 1): 1}),
    "gp_vice_head": collections.Counter(
        {("NONE", 0): 17, ("NONE", 1): 17, ("SC", 1): 1}
    ),
    "block_member": collections.Counter({("NONE", 0): 17, ("NONE", 1): 18}),
    "block_head": collections.Counter({("NONE", 0): 1, ("NONE", 1): 1}),
    "block_vice_head": collections.Counter({("NONE", 0): 1, ("NONE", 1): 1}),
    "zp_member": collections.Counter({("NONE", 0): 2, ("NONE", 1): 2}),
}

HAILAKANDI_BLOCK_GP_COUNTS = {
    "Hailakandi": 14,
    "Katlicherra": 9,
    "South Hailakandi": 7,
    "Algapur": 17,
    "Lala": 15,
}
HAILAKANDI_EXPECTED_ROWS = {
    "gp_ward": 344,
    "gp_head": 33,
    "gp_vice_head": 34,
    "block_member": 36,
    "block_head": 4,
    "block_vice_head": 4,
    "zp_member": 4,
}
HAILAKANDI_CATEGORY_COUNTS = {
    "gp_ward": collections.Counter({("NONE", 1): 271, ("SC", 1): 41, ("SC", 0): 32}),
    "gp_head": collections.Counter({("NONE", 1): 26, ("SC", 1): 4, ("SC", 0): 3}),
    "gp_vice_head": collections.Counter({("NONE", 1): 27, ("SC", 1): 4, ("SC", 0): 3}),
    "block_member": collections.Counter({("NONE", 1): 27, ("SC", 1): 6, ("SC", 0): 3}),
    "block_head": collections.Counter({("NONE", 1): 3, ("SC", 0): 1}),
    "block_vice_head": collections.Counter({("NONE", 1): 3, ("SC", 0): 1}),
    "zp_member": collections.Counter({("NONE", 1): 3, ("SC", 1): 1}),
}

TOTAL_EXPECTED_ROWS = {
    tier: EXPECTED_ROWS[tier]
    + KAMRUP_METROPOLITAN_EXPECTED_ROWS[tier]
    + SOUTH_SALMARA_EXPECTED_ROWS[tier]
    + HAILAKANDI_EXPECTED_ROWS[tier]
    for tier in EXPECTED_ROWS
}
