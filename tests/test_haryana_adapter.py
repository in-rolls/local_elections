"""Haryana adapter: ward rows do not inherit the GP-head printing comparison."""

from local_elections.common.adapters.haryana import convert


def source_row(**updates):
    """Return one minimal sibling-format Haryana row."""
    row = {
        "caste_reservation": "NONE",
        "woman_reserved": "0",
        "district": "Karnal",
        "block": "Indri",
        "gram_panchayat": "Test",
        "ward_no": "1",
        "winner": "Person",
        "father_husband": "Relation",
        "vacant": "0",
        "unopposed": "0",
        "reservation_raw": "Unreserved",
        "script": "latin",
        "printings_agree": "0",
        "source_pdf": "test.pdf",
    }
    row.update(updates)
    return row


def test_ward_does_not_inherit_gp_head_printing_disagreement(tmp_path):
    path = tmp_path / "ward_reservation.csv"
    path.parent.joinpath("pdfs").mkdir()
    got = convert(source_row(), "2022", "gp_ward", "ward", path, tmp_path)
    assert got["printings_agree"] == ""
    got = convert(source_row(), "2022", "gp_head", "sarpanch", path, tmp_path)
    assert got["printings_agree"] == "0"
