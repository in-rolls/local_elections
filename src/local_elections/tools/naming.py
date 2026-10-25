"""Check column names against docs/naming.md.

    python -m local_elections.tools.naming [--strict] [paths ...]

With no paths, checks the pooled tables in data/master/ and every parquet file
a sibling is pinned to in data/sources.json (read from the pinned cache).
Prints each violation; --strict exits non-zero if there is one.
"""

import argparse
import json
import sys
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from local_elections.common import sources
from local_elections.common.runlog import command
from local_elections.paths import ROOT

FORBIDDEN = {"gender", "sex", "female", "women", "category", "quota"}
# Retired names whose words are allowed but whose order is not (docs/naming.md 5).
RETIRED = {
    "woman_reserved": "reserved_woman",
    "caste_scheme": "reserved_caste_scheme",
    "gender_stated": "reserved_woman_stated",
}
# Inferred or transliterated values must say how, per row (docs/naming.md section 3).
NEEDS_METHOD = ("_latin", "_probability")


def violations(columns, flags=()):
    """`flags` are true/false columns: a flag such as winner_printed_in_latin
    says whether something was printed in Latin and is not itself a reading,
    so it needs no _method.
    """
    names = set(columns)
    out = []
    for name in columns:
        words = name.lower().split("_")
        bad = sorted(FORBIDDEN & set(words))
        if bad:
            out.append((name, f"uses {', '.join(bad)}"))
        if "reservation" in words:
            out.append((name, "uses reservation; the seat's quota is reserved_*"))
        if name in RETIRED:
            out.append((name, f"renamed to {RETIRED[name]}"))
        if (
            name.endswith(NEEDS_METHOD)
            and name not in flags
            and f"{name}_method" not in names
        ):
            out.append((name, f"has no {name}_method beside it"))
    return out


def pooled_files():
    yield from sorted((ROOT / "data" / "master").glob("*.parquet"))
    pins = json.loads((ROOT / "data" / "sources.json").read_text())
    for repo, spec in pins.items():
        resolved = sources.resolve(repo)
        if resolved is None:
            continue
        directory, _ = resolved
        for relative in spec["files"]:
            if relative.endswith(".parquet"):
                yield directory / relative


def check(paths):
    """(path, column, why) for every violation in these parquet files."""
    found = []
    for path in paths:
        schema = pq.read_schema(path)
        names = schema.names
        flags = {f.name for f in schema if pa.types.is_boolean(f.type)}
        if path.name == "master_extras.parquet":
            names = sorted(
                set(pq.read_table(path, columns=["column"]).column(0).to_pylist())
            )
        found += [(path, name, why) for name, why in violations(names, flags)]
    return found


@command("validate", artifact="naming")
def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("paths", nargs="*", type=Path)
    ap.add_argument("--strict", action="store_true")
    args = ap.parse_args()
    found = check(args.paths or pooled_files())
    for path, name, why in found:
        print(f"{path}: {name}: {why}")
    print(f"{len(found)} naming violation(s)")
    if args.strict and found:
        sys.exit(1)


if __name__ == "__main__":
    main()
