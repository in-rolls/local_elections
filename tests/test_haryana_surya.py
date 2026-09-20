"""Keep generated table structure from silently becoming source office identity."""

from local_reservations.tools.parse_haryana_surya import parse_samiti, score_rows


def payload(text):
    return {"text": text, "tokens": 100, "max_tokens": 8192}


def test_ward_comes_from_raw_cell_despite_wrong_generated_column():
    text = """<table><tr><th>Sr No</th><th>Ward</th></tr>
    <tr><td>5</td><td></td><td></td><td>NAME</td>
    <td>RELATION</td><td>S.C.</td><td>Woman</td></tr></table>"""
    rows, issues = parse_samiti(payload(text))
    assert not issues
    assert rows[0]["ward"] == 5
    assert rows[0]["body_raw"] is None
    assert rows[0]["caste_candidate"] == "SC"
    assert rows[0]["woman_candidate"] is True
    assert rows[0]["raw_cells"][1]["text"] == ""


def test_body_does_not_cross_tables_and_gp_office_is_not_samiti_member():
    text = """<table><tr><td>4</td><td>HANSI-I</td></tr>
    <tr><td>1</td><td>NAME</td><td>RELATION</td><td>General</td></tr></table>
    <table><tr><td>2</td><td>NAME</td><td>RELATION</td><td>General</td></tr>
    <tr><td>3</td><td>NAME</td><td>RELATION</td><td>Panch</td><td>General</td>
    </tr></table>"""
    rows, issues = parse_samiti(payload(text))
    assert len(rows) == 2
    assert rows[0]["body_raw"] == "HANSI-I"
    assert rows[1]["body_raw"] is None
    assert issues[0]["status"] == "row_grammar_failed"


def test_truncated_model_output_is_not_a_successful_partial_table():
    text = "<table><tr><td>1</td><td>NAME</td><td>RELATION</td><td>General</td></tr>"
    rows, issues = parse_samiti(payload(text))
    assert rows == []
    assert issues[0]["status"] == "incomplete_html_table"
    rows, issues = parse_samiti(payload(text) | {"tokens": 8192})
    assert rows == []
    assert issues[0]["status"] == "generation_limit_reached"


def test_skipped_rows_cannot_improve_a_positional_agreement_score():
    score = score_rows([], [{"ward": 5}])
    assert score["expected_rows"] == 1
    assert score["predicted_rows"] == 0
    assert "correct_ward" not in score
