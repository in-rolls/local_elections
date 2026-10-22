"""Kruti Dev conversion, pinned against strings whose meaning is known.

Every case is either a reservation phrase whose meaning is established elsewhere
in this corpus, or a Jharkhand place whose spelling is checkable against the
world. That matters more than usual here: a wrong mapping produces a real-looking
Devanagari word, not an error, and nobody reading the output would spot it.
"""

import pytest

from local_elections.common import krutidev

# The reservation vocabulary, whose meanings are pinned in test_normalize.py
PHRASES = [
    ("vuqlwfpr tkfr", "अनुसूचित जाति"),
    ("vuqlwfpr tutkfr", "अनुसूचित जनजाति"),
    ("vukjf{kr", "अनारक्षित"),
    ("efgyk", "महिला"),
    ("vU;", "अन्य"),
    ("fiNM+k oxZ", "पिछड़ा वर्ग"),
    ("eqf[k;k", "मुखिया"),
    ("xzke iapk;r lnL;", "ग्राम पंचायत सदस्य"),
    ("iapk;r lfefr lnL;", "पंचायत समिति सदस्य"),
    ('ftyk ifj"kn lnL;', "जिला परिषद सदस्य"),
]


@pytest.mark.parametrize(("raw", "expected"), PHRASES)
def test_the_reservation_vocabulary_converts(raw, expected):
    assert krutidev.to_unicode(raw) == expected


# Jharkhand districts and blocks. Checkable against the world rather than
# against ourselves, which is the only kind of check worth much here.
PLACES = [
    ("/kuckn", "धनबाद"),  # Dhanbad
    ("jkaph", "रांची"),  # Ranchi
    ("gtkjhckx", "हजारीबाग"),  # Hazaribagh
    ("nso?kj", "देवघर"),  # Deoghar
    ("fxfjMhg", "गिरिडीह"),  # Giridih
    ("yksgjnxk", "लोहरदगा"),  # Lohardaga
    ("x<+ok", "गढ़वा"),  # Garhwa
    ("cksdkjks", "बोकारो"),  # Bokaro
    ("fleMsxk", "सिमडेगा"),  # Simdega
    ("ikdqM+", "पाकुड़"),  # Pakur
    ("tkerkM+k", "जामताड़ा"),  # Jamtara
    ("jkex<+", "रामगढ़"),  # Ramgarh
    ("[kwaVh", "खूंटी"),  # Khunti
    ("iwohZ flagHkwe", "पूर्वी सिंहभूम"),  # East Singhbhum
    ("xksfe;k", "गोमिया"),  # Gomia block
    ("pkl", "चास"),  # Chas block
]


@pytest.mark.parametrize(("raw", "expected"), PLACES)
def test_place_names_convert(raw, expected):
    assert krutidev.to_unicode(raw) == expected


def test_the_i_matra_moves_after_its_consonant():
    """Kruti Dev stores glyphs in drawing order, so ि comes before the letter it
    belongs to. Emitting it in place gives िच where चि is meant - a different
    word that still reads as Devanagari."""
    assert krutidev.to_unicode("fp") == "चि"
    assert krutidev.to_unicode("fxfjMhg") == "गिरिडीह"


def test_the_reph_moves_before_its_consonant():
    """The mirror case: र् is written after in Kruti Dev and before in
    Unicode, so "xZ" is र्ग."""
    assert krutidev.to_unicode("oxZ") == "वर्ग"
    assert krutidev.to_unicode("iwohZ") == "पूर्वी"


def test_the_o_matra_is_one_codepoint_not_two():
    """Taken a character at a time "ks" gives ा + े, which draws exactly like ो
    and is two codepoints. बाेकाराे would never join to बोकारो, and nothing on
    screen would show why."""
    got = krutidev.to_unicode("cksdkjks")
    assert got == "बोकारो"
    assert "ो" in got
    assert "ाे" not in got


def test_longest_match_wins():
    """ "Hk" is भ, not ह + क. One byte at a time silently produces a different
    and perfectly plausible word."""
    assert krutidev.to_unicode("Hk") == "भ"
    assert krutidev.to_unicode("{k") == "क्ष"
    assert krutidev.to_unicode("/k") == "ध"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        pytest.param('lq"kek', "सुषमा", id="up-2005-page-1-row-32"),
        pytest.param('lq"ek', "सुष्मा", id="up-2005-page-734-row-16"),
        pytest.param("d'ehjh", "कश्मीरी", id="up-2005-page-12-row-18"),
        pytest.param("d'kehjh", "कशमीरी", id="up-2005-page-41-row-31"),
    ],
)
def test_half_consonants_preserve_source_name_distinctions(raw, expected):
    """Preserve the four visually reviewed readings in UP's 2005 mem_kp.pdf."""
    assert krutidev.to_unicode(raw) == expected


def test_already_converted_text_is_recognised():
    assert krutidev.looks_converted("धनबाद")
    assert not krutidev.looks_converted("/kuckn")


def test_digits_and_punctuation_pass_through():
    assert krutidev.to_unicode("01-y{ehiqj") == "01-लक्ष्मीपुर"


def test_empty_input_is_returned_unchanged():
    assert krutidev.to_unicode("") == ""
    assert krutidev.to_unicode(None) is None
