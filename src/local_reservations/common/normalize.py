"""Read a reservation label, whatever shape the state prints it in.

Generalised from local_elections_haryana/scripts/normalize.py. Every state
publishes the same two facts - which caste category a seat is reserved for, and
whether it is reserved for a woman - but no two print them alike:

    Haryana    "Scheduled Caste Other than Women", or Kruti Dev
               "vuqlwfpr tkfr efgyk ds flok;"
    Goa        codes in one cell: G, ST, OBC, W, OBCW, STW
    Jharkhand  two separate columns: "vuqlwfpr tutkfr" and "efgyk"/"vU;"
    J&K        "Open", "Women", "SC", "ST", "OC"
    Andhra     OCR'd codes: UR, SC, BC, ST, with "(W)" - and "5C", "8c"

So the module exposes the two facts separately - caste_of() and woman_of() -
and normalize_reservation() for the states that print both in one cell. States
whose caste and gender live in different columns call the two directly.

Output is always caste_reservation in {SC, ST, BC, NONE} and woman_reserved in
{0, 1}. BC covers Backward Class, BC(A) and OBC; the states do not agree on the
name and the distinction is not recoverable from the label anyway.

The failure mode this guards against is not an exception. An unmatched spelling
silently downgrades a reserved seat to an open one, which looks entirely
plausible in the output. That is why matching is deliberately loose and why
every observed string is pinned in test_normalize.py.
"""

import re
import unicodedata

# --------------------------------------------------------------- Kruti Dev
# Legacy font encoding, byte-for-byte deterministic rather than OCR guesses.
# "anusuchit" is spelt at least a dozen ways across Haryana and Jharkhand, so it
# is matched as "vuq + anything + jati" rather than by literal.
KD_SC = re.compile(r"vuq\S*\s+tkfr")  # anusuchit jati
KD_ST = re.compile(r"vuq\S*\s+tu\s*tkfr")  # anusuchit janjati
KD_SC_TIGHT = re.compile(r"vuq\w*tkfr")
KD_ST_TIGHT = re.compile(r"vuq\w*tutkfr")
KD_BC = re.compile(r"f[io]NM|fiNM")  # pichhda varg, and its typos
KD_UNRESERVED = re.compile(r"vuk[fj]+\{kr")  # anarakshit, incl. "vukfj{kr"
KD_WOMAN = "efgyk"  # mahila
KD_OTHER = "vU;"  # anya - the "not a woman" cell
KD_OTHER_THAN = "flok;"  # sivay - "other than"

# Unicode Devanagari, which is what OCR of a scanned notification returns -
# Jharkhand's six scanned districts are the same PROFORMA-23 form as its text
# ones, just photographed. Janjati has to be tested before jati for the same
# reason its Kruti Dev spelling does: the first contains the second.
# Uttarakhand abbreviates with a Devanagari zero standing in for a full stop -
# अनु0जा0महिला for अनुसूचित जाति महिला, अ0पि0व0महिला for अन्य पिछड़ा वर्ग
# महिला - in ten spellings across four categories, 1,228 rows of which read as
# no category at all before these patterns covered them. One of them read as
# the wrong category: अनु0ज0जाति is *jan*jati abbreviated, and the jati pattern
# matched it first, filing a scheduled tribe seat as a scheduled caste one.
# Hence the standalone ज before जा here, tested with the rest of janjati.
# Bihar 2021 prints Scheduled Tribe as "अनुसूचित जन - जाति", so the two halves of
# janjati can be held apart by a dash as well as a space. Without the dash the
# label fell through to the unreserved test and 672 seats reserved for tribal
# women read as open seats.
DEV_ST = re.compile(r"अनु\S*\s*जन[\s\-–—]*जाति|जन[\s\-–—]*जाति|ज[०0]\s*जा")
DEV_SC = re.compile(r"अनु\S*\s*जाति|अनु[०0\s]*जा")
DEV_BC = re.compile(r"पिछ\S*\s*वर्ग|पि[०0]\s*व")
DEV_NONE = re.compile(r"अनारक्षित|अनारछित")
# म्हिला is महिला with the vowel sign misplaced, 75 rows of it
DEV_WOMAN = re.compile(r"महिला|म्हिला")
DEV_OTHER = "अन्य"

VACANT = ("rikt", "riet", "vacant", "fjDr", "[kkyh", "रिक्त")

# ------------------------------------------------------------- short codes
# Goa, Andhra and J&K print codes rather than phrases. Matched on the
# letters-only form, so "O.B.C.", "OBC" and "Obc" all land here, and so does
# "UR (W)" -> "urw".
CODES = {
    "g": ("NONE", 0),
    "gn": ("NONE", 0),
    "gen": ("NONE", 0),
    "general": ("NONE", 0),
    "ur": ("NONE", 0),
    "unreserved": ("NONE", 0),
    "open": ("NONE", 0),
    "oc": ("NONE", 0),
    "o": ("NONE", 0),
    "w": ("NONE", 1),
    "women": ("NONE", 1),
    "woman": ("NONE", 1),
    "gw": ("NONE", 1),
    "genw": ("NONE", 1),
    "generalw": ("NONE", 1),
    "urw": ("NONE", 1),
    "openw": ("NONE", 1),
    "ocw": ("NONE", 1),
    "sc": ("SC", 0),
    "scw": ("SC", 1),
    "scwomen": ("SC", 1),
    "st": ("ST", 0),
    "stw": ("ST", 1),
    "stwomen": ("ST", 1),
    "bc": ("BC", 0),
    "bcw": ("BC", 1),
    "bcwomen": ("BC", 1),
    "obc": ("BC", 0),
    "obcw": ("BC", 1),
    "obcwomen": ("BC", 1),
    "bca": ("BC", 0),
    "bcaw": ("BC", 1),
    # Anantapur marks the open seats explicitly with G for General rather than
    # leaving them unmarked: UR(G), SC/G, BC/W.
    "urg": ("NONE", 0),
    "urm": ("NONE", 0),
    "gng": ("NONE", 0),
    "gnm": ("NONE", 0),
    "og": ("NONE", 0),
    "om": ("NONE", 0),
    "scg": ("SC", 0),
    "scm": ("SC", 0),
    "stg": ("ST", 0),
    "stm": ("ST", 0),
    "bcg": ("BC", 0),
    "bcm": ("BC", 0),
    "obcg": ("BC", 0),
    "obcm": ("BC", 0),
}


def _squash(s):
    """Collapse whitespace and fold the apostrophe variants together."""
    s = unicodedata.normalize("NFKC", s or "")
    s = s.replace("‘", "'").replace("’", "'").replace("‛", "'")
    return re.sub(r"\s+", " ", s).strip()


def _undouble(s):
    """Collapse runs of a repeated character to one.

    Some notifications are typeset with every character doubled - "vuqllwfpr"
    for "vuqlwfpr", whole lines as "EEXXTTRRAAOORRDDIINNAARRYY". None of the
    strings matched here contain a genuine doubled character, so collapsing runs
    is safe and makes the match survive it.
    """
    return re.sub(r"(.)\1+", r"\1", s)


def _kd_forms(s):
    """The two Kruti Dev views: run-collapsed, and also space-stripped.

    Words arrive split by stray spaces ("fll ok;" for "flok;", "tu tkfr" for
    "tutkfr"), and "+" is a diacritic that floats position, so "fiNM+k" is also
    typeset "fiN+Mk". Both views are tried against every pattern.
    """
    return _undouble(s).replace("+", ""), _undouble(re.sub(r"[\s+]", "", s))


def is_krutidev(text):
    kd, tight = _kd_forms(_squash(text))
    return bool(
        KD_WOMAN in kd
        or KD_WOMAN in tight
        or KD_OTHER in kd
        or KD_UNRESERVED.search(kd)
        or KD_SC_TIGHT.search(tight)
    )


# Unicode blocks, not guesses about a state's habits.
_DEVANAGARI = re.compile(r"[\u0900-\u097f]")
_BENGALI = re.compile(r"[\u0980-\u09ff]")
_GUJARATI = re.compile(r"[\u0a80-\u0aff]")
_KANNADA = re.compile(r"[\u0c80-\u0cff]")


def script_of(*values):
    """Which script this row's text is actually in.

    Every adapter used to hardcode this - `"script": "latin"` on one row
    builder and `"devanagari"` on the next - and the corpus shipped 304,689
    rows saying the wrong thing: Uttar Pradesh declared latin over 103,729 rows
    of Devanagari, and Bihar declared devanagari over 200,960 rows reading
    RAMADHAR YADAV. That is 37% of the corpus asserting something about itself
    that the text contradicts, and the dictionary's own note for the column
    says it records "which typesetting the row was read from".

    Devanagari and Kannada are decided by their Unicode blocks, which is exact.

    Kruti Dev is checked last and is **not** exact, and the limit is worth
    stating: `is_krutidev` recognises this corpus's reservation vocabulary, not
    Kruti Dev in general, so a *name* set in it - "vfurk nsoh" for अनिता देवी -
    comes back latin here. It is ASCII, so nothing that asks which Unicode
    block a character is in can see it, and that is exactly how 17,115
    Jharkhand winners once shipped as mojibake labelled Unicode. Twenty-three
    rows in the corpus carry the label today; a caller that knows a document is
    Kruti Dev should say so rather than rely on this.
    """
    joined = " ".join(v for v in values if v)
    if _KANNADA.search(joined):
        return "kannada"
    if _GUJARATI.search(joined):
        return "gujarati"
    if _BENGALI.search(joined):
        return "bengali"
    if _DEVANAGARI.search(joined):
        return "devanagari"
    if any(is_krutidev(v) for v in values if v):
        return "krutidev"
    return "latin"


def caste_of(text):
    """SC / ST / BC / NONE, or None when the cell says nothing about caste."""
    s = _squash(text)
    if not s:
        return None
    kd, tight = _kd_forms(s)

    # Scheduled Tribe must be tested before Scheduled Caste: "vuqlwfpr tutkfr"
    # (janjati) contains "tkfr" (jati), so an SC test would claim it first.
    if KD_ST.search(kd) or KD_ST_TIGHT.search(tight):
        return "ST"
    if KD_SC.search(kd) or KD_SC_TIGHT.search(tight):
        return "SC"
    if KD_BC.search(kd) or KD_BC.search(tight):
        return "BC"
    if KD_UNRESERVED.search(kd) or KD_UNRESERVED.search(tight):
        return "NONE"

    # Devanagari, in the same order and for the same reason as the Kruti Dev
    # above: "अन्य पिछड़ा वर्ग" contains "अन्य", so backward class has to be
    # decided before the word that also marks gender.
    if DEV_ST.search(s):
        return "ST"
    if DEV_BC.search(s):
        return "BC"
    if DEV_SC.search(s):
        return "SC"
    if DEV_NONE.search(s):
        return "NONE"

    letters = re.sub(r"[^a-z]", "", s.lower())
    if letters in CODES:
        return CODES[letters][0]

    # Phrase form. Key on the head noun, not the qualifier: "Scheduled Caste"
    # also appears as "Schedule Cast", "Schedulded Caste" and "Seheduled
    # Caste", so chasing the qualifier means chasing each new misspelling.
    # "sched" decides it even when the noun is wrong - the 2016 Haryana gazette
    # prints "Scheduled Class", which is Caste misspelt, not Backward Class.
    # Split on any non-letter, not just whitespace. J&K writes "Res. For
    # SC/Women"; splitting on spaces alone leaves that as the single token
    # "scwomen", the "sc" test misses, and an SC-woman seat is recorded as an
    # open seat reserved for a woman - the caste silently dropped.
    tokens = {t for t in re.split(r"[^a-z]+", s.lower()) if t}
    if "trib" in letters or "st" in tokens:
        return "ST"
    if "cast" in letters or "sched" in letters or "sc" in tokens:
        return "SC"
    if "clas" in letters or "back" in letters or tokens & {"bc", "obc", "bca"}:
        return "BC"
    if "unreserv" in letters or "general" in letters or "open" in letters:
        return "NONE"

    # A cell that states a gender and no caste is an unreserved seat reserved
    # for a woman. `CODES` already answered NONE for the spelling "Woman", and
    # answered nothing for "Female" and "महिला" - the same fact, three
    # spellings, two different answers. The adapters then blanked the whole
    # reservation on those rows rather than the caste alone: 11,166 seats in
    # Uttar Pradesh 2005, 8,402 in 2010, 62,917 candidate rows in 2021 and
    # 35,361 in Uttarakhand read as "no reservation stated" while their source
    # plainly said "reserved for a woman". Every count balanced throughout.
    if woman_of(s) == 1:
        return "NONE"
    return None


def woman_of(text):
    """1 if reserved for a woman, 0 if explicitly not, None if the cell is silent.

    Note the asymmetry: "efgyk" alone means woman, but "efgyk ds flok;" means
    *other than* woman, so the negation has to be checked first.
    """
    s = _squash(text)
    if not s:
        return None
    kd, tight = _kd_forms(s)

    if KD_OTHER_THAN in kd or KD_OTHER_THAN in tight:
        return 0
    # a label truncated mid-phrase to a trailing "ds" is still "ke sivay":
    # that word occurs nowhere else in this vocabulary
    if kd.rstrip().endswith(" ds") or tight.endswith("ds"):
        return 0
    if KD_WOMAN in kd or KD_WOMAN in tight:
        return 1
    if KD_OTHER in kd or KD_OTHER in tight:
        return 0

    # An explicit "महिला" settles it before anything else, because Bihar writes
    # "पिछड़ा वर्ग(महिला)" - a backward-class seat reserved for a woman. Testing
    # the backward-class phrase first, as this did, returned None for all 38,430
    # of those across the six files: the caste read correctly, the woman marker
    # was dropped, and nothing would have flagged it because None is also what a
    # genuinely silent cell returns.
    if DEV_WOMAN.search(s):
        return 1
    # "अन्य पिछड़ा वर्ग" is a caste, not a gender, so the backward-class phrase
    # is still ruled out before "अन्य" is read as "other than woman".
    if DEV_BC.search(s):
        return None
    if DEV_OTHER in s:
        return 0

    letters = re.sub(r"[^a-z]", "", s.lower())
    if letters in CODES:
        return CODES[letters][1]
    if "wom" in letters:
        return 0 if "otherthan" in letters else 1
    # Uttar Pradesh's normalized English column writes "Female" and "Other
    # Backward Class - Female" rather than "Woman" - 24,000 seats of it in 2005
    # alone, every one of them reading as gender-not-stated until now. Tested
    # before any "male", which "female" contains.
    if "femal" in letters:
        return 1
    if "unreserv" in letters or "general" in letters or "open" in letters:
        return 0
    return None


def normalize_reservation(raw):
    """For states that print caste and gender in one cell.

    Returns (caste, woman, script) or None. States with separate columns should
    call caste_of() and woman_of() directly instead.
    """
    s = _squash(raw)
    if not s:
        return None
    script = "krutidev" if is_krutidev(s) else "latin"

    caste = caste_of(s)
    woman = woman_of(s)
    if caste is None and woman is None:
        return None
    # A bare caste name with no gender marker means caste-reserved but open to
    # anyone - that is how the 2016 gazettes write it.
    return caste or "NONE", woman if woman is not None else 0, script


def is_vacant(name):
    """True when nobody holds the seat - unfilled, or the election was
    countermanded. Official "elected" totals exclude these.
    """
    # Both sides are lowercased. Kruti Dev is case-sensitive mojibake, so
    # folding only one side silently stops "fjDr" from ever matching.
    n = _squash(name).lstrip("*").strip().lower()
    return not n or any(n.startswith(v.lower()) for v in VACANT)


def strip_unopposed(name):
    """A leading '*' marks a candidate elected unopposed."""
    n = _squash(name)
    return n.lstrip("*").strip(), n.startswith("*")


def label(caste, woman):
    """Canonical human-readable label."""
    prefix = {"SC": "SC", "ST": "ST", "BC": "BC", "NONE": ""}[caste or "NONE"]
    suffix = "Woman" if woman else "Other than Woman"
    return f"{prefix} {suffix}".strip()
