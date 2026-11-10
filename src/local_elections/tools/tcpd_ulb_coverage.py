"""Verify retained TCPD-CASI sources and summarize their usable field coverage.

The source CSV remains unchanged, including NOTA, duplicate records, blank
years, by-elections and multiple seats within a ward. This produces an inventory,
not a linked election panel or an additional input to the pooled master.
"""

import argparse
import csv
import hashlib
import json

import pandas as pd

from local_elections.common.runlog import command
from local_elections.paths import ROOT

DIRECTORY = ROOT / "data/reference/tcpd"
SOURCE = "tcpd_casi_ulb_v1.1.csv"
GROUPS = ["State_Name", "Year", "LB_Type"]
REQUIRED = [
    *GROUPS,
    "District",
    "LB_Name",
    "LB_Code",
    "Ward_No",
    "Seat",
    "Poll",
    "Candidate_Name",
    "Gender",
    "Ward_Reservation",
    "Position",
]


def verify_sources(directory):
    with (directory / "manifest.csv").open(newline="", encoding="utf-8") as stream:
        for row in csv.DictReader(stream):
            data = (directory / row["file"]).read_bytes()
            sha256 = hashlib.sha256(data).hexdigest()
            blob = hashlib.sha1(
                b"blob " + str(len(data)).encode() + b"\0" + data
            ).hexdigest()
            if (
                len(data) != int(row["bytes"])
                or sha256 != row["sha256"]
                or blob != row["git_blob"]
            ):
                raise ValueError(f"Changed TCPD source: {row['file']}")


def summarize(data):
    missing = set(REQUIRED) - set(data.columns)
    if missing:
        raise ValueError(f"Missing TCPD columns: {sorted(missing)}")
    original_columns = list(data.columns)
    d = data.copy()
    name = d["Candidate_Name"].str.strip()
    d["nota_rows"] = name.str.upper().eq("NOTA")
    d["candidate_rows"] = name.ne("") & ~d["nota_rows"]
    gender = d["Gender"].str.strip()
    d["gender_recorded"] = d["candidate_rows"] & gender.isin(
        ["Female", "Male", "Third Gender"]
    )
    d["reservation_recorded"] = d["candidate_rows"] & d[
        "Ward_Reservation"
    ].str.strip().ne("")
    d["winner_rows"] = d["candidate_rows"] & d["Position"].str.strip().eq("1")
    d["winner_gender_recorded"] = d["winner_rows"] & d["gender_recorded"]
    d["winner_reservation_recorded"] = d["winner_rows"] & d["reservation_recorded"]
    d["duplicate_rows"] = data.duplicated(keep="first")
    counts = [
        "candidate_rows",
        "nota_rows",
        "gender_recorded",
        "reservation_recorded",
        "winner_rows",
        "winner_gender_recorded",
        "winner_reservation_recorded",
        "duplicate_rows",
    ]
    grouped = d.groupby(GROUPS, dropna=False, sort=True)
    coverage = grouped[counts].sum().join(grouped.size().rename("source_rows"))
    coverage = coverage.reset_index()[[*GROUPS, "source_rows", *counts]]
    profile = {
        "source_rows": len(data),
        "source_columns": original_columns,
        "states": sorted(data["State_Name"].unique().tolist()),
        "missing_year_rows": int(data["Year"].str.strip().eq("").sum()),
        "exact_duplicate_rows_beyond_first": int(d["duplicate_rows"].sum()),
        "nota_rows": int(d["nota_rows"].sum()),
        "unknown_gender_labels": sorted(
            set(gender) - {"", "Male", "Female", "Third Gender"}
        ),
        "source_sha256": None,
    }
    return coverage, profile


def build(directory=DIRECTORY):
    verify_sources(directory)
    path = directory / SOURCE
    data = pd.read_csv(path, dtype=str, keep_default_na=False)
    coverage, profile = summarize(data)
    profile["source_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    coverage.to_csv(directory / "coverage.csv", index=False)
    (directory / "profile.json").write_text(
        json.dumps(profile, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return coverage, profile


@command("process", artifact="tcpd_ulb_coverage")
def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    build()


if __name__ == "__main__":
    main()
