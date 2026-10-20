import json

import pandas as pd
import pyarrow as pa
import pytest
from pandera.errors import SchemaErrors

from local_elections.common import contract as C
from local_elections.common import master as M
from local_elections.paths import ROOT
from local_elections.tools import build_master
from local_elections.tools import contract as T


@pytest.mark.parametrize("name", sorted(C.SCHEMAS))
def test_committed_schema_is_generated(name):
    committed = json.loads(
        (ROOT / "schemas" / f"{name}.json").read_text(encoding="utf-8")
    )
    assert committed == json.loads(C.dumps(name)), "run make contract"


@pytest.mark.parametrize(
    ("name", "columns"),
    [
        ("master", M.MASTER_COLUMNS),
        ("candidates", M.CANDIDATE_COLUMNS),
        ("seat_links", build_master.SEAT_LINK_COLUMNS),
    ],
)
def test_contract_declares_every_published_column_in_order(name, columns):
    # the contract describes the tables as written, under their published names
    assert [f["name"] for f in C.SCHEMAS[name]["fields"]] == [
        M.published(c) for c in columns
    ]


def frame(**overrides):
    row = {
        "link_id": "0123456789ab",
        "state": "Uttarakhand",
        "tier": "gp_head",
        "from_year": 2008,
        "to_year": 2014,
        "from_row_id": "0123456789ab",
        "to_row_id": "ba9876543210",
        "link_pass": "name",
        "name_score": 0.93,
        "source_repo": "local_elections_uttarakhand",
        "source_commit": "f" * 40,
        "source_path": "data/linkage/gp_2008_2014.parquet",
    }
    row.update(overrides)
    types = {f["name"]: T.ARROW[f["type"]] for f in C.SEAT_LINKS["fields"]}
    return pd.DataFrame([row]).astype(types)


def test_a_valid_row_passes():
    T.pandera_schema("seat_links").validate(frame(), lazy=True)


@pytest.mark.parametrize(
    "overrides",
    [
        {"state": "Uttaranchal"},  # not an enumerated state
        {"tier": "pradhan"},  # local name, not the canonical tier
        {"name_score": 1.5},  # outside 0-1
        {"from_year": 1989},  # outside the year range
        {"source_commit": "f" * 12},  # abbreviated commit
        {"link_id": None},  # primary key blank
    ],
)
def test_each_rule_catches_a_violation(overrides):
    with pytest.raises(SchemaErrors):
        T.pandera_schema("seat_links").validate(frame(**overrides), lazy=True)


def test_a_stored_type_mismatch_is_not_coerced_away():
    bad = frame().astype({"from_year": pd.ArrowDtype(pa.string())})
    with pytest.raises(SchemaErrors):
        T.pandera_schema("seat_links").validate(bad, lazy=True)
