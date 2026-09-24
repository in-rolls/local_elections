"""What the web archive holds for every state election commission.

    uv run python -m local_elections.tools.archive_sweep            # every state
    uv run python -m local_elections.tools.archive_sweep --only Karnataka

Written because the corpus's largest recent find was an accident. Chasing an
unrelated question, a query against the whole of karsec.gov.in returned 828
archived PDFs including 196 taluk panchayat elected-member gazettes for 2016 -
a tier Karnataka contributes nothing to, naming winners, sitting in a public
archive. Nothing here would have found it: probe_sources.py reads eighteen
hand-picked URLs and none is a commission's site, and ap/harvest.py queries the
archive for one hard-coded path in one state.

So this asks every state the same question and writes the answer down. It
**downloads nothing**; it is an inventory, and its output is the input to a
decision about what is worth harvesting.

The host is derived rather than curated. Commissions name their sites on a few
patterns - karsec.gov.in, sec.gujarat.gov.in, wbsec.gov.in,
mahasec.maharashtra.gov.in - and generating candidates from those resolved seven
of the first eight states tried. Every candidate is recorded, not only the one
that answered: a state reported as holding nothing looks identical to a state
whose domain was guessed wrong, and that difference is the whole value of the
file.
"""

import argparse
import collections
import csv
import json
import re
import sys
import urllib.parse

from local_elections.common import fetch
from local_elections.common.runlog import command
from local_elections.paths import ROOT

OUT = ROOT / "data" / "archive_inventory.csv"
HOSTS = ROOT / "data" / "archive_hosts.csv"

COLUMNS = [
    "state",
    "host",
    "pdfs",
    "first_capture",
    "last_capture",
    "reservation_by_name",
    "results_by_name",
    "delimitation_by_name",
    "other",
    "opened",
    "readable",
    "confirmed",
    "top_directories",
    "status",
]

# Two-letter-ish forms the commissions actually use in their hostnames.
ABBREV = {
    "Andhra Pradesh": "ap",
    "Arunachal Pradesh": "arunachal",
    "Assam": "assam",
    "Bihar": "bihar",
    "Chhattisgarh": "cg",
    "Goa": "goa",
    "Gujarat": "gujarat",
    "Haryana": "haryana",
    "Himachal Pradesh": "hp",
    "Jammu & Kashmir": "jk",
    "Jharkhand": "jharkhand",
    "Karnataka": "kar",
    "Kerala": "kerala",
    "Madhya Pradesh": "mp",
    "Maharashtra": "maha",
    "Manipur": "manipur",
    "Meghalaya": "meghalaya",
    "Mizoram": "mizoram",
    "Nagaland": "nagaland",
    "Odisha": "odisha",
    "Puducherry": "py",
    "Punjab": "punjab",
    "Rajasthan": "raj",
    "Sikkim": "sikkim",
    "Tamil Nadu": "tn",
    "Telangana": "tg",
    "Tripura": "tripura",
    "Uttar Pradesh": "up",
    "Uttarakhand": "uk",
    "West Bengal": "wb",
    "NCT of Delhi": "delhi",
}

# Confirmed by hand, and kept because deriving them every run would re-guess a
# question already answered. Anything not here is derived from ABBREV.
KNOWN = {
    "Karnataka": "karsec.gov.in",
    "Maharashtra": "mahasec.maharashtra.gov.in",
    "Andhra Pradesh": "sec.ap.gov.in",
    "West Bengal": "wbsec.gov.in",
    "Tamil Nadu": "tnsec.tn.gov.in",
    "Madhya Pradesh": "mplocalelection.gov.in",
    # None of these follow the patterns below, and the first sweep reported all
    # three as "nothing archived" - which is what an unresolved host looks like
    # and is why every candidate tried is written to archive_hosts.csv.
    "Haryana": "secharyana.gov.in",
    "Rajasthan": "sec.rajasthan.gov.in",
    "Telangana": "tsec.gov.in",
}


def candidates(state):
    """Hostnames this state's commission might use, most likely first."""
    if state in KNOWN:
        yield KNOWN[state]
    short = ABBREV.get(state, state.split()[0].lower())
    slug = state.lower().replace(" ", "").replace("&", "")
    yield f"{short}sec.gov.in"
    yield f"sec.{slug}.gov.in"
    yield f"{slug}sec.gov.in"
    yield f"sec.{short}.gov.in"
    yield f"{short}sec.nic.in"


def cdx(host, prefix=True, limit=5000):
    """Archived URLs for a host. [] where the archive holds none, None where
    the question could not be asked.

    The distinction is the whole point. A run that folded a rate-limited query
    into [] reported Gujarat at 0 PDFs, Odisha at 0 and Jharkhand at 0, having
    found 614, 817 and 6 an hour earlier - and printed all three in the same
    words it uses for a state with no web presence. An empty answer and an
    unanswered question are not the same fact and must not share a value.

    The pacing, the retries and the reading of Retry-After all live in
    common/fetch.py, because the archive firewalls an IP for an hour if 429s
    are ignored for a minute and a per-script sleep loop cannot be trusted with
    that.
    """
    query = urllib.parse.quote(host + "/" if prefix else host, safe=":/")
    url = (
        f"http://web.archive.org/cdx/search/cdx?url={query}&limit={limit}"
        f"&fl=original,timestamp&collapse=urlkey&output=json"
        f"&matchType={'prefix' if prefix else 'domain'}"
    )
    try:
        body = fetch.body(url, timeout=180).decode("utf-8", "replace")
    except fetch.Unanswered:
        return None
    try:
        rows = json.loads(body or "[]")
    except json.JSONDecodeError:
        # a truncated or HTML body is the archive failing to answer, not the
        # archive answering "nothing"
        return None
    return rows[1:] if rows else []


def resolve(state):
    """The first candidate host with anything archived, every candidate tried,
    and whether any query failed - a host is only "not found" if every
    candidate was actually asked.
    """
    tried, failed = [], False
    for host in candidates(state):
        tried.append(host)
        rows = cdx(host, prefix=False, limit=1)
        if rows is None:
            failed = True
        elif rows:
            return host, tried, False
    return "", tried, failed


# What a filename says it is. Ordered: a reservation gazette for an elected-
# members list is still an elected-members list, and "form" matches too much to
# be trusted before the specific words.
# **These read the URL, not the document.** The column names say so - they end
# in _by_name - because the unqualified ones were believed. West Bengal's 123
# "results" PDFs turned out to be candidate affidavits sitting under a
# directory called Declarations/, and that number was quoted as the largest
# untouched holding of named winners in the corpus before anybody opened one.
#
# A filename match is a floor with an unmeasured error rate. `sampled` and
# `confirmed` in the inventory measure it.
KIND = [
    ("results", r"elected|winner|result|form.?21|form.?25|declaration"),
    ("reservation", r"reserv|roster|rotation|aarakshan|আসন"),
    ("delimitation", r"delimit|ward.?format|boundary"),
]


def classify(url):
    name = urllib.parse.unquote(url).lower()
    for kind, pattern in KIND:
        if re.search(pattern, name):
            return kind
    return "other"


# Words a document that really is an elected-members list puts on its first
# page. Deliberately the office names and the table's own headings rather than
# "result", which is what the filename already matched on.
CONFIRMS = re.compile(
    r"elected|winning|winner|returned candidate|declared elected|"
    r"name of the (?:elected|returned)|sarpanch|mukhiya|pradhan|panch\b|"
    r"ward member|zilla parishad|panchayat samiti",
    re.I,
)


def looks_like_results(pdf):
    """Whether a document's own first page says what its filename claimed.

    Reads text, not the URL. A scan with no text layer returns None - unknown,
    not no - because "we could not tell" and "it is not a results list" are
    different answers and this file has already conflated two things once.
    """
    try:
        import subprocess
        import tempfile

        with tempfile.NamedTemporaryFile(suffix=".pdf") as handle:
            handle.write(pdf)
            handle.flush()
            text = subprocess.run(
                ["pdftotext", "-f", "1", "-l", "2", handle.name, "-"],
                capture_output=True,
                text=True,
                errors="replace",
            ).stdout
    except Exception:
        return None
    if len(text.strip()) < 120:
        return None
    return bool(CONFIRMS.search(text))


def sample(rows, kind, want=5):
    """(opened, readable, confirmed) for documents the filename called `kind`.

    Three numbers and not two, because the three outcomes are different facts
    and folding them loses the one that matters. West Bengal's affidavits carry
    no text layer at all - `pdftotext` returns zero characters - so a text
    check can neither confirm nor contradict them. Reported as two numbers that
    would have read `0 of 0`, which is indistinguishable from "we did not look"
    and from "none of them are results".

      opened     the document was fetched
      readable   it had a text layer to judge
      confirmed  that text says what the filename claimed

    A low `readable` says the archive is scans and this check cannot speak.
    """
    picks = [(u, t) for u, t in rows if classify(u) == kind][:want]
    opened = readable = confirmed = 0
    for url, stamp in picks:
        try:
            body = fetch.body(
                f"https://web.archive.org/web/{stamp}id_/{url}", timeout=120
            )
        except fetch.Unanswered:
            continue
        opened += 1
        verdict = looks_like_results(body)
        if verdict is None:
            continue
        readable += 1
        confirmed += bool(verdict)
    return opened, readable, confirmed


def sweep(state, check=0):
    """(row, candidates tried, status). row is None unless status is "ok"."""
    host, tried, failed = resolve(state)
    if not host:
        return None, tried, "query failed" if failed else "no host"
    listing = cdx(host)
    if listing is None:
        return None, tried, "query failed"
    rows = [r for r in listing if r and r[0].lower().endswith(".pdf")]
    kinds = collections.Counter(classify(u) for u, _ in rows)
    stamps = sorted(t for _, t in rows if t)
    directories = collections.Counter(
        "/".join(urllib.parse.unquote(u).split("/")[3:-1])[:44] for u, _ in rows
    )
    opened, readable, confirmed = sample(rows, "results", check) if check else (0, 0, 0)
    return (
        {
            "opened": opened,
            "readable": readable,
            "confirmed": confirmed,
            "state": state,
            "host": host,
            "pdfs": len(rows),
            "first_capture": stamps[0][:6] if stamps else "",
            "last_capture": stamps[-1][:6] if stamps else "",
            "reservation_by_name": kinds["reservation"],
            "results_by_name": kinds["results"],
            "delimitation_by_name": kinds["delimitation"],
            "other": kinds["other"],
            "top_directories": " | ".join(
                f"{d}({n})" for d, n in directories.most_common(3) if d
            ),
            "status": "ok",
        },
        tried,
        "ok",
    )


def previous():
    """What the last run recorded, by state, so a failed query can carry the
    answer forward instead of overwriting it with a worse one.
    """
    if not OUT.exists():
        return {}
    with OUT.open(encoding="utf-8") as fh:
        return {r["state"]: r for r in csv.DictReader(fh)}


@command("discover", source="internet_archive")
def main():
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("--only", help="one state")
    ap.add_argument(
        "--check",
        type=int,
        default=0,
        metavar="N",
        help="open N of the documents a filename called a result, "
        "and record how many say so themselves",
    )
    args = ap.parse_args()

    states = [args.only] if args.only else sorted(ABBREV)
    prior = previous()
    found, attempts = [], []
    for state in states:
        row, tried, status = sweep(state, args.check)
        if row:
            found.append(row)
            print(
                f"  {state:<20} {row['host']:<30} {row['pdfs']:>5} PDFs  "
                f"res={row['reservation_by_name']:<4} "
                f"results={row['results_by_name']:<4} "
                f"opened={row['opened']} readable={row['readable']} "
                f"confirmed={row['confirmed']}",
                flush=True,
            )
        elif status == "query failed" and state in prior:
            row = dict(prior[state], status="carried forward")
            found.append(row)
            print(
                f"  {state:<20} {row['host']:<30} {row['pdfs']:>5} PDFs  "
                "(carried forward - the archive did not answer)",
                flush=True,
            )
        elif status == "query failed":
            print(
                f"  {state:<20} {'?':<30} the archive did not answer, and "
                f"there is no earlier number to carry",
                flush=True,
            )
        else:
            print(
                f"  {state:<20} {'-':<30} nothing archived under "
                f"{len(tried)} candidate host(s)",
                flush=True,
            )
        attempts.append(
            {
                "state": state,
                "resolved": row["host"] if row else "",
                "status": row["status"] if row else status,
                "candidates_tried": " ".join(tried),
            }
        )

    # --only rewrites one state and must not drop the other thirty.
    #
    # `renamed` carries the older column names forward. Renaming results ->
    # results_by_name without this silently blanked the counts for every state
    # not re-swept, because those rows are read back from the file under their
    # old headings - 22 states reading as zero after a one-state run.
    renamed = {
        "reservation": "reservation_by_name",
        "results": "results_by_name",
        "delimitation": "delimitation_by_name",
    }
    if args.only:
        kept = []
        for state, row in sorted(prior.items()):
            if state == args.only:
                continue
            row = dict(row, status=row.get("status") or "ok")
            for old, new in renamed.items():
                if not row.get(new) and row.get(old):
                    row[new] = row[old]
            kept.append(row)
        found = found + kept

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(
            fh, fieldnames=COLUMNS, extrasaction="ignore", lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(sorted(found, key=lambda r: -int(r["pdfs"])))
    with HOSTS.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(
            fh,
            lineterminator="\n",
            fieldnames=["state", "resolved", "status", "candidates_tried"],
        )
        writer.writeheader()
        writer.writerows(attempts)
    stale = sum(1 for r in found if r["status"] == "carried forward")
    carried = f"  ({stale} carried forward from an earlier run)" if stale else ""
    print(
        f"\n{len(found)} states with an archived host -> "
        f"{OUT.relative_to(ROOT)}{carried}"
    )
    print(f"every candidate tried -> {HOSTS.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
