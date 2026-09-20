"""Measure office-key and category recovery against checked gazette cells.

The frozen validation page was not used to alter the parser. Missing, duplicate
and wrong-key candidates count against recovery; confidence and fill rates are
not used as accuracy measures. These small checks cannot establish GP accuracy.
"""

import argparse
import ast
import csv
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd

from local_reservations.common.runlog import command
from local_reservations.paths import ROOT
from local_reservations.tools.historical_harvest import checksum

BASE = ROOT / "data/source_search/national/haryana/early_cycles"


def score_candidates(candidates, labels):
    keyed = defaultdict(list)
    for row in candidates:
        ward = re.sub(r"[\s*]", "", row["ward_raw"])
        if row["tier"] == "district_member" and ward.isdigit():
            keyed[(row["source_sha256"], int(row["source_page"]), int(ward))].append(
                row
            )
    scores = Counter(total=len(labels))
    by_category = defaultdict(Counter)
    for label in labels:
        key = (label["source_sha256"], int(label["source_page"]), int(label["ward"]))
        predictions = keyed[key]
        category = label["caste"] + ("_W" if label["woman"] == "true" else "")
        by_category[category]["total"] += 1
        if not predictions:
            status = "missing_office_key"
        elif len(predictions) > 1:
            status = "duplicate_office_key"
        else:
            prediction = predictions[0]
            caste, woman = prediction["caste_candidate"], prediction["woman_candidate"]
            if pd.isna(caste) or pd.isna(woman):
                status = "category_abstained"
            elif caste == label["caste"] and bool(woman) == (label["woman"] == "true"):
                status = "correct"
            else:
                status = "wrong_category"
        scores[status] += 1
        by_category[category][status] += 1
    return dict(scores) | {"by_category": {k: dict(v) for k, v in by_category.items()}}


@command("benchmark", state="Haryana", vintage="2000_gazettes")
def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=BASE)
    args = parser.parse_args()
    base = args.source
    folder = base / "benchmark"
    with (folder / "labels.csv").open() as stream:
        labels = list(csv.DictReader(stream))
    keys = [(r["source_sha256"], r["source_page"], r["ward"]) for r in labels]
    if len(set(keys)) != len(keys):
        raise ValueError("Benchmark labels must have unique printed office keys")
    parse_code = ROOT / "src/local_reservations/tools/parse_haryana_gazettes.py"
    plan = json.loads((folder / "split_plan.json").read_text())
    if plan["parser_sha256"] != checksum(parse_code):
        frozen = folder / "frozen_parser.py.txt"
        if checksum(frozen) != plan["parser_sha256"]:
            raise ValueError("Frozen parser bytes changed")
        protected = {
            "token",
            "lines_from_tsv",
            "find_header",
            "candidate_category",
            "parse_pages",
        }

        def extraction_nodes(path):
            return {
                node.name: ast.dump(node)
                for node in ast.parse(path.read_text()).body
                if isinstance(node, ast.FunctionDef) and node.name in protected
            }

        if extraction_nodes(frozen) != extraction_nodes(parse_code):
            raise ValueError("Extraction changed after validation freeze")
    candidates_path = base / "parsed/candidate_rows.parquet"
    candidates = pd.read_parquet(candidates_path).to_dict("records")
    report = {
        "scope": "Two diagnosis pages and one validation page; district members only",
        "scores": {
            split: score_candidates(
                candidates, [r for r in labels if r["split"] == split]
            )
            for split in ("diagnose", "validate")
        },
        "decision": "Do not promote OCR candidates to validated election records",
        "inputs": {
            str(p): checksum(p)
            for p in [
                parse_code,
                Path(__file__),
                candidates_path,
                folder / "labels.csv",
                folder / "split_plan.json",
            ]
        },
    }
    (folder / "scores.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report["scores"]))


if __name__ == "__main__":
    main()
