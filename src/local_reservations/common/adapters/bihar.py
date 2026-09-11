"""Bihar, from local_elections_bihar.

The largest single source in the corpus and the first candidate-level one:
645,605 candidates contesting 219,119 seats in the 2016 panchayat general
election, scraped from the State Election Commission's public candidate viewer.
It is the reason `collapse.py` exists, and the reason the candidate table does.

Six posts across two bodies. Bihar elects a **gram kachahari** - a village court
- alongside the gram panchayat, over the same geography, on the same day. Its
head is the *sarpanch* and its members are *panch*. The panchayat's head is the
*mukhiya* and its members are ward members. So the file called `sarpanch.csv`
is not this state's gram panchayat heads, and `canon.TIER_BY_STATE` says so:
7,916 sarpanch seats pooled as `gp_head` would overstate India's gram panchayat
heads by that much with nothing anywhere to flag it.

Four things this adapter has to get right, all of which fail silently:

**The seat key is four columns, not the `number` column.** `number` reads
`Piprasi/SEMRA LABEDAHA/01` - block, panchayat, serial - with no district. Two
blocks in different districts share a name, so keying on it would merge their
seats and the row count would stay entirely plausible.

**The ward number, not the ward name.** `ward` reads `1 - SRIPATNAGAR`. Keyed on
the name alone, panch and ward member collapse to 58,474 and 60,703 seats with
13,191 and 13,666 reservation conflicts; keyed on the number as well, to 93,341
and 98,131 with none. The conflicts were the signal - two differently-numbered
wards that happen to share a name are not one seat.

**A plain reservation label means not-woman, not silent.** The vocabulary is
closed and paired: every category appears both plain and with `(महिला)`. That is
what licenses reading `पिछड़ा वर्ग` as an unreserved-for-women backward-class
seat, and it is why `gender_stated` is 1 here. 328 rows read `--select--`,
carry no category at all, and are left blank rather than defaulted.

**The scrape captured 651 seats twice.** Those rows are not identical - the
same candidate appears with two different vote counts, usually a few apart and
occasionally far apart, which is what a results page read twice during counting
looks like. 1,098 rows fold away on (serial, name) keeping the higher count;
54 rows where one serial carries two different names are left alone, because
which is the duplicate is not knowable from the file. Both the fold and the
leftovers are flagged on the seat rather than silently applied.

**Year is stated nowhere in the data.** The scrape covered one election and did
not record which. It is declared here, cited to the repository, and would be
wrong in exactly the way that never raises if the sibling ever adds a cycle -
which is what `DECLARED` is for.

Provenance is `dataset`: the scrape kept no document and no page, so a row can
be traced to the file it came from and no further.
"""

import collections
import csv
import pathlib
import re

from local_reservations.common import collapse, normalize
from local_reservations.common.adapters import bihar_2021
from local_reservations.common.normalize import label

REPO = "local_elections_bihar"
URL = "https://github.com/in-rolls/local_elections_bihar"
STATE = "Bihar"

# The scrape covers the 2016 general election and says so in its title and
# nowhere in its rows.
YEAR = "2016"

# file -> (canonical tier, the name Bihar prints, the columns that identify a
#          seat). `NUM` means the serial off the end of the `number` column,
#          which is how the two upper tiers number their seats.
FILES = {
    "mukhiya.csv": ("gp_head", "mukhiya", ("district", "block", "panchayat")),
    "ward_member.csv": (
        "gp_ward",
        "ward member",
        ("district", "block", "panchayat", "ward"),
    ),
    "sarpanch.csv": ("kachahari_head", "sarpanch", ("district", "block", "panchayat")),
    "panch.csv": (
        "kachahari_member",
        "panch",
        ("district", "block", "panchayat", "ward"),
    ),
    "panchayat_samiti_member.csv": (
        "block_member",
        "panchayat samiti member",
        ("district", "block", "NUM"),
    ),
    "zila_parishad_member.csv": (
        "zp_member",
        "zila parishad member",
        ("district", "NUM"),
    ),
}

# Records, not lines. Addresses contain embedded newlines, so `mukhiya.csv` is
# 103,241 lines and 96,266 records; a line count here would fire the tripwire on
# a clean checkout.
DECLARED = {
    "mukhiya.csv": 96266,
    "sarpanch.csv": 45059,
    "panch.csv": 136676,
    "ward_member.csv": 277219,
    "panchayat_samiti_member.csv": 80259,
    "zila_parishad_member.csv": 10126,
}

# What each file must collapse to. Declared because a wrong seat key produces a
# plausible number either way - it is the whole risk of this adapter.
SEATS = {
    "mukhiya.csv": 7997,
    "sarpanch.csv": 7916,
    "panch.csv": 93341,
    "ward_member.csv": 98131,
    "panchayat_samiti_member.csv": 10837,
    "zila_parishad_member.csv": 895,
}

CODED = re.compile(r"^\s*(\d+)\s*-\s*(.*)$")

WOMAN = {"महिला": 1, "पुरुष": 0}


def split_code(value):
    """`01 - PASCHIM CHAMPARAN` into its code and its name.

    Bihar prefixes every place with the code it is numbered by. Left in the join
    key it is harmless; left in `district` it makes the name unjoinable to every
    other source that prints the district on its own.
    """
    got = CODED.match(value or "")
    return (got.group(1), got.group(2).strip()) if got else ("", (value or "").strip())


def serial(value):
    """The seat's number off the end of `Piprasi/01` or `01`.

    Leading zeros are stripped. That merges exactly two panchayat samiti seats
    printed both ways - `TARIYANI/07` and `TARIYANI/7`, `Banma Itahri/03` and
    `Banma Itahri/3` - and both are the same seat: the first pair lists the same
    seven candidates with the same votes, and the second continues one serial
    sequence across the two spellings, 01 to 10 then 11. No zila parishad seat
    is spelt both ways, so its 895 are unaffected.
    """
    last = str(value or "").strip().split("/")[-1].strip()
    return last.lstrip("0") or ("0" if last else "")


def key_of(row, fields):
    out = []
    for field in fields:
        if field == "NUM":
            out.append(serial(row.get("number")))
        elif field == "ward":
            code, name = split_code(row.get("ward"))
            # the number identifies the ward; the name is not unique within a
            # panchayat and keying on it merged 13,666 seats
            out.append(f"{code}|{name}")
        else:
            out.append(split_code(row.get(field))[1])
    return tuple(out)


def slices(root):
    root = pathlib.Path(root)
    csv.field_size_limit(10**7)
    for filename, (tier, tier_local, _fields) in sorted(FILES.items()):
        path = root / "data" / filename
        if not path.exists():
            continue
        with path.open(encoding="utf-8") as fh:
            raw = list(csv.DictReader(fh))
        expected = DECLARED.get(filename)
        if expected is not None and len(raw) != expected:
            raise SystemExit(
                f"{REPO}: {filename} holds {len(raw):,} records, "
                f"{expected:,} declared - the sibling changed"
            )

        candidates = fold([convert(r, tier, tier_local, filename) for r in raw])
        seats = collapse.to_seats(candidates, ["_key"], vote_field="votes")
        expected = SEATS.get(filename)
        if expected is not None and len(seats) != expected:
            raise SystemExit(
                f"{REPO}: {filename} collapses to {len(seats):,} seats, "
                f"{expected:,} declared - the seat key changed"
            )
        for seat in seats:
            members = seat["seat_members"]
            # both are properties of the whole contest, and to_seats copies the
            # first candidate's row, so they have to be gathered from all of it
            seat["duplicate_candidacy"] = int(
                any(m.get("duplicate_candidacy") for m in members)
            )
            seat["serial_not_unique"] = int(
                any(m.get("serial_not_unique") for m in members)
            )
            for row in [seat, *members]:
                row.pop("_key", None)
                row.pop("_serial", None)
        yield {
            "dataset_id": f"bihar/{tier}/{YEAR}",
            "state": STATE,
            "rows": seats,
            # the scrape kept neither a document nor a page
            "provenance_level": "dataset",
            "unit_of_observation": "seat_from_candidates",
        }

    yield from bihar_2021.slices(root)


def fold(candidates):
    """Collapse a candidacy the scrape captured twice.

    A candidacy is a serial number and a name within one seat. Where the same
    one appears more than once the vote counts differ - 130 and 137, 604 and 71
    - so these are two readings of one contest rather than two contests, and the
    higher count is the later reading. Where one serial carries two different
    names nothing is folded: which of them is the stray is not decidable from
    the file, and inventing an answer is worse than carrying both and saying so.
    """
    grouped = collections.OrderedDict()
    for candidate in candidates:
        grouped.setdefault(
            (candidate["_key"], candidate["_serial"], candidate["candidate_name"]), []
        ).append(candidate)

    out = []
    for group in grouped.values():
        kept = max(group, key=lambda c: (c["votes"] is not None, c["votes"]))
        if len(group) > 1:
            kept = dict(kept, duplicate_candidacy=len(group))
        out.append(kept)

    ambiguous = collections.Counter()
    for candidate in out:
        ambiguous[(candidate["_key"], candidate["_serial"])] += 1
    for candidate in out:
        if ambiguous[(candidate["_key"], candidate["_serial"])] > 1:
            candidate["serial_not_unique"] = 1
    return out


def convert(row, tier, tier_local, filename):
    """One candidate, in the shape `collapse.to_seats` reads."""
    stated = row.get("reservation_status", "")
    caste = normalize.caste_of(stated)
    woman = normalize.woman_of(stated)
    district_code, district = split_code(row.get("district"))
    block_code, block = split_code(row.get("block"))
    panchayat_code, panchayat = split_code(row.get("panchayat"))
    ward_code, ward_name = split_code(row.get("ward"))
    return {
        "_key": key_of(row, FILES[filename][2]),
        "_serial": serial(row.get("sr_no")),
        "state": STATE,
        "year": YEAR,
        "tier": tier,
        "tier_local": tier_local,
        "district": district,
        "block": block,
        "gram_panchayat": panchayat,
        "ward_no": ward_code,
        "ward_name": ward_name,
        "seat_no": serial(row.get("number")) if "NUM" in FILES[filename][2] else "",
        "caste_reservation": caste or "",
        "caste_reservation_local": stated.strip(),
        # The vocabulary is paired - every category appears plain and with
        # (महिला) - so a plain label is a statement that the seat is not
        # reserved for a woman, not a silence. 328 rows state no category at
        # all and stay blank in both columns.
        "woman_reserved": "" if caste is None else int(woman == 1),
        "gender_stated": "" if caste is None else 1,
        "reservation": label(caste, woman == 1) if caste else "",
        "reservation_raw": stated.strip(),
        # Read from the row rather than asserted. Hardcoding this shipped
        # 304,689 rows saying the wrong thing - see normalize.script_of.
        "script": normalize.script_of(
            district, block, panchayat, row.get("candidate_name") or ""
        ),
        "source_path": f"data/{filename}",
        "source_page": "",
        # the codes Bihar numbers its places by, kept out of the join key and
        # off the master, recoverable from master_extras.parquet
        "district_code": district_code,
        "block_code": block_code,
        "panchayat_code": panchayat_code,
        "seat_id_printed": (row.get("number") or "").strip(),
        # the long form
        "candidate_name": (row.get("candidate_name") or "").strip(),
        "relation_name": (row.get("father_husband_name") or "").strip(),
        "candidate_gender": (row.get("gender") or "").strip(),
        "candidate_woman": WOMAN.get((row.get("gender") or "").strip(), ""),
        "candidate_age": (row.get("age") or "").strip(),
        "candidate_caste": (row.get("category") or "").strip(),
        "candidate_education": (row.get("educ") or "").strip(),
        "party": "",
        "votes": collapse.votes_of(row.get("valid_vote")),
        "result": (row.get("remarks") or "").strip(),
    }
