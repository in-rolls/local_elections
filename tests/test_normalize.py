"""Every reservation string observed across the state corpora.

Each case here was taken from a real document. They are pinned because the
failure mode is silent: an unmatched spelling reads as an open seat, which is a
perfectly plausible value, so nothing raises and nothing looks wrong.
"""

import pytest

from local_elections.common.normalize import (
    caste_of,
    is_krutidev,
    is_vacant,
    label,
    normalize_reservation,
    script_of,
    strip_unopposed,
    woman_of,
)
from local_elections.paths import ROOT

# ---------------------------------------------------------------- Jharkhand
# Caste and gender sit in separate columns, so these are tested separately.
# "vuqlwfpr tutkfr" (janjati/ST) contains "tkfr" (jati/SC), and the corpus also
# splits it as "tu tkfr", so ST has to be decided before SC in both views.
JHARKHAND_CASTE = [
    ("vukjf{kr", "NONE"),  # anarakshit - unreserved
    ("vukfj{kr", "NONE"),  # same, misspelt
    ("vuqlwfpr tutkfr", "ST"),
    ("vuqlwfpr tu tkfr", "ST"),  # split mid-word
    ("vuqlwfpr tkfr", "SC"),
    ("vuqlwph tkfr", "SC"),
    ("vuqlqfpr tkfr", "SC"),
    ("vU; fiNM+k oxZ", "BC"),
    ("vU; foNMk oxZ", "BC"),
    ("fiNM+k oxZ", "BC"),
]

# ---------------------------------------------------------------- Goa codes
GOA = [
    ("General", "NONE", 0),
    ("Women", "NONE", 1),
    ("W", "NONE", 1),
    ("OBC", "BC", 0),
    ("O.B.C.", "BC", 0),
    ("O.B.C", "BC", 0),
    ("OBCW", "BC", 1),
    ("ST", "ST", 0),
    ("S.T.", "ST", 0),
    ("ST.", "ST", 0),
    ("STW", "ST", 1),
    ("SC", "SC", 0),
]

# ------------------------------------------------- Andhra Pradesh OCR codes
AP = [
    ("UR", "NONE", 0),
    ("UR (W)", "NONE", 1),
    ("UR(W)", "NONE", 1),
    ("SC", "SC", 0),
    ("sc (w)", "SC", 1),
    ("BC", "BC", 0),
    ("Bc (w)", "BC", 1),
    ("UR(M)", "NONE", 0),
    ("SC(M)", "SC", 0),
    ("BC(M)", "BC", 0),
    ("ST", "ST", 0),
]

# ------------------------------------------------------- Haryana, unchanged
HARYANA = [
    ("Women", "NONE", 1),
    ("Other than Women", "NONE", 0),
    ("Scheduled Caste Other than Women", "SC", 0),
    ("Backward Class 'A' Women", "BC", 1),
    ("Unreserved", "NONE", 0),
    ("Scheduled Caste", "SC", 0),
    ("Scheduled Class (Women)", "SC", 1),  # "Class" is Caste misspelt
    ("Seheduled Caste Women", "SC", 1),  # c -> e typo
    ("Scheduled Cast e Women", "SC", 1),  # stray space inside the word
    ("Sc Women", "SC", 1),
    ("BC (A) Other than Women", "BC", 0),
    ("efgyk", "NONE", 1),
    ("efgyk ds flok;", "NONE", 0),
    ("vuqlwfpr tkfr efgyk", "SC", 1),
    ("vuqlwfpr tkfr efgyk ds flok;", "SC", 0),
    ("eefgyk ds fll ok;", "NONE", 0),  # doubled chars, split word
    ("ljiap vuqlwfpr tkfr efgyk ds", "SC", 0),  # truncated to trailing "ds"
    ("fiN+Mk oxZ d efgyk", "BC", 1),  # floating "+" diacritic
]

# ------------------------------------------------------------ J&K vocabulary
# Three different years, three different vocabularies. "Res. For SC/Women" is
# the one that mattered: tokens were split on whitespace only, so "SC/Women"
# became the single token "scwomen", the caste test missed, and an SC-woman seat
# was recorded as an open seat reserved for a woman.
JK = [
    ("Un Reserved", "NONE", 0),
    ("Open", "NONE", 0),
    ("OC", "NONE", 0),
    ("Gn", "NONE", 0),
    ("Gn Women", "NONE", 1),
    ("Res. For Women", "NONE", 1),
    ("Res. For SC", "SC", 0),
    ("Res. For SC/Women", "SC", 1),
    ("Res. For Women/SC", "SC", 1),
    ("ST Reserved", "ST", 0),
    ("ST/W", "ST", 1),
]

NON_CATEGORIES = [
    "",
    None,
    "Sarpanch",
    "Panch",
    "iap",
    "5",
    "--",
    "Independent",
    "Reserved for",
]


def test_gujarati_unicode_is_not_labeled_latin():
    assert script_of("અસલાલી") == "gujarati"


def test_bengali_unicode_is_not_labeled_latin():
    assert script_of("নিজ মনিৰচৰ") == "bengali"


@pytest.mark.parametrize(("raw", "caste"), JHARKHAND_CASTE)
def test_jharkhand_caste_column(raw, caste):
    assert caste_of(raw) == caste


def test_jharkhand_gender_column():
    assert woman_of("efgyk") == 1
    assert woman_of("vU;") == 0


@pytest.mark.parametrize(("raw", "caste", "woman"), GOA + AP + HARYANA + JK)
def test_single_cell_states(raw, caste, woman):
    result = normalize_reservation(raw)
    assert result is not None, f"{raw!r} was not recognized as a category"
    assert result[:2] == (caste, woman)
    assert result[2] == ("krutidev" if is_krutidev(raw) else "latin")


@pytest.mark.parametrize("raw", NON_CATEGORIES)
def test_rejects_non_categories(raw):
    assert normalize_reservation(raw) is None


def test_wrapped_cell_is_whitespace_insensitive():
    """pdfplumber joins a wrapped cell with a newline; that must not matter."""
    assert normalize_reservation("Scheduled Caste\nOther than Women") == (
        "SC",
        0,
        "latin",
    )
    assert normalize_reservation("vuqlwfpr tkfr efgyk\nds flok;") == (
        "SC",
        0,
        "krutidev",
    )


def test_script_detection():
    assert is_krutidev("vuqlwfpr tkfr efgyk")
    assert is_krutidev("efgyk")
    assert not is_krutidev("Scheduled Caste Women")
    assert not is_krutidev("OBCW")


def test_labels():
    assert label("NONE", 1) == "Woman"
    assert label("NONE", 0) == "Other than Woman"
    assert label("SC", 1) == "SC Woman"
    assert label("ST", 0) == "ST Other than Woman"
    assert label("BC", 1) == "BC Woman"


def test_unopposed_and_vacant():
    assert strip_unopposed("*Sunita Rani") == ("Sunita Rani", True)
    assert strip_unopposed("Sunita Rani") == ("Sunita Rani", False)
    assert is_vacant("Vacant")
    assert is_vacant("fjDr in")
    assert is_vacant("")
    assert not is_vacant("Sunita Rani")


# Every value the six Bihar files print, with the number of rows carrying it.
# The vocabulary is closed and paired - each caste appears plain and with
# (महिला) - which is what licenses the adapter reading a plain label as
# not-woman rather than as silent. The counts are asserted against the files
# themselves below, so they cannot quietly become decoration.
BIHAR = [
    ("अनारक्षित  ", "NONE", None, 243_751),
    ("अनारक्षित(महिला)", "NONE", 1, 192_931),
    ("अनुसूचित जाति", "SC", None, 64_538),
    ("पिछड़ा वर्ग", "BC", None, 60_984),
    ("पिछड़ा वर्ग(महिला)", "BC", 1, 38_430),
    ("अनुसूचित जाति(महिला)", "SC", 1, 38_239),
    ("अनुसूचित जनजाति ", "ST", None, 5_009),
    ("अनुसूचित जनजाति(महिला)", "ST", 1, 1_395),
    # 328 rows state no category at all. Not read as unreserved: an unstated
    # reservation and an open seat are different things.
    ("--select--", None, None, 328),
]


@pytest.mark.parametrize(("raw", "caste", "woman", "_"), BIHAR)
def test_bihar_reservation_column(raw, caste, woman, _):
    assert caste_of(raw) == caste
    assert woman_of(raw) == woman


def test_the_bihar_vocabulary_is_closed_and_counted():
    """Asserted against the sibling's own files, so the vocabulary above is a
    claim about the data rather than a comment. Skipped where the sibling is
    not checked out; the adapter's DECLARED counts cover that case."""
    import collections
    import csv
    import unicodedata

    # ROOT, not a count of parents. The count was right while this file lived
    # in scripts/common/ and wrong the moment it moved to tests/ - and it did
    # not fail, it skipped, reporting a sibling that is checked out as absent.
    root = ROOT.parent / "local_elections_bihar" / "data"
    if not root.exists():
        pytest.skip("local_elections_bihar is not checked out")
    csv.field_size_limit(10**7)
    seen = collections.Counter()
    for path in sorted(root.glob("*.csv")):
        with path.open(encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                seen[row["reservation_status"]] += 1

    # Compared under NFC, because ड़ has two spellings - U+095C, and U+0921
    # followed by the nukta U+093C - that draw identically and compare unequal.
    # normalize.py is already safe here (it NFKC-folds every input); this is
    # only about the literals above matching what the files hold.
    def nfc(text):
        return unicodedata.normalize("NFC", text)

    assert {nfc(k): v for k, v in seen.items()} == {
        nfc(raw): n for raw, _, _, n in BIHAR
    }


def test_a_backward_class_seat_reserved_for_a_woman_reads_as_both():
    """Bihar writes "पिछड़ा वर्ग(महिला)". The backward-class phrase was tested
    before the woman marker - because "अन्य पिछड़ा वर्ग" contains "अन्य" - and
    that returned None for all 38,430 of them: the caste read, the gender was
    dropped, and nothing flagged it because None is what a silent cell returns
    too. The guard is still needed, just not first."""
    assert woman_of("पिछड़ा वर्ग(महिला)") == 1
    assert woman_of("अन्य पिछड़ा वर्ग") is None


# Uttarakhand abbreviates with a Devanagari zero where a full stop would go, in
# ten spellings across four categories. 1,228 rows read as no category at all
# before these were covered, and two read as the wrong one.
UTTARAKHAND = [
    ("अनु0जाति", "SC", None),
    ("अनु0जाति महिला", "SC", 1),
    ("अनु0जा0महिला", "SC", 1),
    ("अनु0 जाति", "SC", None),
    ("अनु0जनजाति", "ST", None),
    ("अनु0ज0जा0", "ST", None),
    ("अनु0ज0जा0महिला", "ST", 1),
    ("अनु0 ज0जाति महिला", "ST", 1),
    ("अ0पि0वर्ग", "BC", None),
    ("अ0पि0व0महिला", "BC", 1),
    ("अन्य पि0वर्ग", "BC", None),
    ("अन्य पि0वर्ग महिला", "BC", 1),
    # a bare gender with no caste is an unreserved seat reserved for a woman
    ("म्हिला", "NONE", 1),
    # the reservation cell that also carries a ward range
    ("अनु0जाति वार्ड न० ०१-०७ तक", "SC", None),
]


@pytest.mark.parametrize(("raw", "caste", "woman"), UTTARAKHAND)
def test_uttarakhand_abbreviations(raw, caste, woman):
    assert caste_of(raw) == caste
    assert woman_of(raw) == woman


def test_an_abbreviated_janjati_is_not_a_jati():
    """अनु0ज0जाति is *jan*jati with the syllable abbreviated away. The jati
    pattern matched it first and filed a scheduled tribe seat as a scheduled
    caste one - the same ordering trap the Kruti Dev patterns already carry a
    comment about, in a spelling they did not cover."""
    assert caste_of("अनु0ज0जाति") == "ST"
    assert caste_of("अनु0जाति") == "SC"


def test_uttar_pradesh_writes_female_not_woman():
    """UP's normalized English column says "Female". 24,000 seats in 2005 alone
    read as gender-not-stated, and "wom" does not appear in the word."""
    assert woman_of("Female") == 1
    assert woman_of("Other Backward Class - Female") == 1
    assert caste_of("Other Backward Class - Female") == "BC"


BARE_GENDER = ["Woman", "Female", "महिला", "म्हिला"]


@pytest.mark.parametrize("raw", BARE_GENDER)
def test_a_bare_gender_is_an_unreserved_seat_reserved_for_a_woman(raw):
    """The same fact in four spellings, and it used to get two answers: CODES
    knew "Woman" and returned NONE, and nothing knew "Female" or "महिला". The
    adapters then blanked the whole reservation rather than the caste alone -
    11,166 Uttar Pradesh seats in 2005, 8,402 in 2010, 62,917 candidate rows in
    2021 and 35,361 in Uttarakhand read as "no reservation stated" while the
    source said "reserved for a woman", and every count balanced."""
    assert caste_of(raw) == "NONE"
    assert woman_of(raw) == 1


def test_a_bare_caste_is_not_turned_into_a_womans_seat():
    """The rule runs only where no caste matched, so it cannot reach back and
    change one that did."""
    assert (caste_of("Scheduled Caste"), woman_of("Scheduled Caste")) == ("SC", None)
    assert (caste_of("SC Woman"), woman_of("SC Woman")) == ("SC", 1)
    assert caste_of("Unknown") is None


@pytest.mark.parametrize(
    ("label", "caste", "woman"),
    [
        # Bihar's two printings of its own vocabulary, closed and paired in both
        # years. 2021 spaces and dashes janjati; 2016 runs it together.
        ("अनारक्षित  (अन्य)", "NONE", 0),
        ("अनारक्षित  (महिला)", "NONE", 1),
        ("अनुसूचित जाति  (अन्य)", "SC", 0),
        ("अनुसूचित जाति  (महिला)", "SC", 1),
        ("अनुसूचित जन - जाति  (अन्य)", "ST", 0),
        ("अनुसूचित जन - जाति  (महिला)", "ST", 1),
        ("पिछड़ा वर्ग  (महिला)", "BC", 1),
        ("अनारक्षित", "NONE", None),
        ("अनारक्षित(महिला)", "NONE", 1),
        ("अनुसूचित जाति(महिला)", "SC", 1),
        ("अनुसूचित जनजाति", "ST", None),
        ("अनुसूचित जनजाति(महिला)", "ST", 1),
        ("पिछड़ा वर्ग(महिला)", "BC", 1),
    ],
)
def test_bihar_prints_the_same_seats_two_ways(label, caste, woman):
    assert caste_of(label) == caste
    assert woman_of(label) == woman


@pytest.mark.parametrize(
    ("label", "caste", "woman"),
    [
        # The word that marks a gender is also the first word of a caste.
        ("पिछड़ा वर्ग  (अन्य)", "BC", 0),
        ("अन्य पिछड़ा वर्ग", "BC", None),
        ("अन्य पि0वर्ग", "BC", None),
        ("अन्य पिछड़ा वर्ग महिला", "BC", 1),
    ],
)
def test_other_marks_a_gender_unless_it_opens_the_caste(label, caste, woman):
    assert caste_of(label) == caste
    assert woman_of(label) == woman
