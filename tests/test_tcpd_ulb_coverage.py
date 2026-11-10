import pandas as pd
import pytest

from local_elections.tools.tcpd_ulb_coverage import (
    DIRECTORY,
    REQUIRED,
    SOURCE,
    summarize,
    verify_sources,
)


def test_nota_missingness_multiple_seats_and_duplicates_are_retained():
    base = dict.fromkeys(REQUIRED, "")
    base.update(State_Name="Example", Year="2017", LB_Type="MCL", Ward_No="1")
    woman = dict(base, Candidate_Name="A", Gender="Female", Seat="A", Position="1")
    second_seat = dict(base, Candidate_Name="B", Seat="B", Position="1")
    nota = dict(base, Candidate_Name="NOTA", Seat="A", Position="2")
    unknown_year = dict(base, Candidate_Name="C", Year="", Gender="Third Gender")
    data = pd.DataFrame([woman, woman, second_seat, nota, unknown_year])
    coverage, profile = summarize(data)
    assert coverage.source_rows.sum() == 5
    assert coverage.candidate_rows.sum() == 4
    assert coverage.nota_rows.sum() == 1
    assert coverage.winner_rows.sum() == 3
    assert coverage.winner_gender_recorded.sum() == 2
    assert coverage.reservation_recorded.sum() == 0
    assert profile["missing_year_rows"] == 1
    assert profile["exact_duplicate_rows_beyond_first"] == 1
    assert "Seat" in profile["source_columns"]


def test_missing_source_fields_fail():
    with pytest.raises(ValueError, match="Missing TCPD columns"):
        summarize(pd.DataFrame({"State_Name": ["Example"]}))


def test_complete_retained_source_and_generated_coverage():
    verify_sources(DIRECTORY)
    data = pd.read_csv(DIRECTORY / SOURCE, dtype=str, keep_default_na=False)
    coverage, profile = summarize(data)
    reported = pd.read_csv(DIRECTORY / "coverage.csv", keep_default_na=False)
    reported["Year"] = reported["Year"].astype(str)
    pd.testing.assert_frame_equal(coverage, reported)
    assert len(data) == 215440
    assert len(data.columns) == 37
    assert len(profile["states"]) == 9
    assert profile["missing_year_rows"] == 2238
    assert profile["exact_duplicate_rows_beyond_first"] == 8
    assert not profile["unknown_gender_labels"]
    wb = coverage[coverage.State_Name.eq("West_Bengal")]
    assert wb.gender_recorded.sum() == 0
    assert wb.reservation_recorded.sum() > 0
