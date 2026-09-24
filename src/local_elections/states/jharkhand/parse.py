"""Parse Jharkhand panchayat reservation, 2015.

One folder per district. The filenames suggest a tier ("GARHWA MUKHIYA.pdf")
but they lie: several are named "RANCHI ZP PSS MUKHIYA GPS" and hold the Zila
Parishad, Panchayat Samiti, Mukhiya and ward-member lists one after another.
Trusting the filename gave 12,509 "mukhiya" seats against Jharkhand's ~4,345
gram panchayats.

So every PDF is read once and each row is assigned a tier from its *post*
column, and each tier is written to its own file:

    eqf[k;k              mukhiya            gram panchayat head   <- GP level
    xzke iapk;r lnL;     ward_member        gram panchayat ward
    iapk;r lfefr lnL;    panchayat_samiti   block
    ftyk ifj"kn lnL;     zila_parishad      district

Two things make this state different from Goa:

* **Caste and gender are separate columns** - column 3 is "vuqlwfpr tutkfr",
  column 4 is "efgyk" or "vU;" - so the shared normalizer's caste_of() and
  woman_of() are called directly rather than normalize_reservation().
* **There is no English printing.** Everything is legacy Kruti Dev, so person
  and place names come out as mojibake. The reservation decodes fine, being a
  closed vocabulary, and each seat is still uniquely keyed by (district, block
  number, seat number) from the last column.

Writes data/jharkhand/<tier>_reservation_2015.{csv,jsonl}.
"""

import argparse
import collections
import csv
import html
import re

import pdfplumber

from local_elections.common import canon, emit, krutidev
from local_elections.common.normalize import (
    _undouble,
    caste_of,
    is_vacant,
    label,
    woman_of,
)
from local_elections.common.runlog import command, get_logger
from local_elections.paths import ROOT

LOGGER = get_logger(__name__)

JHARKHAND = ROOT / "data" / "jharkhand" / "2015"
OCR_CACHE = ROOT / "data" / "jharkhand" / "ocr"

COLUMNS = [
    "state",
    "year",
    "district",
    "block",
    "block_no",
    "gram_panchayat",
    "gp_no",
    "ward_no",
    "seat_no",
    "seat_id_raw",
    "seat_from_image",
    "tier",
    "tier_local",
    "reservation",
    "caste_reservation",
    "woman_reserved",
    "winner",
    "vacant",
    "reservation_raw",
    "script",
]

# Kruti Dev for each post. "neoqf[k;k" is a *deputy* mukhiya, so the match is
# exact rather than a substring.
TIERS = {
    "eqf[k;k": "mukhiya",
    "xzke iapk;r lnL;": "ward_member",
    # "member *of the* gram panchayat" - the same post with `ds` in it, 1,870
    # occurrences, and Koderma's notification uses only this spelling. It read
    # as no post at all, so a district with 1,211 ward seats contributed none
    # and its absence was indistinguishable from a district that holds no ward
    # documents. 401 panchayat samiti rows are spelt the same way.
    "xzke iapk;r ds lnL;": "ward_member",
    "iapk;r lfefr lnL;": "panchayat_samiti",
    "iapk;r lfefr ds lnL;": "panchayat_samiti",
    'ftyk ifj"kn lnL;': "zila_parishad",
    'ftyk ifj"kn ds lnL;': "zila_parishad",
    # "mukhiya *of the* gram panchayat", 206 rows across Sahebganj, Giridih and
    # Pakur. The same office as the bare "eqf[k;k" and the reason it has to be
    # here rather than only in tier_of: RE_TEXT_ROW builds its post alternation
    # from these keys, so with only the short form it matched "eqf[k;k" and left
    # "xzke iapk;r" welded to the end of the winner's name - "ज्योती देवी ग्राम
    # पंचायत" - which then failed to dedupe against the table reader's cleaner
    # reading of the same seat. 501 seats were published twice.
    "xzke iapk;r eqf[k;k": "mukhiya",
    "xzke iapk;r ds eqf[k;k": "mukhiya",
}
TIER_BY_KEY = {_undouble(k): v for k, v in TIERS.items()}

# "iz[k.M & [kjkSaa/kh" = prakhand (block) - <name>. Read from the page's layout
# text, because the table renders this header with characters multiplied
# ("iiiizz[[zz[[kkkk....MMMM").
# Stop at "ftyk" (zila): the header reads "iz[k.M & rksipk¡ph ftyk & /kuckn",
# and taking the lot made the block name "Topchanchi zila Dhanbad".
RE_BLOCK = re.compile(r"iz\[k\.M\s*&\s*(\S[^\n]{0,40}?)(?:\s*ftyk\b|$)")

# The last column is not a name. It is a compound seat identifier that runs the
# district, the block, the gram panchayat and the constituency number together:
#
#   XV cksdkjks@08 pkl@18 lruiqj@izk0fu0{ks0 la0&12
#   |  |          |       |      |                |
#   |  district   |       |      the label "izk0fu0{ks0 la0" = territorial
#   roman         block   gram   constituency number
#                         panchayat
#
# Reading it whole as "constituency" cost more than it looks: `block` came out
# 52-100% blank across the four tiers when the block is right there in the
# string, ward_member had no ward number at all for 6,174 rows, and 121 rows
# collided on a seat key that was nothing but a roman numeral.
#
# Four tiers print four layouts and the typesetters bracket the number five
# ways, so the parts are found by searching rather than by position, and
# anything that does not resolve is left blank rather than guessed.
# "territorial constituency no." - the label the identifier's number sits after.
# Both spellings, because the same words reach us in two encodings: Kruti Dev
# from a text layer, Unicode Devanagari from a scan. Reading only the first left
# the label itself standing as the last part of the identifier, so 18 rows were
# published with a gram panchayat of "प्रा0नि0क्षे0 सं0" - a caption, not a place
# - and the real name next to it was dropped.
SEAT_LABEL = re.compile(
    r"izk0\s*fu0\s*\{ks0\s*la0"
    r"|प्रा0\s*नि0\s*क्षे0\s*सं0"
)
# The trailing alternative is the panchayat samiti form - "XII दुमका/04/
# काठीकुण्ड-01" - where the others all bracket the number. Three documents (Gola
# PSS, both Dumka notifications) resolved no seat number at all for want of it,
# on tesseract and on Surya alike, so it is a parser gap rather than a scan one.
# Tried last and anchored to the end, so a bracketed number still wins and a
# hyphen inside a place name cannot be mistaken for the separator.
SEAT_TAIL = re.compile(r"(?:¼\s*(\d+)\s*½|\(\s*(\d+)\s*\)|&\s*(\d+)|[-–—]\s*(\d+))\s*$")
SEAT_ROMAN = re.compile(r"(?<![A-Za-z])([IVXLC]{1,6})(?![A-Za-z])")
SEAT_NUMBERED = re.compile(r"^(\d+)[\s/]+(.*\S)$")

# Fallback for the districts whose tables carry no ruling lines. pdfplumber
# finds no table there and the rows are simply lost - 9 of the 19 districts
# that *do* have readable mukhiya text were being dropped this way. The post
# token is a reliable anchor in the layout text:
#
#   tudjkt nsoh    eqf[k;k vukjf{kr    efgyk    I x<+ok@01@01&lq.Mh
# `\s+` between the words, not a literal space: the typesetter breaks the post
# across a line in 3,588 places - "xzke iapk;r\nds lnL;" and "xzke iapk;r ds\nlnL;"
# - and a literal match sees neither.
RE_TEXT_ROW = re.compile(
    r"^(?P<name>.*?)\s*(?P<post>"
    # Longest first: "eqf[k;k" is a suffix of "xzke iapk;r eqf[k;k", and a
    # regex alternation takes the first branch that matches, not the longest.
    + "|".join(
        r"\s+".join(re.escape(w) for w in k.split())
        for k in sorted(TIERS, key=len, reverse=True)
    )
    + r")\s+(?P<caste>.+?)\s+(?P<woman>efgyk|vU;)\s+(?P<seat>\S.*)$"
)

# Godda's ten notifications carry a text layer that is not Kruti Dev and not
# text either - `pdftotext` returns "Y r" ftr na AvW ro". They were OCR'd along
# with the rest of the scanned districts, and the OCR came back in **Unicode
# Devanagari**, so every token this parser anchors on missed and all ten files
# contributed nothing to any tier. The district read as absent from the corpus:
# no mukhiya, no panchayat samiti, no ward member, no zila parishad, and no
# error anywhere, because a file that yields no rows looks exactly like a file
# with no rows in it.
#
# The offices a Devanagari page names, matched by containment because the state
# does not print them one way. A scan of the whole corpus finds "ग्राम पंचायत के
# सदस्य" and "ग्राम पचायत के सदस्य" without its anusvara, "वार्ड सदस्य", the
# abbreviation "पं०स०स०", and "जिला परिषद् सदस्य" with a virama the others lack.
# Matching the cell exactly recognized the first of those and dropped 1,052 rows
# that were spelt any of the other ways.
#
# Ordered by office, not by length, and for the same reason TIER_HEADS is: the
# head of a gram panchayat is printed "ग्राम पंचायत के मुखिया", so a rule that
# looked for the longest match, or for the ward token first, would file 174
# heads as ward members.
DEV_POSTS = (
    ("मुखिया", "mukhiya"),
    ("जिला परिषद", "zila_parishad"),
    ("पंचायत समिति", "panchayat_samiti"),
    ("पं०स०स०", "panchayat_samiti"),
    ("पं0स0स0", "panchayat_samiti"),
    ("ग्राम पंचायत", "ward_member"),
    ("ग्राम पचायत", "ward_member"),
    ("वार्ड", "ward_member"),
)


def dev_post(cell):
    """The office a post cell names, or None if it names none."""
    return next((tier for token, tier in DEV_POSTS if token in cell), None)


# "[2 गोड्डा /,/0/ छोटा बडामानगढ-(6)" - the identifier survives the scan far
# worse than the row does. What is reliably there is the panchayat, which is the
# run of text before the final bracket, and the number inside it. OCR eats
# leading digits often enough - "-(0)" for ward 10, "-()" for 11 - that 168 of
# 1,032 rows carry no readable number, and those are left blank rather than
# renumbered by position: a row lost to OCR would shift every seat after it.
# Any Devanagari codepoint. Used only to decide which of the two identifier
# readers a row needs, never to decide what a row says.
DEVANAGARI = re.compile(r"[\u0900-\u097F]")

RE_DEV_SEAT = re.compile(r"(?P<panchayat>[^/\]]+?)\s*-\s*\(\s*(?P<number>\d*)\s*\)\s*$")


def split_seat_id(text, tier):
    """Pull the district, block, gram panchayat and constituency number apart.

    The same shape means different things at different tiers - a zila parishad
    identifier names only the district, a panchayat samiti one ends with the
    block, and a ward one ends with the gram panchayat - so the tier decides
    what the trailing name is rather than the parser guessing. Where a string
    does not resolve to a known layout, nothing is returned: a wrong block name
    would be indistinguishable from a right one, and this corpus is legacy-font
    mojibake where nobody would notice.
    """
    s = re.sub(r"\s+", " ", (text or "").strip())
    if not s:
        return {}
    out = {}

    # the number is bracketed five ways across the districts: la0&12, ¼12½,
    # (12), &12, - (12)
    s = SEAT_LABEL.sub("", s)
    tail = SEAT_TAIL.search(s)
    if tail:
        out["seat_no"] = next(g for g in tail.groups() if g)
        s = s[: tail.start()]
    s = s.strip().strip("&-/@ ").strip()

    # Some districts put the panchayat's name after the ampersand where others
    # put its number - "I x<+ok 05@01 & cjMhgk" against "...&¼01½". Reading the
    # ampersand as introducing a number only, the name was dropped and 1,141
    # mukhiya rows named no panchayat at all.
    # The name may contain "/" and the ampersand is the last separator, so
    # everything after it is the name: excluding "/" from the run truncated
    # 709 mukhiya names to nothing - "I x<+ok 15@11& e/ks;k" is मधोया, whose
    # third letter is written "/k" - and left 86 more with the separator still
    # on the front, as "- खरौंधा" and "03-खरौन्धी". The leading character is
    # still guarded, because some districts put the panchayat's *number* after
    # the ampersand rather than its name.
    trailing = re.search(r"&\s*([^&@/\d][^&@]*?)\s*$", s)
    if trailing and re.search(r"\w", trailing.group(1)):
        out["trailing_name"] = trailing.group(1).strip()
        s = s[: trailing.start()].strip()

    # the roman numeral is the district's index and floats: it opens the string
    # in most districts and trails it in East Singhbhum
    roman = SEAT_ROMAN.search(s)
    if roman:
        out["district_roman"] = roman.group(1)
        s = s[: roman.start()] + " " + s[roman.end() :]
    s = s.strip().strip("&-/@ ").strip()

    # Some districts separate the parts with "/" and others with "@" - Ranchi
    # writes both, sometimes on the same page. Splitting on "@" alone left the
    # block and panchayat blank on rows whose ward number parsed perfectly well,
    # which reads as a seat that exists but sits nowhere.
    #
    # "/" cannot be split on blindly: in Kruti Dev it also begins the letter ध,
    # so "[kjkSa/kh" - the block Kharaundhi - would come apart in the middle of
    # its own name.
    #
    # Guarding only on a following "k" was too narrow. ध is written "/k" in
    # खरौंधी but "/;" in "e/; ckxcsM+k" - मध्य बागबेड़ा, where the next letter is
    # य - so East Singhbhum's names split down the middle and 80 rows named no
    # panchayat while the name sat in the string, in two halves. What actually
    # distinguishes the two is whether a number is involved: a separator has a
    # digit or a space on one side of it, a conjunct does not.
    #
    # That narrower rule applies to Kruti Dev only. The ambiguity is an artefact
    # of the encoding - in Unicode Devanagari ध is ध and "/" is only ever a
    # separator - and requiring the digit there cost 69 rows, because OCR leaves
    # commas against the separator ("3,/धसनियाँ") where a digit should be. So the
    # scanned pages keep the rule they were tuned on and the typeset ones get the
    # one their encoding needs.
    slash = r"@|/(?!k)" if DEVANAGARI.search(s) else r"@|(?<=[\s\d])/(?!k)|/(?=[\s\d])"
    parts = [p.strip(" &-") for p in re.split(slash, s)]
    parts = [p for p in parts if p]

    def kind(p):
        if re.fullmatch(r"\d+", p):
            return "N"
        return "M" if SEAT_NUMBERED.match(p) else "T"

    shape = "".join(kind(p) for p in parts)
    out["shape"] = shape

    # A name taken from after the ampersand is the panchayat below block level
    # and the block at panchayat samiti level, the same rule the shapes follow.
    name = out.pop("trailing_name", "")
    if name:
        out["block" if tier == "panchayat_samiti" else "gram_panchayat"] = name

    def numbered(p):
        found = SEAT_NUMBERED.match(p)
        return (found.group(1), found.group(2)) if found else ("", p)

    def devanagari_tail():
        """The panchayat off the end of an OCR'd identifier with no ampersand.

        The scanned districts print the same identifier without the ampersand
        the typeset ones use - "... |! दुमका /0,/05 चरकापाथर" is चरकापाथर, whose
        name is simply the last part. None of the shape rules match, because the
        shapes were written against Kruti Dev and the leading junk here is
        whatever the scan made of the district's roman numeral.

        A last resort, and deliberately narrow: it runs only where nothing else
        named the panchayat, requires Devanagari letters, and requires at least
        three of them, so a stray mark cannot become a place.
        """
        if not parts or tier in ("panchayat_samiti", "zila_parishad"):
            return ""
        tail = re.sub(r"^[\W\d_]+", "", parts[-1]).strip()
        return tail if DEVANAGARI.search(tail) and len(tail) >= 3 else ""

    if not out.get("gram_panchayat") and devanagari_tail():
        out["gram_panchayat"] = devanagari_tail()

    if shape == "TMM":  # district@NN block@NN gram panchayat
        out["block_no"], out["block"] = numbered(parts[1])
        out["gp_no"], out["gram_panchayat"] = numbered(parts[2])
    elif shape == "TNNT":  # district@NN@NN@gram panchayat
        out["block_no"], out["gp_no"] = parts[1], parts[2]
        out["gram_panchayat"] = parts[3]
    elif shape == "TNM":  # district@NN@NN gram panchayat
        out["block_no"] = parts[1]
        out["gp_no"], out["gram_panchayat"] = numbered(parts[2])
    elif shape == "TMT":  # district@NN block@gram panchayat
        out["block_no"], out["block"] = numbered(parts[1])
        out["gram_panchayat"] = parts[2]
    elif shape == "NNT":  # the district is missing, the rest is not
        out["block_no"], out["gp_no"] = parts[0], parts[1]
        out["gram_panchayat"] = parts[2]
    elif shape == "TNT":
        # The trailing name is the block at panchayat samiti level and the gram
        # panchayat below it. Same shape, different meaning - which is why this
        # function needs the tier.
        out["block_no"] = parts[1]
        out["block" if tier == "panchayat_samiti" else "gram_panchayat"] = parts[2]
    elif shape == "NT":
        out["block_no"] = parts[0]
        out["block" if tier == "panchayat_samiti" else "gram_panchayat"] = parts[1]
    elif shape == "T":
        # A bare name is the gram panchayat at mukhiya level, where the
        # identifier is only ever the name, and the district at zila parishad
        # level, whose constituencies are numbered across the whole district.
        if tier == "mukhiya":
            out["gram_panchayat"] = parts[0]
    return out


def clean(cell):
    return re.sub(r"\s+", " ", (cell or "").replace("\n", " ")).strip()


# The post cell as the typesetters decorate it. "in" is पद, the word "post", and
# it appears both as a prefix - "in & xzke iapk;r eqf[k;k" - and as a trailing
# label. "xzke iapk;r eqf[k;k" is a gram panchayat's head, the same office as the
# bare "eqf[k;k"; the state prints it both ways and TIERS carried only one, so
# 217 rows in the Pakur, Giridih and Sahebganj notifications resolved to no post
# at all and their whole page fell through to the looser text reader.
POST_PREFIX = re.compile(r"^\s*in\s*&\s*")
POST_SUFFIX = re.compile(r"\s+in\s*$")
POST_OF_GP = re.compile(r"^\s*xzke\s+iapk;r\s+(?:ds\s+)?")


def tier_of(cell):
    """The office a post cell names.

    Exact against TIER_BY_KEY, and the decorations are stripped rather than
    matched loosely: "neoqf[k;k" is a *deputy* mukhiya and a substring match
    would file it as the head. Each fallback still has to land on a whole key,
    which is why the header cells - "eqf[k;k ftlls in lacaf/kr gS" - stay
    unmatched, as they must.
    """
    text = _undouble(clean(cell))
    found = TIER_BY_KEY.get(text)
    if found:
        return found
    bare = POST_SUFFIX.sub("", POST_PREFIX.sub("", text))
    found = TIER_BY_KEY.get(bare)
    if found:
        return found
    return TIER_BY_KEY.get(POST_OF_GP.sub("", bare))


# Folder names as filed, and the district they name. Only where the folder is
# wrong: "9. GOODA MUKHIYA PSS GPS ZP" is Godda, and left as filed it would
# pool as a 25th district that does not exist and fail to join to any other
# source on name.
FOLDER_TYPOS = {"Gooda": "Godda"}


def district_of(folder):
    """Convert a folder such as ``1. GARHWA MUKHIYA PSS`` to ``Garhwa``.

    The folder names are the only readable place-names in this corpus.
    """
    name = re.sub(r"^\s*\d+\s*[.)]?\s*", "", folder.name)
    name = re.sub(r"\b(MUKHIYA|PSS|GPS|ZP)\b", "", name, flags=re.I)
    name = re.sub(r"[()&]", " ", name)
    name = " ".join(name.split()).title()
    return FOLDER_TYPOS.get(name, name)


def seat_row(district, page_block, tier, caste, woman, raw, winner, raw_label):
    """One row, with the compound seat identifier taken apart.

    The block parsed out of the identifier wins over the one read from the page
    header: the header is a page-level guess that does not change when the table
    crosses a block boundary mid-page, while the identifier is stated on the row
    itself.
    """
    seat = split_seat_id(raw, tier)
    # `split_seat_id` reads the Kruti Dev identifier. A page that came back from
    # OCR carries the same identifier in Devanagari, and the splitter returns
    # nothing for it - so Chatra's 1,475 ward rows had no panchayat while the
    # name sat in the string they were built from: "|/ चतरा / ,/,/ मोनिया-(2)"
    # is ward 2 of मोनिया. The two readers disagree about the alphabet, not
    # about where the name is.
    if not seat.get("gram_panchayat") and DEVANAGARI.search(raw or ""):
        name, ward = dev_seat(raw)
        if name:
            seat = dict(seat, gram_panchayat=name)
            if ward and not seat.get("seat_no"):
                seat["seat_no"] = ward
    number = seat.get("seat_no", "")
    return {
        # Which of the two the block came from, so fill_block_names() can build
        # its lookup from the rows that state it and ignore the rest. Not a
        # declared column, so emit drops it.
        "block_from": "identifier"
        if seat.get("block")
        else ("page" if page_block else ""),
        "state": "Jharkhand",
        "year": "2015",
        "district": district,
        "block": seat.get("block") or page_block,
        "block_no": seat.get("block_no", ""),
        "gram_panchayat": seat.get("gram_panchayat", ""),
        "gp_no": seat.get("gp_no", ""),
        # the trailing number is the ward at ward-member level and the seat
        # within the district or block above it
        "ward_no": number if tier == "ward_member" else "",
        "seat_no": "" if tier == "ward_member" else number,
        "seat_id_raw": clean(raw),
        "tier": canon.tier_of(tier, "Jharkhand"),
        "tier_local": tier,
        "reservation": label(caste, woman),
        "caste_reservation": caste,
        "woman_reserved": woman,
        "winner": winner,
        "vacant": int(is_vacant(winner)),
        "reservation_raw": raw_label,
        "script": "krutidev",
    }


IMAGE_SEATS = JHARKHAND / "image_seats.csv"


def fill_image_seats(rows):
    """Fill the seats that were printed as pictures rather than text.

    Three pages of the Lohardaga notification draw their whole seat column as
    embedded images, so the text layer holds only the district's roman numeral
    and those rows identify no seat at all - the largest single key collision in
    the corpus. scripts/jharkhand/ocr_seats.py reads them; this joins the
    result back on.

    The join is on the serial number, which both sides state, and confirmed by
    the name beside it. It cannot be on position: the OCR finds more rows on a
    page than the parser does - 38 against 34 on page 22 - so matching by order
    would file every seat against the wrong person.
    """
    if not IMAGE_SEATS.exists():
        return 0, 0
    with IMAGE_SEATS.open(encoding="utf-8") as fh:
        found = {
            (r["source_pdf"], r["source_page"], r["serial"]): r
            for r in csv.DictReader(fh)
            if r["serial"]
        }
    # rows whose serial the OCR could not read are still usable by name
    with IMAGE_SEATS.open(encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            found.setdefault(
                (
                    r["source_pdf"],
                    r["source_page"],
                    f"~{r['gram_panchayat']}{r['ward_no']}",
                ),
                r,
            )
    if not found:
        return 0, 0

    # the same rows again, grouped by page, for the fallback below
    by_page = collections.defaultdict(list)
    for got in found.values():
        by_page[(got["source_pdf"], got["source_page"])].append(got)

    filled = rejected = 0
    for row in rows:
        if (row.get("gram_panchayat") or "").strip():
            continue
        page = (row.get("source_pdf", ""), str(row.get("source_page", "")))
        printed = krutidev.to_unicode(
            re.sub(r"^\s*\d{1,3}\s*", "", row.get("winner") or "")
        )
        serial = re.match(r"^\s*(\d{1,3})\b", row.get("winner") or "")
        got = found.get((*page, serial.group(1))) if serial else None
        if (
            got
            and got["name_ocr"]
            and printed
            and _similar(printed, got["name_ocr"]) < 0.5
        ):
            got = None
        if not got and printed:
            # On a page that mixes typeset rows with pasted-in pictures, the
            # serials the OCR reads are not a consecutive run, so anchoring
            # them lands on the wrong numbers - page 21 came out 45-49 where
            # the rows are 1-5. The name is the reliable key there; the serial
            # is only a cheaper one where it works.
            best, score = None, 0.0
            for candidate in by_page.get(page, ()):
                if not candidate["name_ocr"]:
                    continue
                similarity = _similar(printed, candidate["name_ocr"])
                if similarity > score:
                    best, score = candidate, similarity
            got = best if score >= 0.6 else None
        if not got:
            continue
        row["gram_panchayat"] = got["gram_panchayat"]
        # Only where the picture actually stated one. Assigning it flat blanked
        # a ward number the text layer had read correctly whenever the OCR had
        # not - 542 of the 1,235 drawn seats state no number, because a gram
        # panchayat head has no ward and a zila parishad constituency has none
        # either. Clearing a right value to record a missing one is the one
        # move here that is unambiguously a loss.
        row["ward_no"] = got["ward_no"] or row.get("ward_no", "")
        row["block_no"] = got["block_no"] or row.get("block_no", "")
        row["gp_no"] = got.get("gp_no") or row.get("gp_no", "")
        row["seat_from_image"] = 1
        filled += 1
    return filled, rejected


def _similar(a, b):
    """Overlap of two names, for confirming a join rather than making one."""
    left, right = set(a.replace(" ", "")), set(b.replace(" ", ""))
    return len(left & right) / max(len(left | right), 1)


def fill_block_names(rows):
    """Give a block its name where the row states only its number.

    Half the districts print the block as a number and nothing else
    ("yksgjnxk@5@10@ck?kk"), while the panchayat samiti sheets for the same
    district print both. So the name is recovered by joining on a key that both
    sides state, not by inferring anything.

    The lookup is built only from blocks that came from the seat identifier.
    The page header is not usable for it: it is read once per page and does not
    change when a table crosses a block boundary mid-page, which is how Dhanbad
    ended up with three different names against block 04.
    """
    lookup = collections.defaultdict(collections.Counter)
    for row in rows:
        if row.get("block_from") == "identifier" and row["block_no"]:
            lookup[(row["district"], row["block_no"])][row["block"]] += 1

    resolved = {
        key: names.most_common(1)[0][0]
        for key, names in lookup.items()
        if len(names) == 1
    }
    filled = 0
    for row in rows:
        if row.get("block_from") == "identifier" or not row["block_no"]:
            continue
        name = resolved.get((row["district"], row["block_no"]))
        if name:
            row["block"], filled = name, filled + 1
    return filled, len(lookup) - len(resolved)


# The office named by its head noun rather than its whole phrase. Ranchi splits
# the post across lines and interleaves it with the name - "ftyk ifj\"kn" on one
# line, a name fragment next, "lnL;" on the third - so the full phrase never
# appears contiguously. One district also writes "iapk;r lfefr ds lnL;" with an
# extra word. Order matters: gram panchayat and panchayat samiti share a word.
# Most specific first. "eqf[k;k" has to be tested before "xzke iapk;r",
# because a post reading "xzke iapk;r eqf[k;k" - the panchayat's head - would
# otherwise match the ward member's token and file a head as a ward. Ranchi
# produced no mukhiya rows at all until this order was fixed, while reading
# 2,125 rows as ward members.
TIER_HEADS = [
    ("eqf[k;k", "mukhiya"),
    ('ftyk ifj"kn', "zila_parishad"),
    ("iapk;r lfefr", "panchayat_samiti"),
    ("xzke iapk;r", "ward_member"),
    # the same offices as a scan reads them, in Unicode rather than Kruti Dev,
    # and in the same order for the same reason
    ("मुखिया", "mukhiya"),
    ("जिला परिषद", "zila_parishad"),
    ("पंचायत समिति", "panchayat_samiti"),
    ("ग्राम पंचायत", "ward_member"),
]

STACKED_CASTE = re.compile(
    r"vuk[fj]+\{kr|vuq\S*\s*tu\s*tkfr|vuq\S*\s*tkfr|fiNM\+k"
    r"|अनारक्षित|अनु\S*\s*जन\s*जाति|अनु\S*\s*जाति|पिछ\S*\s*वर्ग"
)
# "अन्य पिछड़ा वर्ग" is a caste, so the gender marker must not match inside it
STACKED_GENDER = re.compile(r"(efgyk|vU;|महिला|अन्य)(?!\s*(?:fiNM|पिछ))")


def parse_stacked(path, district):
    """Read a document whose rows are stacked three lines deep.

    Ranchi's gazette puts the name and the post in cells tall enough to wrap, so
    a record spans three lines: the reservation, the gender and the seat
    identifier sit on the middle one while the name and post are spread above
    and below it. Neither the table reader nor the single-line text reader finds
    anything, and Ranchi - Jharkhand's largest district - came out with nothing
    at all across 253 pages.

    Anchored on the reservation line, because that is the one line guaranteed to
    carry a whole record's worth of fields.

    A row is emitted only where the post explicitly names an office. About a
    thousand rows here say only "lnL;" - member - with the office too far away
    to attribute, and the seat identifier cannot settle it: a panchayat samiti
    seat and a ward seat have the same shape, which is exactly why
    split_seat_id has to be told the tier rather than infer it. Guessing would
    put block seats and ward seats in one bucket.
    """
    rows = []
    block = ""
    for page_number, text in stacked_pages(path):
        # An OCR'd page is Surya's HTML, which html_rows reads structurally.
        # Read as flat text it collapses into one "row" whose winner is a
        # screenful of <td> tags, and two of those were enough to cost 115 real
        # mukhiya seats in Latehar: merge() works per tier, so a tier holding
        # any rows at all is treated as answered and the true rows are dropped.
        # "<td", not "<td>": Surya writes the cell tag bare on most pages and
        # as <td style="width: 15%;"> on others, and testing for the bare form
        # let one Latehar page through, which was enough to cost the tier.
        if "<td" not in text:
            header = RE_BLOCK.search(text)
            if header:
                block = clean(header.group(1))
            lines = text.split("\n")
            for index, line in enumerate(lines):
                caste_at = STACKED_CASTE.search(line)
                if not caste_at:
                    continue
                gender_at = STACKED_GENDER.search(line, caste_at.end())
                if not gender_at:
                    continue
                # Pakur's mukhiya list, and Ranchi's, name no seat at all -
                # the gender is the last column and no panchayat is identified
                # anywhere on the page. Those rows are still a reservation for
                # a real seat; they simply do not say which, so they are kept
                # with an empty identifier rather than dropped. 364 rows.
                seat = line[gender_at.end() :].strip()
                left = [line[: caste_at.start()]]
                for other in (index - 1, index + 1):
                    if 0 <= other < len(lines) and not STACKED_CASTE.search(
                        lines[other]
                    ):
                        left.append(lines[other][: caste_at.start()])
                joined = clean(" ".join(left))
                if "in vkjf{kr" in joined:  # the column header
                    continue

                tier = next((v for k, v in TIER_HEADS if k in joined), None)
                if not tier:
                    continue
                caste = caste_of(line[caste_at.start() : gender_at.start()])
                woman = woman_of(gender_at.group(1))
                if caste is None or woman is None:
                    continue
                name = joined
                for key, _ in TIER_HEADS:
                    name = name.replace(key, " ")
                name = clean(re.sub(r"lnL;|\bds\b", " ", name))
                if emit.is_header_text(name):
                    continue
                # The identifier settles head against ward where the post text
                # cannot. A mukhiya seat is "XX jkaph @01@01&yijk" - three
                # parts, no ward number, one per panchayat - while a ward is
                # "XX jk¡ph @01@01@yijk& ¼2½". 88 rows whose post read only
                # "gram panchayat" were heads filed as ward members until this
                # looked at what the seat itself says.
                # only where there is an identifier to read - with none, the
                # post text is the only evidence and overriding it would turn
                # every unidentified ward seat into a panchayat head
                if (
                    seat
                    and tier == "ward_member"
                    and not split_seat_id(seat, "ward_member").get("seat_no")
                ):
                    tier = "mukhiya"
                rows.append(
                    emit.stamp(
                        seat_row(
                            district,
                            block,
                            tier,
                            caste,
                            woman,
                            seat,
                            name,
                            f"{line[caste_at.start() : gender_at.start()].strip()} | "
                            f"{gender_at.group(1)}",
                        ),
                        path,
                        page_number,
                        ROOT,
                    )
                )
    return rows


def stacked_pages(path):
    """The document's pages as text, from its own layer or from OCR.

    Six districts ship the same form as a photograph, so pdftotext returns
    nothing and they contributed no rows at all. scripts/jharkhand/ocr.py caches
    them; a scan reads into Unicode Devanagari, which is easier than the Kruti
    Dev the typeset districts use.
    """
    with pdfplumber.open(str(path)) as pdf:
        pages = [
            (page.page_number, page.extract_text(layout=True) or "")
            for page in pdf.pages
        ]
    # Readability, not length. Chatra and the Godda blocks carry 86,000 to
    # 375,000 characters of a third legacy font - neither Kruti Dev nor Unicode
    # - which decodes to "grgo-s r€-.Ff{ 6rzr rorRrf,". Testing the length let
    # that through and the OCR cache went unread, so three districts stayed
    # empty while their text sat in data/jharkhand/ocr.
    cached = OCR_CACHE / f"{path.stem}.txt"
    if cached.exists() and model_read_it(cached):
        return list(enumerate(cached.read_text(encoding="utf-8").split("\f"), 1))

    joined = "\n".join(t for _, t in pages)
    if any(key in joined for key, _ in TIER_HEADS):
        return pages
    if not cached.exists():
        return pages
    return list(enumerate(cached.read_text(encoding="utf-8").split("\f"), 1))


def model_read(path):
    """Whether this document's OCR is worth preferring over its text layer."""
    cached = OCR_CACHE / f"{path.stem}.txt"
    return cached.exists() and model_read_it(cached)


def model_read_it(cached):
    """Did the OCR actually read this document, or only transcribe its wreckage?

    Every Jharkhand document has now been read twice, and the model wins on most
    of them - Deoghar goes from 844 rows to 2,311. On twenty-nine it returns
    nothing usable, because the *render* is broken before the model sees it:
    those PDFs set their Devanagari in Kruti Dev without embedding it, so poppler
    has no such font to draw with and puts the raw Latin codepoints on the page.
    The model then faithfully transcribes Latin. Palamu's "पंचायत समिति सदस्य"
    arrives as "i p k r l fefr l nL;", and its rendered page is visibly wrecked
    to a human too.

    Preferring OCR everywhere would have cost 3,206 rows. Keeping the text layer
    everywhere would have cost about 1,500. So the choice is per document, and
    the discriminator is whether the output is Devanagari at all - which splits
    this corpus at 3.1% against 10.6%, a gap wide enough that no document sits
    near the line.
    """
    text = cached.read_text(encoding="utf-8")
    return len(DEVANAGARI.findall(text)) / max(len(text), 1) > 0.10


LEADING_SERIAL = re.compile(r"^\s*\d{1,3}\s*[.)|]?\s+(?=\S)")


def table_row(cells):
    """One ruled-table row, located by its post rather than by position.

    The columns were indexed flat - post at 1, caste at 2, gender at 3, the seat
    at 4 - which holds only for documents that print no serial number. Eight of
    them do print one, so every field shifted by one, `tier_of` saw a person's
    name, the row was rejected here, and the looser text reader downstream picked
    it up with the serial welded onto the winner: "1 pk¡nh igkfM+u iz[k.M& f" is
    a serial, a name, and the block header that followed it on the same line.
    2,212 rows carried a winner that was not anybody's name.

    Anchoring on the post is the same fix html_rows already applies to the OCR'd
    pages, and for the same reason: the layout decides whether a serial is a
    column, and a fixed offset silently reads the wrong field where it is.

    Falls back to the flat offsets when nothing resolves to a post, so a document
    that parses correctly today cannot change.
    """
    at = next((i for i, cell in enumerate(cells) if tier_of(cell)), None)
    if at is None or at + 2 >= len(cells):
        return None
    tier = tier_of(cells[at])
    caste, woman = caste_of(cells[at + 1]), woman_of(cells[at + 2])
    if caste is None or woman is None:
        return None
    # The seat identifier is the cell after the gender where the form carries
    # one, and Pakur's does not - its table stops at the gender, and the block is
    # a page header instead. Reading past the end there invented a seat.
    seat = cells[at + 3] if at + 3 < len(cells) else ""
    winner = LEADING_SERIAL.sub("", cells[at - 1]) if at else ""
    return tier, caste, woman, seat, winner, f"{cells[at + 1]} | {cells[at + 2]}"


def parse_pdf(path, district):
    rows = []
    block = ""
    with pdfplumber.open(str(path)) as pdf:
        for page in pdf.pages:
            found = RE_BLOCK.search(page.extract_text() or "")
            if found:
                block = clean(found.group(1))
            before = len(rows)
            for table in page.find_tables():
                for raw in table.extract():
                    cells = [clean(c) for c in raw]
                    if len(cells) < 5:
                        continue
                    got = table_row(cells)
                    if not got:
                        continue  # header, spacer, or an unknown post
                    tier, caste, woman, seat, winner, label_raw = got
                    rows.append(
                        emit.stamp(
                            seat_row(
                                district,
                                block,
                                tier,
                                caste,
                                woman,
                                seat,
                                winner,
                                label_raw,
                            ),
                            path,
                            page.page_number,
                            ROOT,
                        )
                    )

            # The text reader runs on every page, not only where the table
            # reader found nothing, and its rows are added where the table did
            # not already produce that seat.
            #
            # It used to be all-or-nothing per page, which was survivable only
            # while the table reader failed on whole pages at a time. Once it
            # started succeeding on most rows of a page, the pages where a few
            # rows still failed - Deoghar and Dhanbad split the gender onto its
            # own extracted line, so `woman_of` sees an empty cell - stopped
            # falling back at all, and 31 real winners disappeared.
            rows[before:] = union(
                rows[before:], _from_text(page, path, district, block)
            )
    return rows


def page_key(row):
    """What makes two readings of one page the same seat.

    The identifier *and* the winner, not the identifier alone. Keying on the
    identifier by itself cost 266 rows: on Koderma's image pages the seat column
    is a picture, so the text layer keeps only the district's roman numeral and
    every row on the page reads "VI". Two hundred and sixty-one distinct seats
    collapsed into one.

    The winner is safe to key on because both readers now strip the leading
    serial, so they render the same person identically - which was itself a bug
    worth 963 duplicate seats before it was fixed.
    """
    return (
        row.get("tier_local"),
        (row.get("seat_id_raw") or "").strip(),
        (row.get("winner") or "").strip(),
    )


def union(table, text):
    """Both readers' rows for one page, each seat once.

    The text reader used to run only where the table reader found nothing on the
    whole page. That held while the table reader failed by the page; once it
    started succeeding on most rows, pages with a few stragglers stopped falling
    back and 31 real winners vanished. So both always run.

    Where they disagree about a seat, the row that names a winner wins. The
    table reader returns an empty name on layouts that put the name somewhere it
    does not look, and an empty name is not a competing answer - it is the
    absence of one.
    """
    best = {}
    for row in list(table) + list(text):
        best.setdefault(page_key(row), row)
    rows = list(best.values())

    # A row the table reader could not name is superseded by a text row for the
    # same printed seat. An empty name is not a competing answer, it is the
    # absence of one - but only where the page prints an identifier to match on,
    # because "VI" and "" identify nothing and would merge the whole page.
    named = {
        (r.get("tier_local"), (r.get("seat_id_raw") or "").strip())
        for r in rows
        if (r.get("winner") or "").strip()
    }
    return [
        r
        for r in rows
        if (r.get("winner") or "").strip()
        or not (r.get("seat_id_raw") or "").strip()
        or (r.get("tier_local"), (r.get("seat_id_raw") or "").strip()) not in named
    ]


def identity(row):
    """What makes two readings of the same seat the same row.

    Not the raw identifier: the two readers take the page apart differently and
    render it differently. The office, the place and who was elected are what
    both agree on.
    """
    return (
        row.get("tier_local"),
        row.get("block"),
        row.get("gram_panchayat"),
        row.get("ward_no"),
        row.get("seat_no"),
        row.get("winner"),
    )


def merge(first, second):
    """The first reader's rows, plus the second's for tiers it found none of.

    Per tier, not per row. The second reader is a fallback because it is the
    less precise one - it anchors on a post token in loosely-laid-out text - and
    merging it row by row let it add 1,812 mukhiya seats to a state with 4,345
    gram panchayats, 542 of them in a Chatra that has about 180. Where the
    precise reader found a tier, its answer stands.

    What this does fix is the case it was written for: Ranchi's notification
    yields 3,453 ward rows and no mukhiya at all from the ruled-table reader,
    and the stacked reader finds the 95 mukhiya and 35 zila parishad seats.
    Taking whichever answered first dropped whichever tier the other held.
    """
    have = {r.get("tier_local") for r in first}
    return list(first) + [r for r in second if r.get("tier_local") not in have]


def dev_seat(text):
    """The panchayat and the seat number out of a Devanagari identifier."""
    got = RE_DEV_SEAT.search(clean(text))
    if not got:
        return "", ""
    name = re.sub(r"^[\W\d_]+", "", got.group("panchayat")).strip()
    return name, got.group("number")


HTML_ROW = re.compile(r"<tr[^>]*>(.*?)</tr>", re.S | re.I)
HTML_CELL = re.compile(r"<td[^>]*>(.*?)</td>", re.S | re.I)
HTML_TAG = re.compile(r"<[^>]+>")


def html_cells(row):
    return [
        clean(html.unescape(HTML_TAG.sub(" ", cell))) for cell in HTML_CELL.findall(row)
    ]


def html_rows(text, path, district, page_number):
    """Rows off a Surya page, which comes back as an HTML table.

    The whole reason to re-OCR was that tesseract dropped the numbers out of the
    seat identifier. Surya keeps them *and* keeps the district's roman numeral -
    "IV/चतरा /5/18/सलैया –(1)" - which the Devanagari line reader could not.
    So these rows go through `seat_row` like any other, and `split_seat_id` reads
    the block and gram panchayat numbers that the Devanagari reader below has no
    way to reach. That is where the recovery actually lands: 28.6% of identifiers
    resolving to a complete seat identity, against 91.4%.

    Cells are located by anchoring on the post rather than by position. The
    ruled-table reader can index cells[1..4] because pdfplumber gives it the
    columns the rules define; Surya decides for itself whether the serial number
    is a column, and a fixed offset would silently read the caste out of the
    post's cell on the pages where it does.
    """
    out = []
    for raw_row in HTML_ROW.findall(text):
        cells = html_cells(raw_row)
        if len(cells) < 4:
            continue
        at = next((i for i, cell in enumerate(cells) if dev_post(cell)), None)
        if at is None or at + 2 >= len(cells):
            continue
        tier = dev_post(cells[at])
        caste, woman = caste_of(cells[at + 1]), woman_of(cells[at + 2])
        if caste is None or woman is None:
            continue
        # The cell after the gender, not the last cell. Pakur's form stops at
        # the gender - serial, name, post, caste, gender, and no seat column at
        # all - so taking the last cell published "महिला" as 134 seats'
        # identifier, and split_seat_id then read that word as their gram
        # panchayat. "रिक्त" and "निर्विरोध" arrived the same way. The winner is
        # whatever precedes the post, which is the name column on every form
        # here.
        seat = cells[at + 3] if at + 3 < len(cells) else ""
        winner = cells[at - 1] if at else ""
        row = seat_row(
            district,
            "",
            tier,
            caste,
            woman,
            seat,
            winner,
            f"{cells[at + 1]} | {cells[at + 2]}",
        )
        # not Kruti Dev, so `krutidev.to_unicode` must not touch these names
        row["script"] = "devanagari"
        out.append(emit.stamp(row, path, page_number, ROOT))
    return out


def ocr_rows(text, path, district, page_number):
    """Rows off an OCR'd page.

    One reader, not two with a fallback. Surya returns 565 of this corpus' 594
    pages as a table, and the 29 that are not are covers and preamble carrying
    no seats at all - measured, by running this reader over them and counting
    what it found. The Devanagari line reader this used to fall through to had
    nothing left to find, and keeping it "just in case" is how two readers end
    up disagreeing about the same page.
    """
    return html_rows(text, path, district, page_number)


def _from_text(page, path, district, block):
    """Read a page that has no ruled table, using the post token as the anchor."""
    out = []
    for line in (page.extract_text(layout=True) or "").split("\n"):
        found = RE_TEXT_ROW.match(clean(line))
        if not found:
            continue
        tier = tier_of(found.group("post"))
        caste = caste_of(found.group("caste"))
        woman = woman_of(found.group("woman"))
        if not tier or caste is None or woman is None:
            continue
        # Stripped here as well as in the table reader, so the two produce the
        # same string for the same person. They did not, and the page-level
        # dedupe keys on the winner: "1 रेखा देवी" and "रेखा देवी" read as two
        # women and 963 seats were published twice, putting panchayat samiti at
        # 109% of the seats Jharkhand has.
        winner = LEADING_SERIAL.sub("", clean(found.group("name")))
        out.append(
            emit.stamp(
                seat_row(
                    district,
                    block,
                    tier,
                    caste,
                    woman,
                    found.group("seat"),
                    winner,
                    f"{found.group('caste')} | {found.group('woman')}",
                ),
                path,
                page.page_number,
                ROOT,
            )
        )
    return out


@command("parse", state="Jharkhand")
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, help="only the first N district folders")
    args = ap.parse_args()

    folders = sorted(p for p in JHARKHAND.iterdir() if p.is_dir())[: args.limit]
    rows, failed = [], []
    for folder in folders:
        district = district_of(folder)
        # PDFs are nested a further level in several districts
        # (HAZARIBAG/HAZARIBAG MUKHIYA/*.pdf), so this must recurse -
        # a top-level glob saw 36 of the 117 files and silently lost
        # two thirds of the state.
        for path in sorted(folder.rglob("*.pdf")):
            try:
                read_by_model = [
                    r
                    for number, text in stacked_pages(path)
                    for r in ocr_rows(text, path, district, number)
                ]
                # Merged, not chosen between. Ranchi's notification is read by
                # both readers and each finds tiers the other misses: the
                # ruled-table reader gets 3,453 ward rows and no mukhiya at all,
                # the stacked reader 2,171 ward rows plus the 95 mukhiya and 35
                # zila parishad seats. Taking whichever answered first silently
                # dropped whichever tier the other one held.
                #
                # Which goes first decides which wins, because merge() works per
                # tier. The text layer led, and so the model's reading was
                # discarded for every tier the text layer also found - Ranchi
                # published 4,245 rows of which 61 had a Devanagari seat
                # identifier, because only zila parishad, the one tier the text
                # layer missed, came from the model at all. Where the page
                # renders properly the model is the better reader, so it leads.
                if model_read(path):
                    got = merge(read_by_model, parse_pdf(path, district))
                    got = merge(got, parse_stacked(path, district))
                else:
                    got = parse_pdf(path, district)
                    got = merge(got, parse_stacked(path, district))
                    got = merge(got, read_by_model)
                rows += got
            except Exception as exc:
                failed.append((path.name, type(exc).__name__))
                LOGGER.exception(
                    "Source parse failed",
                    extra={
                        "event": "source_parse_failed",
                        "district": district,
                        "source_file": path.name,
                        "error_type": type(exc).__name__,
                    },
                )
        LOGGER.info(
            "District parsed",
            extra={
                "event": "district_parsed",
                "district": district,
                "rows": len(rows),
            },
        )

    # after every district is read, because a block named only by number in one
    # district's sheets is named in full in another's
    filled, ambiguous = fill_block_names(rows)
    from_images, rejected = fill_image_seats(rows)
    if from_images or rejected:
        LOGGER.info(
            "Image seat identifiers reconciled",
            extra={
                "event": "image_seats_reconciled",
                "filled_rows": from_images,
                "rejected_rows": rejected,
            },
        )

    # The names are printed in Kruti Dev, a font encoding rather than damage, so
    # they convert deterministically. Left as printed they cannot be joined to
    # any other source on name, which was the largest recoverable gap in the
    # corpus. seat_id_raw keeps the string exactly as the page had it.
    # district is not in this list: it comes from the folder name and is
    # already English, so running it through the converter turned "Garhwa" into
    # "घ्ंतीूं" - real-looking Devanagari for a word that was never Kruti Dev.
    #
    # `winner` was missing from this list while `script` was set to devanagari
    # regardless, so 17,115 rows shipped a person's name in Kruti Dev under a
    # label saying it was Unicode. The cost is not cosmetic: अनिता देवी appears
    # 92 times as `vfurk nsoh` and 55 times as अनिता देवी, so the same woman
    # counts as two people depending on whether her district was scanned or
    # typeset, and anything joining or grouping on name is wrong.
    #
    # Verified against Surya rather than against the table itself - the model
    # reads the rendered glyphs and owes nothing to this mapping. On Garhwa's
    # first page all 23 converted names appear in Surya's reading, and the
    # fixed vocabulary settles it beyond the names: "O;fDr dk uke" becomes
    # व्यक्ति का नाम, which a wrong table would not produce.
    converted = 0
    for row in rows:
        for column in ("block", "gram_panchayat", "winner"):
            value = row.get(column) or ""
            if value and not krutidev.looks_converted(value):
                row[column] = krutidev.to_unicode(value)
                converted += 1
        # Describes what the row holds, not what this loop attempted. A value
        # the converter could not turn into Devanagari - a stray Latin token,
        # an empty page - must not be labelled as though it had been.
        names = [row.get(c) or "" for c in ("gram_panchayat", "winner")]
        row["script"] = (
            "devanagari"
            if any(krutidev.looks_converted(n) for n in names)
            else "krutidev"
        )
    LOGGER.info(
        "Kruti Dev names converted to Unicode",
        extra={"event": "names_converted", "converted_values": converted},
    )
    LOGGER.info(
        "Block names joined",
        extra={
            "event": "block_names_joined",
            "filled_rows": filled,
            "ambiguous_keys": ambiguous,
        },
    )

    by_tier = collections.defaultdict(list)
    for row in rows:
        by_tier[row["tier_local"]].append(row)

    for tier in sorted(by_tier):
        subset = by_tier[tier]
        stem = ROOT / "data" / "jharkhand" / f"{tier}_reservation_2015"
        csv_path, _ = emit.write(subset, stem, COLUMNS)
        districts = {r["district"] for r in subset}
        blocks = {(r["district"], r["block"]) for r in subset}
        women = sum(r["woman_reserved"] for r in subset)
        print(
            f"{tier:18s} {len(subset):6d} seats  {len(blocks):4d} blocks  "
            f"{len(districts):2d}/{len(folders)} districts  "
            f"women {women / max(len(subset), 1) * 100:4.1f}%  -> {csv_path.name}"
        )

    print("\nmukhiya reservation split:")
    for k, v in collections.Counter(
        r["reservation"] for r in by_tier["mukhiya"]
    ).most_common():
        print(f"   {v:6d}  {v / max(len(by_tier['mukhiya']), 1) * 100:5.1f}%  {k}")
    if failed:
        print(f"\nunreadable: {len(failed)} -> {failed[:5]}")


if __name__ == "__main__":
    main()
