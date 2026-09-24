"""Generate DICTIONARY.md from dictionary.py, so the docs cannot drift.

The readme in this repo drifted twice while it was written by hand. The column
rules are checked by expectations.py and described here from the same
declarations, so a rule cannot change without the documentation changing too.
"""

import sys

from local_elections.common import dictionary as D
from local_elections.common.runlog import command
from local_elections.paths import ROOT

OUT = ROOT / "DICTIONARY.md"

HEAD = """# Data dictionary

Generated from `scripts/common/dictionary.py` by `make dictionary` — edit the
declarations, not this file.

Every column is checked against these rules by `make expect`, which writes
`data/expectations_report.csv`: one row per violated expectation, with the count
and the source document and page of the first offender, so a finding points at a
gazette page rather than at a number.

Severity is **error** when a value cannot be right (outside its enum or range),
**warn** when it is suspicious (blank more often than expected, an unusual
length), and **info** when it is known and accepted.

A column that is *entirely* blank in a file is reported as info, not warn: it
means the source has no such column — J&K's 2010 files carry no district, a
nomination list carries no winner — and that is a fact about the document rather
than a defect.

"""


def constraints(spec):
    bits = []
    if spec["allowed"]:
        bits.append("one of " + ", ".join(f"`{a}`" for a in spec["allowed"]))
    if spec["range"]:
        bits.append(f"range {spec['range'][0]}–{spec['range'][1]}")
    if spec["length"]:
        bits.append(f"length {spec['length'][0]}–{spec['length'][1]}")
    if spec["max_blank"] is not None:
        bits.append(f"≤{spec['max_blank']:.0%} blank")
    if spec["aliases"]:
        bits.append("also called " + ", ".join(f"`{a}`" for a in spec["aliases"]))
    return "; ".join(bits) or "—"


@command("document", artifact="data_dictionary")
def main():
    lines = [
        HEAD,
        "| Column | Type | Severity | Constraints | Notes |",
        "|---|---|---|---|---|",
    ]
    for spec in D.COLUMNS:
        lines.append(
            f"| `{spec['name']}` | {spec['dtype']} | {spec['severity']} | "
            f"{constraints(spec)} | {spec['note'] or ''} |"
        )

    lines.append("\n## Plausible row counts\n")
    lines.append("A file outside its band has lost rows or double counted them.\n")
    lines.append("| State | Tier | Expected rows |")
    lines.append("|---|---|---|")
    for (state, tier), (low, high) in sorted(D.ROW_BANDS.items()):
        lines.append(f"| {state} | {tier} | {low:,}–{high:,} |")

    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {OUT.name} ({len(D.COLUMNS)} columns)")


if __name__ == "__main__":
    sys.exit(main())
