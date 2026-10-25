"""The published tables' contract, as Frictionless Table Schemas.

`dictionary.py` declares the columns of the per-state slices the parsers write.
This module declares what the pooled build *publishes* - the master seat files,
the candidate files, the long-form extras and the seat links - which is what
downstream analyses read and what a state repository's export has to satisfy.

Table Schema (https://specs.frictionlessdata.io/table-schema/) is the JSON
standard for tables: types, required, enums, patterns, ranges, primary keys and
foreign keys, validated by the maintained `frictionless` package. JSON Schema
proper describes JSON documents, not tables, and a pandera model would bind
consumers to this repository's Python.

The schemas state the intended contract, not today's storage. Where the data
falls short - a boolean stored as "0"/"1", a page number of 0 - validation says
so, and the fix belongs in the build rather than in a looser schema.

Vocabularies come from `dictionary.py` and `canon.py`, so a category exists in
one place. Patterns are implicitly anchored, as the Table Schema spec says.
`make schema` writes schemas/*.json from here; a test fails if they differ.
"""

import json

from local_elections.common import canon
from local_elections.common import dictionary as D

SHA12 = r"[0-9a-f]{12}"
SHA40 = r"[0-9a-f]{40}"
STATES = sorted(canon.CASTE_SCHEME)
YEAR = {"minimum": 1990, "maximum": 2030}
NAME = {"minLength": 1, "maxLength": 255}


def field(name, type_, description, **constraints):
    out = {"name": name, "type": type_, "description": description}
    if constraints:
        out["constraints"] = constraints
    return out


def text(name, description, **constraints):
    return field(name, "string", description, **constraints)


def boolean(name, description, **constraints):
    return field(name, "boolean", description, **constraints)


def integer(name, description, **constraints):
    return field(name, "integer", description, **constraints)


def flag(name, description, **constraints):
    """1 / 0 / null, stored as int8 (docs/naming.md: every *_woman column)."""
    out = field(name, "integer", description, minimum=0, maximum=1, **constraints)
    # Table Schema has no int8; the storage type rides along as a custom property
    out["arrow"] = "int8"
    return out


# ------------------------------------------------------------ shared fields
DATASET_ID = text(
    "dataset_id",
    "state_slug/tier/year: the slice the row belongs to.",
    required=True,
    pattern=r"[a-z_]+/[a-z_]+/\d{4}",
)
ROW_ID = text(
    "row_id",
    "Stable row identifier: sha1 of source repository, path, page, seat key "
    "and occurrence, first 12 hex digits. Changes when provenance changes.",
    required=True,
    pattern=SHA12,
)
SEAT_KEY = text(
    "seat_key",
    "The ten seat-identity parts joined by '|' ('|' and '%' escaped). Not "
    "unique: a source can state a seat twice.",
    required=True,
    minLength=1,
)
STATE = text("state", "Printed name of the state.", required=True, enum=STATES)
YEAR_FIELD = integer("year", "Election year.", required=True, **YEAR)
ELECTION_TYPE = text(
    "election_type",
    "General or by-election, where the source names it (Rajasthan).",
    enum=["General Election", "By Election"],
)
ELECTION_DURATION = text(
    "election_duration", "The polling period as the source prints it.", maxLength=40
)
PLACE = [
    text("district", "District as printed.", required=True, minLength=2, maxLength=40),
    text("block", "Block, mandal or taluk as printed.", maxLength=100),
    text("body", "Local body name where the source names one.", maxLength=60),
    text("gp_no", "Panchayat number as printed.", maxLength=40),
    text("gram_panchayat", "Panchayat as printed.", maxLength=160),
]
WARD_NO = text("ward_no", "Ward number as printed (may carry a suffix).", maxLength=40)
SEAT_NO = integer("seat_no", "Seat number within a multi-member ward.", minimum=1)
TIER = text(
    "tier",
    "Canonical office (canon.py maps local names onto it).",
    required=True,
    enum=D.TIERS,
)
TIER_LOCAL = text(
    "tier_local", "The office as the state names it.", required=True, maxLength=40
)
CASTE = text(
    "reserved_caste",
    "Caste category the seat is reserved for; NONE = unreserved. A property of "
    "the seat, never of the winner.",
    required=True,
    enum=D.CASTES,
)
WOMAN = flag(
    "reserved_woman",
    "1 if the seat is reserved for a woman, 0 if not. Never filled from a name.",
    required=True,
)
SOURCE = [
    text(
        "source_repo",
        "Repository the row was read from.",
        required=True,
        pattern=r"local_elections(_[a-z_]+)?",
    ),
    text(
        "source_commit",
        "Full commit of source_repo the row was read at.",
        required=True,
        pattern=SHA40,
    ),
    text("source_path", "File within source_repo.", required=True, minLength=1),
]
SOURCE_PAGE = integer(
    "source_page", "1-based page of source_path, for documents.", minimum=1
)

# ------------------------------------------------------------ master seats
MASTER = {
    "title": "Pooled seats",
    "description": "One row per seat-event as a source states it "
    "(data/master/master_<state>.parquet).",
    "fields": [
        DATASET_ID,
        ROW_ID,
        SEAT_KEY,
        boolean(
            "seat_key_unique",
            "True when no other row in the pooled corpus has this seat_key.",
            required=True,
        ),
        STATE,
        YEAR_FIELD,
        ELECTION_TYPE,
        ELECTION_DURATION,
        *PLACE[:5],
        text(
            "gp_term",
            "Which word the source used for the panchayat.",
            enum=["gram_panchayat", "halqa"],
        ),
        WARD_NO,
        text("ward_name", "Ward name as printed.", maxLength=160),
        SEAT_NO,
        text("district_latin", "District romanized by tools/transliterate.py.", **NAME),
        text(
            "district_latin_method",
            "How the reading was made: `indicate <version> model` (Hindi, "
            "Punjabi), `... after lookup` where indicate's word lookup "
            "replaced a misreading, or `muse-spark-1.3-contributor "
            "reasoning=low prompt=<hash>` for scripts indicate has no model "
            "for. Blank where the reading is blank.",
            maxLength=80,
        ),
        text("block_latin", "Block romanized by tools/transliterate.py.", **NAME),
        text(
            "block_latin_method",
            "How the reading was made: `indicate <version> model` (Hindi, "
            "Punjabi), `... after lookup` where indicate's word lookup "
            "replaced a misreading, or `muse-spark-1.3-contributor "
            "reasoning=low prompt=<hash>` for scripts indicate has no model "
            "for. Blank where the reading is blank.",
            maxLength=80,
        ),
        text(
            "gram_panchayat_latin",
            "Panchayat romanized by tools/transliterate.py.",
            **NAME,
        ),
        text(
            "gram_panchayat_latin_method",
            "How the reading was made: `indicate <version> model` (Hindi, "
            "Punjabi), `... after lookup` where indicate's word lookup "
            "replaced a misreading, or `muse-spark-1.3-contributor "
            "reasoning=low prompt=<hash>` for scripts indicate has no model "
            "for. Blank where the reading is blank.",
            maxLength=80,
        ),
        TIER,
        TIER_LOCAL,
        CASTE,
        text(
            "reserved_caste_local",
            "The state's own caste label before the fold to SC/ST/BC/NONE.",
            maxLength=40,
        ),
        text(
            "reserved_caste_scheme",
            "The state's reservation regime, which fixes what BC means.",
            required=True,
            enum=sorted(canon.SCHEME_CATEGORIES),
        ),
        WOMAN,
        text(
            "reserved_label",
            "Caste and woman reservation combined.",
            required=True,
            enum=D.RESERVATION_LABELS,
        ),
        text("reserved_raw", "The reservation exactly as printed.", maxLength=200),
        text(
            "listing_scope",
            "Whether the source lists every seat or only some.",
            required=True,
            enum=["all_seats", "reserved_only", "partial"],
        ),
        text(
            "unit_of_observation",
            "seat, or seat_from_candidates where a candidate-level source was "
            "collapsed to seats.",
            required=True,
            enum=["seat", "seat_from_candidates"],
        ),
        integer(
            "seat_candidates",
            "Number of candidates, where the row was collapsed from candidates.",
            minimum=0,
        ),
        text("winner", "Elected person as printed.", **NAME),
        text("winner_latin", "Winner romanized by tools/transliterate.py.", **NAME),
        text(
            "winner_latin_method",
            "How the reading was made: `indicate <version> model` (Hindi, "
            "Punjabi), `... after lookup` where indicate's word lookup "
            "replaced a misreading, or `muse-spark-1.3-contributor "
            "reasoning=low prompt=<hash>` for scripts indicate has no model "
            "for. Blank where the reading is blank.",
            maxLength=80,
        ),
        text(
            "winner_basis",
            "How the winner is known.",
            enum=["published", "argmax_votes", "uncontested", "sole_candidate", "lot"],
        ),
        integer("votes", "Winner's votes.", minimum=0),
        text("runner_up", "Second-placed candidate as printed.", **NAME),
        integer("runner_up_votes", "Runner-up's votes.", minimum=0),
        integer("margin", "Winner's votes minus runner-up's.", minimum=0),
        boolean("vacant", "No one was elected."),
        boolean("unopposed", "Elected without a contest."),
        text(
            "script",
            "Script of the printed names.",
            required=True,
            enum=[
                "latin",
                "devanagari",
                "kannada",
                "gujarati",
                "bengali",
                "krutidev",
                "tamil",
            ],
        ),
        *SOURCE,
        SOURCE_PAGE,
        text(
            "provenance_level",
            "The finest unit a row can be traced to.",
            required=True,
            enum=["row", "page", "document", "dataset"],
        ),
        text(
            "quality_flags",
            "';'-joined flags a consumer should read before trusting the row "
            "(master.quality_flags).",
            pattern=r"[a-z_]+(;[a-z_]+)*",
        ),
    ],
    "primaryKey": ["row_id"],
}

# ------------------------------------------------------------ candidates
CANDIDATES = {
    "title": "Pooled candidates",
    "description": "One row per candidate in a contest "
    "(data/master/candidates_<state>.parquet).",
    "fields": [
        DATASET_ID,
        text(
            "candidate_id",
            "Stable candidate-row identifier.",
            required=True,
            pattern=SHA12,
        ),
        ROW_ID,
        SEAT_KEY,
        text(
            "candidate_no", "Candidate serial as printed.", required=True, maxLength=10
        ),
        STATE,
        YEAR_FIELD,
        ELECTION_TYPE,
        ELECTION_DURATION,
        *PLACE,
        WARD_NO,
        SEAT_NO,
        TIER,
        TIER_LOCAL,
        CASTE,
        WOMAN,
        text("candidate_name", "Candidate as printed.", required=True, **NAME),
        text("relation_name", "Father's or husband's name as printed.", **NAME),
        text(
            "candidate_woman_raw",
            "The candidate's sex as the source printed it.",
            maxLength=40,
        ),
        flag(
            "candidate_woman",
            "1 if candidate_woman_raw records a woman, 0 a man; blank otherwise.",
        ),
        integer("candidate_age", "Age as stated.", minimum=18, maximum=120),
        text(
            "candidate_caste",
            "Candidate's own caste category as printed.",
            maxLength=40,
        ),
        text("candidate_education", "Education as printed.", maxLength=60),
        text("candidate_marital_status", "Marital status as printed.", maxLength=20),
        text("candidate_occupation", "Occupation as printed.", maxLength=80),
        integer("candidate_total_assets", "Declared assets, rupees.", minimum=0),
        integer("candidate_children_before_1995_11_27", "As declared.", minimum=0),
        integer("candidate_children_after_1995_11_27", "As declared.", minimum=0),
        text("party", "Party as printed.", maxLength=80),
        integer("votes", "Votes received.", minimum=0),
        integer("candidate_rank", "Rank by votes within the contest.", minimum=1),
        boolean("elected", "The candidate won."),
        text("result", "Result as printed.", maxLength=20),
        *SOURCE,
        SOURCE_PAGE,
    ],
    "primaryKey": ["candidate_id"],
    "foreignKeys": [
        {
            "fields": ["row_id"],
            "reference": {"resource": "master", "fields": ["row_id"]},
        }
    ],
}

# ------------------------------------------------------------ extras
EXTRAS = {
    "title": "State-specific extras",
    "description": "Long-form columns a state carries beyond the master "
    "(data/master/master_extras.parquet).",
    "fields": [
        ROW_ID,
        text(
            "column",
            "Column name, as in DICTIONARY.md.",
            required=True,
            pattern=r"[a-z0-9_]+",
        ),
        text("value", "Value as text.", required=True),
    ],
    "primaryKey": ["row_id", "column"],
    "foreignKeys": [
        {
            "fields": ["row_id"],
            "reference": {"resource": "master", "fields": ["row_id"]},
        }
    ],
}

# ------------------------------------------------------------ seat links
SEAT_LINKS = {
    "title": "Seat links between consecutive elections",
    "description": "A state repository's claim that two rows name one seat "
    "(data/master/supplemental_seat_links.parquet). Not an official identifier.",
    "fields": [
        text(
            "link_id",
            "sha1 of the two row_ids, 12 hex digits.",
            required=True,
            pattern=SHA12,
        ),
        STATE,
        TIER,
        integer("from_year", "Earlier election.", required=True, **YEAR),
        integer("to_year", "Later election.", required=True, **YEAR),
        text(
            "from_row_id", "Earlier seat's master row_id.", required=True, pattern=SHA12
        ),
        text("to_row_id", "Later seat's master row_id.", required=True, pattern=SHA12),
        text(
            "link_pass",
            "The matching rule that made the link.",
            required=True,
            maxLength=40,
        ),
        field(
            "name_score",
            "number",
            "Name similarity, 0-1.",
            required=True,
            minimum=0,
            maximum=1,
        ),
        *SOURCE,
    ],
    "primaryKey": ["link_id"],
    "foreignKeys": [
        {
            "fields": ["from_row_id"],
            "reference": {"resource": "master", "fields": ["row_id"]},
        },
        {
            "fields": ["to_row_id"],
            "reference": {"resource": "master", "fields": ["row_id"]},
        },
    ],
}

SCHEMAS = {
    "master": MASTER,
    "candidates": CANDIDATES,
    "extras": EXTRAS,
    "seat_links": SEAT_LINKS,
}

# Which published files each schema governs, relative to data/master/.
FILES = {
    "master": "master_*.parquet",
    "candidates": "candidates_*.parquet",
    "extras": "master_extras.parquet",
    "seat_links": "supplemental_seat_links.parquet",
}


def dumps(name):
    return json.dumps(SCHEMAS[name], ensure_ascii=False, indent=2) + "\n"
