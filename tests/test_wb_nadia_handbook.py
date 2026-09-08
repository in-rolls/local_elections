"""Source regression checks for the Nadia full office synopsis."""

import json
from collections import Counter
from copy import deepcopy

import pyarrow.parquet as pq
import pytest

from local_reservations.states.wb import parse_nadia_handbook as nadia


@pytest.fixture(scope="module")
def native():
    return json.loads(nadia.NATIVE.read_text())


@pytest.fixture(scope="module")
def offices(native):
    rows = []
    for page in native["pages"][57:67]:
        for table in page["tables"]:
            rows.extend(
                parsed
                for cells in table["rows"]
                if (parsed := nadia.office_row(cells, page["page"], {}))
            )
    return rows


def test_complete_office_serials_and_repeated_names(offices):
    assert len(offices) == 374
    for tier in ["gp_head", "gp_deputy_head"]:
        rows = [row for row in offices if row["tier"] == tier]
        assert Counter(row["source_gp_serial"] for row in rows) == Counter(
            range(1, 188)
        )
        debagram = [row for row in rows if row["gram_panchayat"] == "Debagram"]
        assert {row["source_gp_serial"] for row in debagram} == {48, 159}
        assert len({row["source_gp_key"] for row in debagram}) == 2


def test_blank_printed_head_status_is_not_unreserved(offices):
    rows = {row["tier"]: row for row in offices if row["source_gp_serial"] == 123}
    assert rows["gp_head"]["gram_panchayat"] == "Taldaha Majdia"
    assert rows["gp_head"]["caste_reservation"] is None
    assert rows["gp_head"]["woman_reserved"] is None
    assert rows["gp_deputy_head"]["caste_reservation"] == "SC"
    assert rows["gp_deputy_head"]["woman_reserved"] == 0


@pytest.mark.parametrize(
    ("code", "caste", "woman"),
    [("UR", "UR", 0), ("Women", "UR", 1), ("OBCW", "OBC", 1), ("ST", "ST", 0)],
)
def test_explicit_full_table_category_axes(code, caste, woman):
    row = nadia.office_row(["1", None, "Example", "", code, None], 63, {})
    assert (row["caste_reservation"], row["woman_reserved"]) == (caste, woman)
    assert row["tier"] == "gp_deputy_head"


def test_conflicting_statuses_abstain():
    row = nadia.office_row(["1", "Example", "SC", "UR"], 58, {})
    assert row["reservation"] is None
    assert row["caste_reservation"] is None
    assert row["woman_reserved"] is None
    assert row["reservation_code_raw"] == "SC;UR"


def test_duplicate_ur_heading_is_not_a_second_record(native, offices):
    page = native["pages"][62]
    assert sum(cell == "UR" for cell in page["tables"][0]["rows"][1]) == 2
    assert len([row for row in offices if row["tier"] == "gp_deputy_head"]) == 187


def test_ward_counts_independent_of_office_status(native):
    rows = []
    for page in native["pages"][48:57]:
        for table in page["tables"]:
            rows.extend(
                parsed
                for cells in table["rows"]
                if (parsed := nadia.ward_row(cells, page["page"], {}))
            )
    assert len(rows) == 187
    assert sum(row["gram_panchayat"] is None for row in rows) == 18
    assert sum(row["constituencies_2013"] for row in rows) == 3244
    assert sum(row["seats_2013"] for row in rows) == 3246
    double = [row for row in rows if row["double_seated_constituencies_2013"]]
    assert {row["gram_panchayat"] for row in double} == {
        "Hanspukuria",
        "Birpur-I",
    }
    hanspukuria = next(row for row in double if row["gram_panchayat"] == "Hanspukuria")
    assert hanspukuria["seats_2013"] == 15
    assert hanspukuria["st_women_seats"] is None
    assert "woman_reserved" not in hanspukuria


def test_source_control_detects_disagreement_and_missingness():
    control = [{"field": "seats_2013", "printed_value": 15}]
    assert (
        nadia.compare_counts([{"seats_2013": 14}], control)[0]["status"] == "mismatch"
    )
    assert (
        nadia.compare_counts([{"seats_2013": 15}, {"seats_2013": None}], control)[0][
            "status"
        ]
        == "incomplete"
    )


def test_source_heldout_visual_gold(offices):
    gold = json.loads((nadia.OUT / "visual_review.json").read_text())
    by_key = {(row["tier"], row["source_gp_serial"]): row for row in offices}
    for mark in gold["rows"]:
        row = by_key[mark["tier"], mark["serial"]]
        assert row["gram_panchayat"] == mark["name_printed"]
        assert row["reservation_code_raw"] == mark["code_printed"]


def test_emitted_provenance_page_audit_and_roundtrip():
    rows = [
        json.loads(line)
        for line in (nadia.OUT / "office_reservations.jsonl").read_text().splitlines()
    ]
    assert pq.read_table(nadia.OUT / "office_reservations.parquet").to_pylist() == rows
    assert len({row["row_id"] for row in rows}) == 374
    assert all(row["source_sha256"] == nadia.SHA for row in rows)
    assert all(len(json.loads(row["source_bbox"])) == 4 for row in rows)
    assert all(
        row["review_status"] == "full_source_visual_review_single_assistant"
        and row["visual_review_sha256"] == nadia.OFFICE_AUDIT_SHA
        and "name_not_individually_visually_verified" not in row["quality_flags"]
        for row in rows
    )
    pages = json.loads((nadia.OUT / "page_audit.json").read_text())
    assert [page["source_page"] for page in pages] == list(range(1, 153))
    assert pages[67]["status"] == "native_evidence_only_not_semantically_parsed"
    report = json.loads((nadia.OUT / "parse_report.json").read_text())
    assert report["office_visual_review"]["validated_rows"] == 374
    assert report["office_visual_review"]["sha256"] == nadia.OFFICE_AUDIT_SHA
    assert all(
        item["status"] in {"matches", "incomplete"}
        for item in report["ward_source_checks"]
    )


@pytest.fixture
def emitted_offices():
    return [
        json.loads(line)
        for line in (nadia.OUT / "office_reservations.jsonl").read_text().splitlines()
    ]


def test_full_audit_promotes_status_without_changing_native_values(emitted_offices):
    before = deepcopy(emitted_offices)
    report = nadia.apply_office_visual_audit(emitted_offices)
    assert report["validated_rows"] == 374
    assert report["summary"]["total_printed_fields_reviewed"] == 1122
    for original, reviewed in zip(before, emitted_offices, strict=True):
        assert reviewed["review_status"] == "full_source_visual_review_single_assistant"
        assert (
            "name_not_individually_visually_verified" not in reviewed["quality_flags"]
        )
        assert "block_unstated" in reviewed["quality_flags"]
        for field in [
            "name_raw",
            "raw_cells",
            "gram_panchayat",
            "reservation_code_raw",
            "reservation",
            "caste_reservation",
            "woman_reserved",
            "source_gp_key",
        ]:
            assert reviewed[field] == original[field]
    blank = next(
        row
        for row in emitted_offices
        if row["office"] == "pradhan" and row["source_gp_serial"] == 123
    )
    assert "category_blank" in blank["quality_flags"]
    assert blank["reservation"] is None
    assert blank["caste_reservation"] is None
    assert blank["woman_reserved"] is None


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("source_sha256", "changed"),
        ("source_path", "different.pdf"),
        ("row_id", "different-row"),
        ("source_page", 59),
        ("source_gp_serial", 2),
        ("source_bbox", "[0, 0, 1, 1]"),
        ("gram_panchayat", "Different GP"),
        ("name_raw", "Different native reading"),
        ("reservation_code_raw", "UR"),
        ("woman_reserved", 1),
    ],
)
def test_stale_row_evidence_cannot_receive_full_audit_status(
    emitted_offices, field, value
):
    for row in emitted_offices:
        row["review_status"] = "native_extracted_review_stage"
    emitted_offices[-1][field] = value
    before = deepcopy(emitted_offices)
    with pytest.raises(ValueError, match="Nadia office audit"):
        nadia.apply_office_visual_audit(emitted_offices)
    assert emitted_offices == before


@pytest.mark.parametrize("duplicate", [False, True])
def test_full_audit_requires_exact_row_coverage(emitted_offices, duplicate):
    if duplicate:
        emitted_offices.append(deepcopy(emitted_offices[0]))
    else:
        emitted_offices.pop()
    with pytest.raises(ValueError, match="coverage"):
        nadia.apply_office_visual_audit(emitted_offices)


def test_full_audit_rejects_modified_evidence_file(emitted_offices, tmp_path):
    changed = tmp_path / "audit.json"
    changed.write_bytes(nadia.OFFICE_AUDIT.read_bytes() + b"\n")
    with pytest.raises(ValueError, match="Frozen Nadia"):
        nadia.apply_office_visual_audit(emitted_offices, changed)
