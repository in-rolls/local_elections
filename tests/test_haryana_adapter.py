"""Haryana adapter: ward rows do not inherit the GP-head printing comparison."""

from local_elections.common.adapters.haryana import archived_pdfs, convert


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


def test_archived_pdf_is_named_by_its_archive_path(tmp_path):
    raw_dir = tmp_path / "data" / "raw" / "2000"
    raw_dir.mkdir(parents=True)
    (raw_dir / "manifest.csv").write_text(
        "district,block,saved_as,archive_path\n"
        "Kaithal,Kaithal,test.pdf,raw/gazette_archive/national/early_cycles/raw/test.pdf\n"
    )
    archived = archived_pdfs(raw_dir)
    path = tmp_path / "data" / "extracted" / "2000" / "gp_reservation.csv"
    got = convert(source_row(), "2000", "gp_head", "sarpanch", path, tmp_path, archived)
    assert got["source_path"] == "data/raw/gazette_archive/national/early_cycles/raw/test.pdf"
    got = convert(source_row(), "2022", "gp_head", "sarpanch", path, tmp_path)
    assert got["source_path"] == "data/raw/2022/test.pdf"
