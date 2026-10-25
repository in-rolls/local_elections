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

import pathlib

import pyarrow.parquet as pq

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

# released table -> canonical office
TIERS = {
    "gram_panchayat_head_seat_reservation": ("gp_head", "sarpanch"),
    "gram_panchayat_ward_member_seat_reservation": ("gp_ward", "ward"),
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
# 2010 entered with the sibling's v0.3 release: 22 district notifications,
# against an official 6,075 panchayats and 58,608 panches. Bhuna's printing is
# incomplete and Hassanpur and Nissing are missing, which is most of the gap.
# 2005 and 2000 came from the gazette scans the SEC republished in 2022, read by
# a hosted model. 2005 is complete in all 119 blocks it holds. 2000 holds 5,932
# of the 6,035 panchayats in the SEC's table: Gharaunda stops at GP 24 of 51,
# Radaur misses six and Panchkula/Barwala is not held; the sibling's
# data/manual/2000/block_status.csv records each block.
DECLARED = {
    ("2000", "gp_head"): 5932,
    ("2000", "gp_ward"): 53701,
    ("2005", "gp_head"): 6198,
    ("2005", "gp_ward"): 60425,
    ("2010", "gp_head"): 5924,
    ("2010", "gp_ward"): 57856,
    ("2016", "gp_head"): 6090,
    ("2016", "gp_ward"): 61879,
    ("2022", "gp_head"): 6123,
    ("2022", "gp_ward"): 60981,
}


# The sibling reviewed every 2005 and 2010 block whose printed women's seats
# fall far below the statutory third. In seven 2010 blocks and four 2005 blocks
# the commission's reservation table or the winners' names contradict the
# printed sarpanch categories. In 2005 Ambala/Naraingarh the women's share is
# statutory but a third of sarpanch rows print a BC category the state did not
# reserve before 2021, so only the caste half is unreliable; the single flag
# covers it too, and the sibling's `block_reservation_review` says which half.
# Every such row keeps its printed category and carries the flag.
UNRELIABLE = ("reservation_unreliable", "caste_unreliable")
INFERRED = "data/release/inferred/winner_woman_probability_{year}.parquet"
LINKS = {
    ("2000", "2005"): "data/release/linkage/gp_2000_2005.parquet",
    ("2005", "2010"): "data/release/linkage/gp_2005_2010.parquet",
    ("2010", "2016"): "data/release/linkage/gp_2010_2016.parquet",
    ("2016", "2022"): "data/release/linkage/gp_2016_2022.parquet",
}


def inferred_sex(root, year):
    """The sibling's name-based probability that each elected sarpanch is a woman.

    Haryana's notifications record no sex, so this is the only reading of it,
    and it travels under its own name: winner_gender stays blank.
    """
    path = root / INFERRED.format(year=year)
    if not path.exists():
        return {}
    out = {}
    # A few notifications print one serial twice in a block (Hisar-2 serial 22
    # names Ishwar and Bhal Singh for Kirtan), so the printed winner is part of
    # the key. In 2000, 374 sarpanch rows have no serial the scan could read,
    # and two Om Parkashes win in Tosham, so the printed GP name is too.
    for r in pq.read_table(path).to_pylist():
        probability = r["winner_woman_probability"]
        if probability is None or probability != probability:
            continue
        key = (
            r["district"],
            r["block"],
            "" if r["sr_no"] is None else str(r["sr_no"]),
            r["gram_panchayat"] or "",
            r["winner"],
        )
        if key in out:
            raise SystemExit(f"{REPO}: {year} inferred sex repeats {key}")
        out[key] = {
            "winner_female_probability_from_name": f"{probability:.6f}",
            "winner_female_probability_method": r["winner_woman_probability_method"],
        }
    return out


def locator(district, block, sr_no, gram_panchayat, ward_no=""):
    # The serial alone repeats: Gurgaon/Sohna prints 21 for both Johlaka and
    # Kadarpur. The sibling's links are keyed on serial and name together.
    parts = (district, block, sr_no, gram_panchayat, ward_no)
    return "/".join(str(x) for x in parts if str(x))


def slices(root):
    root = pathlib.Path(root)
    release = root / "data" / "release"
    for year_dir in sorted(p for p in release.iterdir() if p.is_dir()):
        year = year_dir.name
        if not year.isdigit():
            continue
        for stem, (tier, tier_local) in sorted(TIERS.items()):
            path = year_dir / f"{stem}.parquet"
            if not path.exists():
                continue
            inferred = inferred_sex(root, year) if tier == "gp_head" else {}
            source = [text_row(r) for r in pq.read_table(path).to_pylist()]
            rows = [convert(r, year, tier, tier_local) for r in source]
            for raw, row in zip(source, rows, strict=True):
                place = (row["district"], row["block"])
                if tier == "gp_head":
                    row.update(
                        inferred.get(
                            (
                                *place,
                                row["sr_no"],
                                row["printed_gram_panchayat"],
                                row["printed_winner"],
                            ),
                            {},
                        )
                    )
                    if raw.get("block_reservation_review") in UNRELIABLE:
                        row["reservation_source_conflict"] = 1
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


def text_row(record):
    """A released row as the sibling's CSV text: flags as 1/0, nulls blank."""
    out = {}
    for key, value in record.items():
        if value is None:
            out[key] = ""
        elif isinstance(value, bool):
            out[key] = "1" if value else "0"
        else:
            out[key] = str(value)
    return out


def convert(row, year, tier, tier_local):
    local = row.get("reserved_caste", "")
    printed_winner = row.get("winner", "")
    printed_place = row.get("gram_panchayat", "")
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
        # Not gp_no: that would enter the seat key and move every Haryana
        # row_id. It is kept for the joins below and in source_locator.
        "sr_no": row.get("sr_no", ""),
        # before Kruti Dev conversion, as the sibling's inferred table keys it
        "printed_winner": printed_winner,
        "printed_gram_panchayat": printed_place,
        "ward_no": row.get("ward_no", ""),
        # Block A of the Backward Classes list, which is not the same set as
        # another state's BC - the fold is kept reversible
        "caste_reservation": "BC" if local == "BC_A" else local,
        "caste_reservation_local": local,
        "woman_reserved": row.get("reserved_woman", ""),
        # Rebuilt from the pooled category, not carried across. Haryana prints
        # "BC-A Other than Woman" against a caste_reservation of BC, so the
        # label as printed disagrees with the two fields it is meant to
        # summarise - 12,521 rows of it. The printed form survives in
        # reservation_raw and caste_reservation_local. A 2000 or 2005 row whose
        # caste or women's mark could not be read gets no label: rebuilding one
        # would read the silence as "General" or "Other than Woman".
        "reservation": label(
            "BC" if local == "BC_A" else local, str(row.get("reserved_woman")) == "1"
        )
        if local and str(row.get("reserved_woman", "")) in ("0", "1")
        else "",
        "reservation_raw": row.get("reserved_raw", ""),
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
        "source_path": row.get("source_path", ""),
        "source_page": "",
        # the notification's own serial within its block, which is what the
        # sibling's seat links are keyed on
        "source_locator": locator(
            row.get("district", ""),
            row.get("block", ""),
            row.get("sr_no", ""),
            printed_place,
            row.get("ward_no", "") if tier == "gp_ward" else "",
        ),
    }


def links(root):
    """The sibling's sarpanch seat links, keyed by both seats' locators."""
    root = pathlib.Path(root)
    for (a, b), relative in LINKS.items():
        path = root / relative
        if not path.exists():
            continue
        for r in pq.read_table(path).to_pylist():
            yield {
                "from_dataset_id": f"haryana/gp_head/{a}",
                "from_locator": locator(
                    r[f"district_{a}"],
                    r[f"block_{a}"],
                    r[f"sr_no_{a}"],
                    r[f"gram_panchayat_{a}"],
                ),
                "to_dataset_id": f"haryana/gp_head/{b}",
                "to_locator": locator(
                    r[f"district_{b}"],
                    r[f"block_{b}"],
                    r[f"sr_no_{b}"],
                    r[f"gram_panchayat_{b}"],
                ),
                "link_pass": r["link_pass"],
                "name_score": r["name_score"],
                "source_path": relative,
            }
