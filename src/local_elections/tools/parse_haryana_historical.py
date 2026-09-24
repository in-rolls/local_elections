"""Extract the archived column tables, keeping unresolved layouts for review.

Only the explicit GP/ward/name/relation/category and ward/name/relation/category
headers are accepted. The original header rectangles locate columns; ward cells
locate rows. Every row carries raw cells, source coordinates and a review status.
This staging parse is separate from the released master.
"""

import argparse
import csv
import hashlib
import json
import re
from itertools import pairwise
from pathlib import Path

import pandas as pd
import pdfplumber
import pyarrow as pa
import pyarrow.parquet as pq

from local_elections.common.runlog import command


def reservation(raw):
    token = re.sub(r"[^A-Z]", "", raw.upper())
    mapping = {
        "UNRESERVED": ("NONE", False),
        "UNREASERVED": ("NONE", False),
        "GENERAL": ("NONE", False),
        "WOMEN": ("NONE", True),
        "WOMAN": ("NONE", True),
        "SC": ("SC", False),
        "BC": ("BC", False),
        "SCWOMEN": ("SC", True),
        "SCWOMAN": ("SC", True),
        "BCWOMEN": ("BC", True),
        "BCWOMAN": ("BC", True),
    }
    return mapping.get(token, (None, None))


def header_columns(page, gp):
    expected = (
        ["GP NAME", "WARD NO.", "NAME", "F/H NAME", "CATEGORY"]
        if gp
        else ["WARD NO.", "NAME", "F/H NAME", "CATEGORY"]
    )
    for table in page.find_tables():
        rows = table.extract()
        if not rows or rows[0] != expected:
            continue
        cells = sorted(table.rows[0].cells, key=lambda cell: cell[0])
        return cells, max(cell[3] for cell in cells)
    return None, None


def parse_document(path, family, layout_reviews=()):
    gp = family == "gp_head_and_ward"
    records, pages = [], []
    with pdfplumber.open(path) as pdf:
        cells, header_bottom = header_columns(pdf.pages[0], gp)
        title = (pdf.pages[0].extract_text() or "").splitlines()[0:1]
        title = title[0] if title else ""
        for number, page in enumerate(pdf.pages, 1):
            words = page.extract_words(x_tolerance=1.5, y_tolerance=2)
            page_audit = {
                "page": number,
                "chars": len(page.chars),
                "width": page.width,
                "height": page.height,
                "rows": 0,
                "status": "unsupported_header" if cells is None else "extracted",
            }
            if cells is None:
                pages.append(page_audit)
                continue
            offset = 1 if gp else 0
            ward_box = cells[offset]
            anchors = [
                w
                for w in words
                if ward_box[0] - 2 <= w["x0"] < ward_box[2] - 2
                and re.fullmatch(r"Sarpanc\S*|[0-9]+", w["text"], re.I)
                and w["top"] > (header_bottom if number == 1 else 25)
                and w["bottom"] < page.height - 25
            ]
            anchors.sort(key=lambda word: word["top"])
            for index, anchor in enumerate(anchors):
                top = anchor["top"] - 2
                bottom = (
                    anchors[index + 1]["top"] - 2
                    if index + 1 < len(anchors)
                    else page.height - 25
                )
                row_words = [w for w in words if top <= w["top"] < bottom]
                row_cells = cells
                layout_note = ""
                for review in layout_reviews:
                    if (number, anchor["top"]) < (
                        int(review["start_page"]),
                        float(review["start_y"]),
                    ):
                        continue
                    if number > int(review["end_page"]):
                        continue
                    bounds = json.loads(review["column_edges"])
                    row_cells = [
                        (left, 0, right, page.height)
                        for left, right in pairwise(bounds)
                    ]
                    layout_note = review["review_note"]
                raw_cells = []
                for i, cell in enumerate(row_cells):
                    right = (
                        row_cells[i + 1][0] - 2
                        if i + 1 < len(row_cells)
                        else page.width - 20
                    )
                    left = cell[0] - 2
                    selected = [w for w in row_words if left <= w["x0"] < right]
                    raw_cells.append(" ".join(w["text"] for w in selected).strip())
                ward = raw_cells[offset]
                flag = "ward_cell_contains_extra_text" if ward != anchor["text"] else ""
                category = raw_cells[-1]
                caste, woman = reservation(category)
                flags = [flag] if flag else []
                if layout_note:
                    flags.append("appended_geography_unresolved")
                is_head = bool(re.fullmatch(r"Sarpanc\S*", anchor["text"], re.I))
                if is_head and anchor["text"].lower() != "sarpanch":
                    flags.append("office_spelling_variant")
                if caste is None:
                    flags.append("reservation_unresolved")
                if not raw_cells[offset + 1]:
                    flags.append("winner_name_missing")
                if gp and not raw_cells[0]:
                    flags.append("gp_name_missing")
                records.append(
                    {
                        "title_raw": title,
                        "source_page": number,
                        "source_row_on_page": index + 1,
                        "source_bbox": json.dumps(
                            [row_cells[0][0] - 2, top, page.width - 20, bottom]
                        ),
                        "gram_panchayat_raw": raw_cells[0] if gp else "",
                        "ward_or_office_raw": ward,
                        "tier": ("gp_head" if is_head else "gp_ward") if gp else family,
                        "winner_name_raw": raw_cells[offset + 1],
                        "winner_name": re.sub(r"^\s*\*\s*", "", raw_cells[offset + 1]),
                        "unopposed_or_unanimous_mark": raw_cells[offset + 1]
                        .lstrip()
                        .startswith("*"),
                        "layout_review_note": layout_note,
                        "relation_name_raw": raw_cells[offset + 2],
                        "reservation_raw": category,
                        "caste_reservation": caste,
                        "woman_reserved": woman,
                        "winner_gender": None,
                        "raw_cells": json.dumps(raw_cells, ensure_ascii=False),
                        "quality_flags": ";".join(flags),
                        "review_status": "automated; source_validation_pending",
                    }
                )
            page_audit["rows"] = len(anchors)
            if not words:
                page_audit["status"] = "blank_text_layer"
            elif not anchors:
                page_audit["status"] = "text_page_without_recognized_rows"
            pages.append(page_audit)
    return records, pages


def reconcile_sections(frame, reviews):
    """Require a complete one-to-one match before assigning a reviewed section title."""
    frame = frame.copy()
    frame["section_title_raw"] = ""
    frame["matched_source_sha256"] = ""
    frame["matched_source_page"] = pd.Series(pd.NA, index=frame.index, dtype="Int64")
    keys = [
        "gram_panchayat_raw",
        "ward_or_office_raw",
        "tier",
        "winner_name_raw",
        "relation_name_raw",
        "reservation_raw",
    ]
    for review in reviews:
        mask = frame.source_sha256.eq(
            review["source_sha256"]
        ) & frame.quality_flags.str.contains(
            "appended_geography_unresolved", regex=False
        )
        left = frame.loc[mask, keys].reset_index(names="source_index")
        if left.empty:
            continue
        right = frame.loc[frame.source_sha256.eq(review["evidence_sha256"])]
        expected = int(review["expected_rows"])
        if (
            len(left) != expected
            or len(right) != expected
            or set(right.title_raw) != {review["section_title_raw"]}
        ):
            raise ValueError("Reviewed section or corroborating roster changed")
        matches = left.merge(
            right[[*keys, "source_page"]],
            on=keys,
            how="left",
            validate="one_to_one",
            indicator=True,
        )
        if not matches["_merge"].eq("both").all():
            raise ValueError(
                "Reviewed section no longer matches its corroborating roster"
            )
        indices = matches.source_index
        frame.loc[indices, "section_title_raw"] = review["section_title_raw"]
        frame.loc[indices, "matched_source_sha256"] = review["evidence_sha256"]
        frame.loc[indices, "matched_source_page"] = matches.source_page.to_numpy()
        frame.loc[indices, "quality_flags"] = frame.loc[
            indices, "quality_flags"
        ].str.replace(
            "appended_geography_unresolved",
            "section_geography_corroborated;cross_document_section_repeat",
            regex=False,
        )
    return frame


def apply_reservation_reviews(frame, reviews):
    """Apply source-cell decisions only when the exact occurrence still matches."""
    frame = frame.copy()
    frame["reservation_review_note"] = ""
    frame["reservation_missing_reason"] = ""
    frame["reservation_review_status"] = "automated_mapping"
    key = ["source_sha256", "source_page", "source_row_on_page"]
    if frame.duplicated(key).any():
        raise ValueError("Source occurrence keys must be unique")
    lookup = {tuple(row[k] for k in key): i for i, row in frame.iterrows()}
    seen = set()
    for review in reviews:
        identity = (
            review["source_sha256"],
            int(review["source_page"]),
            int(review["source_row_on_page"]),
        )
        if identity in seen or identity not in lookup:
            raise ValueError("Review has duplicate or absent source occurrence")
        seen.add(identity)
        index = lookup[identity]
        if frame.at[index, "reservation_raw"] != review["reservation_raw"]:
            raise ValueError("Reviewed reservation cell changed")
        caste = review["caste_reservation"] or None
        woman = {"true": True, "false": False, "": None}[review["woman_reserved"]]
        if caste not in {None, "NONE", "SC", "BC"}:
            raise ValueError("Invalid reviewed caste reservation")
        if (caste is None or woman is None) != bool(review["missing_reason"]):
            raise ValueError("Missing components need an explicit source reason")
        frame.at[index, "caste_reservation"] = caste
        frame.at[index, "woman_reserved"] = woman
        frame.at[index, "reservation_review_note"] = review["review_note"]
        frame.at[index, "reservation_missing_reason"] = review["missing_reason"]
        frame.at[index, "reservation_review_status"] = "source_cell_reviewed"
        flags = frame.at[index, "quality_flags"].split(";")
        flags = [f for f in flags if f and f != "reservation_unresolved"]
        if review["missing_reason"]:
            flags.append("reservation_" + review["missing_reason"])
        frame.at[index, "quality_flags"] = ";".join(flags)
    return frame


@command("parse", state="Haryana", vintage="historical")
def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    args = parser.parse_args()
    source = args.source
    out = source / "parsed"
    out.mkdir(exist_ok=True)
    with (source / "seeds.csv").open() as stream:
        seeds = {row["url"]: row for row in csv.DictReader(stream)}
    receipts = {}
    for line in (source / "requests.jsonl").read_text().splitlines():
        row = json.loads(line)
        receipts[row["url"]] = row
    records, pages, documents = [], [], []
    reviews = []
    review_path = source / "layout_reviews.csv"
    if review_path.exists():
        with review_path.open() as stream:
            reviews = list(csv.DictReader(stream))
    section_path = source / "section_reviews.csv"
    section_reviews = []
    if section_path.exists():
        with section_path.open() as stream:
            section_reviews = list(csv.DictReader(stream))
    reservation_path = source / "reservation_reviews.csv"
    reservation_reviews = []
    if reservation_path.exists():
        with reservation_path.open() as stream:
            reservation_reviews = list(csv.DictReader(stream))
    seen = set()
    for url, receipt in receipts.items():
        seed = seeds.get(url)
        if not seed or receipt["status"] != "ok_pdf" or "/web/" not in url:
            continue
        family = seed["family"]
        if family not in {
            "gp_head_and_ward",
            "block_member",
            "district_member",
            "block_and_district_heads",
        }:
            continue
        if receipt["sha256"] in seen:
            continue
        seen.add(receipt["sha256"])
        path = source / receipt["path"]
        with path.open("rb") as stream:
            actual = hashlib.file_digest(stream, "sha256").hexdigest()
        if actual != receipt["sha256"]:
            raise ValueError(f"Source hash mismatch: {path}")
        rows, audit = parse_document(
            path, family, [r for r in reviews if r["source_sha256"] == actual]
        )
        provenance = {
            "source_url": url,
            "original_url": seed["label"],
            "source_path": receipt["path"],
            "source_sha256": actual,
            "state": "Haryana",
            "year_context": 2005,
            "year_basis": "archived 2005 results collection; validate parent context",
        }
        records.extend(row | provenance for row in rows)
        pages.extend(row | provenance for row in audit)
        documents.append(
            provenance
            | {
                "pages": len(audit),
                "rows": len(rows),
                "family": family,
                "title_raw": rows[0]["title_raw"] if rows else "",
                "status": "extracted" if rows else "unsupported_layout",
            }
        )
    if not records:
        raise ValueError("No supported source rows extracted")
    frame = pd.DataFrame(records)
    frame = reconcile_sections(frame, section_reviews)
    frame = apply_reservation_reviews(frame, reservation_reviews)
    frame["woman_reserved"] = frame.woman_reserved.astype("boolean")
    frame["winner_gender"] = frame.winner_gender.astype("string")
    key_columns = ["source_sha256", "gram_panchayat_raw", "ward_or_office_raw"]
    duplicate = frame.duplicated(key_columns, keep=False)
    frame.loc[duplicate, "quality_flags"] += ";duplicate_within_document_office_key"
    table = pa.Table.from_pandas(frame, preserve_index=False)
    pq.write_table(table, out / "seat_rows.parquet")
    frame.loc[
        frame.matched_source_sha256.ne(""),
        [
            "source_path",
            "source_sha256",
            "source_page",
            "source_row_on_page",
            "gram_panchayat_raw",
            "ward_or_office_raw",
            "tier",
            "winner_name_raw",
            "relation_name_raw",
            "reservation_raw",
            "section_title_raw",
            "matched_source_sha256",
            "matched_source_page",
        ],
    ].to_csv(out / "section_matches.csv", index=False)
    pd.DataFrame(pages).to_csv(out / "pages.csv", index=False)
    pd.DataFrame(documents).to_csv(out / "documents.csv", index=False)
    frame.groupby(["tier", "reservation_raw"], dropna=False).size().reset_index(
        name="rows"
    ).to_csv(out / "reservation_profile.csv", index=False)
    (out / "schema.json").write_text(
        json.dumps({f.name: str(f.type) for f in table.schema}, indent=2) + "\n"
    )
    summary = {
        "documents": len(documents),
        "pages": len(pages),
        "rows": len(frame),
        "tier_rows": frame.tier.value_counts().to_dict(),
        "unresolved_reservation_rows": int(frame.caste_reservation.isna().sum()),
        "incomplete_reservation_rows": int(
            (frame.caste_reservation.isna() | frame.woman_reserved.isna()).sum()
        ),
        "reservation_cells_reviewed": int(
            frame.reservation_review_status.eq("source_cell_reviewed").sum()
        ),
        "reservation_missing_reasons": frame.loc[
            frame.reservation_missing_reason.ne(""), "reservation_missing_reason"
        ]
        .value_counts()
        .to_dict(),
        "duplicate_key_rows": int(duplicate.sum()),
        "section_geography_corroborated_rows": int(
            frame.matched_source_sha256.ne("").sum()
        ),
        "appended_geography_unresolved_rows": int(
            frame.quality_flags.str.contains(
                "appended_geography_unresolved", regex=False
            ).sum()
        ),
        "release_status": "research staging; source validation incomplete",
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    input_paths = [Path(__file__), source / "seeds.csv", source / "requests.jsonl"]
    if review_path.exists():
        input_paths.append(review_path)
    if section_path.exists():
        input_paths.append(section_path)
    if reservation_path.exists():
        input_paths.append(reservation_path)
    input_hashes = []
    for path in input_paths:
        with path.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        input_hashes.append({"path": str(path), "sha256": digest})
    (out / "parse_inputs.json").write_text(json.dumps(input_hashes, indent=2) + "\n")
    print(json.dumps(summary))


if __name__ == "__main__":
    main()
