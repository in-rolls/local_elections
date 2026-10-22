"""docs/naming.md's rules, as tools/naming.py enforces them."""

from local_elections.tools.naming import violations


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
    import pyarrow as pa
    import pyarrow.parquet as pq

    from local_elections.paths import ROOT

    found = []
    for path in sorted((ROOT / "data" / "master").glob("*.parquet")):
        schema = pq.read_schema(path)
        flags = {f.name for f in schema if pa.types.is_boolean(f.type)}
        found += [(path.name, n) for n, _ in violations(schema.names, flags)]
    assert found == []
