"""Obtain resumable local vision readings of Haryana 2000 ZP-member gazettes.

This stage reads the already held district-member PDFs using a cached local
Ollama model. Responses are source-pinned evidence, not validated master rows.
It does not call a hosted model, infer unreadable ward numbers, or read GP/PS
sections appended to district-member files.
"""

import argparse
import base64
import csv
import json
import subprocess
import tempfile
import time
from pathlib import Path

import requests

from local_reservations.common.runlog import command
from local_reservations.paths import ROOT
from local_reservations.tools.historical_harvest import checksum

BASE = ROOT / "data/source_search/national/haryana/early_cycles"
PROMPT = (
    "Transcribe the English Zila Parishad member table in this gazette image. "
    "Ignore Hindi tables and any Panchayat Samiti or Gram Panchayat tables. "
    "Return JSON with a rows array. Each row has ward_raw and category_raw, "
    "containing only the text visibly printed in those two columns. Include "
    "every printed row. Do not infer missing ward numbers from a sequence. "
    "Do not infer category from a name. Use null for an unreadable or blank "
    "cell. Preserve abbreviations and Woman markers. No explanations."
)
OPTIONS = {"temperature": 0, "num_predict": 3000, "num_ctx": 16384}


def validate_response(payload):
    if not payload.get("done") or payload.get("done_reason") != "stop":
        raise ValueError("Model response did not finish normally")
    result = json.loads(payload["response"])
    if not isinstance(result, dict) or not isinstance(result.get("rows"), list):
        raise ValueError("Missing rows array")
    for row in result["rows"]:
        if not isinstance(row, dict) or set(row) != {"ward_raw", "category_raw"}:
            raise ValueError("Unexpected row schema")
        if any(
            value is not None and not isinstance(value, str) for value in row.values()
        ):
            raise ValueError("Raw cells must be text or null")
    return result["rows"]


@command("ocr", state="Haryana", vintage="2000_zp_local_vision")
def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=BASE)
    parser.add_argument("--model", default="qwen2.5vl:7b")
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()
    base = args.source
    out = base / "vision_members"
    out.mkdir(exist_ok=True)
    session = requests.Session()
    session.trust_env = False
    url = "http://127.0.0.1:11434"
    response = session.get(url + "/api/tags", timeout=20)
    response.raise_for_status()
    model = next(r for r in response.json()["models"] if r["name"] == args.model)
    with (base / "link_frame.csv").open() as stream:
        links = {r["url"]: r for r in csv.DictReader(stream)}
    with (base / "document_profiles.csv").open() as stream:
        sources = [
            r | links[r["url"]]
            for r in csv.DictReader(stream)
            if links[r["url"]]["family"] == "district_member"
        ]
    jobs = []
    seen = set()
    for source in sources:
        path = base / source["source_path"]
        if checksum(path) != source["sha256"]:
            raise ValueError("Original source hash changed")
        if source["sha256"] in seen:
            continue
        seen.add(source["sha256"])
        jobs.extend((source, page) for page in range(1, int(source["pages"]) + 1))
    if args.limit:
        jobs = jobs[: args.limit]
    (out / "run_frame.json").write_text(
        json.dumps(
            [
                {
                    "source_sha256": s["sha256"],
                    "source_page": page,
                    "district_index": s["label"],
                }
                for s, page in jobs
            ],
            indent=2,
        )
        + "\n"
    )
    completed, failures = [], []
    for source, page in jobs:
        target = out / f"{source['sha256']}_{page:04d}.json"
        identity = {
            "source_sha256": source["sha256"],
            "source_page": page,
            "model_digest": model["digest"],
            "prompt": PROMPT,
            "options": OPTIONS,
            "render_long_edge": 2200,
        }
        if target.exists():
            saved = json.loads(target.read_text())
            if (
                all(saved.get(k) == v for k, v in identity.items())
                and saved.get("status") == "response_saved"
            ):
                validate_response(saved["response"])
                completed.append(saved)
                continue
        started = time.monotonic()
        saved = identity | {
            "district_index": source["label"],
            "source_url": source["url"],
            "source_path": source["source_path"],
            "model": model,
            "code_sha256": checksum(Path(__file__)),
        }
        try:
            with tempfile.TemporaryDirectory(prefix="haryana-qwen-") as temporary:
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
                        "2200",
                        "-png",
                        str(base / source["source_path"]),
                        str(prefix),
                    ],
                    check=True,
                    capture_output=True,
                    timeout=120,
                )
                image = prefix.with_suffix(".png")
                saved["image_sha256"] = checksum(image)
                response = session.post(
                    url + "/api/generate",
                    json={
                        "model": model["name"],
                        "prompt": PROMPT,
                        "images": [base64.b64encode(image.read_bytes()).decode()],
                        "stream": False,
                        "format": "json",
                        "options": OPTIONS,
                        "keep_alive": "10m",
                    },
                    timeout=600,
                )
                saved["http_status"] = response.status_code
                saved["response"] = response.json()
                response.raise_for_status()
                saved["rows"] = validate_response(saved["response"])
                saved["status"] = "response_saved"
        except (
            requests.RequestException,
            subprocess.SubprocessError,
            OSError,
            ValueError,
        ) as error:
            saved.update(status="failed", error=str(error))
            failures.append(saved)
        saved["seconds"] = time.monotonic() - started
        pending = target.with_suffix(".tmp")
        pending.write_text(json.dumps(saved, indent=2) + "\n")
        pending.replace(target)
        if saved["status"] == "response_saved":
            completed.append(saved)
        print(
            json.dumps(
                {
                    "completed": len(completed),
                    "total": len(jobs),
                    "failures": len(failures),
                    "district": source["label"],
                    "page": page,
                    "status": saved["status"],
                }
            ),
            flush=True,
        )
    summary = {
        "requested_pages": len(jobs),
        "saved_pages": len(completed),
        "failed_pages": len(failures),
        "raw_rows": sum(len(x["rows"]) for x in completed),
        "scope": "Local vision evidence; validation and reconciliation pending",
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary))
    if failures:
        raise RuntimeError("Some pages failed; rerun to retry")


if __name__ == "__main__":
    main()
