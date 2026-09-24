"""Identity contracts for the Uttar Pradesh sibling adapter."""

import collections

import pytest

from local_elections.common import canon
from local_elections.common.adapters import uttar_pradesh
from local_elections.paths import ROOT


@pytest.fixture(scope="module")
def sibling():
    path = ROOT.parent / uttar_pradesh.REPO
    if not path.exists():
        pytest.skip("Uttar Pradesh sibling repository is not checked out")
    return path


@pytest.fixture(scope="module")
def old_panels(sibling):
    out = {}
    for year, relative in uttar_pradesh.SEAT_FILES.items():
        source = uttar_pradesh.read(
            sibling / relative,
            year,
            uttar_pradesh.DECLARED[year],
        )
        out[year] = [uttar_pradesh.seat_row(row, year, relative) for row in source]
    return out


@pytest.mark.parametrize("year", ["2005", "2010"])
def test_source_gp_code_controls_old_panel_identity(old_panels, year):
    rows = old_panels[year]
    assert all(row["gp_no"] == row["gp_code"] for row in rows)
    keys = collections.Counter(canon.seat_identity(row) for row in rows)
    collisions = {key: count for key, count in keys.items() if count > 1}
    assert sum(collisions.values()) == 2
    assert len(collisions) == 1


def test_same_cleaned_name_with_different_gp_codes_stays_distinct(old_panels):
    rows = [
        row
        for row in old_panels["2005"]
        if row["district"] == "अम्बेडकरनगर"
        and row["block"] == "अकबरपुर"
        and row["gram_panchayat"] == "सुल्तानपुर"
    ]
    assert len(rows) == 2
    assert {row["gp_no"] for row in rows} == {"186", "40"}
    assert len({canon.seat_identity(row) for row in rows}) == 2
