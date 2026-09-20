"""Cache public winner lists and profiles; parsing never accesses the network."""

import argparse
import concurrent.futures
import gzip
import hashlib
import json
import threading
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util import Retry

from local_reservations.common.runlog import command

from .html import winner_links

FOLDERS = {2012: "mcd2012", 2017: "delhi2017", 2022: "Delhi2022"}
LOCAL = threading.local()


def session():
    if not hasattr(LOCAL, "session"):
        client = requests.Session()
        client.headers["User-Agent"] = "Mozilla/5.0 (public election research)"
        retry = Retry(
            total=6,
            backoff_factor=2,
            status_forcelist=[429, 500, 502, 503, 504],
            respect_retry_after_header=True,
        )
        client.mount("https://", HTTPAdapter(max_retries=retry))
        LOCAL.session = client
    return LOCAL.session


def fetch(url, path):
    if path.exists():
        with gzip.open(path, "rt") as handle:
            record = json.load(handle)
        if (
            record["url"] != url
            or hashlib.sha256(record["body"].encode()).hexdigest() != record["sha256"]
        ):
            raise ValueError(f"Cache integrity failure: {path}")
        return record
    response = session().get(url, timeout=(20, 90))
    response.raise_for_status()
    response.encoding = "utf-8"
    body = response.text
    if "myneta" not in body.lower() or "<html" not in body.lower():
        raise ValueError(f"Not a MyNeta HTML response: {url}")
    record = {
        "url": url,
        "fetched_at": datetime.now(UTC).isoformat(),
        "status": response.status_code,
        "sha256": hashlib.sha256(body.encode()).hexdigest(),
        "body": body,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".partial")
    with gzip.open(temporary, "wt") as handle:
        json.dump(record, handle)
    temporary.replace(path)
    return record


def harvest_sources(root):
    sources = json.loads(Path(__file__).with_name("sources.json").read_text())
    for source in sources:
        path = root / "sources" / source["file"]
        if not path.exists():
            response = session().get(source["url"], timeout=(20, 90))
            response.raise_for_status()
            path.parent.mkdir(parents=True, exist_ok=True)
            data = response.content
        else:
            data = path.read_bytes()
        if hashlib.sha256(data).hexdigest() != source["sha256"]:
            raise ValueError(f"Source changed: {source['file']}")
        if not path.exists():
            path.write_bytes(data)


def harvest(root):
    harvest_sources(root)
    frames = []
    for year, folder in FOLDERS.items():
        url = f"https://www.myneta.info/{folder}/index.php?action=show_winners&sort=default"
        record = fetch(url, root / "raw" / f"winners_{year}.json.gz")
        rows = winner_links(record["body"], year, url)
        for row in rows:
            row["profile_path"] = (
                f"raw/profiles/{year}_{row['profile_url'].split('=')[-1]}.json.gz"
            )
        frames.extend(rows)
    frame = pd.DataFrame(frames)
    frame.to_parquet(root / "frame.parquet", index=False)

    def run(row):
        record = fetch(row["profile_url"], root / row["profile_path"])
        return {
            "year": row["year"],
            "ward_number": row["ward_number"],
            "path": row["profile_path"],
            "sha256": record["sha256"],
            "fetched_at": record["fetched_at"],
        }

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        records = list(pool.map(run, frames))
    pd.DataFrame(records).to_csv(root / "fetch_manifest.csv", index=False)


@command("harvest", state="Delhi")
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    args.root.mkdir(parents=True, exist_ok=True)
    harvest(args.root)


if __name__ == "__main__":
    main()
