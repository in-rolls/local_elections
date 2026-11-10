import collections

import pyarrow.parquet as pq
import pytest

from local_elections.states.wb import kolkata


def test_dated_complete_summary_frame():
    rows = kolkata.frame(kolkata.SUMMARY.read_bytes())
    assert len(rows) == 8
    assert sum(r["count"] for r in rows) == 144
    assert next(r["count"] for r in rows if r["party"] == "10") == 114
    with pytest.raises(ValueError, match="dated Kolkata"):
        kolkata.frame(kolkata.SUMMARY.read_bytes().replace(b"18-4-2015", b"18-4-2010"))


def test_error_pages_and_missing_cells_rejected():
    with pytest.raises(ValueError, match="no winner table"):
        kolkata.parse_party(b"<html>Session expired</html>")
    payload = (kolkata.RAW / "winners_party_8.html").read_bytes()
    row = kolkata.parse_party(payload)[0]
    assert row["ward_no"] == 77
    assert row["winner_name_raw"] == "SHAMIMA REHAN KHAN"
    with pytest.raises(ValueError, match="Incomplete winner row"):
        kolkata.parse_party(payload.replace(b"SHAMIMA REHAN KHAN", b""))


def test_complete_release_matches_sources_and_preserves_unknown_sex(
    tmp_path, monkeypatch
):
    published = pq.read_table(kolkata.RELEASE / "winners.parquet")
    monkeypatch.setattr(kolkata, "RELEASE", tmp_path)
    rebuilt = kolkata.build()
    assert rebuilt.equals(published)
    rows = rebuilt.to_pylist()
    assert len(rows) == 144
    assert [r["ward_no"] for r in rows] == list(range(1, 145))
    assert all(r["winner_woman"] is None and r["woman_reserved"] is None for r in rows)
    counts = collections.Counter(r["party_raw"] for r in rows)
    assert counts["ALL INDIA TRINAMOOL CONGRESS"] == 114
    assert counts["BHARATIYA JANATA PARTY"] == 7
    assert counts["COMMUNIST PARTY OF INDIA (MARXIST)"] == 10


def test_changed_summary_rejected_before_build(tmp_path, monkeypatch):
    summary = tmp_path / "summary.html"
    summary.write_bytes(kolkata.SUMMARY.read_bytes() + b"\n")
    monkeypatch.setattr(kolkata, "SUMMARY", summary)
    with pytest.raises(ValueError, match="summary source bytes changed"):
        kolkata.build()
