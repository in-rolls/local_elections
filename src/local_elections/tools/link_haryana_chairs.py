"""Link report chair names to the SEC's held 2000 block directory.

The report does not print districts for these offices. Directory associations
are separate candidate links: they neither amend the printed report nor date
the separate elected-person roster. Two Barwala offices remain ambiguous.
"""

import argparse
import csv
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

from local_elections.common.runlog import command
from local_elections.paths import ROOT
from local_elections.tools.historical_harvest import checksum, links_from_html

BASE = ROOT / "data/source_search/national/haryana"
INDEX = BASE / "early_cycles/raw/f99f62c8bdb6807937ba_f6a1f978f6df.html"
INDEX_SHA = "f6a1f978f6df66f5937c586b221561820a96e3161eb79410d211fbec1fbd9833"
INDEX_URL = (
    "https://secharyana.gov.in/"
    "information-blockwise-regarding-elected-members-of-gram-panchayats-in-2000/"
)


def name_key(value):
    return re.sub(r"[^A-Z0-9]", "", value.upper())


def link_chairs(chairs, directory, aliases):
    by_name = defaultdict(list)
    for entry in directory:
        by_name[name_key(entry["label"])].append(entry)
    alias_map = {}
    chair_names = {r["body_raw"] for r in chairs}
    directory_names = {r["label"] for r in directory}
    for alias in aliases:
        old, new = alias["report_body_raw"], alias["index_body_raw"]
        if old in alias_map or old not in chair_names or new not in directory_names:
            raise ValueError(f"Changed or duplicate spelling review: {alias}")
        alias_map[old] = new
    output = []
    identities = set()
    for chair in chairs:
        identity = (chair["source_sha256"], chair["source_page"], chair["source_bbox"])
        if identity in identities:
            raise ValueError("Duplicate report cell identity")
        identities.add(identity)
        raw = chair["body_raw"]
        matches = by_name[name_key(alias_map.get(raw, raw))]
        districts = sorted({r["heading"] for r in matches})
        method = "reviewed_spelling_variant" if raw in alias_map else "normalized_name"
        if not matches:
            method = "unmatched"
        elif len(matches) != 1:
            method = "ambiguous_name"
        output.append(
            {
                "report_source_sha256": chair["source_sha256"],
                "report_source_page": chair["source_page"],
                "report_source_bbox": chair["source_bbox"],
                "report_body_raw": raw,
                "district_candidate": districts[0] if len(matches) == 1 else None,
                "linkage_method": method,
                "index_matches": json.dumps(matches, ensure_ascii=False),
                "index_source_sha256": INDEX_SHA,
                "index_source_url": INDEX_URL,
                "review_status": "directory_link_candidate; independent_review_pending",
            }
        )
    return output


@command("parse", state="Haryana", vintage="2000_chair_linkage")
def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=BASE)
    args = parser.parse_args()
    base = args.source
    index = base / INDEX.relative_to(BASE)
    report = base / "report_2000/seat_rows.csv"
    report_manifest = base / "report_2000/checksums.json"
    expected = json.loads(report_manifest.read_text())["outputs"][report.name]
    if checksum(index) != INDEX_SHA or checksum(report) != expected:
        raise ValueError("Changed report or directory source")
    directory = [
        r
        for r in links_from_html(index.read_text(), INDEX_URL)
        if r["url"].lower().endswith(".pdf")
    ]
    with report.open(newline="") as stream:
        chairs = [r for r in csv.DictReader(stream) if r["tier"] == "block_head"]
    out = base / "review/chair_linkage"
    aliases_path = out / "spelling_reviews.csv"
    with aliases_path.open(newline="") as stream:
        aliases = list(csv.DictReader(stream))
    if len(chairs) != 114 or len(directory) != 114:
        raise ValueError("Expected both 114-office source frames")
    rows = link_chairs(chairs, directory, aliases)
    with (out / "district_links.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    summary = {
        "report_chairs": len(rows),
        "directory_entries": len(directory),
        "methods": dict(Counter(r["linkage_method"] for r in rows)),
        "district_candidates": sum(r["district_candidate"] is not None for r in rows),
        "unresolved": [
            r["report_body_raw"] for r in rows if not r["district_candidate"]
        ],
        "scope": "Index associations, not verified historical boundary assignments",
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    inputs = [index, report, report_manifest, aliases_path, Path(__file__)]
    (out / "checksums.json").write_text(
        json.dumps(
            {
                "inputs": {str(p.relative_to(ROOT)): checksum(p) for p in inputs},
                "outputs": {
                    p.name: checksum(p)
                    for p in [out / "district_links.csv", out / "summary.json"]
                },
            },
            indent=2,
        )
        + "\n"
    )
    print(json.dumps(summary))


if __name__ == "__main__":
    main()
