"""docs/naming.md's rules, as tools/naming.py enforces them."""

from local_elections.tools.naming import check, pooled_files, violations


def names(columns):
    return {name for name, _ in violations(columns)}


def test_the_new_names_pass():
    ok = [
        "reserved_caste",
        "reserved_caste_local",
        "reserved_woman",
        "reserved_raw",
        "reserved_label",
        "winner_woman",
        "winner_woman_raw",
        "winner_woman_probability",
        "winner_woman_probability_method",
        "winner_latin",
        "winner_latin_method",
        "winner_woman_from_honorific",
    ]
    assert names(ok) == set()


def test_old_words_are_caught():
    old = [
        "caste_reservation",
        "woman_reserved",
        "winner_gender",
        "sex_raw",
        "women_reserved",
    ]
    assert names(old) == set(old)


def test_inferred_and_transliterated_need_a_method():
    assert names(["winner_latin"]) == {"winner_latin"}
    assert names(["winner_woman_probability"]) == {"winner_woman_probability"}


def test_a_true_false_flag_needs_no_method():
    assert (
        names_flags(["winner_printed_in_latin"], {"winner_printed_in_latin"}) == set()
    )


def names_flags(columns, flags):
    return {name for name, _ in violations(columns, flags)}


def test_the_published_tables_follow_naming():
    # the hub's tables and every sibling file it pins, as `make naming` reads them
    assert check(pooled_files()) == []
