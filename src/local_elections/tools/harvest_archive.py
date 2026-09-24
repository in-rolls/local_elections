r"""Fetch archived documents for any host, as crawled, with a manifest.

    uv run python -m local_elections.tools.harvest_archive --host karsec.gov.in \\
        --match TZP_Elected_Members --out data/karnataka/tzp_2016_elected \\
        --dry-run

`archive_sweep.py` says what exists; this brings it here. The two halves are
deliberately separate - the sweep downloads nothing and can be re-run against
every state cheaply, and nothing is fetched until somebody has read its output
and decided a directory is worth the bytes.

Written general because the alternative was another copy. `ap/harvest.py` was
one state's CDX query wrapped in a hundred lines of fetch-and-check, and the
only parts of it that were about Andhra Pradesh were the query and the district
names. Karnataka would have been a second copy, and the sweep resolves 23
states.

Three properties are worth more than the convenience:

**The bytes are as crawled.** The `id_` form of the Wayback URL returns the
original response without the archive's banner, so a PDF is the PDF the
commission published rather than a page about it.

**A file already here is a check, not an obstacle.** If our copy and the
archive's differ, that is a finding and the run says so; it never overwrites.

**Nothing is trusted that is not written down.** Every file lands in a manifest
with the URL it came from, the capture timestamp and a SHA-256, because a
directory of PDFs with no provenance is not evidence of anything.
"""

import argparse
import csv
import hashlib
import pathlib
import re
import sys
import urllib.parse

from local_elections.common import fetch
from local_elections.common.runlog import command
from local_elections.paths import ROOT
from local_elections.tools.archive_sweep import cdx

FIELDS = ["file", "url", "wayback_timestamp", "sha256", "bytes"]


def listing(host, match, suffix=".pdf"):
    """Archived URLs under `host` whose path matches, newest capture each."""
    rows = cdx(host, limit=20000)
    if rows is None:
        return None
    pattern = re.compile(match, re.IGNORECASE) if match else None
    keep = {}
    for url, timestamp in ((r[0], r[1]) for r in rows if len(r) >= 2):
        plain = urllib.parse.unquote(url)
        if suffix and not plain.lower().endswith(suffix):
            continue
        if pattern and not pattern.search(plain):
            continue
        # collapse=urlkey already gives one row per URL, but a host serving
        # both http and https yields the same document twice.
        key = plain.split("://", 1)[-1]
        if key not in keep or timestamp > keep[key][1]:
            keep[key] = (url, timestamp)
    return sorted(keep.values())


def local_name(url):
    """A filesystem-safe name that keeps enough path to stay unique."""
    plain = urllib.parse.unquote(url).split("://", 1)[-1]
    parts = plain.split("/")[1:]
    name = "_".join(parts[-2:]) if len(parts) > 1 else parts[-1]
    return re.sub(r"[^A-Za-z0-9._-]+", "_", name)[:120]


def crawled(url, timestamp, timeout=300):
    """The bytes as crawled. `id_` asks the archive for the original response
    without its own banner, so a PDF is the PDF the commission published.
    """
    wayback = f"http://web.archive.org/web/{timestamp}id_/{url}"
    return fetch.body(wayback, timeout=timeout)


def held(out):
    """What the manifest says we already have, by filename.

    Resumability. Without this a resumed run re-downloads every file it already
    holds purely to compare the bytes, which for the 211-file Karnataka set is
    four minutes of somebody else's bandwidth to learn nothing. A file whose
    bytes on disk still hash to what the manifest recorded is skipped; --verify
    re-fetches everything and compares, which is the check this makes optional
    rather than mandatory.
    """
    manifest = out / "manifest.csv"
    if not manifest.exists():
        return {}
    with manifest.open(encoding="utf-8") as fh:
        recorded = {r["file"]: r for r in csv.DictReader(fh)}
    good = {}
    for name, row in recorded.items():
        target = out / name
        if target.exists() and hashlib.sha256(
            target.read_bytes()
        ).hexdigest() == row.get("sha256"):
            good[name] = row
    return good


def harvest(host, match, out, dry_run=False, limit=None, suffix=".pdf", verify=False):
    found = listing(host, match, suffix)
    if found is None:
        print(f"  {host}: the archive did not answer - nothing fetched")
        return None
    if limit:
        found = found[:limit]
    print(f"  {len(found)} archived file(s) under {host} matching {match!r}")
    if dry_run:
        for url, timestamp in found[:40]:
            print(f"    {timestamp}  {urllib.parse.unquote(url)}")
        if len(found) > 40:
            print(f"    ... and {len(found) - 40} more")
        return []

    out.mkdir(parents=True, exist_ok=True)
    already = {} if verify else held(out)
    rows, fetched, matched, differed, failed = [], 0, 0, [], []
    skipped = 0
    for url, timestamp in found:
        name = local_name(url)
        target = out / name
        if name in already:
            rows.append(already[name])
            skipped += 1
            continue
        try:
            body = crawled(url, timestamp)
        except fetch.Unanswered as exc:
            # the archive would not answer for this file; that is not evidence
            # the file is absent, so it stays off the manifest and is counted
            failed.append(f"{name} ({exc})")
            continue
        digest = hashlib.sha256(body).hexdigest()
        if target.exists():
            if hashlib.sha256(target.read_bytes()).hexdigest() == digest:
                matched += 1
            else:
                differed.append(name)
                continue
        else:
            target.write_bytes(body)
            fetched += 1
        rows.append(
            {
                "file": name,
                "url": url,
                "wayback_timestamp": timestamp,
                "sha256": digest,
                "bytes": len(body),
            }
        )
        if (fetched + matched) % 25 == 0:
            print(f"    {fetched + matched}/{len(found)}", flush=True)

    manifest = out / "manifest.csv"
    if rows:
        merged = {}
        if manifest.exists():
            with manifest.open(encoding="utf-8") as fh:
                merged = {r["file"]: r for r in csv.DictReader(fh)}
        merged.update({r["file"]: r for r in rows})
        with manifest.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(
                fh, fieldnames=FIELDS, lineterminator="\n", extrasaction="ignore"
            )
            writer.writeheader()
            writer.writerows([merged[k] for k in sorted(merged)])

    print(
        f"  {fetched} new, {matched} re-checked and identical, "
        f"{skipped} already held -> {out.relative_to(ROOT)}"
    )
    if differed:
        print(f"  DIFFERENT from our copy, not overwritten: {differed}")
    if failed:
        print(f"  {len(failed)} could not be fetched: {failed[:5]}")
    return rows


@command("harvest", source="internet_archive")
def main():
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("--host", required=True, help="e.g. karsec.gov.in")
    ap.add_argument("--match", default="", help="regex the archived path must contain")
    ap.add_argument("--out", required=True, type=pathlib.Path)
    ap.add_argument(
        "--suffix", default=".pdf", help="file extension to keep; empty for all"
    )
    ap.add_argument("--limit", type=int, help="stop after N files")
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="list what would be fetched and fetch nothing",
    )
    ap.add_argument(
        "--verify",
        action="store_true",
        help="re-fetch everything and compare against our copies",
    )
    args = ap.parse_args()

    out = args.out if args.out.is_absolute() else ROOT / args.out
    rows = harvest(
        args.host,
        args.match,
        out,
        dry_run=args.dry_run,
        limit=args.limit,
        suffix=args.suffix,
        verify=args.verify,
    )
    return 0 if rows is not None else 1


if __name__ == "__main__":
    sys.exit(main())
