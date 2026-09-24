"""Read candidate samiti records from saved generic Surya HTML.

Generated HTML column positions are not source geometry. A strict row grammar
requires an explicit ward, two name cells and a recognized category, and keeps
all original cells and span attributes. It never expands generated rowspan
attributes or supplies a ward from a counter. Outputs require source review.
"""

import argparse
import csv
import json
import re
from html.parser import HTMLParser
from pathlib import Path

from local_elections.common.runlog import command
from local_elections.paths import ROOT
from local_elections.tools.historical_harvest import checksum
from local_elections.tools.parse_haryana_gazettes import candidate_category

BASE = ROOT / "data/source_search/national/haryana/early_cycles/gp_ps_benchmark"


class TableReader(HTMLParser):
    def __init__(self):
        super().__init__()
        self.rows = []
        self.table = 0
        self.depth = 0
        self.row = None
        self.cell = None
        self.unclosed = False

    def handle_starttag(self, tag, attrs):
        if tag == "table":
            self.table += 1
            self.depth += 1
        elif tag == "tr" and self.depth:
            self.row = {"table": self.table, "cells": []}
        elif tag in {"td", "th"} and self.row is not None:
            self.cell = {"tag": tag, "attrs": dict(attrs), "text": ""}
        elif tag == "br" and self.cell is not None:
            self.cell["text"] += " "

    def handle_data(self, data):
        if self.cell is not None:
            self.cell["text"] += data

    def handle_endtag(self, tag):
        if tag in {"td", "th"} and self.cell is not None:
            self.cell["text"] = " ".join(self.cell["text"].split())
            if self.row is not None:
                self.row["cells"].append(self.cell)
            self.cell = None
        elif tag == "tr" and self.row is not None:
            self.rows.append(self.row)
            self.row = None
        elif tag == "table":
            self.depth -= 1


def ward_text(raw):
    match = re.fullmatch(r"\s*([0-9]{1,2})\s*\*?\s*", raw)
    return match[1] if match and int(match[1]) > 0 else None


def parse_samiti(payload, initial_body=None):
    if payload["tokens"] >= payload["max_tokens"]:
        return [], [{"status": "generation_limit_reached"}]
    reader = TableReader()
    reader.feed(payload["text"])
    if reader.depth or reader.row is not None or reader.cell is not None:
        return [], [{"status": "incomplete_html_table"}]
    body, previous_table = initial_body, None
    records, issues = [], []
    for index, row in enumerate(reader.rows, 1):
        if previous_table is not None and row["table"] != previous_table:
            body = None
        previous_table = row["table"]
        if any(c["tag"] == "th" for c in row["cells"]):
            continue
        values = [c["text"] for c in row["cells"] if c["text"]]
        if not values:
            continue
        if (
            len(values) == 2
            and ward_text(values[0])
            and re.search("[A-Za-z]", values[1])
        ):
            body = values[1]
            continue
        if len(values) >= 2 and values[-1].upper() in {"WOMAN", "WOMEN"}:
            values = [*values[:-2], " ".join(values[-2:])]
        category = candidate_category(values[-1])
        if len(values) < 4 or category == (None, None):
            issues.append({"source_row": index, "status": "unsupported_row", **row})
            continue
        ward, winner, relation, raw_category = values[-4:]
        prefix = values[:-4]
        if ward_text(ward) is None or any(
            not re.search("[A-Za-z]", value) for value in (winner, relation)
        ):
            issues.append({"source_row": index, "status": "row_grammar_failed", **row})
            continue
        if prefix:
            names = [value for value in prefix if re.search("[A-Za-z]", value)]
            if len(names) != 1 or len(prefix) > 2:
                issues.append({"source_row": index, "status": "ambiguous_body", **row})
                body = None
                continue
            body = names[0]
        flags = ["table_scope_from_source_index", "model_reading_unvalidated"]
        if body is None:
            flags.append("body_missing")
        if any(c["attrs"].get("rowspan", "1") != "1" for c in row["cells"]):
            flags.append("generated_rowspan_not_expanded")
        records.append(
            {
                "source_row": index,
                "body_raw": body,
                "ward_raw": ward,
                "ward": int(ward_text(ward)),
                "winner_raw": winner,
                "relation_raw": relation,
                "category_raw": raw_category,
                "caste_candidate": category[0],
                "woman_candidate": category[1],
                "quality_flags": ";".join(flags),
                "raw_cells": row["cells"],
            }
        )
    return records, issues


def score_rows(predictions, labels):
    """Align reviewed page rows in printed order; changed row counts fail this score."""
    if len(predictions) != len(labels):
        return {
            "expected_rows": len(labels),
            "predicted_rows": len(predictions),
            "status": "row_count_mismatch; positional_field_score_not_computed",
        }
    correct_ward = correct_category = correct_pair = correct_body = 0
    body_expected = 0
    for prediction, label in zip(predictions, labels, strict=True):
        ward_ok = prediction["ward"] == label["ward"]
        category_ok = (
            prediction["caste_candidate"],
            prediction["woman_candidate"],
        ) == (label["caste"], label["woman"])
        correct_ward += ward_ok
        correct_category += category_ok
        correct_pair += ward_ok and category_ok
        if not label["body_continued_from_previous_page"]:
            body_expected += 1
            correct_body += re.sub(
                r"[^A-Z0-9]", "", (prediction["body_raw"] or "").upper()
            ) == re.sub(r"[^A-Z0-9]", "", label["body"].upper())
    return {
        "expected_rows": len(labels),
        "predicted_rows": len(predictions),
        "correct_ward": correct_ward,
        "correct_category": correct_category,
        "correct_ward_category_pair": correct_pair,
        "body_checkable_within_page": body_expected,
        "correct_body_within_page": correct_body,
        "scope": "Printed-order agreement; names and incoming body context unscored",
    }


@command("parse", state="Haryana", vintage="2000_surya_samiti")
def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=BASE)
    parser.add_argument("--split", choices=["diagnose", "validate"], default="diagnose")
    args = parser.parse_args()
    base = args.source
    plan = json.loads((base / "split_plan.json").read_text())
    labels_path = base / f"labels_{args.split}.json"
    labels = json.loads(labels_path.read_text())
    all_rows, all_issues, scores, inputs = [], [], {}, [Path(__file__), labels_path]
    for source in plan["frame"]:
        if source["split"] != args.split or source["family"] != "block_member":
            continue
        path = base / f"surya_{source['label'].lower()}.json"
        payload = json.loads(path.read_text())
        if (payload["source_sha256"], payload["source_page"]) != (
            source["sha256"],
            source["source_page"],
        ):
            raise ValueError("OCR source identity changed")
        rows, issues = parse_samiti(payload)
        matching = [r for r in labels if r["source_sha256"] == source["sha256"]]
        scores[source["label"]] = score_rows(rows, matching)
        identity = {
            "source_sha256": source["sha256"],
            "source_page": source["source_page"],
            "district_index": source["label"],
            "response_sha256": checksum(path),
        }
        all_rows.extend(r | identity for r in rows)
        all_issues.extend(r | identity for r in issues)
        inputs.append(path)
    for name, data in [
        ("candidates", all_rows),
        ("issues", all_issues),
        ("scores", scores),
    ]:
        (base / f"samiti_{args.split}_{name}.json").write_text(
            json.dumps(data, indent=2) + "\n"
        )
    with (base / f"samiti_{args.split}_inputs.csv").open("w") as stream:
        writer = csv.writer(stream)
        writer.writerow(["path", "sha256"])
        writer.writerows((str(p), checksum(p)) for p in inputs)
    print(json.dumps(scores))


if __name__ == "__main__":
    main()
