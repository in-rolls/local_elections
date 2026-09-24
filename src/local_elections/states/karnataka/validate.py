"""Validate Karnataka outputs against source counts and regression floors."""

import collections
import sys

from local_elections.common import checks, validation
from local_elections.common.runlog import command
from local_elections.paths import ROOT
from local_elections.states.karnataka.parse import DECLARED

DATA = ROOT / "data" / "karnataka"


def expectations():
    specs = [
        validation.DatasetExpectation(
            path=DATA / f"gp_head_{year}.csv",
            state="Karnataka",
            year=year,
            tier="gp_head",
            key=("state", "year", "tier", "gp_no"),
            expected_rows=expected,
        )
        for year, expected in DECLARED.items()
    ]
    specs.extend(
        [
            validation.DatasetExpectation(
                path=DATA / "block_member_2016.csv",
                state="Karnataka",
                year="2016",
                tier="block_member",
                key=("state", "year", "tier", "source_pdf", "seat_no"),
                minimum_rows=3478,
            ),
            validation.DatasetExpectation(
                path=DATA / "zp_member_2016.csv",
                state="Karnataka",
                year="2016",
                tier="zp_member",
                key=("state", "year", "tier", "source_pdf", "seat_no"),
                minimum_rows=888,
            ),
        ]
    )
    return specs


def check_numbering(report, rows):
    by_document = collections.defaultdict(list)
    for row in rows:
        if row.get("seat_no", "").isdigit():
            by_document[row["source_pdf"]].append(int(row["seat_no"]))
    incomplete = []
    for document, numbers in by_document.items():
        expected = set(range(1, max(numbers) + 1))
        if set(numbers) != expected or len(numbers) != len(set(numbers)):
            incomplete.append(document)
    report.check(
        not incomplete,
        "seat numbering is contiguous within each source document",
        f"{len(incomplete)} incomplete documents",
        hard=False,
    )


@command("validate", state="Karnataka")
def main():
    report = checks.Report("Karnataka reservation and results")
    for expectation in expectations():
        rows = validation.apply(report, expectation, ROOT)
        if expectation.tier in {"block_member", "zp_member"} and rows:
            check_numbering(report, rows)
    return report.finish()


if __name__ == "__main__":
    sys.exit(main())
