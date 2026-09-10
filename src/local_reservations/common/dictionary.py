"""What every column is supposed to look like.

One declaration per column, and it is the single source of truth for two things:
the expectations that get checked, and DICTIONARY.md, which is generated from
these entries. Documentation written separately from the rules it describes
drifts away from them - the readme in this repo did exactly that, twice.

The declarations are worth writing because every check in this repo up to now
was written to catch a problem someone had already hit. Declaring what a column
*should* be finds the ones nobody thought to look for: profiling against a first
draft of this file turned up an Andhra Pradesh ward count of 76 (the source says
at most 20), gram panchayat names holding "D. theemavaram 10 sr(w) sr(w)", and
Goa rows with no provenance at all.

`range` and `length` are the two that earn their keep. A column can be the right
type, non-blank, and still obviously wrong.
"""

import re

# Severity of a violated expectation.
ERROR, WARN, INFO = "error", "warn", "info"

# Reservation categories, after normalisation. BC covers Backward Class, BC(A)
# and OBC - the states do not agree on the name and the label does not carry
# enough to tell them apart.
CASTES = ["SC", "ST", "BC", "NONE"]

# The office a row is about. These states do not reserve the same one, which is
# why a pooled file without this column would silently compare different things.
# The canonical offices. States print these under many names - sarpanch,
# mukhiya, pradhan, ward, ward_member - and the printed name is kept alongside
# in tier_local. canon.py owns the mapping and the reasons.
TIERS = [
    "gp_head",
    "gp_vice_head",
    "gp_ward",
    "block_member",
    "block_head",
    "block_vice_head",
    "zp_member",
    "zp_head",
    "kachahari_head",
    "kachahari_member",
    "ulb_ward",
    "ulb_head",
]

RESERVATION_LABELS = [
    "Woman",
    "Other than Woman",
    "SC Woman",
    "SC Other than Woman",
    "ST Woman",
    "ST Other than Woman",
    "BC Woman",
    "BC Other than Woman",
]


def column(name, dtype, severity=ERROR, **kw):
    entry = {
        "name": name,
        "dtype": dtype,
        "severity": severity,
        "aliases": (),
        "required": False,
        "allowed": None,
        "pattern": None,
        "range": None,
        "length": None,
        "max_blank": None,
        "note": "",
    }
    entry.update(kw)
    return entry


COLUMNS = [
    # ----------------------------------------------------------- identity
    column(
        "state",
        "string",
        required=True,
        length=(3, 30),
        max_blank=0.0,
        note="Printed name of the state or union territory.",
    ),
    column(
        "year",
        "integer",
        required=True,
        range=(1990, 2030),
        max_blank=0.0,
        pattern=r"^\d{4}$",
        note="Election year. Four digits; a range would mean two cycles got "
        "merged into one file.",
    ),
    column(
        "tier",
        "enum",
        required=True,
        allowed=TIERS,
        max_blank=0.0,
        note="Which office the seat is, canonically. The same office is "
        "printed under different names by different states, and worse, "
        "the same name means different offices - Bihar's sarpanch heads "
        "a village court, not the panchayat. See canon.py.",
    ),
    column(
        "tier_local",
        "string",
        length=(2, 40),
        max_blank=0.0,
        severity=WARN,
        note="The office as the state printed it: sarpanch, mukhiya, "
        "ward_member. Kept so nothing is lost to the canonical "
        "mapping and any row can be checked against its gazette.",
    ),
    column(
        "district",
        "string",
        length=(3, 30),
        max_blank=0.20,
        severity=WARN,
        note="J&K's 2010 files carry no district column at all, so a blank "
        "share above zero is expected there but not elsewhere.",
    ),
    column(
        "block",
        "string",
        length=(2, 40),
        max_blank=0.35,
        severity=WARN,
        note="Block, taluka or mandal depending on the state.",
    ),
    # ------------------------------------------------------ the seat itself
    column(
        "gram_panchayat",
        "string",
        aliases=("halqa",),
        length=(2, 45),
        max_blank=0.10,
        severity=WARN,
        note="The panchayat. Called halqa in J&K. Jharkhand printed it "
        "inside a compound seat identifier until that was taken apart; "
        "see seat_id_raw. A value far over the length bound has "
        "usually swallowed the next column - that is how AP's broken "
        "mandal split was found.",
    ),
    column(
        "gram_panchayat_standardized",
        "string",
        length=(2, 45),
        severity=INFO,
        note="A source repository's standardized panchayat name, retained for "
        "linkage but excluded from seat identity because a many-to-one name "
        "crosswalk can merge distinct printed panchayats.",
    ),
    column(
        "ward_no",
        "roman_or_integer",
        length=(1, 6),
        max_blank=0.30,
        severity=WARN,
        note="Blank on sarpanch and mukhiya rows by design. J&K and Goa "
        "number wards in Roman numerals, so this is not purely numeric.",
    ),
    column(
        "ward_name",
        "string",
        length=(2, 40),
        max_blank=0.30,
        severity=WARN,
        note="A named ward or upper-tier constituency where the source names "
        "rather than numbers the seat.",
    ),
    # ------------------------------------------------------- the assignment
    column(
        "caste_reservation",
        "enum",
        required=True,
        allowed=CASTES,
        max_blank=0.0,
        note="**The seat's reservation, never the winner's caste.** The "
        "two are different facts and this corpus keeps them apart: a "
        "scheduled-caste person can win an unreserved seat, and in "
        "Uttar Pradesh 2005 the winner's own category matches the "
        "seat's on only 19,324 of 51,872 rows. The winner's category, "
        "where a source states it, is `winner_caste` on a seat row and "
        "`candidate_caste` on a candidate row. "
        "Orthogonal to woman_reserved: a seat can be both.",
    ),
    column(
        "caste_reservation_local",
        "string",
        length=(2, 40),
        severity=INFO,
        note="The source's local-language category or source-specific code; "
        "`caste_reservation` is its canonical interpretation.",
    ),
    column(
        "woman_reserved",
        "boolean",
        required=True,
        max_blank=0.0,
        note="1 if **the seat** is reserved for a woman - not whether a "
        "woman won it. The winner's own gender is `candidate_gender` "
        "in the candidate table. A woman can and does win a seat that "
        "is not reserved for one.",
    ),
    column(
        "reservation",
        "enum",
        required=True,
        allowed=RESERVATION_LABELS,
        max_blank=0.0,
        note="The two fields above, joined. Written separately from them, so "
        "it can disagree with them - which is checked as a row rule.",
    ),
    column(
        "reservation_raw",
        "string",
        length=(1, 120),
        note="The source cell, untouched, so any row can be audited. Where "
        "a source prints separate category flags, this is a JSON array of "
        "the untouched cells in printed order. Blank is valid only when "
        "the source prints no mark for an open, non-woman-reserved seat; "
        "that relationship is checked.",
    ),
    column(
        "reservation_raw_original",
        "string",
        length=(0, 120),
        severity=INFO,
        note="The original source cell when a later official erratum changes "
        "the seat. Blank on rows with no correction.",
    ),
    column(
        "corrected",
        "boolean",
        severity=INFO,
        note="1 when a later official erratum replaces or supplies this seat's "
        "reservation.",
    ),
    column(
        "correction_for_raw",
        "string",
        length=(0, 120),
        severity=INFO,
        note="The erratum's printed `For` cell. A dash means the original "
        "gazette left the seat blank.",
    ),
    column(
        "correction_read_as_raw",
        "string",
        length=(0, 120),
        severity=INFO,
        note="The erratum's printed `Read as` cell, retained independently of "
        "its normalized reservation.",
    ),
    column(
        "correction_source_page",
        "integer",
        range=(1, 1000),
        severity=INFO,
        note="Page carrying the official correction; blank on uncorrected rows.",
    ),
    column(
        "seat_from_image",
        "boolean",
        severity=INFO,
        note="Set where the seat identifier was OCR'd from an image because "
        "the document drew that column as pictures rather than text. "
        "The ward number in these rows comes from the ordering, not "
        "from the digits, which the OCR reads badly.",
    ),
    column(
        "district_declared",
        "boolean",
        severity=INFO,
        note="Set where the district was declared from a roster outside the "
        "corpus rather than read from the document. Eight of J&K's "
        "2010 blocks name no district anywhere in their file; saying "
        "so is the difference between a reading and an assertion.",
    ),
    column(
        "listing_scope",
        "enum",
        allowed=["all_seats", "reserved_only", "partial"],
        severity=WARN,
        note="J&K's 2018 documents list only reserved wards; Goa's 2017 and "
        "2022 files are partial rosters. Absent means all_seats.",
    ),
    # ------------------------------------------------------------ the person
    column(
        "winner",
        "string",
        length=(2, 60),
        max_blank=0.60,
        severity=WARN,
        note="Only some states publish the elected member.",
    ),
    column(
        "winner_address",
        "string",
        length=(2, 200),
        severity=INFO,
        note="Address printed for the elected member, where published.",
    ),
    column(
        "winner_basis",
        "enum",
        allowed=["published", "argmax_votes"],
        severity=INFO,
        note="Why the person is treated as the winner rather than merely a candidate.",
    ),
    column(
        "votes",
        "integer",
        range=(0, 100000),
        max_blank=0.60,
        severity=WARN,
        note="Goa 2012 only.",
    ),
    column(
        "vacant",
        "boolean",
        max_blank=0.0,
        severity=WARN,
        note="Seat unfilled or the election countermanded. Official "
        "'elected' totals exclude these.",
    ),
    column(
        "unopposed",
        "boolean",
        max_blank=0.0,
        severity=WARN,
        note="A '*' against the name in the source.",
    ),
    # ---------------------------------------------------- state-specific keys
    column("block_no", "integer", range=(1, 99), max_blank=0.90, severity=WARN),
    column("seat_no", "integer", range=(1, 999), max_blank=0.90, severity=WARN),
    column(
        "serial",
        "integer",
        range=(1, 9999),
        max_blank=0.10,
        severity=WARN,
        note="AP's per-mandal running number; gaps in it mean lost rows.",
    ),
    column("halqa", "string", length=(2, 45), max_blank=0.10, severity=WARN),
    column(
        "seat_id_raw",
        "string",
        length=(1, 90),
        max_blank=0.05,
        severity=INFO,
        note="Jharkhand. The seat identifier exactly as printed, before it "
        "was taken apart - a compound of district, block, gram "
        "panchayat and constituency number run together with @ and /. "
        "Kept because the split is the kind of thing worth being able "
        "to re-check against the page.",
    ),
    column(
        "gp_no",
        "string",
        length=(1, 10),
        max_blank=0.60,
        severity=WARN,
        note="The gram panchayat's identifier within its block, where the "
        "source states one. J&K uses alphanumeric identifiers such as 14K.",
    ),
    column(
        "gp_identity_from_page_text",
        "boolean",
        severity=INFO,
        note="J&K 2016 only. Set when a merged panchayat cell is visibly "
        "printed but the table extractor returns it empty, so the number and "
        "name are recovered from the source-faithful page text instead.",
    ),
    # --------------------------------------------------------- J&K population
    column(
        "pop_sc",
        "integer",
        range=(0, 100000),
        max_blank=0.90,
        severity=WARN,
        note="J&K prints the populations the allocation was based on, which "
        "is the only place in this repo the rule can be checked against "
        "its own inputs.",
    ),
    column("pop_st", "integer", range=(0, 100000), max_blank=0.90, severity=WARN),
    column("pop_oc", "integer", range=(0, 100000), max_blank=0.90, severity=WARN),
    column("pop_total", "integer", range=(0, 200000), max_blank=0.90, severity=WARN),
    # --------------------------------------------------------- source quality
    column(
        "ward_count",
        "integer",
        range=(1, 40),
        max_blank=0.75,
        note="The number of wards the record itself states. Andhra "
        "Pradesh's gazette header numbers ward columns 1 to 20, so an "
        "AP value above that is an OCR misread - 72 and 74 are 12 and "
        "14 in that font. Assam's municipal boards legitimately reach "
        "28 wards. Blank for most of Andhra Pradesh because "
        "Anantapur's gazette is sarpanch-only and prints no ward "
        "column at all, which is why the blank tolerance is high.",
    ),
    column(
        "sc_reserved_ward_count",
        "integer",
        range=(0, 40),
        severity=INFO,
        note="Number of SC-reserved wards printed or counted from a complete "
        "source table; count_basis distinguishes the two.",
    ),
    column(
        "st_reserved_ward_count",
        "integer",
        range=(0, 40),
        severity=INFO,
        note="Number of ST-reserved wards printed or counted from a complete "
        "source table; count_basis distinguishes the two.",
    ),
    column(
        "women_reserved_ward_count",
        "integer",
        range=(0, 40),
        severity=INFO,
        note="Number of women-reserved wards printed or counted from a complete "
        "source table; count_basis distinguishes the two.",
    ),
    column(
        "count_basis",
        "enum",
        allowed=[
            "printed_gp_summary",
            "derived_from_complete_printed_ward_table",
        ],
        severity=INFO,
        note="Whether GP-level reservation counts are printed summary cells or "
        "derived from a source table that explicitly lists every ward.",
    ),
    column("wards_parsed", "integer", range=(0, 20), max_blank=0.0, severity=WARN),
    column(
        "ward_list_complete",
        "boolean",
        max_blank=0.50,
        severity=WARN,
        note="1 when the ward list matches the stated count. Only about a "
        "third of AP's ward rows qualify, so a consumer should filter "
        "on this rather than assume.",
    ),
    column(
        "ocr_repaired",
        "integer",
        range=(0, 2),
        max_blank=0.0,
        severity=WARN,
        note="How many mends the row's category cell needed. A wrong mend "
        "is indistinguishable from a right one, so these stay "
        "findable.",
    ),
    column(
        "printings",
        "integer",
        range=(1, 4),
        max_blank=0.0,
        severity=WARN,
        note="How many times the gazette states this seat. Anantapur "
        "prints the sarpanch reservation in two proformas - a "
        "sarpanch-only list and the ward table's first column - so "
        "where both carry a seat this is 2 and validate.py checks that "
        "the two agree rather than assuming it.",
    ),
    column(
        "gender_stated",
        "boolean",
        max_blank=0.0,
        severity=WARN,
        note="Whether the source actually stated this seat's gender. Where a "
        "document marks only the women's seats a bare code is a man; "
        "where it marks both, a bare code is a marker that did not "
        "survive the scan, and woman_reserved=0 there is a guess. "
        "Filter on this before computing a women's share.",
    ),
    column(
        "printings_agree",
        "boolean",
        severity=WARN,
        note="Whether the gazette's separate statements of this seat say "
        "the same thing. Blank where the seat is stated only once - "
        "which is not the same as agreeing. Two independent "
        "typesettings agreeing is the strongest evidence available "
        "here that a row was read correctly.",
    ),
    column(
        "text_source",
        "enum",
        allowed=["ocr", "embedded", "embedded_positioned"],
        severity=INFO,
        note="Whether the row came from our own OCR or the PDF's embedded "
        "text layer. `embedded_positioned` means word coordinates, not line "
        "order, determine the table cells.",
    ),
    # ------------------------------------------------------------ provenance
    column(
        "script",
        "enum",
        allowed=[
            "latin",
            "krutidev",
            "devanagari",
            "bengali",
            "kannada",
            "gujarati",
        ],
        max_blank=0.0,
        note="Which typesetting the row was read from.",
    ),
    column("source_pdf", "string", required=True, length=(4, 80), max_blank=0.0),
    column(
        "source_path",
        "path",
        required=True,
        max_blank=0.0,
        note="Relative to data/, and checked by opening it rather than by "
        "matching a pattern - a first attempt at a filename regex "
        "rejected 1,783 perfectly good Jharkhand rows because one file "
        "is called 'Gomia_GPS, GPM & GPVM.pdf'. What matters is that "
        "the document is there, not what it is called.",
    ),
    column("source_page", "integer", required=True, range=(1, 2000), max_blank=0.0),
    # ---------------------------------------------- what a state also carries
    # Declared so `master.extras` keeps them. An extra a state carries and this
    # list does not name is dropped silently, which is how Karnataka's Census
    # populations - the strongest external check available - would have gone
    # missing while every count still balanced.
    column(
        "pop_female",
        "integer",
        range=(0, 10**7),
        severity=INFO,
        note="Census female population of the panchayat, from Karnataka.",
    ),
    column(
        "gp_code",
        "string",
        length=(1, 40),
        severity=INFO,
        note="The panchayat's own identifier in the source. An adapter may "
        "promote a stable source code into the shared gp_no identity field "
        "while retaining the original here.",
    ),
    column("district_code", "string", length=(1, 12), severity=INFO),
    column("block_code", "string", length=(1, 12), severity=INFO),
    column("panchayat_code", "string", length=(1, 12), severity=INFO),
    column(
        "seat_id_printed",
        "string",
        length=(1, 80),
        severity=INFO,
        note="The compound identifier as printed - Bihar's "
        "'Piprasi/SEMRA LABEDAHA/01'. Not a join key: it names no "
        "district, so two blocks sharing a name would merge.",
    ),
    column(
        "seat_no_from_serial",
        "boolean",
        severity=INFO,
        note="Set where the constituency number was taken from the row's "
        "serial column because the seat cell printed only a name. "
        "Karnataka's 2016 notifications come in two shapes - one "
        "prints '1-ನೀರಬೂದಿಹಾಳ', the other a number column and a bare "
        "name - and 442 of the first 1,737 rows are the second. Only "
        "adopted where the serials run 1..N once across the whole "
        "document, since some restart per page and would otherwise "
        "renumber half a taluk onto seats that already exist.",
    ),
    column(
        "seat_no_ocr",
        "string",
        length=(0, 12),
        severity=INFO,
        note="Tesseract's reading of Gujarat's printed constituency number. "
        "The reviewed roster order supplies seat_no; this field keeps "
        "the fallible OCR output auditable rather than calling it raw.",
    ),
    column(
        "seat_no_from_order",
        "boolean",
        severity=INFO,
        note="Set for Gujarat, whose final roster is printed once in strict "
        "1..N order. The table grid proves that no row was skipped; "
        "seat_no_ocr retains the independent OCR reading.",
    ),
    column(
        "sc_rank_ocr",
        "string",
        length=(0, 12),
        severity=INFO,
        note="Tesseract's uncorrected reading of the source's SC ranking.",
    ),
    column(
        "st_rank_ocr",
        "string",
        length=(0, 12),
        severity=INFO,
        note="Tesseract's uncorrected reading of the source's ST ranking.",
    ),
    column(
        "reservation_match_score",
        "string",
        length=(1, 8),
        pattern=r"^(?:0\.\d+|1(?:\.0+)?)$",
        severity=INFO,
        note="Similarity of the selected source-cell OCR reading to the "
        "reviewed Gujarati reservation vocabulary.",
    ),
    column(
        "ocr_mean_confidence",
        "string",
        length=(1, 8),
        severity=INFO,
        note="Mean Tesseract confidence over the whole-page words assigned "
        "to this source row; not a probability of correctness.",
    ),
    column(
        "source_url",
        "string",
        length=(8, 300),
        severity=INFO,
        note="Where the document was fetched from. source_path says which "
        "file on disk a row came from and source_page which page of "
        "it; neither says where the file came from, which is the one "
        "question a reader outside this repository is most likely to "
        "ask. Recorded from the harvest manifest, so it is what was "
        "actually requested rather than what a URL pattern would "
        "reconstruct.",
    ),
    column(
        "source_capture",
        "string",
        length=(8, 40),
        severity=INFO,
        note="The web archive's capture timestamp, YYYYMMDDhhmmss. With "
        "source_url this refetches the exact bytes the row was read "
        "from - a live URL may since have changed or gone. Blank for "
        "documents that were not fetched from an archive.",
    ),
    column(
        "result_source_path",
        "string",
        length=(1, 120),
        severity=INFO,
        note="A second parsed input that supplies the result when source_path "
        "supplies the seat or candidates.",
    ),
    column(
        "nomination_source_path",
        "string",
        length=(1, 120),
        severity=INFO,
        note="The separate source table that supplies GP-event nomination totals.",
    ),
    column(
        "original_filename",
        "string",
        length=(1, 80),
        severity=INFO,
        note="The document a row was read from, where the parse kept it but "
        "the pooled schema has no column for it.",
    ),
    column(
        "party",
        "string",
        length=(1, 80),
        severity=INFO,
        note="The party the winner represented. Kerala prints it and so do "
        "Karnataka's 2016 taluk and zilla notifications; almost "
        "nothing else in the corpus does. Karnataka's is "
        "canonicalised against a fixed list and left blank where the "
        "cell does not settle which party - a reading truncated to "
        "\u0ca6\u0cbe\u0cb0\u0ca4\u0cc0\u0caf fits both of the "
        "two largest, so it is empty rather than guessed. "
        "party_local keeps what the page actually said.",
    ),
    column(
        "party_local",
        "string",
        length=(1, 80),
        severity=INFO,
        note="The party exactly as the document printed it, before any "
        "canonicalisation, so a row can be audited against its page. "
        "Kept for the same reason as reservation_raw.",
    ),
    # Who the elected person was. A reservation says what a seat was reserved
    # for; these say who took it, and the whole point of holding both is that
    # they differ. Kerala states five of these for all 65,296 of its rows and
    # this repository kept only the party until it was checked.
    column(
        "relation_name",
        "string",
        length=(1, 90),
        severity=INFO,
        note="Father's or husband's name, as the source prints it.",
    ),
    column("winner_age", "string", length=(1, 12), severity=INFO),
    column("winner_education", "string", length=(1, 90), severity=INFO),
    column("winner_occupation", "string", length=(1, 90), severity=INFO),
    column("winner_marital_status", "string", length=(1, 24), severity=INFO),
    column("candidate_marital_status", "string", length=(1, 24), severity=INFO),
    column("candidate_occupation", "string", length=(1, 90), severity=INFO),
    column("candidate_total_assets", "string", length=(1, 30), severity=INFO),
    column(
        "candidate_children_before_1995_11_27",
        "string",
        length=(1, 4),
        severity=INFO,
    ),
    column(
        "candidate_children_after_1995_11_27",
        "string",
        length=(1, 4),
        severity=INFO,
    ),
    column(
        "winner_gender",
        "string",
        length=(1, 24),
        severity=INFO,
        note="The elected person's own gender. Not woman_reserved, which "
        "says whether the seat was reserved for a woman.",
    ),
    column(
        "winner_caste",
        "string",
        length=(1, 60),
        severity=INFO,
        note="The elected person's **own** category, where the source "
        "states it alongside the seat's. Not caste_reservation: that "
        "is what the seat was reserved for. Uttar Pradesh 2005 and "
        "2010 are the only seat-level slices that carry both, and they "
        "disagree on 63% of rows - which is what makes them worth "
        "holding separately rather than a redundancy.",
    ),
    column(
        "winner_category_raw",
        "string",
        length=(1, 60),
        severity=INFO,
        note="The source's untouched winning-candidate category, retained "
        "even on a result row where the winner name is blank.",
    ),
    column(
        "election_type",
        "enum",
        allowed=["General Election", "By Election"],
        severity=INFO,
        note="Whether Rajasthan SEC labels the event as a general or by-election.",
    ),
    column(
        "election_duration",
        "string",
        length=(5, 20),
        severity=INFO,
        note="The event period exactly as Rajasthan SEC labels it.",
    ),
    column("total_candidates_stated", "integer", range=(0, 100), severity=INFO),
    column("electorate", "integer", range=(0, 100000), severity=INFO),
    column("votes_polled", "integer", range=(0, 100000), severity=INFO),
    column("rejected_votes", "integer", range=(0, 100000), severity=INFO),
    column("valid_votes", "integer", range=(0, 100000), severity=INFO),
    column("poll_percentage", "string", length=(1, 8), severity=INFO),
    column("nota_votes", "integer", range=(0, 100000), severity=INFO),
    column("tendered_votes", "integer", range=(0, 100000), severity=INFO),
    column("winner_pledge_url", "string", length=(8, 300), severity=INFO),
    column("result_remark", "string", length=(1, 120), severity=INFO),
    column("nominations_filed", "integer", range=(0, 1000), severity=INFO),
    column("nomination_candidates", "integer", range=(0, 1000), severity=INFO),
    column(
        "validly_nominated_candidates",
        "integer",
        range=(0, 1000),
        severity=INFO,
    ),
    column("withdrawals", "integer", range=(0, 1000), severity=INFO),
    column("nominated_unopposed", "integer", range=(0, 1000), severity=INFO),
    column("contestants", "integer", range=(0, 1000), severity=INFO),
    column(
        "lgi_role",
        "string",
        length=(1, 40),
        severity=INFO,
        note="Kerala's Role column. An office the ward member also holds - "
        "President, Vice President - not a tier.",
    ),
    column(
        "body",
        "string",
        length=(1, 80),
        severity=INFO,
        note="The local body a seat belongs to, where it is not a gram panchayat.",
    ),
    column(
        "zilla_parishad_constituency",
        "string",
        length=(2, 80),
        severity=INFO,
        note="Named district-level constituency containing a GP, where printed.",
    ),
    column(
        "vote_percentage",
        "string",
        length=(1, 12),
        severity=INFO,
        note="Uttar Pradesh 2021 records a share of the poll and no vote "
        "total, so this cannot become a count.",
    ),
    column("movable_property", "string", length=(1, 24), severity=INFO),
    column("immovable_property", "string", length=(1, 24), severity=INFO),
    column("criminal_history", "string", length=(1, 40), severity=INFO),
    # ------------------------------------------- what a row cannot be trusted
    column(
        "duplicate_candidacy",
        "integer",
        range=(0, 20),
        severity=INFO,
        note="The source stated this contest more than once, with vote "
        "counts that disagree. Folded on (serial, name) keeping the "
        "higher count; this says it happened.",
    ),
    column(
        "serial_not_unique",
        "integer",
        range=(0, 1),
        severity=INFO,
        note="One serial number carrying two different candidates. Not "
        "resolvable from the file, so both are kept.",
    ),
    column(
        "winner_candidate_ambiguous",
        "integer",
        range=(0, 1),
        severity=INFO,
        note="More than one candidate in the contest has the published "
        "winner's exact normalized name, so the seat winner is known but the "
        "winning candidate serial is not.",
    ),
    column(
        "shared_place_name",
        "integer",
        range=(0, 1),
        severity=INFO,
        note="Two places in one block printed under one name, told apart "
        "only by being reserved differently.",
    ),
]

COLUMNS.extend(
    [
        column(
            "source_row_number",
            "integer",
            range=(1, 100000000),
            severity=INFO,
            note="One-based record ordinal in source_path, excluding a CSV header. "
            "This is not a PDF page number or a geographic identifier.",
        ),
        column(
            "source_sha256",
            "string",
            pattern=r"^[0-9a-f]{64}$",
            length=(64, 64),
            severity=INFO,
            note="SHA-256 of the pinned input bytes identified by source_path.",
        ),
        column(
            "winner_markers_conflict",
            "boolean",
            severity=INFO,
            note="Multiple candidates under one source seat key are marked as "
            "winners. No winner is selected and elected remains unknown.",
        ),
        column(
            "winner_marked_candidate_ids",
            "string",
            severity=INFO,
            note="JSON array of publisher candidate IDs carrying conflicting "
            "winner markers. candidate_no retains these IDs in the long table.",
        ),
    ]
)

BY_NAME = {c["name"]: c for c in COLUMNS}
ALIAS_OF = {alias: c["name"] for c in COLUMNS for alias in c["aliases"]}

# Plausible row counts per state and tier, as a band rather than a number - a
# file outside its band has either lost rows or double counted them.
# Keyed on the canonical tier. An absent band is not a pass - it is an
# unchecked slice, and the two largest slices in the repo (Andhra Pradesh's
# 45,478 wards and Jharkhand's 6,174) went unchecked for exactly that reason,
# because check_dataset skips what it has no band for.
ROW_BANDS = {
    # Four reviewed 2025 district notifications currently supply exactly
    # 1,254 ward rows. Hailakandi is reserved-only, so this is a parser/source
    # contract rather than a statewide ward denominator.
    ("Assam", "gp_ward"): (1254, 1254),
    ("Goa", "gp_ward"): (400, 1800),
    # Mumbai's council has had 227 wards since 1992; two councils are in the schema.
    ("Maharashtra", "ulb_ward"): (454, 454),
    # All 45 Gujarat sources have independent per-order seat totals, so the
    # aggregate expectations are exact rather than merely plausible bands.
    ("Gujarat", "block_member"): (646, 646),
    ("Gujarat", "zp_member"): (532, 532),
    # Jharkhand's upper bounds are set against what the state actually has,
    # not against what the parse happened to hold when the band was written.
    # 4,345 gram panchayats are published; 4,429 mukhiya *rows* exceed that
    # because OCR renders some panchayat names two ways, and 3,172 distinct
    # panchayats sit behind them. 5,000 is where a row count stops being name
    # duplication and starts being double counting - the 6,190 a bad merge
    # produced earlier this session still fails this band, which is the point.
    ("Jharkhand", "gp_head"): (1000, 5000),
    # 11 of 24 districts hold ward documents at all; the other 13 have none.
    # A full state would be nearer 30,000, so 20,000 still catches a doubling
    # of what is held.
    ("Jharkhand", "gp_ward"): (1000, 20000),
    ("Jharkhand", "block_member"): (1000, 5500),
    ("Jharkhand", "zp_member"): (50, 600),
    ("Jammu & Kashmir", "gp_head"): (100, 4500),
    ("Jammu & Kashmir", "gp_ward"): (500, 35000),
    ("Andhra Pradesh", "gp_head"): (500, 13200),
    ("Andhra Pradesh", "gp_ward"): (5000, 130000),
    ("Haryana", "gp_head"): (4000, 8000),
    ("Haryana", "gp_ward"): (40000, 80000),
    ("Rajasthan", "gp_head"): (8000, 14000),
    ("Rajasthan", "gp_ward"): (90000, 130000),
    ("Rajasthan", "block_member"): (5257, 5273),
    ("Rajasthan", "zp_member"): (1008, 1013),
    # Bihar 2016, one cycle. Bounds are set around what the scrape holds rather
    # than around a published total, because there is no published per-tier
    # total available in machine-readable form - see reference.PUBLISHED.
    ("Bihar", "gp_head"): (6000, 9500),
    ("Bihar", "gp_ward"): (80000, 125000),
    ("Bihar", "kachahari_head"): (6000, 9500),
    ("Bihar", "kachahari_member"): (80000, 125000),
    ("Bihar", "block_member"): (8000, 13000),
    ("Bihar", "zp_member"): (500, 1400),
    ("Uttar Pradesh", "gp_head"): (45000, 60000),
    ("Uttarakhand", "gp_head"): (200, 9000),
    ("Uttarakhand", "block_member"): (150, 4000),
    ("Uttarakhand", "zp_member"): (30, 500),
    ("Kerala", "gp_ward"): (14000, 18000),
    ("Kerala", "block_member"): (1500, 2500),
    ("Kerala", "zp_member"): (250, 400),
    ("Karnataka", "gp_head"): (4000, 7000),
    # The state went to the polls for 3,884 taluk panchayat and 1,083 zilla
    # panchayat seats in February 2016, in two phases, and declared 3,882 of
    # the taluk results. Those are the numbers these bands are set against
    # rather than against what the parse happens to hold.
    #
    # The archive holds 169 of Karnataka's 176 taluks and 26 of its 30 zilla
    # panchayats - one more 404s and three were never captured - so a complete
    # parse of what we have lands near 3,700 and 940, not at the published
    # totals. The lower bounds allow for that and for a taluk or two lost
    # entirely; the upper bounds sit just above what the state published,
    # because past that a row count has stopped being coverage and started
    # being double counting.
    ("Karnataka", "block_member"): (2500, 4200),
    ("Karnataka", "zp_member"): (600, 1200),
    ("Telangana", "gp_head"): (10000, 14000),
    ("Telangana", "gp_ward"): (40000, 60000),
}

ROMAN = re.compile(r"^[IVXLC]+$", re.I)
