"""Source-based checks for the complete 2011 Tamil Nadu head roster."""

import collections
import csv
import json

import pyarrow.parquet as pq
import pytest

from local_reservations.states.tn import parse_heads_2011 as parser


@pytest.fixture(scope="module")
def parsed():
    pages = parser.extract_layout(parser.SOURCE)
    rows, audit = parser.parse_layout(pages, parser.digest(parser.SOURCE))
    issues = parser.serial_audit(rows)
    return rows, audit, issues


def test_full_roster_counts_and_roundtrip(parsed, tmp_path):
    rows, pages, _ = parsed
    assert len(rows) == 12524
    assert len({r["row_id"] for r in rows}) == 12524
    assert (
        len({(r["district"], r["union_key"], r["gp_name"].casefold()) for r in rows})
        == 12524
    )
    assert len({r["district"] for r in rows}) == 31
    assert len({(r["district"], r["union_key"]) for r in rows}) == 385
    assert [r["source_page"] for r in pages] == list(range(3, 154))
    assert sum(r["office_rows"] for r in pages) == len(rows)
    assert next(p for p in pages if p["source_page"] == 79)["table_columns"] == 1
    assert next(p for p in pages if p["source_page"] == 79)["office_rows"] == 35
    assert all(p["unaccounted_lines"] == 0 for p in pages)
    path = tmp_path / "roundtrip.parquet"
    import pyarrow as pa

    pq.write_table(pa.Table.from_pylist(rows), path)
    assert pq.read_table(path).to_pylist() == rows
    parser.write_csv(tmp_path / "rows.csv", rows)
    with (tmp_path / "rows.csv").open() as handle:
        reread = list(csv.DictReader(handle))
    assert [r["gp_name_raw"] for r in reread] == [r["gp_name_raw"] for r in rows]


def test_blank_category_and_printed_serial_errors_survive(parsed):
    rows, _, issues = parsed
    missing = [r for r in rows if r["reservation"] is None]
    assert len(missing) == 1
    assert missing[0]["source_page"] == 15
    assert missing[0]["gp_name"] == "Ramakrishnarajupet"
    assert missing[0]["source_serial"] == "14"
    assert missing[0]["woman_reserved"] is None
    assert missing[0]["reservation_raw"] == ""
    assert {
        (r["union_key"], tuple(r["duplicate_serials"]), tuple(r["missing_serials"]))
        for r in issues
    } == {("KAVERIPAKKAM", (23,), (22,)), ("OTTAPIDARAM", (33, 34), (49, 51))}
    assert (
        len(
            [
                r
                for r in rows
                if r["union_key"] == "KAVERIPAKKAM" and r["source_serial"] == "23"
            ]
        )
        == 2
    )


def test_displaced_cells_and_continued_union_are_recovered(parsed):
    rows, _, _ = parsed
    expected = [
        (99, "Okkarai", "SC (General)"),
        (100, "Thirumangalam", "SC (General)"),
        (100, "Athikudi", "General (Women)"),
        (127, "Thavalaikulam", "General"),
        (128, "Pillaiyarkulam", "SC (Women)"),
    ]
    for page, name, code in expected:
        row = next(r for r in rows if r["source_page"] == page and r["gp_name"] == name)
        assert row["reservation"] == code
        assert len(json.loads(row["raw_fragments"])) == 2
    union = [
        r
        for r in rows
        if r["district"] == "TIRUNELVELI" and r["union_key"] == "ALANGULAM"
    ]
    assert len(union) == 28
    assert {r["union_name_raw"] for r in union} == {"ALANKULAM", "ALANGULAM"}
    assert [int(r["source_serial"]) for r in union] == list(range(1, 29))


def test_category_counts_and_reservation_semantics(parsed):
    rows, _, _ = parsed
    assert collections.Counter(r["reservation"] for r in rows) == {
        "General": 6150,
        "General (Women)": 3090,
        "SC (General)": 1967,
        "SC (Women)": 1165,
        "ST (General)": 113,
        "ST (Women)": 38,
        None: 1,
    }
    assert all(
        r["woman_reserved"] is False for r in rows if r["reservation"] == "General"
    )
    assert parser.reservation("GenaralWomen") == ("General (Women)", "UR", True)
    assert parser.reservation("") == (None, None, None)
    with pytest.raises(ValueError, match="Unrecognized"):
        parser.reservation("not legible")
