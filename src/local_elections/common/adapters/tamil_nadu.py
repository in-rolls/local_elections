"""Tamil Nadu, from local_elections_tamil_nadu.

Village panchayat presidents in three ordinary elections: 2011 (all 31 rural
districts), 2019 (27 districts) and 2021 (the 9 districts carved out after
2011, plus 105 by-election seats elsewhere). The same three elections' ward
members are read too: village panchayat wards (gp_ward), panchayat union wards
(block_member) and district panchayat wards (zp_member). The 2011 village
ward sheets print winners only; every other ward sheet lists all candidates.

The sibling has already put each election into seat rows, one per president
or ward seat, with the reservation, the winner and the winner's sex as printed
on the result sheet, and a separate candidate table. So nothing is collapsed
here: seats are read as seats and each seat's candidates are attached to it.

Everything is in Tamil script. The sibling recovered the text from the SEC's
PDFs by inverting the font's glyph table (2019, 2021; exact, and 99.95% agreed
with a second publication) or by labelling glyph outlines (2011). Spellings are
kept as printed.

Women's reservation was one third of seats in 2011 and one half from 2019 (the
2016 amendment; the 2016 election itself was cancelled), so the two cycles are
not the same rule eight years apart.

Provenance is `page`: every seat carries its PDF and page.
"""

import csv
import pathlib

import pyarrow.parquet as pq

from local_elections.common.normalize import label

REPO = "local_elections_tamil_nadu"
URL = "https://github.com/in-rolls/local_elections_tamil_nadu"
STATE = "Tamil Nadu"

YEARS = ("2011", "2019", "2021")
RESULTS = "data/{year}/vp_president_results.parquet"
CANDIDATES = "data/{year}/vp_president_candidates.parquet"
DISTRICTS = "data/reference/districts.csv"
WARD_RESULTS = "data/{year}/ward_results.parquet"
WARD_CANDIDATES = "data/{year}/ward_candidates.parquet"

# The sibling's ward offices, as this repository's tiers.
WARD_TIER = {"vp_ward": "gp_ward", "pu_ward": "block_member", "dp_ward": "zp_member"}

# Rows the sibling's committed files hold; a change stops the build.
DECLARED = {
    "data/2011/vp_president_results.parquet": 12523,
    "data/2019/vp_president_results.parquet": 9624,
    "data/2021/vp_president_results.parquet": 3005,
    "data/2011/vp_president_candidates.parquet": 51032,
    "data/2019/vp_president_candidates.parquet": 35992,
    "data/2021/vp_president_candidates.parquet": 11208,
    "data/2011/ward_results.parquet": 106448,
    "data/2019/ward_results.parquet": 82339,
    "data/2021/ward_results.parquet": 24784,
    "data/2011/ward_candidates.parquet": 36250,
    "data/2019/ward_candidates.parquet": 214335,
    "data/2021/ward_candidates.parquet": 72844,
}

# A seat is identified by district, union and panchayat within an election;
# the sibling checks this is unique in every year.
KEY = ("election_type", "district_code", "block", "gram_panchayat")
WARD_KEY = (*KEY, "tier", "ward_no")

# The sibling's seat links between elections, keyed by each side's locator.
LINKS = {
    ("2011", "2019"): "data/linkage/vp_2011_2019.parquet",
    ("2011", "2021"): "data/linkage/vp_2011_2021.parquet",
}


def locator(district_code, block, panchayat):
    return "/".join((district_code, block, panchayat))


# the sibling's 1/0 *_woman values, as this repository's gender text
GENDER_OF = {"1": "female", "0": "male"}


def text(value):
    if value is None or value != value:  # None or NaN
        return ""
    if isinstance(value, bool):
        return str(int(value))
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


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


def district_names(root):
    with (root / DISTRICTS).open(encoding="utf-8") as fh:
        return {r["district_code"]: r["district"] for r in csv.DictReader(fh)}


def member(c):
    return {
        "candidate_no": text(c.get("candidate_no")),
        "candidate_name": text(c.get("candidate_name")),
        "relation_name": text(c.get("relation_name")),
        # as printed (published as candidate_woman_raw)
        "candidate_gender": text(c.get("candidate_woman_raw")),
        "candidate_woman": text(c.get("candidate_woman")),
        "votes": text(c.get("votes")),
        "result": text(c.get("result")),
        "elected": text(c.get("elected")),
    }


def seat(r, names, members):
    caste = text(r.get("reserved_caste"))
    woman = text(r.get("reserved_woman"))
    stated = caste != "" and woman != ""
    return {
        "state": STATE,
        "year": text(r.get("year")),
        "election_type": text(r.get("election_type")),
        "tier": "gp_head",
        "tier_local": text(r.get("tier_local")),
        "district": names[r["district_code"]],
        "block": text(r.get("block")),
        "gram_panchayat": text(r.get("gram_panchayat")),
        "gp_no": text(r.get("block_seq")),
        "caste_reservation": caste,
        "caste_reservation_local": text(r.get("reserved_caste_local")),
        "woman_reserved": woman,
        # a blank bracket on the sheet states no reservation; left unknown
        "gender_stated": "1" if stated else "0",
        "reservation": label(caste, woman == "1") if stated else "",
        "reservation_raw": text(r.get("reserved_raw")),
        "winner": text(r.get("winner")),
        "winner_gender": GENDER_OF.get(text(r.get("winner_woman")), ""),
        "winner_gender_raw": text(r.get("winner_woman_raw")),
        "winner_basis": text(r.get("winner_basis")),
        "votes": text(r.get("votes")),
        "runner_up": text(r.get("runner_up")),
        "runner_up_votes": text(r.get("runner_up_votes")),
        "margin": text(r.get("margin")),
        "vacant": text(r.get("vacant")),
        "unopposed": text(r.get("unopposed")),
        "seat_candidates": text(r.get("seat_candidates")),
        "electors": text(r.get("electors")),
        "valid_votes": text(r.get("valid_votes")),
        "source_path": text(r.get("source_path")),
        "source_page": text(r.get("source_page")),
        "source_locator": locator(r["district_code"], r["block"], r["gram_panchayat"]),
        "seat_members": members,
    }


def ward_locator(r):
    """Where a ward seat sits; the printed place unless the sheet repeats it.

    A sheet can print one GP name over two GPs' wards (the sibling marks these
    gp_name_repeated), so those seats are told apart by page and row instead.
    """
    place = "/".join(
        text(r.get(k)) for k in ("tier", "district_code", "block", "gram_panchayat")
    )
    out = f"{place}/{text(r.get('ward_no'))}"
    if "gp_name_repeated" in text(r.get("quality_flags")):
        out += f"#p{text(r.get('source_page'))}r{text(r.get('source_row'))}"
    return out


def ward_basis(r, members):
    """Why the winner is the winner: the sheet names them in every case."""
    if text(r.get("unopposed")) in ("1", "True"):
        return "uncontested"
    won = [m for m in members if m["elected"] in ("1", "True")]
    if any("குலுக்கல்" in m["result"] for m in won):
        return "lot"
    return "published" if text(r.get("winner")) else ""


def ward_seat(r, names, members):
    caste = text(r.get("reserved_caste"))
    woman = text(r.get("reserved_woman"))
    stated = caste != "" and woman != ""
    return {
        "state": STATE,
        "year": text(r.get("year")),
        "election_type": text(r.get("election_type")),
        "tier": WARD_TIER[r["tier"]],
        "tier_local": text(r.get("tier_local")),
        "district": names[r["district_code"]],
        "block": text(r.get("block")),
        "gram_panchayat": text(r.get("gram_panchayat")),
        "ward_no": text(r.get("ward_no")),
        "caste_reservation": caste,
        "caste_reservation_local": text(r.get("reserved_caste_local")),
        "woman_reserved": woman,
        "gender_stated": "1" if stated else "0",
        "reservation": label(caste, woman == "1") if stated else "",
        "reservation_raw": text(r.get("reserved_raw")),
        "winner": text(r.get("winner")),
        "winner_gender": GENDER_OF.get(text(r.get("winner_woman")), ""),
        "winner_gender_raw": text(r.get("winner_woman_raw")),
        "winner_category_raw": text(r.get("winner_community_raw")),
        "winner_basis": ward_basis(r, members),
        "party": text(r.get("party")),
        "votes": text(r.get("votes")),
        "unopposed": text(r.get("unopposed")),
        "seat_candidates": text(r.get("seat_candidates")),
        "electors": text(r.get("electors")),
        "valid_votes": text(r.get("valid_votes")),
        "shared_place_name": (
            "1" if "gp_name_repeated" in text(r.get("quality_flags")) else "0"
        ),
        "source_path": text(r.get("source_path")),
        "source_page": text(r.get("source_page")),
        "source_locator": ward_locator(r),
        "seat_members": members,
    }


def ward_slices(root, names, year):
    results = read(root, WARD_RESULTS.format(year=year))
    if results is None:
        return
    grouped = {}
    for c in read(root, WARD_CANDIDATES.format(year=year)) or []:
        grouped.setdefault(tuple(c[k] for k in WARD_KEY), []).append(member(c))
    by_tier = {}
    for r in results:
        key = tuple(r[k] for k in WARD_KEY)
        members = grouped.pop(key, [])
        if members and "gp_name_repeated" in text(r.get("quality_flags")):
            raise SystemExit(f"{REPO}: {year} candidates for a repeated ward {key}")
        by_tier.setdefault(WARD_TIER[r["tier"]], []).append(
            ward_seat(r, names, members)
        )
    if grouped:
        raise SystemExit(
            f"{REPO}: {year} has candidates for {len(grouped)} unknown wards"
        )
    for tier, seats in by_tier.items():
        yield {
            "dataset_id": f"tamil_nadu/{tier}/{year}",
            "state": STATE,
            "rows": seats,
            "provenance_level": "page",
            "unit_of_observation": "seat",
        }


def slices(root):
    root = pathlib.Path(root)
    names = district_names(root)
    for year in YEARS:
        results = read(root, RESULTS.format(year=year))
        if results is None:
            continue
        grouped = {}
        for c in read(root, CANDIDATES.format(year=year)) or []:
            grouped.setdefault(tuple(c[k] for k in KEY), []).append(member(c))
        seats = []
        for r in results:
            key = tuple(r[k] for k in KEY)
            seats.append(seat(r, names, grouped.pop(key, [])))
        if grouped:
            raise SystemExit(
                f"{REPO}: {year} has candidates for {len(grouped)} unknown seats"
            )
        yield {
            "dataset_id": f"tamil_nadu/gp_head/{year}",
            "state": STATE,
            "rows": seats,
            "provenance_level": "page",
            "unit_of_observation": "seat",
        }
    for year in YEARS:
        yield from ward_slices(root, names, year)


def links(root):
    """The sibling's president seat links, keyed by both seats' locators."""
    root = pathlib.Path(root)
    for (a, b), relative in LINKS.items():
        path = root / relative
        if not path.exists():
            continue
        for r in pq.read_table(path).to_pylist():
            yield {
                "from_dataset_id": f"tamil_nadu/gp_head/{a}",
                "from_locator": locator(
                    r[f"district_code_{a}"], r[f"block_{a}"], r[f"gram_panchayat_{a}"]
                ),
                "to_dataset_id": f"tamil_nadu/gp_head/{b}",
                "to_locator": locator(
                    r[f"district_code_{b}"], r[f"block_{b}"], r[f"gram_panchayat_{b}"]
                ),
                "link_pass": r.get("link_rule") or "name",
                "name_score": r["name_score"],
                "source_path": relative,
            }
