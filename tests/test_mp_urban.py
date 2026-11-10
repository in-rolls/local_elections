import collections

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from local_elections.states.mp import contract, urban


def test_offline_build_preserves_sources_and_unknown_outcomes(tmp_path, monkeypatch):
    held = pq.read_table(urban.RELEASE / "winners.parquet")
    monkeypatch.setattr(urban, "RELEASE", tmp_path)
    rebuilt = urban.build()
    assert rebuilt.equals(held)
    rows = rebuilt.to_pylist()
    assert len(rows) == 170
    assert all(r["winner_woman"] is None and r["reserved_woman"] is None for r in rows)
    assert all(r["votes"] is None for r in rows)
    counts = collections.Counter(r["party"] for r in rows if r["body"] == "Bhopal")
    assert counts == {"BJP": 58, "INC": 22, "IND": 5}
    council = pq.read_table(tmp_path / "indore_council_roster.parquet").to_pylist()
    assert len(council) == 85
    assert sum(r["ward_no"] is None for r in council) == 1
    assert sum(r["member_woman_from_honorific"] is not None for r in council) == 82
    assert (
        next(r for r in council if r["ward_no"] == "44")["member_woman_from_honorific"]
        is None
    )
    assert next(r for r in council if r["ward_no"] == "58")["title_raw"] is None
    assert (
        next(r for r in council if r["ward_no"] == "83")["title_raw"]
        == "Jitendra Rathore"
    )
    assert all(
        r["source_status"] == "current_roster_not_election_winners" for r in council
    )


def test_missing_ward_rejected():
    payload = (urban.RAW / "indore_results_2022.html").read_bytes()
    with pytest.raises(ValueError, match="Incomplete or duplicated"):
        urban.parse(payload.replace(b"85.", b"84."), "Indore")


def test_wrong_vintage_and_error_page_rejected():
    payload = (urban.RAW / "indore_results_2022.html").read_bytes()
    with pytest.raises(ValueError, match="dated July 2022"):
        urban.parse(payload.replace(b"2022-07-", b"2026-07-"), "Indore")
    with pytest.raises(ValueError, match="dated July 2022"):
        urban.parse(b"<html>Service unavailable</html>", "Bhopal")


def test_changed_input_rejected_before_output(tmp_path, monkeypatch):
    source = urban.RAW / "indore_results_2022.html"
    (tmp_path / source.name).write_bytes(source.read_bytes() + b"\n")
    monkeypatch.setattr(urban, "RAW", tmp_path)
    with pytest.raises(ValueError, match="Source bytes changed"):
        urban.build()


def test_contract_rejects_wrong_types_duplicate_keys_and_invented_outcomes():
    table = pq.read_table(urban.RELEASE / "winners.parquet")
    contract.validate("winners", table)
    with pytest.raises(ValueError, match="Arrow schema"):
        contract.validate(
            "winners",
            table.set_column(
                table.schema.get_field_index("ward_no"),
                "ward_no",
                table["ward_no"].cast(pa.int64()),
            ),
        )
    with pytest.raises(ValueError, match="primary-key"):
        contract.validate("winners", pa.concat_tables([table, table.slice(0, 1)]))
    rows = table.to_pylist()
    rows[0]["winner_woman"] = 0
    with pytest.raises(ValueError, match="must remain unreported"):
        contract.validate("winners", pa.Table.from_pylist(rows, schema=urban.SCHEMA))
    rows[0]["winner_woman"] = 2
    with pytest.raises(ValueError, match="constraint"):
        contract.validate("winners", pa.Table.from_pylist(rows, schema=urban.SCHEMA))


def test_verify_rejects_tampered_table(tmp_path, monkeypatch):
    monkeypatch.setattr(urban, "RELEASE", tmp_path)
    urban.build()
    contract.verify(tmp_path)
    path = tmp_path / "winners.parquet"
    path.write_bytes(path.read_bytes() + b"changed")
    with pytest.raises(ValueError, match="Output checksum changed"):
        contract.verify(tmp_path)
