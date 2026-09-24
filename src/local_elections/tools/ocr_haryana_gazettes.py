"""Cache page OCR for the held Haryana 2000 gazettes without interpreting records.

Outputs under early_cycles/ocr retain Tesseract words, geometry and confidence.
A checksum-verified page receipt makes interrupted work resumable; recognition
success is a processing status, never a claim of transcription accuracy.
"""

import argparse
import csv
import gzip
import io
import json
import os
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from local_elections.common.runlog import command
from local_elections.paths import ROOT
from local_elections.tools.historical_harvest import checksum

BASE = ROOT / "data/source_search/national/haryana/early_cycles"


def read_page(source, page, out, settings):
    folder = out / source["sha256"]
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / f"page_{page:04d}.tsv.gz"
    receipt_path = target.with_suffix(".json")
    expected = {"source_sha256": source["sha256"], "page": page, **settings}
    if receipt_path.exists() and target.exists():
        receipt = json.loads(receipt_path.read_text())
        raw_settings = {k: v for k, v in expected.items() if k != "code_sha256"}
        if (
            all(receipt.get(k) == v for k, v in raw_settings.items())
            and checksum(target) == receipt["output_sha256"]
        ):
            with gzip.open(target, "rt") as stream:
                rows = csv.DictReader(stream, delimiter="\t", quoting=csv.QUOTE_NONE)
                receipt["words"] = sum(r["level"] == "5" for r in rows)
            receipt["receipt_parser_sha256"] = settings["code_sha256"]
            pending = receipt_path.with_suffix(".tmp")
            pending.write_text(json.dumps(receipt, indent=2) + "\n")
            pending.replace(receipt_path)
            return receipt
    with tempfile.TemporaryDirectory(prefix="haryana-ocr-") as temporary:
        prefix = Path(temporary).resolve() / "page"
        subprocess.run(
            [
                "pdftoppm",
                "-f",
                str(page),
                "-l",
                str(page),
                "-singlefile",
                "-scale-to",
                str(settings["scale_to"]),
                "-gray",
                "-png",
                source["path"],
                str(prefix),
            ],
            check=True,
            capture_output=True,
            timeout=120,
        )
        result = subprocess.run(
            [
                "tesseract",
                str(prefix.with_suffix(".png")),
                "stdout",
                "-l",
                settings["language"],
                "--psm",
                str(settings["psm"]),
                "tsv",
            ],
            check=True,
            capture_output=True,
            timeout=120,
            env=os.environ | {"OMP_THREAD_LIMIT": "1"},
        )
    rows = list(
        csv.DictReader(
            io.StringIO(result.stdout.decode()), delimiter="\t", quoting=csv.QUOTE_NONE
        )
    )
    if not rows or rows[0]["level"] != "1":
        raise ValueError("Tesseract did not return page geometry")
    payload = gzip.compress(result.stdout, mtime=0)
    pending = target.with_suffix(".tmp")
    pending.write_bytes(payload)
    pending.replace(target)
    receipt = expected | {
        "status": "ocr_complete_unvalidated",
        "output": str(target.relative_to(out)),
        "output_sha256": checksum(target),
        "words": sum(r["level"] == "5" for r in rows),
        "width": int(rows[0]["width"]),
        "height": int(rows[0]["height"]),
        "stderr": result.stderr.decode(),
    }
    pending = receipt_path.with_suffix(".tmp")
    pending.write_text(json.dumps(receipt, indent=2) + "\n")
    pending.replace(receipt_path)
    return receipt


@command("ocr", state="Haryana", vintage="2000")
def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=BASE)
    parser.add_argument("--workers", type=int, choices=range(1, 9), default=4)
    parser.add_argument("--limit", type=int)
    parser.add_argument(
        "--family", choices=["district_member", "block_member", "gp_head_and_ward"]
    )
    args = parser.parse_args()
    out = args.source / "ocr"
    out.mkdir(exist_ok=True)
    with (args.source / "document_profiles.csv").open() as stream:
        sources = list(csv.DictReader(stream))
    with (args.source / "link_frame.csv").open() as stream:
        families = {r["url"]: r["family"] for r in csv.DictReader(stream)}
    sources.sort(
        key=lambda r: (
            {"district_member": 0, "block_member": 1, "gp_head_and_ward": 2}[
                families[r["url"]]
            ],
            r["url"],
        )
    )
    settings = {
        "scale_to": 3000,
        "language": "eng",
        "psm": 6,
        "tesseract_version": subprocess.check_output(
            ["tesseract", "--version"], text=True
        ).splitlines()[0],
        "code_sha256": checksum(Path(__file__)),
    }
    jobs = []
    seen = set()
    for source in sources:
        if args.family and families[source["url"]] != args.family:
            continue
        source["path"] = str((args.source / source["source_path"]).resolve())
        if checksum(Path(source["path"])) != source["sha256"]:
            raise ValueError(f"Changed source: {source['source_path']}")
        if source["sha256"] in seen:
            continue
        seen.add(source["sha256"])
        jobs.extend((source, page) for page in range(1, int(source["pages"]) + 1))
    if args.limit:
        jobs = jobs[: args.limit]
    results = []
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {
            executor.submit(read_page, s, p, out, settings): (s, p) for s, p in jobs
        }
        for future in as_completed(futures):
            source, page = futures[future]
            try:
                receipt = future.result()
            except (subprocess.SubprocessError, OSError, ValueError) as error:
                receipt = {
                    "source_sha256": source["sha256"],
                    "page": page,
                    "status": "failed",
                    "error": str(error),
                }
            results.append(receipt)
            if len(results) % 25 == 0 or receipt["status"] == "failed":
                print(
                    json.dumps(
                        {
                            "completed": len(results),
                            "total": len(jobs),
                            "last": receipt["status"],
                        }
                    ),
                    flush=True,
                )
    results.sort(key=lambda r: (r["source_sha256"], r["page"]))
    (out / "run_receipts.json").write_text(json.dumps(results, indent=2) + "\n")
    report = {
        "requested_pages": len(jobs),
        "completed_pages": sum(r["status"] != "failed" for r in results),
        "failed_pages": [r for r in results if r["status"] == "failed"],
        "settings": settings,
    }
    (out / "summary.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report))
    if report["failed_pages"]:
        raise RuntimeError("Some pages failed; rerun to retry")


if __name__ == "__main__":
    main()
