"""The Karnataka table reader, on the HTML that actually broke it.

Every case here is a page Surya really produced. Nothing is invented, because
the failures worth guarding are the ones that looked fine: a page silently
dropped, a row split in two, a category refused by a rule that was right about
a different vocabulary.
"""

from local_elections.states.karnataka import tables


def test_the_four_reservation_families_are_read():
    assert tables.reservation("ಸಾಮಾನ್ಯ") == ("NONE", "", False)
    assert tables.reservation("ಸಾಮಾನ್ಯ (ಮಹಿಳೆ)") == ("NONE", "", True)
    assert tables.reservation("ಅನುಸೂಚಿತ ಜಾತಿ (ಮಹಿಳೆ)") == ("SC", "", True)
    assert tables.reservation("ಅನುಸೂಚಿತ ಪಂಗಡ") == ("ST", "", False)


def test_backward_a_and_b_survive_the_margin_rule():
    """These differ by one character inside an identical phrase, so scored as
    one vocabulary they sit 0.07 apart and the margin rule refuses both - which
    it did, losing 93 of the first 700 rows their category."""
    assert tables.reservation('ಹಿಂದುಳಿದ "ಅ" ವರ್ಗ') == ("BC", "BC-A", False)
    assert tables.reservation("ಹಿಂದುಳಿದ “ಅ” ವರ್ಗ (ಮಹಿಳೆ)") == ("BC", "BC-A", True)
    assert tables.reservation("ಹಿಂದುಳಿದ 'ಬ' ವರ್ಗ") == ("BC", "BC-B", False)


def test_a_misread_category_still_lands_in_the_right_family():
    """Surya confuses sibilants - ಸೂ for ಕೂ, ಪಂ for ಪ್ಪಂ. The categories are a
    fixed list, which is the whole reason that is recoverable."""
    assert tables.reservation("ಅನುಕೂಚಿತ ಜಾತಿ")[0] == "SC"
    assert tables.reservation("ಅನುಸೂಚಿತ ಪ್ಪಂಗಡ (ಮಹಿಳೆ)")[0] == "ST"


def test_a_column_header_is_not_a_category():
    for header in ("ನಿಗದಿ ಪಡಿಸಿರುವ ಮೀಸಲಾತಿ ವರ್ಗ", "ಕ್ಷೇತ್ರದ ಮೀಸಲಾತಿ", "ಮೀಸಲಾತಿ/ ಮೀಸಲಿರಿಸಿದ ವರ್ಗ", "3", ""):
        assert tables.reservation(header) is None, header


def test_a_misread_party_is_recovered_and_an_ambiguous_one_is_not():
    assert tables.party("ಭಾರತೀಯ ಜನತಾ ವಕ್ಷ") == "Bharatiya Janata Party"
    assert tables.party("ಭಾರತೀಯ ರಾಷ್ಟ್ರೀಯ ಕಾಂಗ್ರೇಸ್") == "Indian National Congress"
    assert tables.party("ಪಕ್ಷೇತರ") == "Independent"
    # both parties begin with this word, so the cell does not say which
    assert tables.party("ಭಾರತೀಯ") == ""
    assert tables.party("ಪ್ರತಿನಿಧಿಸಿದ ರಾಜಕೀಯ ಪಕ್ಷದ ಹೆಸರು") == ""


HUNAGUND_P3 = """<table><tr>
<td>19</td><td>19-ಕೂಡಲಸಂಗಮ</td><td>ಹಿಂದುಳಿದ 'ಅ'</td>
<td>ಮಹಾಂತವ್ವ ಬೀಮಪ್ಪ ಯರಜೇರಿ ಸಾ:</td><td>ಭಾರತೀಯ</td></tr>
<tr><td>ವರ್ಗ (ಮಹಿಳೆ)</td><td>ಬಿಸಲದಿನ್ನಿ ತಾ:ಹುನಗುಂದ</td>
<td>ರಾಷ್ಟ್ರೀಯ ಕಾಂಗ್ರೇಸ್</td></tr></table>"""


def test_a_wrapped_row_is_one_seat_and_not_two():
    """Unmerged this is a seat with an unmatchable reservation and no party,
    plus a phantom row - and neither a row count nor a fill rate moves."""
    rows = tables.table_rows(HUNAGUND_P3)
    assert len(rows) == 1
    cells, layout = rows[0]
    assert tables.seat(cells[layout["seat"]]) == (19, "ಕೂಡಲಸಂಗಮ")
    assert tables.reservation(cells[layout["reservation"]]) == ("BC", "BC-A", True)
    assert tables.party(cells[layout["party"]]) == "Indian National Congress"
    assert "ಬಿಸಲದಿನ್ನಿ" in cells[layout["winner"]]


# A gazette page carries its own masthead as a three-column table. On
# Siruguppa page 1 those rows outnumbered the six-column data rows.
MASTHEAD_PLUS_DATA = """<table><tr><td>ಕೋ. 63</td><td>ಕುಮಾರ್</td><td>ನಂ. ೬೪</td></tr>
<tr><td>Part - 6C</td><td>Kalaburagi, Friday</td><td>No. 64</td></tr>
<tr><td>ಧಾ - 946</td><td>ಕರ್ನಾಟಕ ರಾಜ್ಯಪತ್ರ</td><td>ಭಾಗ 6ಬ</td></tr>
<tr><td>1.</td><td>ಸಿರುಗುಪ್ಪ</td><td>1-ಹಚ್ಚೂಳ್ಳಿ</td><td>ಸಾಮಾನ್ಯ</td>
<td>ಶರಣಪ್ಪ ತಂದೆ ರಾಜಶೇಖರ</td><td>ಭಾರತೀಯ ಜನತಾ ಪಕ್ಷ</td></tr>
<tr><td>2.</td><td>ಸಿರುಗುಪ್ಪ</td><td>2-ರಾವಿಹಾಳ</td><td>ಅನುಸೂಚಿತ ಜಾತಿ (ಮಹಿಳೆ)</td>
<td>ಗೌರಮ್ಮ ಗಂಡ ಬಸಪ್ಪ</td><td>ಭಾರತೀಯ ರಾಷ್ಟ್ರೀಯ ಕಾಂಗ್ರೆಸ್</td></tr></table>"""


def test_a_masthead_table_does_not_swallow_the_page():
    """The bug this guards cost Siruguppa its first four seats. The plain mode
    of the row widths was 3, no layout matched it, and the whole page - data
    rows included - was discarded without a word."""
    rows = tables.table_rows(MASTHEAD_PLUS_DATA)
    assert len(rows) == 2
    seats = [tables.seat(c[la["seat"]])[0] for c, la in rows]
    assert seats == [1, 2]


def test_a_page_of_something_else_is_refused():
    """looks_right is the check on a mapping that is otherwise positional."""
    not_a_result_table = """<table>
    <tr><td>1</td><td>ರಾಮ</td><td>ಸೀತಾ</td><td>ಲಕ್ಷ್ಮಣ</td><td>ಭರತ</td></tr>
    <tr><td>2</td><td>ಗಂಗಾ</td><td>ಯಮುನಾ</td><td>ಸರಸ್ವತಿ</td><td>ಕಾವೇರಿ</td></tr>
    </table>"""
    assert tables.table_rows(not_a_result_table) == []


def test_a_table_repeated_by_the_model_is_one_set_of_seats():
    """Siruguppa's repaired first page came back as seats 1,2,3,1,2,3."""
    rows = [(1, "a"), (2, "b"), (3, "c"), (1, "a"), (2, "b"), (3, "c")]
    kept, conflicts = tables.dedupe(rows, key=lambda r: r[0])
    assert [r[0] for r in kept] == [1, 2, 3]
    assert conflicts == []


def test_two_readings_that_disagree_are_a_finding_not_a_duplicate():
    rows = [(1, "ಗೌರಮ್ಮ"), (1, "ಗೌರವ್ವ")]
    kept, conflicts = tables.dedupe(rows, key=lambda r: r[0])
    assert len(kept) == 1
    assert len(conflicts) == 1, "a disagreement was silently dropped"
