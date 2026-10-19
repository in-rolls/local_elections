"""Write the published tables' Table Schemas and validate the files against them.

    python -m local_elections.tools.contract schema    # write schemas/*.json
    python -m local_elections.tools.contract validate  # check data/master/

The contract is the Table Schema JSON in schemas/, so any Frictionless tool can
read it. Validation here goes through pandera, which builds its checks from
that same JSON (`from_frictionless_schema`) and runs them vectorised; the
frictionless validator itself takes over half an hour on the master files and
reads a blank integer as NaN. Two of pandera's defaults are switched off
because they would hide exactly what a contract is for: it coerces every
column (turning the text "1" into True), and it maps types to numpy dtypes,
which cannot hold a null integer. Columns are checked against their Arrow
types as stored; dictionary encoding is a storage detail and is decoded first.

Keys that span files - a row_id unique across the 21 master files, a link end
that must be a master row - are checked with pyarrow.

data/master/contract_report.csv has one row per (file, column, check) with the
count of failing rows and an example value. A column whose type is wrong is
reported once for the type, and its value checks are not run.
"""

import collections
import csv
import sys

import pandas as pd
import pandera.pandas as pdx
import pyarrow as pa
import pyarrow.parquet as pq
from pandera.errors import SchemaErrors
from pandera.io.pandas_io import from_frictionless_schema

from local_elections.common import contract as C
from local_elections.common.runlog import command
from local_elections.paths import ROOT

SCHEMAS = ROOT / "schemas"
MASTER = ROOT / "data" / "master"
REPORT = MASTER / "contract_report.csv"
ARROW = {
    "string": pd.ArrowDtype(pa.string()),
    "integer": pd.ArrowDtype(pa.int64()),
    "boolean": pd.ArrowDtype(pa.bool_()),
    "number": pd.ArrowDtype(pa.float64()),
}


def files(name):
    paths = sorted(MASTER.glob(C.FILES[name]))
    if name == "master":
        paths = [p for p in paths if p.name != "master_extras.parquet"]
    return paths


def write_schemas():
    SCHEMAS.mkdir(exist_ok=True)
    for name in C.SCHEMAS:
        (SCHEMAS / f"{name}.json").write_text(C.dumps(name), encoding="utf-8")
    print(f"wrote {len(C.SCHEMAS)} schemas to {SCHEMAS.relative_to(ROOT)}/")


def pandera_schema(name):
    descriptor = C.SCHEMAS[name]
    parsed = from_frictionless_schema(descriptor)
    columns = parsed.update_columns(
        {
            f["name"]: {"coerce": False, "dtype": ARROW[f["type"]]}
            for f in descriptor["fields"]
        }
    ).columns
    return pdx.DataFrameSchema(
        columns,
        coerce=False,
        strict=True,
        ordered=True,
        unique=parsed.unique,
        name=name,
    )


def load(path):
    table = pq.read_table(path)
    plain = []
    for f in table.schema:
        t = f.type.value_type if pa.types.is_dictionary(f.type) else f.type
        plain.append(
            pa.field(f.name, pa.string() if pa.types.is_large_string(t) else t)
        )
    return table.cast(pa.schema(plain)).to_pandas(types_mapper=pd.ArrowDtype)


def check_file(schema, path):
    frame = load(path)
    try:
        schema.validate(frame, lazy=True)
    except SchemaErrors as errors:
        cases = errors.failure_cases
        # a failed dtype check is reported once, as the column's actual dtype
        grouped = cases.groupby(["column", "check"], dropna=False, sort=False)
        out = []
        typed = {c for c, k in grouped.groups if str(k).startswith("dtype(")}
        for (column, check), group in grouped:
            if column in typed and not str(check).startswith("dtype("):
                continue  # value checks on a mistyped column only repeat the type error
            count = len(frame) if str(check).startswith("dtype(") else len(group)
            example = group["failure_case"].iloc[0]
            if str(check).startswith("dtype("):
                example = str(frame[column].dtype) if column in frame else "missing"
            out.append((path.name, column, str(check), count, str(example)[:80]))
        return len(frame), out
    return len(frame), []


def cross_file_keys():
    out = []
    master_ids = collections.Counter()
    for path in files("master"):
        master_ids.update(pq.read_table(path, columns=["row_id"]).column(0).to_pylist())
    dup = [k for k, n in master_ids.items() if n > 1]
    out.append(
        ("master_*", "row_id", "unique_across_files", len(dup), dup[0] if dup else "")
    )
    known = set(master_ids)
    for name, column in [
        ("candidates", "row_id"),
        ("extras", "row_id"),
        ("seat_links", "from_row_id"),
        ("seat_links", "to_row_id"),
    ]:
        for path in files(name):
            values = pq.read_table(path, columns=[column]).column(0).to_pylist()
            missing = [v for v in values if v not in known]
            out.append(
                (
                    path.name,
                    column,
                    "foreign_key_to_master",
                    len(missing),
                    missing[0] if missing else "",
                )
            )
    return out


def validate():
    out = []
    for name in C.SCHEMAS:
        schema = pandera_schema(name)
        for path in files(name):
            n, found = check_file(schema, path)
            out.extend(found)
            print(f"{path.name}: {n:,} rows, {len(found)} failing checks", flush=True)
    out.extend(cross_file_keys())
    with REPORT.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh, lineterminator="\n")
        writer.writerow(["file", "column", "check", "failing_rows", "example"])
        writer.writerows(out)
    failing = [r for r in out if r[3]]
    where = REPORT.relative_to(ROOT)
    print(f"{len(failing)} failing (file, column, check) groups; see {where}")
    return 1 if failing else 0


@command("validate", artifact="contract")
def main(argv=None):
    action = (argv or sys.argv[1:] or ["validate"])[0]
    if action == "schema":
        write_schemas()
        return 0
    if action == "validate":
        write_schemas()
        return validate()
    raise SystemExit(f"unknown action {action!r}; use schema or validate")


if __name__ == "__main__":
    sys.exit(main())
