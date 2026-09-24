"""Extract raw roster cells from Gujarat's 2020 rotation orders.

The PDFs display Gujarati correctly but expose a misencoded hidden text layer.
This stage therefore renders pages, finds the one roster page from its table
geometry, and writes source-faithful OCR cells to JSONL. It does not interpret
reservation categories; parse.py owns that separate transformation.
"""

import argparse
import csv
import json
import pathlib
import statistics
import subprocess
import tempfile
from itertools import pairwise

from PIL import Image, ImageOps

from local_elections.common.runlog import command, get_logger
from local_elections.paths import ROOT
from local_elections.states.gujarat import controls, geography, harvest

LOGGER = get_logger(__name__)
OCR = ROOT / "data" / "gujarat" / "ocr"
DISCOVERY_DPI = 150
OCR_DPI = 300
ROSTER_PAGE_OVERRIDES = {
    "zp_member_dahod_dp_2020.pdf": {11: None, 12: 0},
    "zp_member_kutchh_dp_2020.pdf": {11: None, 12: 0},
    "zp_member_vadodara_dp_2020.pdf": {11: None, 12: 0},
}
ROSTER_PAGE_LINES = {
    ("zp_member_kutchh_dp_2020.pdf", 12): (
        0.224,
        0.289,
        0.439,
        0.523,
        0.601,
        0.686,
        0.895,
    ),
}
MORBI_ASSIGNMENT_ROWS = (
    (5, 15, 0.8112, 0.8300, (0.14, 0.25, 0.41, 0.69, 0.93)),
    (5, 7, 0.8300, 0.8483, (0.14, 0.25, 0.41, 0.69, 0.93)),
    (5, 24, 0.8665, 0.8848, (0.14, 0.25, 0.41, 0.69, 0.93)),
    (6, 3, 0.1817, 0.2002, (0.15, 0.29, 0.49, 0.49, 0.91)),
    (6, 4, 0.2002, 0.2191, (0.15, 0.29, 0.49, 0.49, 0.91)),
    *(
        (6, seat, top, bottom, (0.14, 0.29, 0.55, 0.55, 0.91))
        for seat, (top, bottom) in zip(
            (1, 2, 5, 6, 10, 11, 14, 16, 22, 23, 8, 9, 12, 13, 17, 18, 19, 20, 21),
            pairwise(
                (
                    0.3813,
                    0.4022,
                    0.4230,
                    0.4438,
                    0.4643,
                    0.4852,
                    0.5057,
                    0.5265,
                    0.5473,
                    0.5682,
                    0.5884,
                    0.6095,
                    0.6301,
                    0.6509,
                    0.6717,
                    0.6922,
                    0.7131,
                    0.7339,
                    0.7544,
                    0.7750,
                )
            ),
            strict=True,
        )
    ),
)
PATAN_PAGE_8_LINES = (
    0.0936,
    0.1147,
    0.1358,
    0.1569,
    0.1786,
    0.2002,
    0.2219,
    0.2430,
    0.2647,
    0.2864,
    0.3078,
    0.3294,
    0.3511,
    0.3722,
    0.3939,
    0.4150,
    0.4364,
    0.4578,
    0.4795,
    0.5006,
    0.5222,
    0.5436,
    0.5650,
    0.5861,
    0.6078,
    0.6295,
)
PATAN_ASSIGNMENT_ROWS = (
    (7, 13, 0.4837, 0.5051, (0.14, 0.27, 0.43, 0.58, 0.92)),
    (7, 2, 0.5051, 0.5265, (0.14, 0.27, 0.43, 0.58, 0.92)),
    (7, 23, 0.5265, 0.5482, (0.14, 0.27, 0.43, 0.58, 0.92)),
    (7, 7, 0.5702, 0.5887, (0.14, 0.27, 0.43, 0.58, 0.92)),
    (7, 4, 0.7151, 0.7367, (0.14, 0.29, 0.49, 0.49, 0.91)),
    (7, 5, 0.7367, 0.7578, (0.14, 0.29, 0.49, 0.49, 0.91)),
    (7, 6, 0.7578, 0.7792, (0.14, 0.29, 0.49, 0.49, 0.91)),
    *(
        (8, seat, top, bottom, (0.14, 0.29, 0.51, 0.51, 0.91))
        for seat, (top, bottom) in zip(
            (
                1,
                3,
                8,
                10,
                12,
                16,
                18,
                19,
                21,
                25,
                31,
                32,
                9,
                11,
                14,
                15,
                17,
                20,
                22,
                24,
                26,
                27,
                28,
                29,
                30,
            ),
            pairwise(PATAN_PAGE_8_LINES),
            strict=True,
        )
    ),
)
RAJKOT_PAGE_9_LINES = (
    0.2325,
    0.2533,
    0.2741,
    0.2949,
    0.3155,
    0.3360,
    0.3571,
    0.3779,
    0.3985,
    0.4196,
    0.4401,
    0.4604,
    0.4815,
    0.5023,
    0.5228,
    0.5436,
    0.5642,
    0.5850,
    0.6058,
    0.6264,
    0.6469,
    0.6677,
    0.6885,
    0.7094,
    0.7302,
    0.7507,
    0.7712,
    0.7921,
)
RAJKOT_ASSIGNMENT_ROWS = (
    (8, 32, 0.6010, 0.6192, (0.15, 0.28, 0.43, 0.56, 0.92)),
    (8, 9, 0.6192, 0.6378, (0.15, 0.28, 0.43, 0.56, 0.92)),
    (8, 8, 0.6378, 0.6563, (0.15, 0.28, 0.43, 0.56, 0.92)),
    (8, 19, 0.6563, 0.6748, (0.15, 0.28, 0.43, 0.56, 0.92)),
    (8, 29, 0.6931, 0.7114, (0.15, 0.28, 0.43, 0.56, 0.92)),
    (8, 4, 0.8369, 0.8554, (0.14, 0.30, 0.50, 0.50, 0.91)),
    (8, 6, 0.8554, 0.8736, (0.14, 0.30, 0.50, 0.50, 0.91)),
    (8, 7, 0.8736, 0.8919, (0.14, 0.30, 0.50, 0.50, 0.91)),
    (8, 10, 0.8919, 0.9102, (0.14, 0.30, 0.50, 0.50, 0.91)),
    *(
        (9, seat, top, bottom, (0.14, 0.29, 0.55, 0.55, 0.91))
        for seat, (top, bottom) in zip(
            (
                1,
                2,
                3,
                11,
                12,
                18,
                21,
                23,
                24,
                25,
                26,
                27,
                34,
                36,
                5,
                13,
                14,
                15,
                16,
                17,
                20,
                22,
                28,
                30,
                31,
                33,
                35,
            ),
            pairwise(RAJKOT_PAGE_9_LINES),
            strict=True,
        )
    ),
)
SURAT_ST_LINES = (
    0.4375,
    0.4598,
    0.4826,
    0.5048,
    0.5274,
    0.5499,
    0.5722,
    0.5947,
    0.6175,
    0.6400,
    0.6626,
    0.6854,
    0.7079,
    0.7305,
    0.7527,
    0.7752,
    0.7975,
    0.8200,
    0.8423,
    0.8645,
)
SURAT_GENERAL_LINES = (
    0.3831,
    0.4059,
    0.4284,
    0.4509,
    0.4735,
    0.4960,
    0.5185,
    0.5411,
    0.5636,
    0.5861,
    0.6087,
    0.6312,
    0.6537,
)
SURAT_ASSIGNMENT_ROWS = (
    (8, 17, 0.3811, 0.4039, (0.14, 0.27, 0.42, 0.57, 0.93)),
    *(
        (8, seat, top, bottom, (0.14, 0.27, 0.42, 0.57, 0.93))
        for seat, (top, bottom) in zip(
            (32, 18, 26, 24, 12, 21, 3, 29, 15, 25, 16, 28, 27, 4, 22, 9, 5, 6, 7),
            pairwise(SURAT_ST_LINES),
            strict=True,
        )
    ),
    (9, 1, 0.1657, 0.1882, (0.14, 0.30, 0.51, 0.51, 0.91)),
    (9, 2, 0.1882, 0.2108, (0.14, 0.30, 0.51, 0.51, 0.91)),
    (9, 8, 0.2108, 0.2336, (0.14, 0.30, 0.51, 0.51, 0.91)),
    (9, 10, 0.2336, 0.2564, (0.14, 0.30, 0.51, 0.51, 0.91)),
    *(
        (9, seat, top, bottom, (0.14, 0.30, 0.51, 0.51, 0.91))
        for seat, (top, bottom) in zip(
            (11, 13, 14, 19, 20, 23, 30, 31, 33, 34, 35, 36),
            pairwise(SURAT_GENERAL_LINES),
            strict=True,
        )
    ),
)
ASSIGNMENT_SUMMARY_ROWS = {
    "zp_member_morabi_dp_2020.pdf": MORBI_ASSIGNMENT_ROWS,
    "zp_member_patan_dp_2020.pdf": PATAN_ASSIGNMENT_ROWS,
    "zp_member_rajkot_dp_2020.pdf": RAJKOT_ASSIGNMENT_ROWS,
    "zp_member_surat_dp_2020.pdf": SURAT_ASSIGNMENT_ROWS,
}

# These five low-contrast cells remain unreadable to Tesseract in both the
# page-wide and isolated-cell passes. The readings were transcribed from the
# rendered source pages and are retained in the raw OCR record so the manual
# intervention is explicit and auditable.
REVIEWED_NAME_READINGS = {
    ("zp_member_bharuch_dp_2020.pdf", 18): "ખરચ",
    ("zp_member_bharuch_dp_2020.pdf", 32): "વાલીયા",
    ("zp_member_bharuch_dp_2020.pdf", 33): "વેડચ",
    ("block_member_vadodara_tps_2020.pdf", 8): "ધનિયાવી",
    ("block_member_vadodara_tps_2020.pdf", 11): "ઇટોલા",
}

# Values are fractions of page width, which survives scan resolution and the
# small translation among files. The SEC's native-text orders use one template
# per government level. Its scanned Bharuch taluka order uses a distinct grid.
LAYOUTS = {
    "zp_member_native": {
        "minimum_score": 0.16,
        "mean_score": 0.25,
        "lines": [0.280, 0.353, 0.493, 0.581, 0.672, 0.764, 0.948],
        "columns": {
            "seat_no_raw": (0.280, 0.353),
            "ward_name_raw": (0.353, 0.493),
            "block_raw": (0.493, 0.581),
            "sc_rank_raw": (0.581, 0.672),
            "st_rank_raw": (0.672, 0.764),
            "reservation_raw": (0.764, 0.948),
        },
    },
    "block_member_native": {
        "minimum_score": 0.16,
        "mean_score": 0.25,
        "lines": [0.133, 0.200, 0.312, 0.391, 0.530, 0.630, 0.736, 0.928],
        "columns": {
            "seat_no_raw": (0.312, 0.391),
            "ward_name_raw": (0.391, 0.530),
            "sc_rank_raw": (0.530, 0.630),
            "st_rank_raw": (0.630, 0.736),
            "reservation_raw": (0.736, 0.928),
        },
    },
    "block_member_bharuch_scan": {
        "minimum_score": 0.09,
        "mean_score": 0.25,
        "lines": [0.118, 0.181, 0.289, 0.390, 0.486, 0.586, 0.689, 0.911],
        "columns": {
            "seat_no_raw": (0.289, 0.390),
            "ward_name_raw": (0.390, 0.486),
            "sc_rank_raw": (0.486, 0.586),
            "st_rank_raw": (0.586, 0.689),
            "reservation_raw": (0.689, 0.911),
        },
    },
    "block_member_wide_scan": {
        "minimum_score": 0.16,
        "mean_score": 0.25,
        "maximum_row_gap": 140,
        "header_lines_to_drop": 3,
        "lines": [0.155, 0.220, 0.332, 0.411, 0.541, 0.655, 0.761, 0.957],
        "columns": {
            "seat_no_raw": (0.332, 0.411),
            "ward_name_raw": (0.411, 0.541),
            "sc_rank_raw": (0.541, 0.655),
            "st_rank_raw": (0.655, 0.761),
            "reservation_raw": (0.761, 0.957),
        },
    },
    "block_member_compact_scan": {
        "minimum_score": 0.16,
        "mean_score": 0.25,
        "lines": [0.112, 0.177, 0.288, 0.367, 0.497, 0.602, 0.711, 0.950],
        "columns": {
            "seat_no_raw": (0.288, 0.367),
            "ward_name_raw": (0.367, 0.497),
            "sc_rank_raw": (0.497, 0.602),
            "st_rank_raw": (0.602, 0.711),
            "reservation_raw": (0.711, 0.950),
        },
    },
    "block_member_full_width_scan": {
        "minimum_score": 0.16,
        "mean_score": 0.25,
        "lines": [0.133, 0.198, 0.309, 0.388, 0.520, 0.632, 0.747, 0.985],
        "columns": {
            "seat_no_raw": (0.309, 0.388),
            "ward_name_raw": (0.388, 0.520),
            "sc_rank_raw": (0.520, 0.632),
            "st_rank_raw": (0.632, 0.747),
            "reservation_raw": (0.747, 0.985),
        },
    },
    "block_member_centered_scan": {
        "minimum_score": 0.16,
        "mean_score": 0.25,
        "lines": [0.144, 0.206, 0.310, 0.385, 0.508, 0.608, 0.710, 0.939],
        "columns": {
            "seat_no_raw": (0.310, 0.385),
            "ward_name_raw": (0.385, 0.508),
            "sc_rank_raw": (0.508, 0.608),
            "st_rank_raw": (0.608, 0.710),
            "reservation_raw": (0.710, 0.939),
        },
    },
    "block_member_morbi_scan": {
        "minimum_score": 0.16,
        "mean_score": 0.25,
        "lines": [0.148, 0.214, 0.325, 0.405, 0.541, 0.639, 0.746, 0.938],
        "columns": {
            "seat_no_raw": (0.325, 0.405),
            "ward_name_raw": (0.405, 0.541),
            "sc_rank_raw": (0.541, 0.639),
            "st_rank_raw": (0.639, 0.746),
            "reservation_raw": (0.746, 0.938),
        },
    },
    "block_member_mundra_scan": {
        "minimum_score": 0.16,
        "mean_score": 0.25,
        "lines": [0.160, 0.226, 0.327, 0.407, 0.536, 0.628, 0.729, 0.945],
        "columns": {
            "seat_no_raw": (0.327, 0.407),
            "ward_name_raw": (0.407, 0.536),
            "sc_rank_raw": (0.536, 0.628),
            "st_rank_raw": (0.628, 0.729),
            "reservation_raw": (0.729, 0.945),
        },
    },
}
TIER_LAYOUTS = {
    "zp_member": ("zp_member_native",),
    "block_member": (
        "block_member_native",
        "block_member_bharuch_scan",
        "block_member_wide_scan",
        "block_member_compact_scan",
        "block_member_full_width_scan",
        "block_member_centered_scan",
        "block_member_morbi_scan",
        "block_member_mundra_scan",
    ),
}
TOPOLOGY_WINDOWS = {
    "zp_member": (
        (0.24, 0.32),
        (0.32, 0.40),
        (0.40, 0.53),
        (0.50, 0.60),
        (0.60, 0.69),
        (0.69, 0.78),
        (0.85, 0.96),
    ),
    "block_member": (
        (0.09, 0.17),
        (0.17, 0.24),
        (0.27, 0.35),
        (0.35, 0.43),
        (0.47, 0.56),
        (0.57, 0.67),
        (0.68, 0.78),
        (0.90, 0.995),
    ),
}
COLUMN_WIDTHS = {
    "zp_member": {
        "seat_no_raw": (0.04, 0.09),
        "ward_name_raw": (0.08, 0.17),
        "block_raw": (0.07, 0.12),
        "sc_rank_raw": (0.07, 0.11),
        "st_rank_raw": (0.07, 0.11),
        "reservation_raw": (0.15, 0.25),
    },
    "block_member": {
        "seat_no_raw": (0.07, 0.11),
        "ward_name_raw": (0.09, 0.15),
        "sc_rank_raw": (0.08, 0.12),
        "st_rank_raw": (0.09, 0.12),
        "reservation_raw": (0.18, 0.25),
    },
}


def page_count(path):
    """Return the page count reported by pdfinfo."""
    result = subprocess.run(
        ["pdfinfo", str(path)], capture_output=True, text=True, check=True
    )
    for line in result.stdout.splitlines():
        if line.startswith("Pages:"):
            return int(line.split()[1])
    raise RuntimeError(f"pdfinfo did not report a page count for {path}")


def render(path, page, dpi, target):
    """Render one PDF page to ``target`` using Poppler."""
    subprocess.run(
        [
            "pdftoppm",
            "-f",
            str(page),
            "-l",
            str(page),
            "-r",
            str(dpi),
            "-png",
            "-singlefile",
            str(path),
            str(target.with_suffix("")),
        ],
        capture_output=True,
        check=True,
    )


def _vertical_score(image, ratios):
    gray = image.convert("L")
    pixels = gray.load()
    width, height = gray.size
    top, bottom = int(height * 0.15), int(height * 0.85)
    scores = []
    for ratio in ratios:
        left = max(0, int((ratio - 0.012) * width))
        right = min(width, int((ratio + 0.012) * width) + 1)
        score = (
            max(
                sum(pixels[x, y] < 180 for y in range(top, bottom))
                for x in range(left, right)
            )
            / height
        )
        scores.append(score)
    return scores


def detect_layout(image, tier, windows=None):
    """Detect exact grid rules within the reviewed tier-specific topology."""
    gray = image.convert("L")
    pixels = gray.load()
    width, height = gray.size
    top, bottom = int(height * 0.15), int(height * 0.85)
    ratios = []
    for left, right in windows or TOPOLOGY_WINDOWS[tier]:
        best = max(
            range(int(left * width), int(right * width) + 1),
            key=lambda x: sum(pixels[x, y] < 180 for y in range(top, bottom)),
        )
        ratios.append(best / width)
    return layout_from_lines(tier, ratios)


def layout_from_lines(tier, ratios):
    """Build column bounds from detected or reviewed vertical rules."""
    if tier == "zp_member":
        names = (
            "seat_no_raw",
            "ward_name_raw",
            "block_raw",
            "sc_rank_raw",
            "st_rank_raw",
            "reservation_raw",
        )
    else:
        names = (
            "unused_serial",
            "unused_body",
            "seat_no_raw",
            "ward_name_raw",
            "sc_rank_raw",
            "st_rank_raw",
            "reservation_raw",
        )
    columns = {
        name: (ratios[index], ratios[index + 1])
        for index, name in enumerate(names)
        if not name.startswith("unused_")
    }
    layout = {
        "minimum_score": 0.12,
        "mean_score": 0.25,
        "header_lines_to_drop": None,
        "lines": ratios,
        "columns": columns,
    }
    if tier == "block_member":
        layout["maximum_row_gap"] = 140
    return layout


def layout_shape_is_valid(layout, tier):
    """Reject other SEC tables that do not have the roster's column widths."""
    return all(
        minimum <= right - left <= maximum
        for column, (minimum, maximum) in COLUMN_WIDTHS[tier].items()
        for left, right in (layout["columns"][column],)
    )


def roster_score(image, layout):
    """Score how closely a rendered page matches the reviewed roster grid."""
    scores = _vertical_score(image, LAYOUTS[layout]["lines"])
    return min(scores), statistics.fmean(scores)


def find_roster_page(path, tier, directory):
    """Find the unique page carrying the final constituency roster."""
    pages = page_count(path)
    candidates = []
    detected_candidates = []
    for page in range(1, pages + 1):
        target = directory / f"discovery-{page}.png"
        render(path, page, DISCOVERY_DPI, target)
        image = Image.open(target)
        detected = detect_layout(image, tier)
        detected_score = roster_score_config(image, detected)
        if (
            layout_shape_is_valid(detected, tier)
            and detected_score[0] >= detected["minimum_score"]
            and detected_score[1] >= detected["mean_score"]
        ):
            detected_candidates.append((detected_score, page, detected))
        for layout in TIER_LAYOUTS[tier]:
            score = roster_score(image, layout)
            candidates.append((score, page, layout))
    detected_candidates.sort(reverse=True)
    if detected_candidates:
        (minimum, mean), page, detected = detected_candidates[0]
        other_pages = [
            candidate for candidate in detected_candidates[1:] if candidate[1] != page
        ]
        if other_pages and other_pages[0][0][0] >= minimum * 0.9:
            raise RuntimeError(
                f"detected roster topology is ambiguous in {path.name}: "
                f"pages {page} and {other_pages[0][1]}"
            )
        return page, f"{tier}_detected", detected, minimum, mean

    candidates.sort(reverse=True)
    (minimum, mean), page, layout = candidates[0]
    expected = LAYOUTS[layout]
    if minimum < expected["minimum_score"] or mean < expected["mean_score"]:
        raise RuntimeError(
            f"no roster layout found in {path.name}; best page {page} "
            f"scored min={minimum:.3f}, mean={mean:.3f}"
        )
    other_pages = [candidate for candidate in candidates[1:] if candidate[1] != page]
    if other_pages and other_pages[0][0][0] >= minimum * 0.9:
        raise RuntimeError(
            f"roster layout is ambiguous in {path.name}: "
            f"pages {page} and {other_pages[0][1]}"
        )
    return page, layout, expected, minimum, mean


def find_roster_pages(path, tier, directory):
    """Return one or more reviewed roster-page layouts for a source."""
    overrides = ROSTER_PAGE_OVERRIDES.get(path.name)
    if overrides is None:
        return [find_roster_page(path, tier, directory)]

    found = []
    prior_lines = None
    for page, header_lines_to_drop in overrides.items():
        target = directory / f"discovery-{page}.png"
        render(path, page, DISCOVERY_DPI, target)
        image = Image.open(target)
        windows = None
        if prior_lines is not None:
            windows = tuple((ratio - 0.03, ratio + 0.03) for ratio in prior_lines)
        reviewed_lines = ROSTER_PAGE_LINES.get((path.name, page))
        layout = (
            layout_from_lines(tier, list(reviewed_lines))
            if reviewed_lines is not None
            else detect_layout(image, tier, windows)
        )
        if header_lines_to_drop == 0:
            layout["minimum_score"] = 0.05
            layout["mean_score"] = 0.05
        minimum, mean = roster_score_config(image, layout)
        if not layout_shape_is_valid(layout, tier):
            raise RuntimeError(f"invalid roster topology on {path.name} page {page}")
        if minimum < layout["minimum_score"] or mean < layout["mean_score"]:
            raise RuntimeError(
                f"weak roster topology on {path.name} page {page}: "
                f"min={minimum:.3f}, mean={mean:.3f}"
            )
        layout["header_lines_to_drop"] = header_lines_to_drop
        layout["minimum_row_lines"] = 3 if header_lines_to_drop == 0 else 12
        found.append((page, f"{tier}_detected", layout, minimum, mean))
        prior_lines = layout["lines"]
    return found


def roster_score_config(image, layout):
    """Score a concrete layout configuration."""
    scores = _vertical_score(image, layout["lines"])
    return min(scores), statistics.fmean(scores)


def _runs(values, threshold):
    runs = []
    start = None
    for index, value in enumerate(values):
        if value > threshold and start is None:
            start = index
        elif value <= threshold and start is not None:
            runs.append((start + index - 1) // 2)
            start = None
    if start is not None:
        runs.append((start + len(values) - 1) // 2)
    return runs


def row_boundaries(image, *, maximum_gap=95, header_lines_to_drop=1, minimum_lines=12):
    """Return the horizontal bounds of every constituency row."""
    gray = image.convert("L")
    pixels = gray.load()
    width, height = gray.size
    left, right = int(width * 0.10), int(width * 0.96)
    darkness = [
        sum(pixels[x, y] < 180 for x in range(left, right)) for y in range(height)
    ]
    detected = _runs(darkness, width * 0.25)
    lines = []
    for line in detected:
        if not lines or line - lines[-1] >= 25:
            lines.append(line)
    groups = []
    group = []
    for line in lines:
        if not group or 35 <= line - group[-1] <= maximum_gap:
            group.append(line)
        else:
            groups.append(group)
            group = [line]
    groups.append(group)
    sequence = max(groups, key=len)
    if len(sequence) < minimum_lines:
        raise RuntimeError(
            f"roster has too few regularly spaced row lines: {len(sequence)}"
        )
    if header_lines_to_drop is None:
        gaps = [right - left for left, right in pairwise(sequence)]
        body_gap = statistics.median(gaps)
        wide_headers = 0
        for gap in gaps:
            if gap <= body_gap * 1.4:
                break
            wide_headers += 1
        header_lines_to_drop = wide_headers + 1
    # Layout metadata or the inferred leading-band geometry says how many
    # header rules precede the body.
    return sequence[header_lines_to_drop:]


def tsv_words(image_path):
    """Run Gujarati OCR and return word boxes from Tesseract TSV output."""
    result = subprocess.run(
        [
            "tesseract",
            str(image_path),
            "stdout",
            "-l",
            "guj+eng",
            "--psm",
            "3",
            "tsv",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    words = []
    for row in csv.DictReader(result.stdout.splitlines(), delimiter="\t"):
        text = (row.get("text") or "").strip()
        if not text:
            continue
        left = int(row["left"])
        top = int(row["top"])
        width = int(row["width"])
        height = int(row["height"])
        words.append(
            {
                "text": text,
                "x": left + width / 2,
                "y": top + height / 2,
                "confidence": float(row["conf"]),
            }
        )
    return words


def cell_text(words, x0, x1, y0, y1):
    """Join OCR words whose centres lie within one printed table cell."""
    held = [word for word in words if x0 < word["x"] < x1 and y0 < word["y"] < y1]
    held.sort(key=lambda word: (word["y"], word["x"]))
    return " ".join(word["text"] for word in held), [
        word["confidence"] for word in held
    ]


def ocr_cell(image, box, target, *, psm=6):
    """OCR one isolated cell without the surrounding table rules."""
    left, top, right, bottom = box
    crop = image.crop((left + 6, top + 3, right - 6, bottom - 3))
    crop = ImageOps.expand(crop, border=20, fill="white")
    crop.save(target)
    result = subprocess.run(
        [
            "tesseract",
            str(target),
            "stdout",
            "-l",
            "guj",
            "--psm",
            str(psm),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    return " ".join(result.stdout.split())


def extract_assignment_summary(path, tier, row_specs):
    """Extract category-assignment tables from reviewed page regions."""
    district, body = geography.places(path.name, tier)
    rows = []
    with tempfile.TemporaryDirectory(dir="/private/tmp") as temporary:
        directory = pathlib.Path(temporary)
        images = {}
        words_by_page = {}
        for page in {spec[0] for spec in row_specs}:
            image_path = directory / f"summary-{page}.png"
            render(path, page, OCR_DPI, image_path)
            images[page] = Image.open(image_path)
            words_by_page[page] = tsv_words(image_path)
        for page, seat, top, bottom, lines in row_specs:
            image = images[page]
            words = words_by_page[page]
            width, height = image.size
            x0, x1, x2, x3, x4 = (int(value * width) for value in lines)
            y0, y1 = int(top * height), int(bottom * height)
            values = {}
            confidences = []
            for column, left, right in (
                ("seat_no_raw", x0, x1),
                ("ward_name_raw", x1, x2),
                ("reservation_raw", x3, x4),
            ):
                page_value, got = cell_text(words, left, right, y0, y1)
                confidences.extend(got)
                isolated = ocr_cell(
                    image,
                    (left, y0, right, y1),
                    directory / f"cell-{page}-{seat}-{column}.png",
                    psm=13,
                )
                if column == "ward_name_raw" and any(
                    "઀" <= character <= "૿" for character in page_value
                ):
                    values[column] = page_value
                    values["ward_name_alt_raw"] = isolated
                else:
                    values[column] = isolated or page_value
                values[column.replace("_raw", "_page_raw")] = page_value
            values["reservation_alt_raw"] = ocr_cell(
                image,
                (x3, y0, x4, y1),
                directory / f"cell-{page}-{seat}-reservation-alt.png",
                psm=11,
            )
            rows.append(
                {
                    "source_pdf": path.name,
                    "source_page": page,
                    "tier": tier,
                    "district": district,
                    "body": body,
                    "row_order": seat,
                    "roster_layout": "zp_member_assignment_summary",
                    "roster_layout_lines": [round(value, 4) for value in lines],
                    "roster_layout_min_score": "",
                    "roster_layout_mean_score": "",
                    "ocr_mean_confidence": (
                        round(statistics.fmean(confidences), 2) if confidences else ""
                    ),
                    **values,
                }
            )
    return sorted(rows, key=lambda row: row["row_order"])


def extract(path, tier):
    """Extract the raw rows from one held source document."""
    if path.name in ASSIGNMENT_SUMMARY_ROWS:
        return extract_assignment_summary(
            path, tier, ASSIGNMENT_SUMMARY_ROWS[path.name]
        )
    with tempfile.TemporaryDirectory(dir="/private/tmp") as temporary:
        directory = pathlib.Path(temporary)
        district, body = geography.places(path.name, tier)
        rows = []
        for page, layout_name, layout, minimum, mean in find_roster_pages(
            path, tier, directory
        ):
            image_path = directory / f"roster-{page}.png"
            render(path, page, OCR_DPI, image_path)
            image = Image.open(image_path)
            width, _ = image.size
            boundaries = row_boundaries(
                image,
                maximum_gap=layout.get("maximum_row_gap", 95),
                header_lines_to_drop=layout.get("header_lines_to_drop", 1),
                minimum_lines=layout.get("minimum_row_lines", 12),
            )
            words = tsv_words(image_path)
            row_offset = len(rows)
            for local_order, (top, bottom) in enumerate(pairwise(boundaries), 1):
                row_order = row_offset + local_order
                row = {
                    "source_pdf": path.name,
                    "source_page": page,
                    "tier": tier,
                    "district": district,
                    "body": body,
                    "row_order": row_order,
                    "roster_layout": layout_name,
                    "roster_layout_lines": [
                        round(value, 4) for value in layout["lines"]
                    ],
                    "roster_layout_min_score": round(minimum, 4),
                    "roster_layout_mean_score": round(mean, 4),
                }
                confidences = []
                for column, (left, right) in layout["columns"].items():
                    value, got = cell_text(
                        words, left * width, right * width, top, bottom
                    )
                    row[column] = value
                    confidences.extend(got)
                    if column in {
                        "ward_name_raw",
                        "block_raw",
                        "reservation_raw",
                    }:
                        box = (int(left * width), top, int(right * width), bottom)
                        cell_path = directory / (
                            f"cell-{page}-{local_order}-{column}.png"
                        )
                        isolated = ocr_cell(image, box, cell_path)
                        if isolated:
                            if column == "reservation_raw":
                                row["reservation_page_raw"] = value
                            else:
                                page_column = column.replace("_raw", "_page_raw")
                                row[page_column] = value
                            row[column] = isolated
                        if column == "ward_name_raw":
                            row["ward_name_alt_raw"] = ocr_cell(
                                image, box, cell_path, psm=11
                            )
                        if column == "reservation_raw":
                            row["reservation_alt_raw"] = ocr_cell(
                                image, box, cell_path, psm=13
                            )
                row["ocr_mean_confidence"] = (
                    round(statistics.fmean(confidences), 2) if confidences else ""
                )
                rows.append(row)
        expected = controls.DISTRICT_ROW_COUNTS.get(
            path.name
        ) or controls.TALUKA_ROW_COUNTS.get(path.name)
        if expected is not None and len(rows) != expected:
            excess = len(rows) - expected
            if not 1 <= excess <= 3:
                raise RuntimeError(
                    f"{path.name} yielded {len(rows)} rows; expected {expected}"
                )
            LOGGER.warning(
                "Leading table headers removed",
                extra={
                    "event": "table_headers_removed",
                    "source_file": path.name,
                    "rows_removed": excess,
                },
            )
            rows = rows[excess:]
            for row_order, row in enumerate(rows, 1):
                row["row_order"] = row_order
    for row in rows:
        reviewed = REVIEWED_NAME_READINGS.get((path.name, row["row_order"]))
        if reviewed:
            row["ward_name_reviewed_raw"] = reviewed
    return rows


def write(rows, path):
    """Write one raw OCR record per line."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


@command("extract", state="Gujarat", method="tesseract")
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pdf", help="process filenames containing this text")
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()

    for path in sorted(harvest.OUT.glob("*.pdf")):
        if args.pdf and args.pdf.lower() not in path.name.lower():
            continue
        target = OCR / f"{path.stem}.jsonl"
        if target.exists() and not args.refresh:
            continue
        tier = "zp_member" if path.name.startswith("zp_member_") else "block_member"
        rows = extract(path, tier)
        write(rows, target)
        LOGGER.info(
            "Source OCR completed",
            extra={
                "event": "source_ocr_completed",
                "source_file": path.name,
                "rows": len(rows),
                "source_pages": sorted({row["source_page"] for row in rows}),
            },
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
