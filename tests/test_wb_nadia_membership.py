"""Regression guards for source-faithful Nadia GP/block membership."""

import hashlib
import json
from collections import Counter

import pyarrow.parquet as pq
import pytest

from local_reservations.states.wb import parse_nadia_handbook as nadia


@pytest.fixture(scope="module")
def membership():
    return nadia.parse_membership()


def test_all_printed_lists_and_occurrences_retained(membership):
    rows, report = membership
    assert len(rows) == 186
    assert report["blocks"] == 17
    assert report["printed_constituency_occurrences"] == 47
    assert report["distinct_printed_constituency_labels"] == 46
    assert report["distinct_block_gp_pairs_case_insensitive"] == 185
    assert {row["source_page"] for row in rows} == {71, 72, 73, 74}
    assert len({row["row_id"] for row in rows}) == len(rows)
    assert all(row["record_kind"] == "gp_block_membership" for row in rows)
    assert all(
        "reservation" not in row and "source_gp_serial" not in row for row in rows
    )


def test_duplicate_zp_label_does_not_invent_missing_constituency(membership):
    rows, _ = membership
    chapra = [row for row in rows if row["zp_constituency_raw"] == "Chapra/ZP-19"]
    assert len(chapra) == 8
    assert {row["source_constituency_index"] for row in chapra} == {1, 2}
    assert all("duplicated_zp_label_printed" in row["quality_flags"] for row in chapra)
    assert not any(row["zp_number_printed"] == 20 for row in rows)


def test_duplicate_gp_and_source_omissions_are_not_repaired(membership):
    rows, _ = membership
    duplicate = [
        row
        for row in rows
        if row["gram_panchayat_printed"].casefold() == "ramnagar-barachupria-ii"
    ]
    assert len(duplicate) == 2
    assert {row["gram_panchayat_printed"] for row in duplicate} == {
        "Ramnagar-Barachupria-II",
        "Ramnagar-barachupria-II",
    }
    assert all(
        "duplicate_gp_membership_printed" in row["quality_flags"] for row in duplicate
    )
    names = {row["gram_panchayat_printed"] for row in rows}
    assert "Haringhata-I" not in names
    assert "Ramnagar-Barachupria-I" not in names
    assert {
        "Fulia Township",
        "Jugalkishore",
        "BetaiII",
        "Dhubuia-II",
        "palitbegia",
    } <= names
    assert "Betai-II" not in names


def test_same_gp_names_in_different_blocks_remain_ambiguous(membership):
    rows, report = membership
    assert report["gp_names_in_multiple_blocks"] == {
        "shyamnagar": ["Ranaghat-II", "Tehatta-I"],
        "majhergram": ["Nakashipara", "Ranaghat-II"],
        "debagram": ["Kaliganj", "Ranaghat-II"],
    }
    debagram = [row for row in rows if row["gram_panchayat_printed"] == "Debagram"]
    assert len(debagram) == 2
    assert all(
        "same_gp_name_printed_in_multiple_blocks" in row["quality_flags"]
        for row in debagram
    )


def test_frozen_audit_and_source_cell_pins_reject_stale_values(tmp_path, monkeypatch):
    audit = json.loads(nadia.MEMBERSHIP_AUDIT.read_text())
    audit["constituencies"][0]["verified_block_printed"] = "Different block"
    path = tmp_path / "changed.json"
    path.write_text(json.dumps(audit))
    with pytest.raises(ValueError, match="Frozen Nadia membership"):
        nadia.parse_membership(path)
    monkeypatch.setattr(
        nadia, "MEMBERSHIP_AUDIT_SHA", hashlib.sha256(path.read_bytes()).hexdigest()
    )
    with pytest.raises(ValueError, match="source cell or position changed"):
        nadia.parse_membership(path)


def test_membership_output_roundtrip_and_page_ledger(membership):
    rows, report = membership
    emitted = pq.read_table(nadia.OUT / "gp_block_membership.parquet").to_pylist()
    assert emitted == rows
    assert all(len(json.loads(row["source_bbox"])) == 4 for row in rows)
    assert all(row["source_sha256"] == nadia.SHA for row in rows)
    assert all(
        row["visual_review_sha256"] == nadia.MEMBERSHIP_AUDIT_SHA for row in rows
    )
    pages = json.loads((nadia.OUT / "page_audit.json").read_text())
    assert len(pages) == 152
    for page in pages[70:74]:
        assert page["status"] == "parsed_source_gp_block_membership"
        assert (
            page["gp_block_membership_rows"]
            == Counter(row["source_page"] for row in rows)[page["source_page"]]
        )
    parsed_report = json.loads((nadia.OUT / "parse_report.json").read_text())
    assert parsed_report["gp_block_membership"]["rows"] == report["rows"]
    assert parsed_report["office_rows"] == 374
