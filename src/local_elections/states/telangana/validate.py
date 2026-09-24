"""Validate Telangana's 2019 gram-panchayat output slices."""

import sys

from local_elections.common import checks, validation
from local_elections.common.runlog import command
from local_elections.paths import ROOT
from local_elections.states.telangana.parse import DECLARED, YEAR

DATA = ROOT / "data" / "telangana"


@command("validate", state="Telangana")
def main():
    report = checks.Report("Telangana gram-panchayat election, 2019")
    for tier, expected in DECLARED.items():
        key = ("state", "year", "tier", "district", "block", "gram_panchayat")
        if tier == "gp_ward":
            key += ("ward_no",)
        validation.apply(
            report,
            validation.DatasetExpectation(
                path=DATA / f"{tier}_{YEAR}.csv",
                state="Telangana",
                year=YEAR,
                tier=tier,
                key=key,
                expected_rows=expected,
            ),
            ROOT,
        )
    return report.finish()


if __name__ == "__main__":
    sys.exit(main())
