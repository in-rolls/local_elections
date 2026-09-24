"""Declarative dataset expectations shared by state validation commands."""

import csv
from dataclasses import dataclass

from local_elections.common import checks


@dataclass(frozen=True)
class DatasetExpectation:
    """Mechanical expectations for one state/year/tier output slice."""

    path: object
    state: str
    year: str
    tier: str
    key: tuple[str, ...]
    expected_rows: int | None = None
    minimum_rows: int | None = None


def load(path):
    """Load one committed CSV output."""
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def apply(report, expectation, root):
    """Apply the common structural, provenance, identity, and count checks."""
    rows = load(expectation.path)
    label = f"{expectation.state} {expectation.year} {expectation.tier}"
    report.section(label)
    report.check(bool(rows), "parsed rows present", str(expectation.path))
    if not rows:
        return rows

    checks.structural(
        report,
        rows,
        root,
        key=expectation.key,
        required=(
            "state",
            "year",
            "tier",
            "reservation",
            "caste_reservation",
            "woman_reserved",
        ),
    )
    checks.provenance(report, rows, root)
    report.check(
        {row["state"] for row in rows} == {expectation.state},
        "state agrees with the output slice",
        str(sorted({row["state"] for row in rows})),
    )
    report.check(
        {row["year"] for row in rows} == {expectation.year},
        "year agrees with the output slice",
        str(sorted({row["year"] for row in rows})),
    )
    report.check(
        {row["tier"] for row in rows} == {expectation.tier},
        "tier agrees with the output slice",
        str(sorted({row["tier"] for row in rows})),
    )
    if expectation.expected_rows is not None:
        report.check(
            len(rows) == expectation.expected_rows,
            "row count equals the reviewed expectation",
            f"{len(rows):,} of {expectation.expected_rows:,}",
        )
    if expectation.minimum_rows is not None:
        report.check(
            len(rows) >= expectation.minimum_rows,
            "row count does not regress below the reviewed floor",
            f"{len(rows):,} against floor {expectation.minimum_rows:,}",
        )
    return rows
