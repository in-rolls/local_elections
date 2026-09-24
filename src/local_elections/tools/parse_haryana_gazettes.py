"""Extract candidate English tables from cached Haryana 2000 gazette OCR.

Every candidate retains its raw OCR line and word geometry. Header discovery and
printed office labels gate extraction; unsupported pages and missing fields are
reported separately. These candidates require source validation before pooling.
"""

import argparse
import csv
import gzip
import json
import re
from collections import defaultdict
from difflib import SequenceMatcher
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from local_elections.common.runlog import command
from local_elections.paths import ROOT
from local_elections.tools.historical_harvest import checksum
from local_elections.tools.parse_haryana_historical import reservation

BASE = ROOT / "data/source_search/national/haryana/early_cycles"
FIELDS = {
    "source_sha256": (pa.string(), "SHA256 of immutable original PDF."),
    "source_url": (pa.string(), "Official acquisition URL."),
    "source_path": (pa.string(), "Original PDF path relative to early_cycles."),
    "source_page": (pa.int64(), "One-based original PDF page."),
    "ocr_sha256": (pa.string(), "SHA256 of compressed page word TSV."),
    "source_line": (pa.string(), "Tesseract block/paragraph/line identifier."),
    "year_context": (
        pa.int64(),
        "2000 from official result directory; individual dates need review.",
    ),
    "district_index": (
        pa.string(),
        "District heading or district file label from official directory.",
    ),
    "block_index": (
        pa.string(),
        "GP file label from index; not necessarily a normalized block.",
    ),
    "local_body_ocr": (
        pa.string(),
        "Last explicit English body label, propagated within document.",
    ),
    "local_body_label_page": (
        pa.int64(),
        "Page supplying local body label; null when absent.",
    ),
    "ward_raw": (pa.string(), "OCR text in ward column; never guessed from a counter."),
    "office_raw": (pa.string(), "Printed office label read by OCR, if present."),
    "tier": (
        pa.string(),
        "gp_head/gp_ward from office label; other tiers from index family.",
    ),
    "winner_name_ocr": (
        pa.string(),
        "Unvalidated OCR of elected-person name; may contain vacancy text.",
    ),
    "relation_name_ocr": (pa.string(), "Unvalidated OCR of relation-name column."),
    "reservation_ocr": (pa.string(), "Unvalidated OCR of reservation cell."),
    "caste_candidate": (
        pa.string(),
        "Exact recognized office category NONE/SC/BC; null on unsupported reading.",
    ),
    "woman_candidate": (
        pa.bool_(),
        "Exact recognized women-reservation component; null on unsupported reading.",
    ),
    "raw_line": (pa.string(), "All OCR words from source line in reading order."),
    "raw_words": (pa.string(), "JSON words with image-pixel geometry and confidence."),
    "quality_flags": (
        pa.string(),
        "Semicolon-separated mechanical concerns; absence is not validation.",
    ),
    "review_status": (pa.string(), "Always OCR candidate, source validation pending."),
}


def token(word):
    return re.sub(r"[^a-z]", "", word.lower())


def lines_from_tsv(path):
    groups = defaultdict(list)
    with gzip.open(path, "rt") as stream:
        rows = list(csv.DictReader(stream, delimiter="\t", quoting=csv.QUOTE_NONE))
    for row in rows:
        if row["level"] != "5" or not row["text"].strip():
            continue
        word = {k: int(row[k]) for k in ["left", "top", "width", "height"]}
        word.update(text=row["text"], conf=float(row["conf"]))
        groups["/".join(row[k] for k in ["block_num", "par_num", "line_num"])].append(
            word
        )
    lines = [
        (key, sorted(words, key=lambda w: w["left"])) for key, words in groups.items()
    ]
    lines.sort(key=lambda pair: min(w["top"] for w in pair[1]))
    return lines, int(rows[0]["width"]), int(rows[0]["height"])


def find_header(words, width, gp):
    by_token = defaultdict(list)
    for word in words:
        by_token[token(word["text"])].append(word)

    def header_like(actual, expected):
        return SequenceMatcher(None, actual, expected).ratio() >= 0.72

    ward = [w for t, ws in by_token.items() if header_like(t, "ward") for w in ws]
    category = [
        w for t, ws in by_token.items() if header_like(t, "category") for w in ws
    ]
    father = [
        w for t, ws in by_token.items() if header_like(t[:6], "father") for w in ws
    ]
    name = [w for t, ws in by_token.items() if header_like(t, "name") for w in ws]
    office = by_token.get("office", [])
    if gp and not office:
        return None
    if not gp and office:
        return None
    family = (
        "gp_head_and_ward"
        if gp
        else (
            "district_member"
            if any(header_like(t, "district") for t in by_token)
            else "block_member"
            if any(header_like(t, "samiti") for t in by_token)
            else None
        )
    )
    if family is None:
        return None
    if not ward or not category or not father or not name or (gp and not office):
        return None
    wx = ward[0]["left"]
    fx = father[0]["left"]
    cx = category[-1]["left"]
    names = [w["left"] for w in name if wx < w["left"] < fx]
    if not names or not wx < min(names) < fx < cx:
        return None
    nx = min(names)
    ox = office[0]["left"] if gp else cx
    if gp and not fx < ox < cx:
        return None
    return {
        "table_family": family,
        "ward": wx / width - 0.03,
        "name": nx / width - 0.025,
        "relation": fx / width - 0.025,
        "office": ox / width - 0.025,
        "category": cx / width - 0.04,
    }


def candidate_category(raw):
    value = reservation(raw)
    if value != (None, None):
        return value
    exact = {"GENERALWOMAN": ("NONE", True), "GENERALWOMEN": ("NONE", True)}
    return exact.get(re.sub("[^A-Z]", "", raw.upper()), (None, None))


def parse_pages(source, pages, base):
    gp = source["family"] == "gp_head_and_ward"
    bounds = None
    body = ""
    body_page = None
    records, audit = [], []
    previous_page = 0
    for receipt in pages:
        if receipt["page"] != previous_page + 1:
            bounds, body, body_page = None, "", None
        previous_page = receipt["page"]
        path = base / "ocr" / receipt["output"]
        if checksum(path) != receipt["output_sha256"]:
            raise ValueError("OCR page hash mismatch")
        lines, width, _height = lines_from_tsv(path)
        page_rows = []
        headers = 0
        reference_office_x = None
        for index, (line_id, words) in enumerate(lines):
            nearby = [w for _, following in lines[index : index + 3] for w in following]
            header = find_header(nearby, width, gp)
            if header:
                bounds = header if header["table_family"] == source["family"] else None
                headers += 1
                continue
            if bounds is None:
                continue
            raw_line = " ".join(w["text"] for w in words)
            if re.search(
                r"Dated[, :]|State Election Commissioner|STATE ELECTION|NOTIFICATION",
                raw_line,
            ):
                bounds = None
                continue

            office_words = [
                w for w in words if token(w["text"]) in {"panch", "sarpanch"}
            ]
            shift = 0
            if gp and len(office_words) == 1:
                office_x = office_words[0]["left"] / width
                if reference_office_x is None:
                    reference_office_x = office_x
                shift = office_x - reference_office_x
                if abs(shift) > 0.05:
                    continue

            def cell(left, right):
                return " ".join(
                    w["text"]
                    for w in words
                    if left + shift <= w["left"] / width < right + shift
                ).strip()

            ward = cell(bounds["ward"], bounds["name"])
            name = cell(bounds["name"], bounds["relation"])
            relation = cell(bounds["relation"], bounds["office"])
            office = cell(bounds["office"], bounds["category"]) if gp else ""
            category = cell(bounds["category"], 1.0)
            unit = cell(0, bounds["ward"])
            unit = re.sub(r"^[\s\d*|.,]+", "", unit).strip()
            office_label = token(office)
            is_head = office_label == "sarpanch"
            is_ward = (
                office_label == "panch"
                if gp
                else bool(re.fullmatch(r"[0-9IlSi|]{1,2}\s*\*?", ward))
            )
            if not (is_head or is_ward):
                continue
            unit_has_name = len(re.findall(r"[A-Za-z]", unit)) >= 3
            if is_head:
                body = unit if unit_has_name else ""
                body_page = receipt["page"] if body else None
            elif unit_has_name and not re.search(r"District|Gram|Samiti|Sr\.", unit):
                body = unit
                body_page = receipt["page"]
            caste, woman = candidate_category(category)
            flags = []
            if not body and source["family"] != "district_member":
                flags.append("body_label_missing")
            if not re.fullmatch(r"[0-9]{1,2}\s*\*?", ward) and not is_head:
                flags.append("ward_unresolved")
            if caste is None:
                flags.append("category_unresolved")
            if not name:
                flags.append("name_missing")
            if any(w["conf"] < 50 for w in words):
                flags.append("low_word_confidence")
            page_rows.append(
                {
                    "source_sha256": source["sha256"],
                    "source_url": source["url"],
                    "source_path": source["source_path"],
                    "source_page": receipt["page"],
                    "ocr_sha256": receipt["output_sha256"],
                    "source_line": line_id,
                    "year_context": 2000,
                    "district_index": source["heading"] if gp else source["label"],
                    "block_index": source["label"] if gp else "",
                    "local_body_ocr": body,
                    "local_body_label_page": body_page,
                    "ward_raw": ward,
                    "office_raw": office,
                    "tier": ("gp_head" if is_head else "gp_ward")
                    if gp
                    else source["family"],
                    "winner_name_ocr": name,
                    "relation_name_ocr": relation,
                    "reservation_ocr": category,
                    "caste_candidate": caste,
                    "woman_candidate": woman,
                    "raw_line": raw_line,
                    "raw_words": json.dumps(words, ensure_ascii=False),
                    "quality_flags": ";".join(flags),
                    "review_status": "ocr_candidate; source_validation_pending",
                }
            )
        records.extend(page_rows)
        audit.append(
            {
                "source_sha256": source["sha256"],
                "source_page": receipt["page"],
                "header_detections": headers,
                "candidate_rows": len(page_rows),
                "status": "candidates_extracted"
                if page_rows
                else "no_supported_english_rows",
            }
        )
    return records, audit


def unique_sources(sources, reviews):
    """Keep byte-identical PDFs once, requiring review of conflicting index labels."""
    grouped = defaultdict(list)
    for source in sources:
        grouped[source["sha256"]].append(source)
    reviewed = {r["source_sha256"]: r for r in reviews}
    result, aliases = [], []
    for digest, group in grouped.items():
        identities = {(r["family"], r["heading"], r["label"]) for r in group}
        chosen = group[0]
        if len(identities) > 1:
            review = reviewed.get(digest)
            if not review:
                raise ValueError("Conflicting index identities need source review")
            matches = [
                r
                for r in group
                if r["url"] == review["canonical_url"]
                and r["heading"] == review["heading"]
            ]
            if len(matches) != 1:
                raise ValueError("Reviewed canonical index binding changed")
            chosen = matches[0]
        result.append(chosen)
        aliases.extend(
            {
                "source_sha256": digest,
                "url": r["url"],
                "heading": r["heading"],
                "label": r["label"],
                "canonical_url": chosen["url"],
                "is_canonical": r["url"] == chosen["url"],
            }
            for r in group
        )
    return result, aliases


@command("parse", state="Haryana", vintage="2000_gazettes")
def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=BASE)
    args = parser.parse_args()
    base = args.source
    with (base / "link_frame.csv").open() as stream:
        links = {r["url"]: r for r in csv.DictReader(stream)}
    with (base / "document_profiles.csv").open() as stream:
        sources = [r | links[r["url"]] for r in csv.DictReader(stream)]
    with (base / "index_reviews.csv").open() as stream:
        sources, aliases = unique_sources(sources, list(csv.DictReader(stream)))
    records, audit, pending = [], [], []
    for source in sources:
        folder = base / "ocr" / source["sha256"]
        pages = []
        for page in range(1, int(source["pages"]) + 1):
            receipt = folder / f"page_{page:04d}.tsv.json"
            if receipt.exists():
                pages.append(json.loads(receipt.read_text()))
            else:
                pending.append({"source_sha256": source["sha256"], "source_page": page})
        rows, checks = parse_pages(source, pages, base)
        records.extend(rows)
        audit.extend(checks)
    out = base / "parsed"
    out.mkdir(exist_ok=True)
    pd.DataFrame(aliases).to_csv(out / "source_aliases.csv", index=False)
    schema = pa.schema([(k, v[0]) for k, v in FIELDS.items()])
    table = pa.Table.from_pylist(records, schema=schema)
    pq.write_table(table, out / "candidate_rows.parquet")
    pd.DataFrame(audit).to_csv(out / "pages.csv", index=False)
    pd.DataFrame(pending, columns=["source_sha256", "source_page"]).to_csv(
        out / "pending_pages.csv", index=False
    )
    with (out / "data_dictionary.csv").open("w", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["column", "type", "definition"])
        writer.writerows((k, str(v[0]), v[1]) for k, v in FIELDS.items())
    (out / "schema.json").write_text(
        json.dumps({k: str(v[0]) for k, v in FIELDS.items()}, indent=2) + "\n"
    )
    frame = table.to_pandas()
    report = {
        "candidate_rows": len(records),
        "unique_documents": len(sources),
        "pages_processed": len(audit),
        "pages_pending_ocr": len(pending),
        "tier_rows": frame.tier.value_counts().to_dict(),
        "incomplete_categories": int(frame.caste_candidate.isna().sum()),
        "status": "Unvalidated English OCR candidates",
    }
    (out / "summary.json").write_text(json.dumps(report, indent=2) + "\n")
    inputs = [
        Path(__file__),
        base / "document_profiles.csv",
        base / "link_frame.csv",
        base / "index_reviews.csv",
    ]
    (out / "parse_inputs.json").write_text(
        json.dumps([{"path": str(p), "sha256": checksum(p)} for p in inputs], indent=2)
        + "\n"
    )
    print(json.dumps(report))


if __name__ == "__main__":
    main()
