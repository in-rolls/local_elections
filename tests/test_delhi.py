import shutil
from pathlib import Path

import pandas as pd
import pytest

from local_reservations.states.delhi.html import (
    case_entries,
    expand_rows,
    profile,
    winner_links,
)
from local_reservations.states.delhi.parse import official_2022

ROOT = Path(__file__).parents[1]


def test_profile_does_not_turn_unknown_fields_into_zero():
    parsed = profile("<h2>Example (Winner)</h2><h5>WARD 1-NARELA</h5>", 2012)
    assert parsed["education"] is None
    assert parsed["age"] is None
    assert parsed["pending_cases"] is None


def test_profile_separates_pending_cases_and_convictions():
    html = """<h2>Example (Winner)</h2><h5>001-S-MADIPUR</h5>
    <script>var data = [['Cases', 1]];</script>
    <h3>Cases where charges framed</h3></div><div class='w3-responsive'>
    <table><tr><td>No Cases</td></tr></table></div>
    <h3>Cases where Cognizance taken</h3><table><tr><td>No Cases</td></tr></table>
    <h3>Cases where convicted</h3><table>
    <tr><td>1</td><td>Convicted</td></tr></table>"""
    result = profile(html, 2017)
    assert result["pending_cases"] == 0
    assert result["convicted_cases"] == 1
    with pytest.raises(ValueError, match="displayed total"):
        profile(html.replace("['Cases', 1]", "['Cases', 2]"), 2017)


def test_case_entries_rejects_broken_numbering():
    html = "Cases where Pending</h3><table><tr><td>2</td></tr></table>"
    with pytest.raises(ValueError, match="consecutive"):
        case_entries(html, "Cases where Pending")


def test_static_row_decoder_preserves_winner_links():
    literal = (
        "document.write('<tr><td>1</td><td>"
        "<a href=/Delhi2022/candidate.php?candidate_id=1>Example</a></td>"
        "<td>1-NARELA</td><td>AAP</td><td>0</td><td>Graduate</td>"
        "<td>0</td><td>0</td></tr>');"
    )
    alphabet = "qzojsdnOV"
    tokens = []
    for char in literal:
        number = ord(char) + 14
        digits = ""
        while number:
            digits = alphabet[number % 5] + digits
            number //= 5
        tokens.append(digits)
    payload = "d".join(tokens) + "d"
    encoded = f'}}("{payload}",35,"{alphabet}",14,5,47))'
    decoded = expand_rows(encoded)
    assert "<td>Graduate</td>" in decoded
    rows = winner_links(encoded, 2022, "https://www.myneta.info/Delhi2022/")
    assert len(rows) == 1
    assert rows[0]["ward_number"] == "1"
    assert rows[0]["profile_url"].endswith("candidate_id=1")


def test_official_gazette_has_every_2022_ward_and_statutory_counts():
    roster = official_2022(ROOT / "data/delhi/delhi_2022.pdf")
    assert roster.reservation_raw.value_counts().to_dict() == {
        "WOMAN": 104,
        "GENERAL": 104,
        "SCW": 21,
        "SC": 21,
    }
    assert roster.assembly_id.nunique() == 68


def test_release_has_unique_elected_wards_and_preserves_missingness():
    data = pd.read_parquet(ROOT / "data/delhi/release/winners.parquet")
    assert not data.duplicated(["year", "ward_number"]).any()
    assert data.groupby("year").size().to_dict() == {2012: 272, 2017: 272, 2022: 250}
    assert data.groupby("year").source_url.count().to_dict() == {
        2012: 237,
        2017: 267,
        2022: 248,
    }
    assert (
        data.loc[data.source_url.isna(), ["education", "age", "pending_cases"]]
        .isna()
        .all()
        .all()
    )
    assert data.assembly_id.notna().all()


def test_2022_profiles_match_adr_published_education_and_case_totals():
    # ADR's 8 December 2022 report: omitted winners p. 3, cases p. 4, education p. 17.
    data = pd.read_parquet(ROOT / "data/delhi/release/winners.parquet")
    data = data[data.year.eq(2022)]
    assert set(data.loc[data.source_url.isna(), "ward_number"]) == {"162", "178"}
    assert data.education.value_counts().to_dict() == {
        "Illiterate": 2,
        "5th Pass": 12,
        "8th Pass": 25,
        "10th Pass": 31,
        "12th Pass": 58,
        "Graduate": 67,
        "Graduate Professional": 20,
        "Post Graduate": 28,
        "Doctorate": 1,
        "Others": 4,
    }
    # The report labels the four unspecified MyNeta entries as Diploma.
    assert ((data.pending_cases + data.convicted_cases) > 0).sum() == 42
    assert (data.pending_cases > 0).sum() == 40


def test_validator_rejects_a_changed_release(tmp_path):
    from local_reservations.states.delhi.validate import validate

    release = ROOT / "data/delhi/release"
    assert validate(release) == {2012: 272, 2017: 272, 2022: 250}
    shutil.copytree(release, tmp_path / "release")
    path = tmp_path / "release/winners.parquet"
    path.write_bytes(path.read_bytes() + b"corruption")
    with pytest.raises(ValueError, match="Release hash changed"):
        validate(tmp_path / "release")
