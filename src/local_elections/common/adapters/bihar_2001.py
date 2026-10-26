"""Bihar 2001, from the sibling's release of the SEC's division lists.

The old SEC site (sec.bih.nic.in, kept by the Wayback Machine) listed the
mukhiyas elected in 2001, panchayat by panchayat, for all nine divisions. The
lists print no reservation - 2001 was Bihar's last panchayat election before
reservation - so the reservation columns stay blank: blank is what the
document says, and "open" would be a reading of the law, not of the list.

The honorific is printed apart from the name, sometimes as a ditto mark ('')
standing for the one above; the sibling keeps both and this adapter passes the
honorific through as an extra.
"""

import hashlib
import json

import pyarrow.parquet as pq

from local_elections.common import normalize

RELEASE = "data/release/2001"
FILE = "mukhiya_winners.parquet"
SHA256 = "c17659ebc6ea7f9bd2e55afef4010edbbe17b753e48df118a380dc3f208916e4"
DECLARED = 8426
YEAR = "2001"
STATE = "Bihar"


def read_release(root):
    directory = root / RELEASE
    manifest = json.loads((directory / "MANIFEST.json").read_text())
    path = directory / FILE
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    published = {item["path"]: item["sha256"] for item in manifest["files"]}
    if digest != SHA256 or published[FILE] != digest:
        raise ValueError(f"Bihar 2001 release checksum changed: {digest}")
    rows = pq.read_table(path).to_pylist()
    if len(rows) != DECLARED:
        raise ValueError(f"Bihar 2001 release holds {len(rows):,} rows")
    if {r["year"] for r in rows} != {2001}:
        raise ValueError("Bihar 2001 release is not dated 2001")
    return rows


def text(value):
    return "" if value is None else str(value).strip()


def convert(r):
    return {
        "state": STATE,
        "year": YEAR,
        "tier": "gp_head",
        "tier_local": "mukhiya",
        "district": text(r["district"]),
        "block": text(r["block"]),
        "gram_panchayat": text(r["gram_panchayat"]),
        "listing_scope": "partial",
        "winner": text(r["winner"]),
        "winner_basis": "published" if text(r["winner"]) else "",
        "winner_honorific": text(r["winner_honorific"]),
        "division": text(r["division"]),
        "script": normalize.script_of(
            text(r["district"]), text(r["block"]), text(r["gram_panchayat"])
        ),
        "source_path": f"{RELEASE}/{FILE}",
        "source_page": text(r["source_page"]),
        "source_sha256": SHA256,
        "source_locator": f"{r['source_path']}#p{r['source_page']}/{r['serial']}",
    }


def slices(root):
    yield {
        "dataset_id": f"bihar/gp_head/{YEAR}",
        "state": STATE,
        "rows": [convert(r) for r in read_release(root)],
        "provenance_level": "row",
        "unit_of_observation": "seat",
    }
