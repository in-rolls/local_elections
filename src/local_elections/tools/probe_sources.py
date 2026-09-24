"""Probe candidate sources for states we do not hold yet, and classify them.

Companion to inventory.py, which classifies what is already on disk. This one
answers the same question for the web: does the source answer, and when you open
the first document it links to, is it text or an image?

That is the only question that matters up front. "The state publishes a
reservation list" is true nearly everywhere and predicts nothing about cost -
Haryana's notifications happened to be digitally generated text and needed no
OCR, while every other state opened so far is a scan.

Reads data/sources_seed.csv, writes data/sources_probe.csv.
"""

import argparse
import csv
import pathlib
import re
import subprocess
import tempfile

from local_elections.common import fetch
from local_elections.common.runlog import command, get_logger
from local_elections.paths import ROOT

LOGGER = get_logger(__name__)

DATA = ROOT / "data"
TEXT_THRESHOLD = 800  # chars/page; same cut inventory.py uses

COLUMNS = [
    "state",
    "tier",
    "url",
    "reachable",
    "doc_url",
    "pages",
    "producer",
    "chars_per_page",
    "format",
    "topic_match",
    "note",
]

# A district homepage links dozens of PDFs and the first one is usually
# unrelated - a computer-disposal tender, a staff transfer list. Classifying
# that as "digital text" and calling the state feasible would be wrong, so the
# extracted text has to look like reservation data before the row counts as
# evidence.
# A document counts as on-topic only if it mentions a panchayat body AND a
# reservation category. Either signal alone produces false positives: bare
# "ward" hits "award", "gram" hits "programme", and the stem "reserv" hits the
# tender boilerplate "NIC reserves the right to reject any/all quotations" -
# which is exactly how a computer-disposal notice first passed this check and
# nearly went into SOURCES.md as evidence that Chhattisgarh was easy.
BODY = re.compile(
    r"\bsarpanch|सरपंच|\bpanchayat\b|पंचायत|\bmukhiya\b|\bhalqa\b"
    r"|\bward\s*(?:no|number|wise)\b|\bजनपद\b",
    re.I,
)
CATEGORY = re.compile(
    r"\breservation\b|\baarakshan\b|आरक्षण|अनुसूचित|\bunreserved\b"
    r"|\bscheduled\s+(?:caste|tribe)\b|\bबीसी\b|\bओबीसी\b",
    re.I,
)

HEADERS = {"User-Agent": "Mozilla/5.0"}


def get(url, timeout=45):
    """The bytes, or `fetch.Unanswered` carrying why."""
    return fetch.body(url, timeout=timeout, headers=HEADERS)


def why_not(exc):
    """What an unanswered request is evidence of.

    A connection that never opens is the signature of the geo-block these
    sources sit behind. A status the server chose - a 429, a 503 - is evidence
    of nothing except our own pacing, and recording it as "needs an India
    egress" would put a claim about the Indian internet next to a rate limit
    we caused.
    """
    if exc.status:
        return f"unanswered-http-{exc.status}"
    return "needs-india-egress"


def first_document(page_html, base_url):
    """The first PDF or spreadsheet linked from a landing page."""
    links = re.findall(rb'href="([^"]+\.(?:pdf|xlsx?|csv))"', page_html, re.I)
    if not links:
        return None
    href = links[0].decode("utf-8", "replace")
    if href.startswith("http"):
        return href
    root = re.match(r"(https?://[^/]+)", base_url)
    return (root.group(1) + href) if href.startswith("/") and root else None


def classify_pdf(payload):
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as fh:
        fh.write(payload)
        path = fh.name
    try:
        info = subprocess.run(
            ["pdfinfo", path], capture_output=True, text=True, timeout=60
        ).stdout
        pages = re.search(r"^Pages:\s+(\d+)", info, re.M)
        producer = re.search(r"^Producer:\s*(.*)$", info, re.M)
        pages = int(pages.group(1)) if pages else 0
        sample = min(pages, 5) or 1
        text = subprocess.run(
            ["pdftotext", "-layout", "-f", "1", "-l", str(sample), path, "-"],
            capture_output=True,
            text=True,
            timeout=120,
        ).stdout
        density = int(len(text) / sample)
        fmt = (
            "digital-text"
            if density >= TEXT_THRESHOLD
            else "mixed"
            if density > 50
            else "scan"
        )
        topic = (
            "yes"
            if (BODY.search(text) and CATEGORY.search(text))
            else "no"
            if density > 50
            else "unknown-no-text"
        )
        return {
            "pages": pages,
            "producer": (producer.group(1).strip() if producer else "") or "(none)",
            "chars_per_page": density,
            "format": fmt,
            "topic_match": topic,
        }
    finally:
        pathlib.Path(path).unlink(missing_ok=True)


def probe(row):
    out = dict(
        row,
        reachable="",
        doc_url="",
        pages="",
        producer="",
        chars_per_page="",
        format="",
        topic_match="",
    )
    try:
        page = get(row["url"])
    except fetch.Unanswered as exc:  # unreachable is the finding
        out["reachable"] = "no"
        out["format"] = why_not(exc)
        out["note"] = f"{row['note']} [{exc}]"
        return out

    out["reachable"] = "yes"
    doc = first_document(page, row["url"])
    if not doc:
        out["format"] = "no-document-linked"
        return out

    out["doc_url"] = doc
    try:
        payload = get(doc, timeout=120)
    except fetch.Unanswered as exc:
        out["format"] = f"document-fetch-failed [{why_not(exc)}]"
        return out

    if doc.lower().endswith(".pdf"):
        out.update(classify_pdf(payload))
    else:
        out["format"] = "tabular"
    return out


@command("discover", artifact="source_probe")
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="list the seed URLs without fetching anything",
    )
    ap.add_argument("--seed", default=str(DATA / "sources_seed.csv"))
    ap.add_argument("--out", default=str(DATA / "sources_probe.csv"))
    ap.add_argument(
        "--skip-unreachable",
        action="store_true",
        help="carry over rows a previous run could not reach, so a "
        "re-run does not spend minutes re-timing-out on them",
    )
    args = ap.parse_args()

    with open(args.seed, encoding="utf-8") as fh:
        seed = list(csv.DictReader(fh))

    if args.dry_run:
        for row in seed:
            print(f"  {row['state']:18s} {row['tier']:9s} {row['url']}")
        print(
            f"\n{len(seed)} candidate sources across "
            f"{len({r['state'] for r in seed})} states"
        )
        return

    previous = {}
    if args.skip_unreachable and pathlib.Path(args.out).exists():
        with open(args.out, encoding="utf-8") as fh:
            previous = {
                r["url"]: r for r in csv.DictReader(fh) if r["reachable"] == "no"
            }

    rows = []
    for i, row in enumerate(seed, 1):
        got = previous.get(row["url"]) or probe(row)
        rows.append(got)
        LOGGER.info(
            "Source probe completed",
            extra={
                "event": "source_probe_completed",
                "state": row["state"],
                "url": row["url"],
                "reachable": got["reachable"],
                "position": i,
                "total": len(seed),
            },
        )

    with open(args.out, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(
            fh, fieldnames=COLUMNS, extrasaction="ignore", lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(rows)
    print(f"wrote {args.out} ({len(rows)} rows)\n")

    for row in rows:
        detail = (
            f"{row['format']:20s} {row['pages'] or '-':>5} pp  "
            f"{row['chars_per_page'] or '-':>5} ch/pg  "
            f"topic={row['topic_match'] or '-':15s} {row['producer']}"
        )
        print(f"  {row['state']:18s} {row['tier']:9s} {detail}")


if __name__ == "__main__":
    main()
