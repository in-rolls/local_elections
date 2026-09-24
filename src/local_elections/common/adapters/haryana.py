"""Haryana, from local_elections_haryana.

The closest of the siblings to the pooled schema: caste and gender are already
separate orthogonal columns, and district, block, gram_panchayat and ward_no are
all present under those names. What is missing is what the repository's layout
encodes rather than states - the year lives in a directory name and the tier in
a filename.

Two things worth naming:

`BC_A` is not a spelling of `BC`. Haryana reserves panchayat seats for Block A
of the Backward Classes list only, so the local label is finer than the pooled
one and both are kept. 12,515 rows carry it.

889 of the 2022 ward rows are typeset in Kruti Dev while their district and
block are Latin - the panchayat's name and the winner's, in Palwal, Fatehabad
and Jhajjar. Kruti Dev is a deterministic byte mapping rather than damage, so
those names convert exactly: `cueanksjh` is बनमंदोरी and `ujsUnz dqekj` is
नरेन्द्र कुमार. Left as printed they could not be joined to any other source on
name, which is the whole point of holding a name. The conversion happens here,
on read, rather than in the sibling: this repository does not write to its
siblings, and `reservation_raw` keeps what the file actually said.

There is no `source_page`. The parser recorded which notification each row came
from but not the page within it, so provenance_level is `document`: a row can be
traced to a PDF and not to a page. That is recoverable by re-parsing and is on
the worklist rather than papered over.
"""

import csv
import pathlib

from local_elections.common import krutidev
from local_elections.common.normalize import label

# Names typeset in Kruti Dev, converted on read. Only these: the district and
# the block are already Latin in every row, and running Latin through the
# converter turns a real word into real-looking Devanagari for a word that was
# never Kruti Dev - the mistake the Jharkhand parser carries a comment about.
TRANSLITERATE = ("gram_panchayat", "ward_name", "winner")

REPO = "local_elections_haryana"
URL = "https://github.com/in-rolls/local_elections_haryana"
STATE = "Haryana"

# filename stem -> canonical office
TIERS = {
    "gp_reservation": ("gp_head", "sarpanch"),
    "ward_reservation": ("gp_ward", "ward"),
}

# What the sibling's committed files hold. A mismatch means the sibling moved
# under us, and silently pooling a different number of rows is exactly the
# failure this repository keeps meeting.
# Moved once, deliberately, for the v0.2.1 correction: the sibling's parser was
# deleting rows whose category it could not read and shifting every field right
# where the English printing writes "Ward 1" for "1". 2016 gained 261 ward rows
# and 11 panchayats; 2022 lost 30 ward rows, which is what stopping a
# double-read costs. Changing these numbers is meant to be a decision, which is
# why the build refuses until somebody makes it.
# 2022 moved again for v0.2.8, and downwards on purpose. Palwal/Prithla prints
# its notification twice and pdfplumber returned the Hindi pages as two tables
# over one grid, so every seat there was emitted a second time with the father
# read as the winner and no ward - 68 panchayats in a block that has 34. The 26
# affected pages are now read by Surya, and the phantom printing is gone.
DECLARED = {
    ("2016", "gp_head"): 6090,
    ("2016", "gp_ward"): 61879,
    ("2022", "gp_head"): 6123,
    ("2022", "gp_ward"): 60981,
}


def slices(root):
    root = pathlib.Path(root)
    for year_dir in sorted(p for p in (root / "data").iterdir() if p.is_dir()):
        year = year_dir.name
        if not year.isdigit():
            continue
        for stem, (tier, tier_local) in sorted(TIERS.items()):
            path = year_dir / f"{stem}.csv"
            if not path.exists():
                continue
            with path.open(encoding="utf-8", errors="replace") as fh:
                rows = [
                    convert(r, year, tier, tier_local, path, root)
                    for r in csv.DictReader(fh)
                ]
            expected = DECLARED.get((year, tier))
            if expected is not None and len(rows) != expected:
                raise SystemExit(
                    f"{REPO}: {year}/{tier} holds {len(rows):,} rows, "
                    f"{expected:,} declared - the sibling changed"
                )
            yield {
                "dataset_id": f"haryana/{tier}/{year}",
                "state": STATE,
                "rows": rows,
                # the parser kept the notification but not the page within it
                "provenance_level": "document",
                "unit_of_observation": "seat",
            }


def convert(row, year, tier, tier_local, path, root):
    local = row.get("caste_reservation", "")
    if row.get("script") == "krutidev":
        row = dict(row)
        for column in TRANSLITERATE:
            value = row.get(column) or ""
            if value and not krutidev.looks_converted(value):
                row[column] = krutidev.to_unicode(value)
    return {
        "state": STATE,
        "year": year,
        "tier": tier,
        "tier_local": tier_local,
        "district": row.get("district", ""),
        "block": row.get("block", ""),
        "gram_panchayat": row.get("gram_panchayat", ""),
        "ward_no": row.get("ward_no", ""),
        # Block A of the Backward Classes list, which is not the same set as
        # another state's BC - the fold is kept reversible
        "caste_reservation": "BC" if local == "BC_A" else local,
        "caste_reservation_local": local,
        "woman_reserved": row.get("woman_reserved", ""),
        # Rebuilt from the pooled category, not carried across. Haryana prints
        # "BC-A Other than Woman" against a caste_reservation of BC, so the
        # label as printed disagrees with the two fields it is meant to
        # summarise - 12,521 rows of it. The printed form survives in
        # reservation_raw and caste_reservation_local.
        "reservation": label(
            "BC" if local == "BC_A" else local, str(row.get("woman_reserved")) == "1"
        ),
        "reservation_raw": row.get("reservation_raw", ""),
        "winner": row.get("winner", ""),
        "winner_basis": "published" if (row.get("winner") or "").strip() else "",
        "relation_name": row.get("father_husband", ""),
        "vacant": row.get("vacant", ""),
        "unopposed": row.get("unopposed", ""),
        # converted above, so the row is Devanagari now whatever it was printed
        # in; the printed form survives in reservation_raw
        "script": "devanagari"
        if row.get("script") == "krutidev"
        else row.get("script", "latin"),
        # The sibling compares the two GP-head reservation printings, keyed by
        # PDF and GP serial, then carries that comparison onto every row for the
        # GP. It is evidence about the head reservation, not each ward seat.
        # Passing it through on ward rows produced 1,392 false ward-level
        # `printings_disagree` flags in the pooled master.
        "printings_agree": row.get("printings_agree", "") if tier == "gp_head" else "",
        "source_path": str(
            (path.parent / "pdfs" / row.get("source_pdf", "")).relative_to(root)
        ),
        "source_page": "",
    }
