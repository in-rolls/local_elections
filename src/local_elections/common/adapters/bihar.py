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

from local_elections.common.adapters import bihar_2016, bihar_2021

REPO = "local_elections_bihar"
URL = "https://github.com/in-rolls/local_elections_bihar"
STATE = "Bihar"


def slices(root):
    yield from bihar_2016.slices(root)
    yield from bihar_2021.slices(root)
