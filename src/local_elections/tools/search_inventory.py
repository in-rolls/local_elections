"""Rebuild the national search baseline from holdings, without claiming exhaustion.

Counts distinguish seat events, candidates, and separate source-specific tables.
The archive inventory is a record of host-level discovery, not document review.
Missing coverage means absent from these inputs, not absent from the web.
"""

import csv
import hashlib
import json

import pandas as pd
import pyarrow.parquet as pq

from local_elections.common.runlog import command
from local_elections.paths import ROOT

OUT = ROOT / "data/source_search/national"


def sha256(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def observed(values):
    return values.notna() & values.astype(str).str.strip().ne("")


def summarize(frame):
    """District/year/tier counts; do not turn unspecified gender into a zero."""
    records = []
    keys = ["state", "year", "district", "tier", "listing_scope"]
    for group, part in frame.groupby(keys, dropna=False, observed=True):
        record = dict(zip(keys, group, strict=True))
        record.update(
            rows=len(part),
            distinct_row_ids=part.row_id.nunique(),
            reservation_raw_observed=int(observed(part.reservation_raw).sum()),
            women_reservation_nonnull=int(part.woman_reserved.notna().sum()),
            caste_reservation_nonnull=int(part.caste_reservation.notna().sum()),
            winner_name_observed=int(observed(part.winner).sum()),
            flagged_rows=int(observed(part.quality_flags).sum()),
            source_paths=part.source_path.nunique(),
        )
        gp = part.loc[observed(part.gram_panchayat)]
        record["named_gp_keys"] = len(
            gp[["district", "block", "gram_panchayat"]].drop_duplicates()
        )
        records.append(record)
    return records


@command("inventory", artifact="national_search")
def main():
    registry = pd.read_csv(OUT / "jurisdictions.csv", keep_default_na=False)
    if len(registry) != 36 or registry.state.duplicated().any():
        raise ValueError("Expected the 36 explicitly listed research jurisdictions")
    archive = pd.read_csv(ROOT / "data/archive_inventory.csv")
    queries = pd.read_csv(ROOT / "data/source_search/early_heads/search_queries.csv")
    inputs = []
    coverage = []
    candidates = []
    for path in sorted((ROOT / "data/master").glob("*.parquet")):
        if not (path.name.startswith("master_") or path.name.startswith("candidates_")):
            continue
        schema = pq.read_schema(path)
        if "state" not in schema.names or "tier" not in schema.names:
            continue
        inputs.append({"path": str(path.relative_to(ROOT)), "sha256": sha256(path)})
        if path.name.startswith("candidates_"):
            frame = pq.read_table(path, columns=["state", "year", "tier"]).to_pandas()
            for group, part in frame.groupby(["state", "year", "tier"], observed=True):
                candidates.append(
                    dict(zip(["state", "year", "tier"], group, strict=True))
                    | {"rows": len(part), "path": str(path.relative_to(ROOT))}
                )
            continue
        columns = [
            "state",
            "year",
            "district",
            "block",
            "gram_panchayat",
            "tier",
            "listing_scope",
            "row_id",
            "reservation_raw",
            "woman_reserved",
            "caste_reservation",
            "winner",
            "quality_flags",
            "source_path",
        ]
        frame = pq.read_table(path, columns=columns).to_pandas()
        for record in summarize(frame):
            coverage.append(record | {"path": str(path.relative_to(ROOT))})
    pd.DataFrame(coverage).to_csv(OUT / "master_district_year_tier.csv", index=False)
    pd.DataFrame(candidates).to_csv(OUT / "candidate_year_tier.csv", index=False)
    supplemental = []
    for state, directory in [("West Bengal", "wb"), ("Tamil Nadu", "tn")]:
        for path in sorted((ROOT / "data" / directory / "derived").rglob("*.parquet")):
            meta = pq.read_metadata(path)
            supplemental.append(
                {
                    "state": state,
                    "path": str(path.relative_to(ROOT)),
                    "rows": meta.num_rows,
                    "columns": ";".join(meta.schema.names),
                    "sha256": sha256(path),
                    "scope": "includes audits/aggregates; not additive seat counts",
                }
            )
    pd.DataFrame(supplemental).to_csv(OUT / "additional_tables.csv", index=False)
    coverage_frame = pd.DataFrame(coverage)
    coverage_frame["state"] = coverage_frame.state.replace(
        {"Jammu & Kashmir": "Jammu and Kashmir"}
    )
    by_state = coverage_frame.groupby("state").agg(
        master_rows=("rows", "sum"),
        first_master_year=("year", "min"),
        last_master_year=("year", "max"),
        master_tiers=("tier", lambda x: ";".join(sorted(set(x)))),
    )
    queue = registry.merge(by_state, on="state", how="left", validate="one_to_one")
    archive["state"] = archive.state.replace(
        {"NCT of Delhi": "Delhi", "Jammu & Kashmir": "Jammu and Kashmir"}
    )
    queue = queue.merge(
        archive[["state", "host", "pdfs", "status"]].rename(
            columns={
                "host": "prior_archive_host",
                "pdfs": "prior_archive_pdf_urls",
                "status": "prior_archive_status",
            }
        ),
        on="state",
        how="left",
        validate="one_to_one",
    )
    query_counts = queries.groupby("state").size().rename("prior_early_search_queries")
    queue = queue.merge(query_counts, on="state", how="left", validate="one_to_one")
    queue["archive_exhausted"] = False
    queue["district_search_complete"] = False
    queue["master_rows"] = queue.master_rows.fillna(0).astype(int)
    if queue.master_rows.sum() != coverage_frame.rows.sum():
        raise ValueError("A master state failed to match the jurisdiction registry")
    queue.sort_values(["search_order", "state"]).to_csv(
        OUT / "state_queue.csv", index=False
    )
    for path in [
        OUT / "jurisdictions.csv",
        ROOT / "data/archive_inventory.csv",
        ROOT / "data/source_search/early_heads/search_queries.csv",
    ]:
        inputs.append({"path": str(path.relative_to(ROOT)), "sha256": sha256(path)})
    with (OUT / "baseline_inputs.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=["path", "sha256"])
        writer.writeheader()
        writer.writerows(inputs)
    print(
        json.dumps(
            {
                "jurisdictions": len(queue),
                "master_states": len(by_state),
                "master_rows": int(queue.master_rows.sum()),
                "district_year_tier_groups": len(coverage),
                "additional_tables": len(supplemental),
                "prior_archive_inventory_jurisdictions": len(archive),
            }
        )
    )


if __name__ == "__main__":
    main()
