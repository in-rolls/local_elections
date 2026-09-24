"""Mumbai's Brihanmumbai Municipal Corporation: 227 ward seats, five councils.

Everything under ``data/maharashtra/mumbai/`` arrived as result tables assembled
for research (Bhavnani's 1997 and 2002 sheets; Karekurve-Ramachandra's 2007,
2012 and 2017 files), not as the Maharashtra State Election Commission's own
reservation rosters. That shapes what can honestly be emitted:

    council   reservation roster                            winners
    1997      none held                                     xls (209 of 221 wards)
    2002      none held                                     xls (203 of 227 wards)
    2007      women's flag only (deposit, 2011 wave)        2007 sheet
    2012      2007 sheet, "Present Reservation" column      2012 scan (218 wards)
    2017      deposit, 2018 wave `reservation_status`       2017 result csv

**The 2007 sheet's reservation column is the 2012 draw.** It lists 115 women's
seats where the 2007 council had 76 (one third), and it agrees ward for ward
with the deposit's 2012-term flag on 226 of 227 wards while agreeing with the
2007 term on 38. Its "Sitting Corporator" column is the 2007 winner (89% name
match to the 2011 survey wave). The sheet is a "who sits here now, what is the
seat reserved as next time" table, and reading it at face value would attach
the wrong term's reservation to every ward. It is therefore the source for the
**2012** slice's reservation and for the 2007 supplemental file's winners.

The deposit is Karekurve-Ramachandra & Lee (2025), Harvard Dataverse
doi:10.7910/DVN/IO9SLQ (CC0), fetched by ``harvest.py``. Its 2018 wave carries
the full 2017 reservation vocabulary (G, W, OBC, OBC-W, SC, SC-W, ST, ST-W); its
2011 wave carries only a women's flag for the 2007 council, so 2007 cannot enter
the schema (``caste_reservation`` is required on every row) and is written as a
supplemental file instead. The deposit digitised the commission's handbooks, so
its reservation is a secondary source and is recorded as such in the state
readme.

Two slices enter the schema: ``ulb_ward_2012`` and ``ulb_ward_2017``. Six files
are supplemental and carry no ``reservation`` column, which keeps them out of
the pooled machinery on purpose: the 2007 seats, one candidate table per
council, and the Praja Foundation ward-by-wave citizen ratings that the deposit
exists to publish. The ratings carry one flag: the satisfaction item is inverted
in the 2018 wave (its correlation with the thirteen service items is +0.44 in
2016 and -0.33 in 2018), which the parser records rather than repairs.

Ward 220 in 2017 is a two-way tie at 5,946 votes in the result file; the
deposit names the councillor who took the seat, and that name is used with
``winner_basis`` "published".
"""

import argparse
import collections
import csv
import re

from local_elections.common import emit, normalize
from local_elections.common.normalize import label
from local_elections.common.runlog import command
from local_elections.paths import ROOT

STATE = "Maharashtra"
DISTRICT = "Mumbai"
BODY = "Brihanmumbai Municipal Corporation"
WARDS = 227

DATA = ROOT / "data" / "maharashtra"
MUMBAI = DATA / "mumbai"
SHEET_2007 = "data/maharashtra/mumbai/BMC-2007_raw.xlsx"
SCAN_2012 = "data/maharashtra/mumbai/2012_scanned_data.xlsx"
CSV_2017 = "data/maharashtra/mumbai/mumbai_2017.csv"
XLS_1997 = "data/maharashtra/mumbai/BMC 1997.xls"
XLS_2002 = "data/maharashtra/mumbai/BMC 2002.xls"
DEPOSIT_DIR = "data/maharashtra/mumbai/dataverse_IO9SLQ"
DEPOSIT = f"{DEPOSIT_DIR}/mumbai_full.tab"
DEPOSIT_DAYS = f"{DEPOSIT_DIR}/fulldata_reshaped.tab"

COLUMNS = [
    "state",
    "year",
    "district",
    "body",
    "ward_no",
    "ward_name",
    "tier",
    "tier_local",
    "reservation",
    "caste_reservation",
    "caste_reservation_local",
    "woman_reserved",
    "reservation_raw",
    "winner",
    "winner_basis",
    "party",
    "party_local",
    "votes",
    "valid_votes",
    "electorate",
    "total_candidates_stated",
    "listing_scope",
    "script",
    "result_source_path",
    "source_path",
    "source_page",
]

# Statutory women's share per council: one third until 2011, one half after.
WOMEN_SEATS = {"2007": 76, "2012": 114, "2017": 114}
DECLARED = {"2012": WARDS, "2017": WARDS}

# Party names as the three result files print them -> one short label.
PARTY = {
    "sena": "SS",
    "shivsena": "SS",
    "shiv sena": "SS",
    "bjp": "BJP",
    "bhartiya janata party": "BJP",
    "bharatiya janata party": "BJP",
    "cong": "INC",
    "inc": "INC",
    "indian national congress": "INC",
    "ncp": "NCP",
    "nationalist congress party": "NCP",
    # the 2012 scan's spelling of the NCP
    "indian nationalist congress": "NCP",
    "mns": "MNS",
    "maharashtra navnirman sena": "MNS",
    "sp": "SP",
    "samajwadi party": "SP",
    "bsp": "BSP",
    "bahujan samaj party": "BSP",
    "ind": "IND",
    "independent": "IND",
    # Marathi for independent
    "apaksh": "IND",
    "rpi(a)": "RPI(A)",
    "abs": "ABS",
    "aimim": "AIMIM",
    "all india majlis e ittehadul muslimeen": "AIMIM",
}

# The deposit's survey items, as its columns name them -> readable names.
RATING_ITEMS = {
    "conditionofroads": "roads",
    "trafficjamscongestionofroads": "traffic",
    "availabilityofpublicgardensopenp": "gardens",
    "availabilityofpublictransportfac": "transport",
    "availabilityoffoodthroughrations": "rations",
    "hospitalsandothermedicalfaciliti": "hospitals",
    "appropriateschoolsandcolleges": "schools",
    "powersupply": "power",
    "watersupply": "water",
    "waterloggingduringrainyseason": "flooding",
    "pollutionproblems": "pollution",
    "instancesofcrime": "crime",
    "lawordersituation": "law_order",
    "cleanlinesssanitationfacilities": "sanitation",
    "recallforpartynametowhichthecorp": "recall_party",
    "recallfornameofthecorporator": "recall_name",
    "accesibilityofthecorporator": "accessibility",
    "satisfactionwiththecorporator": "satisfaction",
    "curruption": "corruption",
    "improvmentinlifestyle": "quality_of_life",
    "availabilityoffootpathsandpedest": "footpaths",
}
SERVICE_ITEMS = [
    "roads", "traffic", "gardens", "transport", "hospitals", "schools", "power",
    "water", "flooding", "pollution", "crime", "law_order", "sanitation",
]  # fmt: skip
COUNCILLOR_FIELDS = {
    "name": "councillor",
    "woman": "councillor_woman",
    "party": "councillor_party",
    "age": "councillor_age",
    "education_level": "councillor_education",
    "professional_education": "councillor_professional_education",
    "pan_card": "councillor_pan_card",
    "no_of_criminal_cases": "councillor_criminal_cases",
    "term": "council",
    "newid": "councillor_spell_id",
    "genderquota": "woman_reserved",
    "reservation_status": "reservation_raw",
}
ACTIVITY_FIELDS = [
    "total_funds", "funds_prop", "gbm_attended", "total_gbms", "ward_attendance",
    "total_ward_meetings", "other_meetings", "total_other_meetings", "total_questions",
    "slum", "samplesize", "adminward",
]  # fmt: skip
QUESTION_FIELDS = re.compile(r"^q_")
INVERTED = {("satisfaction", "2018")}


def clean(value):
    """A cell as text, with pandas' NaN and float-formatted integers removed.

    The deposit stores integers as "1.0" and "2007.0"; those become "1" and
    "2007" so a reader can compare them to the other files without casting.
    """
    if value is None:
        return ""
    if isinstance(value, float):
        if value != value:  # NaN
            return ""
        if value.is_integer():
            return str(int(value))
    text = str(value).strip()
    if re.fullmatch(r"-?\d+\.0+", text):
        return text.split(".")[0]
    return text


def party_of(printed):
    """A short party label for the printed name, or the name itself if unknown."""
    key = re.sub(r"\s+", " ", clean(printed).lower().replace(".", ""))
    return PARTY.get(key, clean(printed))


def read_excel(path, sheet: int | str = 0):
    """A spreadsheet as a list of dicts keyed by its header row."""
    import pandas

    frame = pandas.read_excel(ROOT / path, sheet_name=sheet, header=0)
    frame.columns = [clean(c) for c in frame.columns]
    return [{k: clean(v) for k, v in row.items()} for row in frame.to_dict("records")]


def read_tsv(path):
    """The deposit's tab-separated tables."""
    with (ROOT / path).open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh, delimiter="\t"))


def deposit_wave(rows, year):
    """One deposit row per ward for a survey wave, keyed by ward number."""
    out = {}
    for row in rows:
        if clean(row.get("year")) != year or not clean(row.get("ward")):
            continue
        out[clean(row["ward"])] = row
    return out


def seat(year, ward_no, stated, **rest):
    """One schema row; the reservation label is derived, never typed."""
    caste = normalize.caste_of(stated)
    # a phrase with no women's word ("Backward Class", "G") is an open seat
    woman = normalize.woman_of(stated) == 1
    if caste is None:
        raise SystemExit(
            f"maharashtra {year}: ward {ward_no} reservation {stated!r} unread"
        )
    row = {
        "state": STATE,
        "year": year,
        "district": DISTRICT,
        "body": BODY,
        "ward_no": ward_no,
        "tier": "ulb_ward",
        "tier_local": "corporator",
        "caste_reservation": caste,
        "caste_reservation_local": "OBC" if caste == "BC" else "",
        "woman_reserved": int(woman),
        "reservation": label(caste, woman),
        "reservation_raw": stated,
        "listing_scope": "all_seats",
        "script": "latin",
        "source_page": "",
        **rest,
    }
    if not re.search(r"[A-Za-z]", clean(row.get("winner"))):
        # ward 78 in 2017 prints its winner as underscores: a Devanagari name
        # the result export lost. Better blank than a row of underscores.
        row["winner"] = ""
        row["winner_basis"] = ""
    row["winner_basis"] = row.get("winner_basis") or (
        "published" if clean(row.get("winner")) else ""
    )
    return row


# ---------------------------------------------------------------------------
# 2007 sheet: 2007 winners, 2012 reservation
# ---------------------------------------------------------------------------


def sheet_2007():
    rows = read_excel(SHEET_2007, "Table 1")
    if len(rows) != WARDS or {r["WARD NO"] for r in rows} != {
        str(i) for i in range(1, 228)
    }:
        raise SystemExit(
            "maharashtra: the 2007 sheet no longer has wards 1-227 once each"
        )
    return rows


def winners_2012():
    """Top valid-vote candidate per ward from the 2012 scan transcription.

    218 of 227 wards are present and 9 of those winners have no name in the
    transcription; both stay blank rather than being filled from elsewhere.
    """
    rows = read_excel(SCAN_2012, "Sheet1")
    by_ward = collections.defaultdict(list)
    for r in rows:
        if r.get("Ward_No.") and r.get("Valid Votes"):
            by_ward[r["Ward_No."]].append(r)
    out = {}
    for ward, cands in by_ward.items():
        top = max(cands, key=lambda r: int(float(r["Valid Votes"])))
        out[ward] = {
            "winner": top.get("Candidates Name", ""),
            "party_local": top.get("Political Parties Name", ""),
            "votes": top["Valid Votes"],
            "electorate": top.get("Total Voters", ""),
            "valid_votes": top.get("Total Valid Votes", ""),
            "total_candidates_stated": len(cands),
        }
    return out


def rows_2012():
    winners = winners_2012()
    out = []
    for r in sheet_2007():
        ward = r["WARD NO"]
        won = winners.get(ward, {})
        out.append(
            seat(
                "2012",
                ward,
                r["Present Reservation"],
                ward_name=r.get("Locality", ""),
                winner=won.get("winner", ""),
                winner_basis="argmax_votes" if won.get("winner") else "",
                # the scan names the winning party even where it lost the name
                party=party_of(won.get("party_local", "")) if won else "",
                party_local=won.get("party_local", ""),
                votes=won.get("votes", ""),
                valid_votes=won.get("valid_votes", ""),
                electorate=won.get("electorate", ""),
                total_candidates_stated=won.get("total_candidates_stated", ""),
                result_source_path=SCAN_2012,
                source_path=SHEET_2007,
            )
        )
    return out


# ---------------------------------------------------------------------------
# 2017: results csv, reservation from the deposit's 2018 wave
# ---------------------------------------------------------------------------


def candidates_2017():
    with (ROOT / CSV_2017).open(encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
    by_ward = collections.defaultdict(list)
    for r in rows:
        by_ward[r["constituency"].strip()].append(r)
    return by_ward


def rows_2017(deposit):
    wave = deposit_wave(deposit, "2018")
    by_ward = candidates_2017()
    if set(by_ward) != {str(i) for i in range(1, 228)} or set(wave) != set(by_ward):
        raise SystemExit(
            "maharashtra 2017: results and deposit no longer cover wards 1-227"
        )
    out = []
    for ward in sorted(by_ward, key=int):
        cands = by_ward[ward]
        top_votes = max(int(c["Total Votes Secured"]) for c in cands)
        leaders = [c for c in cands if int(c["Total Votes Secured"]) == top_votes]
        basis = "published"
        if len(leaders) == 1:
            top = leaders[0]
        else:
            # a tie decided by lot; the deposit names who took the seat
            sitting = normalize_name(wave[ward].get("name", ""))
            match = [
                c
                for c in leaders
                if normalize_name(c["Name of Contesting Candidate"]) == sitting
            ]
            if len(match) != 1:
                raise SystemExit(
                    f"maharashtra 2017: ward {ward} tie not resolved by the deposit"
                )
            top = match[0]
        out.append(
            seat(
                "2017",
                ward,
                clean(wave[ward].get("reservation_status")),
                ward_name="",
                winner=top["Name of Contesting Candidate"].strip(),
                winner_basis=basis,
                party=party_of(top["Party Name"]),
                party_local=top["Party Name"].strip(),
                votes=top["Total Votes Secured"].strip(),
                total_candidates_stated=len(cands),
                result_source_path=CSV_2017,
                source_path=DEPOSIT,
            )
        )
    return out


def normalize_name(name):
    return re.sub(r"[^a-z]", "", clean(name).lower())


# ---------------------------------------------------------------------------
# Supplemental: 2007 seats, candidate tables, Praja ratings
# ---------------------------------------------------------------------------


def seats_2007(deposit):
    wave = deposit_wave(deposit, "2011")
    out = []
    for r in sheet_2007():
        ward = r["WARD NO"]
        flag = clean(wave.get(ward, {}).get("genderquota"))
        out.append(
            {
                "state": STATE,
                "year": "2007",
                "district": DISTRICT,
                "body": BODY,
                "ward_no": ward,
                "ward_name": r.get("Locality", ""),
                "tier": "ulb_ward",
                "woman_reserved": flag,
                "reservation_raw": "W" if flag == "1" else "",
                "caste_reservation_known": 0,
                "winner": r.get("Sitting Corporator", ""),
                "party": party_of(r.get("WINNING PARTY", "")),
                "party_local": r.get("WINNING PARTY", ""),
                "votes": r.get("WINNING VOTES", ""),
                "votes_polled": r.get("Total Votes polled", ""),
                "reservation_source_path": DEPOSIT,
                "source_path": SHEET_2007,
            }
        )
    return out


def candidates_xls(path, sheet, year):
    out = []
    for r in read_excel(path, sheet):
        keys = {k.lower().replace(" ", "").replace(".", ""): v for k, v in r.items()}
        ward = keys.get("wardno", "")
        if not ward or not keys.get("candidate"):
            continue
        out.append(
            {
                "year": year,
                "ward_no": ward,
                "candidate": keys.get("candidate", ""),
                "symbol": keys.get("symbol", ""),
                "gender": keys.get("gender", ""),
                "votes": keys.get("noofvotes", ""),
                "won": keys.get("wonlostwl", "").upper(),
                "incumbent": keys.get("incumbent", ""),
                "source_path": path,
            }
        )
    return out


def candidates_2012():
    return [
        {
            "year": "2012",
            "ward_no": r["Ward_No."],
            "serial": r.get("Sr.No.", ""),
            "candidate": r.get("Candidates Name", ""),
            "party": party_of(r.get("Political Parties Name", "")),
            "party_local": r.get("Political Parties Name", ""),
            "votes": r.get("Valid Votes", ""),
            "electorate": r.get("Total Voters", ""),
            "valid_votes": r.get("Total Valid Votes", ""),
            "source_path": SCAN_2012,
        }
        for r in read_excel(SCAN_2012, "Sheet1")
        if r.get("Ward_No.")
    ]


def candidates_2017_rows():
    out = []
    for ward, cands in candidates_2017().items():
        for c in cands:
            out.append(
                {
                    "year": "2017",
                    "ward_no": ward,
                    "candidate": c["Name of Contesting Candidate"].strip(),
                    "party": party_of(c["Party Name"]),
                    "party_local": c["Party Name"].strip(),
                    "votes": c["Total Votes Secured"].strip(),
                    "rank": c["Rank"].strip(),
                    "source_path": CSV_2017,
                }
            )
    return out


def praja_ratings(deposit):
    """The deposit's ward-by-wave table with readable names and one flag."""
    out = []
    for r in deposit:
        year = clean(r.get("year"))
        ward = clean(r.get("ward"))
        if not year or not ward or not clean(r.get("term")):
            continue  # one empty ward-8/2014 row in the deposit
        row = {
            "state": STATE,
            "body": BODY,
            "ward_no": ward,
            "survey_year": year,
        }
        for src, dst in COUNCILLOR_FIELDS.items():
            row[dst] = clean(r.get(src))
        for field in ACTIVITY_FIELDS:
            row[field] = clean(r.get(field))
        for src, dst in RATING_ITEMS.items():
            row[f"rating_{dst}"] = clean(r.get(src))
        for key in r:
            if QUESTION_FIELDS.match(key):
                row[f"questions_{key[2:]}"] = clean(r.get(key))
        row["rating_flags"] = ";".join(
            f"{item}_inverted" for item, wave in sorted(INVERTED) if wave == year
        )
        row["source_path"] = DEPOSIT
        out.append(row)
    return out


def complaint_days():
    return [
        {**{k: clean(v) for k, v in r.items()}, "source_path": DEPOSIT_DAYS}
        for r in read_tsv(DEPOSIT_DAYS)
    ]


def write_csv(rows, path):
    columns = list(dict.fromkeys(k for r in rows for k in r))
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


@command("parse", state=STATE)
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    deposit = read_tsv(DEPOSIT)
    archive = emit.archived(ROOT / DEPOSIT_DIR)

    for year, rows in (("2012", rows_2012()), ("2017", rows_2017(deposit))):
        for row in rows:
            if row["source_path"] == DEPOSIT:
                url, capture = archive.get("mumbai_full.tab", ("", ""))
                row["source_url"], row["source_capture"] = url, capture
            row["source_pdf"] = row["source_path"].rsplit("/", 1)[-1]
        emit.write(rows, DATA / f"ulb_ward_{year}", COLUMNS)
        if not args.quiet:
            women = sum(int(r["woman_reserved"]) for r in rows)
            print(f"  ulb_ward_{year}: {len(rows)} seats, {women} reserved for women")

    supplemental = {
        "bmc_seats_2007.csv": seats_2007(deposit),
        "bmc_candidates_1997.csv": candidates_xls(XLS_1997, "work1", "1997"),
        "bmc_candidates_2002.csv": candidates_xls(XLS_2002, "work3", "2002"),
        "bmc_candidates_2012.csv": candidates_2012(),
        "bmc_candidates_2017.csv": candidates_2017_rows(),
        "praja_ward_ratings_2011_2018.csv": praja_ratings(deposit),
        "praja_admin_ward_complaint_days_2013_2018.csv": complaint_days(),
    }
    for name, rows in supplemental.items():
        write_csv(rows, MUMBAI / name)
        if not args.quiet:
            print(f"  {name}: {len(rows):,} rows")


if __name__ == "__main__":
    main()
