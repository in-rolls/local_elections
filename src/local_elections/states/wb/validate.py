"""Validate West Bengal's 2018 zilla-parishad reservation roster."""

import collections
import sys

from local_elections.common import checks, validation
from local_elections.common.runlog import command
from local_elections.paths import ROOT

DATA = ROOT / "data" / "wb"
EXPECTED_ROWS = 825
EXPECTED_DISTRICTS = 20


@command("validate", state="West Bengal")
def main():
    report = checks.Report("West Bengal zilla-parishad reservation, 2018")
    rows = validation.apply(
        report,
        validation.DatasetExpectation(
            path=DATA / "zp_member_2018.csv",
            state="West Bengal",
            year="2018",
            tier="zp_member",
            key=("state", "year", "tier", "district", "seat_no"),
            expected_rows=EXPECTED_ROWS,
        ),
        ROOT,
    )
    if rows:
        by_district = collections.defaultdict(list)
        for row in rows:
            if row["seat_no"].isdigit():
                by_district[row["district"]].append(int(row["seat_no"]))
        report.check(
            len(by_district) == EXPECTED_DISTRICTS,
            "all district gazettes are represented",
            f"{len(by_district)} of {EXPECTED_DISTRICTS}",
        )
        incomplete = {
            district: numbers
            for district, numbers in by_district.items()
            if set(numbers) != set(range(1, max(numbers) + 1))
            or len(numbers) != len(set(numbers))
        }
        report.check(
            not incomplete,
            "district seat numbers are complete and unique from 1 through N",
            f"{len(incomplete)} incomplete districts",
        )
    return report.finish()


if __name__ == "__main__":
    sys.exit(main())
