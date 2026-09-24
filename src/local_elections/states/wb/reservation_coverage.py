"""Build a reservation-only search matrix using historical district boundaries.

Writes data/wb/vintage_search/reservation_gaps.csv and .parquet from the
curated holdings.csv and the Birbhum observation audit. Results tables and
district/block reservation percentages cannot fill a named-GP reservation gap.
"""

import hashlib
import json
from collections import defaultdict

import pandas as pd

from local_elections.common.runlog import command
from local_elections.paths import ROOT
from local_elections.states.wb.parse_birbhum import BASE, OUT

YEARS = (1978, 1983, 1988, 1993, 1998, 2003, 2008, 2013, 2018, 2023)
DERIVED = ROOT / "data/wb/derived"


def parsed_office_coverage():
    """Keep source cells and source GP rows in separate coverage units."""
    groups = defaultdict(list)
    for folder, filename in (
        ("office_native", "cell_review.csv"),
        ("office_scans", "row_review.csv"),
        ("nadia_2013_handbook", "office_reservations.csv"),
        ("alipurduar_offices", "office_reservations.csv"),
    ):
        path = DERIVED / folder / filename
        if not path.exists():
            continue
        for row in pd.read_csv(path, dtype=str, keep_default_na=False).to_dict(
            "records"
        ):
            if not row["tier"].startswith("gp_"):
                continue
            if row.get("heading") == "True" or "block_heading" in row.get(
                "quality_flags", ""
            ):
                continue
            sha = row.get("source_sha256") or row["sha256"]
            year = row.get("election_year") or row["year"]
            stage = row.get("stage") or (
                "handbook" if folder == "nadia_2013_handbook" else "final"
            )
            unit = (
                "source_cell"
                if folder.startswith("office_")
                else "source_gp_office_row"
            )
            source_tier = row["tier"]
            tier = "gp_deputy" if source_tier == "gp_deputy_head" else source_tier
            key = row["district"], int(year), stage, tier, sha, unit
            name = (
                row.get("gram_panchayat_reading")
                or row.get("gram_panchayat")
                or row.get("name")
            )
            review = row.get("review_status", "")
            name_review = row.get("name_review_status", "")
            visually_reviewed = any(
                "visual" in value and "unreviewed" not in value
                for value in (review, name_review)
            )
            name_unresolved = (
                row.get("name_ambiguous") == "True"
                or row.get("visual_name_ambiguous") == "True"
                or any(
                    token in review + ";" + name_review
                    for token in ("ambiguous", "unresolved")
                )
            )
            groups[key].append(
                {
                    "name": name,
                    "category": row.get("category") or row.get("reservation"),
                    "source_gp_key": row.get("source_gp_key"),
                    "source_tier": source_tier,
                    "visually_reviewed": visually_reviewed,
                    "resolved_name_visually_reviewed": bool(name)
                    and visually_reviewed
                    and not name_unresolved,
                    "output": str(path.relative_to(ROOT)),
                }
            )
    result = []
    for key, records in sorted(groups.items()):
        district, year, stage, tier, sha, unit = key
        result.append(
            {
                "district": district,
                "year": year,
                "stage": stage,
                "tier": tier,
                "source_tiers": ";".join(sorted({r["source_tier"] for r in records})),
                "source_sha256": sha,
                "unit": unit,
                "parsed_rows": len(records),
                "rows_with_category": sum(bool(r["category"]) for r in records),
                "rows_visually_reviewed": sum(r["visually_reviewed"] for r in records),
                "rows_with_visually_reviewed_resolved_name": sum(
                    r["resolved_name_visually_reviewed"] for r in records
                ),
                "distinct_name_readings": len(
                    {r["name"] for r in records if r["name"]}
                ),
                "distinct_source_gp_keys": len(
                    {r["source_gp_key"] for r in records if r["source_gp_key"]}
                ),
                "output": records[0]["output"],
                "note": (
                    "Do not sum drafts/finals or overlapping sources. "
                    "Distinct name strings are not harmonized GP identifiers. "
                    "Reviewed cells include reviewed blanks and unresolved names. "
                    "Blank other axes remain unknown in positive office lists."
                ),
            }
        )
    return pd.DataFrame(result)


def districts(year):
    names = {
        "Bankura",
        "Birbhum",
        "Bardhaman",
        "Cooch Behar",
        "Hooghly",
        "Howrah",
        "Jalpaiguri",
        "Malda",
        "Murshidabad",
        "Nadia",
        "Purulia",
    }
    names.update(
        ["24 Parganas"] if year < 1986 else ["North 24 Parganas", "South 24 Parganas"]
    )
    names.update(
        ["West Dinajpur"] if year < 1992 else ["Uttar Dinajpur", "Dakshin Dinajpur"]
    )
    names.update(
        ["Medinipur"] if year < 2002 else ["Purba Medinipur", "Paschim Medinipur"]
    )
    if year >= 2014:
        names.add("Alipurduar")
    if year >= 2017:
        names.remove("Bardhaman")
        names.update(["Purba Bardhaman", "Paschim Bardhaman", "Jhargram"])
    if year == 2023:
        names.update(["Darjeeling hills", "Kalimpong"])
    return sorted(names)


def build():
    holdings = pd.read_csv(BASE / "holdings.csv", dtype="string", keep_default_na=False)
    if holdings.duplicated(["district", "year"]).any():
        raise ValueError("Holdings must have one row per district and cycle")
    observations = pd.read_parquet(OUT / "observations.parquet")
    court = pd.read_json(BASE / "court_observations.jsonl", lines=True)
    office_coverage = parsed_office_coverage()
    for r in court.to_dict("records"):
        if (
            hashlib.sha256((ROOT / r["source_file"]).read_bytes()).hexdigest()
            != r["source_sha256"]
        ):
            raise ValueError("Court source checksum changed")
    rows = []
    for year in YEARS:
        for district in districts(year):
            row = {
                "district": district,
                "year": year,
                "head_source_status": "not_acquired",
                "ward_source_status": "not_acquired",
                "deputy_source_status": "not_acquired",
                "head_gp_source_universe": None,
                "head_gp_parsed_source_complete": 0,
                "head_gp_parsed_strict": 0,
                "head_gp_officially_verified": 0,
                "head_gp_judgment_evidence": 0,
                "source_reference": "",
                "next_action": "Search district/block Pradhan reservation schedules",
                "notes": "Not acquired does not establish nonexistence",
            }
            if year < 1998:
                row.update(
                    next_action="Check office rules; seek named ward reservations",
                    notes=(
                        "Women head quotas start in 1998; earlier SC/ST office "
                        "timing needs review. Do not infer all offices unreserved."
                    ),
                )
            held = holdings[
                holdings.district.eq(district) & holdings.year.eq(str(year))
            ]
            if len(held):
                values = held.iloc[0].to_dict()
                for key in ("district", "year"):
                    values.pop(key)
                row.update(values)
                row["head_gp_source_universe"] = (
                    int(row["head_gp_source_universe"])
                    if row["head_gp_source_universe"]
                    else None
                )
            if district == "Birbhum" and year in (1998, 2003):
                source = "cd" if year == 1998 else "beaman"
                subset = observations[
                    observations.source.eq(source)
                    & observations.reported_period.eq("current")
                ]
                complete = (
                    subset[[f"reserved_{c}" for c in ("women", "sc", "st")]]
                    .notna()
                    .all(axis=1)
                )
                row["head_gp_parsed_source_complete"] = int(complete.sum())
                row["head_gp_parsed_strict"] = int(
                    subset.eligible_after_exact_name_audit.sum()
                )
            court_subset = court[
                court.district.eq(district) & court.election_year_inferred.eq(year)
            ]
            if len(court_subset):
                row.update(
                    head_source_status="judgment_partial_year_inferred",
                    head_gp_judgment_evidence=int(court_subset.gp_raw.nunique()),
                    source_reference="data/wb/vintage_search/court_observations.jsonl",
                    next_action="Recover dated district office-reservation orders",
                    notes=(
                        "Named Pradhan category stated in judgment; cycle inferred. "
                        "Unmentioned categories null; not a district roster."
                    ),
                )
            if not office_coverage.empty:
                parsed = office_coverage[
                    office_coverage.district.eq(district)
                    & office_coverage.year.eq(year)
                ]
                for tier, prefix in (("gp_head", "head"), ("gp_deputy", "deputy")):
                    if parsed.tier.eq(tier).any():
                        row[f"{prefix}_source_status"] = (
                            "parsed_office_sources_review_status_varies"
                        )
                        row["source_reference"] += (
                            ";data/wb/vintage_search/office_parsing_by_source.csv"
                        )
                        row["next_action"] = (
                            "Review source-pinned office readings; "
                            "recover gaps in named GP coverage"
                        )
                handbook = parsed[
                    parsed.tier.eq("gp_head") & parsed.stage.eq("handbook")
                ]
                if not handbook.empty:
                    row["head_gp_source_universe"] = int(
                        handbook.distinct_source_gp_keys.max()
                    )
                    row["head_gp_parsed_source_complete"] = int(
                        handbook.rows_with_category.max()
                    )
                    row["notes"] = (
                        "Full handbook roster includes explicit UR and "
                        "a blank Pradhan category. Separate reserved-office "
                        "orders overlap; do not sum their rows."
                    )
                row["source_reference"] = ";".join(
                    dict.fromkeys(row["source_reference"].strip(";").split(";"))
                )
            rows.append(row)
    frame = pd.DataFrame(rows)
    frame["head_gp_source_universe"] = frame.head_gp_source_universe.astype("Int64")
    return frame


@command("coverage", state="West Bengal", source="gp_reservation_search")
def main():
    frame = build()
    office_coverage = parsed_office_coverage()
    office_coverage.to_csv(BASE / "office_parsing_by_source.csv", index=False)
    office_coverage.to_parquet(BASE / "office_parsing_by_source.parquet", index=False)
    frame.to_csv(BASE / "reservation_gaps.csv", index=False)
    frame.to_parquet(BASE / "reservation_gaps.parquet", index=False)
    court = pd.DataFrame(
        [
            json.loads(line)
            for line in (BASE / "court_observations.jsonl").read_text().splitlines()
        ]
    )
    for category in ("sc", "st", "women"):
        court[f"reserved_{category}"] = court[f"reserved_{category}"].astype("boolean")
    court.to_parquet(BASE / "court_observations.parquet", index=False)
    court.to_csv(BASE / "court_observations.csv", index=False)
    pd.testing.assert_frame_equal(
        frame, pd.read_parquet(BASE / "reservation_gaps.parquet")
    )
    print(f"{len(frame)} district-cycle rows; special cycles documented separately")


if __name__ == "__main__":
    main()
