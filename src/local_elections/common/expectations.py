"""Triage every dataset against the declared expectations.

Three levels, because a bad value can hide at any of them:

  column    the value itself - wrong type, outside the enum, outside the range,
            a name three times longer than a name should be
  row       agreements between columns that no single column can see, like the
            reservation label matching the two fields it summarises
  dataset   shape - row counts against a plausible band, and the distribution of
            name lengths. A file whose median name length doubles has absorbed
            an adjacent column, which is invisible one row at a time.

Writes data/expectations_report.csv: one row per violated expectation, with the
count, the share, three example values, and the source document and page of the
first offender, so a finding points at a gazette page rather than at a number.
Exits non-zero if anything is `error` severity.
"""

import argparse
import collections
import csv
import re
import statistics
import sys

from local_elections.common import datasets as DS
from local_elections.common import dictionary as D
from local_elections.common import reference
from local_elections.common.runlog import command
from local_elections.paths import ROOT

DATA = ROOT / "data"
REPORT = DATA / "expectations_report.csv"

REPORT_COLUMNS = [
    "severity",
    "file",
    "scope",
    "column",
    "rule",
    "count",
    "share",
    "examples",
    "first_source",
    "first_page",
]


def datasets():
    return DS.parsed()


class Findings:
    def __init__(self):
        self.rows = []

    def add(self, severity, path, scope, column, rule, offenders, total):
        if not offenders:
            return
        examples = " | ".join(str(v)[:30] for _, v in offenders[:3])
        first = offenders[0][0]
        self.rows.append(
            {
                "severity": severity,
                "file": str(path.relative_to(DATA)),
                "scope": scope,
                "column": column,
                "rule": rule,
                "count": len(offenders),
                "share": round(len(offenders) / max(total, 1), 4),
                "examples": examples,
                "first_source": (first or {}).get("source_path", ""),
                "first_page": (first or {}).get("source_page", ""),
            }
        )

    def errors(self):
        return [r for r in self.rows if r["severity"] == D.ERROR]


# ---------------------------------------------------------------- columns


def is_integer(value):
    return bool(re.fullmatch(r"-?\d+", value.strip()))


def check_column(findings, path, rows, name, values):
    """`values` is a list of (row, value) for the non-blank cells."""
    spec = D.BY_NAME.get(name) or D.BY_NAME.get(D.ALIAS_OF.get(name, ""))
    total = len(rows)
    if spec is None:
        findings.add(
            D.WARN,
            path,
            "column",
            name,
            "column is not declared in dictionary.py",
            [(rows[0], name)],
            total,
        )
        return

    severity = spec["severity"]
    blank = [(r, "") for r in rows if not (r.get(name) or "").strip()]
    if spec["max_blank"] is not None and blank:
        share = len(blank) / max(total, 1)
        if share >= 1.0:
            # The column is simply not in this source - J&K 2010 has no
            # district column, a nomination list has no winner. Partial
            # blankness is the suspicious case; total blankness is a fact about
            # the document.
            findings.add(
                D.INFO,
                path,
                "column",
                name,
                "not present in this source (entirely blank)",
                blank[:1],
                total,
            )
        elif share > spec["max_blank"]:
            declared_reasons = {
                reference.declared_partial_blank(
                    row.get("state", ""),
                    row.get("year", ""),
                    row.get("tier", ""),
                    name,
                )
                for row in rows
            }
            if len(declared_reasons) == 1 and None not in declared_reasons:
                findings.add(
                    D.INFO,
                    path,
                    "column",
                    name,
                    f"declared source blank: {declared_reasons.pop()}",
                    blank[:1],
                    total,
                )
            else:
                findings.add(
                    severity,
                    path,
                    "column",
                    name,
                    f"blank share {share:.0%} above the "
                    f"{spec['max_blank']:.0%} tolerated",
                    blank,
                    total,
                )

    dtype = spec["dtype"]
    if dtype in ("integer", "boolean"):
        bad = [(r, v) for r, v in values if not is_integer(v)]
        findings.add(severity, path, "column", name, "not an integer", bad, total)
        if dtype == "boolean":
            bad = [(r, v) for r, v in values if v.strip() not in ("0", "1")]
            findings.add(severity, path, "column", name, "not 0 or 1", bad, total)
    elif dtype == "enum":
        allowed = set(spec["allowed"] or ())
        bad = [(r, v) for r, v in values if v not in allowed]
        findings.add(
            severity, path, "column", name, f"outside {sorted(allowed)[:6]}", bad, total
        )
    elif dtype == "path":
        missing = [(r, v) for r, v in values if not (ROOT / v).exists()]
        findings.add(
            severity, path, "column", name, "document not on disk", missing, total
        )
    elif dtype == "roman_or_integer":
        bad = [(r, v) for r, v in values if not is_integer(v) and not D.ROMAN.match(v)]
        findings.add(
            severity,
            path,
            "column",
            name,
            "neither a number nor a Roman numeral",
            bad,
            total,
        )

    if spec["range"] and dtype in ("integer", "boolean"):
        low, high = spec["range"]
        bad = [
            (r, v) for r, v in values if is_integer(v) and not (low <= int(v) <= high)
        ]
        findings.add(
            severity, path, "column", name, f"outside {low}..{high}", bad, total
        )

    if spec["length"]:
        low, high = spec["length"]
        bad = [(r, v) for r, v in values if not (low <= len(v) <= high)]
        findings.add(
            severity, path, "column", name, f"length outside {low}..{high}", bad, total
        )

    if spec["pattern"]:
        pattern = re.compile(spec["pattern"])
        bad = [(r, v) for r, v in values if not pattern.match(v)]
        findings.add(
            severity,
            path,
            "column",
            name,
            f"does not match {spec['pattern']}",
            bad,
            total,
        )


# ------------------------------------------------------------------- rows


def label_for(caste, woman):
    prefix = {"SC": "SC", "ST": "ST", "BC": "BC", "NONE": ""}.get(caste, "")
    return f"{prefix} {'Woman' if woman else 'Other than Woman'}".strip()


def check_rows(findings, path, rows):
    total = len(rows)

    # the label is written separately from the fields it summarises
    bad = [
        (
            r,
            f"{r.get('reservation')} vs {r.get('caste_reservation')}/"
            f"{r.get('woman_reserved')}",
        )
        for r in rows
        if r.get("reservation")
        != label_for(
            r.get("caste_reservation", ""), str(r.get("woman_reserved")) == "1"
        )
    ]
    findings.add(
        D.ERROR,
        path,
        "row",
        "reservation",
        "label disagrees with caste_reservation + woman_reserved",
        bad,
        total,
    )

    if rows and "reservation_raw" in rows[0]:
        bad = [
            (r, f"{r.get('caste_reservation')}/{r.get('woman_reserved')}")
            for r in rows
            if not (r.get("reservation_raw") or "").strip()
            and (
                r.get("caste_reservation") not in ("", "NONE")
                or str(r.get("woman_reserved")) == "1"
            )
        ]
        findings.add(
            D.ERROR,
            path,
            "row",
            "reservation_raw",
            "blank source mark is valid only for an open seat",
            bad,
            total,
        )

    # a seat-level row has no ward; a ward row must have one
    seat_tiers = {
        "gp_head",
        "gp_vice_head",
        "block_member",
        "block_head",
        "block_vice_head",
        "zp_member",
        "zp_head",
        "kachahari_head",
    }
    bad = [
        (r, r.get("ward_no"))
        for r in rows
        if r.get("tier") in seat_tiers and (r.get("ward_no") or "").strip()
    ]
    findings.add(
        D.WARN,
        path,
        "row",
        "ward_no",
        "seat-level row carries a ward number",
        bad,
        total,
    )
    bad = [
        (r, "")
        for r in rows
        if r.get("tier") in ("gp_ward", "ulb_ward", "kachahari_member")
        and not (r.get("ward_no") or "").strip()
    ]
    findings.add(
        D.WARN, path, "row", "ward_no", "ward row has no ward number", bad, total
    )

    # AP: the completeness flag must agree with the two counts it summarises
    if rows and "ward_list_complete" in rows[0]:
        bad = []
        for r in rows:
            flag = (r.get("ward_list_complete") or "").strip()
            count, got = (
                (r.get("ward_count") or "").strip(),
                (r.get("wards_parsed") or "").strip(),
            )
            if (
                flag
                and count.isdigit()
                and got.isdigit()
                and (flag == "1") != (int(got) == int(count))
            ):
                bad.append((r, f"flag={flag} {got}/{count}"))
        findings.add(
            D.ERROR,
            path,
            "row",
            "ward_list_complete",
            "flag disagrees with wards_parsed vs ward_count",
            bad,
            total,
        )


# --------------------------------------------------------------- datasets


def check_dataset(findings, path, rows):
    total = len(rows)
    state = rows[0].get("state", "")
    for tier, subset in collections.Counter(r.get("tier") for r in rows).items():
        band = D.ROW_BANDS.get((state, tier))
        if band and not (band[0] <= subset <= band[1]):
            findings.add(
                D.WARN,
                path,
                "dataset",
                tier,
                f"{subset} rows outside the plausible band {band[0]}..{band[1]}",
                [(rows[0], subset)],
                total,
            )

    # A name column whose length distribution jumps has absorbed its neighbour.
    for name in ("gram_panchayat", "halqa", "block", "district"):
        values = [(r.get(name) or "").strip() for r in rows]
        values = [v for v in values if v]
        if len(values) < 20:
            continue
        p95 = sorted(map(len, values))[int(len(values) * 0.95)]
        median = statistics.median(map(len, values))
        if p95 > 45 or (median and p95 > 4 * median):
            findings.add(
                D.WARN,
                path,
                "dataset",
                name,
                f"length distribution is skewed - median {median:.0f}, "
                f"p95 {p95}; a name this long has usually swallowed "
                f"the next column",
                [(rows[0], f"p95={p95}")],
                total,
            )


@command("validate", expectation_set="repository")
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    findings = Findings()
    seen_columns = set()
    for path, rows in datasets():
        columns = list(rows[0])
        seen_columns |= set(columns)
        for name in columns:
            values = [(r, (r.get(name) or "").strip()) for r in rows]
            values = [(r, v) for r, v in values if v]
            check_column(findings, path, rows, name, values)
        check_rows(findings, path, rows)
        check_dataset(findings, path, rows)

    undeclared = seen_columns - set(D.BY_NAME) - set(D.ALIAS_OF)
    order = {D.ERROR: 0, D.WARN: 1, D.INFO: 2}
    findings.rows.sort(key=lambda r: (order[r["severity"]], -r["count"]))

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    with REPORT.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=REPORT_COLUMNS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(findings.rows)

    counts = collections.Counter(r["severity"] for r in findings.rows)
    print(f"\n{len(findings.rows)} findings -> {REPORT.relative_to(ROOT)}")
    print("  " + "  ".join(f"{k}={v}" for k, v in counts.most_common()))
    if undeclared:
        print(f"  undeclared columns: {sorted(undeclared)}")

    if not args.quiet:
        print(f"\n{'sev':6s} {'file':44s} {'column':20s} {'n':>6s}  rule")
        for row in findings.rows[:28]:
            print(
                f"{row['severity']:6s} {row['file'][:44]:44s} "
                f"{row['column'][:20]:20s} {row['count']:6d}  {row['rule'][:60]}"
            )

    errors = findings.errors()
    print(
        f"\n{'FAILED' if errors else 'OK'}: {len(errors)} error-severity "
        f"expectation(s) violated\n"
    )
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
