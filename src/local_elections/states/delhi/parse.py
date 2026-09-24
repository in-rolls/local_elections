"""Build one record per elected Delhi ward from cached, source-linked inputs."""

import argparse
import gzip
import hashlib
import json
import re
from pathlib import Path

import pandas as pd
import pdfplumber
import pyarrow.parquet as pq

from local_elections.common.runlog import command

from .html import profile

RESERVATION = {
    "W": (1, "NONE"),
    "WOMAN": (1, "NONE"),
    "SCW": (1, "SC"),
    "G": (0, "NONE"),
    "GENERAL": (0, "NONE"),
    "SC": (0, "SC"),
}


def official_2022(path):
    pattern = re.compile(
        r"(?<!\d)(\d{1,3})\s+([A-Z][A-Z\s()./-]*?)\s+(\d{1,2})\s+"
        r"([A-Z][A-Z\s/.-]*?)\s+(\d{4,6})\s+(\d{1,6})\s+(GENERAL|WOMAN|SCW|SC)\b"
    )
    rows = []
    with pdfplumber.open(path) as pdf:
        for index in range(10, 16):
            text = pdf.pages[index].extract_text(use_text_flow=True)
            if index == 10:
                start = re.search("Annexure-B", text, re.I)
                if start is None:
                    raise ValueError("Missing Annexure B")
                text = text[start.start() :]
            for match in pattern.finditer(text):
                (
                    ward,
                    name,
                    assembly,
                    assembly_name,
                    _population,
                    _sc_population,
                    reservation,
                ) = match.groups()
                rows.append(
                    {
                        "year": 2022,
                        "ward_number": str(int(ward)),
                        "ward_name": " ".join(name.split()),
                        "assembly_id": int(assembly),
                        "assembly_name": " ".join(assembly_name.split()),
                        "reservation_raw": reservation,
                        "source_page": index + 1,
                    }
                )
    frame = pd.DataFrame(rows)
    if len(frame) != 250 or set(frame.ward_number) != {str(i) for i in range(1, 251)}:
        raise ValueError(
            "Official 2022 roster must contain each of 250 wards exactly once"
        )
    return frame


def universe(root, gazette):
    raw = pd.read_excel(root / "sources/goyal_candidates.xlsx")
    old = raw[raw.eci_pos.eq(1) & raw.election.isin([2012, 2017])].copy()
    old = old.rename(
        columns={
            "election": "year",
            "commonname": "ward_number",
            "eci_candname": "winner_name",
            "resstatus": "reservation_raw",
            "education": "goyal_education",
        }
    )
    old["winner_party"] = old.eci_party.str.strip()
    old["ward_number"] = old.ward_number.astype(str)
    mapping = pd.read_csv(
        root / "sources/goyal_mapping.tab", sep="\t", dtype={"commonname": str}
    )
    mapping = mapping.rename(
        columns={"election": "year", "commonname": "ward_number", "acno": "assembly_id"}
    )
    old = old.merge(
        mapping[["year", "ward_number", "assembly_id"]],
        on=["year", "ward_number"],
        how="left",
        validate="one_to_one",
    )
    if len(old) != 544 or old.assembly_id.isna().any():
        raise ValueError("Goyal winner-to-assembly join failed")
    new = pd.read_csv(root / "sources/opencity2022.csv")
    new = new[new.Position.eq(1)].rename(
        columns={"Ward_No": "ward_number", "Candidate_Name": "winner_name"}
    )
    new["winner_party"] = new.Party_Name.map(
        {
            "AAM AADMI PARTY": "AAP",
            "BHARATIYA JANATA PARTY": "BJP",
            "INDIAN NATIONAL CONGRESS": "INC",
            "INDEPENDENT": "IND",
        }
    )
    new["ward_number"] = new.ward_number.astype(str)
    new = official_2022(gazette).merge(
        new[["ward_number", "winner_name", "winner_party", "Ward_Reservation"]],
        on="ward_number",
        how="left",
        validate="one_to_one",
    )
    crosscheck = {
        "Women": "WOMAN",
        "Unreserved": "GENERAL",
        "Scheduled Caste": "SC",
        "Scheduled Caste (Women)": "SCW",
    }
    if not new.Ward_Reservation.map(crosscheck).eq(new.reservation_raw).all():
        raise ValueError(
            "2022 result compilation disagrees with the official reservation schedule"
        )
    keep = [
        "year",
        "ward_number",
        "winner_name",
        "reservation_raw",
        "assembly_id",
        "winner_party",
    ]
    return pd.concat([old[keep], new[keep]], ignore_index=True)


def build(root, gazette):
    sources = json.loads(Path(__file__).with_name("sources.json").read_text())
    for source in sources:
        path = root / "sources" / source["file"]
        if hashlib.sha256(path.read_bytes()).hexdigest() != source["sha256"]:
            raise ValueError(f"Source changed: {path}")
    frame = pd.read_parquet(root / "frame.parquet")
    records = []
    for row in frame.to_dict("records"):
        with gzip.open(root / row["profile_path"], "rt") as handle:
            response = json.load(handle)
        if hashlib.sha256(response["body"].encode()).hexdigest() != response["sha256"]:
            raise ValueError("Cached profile hash changed")
        parsed = profile(response["body"], row["year"])
        if parsed["ward_number"] != row["ward_number"]:
            raise ValueError(
                f"Profile ward disagrees with winner list: {row['profile_url']}"
            )
        parsed.update(
            {
                "source_url": row["profile_url"],
                "source_sha256": response["sha256"],
                "source_capture": response["fetched_at"],
                "source_path": row["profile_path"],
                "list_education": row["list_education"],
                "list_cases": row["list_cases"],
            }
        )
        records.append(parsed)
    profiles = pd.DataFrame(records)
    d = universe(root, gazette).merge(
        profiles, on=["year", "ward_number"], how="left", validate="one_to_one"
    )
    if len(d) != 794 or d.winner_name.isna().any():
        raise ValueError("Winner universe is incomplete")
    linked = d.source_url.notna()
    if not d.loc[linked, "winner_party"].eq(d.loc[linked, "profile_party"]).all():
        raise ValueError("Profile party disagrees with the election winner")
    d["quota"] = d.reservation_raw.map(lambda x: RESERVATION[x][0]).astype("int64")
    d["caste_reservation"] = d.reservation_raw.map(lambda x: RESERVATION[x][1])
    d["assembly_id"] = d.assembly_id.astype("int64")
    for col in ["age", "pending_cases", "convicted_cases"]:
        d[col] = d[col].astype("Int64")
    release = root.parent / "release"
    release.mkdir(exist_ok=True)
    d.to_parquet(release / "winner_source_audit.parquet", index=False)
    d.drop(
        columns=["winner_name", "profile_name", "list_education", "list_cases"]
    ).to_parquet(release / "winners.parquet", index=False)
    summary = d.groupby("year").agg(
        winners=("ward_number", "size"),
        linked_profiles=("source_url", "count"),
        education=("education", "count"),
        age=("age", "count"),
        cases=("pending_cases", "count"),
    )
    summary.to_csv(release / "coverage.csv")
    manifest = []
    for path in sorted(release.glob("*.parquet")):
        manifest.append(
            {
                "path": path.name,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "rows": len(pd.read_parquet(path)),
                "bytes": path.stat().st_size,
            }
        )
    (release / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    definitions = {
        "year": "Election year; 2012, 2017 or 2022. Not a ward panel.",
        "ward_number": (
            "Ward identifier within year, including corporation suffix in 2017."
        ),
        "reservation_raw": "Source seat category: W/WOMAN, G/GENERAL, SC or SCW.",
        "assembly_id": (
            "Assembly constituency; Goyal mapping in 2012/2017, SEC gazette in 2022."
        ),
        "winner_party": (
            "Election roster party; Goyal in 2012/2017, OpenCity/Lok Dhaba in 2022."
        ),
        "profile_party": (
            "MyNeta party; must equal roster party for every linked profile."
        ),
        "education": (
            "MyNeta education category verbatim; unspecified categories "
            "are not degrees."
        ),
        "age": "MyNeta age in years; null when absent or unparseable.",
        "pending_cases": (
            "Number of accusation/pending-case table entries, excluding "
            "convictions; null if unknown."
        ),
        "convicted_cases": "Separate conviction-table entry count; null if unknown.",
        "occupation": "MyNeta profession verbatim; not used as a quality ranking.",
        "source_url": "Individual MyNeta profile URL; null for unlinked winners.",
        "source_sha256": "SHA-256 of UTF-8 cached response body.",
        "source_capture": "UTC timestamp when the response was fetched.",
        "source_path": "Cached JSON gzip path relative to qualification_audit.",
        "quota": "1 for a women-reserved seat, 0 for a seat open to either sex.",
        "caste_reservation": "SC or NONE; distinct from the winner's caste.",
    }
    schema = pq.read_schema(release / "winners.parquet")
    dictionary = {
        "row_unit": "One elected ward in one election",
        "key": ["year", "ward_number"],
        "missing": "Nulls remain unknown; no missing profile is coded zero.",
        "columns": [
            {
                "name": field.name,
                "type": str(field.type),
                "description": definitions[field.name],
            }
            for field in schema
        ],
    }
    (release / "schema.json").write_text(json.dumps(dictionary, indent=2) + "\n")
    inputs = [
        *sources,
        {
            "file": "../delhi_2022.pdf",
            "url": "https://sec.delhi.gov.in/sites/default/files/SEC/generic_multiple_files/reservationorder_0.pdf",
            "sha256": hashlib.sha256(gazette.read_bytes()).hexdigest(),
            "pages": "11-16, Annexure B",
        },
    ]
    (release / "source_manifest.json").write_text(json.dumps(inputs, indent=2) + "\n")
    return summary


@command("parse", state="Delhi")
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--gazette", type=Path, required=True)
    args = parser.parse_args()
    build(args.root, args.gazette)


if __name__ == "__main__":
    main()
