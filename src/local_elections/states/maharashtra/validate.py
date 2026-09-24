"""Checks for the Mumbai (BMC) slices against things outside the parsed rows.

Three controls that do not come from the parser: the statutory women's share
(one third of 227 = 76 seats for the 2007 council, one half = 114 from 2012),
the deposit's independently digitised reservation flag for the 2012 council,
and the deposit's councillor names for 2012 and 2017, which were typed from
different documents than the result files the winners come from.
"""

import collections
import csv
import re
import statistics
import sys

from local_elections.common import checks, validation
from local_elections.common.runlog import command
from local_elections.paths import ROOT
from local_elections.states.maharashtra import harvest, parse

KEY = ("state", "year", "tier", "body", "ward_no")


def load(path):
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def tokens(name):
    return set(re.findall(r"[a-z]{3,}", str(name).lower()))


def overlap(a, b):
    """Share of one name's tokens found in the other, order-free."""
    ta, tb = tokens(a), tokens(b)
    return len(ta & tb) / max(1, len(ta))


def name_check(report, rows, wave, label, floor=0.8):
    """Winner names from the result files against the deposit's councillors.

    `floor` is the share of named wards that must match on at least half their
    name tokens. The 2012 scan is a surname-first phonetic transcription of
    Marathi names ("Siril Disoza" for "Cyril D'souza"), so its floor is lower
    and the mean overlap is reported rather than required.
    """
    scores = []
    low = []
    for row in rows:
        sitting = wave.get(row["ward_no"], {}).get("name", "")
        if not row["winner"] or not sitting:
            continue
        score = overlap(row["winner"], sitting)
        scores.append(score)
        if score < 0.5:
            low.append((row["ward_no"], row["winner"], sitting))
    mean = statistics.mean(scores) if scores else 0.0
    matched = sum(score >= 0.5 for score in scores)
    report.check(
        scores and matched / len(scores) >= floor,
        f"{label}: winners agree with the deposit's councillors",
        f"{matched} of {len(scores)} named wards share half their name tokens "
        f"(floor {floor:.0%}); mean overlap {mean:.2f}",
    )
    report.info(
        f"{label}: wards where the two sources name different people",
        f"{len(low)}: " + "; ".join(f"{w} {a!r} vs {b!r}" for w, a, b in low[:8]),
    )


def women_check(report, rows, year):
    women = sum(int(r["woman_reserved"]) for r in rows)
    expected = parse.WOMEN_SEATS[year]
    report.check(
        abs(women - expected) <= 1,
        f"{year}: women's seats match the statutory share (within one)",
        f"{women} reserved, statute {expected}",
    )
    if women != expected:
        report.info(
            f"{year}: women's seats differ from the statute",
            f"{women} in the source against {expected} by law; "
            "see the deposit comparison",
        )


@command("validate", state="Maharashtra")
def main():
    slices = {
        year: load(parse.DATA / f"ulb_ward_{year}.csv") for year in parse.DECLARED
    }
    if not all(slices.values()):
        sys.exit("no parsed Maharashtra data - run make maharashtra first")

    report = checks.Report("Mumbai (BMC) ward seats, 2012 and 2017 councils")

    report.section("Held Dataverse deposit")
    manifest = load(harvest.MANIFEST)
    report.check(
        len(manifest) == harvest.EXPECTED_DOCUMENTS
        and all((harvest.OUT / r["file"]).exists() for r in manifest),
        "the seven deposit files are held and listed in the manifest",
        f"{len(manifest)} of {harvest.EXPECTED_DOCUMENTS}",
    )

    for year, expected in parse.DECLARED.items():
        validation.apply(
            report,
            validation.DatasetExpectation(
                path=parse.DATA / f"ulb_ward_{year}.csv",
                state="Maharashtra",
                year=year,
                tier="ulb_ward",
                key=KEY,
                expected_rows=expected,
            ),
            ROOT,
        )

    report.section("Statute")
    for year, rows in slices.items():
        women_check(report, rows, year)
    bc_2012 = sum(r["caste_reservation"] == "BC" for r in slices["2012"])
    report.check(
        bc_2012 == 61,
        "2012: Backward Class seats are 27% of the council",
        f"{bc_2012} of 227 (27% = 61)",
    )
    wards = collections.Counter(r["winner"] != "" for r in slices["2012"])
    report.info(
        "2012: winners named by the scan transcription", f"{wards[True]} of 227"
    )

    report.section("Deposit as an independent reading")
    deposit = parse.read_tsv(parse.DEPOSIT)
    wave_2013 = parse.deposit_wave(deposit, "2013")
    agree = [
        (r["ward_no"], r["reservation_raw"], wave_2013[r["ward_no"]].get("name", ""))
        for r in slices["2012"]
        if r["ward_no"] in wave_2013
        and str(r["woman_reserved"])
        != parse.clean(wave_2013[r["ward_no"]].get("genderquota"))
    ]
    report.check(
        len(agree) <= 1,
        "2012: the sheet's reservation agrees with the deposit's flag on 226+ wards",
        f"{227 - len(agree)} of 227 agree; differ: {agree}",
    )
    name_check(report, slices["2012"], wave_2013, "2012", floor=0.8)
    name_check(
        report, slices["2017"], parse.deposit_wave(deposit, "2018"), "2017", floor=0.95
    )

    report.section("Supplemental files")
    seats_2007 = load(parse.MUMBAI / "bmc_seats_2007.csv")
    women_2007 = sum(r["woman_reserved"] == "1" for r in seats_2007)
    report.check(
        len(seats_2007) == 227 and women_2007 == parse.WOMEN_SEATS["2007"],
        "2007: 227 seats, one third reserved for women (deposit flag)",
        f"{len(seats_2007)} seats, {women_2007} reserved",
    )
    ratings = load(parse.MUMBAI / "praja_ward_ratings_2011_2018.csv")
    by_wave = collections.Counter(r["survey_year"] for r in ratings)
    report.check(
        set(by_wave) == {"2011", "2013", "2014", "2015", "2016", "2018"}
        and all(226 <= n <= 227 for n in by_wave.values()),
        "Praja ratings: six waves of 226-227 wards",
        str(dict(sorted(by_wave.items()))),
    )
    flagged = {r["survey_year"] for r in ratings if r["rating_flags"]}
    report.check(
        flagged == {"2018"},
        "Praja ratings: the inverted-satisfaction flag sits on the 2018 wave only",
        str(sorted(flagged)),
    )
    for wave, expected_sign in (("2016", 1), ("2018", -1)):
        rows = [
            r for r in ratings if r["survey_year"] == wave and r["rating_satisfaction"]
        ]
        sat = [float(r["rating_satisfaction"]) for r in rows]
        service = [
            statistics.mean(float(r[f"rating_{item}"]) for item in parse.SERVICE_ITEMS)
            for r in rows
        ]
        corr = statistics.correlation(sat, service)
        report.check(
            corr * expected_sign > 0,
            f"Praja {wave}: satisfaction runs "
            f"{'with' if expected_sign > 0 else 'against'} the service items",
            f"r = {corr:.2f}",
        )

    return report.finish()


if __name__ == "__main__":
    sys.exit(main())
