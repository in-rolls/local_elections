"""Andhra Pradesh's line layouts, pinned to real gazette lines.

AP is read positionally, and the districts do not agree on the positions -
neither does Krishna with itself, whose pages 12 and 13 put the ward count on
opposite sides of the sarpanch's own cell. Every case here is a line copied out
of a gazette, because each one of these got parsed plausibly and wrongly first:

  - Anantapur's mandal and panchayat came out as the same string
  - Nellore's revenue division was glued to the front of the mandal
  - Krishna's Pinapaka was recorded "Other than Woman" when the page says UR(W),
    because "uUR(W)" failed to match and the parser took ward 1's code instead
  - Nellore lost one ward on a quarter of its records to codes like "JUR(W)"

None of those raised. They are pinned so they cannot come back quietly.
"""

from collections import Counter

import pytest

from local_elections.common import parsers
from local_elections.paths import ROOT
from local_elections.states.ap import harvest
from local_elections.states.ap.extract import parse_word_pages
from local_elections.states.ap.parse_kadapa import abstract_controls

ap = parsers.load("ap")
apply_layout, as_category = ap.apply_layout, ap.as_category
mandal_vocabulary, recover_wards = ap.mandal_vocabulary, ap.recover_wards
scan_line, split_names = ap.scan_line, ap.split_names


# ------------------------------------------------------------ damaged codes

DAMAGED = [
    ("UR(W)", "UR(W)"),
    ("uUR(W)", "UR(W)"),  # Krishna p13, a doubled leading letter
    ("JUR(W)", "UR(W)"),  # Nellore, a table rule read as a J
    ("sccw)", "SC(W)"),  # the bracket read as a c
    ("SC (G)", "SC(G)"),
    ("BC(M)", "BC(M)"),
    ("sc", "SC"),
    ("Bc(w)", "BC(W)"),
]


@pytest.mark.parametrize(("raw", "expected"), DAMAGED)
def test_recognises_a_damaged_code(raw, expected):
    assert as_category(raw) == expected


# The gender marker is bracketed three ways and two were being dropped, which
# does not blank the gender - it silently records the seat as not reserved for a
# woman. 6,422 ward rows across the three districts that mark both, and it is
# why Anantapur read 38% women against a statutory half.
MARKERS = [
    ("UR(W)", "UR(W)"),
    ("UR-W", "UR(W)"),  # Anantapur, hyphen for the bracket
    ("BC-w", "BC(W)"),
    ("URW", "UR(W)"),  # run on, no separator at all
    ("SC-G", "SC(G)"),
]


@pytest.mark.parametrize(("raw", "expected"), MARKERS)
def test_the_gender_marker_survives_every_separator(raw, expected):
    assert as_category(raw) == expected


RUN_ON_SAFE = [
    ("URW", "URW"),  # adjacent - a real run-on marker
    ("UR WARD", "UR"),  # separated by a space, so WARD is not a marker
    ("URWA", "UR"),  # a longer word cannot supply the marker either
]


@pytest.mark.parametrize(("text", "expected"), RUN_ON_SAFE)
def test_a_run_on_marker_must_be_adjacent_and_alone(text, expected):
    """The run-on form was added because Anantapur prints URW for UR(W) 1,393
    times. It must not turn "UR WARD" into a woman-reserved seat, so it is only
    read when nothing separates it from the code and no letter follows it."""
    assert ap.CATEGORY.search(text).group(0) == expected


NOT_A_CODE = ["Amancherla", "Agali", "Kunavaram", "Buchireddypalem", ""]


@pytest.mark.parametrize("raw", NOT_A_CODE)
def test_a_place_name_is_not_a_code(raw):
    """The layout test turns on this: a name after the number means Nellore's
    panchayat index, a code after it means Krishna's count-first order."""
    assert as_category(raw) is None


# ------------------------------------------------------------- line layouts


def parsed(line):
    record = scan_line(line)
    assert record is not None, line
    return apply_layout(record)


def test_krishna_sarpanch_before_count():
    """Krishna p12: mandal, panchayat, SARPANCH, count, wards."""
    row = parsed(
        "1 |Ghantasala Atchampalem UR 8 SC(W) | UR(W) | UR(W) UR UR(W) | UR UR UR"
    )
    assert row["sarpanch_raw"].strip() == "UR"
    assert row["ward_count"] == "8"
    assert len(row["ward_raws"]) == 8


def test_krishna_count_before_sarpanch():
    """Krishna p13, the same document, the other way round."""
    row = parsed("1 |G.Konduru Atkuru 8 UR(W) | UR(W) UR UR(w) sc UR sc(w) sc sc(w)")
    assert row["sarpanch_raw"].strip() == "UR(W)"
    assert row["ward_count"] == "8"
    assert len(row["ward_raws"]) == 8


def test_krishna_damaged_sarpanch_is_not_ward_ones_code():
    """The bug this cost: "uUR(W)" does not match, so the first code the
    scanner sees belongs to ward 1, and the sarpanch silently takes it."""
    row = parsed(
        "17 |G.Konduru _—|Pinapaka 10 | uUR(W)| UR | UR(W)| UR | "
        "UR(W)| SC(W)} SC sc |sccw)|sc(w)| UR"
    )
    assert row["sarpanch_raw"] == "UR(W)"
    assert row["code_repaired"] == 1
    assert row["ward_count"] == "10"


def test_nellore_index_marks_the_name_boundary():
    row = parsed(
        "41 |Nellore Nellore Rural 1 |Amancherla ST(W) 14 UR(G) | "
        "UR(G) | UR(G) |SC(W) ST(W) |ST(G) | UR(G) |SC(G) ST(W) "
        "|SC(W)"
    )
    assert row["place"] == "Nellore Nellore Rural"
    assert row["panchayat"] == "Amancherla"
    assert row["sarpanch_raw"] == "ST(W)"
    assert row["ward_count"] == "14"


def test_anantapur_has_no_boundary_in_the_line():
    """Both names are Title Case and there is no number, so the line alone
    cannot be split - split_names() does it from the record order."""
    row = parsed("2 Agali H.D.Halli UR(G)")
    assert row["place"] == "Agali H.D.Halli"
    assert row["panchayat"] == ""


def test_kurnool_serial_after_row_is_restored_from_pdf_text_order():
    lines = [
        "      KOSIGI   AGASANURU   BC   UR-W BC(W) UR-W",
        "169",
        "      KOSIGI   ARLABANDA   BC   UR UR BC-W",
        "170",
    ]
    assert list(ap._records(lines)) == [
        "169 KOSIGI AGASANURU BC UR-W BC(W) UR-W",
        "170 KOSIGI ARLABANDA BC UR UR BC-W",
    ]


def test_kurnool_complete_source_contract():
    rows = ap.parse_pdf(ROOT / "data" / "ap" / "2020_res_gp" / "knl_res_gp.pdf")
    heads = [row for row in rows if row["tier"] == "gp_head"]
    wards = [row for row in rows if row["tier"] == "gp_ward"]
    assert len(heads) == 972
    assert len(wards) == 9_987
    assert {int(row["serial"]) for row in heads} == set(range(1, 973))
    assert {row["district"] for row in rows} == {"Kurnool"}
    source_url = next(
        document.url
        for document in harvest.documents()
        if document.file == "knl_res_gp.pdf"
    )
    assert all(row["source_url"] == source_url for row in rows)


def test_kadapa_complete_source_and_errata_contract():
    rows = ap.parse_pdf(ROOT / "data" / "ap" / "2020_res_gp" / "kdp_res_gp.pdf")
    heads = [row for row in rows if row["tier"] == "gp_head"]
    wards = [row for row in rows if row["tier"] == "gp_ward"]
    controls = {row["block"]: row["gp_count"] for row in abstract_controls()}
    assert len(heads) == 807
    assert len(wards) == 7_903
    assert len(controls) == 50
    assert Counter(row["block"] for row in heads) == controls
    assert sum(row["corrected"] for row in rows) == 41
    assert (
        sum(row["corrected"] and row["reservation_raw_original"] == "" for row in rows)
        == 5
    )
    assert {row["correction_source_page"] for row in rows if row["corrected"]} == {
        56,
        57,
    }
    assert all(row["source_url"] for row in rows)


def test_kadapa_errata_keeps_both_printed_values():
    rows = ap.parse_pdf(ROOT / "data" / "ap" / "2020_res_gp" / "kdp_res_gp.pdf")
    corrected = {
        (row["block"], row["gram_panchayat"], row["tier"], row["ward_no"]): row
        for row in rows
        if row["corrected"]
    }
    gadela = corrected[("Obulavaripalli", "Gadela", "gp_head", "")]
    assert gadela["reservation_raw_original"] == "ST{W)"
    assert gadela["correction_for_raw"] == "sT(w)"
    assert gadela["correction_read_as_raw"] == "sc-w"
    assert gadela["reservation"] == "SC Woman"
    added = corrected[("Chitvel", "Chitvel", "gp_ward", 14)]
    assert added["reservation_raw_original"] == ""
    assert added["correction_for_raw"] == "-"
    assert added["correction_read_as_raw"] == "BC"
    assert added["reservation"] == "BC Other than Woman"


def test_ap_source_inventory_is_the_13_district_series():
    documents = harvest.documents()
    assert len(documents) == harvest.EXPECTED_DOCUMENTS == 13
    assert {document.district for document in documents} == set(
        harvest.DISTRICTS.values()
    )
    assert {document.file for document in documents} == {
        f"{code}_res_gp.pdf" for code in harvest.DISTRICTS
    }


def test_poppler_word_tsv_treats_quotes_as_printed_text():
    tsv = (
        "level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\t"
        "width\theight\tconf\ttext\n"
        "1\t1\t0\t0\t0\t0\t0\t0\t100\t200\t-1\t\n"
        '5\t1\t1\t1\t1\t1\t10\t20\t30\t8\t90\tprinted"quote\n'
        "5\t1\t1\t1\t1\t2\t45\t20\t20\t8\t90\tUR(W)\n"
    )
    pages = parse_word_pages(tsv)
    assert pages == [
        {
            "page": 1,
            "width": 100.0,
            "height": 200.0,
            "words": [
                {
                    "left": 10.0,
                    "top": 20.0,
                    "width": 30.0,
                    "height": 8.0,
                    "text": 'printed"quote',
                },
                {
                    "left": 45.0,
                    "top": 20.0,
                    "width": 20.0,
                    "height": 8.0,
                    "text": "UR(W)",
                },
            ],
        }
    ]


# ------------------------------------------------- learning the mandal names


def test_mandal_is_one_word_when_the_second_varies():
    names = [
        "Atmakur B.Yaleru",
        "Atmakur Goridindla",
        "Atmakur Muttala",
        "Atmakur Talupur",
    ]
    assert mandal_vocabulary(names)["atmakur"] == "Atmakur"
    assert "atmakur b.yaleru" not in mandal_vocabulary(names)


def test_mandal_is_two_words_when_every_record_repeats_both():
    names = [
        "Anantapur Rural Bandlapalli",
        "Anantapur Rural Itukalapalli",
        "Anantapur Rural Kondampalli",
        "Anantapur Rural Marur",
    ]
    assert mandal_vocabulary(names)["anantapur rural"] == "Anantapur Rural"


def test_three_hamlets_do_not_invent_a_two_word_mandal():
    """Consecutive records sharing two words look exactly like a two-word
    mandal from close up. Only the records that do *not* share the second word
    settle it, which is why the vocabulary is built over the whole document."""
    names = [
        "Pamidi Ramagiri",
        "Pamidi Ramagiri Thanda",
        "Pamidi Ramagiri X",
        "Pamidi Kothapalli",
        "Pamidi Somalapuram",
    ]
    assert mandal_vocabulary(names)["pamidi"] == "Pamidi"
    assert "pamidi ramagiri" not in mandal_vocabulary(names)


def test_split_names_uses_the_whole_document():
    records = [
        {"place": p, "panchayat": "", "mandal": ""}
        for p in [
            "Kalyandurg Garudapuram",
            "Kalyandurg Golla",
            "Kalyandurg Hulikal",
            "Agali Agali",
        ]
    ]
    split_names(records)
    assert [r["mandal"] for r in records[:3]] == ["Kalyandurg"] * 3
    assert [r["panchayat"] for r in records[:3]] == ["Garudapuram", "Golla", "Hulikal"]
    # a panchayat named after its own mandal keeps the name in both columns
    assert (records[3]["mandal"], records[3]["panchayat"]) == ("Agali", "Agali")


def test_revenue_division_is_dropped_only_when_it_spans_mandals():
    records = [
        {"place": p, "panchayat": "x", "mandal": ""}
        for p in [
            "Nellore Nellore Rural",
            "Nellore Kodavalur",
            "Nellore Podalakur",
            "Nellcre Podalakur",
            "Gudur Chillakur",
        ]
    ]
    split_names(records)
    assert [r["mandal"] for r in records] == [
        "Nellore Rural",
        "Kodavalur",
        "Podalakur",
        # a division whose own name is misread still heads a place string
        "Podalakur",
        # ...but a division seen only once is not one, so this keeps both words
        "Gudur Chillakur",
    ]


# ------------------------------------------------------- recovering a ward


def test_recovers_only_as_many_wards_as_are_declared_missing():
    region = " 8 UR(G) JUR(W) UR(W)"
    spans = [(3, 9), (17, 22)]
    assert [c for _, c in recover_wards(region, spans, 1)] == ["UR(W)"]


def test_recovers_nothing_when_more_candidates_than_are_missing():
    """More candidates than the shortfall means the shortfall is not
    understood, and guessing which to take would be worse than leaving it."""
    assert recover_wards(" JUR(W) JSC(G) JBC(W)", [], 1) == []


def test_never_reads_a_ward_out_of_a_place_name():
    """With the word boundary relaxed, "Surareddypalem" contains UR. Nothing is
    recovered from a region that is only a name."""
    assert recover_wards(" Surareddypalem Thakur", [], 3) == []


# ------------------------------------------------------- the gender-marker repair
# The gazette is a ruled grid twenty ward columns wide, and the parser reads it
# by character column: ward 6 is ward 6 because of where it sits on the line.
# So a repair that changes a cell's width moves every ward after it.


def test_a_repair_never_changes_the_width_of_a_line():
    """The bug this guards shipped for one run and every aggregate approved of
    it: 2,401 gender markers recovered, unstated rows down from 1,754 to 1,122,
    the women's share moving toward the statutory half - while Alurupadu
    quietly lost three of its eight wards, because "[URW" -> "UR(W)" is one
    character wider and slid the rest of the row left."""
    from local_elections.states.ap.ocr import apply_repairs

    line = "| [URW    | sc)     | IBC)    |"
    fixed = apply_repairs(line, {"[URW": "UR(W)", "sc)": "SC(W)", "IBC)": "BC(W)"})
    assert len(fixed) == len(line), f"{fixed!r} is not the width of {line!r}"
    assert "UR(W)" in fixed
    assert "SC(W)" in fixed
    assert "BC(W)" in fixed


def test_a_repair_with_no_room_is_declined_rather_than_shifted():
    """A cell that cannot be widened keeps its bare code and stays flagged. An
    unknown gender is recoverable later; a ward number silently shifted by one
    is not."""
    from local_elections.states.ap.ocr import apply_repairs

    tight = "a sc) b"
    assert apply_repairs(tight, {"sc)": "SC(W)"}) == tight


def test_only_a_whole_cell_is_repaired():
    """The match that builds the table is positional; str.replace is not.
    "sc)" appearing inside another token must not be rewritten."""
    from local_elections.states.ap.ocr import apply_repairs

    text = "URW)x  |URW)  "
    fixed = apply_repairs(text, {"|URW)": "UR(W)"})
    assert fixed.startswith("URW)x"), fixed
    assert "UR(W)" in fixed
