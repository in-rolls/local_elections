import pandas as pd

from local_elections.states.wb import reservation_coverage as coverage


def write_rows(tmp_path, folder, filename, rows):
    directory = tmp_path / folder
    directory.mkdir()
    pd.DataFrame(rows).to_csv(directory / filename, index=False)


def test_deputy_tier_adapter_preserves_source_label(tmp_path, monkeypatch):
    monkeypatch.setattr(coverage, "DERIVED", tmp_path)
    monkeypatch.setattr(coverage, "ROOT", tmp_path)
    write_rows(
        tmp_path,
        "alipurduar_offices",
        "office_reservations.csv",
        [
            {
                "district": "Alipurduar",
                "year": 2018,
                "tier": "gp_deputy_head",
                "source_sha256": "source-sha",
                "gram_panchayat": "Printed name",
                "reservation": "W",
                "review_status": "visually_transcribed",
            }
        ],
    )
    result = coverage.parsed_office_coverage().iloc[0]
    assert result.tier == "gp_deputy"
    assert result.source_tiers == "gp_deputy_head"
    assert result.unit == "source_gp_office_row"
    assert result.rows_with_category == 1


def test_reviewed_cells_include_blanks_and_ambiguous_names(tmp_path, monkeypatch):
    monkeypatch.setattr(coverage, "DERIVED", tmp_path)
    monkeypatch.setattr(coverage, "ROOT", tmp_path)
    shared = {
        "district": "Example",
        "election_year": 2023,
        "tier": "gp_head",
        "sha256": "source-sha",
        "stage": "final",
        "quality_flags": "positive_mentions_only",
    }
    rows = [
        {
            "name": "Readable",
            "category": "SC",
            "review_status": "visually_corrected",
            "name_review_status": "visually_read_independent_verification_pending",
        },
        {
            "name": "",
            "category": "",
            "review_status": "visually_reviewed_blank",
            "name_review_status": "not_a_named_entry",
        },
        {
            "name": "",
            "category": "women",
            "review_status": "visually_read_ambiguous_exact_name",
            "name_review_status": "unresolved_exact_name",
        },
        {
            "name": "Unreviewed OCR",
            "category": "SC",
            "review_status": "pending_cell_review",
            "name_review_status": "unreviewed_ocr",
        },
        {
            "name": "Block heading",
            "category": "",
            "review_status": "visually_identified_block_heading",
            "name_review_status": "unreviewed_ocr",
            "quality_flags": "block_heading",
        },
    ]
    write_rows(
        tmp_path,
        "office_scans",
        "row_review.csv",
        [shared | row for row in rows],
    )
    result = coverage.parsed_office_coverage().iloc[0]
    assert result.parsed_rows == 4
    assert result.rows_visually_reviewed == 3
    assert result.rows_with_visually_reviewed_resolved_name == 1
    assert result.rows_with_category == 3
    assert result.distinct_name_readings == 2
    assert result.distinct_source_gp_keys == 0
    assert result.unit == "source_cell"
