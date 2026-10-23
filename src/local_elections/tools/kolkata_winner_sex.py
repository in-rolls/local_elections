"""Code the sex of Kolkata councillors, 2010 and 2015, from their names.

    uv run --with naampy python -m local_elections.tools.kolkata_winner_sex

The Lok Dhaba files OpenCity republishes leave `Gender` blank for Kolkata, so
sex here is inferred, not recorded. The output follows the `name-sex-inference`
standard: `winner_female_probability_from_name` with its method on every row.

Every winner is coded from the name alone. A seat reserved for women says the
winner is a woman by law, but that is the seat's reservation, not the name, and
it stays in `ward_reservation` for the analysis to apply. The first name after
titles is scored by naampy: 0.8 or more is 1, 0.35 or less is 0. Surname markers
(Begum, Khatoon, Devi, Bibi) give 1. Open-seat winners between the thresholds
were read by hand; the decisions are in REVIEWED. Names that can belong to
either sex in Bengal, and women's-seat winners between the thresholds, are left
blank, so an analysis can drop them or bound the result both ways.

Women's-seat winners also check naampy here: 20 of 94 score below 0.8 and 8
below 0.35 (Javed Rafat, Ashoka Mondal; Basu Anita prints the surname first).

Writes data/reference/opencity/kolkata_winner_sex.csv.
"""

import csv
import re

import pandas as pd

from local_elections.common.runlog import command
from local_elections.paths import ROOT

DIR = ROOT / "data" / "reference" / "opencity"
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


PROBABILITY = {"female": 1.0, "male": 0.0, "uncertain": None}


def code(row, naampy):
    """The name-based probability and how it was made."""
    if row.winner in REVIEWED:
        decision = REVIEWED[row.winner]
        return PROBABILITY[decision], f"manual review: {decision}"
    if set(words(row.winner)) & FEMALE_SURNAMES:
        return 1.0, "surname marker (begum, khatoon, khatun, devi, bibi)"
    rule = f"naampy {naampy} first-name score: >= {FEMALE_AT} is 1, <= {MALE_AT} is 0"
    if row.naampy_score >= FEMALE_AT:
        return 1.0, rule
    if row.naampy_score <= MALE_AT:
        return 0.0, rule
    if "Women" in row.ward_reservation:
        return None, f"{rule}; between thresholds, not reviewed (women's seat)"
    raise SystemExit(
        f"{row.winner} ({row.naampy_score:.2f}) needs a decision in REVIEWED"
    )


@command("transform", artifact="kolkata_winner_sex")
def main():
    from importlib.metadata import version

    from naampy import estimate_first_name_pattern

    w = winners()
    w["first_name"] = w.winner.map(first_name)
    est = estimate_first_name_pattern(w.first_name.tolist())
    w["naampy_score"] = est["female_label_score"].to_numpy(dtype=float).round(4)
    coded = [code(r, version("naampy")) for r in w.itertuples()]
    w["winner_female_probability_from_name"] = [p for p, _ in coded]
    w["winner_female_probability_method"] = [m for _, m in coded]
    w.to_csv(OUT, index=False, quoting=csv.QUOTE_MINIMAL, lineterminator="\n")
    summary = w.assign(
        women_seat=w.ward_reservation.str.contains("Women"),
        p=w.winner_female_probability_from_name.astype(str),
    )
    print(summary.groupby(["year", "women_seat", "p"]).size().to_string())


if __name__ == "__main__":
    main()
