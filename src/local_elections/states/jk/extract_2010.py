"""Extract J&K's 2010 digital tables without interpreting their contents.

The source PDFs are already held in ``data/jk/2010``.  This command records
what pdfplumber sees on every page as JSONL: the page text and every table cell,
including blank cells, punctuation, and repeated headers.  The parser consumes
that cache and never opens a PDF, keeping document extraction separate from
the decisions that turn a printed row into a seat.

Writes ``data/jk/2010_extracted/pages.jsonl``.  One record is one PDF page.
"""

import hashlib
import json
from pathlib import Path

import pdfplumber

from local_elections.common.runlog import command, get_logger
from local_elections.paths import ROOT

LOGGER = get_logger(__name__)

SOURCE_DIR = ROOT / "data" / "jk" / "2010"
OUT_DIR = ROOT / "data" / "jk" / "2010_extracted"
OUT = OUT_DIR / "pages.jsonl"
SCHEMA_VERSION = 1


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def page_records(paths=None):
    """Yield source-faithful page records for the selected PDFs."""
    paths = sorted(paths or SOURCE_DIR.glob("*.pdf"))
    for path in paths:
        digest = sha256(path)
        page_count = 0
        table_count = 0
        with pdfplumber.open(str(path)) as document:
            for page in document.pages:
                tables = [table.extract() for table in page.find_tables()]
                page_count += 1
                table_count += len(tables)
                yield {
                    "schema_version": SCHEMA_VERSION,
                    "source_path": str(path.relative_to(ROOT)),
                    "source_pdf": path.name,
                    "source_sha256": digest,
                    "source_page": page.page_number,
                    "page_text": page.extract_text() or "",
                    "tables": tables,
                }
        LOGGER.info(
            "Source extracted",
            extra={
                "event": "source_extracted",
                "source_file": path.name,
                "source_sha256": digest,
                "pages": page_count,
                "tables": table_count,
            },
        )


def write(records, path=OUT):
    """Write page records atomically and return their count."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    count = 0
    with temporary.open("w", encoding="utf-8") as destination:
        for record in records:
            destination.write(json.dumps(record, ensure_ascii=False) + "\n")
            count += 1
    temporary.replace(path)
    return count


def load(path=OUT):
    """Load extracted page records, rejecting an unknown cache schema."""
    path = Path(path)
    if not path.exists():
        raise RuntimeError(f"missing extraction {path}; run make jk-2010-extract")
    records = []
    with path.open(encoding="utf-8") as source:
        for line_number, line in enumerate(source, 1):
            record = json.loads(line)
            if record.get("schema_version") != SCHEMA_VERSION:
                raise RuntimeError(
                    f"unsupported extraction schema on line {line_number}: "
                    f"{record.get('schema_version')}"
                )
            records.append(record)
    return records


def validate(records):
    """Check that the cache represents every held PDF and every page once."""
    paths = sorted(SOURCE_DIR.glob("*.pdf"))
    expected_files = {path.name for path in paths}
    found_files = {record["source_pdf"] for record in records}
    if found_files != expected_files:
        missing = sorted(expected_files - found_files)
        extra = sorted(found_files - expected_files)
        raise RuntimeError(
            f"extraction file mismatch: missing={missing}, extra={extra}"
        )

    by_file = {}
    for record in records:
        by_file.setdefault(record["source_pdf"], []).append(record)
    for path in paths:
        with pdfplumber.open(str(path)) as document:
            expected_pages = len(document.pages)
        pages = sorted(record["source_page"] for record in by_file[path.name])
        if pages != list(range(1, expected_pages + 1)):
            raise RuntimeError(
                f"non-contiguous extraction for {path.name}: "
                f"expected 1..{expected_pages}, found {pages}"
            )
        expected_digest = sha256(path)
        digests = {record["source_sha256"] for record in by_file[path.name]}
        if digests != {expected_digest}:
            raise RuntimeError(f"source bytes changed for {path.name}")


@command("extract", state="Jammu and Kashmir", year=2010, method="pdfplumber")
def main():
    records = list(page_records())
    validate(records)
    count = write(records)
    tables = sum(len(record["tables"]) for record in records)
    print(
        f"2010: {len({record['source_pdf'] for record in records})} PDFs, "
        f"{count} pages, {tables} tables -> {OUT.relative_to(ROOT)}"
    )


if __name__ == "__main__":
    main()
