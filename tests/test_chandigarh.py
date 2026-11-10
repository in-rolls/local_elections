"""Check source contradictions, sex measurement, coverage and geographic joins."""

import hashlib
import json
from collections import Counter

import pyarrow.parquet as pq
import pytest

from local_elections.states.chandigarh import panel as panel_module
from local_elections.states.chandigarh import parse


def test_contemporaneous_winner_precedes_later_by_election():
    rows = {r["ward_no"]: r for r in parse.winner_table(2006)}
    assert len(rows) == 25
    assert 7 not in rows
    assert rows[10]["winner_name"] == "Gurnam Singh"
    assert rows[10]["winner_votes"] == 3159
    assert rows[10]["poll_date"] == "2006-12-20"
    assert "Bhupinder Singh Badheri" in parse.pages(parse.REPORTS[2006])[241]
    assert all(r["winner_sex"] is None for r in rows.values())


def test_deferred_ward_retains_actual_poll_and_source_basis():
    row = parse.deferred_winner()
    assert row["election_year"] == 2006
    assert row["poll_date"] == "2007-01-14"
    assert row["ward_no"] == 7
    assert row["winner_votes"] == 2808
    assert row["total_votes"] == 8175
    assert row["caste_reservation"] == "SC"
    assert row["woman_reserved"] is False
    assert row["winner_sex"] == "Male"
    assert row["winner_sex_basis"] == "printed_honorific"


def test_all_candidates_reconcile_to_printed_gender_totals():
    candidates, controls = parse.candidates_2011()
    assert len(candidates) == 152
    assert len(controls) == 26
    assert sum(r["male_candidates"] for r in controls) == 102
    assert sum(r["female_candidates"] for r in controls) == 50
    assert Counter(r["candidate_sex"] for r in candidates) == {
        "Male": 102,
        "Female": 49,
        None: 1,
    }
    unknown = [r for r in candidates if r["candidate_sex"] is None]
    assert unknown[0]["candidate_name"] == "Meena Kumari Sharma"
    assert unknown[0]["honorific_raw"] == "Dr."
    wrapped = [
        r for r in candidates if r["candidate_name"] == "Harphool Chander Kalyan"
    ]
    assert "Harijan)" in wrapped[0]["candidate_name_raw"]


def test_winner_sex_is_linked_independently_of_quota():
    candidates, _ = parse.candidates_2011()
    rows = {
        r["ward_no"]: r for r in parse.attach_sex(parse.winner_table(2011), candidates)
    }
    assert len(rows) == 26
    assert all(r["winner_sex"] is not None for r in rows.values())
    assert rows[15]["woman_reserved"] is False
    assert rows[15]["winner_sex"] == "Female"
    assert rows[15]["sex_source_page"] == 102
    assert rows[22]["winner_sex"] == "Male"
    assert "winner_candidate_spelling_alias" in rows[22]["quality_flags"]
    assert "17.12.2011" in parse.pages(parse.REPORTS[2011])[120]
    assert "2006" in parse.pages(parse.REPORTS[2011])[119].split("NAMES OF")[0]


def test_reservation_matches_independent_notices():
    prior = [*parse.winner_table(2006), parse.deferred_winner()]
    later = parse.winner_table(2011)
    assert {r["ward_no"] for r in prior if r["woman_reserved"]} == {
        2,
        5,
        6,
        8,
        15,
        17,
        19,
        20,
        26,
    }
    assert {r["ward_no"] for r in later if r["woman_reserved"]} == {
        1,
        4,
        7,
        9,
        12,
        14,
        21,
        23,
        24,
    }
    assert "2, 8, 15, 17, 19, 20 & 26" in parse.pages(parse.REPORTS[2006])[76]
    assert "1, 4, 7, 9, 14, 21 & 23" in " ".join(parse.pages(parse.REPORTS[2011]))


def test_boundary_join_preserves_every_ward_and_unknowns_fail():
    candidates, _ = parse.candidates_2011()
    before = [*parse.winner_table(2006), parse.deferred_winner()]
    after = parse.attach_sex(parse.winner_table(2011), candidates)
    panel = parse.panel_2006_2011([*before, *after])
    assert len(panel) == 26
    eligible = [r for r in panel if r["is_eligible"]]
    assert len(eligible) == 17
    assert Counter(r["reserved_woman_2006"] for r in eligible) == {True: 9, False: 8}
    assert {r["boundary_source_page"] for r in panel} == {15}
    after[0]["winner_sex"] = None
    with pytest.raises(ValueError, match="winner sex"):
        parse.panel_2006_2011([*before, *after])


def test_2021_gazette_signature_overlay_preserves_ward_seven():
    rows = {r["ward_no"]: r for r in parse.winners_2021()}
    assert set(rows) == set(range(1, 36))
    assert sum(r["woman_reserved"] for r in rows.values()) == 12
    assert rows[7]["winner_name"] == "Manoj Kumar"
    assert rows[7]["caste_reservation"] == "SC"
    assert rows[35]["winner_name"] == "Rajinder Kumar Sharma"
    assert Counter(r["party"] for r in rows.values()) == {
        "AAP": 14,
        "BJP": 12,
        "INC": 8,
        "SAD": 1,
    }
    assert all(r["winner_sex"] is None for r in rows.values())


def test_published_hashes_and_typed_nulls():
    out = parse.DATA / "release"
    manifest = json.loads((out / "manifest.json").read_text())
    for name, record in manifest["files"].items():
        path = out / name
        assert hashlib.sha256(path.read_bytes()).hexdigest() == record["sha256"]
        table = pq.read_table(path)
        assert table.num_rows == record["rows"]
        assert {f.name: str(f.type) for f in table.schema} == record["columns"]
    for name, digest in manifest["metadata"].items():
        assert hashlib.sha256((out / name).read_bytes()).hexdigest() == digest
    for row in manifest["sources"]:
        path = parse.ROOT / row["path"]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == row["sha256"]
    winners = pq.read_table(out / "winners.parquet").to_pylist()
    assert len(winners) == 87
    assert sum(r["winner_sex"] is None for r in winners) == 60


def test_unknown_reservation_and_duplicate_wards_are_rejected():
    with pytest.raises(ValueError, match="Unrecognized reservation"):
        parse.category("Unknown")
    with pytest.raises(ValueError, match="ward coverage"):
        parse.unique_wards([{"ward_no": 1}, {"ward_no": 1}], [1, 2])


def test_panel_rejects_duplicate_prior_before_dictionary_join():
    candidates, _ = parse.candidates_2011()
    before = [*parse.winner_table(2006), parse.deferred_winner()]
    after = parse.attach_sex(parse.winner_table(2011), candidates)
    with pytest.raises(ValueError, match="ward coverage"):
        parse.panel_2006_2011([*before, before[0], *after])


def test_panel_checks_notifications_rankings_and_caste_overlap():
    candidates, _ = parse.candidates_2011()
    before = [*parse.winner_table(2006), parse.deferred_winner()]
    after = parse.attach_sex(parse.winner_table(2011), candidates)
    rows = parse.panel_2006_2011([*before, *after])
    assert {r["ward_no"] for r in rows if r["population_sc_rank_2001"] <= 5} == {
        "5",
        "6",
        "7",
        "11",
        "23",
    }
    assert {
        r["population_sc_rank_2001"] for r in rows if r["ward_no"] in {"4", "18"}
    } == {15}
    strata = {}
    for row in rows:
        if row["is_eligible"]:
            strata.setdefault(row["caste_transition"], Counter())[
                row["reserved_woman_2006"]
            ] += 1
    assert strata == {
        "SC_to_NONE": {1: 2, 0: 1},
        "NONE_to_SC": {1: 2, 0: 1},
        "NONE_to_NONE": {1: 5, 0: 6},
    }
    open_woman = next(r for r in rows if r["ward_no"] == "15")
    assert open_woman["is_eligible"]
    assert open_woman["winner_woman_from_honorific_2011"] == 1
    assert open_woman["winner_honorific_raw_2011"] == "Smt."
    before[0]["woman_reserved"] = not before[0]["woman_reserved"]
    with pytest.raises(ValueError, match="reservation notification"):
        parse.panel_2006_2011([*before, *after])


def test_panel_contract_round_trip_dictionary_and_null_semantics(tmp_path):
    import csv

    import pyarrow as pa

    candidates, _ = parse.candidates_2011()
    winners = [*parse.winner_table(2006), parse.deferred_winner()]
    winners += parse.attach_sex(parse.winner_table(2011), candidates)
    rows = parse.panel_2006_2011(winners)
    result = panel_module.write(rows, tmp_path)
    path = tmp_path / "ward_panel_2006_2011.parquet"
    table = pq.read_table(path)
    panel_module.validate(table)
    assert result["sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
    assert table.schema == panel_module.SCHEMA
    assert table.schema.field("ward_no").type == pa.string()
    assert table.schema.field("winner_woman_from_honorific_2011").type == pa.int8()
    dictionary = list(csv.DictReader((tmp_path / "dictionary.csv").open()))
    assert {r["column"] for r in dictionary} == set(table.column_names)
    assert all(r["description"] and r["nulls"] == "0" for r in dictionary)
    assert (
        json.loads((tmp_path / "ward_panel_2006_2011.schema.json").read_text())
        == panel_module.CONTRACT
    )
    rows[0]["winner_woman_from_honorific_2011"] = None
    with pytest.raises(ValueError, match="requires complete"):
        panel_module.validate(pa.Table.from_pylist(rows, schema=panel_module.SCHEMA))
    rows[0]["winner_woman_from_honorific_2011"] = 2
    with pytest.raises(ValueError, match="constraint"):
        panel_module.validate(pa.Table.from_pylist(rows, schema=panel_module.SCHEMA))
