"""Retain usable embedded text from Andhra Pradesh source PDFs."""

import argparse
import csv
import io
import json
import subprocess

from local_elections.common.runlog import command, get_logger
from local_elections.paths import ROOT

LOGGER = get_logger(__name__)
SOURCE = ROOT / "data" / "ap" / "2020_res_gp"
CACHE = ROOT / "data" / "ap" / "extracted"


def extract_pdf(path):
    """Return Poppler's layout-preserving text for one held PDF."""
    result = subprocess.run(
        ["pdftotext", "-layout", str(path), "-"],
        capture_output=True,
        check=True,
        text=True,
    )
    return result.stdout


def extract_word_pages(path):
    """Return page dimensions and positioned words from Poppler TSV."""
    result = subprocess.run(
        ["pdftotext", "-tsv", str(path), "-"],
        capture_output=True,
        check=True,
        text=True,
    )
    return parse_word_pages(result.stdout)


def parse_word_pages(tsv):
    """Parse Poppler TSV without treating quotation marks as CSV syntax."""
    pages = {}
    for row in csv.DictReader(io.StringIO(tsv), delimiter="\t", quoting=csv.QUOTE_NONE):
        page = int(row["page_num"])
        level = int(row["level"])
        if level == 1:
            pages[page] = {
                "page": page,
                "width": float(row["width"]),
                "height": float(row["height"]),
                "words": [],
            }
        elif level == 5 and row["text"].strip():
            pages[page]["words"].append(
                {
                    "left": float(row["left"]),
                    "top": float(row["top"]),
                    "width": float(row["width"]),
                    "height": float(row["height"]),
                    "text": row["text"],
                }
            )
    return [pages[page] for page in sorted(pages)]


@command("extract", state="Andhra Pradesh", method="embedded_text")
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--only", help="substring of a filename to limit to")
    args = parser.parse_args()

    CACHE.mkdir(parents=True, exist_ok=True)
    files = sorted(SOURCE.glob("*.pdf"))
    if args.only:
        files = [path for path in files if args.only in path.name]
    for path in files:
        target = CACHE / f"{path.stem}.txt"
        words_target = CACHE / f"{path.stem}.words.jsonl"
        if target.exists() and words_target.exists() and not args.refresh:
            LOGGER.info(
                "Embedded text already retained",
                extra={
                    "event": "extraction_cached",
                    "source_file": path.name,
                    "output_file": target.name,
                    "bytes": target.stat().st_size,
                },
            )
            continue
        text = extract_pdf(path)
        if not text.strip():
            LOGGER.warning(
                "Source has no embedded text",
                extra={
                    "event": "extraction_empty",
                    "source_file": path.name,
                },
            )
            continue
        pages = extract_word_pages(path)
        target.write_text(text, encoding="utf-8")
        with words_target.open("w", encoding="utf-8") as fh:
            for page in pages:
                fh.write(json.dumps(page, ensure_ascii=False) + "\n")
        LOGGER.info(
            "Embedded text retained",
            extra={
                "event": "extraction_completed",
                "source_file": path.name,
                "output_file": target.name,
                "pages": len(pages),
                "words": sum(len(page["words"]) for page in pages),
                "bytes": len(text.encode("utf-8")),
            },
        )


if __name__ == "__main__":
    main()
