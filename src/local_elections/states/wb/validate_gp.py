"""Measure held-out visual transcriptions and build the GP review worklist.

The gold sample is intentionally small and records its reviewer and source.
Accuracy in this sample is not a population accuracy estimate. This command
reports errors; it never edits parsed values or treats missing rows as correct.
"""

import collections
import csv
import hashlib
import json

import pyarrow.parquet as pq

from local_elections.common.runlog import command
from local_elections.paths import ROOT

OUT = ROOT / "data/wb/derived"


def equivalent(a, b):
    if isinstance(a, str) and isinstance(b, str):
        return " ".join(a.upper().split()) == " ".join(b.upper().split())
    return a == b


@command("validate", state="West Bengal", source="gp_derived")
def main():
    tables = {
        dataset: pq.read_table(OUT / dataset / "gp_seats.parquet").to_pylist()
        for dataset in ["nadia_2008", "alipurduar_2018"]
    }
    candidates = pq.read_table(
        OUT / "alipurduar_2018/gp_candidates.parquet"
    ).to_pylist()
    gold = json.loads((OUT / "quality/heldout_gold.json").read_text())
    metrics, errors = collections.defaultdict(collections.Counter), []
    for expected in gold["rows"]:
        source = ROOT / expected["source_path"]
        if hashlib.sha256(source.read_bytes()).hexdigest() != expected["source_sha256"]:
            raise ValueError(f"Gold source changed: {source}")
        rows = [
            r
            for r in tables[expected["dataset"]]
            if all(
                r[k] == expected[k] for k in ["source_path", "source_page", "seat_no"]
            )
        ]
        metric = metrics[expected["dataset"]]
        metric["expected_rows"] += 1
        matched = len(rows) == 1
        metric["uniquely_matched_rows"] += int(matched)
        for field, value in expected["expected"].items():
            observed = rows[0].get(field) if matched else None
            correct = matched and equivalent(observed, value)
            metric["fields_checked"] += 1
            metric["fields_correct"] += int(correct)
            if not correct:
                errors.append(
                    {
                        "dataset": expected["dataset"],
                        "source_path": expected["source_path"],
                        "source_page": expected["source_page"],
                        "seat_no": expected["seat_no"],
                        "field": field,
                        "expected": value,
                        "observed": observed,
                        "match_count": len(rows),
                    }
                )
        if "candidate_votes" in expected:
            observed = [
                c["votes"]
                for c in candidates
                if matched and c["seat_row_id"] == rows[0]["row_id"]
            ]
            metric["candidate_votes_expected"] += len(expected["candidate_votes"])
            metric["candidate_rows_observed"] += len(observed)
            metric["candidate_votes_correct_by_position"] += sum(
                i < len(observed) and value == observed[i]
                for i, value in enumerate(expected["candidate_votes"])
            )
            if observed != expected["candidate_votes"]:
                errors.append(
                    {
                        "dataset": expected["dataset"],
                        "source_path": expected["source_path"],
                        "source_page": expected["source_page"],
                        "seat_no": expected["seat_no"],
                        "field": "candidate_votes_in_printed_order",
                        "expected": expected["candidate_votes"],
                        "observed": observed,
                    }
                )
    report = {
        "method": gold["method"],
        "metrics": dict(metrics),
        "errors": errors,
        "gold_rows": len(gold["rows"]),
        "manual_corrections_applied": 0,
    }
    controls = json.loads((OUT / "quality/block_controls.json").read_text())
    block_comparison = []
    seat_blocks = {r["row_id"]: r["block"] for r in tables["alipurduar_2018"]}
    for control in controls["rows"]:
        if (
            hashlib.sha256((ROOT / control["source_path"]).read_bytes()).hexdigest()
            != control["source_sha256"]
        ):
            raise ValueError("Block control source changed")
        seats = [r for r in tables["alipurduar_2018"] if r["block"] == control["block"]]
        observed_candidates = sum(
            seat_blocks[c["seat_row_id"]] == control["block"] for c in candidates
        )
        block_comparison.append(
            {
                **control,
                "parsed_seat_records": len(seats),
                "parsed_candidate_records": observed_candidates,
                "candidate_count_difference": observed_candidates
                - control["contesting_candidates"],
                "seat_count_minus_election_held": len(seats)
                - control["seats_election_held"],
                "seat_count_minus_total_seats": len(seats) - control["total_gp_seats"],
            }
        )
    report["block_controls"] = block_comparison
    report["block_comparison_caveat"] = (
        "Detail files may include uncontested rows while summary candidates refer "
        "to contested elections. Counts are not unique verified seat coverage. "
        "Differences require source review, not value imputation."
    )
    (OUT / "quality/validation.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    )
    queue = []
    for dataset, rows in tables.items():
        for row in rows:
            if row["quality_flags"]:
                queue.append(
                    {
                        "dataset": dataset,
                        "table": "gp_seats",
                        "row_id": row["row_id"],
                        "source_path": row["source_path"],
                        "source_page": row["source_page"],
                        "quality_flags": row["quality_flags"],
                    }
                )
    for row in candidates:
        if row["quality_flags"]:
            queue.append(
                {
                    "dataset": "alipurduar_2018",
                    "table": "gp_candidates",
                    "row_id": row["candidate_row_id"],
                    "source_path": row["source_path"],
                    "source_page": row["source_page"],
                    "quality_flags": row["quality_flags"],
                }
            )
    with (OUT / "quality/row_review_queue.csv").open("w", newline="") as out:
        writer = csv.DictWriter(
            out,
            fieldnames=[
                "dataset",
                "table",
                "row_id",
                "source_path",
                "source_page",
                "quality_flags",
            ],
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(queue)
    documents = json.loads((OUT / "native/index.json").read_text())
    nadia = {
        a["source_path"]: a
        for a in json.loads((OUT / "nadia_2008/document_audit.json").read_text())
    }
    alipurduar = collections.defaultdict(list)
    page_queue = []
    for a in json.loads((OUT / "alipurduar_2018/page_audit.json").read_text()):
        alipurduar[a["source_path"]].append(a)
        if a["status"] != "not_gp_detail" and (
            a["status"] != "parsed" or a["rejected_bands"]
        ):
            page_queue.append(
                {
                    "source_path": a["source_path"],
                    "source_page": a["source_page"],
                    "status": a["status"],
                    "unresolved_bands": len(a["rejected_bands"]),
                    "recovered_seats": a["seat_rows"],
                }
            )
    with (OUT / "quality/page_review_queue.csv").open("w", newline="") as out:
        writer = csv.DictWriter(
            out,
            fieldnames=[
                "source_path",
                "source_page",
                "status",
                "unresolved_bands",
                "recovered_seats",
            ],
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(page_queue)
    source_rows = collections.Counter(
        row["source_path"] for rows in tables.values() for row in rows
    )
    review_rows = collections.Counter(r["source_path"] for r in queue)
    for document in documents:
        path = document["source_path"]
        status = "semantic_parser_not_applied"
        if path in nadia:
            status = "nadia:" + nadia[path]["status"]
        elif path in alipurduar:
            status = ";".join(
                f"{k}:{v}"
                for k, v in sorted(
                    collections.Counter(a["status"] for a in alipurduar[path]).items()
                )
            )
        document.update(
            semantic_status=status,
            seat_records=source_rows[path],
            flagged_seat_or_candidate_records=review_rows[path],
        )
    with (OUT / "quality/document_coverage.csv").open("w", newline="") as out:
        writer = csv.DictWriter(out, fieldnames=list(documents[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(documents)
    schemas = {}
    for path in sorted(OUT.glob("*/*.parquet")):
        table = pq.read_table(path)
        schemas[str(path.relative_to(OUT))] = [
            {
                "field": field.name,
                "type": str(field.type),
                "null_count": table[field.name].null_count,
            }
            for field in table.schema
        ]
    (OUT / "quality/schemas.json").write_text(json.dumps(schemas, indent=2) + "\n")
    print(
        json.dumps(
            {"metrics": dict(metrics), "review_queue_rows": len(queue)}, indent=2
        )
    )


if __name__ == "__main__":
    main()
