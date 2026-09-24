"""Parse Kadapa's positioned 2020 gram-panchayat reservation table."""

import collections
import itertools
import json
import re
import statistics

from local_elections.paths import ROOT

TEXT = ROOT / "data" / "ap" / "extracted" / "kdp_res_gp.txt"
WORDS = ROOT / "data" / "ap" / "extracted" / "kdp_res_gp.words.jsonl"

MAX_WARDS = 20
ROW_TOLERANCE = 5.5
WORD_TOLERANCE = 9.0
POSITION_TOLERANCE = 3.0
CELL_REPAIRS = {"IK": "BC", "U~": "UR"}


def _distance(a, b):
    previous = list(range(len(b) + 1))
    for i, left in enumerate(a, 1):
        current = [i]
        for j, right in enumerate(b, 1):
            current.append(
                min(
                    previous[j] + 1,
                    current[j - 1] + 1,
                    previous[j - 1] + (left != right),
                )
            )
        previous = current
    return previous[-1]


def category(raw):
    """Return a canonical Kadapa category and whether its text was repaired."""
    if raw.strip().upper() in CELL_REPAIRS:
        return CELL_REPAIRS[raw.strip().upper()], 1
    letters = re.sub(r"[^A-Z]", "", raw.upper().translate(str.maketrans("58", "SB")))
    stem = letters.replace("W", "")
    if stem.startswith("UR"):
        base = "UR"
    elif stem.startswith(("SC", "SQ")) or (stem.startswith("SE") and "W" in letters):
        base = "SC"
    elif stem.startswith("ST"):
        base = "ST"
    elif stem.startswith(("BC", "BQ")):
        base = "BC"
    else:
        return None
    code = f"{base}(W)" if "W" in letters[2:] else base
    printed = re.sub(r"[.\-]", "", raw.upper())
    printed = re.sub(r"[^A-Z]", "", printed)
    repaired = printed != code.replace("(", "").replace(")", "")
    return code, int(repaired)


def abstract_controls(text=None):
    """Read the mandal GP counts printed in the three abstract pages."""
    if text is None:
        text = TEXT.read_text(encoding="utf-8")
    rows = []
    for page_no, page in enumerate(text.split("\f")[2:5], 3):
        for line in page.splitlines():
            match = re.match(r"^\s*\d+\s+(.+?)\s+(\d+)\s+", line)
            if match:
                rows.append(
                    {
                        "block": match.group(1).strip(),
                        "gp_count": int(match.group(2)),
                        "source_page": page_no,
                    }
                )
    if len(rows) != 50 or sum(row["gp_count"] for row in rows) != 807:
        raise ValueError("Kadapa abstract does not contain 50 mandals and 807 GPs")
    return rows


def load_pages(path=WORDS):
    """Load retained positioned words, one JSON object per source page."""
    with path.open(encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def _printed_number(text):
    cleaned = text.strip().lower().translate(str.maketrans("lio", "110"))
    match = re.match(r"^(\d+)(?:st|nd|rd|th|[\"'*.,-])?$", cleaned)
    return int(match.group(1)) if match else None


def _ward_centers(page):
    candidates = collections.defaultdict(list)
    for word in page["words"]:
        number = _printed_number(word["text"])
        if number and 1 <= number <= MAX_WARDS:
            candidates[number].append(word)
    if len(candidates) < MAX_WARDS - 1:
        return None
    header = {
        number: min(words, key=lambda word: word["top"])
        for number, words in candidates.items()
    }
    median_top = statistics.median(word["top"] for word in header.values())
    header = {
        number: word
        for number, word in header.items()
        if abs(word["top"] - median_top) <= 15
    }
    if len(header) < MAX_WARDS - 1:
        return None
    numbers = sorted(header)
    observed_centers = [
        header[number]["left"] + header[number]["width"] / 2 for number in numbers
    ]
    mean_number = sum(numbers) / len(numbers)
    mean_observed = sum(observed_centers) / len(observed_centers)
    spacing = sum(
        (number - mean_number) * (center - mean_observed)
        for number, center in zip(numbers, observed_centers, strict=True)
    ) / sum((number - mean_number) ** 2 for number in numbers)
    intercept = mean_observed - spacing * mean_number
    if (
        max(
            abs(center - (intercept + spacing * number))
            for number, center in zip(numbers, observed_centers, strict=True)
        )
        > 10
    ):
        return None
    centers = [
        (
            header[number]["left"] + header[number]["width"] / 2
            if number in header
            else intercept + spacing * number
        )
        for number in range(1, MAX_WARDS + 1)
    ]
    if centers != sorted(centers):
        return None
    gaps = [right - left for left, right in itertools.pairwise(centers)]
    mean_gap = sum(gaps) / len(gaps)
    if not 20 <= mean_gap <= 40 or max(abs(gap - mean_gap) for gap in gaps) > 6:
        return None
    header_words = list(header.values())
    header_centers = [word["left"] + word["width"] / 2 for word in header_words]
    mean_header_center = sum(header_centers) / len(header_centers)
    mean_top = sum(word["top"] for word in header_words) / len(header_words)
    slope = sum(
        (center - mean_header_center) * (word["top"] - mean_top)
        for center, word in zip(header_centers, header_words, strict=True)
    ) / sum((center - mean_header_center) ** 2 for center in header_centers)
    header_bottom = max(
        word["top"] + word["height"] - slope * center
        for center, word in zip(header_centers, header_words, strict=True)
    )
    return centers, header_bottom, mean_gap, slope


def _clusters(values, tolerance):
    clusters = []
    for value in sorted(values):
        if clusters and value - sum(clusters[-1]) / len(clusters[-1]) <= tolerance:
            clusters[-1].append(value)
        else:
            clusters.append([value])
    return clusters


def _adjusted_top(word, slope):
    return word["top"] - slope * (word["left"] + word["width"] / 2)


def _row_positions(page, category_start, category_end, header_bottom, slope):
    tops = []
    for word in page["words"]:
        center = word["left"] + word["width"] / 2
        if (
            _adjusted_top(word, slope) > header_bottom + 2
            and category_start <= center <= category_end
            and category(word["text"])
        ):
            tops.append(_adjusted_top(word, slope))
    return [
        sum(cluster) / len(cluster)
        for cluster in _clusters(tops, ROW_TOLERANCE)
        if len(cluster) >= 2
    ]


def _row_words(page, row_positions, slope):
    rows = [[] for _ in row_positions]
    for word in page["words"]:
        nearest = min(
            range(len(row_positions)),
            key=lambda index: abs(_adjusted_top(word, slope) - row_positions[index]),
        )
        if abs(_adjusted_top(word, slope) - row_positions[nearest]) <= WORD_TOLERANCE:
            rows[nearest].append(word)
    return rows


def _name_starts(rows, category_start):
    positioned = []
    for row_no, words in enumerate(rows):
        for word in words:
            if word["left"] + word["width"] / 2 < category_start:
                positioned.append((word["left"], row_no))
    clusters = []
    for left, row_no in sorted(positioned):
        if clusters and left - clusters[-1]["mean"] <= POSITION_TOLERANCE:
            cluster = clusters[-1]
            cluster["values"].append(left)
            cluster["rows"].add(row_no)
            cluster["mean"] = sum(cluster["values"]) / len(cluster["values"])
        else:
            clusters.append({"mean": left, "values": [left], "rows": {row_no}})
    threshold = max(2, round(len(rows) * 0.55))
    starts = [
        cluster["mean"] for cluster in clusters if len(cluster["rows"]) >= threshold
    ]
    if len(starts) < 3:
        raise ValueError("could not infer serial, mandal, and GP columns")
    return starts[:3]


def _join(words):
    return " ".join(
        word["text"] for word in sorted(words, key=lambda word: word["left"])
    )


def parse_main_page(page):
    """Read one main-table page using its own printed ward-column headers."""
    geometry = _ward_centers(page)
    if geometry is None:
        return []
    ward_centers, header_bottom, spacing, slope = geometry
    category_start = ward_centers[0] - 1.8 * spacing
    category_end = ward_centers[-1] + spacing / 2
    row_positions = _row_positions(
        page, category_start, category_end, header_bottom, slope
    )
    if not row_positions:
        return []
    rows = _row_words(page, row_positions, slope)
    serial_start, block_start, gp_start = _name_starts(rows, category_start)
    serial_boundary = (serial_start + block_start) / 2
    gp_boundary = (block_start + gp_start) / 2
    ward_boundary = ward_centers[0] - spacing / 2
    records = []
    for words in rows:
        serial_words = [word for word in words if word["left"] < serial_boundary]
        block_words = [
            word for word in words if serial_boundary <= word["left"] < gp_boundary
        ]
        gp_words = [
            word
            for word in words
            if word["left"] >= gp_boundary
            and word["left"] + word["width"] / 2 < category_start
        ]
        cells = collections.defaultdict(list)
        for word in words:
            center = word["left"] + word["width"] / 2
            if not category_start <= center <= category_end:
                continue
            if center < ward_boundary:
                cells[0].append(word)
                continue
            ward_no = min(
                range(1, MAX_WARDS + 1),
                key=lambda number: abs(center - ward_centers[number - 1]),
            )
            if abs(center - ward_centers[ward_no - 1]) <= spacing / 2:
                cells[ward_no].append(word)
        raw_cells = {number: _join(cell) for number, cell in cells.items()}
        sarpanch = category(raw_cells.get(0, ""))
        if not sarpanch or not block_words or not gp_words:
            raise ValueError(
                f"page {page['page']} has an incomplete row near "
                f"{row_positions[len(records)]:.1f}: block={_join(block_words)!r}, "
                f"gp={_join(gp_words)!r}, sarpanch={raw_cells.get(0, '')!r}"
            )
        ward_raws = []
        ended = False
        empty_run = 0
        for ward_no in range(1, MAX_WARDS + 1):
            raw = raw_cells.get(ward_no, "")
            parsed = category(raw)
            if parsed and not ended:
                ward_raws.append(raw)
                empty_run = 0
            elif parsed and ended:
                raise ValueError(
                    f"page {page['page']} {_join(gp_words)!r} has a ward after "
                    f"an empty cell at ward {ward_no}"
                )
            elif raw and raw.strip("-–— ") and empty_run < 2:
                raise ValueError(
                    f"page {page['page']} {_join(gp_words)!r} has an unreadable "
                    f"ward {ward_no}: {raw!r}"
                )
            else:
                ended = True
                empty_run += 1
        records.append(
            {
                "source_page": page["page"],
                "serial_raw": _join(serial_words),
                "block_raw": _join(block_words),
                "gram_panchayat": _join(gp_words),
                "sarpanch_raw": raw_cells[0],
                "ward_raws": ward_raws,
                "column_starts": [serial_start, block_start, gp_start],
            }
        )
    return records


def _key(value):
    return re.sub(r"[^a-z0-9]", "", value.lower())


def _is_subsequence(short, long):
    letters = iter(long)
    return all(any(letter == candidate for candidate in letters) for letter in short)


def match_block(raw, controls, gp_count=None):
    """Match a main-table mandal spelling to one unique abstract row."""
    if gp_count is not None:
        controls = [control for control in controls if control["gp_count"] == gp_count]
    target = _key(raw)
    abbreviations = [
        control
        for control in controls
        if len(target) >= 4 and _is_subsequence(target, _key(control["block"]))
    ]
    if len(abbreviations) == 1:
        return abbreviations[0]["block"]
    ranked = sorted(
        ((_distance(target, _key(control["block"])), control) for control in controls),
        key=lambda item: item[0],
    )
    if len(ranked) > 1 and ranked[0][0] == ranked[1][0]:
        raise ValueError(f"ambiguous Kadapa mandal spelling: {raw}")
    if ranked[0][0] > 3:
        raise ValueError(f"unmatched Kadapa mandal spelling: {raw}")
    return ranked[0][1]["block"]


def parse_main(pages=None, text=None):
    """Parse all pages carrying the 20-column main reservation table."""
    if pages is None:
        pages = load_pages()
    controls = abstract_controls(text)
    records = []
    for page in pages:
        page_records = parse_main_page(page)
        if not page_records:
            continue
        printed = collections.Counter(
            record["block_raw"] for record in page_records
        ).most_common(1)[0][0]
        block = match_block(printed, controls, len(page_records))
        for record in page_records:
            record["block"] = block
        records.extend(page_records)
    return records


def _correction_row_positions(page):
    tops = [
        word["top"]
        for word in page["words"]
        if word["left"] + word["width"] / 2 > page["width"] * 0.55
        and (category(word["text"]) or not word["text"].strip("-–— "))
    ]
    return [
        sum(cluster) / len(cluster)
        for cluster in _clusters(tops, 5)
        if len(cluster) >= 1
    ]


def _correction_category_centers(rows, page_width):
    centers = []
    for words in rows:
        for word in words:
            center = word["left"] + word["width"] / 2
            if center > page_width * 0.55 and (
                category(word["text"]) or not word["text"].strip("-–— ")
            ):
                centers.append(center)
    clusters = _clusters(centers, 12)
    if len(clusters) != 2:
        raise ValueError("could not infer the errata For and Read as columns")
    return [sum(cluster) / len(cluster) for cluster in clusters]


def _leading_number(text):
    cleaned = text.lower().translate(str.maketrans("lio", "110"))
    digits = "".join(re.findall(r"\d", cleaned))
    return int(digits) if digits else None


def _parse_errata_table(page, row_positions):
    rows = _row_words(page, row_positions, 0)
    for_center, read_center = _correction_category_centers(rows, page["width"])
    category_boundary = (for_center + read_center) / 2
    ward_boundary = for_center - 1.5 * (read_center - for_center)
    ward_end = for_center - (read_center - for_center) / 2

    def has_ward_number(words):
        region = (
            word
            for word in words
            if ward_boundary <= word["left"] + word["width"] / 2 < ward_end
        )
        return any("ard" in word["text"].lower() for word in region)

    name_region = []
    for words in rows:
        has_ward = has_ward_number(words)
        cutoff = ward_boundary if has_ward else ward_end
        name_region.append(
            [word for word in words if word["left"] + word["width"] / 2 < cutoff]
        )
    _, block_start, gp_start = _name_starts(name_region, ward_end)
    block_boundary = (block_start + gp_start) / 2
    records = []
    previous_block = ""
    for words in rows:
        has_ward = has_ward_number(words)
        gp_end = ward_boundary if has_ward else ward_end
        block = _join(
            [
                word
                for word in words
                if block_start - POSITION_TOLERANCE <= word["left"] < block_boundary
            ]
        )
        if block:
            previous_block = block
        block = previous_block
        gp = _join(
            [
                word
                for word in words
                if word["left"] >= block_boundary
                and word["left"] + word["width"] / 2 < gp_end
            ]
        )
        for_raw = _join(
            [
                word
                for word in words
                if ward_boundary <= word["left"] + word["width"] / 2 < category_boundary
                and (category(word["text"]) or not word["text"].strip("-–— "))
            ]
        )
        read_raw = _join(
            [
                word
                for word in words
                if word["left"] + word["width"] / 2 >= category_boundary
                and category(word["text"])
            ]
        )
        ward_no = None
        if has_ward:
            ward_no = _leading_number(
                _join(
                    [
                        word
                        for word in words
                        if ward_boundary <= word["left"] + word["width"] / 2 < ward_end
                    ]
                )
            )
        if not block or not gp or not read_raw or (has_ward and not ward_no):
            raise ValueError(
                f"page {page['page']} has an incomplete errata row near "
                f"{row_positions[len(records)]:.1f}: block={block!r}, gp={gp!r}, "
                f"ward={ward_no!r}, for={for_raw!r}, read={read_raw!r}"
            )
        if not for_raw:
            for_raw = "-"
        records.append(
            {
                "source_page": page["page"],
                "tier": "gp_ward" if has_ward else "gp_head",
                "block_raw": block,
                "gram_panchayat_raw": gp,
                "ward_no": ward_no,
                "for_raw": for_raw,
                "read_as_raw": read_raw,
            }
        )
    return records


def parse_errata_page(page):
    """Read correction rows from one errata page by its printed columns."""
    row_positions = _correction_row_positions(page)
    if not row_positions:
        return []
    groups = [[row_positions[0]]]
    for position in row_positions[1:]:
        if position - groups[-1][-1] > 30:
            groups.append([position])
        else:
            groups[-1].append(position)
    return [
        record
        for positions in groups
        for record in _parse_errata_table(page, positions)
    ]


def parse_errata(pages=None):
    """Read all positioned pages that announce correction tables."""
    if pages is None:
        pages = load_pages()
    records = []
    for page in pages:
        text = " ".join(word["text"] for word in page["words"]).lower()
        if "erratta" in text or "ers'ata" in text or records:
            records.extend(parse_errata_page(page))
    return records


def _match_correction(correction, records):
    target_block = _key(correction["block_raw"])
    target_gp = _key(correction["gram_panchayat_raw"])
    ranked = sorted(
        (
            (
                _distance(target_block, _key(record["block"]))
                + _distance(target_gp, _key(record["gram_panchayat"])),
                record,
            )
            for record in records
        ),
        key=lambda item: item[0],
    )
    if len(ranked) > 1 and ranked[0][0] == ranked[1][0]:
        raise ValueError(
            "ambiguous Kadapa errata target: "
            f"{correction['block_raw']} / {correction['gram_panchayat_raw']}"
        )
    if ranked[0][0] > 6:
        raise ValueError(
            "unmatched Kadapa errata target: "
            f"{correction['block_raw']} / {correction['gram_panchayat_raw']}"
        )
    return ranked[0][1]


def apply_errata(records=None, corrections=None):
    """Apply the later gazette as an auditable correction layer."""
    if records is None:
        records = parse_main()
    if corrections is None:
        corrections = parse_errata()
    applied = 0
    for correction in corrections:
        record = _match_correction(correction, records)
        ward_no = correction["ward_no"]
        if correction["tier"] == "gp_head":
            current = record["sarpanch_raw"]
        elif ward_no <= len(record["ward_raws"]):
            current = record["ward_raws"][ward_no - 1]
        elif ward_no == len(record["ward_raws"]) + 1:
            current = ""
        else:
            raise ValueError(
                f"errata skips wards for {record['block']} / "
                f"{record['gram_panchayat']}: {ward_no}"
            )
        expected = category(correction["for_raw"])
        observed = category(current)
        if (expected[0] if expected else None) != (observed[0] if observed else None):
            raise ValueError(
                f"errata For value does not match {record['block']} / "
                f"{record['gram_panchayat']} ward {ward_no}: "
                f"{correction['for_raw']!r} != {current!r}"
            )
        provenance = {
            "reservation_raw_original": current,
            "correction_for_raw": correction["for_raw"],
            "correction_read_as_raw": correction["read_as_raw"],
            "correction_source_page": correction["source_page"],
            "corrected": 1,
        }
        if correction["tier"] == "gp_head":
            record["sarpanch_raw"] = correction["read_as_raw"]
            record["head_correction"] = provenance
        else:
            if ward_no > len(record["ward_raws"]):
                record["ward_raws"].append(correction["read_as_raw"])
            else:
                record["ward_raws"][ward_no - 1] = correction["read_as_raw"]
            record.setdefault("ward_corrections", {})[ward_no] = provenance
        applied += 1
    if applied != 41:
        raise ValueError(f"expected 41 Kadapa corrections, applied {applied}")
    return records
