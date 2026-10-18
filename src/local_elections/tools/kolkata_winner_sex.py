"""Code the sex of Kolkata councillors, 2010 and 2015, from their names.

    uv run --with naampy python -m local_elections.tools.kolkata_winner_sex

The Lok Dhaba files OpenCity republishes leave `Gender` blank for Kolkata, so
sex here is inferred, not recorded, and the output says so in every row.

A winner on a seat reserved for women is coded female: the law allows nobody
else to stand. Every other winner is coded from the first name after titles.
naampy's first-name score decides the clear cases (0.8 or more is female, 0.35
or less male), surname markers (Begum, Khatoon, Devi, Bibi) mark women, and
every name between the thresholds was read by hand; the decisions are in
REVIEWED. Names that can belong to either sex in Bengal stay `uncertain`, so an
analysis can drop them or bound the result both ways.

Writes data/opencity/kolkata_winner_sex.csv.
"""

import csv
import re

import pandas as pd

from local_elections.paths import ROOT

DIR = ROOT / "data" / "opencity"
OUT = DIR / "kolkata_winner_sex.csv"
FILES = {
    2010: "kolkata_kmc_2010_candidates.csv",
    2015: "kolkata_kmc_2015_candidates.csv",
}
TITLES = {
    "dr",
    "smt",
    "sri",
    "shri",
    "md",
    "mohd",
    "sk",
    "ms",
    "mrs",
    "mr",
    "km",
    "adv",
    "prof",
    "haji",
}
FEMALE_SURNAMES = {"begum", "khatoon", "khatun", "devi", "bibi"}
FEMALE_AT, MALE_AT = 0.8, 0.35
# Open-seat winners whose naampy score falls between the thresholds, or whose
# name contradicts it, read by hand.
REVIEWED = {
    "DR. SHASHI PANJA": "female",
    "RATNA SUR": "female",
    "RATNA ROY MAJUMDER": "female",
    "KARUNA SENGUPTA": "female",
    "SADHANA BOSE": "female",
    # naampy reads it as male; Dola is a woman's name in Bengal
    "DOLA SARKAR": "female",
    "RAJ KISHORE GUPTA": "male",
    "SANTOSH KUMAR PATHAK": "male",
    "SANTOSH KR. PATHAK": "male",
    "DURGA PRASAD MUKHERJEE": "male",
    "SUSHANTA KUMAR GHOSH": "male",
    "SAILEN DASGUPTA": "male",
    "ANINDA KISHORE ROUTH": "male",
    "SHYAMAL BANERJEE": "male",
    "REHMAT ALAM ANSSARI": "male",
    # used for either sex in Bengal
    "HEMA RAM": "uncertain",
    "PABITRA BISWAS": "uncertain",
    "RINKU NASKAR": "uncertain",
    "SUMAN SINGH": "uncertain",
    "SASTI DAS": "uncertain",
    # a nickname for either sex; not the Dipu Das Thakur who won ward 106 in
    # the same election
    "DIPU DAS": "uncertain",
}


def words(name):
    plain = re.sub(r"\(.*?\)", " ", name.lower()).replace(".", " ")
    return [w for w in re.sub(r"[^a-z ]", " ", plain).split() if w]


def first_name(name):
    w = words(name)
    while w and w[0] in TITLES:
        w = w[1:]
    return w[0] if w else ""


def winners():
    rows = []
    for year, file in FILES.items():
        d = pd.read_csv(DIR / file)
        d.columns = d.columns.str.strip()
        for r in d[d.Position == 1].itertuples():
            rows.append(
                {
                    "year": year,
                    "ward_no": int(r.Ward_No),
                    "ward_reservation": r.Ward_Reservation,
                    "winner": r.Candidate_Name,
                }
            )
    return pd.DataFrame(rows)


def code(row):
    if "Women" in row.ward_reservation:
        return "female", "women_seat"
    if row.winner in REVIEWED:
        return REVIEWED[row.winner], "name_reviewed"
    if set(words(row.winner)) & FEMALE_SURNAMES:
        return "female", "name_marker"
    if row.naampy_score >= FEMALE_AT:
        return "female", "name_score"
    if row.naampy_score <= MALE_AT:
        return "male", "name_score"
    raise SystemExit(
        f"{row.winner} ({row.naampy_score:.2f}) needs a decision in REVIEWED"
    )


def main():
    from naampy import estimate_first_name_pattern

    w = winners()
    w["first_name"] = w.winner.map(first_name)
    est = estimate_first_name_pattern(w.first_name.tolist())
    w["naampy_score"] = est["female_label_score"].to_numpy(dtype=float).round(4)
    w[["winner_sex_from_name", "basis"]] = [code(r) for r in w.itertuples()]
    w.to_csv(OUT, index=False, quoting=csv.QUOTE_MINIMAL, lineterminator="\n")
    print(w.groupby(["year", "basis", "winner_sex_from_name"]).size().to_string())


if __name__ == "__main__":
    main()
