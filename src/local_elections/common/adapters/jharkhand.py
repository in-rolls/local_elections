"""Jharkhand's panchayat seats, from local_elections_jharkhand.

Mukhiya (gram panchayat head) seats for 2015 and 2022 come from the State
Election Commission's Form 23 ("publication of election results"), OCRed
on-device and parsed by the sibling: one row per seat with its reservation and
its winner.

The 2015 ward member, panchayat samiti and zila parishad seats come from the
sibling's parse/members_2015.py, the parser this repository ran in-tree until
October 2026 and moved there unchanged. Those rows are rebuilt here in the
row vocabulary the in-tree parse wrote, and `reserved_caste` and
`reserved_woman` are read again from the printed cell (`reserved_raw`) with
this repository's normalizer; a disagreement stops the build.

Form 23 prints the seat's reservation, not the winner's sex. Where the sibling
has inferred it from the name, the probability travels under its own name
(winner_female_probability_from_name); winner_gender stays blank.

Two encodings to know about:

- Block names are missing on many rows (the gazette prints only a number in
  places), and block numbers are what identify a block. The master has no
  block-number column, so gp_no carries "<block_no>/<gp_no>" and the seat key
  keeps the block's identity.
- 2022 dropped OBC reservation; its former BC seats are printed as "open
  category" and are unreserved (NONE). Khunti prints a bare "reserved" for some
  seats with no category; their caste category is left blank.

Provenance is `page`: every seat carries its PDF and page.
"""

import pathlib

import pyarrow.parquet as pq

from local_elections.common.normalize import caste_of, label, woman_of

REPO = "local_elections_jharkhand"
URL = "https://github.com/in-rolls/local_elections_jharkhand"
STATE = "Jharkhand"

YEARS = ("2015", "2022")
RESULTS = "data/release/{year}/mukhiya_results.parquet"
LINKS = {("2015", "2022"): "data/release/linkage/gp_2015_2022.parquet"}
INFERRED = "data/release/inferred/winner_woman_probability_{year}.parquet"
# tier_local -> the 2015 file that holds it
MEMBERS = {
    "ward_member": "data/release/2015/ward_member_results.parquet",
    "panchayat_samiti": "data/release/2015/panchayat_samiti_results.parquet",
    "zila_parishad": "data/release/2015/zila_parishad_results.parquet",
}

DECLARED = {
    "data/release/2015/mukhiya_results.parquet": 4137,
    "data/release/2022/mukhiya_results.parquet": 4334,
    "data/release/2015/ward_member_results.parquet": 19843,
    "data/release/2015/panchayat_samiti_results.parquet": 5171,
    "data/release/2015/zila_parishad_results.parquet": 226,
}

CASTES = {"SC", "ST", "BC", "NONE"}


def text(value):
    if value is None or value != value:  # None or NaN
        return ""
    if isinstance(value, bool):
        return str(int(value))
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def locator(district, block_no, gp_no, panchayat):
    return "/".join((text(district), text(block_no), text(gp_no), text(panchayat)))


# The inferred file is keyed by where the seat is printed, which is unique even
# where (district, block, GP number, name) repeats.
INFERRED_KEY = ("district", "block_no", "gp_no", "source_path", "source_page", "row_y0")


def printed_at(r):
    return tuple(text(r.get(k)) for k in INFERRED_KEY)


def read(root, relative):
    path = root / relative
    if not path.exists():
        return None
    rows = pq.read_table(path).to_pylist()
    expected = DECLARED.get(relative)
    if expected is not None and len(rows) != expected:
        raise SystemExit(
            f"{REPO}: {relative} holds {len(rows):,} rows, "
            f"{expected:,} declared - the sibling changed"
        )
    return rows


def inferred_sex(root, year):
    rows = read(root, INFERRED.format(year=year)) or []
    out = {}
    for r in rows:
        probability = r.get("winner_woman_probability")
        if probability is None or probability != probability:
            continue
        key = printed_at(r)
        if key in out:
            raise SystemExit(f"{REPO}: {year} inferred sex repeats {key}")
        out[key] = {
            "winner_female_probability_from_name": f"{probability:.6f}",
            "winner_female_probability_method": r["winner_woman_probability_method"],
        }
    return out


def seat(r, inferred):
    caste = text(r.get("reserved_caste"))
    caste = caste if caste in CASTES else ""
    woman = text(r.get("reserved_woman"))
    stated = caste != "" and woman != ""
    where = locator(r["district"], r["block_no"], r["gp_no"], r["gram_panchayat"])
    row = {
        "state": STATE,
        "year": text(r.get("year")),
        "tier": "gp_head",
        "tier_local": text(r.get("tier_local")),
        "district": text(r.get("district")),
        "block": text(r.get("block")),
        "gram_panchayat": text(r.get("gram_panchayat")),
        "gp_no": f"{text(r.get('block_no'))}/{text(r.get('gp_no'))}",
        "caste_reservation": caste,
        "caste_reservation_local": text(r.get("reserved_raw")),
        "woman_reserved": woman,
        "gender_stated": "1" if woman != "" else "0",
        "reservation": label(caste, woman == "1") if stated else "",
        "reservation_raw": text(r.get("reserved_raw")),
        "winner": text(r.get("winner")),
        "winner_basis": "published" if text(r.get("winner")) else "",
        "vacant": text(r.get("vacant")),
        "open_category": text(r.get("reserved_open_seat")),
        "entry_method": text(r.get("entry_method")),
        "source_path": text(r.get("source_path")),
        "source_page": text(r.get("source_page")),
        "source_locator": where,
    }
    row.update(inferred.get(printed_at(r), {}))
    return row


def member(r):
    """A 2015 member-tier row in the row vocabulary the in-tree parse wrote.

    The printed cell is "<caste> | <woman>", as the parser joined its two
    columns. Each half is read again here; the sibling's reading must agree.
    """
    caste_cell, _, woman_cell = text(r["reserved_raw"]).partition(" | ")
    caste, woman = text(r["reserved_caste"]), int(r["reserved_woman"])
    if caste_of(caste_cell) != caste or woman_of(woman_cell) != woman:
        raise SystemExit(
            f"{REPO}: {r['source_path']} p{r['source_page']} reads "
            f"{r['reserved_raw']!r} as {caste}/{woman}; this repository's "
            f"normalizer reads {caste_of(caste_cell)}/{woman_of(woman_cell)}"
        )
    path = text(r["source_path"])
    return {
        "state": text(r["state"]),
        "year": text(r["year"]),
        "district": text(r["district"]),
        "block": text(r["block"]),
        "block_no": text(r["block_no"]),
        "gram_panchayat": text(r["gram_panchayat"]),
        "gp_no": text(r["gp_no"]),
        "ward_no": text(r["ward_no"]),
        "seat_no": text(r["seat_no"]),
        "seat_id_raw": text(r["seat_id_raw"]),
        "seat_from_image": "1" if r["seat_from_image"] else "",
        "tier": text(r["tier"]),
        "tier_local": text(r["tier_local"]),
        "reservation": label(caste, woman),
        "caste_reservation": caste,
        "woman_reserved": str(woman),
        "winner": text(r["winner"]),
        "vacant": text(r["vacant"]),
        "reservation_raw": text(r["reserved_raw"]),
        "script": text(r["script"]),
        "source_path": path,
        "source_page": text(r["source_page"]),
        "source_pdf": path.rsplit("/", 1)[-1],
        "source_url": "",
        "source_capture": "",
    }


def members(root):
    for tier_local, relative in MEMBERS.items():
        rows = read(root, relative)
        if rows is None:
            continue
        tier = rows[0]["tier"] if rows else tier_local
        yield {
            "dataset_id": f"jharkhand/{tier}/2015",
            "state": STATE,
            "rows": [member(r) for r in rows],
            "provenance_level": "page",
            "unit_of_observation": "seat",
        }


def slices(root):
    root = pathlib.Path(root)
    for year in YEARS:
        results = read(root, RESULTS.format(year=year))
        if results is None:
            continue
        inferred = inferred_sex(root, year)
        yield {
            "dataset_id": f"jharkhand/gp_head/{year}",
            "state": STATE,
            "rows": [seat(r, inferred) for r in results],
            "provenance_level": "page",
            "unit_of_observation": "seat",
        }
    yield from members(root)


def links(root):
    """The sibling's mukhiya seat links, keyed by both seats' locators."""
    root = pathlib.Path(root)
    for (a, b), relative in LINKS.items():
        path = root / relative
        if not path.exists():
            continue
        for r in pq.read_table(path).to_pylist():
            yield {
                "from_dataset_id": f"jharkhand/gp_head/{a}",
                "from_locator": locator(
                    r[f"district_{a}"],
                    r[f"block_no_{a}"],
                    r[f"gp_no_{a}"],
                    r[f"gram_panchayat_{a}"],
                ),
                "to_dataset_id": f"jharkhand/gp_head/{b}",
                "to_locator": locator(
                    r[f"district_{b}"],
                    r[f"block_no_{b}"],
                    r[f"gp_no_{b}"],
                    r[f"gram_panchayat_{b}"],
                ),
                "link_pass": r.get("link_rule") or "name",
                "name_score": r["name_score"],
                "source_path": relative,
            }
