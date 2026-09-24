"""The worklist and the master must agree about the same rows.

They are generated separately - the worklist from the notes, the master from the
adapters - and for months they disagreed without anything noticing. The master
reported 9,543 rows that identify no distinct seat; the worklist accounted for
1,425 of them, because it read only this repository's own parses and could not
see a sibling row at all.

A worklist that says "generated from the rows and cannot go stale" while being
blind to two thirds of the rows is worse than one that admits its scope: it
reports few problems and reads as though there are few.
"""

import collections
import csv

from local_elections.paths import ROOT

WORKLIST = ROOT / "data" / "worklist.csv"
COLLISIONS = ROOT / "data" / "master" / "master_key_collisions.csv"
STATS = ROOT / "data" / "stats" / "slice_stats.csv"

# Every reason a row can fail to identify a distinct seat.
EXPLAINS = {"seat_key_not_unique", "panchayat_not_named", "seat_not_numbered"}

SLUG = {
    "andhra_pradesh": "Andhra Pradesh",
    "goa": "Goa",
    "haryana": "Haryana",
    "jammu_and_kashmir": "Jammu & Kashmir",
    "jharkhand": "Jharkhand",
    "rajasthan": "Rajasthan",
    "kerala": "Kerala",
    "bihar": "Bihar",
    "uttar_pradesh": "Uttar Pradesh",
    "uttarakhand": "Uttarakhand",
    "karnataka": "Karnataka",
    "telangana": "Telangana",
}


def read(path):
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def test_every_colliding_row_is_explained():
    """Per slice, not in total.

    A row can be both unnamed and colliding, so the two artifacts will not sum
    to the same number and asserting that they do would be wrong. What must
    hold is containment: no slice may collide more than its notes explain.
    """
    explained = collections.Counter()
    for row in read(WORKLIST):
        if row["note_id"] in EXPLAINS:
            explained[(row["state"], row["year"], row["tier"])] += int(
                row["rows_affected"]
            )

    colliding = collections.Counter()
    for row in read(COLLISIONS):
        slug, tier, year = row["dataset_id"].split("/")
        colliding[(SLUG.get(slug, slug), year, tier)] += 1

    unexplained = {
        key: (n, explained.get(key, 0))
        for key, n in colliding.items()
        if explained.get(key, 0) < n
    }
    assert not unexplained, unexplained


def test_the_worklist_covers_every_state_in_the_master():
    """A state in the master with no worklist coverage at all means the notes
    are not reading it - which is exactly how Haryana and Rajasthan sat there
    for months contributing 3,876 unexplained collisions."""
    if not COLLISIONS.exists() or not STATS.exists():
        return
    in_master = {SLUG.get(r["dataset_id"].split("/")[0]) for r in read(COLLISIONS)}
    in_stats = {r["state"] for r in read(STATS)}
    assert in_master <= in_stats, in_master - in_stats


def test_stats_cover_the_pooled_states_not_just_the_local_ones():
    """slice_stats is built from datasets.pooled(); if it ever drops back to
    parsed() this catches it, because the sibling states vanish."""
    states = {r["state"] for r in read(STATS)}
    if not states:
        return
    local = {"Andhra Pradesh", "Goa", "Jammu & Kashmir", "Jharkhand"}
    assert states > local, f"only local states present: {states}"
