"""A validation battery every state runs, so a pooled dataset is not assembled
from files checked to four different standards.

Each state was validated against its own quirks while it was being built, which
was the right way to get them out but leaves no common floor. This module is
that floor. States keep their own substantive checks - Goa's cross-cycle ward
set, J&K's populations, AP's OCR repairs - and add them on top.

Three layers, in increasing order of how much they can actually catch:

  structural   cheap, mechanical, and true of every state. Cannot catch a
               misread category, but catches a shifted column, a lost key, a
               row counted twice.
  coverage     did we get everything the sources hold, and where we did not, is
               that the source's limit or ours.
  substantive  appeals to something outside the data - a published total, a
               statutory share, a population. These are the only checks that
               reliably catch silent corruption, because every parser bug in
               this repo produced plausible values rather than an error.
"""

import collections
import pathlib
import re
import subprocess

from local_elections.common import canon, dictionary

CASTES = {"SC", "ST", "BC", "NONE"}
SEAT_KEY = canon.SEAT_IDENTITY_FIELDS


def pct(part, whole):
    """A percentage, and zero rather than a crash when the denominator is.

    Three states' validators each carried this identically. A share of nothing
    is the case that turns up whenever a slice is empty, which is exactly when
    a validator is most likely to be run.
    """
    return 100.0 * part / whole if whole else 0.0


class Report:
    """Collects check results and decides the exit status.

    `hard=False` records a warning: real information, but not a reason to fail a
    build. Anything that means the shipped data is wrong should be hard.
    """

    def __init__(self, title):
        self.failed = 0
        self.warned = 0
        print(f"\n=== {title} ===\n")

    def check(self, ok, label, detail="", hard=True):
        if ok:
            status = "PASS"
        elif hard:
            status = "FAIL"
            self.failed += 1
        else:
            status = "WARN"
            self.warned += 1
        print(f"  [{status}] {label}" + (f" - {detail}" if detail else ""))
        return ok

    def info(self, label, detail=""):
        print(f"  [INFO] {label}" + (f" - {detail}" if detail else ""))

    def section(self, name):
        print(f"\n{name}")

    def finish(self):
        verdict = "FAILED" if self.failed else "OK"
        print(f"\n{verdict}: {self.failed} hard, {self.warned} warning(s)\n")
        return 1 if self.failed else 0


# ------------------------------------------------------------- structural


def structural(report, rows, root, key=None, required=()):
    """The checks that hold for every state regardless of its quirks."""
    report.section("Structural")
    if not rows:
        report.check(False, "rows present", "file is empty")
        return

    columns = set(rows[0])
    missing = set(required) - columns
    report.check(not missing, "required columns present", f"missing {sorted(missing)}")

    bad_caste = [r for r in rows if r.get("caste_reservation") not in CASTES]
    report.check(
        not bad_caste,
        "caste_reservation in {SC, ST, BC, NONE}",
        f"{len(bad_caste)} rows",
    )

    bad_woman = [r for r in rows if str(r.get("woman_reserved")) not in ("0", "1")]
    report.check(not bad_woman, "woman_reserved in {0, 1}", f"{len(bad_woman)} rows")

    # The label is written separately from the two fields it summarises, so the
    # two can silently disagree; that would surface as a contradiction only for
    # whoever reads the label.
    mismatched = [
        r
        for r in rows
        if r.get("reservation")
        and r["reservation"]
        != _label(r.get("caste_reservation"), str(r.get("woman_reserved")) == "1")
    ]
    report.check(
        not mismatched,
        "reservation label agrees with its two fields",
        f"{len(mismatched)} rows",
    )

    blank = [
        r for r in rows if not r.get("state") or not r.get("year") or not r.get("tier")
    ]
    report.check(not blank, "no blank state/year/tier", f"{len(blank)} rows")

    # J&K calls it halqa; without the alias the key degrades to
    # (district, block) and reports collisions that are really just a missing
    # column. The mapping is read from the dictionary rather than repeated here,
    # so there is one place that decides what the panchayat column is called.
    if key is None:
        present = list(SEAT_KEY)
        counts = collections.Counter(canon.seat_identity(row) for row in rows)
    else:
        key = list(key)
        if "gram_panchayat" not in columns:
            for alias, canonical in dictionary.ALIAS_OF.items():
                if canonical == "gram_panchayat" and alias in columns:
                    key = [alias if f == "gram_panchayat" else f for f in key]
                    break
        present = [f for f in key if f in columns]
        counts = collections.Counter(tuple(r.get(f, "") for f in present) for r in rows)
    duplicates = [k for k, n in counts.items() if n > 1]
    duplicate_rows = sum(counts[key] for key in duplicates)
    report.check(
        not duplicates,
        f"seat key unique on {present}",
        f"{duplicate_rows} rows across {len(duplicates)} duplicated keys, "
        f"e.g. {duplicates[:2]}",
        hard=False,
    )


def provenance(report, rows, root):
    """Every row must point at a document that exists, on a page that exists."""
    report.section("Provenance")
    paths = collections.Counter(r.get("source_path", "") for r in rows)
    missing = [p for p in paths if not p or not (pathlib.Path(root) / p).exists()]
    report.check(
        not missing,
        "every source_path exists on disk",
        f"{len(missing)} missing, e.g. {missing[:2]}",
    )

    # page numbers are cheap to get wrong by an off-by-one and impossible to
    # notice later, so check them against the real page count
    overruns = []
    for path in list(paths)[:40]:
        full = pathlib.Path(root) / path
        if not full.exists():
            continue
        total = _page_count(full)
        if not total:
            continue
        worst = max(
            (
                int(r["source_page"])
                for r in rows
                if r.get("source_path") == path
                and str(r.get("source_page", "")).isdigit()
            ),
            default=0,
        )
        if worst > total:
            overruns.append((path, worst, total))
    report.check(
        not overruns,
        "source_page within the document",
        f"{len(overruns)} overrun, e.g. {overruns[:2]}",
    )


# --------------------------------------------------------------- coverage


def coverage(report, rows, published=None, unit="seats"):
    report.section("Coverage")
    districts = {r.get("district") for r in rows if r.get("district")}
    blocks = {(r.get("district"), r.get("block")) for r in rows if r.get("block")}
    report.info(
        f"{len(rows):,} {unit}", f"{len(blocks)} blocks, {len(districts)} districts"
    )
    if published:
        share = 100.0 * len(rows) / published
        report.check(
            share >= 90,
            f"{unit} against the published total",
            f"{len(rows):,} of {published:,} ({share:.1f}%)",
            hard=False,
        )


# ------------------------------------------------------------ substantive


def women_share(report, rows, floor=None, target=None, tolerance=0.05, note=""):
    """Check the women's share against the statute.

    `floor` for "not less than one third" - the constitutional wording, so a
    higher share is compliance, not error. `target` for an exact split like
    Haryana's half. Passing the wrong one of these turned J&K's compliant 48%
    into a failure.
    """
    women = sum(1 for r in rows if str(r.get("woman_reserved")) == "1")
    share = women / len(rows) if rows else 0
    if floor is not None:
        report.check(
            share >= floor - 0.02,
            f"women's share at or above the {floor:.0%} floor",
            f"{women}/{len(rows)} = {share:.1%} {note}",
        )
    elif target is not None:
        report.check(
            abs(share - target) <= tolerance,
            f"women's share within {tolerance:.0%} of {target:.0%}",
            f"{women}/{len(rows)} = {share:.1%} {note}",
        )


def share_by_group(report, rows, group, target, tolerance=0.06, label=""):
    """Statutory shares usually bind per block or per taluka, not statewide.

    That is what makes this worth running: a per-group check cannot be satisfied
    by offsetting errors the way a state total can, which is how Haryana's
    wrapped-label bug was found.
    """
    grouped = collections.defaultdict(list)
    for row in rows:
        grouped[tuple(row.get(g, "") for g in group)].append(row)
    off = []
    for key, subset in grouped.items():
        share = sum(1 for r in subset if str(r.get("woman_reserved")) == "1") / len(
            subset
        )
        if abs(share - target) > tolerance:
            off.append((key, len(subset), share))
    report.check(
        len(off) <= 0.1 * max(len(grouped), 1),
        f"per-{label or '/'.join(group)} share within {tolerance:.0%} of {target:.0%}",
        f"{len(off)} of {len(grouped)} off",
        hard=False,
    )
    for key, size, share in sorted(off, key=lambda x: -abs(x[2] - target))[:5]:
        print(
            f"        {'/'.join(str(k) for k in key if k):34s} n={size:4d}  {share:.0%}"
        )
    return off


# ----------------------------------------------------------------- helpers


def _label(caste, woman):
    prefix = {"SC": "SC", "ST": "ST", "BC": "BC", "NONE": ""}.get(caste or "NONE", "")
    return f"{prefix} {'Woman' if woman else 'Other than Woman'}".strip()


_PAGES = {}


def _page_count(path):
    key = str(path)
    if key not in _PAGES:
        try:
            out = subprocess.run(
                ["pdfinfo", key], capture_output=True, text=True, timeout=60
            ).stdout
            found = re.search(r"^Pages:\s+(\d+)", out, re.M)
            _PAGES[key] = int(found.group(1)) if found else 0
        except (subprocess.SubprocessError, OSError):
            _PAGES[key] = 0
    return _PAGES[key]
