"""Preserve a bounded historical index tree before extracting any election rows.

The seed CSV fixes the scope. HTML navigation outside the page's main heading
is excluded; every retained link keeps its parent, heading and literal label.
HTTP errors are evidence, never successful documents. Replays use saved bytes.
"""

import argparse
import csv
import hashlib
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from html.parser import HTMLParser
from pathlib import Path
from threading import Lock
from urllib.parse import urljoin, urlsplit

import pdfplumber
import requests
from requests_ratelimiter import LimiterAdapter

from local_elections.common import fetch
from local_elections.common.runlog import command

_RECEIPT_LOCK = Lock()


class IndexLinks(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.active = False
        self.heading = ""
        self.capture = None
        self.parts = []
        self.href = ""
        self.links = []

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag == "h1":
            self.active = True
        if tag == "footer":
            self.active = False
        if self.active and tag in {"h1", "h2", "h3", "a"}:
            self.capture = tag
            self.parts = []
            self.href = attributes.get("href", "")

    def handle_data(self, data):
        if self.capture and self.active:
            self.parts.append(data)

    def handle_endtag(self, tag):
        if tag != self.capture:
            return
        label = " ".join(" ".join(self.parts).split())
        if tag == "a" and self.href:
            self.links.append(
                {"href": self.href, "label": label, "heading": self.heading}
            )
        elif tag in {"h1", "h2", "h3"}:
            self.heading = label
        self.capture = None


def links_from_html(body, base_url):
    parser = IndexLinks()
    parser.feed(body)
    return [
        {**link, "url": urljoin(base_url, link["href"])}
        for link in parser.links
        if not link["href"].startswith("#")
        and urlsplit(urljoin(base_url, link["href"])).scheme in {"http", "https"}
    ]


def checksum(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def write_csv(path, rows, columns):
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def acquire(url, out, saved, active_session=None):
    prior = saved.get(url)
    if prior and prior["status"] in {"ok_pdf", "ok_html", "ok_json"}:
        path = out / prior["path"]
        if path.exists() and checksum(path) == prior["sha256"]:
            return prior
    receipt = {"url": url, "retrieved_utc": datetime.now(UTC).isoformat()}
    try:
        response = (active_session or fetch.session()).get(url, timeout=60)
        body = response.content
        suffix = ".bin"
        status = "unclassified_response"
        if body.startswith(b"%PDF"):
            suffix = ".pdf"
            status = "ok_pdf"
        elif "html" in response.headers.get("Content-Type", ""):
            suffix = ".html"
            status = "ok_html"
        elif body.lstrip().startswith((b"[", b"{")):
            suffix = ".json"
            try:
                json.loads(body)
                status = "ok_json"
            except (ValueError, UnicodeDecodeError):
                status = "invalid_json"
        if not response.ok:
            status = "http_error"
        elif not body.strip():
            status = "empty_response"
        elif urlsplit(url).path.lower().endswith(".pdf") and suffix != ".pdf":
            status = "pdf_link_returned_non_pdf"
        url_digest = hashlib.sha256(url.encode()).hexdigest()[:20]
        body_digest = hashlib.sha256(body).hexdigest()
        filename = f"{url_digest}_{body_digest[:12]}{suffix}"
        path = out / "raw" / filename
        path.write_bytes(body)
        receipt.update(
            final_url=response.url,
            http_status=response.status_code,
            content_type=response.headers.get("Content-Type", ""),
            path=str(path.relative_to(out)),
            bytes=len(body),
            sha256=hashlib.sha256(body).hexdigest(),
            status=status,
        )
        if status == "ok_pdf":
            try:
                with pdfplumber.open(path) as pdf:
                    receipt["pages"] = len(pdf.pages)
                    if not pdf.pages:
                        receipt["status"] = "empty_pdf"
            except Exception as exc:  # Retain unreadable original and parser error.
                receipt.update(status="invalid_pdf", error=str(exc))
    except Exception as exc:  # Request exhaustion is not a negative search result.
        receipt.update(status="unanswered", error=str(exc))
    with _RECEIPT_LOCK:
        with (out / "requests.jsonl").open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(receipt, ensure_ascii=False) + "\n")
        saved[url] = receipt
    return receipt


def download_documents(urls, out, saved, workers):
    """Overlap transfers with isolated sessions and the shared host rate limit."""
    adapter = fetch.session().get_adapter("https://")

    def download(url):
        with requests.Session() as active_session:
            worker_adapter = LimiterAdapter(
                limiter=adapter.limiter, max_retries=adapter.max_retries
            )
            active_session.mount("http://", worker_adapter)
            active_session.mount("https://", worker_adapter)
            return acquire(url, out, saved, active_session)

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(download, url) for url in dict.fromkeys(urls)]
        for completed, future in enumerate(as_completed(futures), 1):
            receipt = future.result()
            if completed % 10 == 0 or receipt["status"] != "ok_pdf":
                print(
                    json.dumps(
                        {
                            "documents_completed": completed,
                            "documents_queued": len(futures),
                            "url": receipt["url"],
                            "status": receipt["status"],
                        }
                    ),
                    flush=True,
                )


def harvest(seeds, out, depth, workers=1):
    if workers < 1:
        raise ValueError("workers must be positive")
    out.mkdir(parents=True, exist_ok=True)
    (out / "raw").mkdir(exist_ok=True)
    saved = {}
    if (out / "requests.jsonl").exists():
        for line in (out / "requests.jsonl").read_text().splitlines():
            receipt = json.loads(line)
            saved[receipt["url"]] = receipt
    queue = [{**seed, "depth": 0, "parent_url": "", "heading": ""} for seed in seeds]
    edges = []
    index_links = []
    allowed_hosts = {urlsplit(seed["url"]).hostname for seed in seeds}
    allowed_hosts |= {f"www.{host}" for host in list(allowed_hosts) if host}
    visited = set()
    documents = []
    for item in queue:
        url = item["url"]
        edges.append(item)
        if url in visited:
            continue
        visited.add(url)
        if workers > 1 and urlsplit(url).path.lower().endswith(".pdf"):
            documents.append(url)
            continue
        receipt = acquire(url, out, saved)
        if len(visited) % 10 == 0 or receipt["status"] not in {"ok_pdf", "ok_html"}:
            print(
                json.dumps(
                    {
                        "completed": len(visited),
                        "queued": len(queue),
                        "url": url,
                        "status": receipt["status"],
                    }
                ),
                flush=True,
            )
        if receipt["status"] != "ok_html" or item["depth"] >= depth:
            continue
        body = (out / receipt["path"]).read_text(errors="replace")
        for link in links_from_html(body, receipt["final_url"]):
            host = urlsplit(link["url"]).hostname or ""
            path = urlsplit(link["url"]).path
            scheduled = host in allowed_hosts and (
                path.lower().endswith(".pdf") or "information-" in path
            )
            index_links.append(link | {"parent_url": url, "scheduled": scheduled})
            if not scheduled:
                continue
            queue.append(
                {
                    "state": item["state"],
                    "year_hint": item["year_hint"],
                    "family": item["family"],
                    "url": link["url"],
                    "label": link["label"],
                    "depth": item["depth"] if "/page/" in path else item["depth"] + 1,
                    "parent_url": url,
                    "heading": link["heading"],
                }
            )
        write_csv(out / "link_frame.csv", queue, list(queue[0]))
        if index_links:
            write_csv(out / "index_links.csv", index_links, list(index_links[0]))
    write_csv(out / "link_frame.csv", edges, list(queue[0]))
    if documents:
        download_documents(documents, out, saved, workers)
    (out / "current_receipts.json").write_text(
        json.dumps([saved[url] for url in sorted(visited)], indent=2) + "\n"
    )


def catalog(out):
    """Verify every receipt across collection subfolders and publish a flat catalog."""
    files = {}
    receipts = []
    for log in sorted(out.rglob("requests.jsonl")):
        directory = log.parent
        frame = directory / "link_frame.csv"
        labels = {}
        if frame.exists():
            with frame.open() as stream:
                labels = {row["url"]: row for row in csv.DictReader(stream)}
        current = {}
        for line in log.read_text().splitlines():
            row = json.loads(line)
            current[row["url"]] = row
            if "path" not in row:
                continue
            path = directory / row["path"]
            if checksum(path) != row["sha256"]:
                raise ValueError(f"Receipt checksum mismatch: {path}")
            files[str(path.relative_to(out))] = {
                "path": str(path.relative_to(out)),
                "sha256": row["sha256"],
                "bytes": row["bytes"],
                "source_url": row["url"],
            }
        for row in current.values():
            receipts.append(
                {
                    "collection": str(directory.relative_to(out)),
                    "url": row["url"],
                    "status": row["status"],
                    "path": str((directory / row["path"]).relative_to(out))
                    if "path" in row
                    else "",
                    "sha256": row.get("sha256", ""),
                    "bytes": row.get("bytes", 0),
                    "pages": row.get("pages", ""),
                    "family": labels.get(row["url"], {}).get("family", ""),
                    "label": labels.get(row["url"], {}).get("label", ""),
                    "year_hint": labels.get(row["url"], {}).get("year_hint", ""),
                }
            )
    for path in out.rglob("raw/*"):
        if not path.is_file() or str(path.relative_to(out)) in files:
            continue
        files[str(path.relative_to(out))] = {
            "path": str(path.relative_to(out)),
            "sha256": checksum(path),
            "bytes": path.stat().st_size,
            "source_url": "not_in_request_ledger; retained_pilot",
        }
    write_csv(
        out / "source_files.csv",
        list(files.values()),
        ["path", "sha256", "bytes", "source_url"],
    )
    write_csv(out / "acquisition_status.csv", receipts, list(receipts[0]))
    summary = {
        "requests": len(receipts),
        "verified_source_files": len(files),
        "source_bytes": sum(row["bytes"] for row in files.values()),
        "valid_pdf_urls": sum(row["status"] == "ok_pdf" for row in receipts),
        "valid_pdf_pages_with_duplicate_documents": sum(
            int(row["pages"]) for row in receipts if row["status"] == "ok_pdf"
        ),
        "unsuccessful_requests": [
            row for row in receipts if not row["status"].startswith("ok_")
        ],
        "scope": "Fetch counts; geographic coverage and row validation are separate.",
    }
    (out / "acquisition_summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary))


@command("acquire", source="historical_indexes")
def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seeds", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--depth", type=int, default=1)
    parser.add_argument("--workers", type=int, choices=range(1, 9), default=1)
    parser.add_argument("--catalog-only", action="store_true")
    args = parser.parse_args()
    if args.catalog_only:
        catalog(args.out)
        return
    if not args.seeds:
        parser.error("--seeds is required for acquisition")
    with args.seeds.open() as stream:
        seeds = list(csv.DictReader(stream))
    harvest(seeds, args.out, args.depth, args.workers)


if __name__ == "__main__":
    main()
