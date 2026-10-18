"""Bihar, from local_elections_bihar.

The largest single source in the corpus and the first candidate-level one, now
in two manifested releases rather than loose files: 227,317 seats and 644,537
candidate rows for the 2016 general election, and 247,671 seats with 924,708
candidates for 2021. This module only chains the two; each reads its own
release and states its own pins.

Six posts across two bodies. Bihar elects a **gram kachahari** - a village court
- alongside the gram panchayat, over the same geography, on the same day. Its
head is the *sarpanch* and its members are *panch*. The panchayat's head is the
*mukhiya* and its members are ward members. So the file called `sarpanch.csv`
is not this state's gram panchayat heads, and `canon.TIER_BY_STATE` says so:
7,916 sarpanch seats pooled as `gp_head` would overstate India's gram panchayat
heads by that much with nothing anywhere to flag it.

**What reading the release settled.** The 2016 scrape this adapter used to parse
kept its rows and nothing else, and four things about it failed silently. The
`number` column read `Piprasi/SEMRA LABEDAHA/01` with no district, so two blocks
of the same name in different districts merged and the row count stayed
plausible. Wards keyed on a name alone collapsed to 58,474 and 60,703 seats with
13,191 and 13,666 reservation conflicts. 651 seats were captured twice with
different vote counts and something had to decide which reading was later. And
the year was stated nowhere in the data.

The sibling's re-collection carries the form's own codes for district, block,
panchayat and seat, saves every page it read, and states the year in its
manifest, so none of that is inferred here any more. It also settles the
duplicates at the source: the re-collection fetches each form code once.

The 2016 rows that do not enter are the seats whose page answers "Record not
Found" and therefore prints no reservation - 30,764 of them, counted per tier in
each slice's notes rather than admitted as open seats.
"""

import pyarrow.parquet as pq

from local_elections.common.adapters import bihar_2011, bihar_2016, bihar_2021

REPO = "local_elections_bihar"
URL = "https://github.com/in-rolls/local_elections_bihar"
STATE = "Bihar"

# The sibling's mukhiya seat links. 2016 and 2021 are joined on panchayat names
# inside matched blocks, with ward counts as a second pass; 2011 records are
# joined to 2016 seats on names alone, inside a reviewed block crosswalk.
LINKS = {
    "2011_2016": "data/linkage/mukhiya_2011_2016.parquet",
    "2016_2021": "data/linkage/mukhiya_2016_2021.parquet",
}


def slices(root):
    yield from bihar_2011.slices(root)
    yield from bihar_2016.slices(root)
    yield from bihar_2021.slices(root)


def locator_2016(r):
    # bihar_2016's key is office/district/block/panchayat/unit, and a mukhiya's
    # panchayat code is empty: the seat is the panchayat itself.
    return "/".join(
        ["mukhiya", r["district_code"], r["block_code"], "", r["unit_code"]]
    )


def links(root):
    """The sibling's mukhiya seat links, keyed by both seats' locators."""
    path = root / LINKS["2011_2016"]
    for r in pq.read_table(path).to_pylist():
        yield {
            "from_dataset_id": "bihar/gp_head/2011",
            "from_locator": r["record_id_2011"],
            "to_dataset_id": "bihar/gp_head/2016",
            "to_locator": locator_2016(r),
            "link_pass": "name",
            "name_score": r["name_score"],
            "source_path": LINKS["2011_2016"],
        }
    path = root / LINKS["2016_2021"]
    for r in pq.read_table(path).to_pylist():
        yield {
            "from_dataset_id": "bihar/gp_head/2016",
            "from_locator": locator_2016(r),
            "to_dataset_id": "bihar/gp_head/2021",
            # bihar_2021's key is post/unit, and post 3 is the mukhiya
            "to_locator": f"3/{r['unit_id_2021']}",
            "link_pass": r["link_pass"],
            "name_score": r["name_score"],
            "source_path": LINKS["2016_2021"],
        }
