"""Verify Chandigarh's published sources, panels, and metadata without writing."""

import argparse
import json
from pathlib import Path

import pyarrow.parquet as pq

from local_elections.common.runlog import command
from local_elections.states.chandigarh import extension, panel, parse


def validate(release):
    original = json.loads((release / "manifest.json").read_text())
    for name, record in original["files"].items():
        if extension.digest(release / name) != record["sha256"]:
            raise ValueError(f"Published output changed: {name}")
        table = pq.read_table(release / name)
        if table.num_rows != record["rows"]:
            raise ValueError(f"Published row count changed: {name}")
        if {f.name: str(f.type) for f in table.schema} != record["columns"]:
            raise ValueError(f"Published schema changed: {name}")
    for name, expected in original["metadata"].items():
        if extension.digest(release / name) != expected:
            raise ValueError(f"Published metadata changed: {name}")
    for source in original["sources"]:
        if extension.digest(parse.ROOT / source["path"]) != source["sha256"]:
            raise ValueError(f"Retained original changed: {source['path']}")
    later = json.loads((release / "ward_panel_2011_2016_manifest.json").read_text())
    for record in later["outputs"]:
        if extension.digest(release / record["path"]) != record["sha256"]:
            raise ValueError(f"Published output changed: {record['path']}")
    for source in later["sources"]:
        if extension.digest(parse.ROOT / source["path"]) != source["sha256"]:
            raise ValueError(f"Retained input changed: {source['path']}")
    panel.validate(pq.read_table(release / "ward_panel_2006_2011.parquet"))
    rows = pq.read_table(release / "ward_panel_2011_2016.parquet").to_pylist()
    extension.validate(rows)
    if rows != extension.build_rows():
        raise ValueError("Published panel differs from original-source reconstruction")
    return {"original_tables": len(original["files"]), "new_panel_wards": len(rows)}


@command("validate", artifact="chandigarh_elections")
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--release", type=Path, default=parse.DATA / "release")
    print(json.dumps(validate(ap.parse_args().release), indent=2))


if __name__ == "__main__":
    main()
