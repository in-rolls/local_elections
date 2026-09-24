"""Run the approved Haryana page frame through the tested synchronous Muse call.

Page selection, source checks and review gates live here. The pilot owns the
single API call and budget reservation; no provider framework is duplicated.
"""

import argparse
import base64
import csv
import fcntl
import hashlib
import json
import os
import re
import subprocess
import time
import tomllib
import unicodedata
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

from local_elections.common.runlog import command
from local_elections.tools import pilot_haryana_hosted as pilot
from local_elections.tools.historical_harvest import checksum
from local_elections.tools.parse_haryana_gazettes import candidate_category
from local_elections.tools.source_nonseat_reviews import apply_source_nonseat_reviews

BASE = pilot.BASE / "gp_ps_benchmark"
OUT = BASE / "muse_rollout"
RENDER_LONG_EDGE = 4000


def page_payload(image):
    payload = pilot.payload_for(image)
    prompt = pilot.PROMPT.replace(
        "every English election-table row", "every English or Hindi election-table row"
    ).replace(
        "transcribes Panch or Sarpanch only if actually printed",
        "transcribes the office exactly as printed in either language",
    )
    payload["messages"][0]["content"][0]["text"] = prompt + (
        " Preserve the original script; never translate or transliterate. "
        "Include both languages when both are printed, retaining separate rows."
        " Hindi must be readable Devanagari Unicode, never control characters, "
        "placeholder symbols or phonetic Latin text. Do not copy a village serial "
        "number into body_raw. Follow each physical row across the slant of the "
        "page: right-hand cells may sit lower than their left-hand ward number. "
        "A wrapped or displaced category cell belongs to its existing row, not "
        "a new record. A printed vacant-seat entry is one row, not a person plus "
        "a second category-only row. Inspect the entire right margin for faint "
        "handwritten Woman/Women annotations, preserving them in category_raw. "
        "Do not assign a woman marker to a neighbouring row. Each table can "
        "belong to a different notification or office type on the same page."
    )
    return payload


def category_for(raw):
    raw = raw or ""
    parsed = candidate_category(raw)
    if parsed != (None, None):
        return parsed
    value = re.sub(r"[\s.,()\-]", "", unicodedata.normalize("NFC", raw))
    woman = "\u092e\u0939\u093f\u0932\u093e" in value
    value = value.replace("\u092e\u0939\u093f\u0932\u093e", "")
    categories = {
        unicodedata.normalize("NFC", k): v
        for k, v in {
            "\u0938\u093e\u092e\u093e\u0928\u094d\u092f": "NONE",
            (
                "\u0905\u0928\u0941\u0938\u0942\u091a\u093f\u0924"
                "\u091c\u093e\u0924\u093f"
            ): "SC",
            "\u0905\u0928\u0941\u091c\u093e\u0924\u093f": "SC",
            "\u092a\u093f\u091b\u0921\u093c\u0940\u091c\u093e\u0924\u093f": "BC",
            "\u092a\u093f\u091b\u0921\u0940\u091c\u093e\u0924\u093f": "BC",
        }.items()
    }
    if value in categories:
        return categories[value], woman
    return ("NONE", True) if not value and woman else (None, None)


def normalized_office(raw):
    if isinstance(raw, str) and raw.strip().upper() == "PARICH":
        return "PANCH"
    value = unicodedata.normalize("NFC", raw or "").strip().upper()
    value = value.strip(" .-*\u2022")
    # Pinjore PDF 6b0f2814..., page 6, prints Sarpancn for Nanak Pur.
    # Fatehabad PDF 1dceb1db..., page 6, prints Ponch in a Panch office cell.
    return {"SARPANCN": "SARPANCH", "PONCH": "PANCH"}.get(value, value)


def confirmed_non_seat_row(row, ordinal, source):
    return (
        source is not None
        and source["source_sha256"]
        == "025748a47542c15ba052b379ead27ea55977e50c8965473a5061e40658ed5f5a"
        and int(source["source_page"]) == 2
        and ordinal == 47
        and row["winner_raw"]
        == "\u0928\u093f\u0930\u094d\u0935\u093f\u0930\u094b\u0927"
        and all(
            row[field] is None
            for field in (
                "body_raw",
                "ward_raw",
                "relation_raw",
                "office_raw",
                "category_raw",
            )
        )
    )


def office_tier(office, family):
    printed = {
        "PANCH": "gp_ward",
        "SARPANCH": "gp_head",
        "\u092a\u0902\u091a": "gp_ward",
        "\u0938\u0930\u092a\u0902\u091a": "gp_head",
    }.get(normalized_office(office))
    if printed:
        return printed
    if not office and family == "block_member":
        return "block_member"
    return None


def save(path, value):
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w") as stream:
        stream.write(json.dumps(value, indent=2) + "\n")
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)


def page_id(row):
    return f"{row['source_sha256']}-p{int(row['source_page']):04d}"


def _prepare_primary(source):
    label = page_id(source)
    folder = OUT / f"images_{RENDER_LONG_EDGE}"
    folder.mkdir(exist_ok=True)
    image = folder / f"{label}.jpg"
    if not image.exists():
        subprocess.run(
            [
                "pdftoppm",
                "-f",
                source["source_page"],
                "-l",
                source["source_page"],
                "-singlefile",
                "-scale-to",
                str(RENDER_LONG_EDGE),
                "-jpeg",
                "-jpegopt",
                "quality=85",
                str(pilot.BASE / source["source_path"]),
                str(image.with_suffix("")),
            ],
            check=True,
            capture_output=True,
            timeout=60,
        )
    payload = page_payload(image.read_bytes())
    identity = {
        "label": label,
        "source_sha256": source["source_sha256"],
        "source_page": int(source["source_page"]),
        "image_sha256": checksum(image),
        "request_sha256": hashlib.sha256(
            json.dumps(payload, sort_keys=True).encode()
        ).hexdigest(),
        "model": pilot.MODEL,
    }
    target = OUT / f"attempt_{label}.json"
    if not target.exists():
        for name in ("assandh", "kaithal"):
            prior = BASE / "muse_rest_validation" / f"attempt_{name}.json"
            receipt = json.loads(prior.read_text())
            if all(
                receipt.get(k) == identity[k]
                for k in (
                    "source_sha256",
                    "source_page",
                    "image_sha256",
                    "request_sha256",
                )
            ):
                raw = prior.with_name(f"response_{name}.json")
                if checksum(raw) != receipt["response_sha256"]:
                    raise ValueError("Cached pilot response changed")
                (OUT / f"response_{label}.json").write_bytes(raw.read_bytes())
                save(target, receipt | identity | {"reused_from": str(prior)})
                break
    return payload, identity


def _submit_page(source, key):
    payload, identity = prepare(source)
    attempt_pattern = re.compile(
        rf"attempt_{re.escape(identity['label'])}(?:-retry([0-9]+))?\.json"
    )
    prior_numbers = [
        int(match.group(1) or 0)
        for path in OUT.glob(f"attempt_{identity['label']}*.json")
        if (match := attempt_pattern.fullmatch(path.name))
    ]
    first_retry = max(prior_numbers, default=-1) + 1
    if first_retry:
        payload = payload | {"reasoning_effort": "medium"}
    if source.get("reasoning_effort"):
        payload = payload | {"reasoning_effort": source["reasoning_effort"]}
    with requests.Session() as client:
        client.headers["Authorization"] = f"Bearer {key}"
        for retry_offset in range(3):
            retry = first_retry + retry_offset
            label = identity["label"] + (f"-retry{retry}" if retry else "")
            try:
                result = pilot.submit_one(
                    client,
                    payload,
                    identity
                    | {
                        "label": label,
                        "request_sha256": hashlib.sha256(
                            json.dumps(payload, sort_keys=True).encode()
                        ).hexdigest(),
                        "reasoning_effort": payload["reasoning_effort"],
                    },
                    OUT,
                    10,
                    max_requests=1 + 3 * 1646,
                    allow_empty=True,
                    read_timeout=300,
                )
                selection_path = OUT / f"selection_{identity['label']}.json"
                previous = (
                    json.loads(selection_path.read_text())
                    if selection_path.exists()
                    else {}
                )
                history = previous.get("previous_labels", [])
                if previous.get("label") and previous["label"] != label:
                    history = list(dict.fromkeys([*history, previous["label"]]))
                save(selection_path, {"label": label, "previous_labels": history})
                return result
            except (requests.RequestException, ValueError) as exc:
                raw = OUT / f"response_{label}.json"
                if raw.exists():
                    try:
                        response = json.loads(raw.read_text())
                        if any(
                            c.get("finish_reason") == "length"
                            for c in response.get("choices", [])
                        ):
                            payload = payload | {
                                "reasoning_effort": source.get(
                                    "reasoning_effort", "medium"
                                )
                            }
                        cost = pilot.usage_cost(response)
                        with pilot.SUBMISSION_LOCK:
                            path = OUT / f"attempt_{label}.json"
                            receipt = json.loads(path.read_text())
                            receipt.update(
                                status="response_saved; unusable; cost_reconciled",
                                usage=response["usage"],
                                usage_priced_usd=cost,
                                reserved_usd=cost,
                            )
                            save(path, receipt)
                    except (ValueError, KeyError):
                        pass
                if isinstance(exc, requests.HTTPError) and exc.response is not None:
                    status = exc.response.status_code
                    if status < 500 and status not in {408, 409, 429}:
                        raise
                if "spending limit" in str(exc) or retry_offset == 2:
                    raise
                print(
                    json.dumps(
                        {
                            "page": identity["label"],
                            "retry": retry + 1,
                            "reason": type(exc).__name__,
                        }
                    ),
                    flush=True,
                )
                time.sleep(10 * (retry_offset + 1))


def _export_primary(frame):
    """Keep every printed record and flag uncertain context instead of inventing it."""
    records, pages = [], []
    previous = {}
    for source in sorted(
        frame, key=lambda r: (r["source_sha256"], int(r["source_page"]))
    ):
        label = page_id(source)
        selection = OUT / f"selection_{label}.json"
        if selection.exists():
            label = json.loads(selection.read_text())["label"]
        path = OUT / f"response_{label}.json"
        receipt_path = OUT / f"attempt_{label}.json"
        if not receipt_path.exists():
            continue
        receipt = json.loads(receipt_path.read_text())
        if receipt.get("status") != "response_saved; accuracy_unvalidated":
            pages.append(source | {"status": "unanswered_or_invalid", "rows": 0})
            continue
        if checksum(path) != receipt["response_sha256"]:
            raise ValueError("Response checksum changed")
        rows = pilot.response_rows(json.loads(path.read_text()), allow_empty=True)
        body = None
        page_records = []
        prior = previous.get(source["source_sha256"])
        for index, row in enumerate(rows, 1):
            if confirmed_non_seat_row(row, index, source):
                continue
            body = row["body_raw"] or body
            if row["body_raw"] and all(row[k] is None for k in pilot.FIELDS[1:]):
                continue
            ward_text = row["ward_raw"] or ""
            ward_text = ward_text.translate(
                {0x0966 + digit: str(digit) for digit in range(10)}
            )
            match = re.fullmatch(
                r"\s*([0-9]{1,2})\s*(?:[*\u2022.]|[\x06\x07]\s*[*\u2022.]?)?\s*",
                ward_text,
            )
            caste, woman = category_for(row["category_raw"] or "")
            office = (row["office_raw"] or "").strip().upper()
            flags = []
            if match and re.search(r"[\x06\x07]", ward_text):
                flags.append("ward_footnote_marker_unreadable")
            if normalized_office(office) != office:
                flags.append("office_spelling_normalized_raw_preserved")
            hindi = any(
                re.search(r"[\u0900-\u097f]", value or "") for value in row.values()
            )
            if hindi:
                flags.append("bilingual_occurrence_reconciliation_pending")
            if any(
                re.search(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", value or "")
                for key, value in row.items()
                if key != "ward_raw"
            ):
                flags.append("invalid_control_characters")
            if row["body_raw"] and re.match(r"^\s*\d+\s+", row["body_raw"]):
                flags.append("body_serial_in_name")
            if not any(row[k] for k in ("ward_raw", "winner_raw", "relation_raw")):
                flags.append("unanchored_fragment")
            if ward_text and not match:
                flags.append("malformed_ward")
            if caste is None or woman is None:
                flags.append("category_unresolved")
            if not body:
                flags.append("incoming_body_context_unvalidated")
            tier = office_tier(office, source["family"])
            if tier is None:
                flags.append("office_unresolved")
            elif tier == "block_member":
                flags.append("tier_from_inventory_unvalidated")
            elif source["family"] == "block_member":
                flags.append("mixed_notification_context_requires_review")
            if tier != "gp_head" and not match:
                flags.append("ward_missing")
            if not row["winner_raw"]:
                flags.append("winner_missing")
            record = (
                source
                | row
                | {
                    "source_row_on_page": index,
                    "state": "Haryana",
                    "year_context": 2000,
                    "year_basis": "source inventory; notification context unvalidated",
                    "script": "Devanagari"
                    if hindi
                    else "Latin"
                    if any(re.search(r"[A-Za-z]", v or "") for v in row.values())
                    else "Unreadable",
                    "body_within_page": body,
                    "incoming_body_candidate": prior[1]
                    if (
                        not body
                        and prior
                        and prior[0] + 1 == int(source["source_page"])
                    )
                    else None,
                    "ward": int(match[1]) if match else None,
                    "tier": tier,
                    "office_normalized": normalized_office(office),
                    "caste_reservation": caste,
                    "woman_reserved": woman,
                    "quality_flags": ";".join(flags),
                    "review_status": "automated transcription; source review pending",
                }
            )
            page_records.append(record)
        keys = Counter(
            (r["body_within_page"], r["ward"], r["tier"]) for r in page_records
        )
        for r in page_records:
            if keys[(r["body_within_page"], r["ward"], r["tier"])] > 1:
                r["quality_flags"] += ";duplicate_seat_key_within_page"
        if page_records:
            previous[source["source_sha256"]] = (
                int(source["source_page"]),
                page_records[-1]["body_within_page"],
            )
        records.extend(page_records)
        pages.append(
            source
            | {
                "status": "transcribed" if page_records else "empty_requires_review",
                "rows": len(page_records),
                "usage_priced_usd": receipt["usage_priced_usd"],
            }
        )
    if records:
        import pandas as pd

        table = pd.DataFrame(records)
        table["source_page"] = table.source_page.astype("Int64")
        table["ward"] = table.ward.astype("Int64")
        table["woman_reserved"] = table.woman_reserved.astype("boolean")
        table.to_parquet(OUT / "seat_rows.parquet", index=False)
        table[table.quality_flags.ne("")].to_csv(OUT / "review_queue.csv", index=False)
    receipts = [json.loads(p.read_text()) for p in OUT.glob("attempt_*.json")]
    exposure = sum(r.get("usage_priced_usd", r["reserved_usd"]) for r in receipts)
    summary = {
        "pages_in_frame": len(frame),
        "pages_transcribed": sum(r["status"] == "transcribed" for r in pages),
        "records": len(records),
        "accounted_exposure_usd": exposure,
        "cap_usd": 10,
        "page_statuses": dict(Counter(r["status"] for r in pages)),
        "quality_flags": dict(
            Counter(f for r in records for f in r["quality_flags"].split(";") if f)
        ),
        "status": "research staging; unresolved readings retained for review",
    }
    save(OUT / "pages.json", pages)
    save(OUT / "summary.json", summary)
    return summary


def _legacy_main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--stage", choices=["review", "production", "export"], required=True
    )
    parser.add_argument("--workers", type=int, default=8, choices=range(1, 17))
    parser.add_argument("--limit", type=int, default=32)
    args = parser.parse_args()
    plan = json.loads((OUT / "plan.json").read_text())
    frame_path = BASE / "hosted_rollout/page_frame.csv"
    if plan["authorized_usd"] != 10 or checksum(frame_path) != plan["frame_sha256"]:
        raise ValueError("Approval or frozen page frame changed")
    method = hashlib.sha256(
        json.dumps(page_payload(b""), sort_keys=True).encode()
    ).hexdigest()
    if plan["method_sha256"] != method:
        raise ValueError("Extraction method changed; new quality gate required")
    if plan["render_long_edge"] != RENDER_LONG_EDGE:
        raise ValueError("Image resolution changed; new quality gate required")
    with frame_path.open() as stream:
        frame = list(csv.DictReader(stream))
    with (OUT / "submission.lock").open("a") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        if args.stage == "export":
            print(json.dumps(export(frame)), flush=True)
            return
        if args.stage == "production":
            gate = json.loads((OUT / "review_gate.json").read_text())
            approved_staging = (
                plan.get("production_authorized_with_review_queue") is True
                and gate.get("scope") == "raw_transcription_only"
            )
            if not (gate["passed"] or approved_staging) or gate[
                "plan_sha256"
            ] != checksum(OUT / "plan.json"):
                raise ValueError("Broader review gate has not passed")
        sources = plan["review_pages"] if args.stage == "review" else frame
        sources = [
            r for r in sources if not (OUT / f"attempt_{page_id(r)}.json").exists()
        ]
        if args.limit <= 0:
            raise ValueError("Limit must be positive")
        sources = sources[: args.limit]
        for sha, path in {(r["source_sha256"], r["source_path"]) for r in sources}:
            if checksum(pilot.BASE / path) != sha:
                raise ValueError(f"Source PDF changed: {path}")
        cfg = tomllib.loads(pilot.CONFIG_PATH.read_text())
        key = os.getenv("MODEL_API_KEY") or cfg["meta"]["api_key"]
        prior = OUT / "attempt_prior_pilot.json"
        if not prior.exists():
            save(
                prior,
                {"reserved_usd": 0.216273, "status": "prior_unknown_charges_and_probe"},
            )
        failures = []
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            # Submit only a bounded stage; expansion is a separate quality decision.
            futures = {pool.submit(read_page, r, key): r for r in sources}
            for future in as_completed(futures):
                source = futures[future]
                try:
                    result = future.result()
                    print(
                        json.dumps(
                            {
                                k: result[k]
                                for k in ("label", "rows", "usage_priced_usd")
                            }
                        ),
                        flush=True,
                    )
                except Exception as exc:
                    failures.append(
                        {"page": page_id(source), "error": type(exc).__name__}
                    )
        summary = export(frame)
        summary["stage_failures"] = failures
        save(OUT / "stage_result.json", summary)
        print(json.dumps(summary), flush=True)


COLUMN_PROMPT = (
    "Read only the two visible columns, office and reservation category, in "
    "top-to-bottom printed order. Each printed office word is exactly one row, "
    "including rows with a blank category. Copy the office word into office_raw "
    "and the entire corresponding Category cell, including any female marker, "
    "into category_raw. All four other fields must be null because those columns "
    "are outside this crop. Preserve the original Devanagari or Latin script "
    "exactly; use readable Unicode, never control-character placeholders. Do not "
    "translate or infer. Never create an extra row for a woman marker or a "
    "wrapped category. Ignore header labels, footnotes and scan borders. Return "
    "the rows object matching the JSON schema."
)


def column_payload(image):
    payload = pilot.payload_for(image)
    for message in payload["messages"]:
        if message["role"] == "user":
            for item in message["content"]:
                if item["type"] == "text":
                    item["text"] = COLUMN_PROMPT
    payload["reasoning_effort"] = "medium"
    return payload


def prepare_anchor(source):
    payload, identity = _prepare_primary(source)
    folder = OUT / "anchor_crops_4000"
    folder.mkdir(exist_ok=True)
    crops = []
    content = payload["messages"][0]["content"]
    content[0]["text"] += (
        " Additional images are overlapping close-ups of this SAME page. "
        "Use them to read small letters, not as additional tables. Return each "
        "physical row exactly once, in the original full-page order. Preserve "
        "candidate and parent/spouse names so the rows can be identified."
    )
    for y in (0, 1900):
        image = folder / f"{page_id(source)}-y{y}.jpg"
        if not image.exists():
            subprocess.run(
                [
                    "pdftoppm",
                    "-f",
                    str(source["source_page"]),
                    "-l",
                    str(source["source_page"]),
                    "-singlefile",
                    "-scale-to",
                    "4000",
                    "-x",
                    "0",
                    "-y",
                    str(y),
                    "-W",
                    "4000",
                    "-H",
                    "2100",
                    "-jpeg",
                    "-jpegopt",
                    "quality=95",
                    str(pilot.BASE / source["source_path"]),
                    str(image.with_suffix("")),
                ],
                check=True,
                capture_output=True,
                timeout=60,
            )
        content.append(
            {
                "type": "image_url",
                "image_url": {
                    "url": "data:image/jpeg;base64,"
                    + base64.b64encode(image.read_bytes()).decode()
                },
            }
        )
        crops.append(
            {"crop_at_4000px": [0, y, 4000, 2100], "image_sha256": checksum(image)}
        )
    payload["reasoning_effort"] = "medium"
    return payload, identity | {
        "label": f"{page_id(source)}-anchors-v1",
        "closeups": crops,
        "request_sha256": hashlib.sha256(
            json.dumps(payload, sort_keys=True).encode()
        ).hexdigest(),
    }


def prepare(source):
    if source.get("anchor_audit"):
        return prepare_anchor(source)
    if "column_crop_x" not in source:
        return _prepare_primary(source)
    x = source["column_crop_x"]
    suffix = "columns2" if x == 1780 else f"columns-wide{x}"
    label = f"{page_id(source)}-{suffix}"
    folder = OUT / "column_fullheight_quality"
    folder.mkdir(exist_ok=True)
    image = folder / f"{label}.jpg"
    if not image.exists():
        page = str(source["source_page"])
        subprocess.run(
            [
                "pdftoppm",
                "-f",
                page,
                "-l",
                page,
                "-singlefile",
                "-scale-to",
                "4000",
                "-x",
                str(x),
                "-y",
                "0",
                "-W",
                "4000",
                "-H",
                "4000",
                "-jpeg",
                "-jpegopt",
                "quality=95",
                str(pilot.BASE / source["source_path"]),
                str(image.with_suffix("")),
            ],
            check=True,
            timeout=60,
        )
    payload = column_payload(image.read_bytes())
    return payload, {
        "label": label,
        "source_sha256": source["source_sha256"],
        "source_page": int(source["source_page"]),
        "image_sha256": checksum(image),
        "request_sha256": hashlib.sha256(
            json.dumps(payload, sort_keys=True).encode()
        ).hexdigest(),
        "model": payload["model"],
        "crop_at_4000px": [x, 0, 4000, 4000],
    }


def cached_response(source, label):
    selection = OUT / f"selection_{label}.json"
    if selection.exists():
        label = json.loads(selection.read_text())["label"]
    receipt_path = OUT / f"attempt_{label}.json"
    response_path = OUT / f"response_{label}.json"
    if not receipt_path.exists() or not response_path.exists():
        return None
    receipt = json.loads(receipt_path.read_text())
    if receipt.get("status") != "response_saved; accuracy_unvalidated":
        return None
    if (
        receipt.get("source_sha256") != source["source_sha256"]
        or int(receipt.get("source_page", -1)) != int(source["source_page"])
        or receipt.get("response_sha256") != checksum(response_path)
    ):
        raise ValueError(f"Cached response provenance mismatch: {label}")
    rows = pilot.response_rows(json.loads(response_path.read_text()), allow_empty=True)
    return receipt, rows


def office_sequence(rows):
    return [normalized_office(row["office_raw"]) for row in rows]


def seat_rows_with_ordinals(primary, source=None):
    return [
        (ordinal, row)
        for ordinal, row in enumerate(primary, 1)
        if not confirmed_non_seat_row(row, ordinal, source)
        and not (
            row["body_raw"]
            and all(
                row[field] is None
                for field in (
                    "ward_raw",
                    "winner_raw",
                    "relation_raw",
                    "office_raw",
                    "category_raw",
                )
            )
        )
    ]


def column_alignment_issues(primary, columns, source=None):
    primary = [row for _, row in seat_rows_with_ordinals(primary, source)]
    offices = office_sequence(primary)
    known = {
        "PANCH",
        "SARPANCH",
        "\u092a\u0902\u091a",
        "\u0938\u0930\u092a\u0902\u091a",
    }
    issues = []
    if not primary:
        issues.append("no_primary_seat_rows")
    if len(primary) != len(columns):
        issues.append("different_row_counts")
    if any(office not in known for office in offices):
        issues.append("primary_office_missing_or_unrecognized")
    if offices != office_sequence(columns):
        issues.append("office_sequences_differ")
    if any(
        any(
            row[field] is not None
            for field in ("body_raw", "ward_raw", "winner_raw", "relation_raw")
        )
        for row in columns
    ):
        issues.append("crop_populated_forbidden_fields")
    return issues


def column_alignment(primary, columns, source=None):
    return not column_alignment_issues(primary, columns, source)


def name_anchor(row):
    values = [row["winner_raw"], row["relation_raw"]]
    if any(not value or re.search(r"[\x00-\x1f]", value) for value in values):
        return None
    values[0] = re.sub(r"^\s*\*\s*", "", values[0], count=1)
    if not values[0].strip():
        return None
    return tuple(
        " ".join(unicodedata.normalize("NFC", value).casefold().split())
        for value in values
    )


def anchor_ward(raw):
    text = (raw or "").translate({0x0966 + digit: str(digit) for digit in range(10)})
    match = re.fullmatch(
        r"\s*([0-9]{1,2})\s*(?:[*\u2022.]|[\x06\x07]\s*[*\u2022.]?)?\s*", text
    )
    return int(match[1]) if match else None


def read_page(source, key, *, cache_only=False):
    label = page_id(source)
    cached = cached_response(source, label)
    previous_primary_sha256 = cached[0]["response_sha256"] if cached else None
    if source.get("refresh_primary"):
        if cache_only:
            raise ValueError("A cache-only pass cannot refresh provider responses")
        _submit_page(source, key)
        cached = cached_response(source, label)
    if cached is None:
        if cache_only:
            raise ValueError(f"No usable cached primary response: {label}")
        _submit_page(source, key)
        cached = cached_response(source, label)
    if cached is None:
        raise ValueError(f"No usable primary response: {label}")
    receipt, primary = cached
    report = {
        "source_sha256": source["source_sha256"],
        "source_page": int(source["source_page"]),
        "primary_response_sha256": receipt["response_sha256"],
        "primary_rows": len(primary),
        "previous_primary_response_sha256": previous_primary_sha256,
        "aligned": False,
        "category_overrides": [],
        "alignment_version": 5,
        "primary_seat_rows": len(seat_rows_with_ordinals(primary, source)),
        "status": "column_pass_pending",
        "column_attempts": [],
        "excluded_primary_rows": [
            {
                "source_row_on_page": i,
                "reason": "source_confirmed_unopposed_footnote",
                "raw": row,
            }
            for i, row in enumerate(primary, 1)
            if confirmed_non_seat_row(row, i, source)
        ],
        "primary_office_normalizations": [
            {
                "source_row_on_page": i,
                "raw": row["office_raw"],
                "normalized": normalized_office(row["office_raw"]),
            }
            for i, row in enumerate(primary, 1)
            if normalized_office(row["office_raw"])
            != (row["office_raw"] or "").strip().upper()
        ],
    }
    if source["family"] == "block_member" or not primary:
        report["status"] = "samiti_or_empty_page_source_review_required"
    else:
        for x in (1780, 1450):
            suffix = "columns2" if x == 1780 else f"columns-wide{x}"
            column_label = f"{label}-{suffix}"
            columns_cached = cached_response(source, column_label)
            if source.get("refresh_columns"):
                if cache_only:
                    raise ValueError(
                        "A cache-only pass cannot refresh provider responses"
                    )
                _submit_page(source | {"column_crop_x": x}, key)
                columns_cached = cached_response(source, column_label)
            if columns_cached is None:
                if cache_only:
                    report["column_attempts"].append(
                        {"crop_x": x, "issues": ["usable_column_cache_missing"]}
                    )
                    continue
                _submit_page(source | {"column_crop_x": x}, key)
                columns_cached = cached_response(source, column_label)
            if columns_cached is None:
                raise ValueError(f"No usable column response: {column_label}")
            column_receipt, columns = columns_cached
            issues = column_alignment_issues(primary, columns, source)
            aligned = not issues
            report["column_attempts"].append(
                {
                    "crop_x": x,
                    "column_label": column_receipt["label"],
                    "column_rows": len(columns),
                    "issues": issues,
                    "column_response_sha256": column_receipt["response_sha256"],
                }
            )
            report.update(
                aligned=aligned,
                column_rows=len(columns),
                crop_x=x,
                alignment_issues=issues,
                column_label=column_receipt["label"],
                column_response_sha256=column_receipt["response_sha256"],
                status="aligned" if aligned else "column_alignment_failed",
            )
            if aligned:
                report["category_overrides"] = [
                    {
                        "source_row_on_page": i,
                        "primary_raw": row["category_raw"],
                        "column_raw": column["category_raw"],
                        "recognized": category_for(column["category_raw"])[0]
                        is not None,
                    }
                    for (i, row), column in zip(
                        seat_rows_with_ordinals(primary, source), columns, strict=True
                    )
                ]
                break
    save(OUT / f"alignment_{label}.json", report)
    return receipt | {"column_status": report["status"]}


def corroborate_page(source, key):
    """Attach office/category evidence without replacing names or ward readings."""
    label = page_id(source)
    primary_cached = cached_response(source, label)
    if primary_cached is None:
        raise ValueError(f"No usable primary response to corroborate: {label}")
    primary_receipt, primary = primary_cached
    audit_label = f"{label}-anchors-v1"
    audit_cached = cached_response(source, audit_label)
    if audit_cached is None:
        _submit_page(source | {"anchor_audit": True}, key)
        audit_cached = cached_response(source, audit_label)
    if audit_cached is None:
        raise ValueError(f"No usable anchor audit: {label}")
    audit_receipt, audit = audit_cached
    primary_seats = seat_rows_with_ordinals(primary, source)
    audit_seats = seat_rows_with_ordinals(audit, source)
    primary_counts = Counter(name_anchor(row) for _, row in primary_seats)
    audit_counts = Counter(name_anchor(row) for _, row in audit_seats)
    audit_index = {
        name_anchor(row): (ordinal, row)
        for ordinal, row in audit_seats
        if name_anchor(row) and audit_counts[name_anchor(row)] == 1
    }
    matches, issues, corrections = [], [], []
    for ordinal, row in primary_seats:
        anchor = name_anchor(row)
        if not anchor or primary_counts[anchor] != 1 or anchor not in audit_index:
            issues.append(
                {
                    "source_row_on_page": ordinal,
                    "reason": "name_anchor_missing_or_nonunique",
                }
            )
            continue
        audit_ordinal, other = audit_index[anchor]
        matches.append((ordinal, row, audit_ordinal, other))
    order = [item[2] for item in matches]
    if order != sorted(order):
        issues.append(
            {"source_row_on_page": None, "reason": "name_anchor_order_conflict"}
        )
        matches = []
    known = {
        "PANCH",
        "SARPANCH",
        "\u092a\u0902\u091a",
        "\u0938\u0930\u092a\u0902\u091a",
    }
    for ordinal, row, audit_ordinal, other in matches:
        old_ward, new_ward = (
            anchor_ward(row["ward_raw"]),
            anchor_ward(other["ward_raw"]),
        )
        old_office, new_office = (
            normalized_office(row["office_raw"]),
            normalized_office(other["office_raw"]),
        )
        old_category, new_category = (
            category_for(row["category_raw"]),
            category_for(other["category_raw"]),
        )
        reason = None
        if old_ward is not None and new_ward is not None and old_ward != new_ward:
            reason = "ward_disagreement"
        elif new_office not in known:
            reason = "audit_office_unrecognized"
        elif old_office in known and old_office != new_office:
            reason = "office_disagreement"
        elif new_category[0] is None:
            reason = "audit_category_unrecognized"
        elif old_category[0] is not None and old_category != new_category:
            reason = "recognized_category_disagreement"
        if reason:
            issues.append(
                {
                    "source_row_on_page": ordinal,
                    "audit_row_on_page": audit_ordinal,
                    "reason": reason,
                    "primary": row,
                    "audit": other,
                }
            )
            continue
        corrections.append(
            {
                "source_row_on_page": ordinal,
                "audit_row_on_page": audit_ordinal,
                "office_raw": other["office_raw"],
                "category_raw": other["category_raw"],
                "primary_office_raw": row["office_raw"],
                "primary_category_raw": row["category_raw"],
                "category_recovered": old_category[0] is None,
            }
        )
    status = (
        "all_rows_anchored"
        if (
            primary_seats and len(corrections) == len(primary_seats) == len(audit_seats)
        )
        else "partially_anchored"
        if corrections
        else "no_accepted_anchors"
    )
    report = {
        "audit_version": 3,
        "source_sha256": source["source_sha256"],
        "name_anchor_policy": (
            "Ignore one leading winner footnote asterisk in comparison keys only; "
            "preserve raw fields"
        ),
        "source_page": int(source["source_page"]),
        "status": status,
        "primary_response_sha256": primary_receipt["response_sha256"],
        "audit_label": audit_receipt["label"],
        "audit_response_sha256": audit_receipt["response_sha256"],
        "primary_seat_rows": len(primary_seats),
        "audit_seat_rows": len(audit_seats),
        "accepted_rows": len(corrections),
        "corrections": corrections,
        "issues": issues,
        "issue_counts": dict(Counter(item["reason"] for item in issues)),
        "unmatched_audit_ordinals": sorted(
            {i for i, _ in audit_seats}
            - {item["audit_row_on_page"] for item in corrections}
        ),
        "quality_status": (
            "Automated corroboration, not independent source accuracy certification"
        ),
        "fields_never_replaced": ["body_raw", "ward_raw", "winner_raw", "relation_raw"],
    }
    save(OUT / f"anchor_audit_{label}.json", report)
    return audit_receipt | {"column_status": status}


def apply_source_office_reviews(records):
    import pandas as pd

    from local_elections.tools.source_context_reviews import (
        validate_gp_notification_review,
    )

    reviews = {}
    counts = Counter()
    for path in sorted(OUT.glob("source_office_review_*.json")):
        review = json.loads(path.read_text())
        key = (
            review["source_sha256"],
            int(review["source_page"]),
            int(review["source_row_on_page"]),
        )
        if key in reviews:
            raise ValueError("Conflicting source-office reviews for the same row")
        if review["office_normalized"] not in {"PANCH", "SARPANCH"}:
            raise ValueError("Unsupported source-reviewed office")
        gp_notification = review.get("review_kind") == "same_page_gp_notification"
        if gp_notification:
            validate_gp_notification_review(review, OUT)
        unverified_category = gp_notification and review["category_authority"] == (
            "handwritten_amendment_unverified"
        )
        required = {"winner_raw", "relation_raw", "office_raw"}
        if not required.issubset(review["expected_raw"]):
            raise ValueError("Source-office review lacks raw identity preconditions")
        for identity in ("winner", "relation"):
            field = f"{identity}_source_raw"
            if field in review and (
                not isinstance(review[field], str) or not review[field].strip()
            ):
                raise ValueError("Source-reviewed identity must be nonempty text")
        if (
            "caste_reservation" in review
            and not unverified_category
            and review["caste_reservation"]
            not in {
                "NONE",
                "UR",
                "BC",
                "SC",
                "ST",
            }
        ):
            raise ValueError("Unsupported source-reviewed category")
        if (
            "woman_reserved" in review
            and not unverified_category
            and not isinstance(review["woman_reserved"], bool)
        ):
            raise ValueError("Source-reviewed woman marker must be boolean")
        if (
            "category_source_normalized" in review
            and "category_source_raw" not in review
        ):
            raise ValueError(
                "Reviewed category normalization lacks literal source text"
            )
        if "category_source_raw" in review:
            category_label = review["category_source_raw"]
            if "category_source_normalized" in review:
                normalization = {
                    "Gonoral": "General",
                    "Gonoral Woman": "General Woman",
                }.get(category_label)
                if (
                    normalization is None
                    or review["category_source_normalized"] != normalization
                ):
                    raise ValueError("Unsupported manual source-category normalization")
                category_label = normalization
            caste, woman = category_for(category_label)
            expected_caste = review.get("caste_reservation")
            if expected_caste == "UR":
                expected_caste = "NONE"
            if (
                caste is None
                or woman is None
                or (expected_caste is not None and caste != expected_caste)
                or ("woman_reserved" in review and woman != review["woman_reserved"])
            ):
                raise ValueError(
                    "Reviewed category disagrees with the shared category parser"
                )
            review["caste_reservation"] = caste
            review["woman_reserved"] = woman
        reviews[key] = (review, path)
    seen = set()
    for record in records:
        key = (
            record["source_sha256"],
            int(record["source_page"]),
            int(record["source_row_on_page"]),
        )
        record["source_office_review_status"] = "not_requested"
        if key not in reviews:
            continue
        seen.add(key)
        review, path = reviews[key]
        flags = set(record["quality_flags"].split(";")) - {""}
        record["source_office_review_sha256"] = checksum(path)
        record["source_office_review_file"] = path.name
        if any(
            field not in record
            or (
                not pd.isna(record[field])
                if value is None
                else pd.isna(record[field]) or record[field] != value
            )
            for field, value in review["expected_raw"].items()
        ):
            record["source_office_review_status"] = "precondition_failed"
            flags.add("source_office_review_precondition_failed")
            counts["precondition_failed"] += 1
        else:
            record["office_before_source_review"] = record.get("office_normalized")
            record["tier_before_source_review"] = record.get("tier")
            record["office_normalized"] = review["office_normalized"]
            record["tier"] = office_tier(review["office_normalized"], "")
            if "body_within_page" in review:
                record["body_before_source_review"] = record["body_within_page"]
                record["body_within_page"] = review["body_within_page"]
                flags.add("body_source_reviewed_raw_preserved")
            if "caste_reservation" in review:
                record["caste_before_source_review"] = record["caste_reservation"]
                record["caste_reservation"] = review["caste_reservation"]
            if "woman_reserved" in review:
                record["woman_before_source_review"] = record["woman_reserved"]
                record["woman_reserved"] = review["woman_reserved"]
            if "category_source_raw" in review:
                record["category_source_review_raw"] = review["category_source_raw"]
                flags.add("category_source_reviewed_raw_preserved")
                flags.discard("category_unresolved")
                flags.discard("column_category_unresolved")
            flags.discard("office_unresolved")
            if review["office_normalized"] == "SARPANCH":
                flags.discard("ward_missing")
            if review.get("row_alignment_reviewed") is True:
                flags.discard("column_alignment_failed")
            flags.add("office_source_reviewed_raw_preserved")
            if review.get("review_kind") == "same_page_gp_notification":
                context = review["notification_context"]
                for field in (
                    "district_source_raw",
                    "block_source_raw",
                    "body_source_raw",
                    "heading_page",
                ):
                    record[f"gp_notification_{field}"] = context[field]
                record["gp_category_authority"] = review["category_authority"]
                record["gp_category_annotation_description"] = review.get(
                    "category_annotation_description"
                )
                flags.difference_update(
                    {
                        "mixed_notification_context_requires_review",
                        "samiti_or_empty_page_source_review_required",
                        "incoming_body_context_unvalidated",
                    }
                )
                flags.add("gp_notification_context_source_reviewed")
                if review["category_authority"] == "handwritten_amendment_unverified":
                    flags.update(
                        {
                            "category_unresolved",
                            "handwritten_category_amendment_requires_authority_review",
                        }
                    )
            for identity in ("winner", "relation"):
                field = f"{identity}_source_raw"
                if field in review:
                    record[f"{identity}_source_review_raw"] = review[field]
                    flags.add(f"{identity}_source_reviewed_raw_preserved")
            record["source_office_review_status"] = "applied"
            counts["applied"] += 1
        record["quality_flags"] = ";".join(sorted(flags))
    counts["reviewed_rows_absent_from_export"] = len(set(reviews) - seen)
    for record in records:
        if (
            record["tier"] == office_tier("Sarpanch", "")
            and isinstance(record.get("ward_raw"), str)
            and anchor_ward(record["ward_raw"]) is not None
        ):
            flags = set(record["quality_flags"].split(";")) - {""}
            flags.add("gp_head_has_numbered_ward_source_review_required")
            record["quality_flags"] = ";".join(sorted(flags))
            counts["gp_head_has_numbered_ward"] += 1
    counts.update(apply_source_nonseat_reviews(records, OUT))
    return dict(counts)


def export(frame):
    save(
        OUT / "EXPORT_INCOMPLETE.json",
        {
            "status": "export_in_progress_or_failed",
            "warning": (
                "Derived outputs are not a complete reconciled export "
                "while this marker exists."
            ),
            "raw_ocr_responses_intact": True,
            "recovery": (
                "Rerun the cache-only export; "
                "successful completion removes this marker."
            ),
        },
    )
    import pandas as pd

    summary = _export_primary(frame)
    path = OUT / "seat_rows.parquet"
    if not path.exists():
        return summary
    table = pd.read_parquet(path)
    reports = {}
    anchor_reports = {}
    for source in frame:
        label = page_id(source)
        report_path = OUT / f"alignment_{label}.json"
        if report_path.exists():
            report = json.loads(report_path.read_text())
            primary = cached_response(source, label)
            if (
                primary
                and report["primary_response_sha256"] == primary[0]["response_sha256"]
            ):
                if report.get("aligned"):
                    column = cached_response(source, report["column_label"])
                    if (
                        not column
                        or column[0]["response_sha256"]
                        != report["column_response_sha256"]
                    ):
                        raise ValueError(f"Column provenance mismatch: {label}")
                reports[label] = report
        anchor_path = OUT / f"anchor_audit_{label}.json"
        if anchor_path.exists():
            anchor = json.loads(anchor_path.read_text())
            primary = cached_response(source, label)
            if (
                primary
                and anchor["primary_response_sha256"] == primary[0]["response_sha256"]
            ):
                audit = cached_response(source, anchor["audit_label"])
                if (
                    not audit
                    or anchor["audit_response_sha256"] != audit[0]["response_sha256"]
                ):
                    raise ValueError(f"Anchor response provenance mismatch: {label}")
                anchor_reports[label] = anchor
    records = []
    counts = Counter()
    anchor_counts = Counter()
    for record in table.to_dict("records"):
        report = reports.get(page_id(record), {})
        status = report.get("status", "column_pass_pending")
        flags = set(filter(None, str(record.get("quality_flags") or "").split(";")))
        record["category_primary_raw"] = record.get("category_raw")
        record["category_column_raw"] = None
        record["column_status"] = status
        record["column_response_sha256"] = report.get("column_response_sha256")
        if report.get("aligned"):
            corrections = {
                item["source_row_on_page"]: item
                for item in report["category_overrides"]
            }
            correction = corrections[int(record["source_row_on_page"])]
            record["category_column_raw"] = correction["column_raw"]
            if correction["recognized"]:
                caste, woman = category_for(correction["column_raw"])
                record.update(
                    category_raw=correction["column_raw"],
                    caste_reservation=caste,
                    woman_reserved=woman,
                )
                flags.discard("category_unresolved")
                if category_for(correction["primary_raw"]) != (caste, woman):
                    flags.add("category_reconciled_by_aligned_column_pass")
                    counts["category_values_reconciled"] += 1
            else:
                flags.add("column_category_unresolved")
        else:
            flags.add(status)
        anchor = anchor_reports.get(page_id(record), {})
        evidence = next(
            (
                item
                for item in anchor.get("corrections", [])
                if item["source_row_on_page"] == int(record["source_row_on_page"])
            ),
            None,
        )
        record["anchor_status"] = (
            "accepted" if evidence else "unresolved" if anchor else "not_requested"
        )
        record["anchor_response_sha256"] = anchor.get("audit_response_sha256")
        record["office_anchor_raw"] = evidence["office_raw"] if evidence else None
        record["category_anchor_raw"] = evidence["category_raw"] if evidence else None
        if evidence:
            caste, woman = category_for(evidence["category_raw"])
            record.update(
                category_raw=evidence["category_raw"],
                caste_reservation=caste,
                woman_reserved=woman,
                office_normalized=normalized_office(evidence["office_raw"]),
                tier=office_tier(evidence["office_raw"], record["family"]),
            )
            flags.difference_update(
                {
                    "office_unresolved",
                    "category_unresolved",
                    "column_category_unresolved",
                    "column_alignment_failed",
                    "column_pass_pending",
                }
            )
            flags.add("office_category_corroborated_by_unique_name_anchor")
            if evidence["category_recovered"]:
                flags.add("category_recovered_by_anchor_audit")
                anchor_counts["category_values_recovered"] += 1
            anchor_counts["rows_with_accepted_anchors"] += 1
        record["quality_flags"] = ";".join(sorted(flags))
        records.append(record)
    from local_elections.tools.source_context_reviews import (
        apply_source_context_reviews,
    )
    from local_elections.tools.source_gp_fragment_context_reviews import (
        apply_source_gp_fragment_context_reviews,
    )
    from local_elections.tools.source_identity_reviews import (
        apply_source_identity_reviews,
    )
    from local_elections.tools.source_samiti_reviews import (
        apply_source_samiti_reviews,
    )

    source_office_reviews = apply_source_office_reviews(records)
    source_samiti_reviews = apply_source_samiti_reviews(records, OUT)
    source_context_reviews = apply_source_context_reviews(records, OUT)
    from local_elections.tools.source_district_reviews import (
        apply_source_district_reviews,
    )

    source_context_reviews["district_member_reviews"] = apply_source_district_reviews(
        records, OUT
    )
    source_identity_reviews = apply_source_identity_reviews(records, OUT)
    source_context_reviews["gp_fragment_reviews"] = (
        apply_source_gp_fragment_context_reviews(records, OUT)
    )
    anchor_review_counts = Counter()
    source_review_flags = {
        "office_source_reviewed_raw_preserved",
        "category_source_reviewed_raw_preserved",
    }
    for record in records:
        flags = set(filter(None, record["quality_flags"].split(";")))
        if "office_category_corroborated_by_unique_name_anchor" not in flags:
            continue
        if "source_confirmed_nonseat_raw_preserved" in flags:
            anchor_review_counts["source_confirmed_nonseat"] += 1
        elif source_review_flags.issubset(flags):
            anchor_review_counts["office_and_category_source_reviewed"] += 1
        else:
            flags.add("anchor_corroboration_requires_source_review")
            anchor_review_counts["source_review_required"] += 1
        record["quality_flags"] = ";".join(sorted(flags))
    if records:
        table = pd.DataFrame.from_records(records)
        table["woman_reserved"] = pd.array(table["woman_reserved"], dtype="boolean")
        for field in ("ward", "source_page", "source_row_on_page"):
            table[field] = pd.array(table[field], dtype="Int64")
        duplicates = table.duplicated(
            ["source_sha256", "source_page", "body_within_page", "ward", "tier"],
            keep=False,
        )
        for record, duplicate in zip(records, duplicates, strict=True):
            flags = set(record["quality_flags"].split(";")) - {
                "",
                "duplicate_seat_key_within_page",
            }
            if duplicate:
                flags.add("duplicate_seat_key_within_page")
            record["quality_flags"] = ";".join(sorted(flags))
        table["quality_flags"] = [record["quality_flags"] for record in records]
        table.to_parquet(path, index=False)
        table.to_csv(OUT / "review_queue.csv", index=False)
    counts.update(report["status"] for report in reports.values())
    summary = (summary or {}) | {"column_reconciliation": dict(counts)}
    anchor_counts.update(report["status"] for report in anchor_reports.values())
    summary["anchor_corroboration"] = dict(anchor_counts)
    summary["anchor_source_review"] = dict(anchor_review_counts)
    summary["anchor_agreement_certifies_source_accuracy"] = False
    summary["source_office_reviews"] = source_office_reviews
    summary["source_identity_reviews"] = source_identity_reviews
    summary["source_samiti_reviews"] = source_samiti_reviews
    summary["source_context_reviews"] = source_context_reviews
    summary["quality_flags_before_reconciliation"] = summary.get("quality_flags", {})
    summary["quality_flags"] = dict(
        Counter(
            flag
            for record in records
            for flag in record["quality_flags"].split(";")
            if flag
        )
    )
    save(OUT / "column_summary.json", summary)
    save(OUT / "summary.json", summary)
    (OUT / "SOURCE_REVIEW_CATEGORY_BLOCKER.json").unlink(missing_ok=True)
    (OUT / "EXPORT_INCOMPLETE.json").unlink(missing_ok=True)
    return summary


@command("ocr", state="Haryana", artifact="historical_seat_observations")
def main():
    from pathlib import Path

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--stage",
        choices=("review", "production", "export", "reconcile", "corroborate"),
        required=True,
    )
    parser.add_argument("--workers", type=int, choices=range(1, 17), default=8)
    parser.add_argument("--limit", type=int, default=32)
    parser.add_argument(
        "--pages", help="Comma-separated page IDs for a targeted source-quality pass"
    )
    parser.add_argument(
        "--wait-for-lock",
        action="store_true",
        help="Wait for the active run instead of writing concurrently",
    )
    parser.add_argument(
        "--reasoning-effort",
        choices=("low", "medium", "high"),
        help="Override effort for explicitly selected recovery pages",
    )
    parser.add_argument(
        "--refresh-primary",
        action="store_true",
        help="Re-read explicitly selected pages; retain prior response caches",
    )
    parser.add_argument(
        "--refresh-columns",
        action="store_true",
        help="Re-read office/category crops for explicitly selected pages",
    )
    args = parser.parse_args()
    if args.reasoning_effort and (
        not args.pages or args.stage not in ("review", "production", "corroborate")
    ):
        parser.error(
            "--reasoning-effort requires explicit --pages and a submission stage"
        )
    if (args.refresh_primary or args.refresh_columns) and (
        not args.pages or args.stage not in ("review", "production")
    ):
        parser.error("Refresh options require explicit --pages and a submission stage")
    plan_path = OUT / "plan.json"
    plan = json.loads(plan_path.read_text())
    frame_path = BASE / "hosted_rollout" / "page_frame.csv"
    if (
        checksum(frame_path)
        != "449ef9dcd2ec0ea0aee9564bb614345ea30d4f11ae24c7481b2e681cc8785ce8"
    ):
        raise ValueError("Page frame changed")
    frame = list(csv.DictReader(frame_path.open()))
    with (OUT / "submission.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | (0 if args.wait_for_lock else fcntl.LOCK_NB))
        if args.stage == "export":
            print(json.dumps(export(frame)), flush=True)
            return
        if args.stage in ("production", "corroborate"):
            gate = json.loads((OUT / "review_gate.json").read_text())
            if not (
                plan.get("production_authorized_with_review_queue") is True
                and gate.get("scope") == "raw_transcription_only"
                and gate.get("plan_sha256") == checksum(plan_path)
            ):
                raise ValueError(
                    "Production staging gate is not authorized for this plan"
                )
        sources = frame
        if args.pages:
            requested = set(args.pages.split(","))
            sources = [row for row in frame if page_id(row) in requested]
            if {page_id(row) for row in sources} != requested:
                raise ValueError("Requested page absent from immutable frame")
        elif args.stage == "review":
            requested = {
                (row["source_sha256"], int(row["source_page"]))
                for row in plan["review_pages"]
            }
            sources = [
                row
                for row in frame
                if (row["source_sha256"], int(row["source_page"])) in requested
            ]
        elif args.stage == "corroborate":
            sources = [
                row
                for row in sources
                if (OUT / f"alignment_{page_id(row)}.json").exists()
                and json.loads(
                    (OUT / f"alignment_{page_id(row)}.json").read_text()
                ).get("status")
                == "column_alignment_failed"
            ]

        def pending(source):
            if args.stage == "corroborate":
                path = OUT / f"anchor_audit_{page_id(source)}.json"
                if not path.exists():
                    return True
                primary = cached_response(source, page_id(source))
                report = json.loads(path.read_text())
                return (
                    report.get("audit_version") != 3
                    or primary is None
                    or report.get("primary_response_sha256")
                    != primary[0]["response_sha256"]
                )
            path = OUT / f"alignment_{page_id(source)}.json"
            return (
                not path.exists()
                or json.loads(path.read_text()).get("alignment_version") != 5
            )

        sources = [
            row
            for row in sources
            if args.refresh_primary or args.refresh_columns or pending(row)
        ]
        if args.refresh_primary or args.refresh_columns:
            sources = [
                row
                | {
                    "refresh_primary": args.refresh_primary,
                    "refresh_columns": args.refresh_columns,
                }
                for row in sources
            ]
        if args.reasoning_effort:
            sources = [
                row | {"reasoning_effort": args.reasoning_effort} for row in sources
            ]
        if args.limit > 0:
            sources = sources[: args.limit]
        checked = set()
        for row in sources:
            if row["source_sha256"] not in checked:
                if checksum(pilot.BASE / row["source_path"]) != row["source_sha256"]:
                    raise ValueError("Source PDF checksum mismatch")
                checked.add(row["source_sha256"])
        key = None
        if args.stage != "reconcile":
            config = Path.home() / ".config/local_elections/haryana_ocr.toml"
            key = tomllib.loads(config.read_text())["meta"]["api_key"]
        print(
            json.dumps(
                {"stage": args.stage, "pages_pending": len(sources), "cap_usd": 10}
            ),
            flush=True,
        )
        failures = []
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            if args.stage == "corroborate":
                futures = {
                    pool.submit(corroborate_page, source, key): source
                    for source in sources
                }
            else:
                futures = {
                    pool.submit(
                        read_page, source, key, cache_only=args.stage == "reconcile"
                    ): source
                    for source in sources
                }
            for completed, future in enumerate(as_completed(futures), 1):
                source = futures[future]
                try:
                    result = future.result()
                    print(
                        json.dumps(
                            {
                                "completed": completed,
                                "label": page_id(source),
                                "rows": result["rows"],
                                "column_status": result["column_status"],
                                "primary_usage_priced_usd": result["usage_priced_usd"],
                            }
                        ),
                        flush=True,
                    )
                except Exception as exc:
                    failure = {
                        "label": page_id(source),
                        "error": type(exc).__name__,
                        "reason": str(exc)[:240],
                    }
                    failures.append(failure)
                    print(json.dumps(failure), flush=True)
                if completed % 32 == 0 and args.stage != "reconcile":
                    print(json.dumps({"checkpoint": export(frame)}), flush=True)
        summary = export(frame) | {"stage_failures": failures}
        save(OUT / f"{args.stage}_result.json", summary)
        print(json.dumps(summary), flush=True)
        if failures:
            raise SystemExit(1)


if __name__ == "__main__":
    main()
