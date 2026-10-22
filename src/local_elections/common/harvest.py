"""Shared boundary between remote source discovery and local parsing.

State modules decide which links constitute a source series. This module owns
the lower-level contract: stable document identity, immutable local bytes,
checksums, retrieval timestamps, a common manifest schema, and structured
events. Parsers consume only the held files and never call this module.
"""

import collections
import csv
import hashlib
import logging
import pathlib
import re
import urllib.parse
from dataclasses import asdict, dataclass
from datetime import UTC, datetime

from local_elections.common import fetch

LOGGER = logging.getLogger(__name__)
HEADERS = {"User-Agent": "Mozilla/5.0"}
MANIFEST_FIELDS = [
    "source_id",
    "state",
    "year",
    "government_level",
    "tier",
    "language",
    "document_format",
    "district",
    "body",
    "file",
    "url",
    "landing_url",
    "retrieved_at",
    "sha256",
    "bytes",
]


@dataclass(frozen=True)
class SourceDocument:
    """One published artifact in a separately measurable source series."""

    source_id: str
    state: str
    year: str
    government_level: str
    tier: str
    language: str
    document_format: str
    file: str
    url: str
    landing_url: str
    district: str = ""
    body: str = ""


def slugged_pdf_name(url, prefix=""):
    """Return a stable lowercase filename from a published PDF URL."""
    basename = pathlib.PurePosixPath(
        urllib.parse.unquote(urllib.parse.urlsplit(url).path)
    ).name
    stem = re.sub(r"[^a-z0-9]+", "_", pathlib.Path(basename).stem.lower()).strip("_")
    return f"{prefix}{stem}.pdf"


def require_count(documents, expected, source_id):
    """Fail when live discovery drifts from its reviewed expectation."""
    actual = len(documents)
    if actual != expected:
        raise RuntimeError(
            f"{source_id}: expected {expected} documents, found {actual}"
        )


def _recorded(manifest):
    if not manifest.exists():
        return {}
    with manifest.open(encoding="utf-8") as fh:
        return {row["file"]: row for row in csv.DictReader(fh)}


def verify(manifest, out, expected):
    """Verify a held source series offline against its standard manifest."""
    if not manifest.exists():
        raise RuntimeError(f"source manifest does not exist: {manifest}")
    with manifest.open(encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        if reader.fieldnames != MANIFEST_FIELDS:
            raise RuntimeError("source manifest does not use the standard schema")
        rows = list(reader)

    counts = collections.Counter(row["source_id"] for row in rows)
    if counts != collections.Counter(expected):
        raise RuntimeError(
            f"source manifest counts {dict(counts)} differ from {expected}"
        )
    files = [row["file"] for row in rows]
    urls = [row["url"] for row in rows]
    if len(files) != len(set(files)) or len(urls) != len(set(urls)):
        raise RuntimeError("source manifest contains duplicate files or URLs")
    held = {path.name for path in out.glob("*.pdf")}
    if held != set(files):
        raise RuntimeError("held PDFs and source manifest file list differ")
    for row in rows:
        path = out / row["file"]
        payload = path.read_bytes()
        if len(payload) != int(row["bytes"]):
            raise RuntimeError(f"source byte count differs: {row['file']}")
        if hashlib.sha256(payload).hexdigest() != row["sha256"]:
            raise RuntimeError(f"source checksum differs: {row['file']}")
    return rows


def _event_fields(document, **extra):
    fields = {key: value for key, value in asdict(document).items() if value}
    fields["domain"] = urllib.parse.urlsplit(document.url).netloc
    fields.update(extra)
    return fields


def acquire(documents, out, manifest, root, *, dry_run=False):
    """Acquire reviewed documents and write the standard source manifest."""
    documents = list(documents)
    names = [document.file for document in documents]
    if len(names) != len(set(names)):
        raise RuntimeError("two source URLs map to the same local filename")

    for document in documents:
        LOGGER.info(
            "source discovered",
            extra={"event": "source_discovered", **_event_fields(document)},
        )
    if dry_run:
        return []

    out.mkdir(parents=True, exist_ok=True)
    prior = _recorded(manifest)
    rows = []
    for document in documents:
        target = out / document.file
        old = prior.get(document.file, {})
        document_fields = asdict(document)
        held = target.read_bytes() if target.exists() else None
        held_digest = hashlib.sha256(held).hexdigest() if held is not None else ""
        unchanged_document = all(
            old.get(field, "") == str(value) for field, value in document_fields.items()
        )
        verified_held = (
            held is not None
            and unchanged_document
            and old.get("sha256") == held_digest
            and old.get("bytes") == str(len(held))
        )
        payload: bytes
        if verified_held and held is not None:
            payload = held
            digest = held_digest
            status = "held"
        else:
            payload = fetch.body(document.url, timeout=300, headers=HEADERS)
            digest = hashlib.sha256(payload).hexdigest()
            status = "fetched"
            if held is not None and held_digest != digest:
                LOGGER.error(
                    "held source differs from live bytes",
                    extra={
                        "event": "source_changed",
                        **_event_fields(
                            document,
                            held_sha256=held_digest,
                            live_sha256=digest,
                        ),
                    },
                )
                raise RuntimeError(
                    f"{target.relative_to(root)} differs from the live source; "
                    "not overwritten"
                )
            if held is None:
                target.write_bytes(payload)

        row = document_fields
        row.update(
            {
                "retrieved_at": old.get("retrieved_at")
                or datetime.now(UTC).isoformat(),
                "sha256": digest,
                "bytes": len(payload),
            }
        )
        rows.append(row)
        LOGGER.info(
            f"source {status}",
            extra={
                "event": f"source_{status}",
                **_event_fields(
                    document,
                    bytes=len(payload),
                    sha256=digest,
                ),
            },
        )

    with manifest.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=MANIFEST_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(sorted(rows, key=lambda row: row["file"]))
    LOGGER.info(
        "source manifest written",
        extra={
            "event": "source_manifest_written",
            "documents": len(rows),
            "manifest": str(manifest.relative_to(root)),
        },
    )
    return rows
