"""Parse Andhra Pradesh gram panchayat reservation, 2020.

One gazette per district. Pages 10 onward hold "Details of Reservations for the
Office of Sarpanches & Ward Members", one line per gram panchayat:

    44 Alamuru ALAMURU sc(w) t4 Bc (w) UR (W) SC sc (w) BC UR (W) UR ...
    |  |       |       |     |  |
    |  mandal  GP      |     |  the wards, one category each
    |                  |     number of wards
    serial             the sarpanch's own reservation

...but only in some districts. Krishna prints the count before the sarpanch's
cell on some of its pages and after it on others, and Nellore puts a revenue
division in front of the mandal and numbers the panchayats within it.

Two things make this the hardest state in the repo:

**The text layer is OCR output, and it is wrong in places.** `5C` for SC, `8c`
for BC, `t4` for 14, `72` for 12, `UR {W)` with a brace. The category vocabulary
is closed - UR, SC, ST, BC, each optionally "(W)" - so the damage is repairable,
but a repair that is wrong looks exactly like one that is right. Every row
therefore carries `ocr_repaired`, counting how many of its cells had to be
mended, so the doubtful rows can be found again.

**There are no ruled tables**, so the line is read positionally. The mandal and
the gram panchayat are separated only by case: the mandal is Title Case and the
gram panchayat is UPPERCASE.

Writes data/ap/{sarpanch,ward}_reservation_2020.{csv,jsonl}.
"""

import argparse
import collections
import re

from local_elections.common import emit
from local_elections.common.normalize import (
    label,
    normalize_reservation,
)
from local_elections.common.runlog import command, get_logger
from local_elections.paths import ROOT
from local_elections.states.ap import harvest, parse_kadapa

LOGGER = get_logger(__name__)

AP = ROOT / "data" / "ap" / "2020_res_gp"
OCR_CACHE = ROOT / "data" / "ap" / "ocr"
TEXT_CACHE = ROOT / "data" / "ap" / "extracted"

COLUMNS = [
    "state",
    "year",
    "district",
    "block",
    "gram_panchayat",
    "serial",
    "ward_no",
    "tier",
    "tier_local",
    "reservation",
    "caste_reservation",
    "woman_reserved",
    "ward_count",
    "wards_parsed",
    "ward_list_complete",
    "printings",
    "printings_agree",
    "gender_stated",
    "ocr_repaired",
    "reservation_raw",
    "reservation_raw_original",
    "corrected",
    "correction_for_raw",
    "correction_read_as_raw",
    "correction_source_page",
    "script",
    "text_source",
]

DISTRICTS = harvest.DISTRICTS

# A reservation token, tolerant of the OCR substitutions actually observed:
# S<->5, B<->8, and the bracket around "W" appearing as ( { [ or mismatched.
CATEGORY = re.compile(
    r"(?<![A-Za-z0-9])(?:[Uu][Rr]|[Ss5][CcTt]|[Bb8][Cc]|[Gg][Nn])"
    # The gender marker is "(W)" in most districts, but Anantapur, Nellore and
    # Prakasam mark the open seats explicitly too - UR(G), SC/G, BC/W - and the
    # OCR renders the bracket three ways. Two of them were being dropped:
    #
    #   UR(W)   bracket     35,971 across the five districts
    #   UR-W    hyphen       1,937   <- matched only "UR", marker lost
    #   URW     run on       1,393   <- likewise
    #
    # Losing the marker does not blank the gender, it silently records the seat
    # as not reserved for a woman. That is 6,422 ward rows across the three
    # districts that mark both, and it is why Anantapur read 38% women against a
    # statutory half while East Godavari - which marks women only, so a bare
    # code really is a man - read 50%.
    #
    # Both added forms only ever extend a match that already happened at the
    # same position, so no new matches are created; and the run-on form must be
    # adjacent, so "UR WARD" cannot become a woman-reserved seat.
    r"(?:\s*[({\[/¢]\s*[WwVvGgMm]\s*[)}\]]?"
    r"|\s*[-\u2013\u2014]\s*[WwGgMm](?![A-Za-z])"
    r"|[WwGgMm](?![A-Za-z])"
    # A trailing bracket with nothing readable in it is a mangled "(G)":
    # Prakasam renders it URC), sc(c), uri), Scie). Left unmatched, those rows
    # look like a marker that vanished, and filtering them out as "gender not
    # stated" then over-selects the women's seats - Prakasam read 66% women
    # that way. (G) is damaged far more often than (W) here, so the two cannot
    # be treated symmetrically.
    r"|\s*[({\[/¢]?\s*[CcGgei€]{1,2}\s*[)}\]])?",
    re.X,
)

# A gram panchayat name: at least one run of letters. Used to tell a real record
# from an abstract row, which is numbers all the way across.
HAS_NAME = re.compile(r"[A-Za-z]{3}")

# a ward count, with the digit confusions this OCR makes: l/I->1, t->1, O->0
COUNT = re.compile(r"^[0-9tTlIiOo]{1,3}$")

CANONICAL = {"5": "S", "8": "B", "0": "O"}

# the gazette header numbers ward columns 1..20
MAX_WARDS = 20

REVIEWED_LINE_SOURCES = {
    "atp_res_gp.pdf",
    "est_res_gp.pdf",
    "kri_res_gp.pdf",
    "knl_res_gp.pdf",
    "nlr_res_gp.pdf",
    "pkm_res_gp.pdf",
    "wg_res_gp.pdf",
}


class UnreviewedSource(Exception):
    """A retained artifact whose row interpretation has not passed review."""


def repair(token):
    """Return (clean token, was_repaired). Only the closed category vocabulary
    is repaired - never a name, where a wrong guess would be undetectable.
    """
    original = token
    fixed = re.sub(r"\s+", " ", token).strip()
    fixed = "".join(CANONICAL.get(c, c) for c in fixed)
    fixed = (
        fixed.replace("{", "(").replace("[", "(").replace("}", ")").replace("]", ")")
    )
    if "(" in fixed and ")" not in fixed:
        fixed += ")"
    # a closing bracket carrying no W is an open seat whose marker was mangled
    if re.search(r"[)}\]]$", fixed) and not re.search(r"[WwVvGgMm]", fixed):
        fixed = re.sub(r"^([A-Za-z]{2}).*$", r"\1(G)", fixed)
    return fixed, fixed.upper().replace(" ", "") != original.upper().replace(" ", "")


def digits(token):
    """A ward count as OCR left it: "t4" is 14, "72" is 12 in this font."""
    mapped = token.translate(str.maketrans("tTlIiOo", "1110000"))
    if mapped.isdigit() and int(mapped) > MAX_WARDS and mapped.startswith("7"):
        # "72" and "74" are 12 and 14 in this font. Only rewrite when the value
        # is otherwise impossible - the header numbers wards 1..20 - so a
        # genuine 7 is never touched.
        mapped = "1" + mapped[1:]
    # Anything still outside 1..20 is not a ward count. It is usually the next
    # record's serial number, picked up because Anantapur's gazette is
    # sarpanch-only and has no ward column for the reader to land on. Returning
    # blank says "not stated", which is true; returning 202 would not be.
    if not mapped.isdigit() or not (1 <= int(mapped) <= MAX_WARDS):
        return ""
    return mapped


STANDALONE = re.compile(r"(?:(?<=\s)|^)([0-9tTlIiOo]{1,3})(?=\s|$)")

# Every form the closed category vocabulary can legitimately take. Used only to
# recognise an OCR-damaged sarpanch code in the one position the layout says a
# code must be - never to invent one anywhere else.
CANONICAL_CODES = [
    f"{c}{g}" for c in ("UR", "SC", "ST", "BC", "GN") for g in ("", "(W)", "(G)", "(M)")
]


def _distance(a, b):
    """Levenshtein, for deciding whether a damaged token is still that code."""
    if a == b:
        return 0
    previous = list(range(len(b) + 1))
    for i, x in enumerate(a, 1):
        current = [i]
        for j, y in enumerate(b, 1):
            current.append(
                min(previous[j] + 1, current[j - 1] + 1, previous[j - 1] + (x != y))
            )
        previous = current
    return previous[-1]


def as_category(text, limit=1):
    """Read `text` as a reservation code, or return None.

    The gazette's own layout tells us a code sits here, and the vocabulary is
    fifteen strings long, so a token that is nearly one of them almost certainly
    is it: "uUR(W)" is UR(W) with a doubled letter, "sccw)" is SC(W) with the
    bracket read as a c. Without this the token fails to match, the parser takes
    the *next* code on the line - which belongs to ward 1 - and records it as
    the sarpanch's. That is not a missing value but a wrong one, and it is
    invisible in the output: Krishna's Pinapaka came out "Other than Woman"
    when the page says UR(W).

    `limit` is deliberately tight. Beyond one edit the guess stops being
    recoverable and the row is better dropped than silently misfiled.
    """
    # a hyphen or a run-on is the same marker as a bracket, so normalise before
    # measuring distance or "UR-W" reads as two edits from UR(W) and is rejected
    text = re.sub(r"[-\u2013\u2014]\s*([WwGgMm])(?![A-Za-z])", r"(\1)", text or "")
    text = re.sub(r"(?<=[A-Za-z])([WwGgMm])$", r"(\1)", text)
    squashed = re.sub(r"[^A-Za-z()]", "", text.upper())
    squashed = squashed.replace("{", "(").replace("[", "(")
    if not squashed:
        return None
    best, best_distance = None, limit + 1
    for code in CANONICAL_CODES:
        d = _distance(squashed, code)
        if d < best_distance:
            best, best_distance = code, d
    return best if best_distance <= limit else None


def scan_line(line):
    """Pick a record apart as far as the layout-independent facts go."""
    # Tesseract renders the table rules as pipes and stray brackets; they carry
    # no information and would otherwise break the category tokens apart.
    line = re.sub(r"[|]+", " ", line)
    line = re.sub(r"\s+", " ", line).strip()
    # the serial itself is OCR-damaged in places ("4a" for 48)
    head = re.match(r"^(\d{1,4}[A-Za-z]?)\s+(.*)$", line)
    if not head:
        return None
    rest = head.group(2)

    matches = list(CATEGORY.finditer(rest))
    if not matches:
        return None

    # Distinguishing a real record from an abstract row cannot be done by
    # counting categories: Anantapur's gazette is sarpanch-only, with no ward
    # columns at all, so its records carry exactly one. What separates them is
    # that a record names a place and an abstract row is numbers across.
    names = rest[: matches[0].start()].strip()
    if not names or not HAS_NAME.search(names):
        return None
    return {"serial": head.group(1), "names": names, "rest": rest, "matches": matches}


# A code with one stray character stuck to its front, which is how this OCR
# renders a table rule that touched the text: "JUR(W)" for UR(W), "lurcwy" for
# UR(W). Used only to fill a shortfall the record itself declares - see
# recover_wards - never to find codes in the first place, because with the word
# boundary relaxed this also matches inside ordinary names ("Sur-" would give
# UR) and would start inventing wards out of place names.
LOOSE = re.compile(
    r"(?<![A-Za-z0-9])[A-Za-z]?(?:[Uu][Rr]|[Ss5][CcTt]|[Bb8][Cc]"
    r"|[Gg][Nn])\s*(?:[({\[/]\s*[WwVvGg]\s*[)}\]]?)?"
    # the match has to end at a word boundary as well as start
    # at one, or "Surareddypalem" yields a UR ward out of a
    # place name - which a truncated line can put in this region
    r"(?![A-Za-z])"
)


# A cell that no longer looks like a code at all. Used only after the looser
# pattern has found nothing, and only up to the shortfall the record declares.
ORPHAN = re.compile(
    r"(?<![A-Za-z])[A-Za-z]{2}(?:\s*[({\[/]\s*[WwGg]\s*[)}\]]?)?"
    r"(?![A-Za-z])"
)


def recover_wards(region, spans, shortfall):
    """Find wards the strict pattern missed, up to the number declared missing.

    A ward whose code did not match is not a blank in the output - the ward
    simply is not there, and the row count is short by one with nothing to say
    why. Nellore loses one ward on a quarter of its records that way.

    The record states how many wards it has, so the search is bounded by an
    external fact rather than by how many candidates a looser pattern can find:
    at most `shortfall` are taken, and each still has to be within one edit of a
    real code. If more candidates turn up than are missing, none are taken -
    that means the shortfall is not understood and guessing would be worse.
    """
    if shortfall <= 0:
        return []
    found = []
    for m in LOOSE.finditer(region):
        if any(m.start() < end and start < m.end() for start, end in spans):
            continue
        code = as_category(m.group(0))
        if code:
            found.append((m.start(), code))
    if found:
        return found if len(found) <= shortfall else []

    # Nothing that still looks like a code. Some cells are mangled past the
    # pattern entirely - Prakasam's "Ss" for SC, "es" for something now
    # unreadable - and those are not truncation, they are one cell the scan
    # lost. Any short token is considered, but only because the record states
    # how many wards it has: at most `shortfall` are taken, each still has to
    # be within one edit of a real code, and finding more candidates than are
    # missing means the shortfall is not understood and none are taken.
    for m in ORPHAN.finditer(region):
        if any(m.start() < end and start < m.end() for start, end in spans):
            continue
        code = as_category(m.group(0))
        if code:
            found.append((m.start(), code))
    return found if 0 < len(found) <= shortfall else []


def apply_layout(record):
    """Fill in the fields whose position depends on the layout.

    The districts do not agree on the column order, and neither does a single
    district with itself. Krishna's page 12 prints

        serial  mandal  panchayat  SARPANCH  count  ward...

    and its page 13 prints

        serial  mandal  panchayat  count  SARPANCH  ward...

    which is why this is decided per record rather than per document: these
    gazettes are compiled from sheets typeset mandal by mandal.

    The signal is where the standalone number falls. When it ends the name
    segment the count comes first, and the sarpanch's own cell is whatever
    follows - the position where a damaged code would otherwise be lost
    entirely. When a place name follows the number instead, it is Nellore's
    panchayat index, the one case where a district marks the boundary between
    the two names explicitly. Either reading is checked afterwards against the
    count the record states, via ward_list_complete.
    """
    names, rest, matches = record["names"], record["rest"], record["matches"]
    found = list(STANDALONE.finditer(names))
    trailing = names[found[-1].end() :].strip() if found else ""
    count_first = bool(found) and (not trailing or bool(as_category(trailing)))
    place, panchayat, sarpanch_raw, ward_count = names, "", "", ""
    repaired = recovered = 0

    if count_first:
        last = found[-1]
        ward_count = digits(last.group(1))
        place = names[: last.start()].strip()
        mended = as_category(trailing)
        if mended:
            sarpanch_raw, repaired = mended, 1
            wards = [m.group(0) for m in matches]
        else:
            sarpanch_raw = matches[0].group(0)
            wards = [m.group(0) for m in matches[1:]]
    else:
        sarpanch_raw = matches[0].group(0)
        wards = [m.group(0) for m in matches[1:]]
        tail = rest[matches[0].end() :].strip()
        token = tail.split(" ")[0] if tail else ""
        ward_count = digits(token) if COUNT.match(token or "") else ""
        if found:
            # Nellore numbers the panchayats within each mandal and prints that
            # number between the two names, which is the only place any district
            # marks the boundary explicitly. Where it is there, use it.
            last = found[-1]
            after = names[last.end() :].strip()
            if after and HAS_NAME.search(after):
                place, panchayat = names[: last.start()].strip(), after

    # Bound the ward list by the count the record itself states. Reassembling
    # wrapped records means the buffer also picks up page furniture and stray
    # fragments, which pushed the ward total to 134% of what the gazette says
    # it should be. Trusting the document's own count fixes the over-capture
    # and makes any shortfall measurable rather than hidden by a surplus.
    if ward_count.isdigit() and int(ward_count) > 0:
        spans = [m.span() for m in matches]
        start = matches[0].start() if count_first else matches[0].end()
        extra = recover_wards(
            rest[start:],
            [(a - start, b - start) for a, b in spans],
            int(ward_count) - len(wards),
        )
        if extra:
            ordered = [
                (m.start() - start, m.group(0)) for m in matches if m.start() >= start
            ] + extra
            # matches before `start` are the sarpanch's own cell, already
            # excluded by the offset filter above - do not drop one again
            wards = [c for _, c in sorted(ordered)]
            recovered = len(extra)
        wards = wards[: int(ward_count)]
    else:
        # No readable count on this record. The gazette's own header numbers
        # wards 1 to 20, so that is the ceiling; without it the reassembled
        # buffer keeps absorbing page furniture.
        wards = wards[:MAX_WARDS]

    record.update(
        {
            "mandal": "",
            "place": place,
            "panchayat": panchayat,
            "sarpanch_raw": sarpanch_raw,
            "ward_count": ward_count,
            "ward_raws": wards,
            "code_repaired": repaired,
            "wards_recovered": recovered,
        }
    )
    return record


MIN_GROUP = 3


def mandal_vocabulary(names):
    """Learn the mandal names from how the records are ordered.

    The gazette lists panchayats grouped by mandal, so the mandal name repeats
    down a run of consecutive records while the panchayat name does not. Every
    first word that opens such a run is therefore a mandal name.

    Whether the mandal is one word or two has to be decided once for the whole
    document, not run by run. "Anantapur Rural" is a real two-word mandal and
    every single record under it repeats both words; "Atmakur B.Yaleru" is
    mandal Atmakur with a two-word panchayat, and looking only at a few adjacent
    records cannot tell the two apart - three consecutive B.Yaleru hamlets look
    exactly like a two-word mandal. Deciding it across every record that shares
    the first word can: Atmakur's second word varies, Anantapur's never does.
    """
    groups = collections.defaultdict(list)
    for name in names:
        words = name.split()
        if words:
            groups[words[0].lower()].append(words)

    vocabulary = {}
    for key, group in groups.items():
        vocabulary[key] = group[0][0]
        second = {w[1].lower() for w in group if len(w) > 1}
        if (
            len(group) >= MIN_GROUP
            and len(second) == 1
            and all(len(w) > 2 for w in group)
        ):
            vocabulary[key + " " + second.pop()] = " ".join(group[0][:2])
    return vocabulary


def split_names(records):
    """Separate the mandal from the panchayat where the line itself cannot.

        406 Kalyandurg Garudapuram      ->  Kalyandurg | Garudapuram
        407 Kalyandurg Golla            ->  Kalyandurg | Golla
        408 Kalyandurg Hulikal          ->  Kalyandurg | Hulikal

    Without this the two columns come out identical, which is how Anantapur's
    block and gram_panchayat ended up holding the same string. The vocabulary is
    built over the whole document rather than a page, so a mandal that happens
    to have one record on a page still gets split - it was learnt elsewhere.
    """
    pending = [r for r in records if not r["panchayat"]]
    vocabulary = mandal_vocabulary([r["place"] for r in pending])
    for record in pending:
        words = record["place"].split()
        record["mandal"], record["panchayat"] = "", record["place"]
        # longest match wins, so a two-word mandal beats its own first word
        for size in (2, 1):
            if len(words) < size:
                continue
            key = " ".join(w.lower() for w in words[:size])
            if key in vocabulary:
                record["mandal"] = vocabulary[key]
                record["panchayat"] = " ".join(words[size:]) or vocabulary[key]
                break

    # Where the panchayat name was already known, everything before it is the
    # mandal - except that Nellore prints the revenue division in front of it.
    # A division spans several mandals, so its name heads more than one distinct
    # place string, while a genuine two-word mandal like "Anantapur Rural" heads
    # exactly one.
    known = [r for r in records if not r["mandal"] and r["panchayat"]]
    spread = collections.defaultdict(set)
    for record in known:
        words = record["place"].split()
        if words:
            spread[words[0].lower()].add(record["place"])
    divisions = {word for word, places in spread.items() if len(places) > 1}
    for record in known:
        words = record["place"].split()
        # A division whose own name is misread heads only the one place string
        # and so never reaches the test above - "Nellcre Podalakur" for Nellore
        # Podalakur. Allowing a single edit against a division already learnt
        # recognises it. This picks where the name starts; it does not rewrite
        # the name, which stays as printed.
        if len(words) > 1 and (
            words[0].lower() in divisions
            or any(_distance(words[0].lower(), d) <= 1 for d in divisions)
        ):
            words = words[1:]
        record["mandal"] = " ".join(words)


def _records(lines):
    """Reassemble gram panchayat records that the layout split across lines.

    A long ward list wraps, so a record often arrives as

        53 Alamuru MOOLASTANAM
        8C
        5C sc (w) UR

    Reading line by line finds the first fragment, fails to see any category on
    it, and drops the panchayat entirely - which is how East Godavari came out
    at 748 of its 1,103 gram panchayats. So a line that opens a record is held
    open and the continuation lines are appended until the next record starts.
    """
    opener = re.compile(r"^\s*\d{1,4}[A-Za-z]?\s+[A-Za-z]")
    normalized = []
    source_lines = list(lines)
    skip = False
    for index, raw in enumerate(source_lines):
        if skip:
            skip = False
            continue
        line = re.sub(r"[|]+", " ", raw)
        line = re.sub(r"\s+", " ", line).strip()
        following = ""
        if index + 1 < len(source_lines):
            following = re.sub(r"\s+", " ", source_lines[index + 1]).strip()
        # One Kurnool page stores each serial after the rest of its row in the
        # PDF text order. Reorder only the exact, externally checkable shape:
        # a category-bearing place row immediately followed by a bare serial.
        if (
            line
            and line[0].isalpha()
            and CATEGORY.search(line)
            and re.fullmatch(r"\d{1,4}[A-Za-z]?", following)
        ):
            normalized.append(f"{following} {line}")
            skip = True
        else:
            normalized.append(line)
    buffer = ""
    for line in normalized:
        # Strip the table rules here, not only in parse_line. Our OCR renders
        # them as pipes, so a row arrives as "44 |Alamuru ALAMURU ..." and the
        # opener - which expects a letter after the serial - never matches.
        # That silently cut East Godavari from 10,226 rows to 83.
        if not line:
            continue
        if opener.match(line):
            if buffer:
                yield buffer
            buffer = line
        elif buffer:
            buffer = f"{buffer} {line}"
    if buffer:
        yield buffer


def source_text(path):
    """Read a retained extraction artifact, never the source PDF directly.

    The layer these gazettes ship is itself OCR and gets digits and letters
    wrong in the category cells - 5C, 8c, t4. ``ocr.py`` re-renders and reads
    scanned pages; ``extract.py`` retains usable embedded text. Keeping both
    outside the parser means extraction can be inspected and replaced without
    changing row semantics.
    """
    if path.name not in REVIEWED_LINE_SOURCES:
        raise UnreviewedSource(f"no reviewed line parser for {path.name}")
    cached = OCR_CACHE / f"{path.stem}.txt"
    if cached.exists():
        return cached.read_text(encoding="utf-8"), "ocr"
    cached = TEXT_CACHE / f"{path.stem}.txt"
    if cached.exists():
        return cached.read_text(encoding="utf-8"), "embedded"
    raise FileNotFoundError(f"no retained extraction for {path.name}")


def parse_kadapa_pdf(path):
    """Emit Kadapa rows after its positioned parser and errata contracts pass."""
    sources = emit.archived(AP)
    rows = []
    for record in parse_kadapa.apply_errata():
        serial = parse_kadapa._printed_number(record["serial_raw"])
        base = {
            "state": "Andhra Pradesh",
            "year": "2020",
            "district": DISTRICTS["kdp"],
            "block": record["block"],
            "gram_panchayat": record["gram_panchayat"],
            "serial": str(serial),
            "ward_count": len(record["ward_raws"]),
            "wards_parsed": len(record["ward_raws"]),
            "ward_list_complete": 1,
            "printings": 1,
            "printings_agree": "",
            "gender_stated": 1,
            "text_source": "embedded_positioned",
        }

        def make_row(raw, ward_no, tier, tier_local, correction=None):
            parsed = parse_kadapa.category(raw)
            if parsed is None:
                raise ValueError(f"unreadable Kadapa reservation cell: {raw!r}")
            fixed, repaired = parsed
            normalized = normalize_reservation(fixed)
            if normalized is None:
                raise ValueError(f"unrecognized Kadapa reservation cell: {raw!r}")
            caste, woman, script = normalized
            correction = correction or {}
            return emit.stamp(
                dict(
                    base,
                    ward_no=ward_no,
                    tier=tier,
                    tier_local=tier_local,
                    reservation=label(caste, woman),
                    caste_reservation=caste,
                    woman_reserved=woman,
                    ocr_repaired=repaired,
                    reservation_raw=raw,
                    reservation_raw_original=correction.get(
                        "reservation_raw_original", ""
                    ),
                    corrected=correction.get("corrected", 0),
                    correction_for_raw=correction.get("correction_for_raw", ""),
                    correction_read_as_raw=correction.get("correction_read_as_raw", ""),
                    correction_source_page=correction.get("correction_source_page", ""),
                    script=script,
                ),
                path,
                record["source_page"],
                ROOT,
                archive=sources,
            )

        rows.append(
            make_row(
                record["sarpanch_raw"],
                "",
                "gp_head",
                "sarpanch",
                record.get("head_correction"),
            )
        )
        corrections = record.get("ward_corrections", {})
        rows.extend(
            make_row(raw, ward_no, "gp_ward", "ward", corrections.get(ward_no))
            for ward_no, raw in enumerate(record["ward_raws"], 1)
        )
    if len(rows) != 8_710:
        raise ValueError(f"Kadapa expected 8,710 seat rows, parsed {len(rows)}")
    return rows


def parse_pdf(path):
    if path.name == "kdp_res_gp.pdf":
        return parse_kadapa_pdf(path)
    district = DISTRICTS.get(path.stem.split("_")[0], path.stem)
    text, origin = source_text(path)
    sources = emit.archived(AP)
    rows = []
    # the whole document is parsed before any row is emitted, because the mandal
    # names are learnt from the order of the records rather than from any one
    # line - see split_names()
    document = []
    for page_no, page in enumerate(text.split("\f"), 1):
        for line in _records(page.split("\n")):
            parsed = scan_line(line)
            if parsed:
                document.append((page_no, parsed))
    scanned = [r for _, r in document]
    for record in scanned:
        apply_layout(record)
    split_names(scanned)
    for page_no, parsed in document:
        fixed, repaired = repair(parsed["sarpanch_raw"])
        # the sarpanch's own cell only - wards recovered for this record are
        # counted on the ward rows, not here
        repaired = int(repaired) + parsed["code_repaired"]
        got = normalize_reservation(fixed)
        if not got:
            continue
        caste, woman, script = got
        base = {
            "state": "Andhra Pradesh",
            "year": "2020",
            "district": district,
            "block": parsed["mandal"],
            "gram_panchayat": parsed["panchayat"],
            "ward_count": parsed["ward_count"],
            "wards_parsed": len(parsed["ward_raws"]),
            "serial": parsed["serial"],
            "script": script,
            "text_source": origin,
            # 1 when the ward list matches the count the record states, 0
            # when it does not, blank when the record states no count. 92% of
            # the records that state a count come out complete; a ward row
            # without this flag would silently mix those with the truncated
            # ones, which are mostly lines the page cut off at its right edge.
            "ward_list_complete": (
                int(len(parsed["ward_raws"]) == int(parsed["ward_count"]))
                if parsed["ward_count"].isdigit()
                else ""
            ),
        }
        rows.append(
            emit.stamp(
                dict(
                    base,
                    ward_no="",
                    tier="gp_head",
                    tier_local="sarpanch",
                    reservation=label(caste, woman),
                    caste_reservation=caste,
                    woman_reserved=woman,
                    ocr_repaired=repaired,
                    reservation_raw=parsed["sarpanch_raw"],
                ),
                path,
                page_no,
                ROOT,
                archive=sources,
            )
        )

        for index, raw in enumerate(parsed["ward_raws"], 1):
            fixed, repaired = repair(raw)
            got = normalize_reservation(fixed)
            if not got:
                continue
            caste, woman, script = got
            rows.append(
                emit.stamp(
                    dict(
                        base,
                        ward_no=str(index),
                        tier="gp_ward",
                        tier_local="ward",
                        reservation=label(caste, woman),
                        caste_reservation=caste,
                        woman_reserved=woman,
                        ocr_repaired=int(repaired),
                        reservation_raw=raw,
                        script=script,
                    ),
                    path,
                    page_no,
                    ROOT,
                    archive=sources,
                )
            )
    unstated = mark_gender_stated(rows)
    if unstated:
        LOGGER.warning(
            "Rows state a caste but no gender",
            extra={
                "event": "reservation_gender_unstated",
                "district": district,
                "rows": len(rows),
                "unstated_rows": unstated,
            },
        )
    return dedupe(rows)


GENDER_MARKER = re.compile(r"[({\[/\u00a2-]\s*[WwVvGgMm]\s*[)}\]]?$|[WwGgMm]$")
OPEN_MARKER = re.compile(r"[({\[/\u00a2-]\s*[GgMm]\s*[)}\]]?$|[GgMm]$")


def mark_gender_stated(rows):
    """Say whether the source actually stated the seat's gender.

    Two conventions run through these gazettes and they cannot be told apart
    row by row. East Godavari and Krishna mark only the women's seats, so a bare
    UR really is a seat not reserved for a woman. Anantapur, Nellore and
    Prakasam mark both - UR(G) as well as UR(W) - so there a bare UR is a code
    whose marker did not survive the scan, and calling it a man's seat is an
    invention rather than a reading.

    The difference is worth thousands of rows. Anantapur read 38% women against
    a statutory half until the hyphen and run-on forms of the marker were
    recognized; what is left is genuinely absent from the page, and the honest
    answer is that we do not know, not that it was a man.

    **The convention is decided per page, not per document.** Prakasam does both
    - open the file to page 14 and every open seat is a bare UR with no (G) in
    sight, while other pages mark them - so judging the whole document by its
    majority marked 2,431 rows unknown that the page had stated perfectly
    clearly. Krishna's ward count moves between pages of one document for the
    same reason: these gazettes are assembled from sheets typeset separately.

    **Finer than a page was tried, and is wrong.** A page can disagree with
    itself - Nellore page 33 carries UR(G) seventeen times and UR-W fourteen -
    so the obvious next move is to let each panchayat decide from its own
    cells: one that marks women with -W and never prints a (G) is using a
    convention where a bare code states an open seat, and 119 rows would stop
    being unknown.

    They should stay unknown. Read MITTATHMAKUR off page 33 and the gazette
    says UR-W, UR, UR, UR-W, ST-W, **SC-W**, SC, SC; this parser reads its
    sixth ward as a bare SC, because the scan drops that -W exactly as readily
    as it drops a (W). The rule would publish that seat as confidently
    not-a-woman - one wrong in eight on the single row that was checked -
    where today it says it does not know. An unknown a reader can exclude is
    worth more than a value that is quietly false.
    """
    by_page = collections.defaultdict(list)
    for row in rows:
        by_page[(row.get("source_pdf", ""), row.get("source_page", ""))].append(row)

    for page in by_page.values():
        marks_open = sum(
            1 for r in page if OPEN_MARKER.search(r["reservation_raw"].strip())
        )
        both = marks_open > 0.05 * max(len(page), 1)
        for row in page:
            stated = bool(GENDER_MARKER.search(row["reservation_raw"].strip()))
            row["gender_stated"] = 1 if (stated or not both) else 0
    return sum(1 for r in rows if not r["gender_stated"])


def dedupe(rows):
    """Collapse seats that the gazette states more than once.

    Anantapur's gazette carries the sarpanch reservation twice, in two
    different proformas: PROFORMA-I is the sarpanch list on its own, and
    PROFORMA-III is the ward table whose first column is the panchayat's own
    seat. Neither is complete - 212 seats appear only in the first and 472 only
    in the second - so the shipped file is their union, not either one.

    Left alone this counted 432 seats twice, and the duplication was invisible
    while the mandal and panchayat columns were still wrong, because no two keys
    ever collided to reveal it.

    The second statement is worth more as a check than as a row: two independent
    typesettings of the same fact agree on 427 of those 432 seats, and the five
    that disagree are reported by validate.py rather than silently resolved.
    `printings` records how many statements stood behind each row.
    """
    groups = collections.OrderedDict()
    for row in rows:
        key = (
            row["tier"],
            row["district"],
            row["block"].lower(),
            row["gram_panchayat"].lower(),
            row["ward_no"],
        )
        groups.setdefault(key, []).append(row)
    out = []
    for group in groups.values():
        # keep the statement that carries the most, so a seat listed in both the
        # sarpanch-only proforma and the ward table keeps its ward count
        best = max(
            group,
            key=lambda r: (int(r["wards_parsed"] or 0), -int(r["ocr_repaired"] or 0)),
        )
        best["printings"] = len(group)
        # blank when there is nothing to compare, so "no second statement" is
        # never mistaken for "the two statements matched"
        best["printings_agree"] = (
            "" if len(group) == 1 else int(len({r["reservation"] for r in group}) == 1)
        )
        out.append(best)
    return out


@command("parse", state="Andhra Pradesh")
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int)
    ap.add_argument("--only", help="substring of a filename to limit to")
    args = ap.parse_args()

    rows = []
    files = sorted(AP.glob("*.pdf"))
    if args.only:
        files = [path for path in files if args.only in path.name]
    if args.limit is not None:
        files = files[: args.limit]
    for path in files:
        try:
            got = parse_pdf(path)
        except UnreviewedSource:
            LOGGER.warning(
                "Retained source has no reviewed parser",
                extra={
                    "event": "source_unparsed",
                    "source_file": path.name,
                    "reason": "retained_extraction_not_reviewed",
                },
            )
            continue
        except FileNotFoundError:
            LOGGER.warning(
                "Source has no retained extraction",
                extra={
                    "event": "source_unparsed",
                    "source_file": path.name,
                    "reason": "no_retained_extraction",
                },
            )
            continue
        rows += got
        LOGGER.info(
            "Source parsed",
            extra={
                "event": "source_parsed",
                "source_file": path.name,
                "rows": len(got),
            },
        )

    by_tier = collections.defaultdict(list)
    for row in rows:
        by_tier[row["tier_local"]].append(row)

    for tier in sorted(by_tier):
        subset = by_tier[tier]
        stem = ROOT / "data" / "ap" / f"{tier}_reservation_2020"
        csv_path, _ = emit.write(subset, stem, COLUMNS)
        women = sum(r["woman_reserved"] for r in subset)
        repaired = sum(r["ocr_repaired"] for r in subset)
        districts = {r["district"] for r in subset}
        print(
            f"{tier:9s} {len(subset):6d} seats  {len(districts)} districts  "
            f"women {women / max(len(subset), 1) * 100:4.1f}%  "
            f"ocr-repaired {repaired / max(len(subset), 1) * 100:4.1f}%  "
            f"-> {csv_path.name}"
        )

    print("\nsarpanch reservation split:")
    total = max(len(by_tier["sarpanch"]), 1)
    for k, v in collections.Counter(
        r["reservation"] for r in by_tier["sarpanch"]
    ).most_common():
        print(f"   {v:6d}  {v / total * 100:5.1f}%  {k}")


if __name__ == "__main__":
    main()
