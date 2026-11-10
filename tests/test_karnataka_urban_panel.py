"""Check Bengaluru source adjudication, panel linkage, and typed handoff."""

import copy
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from local_elections.states.karnataka import urban_panel

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def rows():
    """Read the reviewed source input once for this test module."""
    return urban_panel.build_rows(ROOT)


@pytest.mark.parametrize(
    ("title", "sex", "expected", "conflict"),
    [
        ("ಶ್ರೀ", "F", None, True),
        ("ಶ್ರೀಮತಿ", "M", None, True),
        ("ಡಾ", "M", 0, False),
        ("ಕುಮಾರಿ", "F", 1, False),
    ],
)
def test_reconcile_does_not_resolve_conflicts_from_reservation(
    title,
    sex,
    expected,
    conflict,
):
    """Adjudication uses only person measurements, never treatment or names."""
    reading = urban_panel.reconcile_woman(title, sex)
    assert reading[2] == expected
    assert reading[3] is conflict
    if title == "ಡಾ":
        assert reading[0] is None


def test_duplicates_cannot_overwrite_ward_rows(rows):
    """A duplicate accompanied by a missing ward must fail before dict creation."""
    duplicated = copy.deepcopy(rows)
    duplicated[-1] = duplicated[0]
    with pytest.raises(ValueError, match="exactly one record"):
        urban_panel.unique_wards(duplicated)


def test_source_hash_changes_fail(tmp_path):
    """A changed source cannot pass simply because the file still exists."""
    source = tmp_path / "original.pdf"
    source.write_bytes(b"retained bytes")
    records = [{"source": "original.pdf", "source_sha256": urban_panel.sha256(source)}]
    urban_panel.source_check(tmp_path, records)
    source.write_bytes(b"changed bytes")
    with pytest.raises(ValueError, match="hash mismatch"):
        urban_panel.source_check(tmp_path, records)


def test_primary_assignment_and_separate_title_measurement(rows):
    """Known source disagreements retain both readings and the justified priority."""
    keyed = {r["ward_no"]: r for r in rows}
    assert keyed["5"]["reserved_woman_2010"] == 0
    assert keyed["5"]["reserved_woman_opencity_2010"] == 1
    assert keyed["4"]["reserved_woman_2015"] == 0
    assert keyed["4"]["reserved_woman_opencity_2015"] == 1
    assert keyed["16"]["reserved_caste_2015"] == "BC_B"
    assert keyed["16"]["reserved_caste_from_results_2015"] == "BC_A"
    assert keyed["112"]["winner_woman_2015"] is None
    assert keyed["112"]["winner_woman_from_honorific_2015"] == 1
    assert keyed["112"]["winner_woman_opencity_2015"] == 0
    assert keyed["197"]["winner_woman_2015"] is None
    assert keyed["132"]["winner_woman_from_honorific_2015"] is None
    assert keyed["132"]["winner_woman_2015"] == 0


def test_full_frame_and_missing_outcome_denominators(rows):
    """Missing person outcomes remain in eligibility counts for bounds."""
    audit = urban_panel.audit_rows(rows)
    assert audit["rows"] == 198
    assert audit["eligible"] == 101
    assert audit["arms"] == [
        {
            "reserved_woman_2010": 0,
            "eligible": 76,
            "observed": 76,
            "women": 3,
            "missing_wards": [],
        },
        {
            "reserved_woman_2010": 1,
            "eligible": 25,
            "observed": 24,
            "women": 0,
            "missing_wards": ["112"],
        },
    ]
    assert audit["women_reserved_counts"] == {"2010": 66, "2015": 97}
    assert audit["source_title_conflict_wards"] == ["112", "197"]


def test_parquet_preserves_missing_flags_and_string_ids(rows, tmp_path):
    """The analytical handoff preserves nulls rather than converting them to zero."""
    table = pa.Table.from_pylist(rows, schema=urban_panel.SCHEMA)
    output = tmp_path / "panel.parquet"
    pq.write_table(table, output, compression="zstd")
    recovered = pq.read_table(output)
    assert recovered.equals(table)
    assert recovered.schema.field("ward_no").type == pa.string()
    assert recovered.schema.field("reserved_woman_2010").type == pa.int8()
    assert recovered.column("winner_woman_2015").null_count == 2
    assert recovered.column("winner_woman_from_honorific_2015").null_count == 1
