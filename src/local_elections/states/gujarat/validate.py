"""Verify Gujarat's held 2020 source series without network access."""

import collections
import sys

from local_elections.common import checks, validation
from local_elections.common import harvest as source_harvest
from local_elections.common.runlog import command
from local_elections.paths import ROOT
from local_elections.states.gujarat import controls, harvest

DATA = ROOT / "data" / "gujarat"


def validate_parsed_series(report, rows, expected, title):
    """Check one parsed Gujarat series against independent source controls."""
    report.section(title)
    by_source = collections.defaultdict(list)
    for row in rows:
        by_source[row["source_pdf"]].append(row)
    report.check(
        set(by_source) == set(expected),
        "every controlled source document is represented exactly once",
        f"{len(by_source)} of {len(expected)} documents",
    )
    row_mismatches = {}
    sequence_mismatches = []
    category_mismatches = []
    for source, category_counts in expected.items():
        held = by_source[source]
        expected_rows = sum(category_counts.values())
        if len(held) != expected_rows:
            row_mismatches[source] = (len(held), expected_rows)
        if {int(row["seat_no"]) for row in held} != set(range(1, expected_rows + 1)):
            sequence_mismatches.append(source)
        got = collections.Counter(
            (row["caste_reservation"], int(row["woman_reserved"])) for row in held
        )
        if got != collections.Counter(category_counts):
            category_mismatches.append(source)
    report.check(
        not row_mismatches,
        "every source row count agrees with its published total",
        str(row_mismatches),
    )
    report.check(
        not sequence_mismatches,
        "constituency identifiers are complete within every source",
        str(sequence_mismatches),
    )
    report.check(
        not category_mismatches,
        "every source reproduces its eight published reservation totals",
        str(category_mismatches),
    )
    report.check(
        all(row["ward_name"].strip() for row in rows),
        "every constituency has a source-script name",
    )
    minimum_match = min(float(row["reservation_match_score"]) for row in rows)
    report.check(
        minimum_match >= 0.70,
        "every OCR category matches a reviewed label at 0.70 or above",
        f"minimum {minimum_match:.3f}",
    )


@command("validate", state="Gujarat")
def main():
    report = checks.Report("Gujarat 2020 PRI source series")
    expected = {
        series["source_id"]: series["expected"] for series in harvest.SERIES.values()
    }
    rows = source_harvest.verify(harvest.MANIFEST, harvest.OUT, expected)
    counts = collections.Counter(row["source_id"] for row in rows)
    for source_id, count in expected.items():
        report.check(
            counts[source_id] == count,
            f"{source_id} document count",
            f"{counts[source_id]} of {count}",
        )
    report.check(
        {row["language"] for row in rows} == {"Gujarati"},
        "source language is recorded",
        str(sorted({row["language"] for row in rows})),
    )
    report.check(
        {row["document_format"] for row in rows} == {"encoded-text"},
        "misencoded hidden text is not classified as usable digital text",
        str(sorted({row["document_format"] for row in rows})),
    )
    report.check(
        all(row["district"].strip() and row["body"].strip() for row in rows),
        "every source manifest row records its district and body",
    )

    parsed = validation.apply(
        report,
        validation.DatasetExpectation(
            path=DATA / "zp_member_reservation_2020.csv",
            state="Gujarat",
            year="2020",
            tier="zp_member",
            key=("state", "year", "tier", "district", "body", "seat_no"),
            minimum_rows=sum(controls.DISTRICT_ROW_COUNTS.values()),
        ),
        ROOT,
    )
    if parsed:
        validate_parsed_series(
            report,
            parsed,
            controls.DISTRICT_CATEGORY_COUNTS,
            "District-panchayat rosters",
        )

    block_parsed = validation.apply(
        report,
        validation.DatasetExpectation(
            path=DATA / "block_member_reservation_2020.csv",
            state="Gujarat",
            year="2020",
            tier="block_member",
            key=("state", "year", "tier", "district", "body", "seat_no"),
            minimum_rows=sum(controls.TALUKA_ROW_COUNTS.values()),
        ),
        ROOT,
    )
    if block_parsed:
        validate_parsed_series(
            report,
            block_parsed,
            controls.TALUKA_CATEGORY_COUNTS,
            "Taluka-panchayat rosters",
        )
    return report.finish()


if __name__ == "__main__":
    sys.exit(main())
