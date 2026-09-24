"""Preserve and audit named Birbhum Pradhan reservation survey observations.

Writes data/wb/derived/birbhum_reservations/. One row is a source GP and
reported period, not a reconciled GP-election assignment. Source disagreements
and date exceptions remain visible. No fuzzy joins or reservation imputation.
"""

import hashlib
import json
import re
import zipfile

import pandas as pd

from local_elections.common.runlog import command
from local_elections.paths import ROOT

BASE = ROOT / "data/wb/vintage_search"
OUT = ROOT / "data/wb/derived/birbhum_reservations"
OLD = ROOT / "data/wb/chattopadhyaya_duflo.zip"
NEW = BASE / "raw/898f2f74836e83ae.dta"
NEW_SHA = "e6454a2ae5a36829376557b20a45da7776a2951f9accc05ec75ac289a462d763"
NEW_URL = (
    "https://raw.githubusercontent.com/in-rolls/beaman/main/data/"
    "powerful_women_in_india_pradhan_seats_reserved_for_women.dta"
)
CATEGORIES = ("women", "sc", "st")


def yes_no(value):
    if pd.isna(value):
        return None
    if value not in (1, 2):
        raise ValueError(f"Unknown reservation code: {value}")
    return value == 1


def name_key(value):
    return re.sub(r"[^A-Z0-9]", "", value.upper())


def previous_cycle(row):
    if row["prev_year"] == 1:
        return 1998, "explicit_1998_to_2003"
    start, end = row["prev_year_888_1"], row["prev_year_888_2"]
    if (
        pd.notna(start)
        and pd.notna(end)
        and 1998 <= start < 2003
        and start <= end <= 2003
    ):
        return 1998, "within_1998_term_inferred"
    return None, "previous_incumbent_not_linked_to_1998"


def read_stata(source):
    with pd.io.stata.StataReader(source) as reader:
        frame = reader.read(convert_categoricals=False)
        labels = {
            "variables": reader.variable_labels(),
            "values": {
                field: {str(k): v for k, v in values.items()}
                for field, values in reader.value_labels().items()
            },
        }
    return frame, labels


def source_rows(frame, *, source, period, fields, source_file, digest):
    rows = []
    for _, r in frame.iterrows():
        record = {
            "source": source,
            "source_gp_id": str(int(r["gpnum" if source == "cd" else "res_id"])),
            "district": "Birbhum",
            "block_raw": r["blockp" if source == "cd" else "block"],
            "gp_raw": r["gpnamep" if source == "cd" else "gp"],
            "office": "Pradhan",
            "reported_period": period,
            "source_file": source_file,
            "source_sha256": digest,
        }
        flags = []
        for category, field in zip(CATEGORIES, fields, strict=True):
            record[f"raw_{category}"] = r[field]
            record[f"reserved_{category}"] = yes_no(r[field])
        if any(record[f"reserved_{c}"] is None for c in CATEGORIES):
            flags.append("missing_reservation")
        if record["reserved_sc"] is True and record["reserved_st"] is True:
            flags.append("source_reports_both_sc_and_st")
        if not record["block_raw"].strip() or not record["gp_raw"].strip():
            flags.append("missing_place_name")
        if source == "cd":
            year, evidence = 1998, "survey_2000_paper_dates_1998_election"
        elif period == "current":
            year = 2003
            evidence = "explicit_2003_code" if r["year"] == 1 else "study_term_context"
            if r["year"] != 1:
                flags.append("current_election_year_exception")
        else:
            year, evidence = previous_cycle(r)
            if evidence != "explicit_1998_to_2003":
                flags.append(evidence)
        record["election_year"] = year
        record["year_evidence"] = evidence
        if source == "beaman":
            for field in (
                "AA0_2b",
                "year",
                "year_2",
                "year_888",
                "prev_year",
                "prev_year_888_1",
                "prev_year_888_2",
                "comments",
            ):
                record[f"raw_{field}"] = r[field]
        record["flags"] = ";".join(flags)
        record["eligible_within_source_strict"] = not flags
        record["name_key"] = (
            name_key(record["block_raw"]) + "|" + name_key(record["gp_raw"])
        )
        rows.append(record)
    return rows


def build():
    if hashlib.sha256(NEW.read_bytes()).hexdigest() != NEW_SHA:
        raise ValueError("Beaman source checksum changed")
    labels = {}
    with zipfile.ZipFile(OLD) as archive:
        a, labels["cd_parta"] = read_stata(archive.open("womenpolicymakers_parta.dta"))
        b, labels["cd_partb"] = read_stata(archive.open("womenpolicymakers_partb.dta"))
    if len(a) != 166 or len(b) != 166 or set(a.gpnum) != set(b.gpnum):
        raise ValueError("CD source universe changed")
    old = a[["gpnum", "womres", "scres", "stres"]].merge(
        b[["gpnum", "blockp", "gpnamep"]],
        on="gpnum",
        how="left",
        validate="1:1",
        indicator=True,
    )
    if len(old) != 166 or not old["_merge"].eq("both").all():
        raise ValueError("CD name join did not preserve every GP")
    new, labels["beaman"] = read_stata(NEW)
    if len(new) != 165 or not new.res_id.is_unique or not new.AA0_2b.is_unique:
        raise ValueError("Beaman source identifiers changed")
    old_sha = hashlib.sha256(OLD.read_bytes()).hexdigest()
    rows = source_rows(
        old,
        source="cd",
        period="current",
        fields=("womres", "scres", "stres"),
        source_file=str(OLD.relative_to(ROOT)),
        digest=old_sha,
    )
    for period, fields in (
        ("current", ("res_woman", "res_sc", "res_st")),
        ("previous", ("prev_res_woman", "prev_res_sc", "prev_res_st")),
    ):
        rows.extend(
            source_rows(
                new,
                source="beaman",
                period=period,
                fields=fields,
                source_file=str(NEW.relative_to(ROOT)),
                digest=NEW_SHA,
            )
        )
    data = pd.DataFrame(rows)
    for col in [
        "election_year",
        *[c for c in data if c.startswith("raw_") and c != "raw_comments"],
    ]:
        data[col] = data[col].astype("Int64")
    for col in [
        "eligible_within_source_strict",
        *[f"reserved_{c}" for c in CATEGORIES],
    ]:
        data[col] = data[col].astype("boolean")
    if data.duplicated(["source", "source_gp_id", "reported_period"]).any():
        raise ValueError("Duplicate source-period GP key")
    # This outer join is an audit, never a source of filled reservation fields.
    left = data[data.source.eq("cd")]
    right = data[data.source.eq("beaman") & data.reported_period.eq("previous")]
    audit = left.merge(
        right,
        on="name_key",
        how="outer",
        validate="1:1",
        suffixes=("_cd", "_beaman"),
        indicator="name_match",
    )
    same_year = audit.election_year_cd.eq(1998) & audit.election_year_beaman.eq(1998)
    for c in CATEGORIES:
        audit[f"conflict_{c}"] = (
            same_year & audit[f"reserved_{c}_cd"].ne(audit[f"reserved_{c}_beaman"])
        ).fillna(False)
    audit["any_conflict"] = audit[[f"conflict_{c}" for c in CATEGORIES]].any(axis=1)
    conflicted = set(audit.loc[audit.any_conflict, "name_key"])
    data["cross_source_conflict"] = data.election_year.eq(1998).fillna(
        False
    ) & data.name_key.isin(conflicted)
    data["eligible_after_exact_name_audit"] = (
        data.eligible_within_source_strict & ~data.cross_source_conflict
    )
    recodes = []
    for c in CATEGORIES:
        counts = (
            data.groupby(
                ["source", "reported_period", f"raw_{c}", f"reserved_{c}"],
                dropna=False,
            )
            .size()
            .reset_index(name="n")
        )
        counts["category"] = c
        counts = counts.rename(columns={f"raw_{c}": "raw", f"reserved_{c}": "reserved"})
        recodes.extend(json.loads(counts.to_json(orient="records")))
    summary = (
        data.groupby(
            ["source", "reported_period", "election_year", "year_evidence"],
            dropna=False,
        )
        .agg(
            rows=("source_gp_id", "size"),
            complete_reservation=("reserved_women", "count"),
            within_source_strict=("eligible_within_source_strict", "sum"),
            after_exact_name_audit=("eligible_after_exact_name_audit", "sum"),
        )
        .reset_index()
    )
    report = {
        "unit": "source GP and reported period; not a deduplicated election panel",
        "rows": len(data),
        "new_source_url": NEW_URL,
        "cd_name_join": {
            "left": 166,
            "right": 166,
            "output": len(old),
            "matched": 166,
            "cardinality": "1:1",
        },
        "cross_source_audit": {
            "cardinality": "1:1 outer; normalized block and GP spelling only",
            "name_matches": int(audit.name_match.eq("both").sum()),
            "cd_only": int(audit.name_match.eq("left_only").sum()),
            "beaman_only": int(audit.name_match.eq("right_only").sum()),
            "same_year_category_conflicts": int(audit.any_conflict.sum()),
            "unmatched_rows": "cross_source_audit.parquet",
            "by_cd_block": json.loads(
                audit[audit.name_match.ne("right_only")]
                .assign(matched=lambda x: x.name_match.eq("both"))
                .groupby("block_raw_cd", dropna=False)
                .agg(rows=("name_key", "size"), matched=("matched", "sum"))
                .reset_index()
                .to_json(orient="records")
            ),
            "limitation": (
                "No fuzzy linkage; unmatched names are not missing GPs. "
                "Matching accuracy has not been externally adjudicated."
            ),
        },
        "summary": json.loads(summary.to_json(orient="records")),
        "recodes": recodes,
        "missing_policy": (
            "Preserve all observations and nulls; "
            "never infer unreserved from missingness."
        ),
        "pooled": False,
    }
    return data, audit, report, labels


@command("parse", state="West Bengal", source="birbhum_research_reservations")
def main():
    data, audit, report, labels = build()
    OUT.mkdir(parents=True, exist_ok=True)
    for name, frame in (("observations", data), ("cross_source_audit", audit)):
        frame.to_parquet(OUT / f"{name}.parquet", index=False)
        frame.to_csv(OUT / f"{name}.csv", index=False)
        pd.testing.assert_frame_equal(frame, pd.read_parquet(OUT / f"{name}.parquet"))
    data[data["flags"].ne("") | data.cross_source_conflict].to_csv(
        OUT / "review_queue.csv",
        index=False,
    )
    for name, value in (("validation", report), ("stata_labels", labels)):
        (OUT / f"{name}.json").write_text(json.dumps(value, indent=2) + "\n")
    print(json.dumps(report["summary"], indent=2))


if __name__ == "__main__":
    main()
