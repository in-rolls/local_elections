"""Audit historical Haryana occurrences and preserve the undated head roster.

Repeated office labels are not assumed to be duplicate records. The office-key
ledger separates identical source repeats from conflicting printed records.
The separate head roster has no reservation column and is never assigned the
surrounding archive collection's year without dated corroboration.
"""

import argparse
import json
import re
from pathlib import Path

import pandas as pd
import pdfplumber
import pyarrow as pa
import pyarrow.parquet as pq

from local_elections.common.runlog import command
from local_elections.paths import ROOT
from local_elections.tools.historical_harvest import checksum

BASE = ROOT / "data/source_search/national/haryana"
HEAD_PATH = "gap_recovery/raw/11336814aa4b51ff51a4.pdf"


def name_key(raw):
    raw = re.sub(r"^(?:SMT|SHRI|SH)[.\s]+", "", raw.upper().strip())
    return re.sub(r"[^A-Z]", "", raw)


def parse_heads(path):
    records = []
    with pdfplumber.open(path) as pdf:
        cells = pdf.pages[0].find_tables()[0].rows[0].cells
        for number, page in enumerate(pdf.pages, 1):
            words = page.extract_words(x_tolerance=1, y_tolerance=2)
            anchors = [
                w
                for w in words
                if cells[2][0] <= w["x0"] < cells[2][2]
                and w["text"]
                in {
                    "PRESIDENT",
                    "VICE-PRESIDENT",
                    "CHAIRMAN",
                    "CAHIRMAN",
                    "VICE-CHAIRMAN",
                }
            ]
            for index, anchor in enumerate(anchors):
                top = anchor["top"] - 2
                bottom = (
                    anchors[index + 1]["top"] - 2
                    if index + 1 < len(anchors)
                    else page.height - 25
                )
                raw = []
                for cell in cells:
                    crop = page.crop((cell[0], top, cell[2], bottom))
                    raw.append((crop.extract_text(x_tolerance=1) or "").strip())
                records.append(
                    {
                        "source_page": number,
                        "source_row_on_page": index + 1,
                        "district_raw": raw[0],
                        "body_raw": raw[1],
                        "office_raw": raw[2],
                        "winner_name_raw": raw[3],
                        "relation_name_raw": raw[4],
                        "raw_cells": json.dumps(raw, ensure_ascii=False),
                    }
                )
    return pd.DataFrame(records)


def match_dated_presidents(heads, dated):
    heads = heads.copy()
    heads["year"] = pd.Series(pd.NA, index=heads.index, dtype="Int64")
    heads["year_basis"] = "undated_head_roster"
    heads["caste_reservation"] = pd.Series(pd.NA, index=heads.index, dtype="string")
    heads["woman_reserved"] = pd.Series(pd.NA, index=heads.index, dtype="boolean")
    heads["dated_evidence_page"] = pd.Series(pd.NA, index=heads.index, dtype="Int64")
    for index, row in heads[heads.office_raw.eq("PRESIDENT")].iterrows():
        matches = dated[
            dated.winner_name_raw.map(name_key).eq(name_key(row.winner_name_raw))
            & dated.relation_name_raw.map(name_key).eq(name_key(row.relation_name_raw))
            & dated.district_raw.map(name_key).eq(name_key(row.district_raw))
        ]
        if len(matches) != 1:
            continue
        evidence = matches.iloc[0]
        heads.at[index, "year"] = 2000
        heads.at[index, "year_basis"] = "district_name_relation_match_to_dated_report"
        heads.at[index, "caste_reservation"] = evidence.caste_reservation
        heads.at[index, "woman_reserved"] = evidence.woman_reserved
        heads.at[index, "dated_evidence_page"] = evidence.source_page
    return heads


@command("audit", state="Haryana", vintage="historical")
def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=BASE)
    args = parser.parse_args()
    base = args.source
    out = base / "review/completion"
    out.mkdir(parents=True, exist_ok=True)
    path = base / "gap_recovery/parsed/seat_rows.parquet"
    frame = pd.read_parquet(path)
    key = ["source_sha256", "gram_panchayat_raw", "ward_or_office_raw"]
    repeated = frame[frame.duplicated(key, keep=False)].copy()
    values = ["tier", "winner_name_raw", "relation_name_raw", "reservation_raw"]
    groups = []
    for identity, group in repeated.groupby(key, dropna=False):
        distinct = len(group[values].drop_duplicates())
        groups.append(
            dict(zip(key, identity, strict=True))
            | {
                "occurrences": len(group),
                "distinct_printed_records": distinct,
                "classification": "identical_record_repeat"
                if distinct == 1
                else "conflicting_source_office_key",
                "source_pages": ";".join(
                    str(v) for v in sorted(group.source_page.unique())
                ),
                "disposition": "retain_all; resolve_source_or_entity_conflict",
            }
        )
    pd.DataFrame(groups).to_csv(out / "office_key_groups.csv", index=False)
    repeated.to_csv(out / "office_key_occurrences.csv", index=False)
    heads = parse_heads(base / HEAD_PATH)
    dated_path = base / "report_2000/seat_rows.parquet"
    dated = pd.read_parquet(dated_path)
    dated = dated[dated.tier.eq("zp_head")]
    heads = match_dated_presidents(heads, dated)
    heads["source_sha256"] = checksum(base / HEAD_PATH)
    heads["source_path"] = HEAD_PATH
    heads["dated_evidence_sha256"] = str(dated.source_sha256.iloc[0])
    heads.loc[heads.year.isna(), "dated_evidence_sha256"] = ""
    heads["reservation_basis"] = "not_stated_in_head_roster"
    heads.loc[heads.year.notna(), "reservation_basis"] = (
        "linked_dated_office_category_in_report"
    )
    pq.write_table(
        pa.Table.from_pandas(heads, preserve_index=False), out / "head_roster.parquet"
    )
    heads.to_csv(out / "head_roster.csv", index=False)
    summary = {
        "office_key_groups": len(groups),
        "affected_occurrences": len(repeated),
        "identical_repeat_groups": sum(
            r["classification"] == "identical_record_repeat" for r in groups
        ),
        "conflicting_groups": sum(
            r["classification"] == "conflicting_source_office_key" for r in groups
        ),
        "head_roster_rows": len(heads),
        "head_office_counts": heads.office_raw.value_counts().to_dict(),
        "heads_corroborated_as_2000": int(heads.year.notna().sum()),
        "remaining_heads_without_validated_year": int(heads.year.isna().sum()),
        "scope": "Mechanical audit; source validation remains separate",
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    inputs = [Path(__file__), path, base / HEAD_PATH, dated_path]
    (out / "inputs.json").write_text(
        json.dumps([{"path": str(p), "sha256": checksum(p)} for p in inputs], indent=2)
        + "\n"
    )
    print(json.dumps(summary))


if __name__ == "__main__":
    main()
