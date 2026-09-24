"""Extract Assam's scanned 2025 PRI notifications into cached page HTML.

The source manifest chooses documents; no district rows or table values live
in this module. Surya returns page text and tables with cell boundaries intact.
Parsing is a separate stage and never opens a PDF or loads the OCR model.
"""

import argparse
import csv
import hashlib
import json
import os
import sys

from local_elections.common import ocr_engine
from local_elections.common.runlog import command, get_logger
from local_elections.paths import ROOT

LOGGER = get_logger(__name__)
SOURCE = ROOT / "data" / "assam" / "2025_reservation"
MANIFEST = SOURCE / "manifest.csv"
CACHE = ROOT / "data" / "assam" / "2025_ocr"
MODEL = os.environ.get("SURYA_MLX_PATH")
OCR_DPI = 300


def manifest_documents():
    """Return checksummed source metadata from the acquisition manifest."""
    with MANIFEST.open(encoding="utf-8", newline="") as handle:
        records = list(csv.DictReader(handle))
    documents = []
    for record in records:
        path = SOURCE / record["file"]
        if not path.exists():
            raise RuntimeError(f"missing Assam source: {path}")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != record["sha256"]:
            raise RuntimeError(
                f"Assam source changed: {path.name}; "
                f"expected {record['sha256']}, found {digest}"
            )
        documents.append((record, path))
    return documents


def select_documents(documents, district=None, all_documents=False):
    """Select one district or the complete held series."""
    if all_documents:
        return documents
    district = (district or "").strip()
    if not district:
        raise ValueError("pass --district NAME or --all")
    selected = [item for item in documents if item[0]["district"] == district]
    if not selected:
        choices = ", ".join(sorted(record["district"] for record, _ in documents))
        raise ValueError(f"unknown district {district!r}; choose one of: {choices}")
    return selected


def seed_pages(target, partial, retry_pages):
    """Reuse every cached page except a caller-selected retry set."""
    if not target.exists():
        return []
    pages = target.read_text(encoding="utf-8").split("\f")
    retry_pages = sorted(set(retry_pages))
    invalid = [page for page in retry_pages if page < 1 or page > len(pages)]
    if invalid:
        raise ValueError(f"page numbers outside 1..{len(pages)}: {invalid}")
    if not retry_pages:
        return []
    partial.parent.mkdir(parents=True, exist_ok=True)
    with partial.open("w", encoding="utf-8") as handle:
        for number, text in enumerate(pages, start=1):
            if number not in retry_pages:
                handle.write(json.dumps({"page": number, "text": text}) + "\n")
    return retry_pages


def seed_repair(target, partial):
    """Reuse readable cached pages and return the pages that need another run."""
    if not target.exists():
        return []
    pages = target.read_text(encoding="utf-8").split("\f")
    unread = [
        number
        for number, text in enumerate(pages, start=1)
        if "<!-- ocr-unread " in text
    ]
    return seed_pages(target, partial, unread)


@command("extract", state="Assam", source_id="assam_sec_pri_reservation_2025")
def main():
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument("--district")
    selection.add_argument("--all", action="store_true", dest="all_documents")
    parser.add_argument("--force", action="store_true", help="ignore completed caches")
    parser.add_argument(
        "--repair",
        action="store_true",
        help="reuse readable cached pages and retry only pages marked unread",
    )
    parser.add_argument(
        "--page",
        action="append",
        type=int,
        default=[],
        help="retry one page while retaining the rest; may be repeated",
    )
    parser.add_argument("--dpi", type=int, default=OCR_DPI)
    args = parser.parse_args()

    try:
        documents = select_documents(
            manifest_documents(), args.district, args.all_documents
        )
    except ValueError as exc:
        parser.error(str(exc))

    CACHE.mkdir(parents=True, exist_ok=True)
    done = skipped = 0
    for record, path in documents:
        target = CACHE / f"{path.stem}.html"
        partial = CACHE / ".partial" / f"{path.stem}.jsonl"
        repair_pages = (
            seed_pages(target, partial, args.page)
            if args.page
            else seed_repair(target, partial)
            if args.repair
            else []
        )
        if target.exists() and not args.force and not repair_pages:
            skipped += 1
            continue
        text = ocr_engine.ocr(
            path,
            model=MODEL,
            dpi=args.dpi,
            deskew=False,
            partial=partial,
        )
        target.write_text(text, encoding="utf-8")
        partial.unlink(missing_ok=True)
        done += 1
        LOGGER.info(
            "Assam scan extracted",
            extra={
                "event": "source_extraction_written",
                "district": record["district"],
                "source_path": str(path.relative_to(ROOT)),
                "pages": len(text.split("\f")),
                "repair_pages": repair_pages,
                "output_path": str(target.relative_to(ROOT)),
            },
        )

    print(f"{done} read, {skipped} already cached -> {CACHE.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
