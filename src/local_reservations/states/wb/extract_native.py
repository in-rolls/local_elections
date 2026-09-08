"""Preserve native text and ruled tables from every acquired GP-source PDF.

This is a document extraction layer, not semantic election data. Embedded OCR
may be wrong even when text is nonempty. Every page, including empty pages,
gets an explicit record; byte-identical PDFs share an extraction cache.
"""

import argparse
import hashlib
import json
import os
import re
import subprocess
from concurrent.futures import ProcessPoolExecutor

import pdfplumber

from local_reservations.common.runlog import command
from local_reservations.paths import ROOT

OUT = ROOT / "data/wb/derived/native"
VERSION = 1


def extract(path):
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    cache = OUT / (digest + ".json")
    if cache.exists():
        record = json.loads(cache.read_text())
        if record["version"] != VERSION:
            raise ValueError("Stale native extraction cache")
    else:
        pages = []
        with pdfplumber.open(path) as pdf:
            for number, page in enumerate(pdf.pages, 1):
                tables = [
                    {"bbox": table.bbox, "rows": table.extract()}
                    for table in page.find_tables()
                ]
                pages.append(
                    {
                        "page": number,
                        "width": page.width,
                        "height": page.height,
                        "text": page.extract_text() or "",
                        "tables": tables,
                        "images": len(page.images),
                        "characters": len(page.chars),
                    }
                )
        record = {
            "version": VERSION,
            "sha256": digest,
            "pdfplumber_version": pdfplumber.__version__,
            "pages": pages,
        }
    info = subprocess.check_output(["pdfinfo", str(path)], text=True)
    expected = int(re.search(r"Pages:\s*(\d+)", info)[1])
    if len(record["pages"]) != expected:
        poppler = subprocess.check_output(
            ["pdftotext", "-layout", str(path), "-"], text=True
        )
        pieces = poppler.split("\f")
        if pieces[-1].strip() == "":
            pieces.pop()
        if len(pieces) != expected:
            raise ValueError(f"Both native readers failed page coverage: {path}")
        record["pdfplumber_pages"] = len(record["pages"])
        record["reader_status"] = "pdfplumber_page_count_mismatch_poppler_fallback"
        record["pages"] = [
            {
                "page": i,
                "width": None,
                "height": None,
                "text": s,
                "tables": [],
                "images": None,
                "characters": None,
            }
            for i, s in enumerate(pieces, 1)
        ]
    record.setdefault("reader_status", "pdfplumber_page_count_reconciled")
    record["expected_pages"] = expected
    OUT.mkdir(parents=True, exist_ok=True)
    temporary = cache.with_suffix(f".{os.getpid()}.tmp")
    temporary.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n")
    temporary.replace(cache)
    return {
        "source_path": str(path.relative_to(ROOT)),
        "sha256": digest,
        "cache": str(cache.relative_to(ROOT)),
        "pages": len(record["pages"]),
        "reader_status": record["reader_status"],
        "pages_with_text": sum(bool(p["text"].strip()) for p in record["pages"]),
        "tables": sum(len(p["tables"]) for p in record["pages"]),
    }


@command("extract", state="West Bengal", method="native_pdf")
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--match", default="")
    ap.add_argument("--workers", type=int, default=2)
    args = ap.parse_args()
    files = sorted(
        {
            p
            for directory in ["data/wb/2023", "data/wb/gp_source_search"]
            for p in (ROOT / directory).rglob("*")
            if p.suffix.lower() == ".pdf" and args.match in str(p)
        }
    )
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        rows = list(pool.map(extract, files))
    OUT.mkdir(parents=True, exist_ok=True)
    index = OUT / ("index.json" if not args.match else "index_filtered.json")
    index.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps(
            {
                "files": len(rows),
                "pages": sum(r["pages"] for r in rows),
                "tables": sum(r["tables"] for r in rows),
            }
        )
    )


if __name__ == "__main__":
    main()
