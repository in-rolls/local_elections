"""Classify the source documents already sitting in data/.

The repo holds roughly 2 GB of PDFs for states the readme still lists as empty,
so for many of them acquisition is already done and the open question is whether
the files can be parsed at all.

That question has one decisive answer: whether a PDF carries a text layer or is
an image. The Haryana build turned entirely on this - its notifications were
digitally generated text, which is why no OCR was needed. Almost everything else
published by Indian states is a scan.

Writes data/inventory.csv, one row per document.
"""

import argparse
import collections
import csv
import re
import subprocess

from local_elections.common.runlog import command, get_logger
from local_elections.paths import ROOT

DATA = ROOT / "data"
LOGGER = get_logger(__name__)

# chars of extractable text per page, above which a PDF has a real text layer.
# Scanned pages yield 0-2 (sometimes a stray "CamScanner" watermark).
TEXT_THRESHOLD = 800

COLUMNS = [
    "state",
    "path",
    "kind",
    "pages",
    "producer",
    "chars_per_page",
    "format",
    "bytes",
]


def reviewed_formats():
    """Document formats explicitly reviewed in standard source manifests."""
    found = {}
    for manifest in DATA.rglob("manifest.csv"):
        with manifest.open(encoding="utf-8", errors="replace") as fh:
            reader = csv.DictReader(fh)
            if not reader.fieldnames or "document_format" not in reader.fieldnames:
                continue
            for row in reader:
                if not row.get("file") or not row.get("document_format"):
                    continue
                path = manifest.parent / row["file"]
                found[path] = row["document_format"]
    return found


def pdf_facts(path):
    """(pages, producer) from pdfinfo, or (0, '') if it cannot be read."""
    try:
        out = subprocess.run(
            ["pdfinfo", str(path)], capture_output=True, text=True, timeout=60
        ).stdout
    except (subprocess.SubprocessError, OSError):
        return 0, "unreadable"
    pages = re.search(r"^Pages:\s+(\d+)", out, re.M)
    producer = re.search(r"^Producer:\s*(.*)$", out, re.M)
    return (
        int(pages.group(1)) if pages else 0,
        (producer.group(1).strip() if producer else "") or "(none)",
    )


def pdf_text_density(path, pages):
    """Characters of extractable text per page, sampled from the first pages."""
    sample = min(pages, 5) or 1
    try:
        text = subprocess.run(
            ["pdftotext", "-layout", "-f", "1", "-l", str(sample), str(path), "-"],
            capture_output=True,
            text=True,
            timeout=120,
        ).stdout
    except (subprocess.SubprocessError, OSError):
        return 0
    return int(len(text) / sample)


def classify(path):
    suffix = path.suffix.lower()
    size = path.stat().st_size
    if suffix != ".pdf":
        kind = {
            ".csv": "tabular",
            ".xlsx": "tabular",
            ".xls": "tabular",
            ".dta": "tabular",
            ".zip": "archive",
            ".docx": "doc",
        }.get(suffix, "other")
        return {
            "kind": kind,
            "pages": "",
            "producer": "",
            "chars_per_page": "",
            "format": "tabular" if kind == "tabular" else kind,
            "bytes": size,
        }

    pages, producer = pdf_facts(path)
    density = pdf_text_density(path, pages) if pages else 0
    if producer == "unreadable":
        fmt = "unreadable"
    elif density >= TEXT_THRESHOLD:
        fmt = "digital-text"
    elif density > 50:
        fmt = "mixed"  # a text layer exists but is thin - partial OCR or cover pages  # noqa: E501
    else:
        fmt = "scan"
    return {
        "kind": "pdf",
        "pages": pages,
        "producer": producer,
        "chars_per_page": density,
        "format": fmt,
        "bytes": size,
    }


@command("inventory", artifact="source_documents")
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--state", help="limit to one state directory")
    ap.add_argument("--out", default=str(DATA / "inventory.csv"))
    args = ap.parse_args()

    states = (
        [DATA / args.state]
        if args.state
        else sorted(p for p in DATA.iterdir() if p.is_dir())
    )
    formats = reviewed_formats()

    rows = []
    for state_dir in states:
        files = [
            p
            for p in sorted(state_dir.rglob("*"))
            if p.is_file() and p.name != ".DS_Store"
        ]
        for path in files:
            row = {"state": state_dir.name, "path": str(path.relative_to(DATA))}
            row.update(classify(path))
            if path in formats:
                row["format"] = formats[path]
            rows.append(row)
        LOGGER.info(
            "state inventory completed",
            extra={
                "event": "inventory_state_completed",
                "state_directory": state_dir.name,
                "documents": len(files),
            },
        )

    with open(args.out, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=COLUMNS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    print(f"wrote {args.out} ({len(rows)} documents)\n")

    print(
        f"{'state':16s} {'docs':>5s} {'text':>5s} {'scan':>5s} "
        f"{'encoded':>7s} {'mixed':>5s} {'tabular':>7s} {'pages':>7s}"
    )
    print("-" * 69)
    for state in dict.fromkeys(r["state"] for r in rows):
        sub = [r for r in rows if r["state"] == state]
        count = collections.Counter(r["format"] for r in sub)
        pages = sum(int(r["pages"]) for r in sub if str(r["pages"]).isdigit())
        print(
            f"{state:16s} {len(sub):5d} {count['digital-text']:5d} "
            f"{count['scan']:5d} {count['encoded-text']:7d} "
            f"{count['mixed']:5d} {count['tabular']:7d} {pages:7d}"
        )


if __name__ == "__main__":
    main()
