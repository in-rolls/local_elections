"""Reconcile every acquired WB PDF page with extraction and parser evidence.

Counts here are files, pages, and explicitly labelled output rows; none are
silently interpreted as unique GPs or as evidence of randomized assignment.
"""

import csv
import hashlib
import json
from collections import Counter, defaultdict

import pyarrow.parquet as pq

from local_elections.common.runlog import command
from local_elections.paths import ROOT
from local_elections.states.wb.parse_results import write_table

BASE = ROOT / "data/wb/derived"
OUT = BASE / "parsing_inventory"


def read(path):
    if not path.exists():
        return []
    if path.suffix == ".csv":
        with path.open() as handle:
            return list(csv.DictReader(handle))
    return json.loads(path.read_text())


def collect_audits():
    audits = defaultdict(list)
    for name, filename in [
        ("nadia_2008", "page_audit.json"),
        ("alipurduar_2018", "page_audit.json"),
        ("alipurduar_offices", "page_audit.json"),
        ("ward_schedules", "page_audit.json"),
        ("office_native", "page_audit.csv"),
        ("office_scans", "page_review.csv"),
        ("ancillary", "page_audit.json"),
        ("nadia_2013_handbook", "page_audit.json"),
        ("reference_tables", "page_audit.json"),
        ("base_drafts", "page_audit.json"),
    ]:
        for row in read(BASE / name / filename):
            sha = row.get("source_sha256") or row.get("sha256")
            page = row.get("source_page") or row.get("page")
            if sha and page:
                audits[(sha, int(page))].append(
                    {
                        "parser": name,
                        "status": row.get("status") or row.get("review_status"),
                        "audit": str((BASE / name / filename).relative_to(ROOT)),
                        "ocr_path": row.get("ocr_path"),
                        "ocr_sha256": row.get("ocr_sha256"),
                    }
                )
    return audits


def build_inventory(sources, native, audits, base_sources, reference_sources=()):
    """Deduplicate both acquired collections by PDF hash without inventing text."""
    metadata = {"data/wb/" + r["file"]: r for r in sources}
    documents = {}
    scopes = defaultdict(set)
    for entry in native:
        documents.setdefault(entry["sha256"], []).append(entry)
        scopes[entry["sha256"]].add("gp_source_search")
    for entry in base_sources:
        sha = entry["source_sha256"]
        documents.setdefault(sha, []).append(
            {
                "sha256": sha,
                "source_path": entry["source_path"],
                "pages": int(entry["pages"]),
            }
        )
        scopes[sha].add("base_2018_gazettes")
        metadata[entry["source_path"]] = {
            "district": entry["district"],
            "stage": entry["stage"],
            "election_year": 2018,
            "content_kind": "zp_member_reservation_gazette",
        }
    for entry in reference_sources:
        sha = entry["source_sha256"]
        documents.setdefault(sha, []).append(
            {
                "sha256": sha,
                "source_path": entry["source_path"],
                "pages": int(entry["expected_pages"]),
                "cache": entry["native_cache"],
            }
        )
        scopes[sha].add("search_references")
        metadata[entry["source_path"]] = {
            "content_kind": entry["reference_kind"],
            "document_reference_year": entry["document_reference_year"],
        }
    pages, file_rows = [], []
    for sha, aliases in sorted(documents.items()):
        entry = aliases[0]
        source = next(
            (
                metadata[a["source_path"]]
                for a in aliases
                if a["source_path"] in metadata
            ),
            {},
        )
        cached = next((alias for alias in aliases if alias.get("cache")), None)
        document = (read(ROOT / cached["cache"]) or {}) if cached else {}
        extracted = {p["page"]: p for p in document.get("pages", [])}
        expected = max(
            int(document.get("expected_pages") or 0),
            max(int(alias.get("pages") or 0) for alias in aliases),
            len(extracted),
        )
        inventory_scopes = ";".join(sorted(scopes[sha]))
        election_year = source.get("election_year")
        election_year = str(election_year) if election_year not in (None, "") else None
        for page in range(1, expected + 1):
            key = (sha, page)
            native_page = extracted.get(page, {})
            evidence = audits.get(key, [])
            cache = BASE / "ward_schedules/ocr" / sha / f"{page:04d}.json"
            if cache.exists():
                ocr = read(cache)
                # Extraction can run ahead of the last semantic-parser refresh.
                ocr_state = (
                    "ocr_cache_exists"
                    if not ocr.get("error")
                    else "ocr_cache_reports_error"
                )
            else:
                ocr_state = None
            pages.append(
                {
                    "source_sha256": sha,
                    "source_page": page,
                    "source_path": entry["source_path"],
                    "district": source.get("district"),
                    "election_year": election_year,
                    "document_reference_year": source.get("document_reference_year"),
                    "content_kind": source.get("content_kind"),
                    "stage": source.get("stage"),
                    "inventory_scopes": inventory_scopes,
                    "native_page_extracted": page in extracted,
                    "native_text_characters": len(native_page.get("text") or ""),
                    "native_tables": len(native_page.get("tables") or []),
                    "parsers": ";".join(sorted({e["parser"] for e in evidence})),
                    "parser_evidence": json.dumps(evidence),
                    "ward_ocr_state": ocr_state,
                    "base_ocr_state": "ocr_cache_evidence"
                    if any(
                        item["parser"] == "base_drafts" and item.get("ocr_sha256")
                        for item in evidence
                    )
                    else None,
                    "routing_status": "parser_audited"
                    if evidence
                    else "native_extraction_only_requires_triage",
                }
            )
        file_rows.append(
            {
                "source_sha256": sha,
                "source_path": entry["source_path"],
                "aliases": json.dumps(sorted({a["source_path"] for a in aliases})),
                "district": source.get("district"),
                "election_year": election_year,
                "document_reference_year": source.get("document_reference_year"),
                "content_kind": source.get("content_kind"),
                "stage": source.get("stage"),
                "inventory_scopes": inventory_scopes,
                "expected_pages": expected,
                "native_pages_extracted": len(extracted),
                "pages_with_parser_audit": sum(
                    bool(audits.get((sha, p))) for p in range(1, expected + 1)
                ),
            }
        )
    return pages, file_rows


def raw_pdf_coverage(documents):
    known = {row["source_sha256"] for row in documents}
    files = [
        path
        for path in (ROOT / "data/wb").rglob("*")
        if path.is_file() and path.suffix.lower() == ".pdf"
    ]
    hashes = {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in files}
    return {
        "physical_pdf_paths_on_disk": len(files),
        "unique_pdf_hashes_on_disk": len(set(hashes.values())),
        "unindexed_pdf_paths": [
            str(path.relative_to(ROOT))
            for path, sha in hashes.items()
            if sha not in known
        ],
        "indexed_hashes_absent_from_disk": sorted(known - set(hashes.values())),
    }


@command("validate", state="West Bengal", source="all_wb_pdf_inventory")
def main():
    sources = read(ROOT / "data/wb/gp_source_search/manual_entry_index.csv")
    native = read(BASE / "native/index.json")
    base_sources = read(BASE / "base_drafts/sources.csv")
    reference_sources = read(BASE / "reference_tables/additional_sources.json")
    pages, file_rows = build_inventory(
        sources, native, collect_audits(), base_sources, reference_sources
    )
    outputs = []
    for path in sorted(BASE.glob("*/*.parquet")):
        if path.parent == OUT:
            continue
        table = pq.read_table(path)
        outputs.append(
            {
                "output": str(path.relative_to(ROOT)),
                "rows": table.num_rows,
                "columns": table.num_columns,
                "unit": (
                    "candidate"
                    if "candidates" in path.stem
                    else "seat_or_seat_reading"
                    if path.stem.endswith("seats")
                    else "positive_office_mention"
                    if path.stem == "mentions"
                    else "source_office_row"
                    if path.stem == "office_reservations"
                    else "see_output_schema"
                ),
                "schema": str(table.schema),
                "review_status_counts": json.dumps(
                    Counter(table["review_status"].to_pylist())
                )
                if "review_status" in table.column_names
                else None,
            }
        )
    OUT.mkdir(parents=True, exist_ok=True)
    write_table(pages, OUT / "pages")
    write_table(file_rows, OUT / "documents")
    write_table(outputs, OUT / "outputs")
    semantic = read(BASE / "ward_schedules/semantic_backlog.json")
    summary = {
        "manual_index_physical_entries": len(sources),
        "manual_index_unique_hashes": len({r["sha256"] for r in sources}),
        "native_index_physical_pdfs": len(native),
        "unique_pdfs": len(file_rows),
        "unique_pdf_pages": len(pages),
        "scope_counts": {
            scope: {
                "unique_pdfs": sum(
                    scope in row["inventory_scopes"].split(";") for row in file_rows
                ),
                "unique_pages": sum(
                    scope in row["inventory_scopes"].split(";") for row in pages
                ),
            }
            for scope in ("gp_source_search", "base_2018_gazettes", "search_references")
        },
        "pages_with_parser_audit": sum(
            r["routing_status"] == "parser_audited" for r in pages
        ),
        "pages_native_only": sum(
            r["routing_status"] != "parser_audited" for r in pages
        ),
        "ward_ocr_cached_pages": sum(
            r["ward_ocr_state"] == "ocr_cache_exists" for r in pages
        ),
        "ward_semantic_coverage": {
            key: semantic[key]
            for key in (
                "ocr_pages",
                "coverage",
                "pages_with_any_reservation_field",
                "raw_only_distinct_documents",
                "page_ledger",
                "quality_claim",
            )
            if key in semantic
        }
        if semantic
        else None,
        "base_ocr_evidence_pages": sum(bool(row["base_ocr_state"]) for row in pages),
        "raw_pdf_coverage": raw_pdf_coverage(file_rows),
        "note": (
            "A parser audit can still report pending OCR, unresolved cells, or "
            "reference-only material. Consult per-page evidence. "
            "Row counts are not unique GP counts."
        ),
    }
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary))


if __name__ == "__main__":
    main()
