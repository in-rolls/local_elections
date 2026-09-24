"""Rajasthan, from ``local_elections_rajasthan``.

The sibling contains complementary rural sources. Four standardized
sarpanch panels cover the 2005, 2010, 2015 and 2020 reservation cycles. The
2005 and 2010 Panchayat Samiti and Zila Parishad result books supply every
block- and district-member ward with its seat reservation and elected member.
A separate Rajasthan SEC scrape records sarpanch candidates, sarpanch results,
ward winners and nomination summaries for 2020--2022. The scrape is already
acquired data: this adapter parses it without touching the network.

The 2020 reservation roster has 11,314 rows. The general-election scrape names
11,310 contests; four roster seats have no scraped contest. Those four are kept
as roster-only seats rather than discarded. Conversely, thirteen by-election
contests have candidates but no winner row. They remain candidate-derived seats
with a blank winner. No fuzzy linkage is used: all 11,432 published winners
match a candidate contest and candidate name on normalized exact keys.

The candidate scrape includes mobile numbers and email addresses. Those are
deliberately excluded under the pooled corpus's contact-data policy; the
candidate's non-contact attributes are retained.
"""

import collections
import csv
import gzip
import hashlib
import pathlib
import re

from local_elections.common import normalize
from local_elections.common.normalize import label
from local_elections.common.runlog import get_logger

REPO = "local_elections_rajasthan"
URL = "https://github.com/in-rolls/local_elections_rajasthan"
STATE = "Rajasthan"

LOGGER = get_logger(__name__)

SEAT_FILES = {
    "2005": "data/fin/source_2005_std.parquet",
    "2010": "data/fin/source_2010_std.parquet",
    "2015": "data/fin/source_2015_std.parquet",
    "2020": "data/fin/source_2020_std.parquet",
}

CONTESTING_FILE = "data/ContestingSarpanch.csv.gz"
WINNER_FILE = "data/WinnerSarpanch.csv.gz"
WARD_FILE = "data/WarnWinningPanch.csv.gz"
NOMINATION_FILE = "data/StatsNomination.csv.gz"
BLOCK_MEMBER_FILES = {
    "2005": "data/fin/panchayat_samiti_2005_std.parquet",
    "2010": "data/fin/panchayat_samiti_2010_std.parquet",
}
ZP_MEMBER_FILES = {
    "2005": "data/fin/zila_parishad_2005_std.parquet",
    "2010": "data/fin/zila_parishad_2010_std.parquet",
}

DECLARED = {
    **{"2005": 9178, "2010": 9166, "2015": 9862, "2020": 11314},
    CONTESTING_FILE: 68202,
    WINNER_FILE: 11432,
    WARD_FILE: 110296,
    NOMINATION_FILE: 13473,
    "data/fin/panchayat_samiti_2005_std.parquet": 5257,
    "data/fin/panchayat_samiti_2010_std.parquet": 5273,
    "data/fin/zila_parishad_2005_std.parquet": 1008,
    "data/fin/zila_parishad_2010_std.parquet": 1013,
}

DECLARED_UNITS = {
    ("gp_head", "2005"): 9178,
    ("gp_head", "2010"): 9166,
    ("gp_head", "2015"): 9862,
    ("gp_head", "2020"): 11304,
    ("gp_head", "2021"): 89,
    ("gp_head", "2022"): 56,
    ("gp_ward", "2020"): 108197,
    ("gp_ward", "2021"): 1373,
    ("gp_ward", "2022"): 726,
    ("block_member", "2005"): 5257,
    ("block_member", "2010"): 5273,
    ("zp_member", "2005"): 1008,
    ("zp_member", "2010"): 1013,
}

NOMINATION_UNITS = {"2020": 11310, "2021": 1304, "2022": 859}

CASTE = {"GEN": "NONE", "SC": "SC", "ST": "ST", "OBC": "BC"}
YEAR = re.compile(r"(20\d{2})")


def blank(value):
    text = "" if value is None else str(value).strip()
    return "" if text.lower() in {"", "nan", "none", "null"} else text


def integer(value):
    text = blank(value)
    if not text:
        return ""
    try:
        number = float(text)
    except ValueError:
        return text
    return str(int(number)) if number.is_integer() else text


def event_year(row):
    got = YEAR.search(blank(row.get("ElectionDuration")))
    if not got:
        raise SystemExit(f"{REPO}: no election year in {row.get('ElectionDuration')!r}")
    return got.group(1)


def place(value):
    return blank(value).replace(" PANCHAYAT SAMITI", "").strip()


def normalized(value):
    return "".join(
        character for character in place(value).casefold() if character.isalnum()
    )


def event_key(row, gp_field):
    return (
        blank(row.get("ElectionType")),
        blank(row.get("ElectionDuration")),
        normalized(row.get("District")),
        normalized(row.get("PanchayatSamiti")),
        normalized(row.get(gp_field)),
    )


def roster_key(row):
    local = blank(row.get("reservation_raw")).upper()
    local = normalized(local).replace("GENERAL", "GEN").replace("WOMAN", "W")
    return (
        normalized(row.get("district_raw")),
        normalized(row.get("gp_raw")),
        local,
    )


def result_roster_key(row):
    local = normalized(row.get("CategoryOfGramPanchyat"))
    local = local.replace("GENERAL", "GEN").replace("WOMAN", "W")
    return (
        normalized(row.get("District")),
        normalized(row.get("NameOfGramPanchyat")),
        local,
    )


def reservation(category):
    local = blank(category)
    caste = normalize.caste_of(local)
    woman = normalize.woman_of(local)
    if caste is None or woman is None:
        raise SystemExit(f"{REPO}: unrecognized reservation label {local!r}")
    return {
        "caste_reservation": caste,
        "caste_reservation_local": local,
        "woman_reserved": int(woman),
        "gender_stated": 1,
        "reservation": label(caste, woman == 1),
        "reservation_raw": local,
    }


def read_csv(root, relative, expected):
    path = pathlib.Path(root) / relative
    if not path.exists():
        return []
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8-sig", errors="replace", newline="") as fh:
        rows = list(csv.DictReader(fh))
    if len(rows) != expected:
        raise SystemExit(
            f"{REPO}: {relative} holds {len(rows):,} records, "
            f"{expected:,} declared - the sibling changed"
        )
    LOGGER.info(
        "Rajasthan source loaded",
        extra={
            "event": "adapter_source_loaded",
            "state": STATE,
            "source_path": relative,
            "records": len(rows),
        },
    )
    return rows


def check_units(tier, year, rows):
    expected = DECLARED_UNITS[(tier, year)]
    if len(rows) != expected:
        raise SystemExit(
            f"{REPO}: {year} {tier} produces {len(rows):,} seats, "
            f"{expected:,} declared - the seat key changed"
        )


def old_panel_slices(root):
    try:
        import pandas
    except ImportError:
        raise SystemExit(
            f"{REPO}: pandas is required to read its parquet panels"
        ) from None

    root = pathlib.Path(root)
    for year, relative in sorted(SEAT_FILES.items()):
        if year == "2020":
            continue
        path = root / relative
        if not path.exists():
            continue
        frame = pandas.read_parquet(path)
        if len(frame) != DECLARED[year]:
            raise SystemExit(
                f"{REPO}: {year} holds {len(frame):,} rows, "
                f"{DECLARED[year]:,} declared - the sibling changed"
            )
        rows = [
            old_panel_row(record, year, relative) for record in frame.to_dict("records")
        ]
        check_units("gp_head", year, rows)
        yield {
            "dataset_id": f"rajasthan/gp_head/{year}",
            "state": STATE,
            "rows": rows,
            "provenance_level": "dataset",
            "unit_of_observation": "seat",
        }


def old_panel_row(record, year, relative):
    local = blank(record.get("caste_category")).upper()
    caste = CASTE.get(local)
    if local and caste is None:
        raise SystemExit(f"{REPO}: {year} has unknown caste label {local!r}")
    woman = integer(record.get("female_reserved")) if caste else ""
    winner_female = integer(record.get("winner_female"))
    return {
        "state": STATE,
        "year": year,
        "tier": "gp_head",
        "tier_local": "sarpanch",
        "district": blank(record.get("district_raw")),
        "block": blank(record.get("samiti_raw")),
        # The sibling's cross-year standardization is useful for linkage but
        # is not an identifier: in 2005 it maps distinct printed GPs such as
        # DAULATPURA-I and DAULATPURA-II onto one name. The printed value is
        # therefore authoritative for seat identity, while the standardized
        # value remains available as a non-key auxiliary field.
        "gram_panchayat": blank(record.get("gp_raw")) or blank(record.get("gp_std")),
        "gram_panchayat_standardized": blank(record.get("gp_std")),
        "ward_no": "",
        "caste_reservation": caste or "",
        "caste_reservation_local": local,
        "woman_reserved": woman,
        "gender_stated": 1 if caste else 0,
        "reservation": label(caste, woman == "1") if caste else "",
        "reservation_raw": blank(record.get("reservation_raw")),
        "winner": blank(record.get("winner_name")),
        "winner_basis": "published" if blank(record.get("winner_name")) else "",
        "winner_gender": ("Woman" if winner_female == "1" else "Other than Woman")
        if winner_female
        else "",
        "script": "latin",
        "source_path": relative,
        "source_page": "",
    }


def block_member_slices(root):
    try:
        import pandas
    except ImportError:
        raise SystemExit(
            f"{REPO}: pandas is required to read its parquet panels"
        ) from None

    root = pathlib.Path(root)
    for year, relative in sorted(BLOCK_MEMBER_FILES.items()):
        path = root / relative
        if not path.exists():
            continue
        frame = pandas.read_parquet(path)
        if len(frame) != DECLARED[relative]:
            raise SystemExit(
                f"{REPO}: {relative} holds {len(frame):,} rows, "
                f"{DECLARED[relative]:,} declared - the sibling changed"
            )
        rows = [
            block_member_row(record, year, relative)
            for record in frame.to_dict("records")
        ]
        check_units("block_member", year, rows)
        LOGGER.info(
            "Rajasthan source loaded",
            extra={
                "event": "adapter_source_loaded",
                "state": STATE,
                "source_path": relative,
                "records": len(rows),
            },
        )
        yield {
            "dataset_id": f"rajasthan/block_member/{year}",
            "state": STATE,
            "rows": rows,
            "provenance_level": "row",
            "unit_of_observation": "seat",
        }


def block_member_row(record, year, relative):
    local = blank(record.get("caste_category")).upper()
    caste = CASTE.get(local)
    if caste is None:
        raise SystemExit(f"{REPO}: {year} block member has unknown caste {local!r}")
    filled = integer(record.get("seat_filled")) != "0"
    winner_local = blank(record.get("winner_caste_category")).upper()
    winner_caste = CASTE.get(winner_local)
    if filled and winner_caste is None:
        raise SystemExit(
            f"{REPO}: {year} block member has unknown winner caste {winner_local!r}"
        )
    woman = integer(record.get("female_reserved"))
    winner_female = integer(record.get("winner_female"))
    category_sex_agree = integer(record.get("winner_category_sex_agree"))
    return {
        "state": STATE,
        "year": year,
        "tier": "block_member",
        "tier_local": "panchayat_samiti_member",
        "district": blank(record.get("district_raw")),
        "block": blank(record.get("samiti_raw")),
        "seat_no": integer(record.get("ward_no")),
        "ward_no_raw": integer(record.get("ward_no_raw")),
        "ward_no_inferred": integer(record.get("ward_no_inferred")),
        "listing_scope": "all_seats",
        "caste_reservation": caste,
        "caste_reservation_local": blank(record.get("reservation_raw")),
        "woman_reserved": woman,
        "gender_stated": 1,
        "reservation": label(caste, woman == "1"),
        "reservation_raw": blank(record.get("reservation_raw")),
        "winner": blank(record.get("winner_name")),
        "winner_basis": "published" if blank(record.get("winner_name")) else "",
        "winner_gender": ("Woman" if winner_female == "1" else "Other than Woman")
        if winner_female
        else "",
        "winner_caste": winner_caste or "",
        "winner_category_raw": blank(record.get("winner_category_raw")),
        "winner_category": blank(record.get("winner_category")),
        "winner_category_sex_agree": category_sex_agree,
        "party": blank(record.get("party")) or blank(record.get("party_raw")),
        "party_local": blank(record.get("party_raw")),
        "winner_votes": integer(record.get("votes_secured")),
        "margin": integer(record.get("margin")),
        "unopposed": integer(record.get("elected_uncontested")),
        "vacant": 0 if filled else 1,
        "winner_name_missing": integer(record.get("winner_name_missing")),
        "reservation_body_control_agree": integer(
            record.get("reservation_body_control_agree")
        ),
        "margin_below_votes": integer(record.get("margin_below_votes")),
        "script": "latin",
        "source_path": blank(record.get("source_path")) or relative,
        "source_page": integer(record.get("source_page")),
    }


def zp_member_slices(root):
    try:
        import pandas
    except ImportError:
        raise SystemExit(
            f"{REPO}: pandas is required to read its parquet panels"
        ) from None

    root = pathlib.Path(root)
    for year, relative in sorted(ZP_MEMBER_FILES.items()):
        path = root / relative
        if not path.exists():
            continue
        frame = pandas.read_parquet(path)
        if len(frame) != DECLARED[relative]:
            raise SystemExit(
                f"{REPO}: {relative} holds {len(frame):,} rows, "
                f"{DECLARED[relative]:,} declared - the sibling changed"
            )
        rows = [
            zp_member_row(record, year, relative) for record in frame.to_dict("records")
        ]
        check_units("zp_member", year, rows)
        LOGGER.info(
            "Rajasthan source loaded",
            extra={
                "event": "adapter_source_loaded",
                "state": STATE,
                "source_path": relative,
                "records": len(rows),
            },
        )
        yield {
            "dataset_id": f"rajasthan/zp_member/{year}",
            "state": STATE,
            "rows": rows,
            "provenance_level": "row",
            "unit_of_observation": "seat",
        }


def zp_member_row(record, year, relative):
    local = blank(record.get("caste_category")).upper()
    caste = CASTE.get(local)
    if caste is None:
        raise SystemExit(f"{REPO}: {year} ZP member has unknown caste {local!r}")
    filled = integer(record.get("seat_filled")) != "0"
    winner_local = blank(record.get("winner_caste_category")).upper()
    winner_caste = CASTE.get(winner_local)
    if filled and winner_caste is None:
        raise SystemExit(
            f"{REPO}: {year} ZP member has unknown winner caste {winner_local!r}"
        )
    woman = integer(record.get("female_reserved"))
    winner_female = integer(record.get("winner_female"))
    return {
        "state": STATE,
        "year": year,
        "tier": "zp_member",
        "tier_local": "zila_parishad_member",
        "district": blank(record.get("district")) or blank(record.get("district_raw")),
        "district_raw": blank(record.get("district_raw")),
        "district_inferred": integer(record.get("district_inferred")),
        "seat_no": integer(record.get("ward_no")),
        "ward_no_raw": integer(record.get("ward_no_raw")),
        "ward_no_inferred": integer(record.get("ward_no_inferred")),
        "listing_scope": "all_seats",
        "caste_reservation": caste,
        "caste_reservation_local": blank(record.get("reservation_raw")),
        "woman_reserved": woman,
        "gender_stated": 1,
        "reservation": label(caste, woman == "1"),
        "reservation_raw": blank(record.get("reservation_raw")),
        "winner": blank(record.get("winner_name")),
        "winner_basis": "published" if blank(record.get("winner_name")) else "",
        "winner_gender": ("Woman" if winner_female == "1" else "Other than Woman")
        if winner_female
        else "",
        "winner_caste": winner_caste or "",
        "winner_category_raw": blank(record.get("winner_category_raw")),
        "winner_category": blank(record.get("winner_category")),
        "winner_category_sex_agree": integer(record.get("winner_category_sex_agree")),
        "party": blank(record.get("party")) or blank(record.get("party_raw")),
        "party_local": blank(record.get("party_raw")),
        "winner_votes": integer(record.get("votes_secured")),
        "margin": integer(record.get("margin")),
        "unopposed": integer(record.get("elected_uncontested")),
        "unopposed_inferred": integer(record.get("uncontested_inferred")),
        "vacant": 0 if filled else 1,
        "margin_below_votes": integer(record.get("margin_below_votes")),
        "script": "latin",
        "source_path": blank(record.get("source_path")) or relative,
        "source_page": integer(record.get("source_page")),
    }


def candidate_member(row, winner=None, winner_matches=0, runner_matches=0):
    name = blank(row.get("NameOfContestingCandidate"))
    winner_name = blank((winner or {}).get("WinnerCandidateName"))
    runner_name = blank((winner or {}).get("RunnerupCandidateName"))
    matches_winner = bool(winner_name and normalized(name) == normalized(winner_name))
    matches_runner = bool(runner_name and normalized(name) == normalized(runner_name))
    is_winner = matches_winner and winner_matches == 1
    is_runner = matches_runner and runner_matches == 1
    gender = blank(row.get("Gender"))
    return {
        "candidate_no": integer(row.get("ContestingCandidateSerialNo")),
        "candidate_name": name,
        "relation_name": blank(row.get("FatherHusbandOfContestingCandidate")),
        "candidate_gender": gender,
        "candidate_woman": 1 if gender == "F" else 0 if gender in {"M", "O"} else "",
        "candidate_age": integer(row.get("Age")),
        "candidate_caste": blank(row.get("CategoryOfCandidate")),
        "candidate_education": blank(row.get("EducationStatus")),
        "candidate_marital_status": blank(row.get("MartialStatus")),
        "candidate_occupation": blank(row.get("ContestingCandidateOccupation")),
        "candidate_total_assets": integer(row.get("TotalValueOfCapitalAssets")),
        "candidate_children_before_1995_11_27": integer(
            row.get("ChildrenBefore27111995")
        ),
        "candidate_children_after_1995_11_27": integer(
            row.get("ChildrenOnOrAfter28111995")
        ),
        "party": "",
        "votes": (
            integer((winner or {}).get("VoteSecureByWinner"))
            if is_winner
            else integer((winner or {}).get("VoteSecureByRunnerup"))
            if is_runner
            else ""
        ),
        "candidate_rank": 1 if is_winner else 2 if is_runner else "",
        "elected": (
            1
            if is_winner
            else ""
            if matches_winner and winner_matches > 1
            else 0
            if winner
            else ""
        ),
        "result": "winner" if is_winner else "runner_up" if is_runner else "",
    }


def nomination_fields(row):
    if not row:
        return {}
    return {
        "nominations_filed": integer(row.get("NominationTotalNoOfNominationFilled")),
        "nomination_candidates": integer(row.get("NominationCandidate")),
        "validly_nominated_candidates": integer(row.get("ValidlyNominatedCandidate")),
        "withdrawals": integer(row.get("Withdrawal")),
        "nominated_unopposed": integer(row.get("Unopposed")),
        "contestants": integer(row.get("Contestants")),
        "nomination_source_path": NOMINATION_FILE,
    }


def head_row(candidate_rows, winner, nomination):
    first = candidate_rows[0]
    candidate_names = collections.Counter(
        normalized(row.get("NameOfContestingCandidate")) for row in candidate_rows
    )
    winner_matches = candidate_names[
        normalized((winner or {}).get("WinnerCandidateName"))
    ]
    runner_matches = candidate_names[
        normalized((winner or {}).get("RunnerupCandidateName"))
    ]
    got = {
        "state": STATE,
        "year": event_year(first),
        "tier": "gp_head",
        "tier_local": "sarpanch",
        "district": blank(first.get("District")),
        "block": place(first.get("PanchayatSamiti")),
        "gp_no": integer(first.get("SrNo")),
        "gram_panchayat": blank(first.get("NameOfGramPanchayat")),
        "ward_no": "",
        "listing_scope": "all_seats",
        "winner": blank((winner or {}).get("WinnerCandidateName")),
        "winner_basis": "published" if winner else "",
        "votes": integer((winner or {}).get("VoteSecureByWinner")),
        "runner_up": blank((winner or {}).get("RunnerupCandidateName")),
        "runner_up_votes": integer((winner or {}).get("VoteSecureByRunnerup")),
        "unopposed": (
            1
            if blank((winner or {}).get("ElectedUnoppose")).upper() == "YES"
            else 0
            if winner
            else ""
        ),
        "script": "latin",
        "source_path": CONTESTING_FILE,
        "source_page": "",
        "result_source_path": WINNER_FILE if winner else "",
        "election_type": blank(first.get("ElectionType")),
        "election_duration": blank(first.get("ElectionDuration")),
        "seat_members": [
            candidate_member(row, winner, winner_matches, runner_matches)
            for row in candidate_rows
        ],
        "seat_candidates": len(candidate_rows),
        "winner_candidate_ambiguous": int(winner_matches > 1),
    }
    got.update(reservation(first.get("CategoryOfGramPanchayat")))
    got.update(nomination_fields(nomination))
    if winner:
        winner_votes = integer(winner.get("VoteSecureByWinner"))
        runner_votes = integer(winner.get("VoteSecureByRunnerup"))
        unopposed = blank(winner.get("ElectedUnoppose")).upper() == "YES"
        if winner_votes and runner_votes and not unopposed:
            got["margin"] = int(winner_votes) - int(runner_votes)
        got.update(
            {
                "total_candidates_stated": integer(
                    winner.get("TotalNoOfContestingCandidate")
                ),
                "electorate": integer(winner.get("TotalElectorateVotes")),
                "votes_polled": integer(winner.get("TotalPolledVotes")),
                "rejected_votes": integer(winner.get("RejectedVotes")),
                "valid_votes": integer(winner.get("TotalValidVotes")),
                "poll_percentage": blank(winner.get("PollPercent")),
                "nota_votes": integer(winner.get("TotalNoOfNOTACount")),
                "tendered_votes": integer(winner.get("TenderedVotes")),
                "winner_pledge_url": blank(winner.get("ViewPledge")),
            }
        )
        winning_member = next(
            (
                member
                for member in got["seat_members"]
                if member.get("result") == "winner"
            ),
            {},
        )
        got.update(
            {
                "winner_gender": winning_member.get("candidate_gender", ""),
                "winner_caste": winning_member.get("candidate_caste", ""),
                "winner_age": winning_member.get("candidate_age", ""),
                "winner_education": winning_member.get("candidate_education", ""),
                "winner_occupation": winning_member.get("candidate_occupation", ""),
                "winner_marital_status": winning_member.get(
                    "candidate_marital_status", ""
                ),
                "relation_name": winning_member.get("relation_name", ""),
            }
        )
    return got


def roster_only_rows(root, result_rows):
    try:
        import pandas
    except ImportError:
        raise SystemExit(
            f"{REPO}: pandas is required to read its parquet panels"
        ) from None

    relative = SEAT_FILES["2020"]
    frame = pandas.read_parquet(pathlib.Path(root) / relative)
    if len(frame) != DECLARED["2020"]:
        raise SystemExit(
            f"{REPO}: 2020 holds {len(frame):,} rows, {DECLARED['2020']:,} declared"
        )
    general = [
        row for row in result_rows if row.get("ElectionType") == "General Election"
    ]
    available = collections.Counter(result_roster_key(row) for row in general)
    out = []
    for record in frame.to_dict("records"):
        key = roster_key(record)
        if available[key]:
            available[key] -= 1
            continue
        row = old_panel_row(record, "2020", relative)
        row["unit_of_observation"] = "seat"
        out.append(row)
    if sum(available.values()):
        raise SystemExit(
            f"{REPO}: result rows exist outside the 2020 reservation roster"
        )
    if len(out) != 4:
        raise SystemExit(
            f"{REPO}: 2020 roster has {len(out):,} result-free rows, 4 declared"
        )
    return out


def head_slices(root, candidates, winners, nominations):
    winner_by_key = {event_key(row, "NameOfGramPanchyat"): row for row in winners}
    if len(winner_by_key) != len(winners):
        raise SystemExit(f"{REPO}: winner event key is not unique")
    nomination_by_key = {event_key(row, "GramPanchayat"): row for row in nominations}
    if len(nomination_by_key) != len(nominations):
        raise SystemExit(f"{REPO}: nomination event key is not unique")

    grouped = collections.OrderedDict()
    for row in candidates:
        grouped.setdefault(event_key(row, "NameOfGramPanchayat"), []).append(row)
    if len(grouped) != 11445:
        raise SystemExit(
            f"{REPO}: candidates identify {len(grouped):,} contests, 11,445 declared"
        )
    missing_candidates = set(winner_by_key) - set(grouped)
    if missing_candidates:
        raise SystemExit(
            f"{REPO}: {len(missing_candidates):,} winner contests have no candidates"
        )

    by_year = collections.defaultdict(list)
    for key, members in grouped.items():
        row = head_row(members, winner_by_key.get(key), nomination_by_key.get(key))
        by_year[row["year"]].append(row)
    for row in roster_only_rows(root, winners):
        by_year["2020"].append(row)

    for year, rows in sorted(by_year.items()):
        check_units("gp_head", year, rows)
        yield {
            "dataset_id": f"rajasthan/gp_head/{year}",
            "state": STATE,
            "rows": rows,
            "provenance_level": "dataset",
            "unit_of_observation": "seat_from_candidates",
        }


def ward_row(row):
    winner = blank(row.get("NameOfCandidate"))
    winner_category = blank(row.get("CategoryOfWinningCandidate"))
    got = {
        "state": STATE,
        "year": event_year(row),
        "tier": "gp_ward",
        "tier_local": "panch",
        "district": blank(row.get("District")),
        "block": place(row.get("PanchayatSamiti")),
        "gp_no": integer(row.get("SrNo")),
        "gram_panchayat": blank(row.get("Grampanchayat")),
        "ward_no": integer(row.get("WardNo")),
        "ward_name": blank(row.get("NameOfVillage")),
        "listing_scope": "all_seats",
        "winner": winner,
        "winner_basis": "published" if winner else "",
        "votes": integer(row.get("WinnerVotes")),
        "runner_up_votes": (
            ""
            if blank(row.get("WhetherElectedUnoppose")).upper() == "YES"
            else integer(row.get("LooserVotes"))
        ),
        "unopposed": 1
        if blank(row.get("WhetherElectedUnoppose")).upper() == "YES"
        else 0,
        "vacant": int(not winner),
        "winner_caste": winner_category if winner else "",
        "winner_gender": (
            "Woman"
            if winner and normalize.woman_of(winner_category) == 1
            else "Other than Woman"
            if winner
            else ""
        ),
        "winner_category_raw": winner_category,
        "electorate": integer(row.get("TotalNoOfVotes")),
        "votes_polled": integer(row.get("VotesPolled")),
        "poll_percentage": blank(row.get("PollPercent")),
        "result_remark": blank(row.get("RemarkIfAny")),
        "election_type": blank(row.get("ElectionType")),
        "election_duration": blank(row.get("ElectionDuration")),
        "script": "latin",
        "source_path": WARD_FILE,
        "source_page": "",
    }
    got.update(reservation(row.get("CategoryOfWard")))
    winner_votes = integer(row.get("WinnerVotes"))
    runner_votes = integer(row.get("LooserVotes"))
    if winner_votes and runner_votes and not got["unopposed"]:
        got["margin"] = int(winner_votes) - int(runner_votes)
    return got


def ward_slices(rows):
    by_year = collections.defaultdict(list)
    seen = set()
    for raw in rows:
        key = (*event_key(raw, "Grampanchayat"), integer(raw.get("WardNo")))
        if key in seen:
            raise SystemExit(f"{REPO}: duplicate ward event key {key!r}")
        seen.add(key)
        row = ward_row(raw)
        by_year[row["year"]].append(row)
    for year, subset in sorted(by_year.items()):
        check_units("gp_ward", year, subset)
        yield {
            "dataset_id": f"rajasthan/gp_ward/{year}",
            "state": STATE,
            "rows": subset,
            "provenance_level": "dataset",
            "unit_of_observation": "seat",
        }


def slices(root):
    yield from old_panel_slices(root)
    yield from block_member_slices(root)
    yield from zp_member_slices(root)
    candidates = read_csv(root, CONTESTING_FILE, DECLARED[CONTESTING_FILE])
    winners = read_csv(root, WINNER_FILE, DECLARED[WINNER_FILE])
    nominations = read_csv(root, NOMINATION_FILE, DECLARED[NOMINATION_FILE])
    yield from head_slices(root, candidates, winners, nominations)
    wards = read_csv(root, WARD_FILE, DECLARED[WARD_FILE])
    yield from ward_slices(wards)


SUPPLEMENTAL_COLUMNS = [
    "dataset_id",
    "row_id",
    "state",
    "year",
    "election_type",
    "election_duration",
    "district",
    "block",
    "gp_no",
    "gram_panchayat",
    "nominations_filed",
    "nomination_candidates",
    "validly_nominated_candidates",
    "withdrawals",
    "nominated_unopposed",
    "contestants",
    "source_repo",
    "source_commit",
    "source_path",
    "provenance_level",
]


def supplemental(root):
    rows = read_csv(root, NOMINATION_FILE, DECLARED[NOMINATION_FILE])
    out = []
    by_year = collections.Counter()
    for raw in rows:
        year = event_year(raw)
        material = "|".join(event_key(raw, "GramPanchayat"))
        out.append(
            {
                "dataset_id": f"rajasthan/nomination_stats/{year}",
                "row_id": hashlib.sha1(material.encode("utf-8")).hexdigest()[:12],
                "state": STATE,
                "year": year,
                "election_type": blank(raw.get("ElectionType")),
                "election_duration": blank(raw.get("ElectionDuration")),
                "district": blank(raw.get("District")),
                "block": place(raw.get("PanchayatSamiti")),
                "gp_no": integer(raw.get("SrNo")),
                "gram_panchayat": blank(raw.get("GramPanchayat")),
                **nomination_fields(raw),
                "source_path": NOMINATION_FILE,
                "provenance_level": "dataset",
            }
        )
        by_year[year] += 1
    if dict(by_year) != NOMINATION_UNITS:
        raise SystemExit(
            f"{REPO}: nomination units are {dict(by_year)!r}, "
            f"{NOMINATION_UNITS!r} declared"
        )
    return {
        "name": "supplemental_rajasthan_nomination_stats.parquet",
        "columns": SUPPLEMENTAL_COLUMNS,
        "rows": out,
    }
