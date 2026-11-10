"""Contracts for the supplemental MP winner list and current council roster."""

import csv
import hashlib
import json

import pyarrow as pa
import pyarrow.parquet as pq
from frictionless import Resource, Schema

from local_elections.common.contract import flag, integer, text
from local_elections.paths import ROOT

BODY = text(
    "body", "Municipal corporation name.", required=True, enum=["Bhopal", "Indore"]
)
WARD = text(
    "ward_no", "Printed ward number; null only for the roster's unlabeled entry."
)
SOURCE = [
    text(
        "source_status",
        "Evidence status; current roster is not an election result.",
        required=True,
    ),
    text(
        "source_path",
        "Original file path relative to the repository root.",
        required=True,
    ),
    text(
        "source_sha256",
        "SHA-256 of the complete original source bytes.",
        required=True,
        pattern="[0-9a-f]{64}",
    ),
]
ROW = integer(
    "source_row",
    "One-based extracted list or CMS array position.",
    required=True,
    minimum=1,
)
CONTRACTS = {
    "winners": {
        "description": (
            "One provisional 2022 news-reported winner per municipal ward. "
            "Sex, reservation and votes are unreported and remain null."
        ),
        "primaryKey": ["year", "body", "ward_no"],
        "fields": [
            integer(
                "year",
                "Election year of the dated news list.",
                required=True,
                enum=[2022],
            ),
            BODY,
            text(
                "tier",
                "Canonical office; excludes the mayor.",
                required=True,
                enum=["ulb_ward"],
            ),
            dict(WARD, constraints={"required": True}),
            text(
                "winner",
                "Reported winner name in the original script and spelling.",
                required=True,
                minLength=1,
            ),
            text("party_raw", "Printed Hindi party label.", required=True),
            text(
                "party",
                "Normalized party: BJP, INC or IND; mapping documented in README.",
                required=True,
                enum=["BJP", "INC", "IND"],
            ),
            flag(
                "winner_woman",
                "Unreported by these lists; always null, not inferred from names.",
            ),
            flag("reserved_woman", "Unreported by these lists; always null."),
            integer("votes", "Unreported by these lists; always null.", minimum=0),
            text(
                "source_publication_date",
                "Original NewsArticle datePublished string.",
                required=True,
            ),
            *SOURCE,
            text("source_url", "Original article URL.", required=True),
            ROW,
            text(
                "raw_line",
                "Unchanged extracted line supporting the name, ward and party.",
                required=True,
            ),
        ],
    },
    "indore_council_roster": {
        "description": (
            "One entry in the current Indore council CMS; not election-time winners. "
            "The unlabeled entry is not assigned a ward."
        ),
        "primaryKey": ["source_entry_id"],
        "fields": [
            dict(BODY, constraints={"required": True, "enum": ["Indore"]}),
            text(
                "source_entry_id",
                "Unique CMS entry identifier; not a ward number.",
                required=True,
            ),
            WARD,
            text(
                "ward_label_raw",
                "Original ward-number label, including an empty string.",
            ),
            text("ward_name_raw", "Original named ward label."),
            text(
                "title_raw",
                "Original title, including honorific or court-status text; "
                "null if absent.",
            ),
            flag(
                "member_woman_from_honorific",
                "1 for Mrs./Ms., 0 for Mr., null otherwise. Applies only to this "
                "roster entry; does not measure 2022 winner sex.",
            ),
            text(
                "source_updated_at",
                "Original CMS updatedAt timestamp; not an election date.",
                required=True,
            ),
            text(
                "retrieved_at",
                "UTC source retrieval timestamp from the acquisition receipt.",
                required=True,
            ),
            *SOURCE,
            ROW,
        ],
    },
}


def arrow_schema(name):
    types = {"string": pa.string(), "integer": pa.int64(), "int8": pa.int8()}
    return pa.schema(
        [
            pa.field(
                f["name"],
                types[f.get("arrow", f["type"])],
                nullable=not f.get("constraints", {}).get("required", False),
            )
            for f in CONTRACTS[name]["fields"]
        ]
    )


def validate(name, table):
    if table.schema != arrow_schema(name):
        raise ValueError(f"{name}: Arrow schema differs from the contract")
    report = Resource(data=table.to_pylist(), schema=Schema(CONTRACTS[name])).validate()
    if not report.valid:
        raise ValueError(f"{name}: {report.flatten(['type', 'message'])}")
    if name == "winners":
        for column in ("winner_woman", "reserved_woman", "votes"):
            if table[column].null_count != table.num_rows:
                raise ValueError(f"{name}: {column} must remain unreported")


def write_metadata(directory):
    for name, descriptor in CONTRACTS.items():
        (directory / f"{name}.schema.json").write_text(
            json.dumps(descriptor, indent=2) + "\n"
        )
    with (directory / "dictionary.csv").open("w", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(
            ["table", "column", "type", "required", "description", "missing"]
        )
        for name, descriptor in CONTRACTS.items():
            for f in descriptor["fields"]:
                required = f.get("constraints", {}).get("required", False)
                writer.writerow(
                    [
                        name,
                        f["name"],
                        str(arrow_schema(name).field(f["name"]).type),
                        required,
                        f["description"],
                        "not allowed"
                        if required
                        else "not reported or not interpretable; see description",
                    ]
                )


def verify(directory):
    audit = json.loads((directory / "audit.json").read_text())
    hashes = {
        "winners": audit["parquet_sha256"],
        "indore_council_roster": audit["current_council_roster"]["sha256"],
    }
    for name, descriptor in CONTRACTS.items():
        path = directory / f"{name}.parquet"
        if hashlib.sha256(path.read_bytes()).hexdigest() != hashes[name]:
            raise ValueError(f"Output checksum changed: {path}")
        if json.loads((directory / f"{name}.schema.json").read_text()) != descriptor:
            raise ValueError(f"Stale schema: {name}")
        table = pq.read_table(path)
        validate(name, table)
        sources = {
            (row["source_path"], row["source_sha256"]) for row in table.to_pylist()
        }
        for relative, expected in sources:
            source = ROOT / relative
            if hashlib.sha256(source.read_bytes()).hexdigest() != expected:
                raise ValueError(f"Source checksum changed: {relative}")
    print("MP urban: both table contracts, keys and output hashes verified")
