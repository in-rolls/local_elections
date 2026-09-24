"""Turn a state's rows into the pooled schema.

The master's point is that you can group by it, so its columns are fixed and
declared rather than a union of whatever each state happens to carry. The 23
state-specific extras stay out and go to master_extras.parquet long-form, so nothing
is lost and the table does not become mostly blank.

**What is deliberately not carried.** Three sources publish contact details for
named individuals - Bihar a mobile number, postal address and email for each of
645,605 candidates, Kerala an address, phone, mobile and photograph for each of
its 65,296 elected members, Uttar Pradesh 2010 an address. Those columns are
read and dropped, and this is the one place in the repository where dropping
data is not a defect to be fixed. Everything else a source states about a person
is kept: name, relation, gender, age, caste, education, occupation, marital
status, party, votes.

**A reservation is a property of the seat, never of the person who won it.**
`caste_reservation` and `woman_reserved` say what the seat was reserved for.
The winner's own category and gender are `winner_caste` and `winner_gender` on a
seat row, and `candidate_caste` and `candidate_gender` in the candidate table.
They are different facts and the data says so: Uttar Pradesh 2005 states both,
and they agree on 19,324 of 51,872 rows. A scheduled-caste person winning an
unreserved seat is the thing most of these data exist to measure, and collapsing
the two columns would delete it.

Three columns exist because one could not carry the fact:

  tier / tier_local              the same office is printed under different
                                 names, and the same name means different
                                 offices - see canon.py
  caste_reservation / _local /   the fold to BC is lossy and not the same fold
  caste_scheme                   in every state, so the local label and the
                                 regime are both kept
  unit_of_observation /          three sources are candidate-level and get
  seat_candidates                collapsed to seats; a row that came from a
                                 collapse has to say so

The grain is **one row per seat-event as a source states it**. Most sources name
only a cycle, so year identifies the event; Rajasthan also names general and
by-election periods, which remain separate. Rows that still do not identify a
distinct event are exported rather than hidden behind a claim the data does not
support.
"""

import hashlib

from local_elections.common import canon, dictionary, normalize, reference

MASTER_COLUMNS = [
    # grain
    "dataset_id",
    "row_id",
    "seat_key",
    "seat_key_unique",
    # place
    "state",
    "year",
    "election_type",
    "election_duration",
    "district",
    "block",
    "body",
    "gp_no",
    "gram_panchayat",
    "gp_term",
    "ward_no",
    "ward_name",
    "seat_no",
    # The same places in Latin, so they can be searched and joined against a
    # register that is not in Devanagari. Derived by a model, never read from a
    # document - see tools/transliterate.py - and blank wherever that reading
    # was flagged, on the same principle as party: a value that does not settle
    # the question is left empty rather than filled with a plausible one.
    "district_latin",
    "block_latin",
    "gram_panchayat_latin",
    # office
    "tier",
    "tier_local",
    # reservation
    "caste_reservation",
    "caste_reservation_local",
    "caste_scheme",
    "woman_reserved",
    "reservation",
    "reservation_raw",
    "listing_scope",
    # what a row is
    "unit_of_observation",
    "seat_candidates",
    # who won, and - where the source states a contest rather than a seat -
    # who came second and by how much. These are facts about the seat, so they
    # belong here; the full field of candidates is a fact about the contest and
    # lives in the candidate table.
    "winner",
    "winner_latin",
    "winner_basis",
    "votes",
    "runner_up",
    "runner_up_votes",
    "margin",
    "vacant",
    "unopposed",
    # provenance
    "script",
    "source_repo",
    "source_commit",
    "source_path",
    "source_page",
    "provenance_level",
    "quality_flags",
]

# Columns that the master carries under its own name, so an adapter's leftovers
# can be identified as extras rather than silently dropped.
CARRIED = set(MASTER_COLUMNS) | {
    "halqa",
    "gender_stated",
    "seat_members",
    "winner_votes",
}

# The long form, and a table in its own right rather than an appendage. Four of
# the sources state a contest, not a seat: every candidate who stood, what they
# polled, and who they were. That is a different unit of observation, not a
# lesser one, so it gets its own declared schema, its own files, its own row
# identifiers and its own place in the manifest.
#
# It carries place and office rather than only a join key, so it can be read on
# its own without reconstructing the seat first, and it carries the seat's
# reservation so the obvious question - who contests a seat reserved for whom -
# is answerable in one table. `row_id` joins it back to the wide one.
CANDIDATE_COLUMNS = [
    # grain
    "dataset_id",
    "candidate_id",
    "row_id",
    "seat_key",
    "candidate_no",
    # place
    "state",
    "year",
    "election_type",
    "election_duration",
    "district",
    "block",
    "body",
    "gp_no",
    "gram_panchayat",
    "ward_no",
    "seat_no",
    # office
    "tier",
    "tier_local",
    # what the seat was reserved for, so the long form stands on its own
    "caste_reservation",
    "woman_reserved",
    # who stood
    "candidate_name",
    "relation_name",
    "candidate_gender",
    "candidate_woman",
    "candidate_age",
    "candidate_caste",
    "candidate_education",
    "candidate_marital_status",
    "candidate_occupation",
    "candidate_total_assets",
    "candidate_children_before_1995_11_27",
    "candidate_children_after_1995_11_27",
    "party",
    # how they did
    "votes",
    "candidate_rank",
    "elected",
    "result",
    # provenance, the same as the seat it belongs to
    "source_repo",
    "source_commit",
    "source_path",
    "source_page",
]

# What an adapter supplies per candidate. Everything else on a candidate row is
# copied from the seat it belongs to, so an adapter states each fact once.
CANDIDATE_FIELDS = [
    "candidate_name",
    "relation_name",
    "candidate_gender",
    "candidate_woman",
    "candidate_age",
    "candidate_caste",
    "candidate_education",
    "candidate_marital_status",
    "candidate_occupation",
    "candidate_total_assets",
    "candidate_children_before_1995_11_27",
    "candidate_children_after_1995_11_27",
    "party",
    "votes",
    "candidate_rank",
    "elected",
    "result",
]

SEAT_FIELDS = list(canon.SEAT_IDENTITY_FIELDS)


def seat_key(row):
    # Source-faithful OCR occasionally contains a literal table rule (``|``).
    # Escape the delimiter and the escape marker so the ten-part key remains
    # unambiguous without altering the source columns themselves.
    components = (
        value.replace("%", "%25").replace("|", "%7C")
        for value in canon.seat_identity(row)
    )
    return "|".join(components)


def row_id(row, occurrence):
    """A stable identifier for a row.

    Built from where the row came from plus its seat key plus which occurrence
    it is, so it survives a rebuild and changes when the provenance changes.
    `occurrence` disambiguates rows that a source states more than once, which
    it does - the key alone is not unique.
    """
    material = "|".join(
        [
            row.get("source_repo", ""),
            row.get("source_path", ""),
            str(row.get("source_page", "")),
            seat_key(row),
            str(occurrence),
        ]
    )
    return hashlib.sha1(material.encode("utf-8")).hexdigest()[:12]


def quality_flags(row):
    """What a consumer should know about this row before trusting it."""
    flags = []
    if str(row.get("ocr_repaired") or "0") not in ("0", ""):
        flags.append("ocr_repaired")
    if row.get("printings_agree") == "0":
        flags.append("printings_disagree")
    if row.get("ward_list_complete") == "0":
        flags.append("ward_list_incomplete")
    # woman_reserved is 0 by default where the marker did not survive the scan,
    # so a row whose gender was never stated is a guess, not a reading
    if row.get("gender_stated") == "0":
        flags.append("gender_not_stated")
    if row.get("winner_basis") == "argmax_votes":
        flags.append("winner_inferred")
    # the source stated this contest twice, with vote counts that disagree
    if str(row.get("duplicate_candidacy") or "0") not in ("0", ""):
        flags.append("duplicate_candidacy")
    # one serial number carrying two different candidates, unresolvable
    if str(row.get("serial_not_unique") or "0") not in ("0", ""):
        flags.append("serial_not_unique")
    if str(row.get("winner_candidate_ambiguous") or "0") not in ("0", ""):
        flags.append("winner_candidate_ambiguous")
    if str(row.get("winner_markers_conflict") or "0") not in ("0", ""):
        flags.append("winner_markers_conflict")
    if str(row.get("ward_no_inferred") or "0") not in ("0", ""):
        flags.append("seat_number_inferred")
    if str(row.get("winner_name_missing") or "0") not in ("0", ""):
        flags.append("winner_name_missing")
    if str(row.get("reservation_body_control_agree", "")) == "0":
        flags.append("reservation_control_disagree")
    if str(row.get("margin_below_votes", "")) == "0":
        flags.append("margin_not_below_votes")
    if str(row.get("winner_category_sex_agree", "")) == "0":
        flags.append("winner_category_sex_disagree")
    # two places in one block printed under one name, told apart only by the
    # fact that they are reserved differently
    if str(row.get("shared_place_name") or "0") not in ("0", ""):
        flags.append("shared_place_name")
    # The flag means what its name says: this row's name cannot be read by
    # someone who does not read the script. A row that now carries a Latin
    # reading can be, so the flag lifts - otherwise correcting Uttar Pradesh's
    # script label would have raised it on 153,505 rows in the same commit that
    # gave every one of them a transliteration, and the flag would have been
    # measuring the label rather than the difficulty it names.
    if row.get("script") in (
        "krutidev",
        "devanagari",
        "bengali",
        "gujarati",
        "kannada",
    ) and not (row.get("winner_latin") or row.get("gram_panchayat_latin")):
        flags.append("name_untransliterated")
    return ";".join(flags)


def gp_term(row):
    """Which word the source used for the panchayat, since the master keeps one
    column and the term itself is information about the state.
    """
    for column in canon.UNIT_COLUMNS:
        if (row.get(column) or "").strip():
            return column
    return ""


# Which master column carries the Latin reading of which source column. Four
# of the five go into the master; ward_name is non-Latin on 1.7% of rows, which
# is the mostly-blank case the declared-columns rule exists for, so it travels
# as an extra instead.
LATIN_OF = {
    "district": "district_latin",
    "block": "block_latin",
    "gram_panchayat": "gram_panchayat_latin",
    "winner": "winner_latin",
    "ward_name": "ward_name_latin",
}


def transliterations(root):
    """{source string: Latin reading} for every reading that was not flagged.

    A flagged one is left out rather than carried with a warning column: the
    table on disk keeps it and says why, and the pooled corpus holds only
    readings that passed. Same call `party` got - a value that does not settle
    the question is blank rather than plausible.
    """
    import csv
    import pathlib as _pathlib

    out = {}
    directory = _pathlib.Path(root) / "data" / "transliteration"
    for path in sorted(directory.glob("*.csv")):
        with path.open(encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                if not row.get("suspect") and row.get("latin"):
                    out[row["source"]] = row["latin"]
    return out


def to_master(
    row,
    dataset_id,
    source_repo,
    source_commit,
    provenance_level,
    unit_of_observation="seat",
    seat_candidates="",
    latin=None,
):
    """One parsed row in the pooled schema. Returns None for an urban seat.

    `latin` is the transliteration table - {source string: Latin reading} - read
    once by the caller and passed down, because this runs 829,628 times.
    """
    state = row.get("state", "")
    tier = row.get("tier", "")
    if not canon.is_rural(tier):
        return None

    local = row.get("caste_reservation_local") or row.get("caste_reservation", "")
    out = {
        "dataset_id": dataset_id,
        "state": state,
        "year": row.get("year", ""),
        "election_type": row.get("election_type", ""),
        "election_duration": row.get("election_duration", ""),
        "district": row.get("district", ""),
        "block": row.get("block", ""),
        "body": row.get("body", ""),
        "gp_no": row.get("gp_no", ""),
        "gram_panchayat": canon.unit_name(row),
        "gp_term": gp_term(row),
        "ward_no": row.get("ward_no", ""),
        "ward_name": row.get("ward_name", ""),
        # A block or district seat is numbered within its body and has no
        # panchayat, so this is the whole of its identity. It was named in
        # SEAT_FIELDS but never in MASTER_COLUMNS, so every seat key was built
        # with an empty slot where it belonged and Jharkhand's 181 zila
        # parishad seats all collided with each other.
        "seat_no": row.get("seat_no", ""),
        "tier": tier,
        "tier_local": row.get("tier_local", ""),
        "caste_reservation": row.get("caste_reservation", ""),
        "caste_reservation_local": local,
        "caste_scheme": canon.caste_scheme(state) or "",
        "woman_reserved": row.get("woman_reserved", ""),
        "reservation": row.get("reservation", ""),
        "reservation_raw": row.get("reservation_raw", ""),
        # The row's own value first, then what reference declares for the
        # slice, and only then the convention. Writing "all_seats" without
        # asking reference overwrote Goa 2017 and 2022 - declared partial
        # listings - and the statutory check then measured half a roster
        # against the statute and failed a state that had done nothing wrong.
        "listing_scope": (
            row.get("listing_scope")
            or reference.listing_scope(state, row.get("year", ""), tier)
        ),
        "unit_of_observation": unit_of_observation,
        "seat_candidates": seat_candidates,
        "winner": row.get("winner", ""),
        "winner_basis": row.get("winner_basis", ""),
        # winner_votes where a collapse worked it out, votes where the source
        # stated it directly against the seat
        "votes": row.get("winner_votes") or row.get("votes", ""),
        "runner_up": row.get("runner_up", ""),
        "runner_up_votes": row.get("runner_up_votes", ""),
        "margin": row.get("margin", ""),
        "vacant": row.get("vacant", ""),
        "unopposed": row.get("unopposed", ""),
        # Derived from the row this label sits on, not asserted upstream.
        #
        # Adapters set it per *candidate* and collapse.to_seats then merges
        # many candidates into one seat, so a seat could carry the script of a
        # name it does not show: 7,226 Bihar seats said devanagari while every
        # word in the row read Latin. Deriving it here means the label always
        # describes the row it labels, which is what makes it checkable at all.
        #
        # An upstream krutidev survives, because it is the one value that
        # cannot be derived: Kruti Dev is ASCII, so no test of which Unicode
        # block a character belongs to can see it, and only the parser that
        # read the document knows.
        "script": (
            "krutidev"
            if row.get("script") == "krutidev"
            else normalize.script_of(
                row.get("winner", ""),
                row.get("gram_panchayat", ""),
                row.get("district", ""),
                row.get("block", ""),
                row.get("ward_name", ""),
            )
        ),
        "source_repo": source_repo,
        "source_commit": source_commit,
        "source_path": row.get("source_path", ""),
        "source_page": row.get("source_page", ""),
        "provenance_level": provenance_level,
    }
    # The Latin readings, looked up on the source string. A name absent from
    # the table was either already Latin or its reading was withheld, and both
    # come out blank - which is the honest answer to "what is this in Latin".
    # Always set, never conditionally: a declared column that appears on some
    # rows and not others is not a column, and test_the_projection_does_not_
    # replace_the_source_row says so. Blank is the honest value where the name
    # was already Latin or its reading was withheld.
    for source_column, latin_column in LATIN_OF.items():
        out[latin_column] = (latin or {}).get(
            out.get(source_column) or row.get(source_column) or "", ""
        )

    out["quality_flags"] = quality_flags(dict(row, **out))
    out["seat_key"] = seat_key(out)
    # Every value is a string, as it will be once written. An adapter that sets
    # woman_reserved to the integer 1 produces a row that behaves differently
    # in memory than after a round trip through the CSV, and the checks - which
    # were written against rows read back from disk - then fail on .strip().
    # Ordered by MASTER_COLUMNS rather than by insertion. The parquet takes its
    # column order from this dict, and the manifest records that order and is
    # tested against the declaration - so a column added in a loop after the
    # literal would land at the end and the two would disagree.
    ordered = {k: out[k] for k in MASTER_COLUMNS if k in out}
    ordered.update({k: v for k, v in out.items() if k not in ordered})
    return {k: "" if v is None else str(v) for k, v in ordered.items()}


def candidates(row, seat):
    """The long-form rows for one seat, in the candidate schema.

    `row` is the adapter's row, which carries `seat_members`; `seat` is the
    finished master row, which carries the place, the office, the reservation
    and the provenance. Each is stated once and copied here, so the two tables
    cannot drift from each other.

    A seat-level source contributes nothing and that is not a gap - Haryana
    states seats, so there are no candidates to state.
    """
    shared = {c: seat.get(c, "") for c in CANDIDATE_COLUMNS if c in seat}
    out = []
    for position, member in enumerate(row.get("seat_members") or (), 1):
        got: dict[str, object] = dict(
            shared, candidate_no=position, row_id=seat.get("row_id", "")
        )
        got.update({c: member.get(c, "") for c in CANDIDATE_FIELDS})
        got["candidate_no"] = member.get("candidate_no") or position
        got["candidate_id"] = hashlib.sha1(
            f"{seat.get('row_id', '')}|{position}".encode()
        ).hexdigest()[:12]
        out.append(
            {
                c: "" if got.get(c) is None else str(got.get(c, ""))
                for c in CANDIDATE_COLUMNS
            }
        )
    return out


def extras(row, row_id_value):
    """The state-specific columns, long-form.

    Widening the master to a sparse union of every state's extras is the thing
    to avoid; dropping them is worse. This keeps ward_count, printings_agree,
    pop_sc and the rest recoverable by a join on row_id.
    """
    out = []
    for column, value in row.items():
        if column in CARRIED or not str(value or "").strip():
            continue
        if column not in dictionary.BY_NAME:
            continue
        out.append({"row_id": row_id_value, "column": column, "value": str(value)})
    return out
