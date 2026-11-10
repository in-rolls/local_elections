"""Check the new Chandigarh wave against dated sources and prior history."""

import csv
import json
from collections import Counter

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from local_elections.states.chandigarh import extension, parse


@pytest.fixture(scope="module")
def rows():
    return extension.build_rows()


def test_notifications_results_and_titles_are_separate(rows):
    reservations = extension.reservation_rows()
    assert {w for w, (_, woman) in reservations.items() if woman} == {
        "2",
        "4",
        "5",
        "6",
        "9",
        "12",
        "13",
        "15",
        "17",
    }
    results = extension.detailed_results()
    assert len(results) == 148
    assert sum(r["candidate"] != "NOTA" for r in results) == 122
    titles = {r["ward_no"]: r for r in extension.verified_review()}
    for row in rows:
        ward = row["ward_no"]
        winner = max(
            (r for r in results if r["ward_no"] == ward and r["candidate"] != "NOTA"),
            key=lambda r: r["votes"],
        )
        assert winner["candidate"] == row["winner_2016"]
        assert row["winner_woman_2016"] is None
        assert row["winner_woman_from_honorific_2016"] == int(
            titles[ward]["candidate_honorific_raw"] == "Smt."
        )
    assert (
        sum(r["winner_woman_from_honorific_2016"] for r in rows if r["is_eligible"])
        == 0
    )


def test_join_retains_history_and_treatment_support(rows):
    previous = pq.read_table(
        parse.DATA / "release/ward_panel_2006_2011.parquet"
    ).to_pylist()
    before = {r["ward_no"]: r for r in previous}
    assert len(rows) == len(before) == 26
    for row in rows:
        assert row["body"] == before[row["ward_no"]]["body"]
        for year in (2006, 2011):
            for field in ("reserved_woman", "reserved_caste", "source_sha256"):
                assert (
                    row[f"{field}_{year}"] == before[row["ward_no"]][f"{field}_{year}"]
                )
    assert Counter(r["reserved_woman_2011"] for r in rows if r["is_eligible"]) == {
        1: 6,
        0: 11,
    }
    assert Counter(
        r["reserved_woman_2011"] for r in rows if r["is_eligible_without_2006_quota"]
    ) == {1: 6, 0: 7}
    with pytest.raises(ValueError, match="ward coverage"):
        extension.build_rows([*previous, previous[0]])


def test_independent_title_change_cannot_enter_output(monkeypatch, tmp_path):
    with extension.REVIEW.open() as stream:
        records = list(csv.DictReader(stream))
    records[0]["candidate_honorific_raw"] = "Smt."
    path = tmp_path / "review.csv"
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=records[0])
        writer.writeheader()
        writer.writerows(records)
    monkeypatch.setattr(extension, "REVIEW", path)
    with pytest.raises(ValueError, match="honorific"):
        extension.verified_review()


def test_nulls_types_provenance_and_round_trip(rows, tmp_path):
    audit = extension.write(rows, tmp_path)
    assert audit["eligible"] == 17
    assert audit["eligible_without_2006_quota"] == 13
    table = pq.read_table(tmp_path / "ward_panel_2011_2016.parquet")
    assert table.schema.field("ward_no").type == pa.string()
    assert table.schema.field("winner_woman_2016").type == pa.int8()
    assert table["winner_woman_2016"].null_count == 26
    assert table["winner_woman_from_honorific_2016"].null_count == 0
    assert table["repoll_date_2016"].null_count == 25
    assert table.to_pylist() == rows
    contract = json.loads((tmp_path / "ward_panel_2011_2016.schema.json").read_text())
    assert {f["name"] for f in contract["fields"]} == set(table.column_names)
    manifest = json.loads((tmp_path / "ward_panel_2011_2016_manifest.json").read_text())
    for entry in manifest["sources"]:
        assert extension.digest(parse.ROOT / entry["path"]) == entry["sha256"]
    for entry in manifest["outputs"]:
        assert extension.digest(tmp_path / entry["path"]) == entry["sha256"]


def test_unknown_is_not_zero_and_eligibility_is_not_outcome(rows):
    changed = [r.copy() for r in rows]
    changed[0]["winner_woman_2016"] = 0
    with pytest.raises(ValueError, match="preserve null"):
        extension.validate(changed)
    changed = [r.copy() for r in rows]
    changed[0]["is_eligible"] = False
    with pytest.raises(ValueError, match="Eligibility"):
        extension.validate(changed)


def test_clean_source_dictionary_rebuilds_full_metadata(tmp_path):
    import shutil

    from local_elections.states.chandigarh import dictionary
    from local_elections.states.chandigarh import panel as panel_module

    release = parse.DATA / "release"
    for name in (
        "candidate_counts_2011.parquet",
        "candidates_2011.parquet",
        "winners.parquet",
    ):
        shutil.copy2(release / name, tmp_path / name)
    dictionary.write(tmp_path)
    previous = pq.read_table(release / "ward_panel_2006_2011.parquet").to_pylist()
    panel_module.write(previous, tmp_path)
    assert (tmp_path / "dictionary.csv").read_bytes() == (
        release / "dictionary.csv"
    ).read_bytes()


def test_standalone_validator_rejects_changed_published_bytes(tmp_path):
    import shutil

    from local_elections.states.chandigarh import validate as validator

    release = tmp_path / "release"
    shutil.copytree(parse.DATA / "release", release)
    assert validator.validate(release)["new_panel_wards"] == 26
    path = release / "ward_panel_2011_2016.parquet"
    path.write_bytes(path.read_bytes() + b"changed")
    with pytest.raises(ValueError, match="Published output changed"):
        validator.validate(release)
