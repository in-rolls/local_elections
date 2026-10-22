"""Turn candidate rows into seats.

Three of the sources are candidate-level: Bihar lists every contestant, UP's 2021
file has 373,096 rows over 49,772 panchayats, and Uttarakhand denormalises the
winner onto each candidate's row. Pooling them as-is would count a seat once per
person who stood for it.

**This is the riskiest transformation in the repository**, and not because it is
hard. It is the only step that changes the row count *by design*, so a bug is
indistinguishable from correct behaviour by row count alone - the exact failure
mode this corpus keeps meeting. A wrong seat key does not raise: it merges two
seats or splits one, `reconcile()` still balances because it only counts inputs
against outputs, and the women's share moves by a point nobody can attribute.

Two things contain it, and both are here rather than in the adapters:

- the reservation must be constant within a seat, checked before anything is
  pooled. Every candidate for a seat is contesting the same seat, so they all
  carry the same reservation; if two do not, the key is wrong. Run by hand
  before this module was written: 0 violations across all six Bihar files and
  UP 2021, and **9 of 18,826 seats in Uttarakhand** - the check found something
  real before it was even committed.
- `seat_candidates` on every row, so the denominator is visible. Bihar's
  mukhiya averages 12 candidates a seat; one showing 40, or 1, is where to look.

The winner is the only field that needs inference, and it says which kind it is:
`published` where the source marks the winner, `argmax_votes` where it has to be
worked out - and that one also sets `winner_inferred` in quality_flags.
"""

import collections

# Values that mean "no vote was recorded", not "zero votes".
NOT_A_COUNT = {"", "-", "--", "na", "n/a", "nil", "--select--"}


class ReservationVaries(Exception):
    """One seat, two reservations. The seat key is wrong, or the source is.

    Raised rather than resolved: picking the majority would hide a key that
    merges two real seats, which is the thing this module exists to prevent.
    """


def votes_of(value):
    """A vote count, or None where the source recorded none.

    None is not zero. An uncontested seat and a seat where nobody voted are
    different, and Bihar writes both - 24 seats with no numeric vote, and one
    reading "986+1 (BY LOT)".
    """
    text = str(value or "").strip().lower()
    if text in NOT_A_COUNT:
        return None
    digits = "".join(c for c in text.split("+")[0] if c.isdigit())
    return int(digits) if digits else None


def to_seats(
    rows,
    key_fields,
    reservation_fields=("caste_reservation", "woman_reserved"),
    vote_field=None,
    winner_field=None,
    winner_value=None,
    runner_up_value=None,
):
    """One row per seat, from many rows per candidate.

    `winner_field`/`winner_value` name an explicit winner marker; failing that,
    `vote_field` selects by highest vote. A tie leaves the winner blank rather
    than picking one - two people cannot both have won, and a coin toss recorded
    as fact is worse than a gap.

    Every candidate keeps a `candidate_rank` - 1 for the highest vote, shared on
    a tie, blank where no vote was recorded - so the long form carries the
    contest and the seat row can state the runner-up and the margin without
    anybody having to reconstruct them.
    """
    grouped = collections.OrderedDict()
    for row in rows:
        grouped.setdefault(tuple(row.get(f, "") for f in key_fields), []).append(row)

    out = []
    for key, candidates in grouped.items():
        stated = {tuple(c.get(f, "") for f in reservation_fields) for c in candidates}
        if len(stated) > 1:
            raise ReservationVaries(f"{key}: {sorted(stated)}")

        seat = dict(candidates[0])
        seat["seat_candidates"] = len(candidates)
        seat["unit_of_observation"] = "seat_from_candidates"

        won, basis = None, ""
        if winner_field:
            marked = [
                c
                for c in candidates
                if str(c.get(winner_field, "")).strip() == winner_value
            ]
            if len(marked) == 1:
                won, basis = marked[0], "published"
        if won is None and vote_field:
            counted = [(votes_of(c.get(vote_field)), c) for c in candidates]
            counted = [(v, c) for v, c in counted if v is not None]
            if counted:
                best = max(v for v, _ in counted)
                leaders = [c for v, c in counted if v == best]
                if len(leaders) == 1:
                    won, basis = leaders[0], "argmax_votes"

        seat["winner"] = (
            (won or {}).get("candidate_name") or (won or {}).get("winner") or ""
        )
        seat["winner_basis"] = basis if seat["winner"] else ""

        for candidate in candidates:
            candidate["elected"] = int(candidate is won)
        rank(candidates, vote_field)
        seat["seat_members"] = candidates
        seat.update(margin(candidates, vote_field))
        if runner_up_value and winner_field and not seat["runner_up"]:
            seat.update(stated_runner_up(candidates, winner_field, runner_up_value))
        out.append(seat)
    return out


def rank(candidates, vote_field):
    """Place each candidate in the contest, in the row itself.

    Ties share a rank and the next rank skips, as a results table prints it. A
    candidate with no recorded vote gets no rank rather than last place: 328
    Bihar rows state no vote at all, and ranking them last would assert they
    lost when the source says nothing.
    """
    if not vote_field:
        return
    counted = sorted(
        ((votes_of(c.get(vote_field)), c) for c in candidates),
        key=lambda pair: -(pair[0] if pair[0] is not None else -1),
    )
    place, previous, seen = 0, object(), 0
    for votes, candidate in counted:
        if votes is None:
            candidate["candidate_rank"] = ""
            continue
        seen += 1
        if votes != previous:
            place, previous = seen, votes
        candidate["candidate_rank"] = place


def margin(candidates, vote_field):
    """The seat-level view of the contest: who came second, and by how much.

    The wide table is where this belongs. It is one row per seat, and "who won
    and by how much" is a fact about the seat; the full field of candidates is
    a fact about the contest and lives in the long form.
    """
    blank = {"runner_up": "", "winner_votes": "", "runner_up_votes": "", "margin": ""}
    if not vote_field:
        return blank
    ranked = [
        (c.get("candidate_rank"), votes_of(c.get(vote_field)), c)
        for c in candidates
        if c.get("candidate_rank")
    ]
    first = [c for r, _, c in ranked if r == 1]
    second = [c for r, _, c in ranked if r == 2]
    if len(first) != 1:
        return blank
    top = votes_of(first[0].get(vote_field))
    out = dict(blank, winner_votes=top)
    if len(second) == 1:
        runner = votes_of(second[0].get(vote_field))
        # votes_of returns None where the source recorded no count, and its
        # own docstring is emphatic that None is not zero - Bihar writes 24
        # seats with no numeric vote and one reading "986+1 (BY LOT)". So the
        # subtraction was a TypeError waiting for the first of those to reach
        # a two-candidate seat. A margin between an unknown and a number is
        # unknown, which is what blank already means here.
        margin = top - runner if top is not None and runner is not None else ""
        out.update(runner_up=name_of(second[0]), runner_up_votes=runner, margin=margin)
    elif not second:
        # Nobody else polled a vote. Unopposed, or the only recorded candidate.
        out["margin"] = top
    return out


def stated_runner_up(candidates, winner_field, runner_up_value):
    """Who the source says came second, where it says so rather than counting.

    Uttar Pradesh's 2021 file marks विजेता and उपविजेता and records no vote
    total at all, only a percentage, so the runner-up is stated and the margin
    is not derivable. A stated second place with no margin is the honest shape
    of that, and better than turning a percentage into a vote count.
    """
    marked = [
        c for c in candidates if str(c.get(winner_field, "")).strip() == runner_up_value
    ]
    if len(marked) != 1:
        return {}
    marked[0].setdefault("candidate_rank", 2)
    return {"runner_up": name_of(marked[0])}


def name_of(candidate):
    return candidate.get("candidate_name") or candidate.get("winner") or ""


def varies(
    rows, key_fields, reservation_fields=("caste_reservation", "woman_reserved")
):
    """Seats whose candidates disagree about the reservation, without raising.

    For measuring a source before deciding how to treat it - Uttarakhand's nine
    are a finding to look at, not a reason to refuse the whole state.
    """
    grouped = collections.defaultdict(set)
    for row in rows:
        grouped[tuple(row.get(f, "") for f in key_fields)].add(
            tuple(row.get(f, "") for f in reservation_fields)
        )
    return {k: v for k, v in grouped.items() if len(v) > 1}
