"""Parse Assam's 2020 municipal-board reservation notifications.

The committed PDF is a scan with an inaccurate hidden OCR layer. Its ward
table states one row per municipal board: the total number of wards and the
ward identifiers reserved in five mutually exclusive categories. It does not
identify the unreserved wards, so this parser emits only the seats the source
identifies and marks the slice ``reserved_only``. The printed total remains on
every emitted row and is checked independently by ``validate.py``.

The two short tables are transcribed below rather than inferred from the noisy
OCR. The PDF hash guards that transcription against being applied to different
bytes, and every output row points back to the page on which it appears.
"""

import hashlib

from local_elections.common import emit
from local_elections.common.normalize import label
from local_elections.common.runlog import command
from local_elections.paths import ROOT

DATA = ROOT / "data" / "assam"
SOURCE = (
    DATA
    / "pdfs"
    / ("Reservation of Wards and post of Chairperson of Municipal Boards_2020.pdf")
)
SOURCE_SHA256 = "654319203cc97275f9107046191284c1082c88c043f10fcdb10fbbaa4904d328"
SOURCE_PATH = SOURCE.relative_to(ROOT)

WARD_COLUMNS = [
    "state",
    "year",
    "district",
    "block",
    "body",
    "ward_no",
    "ward_count",
    "serial",
    "tier",
    "tier_local",
    "reservation",
    "caste_reservation",
    "woman_reserved",
    "reservation_raw",
    "listing_scope",
    "script",
]
HEAD_COLUMNS = [
    "state",
    "year",
    "district",
    "block",
    "body",
    "serial",
    "tier",
    "tier_local",
    "reservation",
    "caste_reservation",
    "woman_reserved",
    "reservation_raw",
    "listing_scope",
    "script",
]

# serial|page|district|subdivision|board|total|SC|SC women|ST|ST women|women
WARD_TABLE = """
1|2|Jorhat|Jorhat|Jorhat|19|3|-|-|-|1,6,8,9,10,11,15,17
2|2|Jorhat|Jorhat|Teok|10|9|2|-|-|1,3,4,8
3|2|Jorhat|Titabor|Titabor|10|-|5|2|-|1,4,6,8
4|2|Jorhat|Titabor|Mariani|10|-|-|-|-|5,6,7,8,9
5|2|Golaghat|Golaghat|Golaghat|13|-|-|-|-|1,2,3,5,12,13
6|2|Golaghat|Golaghat|Dergaon|10|8|-|-|-|3,5,6,7,9
7|2|Golaghat|Dhansiri|Barpathar|10|-|-|-|-|1,5,6,7,8
8|2|Golaghat|Dhansiri|Sarupathar|10|-|-|-|-|1,3,5,7,8
9|2|Golaghat|Bokakhat|Bokakhat|10|3|-|-|-|2,4,5,6,8
10|2|Dibrugarh|Dibrugarh|Dibrugarh|22|5|22|2|-|3,6,7,12,13,15,16,17,19,20
11|2|Dibrugarh|Dibrugarh|Chabua|10|7|-|-|-|1,3,4,6,8
12|2|Dibrugarh|Dibrugarh|Naharkatia|10|-|-|9|-|2,3,4,8,10
13|2|Dibrugarh|Dibrugarh|Namrup|10|-|-|-|-|1,3,5,6,9
14|3|Tinsukia|Tinsukia|Tinsukia|15|-|14|-|-|1,4,5,6,7,12
15|3|Tinsukia|Tinsukia|Makum|10|-|-|-|-|3,6,7,9,10
16|3|Tinsukia|Tinsukia|Doom Dooma|10|-|9|-|-|1,2,3,10
17|3|Tinsukia|Sadiya|Chapakhowa|10|-|-|-|7|2,4,8,9
18|3|Tinsukia|Margherita|Margherita|10|-|-|-|-|2,4,7,8,10
19|3|Tinsukia|Margherita|Digboi|10|-|-|-|-|3,5,7,9,10
20|3|Dhemaji|Dhemaji|Dhemaji|10|-|-|9|2|1,3,4,5
21|3|Dhemaji|Dhemaji|Silapathar|12|10|-|8|6|2,4,5,7,11
22|3|Sonitpur|Sonitpur|Tezpur|19|5|6|-|-|8,9,11,12,13,16,17,18
23|3|Sonitpur|Sonitpur|Jamugurihat|10|2|6|-|-|5,7,8,10
24|3|Sonitpur|Sonitpur|Rangapara|10|-|5|-|-|2,3,4,7
25|3|Sonitpur|Sonitpur|Dhekiajuli|10|-|6|-|-|4,5,7,10
26|3|Biswanath|Biswanath Chariali|Biswanath Chariali|12|-|-|-|-|1,3,7,8,9,11
27|3|Biswanath|Biswanath Chariali|Sootea|10|-|-|-|-|2,3,5,6,8
28|3|Biswanath|Gohpur|Gohpur|10|10|-|8|-|1,3,6,7,9
29|3|Darrang|Mangaldoi|Mangaldoi|10|4|7|-|-|1,8,9,10
30|3|Darrang|Mangaldoi|Kharupetia|10|10|-|-|-|1,3,4,8,9
31|3|Darrang|Mangaldoi|Sipajhar|10|-|3|-|-|4,5,8,10
32|3|Lakhimpur|Lakhimpur|North Lakhimpur|21|-|-|3B|5B|2A,2B,3A,4,9,10,12A,14A,14C,14D
33|3|Lakhimpur|Lakhimpur|Narayanpur|10|5A|-|-|6B|1B,3B,4,6A
34|3|Lakhimpur|Lakhimpur|Bihpuria|10|7|-|-|-|1,4,6,8,9
35|4|Lakhimpur|Dhakuakhana|Dhakuakhana|10|10|8|-|2|3,7,9
36|4|Charaideo|Charaideo|Sonari|16|-|9|-|-|5,7,8,10,13,15,16
37|4|Charaideo|Charaideo|Moranhat|11|-|-|-|-|1,3,5,6,7,8
38|4|Sivasagar|Sivasagar|Sivasagar|14|-|7|-|-|1,4,8,10,13,14
39|4|Sivasagar|Sivasagar|Amguri|10|-|2|-|-|1,5,6,9
40|4|Sivasagar|Sivasagar|Demow|10|-|-|-|-|2,5,7,8,10
41|4|Sivasagar|Sivasagar|Simaluguri|10|-|-|-|-|2,3,5,7,9
42|4|Sivasagar|Nazira|Nazira|10|6|1|-|-|3,7,8,9
43|4|Nagaon|Nagaon|Nagaon|26|21|1|-|-|2,3,4,6,10,13,15,17,19,24,25,26
44|4|Nagaon|Nagaon|Dhing|10|10|-|-|-|2,3,5,7,8
45|4|Nagaon|Nagaon|Kampur|10|8|-|-|-|1,2,3,4,7
46|4|Nagaon|Nagaon|Raha|10|6,10|7|4,5|1|2,3,8
47|4|Morigaon|Morigaon|Morigaon|11|5|6|10|-|3,4,7,9
48|4|Hojai|Hojai|Hojai|19|13|6|-|-|2,4,10,11,14,15,16,17
49|4|Hojai|Hojai|Lanka|11|4|1|-|-|5,6,9,10
50|4|Hojai|Hojai|Lumding|13|11|-|-|-|1,3,5,9,10,13
51|4|Hojai|Hojai|Doboka|10|-|-|-|-|2,4,6,9,10
52|4|Cachar|Silchar|Silchar|28|17,25|14,20|-|-|2,3,4,8,9,11,16,18,22,23,26,28
53|4|Cachar|Silchar|Sonai|11|3|4|-|-|5,6,9,11
54|4|Cachar|Lakhipur|Lakhipur|10|-|-|-|-|1,3,4,7,10
55|4|Hailakandi|Hailakandi|Hailakandi|16|2|-|-|-|3,6,7,8,10,12,13,16
56|4|Hailakandi|Hailakandi|Lala|10|9|2|-|-|1,4,7,8
57|5|Goalpara|Goalpara|Goalpara|19|15|9|17|-|1,3,4,6,7,8,10,19
58|5|Goalpara|Lakhipur|Lakhipur|10|10|-|8|-|1,3,5,6,7
59|5|Dhubri|Dhubri|Dhubri|16|10,14|13|-|-|4,6,7,8,9,15,16
60|5|Dhubri|Dhubri|Gauripur|13|5|-|-|-|1,2,4,7,9,11,13
61|5|Dhubri|Dhubri|Golakganj|10|9|1|-|-|4,5,6,10
62|5|Dhubri|Bilasipara|Bilasipara|14|8,12|7|-|-|1,3,5,11,13,14
63|5|Dhubri|Bilasipara|Chapar|10|-|4|-|-|2,3,8,9
64|5|Dhubri|Bilasipara|Sapatgram|10|3,8|2|-|-|6,7,9,10
65|5|Bongaigaon|Bongaigaon|Bongaigaon|25|15,19|2|13|-|4,6,7,8,11,12,14,17,18,20,25
66|5|Bongaigaon|North Salmara|Abhayapuri|11|7|9|-|-|1,3,5,11
67|5|Karimganj|Karimganj|Karimganj|27|15,16|11,24|-|-|1,2,3,4,5,6,7,8,10,18,26,27
68|5|Karimganj|Karimganj|Badarpur|11|9|8|-|-|2,4,6,10,11
69|5|Karimganj|Karimganj|Ramkrishna Nagar|10|9|2|-|-|4,6,8,10
70|5|Kamrup (Rural)|Rangia|Rangia|10|-|7|-|3|4,9,10
71|5|Kamrup (Rural)|Rangia|Palashbari|10|-|2|-|-|1,3,6,8
72|5|Kamrup (Rural)|Rangia|North Guwahati|10|2,10|7|5|-|1,3,8,9
73|5|Nalbari|Nalbari|Nalbari|17|10|-|-|-|1,3,5,6,7,12,14,16
74|5|Nalbari|Nalbari|Tihu|10|8,10|3,7|-|-|2,6,9
75|6|Barpeta|Barpeta|Barpeta|22|-|4,21|-|-|6,9,10,11,13,17,19,20,22
76|6|Barpeta|Barpeta|Howly|10|-|-|-|-|2,3,4,7,8
77|6|Barpeta|Barpeta|Sarthebari|10|-|-|-|-|5,6,7,8,9
78|6|Barpeta|Barpeta|Barpeta Road|10|-|2|-|-|1,5,6,10
79|6|Barpeta|Barpeta|Sorbhog|10|-|-|-|-|1,2,5,8,10
80|6|Barpeta|Bajali|Pathsala|10|8|-|-|-|2,3,4,9,10
81|6|Barpeta|Bajali|Patacharkuchi|10|-|-|-|-|4,6,8,9,10
"""

# serial|page|district|subdivision|board|reservation
HEAD_TABLE = """
1|7|Dhemaji|-|Silapathar|Scheduled Tribe
2|7|Lakhimpur|-|North Lakhimpur|Scheduled Tribe (Woman)
3|7|Lakhimpur|Dhakuakhana|Dhakuakhana|Scheduled Caste
4|7|Bongaigaon|-|Bongaigaon|Scheduled Caste
5|7|Kamrup (Rural)|-|North Guwahati|Scheduled Caste
6|7|Barpeta|-|Barpeta|Scheduled Caste
7|7|Nagaon|-|Raha|Scheduled Caste (Woman)
8|7|Dhubri|Bilasipara|Bilasipara|Scheduled Caste (Woman)
9|7|Dhubri|Bilasipara|Sapatgram|Scheduled Caste (Woman)
10|7|Nalbari|-|Tihu|Scheduled Caste (Woman)
11|7|Jorhat|-|Jorhat|Woman
12|7|Jorhat|-|Teok|Woman
13|7|Jorhat|Titabor|Titabor|Woman
14|7|Jorhat|Titabor|Mariani|Woman
15|7|Golaghat|-|Golaghat|Woman
16|7|Golaghat|-|Dergaon|Woman
17|7|Golaghat|Dhansiri|Sarupathar|Woman
18|7|Dibrugarh|-|Naharkatia|Woman
19|7|Tinsukia|-|Makum|Woman
20|7|Tinsukia|Sadiya|Chapakhowa|Woman
21|7|Dhemaji|-|Dhemaji|Woman
22|7|Sonitpur|-|Jamugurihat|Woman
23|7|Sonitpur|-|Dhekiajuli|Woman
24|7|Biswanath|-|Sootea|Woman
25|7|Darrang|-|Mangaldoi|Woman
26|7|Darrang|-|Sipajhar|Woman
27|7|Lakhimpur|-|Bihpuria|Woman
28|7|Sivasagar|-|Amguri|Woman
29|7|Sivasagar|Nazira|Nazira|Woman
30|7|Nagaon|-|Nagaon|Woman
31|7|Nagaon|-|Kampur|Woman
32|7|Hojai|-|Lanka|Woman
33|8|Hojai|-|Doboka|Woman
34|8|Cachar|-|Silchar|Woman
35|8|Cachar|-|Sonai|Woman
36|8|Hailakandi|-|Lala|Woman
37|8|Dhubri|-|Gauripur|Woman
38|8|Dhubri|-|Golakganj|Woman
39|8|Dhubri|Bilasipara|Chapar|Woman
40|8|Karimganj|-|Badarpur|Woman
41|8|Karimganj|-|Ramkrishna Nagar|Woman
42|8|Kamrup (Rural)|-|Palashbari|Woman
43|8|Nalbari|-|Nalbari|Woman
44|8|Barpeta|-|Sarthebari|Woman
45|8|Barpeta|-|Sorbhog|Woman
46|8|Barpeta|Bajali|Pathsala|Woman
"""

CATEGORY_COLUMNS = (
    ("SC", "SC", 0),
    ("SC (Women)", "SC", 1),
    ("ST", "ST", 0),
    ("ST (Women)", "ST", 1),
    ("Women", "NONE", 1),
)


def _cells(text):
    return [line.split("|") for line in text.strip().splitlines()]


def _wards(text):
    return () if text == "-" else tuple(text.split(","))


def ward_records():
    """The 81 board-level records transcribed from pages 2--6."""
    out = []
    for cells in _cells(WARD_TABLE):
        serial, page, district, block, body, total, *categories = cells
        out.append(
            {
                "serial": int(serial),
                "source_page": int(page),
                "district": district,
                "block": "" if block == "-" else block,
                "body": body,
                "ward_count": int(total),
                "categories": tuple(_wards(value) for value in categories),
            }
        )
    return out


def ward_rows():
    """One row per explicitly identified reserved municipal ward."""
    rows = []
    for record in ward_records():
        for (raw, caste, woman), wards in zip(
            CATEGORY_COLUMNS, record["categories"], strict=True
        ):
            for ward in wards:
                row = {
                    "state": "Assam",
                    "year": 2020,
                    "district": record["district"],
                    "block": record["block"],
                    "body": record["body"],
                    "ward_no": ward,
                    "ward_count": record["ward_count"],
                    "serial": record["serial"],
                    "tier": "ulb_ward",
                    "tier_local": "Municipal Board ward",
                    "reservation": label(caste, woman),
                    "caste_reservation": caste,
                    "woman_reserved": woman,
                    "reservation_raw": raw,
                    "listing_scope": "reserved_only",
                    "script": "latin",
                }
                rows.append(emit.stamp(row, SOURCE, record["source_page"], root=ROOT))
    return rows


def head_rows():
    """The 46 explicitly reserved municipal-board chairperson posts."""
    rows = []
    for serial, page, district, block, body, raw in _cells(HEAD_TABLE):
        caste = "ST" if "Tribe" in raw else "SC" if "Caste" in raw else "NONE"
        woman = int("Woman" in raw)
        row = {
            "state": "Assam",
            "year": 2020,
            "district": district,
            "block": "" if block == "-" else block,
            "body": body,
            "serial": int(serial),
            "tier": "ulb_head",
            "tier_local": "Municipal Board chairperson",
            "reservation": label(caste, woman),
            "caste_reservation": caste,
            "woman_reserved": woman,
            "reservation_raw": raw,
            "listing_scope": "reserved_only",
            "script": "latin",
        }
        rows.append(emit.stamp(row, SOURCE, int(page), root=ROOT))
    return rows


def verify_source():
    """Refuse to apply the transcription to a changed source document."""
    digest = hashlib.sha256(SOURCE.read_bytes()).hexdigest()
    if digest != SOURCE_SHA256:
        raise RuntimeError(
            f"Assam source changed: expected {SOURCE_SHA256}, found {digest}"
        )


@command("parse", state="Assam", source_id="assam_ulb_reservation_2020")
def main():
    verify_source()
    wards = ward_rows()
    heads = head_rows()
    emit.write(wards, DATA / "ward_reservation_2020", WARD_COLUMNS)
    emit.write(heads, DATA / "chairperson_reservation_2020", HEAD_COLUMNS)
    print(f"Assam 2020: {len(wards):,} identified reserved wards")
    print(f"Assam 2020: {len(heads):,} identified reserved chairperson posts")


if __name__ == "__main__":
    main()
