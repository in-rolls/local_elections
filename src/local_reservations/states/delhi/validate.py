"""Validate winner coverage and the independent ADR 2022 education benchmark."""

import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd

from local_reservations.common.runlog import command


def validate(release):
    for entry in json.loads((release / "manifest.json").read_text()):
        path = release / entry["path"]
        if hashlib.sha256(path.read_bytes()).hexdigest() != entry["sha256"]:
            raise ValueError(f"Release hash changed: {path}")
    d = pd.read_parquet(release / "winners.parquet")
    if d.duplicated(["year", "ward_number"]).any():
        raise ValueError("Duplicate elected ward")
    if d.groupby("year").size().to_dict() != {2012: 272, 2017: 272, 2022: 250}:
        raise ValueError("Winner universe disagrees with election seat totals")
    if d[["assembly_id", "quota", "caste_reservation"]].isna().any().any():
        raise ValueError("Missing reservation or geography")
    if not d.quota.isin([0, 1]).all():
        raise ValueError("Invalid reservation indicator")
    absent = d.source_url.isna()
    if d.loc[absent, ["education", "age", "pending_cases"]].notna().any().any():
        raise ValueError("Unlinked profile gained an outcome")
    x = d[d.year.eq(2022)]
    if set(x.loc[x.source_url.isna(), "ward_number"]) != {"162", "178"}:
        raise ValueError("Missing 2022 profiles differ from ADR report page 3")
    # ADR 8 December 2022, page 17; its Diploma label is MyNeta's Others.
    expected = {
        "Illiterate": 2,
        "5th Pass": 12,
        "8th Pass": 25,
        "10th Pass": 31,
        "12th Pass": 58,
        "Graduate": 67,
        "Graduate Professional": 20,
        "Post Graduate": 28,
        "Doctorate": 1,
        "Others": 4,
    }
    if x.education.value_counts().to_dict() != expected:
        raise ValueError("Education counts disagree with ADR report page 17")
    if ((x.pending_cases + x.convicted_cases) > 0).sum() != 42:
        raise ValueError("All-case count disagrees with ADR report page 4")
    return d.groupby("year").size().to_dict()


@command("validate", state="Delhi")
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--release", type=Path, required=True)
    print(validate(parser.parse_args().release))


if __name__ == "__main__":
    main()
