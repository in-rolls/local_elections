"""Regenerate source-table dictionary from actual published columns and nulls."""

import csv

import pyarrow.parquet as pq

DESCRIPTIONS = {
    "election_year": "General-election cohort; ward 7 in the 2006 cohort actually "
    "polled in January 2007.",
    "ward_no": "Ward identifier within the municipality and election; not a universal "
    "longitudinal key.",
    "total_candidates": "Number of contesting candidates printed for the ward in 2011.",
    "male_candidates": "Printed count of male candidates, independent of "
    "name/honorific extraction.",
    "female_candidates": "Printed count of female candidates, independent of "
    "name/honorific extraction.",
    "source_path": "Retained original PDF path relative to the local_elections "
    "repository.",
    "source_page": "One-based PDF page containing the selected row; not the printed "
    "page number.",
    "candidate_order": "One-based candidate position within the ward in the 2011 "
    "candidate list; not an electoral rank.",
    "candidate_name": "Printed candidate name with leading honorific and trailing "
    "parenthetical caste/nickname removed for linkage; not inferred "
    "or transliterated.",
    "candidate_name_raw": "Candidate name cell retaining printed honorific and "
    "parenthetical text, including the wrapped Harijan "
    "continuation.",
    "honorific_raw": "Printed Sh., Smt., Ms., or Dr.; preserved separately from "
    "personal name.",
    "candidate_sex": "Male for Sh.; Female for Smt./Ms.; null for Dr. alone. Candidate "
    "titles checked against printed ward-level gender totals.",
    "sex_basis": "printed_honorific or title_not_sex_specific; no quota-based "
    "classification.",
    "body": "Municipal institution; this collection covers the Municipal Corporation "
    "of Chandigarh.",
    "poll_date": "Actual polling date in ISO YYYY-MM-DD form; distinct from "
    "report/publication date.",
    "source_raw": "Unedited extracted source row, excluding separate continuation "
    "lines unless stated.",
    "winner_sex": "Male or Female from a separately printed sex-specific honorific; "
    "null when not measured in selected sources. Never inferred from "
    "name or reservation.",
    "winner_sex_basis": "printed_honorific or not_recorded_in_selected_source.",
    "sex_source_path": "Original PDF used to classify the elected person; null when "
    "sex unavailable.",
    "sex_source_page": "One-based PDF page containing the elected person's "
    "sex-specific honorific; null when unavailable.",
    "winner_votes": "Winner vote count; integer ballots. Null for 2021, whose selected "
    "gazette reports no votes.",
    "total_votes": "Ward total votes reported in election summary; integer ballots. "
    "Null for 2021.",
    "votes_source_path": "Original PDF containing vote counts; null where counts "
    "unavailable.",
    "votes_source_page": "One-based PDF page containing the result summary or deferred "
    "result.",
    "quality_flags": "List of documented source date, heading, spelling or "
    "deferred-election issues; empty list means none of these "
    "specified issues.",
    "reservation_raw": "Reservation label exactly as extracted from selected table.",
    "caste_reservation": "GEN (no caste reservation) or SC (Scheduled Castes); "
    "normalized from explicit reservation label.",
    "woman_reserved": "True for women-only seats (including SC women); false for seats "
    "without a women-only restriction. Does not classify winner sex.",
    "winner_name": "Name from contemporaneous winner table or notification; trailing "
    "punctuation removed. Historical spelling retained.",
    "party": "Party abbreviation normalized from printed affiliation: "
    "INC/BJP/SAD/BSP/IND/AAP.",
}


def write(out):
    with (out / "dictionary.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=["file", "column", "type", "rows", "nulls", "description"],
        )
        writer.writeheader()
        for name in (
            "candidate_counts_2011.parquet",
            "candidates_2011.parquet",
            "winners.parquet",
        ):
            table = pq.read_table(out / name)
            for field in table.schema:
                writer.writerow(
                    {
                        "file": name,
                        "column": field.name,
                        "type": str(field.type),
                        "rows": table.num_rows,
                        "nulls": table[field.name].null_count,
                        "description": DESCRIPTIONS[field.name],
                    }
                )
