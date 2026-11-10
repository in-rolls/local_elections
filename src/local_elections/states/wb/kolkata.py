"""Acquire and parse Kolkata's official archived 2015 winner lists."""

import argparse
import collections
import csv
import hashlib
import json
import re
from urllib.parse import parse_qs, urlencode, urlsplit

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from bs4 import BeautifulSoup

from local_elections.common.harvest import SourceDocument, acquire
from local_elections.common.runlog import command
from local_elections.paths import ROOT
from local_elections.tools.tcpd_ulb_coverage import DIRECTORY as TCPD_DIR
from local_elections.tools.tcpd_ulb_coverage import SOURCE as TCPD_SOURCE
from local_elections.tools.tcpd_ulb_coverage import verify_sources

SUMMARY = (
    ROOT / "data/reference/urban_sources/raw/west_bengal/kolkata-results-2015.html"
)
RAW = ROOT / "data/west_bengal/raw/kolkata/2015"
RELEASE = ROOT / "data/west_bengal/release/kolkata/2015"
MANIFEST = RAW / "manifest.csv"
BASE = "https://archive.wbsec.org/Municipal/"
SUMMARY_URL = BASE + "FinalResult_Mun_KMC.aspx"
SCHEMA = pa.schema(
    [
        ("year", pa.int16()),
        ("body", pa.string()),
        ("ward_no", pa.int16()),
        ("winner_name_raw", pa.string()),
        ("party_raw", pa.string()),
        ("party_source_id", pa.string()),
        ("winner_woman", pa.bool_()),
        ("woman_reserved", pa.bool_()),
        ("source_path", pa.string()),
        ("source_row", pa.int16()),
        ("source_sha256", pa.string()),
        ("source_url", pa.string()),
        ("source_status", pa.string()),
    ]
)


def frame(payload):
    soup = BeautifulSoup(payload, "html.parser")
    text = soup.get_text(" ", strip=True)
    if "KOLKATA MUNICIPAL CORPORATION" not in text or "18-4-2015" not in text:
        raise ValueError("Source is not the dated Kolkata 2015 summary")
    rows = {}
    for link in soup.select("a[href]"):
        if "ResultDetails_Mun_KMC.aspx?" not in link["href"]:
            continue
        count = int(link.get_text(strip=True))
        query = parse_qs(urlsplit(link["href"]).query)
        party = query["Party"][0]
        if party in rows:
            raise ValueError("Duplicate party in summary")
        rows[party] = {
            "party": party,
            "count": count,
            "url": BASE
            + "ResultDetails_Mun_KMC.aspx?"
            + urlencode({k: v[0].strip() for k, v in query.items()}),
        }
    if sum(r["count"] for r in rows.values()) != 144:
        raise ValueError("Summary does not account for all 144 winners")
    return [r for r in rows.values() if r["count"]]


def summary_bytes():
    payload = SUMMARY.read_bytes()
    receipts = json.loads(
        (ROOT / "data/reference/urban_sources/acquisition_log.json").read_text()
    )
    matches = [r for r in receipts if r.get("url") == SUMMARY_URL and "sha256" in r]
    if len(matches) != 1:
        raise ValueError("Expected one retained Kolkata summary receipt")
    receipt = matches[0]
    if (
        hashlib.sha256(payload).hexdigest() != receipt["sha256"]
        or len(payload) != receipt["bytes"]
    ):
        raise ValueError("Kolkata summary source bytes changed")
    return payload


def documents():
    return [
        SourceDocument(
            source_id="kolkata_winners_2015",
            state="West Bengal",
            year="2015",
            government_level="municipal_corporation",
            tier="ulb_ward",
            language="English",
            document_format="html",
            body="Kolkata",
            file=f"winners_party_{r['party']}.html",
            url=r["url"],
            landing_url=SUMMARY_URL,
        )
        for r in frame(summary_bytes())
    ]


def parse_party(payload):
    soup = BeautifulSoup(payload, "html.parser")
    table = soup.select_one("#grid_mn")
    if table is None:
        raise ValueError("Response has no winner table")
    trs = table.select("tr")
    header = [c.get_text(" ", strip=True) for c in trs[0].select("td,th")]
    if header != ["Ward Name", "Candidate Name", "Party Name"]:
        raise ValueError(f"Unexpected winner table columns: {header}")
    rows = []
    for row_no, tr in enumerate(trs[1:], 1):
        cells = [c.get_text(" ", strip=True) for c in tr.select("td")]
        if len(cells) != 3 or not cells[1] or not cells[2]:
            raise ValueError(f"Incomplete winner row {row_no}")
        ward = re.fullmatch(r"Ward No\.\s*(\d+)", cells[0])
        if ward is None:
            raise ValueError(f"Invalid ward label: {cells[0]}")
        rows.append(
            {
                "ward_no": int(ward[1]),
                "winner_name_raw": cells[1],
                "party_raw": cells[2],
                "source_row": row_no,
            }
        )
    return rows


def build():
    with MANIFEST.open() as fh:
        manifest = {r["file"]: r for r in csv.DictReader(fh)}
    plan = frame(summary_bytes())
    expected_files = {f"winners_party_{r['party']}.html" for r in plan}
    if set(manifest) != expected_files:
        raise ValueError("Acquired files do not match the complete party frame")
    rows = []
    for party in plan:
        path = RAW / f"winners_party_{party['party']}.html"
        receipt = manifest[path.name]
        payload = path.read_bytes()
        digest = hashlib.sha256(payload).hexdigest()
        if digest != receipt["sha256"] or len(payload) != int(receipt["bytes"]):
            raise ValueError(f"Source bytes changed: {path}")
        subset = parse_party(payload)
        if len(subset) != party["count"]:
            raise ValueError(f"Party {party['party']} count differs from summary")
        if len({r["party_raw"] for r in subset}) != 1:
            raise ValueError("Multiple parties in one party list")
        for row in subset:
            rows.append(
                dict(
                    row,
                    year=2015,
                    body="Kolkata Municipal Corporation",
                    party_source_id=party["party"],
                    winner_woman=None,
                    woman_reserved=None,
                    source_path=str(path.relative_to(ROOT)),
                    source_sha256=digest,
                    source_url=receipt["url"],
                    source_status="sec_informational_results_not_certified",
                )
            )
    if len(rows) != 144 or {r["ward_no"] for r in rows} != set(range(1, 145)):
        raise ValueError("Winner records must cover wards 1–144 exactly once")
    rows.sort(key=lambda r: r["ward_no"])
    RELEASE.mkdir(parents=True, exist_ok=True)
    table = pa.Table.from_pylist(rows, schema=SCHEMA)
    path = RELEASE / "winners.parquet"
    pq.write_table(table, path)
    if not table.equals(pq.read_table(path)):
        raise ValueError("Parquet round trip changed records")
    audit = {
        "rows": len(rows),
        "unit": "one declared winner per ward in April 2015",
        "key": ["year", "body", "ward_no"],
        "party_counts": dict(collections.Counter(r["party_raw"] for r in rows)),
        "recorded_winner_sex": 0,
        "recorded_reservation": 0,
        "summary_source": str(SUMMARY.relative_to(ROOT)),
        "summary_sha256": hashlib.sha256(SUMMARY.read_bytes()).hexdigest(),
        "parquet_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "sources": str(MANIFEST.relative_to(ROOT)),
    }
    (RELEASE / "schema.json").write_text(
        json.dumps(
            [
                {"name": f.name, "type": str(f.type), "nullable": f.nullable}
                for f in SCHEMA
            ],
            indent=2,
        )
        + "\n"
    )
    verify_sources(TCPD_DIR)
    tcpd = pd.read_csv(TCPD_DIR / TCPD_SOURCE, dtype=str, keep_default_na=False)
    tcpd["source_record"] = range(1, len(tcpd) + 1)
    selected = tcpd[
        tcpd.State_Name.eq("West_Bengal")
        & tcpd.LB_Name.eq("KOLKATA M C")
        & tcpd.Year.eq("2015")
        & tcpd.Position.eq("1")
    ].copy()
    selected["ward_no"] = selected.Ward_No.astype(int)
    comparison = table.to_pandas()[["ward_no", "winner_name_raw"]].merge(
        selected[["ward_no", "Candidate_Name", "Ward_Reservation", "source_record"]],
        on="ward_no",
        how="outer",
        validate="one_to_one",
        indicator=True,
    )
    if len(comparison) != 144 or not comparison["_merge"].eq("both").all():
        raise ValueError("TCPD comparison does not cover the same 144 wards")

    def normalize(s):
        return " ".join(s.split()).casefold()

    comparison["name_agrees_after_whitespace"] = comparison.winner_name_raw.map(
        normalize
    ) == comparison.Candidate_Name.map(normalize)
    comparison["tcpd_source_path"] = str((TCPD_DIR / TCPD_SOURCE).relative_to(ROOT))
    comparison["tcpd_source_sha256"] = hashlib.sha256(
        (TCPD_DIR / TCPD_SOURCE).read_bytes()
    ).hexdigest()
    comparison.drop(columns="_merge").to_csv(
        RELEASE / "tcpd_comparison.csv", index=False
    )
    audit["tcpd_name_agreements_after_whitespace"] = int(
        comparison.name_agrees_after_whitespace.sum()
    )
    audit["tcpd_comparison_sha256"] = hashlib.sha256(
        (RELEASE / "tcpd_comparison.csv").read_bytes()
    ).hexdigest()
    (RELEASE / "checksums.json").write_text(json.dumps(audit, indent=2) + "\n")
    print(json.dumps(audit, indent=2))
    return table


@command("process", artifact="kolkata")
def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["fetch", "build"])
    args = parser.parse_args()
    if args.command == "fetch":
        acquire(documents(), RAW, MANIFEST, ROOT)
    else:
        build()


if __name__ == "__main__":
    main()
