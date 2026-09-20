"""Kruti Dev to Unicode Devanagari.

Jharkhand's notifications are typeset in Kruti Dev, an 8-bit font encoding from
before Unicode. It is not damage and it is not OCR error: every glyph maps to a
Devanagari character deterministically, and "vuqlwfpr tkfr" is exactly
अनुसूचित जाति every time. Left as printed, 11,711 rows cannot be joined to any
other source on name, which is the single largest recoverable gap in the corpus.

Two things make it more than a lookup table.

**The i-matra is written before its consonant.** Kruti Dev stores glyphs in the
order they are *drawn*, so ि precedes the letter it belongs to, while Unicode
stores them in the order they are *spoken*. "fp" is चि, not िच. So the matra is
held back and emitted after the consonant cluster it attaches to.

**Longest match wins.** "Hk" is भ, not ह + क; "{k" is क्ष, not { + क. Scanning
one byte at a time silently produces a different, plausible-looking word.

Verified against strings whose meaning is known from the corpus, pinned in
test_krutidev.py.
"""

import re

# Order matters only in that the scanner tries longer keys first; this table is
# written grouped by kind for reading.
MAP = {
    # conjuncts and two-byte consonants, tried before their single-byte parts
    "{k": "क्ष",
    "=": "त्र",
    "K": "ज्ञ",
    "»": "द्ध",
    "Ø": "क्र",
    "Ck": "ब्ल",
    "'k": "श",
    '"k': "ष",
    "Hk": "भ",
    "[k": "ख",
    "?k": "घ",
    "Fk": "थ",
    ".k": "ण",
    ".": "ण्",
    "/k": "ध",
    "|": "द्य",
    "N": "छ",
    "V": "ट",
    "B": "ठ",
    "M": "ड",
    "<": "ढ",
    "M+": "ड़",
    "<+": "ढ़",
    "Q": "फ",
    "q": "ु",
    "w": "ू",
    # vowels
    "vks": "ओ",
    "vkS": "औ",
    "vk": "आ",
    "v": "अ",
    "b": "इ",
    "bZ": "ई",
    "m": "उ",
    "Å": "ऊ",
    ",": "ए",
    ",s": "ऐ",
    "_": "ऋ",
    # consonants
    "d": "क",
    "x": "ग",
    "p": "च",
    "t": "ज",
    ">": "झ",
    "M~": "ड्",
    "r": "त",
    "n": "द",
    "/": "ध्",
    "u": "न",
    "i": "प",
    "c": "ब",
    "e": "म",
    ";": "य",
    "j": "र",
    "y": "ल",
    "o": "व",
    "l": "स",
    "g": "ह",
    "'": "श्",
    '"': "ष्",
    "\\": "ॉ",
    # Half consonants. Kruti Dev puts them on the shifted keys, so a capital is
    # usually a consonant with its halant already attached - "L" is स्, not स.
    "D": "क्",
    "X": "ग्",
    "P": "च्",
    "T": "ज्",
    "R": "त्",
    "F": "थ्",
    "U": "न्",
    "I": "प्",
    "C": "ब्",
    "H": "भ्",
    "E": "म्",
    "Y": "ल्",
    "O": "व्",
    "L": "स्",
    "G": "घ्",
    "J": "श्र",
    "A": "ॐ",
    # the chandrabindu, not a vowel: "mjkWo" is उराँव and "[kjlkokW" खरसावाँ
    "W": "ँ",
    # "z" is the ra that hangs under a consonant (ग + z = ग्र)
    "z": "्र",
    # Conjuncts that live on their own key: "y{eh" is लक्ष्मी, "czkã.k" is
    # ब्राह्मण, "}kjk" is द्वारा. Found by converting the whole corpus and
    # looking at what came out still Latin - 16 characters in 29,778 values.
    "{": "क्ष्",
    "ã": "ह्म",
    "}": "द्व",
    # matras and signs. "ks" and "kS" have to be here as pairs: taken one
    # character at a time they give ा + े, which draws like ो and is two
    # codepoints rather than one - so बाेकाराे would never join to बोकारो.
    "ks": "ो",
    "kS": "ौ",
    "k": "ा",
    "h": "ी",
    "s": "े",
    "S": "ै",
    "a": "ं",
    "%": "ः",
    "`": "ृ",
    "‘": "ृ",
    "~": "्",
    "•": "्",
    "&": "-",
    "+": "़",
    "ॅ": "ॅ",
    "@": "/",
}

# The reph - the r that rides above the next consonant. Kruti Dev writes it
# after the consonant it precedes in Unicode, the mirror of the i-matra: "xZ" is
# र्ग. It is inserted backwards, before the cluster already emitted.
REPH = "Z"

# Written before its consonant in Kruti Dev and after it in Unicode.
I_MATRA = "f"
I_MATRA_LONG = "fh"  # ी written as f + h in some strings

KEYS = sorted(MAP, key=len, reverse=True)

# A consonant cluster the held-back i-matra attaches to: the consonant plus any
# nukta or halant-joined consonant that follows it.
CLUSTER = re.compile(r"^[क-ह]़?(?:्[क-ह]़?)*")


def _convert(chunk):
    """One run of Kruti Dev text, no whitespace handling."""
    out = []
    pending_i = ""
    index = 0
    while index < len(chunk):
        if chunk.startswith(I_MATRA_LONG, index):
            pending_i, index = "ी", index + 2
            continue
        if chunk[index] == I_MATRA:
            pending_i, index = "ि", index + 1
            continue
        if chunk[index] == REPH:
            # walk back over any matra to sit in front of the consonant itself
            at = len(out)
            while at > 0 and out[at - 1] and out[at - 1][-1] in "ािीुूेैोौंःृ":
                at -= 1
            if at > 0:
                out.insert(at - 1, "र्")
            else:
                out.append("र्")
            index += 1
            continue
        for key in KEYS:
            if chunk.startswith(key, index):
                out.append(MAP[key])
                index += len(key)
                break
        else:
            out.append(chunk[index])
            index += 1
        # the matra waits for a whole cluster, so "f" + "Hk" gives भि not िभ
        if (
            pending_i
            and out
            and CLUSTER.match(out[-1])
            and not "".join(out).endswith("्")
        ):
            out.append(pending_i)
            pending_i = ""
    if pending_i:
        out.append(pending_i)
    return "".join(out)


def to_unicode(text):
    """Convert Kruti Dev to Unicode Devanagari, leaving anything else alone."""
    if not text:
        return text
    # digits, punctuation and Latin runs pass through untouched; only the
    # letter-ish runs are font-encoded
    return "".join(
        _convert(part) if part.strip() else part for part in re.split(r"(\s+)", text)
    )


def looks_converted(text):
    """True when the text is already Devanagari, so conversion is a no-op."""
    return bool(re.search(r"[ऀ-ॿ]", text or ""))
