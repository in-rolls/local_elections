"""Prepare and score fixed Haryana pages; submit to Meta's synchronous API.

Other providers belong in ../batchlane. This module owns only the Haryana
prompt, page provenance, pilot spending gate and accuracy checks.
"""

import argparse
import base64
import fcntl
import hashlib
import json
import math
import os
import re
import subprocess
import tempfile
import threading
import tomllib
from pathlib import Path

import requests

from local_elections.common.runlog import command
from local_elections.paths import ROOT
from local_elections.tools.historical_harvest import checksum
from local_elections.tools.parse_haryana_gazettes import candidate_category
from local_elections.tools.parse_haryana_surya import score_rows

BASE = ROOT / "data/source_search/national/haryana/early_cycles"
MODEL = "muse-spark-1.3-contributor"
ENDPOINT = "https://api.meta.ai/v1"
MAX_INPUT = 1_048_576
MAX_OUTPUT = 16384
INPUT_RATE = 0.10
OUTPUT_RATE = 0.20
MAX_REQUEST_USD = (MAX_INPUT * INPUT_RATE + MAX_OUTPUT * OUTPUT_RATE) / 1_000_000
PRICING_URL = "https://vercel.com/ai-gateway/models/muse-spark-1.3-contributor"
CONFIG_PATH = Path.home() / ".config/local_elections/haryana_ocr.toml"
SUBMISSION_LOCK = threading.Lock()
FIELDS = (
    "body_raw",
    "ward_raw",
    "winner_raw",
    "relation_raw",
    "office_raw",
    "category_raw",
)
PROMPT = (
    "Transcribe every English election-table row in original top-to-bottom order. "
    "Read actual data columns even when a continuation page repeats an incorrect "
    "header. body_raw is the printed village or Panchayat Samiti name on that row, "
    "never the elected person's name. Do not propagate body labels. Include a "
    "standalone body label as a row with all other fields null. ward_raw is only "
    "the visibly printed ward number, preserving its punctuation; never use a "
    "body serial number or infer a missing number from a sequence. winner_raw "
    "and relation_raw transcribe the two personal-name columns. office_raw "
    "transcribes Panch or Sarpanch only if actually printed, otherwise null. "
    "category_raw transcribes the complete Category cell including Woman/Women "
    "and handwritten annotations. A blank or unreadable cell must be null. "
    "Do not infer category from names, fill gaps, omit incomplete rows, or repeat "
    "tables. Ignore mastheads, headers and footnotes. Return only the rows array."
)


def payload_for(image):
    return {
        "model": MODEL,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": PROMPT},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": "data:image/jpeg;base64,"
                            + base64.b64encode(image).decode()
                        },
                    },
                ],
            }
        ],
        "temperature": 0,
        "max_completion_tokens": MAX_OUTPUT,
        "reasoning_effort": "high",
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "election_rows",
                "strict": True,
                "schema": {
                    "type": "object",
                    "properties": {
                        "rows": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    field: {"type": ["string", "null"]}
                                    for field in FIELDS
                                },
                                "required": list(FIELDS),
                                "additionalProperties": False,
                            },
                        }
                    },
                    "required": ["rows"],
                    "additionalProperties": False,
                },
            },
        },
    }


def response_rows(response, *, allow_empty=False):
    if "candidates" in response:
        candidates = response["candidates"]
        if len(candidates) != 1 or candidates[0].get("finishReason") != "STOP":
            raise ValueError("Missing or truncated model completion")
        parts = candidates[0].get("content", {}).get("parts", [])
        text = "".join(p.get("text", "") for p in parts if not p.get("thought"))
    else:
        choices = response.get("choices", [])
        if len(choices) != 1 or choices[0].get("finish_reason") != "stop":
            raise ValueError("Missing or truncated model completion")
        text = choices[0].get("message", {}).get("content")
        if not isinstance(text, str):
            raise ValueError("Missing completion text")
    result = json.loads(text)
    if not isinstance(result, dict) or set(result) != {"rows"}:
        raise ValueError("Unexpected response schema")
    rows = result["rows"]
    if not isinstance(rows, list) or (not rows and not allow_empty):
        raise ValueError("Missing table rows")
    for row in rows:
        if not isinstance(row, dict) or set(row) != set(FIELDS):
            raise ValueError("Unexpected cell schema")
        if any(v is not None and not isinstance(v, str) for v in row.values()):
            raise ValueError("Raw cells must remain text or null")
    return rows


def usage_cost(response):
    usage = response.get("usage")
    if not isinstance(usage, dict):
        raise ValueError("Missing usage metadata")
    prompt, output = usage.get("prompt_tokens"), usage.get("completion_tokens")
    if any(type(value) is not int or value < 0 for value in (prompt, output)):
        raise ValueError("Missing or invalid usage metadata")
    if prompt > MAX_INPUT or output > MAX_OUTPUT:
        raise ValueError("Provider usage exceeds the reserved request envelope")
    return (prompt * INPUT_RATE + output * OUTPUT_RATE) / 1_000_000


def reserve_one(identity, out, cap, max_requests, allow_empty):
    label = identity["label"].lower()
    target = out / f"attempt_{label}.json"
    raw = out / f"response_{label}.json"
    if target.exists():
        saved = json.loads(target.read_text())
        if (
            saved.get("status") == "response_saved; accuracy_unvalidated"
            and all(
                saved.get(k) == v for k, v in identity.items() if k != "code_sha256"
            )
            and raw.exists()
            and checksum(raw) == saved.get("response_sha256")
        ):
            result = json.loads(raw.read_text())
            response_rows(result, allow_empty=allow_empty)
            usage_cost(result)
            return saved, True
        raise ValueError("Existing attempt requires reconciliation; no automatic retry")
    attempts = list(out.glob("attempt_*.json"))
    records = [json.loads(p.read_text()) for p in attempts]
    reserved = sum(
        record["usage_priced_usd"]
        if record.get("status") == "response_saved; accuracy_unvalidated"
        else record["reserved_usd"]
        for record in records
    )
    if (
        not math.isfinite(cap)
        or cap <= 0
        or cap > 10
        or len(attempts) >= max_requests
        or reserved + MAX_REQUEST_USD > cap
    ):
        raise ValueError("Pilot request or spending limit reached")
    record = identity | {
        "reserved_usd": MAX_REQUEST_USD,
        "status": "attempt_reserved; outcome_unknown",
    }
    with target.open("x") as stream:
        stream.write(json.dumps(record, indent=2) + "\n")
        stream.flush()
        os.fsync(stream.fileno())
    return record, False


def submit_one(
    client,
    payload,
    identity,
    out,
    cap,
    *,
    max_requests=3,
    allow_empty=False,
    read_timeout=120,
):
    with SUBMISSION_LOCK:
        record, cached = reserve_one(identity, out, cap, max_requests, allow_empty)
    if cached:
        return record
    label = identity["label"].lower()
    target = out / f"attempt_{label}.json"
    raw = out / f"response_{label}.json"
    response = client.post(
        ENDPOINT + "/chat/completions", json=payload, timeout=(10, read_timeout)
    )
    raw.write_bytes(response.content)
    record["response_sha256"] = checksum(raw)
    with SUBMISSION_LOCK:
        target.write_text(json.dumps(record, indent=2) + "\n")
    response.raise_for_status()
    result = response.json()
    rows = response_rows(result, allow_empty=allow_empty)
    record.update(
        status="response_saved; accuracy_unvalidated",
        usage=result["usage"],
        usage_priced_usd=usage_cost(result),
        rows=len(rows),
    )
    with SUBMISSION_LOCK:
        target.write_text(json.dumps(record, indent=2) + "\n")
    return record


def score_reading(rows, labels, family):
    predictions = []
    body = None
    invalid_wards = 0
    for row in rows:
        if row["body_raw"]:
            body = row["body_raw"]
        if row["body_raw"] and all(row[key] is None for key in FIELDS[1:]):
            continue
        ward_raw = row["ward_raw"] or ""
        match = re.fullmatch(r"\s*([0-9]{1,2})\s*[*•.\x07]?\s*", ward_raw)
        invalid_wards += bool(ward_raw.strip()) and match is None
        caste, woman = candidate_category(row["category_raw"] or "")
        office = (row["office_raw"] or "").strip().upper()
        predictions.append(
            {
                "body_raw": body,
                "ward": int(match[1]) if match else None,
                "caste_candidate": caste,
                "woman_candidate": woman,
                "office_candidate": (
                    {"PANCH": "Panch", "SARPANCH": "Sarpanch"}.get(office)
                    if family == "gp_head_and_ward"
                    else "member"
                    if not office
                    else None
                ),
                "raw_cells": row,
            }
        )
    score = score_rows(predictions, labels)
    score["malformed_ward_readings"] = invalid_wards
    if len(predictions) == len(labels):
        score["correct_office"] = sum(
            p["office_candidate"] == label["office"]
            for p, label in zip(predictions, labels, strict=True)
        )
    score["gate_passed"] = (
        score.get("correct_ward_category_pair") == len(labels)
        and score.get("correct_office") == len(labels)
        and score.get("correct_body_within_page")
        == score.get("body_checkable_within_page")
        and len(predictions) == len(labels)
        and not invalid_wards
    )
    return score


@command("ocr", state="Haryana", vintage="2000_hosted_pilot")
def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--submit", action="store_true")
    parser.add_argument("--approved-usd", type=float, default=0)
    parser.add_argument("--score", action="store_true")
    parser.add_argument("--stage", choices=["diagnose", "validate"], default="diagnose")
    args = parser.parse_args()
    if args.submit and not 0 < args.approved_usd <= 1:
        raise ValueError("Supply the explicitly approved pilot cap, at most $1")
    benchmark = BASE / "gp_ps_benchmark"
    out = benchmark / (
        "muse_rest_pilot" if args.stage == "diagnose" else "muse_rest_validation"
    )
    out.mkdir(exist_ok=True)
    plan = json.loads((benchmark / "subsequent_split_plan.json").read_text())
    sources = [r for r in plan["frame"] if r["split"] == args.stage]
    expected = (
        [("AGROHA", 2), ("HISAR", 2), ("ROHTAK", 2)]
        if args.stage == "diagnose"
        else [("ASSANDH", 4), ("KAITHAL", 2)]
    )
    if [(r["label"], r["source_page"]) for r in sources] != expected:
        raise ValueError("Stage must retain its fixed page list")
    if args.stage == "validate":
        scores = json.loads((benchmark / "hosted_pilot/scores.json").read_text())
        if set(scores) != {"agroha", "hisar", "rohtak"} or not all(
            r["gate_passed"] for r in scores.values()
        ):
            raise ValueError("Diagnosis must pass before validation")
    if args.score:
        labels = []
        if args.stage == "diagnose":
            for split in ["diagnose", "validate"]:
                labels.extend(
                    json.loads((benchmark / f"labels_{split}.json").read_text())
                )
        else:
            labels = json.loads(
                (benchmark / "hosted_validation/labels.json").read_text()
            )
        scores = {}
        for source in sources:
            label = source["label"].lower()
            path = out / f"response_{label}.json"
            receipt = json.loads((out / f"attempt_{label}.json").read_text())
            if (
                receipt.get("response_sha256"),
                receipt["source_sha256"],
                receipt["source_page"],
            ) != (checksum(path), source["sha256"], source["source_page"]):
                raise ValueError("Response checksum or source identity changed")
            truth = [
                r
                for r in labels
                if r["source_sha256"] == source["sha256"]
                and r["source_page"] == source["source_page"]
            ]
            scores[label] = score_reading(
                response_rows(json.loads(path.read_text())), truth, source["family"]
            )
        (out / "scores.json").write_text(json.dumps(scores, indent=2) + "\n")
        print(json.dumps(scores))
        return
    client = None
    if args.submit:
        cfg = tomllib.loads(CONFIG_PATH.read_text()) if CONFIG_PATH.exists() else {}
        api_key = os.getenv("MODEL_API_KEY") or cfg.get("meta", {}).get("api_key")
        if not api_key:
            raise ValueError(f"Set MODEL_API_KEY or meta.api_key in {CONFIG_PATH}")
        client = requests.Session()
        client.headers["Authorization"] = f"Bearer {api_key}"
    with tempfile.TemporaryDirectory(prefix="hr-hosted-") as temporary:
        jobs = []
        for source in sources:
            pdf = BASE / source["source_path"]
            if checksum(pdf) != source["sha256"]:
                raise ValueError("Source PDF changed")
            prefix = Path(temporary).resolve() / source["label"]
            subprocess.run(
                [
                    "pdftoppm",
                    "-f",
                    str(source["source_page"]),
                    "-l",
                    str(source["source_page"]),
                    "-singlefile",
                    "-scale-to",
                    "2000",
                    "-jpeg",
                    "-jpegopt",
                    "quality=85",
                    str(pdf),
                    str(prefix),
                ],
                check=True,
                capture_output=True,
                timeout=120,
            )
            image = prefix.with_suffix(".jpg")
            payload = payload_for(image.read_bytes())
            encoded = json.dumps(payload, sort_keys=True).encode()
            identity = {
                "label": source["label"],
                "source_sha256": source["sha256"],
                "source_page": source["source_page"],
                "image_sha256": checksum(image),
                "image_bytes": image.stat().st_size,
                "request_bytes": len(encoded),
                "request_sha256": hashlib.sha256(encoded).hexdigest(),
                "model": MODEL,
                "render_long_edge": 2000,
                "prompt": PROMPT,
                "generation_config": {
                    k: v for k, v in payload.items() if k != "messages"
                },
                "code_sha256": checksum(Path(__file__)),
            }
            jobs.append((payload, identity))
        prepared = {
            "jobs": [identity for _, identity in jobs],
            "max_requests": len(sources),
            "max_input_tokens_each": MAX_INPUT,
            "max_output_tokens_each_including_thoughts": MAX_OUTPUT,
            "maximum_stage_usd": MAX_REQUEST_USD * len(sources),
            "rates_usd_per_million": {
                "input": INPUT_RATE,
                "output_including_thoughts": OUTPUT_RATE,
            },
            "pricing_checked": "2026-09-09",
            "pricing_basis": "Vercel Meta listing; direct billing unconfirmed",
            "pricing_url": PRICING_URL,
            "scope": (
                f"Fixed {args.stage} pages only; no automatic retries or expansion"
            ),
        }
        (out / "prepared.json").write_text(json.dumps(prepared, indent=2) + "\n")
        if args.submit:
            with (out / "submission.lock").open("a") as lock:
                fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                for payload, identity in jobs:
                    result = submit_one(
                        client,
                        payload,
                        identity,
                        out,
                        args.approved_usd,
                        max_requests=len(sources),
                    )
                    print(
                        json.dumps(
                            {
                                k: result[k]
                                for k in ["label", "rows", "usage_priced_usd"]
                            }
                        )
                    )
        else:
            print(
                json.dumps(
                    {
                        "prepared_requests": len(jobs),
                        "maximum_usd": MAX_REQUEST_USD * len(sources),
                    }
                )
            )


if __name__ == "__main__":
    main()
