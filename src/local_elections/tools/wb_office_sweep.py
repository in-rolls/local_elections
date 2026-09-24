"""Inventory archived West Bengal district documents that may hold Pradhan
reservation orders (Form 1A/1B under Rule 2A) for the 2008, 2013 and 2018 terms.

    uv run python -m local_elections.tools.wb_office_sweep
    uv run python -m local_elections.tools.wb_office_sweep --only Malda

The Form 1B for Pradhan offices is issued by each District Magistrate, not the
State Election Commission, so the search has to be district by district. The
September 2026 passes were run by hand; only their outputs survived, and they
left three holes this closes:

- the keyword filter lacked `office`, `bearer`, `1b` and `book`, the words the
  orders actually carry in their paths (Malda's `Office_Bearer of_ZP_PS_GP.pdf`,
  Alipurduar's `OfficeBearer.pdf`);
- one query per host hit the 5,000-row cap on nadia.nic.in, so the index was
  not exhaustive; queries here are split by capture window and a capped answer
  is recorded as `truncated`, not as complete;
- about ten district domains either failed or were never asked.

Like `tools/archive_sweep.py` this **downloads nothing**. Fetching is
`tools/harvest_archive.py`, after someone has read `candidates.csv`.

An unanswered query is written as `unanswered` and retried on the next run; an
answered one is kept. The two must not share a value (see common/fetch.py).
"""

import argparse
import csv
import json
import re
import sys
import urllib.parse

from local_elections.common import fetch
from local_elections.common.runlog import command
from local_elections.paths import ROOT

OUT = ROOT / "data" / "wb" / "vintage_search" / "office_sweep"
QUERIES = OUT / "queries.csv"
CANDIDATES = OUT / "candidates.csv"

# Every domain a district's site has used. Old names are kept because captures
# from 2008-2014 sit under the .nic.in hosts and pre-bifurcation names.
HOSTS = {
    "Alipurduar": ["alipurduar.gov.in", "alipurduar.nic.in"],
    "Bankura": ["bankura.nic.in", "bankura.gov.in"],
    "Birbhum": ["birbhum.nic.in", "birbhum.gov.in"],
    "Cooch Behar": ["coochbehar.nic.in", "coochbehar.gov.in"],
    "Dakshin Dinajpur": ["ddinajpur.nic.in", "ddinajpur.gov.in"],
    "Darjeeling": ["darjeeling.gov.in", "darjeeling.nic.in"],
    "Hooghly": ["hooghly.nic.in", "hooghly.gov.in"],
    "Howrah": ["howrah.nic.in", "howrah.gov.in"],
    "Jalpaiguri": ["jalpaiguri.nic.in", "jalpaiguri.gov.in"],
    "Jhargram": ["jhargram.gov.in"],
    "Kalimpong": ["kalimpong.gov.in"],
    "Malda": ["malda.nic.in", "malda.gov.in"],
    "Murshidabad": ["murshidabad.nic.in", "murshidabad.gov.in"],
    "Nadia": ["nadia.nic.in", "nadia.gov.in"],
    "North 24 Parganas": ["north24parganas.nic.in", "north24parganas.gov.in"],
    "Paschim Bardhaman": ["paschimbardhaman.gov.in"],
    "Paschim Medinipur": ["paschimmedinipur.gov.in", "paschimmedinipur.nic.in"],
    "Purba Bardhaman": [
        "burdwan.nic.in",
        "bardhaman.nic.in",
        "bardhaman.gov.in",
        "purbabardhaman.nic.in",
        "purbabardhaman.gov.in",
    ],
    "Purba Medinipur": ["purbamedinipur.gov.in", "purbamedinipur.nic.in"],
    "Purulia": ["purulia.nic.in", "purulia.gov.in"],
    "South 24 Parganas": ["s24pgs.gov.in", "s24pgs.nic.in"],
    "Uttar Dinajpur": ["uttardinajpur.nic.in", "uttardinajpur.gov.in"],
    "State": ["wbsec.gov.in", "wbsec.org", "wbprd.gov.in", "prd.wb.gov.in"],
}

# Orders are published about two months before a May poll and stay up for
# years, so each window runs from the year before the election to two after.
WINDOWS = {2008: ("2007", "2010"), 2013: ("2012", "2015"), 2018: ("2017", "2020")}

KEYWORDS = (
    "panch|reserv|pradhan|prodhan|office|bearer|1b|1a|form|book|pge|pelec|"
    "election|electn|upa|sabhapati|rotation|roster"
)

# The broad filter above is for recall and matches every application form on a
# district site. This narrower one ranks candidates for reading; it is a triage
# aid, never a reason to drop a row.
LIKELY = re.compile(
    r"pradhan|prodhan|office.?bearer|form.?1\s*[ab]\b|1b_|reserv|panchayat|"
    r"pge|pelec|upa.?pradhan|sabhapati",
    re.IGNORECASE,
)

DOCUMENT = (".pdf", ".zip", ".rar", ".xls", ".xlsx", ".doc", ".docx", ".jpg")

LIMIT = 5000

QUERY_FIELDS = ["district", "host", "term", "status", "rows", "truncated", "detail"]
CANDIDATE_FIELDS = [
    "district",
    "host",
    "term",
    "likely",
    "url",
    "timestamp",
    "mimetype",
]


def query(host, window):
    """CDX rows [original, timestamp, mimetype] for one host and window, or
    `fetch.Unanswered`.
    """
    params = [
        ("url", f"{host}/*"),
        ("from", window[0]),
        ("to", window[1]),
        ("filter", "statuscode:200"),
        ("filter", f"urlkey:.*({KEYWORDS}).*"),
        ("collapse", "urlkey"),
        ("fl", "original,timestamp,mimetype"),
        ("output", "json"),
        ("limit", str(LIMIT)),
    ]
    url = "http://web.archive.org/cdx/search/cdx?" + urllib.parse.urlencode(params)
    text = fetch.body(url, timeout=180).decode("utf-8", "replace")
    try:
        rows = json.loads(text or "[]")
    except json.JSONDecodeError as exc:
        raise fetch.Unanswered(f"unparseable CDX body: {text[:80]!r}") from exc
    return rows[1:] if rows else []


def is_document(url):
    path = urllib.parse.urlparse(urllib.parse.unquote(url)).path.lower()
    return path.endswith(DOCUMENT)


def read(path):
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def write(path, fields, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


@command("discover", source="internet_archive")
def main():
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("--only", help="one district, as named in HOSTS")
    ap.add_argument(
        "--retry-answered",
        action="store_true",
        help="re-ask host/term pairs that already have an answer",
    )
    args = ap.parse_args()

    queries = {(r["host"], r["term"]): r for r in read(QUERIES)}
    candidates = {(r["url"], r["term"]): r for r in read(CANDIDATES)}

    districts = [args.only] if args.only else list(HOSTS)
    for district in districts:
        for host in HOSTS[district]:
            for term, window in WINDOWS.items():
                key = (host, str(term))
                prior = queries.get(key)
                if prior and prior["status"] == "answered" and not args.retry_answered:
                    continue
                try:
                    rows = query(host, window)
                except fetch.Unanswered as exc:
                    queries[key] = {
                        "district": district,
                        "host": host,
                        "term": term,
                        "status": "unanswered",
                        "rows": "",
                        "truncated": "",
                        "detail": str(exc)[:200],
                    }
                    print(f"  {host:<28} {term}  unanswered", flush=True)
                else:
                    docs = [r for r in rows if len(r) >= 2 and is_document(r[0])]
                    for url, stamp, *rest in docs:
                        candidates[(url, str(term))] = {
                            "district": district,
                            "host": host,
                            "term": term,
                            "likely": bool(LIKELY.search(urllib.parse.unquote(url))),
                            "url": url,
                            "timestamp": stamp,
                            "mimetype": rest[0] if rest else "",
                        }
                    queries[key] = {
                        "district": district,
                        "host": host,
                        "term": term,
                        "status": "answered",
                        "rows": len(rows),
                        "truncated": len(rows) >= LIMIT,
                        "detail": f"{len(docs)} documents",
                    }
                    print(
                        f"  {host:<28} {term}  {len(rows):>5} rows  {len(docs):>4} docs"
                        + ("  TRUNCATED" if len(rows) >= LIMIT else ""),
                        flush=True,
                    )
                # written after every query so an interrupted run loses nothing
                write(QUERIES, QUERY_FIELDS, sorted(queries.values(), key=_order))
                write(
                    CANDIDATES,
                    CANDIDATE_FIELDS,
                    sorted(candidates.values(), key=lambda r: (_order(r), r["url"])),
                )

    likely = sum(1 for r in candidates.values() if str(r["likely"]) == "True")
    unanswered = sum(1 for r in queries.values() if r["status"] != "answered")
    print(
        f"\n{len(queries)} host/term queries, {unanswered} unanswered; "
        f"{len(candidates)} candidate documents ({likely} likely) -> "
        f"{CANDIDATES.relative_to(ROOT)}"
    )
    return 0


def _order(row):
    return (row["district"], row["host"], str(row["term"]))


if __name__ == "__main__":
    sys.exit(main())
