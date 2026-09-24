"""The pooled schema, and the assumptions it rests on."""

import subprocess

import pytest

from local_elections.common import master as M
from local_elections.tools import build_master

BASE = {
    "state": "Goa",
    "year": "2012",
    "tier": "gp_ward",
    "tier_local": "ward",
    "district": "North Goa",
    "block": "Bardez",
    "gram_panchayat": "Anjuna",
    "ward_no": "1",
    "caste_reservation": "NONE",
    "woman_reserved": "0",
    "reservation": "Other than Woman",
    "reservation_raw": "G",
    "script": "latin",
    "source_path": "data/goa/x.pdf",
    "source_page": "3",
}


def convert(**overrides):
    return M.to_master(
        dict(BASE, **overrides), "goa/gp_ward/2012", "local_elections", "abc123", "page"
    )


# ------------------------------------------------------------- the coalesce


def test_the_panchayat_column_records_which_term_the_source_used():
    row = convert()
    assert (row["gram_panchayat"], row["gp_term"]) == ("Anjuna", "gram_panchayat")


def test_a_halqa_lands_in_the_same_column_and_says_so():
    row = M.to_master(
        {
            **{k: v for k, v in BASE.items() if k != "gram_panchayat"},
            "halqa": "Kupwara A",
            "state": "Jammu & Kashmir",
        },
        "jk/gp_ward/2016",
        "local_elections",
        "abc123",
        "page",
    )
    assert (row["gram_panchayat"], row["gp_term"]) == ("Kupwara A", "halqa")


def test_naming_the_panchayat_twice_raises():
    """The coalesce assumes exactly one is populated. If two were it would
    silently prefer one and drop the other, and nobody would see which."""
    with pytest.raises(ValueError, match=r"\w"):
        convert(halqa="Kupwara A")


# ------------------------------------------------------------------ row ids


def test_a_row_id_is_stable_across_builds():
    assert M.row_id(convert(), 1) == M.row_id(convert(), 1)


def test_a_row_id_changes_when_the_provenance_does():
    assert M.row_id(convert(), 1) != M.row_id(convert(source_page="4"), 1)


def test_a_row_id_distinguishes_repeated_statements_of_one_seat():
    """The seat key is not unique - 5,311 rows in the corpus share one - so the
    occurrence has to be part of the identifier or two rows collapse into one."""
    row = convert()
    assert M.row_id(row, 1) != M.row_id(row, 2)


def test_a_source_table_rule_cannot_break_the_seat_key_delimiter():
    key = M.seat_key(convert(gram_panchayat="Sakra - |"))
    assert len(key.split("|")) == len(M.SEAT_FIELDS)
    assert "Sakra - %7C" in key


def test_gp_number_survives_projection_and_distinguishes_same_named_gps():
    gp_18 = convert(gp_no="18", gram_panchayat="नावाडीह")
    gp_32 = convert(gp_no="32", gram_panchayat="नावाडीह")
    assert (gp_18["gp_no"], gp_32["gp_no"]) == ("18", "32")
    assert gp_18["seat_key"] != gp_32["seat_key"]
    assert convert(gp_no="14K")["gp_no"] == "14K"


# ------------------------------------------------------------------- scope


def test_an_urban_seat_is_not_pooled():
    """Kerala mixes urban and rural rows, so scope is enforced per row."""
    assert convert(tier="ulb_ward") is None
    assert convert(tier="gp_ward") is not None


def test_generated_outputs_do_not_advance_local_source_commit(tmp_path):
    subprocess.run(["git", "init", "-q", tmp_path], check=True)
    subprocess.run(
        ["git", "-C", tmp_path, "config", "user.email", "test@example.com"],
        check=True,
    )
    subprocess.run(["git", "-C", tmp_path, "config", "user.name", "Test"], check=True)

    source = tmp_path / "src" / "parser.py"
    stats = tmp_path / "data" / "stats" / "slice_checks.csv"
    master = tmp_path / "data" / "master" / "state.parquet"
    report = tmp_path / "data" / "expectations_report.csv"
    state_readme = tmp_path / "data" / "assam" / "readme.md"
    for path in (source, stats, master, report, state_readme):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("first\n", encoding="utf-8")
    subprocess.run(["git", "-C", tmp_path, "add", "."], check=True)
    subprocess.run(["git", "-C", tmp_path, "commit", "-qm", "source"], check=True)
    expected = subprocess.run(
        ["git", "-C", tmp_path, "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()[:12]

    for path in (stats, master, report, state_readme):
        path.write_text("second\n", encoding="utf-8")
    subprocess.run(["git", "-C", tmp_path, "add", "."], check=True)
    subprocess.run(["git", "-C", tmp_path, "commit", "-qm", "generated"], check=True)

    assert build_master.git_commit(tmp_path, build_master.LOCAL_INPUTS) == (
        expected,
        False,
    )


# ------------------------------------------------------------------- caste


def test_the_local_caste_label_survives_the_fold():
    """Haryana reserves only Block A of its Backward Classes list. Folding that
    to BC is right for pooling and wrong to be the only thing recorded."""
    row = M.to_master(
        dict(
            BASE,
            state="Haryana",
            caste_reservation="BC",
            caste_reservation_local="BC_A",
        ),
        "haryana/gp_ward/2022",
        "local_elections_haryana",
        "def456",
        "document",
    )
    assert row["caste_reservation"] == "BC"
    assert row["caste_reservation_local"] == "BC_A"
    assert row["caste_scheme"] == "sc_st_bca_only"


def test_the_listing_scope_is_written_on_every_row():
    """Absent meant all_seats by convention, and a convention that lives only in
    a docstring is one nobody can filter on."""
    assert convert()["listing_scope"] == "all_seats"
    assert convert(listing_scope="reserved_only")["listing_scope"] == "reserved_only"


# ---------------------------------------------------------- quality flags


def test_a_guessed_gender_is_flagged():
    """woman_reserved is 0 by default where the marker did not survive the
    scan, so the row is a guess rather than a reading and has to say so."""
    assert "gender_not_stated" in convert(gender_stated="0")["quality_flags"]
    assert "gender_not_stated" not in convert(gender_stated="1")["quality_flags"]


def test_an_inferred_winner_is_flagged():
    assert "winner_inferred" in convert(winner_basis="argmax_votes")["quality_flags"]


def test_source_level_seat_exceptions_are_flagged():
    row = convert(
        ward_no_inferred="1",
        winner_name_missing="1",
        reservation_body_control_agree="0",
        margin_below_votes="0",
    )
    assert set(row["quality_flags"].split(";")) == {
        "seat_number_inferred",
        "winner_name_missing",
        "reservation_control_disagree",
        "margin_not_below_votes",
    }


def test_untransliterated_names_are_flagged():
    assert "name_untransliterated" in convert(script="krutidev")["quality_flags"]


def test_gujarati_script_survives_the_master_projection():
    row = convert(block="દસક્રોઈ", ward_name="અસલાલી", script="gujarati")
    assert row["script"] == "gujarati"
    assert "name_untransliterated" in row["quality_flags"]


def test_bengali_script_survives_the_master_projection():
    row = convert(ward_name="নিজ মনিৰচৰ", script="bengali")
    assert row["script"] == "bengali"
    assert "name_untransliterated" in row["quality_flags"]


def test_a_clean_row_carries_no_flags():
    assert convert()["quality_flags"] == ""


# ------------------------------------------------------------------ extras


def test_state_specific_columns_go_long_form_rather_than_widening_the_table():
    got = M.extras(
        {
            "pop_sc": "412",
            "ward_count": "8",
            "state": "Goa",
            "gram_panchayat": "Anjuna",
        },
        "abc",
    )
    assert {e["column"] for e in got} == {"pop_sc", "ward_count"}
    assert all(e["row_id"] == "abc" for e in got)


def test_blank_extras_are_not_recorded():
    assert M.extras({"pop_sc": "", "ward_count": None}, "abc") == []


def test_an_undeclared_column_is_not_smuggled_into_extras():
    """Extras are still declared columns. An unknown one means a parser grew a
    field nobody documented, and the dictionary should hear about it first."""
    assert M.extras({"mystery_column": "42"}, "abc") == []


def test_every_rows_script_matches_its_own_text():
    """`script` says which typesetting a row was read from, so it has to be
    true of that row.

    It was a literal in every adapter, and the corpus shipped 304,689 rows -
    36.7% - asserting a script their own text contradicted: Uttar Pradesh
    declared latin over Devanagari, Bihar declared devanagari over RAMADHAR
    YADAV. Then, once derived, it was derived per *candidate* while
    collapse.to_seats merges candidates into seats, so 7,226 Bihar seats
    carried the script of a name they do not show.

    Nothing failed either time. This is the check that does.

    krutidev is exempt and has to be: it is ASCII, so no test of which Unicode
    block a character belongs to can see it, and only the parser that read the
    document knows.
    """
    import re

    import pyarrow.parquet as pq

    from local_elections.paths import ROOT

    devanagari = re.compile(r"[ऀ-ॿ]")
    bengali = re.compile(r"[ঀ-৿]")
    gujarati = re.compile(r"[઀-૿]")
    kannada = re.compile(r"[ಀ-೿]")
    columns = ["winner", "gram_panchayat", "district", "block", "ward_name"]
    wrong = []
    for path in sorted((ROOT / "data" / "master").glob("master_*.parquet")):
        if path.name == "master_extras.parquet":
            continue
        table = pq.read_table(path, columns=[*columns, "script"])
        held = [table.column(c).to_pylist() for c in columns]
        for values in zip(*held, table.column("script").to_pylist(), strict=True):
            script = values[-1]
            if script == "krutidev":
                continue
            text = " ".join(v for v in values[:-1] if v)
            want = (
                "kannada"
                if kannada.search(text)
                else "gujarati"
                if gujarati.search(text)
                else "bengali"
                if bengali.search(text)
                else "devanagari"
                if devanagari.search(text)
                else "latin"
            )
            if want != script:
                wrong.append((path.name, want, script, text[:40]))
    assert not wrong, f"{len(wrong)} rows: {wrong[:3]}"
