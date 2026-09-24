"""What is wrong with a slice, and whether anyone can do anything about it.

The readme's per-slice table carried its caveats as free text in a Notes column,
which mixed two things that need separating:

  - facts about what a document contains, which no amount of work on *that
    document* changes; and
  - places where the document contains more than our parse recovered.

Read together they are background noise. Read apart, the second list is a
worklist. So a note is a declaration with a **status**:

    SOURCE_PROPERTY   the document says what it says. Nothing to do.
    OPEN_GAP          the document holds more than we took. `closes_with` says
                      what would close it.
    UNDETERMINED      we have not established which of the two it is - and that
                      is itself the work.

`UNDETERMINED` is the honest third answer and it earns its place. "No winner was
published" is a claim about the universe of documents, not about the file in
hand; asserting it as a source property is asserting something nobody checked.

Every note is detected from the rows, so a note cannot be marked done while the
condition still holds, and cannot linger once it stops holding. Fix Jharkhand's
image-only column and the line disappears from WORKLIST.md on the next build.
"""

import collections
import csv

from local_elections.common import canon, reference

SOURCE_PROPERTY = "source property"
OPEN_GAP = "open gap"
UNDETERMINED = "undetermined"
# Closable, but not from here. Kept apart from OPEN_GAP because "nobody has done
# this" and "nobody here can do this" are different claims, and a worklist that
# mixes them is one nobody trusts.
BLOCKED = "blocked"
# Closable from here, and deliberately not being closed. A third claim again:
# BLOCKED is waiting on access, OPEN_GAP is waiting on effort, and this is a
# decision that the effort is better spent elsewhere for now. Recording it is
# what stops the same state being re-triaged every time somebody reads the list,
# and what stops "still open" being mistaken for "nobody noticed".
PARKED = "parked"

NOTES = []


def note(note_id, text, status, because, closes_with=""):
    def register(detect):
        NOTES.append(
            {
                "id": note_id,
                "text": text,
                "status": status,
                "because": because,
                "closes_with": closes_with,
                "detect": detect,
            }
        )
        return detect

    return register


def found(rows_affected, detail="", status=None, **overrides):
    return {
        "rows_affected": rows_affected,
        "detail": detail,
        "status": status,
        **overrides,
    }


# --------------------------------------------------------- source properties


@note(
    "reserved_only_listing",
    "lists only the reserved seats",
    SOURCE_PROPERTY,
    because="The document is a roster of reserved seats. Its shares describe "
    "which pages were published, not the state - J&K 2018 reads 82% "
    "women for that reason alone.",
)
def reserved_only_listing(s):
    if s.scope == "reserved_only":
        return found(s.n, "shares here are a property of the document")
    return None


@note(
    "no_ward_column_in_the_source",
    "the source has no ward column",
    SOURCE_PROPERTY,
    because="Anantapur's PROFORMA-I is a sarpanch list printed without ward "
    "columns, so there is no count to read and no wards missing.",
)
def no_ward_column_in_the_source(s):
    if "ward_count" not in s.rows[0] or s.tier != "gp_head":
        return None
    none = sum(
        1
        for r in s.rows
        if not (r.get("ward_count") or "").strip()
        and str(r.get("wards_parsed") or "0") == "0"
    )
    return found(none, "sarpanch rows carrying no wards at all") if none else None


@note(
    "no_reservation_in_the_source",
    "the source records no reservation",
    SOURCE_PROPERTY,
    because="Kerala's 2005 file is an unpivoted table of Ward No, Elected "
    "Members, Front and Votes, with header rows left in the body. "
    "There is no reservation column in it to parse, which is a "
    "property of that source rather than work outstanding.",
)
def no_reservation_in_the_source(s):
    if not s.rows:
        return None
    stated = sum(
        1
        for r in s.rows
        if (r.get("caste_reservation") or "").strip()
        or str(r.get("woman_reserved") or "").strip()
    )
    if stated:
        return None
    return found(s.n, "no row in this slice states a reservation")


# ----------------------------------------------------------------- open gaps


@note(
    "names_not_transliterated",
    "place names are in a legacy font",
    OPEN_GAP,
    because="Kruti Dev is a deterministic byte mapping, not damage. The names "
    "are recoverable; they simply have not been converted, so these "
    "rows cannot be joined to any other source on name.",
    closes_with="a Kruti Dev to Unicode transliterator applied to district, "
    "block and gram_panchayat",
)
def names_not_transliterated(s):
    affected = sum(1 for r in s.rows if r.get("script") == "krutidev")
    return found(affected) if affected else None


@note(
    "seat_id_drawn_as_an_image",
    "the seat identifier is an image, not text",
    OPEN_GAP,
    because="On three pages of the Lohardaga notification the whole seat "
    "column is 40 embedded images. The text layer holds only the "
    "district's roman numeral, so the block, panchayat and ward "
    "number are unreachable by parsing - and those rows then collide "
    "with each other on the seat key.",
    closes_with="Devanagari OCR of the seat column on pages 22-24 of "
    "LOHARDAGA ZP PSS MUKHIYA GPS.pdf. The images render clean "
    "Unicode, easier than the Kruti Dev the rest of the state is "
    "in, and split_seat_id already parses the shape they use",
)
def seat_id_drawn_as_an_image(s):
    affected = sum(
        1
        for r in s.rows
        if (r.get("seat_id_raw") or "").strip().isupper()
        and len((r.get("seat_id_raw") or "").split()) == 1
        and not canon.unit_name(r)
    )
    return found(affected) if affected else None


@note(
    "gender_not_stated",
    "the source states a caste but no gender",
    OPEN_GAP,
    because="Where a document marks both the women's and the open seats, a "
    "code whose marker did not survive the scan is unknown, not male "
    "- and woman_reserved defaults to 0, which silently turns a "
    "woman's seat into an open one. Worse, the two markers are not "
    "lost at equal rates: Prakasam loses (G) about twice as often as "
    "(W), so its surviving rows read 66% women against a statutory "
    "half. Neither the raw share nor the filtered one estimates the "
    "truth there.",
    closes_with="a second reading of the affected pages - the codes are "
    "printed, they simply did not survive this scan. Anantapur "
    "fell from 25% unmarked to 4% once the hyphen and run-on "
    "forms of the marker were recognized, so the remainder is "
    "likely reachable the same way",
)
def gender_not_stated(s):
    if "gender_stated" not in s.rows[0]:
        return None
    unstated = [r for r in s.rows if r.get("gender_stated") != "1"]
    if not unstated:
        return None
    worst = collections.Counter(r.get("district", "") for r in unstated)
    where = ", ".join(f"{d} {n:,}" for d, n in worst.most_common(3))
    return found(len(unstated), where)


@note(
    "ward_list_incomplete",
    "some ward lists are shorter than the record says",
    OPEN_GAP,
    because="The line was cut at the page's right edge, so wards are missing "
    "rather than blank. This is measurable rather than hidden only "
    "because the record states its own count - and it biases the "
    "women's share downward, 37% across truncated records against "
    "47% across whole ones.",
    closes_with="re-reading the truncated records at a wider render, or from "
    "the second proforma where one exists",
)
def ward_list_incomplete(s):
    short = sum(1 for r in s.rows if r.get("ward_list_complete") == "0")
    return found(short, f"{short / s.n:.0%} of rows") if short else None


@note(
    "districts_missing",
    "some districts are not held",
    OPEN_GAP,
    because="The state has more districts than we have documents for, so "
    "every share here describes the districts we hold.",
    closes_with="harvesting the remaining districts' notifications",
)
def districts_missing(s):
    """Rows affected is an estimate of what is *missing*, not what we have.

    Counting every row of a partial state made the gap grow each time a
    district was added - West Godavari brought 9,070 wards and the entry went up
    by 9,921, which reads as a regression for what is plainly progress. The
    estimate is the average district's row count times the number of districts
    still unheld, so it falls as they are collected.
    """
    expected = reference.districts_expected(s.state, s.year)
    got = len({r.get("district") for r in s.rows if r.get("district")})
    if not (expected and got and got < expected):
        return None
    estimate = round(s.n / got * (expected - got))
    detail = f"{got} of {expected} districts, roughly {estimate:,} rows missing"
    held = set()
    for manifest in (s.root / "data").glob("*/*/manifest.csv"):
        with manifest.open(encoding="utf-8", errors="replace") as fh:
            for row in csv.DictReader(fh):
                if row.get("state") == s.state and row.get("year") == s.year:
                    district = (row.get("district") or "").strip()
                    if district:
                        held.add(district)
    if len(held) >= expected:
        return found(
            estimate,
            f"{got} of {expected} districts parsed; {len(held)} of {expected} "
            f"district source PDFs held; roughly {estimate:,} rows remain unparsed",
            text="some held districts are unparsed",
            because="The complete district source series is held locally, but "
            "not every document has passed extraction, parsing, and validation.",
            closes_with="extracting and parsing the held district documents",
        )
    # "Not held" is a claim about the world, and it is worth saying whether
    # anyone has tested it. Where the search has been done, say when and what
    # it turned up, so the next person does not repeat it.
    done = reference.investigated(s.state, s.year, s.tier, "missing_districts")
    if done:
        detail += f". Searched {done['on']}: {done['found'].splitlines()[0]}"
    access, why = reference.source_access(s.state)
    if access == "blocked":
        return found(estimate, f"{detail} - {why}", status=BLOCKED)
    return found(estimate, detail)


@note(
    "panchayat_not_named",
    "the row does not say which panchayat",
    OPEN_GAP,
    because="The reservation and the winner were read but the seat column "
    "was not, so the row is a real seat whose identity is unknown. "
    "This is most of what looks like a key collision: two rows that "
    "both name no panchayat are not duplicates, they are two "
    "different seats we cannot tell apart.\n\n"
    "This note used to say the gap was Jharkhand's scans, naming 34% "
    "of OCR'd rows against 92% of typeset ones, and to prescribe "
    "re-OCR. Both halves were wrong by the time anyone read them "
    "again: the scanned districts now name the panchayat on 99.9% of "
    "ward rows against 96.2% for the districts that came as digital "
    "text, and 519 of the 524 rows still unnamed are in digital-text "
    "documents. Re-OCR would reach five of them. A closes_with is a "
    "claim about the present, and this one outlived the two commits "
    "that made it false.",
    closes_with="three different things, only one of which is a parse. "
    "Koderma's 261 rows are the Lohardaga defect again: on pages "
    "30-35 the seat column is drawn rather than typed, 33 to 51 "
    "embedded images a page against 32 to 50 rows that name "
    "nothing, and the text layer keeps only the district's roman "
    "numeral, which is why every one of them reads 'VI'. That "
    "closes the way Lohardaga's did, through ocr_seats.py. "
    "Pakur's 106 carry no identifier at all. East Singhbhum's 80 "
    "were the parse, and are fixed: the name was there in full "
    "and split down the middle, because ध is written '/' in Kruti "
    "Dev and 'e/; ckxcsM+k' is मध्य बागबेड़ा.",
)
def panchayat_not_named(s):
    # A seat above panchayat level has no panchayat to name: a block member's
    # constituency is numbered within its block and a district member's across
    # the district. Counting those as unnamed made 4,107 correctly-parsed
    # panchayat samiti rows look like a defect - they carry a block and a seat
    # number, which is the whole of their identity.
    if s.tier in (
        "block_member",
        "block_head",
        "block_vice_head",
        "zp_member",
        "zp_head",
    ):
        return None
    missing = [r for r in s.rows if not canon.unit_name(r)]
    if not missing:
        return None
    worst = collections.Counter(r.get("district", "") for r in missing)
    return found(len(missing), ", ".join(f"{d} {n:,}" for d, n in worst.most_common(3)))


@note(
    "seat_not_numbered",
    "the row does not say which seat",
    OPEN_GAP,
    because="A seat is numbered within the body that elects it - a ward "
    "within its panchayat, a constituency within its block or "
    "district - and without that number the row is a real "
    "reservation for a seat nobody can point at.\n\n"
    "This used to skip panchayat wards, on the reasoning that a ward "
    "has a panchayat to identify it while a block constituency has "
    "nothing but its number. That is wrong: a panchayat has many "
    "wards, so a ward without a number is no more identified than a "
    "block seat without one. 2,692 Haryana rows sat in that blind "
    "spot, surfacing as `seat_key_not_unique` with the unhelpful "
    "detail 'largest group 35 rows' - seven real seats in Atela with "
    "different winners and different reservations, keyed alike "
    "because none of them says which ward it is.",
    closes_with="reading the number from the seat identifier, or from the "
    "okMZ ua0 column the Haryana gazettes print it in - those "
    "PDFs are digital text, not scans, so it is a re-parse and "
    "not an OCR job, and it is confined to a few files "
    "(Karnal__Indri.pdf alone holds 639 of the unnumbered rows).\n\n"
    "NOT by renumbering the rows by their position. That was "
    "tested and refused: 5,899 of Haryana's 6,159 panchayats do "
    "number their wards, and 95% of those run 1..N in row order "
    "- but 182 have gaps, "
    "['1','2','3','5','6','7','8','9'] skipping 4, because a "
    "ward whose result was not declared is simply absent. "
    "Filling by position would misnumber every ward after a gap "
    "and the row would look entirely correct.",
)
def seat_not_numbered(s):
    # Heads are unique within their body and need no constituency number.
    # Member constituencies may be numbered or named; Assam names each APC
    # after a GP and each ZPC directly.
    if s.tier not in ("gp_ward", "ulb_ward", "block_member", "zp_member"):
        return None
    if s.tier in ("gp_ward", "ulb_ward"):
        identity_columns = ("ward_no", "ward_name")
    elif s.tier == "block_member":
        identity_columns = ("seat_no", "gram_panchayat")
    else:
        identity_columns = ("seat_no", "ward_name")
    missing = [
        r
        for r in s.rows
        if not any((r.get(column) or "").strip() for column in identity_columns)
    ]
    if not missing:
        return None
    worst = collections.Counter(r.get("district", "") for r in missing)
    return found(len(missing), ", ".join(f"{d} {n:,}" for d, n in worst.most_common(3)))


@note(
    "seat_key_not_unique",
    "some rows do not identify a distinct seat",
    OPEN_GAP,
    because="Two rows sharing every standardized seat-identity field cannot "
    "be told apart. Usually one printed identifier did not parse.",
    closes_with="parsing whichever identifier is blank on the colliding "
    "rows. For the Jharkhand scans that means re-OCR: Surya "
    "keeps the block and panchayat numbers - the 1 and 2 of "
    "'IVचतरा/1/2/जोगीडीह' - that tesseract drops, and those "
    "numbers are exactly what these rows are short of",
)
def seat_key_not_unique(s):
    counts = collections.Counter(canon.seat_identity(row) for row in s.rows)
    dup = sum(n for n in counts.values() if n > 1)
    if not dup:
        return None
    worst = counts.most_common(1)[0] if counts else ((), 0)
    return found(dup, f"largest group {worst[1]} rows")


@note(
    "winner_candidate_ambiguous",
    "the winner name matches more than one candidate",
    OPEN_GAP,
    because="The result names the winner but not the candidate serial, and "
    "two people in the same contest print the same normalized name. The seat "
    "winner remains known; which candidate record won does not.",
    closes_with="linking the result's pledge document or another source that "
    "states the winning candidate serial",
)
def winner_candidate_ambiguous(s):
    affected = sum(
        1
        for row in s.rows
        if "winner_candidate_ambiguous" in (row.get("quality_flags") or "").split(";")
    )
    return found(affected) if affected else None


@note(
    "district_not_printed",
    "the district column is mostly blank",
    OPEN_GAP,
    because="The source prints no district, but the file path names one, so "
    "it is recoverable from provenance rather than from the page.",
    closes_with="deriving district from source_path where the page omits it",
)
def district_not_printed(s):
    blank = sum(1 for r in s.rows if not (r.get("district") or "").strip())
    if blank > 0.5 * s.n:
        return found(blank, f"{blank / s.n:.0%} of rows")
    return None


# ------------------------------------------------------------- undetermined


@note(
    "no_winner_recorded",
    "no winner is recorded",
    UNDETERMINED,
    because="Whether this is a source property depends on what stage of "
    "document it is. A pre-poll reservation roster names no winner "
    "and never will; for anything else, a results notification may "
    "exist that we have not looked for. Asserting the first without "
    "checking is a claim about every document a state published.",
    closes_with="declaring reference.DOCUMENT_STAGE for this slice - "
    "pre_poll settles it as a source property, and anything else "
    "means going to look",
)
def no_winner_recorded(s):
    if any((r.get("winner") or "").strip() for r in s.rows):
        return None
    stage = reference.document_stage(s.state, s.year, s.tier)
    if stage == "pre_poll":
        return found(s.n, "a pre-poll roster names no winner", status=SOURCE_PROPERTY)
    if stage == "result":
        return found(
            s.n,
            "a result-stage source should identify the elected person",
            status=OPEN_GAP,
        )
    # "Nobody has looked" and "somebody looked and found nothing" are the same
    # absence to DOCUMENT_STAGE and are not the same claim. Saying which costs
    # one line here and saves the next person repeating the search.
    done = reference.investigated(s.state, s.year, s.tier, "results_notification")
    if done:
        return found(
            s.n, f"searched {done['on']}: {done['searched']} - {done['found']}"
        )
    return found(s.n, "no document stage declared, and nobody has looked")


@note(
    "some_winners_missing",
    "some result rows do not identify a winner",
    UNDETERMINED,
    because="A blank winner inside a result-stage slice is not the same as a "
    "pre-poll roster that names nobody. Vacant seats are excluded; the "
    "remaining blanks need a result source or an explicit source reason.",
    closes_with="recovering the missing result rows or recording why those "
    "specific contests produced no elected person",
)
def some_winners_missing(s):
    missing = [
        row
        for row in s.rows
        if not (row.get("winner") or "").strip()
        and str(row.get("vacant") or "0") not in {"1", "True", "true"}
    ]
    if not missing or len(missing) == s.n:
        return None
    stage = reference.document_stage(s.state, s.year, s.tier)
    status = OPEN_GAP if stage == "result" else None
    return found(len(missing), f"{len(missing):,} of {s.n:,} rows", status=status)


@note(
    "partial_listing",
    "the roster is incomplete",
    UNDETERMINED,
    because="The document holds fewer seats than the state has. Whether a "
    "complete roster was ever published is a different question from "
    "whether this file is complete, and only the second is settled.",
    closes_with="establishing whether a full roster exists for this cycle",
)
def partial_listing(s):
    if s.scope == "partial":
        return found(s.n, "measured against a complete cycle of the same state")
    return None


def for_slice(a_slice):
    """Every note that applies to one slice."""
    out = []
    for spec in NOTES:
        got = spec["detect"](a_slice)
        if not got:
            continue
        status = got.get("status") or spec["status"]
        # A parked state's gaps are still real and still described; they move out
        # of the queue rather than out of the file. Source properties are left
        # alone - there is nothing there to decide not to do.
        parked = reference.parked(a_slice.state)
        if parked and status in (OPEN_GAP, UNDETERMINED):
            status = PARKED
        out.append(
            {
                "note_id": spec["id"],
                "text": got.get("text") or spec["text"],
                "status": status,
                "because": got.get("because") or spec["because"],
                "closes_with": got.get("closes_with") or spec["closes_with"],
                "rows_affected": got["rows_affected"],
                "detail": got["detail"],
            }
        )
    return out
