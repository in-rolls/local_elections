import pandas as pd
import pytest

from local_elections.states.wb import parse_birbhum as parser
from local_elections.states.wb import reservation_coverage as coverage


@pytest.fixture(scope="module")
def parsed():
    return parser.build()


def test_reservation_codebook_and_missing():
    assert parser.yes_no(1) is True
    assert parser.yes_no(2) is False
    assert parser.yes_no(float("nan")) is None
    with pytest.raises(ValueError, match="Unknown reservation code"):
        parser.yes_no(9)


def test_year_exceptions_are_preserved(parsed):
    data, _, _, _ = parsed
    current = data[data.source.eq("beaman") & data.reported_period.eq("current")]
    assert len(current) == 165
    assert current.eligible_within_source_strict.sum() == 163
    assert set(current.loc[current.raw_year.ne(1), "gp_raw"]) == {"Ayas", "Rudranagar"}
    previous = data[data.reported_period.eq("previous")]
    assert previous.election_year.isna().sum() == 3
    assert set(previous.loc[previous.election_year.isna(), "gp_raw"]) == {
        "Paikor-II",
        "Kirnahar-II",
        "Rudranagar",
    }
    assert previous.year_evidence.eq("within_1998_term_inferred").sum() == 10
    assert previous.year_evidence.eq("explicit_1998_to_2003").sum() == 152


def test_previous_incumbent_is_not_automatically_1998():
    row = {"prev_year": 888, "prev_year_888_1": 2003, "prev_year_888_2": 2005}
    assert parser.previous_cycle(row)[0] is None
    row.update(prev_year_888_1=2001, prev_year_888_2=2003)
    assert parser.previous_cycle(row) == (1998, "within_1998_term_inferred")


def test_source_contradictions_never_overwritten(parsed):
    data, audit, report, _ = parsed
    old = data[data.source.eq("cd")]
    assert len(old) == 166
    assert old.reserved_women.isna().sum() == 5
    contradictory = old[old.reserved_sc & old.reserved_st]
    assert len(contradictory) == 1
    assert contradictory.source_gp_id.iloc[0] == "150"
    assert not contradictory.eligible_within_source_strict.any()
    assert audit.any_conflict.sum() == 3
    assert report["cross_source_audit"]["name_matches"] == 104
    assert old.eligible_after_exact_name_audit.sum() == 158
    assert not data.duplicated(["source", "source_gp_id", "reported_period"]).any()


def test_parquet_round_trip_preserves_nullable_fields(parsed, tmp_path):
    data, audit, _, _ = parsed
    for name, frame in (("observations", data), ("audit", audit)):
        path = tmp_path / f"{name}.parquet"
        frame.to_parquet(path, index=False)
        pd.testing.assert_frame_equal(frame, pd.read_parquet(path))


def test_historical_district_boundaries():
    assert len(coverage.districts(2003)) == 17
    assert "Bardhaman" in coverage.districts(2003)
    assert "Purba Bardhaman" not in coverage.districts(2003)
    assert "Alipurduar" not in coverage.districts(2013)
    assert "Alipurduar" in coverage.districts(2018)
    assert len(coverage.districts(2018)) == 20
    assert len(coverage.districts(2023)) == 22


def test_results_cannot_close_reservation_gaps():
    data = coverage.build()
    assert len(data) == 168
    assert not data.duplicated(["district", "year"]).any()
    vintage = data[data.year.eq(2003)]
    for district in ("Bardhaman", "Hooghly"):
        row = vintage[vintage.district.eq(district)].iloc[0]
        assert row.head_source_status == "not_acquired"
        assert row.head_gp_parsed_source_complete == 0
    assert vintage.head_gp_parsed_strict.sum() == 163
    assert vintage.head_gp_officially_verified.sum() == 0
    assert data[data.year.eq(1993)].head_source_status.eq("not_acquired").all()


def test_judgment_evidence_keeps_unknown_categories_and_inferred_years():
    court = pd.read_json(parser.BASE / "court_observations.jsonl", lines=True)
    assert court.reserved_st.isna().all()
    bagmundi = court[court.gp_raw.eq("Bagmundi")].iloc[0]
    assert pd.isna(bagmundi.reserved_women)
    assert bagmundi.reserved_sc
    assert court.election_year_inferred.eq(2008).all()
    assert court.reservation_order_date.isna().all()
    gaps = coverage.build()
    assert gaps[gaps.year.eq(2008)].head_gp_judgment_evidence.sum() == 2
    assert gaps[gaps.year.eq(2003)].head_gp_judgment_evidence.sum() == 0


def test_office_coverage_keeps_cells_roster_keys_and_stages_distinct(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(coverage, "ROOT", tmp_path)
    monkeypatch.setattr(coverage, "DERIVED", tmp_path / "derived")
    cell_dir = tmp_path / "derived/office_native"
    cell_dir.mkdir(parents=True)
    shared = {
        "tier": "gp_head",
        "district": "Example",
        "election_year": "2018",
        "stage": "final",
        "source_sha256": "final_sha",
        "heading": "False",
        "gram_panchayat_reading": "Repeated name",
        "review_status": "needs_cell_review",
    }
    pd.DataFrame(
        [
            shared | {"category": "SC"},
            shared | {"category": "women"},
            shared | {"category": "", "heading": "True"},
            shared | {"stage": "draft", "source_sha256": "draft_sha", "category": "ST"},
        ]
    ).to_csv(cell_dir / "cell_review.csv", index=False)
    roster_dir = tmp_path / "derived/nadia_2013_handbook"
    roster_dir.mkdir()
    pd.DataFrame(
        [
            {
                "tier": "gp_head",
                "district": "Nadia",
                "year": "2013",
                "source_sha256": "handbook_sha",
                "source_gp_key": key,
                "gram_panchayat": "Same name",
                "reservation": code,
            }
            for key, code in (("1", "UR"), ("2", ""))
        ]
    ).to_csv(roster_dir / "office_reservations.csv", index=False)
    result = coverage.parsed_office_coverage().set_index("source_sha256")
    assert result.loc["final_sha", "parsed_rows"] == 2
    assert result.loc["final_sha", "distinct_name_readings"] == 1
    assert result.loc["final_sha", "distinct_source_gp_keys"] == 0
    assert result.loc["draft_sha", "rows_with_category"] == 1
    assert result.loc["handbook_sha", "distinct_source_gp_keys"] == 2
    assert result.loc["handbook_sha", "rows_with_category"] == 1
    assert result.loc["handbook_sha", "unit"] == "source_gp_office_row"
