"""Contracts for source-specific data expectations."""

from pathlib import Path

import pyarrow.parquet as pq

from local_elections.common import datasets, dictionary, expectations


def generated_values(column):
    """Values actually present in parsed and pooled release artifacts."""
    values = {
        str(row.get(column) or "").strip()
        for _, rows in datasets.parsed()
        for row in rows
        if str(row.get(column) or "").strip()
    }
    for path in Path("data/master").glob("master_*.parquet"):
        if (
            path.name == "master_extras.parquet"
            or column not in pq.read_schema(path).names
        ):
            continue
        values.update(
            str(value).strip()
            for value in pq.read_table(path, columns=[column])[column].to_pylist()
            if value is not None and str(value).strip()
        )
    return values


def test_declared_enums_cover_generated_values():
    for column in ("listing_scope", "winner_basis", "count_basis"):
        assert generated_values(column) <= set(dictionary.BY_NAME[column]["allowed"])


def test_declared_source_blanks_are_information_not_warnings():
    rows = [
        {
            "state": "Assam",
            "year": "2025",
            "tier": "gp_ward",
            "ward_name": "",
        }
        for _ in range(4)
    ]
    rows.append({**rows[0], "ward_name": "Majirgaon"})
    findings = expectations.Findings()
    expectations.check_column(
        findings,
        expectations.DATA / "assam" / "gp_ward_reservation_2025.csv",
        rows,
        "ward_name",
        [(rows[-1], "Majirgaon")],
    )
    assert len(findings.rows) == 1
    assert findings.rows[0]["severity"] == "info"
    assert "Charaideo numbers wards" in findings.rows[0]["rule"]


def test_perfect_reservation_match_score_is_valid():
    row = {"reservation_match_score": "1"}
    findings = expectations.Findings()
    expectations.check_column(
        findings,
        expectations.DATA / "gujarat" / "fixture.csv",
        [row],
        "reservation_match_score",
        [(row, "1")],
    )
    assert not findings.rows
