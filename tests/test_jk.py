import collections
import csv

from local_elections.common import canon
from local_elections.states.jk import extract_2010, extract_2016, parse


def page(source_pdf, table):
    return {
        "schema_version": 1,
        "source_path": f"data/jk/2010/{source_pdf}",
        "source_pdf": source_pdf,
        "source_sha256": "test",
        "source_page": 1,
        "page_text": "BLOCK DUDU DISTRICT UDHAMPUR",
        "tables": [table],
    }


def test_four_column_rows_keep_blank_open_seats(monkeypatch):
    def no_pdf_access(*args, **kwargs):
        raise AssertionError("the parser crossed the extraction boundary")

    monkeypatch.setattr(parse.pdfplumber, "open", no_pdf_access)
    records = [
        page(
            "Dudu .pdf",
            [
                ["S. No.", "Name of Pyt", "No. and Name", "Whether reserved"],
                ["1", "Babey", "I-Kanara", "Women"],
                ["", "", "II-Pacca", "ST"],
                ["", "", "III-Tilish", ""],
            ],
        )
    ]
    rows, sources, unknown = parse.parse_2010_records(records)
    assert sources == {"Dudu .pdf"}
    assert not unknown
    assert [(row["ward_no"], row["ward_name"]) for row in rows] == [
        ("I", "Kanara"),
        ("II", "Pacca"),
        ("III", "Tilish"),
    ]
    assert [row["reservation"] for row in rows] == [
        "Woman",
        "ST Other than Woman",
        "Other than Woman",
    ]
    assert rows[-1]["reservation_raw"] == ""


def test_separate_sc_st_women_columns_retain_all_combinations():
    records = [
        page(
            "Balakote.pdf",
            [
                ["S.No", "Panchayat", "No. & Name", "Reserved for", "", ""],
                ["Block", "", "", "SC", "ST", "Women"],
                ["1", "Naka Manjari", "1. Dahri", "", "", "Women"],
                ["", "", "2. Kalsyian", "", "ST", ""],
                ["", "", "3. Majari-A", "", "", ""],
                ["", "", "4. Moh. Jaba", "", "ST", "Women"],
            ],
        )
    ]
    rows, _, unknown = parse.parse_2010_records(records)
    assert not unknown
    assert [row["reservation"] for row in rows] == [
        "Woman",
        "ST Other than Woman",
        "Other than Woman",
        "ST Woman",
    ]
    assert rows[-1]["reservation_raw"] == '["", "ST", "Women"]'


def test_district_is_document_level_not_redetected_from_ward_names():
    first = page(
        "Banihal .pdf",
        [["1", "Khari", "1", "Ward one", "Women"]],
    )
    first["page_text"] = "BLOCK BANIHAL DISTRICT RAMBAN"
    second = page(
        "Banihal .pdf",
        [["2", "Budgam", "1", "Ward two", ""]],
    )
    second["source_page"] = 2
    second["page_text"] = "Budgam 1 Ward two"

    rows, _, _ = parse.parse_2010_records([first, second])
    assert [row["district"] for row in rows] == ["Ramban", "Ramban"]


def test_2010_extraction_and_document_controls_agree():
    records = extract_2010.load()
    with parse.JK.joinpath("2010_extracted", "controls.csv").open(
        encoding="utf-8"
    ) as source:
        controls = list(csv.DictReader(source))

    pages = collections.Counter(record["source_pdf"] for record in records)
    tables = collections.Counter()
    for record in records:
        tables[record["source_pdf"]] += len(record["tables"])

    assert len(controls) == len(pages) == 65
    assert sum(pages.values()) == 435
    assert sum(tables.values()) == 433
    assert {
        row["source_pdf"] for row in controls if row["status"] == "held_unparsed"
    } == set(parse.EXCLUDED_2010)
    for control in controls:
        source_pdf = control["source_pdf"]
        assert pages[source_pdf] == int(control["expected_pages"])
        assert tables[source_pdf] == int(control["expected_tables"])


def test_2010_parser_matches_document_row_controls():
    rows, sources, unknown = parse.parse_2010_records(extract_2010.load())
    with parse.JK.joinpath("2010_extracted", "controls.csv").open(
        encoding="utf-8"
    ) as source:
        controls = list(csv.DictReader(source))
    expected = {
        row["source_pdf"]: int(row["expected_rows"])
        for row in controls
        if row["expected_rows"]
    }
    actual = collections.Counter(row["source_pdf"] for row in rows)
    districts = collections.defaultdict(set)
    for row in rows:
        districts[row["source_pdf"]].add(row["district"])

    assert not unknown
    assert sources == set(expected)
    assert actual == expected
    for control in controls:
        if control["status"] == "parsed":
            assert districts[control["source_pdf"]] == {control["expected_district"]}
    assert len(rows) == 13016


def test_2016_parser_matches_extraction_and_document_controls(monkeypatch):
    def no_pdf_access(*args, **kwargs):
        raise AssertionError("the parser crossed the extraction boundary")

    monkeypatch.setattr(parse.pdfplumber, "open", no_pdf_access)
    records = extract_2016.load()
    diagnostics = {}
    rows = parse.parse_2016_records(records, diagnostics)
    with parse.JK.joinpath("2016_extracted", "controls.csv").open(
        encoding="utf-8"
    ) as source:
        controls = list(csv.DictReader(source))

    pages = collections.Counter(record["source_pdf"] for record in records)
    tables = collections.Counter()
    for record in records:
        tables[record["source_pdf"]] += len(record["tables"])
    wards = collections.Counter(
        row["source_pdf"] for row in rows if row["tier_local"] == "ward"
    )
    heads = collections.Counter(
        row["source_pdf"] for row in rows if row["tier_local"] == "sarpanch"
    )
    districts = collections.defaultdict(set)
    for row in rows:
        districts[row["source_pdf"]].add(row["district"])

    assert len(controls) == len(pages) == 25
    assert sum(pages.values()) == sum(tables.values()) == 575
    assert len(rows) == 14063
    assert sum(wards.values()) == 12300
    assert sum(heads.values()) == 1763
    assert diagnostics["skipped_identity_rows"] == {
        "PDF Samba Distt.pdf": 24,
        "Ramban.pdf": 14,
    }
    assert diagnostics["skipped_identity_groups"] == {
        "PDF Samba Distt.pdf": 3,
        "Ramban.pdf": 4,
    }
    assert all(row["gp_no"] or row["halqa"] for row in rows)
    assert len({canon.seat_identity(row) for row in rows}) == len(rows)

    for control in controls:
        source_pdf = control["source_pdf"]
        assert pages[source_pdf] == int(control["expected_pages"])
        assert tables[source_pdf] == int(control["expected_tables"])
        assert wards[source_pdf] == int(control["expected_ward_rows"])
        assert heads[source_pdf] == int(control["expected_head_rows"])
        assert districts[source_pdf] == {control["expected_district"]}
