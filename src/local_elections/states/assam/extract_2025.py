"""Extract source-faithful records from Assam's 2025 PRI notifications.

Acquisition is handled by :mod:`harvest`. This module is the next boundary:
PDF pages become raw JSONL, and reviewed table cells become source-faithful
records. It does not assign canonical tiers or reservation labels; that is the
parser's job.

Charaideo and Kamrup Metropolitan are the first district adapters. Both have
usable embedded text, but they use different tables: Charaideo prints a GP
summary plus reserved-seat lists, while Kamrup Metropolitan prints every seat
and its status. Reviewed transcriptions are guarded by source SHA-256 values.
"""

import hashlib
import json
import re
import subprocess

import pdfplumber

from local_elections.common.runlog import command, get_logger
from local_elections.paths import ROOT

LOGGER = get_logger(__name__)

SOURCE = ROOT / "data" / "assam" / "2025_reservation" / "charaideo_reservation.pdf"
SOURCE_SHA256 = "acce736f20e0fb2f1b9d7780332ea933b9a1009a72bc635691109af1fe0d9c91"
OUT = ROOT / "data" / "assam" / "2025_extracted"
PAGES = OUT / "charaideo_pages.jsonl"
GP_ROSTER = OUT / "charaideo_gp_roster.jsonl"
OFFICE_ASSIGNMENTS = OUT / "charaideo_office_assignments.jsonl"
KAMRUP_METROPOLITAN_SOURCE = (
    ROOT / "data" / "assam" / "2025_reservation" / "reservation_kamrup_m.pdf"
)
KAMRUP_METROPOLITAN_SHA256 = (
    "f9f963f017602deb33a93019beb04e7dd5c7a009f42f7a893b0ce93d6857bcfd"
)
KAMRUP_METROPOLITAN_PAGES = OUT / "kamrup_metropolitan_pages.jsonl"
KAMRUP_METROPOLITAN_GP_ROSTER = OUT / "kamrup_metropolitan_gp_roster.jsonl"
KAMRUP_METROPOLITAN_OFFICES = OUT / "kamrup_metropolitan_office_assignments.jsonl"
KAMRUP_METROPOLITAN_WARDS = OUT / "kamrup_metropolitan_ward_assignments.jsonl"

# serial|ZPC|AP|GP|SC ward count|ST ward count|women wards|SC-women wards|
# ST-women wards|SC-open wards|ST-open wards
GP_TABLE = """
1|Sapekhati|Sapekhati|Ahukhat|0|0|2,4,6,9,10||||
2|Sapekhati|Sapekhati|Borguri|0|0|8,2,10,5,4||||
3|Sapekhati|Sapekhati|Milonjyoti|0|1|4,7,8,9,10||||6
4|Sapekhati|Sapekhati|Rahan|0|0|2,8,6,5,7||||
5|Sapekhati|Sapekhati|Sapekhati|1|0|6,3,5,7,10|6|||
6|Sapekhati|Sapekhati|Udayshree|0|0|7,10,1,3,2||||
7|Baruasali|Sapekhati|Bhuyakhat|0|0|8,5,2,4,1||||
8|Baruasali|Sapekhati|Borhat|0|0|1,6,7,8,10||||
9|Baruasali|Sapekhati|Nahorpukhuri|0|0|2,3,5,7,9||||
10|Baruasali|Sapekhati|Purbanchal|0|0|4,5,6,7,8||||
11|Baruasali|Sapekhati|Sonali|0|0|2,3,4,5,8||||
12|Sonari|Sonari|Bhojo|0|0|3,7,4,1,9||||
13|Sonari|Sonari|Sonari|0|0|4,6,1,2,9||||
14|Sonari|Sonari|Rajapukhuri|0|0|4,6,7,9,10||||
15|Sonari|Sonari|Towkak|0|0|3,5,7,10,6||||
16|Haridev|Sonari|Bengenabari|0|1|9,7,6,2,1||9||
17|Haridev|Sonari|Haridev|0|0|9,1,5,7,3||||
18|Haridev|Sonari|Longpotia|0|1|10,5,2,6,9||10||
19|Haridev|Sonari|Sarupather|0|1|1,5,10,3,6||1||
20|Charaideo|Lakwa|Charaideo|0|0|8,3,9,7,10||||
21|Charaideo|Lakwa|Hollowphukan|0|0|5,6,2,3,8||||
22|Charaideo|Lakwa|Nimonagarh|0|0|1,7,8,9,10||||
23|Suffry|Lakwa|Abhoipur|0|0|9,10,2,8,1||||
24|Suffry|Lakwa|Chalapathar|0|0|5,4,9,7,6||||
25|Suffry|Lakwa|Suffry|2|0|8,4,3,5,9|8||7|
26|Rangoli|Mahmora|Bordoba|0|0|1,9,5,2,10||||
27|Rangoli|Mahmora|Desangpani|0|0|1,9,2,7,10||||
28|Rangoli|Mahmora|Doba|0|0|1,3,5,8,9||||
29|Rangoli|Mahmora|Nizkhaloighugura|0|0|3,5,8,9,10||||
30|Rangoli|Mahmora|Milon|0|1|3,5,6,7,8||||1
31|Rangoli|Mahmora|Sepon|0|0|2,4,5,6,7||||
32|Mahmora|Mahmora|Bhoralipukhuri|0|0|4,6,9,8,2||||
33|Mahmora|Mahmora|Kakotibari|0|0|10,1,7,5,9||||
34|Mahmora|Mahmora|Khumtai|0|0|5,9,7,4,3||||
35|Mahmora|Mahmora|Sarbudoi|0|0|9,10,2,3,4||||
36|Mahmora|Mahmora|Udoipur|0|2|1,2,5,7,6||1||9
"""

# office|page|block|seat|caste|woman|source wording
OFFICE_TABLE = """
zp_member|2||Baruasali|NONE|1|Reserved for Women
zp_member|2||Sapekhati|NONE|1|Reserved for Women
zp_member|2||Rangoli|NONE|1|Reserved for Women
zp_member|2||Mahmora|NONE|1|Reserved for Women
block_member|3|Sonari|Haridev|NONE|1|Reserved for Women
block_member|3|Sonari|Towkak|NONE|1|Reserved for Women
block_member|3|Sonari|Sarupather|NONE|1|Reserved for Women
block_member|3|Sonari|Bhojo|NONE|1|Reserved for Women
block_member|3|Sapekhati|Rahan|NONE|1|Reserved for Women
block_member|3|Sapekhati|Sapekhati|NONE|1|Reserved for Women
block_member|3|Sapekhati|Sonali|NONE|1|Reserved for Women
block_member|3|Sapekhati|Purbanchal|NONE|1|Reserved for Women
block_member|3|Sapekhati|Ahukhat|NONE|1|Reserved for Women
block_member|3|Sapekhati|Udayshree|NONE|1|Reserved for Women
block_member|4|Mahmora|Milon|NONE|1|Reserved for Women
block_member|4|Mahmora|Bhoralipukhuri|NONE|1|Reserved for Women
block_member|4|Mahmora|Khumtai|NONE|1|Reserved for Women
block_member|4|Mahmora|Doba|NONE|1|Reserved for Women
block_member|4|Mahmora|Bordoba|NONE|1|Reserved for Women
block_member|4|Lakwa|Hollowphukan|NONE|1|Reserved for Women
block_member|4|Lakwa|Charaideo|NONE|1|Reserved for Women
block_member|4|Lakwa|Nimonagarh|NONE|1|Reserved for Women
block_head|5|Lakwa|Lakwa|NONE|1|Reserved for Women
block_head|5|Sapekhati|Sapekhati|NONE|1|Reserved for Women
block_vice_head|5|Sonari|Sonari|NONE|1|Reserved for Women
block_vice_head|5|Mahmora|Mahmora|NONE|1|Reserved for Women
gp_head|7|Sonari|Haridev|NONE|1|Reserved for Women
gp_head|7|Sonari|Bhojo|NONE|1|Reserved for Women
gp_head|7|Sonari|Towkak|NONE|1|Reserved for Women
gp_head|7|Sonari|Rajapukhuri|NONE|1|Reserved for Women
gp_head|7|Sapekhati|Purbanchal|NONE|1|Reserved for Women
gp_head|7|Sapekhati|Ahukhat|NONE|1|Reserved for Women
gp_head|7|Sapekhati|Milonjyoti|NONE|1|Reserved for Women
gp_head|7|Sapekhati|Borhat|NONE|1|Reserved for Women
gp_head|7|Sapekhati|Rahan|NONE|1|Reserved for Women
gp_head|7|Mahmora|Milon|NONE|1|Reserved for Women
gp_head|7|Mahmora|Desangpani|NONE|1|Reserved for Women
gp_head|7|Mahmora|Nizkhaloighugura|NONE|1|Reserved for Women
gp_head|7|Mahmora|Sepon|NONE|1|Reserved for Women
gp_head|7|Mahmora|Khumtai|NONE|1|Reserved for Women
gp_head|7|Mahmora|Udoipur|ST|1|Reserved for ST Women
gp_head|7|Lakwa|Chalapathar|NONE|1|Reserved for Women
gp_head|7|Lakwa|Suffry|SC|1|Reserved for SC Women
gp_head|7|Lakwa|Hollowphukan|NONE|1|Reserved for Women
gp_vice_head|7|Sonari|Sonari|NONE|1|Reserved for Women
gp_vice_head|7|Sonari|Longpotia|NONE|1|Reserved for Women
gp_vice_head|7|Sonari|Sarupather|NONE|1|Reserved for Women
gp_vice_head|7|Sonari|Bengenabari|NONE|1|Reserved for Women
gp_vice_head|7|Sapekhati|Borguri|NONE|1|Reserved for Women
gp_vice_head|7|Sapekhati|Sapekhati|SC|1|Reserved for SC Women
gp_vice_head|7|Sapekhati|Udayshree|NONE|1|Reserved for Women
gp_vice_head|7|Sapekhati|Bhuyakhat|NONE|1|Reserved for Women
gp_vice_head|7|Sapekhati|Sonali|NONE|1|Reserved for Women
gp_vice_head|7|Sapekhati|Nahorpukhuri|NONE|1|Reserved for Women
gp_vice_head|7|Mahmora|Bhoralipukhuri|NONE|1|Reserved for Women
gp_vice_head|7|Mahmora|Kakotibari|NONE|1|Reserved for Women
gp_vice_head|7|Mahmora|Doba|NONE|1|Reserved for Women
gp_vice_head|7|Mahmora|Bordoba|NONE|1|Reserved for Women
gp_vice_head|7|Mahmora|Sarbudoi|NONE|1|Reserved for Women
gp_vice_head|7|Lakwa|Nimonagarh|NONE|1|Reserved for Women
gp_vice_head|7|Lakwa|Abhoipur|NONE|1|Reserved for Women
gp_vice_head|7|Lakwa|Charaideo|NONE|1|Reserved for Women
gp_vice_head|6|Mahmora|Milon|ST|0|ST Reserved for GP Vice-President (Open)
"""

# serial|block|GP. These are the complete AP-member tables on pages 1--2.
KAMRUP_METROPOLITAN_GP_TABLE = """
1|Ramcharani|Majirgaon
2|Ramcharani|Garal
3|Ramcharani|Kahikuchi
4|Ramcharani|Dharapur
5|Ramcharani|Azara
6|Chandrapur|Panikhaiti
7|Chandrapur|Amsing
8|Chandrapur|Chandrapur
9|Dimoria|Kamarkuchi
10|Dimoria|Digaru
11|Dimoria|Barkhat
12|Dimoria|Baruabari
13|Dimoria|Hahara
14|Dimoria|Sonapur
15|Dimoria|Tetelia
16|Dimoria|Nartap
17|Dimoria|Khetri
18|Dimoria|Maloibari
19|Dimoria|Dhupguri
20|Dimoria|Topatoli
"""

# office|page|block|seat|printed status. Every office row is printed, including
# Unreserved. The transcription was checked against rendered pages 1--3.
KAMRUP_METROPOLITAN_OFFICE_TABLE = """
zp_member|1||Rani Chapari|Unreserved
zp_member|1||Deepor Beel|Women
zp_member|1||Pragjyotishpur|Women
zp_member|1||Barkhat|ST(Women)
zp_member|1||Sonapur|Unreserved
zp_member|1||Dimoria|SC
block_head|1|Ramcharani|Ramcharani|Unreserved
block_head|1|Chandrapur|Chandrapur|Women
block_head|1|Dimoria|Dimoria|Women
block_vice_head|1|Ramcharani|Ramcharani|Women
block_vice_head|1|Chandrapur|Chandrapur|Unreserved
block_vice_head|1|Dimoria|Dimoria|Women
block_member|1|Ramcharani|Majirgaon|Women
block_member|1|Ramcharani|Garal|Unreserved
block_member|1|Ramcharani|Kahikuchi|Women
block_member|1|Ramcharani|Dharapur|Women
block_member|1|Ramcharani|Azara|Unreserved
block_member|1|Chandrapur|Panikhaiti|Women
block_member|1|Chandrapur|Amsing|Unreserved
block_member|1|Chandrapur|Chandrapur|Women
block_member|1|Dimoria|Kamarkuchi|Unreserved
block_member|1|Dimoria|Digaru|ST(Women)
block_member|1|Dimoria|Barkhat|ST
block_member|1|Dimoria|Baruabari|Unreserved
block_member|2|Dimoria|Hahara|Women
block_member|2|Dimoria|Sonapur|Unreserved
block_member|2|Dimoria|Tetelia|Unreserved
block_member|2|Dimoria|Nartap|Women
block_member|2|Dimoria|Khetri|Women
block_member|2|Dimoria|Maloibari|SC
block_member|2|Dimoria|Dhupguri|Women
block_member|2|Dimoria|Topatoli|SC(Women)
gp_head|2|Ramcharani|Majirgaon|Unreserved
gp_head|2|Ramcharani|Garal|Women
gp_head|2|Ramcharani|Kahikuchi|Women
gp_head|2|Ramcharani|Dharapur|Women
gp_head|2|Ramcharani|Azara|Unreserved
gp_head|2|Chandrapur|Panikhaiti|Unreserved
gp_head|2|Chandrapur|Amsing|Women
gp_head|2|Chandrapur|Chandrapur|Unreserved
gp_head|2|Dimoria|Kamarkuchi|Women
gp_head|2|Dimoria|Digaru|ST
gp_head|2|Dimoria|Barkhat|ST(Women)
gp_head|2|Dimoria|Baruabari|Women
gp_head|2|Dimoria|Hahara|Women
gp_head|2|Dimoria|Sonapur|Unreserved
gp_head|2|Dimoria|Tetelia|Unreserved
gp_head|2|Dimoria|Nartap|Women
gp_head|2|Dimoria|Khetri|Unreserved
gp_head|2|Dimoria|Maloibari|SC(Women)
gp_head|2|Dimoria|Dhupguri|Unreserved
gp_head|2|Dimoria|Topatoli|SC
gp_vice_head|2|Ramcharani|Majirgaon|Unreserved
gp_vice_head|2|Ramcharani|Garal|Women
gp_vice_head|2|Ramcharani|Kahikuchi|Unreserved
gp_vice_head|2|Ramcharani|Dharapur|Unreserved
gp_vice_head|2|Ramcharani|Azara|Unreserved
gp_vice_head|2|Chandrapur|Panikhaiti|ST
gp_vice_head|2|Chandrapur|Amsing|Women
gp_vice_head|2|Chandrapur|Chandrapur|Unreserved
gp_vice_head|2|Dimoria|Kamarkuchi|Women
gp_vice_head|2|Dimoria|Digaru|Women
gp_vice_head|2|Dimoria|Barkhat|Women
gp_vice_head|2|Dimoria|Baruabari|SC
gp_vice_head|3|Dimoria|Hahara|SC(Women)
gp_vice_head|3|Dimoria|Sonapur|Women
gp_vice_head|3|Dimoria|Tetelia|Unreserved
gp_vice_head|3|Dimoria|Nartap|Unreserved
gp_vice_head|3|Dimoria|Khetri|Unreserved
gp_vice_head|3|Dimoria|Maloibari|Unreserved
gp_vice_head|3|Dimoria|Dhupguri|ST(Women)
gp_vice_head|3|Dimoria|Topatoli|Women
"""

KAMRUP_METROPOLITAN_PAGE_SERIALS = {
    3: (1, 18),
    4: (19, 41),
    5: (42, 61),
    6: (62, 81),
    7: (82, 97),
    8: (98, 116),
    9: (117, 139),
    10: (140, 153),
    11: (154, 164),
    12: (165, 180),
    13: (181, 195),
    14: (196, 200),
}


def _verify_source(path, expected, district):
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != expected:
        raise RuntimeError(
            f"Assam {district} source changed: expected {expected}, found {digest}"
        )


def verify_source():
    """Refuse to extract reviewed transcriptions from different bytes."""
    _verify_source(SOURCE, SOURCE_SHA256, "Charaideo")
    _verify_source(
        KAMRUP_METROPOLITAN_SOURCE,
        KAMRUP_METROPOLITAN_SHA256,
        "Kamrup Metropolitan",
    )


def _numbers(value):
    return [] if not value else [int(item) for item in value.split(",")]


def gp_records():
    """Return the 36 reviewed source rows from page 9."""
    records = []
    for line in GP_TABLE.strip().splitlines():
        (
            serial,
            zpc,
            block,
            gp,
            sc_count,
            st_count,
            women,
            sc_women,
            st_women,
            sc_open,
            st_open,
        ) = line.split("|")
        records.append(
            {
                "serial": int(serial),
                "district": "Charaideo",
                "zilla_parishad_constituency": zpc,
                "anchalik_panchayat": block,
                "gram_panchayat": gp,
                "ward_count": 10,
                "sc_reserved_ward_count": int(sc_count),
                "st_reserved_ward_count": int(st_count),
                "women_reserved_wards": _numbers(women),
                "sc_women_wards": _numbers(sc_women),
                "st_women_wards": _numbers(st_women),
                "sc_open_wards": _numbers(sc_open),
                "st_open_wards": _numbers(st_open),
                "source_page": 9,
                "review_status": "human_checked_from_rendered_page",
            }
        )
    return records


def office_records():
    """Return explicitly reserved office assignments from pages 2--7."""
    records = []
    for line in OFFICE_TABLE.strip().splitlines():
        office, page, block, seat, caste, woman, raw = line.split("|")
        records.append(
            {
                "office": office,
                "district": "Charaideo",
                "anchalik_panchayat": block,
                "seat": seat,
                "caste_reservation_raw": caste,
                "woman_reserved_raw": int(woman),
                "reservation_raw": raw,
                "source_page": int(page),
                "review_status": "human_checked_from_rendered_page",
            }
        )
    return records


def _reservation_parts(raw):
    normalized = re.sub(r"\s+", "", raw).upper()
    caste = (
        "SC"
        if normalized.startswith("SC")
        else "ST"
        if normalized.startswith("ST")
        else "NONE"
    )
    return caste, int("WOMEN" in normalized)


def kamrup_metropolitan_gp_records():
    """Return the complete 20-GP roster printed in the AP-member tables."""
    records = []
    for line in KAMRUP_METROPOLITAN_GP_TABLE.strip().splitlines():
        serial, block, gp = line.split("|")
        records.append(
            {
                "serial": int(serial),
                "district": "Kamrup Metropolitan",
                "anchalik_panchayat": block,
                "gram_panchayat": gp,
                "ward_count": 10,
                "source_page": 1 if int(serial) <= 12 else 2,
                "review_status": "human_checked_from_rendered_page",
            }
        )
    return records


def kamrup_metropolitan_office_records():
    """Return all office rows, including printed Unreserved statuses."""
    records = []
    for line in KAMRUP_METROPOLITAN_OFFICE_TABLE.strip().splitlines():
        office, page, block, seat, raw = line.split("|")
        caste, woman = _reservation_parts(raw)
        records.append(
            {
                "office": office,
                "district": "Kamrup Metropolitan",
                "anchalik_panchayat": block,
                "seat": seat,
                "caste_reservation_raw": caste,
                "woman_reserved_raw": woman,
                "reservation_raw": raw,
                "source_page": int(page),
                "review_status": "human_checked_from_rendered_page",
            }
        )
    return records


def _status_from_words(words):
    text = " ".join(word["text"] for word in words).upper()
    woman = "WOMEN" in text
    if "SC" in text:
        return "SC(Women)" if woman else "SC"
    if re.search(r"(^|\s)ST(?:\s|\(|$)", text):
        return "ST(Women)" if woman else "ST"
    if woman:
        return "Women"
    if any(
        word["text"].upper().startswith("UN")
        and ("SERV" in word["text"].upper() or "YESERV" in word["text"].upper())
        for word in words
    ):
        return "Unreserved"
    return None


def _word_lines(words, tolerance=2.5):
    lines = []
    for word in sorted(words, key=lambda item: (item["top"], item["x0"])):
        if lines and abs(lines[-1][0] - word["top"]) <= tolerance:
            lines[-1][1].append(word)
        else:
            lines.append([word["top"], [word]])
    return lines


def _ward_anchors(words):
    anchors = []
    for word in words:
        if word["text"] != "Ward" or not 160 <= word["x0"] <= 195:
            continue
        same_line = [
            other
            for other in words
            if abs(other["top"] - word["top"]) <= 3 and word["x0"] < other["x0"] < 250
        ]
        if any(
            other["text"].rstrip(".,").isdigit() or other["text"] in {"I", "l"}
            for other in same_line
        ):
            anchors.append(word["top"])
    return anchors


def _status_lines(words):
    lines = _word_lines([word for word in words if word["x0"] >= 375])
    return [
        (top, status) for top, line in lines if (status := _status_from_words(line))
    ]


def _village_text(words, low, high, ward_top):
    same_line = sorted(
        [word for word in words if abs(word["top"] - ward_top) <= 3],
        key=lambda item: item["x0"],
    )
    ward_numbers = [
        word
        for word in same_line
        if 190 <= word["x0"] < 260
        and (word["text"].rstrip(".,").isdigit() or word["text"] in {"I", "l"})
    ]
    label_right = max((word["x1"] for word in ward_numbers), default=230)
    village_words = []
    for word in words:
        if not (low <= word["top"] < high and 230 <= word["x0"] < 375):
            continue
        if abs(word["top"] - ward_top) <= 3 and word["x0"] <= label_right + 3:
            continue
        village_words.append(word)
    lines = _word_lines(village_words)
    return " ".join(
        " ".join(word["text"] for word in sorted(line, key=lambda item: item["x0"]))
        for _, line in lines
    ).strip()


def kamrup_metropolitan_ward_records():
    """Extract all 200 printed GP-ward rows from positioned PDF text.

    The GP name is column 2 of the source table. Its vertically merged cell
    spans all ten ward rows for that GP, so the name applies to every row in
    the span even though the text appears only once.
    """
    gps = kamrup_metropolitan_gp_records()
    records = []
    with pdfplumber.open(KAMRUP_METROPOLITAN_SOURCE) as document:
        for page, (first, last) in KAMRUP_METROPOLITAN_PAGE_SERIALS.items():
            words = document.pages[page - 1].extract_words(
                x_tolerance=1,
                y_tolerance=3,
            )
            anchors = _ward_anchors(words)
            statuses = _status_lines(words)
            expected = last - first + 1
            if page == 9:
                statuses.append((anchors[-1], "Unreserved"))
                statuses.sort()
            if len(anchors) != expected or len(statuses) != expected:
                raise RuntimeError(
                    f"Kamrup Metropolitan page {page}: {len(anchors)} ward anchors, "
                    f"{len(statuses)} statuses; expected {expected}"
                )
            centers = [
                (ward_top + status_top) / 2
                for ward_top, (status_top, _) in zip(anchors, statuses, strict=True)
            ]
            for offset, (ward_top, (status_top, raw)) in enumerate(
                zip(anchors, statuses, strict=True)
            ):
                serial = first + offset
                # Column 2 is a merged GP cell spanning wards 1--10.
                gp = gps[(serial - 1) // 10]
                low = (
                    (centers[offset - 1] + centers[offset]) / 2
                    if offset
                    else centers[offset] - 25
                )
                high = (
                    (centers[offset] + centers[offset + 1]) / 2
                    if offset + 1 < len(centers)
                    else centers[offset] + 10
                )
                caste, woman = _reservation_parts(raw)
                records.append(
                    {
                        "serial": serial,
                        "district": "Kamrup Metropolitan",
                        "anchalik_panchayat": gp["anchalik_panchayat"],
                        "gram_panchayat": gp["gram_panchayat"],
                        "ward_no": (serial - 1) % 10 + 1,
                        "village_name_raw": _village_text(
                            words,
                            low,
                            high,
                            ward_top,
                        ),
                        "caste_reservation_raw": caste,
                        "woman_reserved_raw": woman,
                        "reservation_raw": raw,
                        "source_page": page,
                        "extraction_method": (
                            "human_checked_from_rendered_page"
                            if serial == 139
                            else "positioned_embedded_text"
                        ),
                        "status_top": status_top,
                    }
                )
    return records


def page_records(source=SOURCE, source_sha256=SOURCE_SHA256, page_count=10):
    """Extract a PDF's embedded layout text without interpreting it."""
    records = []
    for page in range(1, page_count + 1):
        result = subprocess.run(
            [
                "pdftotext",
                "-f",
                str(page),
                "-l",
                str(page),
                "-layout",
                str(source),
                "-",
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        records.append(
            {
                "source_path": str(source.relative_to(ROOT)),
                "source_pdf": source.name,
                "source_sha256": source_sha256,
                "source_page": page,
                "extraction_method": "pdftotext-layout",
                "text": result.stdout.rstrip("\f\n"),
            }
        )
    return records


def _write_jsonl(path, records):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")


@command("extract", state="Assam", source_id="assam_sec_pri_reservation_2025")
def main():
    verify_source()
    pages = page_records()
    gps = gp_records()
    offices = office_records()
    kamrup_pages = page_records(
        KAMRUP_METROPOLITAN_SOURCE,
        KAMRUP_METROPOLITAN_SHA256,
        14,
    )
    kamrup_gps = kamrup_metropolitan_gp_records()
    kamrup_offices = kamrup_metropolitan_office_records()
    kamrup_wards = kamrup_metropolitan_ward_records()
    _write_jsonl(PAGES, pages)
    _write_jsonl(GP_ROSTER, gps)
    _write_jsonl(OFFICE_ASSIGNMENTS, offices)
    _write_jsonl(KAMRUP_METROPOLITAN_PAGES, kamrup_pages)
    _write_jsonl(KAMRUP_METROPOLITAN_GP_ROSTER, kamrup_gps)
    _write_jsonl(KAMRUP_METROPOLITAN_OFFICES, kamrup_offices)
    _write_jsonl(KAMRUP_METROPOLITAN_WARDS, kamrup_wards)
    LOGGER.info(
        "Charaideo extraction written",
        extra={
            "event": "source_extraction_written",
            "district": "Charaideo",
            "pages": len(pages),
            "gp_records": len(gps),
            "office_assignments": len(offices),
        },
    )
    LOGGER.info(
        "Kamrup Metropolitan extraction written",
        extra={
            "event": "source_extraction_written",
            "district": "Kamrup Metropolitan",
            "pages": len(kamrup_pages),
            "gp_records": len(kamrup_gps),
            "office_assignments": len(kamrup_offices),
            "ward_assignments": len(kamrup_wards),
        },
    )
    print(
        f"Assam 2025 Charaideo: {len(pages)} pages, {len(gps)} GPs, "
        f"{len(offices)} explicit office assignments"
    )
    print(
        f"Assam 2025 Kamrup Metropolitan: {len(kamrup_pages)} pages, "
        f"{len(kamrup_gps)} GPs, {len(kamrup_offices)} office assignments, "
        f"{len(kamrup_wards)} ward assignments"
    )


if __name__ == "__main__":
    main()
