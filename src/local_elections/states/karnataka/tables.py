"""Turning Surya's HTML back into the rows the gazette printed.

Kept apart from the parser so it can be tested without a cache: everything here
is a pure function of a page's HTML, and every one of these rules was written
because the naive reading produced rows that looked fine and were wrong.

**Rows wrap, and Surya splits a wrapped row in two.** On Hunagund page 3 every
seat is two `<tr>` elements - the row, and a continuation carrying the tails of
whichever columns overflowed, right-aligned:

    19 | 19-ಕೂಡಲಸಂಗಮ | ಹಿಂದುಳಿದ 'ಅ'   | ಮಹಾಂತವ್ವ ... ಸಾ:      | ಭಾರತೀಯ
       |             | ವರ್ಗ (ಮಹಿಳೆ)   | ಬಿಸಲದಿನ್ನಿ ತಾ:ಹುನಗುಂದ | ರಾಷ್ಟ್ರೀಯ ಕಾಂಗ್ರೇಸ್

Read as two rows that is one seat with an unmatchable reservation and no party,
plus a phantom. Merged it is Backward-A (Woman), Congress. 20 of 741 rows in
the first 24 documents are continuations, so this is 2.7% phantom rows and a
similar number quietly mangled - and neither a row count nor a fill rate moves.

**Two layouts.** Most districts print five columns; Ballari and others add the
taluk's name as a second. The mapping keys on the table's width rather than on
its header text, because a continuation page carries no header at all and the
header that does exist is OCR'd like everything else.

That leaves the mapping unverified, so `looks_right` checks it rather than
assuming: the column claimed to be the reservation has to canonicalise on most
of its rows. A wrong mapping fails that immediately - names and party names do
not look like a fixed list of ten categories.
"""

import difflib
import re

# The decision is made in two stages, and the reason is that one of these
# distinctions is nothing like the others.
#
# The four families are far apart as strings, so the margin rule below applies
# cleanly. But Karnataka splits Backward Class into A and B, and those two
# differ by a single character - ಅ against ಬ - inside an otherwise identical
# phrase. Scored as one vocabulary they sit 0.07 apart, the margin rule refuses
# both, and 93 of the first 700 rows lose their category. Scored as a family
# first they are unambiguous.
#
# Keeping the one-character decision separate is also honest about the stakes:
# getting it wrong moves BC-A to BC-B, which changes caste_local and not
# caste_reservation, where confusing a family would change the seat's caste.
FAMILIES = {
    "ಸಾಮಾನ್ಯ": "NONE",
    "ಅನುಸೂಚಿತ ಜಾತಿ": "SC",
    "ಅನುಸೂಚಿತ ಪಂಗಡ": "ST",
    "ಹಿಂದುಳಿದ ವರ್ಗ": "BC",
}

BACKWARD_A = "ಅ"
BACKWARD_B = "ಬ"

WOMAN = "ಮಹಿಳೆ"

PARTIES = {
    "ಭಾರತೀಯ ಜನತಾ ಪಕ್ಷ": "Bharatiya Janata Party",
    "ಭಾರತೀಯ ರಾಷ್ಟ್ರೀಯ ಕಾಂಗ್ರೆಸ್": "Indian National Congress",
    "ಜನತಾದಳ (ಜಾತ್ಯಾತೀತ)": "Janata Dal (Secular)",
    "ಜನತಾದಳ (ಸಂಯುಕ್ತ)": "Janata Dal (United)",
    "ಬಹುಜನ ಸಮಾಜ ಪಕ್ಷ": "Bahujan Samaj Party",
    "ಕರ್ನಾಟಕ ಜನತಾ ಪಕ್ಷ": "Karnataka Janata Paksha",
    "ಪಕ್ಷೇತರ": "Independent",
    "ಸ್ವತಂತ್ರ": "Independent",
}

# A match has to be close *and* clearly closer than the runner-up. Both halves
# earn their place. Measured against the strings the OCR actually produced:
# "ಜನತಾ ವಕ್ಷ" scores 0.94 for BJP and "ಕಾಲ್ಯಾಣ ಕಾಂಗ್ರೆಸ್" 0.80 for Congress,
# while a column header scores 0.42 - so the ratio alone separates real
# readings from junk. The margin catches something the ratio cannot: a cell
# truncated to "ಭಾರತೀಯ" scores 0.55 against BJP and 0.38 against Congress, and
# **both parties begin with that word**. Guessing there would invent a party
# from a cell that genuinely does not say which one.
CLOSE = 0.75
MARGIN = 0.20


LINE_BREAK = "\u2028"


def clean(text, keep_breaks=False):
    """Cell text. `keep_breaks` preserves <br/> as a line separator.

    The gazette stacks the winner's name over their address inside one cell and
    Surya marks the stack with <br/>. Flattening it to a space threw away the
    only reliable boundary between the two - and looking for the address in
    words instead missed "ಬಿನ್" and "ಮನೆ ನಂ.", which left names of 220
    characters in a column the dictionary bounds at 60.
    """
    replacement = LINE_BREAK if keep_breaks else " "
    text = re.sub(r"<br\s*/?>", replacement, text or "")
    text = re.sub(r"<[^>]+>", " ", text)
    text = text.replace("‌", "").replace("‍", "")
    return re.sub(r"\s+", " ", text).strip()


def nearest(text, table):
    """The closest key in `table`, or None where nothing is close enough."""
    if not text:
        return None
    scored = sorted(
        ((difflib.SequenceMatcher(None, text, key).ratio(), key) for key in table),
        reverse=True,
    )
    best = scored[0]
    runner_up = scored[1][0] if len(scored) > 1 else 0.0
    if best[0] >= CLOSE and best[0] - runner_up >= MARGIN:
        return best[1]
    return None


def reservation(cell):
    """(caste, caste_local, woman) or None where the cell is not a category."""
    text = clean(cell)
    if not text:
        return None
    bracketed = " ".join(re.findall(r"\((.*?)\)", text))
    woman = bool(nearest(bracketed, {WOMAN: 1})) if bracketed else False
    stem = re.sub(r"\(.*?\)", " ", text)
    marker = (
        BACKWARD_A
        if BACKWARD_A in _quoted(stem)
        else (BACKWARD_B if BACKWARD_B in _quoted(stem) else "")
    )
    stem = re.sub(r"[\"\'“”‘’]", "", stem)
    stem = re.sub(r"\s+", " ", stem).strip()
    # the quoted letter is what A and B differ by, and it is settled separately
    stem = (
        re.sub(f"\\s*[{BACKWARD_A}{BACKWARD_B}]\\s*", " ", stem).strip()
        if stem.startswith("ಹಿಂದುಳಿದ")
        else stem
    )
    stem = re.sub(r"\s+", " ", stem).strip()
    key = nearest(stem, FAMILIES)
    if key is None:
        return None
    caste = FAMILIES[key]
    local = ""
    if caste == "BC":
        local = {BACKWARD_A: "BC-A", BACKWARD_B: "BC-B"}.get(marker, "")
    return caste, local, woman


def _quoted(text):
    """Whatever sits inside quotation marks - where A or B is printed."""
    return " ".join(re.findall(r"[\"\'“”‘’]\s*(.*?)\s*[\"\'“”‘’]", text))


def party(cell):
    """The party in English, or "" where the cell does not say which."""
    key = nearest(clean(cell), PARTIES)
    return PARTIES[key] if key else ""


def seat(cell):
    """(number, name) from "01-ನೆಲ್ಲೂಡಿ" or "3- ಸೂಳಿಕೇರಿ"."""
    text = clean(cell)
    match = re.match(r"^\s*(\d{1,3})\s*[-–—.]\s*(.*)$", text)
    if match:
        return int(match.group(1)), match.group(2).strip()
    return None, text


def rows_of(page):
    """Every <tr> on a page as a list of cleaned cell strings."""
    out = []
    for row in re.findall(r"<tr>(.*?)</tr>", page, re.S):
        cells = re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", row, re.S)
        out.append([clean(c) for c in cells])
    return out


def merge_continuations(rows, width):
    """Fold each wrapped tail back into the row above it.

    A continuation is narrower than the table and does not start with a serial
    number. Its cells belong to the *last* n columns - the serial and the seat
    number never wrap, so the overflow is always on the right.
    """
    merged = []
    for cells in rows:
        is_continuation = (
            merged
            and len(cells) < width
            and not re.match(r"^\s*\d", cells[0] if cells else "")
        )
        if is_continuation:
            offset = width - len(cells)
            for i, extra in enumerate(cells):
                if extra:
                    target = offset + i
                    if target < len(merged[-1]):
                        merged[-1][target] = f"{merged[-1][target]} {extra}".strip()
            continue
        merged.append(list(cells))
    return merged


# Which column is what, by how many columns the table has. Ballari and a few
# others print the taluk's name as a second column; most districts do not.
# Four shapes, and the fourth is not a narrowing of the others. Bidar, Koppal,
# Raichur and Yadgir - four contiguous northern districts - print no serial at
# all and put the winner *before* the reservation, where every other district
# puts it after. 15 documents and about 300 rows returned nothing at all until
# this existed, and none of them was an OCR failure: the model read them and
# the reader had no shape to put them in.
#
# Positional mapping is exactly what makes a swapped pair dangerous, which is
# why looks_right() exists - a winner column read as the reservation fails it
# on the first page, because people's names do not canonicalise to a list of
# four categories.
# A width can have more than one order, so this maps a width to *candidates*
# and looks_right() picks between them. Bidar and Raichur both print four
# columns and they are not the same four:
#
#     Bidar    seat | winner      | reservation | party
#     Raichur  seat | reservation | winner      | party
#
# Asserting one order per width filed ten documents as unreadable when the OCR
# had read them perfectly well. Using the guard to choose rather than only to
# veto costs nothing - a wrong order fails looks_right on the first page,
# because people's names do not canonicalise to a list of four categories.
LAYOUTS = {
    4: [
        {"seat": 0, "winner": 1, "reservation": 2, "party": 3},
        {"seat": 0, "reservation": 1, "winner": 2, "party": 3},
    ],
    5: [{"serial": 0, "seat": 1, "reservation": 2, "winner": 3, "party": 4}],
    6: [
        {"serial": 0, "taluk": 1, "seat": 2, "reservation": 3, "winner": 4, "party": 5}
    ],
}


def looks_right(rows, layout):
    """Whether the reservation column really is the reservation column.

    The mapping is positional, so it deserves a check that does not come from
    the same reasoning. A column of ten fixed categories canonicalises; a
    column of people's names or of party names does not, so a mapping applied
    to the wrong table fails this at once rather than producing a page of rows
    with an empty caste.
    """
    column = layout["reservation"]
    candidates = [r for r in rows if len(r) > column and r[column]]
    if not candidates:
        return False
    hits = sum(1 for r in candidates if reservation(r[column]))
    return hits >= max(1, len(candidates) // 2)


def table_rows(page):
    """(cells, layout) for every data row on a page, wrapped rows folded in."""
    rows = rows_of(page)
    if not rows:
        return []
    # The most common width among those we have a layout for - not the most
    # common width outright. A gazette page carries its masthead as a
    # three-column table of its own, and on Siruguppa page 1 those rows plus the
    # continuations outnumbered the data rows, so the plain mode chose 3, found
    # no layout and threw the page away. Seats 1 to 4 of that taluk went with
    # it, which is how the contiguity check found this.
    widths = [len(r) for r in rows if len(r) in LAYOUTS]
    if not widths:
        return []
    width = max(set(widths), key=widths.count)
    merged = merge_continuations(rows, width)
    data = [r for r in merged if len(r) == width]
    for layout in LAYOUTS[width]:
        if looks_right(data, layout):
            return [(r, layout) for r in data]
    return []


def dedupe(rows, key, better=None):
    """(kept, conflicts). A seat stated twice identically is one seat.

    Surya sometimes emits a page's table twice - Siruguppa's first page came
    back as seats 1,2,3,1,2,3 after its crop repair. Dropping repeats by seat
    number alone would also hide a real disagreement, so two rows that share a
    seat number and differ in what they say are kept apart and reported: that
    is a page read two ways, which is a finding, not a duplicate.

    `better` decides which of two disagreeing rows survives. Without it the
    first wins, and on Bidar's second page the first is the wrong one: seats 16
    and 17 each arrive as a garbled row - the winner read as "ವಿಶ್ವದ ಗಣಕಾಲವು",
    the party unresolvable - before the real ಮೆನ್ನಳ್ಳಿ and ನಾಗೂರಾ rows whose
    parties resolve cleanly. Order is not evidence, and keeping the first there
    kept the garbage and dropped the reading that is plainly right.
    """
    kept, seen, conflicts = [], {}, []
    for row in rows:
        identity = key(row)
        if identity is None:
            kept.append(row)
            continue
        if identity not in seen:
            seen[identity] = row
            kept.append(row)
        elif seen[identity] != row:
            held = seen[identity]
            conflicts.append((held, row))
            if better and better(row) > better(held):
                kept[kept.index(held)] = row
                seen[identity] = row
    return kept, conflicts
