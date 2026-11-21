"""Render the public data catalog from the exact archive offered for download."""

import argparse
import hashlib
import json
import tarfile
from collections import Counter
from datetime import date
from pathlib import Path, PurePosixPath

import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq
import yaml
from jinja2 import Environment, FileSystemLoader, StrictUndefined

SITE = Path(__file__).resolve().parent
OFFICES = {
    "gp_head": "Village council head",
    "gp_vice_head": "Village council deputy head",
    "gp_ward": "Village council ward member",
    "block_head": "Block council head",
    "block_vice_head": "Block council deputy head",
    "block_member": "Block council member",
    "zp_head": "District council head",
    "zp_member": "District council member",
    "kachahari_head": "Village court head",
    "kachahari_member": "Village court member",
    "ulb_ward": "Municipal ward member",
    "ulb_head": "Municipal head",
}


def read_archive(path):
    """Count records in the archive and recover its citation metadata."""
    citation = None
    rows = []
    candidates = 0
    with tarfile.open(path, "r|gz") as archive:
        for member in archive:
            name = PurePosixPath(member.name)
            if name.as_posix() == "CITATION.cff":
                citation = yaml.safe_load(archive.extractfile(member))
            if name.parent.as_posix() != "data/master" or name.suffix != ".parquet":
                continue
            if name.stem.startswith("candidates_"):
                stream = pa.BufferReader(archive.extractfile(member).read())
                candidates += pq.read_metadata(stream).num_rows
            elif name.stem.startswith("master_") and name.stem != "master_extras":
                stream = pa.BufferReader(archive.extractfile(member).read())
                columns = ["state", "year", "tier", "winner"]
                table = pq.read_table(stream, columns=columns)
                winners = pc.utf8_trim_whitespace(pc.fill_null(table["winner"], ""))
                table = table.append_column(
                    "named", pc.cast(pc.not_equal(winners, ""), pa.int64())
                )
                counts = table.group_by(columns[:3]).aggregate(
                    [("named", "count"), ("named", "sum")]
                )
                rows.extend(counts.to_pylist())
    if citation is None:
        raise ValueError("Missing CITATION.cff in the pooled archive")
    if not rows or not candidates:
        raise ValueError("Expected both seat and candidate files in the pooled archive")
    return (
        citation,
        candidates,
        sorted(rows, key=lambda r: (r["state"], r["year"], r["tier"])),
    )


def render(release_path, archive_dir, output):
    """Write the edition page and its browser assets to the output directory."""
    release = json.loads(release_path.read_text())
    tag = release["tag_name"]
    filename = f"pooled_data_{tag}.tar.gz"
    (asset,) = [a for a in release["assets"] if a["name"] == filename]
    path = archive_dir / filename
    with path.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    if asset["digest"] != f"sha256:{digest}":
        raise ValueError(f"Archive checksum differs from the GitHub release for {tag}")
    citation, candidates, rows = read_archive(path)
    if str(citation["version"]) != tag.removeprefix("v"):
        raise ValueError("Citation version differs from release tag")
    released = date.fromisoformat(str(citation["date-released"]))
    authors = ", ".join(
        a.get("name") or f'{a["family-names"]}, {a["given-names"]}'
        for a in citation["authors"]
    )
    state_rows = Counter()
    for row in rows:
        row["office"] = OFFICES[row["tier"]]
        state_rows[row["state"]] += row["named_count"]
    template = Environment(
        loader=FileSystemLoader(SITE),
        autoescape=True,
        undefined=StrictUndefined,
    ).get_template("index.html")
    html = template.render(
        tag=tag,
        released=released,
        authors=authors,
        archive_url=asset["browser_download_url"],
        megabytes=round(asset["size"] / 1_000_000),
        release_url=release["html_url"],
        docs=f'{citation["repository-code"]}/blob/{tag}',
        rows=rows,
        states=sorted(state_rows),
        years=sorted({r["year"] for r in rows}),
        offices=sorted({r["office"] for r in rows}),
        seats=state_rows.total(),
        candidates=candidates,
    )
    output.mkdir(parents=True, exist_ok=True)
    (output / "index.html").write_text(html, encoding="utf-8")
    for name in ("site.css", "site.js"):
        (output / name).write_bytes((SITE / name).read_bytes())


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("release", type=Path, help="GitHub REST release metadata JSON")
    parser.add_argument(
        "archives", type=Path, help="Directory containing the pooled archive"
    )
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    render(args.release, args.archives, args.output)
