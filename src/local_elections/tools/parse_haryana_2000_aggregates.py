"""Parse the four archived Haryana March 2000 aggregate tables.

Run with python -m local_elections.tools.parse_haryana_2000_aggregates
--source-root PATH. Requires Poppler's pdftotext. Outputs are aggregate
observations, never individual reservation assignments.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import re
import subprocess
import tempfile
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from local_elections.common.runlog import command

RESERVATION = (
    "total_seats",
    "sc_other_than_sc_women",
    "sc_women",
    "sc_total",
    "women_other_than_sc_women",
    "bc",
    "reserved_total",
    "unreserved",
    "grand_total",
)
SOURCES = (
    {
        "id": "panch_reservation",
        "sha256": "e9ded2e062d021010d0b9ccb1924b5f0a74f7bc3306e8499c4d9710eff085991",
        "metrics": ("gram_panchayats", *RESERVATION),
        "header": "FOR PANCHES",
        "pages": 7,
    },
    {
        "id": "samiti_reservation",
        "sha256": "cb59411d52213628096fb79eff6b48e3cca77204440bdd0ee6b1e8c8810ba69e",
        "metrics": RESERVATION,
        "header": "FOR PANCHAYAT SAMITI",
        "pages": 7,
    },
    {
        "id": "samiti_election_statistics",
        "sha256": "374ad6530dcbb7f259347963df3895e707d4d345b0cc9b4a03823c7846497e91",
        "metrics": (
            "total_wards",
            "members_elected_unopposed",
            "seats_contested",
            "contesting_candidates",
            "voters_all_wards",
            "poll_percentage_contested_seats",
        ),
        "header": "POLL PERCENTAGE",
        "pages": 6,
    },
    {
        "id": "samiti_women_winners",
        "sha256": "92059fd0ff90728885a993ed7bedd22ceb1df8a22a13361e1edc639b9a7d293d",
        "metrics": (
            "sc_women_on_sc_women_seats",
            "sc_women_on_unreserved_seats",
            "sc_women_on_general_women_seats",
            "sc_women_on_sc_nonwomen_seats",
            "sc_women_total",
            "bc_women_on_unreserved_seats",
            "bc_women_on_general_women_seats",
            "bc_women_on_bc_seats",
            "bc_women_total",
            "general_women_on_unreserved_seats",
            "general_women_on_women_seats",
            "general_women_total",
        ),
        "header": "WOMEN CANDIDATES ELECTED",
        "pages": 1,
    },
)
DISTRICTS = {
    "AMBALA",
    "BHIWANI",
    "FATEHABAD",
    "FARIDABAD",
    "GURGAON",
    "HISAR",
    "JHAJJAR",
    "JIND",
    "KAITHAL",
    "KARNAL",
    "KURUKSHETRA",
    "MAHENDERGARH",
    "MAHENDERGARH AT NARNAUL",
    "PANIPAT",
    "PANCHKULA",
    "ROHTAK",
    "REWARI",
    "SONEPAT",
    "SIRSA",
    "YAMUNA NAGAR",
}
NUMBER = re.compile(r"(?:[0-9]+(?:\.[0-9]+)?|-+)$")
SERIAL = re.compile(r"^\s*([0-9]+)\.\s*")
COLUMN_HEADER = re.compile(r"^(?:\(?[0-9]+\)?\.?\s*)+$")


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=True, indent=2) + "\n")


def write_gzip(path, data):
    path.write_bytes(gzip.compress(data, mtime=0))
    return {
        "path": path.name,
        "sha256": sha256(path.read_bytes()),
        "uncompressed_sha256": sha256(data),
        "uncompressed_bytes": len(data),
    }


def line_ref(page, number, text):
    return {"page": page, "line": number, "text": text}


def parse_layout(source, layout):
    pages = layout.split("\f")
    if not pages[-1].strip():
        pages.pop()
    heading = " ".join(pages[0].split()).upper()
    if source["header"] not in heading or "MARCH, 2000" not in heading:
        raise ValueError(f"Unexpected source heading: {source['id']}")
    if len(pages) != source["pages"]:
        raise ValueError(f"Unexpected page count: {source['id']}")
    rows, holds = [], []
    district = None
    body_started = False
    state_pending = False
    pending = []
    pending_serial = None
    women = source["id"] == "samiti_women_winners"
    metrics = source["metrics"]
    for page, text in enumerate(pages, 1):
        continuation_row = None
        for line_number, line in enumerate(text.splitlines(), 1):
            stripped = line.strip()
            if not stripped:
                continue
            previous_continuation = continuation_row
            continuation_row = None
            ref = line_ref(page, line_number, line)
            if COLUMN_HEADER.fullmatch(stripped) and not (
                women and body_started and SERIAL.fullmatch(line)
            ):
                continue
            if not women and stripped in DISTRICTS:
                district = {"raw": stripped, "source": ref}
                body_started = True
                pending = []
                continue
            tokens = list(re.finditer(r"\S+", line))
            tail = []
            for token in reversed(tokens):
                if not NUMBER.fullmatch(token.group()):
                    break
                tail.insert(0, token)
            if len(tail) == len(metrics):
                prefix = line[: tail[0].start()]
                serial_match = SERIAL.match(prefix)
                label = SERIAL.sub("", prefix).strip()
                if women:
                    serial = (
                        int(serial_match.group(1)) if serial_match else pending_serial
                    )
                    if not body_started and serial != 1:
                        continue
                    body_started = True
                    level = "state" if label.upper() == "TOTAL" else "district"
                    name = " ".join(
                        [item["text"].strip() for item in pending] + [label]
                    )
                    district_raw = None if level == "state" else name
                else:
                    if not body_started:
                        continue
                    serial = int(serial_match.group(1)) if serial_match else None
                    if state_pending or "STATE" in label.upper():
                        level = "state"
                    elif label.upper() == "TOTAL":
                        level = "district"
                    elif serial is not None:
                        level = "block"
                    else:
                        holds.append({**ref, "reason": "unresolved_row_level"})
                        continue
                    name = label
                    district_raw = district["raw"] if level != "state" else None
                cells, flags = [], []
                for metric, token in zip(metrics, tail, strict=True):
                    raw = token.group()
                    reason = None
                    if re.fullmatch(r"-+", raw):
                        value = None
                        reason = "source_dash_semantics_unresolved"
                    elif len(raw) > 1 and raw.startswith("0") and "." not in raw:
                        value = None
                        reason = "leading_zero_numeric_token"
                    elif "." in raw:
                        value = float(raw)
                        if metric != "poll_percentage_contested_seats":
                            reason = "unexpected_decimal_in_count"
                            value = None
                    else:
                        value = int(raw)
                    if reason:
                        flags.append(f"{metric}:{reason}")
                    cells.append(
                        {
                            "metric": metric,
                            "raw": raw,
                            "value": value,
                            "unit": "percent"
                            if metric.startswith("poll_percentage")
                            else "count",
                            "hold": reason,
                            "page": page,
                            "line": line_number,
                            "column_start": token.start() + 1,
                            "column_end_exclusive": token.end() + 1,
                        }
                    )
                row = {
                    "source_id": source["id"],
                    "source_sha256": source["sha256"],
                    "observation_id": f"{source['sha256']}:p{page}:l{line_number}",
                    "election_year": 2000,
                    "election_month": 3,
                    "geographic_level": level,
                    "district_raw": district_raw,
                    "district_heading_source": district
                    if not women and level != "state"
                    else None,
                    "block_raw": name if level == "block" else None,
                    "source_serial": serial,
                    "label_raw": name,
                    "source_lines": [*pending, ref],
                    "cells": cells,
                    "flags": flags,
                    "assignment_usable": False,
                    "aggregate_usable": False,
                    "review_status": "pending_independent_source_fidelity_review",
                }
                rows.append(row)
                continuation_row = row if level == "block" else None
                pending = []
                pending_serial = None
                continue
            if not body_started:
                continue
            if "GRAND" in stripped.upper() or (
                state_pending
                and stripped.upper() in {"TOTAL OF", "THE STATE", "OF THE STATE"}
            ):
                state_pending = True
                if rows and rows[-1]["geographic_level"] == "state":
                    rows[-1]["source_lines"].append(ref)
                else:
                    pending.append(ref)
                continue
            if women and SERIAL.fullmatch(line):
                pending_serial = int(SERIAL.fullmatch(line).group(1))
                continue
            if (
                not tail
                and re.fullmatch(r"[A-Za-z][A-Za-z -]*", stripped)
                and previous_continuation is not None
                and not women
                and not state_pending
            ):
                previous_continuation["block_raw"] += " " + stripped
                previous_continuation["label_raw"] += " " + stripped
                previous_continuation["source_lines"].append(ref)
                continuation_row = previous_continuation
                continue
            if women and not tail and stripped == "Yamuna":
                pending.append(ref)
                continue
            holds.append(
                {
                    **ref,
                    "reason": "unparsed_body_line",
                    "numeric_suffix_length": len(tail),
                }
            )
    if pending and not (rows and rows[-1]["geographic_level"] == "state"):
        holds.extend({**item, "reason": "unattached_label"} for item in pending)
    return rows, holds, len(pages)


def arithmetic_observations(rows, source):
    findings = []
    for row in rows:
        values = {cell["metric"]: cell["value"] for cell in row["cells"]}
        equations = []
        if source["id"].endswith("_reservation"):
            equations = [
                ("sc_total", ("sc_other_than_sc_women", "sc_women")),
                ("reserved_total", ("sc_total", "women_other_than_sc_women", "bc")),
                ("grand_total", ("reserved_total", "unreserved")),
                ("total_seats", ("grand_total",)),
            ]
        elif source["id"] == "samiti_election_statistics":
            equations = [
                ("total_wards", ("members_elected_unopposed", "seats_contested"))
            ]
        else:
            equations = [
                ("sc_women_total", source["metrics"][:4]),
                ("bc_women_total", source["metrics"][5:8]),
                ("general_women_total", source["metrics"][9:11]),
            ]
        for reported, components in equations:
            if values[reported] is None or any(
                values[key] is None for key in components
            ):
                continue
            summed = sum(values[key] for key in components)
            if values[reported] != summed:
                findings.append(
                    {
                        "observation_id": row["observation_id"],
                        "metric": reported,
                        "reported": values[reported],
                        "component_sum": summed,
                        "components": components,
                        "source_values_modified": False,
                    }
                )
    return findings


@command("parse", state="Haryana", artifact="historical_aggregate_observations")
def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, required=True)
    args = parser.parse_args()
    root = args.source_root.resolve()
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    output = root / "parsed_aggregates" / stamp
    output.mkdir(parents=True, exist_ok=False)
    receipt = {
        "created_utc": datetime.now(UTC).isoformat(),
        "parser_sha256": sha256(Path(__file__).read_bytes()),
        "format_version": 1,
        "source_root": str(root),
        "coordinate_system": "Poppler layout text; 1-based page/line/character columns",
        "assignment_usable": False,
        "aggregate_usable": False,
        "new_paid_api_cost_usd": 0,
        "sources": [],
        "cautions": [
            "Aggregate counts are not individual seat assignments.",
            "Historical names remain as printed; no modern geography crosswalk.",
            "Source dashes and leading-zero integers remain unresolved.",
            "Candidate caste and seat reservation are separate axes.",
            "Voters are registered voters for all wards, not votes cast.",
            "Poll percentages are reported, never summed or unweighted-averaged.",
            "Reported totals must not be used to reconstruct damaged seat records.",
            "Runtime extraction is not independent source-fidelity certification.",
        ],
    }
    with tempfile.TemporaryDirectory(prefix="haryana_2000_aggregates_") as temp:
        for source in SOURCES:
            raw_path = root / "raw" / f"{source['sha256']}.body.gz"
            raw = gzip.decompress(raw_path.read_bytes())
            if sha256(raw) != source["sha256"] or not raw.startswith(b"%PDF"):
                raise ValueError(f"Source integrity failure: {raw_path}")
            pdf = Path(temp) / f"{source['id']}.pdf"
            pdf.write_bytes(raw)
            result = subprocess.run(
                ["pdftotext", "-layout", "-enc", "UTF-8", str(pdf), "-"],
                check=True,
                capture_output=True,
                timeout=60,
            )
            layout = result.stdout.decode("utf-8")
            rows, holds, pages = parse_layout(source, layout)
            arithmetic = arithmetic_observations(rows, source)
            artifacts = {}
            for suffix, records in (
                ("observations", rows),
                ("unparsed_lines", holds),
                ("arithmetic_discrepancies", arithmetic),
            ):
                data = "".join(
                    json.dumps(item, ensure_ascii=True) + "\n" for item in records
                ).encode()
                artifacts[suffix] = write_gzip(
                    output / f"{source['id']}_{suffix}.jsonl.gz", data
                )
            artifacts["layout"] = write_gzip(
                output / f"{source['id']}_layout.txt.gz", result.stdout
            )
            item = {
                **source,
                "raw_path": str(raw_path.relative_to(root)),
                "pages": pages,
                "rows": len(rows),
                "cells": sum(len(row["cells"]) for row in rows),
                "levels": dict(Counter(row["geographic_level"] for row in rows)),
                "unparsed_body_lines": len(holds),
                "cell_holds": dict(
                    Counter(
                        cell["hold"]
                        for row in rows
                        for cell in row["cells"]
                        if cell["hold"]
                    )
                ),
                "arithmetic_discrepancies": len(arithmetic),
                "artifacts": artifacts,
                "pdftotext_stderr": result.stderr.decode("utf-8"),
                "reported_state_rows": [
                    {
                        cell["metric"]: {"raw": cell["raw"], "value": cell["value"]}
                        for cell in row["cells"]
                    }
                    for row in rows
                    if row["geographic_level"] == "state"
                ],
            }
            receipt["sources"].append(item)
            print(
                json.dumps(
                    {
                        key: item[key]
                        for key in (
                            "id",
                            "pages",
                            "rows",
                            "cells",
                            "levels",
                            "unparsed_body_lines",
                            "cell_holds",
                            "arithmetic_discrepancies",
                            "reported_state_rows",
                        )
                    }
                ),
                flush=True,
            )
    write_json(output / "receipt.json", receipt)
    print(json.dumps({"output": str(output), "new_paid_api_cost_usd": 0}), flush=True)


if __name__ == "__main__":
    main()
