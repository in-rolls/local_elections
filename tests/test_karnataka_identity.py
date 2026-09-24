"""Identity contracts for Karnataka's gram-panchayat panel."""

import collections
import csv

import pytest

from local_elections.common import canon
from local_elections.paths import ROOT
from local_elections.states.karnataka import parse


@pytest.mark.parametrize("year", parse.YEARS)
def test_gp_code_is_promoted_into_the_shared_identity(year):
    path = ROOT / "data" / "karnataka" / f"gp_head_{year}.csv"
    with path.open(encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))

    assert len(rows) == parse.DECLARED[year]
    assert all(row["gp_no"] and row["gp_no"] == row["gp_code"] for row in rows)
    keys = collections.Counter(canon.seat_identity(row) for row in rows)
    assert not {key: count for key, count in keys.items() if count > 1}
