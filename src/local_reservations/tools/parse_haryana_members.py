"""Build source-reviewed Haryana 2000 ZP category readings and audit local OCR.

The checked English tables identify district, ward and a reported Category.
These outputs preserve that source meaning; they do not establish reservation
semantics or infer a winner's characteristics. Review is by the primary reader,
not an independent adjudicator. The raw model pass remains separate evidence.
"""

import argparse
import csv
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from local_reservations.common.runlog import command
from local_reservations.paths import ROOT
from local_reservations.tools.historical_harvest import checksum
from local_reservations.tools.ocr_haryana_members import validate_response
from local_reservations.tools.parse_haryana_gazettes import candidate_category

BASE = ROOT / "data/source_search/national/haryana/early_cycles"
FIELDS = {
    "source_sha256": (pa.string(), "SHA256 of the original held PDF."),
    "source_url": (pa.string(), "Official PDF acquisition URL."),
    "source_path": (pa.string(), "PDF path relative to early_cycles."),
    "source_page": (pa.int64(), "One-based original PDF page."),
    "source_year": (pa.int64(), "Year visibly printed in the gazette."),
    "district_index": (pa.string(), "District label in official link directory."),
    "district_printed": (pa.string(), "District spelling in the English notification."),
    "ward": (pa.int64(), "Visually checked printed ward number."),
    "tier": (pa.string(), "District member from notification scope and continuation."),
    "category_reading": (
        pa.string(),
        "Standardized reading of Category; not a verbatim punctuation transcription.",
    ),
    "caste_reported": (pa.string(), "Reported category NONE/SC/BC; null if blank."),
    "woman_reported": (
        pa.bool_(),
        "Woman marker in reported category; no inference from name or vacancy.",
    ),
    "missing_reason": (pa.string(), "Source reason for a missing category, if any."),
    "status_text": (
        pa.string(),
        "Explicit vacancy or election-status text, if checked.",
    ),
    "corroborating_page": (
        pa.int64(),
        "Additional source page used to check a reading.",
    ),
    "review_note": (pa.string(), "Source qualifications and continuation decisions."),
    "reviewer": (pa.string(), "Identity of source reader."),
    "review_method": (pa.string(), "Method used for cell review."),
    "review_date": (pa.string(), "ISO date of visual review."),
    "review_status": (
        pa.string(),
        "Primary visual review; independent review pending.",
    ),
}


def checked_rows(cells, pages):
    page_map = {}
    expected = set()
    for page in pages:
        key = (page["source_sha256"], page["source_page"])
        if key in page_map:
            raise ValueError("Duplicate reviewed page")
        page_map[key] = page
        wards = page["printed_ward_keys"]
        if len(set(wards)) != len(wards) or any(
            type(w) is not int or w < 1 for w in wards
        ):
            raise ValueError("Invalid printed ward frame")
        expected.update((*key, ward) for ward in wards)
    seen, result = set(), []
    for cell in cells:
        if type(cell["ward"]) is not int or type(cell["source_page"]) is not int:
            raise ValueError("Reviewed page and ward must be integers")
        if cell["woman"] is not None and type(cell["woman"]) is not bool:
            raise ValueError("Woman component must be boolean or null")
        key = (cell["source_sha256"], cell["source_page"], cell["ward"])
        if key in seen or key not in expected:
            raise ValueError("Duplicate or unexpected reviewed office key")
        seen.add(key)
        page = page_map[key[:2]]
        if cell["district"] != page["district_index"]:
            raise ValueError("Cell and page district disagree")
        category = candidate_category(cell["category_reading"] or "")
        if category != (cell["caste"], cell["woman"]):
            raise ValueError("Checked category components disagree")
        missing = category == (None, None)
        if missing != bool(cell.get("missing_reason")):
            raise ValueError("Missing category requires a source reason")
        row = {k: page[k] for k in FIELDS if k in page}
        row.update(
            {
                k: cell.get(k)
                for k in [
                    "ward",
                    "category_reading",
                    "missing_reason",
                    "status_text",
                    "corroborating_page",
                    "review_note",
                    "reviewer",
                    "review_method",
                    "review_date",
                ]
            }
        )
        row.update(
            tier="district_member",
            caste_reported=cell["caste"],
            woman_reported=cell["woman"],
            review_status="primary_visual_review; independent_review_pending",
        )
        result.append(row)
    if seen != expected:
        raise ValueError("Reviewed cells do not cover the checked page frame")
    return result


def compare_model(cells, predictions):
    keyed = defaultdict(list)
    invalid = []
    for prediction in predictions:
        ward = re.fullmatch(r"\s*([0-9]+)\s*\*?\s*", prediction["ward_raw"] or "")
        if ward is None:
            invalid.append(prediction)
            continue
        key = (
            prediction["source_sha256"],
            prediction["source_page"],
            int(ward[1]),
        )
        keyed[key].append(prediction)
    details, expected = [], set()
    for cell in cells:
        key = (cell["source_sha256"], cell["source_page"], cell["ward"])
        expected.add(key)
        values = keyed[key]
        if not values:
            status = "missing_office_key"
        elif len(values) > 1:
            status = "duplicate_office_key"
        else:
            value = candidate_category(values[0]["category_raw"] or "")
            truth = (cell["caste"], cell["woman"])
            if value == truth:
                status = "correct_source_blank" if truth == (None, None) else "correct"
                if truth == (None, None) and values[0]["category_raw"]:
                    status = "unsupported_text_in_source_blank"
            elif value == (None, None):
                status = "category_abstained"
            else:
                status = "wrong_category"
        details.append(
            {k: cell[k] for k in ["source_sha256", "source_page", "district", "ward"]}
            | {"status": status, "corroborating_page": cell.get("corroborating_page")}
        )
    scores = dict(Counter(r["status"] for r in details))
    scores.update(
        total=len(cells),
        invalid_predicted_ward=len(invalid),
        extra_predicted_rows=sum(len(v) for k, v in keyed.items() if k not in expected),
        predicted_rows=len(predictions),
    )
    return scores, details


@command("parse", state="Haryana", vintage="2000_reviewed_members")
def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=BASE)
    args = parser.parse_args()
    base, out = args.source, args.source / "member_review"
    cells = json.loads((out / "cell_reviews.json").read_text())
    pages = json.loads((out / "page_reviews.json").read_text())
    inputs = [Path(__file__), out / "cell_reviews.json", out / "page_reviews.json"]
    for page in pages:
        original = base / page["source_path"]
        if original not in inputs:
            if checksum(original) != page["source_sha256"]:
                raise ValueError("Original PDF hash changed")
            inputs.append(original)
    rows = checked_rows(cells, pages)
    schema = pa.schema([(k, v[0]) for k, v in FIELDS.items()])
    table = pa.Table.from_pylist(rows, schema=schema)
    pq.write_table(table, out / "category_rows.parquet")
    table.to_pandas().to_csv(out / "category_rows.csv", index=False)
    with (out / "dictionary.csv").open("w") as stream:
        writer = csv.writer(stream)
        writer.writerow(["field", "arrow_type", "meaning"])
        writer.writerows((k, str(t), meaning) for k, (t, meaning) in FIELDS.items())
    (out / "schema.json").write_text(
        json.dumps({k: str(v[0]) for k, v in FIELDS.items()}, indent=2) + "\n"
    )
    predictions, page_status, completed = [], [], set()
    for page in pages:
        key = (page["source_sha256"], page["source_page"])
        path = base / "vision_members" / f"{key[0]}_{key[1]:04d}.json"
        status, count = "not_completed", 0
        if path.exists():
            inputs.append(path)
            raw = json.loads(path.read_text())
            if (raw["source_sha256"], raw["source_page"]) != key:
                raise ValueError("Model receipt source identity mismatch")
            status = raw["status"]
            if status == "response_saved":
                predicted = validate_response(raw["response"])
                if predicted != raw["rows"]:
                    raise ValueError("Model receipt rows differ from original response")
                completed.add(key)
                count = len(predicted)
                predictions.extend(
                    r
                    | {
                        "source_sha256": key[0],
                        "source_page": key[1],
                        "response_sha256": checksum(path),
                        "model_digest": raw["model_digest"],
                    }
                    for r in predicted
                )
        page_status.append(
            {k: page[k] for k in ["source_sha256", "source_page", "district_index"]}
            | {
                "model_status": status,
                "model_rows": count,
                "checked_rows": len(page["printed_ward_keys"]),
            }
        )
    scored = [r for r in cells if (r["source_sha256"], r["source_page"]) in completed]
    scores, details = compare_model(scored, predictions)
    for name, payload in [
        ("model_candidates", predictions),
        ("model_page_status", page_status),
        ("model_comparison", details),
    ]:
        (out / f"{name}.json").write_text(json.dumps(payload, indent=2) + "\n")
    summary = {
        "reviewed_rows": len(rows),
        "reviewed_pages": len(pages),
        "districts": len({r["district_index"] for r in rows}),
        "source_blank_categories": sum(r["caste_reported"] is None for r in rows),
        "model_completed_pages": len(completed),
        "model_uncompleted_pages": len(pages) - len(completed),
        "model_scores_on_completed_pages": scores,
        "scope": (
            "Primary visual Category readings; independent and reservation-semantic "
            "review pending. Model scores include cross-page corroborated cells, "
            "identified in model_comparison.json; not a blind independent evaluation."
        ),
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    inputs.extend(
        ROOT / f"src/local_reservations/tools/{name}.py"
        for name in [
            "parse_haryana_gazettes",
            "parse_haryana_historical",
            "ocr_haryana_members",
        ]
    )
    (out / "inputs.json").write_text(
        json.dumps({str(p.relative_to(ROOT)): checksum(p) for p in inputs}, indent=2)
        + "\n"
    )
    print(json.dumps(summary))


if __name__ == "__main__":
    main()
