"""Retain and parse provisional 2022 Bhopal and Indore councilor lists."""

import argparse
import collections
import csv
import hashlib
import json
import re

import pyarrow as pa
import pyarrow.parquet as pq
from bs4 import BeautifulSoup

from local_elections.common.harvest import SourceDocument, acquire
from local_elections.common.runlog import command
from local_elections.paths import ROOT
from local_elections.states.mp import contract

RAW = ROOT / "data/madhya_pradesh/raw/urban"
RELEASE = ROOT / "data/madhya_pradesh/release/urban"
MANIFEST = RAW / "manifest.csv"
PARTY = {"भाजपा": "BJP", "कांग्रेस": "INC", "कांग्र्रेस": "INC", "निर्दलीय": "IND"}
URLS = {
    "Indore": (
        "https://hindi.webdunia.com/madhya-pradesh/"
        "indore-corporator-list-2022-122071800018_1.html"
    ),
    "Bhopal": (
        "https://www.naidunia.com/madhya-pradesh/"
        "bhopal-mp-bhopal-nagar-nigam-election-2022-results-who-will-become-"
        "the-ruler-of-the-city-in-the-capital-decision-today-7681063"
    ),
}
SCHEMA = contract.arrow_schema("winners")


def documents():
    return [
        SourceDocument(
            source_id="municipal_winners_2022_secondary",
            state="Madhya Pradesh",
            year="2022",
            government_level="municipal_corporation",
            tier="ulb_ward",
            language="Hindi",
            document_format="html",
            body=body,
            file=f"{body.lower()}_results_2022.html",
            url=url,
            landing_url=url,
        )
        for body, url in URLS.items()
    ]


def supporting_documents():
    return [
        SourceDocument(
            source_id=source_id,
            state="Madhya Pradesh",
            year=year,
            government_level="municipal_corporation",
            tier="ulb_ward",
            language="English",
            document_format=fmt,
            body="Indore",
            file=filename,
            url=url,
            landing_url=url,
        )
        for source_id, year, fmt, filename, url in [
            (
                "current_council_roster",
                "",
                "html",
                "indore_council.html",
                "https://imcindore.mp.gov.in/councillors",
            ),
            (
                "municipal_bond_disclosure",
                "2023",
                "pdf",
                "indore_offer_2023.pdf",
                "https://archives.nseindia.com/content/equities/DEBT_IPO_RHP_IMC.pdf",
            ),
        ]
    ]


def parse(payload, body):
    soup = BeautifulSoup(payload, "html.parser")
    dates = []
    for script in soup.select('script[type="application/ld+json"]'):
        try:
            item = json.loads(script.get_text())
        except ValueError:
            continue
        if isinstance(item, dict) and item.get("@type") == "NewsArticle":
            dates.append(item.get("datePublished", ""))
    if len(dates) != 1 or not dates[0].startswith("2022-07-"):
        raise ValueError("Expected dated July 2022 news source")
    selector = "article.article_in_content" if body == "Indore" else ".articleSide"
    article = soup.select_one(selector)
    if article is None:
        raise ValueError("Missing article container")
    lines = article.get_text("\n", strip=True).splitlines()
    pattern = (
        r"(\d+)\.\s*(.+),\s*(.+)"
        if body == "Indore"
        else r"(\d+)\s*-+\s*-?\s*([^\-]+?)\s*-+\s*(.+)"
    )
    rows = []
    for line in lines:
        match = re.fullmatch(pattern, line)
        if not match:
            continue
        ward, first, second = match.groups()
        name, party = (first, second) if body == "Indore" else (second, first)
        party = party.strip()
        if party not in PARTY or not name.strip():
            raise ValueError(f"Unrecognized winner row: {line}")
        rows.append(
            {
                "ward_no": ward,
                "winner": name.strip(),
                "party_raw": party,
                "party": PARTY[party],
                "source_publication_date": dates[0],
                "raw_line": line,
                "source_row": len(rows) + 1,
            }
        )
    if len(rows) != 85 or {r["ward_no"] for r in rows} != {
        str(n) for n in range(1, 86)
    }:
        raise ValueError(f"Incomplete or duplicated {body} ward frame")
    return rows


COUNCIL_SCHEMA = contract.arrow_schema("indore_council_roster")


def build_council():
    path = RAW / "indore_council.html"
    with MANIFEST.open() as stream:
        receipt = next(r for r in csv.DictReader(stream) if r["file"] == path.name)
    payload = path.read_bytes()
    if hashlib.sha256(payload).hexdigest() != receipt["sha256"] or len(payload) != int(
        receipt["bytes"]
    ):
        raise ValueError("Council roster source bytes changed")
    soup = BeautifulSoup(payload, "html.parser")
    data = json.loads(soup.select_one("#__NEXT_DATA__").get_text())
    attributes = data["props"]["pageProps"]["data"]["data"]["attributes"]
    rows = []
    for number, entry in enumerate(attributes["details"], 1):
        record = entry["otherContent"]
        label = record.get("wardNumber") or ""
        ward = re.fullmatch(r"Ward No[.:-]+\s*(\d+)", label.strip())
        title = record.get("title")
        honorific = re.match(r"^(Mr|Mrs|Ms)(?:\.|\s)", (title or "").strip())
        rows.append(
            {
                "body": "Indore",
                "source_entry_id": str(entry["id"]),
                "ward_no": ward[1] if ward else None,
                "ward_label_raw": label,
                "ward_name_raw": record.get("wardName"),
                "title_raw": title,
                "member_woman_from_honorific": int(honorific[1] in {"Mrs", "Ms"})
                if honorific
                else None,
                "source_updated_at": attributes["updatedAt"],
                "retrieved_at": receipt["retrieved_at"],
                "source_status": "current_roster_not_election_winners",
                "source_path": str(path.relative_to(ROOT)),
                "source_sha256": receipt["sha256"],
                "source_row": number,
            }
        )
    wards = [r["ward_no"] for r in rows if r["ward_no"] is not None]
    if len(rows) != 85 or len({r["source_entry_id"] for r in rows}) != 85:
        raise ValueError("Unexpected council roster entry frame")
    if len(wards) != 84 or set(wards) != {str(n) for n in range(1, 86)} - {"62"}:
        raise ValueError("Council roster ward coverage changed")
    table = pa.Table.from_pylist(rows, schema=COUNCIL_SCHEMA)
    path = RELEASE / "indore_council_roster.parquet"
    contract.validate("indore_council_roster", table)
    pq.write_table(table, path)
    if not table.equals(pq.read_table(path)):
        raise ValueError("Council roster round trip changed values")
    return {
        "entries": len(rows),
        "ward_labels": len(wards),
        "honorific_sex_present": sum(
            r["member_woman_from_honorific"] is not None for r in rows
        ),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }


def build():
    with MANIFEST.open() as stream:
        receipts = {r["file"]: r for r in csv.DictReader(stream)}
    output = []
    for source in documents():
        path = RAW / source.file
        payload = path.read_bytes()
        digest = hashlib.sha256(payload).hexdigest()
        receipt = receipts[source.file]
        if digest != receipt["sha256"] or len(payload) != int(receipt["bytes"]):
            raise ValueError(f"Source bytes changed: {path}")
        for row in parse(payload, source.body):
            output.append(
                dict(
                    row,
                    year=2022,
                    body=source.body,
                    tier="ulb_ward",
                    source_status="contemporaneous_news_unverified_against_returns",
                    source_path=str(path.relative_to(ROOT)),
                    source_sha256=digest,
                    source_url=source.url,
                    winner_woman=None,
                    reserved_woman=None,
                    votes=None,
                )
            )
    output.sort(key=lambda r: (r["body"], int(r["ward_no"])))
    table = pa.Table.from_pylist(output, schema=SCHEMA)
    RELEASE.mkdir(parents=True, exist_ok=True)
    target = RELEASE / "winners.parquet"
    contract.validate("winners", table)
    pq.write_table(table, target)
    if not table.equals(pq.read_table(target)):
        raise ValueError("Parquet round trip changed source fields")
    audit = {
        "rows": len(output),
        "party_counts": {
            body: dict(
                collections.Counter(r["party"] for r in output if r["body"] == body)
            )
            for body in URLS
        },
        "recorded_winner_sex": 0,
        "recorded_reservation": 0,
        "recorded_votes": 0,
        "input_sha256": {r["source_path"]: r["source_sha256"] for r in output},
        "parquet_sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
    }
    audit["current_council_roster"] = build_council()
    (RELEASE / "audit.json").write_text(json.dumps(audit, indent=2) + "\n")
    contract.write_metadata(RELEASE)
    print(json.dumps(audit, indent=2))
    return table


@command("process", artifact="urban")
def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["fetch", "build", "verify"])
    args = parser.parse_args()
    if args.command == "fetch":
        acquire(documents() + supporting_documents(), RAW, MANIFEST, ROOT)
    elif args.command == "verify":
        contract.verify(RELEASE)
    else:
        build()


if __name__ == "__main__":
    main()
