"""No one person won a tenth of the seats.

Written because a name field can be wrong in a way that every other check calls
healthy. `winner` was published for 17,115 Jharkhand rows in Kruti Dev while the
`script` column said Unicode: the field was populated, the row count was right,
the reservation shares were right, and every gate passed. What it cost was
invisible per row and obvious in aggregate - अनिता देवी appeared 92 times as
`vfurk nsoh` and 55 times as अनिता देवी, so the same woman counted as two people
and anything joining on name was quietly wrong.

The other failures this guards are the ones that put something which is not a
name into a name column: a table label ("ग्राम पंचायत"), a page header
("Election for the post of Sarpanch"), a phone number. Each shows up the same
way - one value repeating far more than a person plausibly could.

A real name does repeat. देवी is a common surname and अनिता देवी legitimately
wins 147 seats across a state, so the threshold is deliberately loose: this is
a smoke alarm for a field that has stopped holding names, not an attempt to
detect duplicates. Placeholders the sources genuinely print - रिक्त, vacant, and
"no nomination received" - are named and excluded rather than allowed to raise
the ceiling for everything else.
"""

import collections
import csv
import re

import pytest

from local_elections.paths import ROOT

DEVANAGARI = re.compile(r"[ऀ-ॿ]")

# Not names, and the documents say so: a seat with no winner declared.
PLACEHOLDERS = {"रिक्त", "नामांकन प्राप्त नहीं हुआ", "-", "–", "—"}

# One name may hold at most this share of a slice's seats. 5% of Jharkhand's
# 26,000 rows is 1,300 seats for one person, which no name approaches - the
# most common real name reaches 0.55%. The Kruti Dev split did not trip this
# either; what trips it is a label or a header landing in the column, which is
# the failure that has actually happened twice.
CEILING = 0.05

FILES = sorted((ROOT / "data" / "jharkhand").glob("*_reservation_2015.csv"))


def winners(path):
    with path.open(encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            value = (row.get("winner") or "").strip()
            if value and value not in PLACEHOLDERS:
                yield value


@pytest.mark.parametrize("path", FILES, ids=lambda p: p.stem)
def test_no_single_name_dominates(path):
    counts = collections.Counter(winners(path))
    if sum(counts.values()) < 100:
        pytest.skip("too few winners for a share to mean anything")
    name, n = counts.most_common(1)[0]
    share = n / sum(counts.values())
    assert share <= CEILING, (
        f"{name!r} holds {share:.1%} of {path.stem} winners ({n:,} of "
        f"{sum(counts.values()):,}). A name column that repeats like this is "
        f"usually holding a label, a header or a placeholder rather than a "
        f"person - add it to PLACEHOLDERS only if the source really prints it."
    )


@pytest.mark.parametrize("path", FILES, ids=lambda p: p.stem)
def test_winners_are_not_left_in_a_font_encoding(path):
    """The bug this file was written for: names shipped as Kruti Dev bytes.

    Checked as a share rather than absolutely, because a handful of rows
    legitimately carry a dash or a Latin token, and because the point is to
    notice a whole district reverting rather than to police individual values.
    """
    values = list(winners(path))
    if len(values) < 100:
        pytest.skip("too few winners to measure")
    unconverted = [v for v in values if not DEVANAGARI.search(v)]
    share = len(unconverted) / len(values)
    assert share < 0.01, (
        f"{share:.0%} of {path.stem} winners carry no Devanagari - "
        f"e.g. {unconverted[:3]}. Kruti Dev is a font encoding, not damage: "
        f"krutidev.to_unicode converts it exactly, and leaving it means the "
        f"same person counts as two depending on which district they are in."
    )
