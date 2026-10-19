"""Tamil Nadu, from local_elections_tamil_nadu.

Village panchayat presidents in three ordinary elections: 2011 (all 31 rural
districts), 2019 (27 districts) and 2021 (the 9 districts carved out after
2011, plus 105 by-election seats elsewhere). The sibling has already put each
election into seat rows, one per president seat, with the reservation, the
winner and the winner's sex as printed on the result sheet, and a separate
candidate table. So nothing is collapsed here: seats are read as seats and
each seat's candidates are attached to it.

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

# Rows the sibling's committed files hold; a change stops the build.
DECLARED = {
    "data/2011/vp_president_results.parquet": 12523,
    "data/2019/vp_president_results.parquet": 9624,
    "data/2021/vp_president_results.parquet": 3005,
    "data/2011/vp_president_candidates.parquet": 51032,
    "data/2019/vp_president_candidates.parquet": 35992,
    "data/2021/vp_president_candidates.parquet": 11208,
}

# A seat is identified by district, union and panchayat within an election;
# the sibling checks this is unique in every year.
KEY = ("election_type", "district_code", "block", "gram_panchayat")

# The sibling's seat links between elections, keyed by each side's locator.
LINKS = {
    ("2011", "2019"): "data/linkage/vp_2011_2019.parquet",
    ("2011", "2021"): "data/linkage/vp_2011_2021.parquet",
}


def locator(district_code, block, panchayat):
    return "/".join((district_code, block, panchayat))


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
    gender = text(c.get("candidate_gender"))
    return {
        "candidate_no": text(c.get("candidate_no")),
        "candidate_name": text(c.get("candidate_name")),
        "relation_name": text(c.get("relation_name")),
        "candidate_gender": gender,
        "candidate_woman": {"female": "1", "male": "0"}.get(gender, ""),
        "votes": text(c.get("votes")),
        "result": text(c.get("result")),
        "elected": text(c.get("elected")),
    }


def seat(r, names, members):
    caste = text(r.get("caste_reservation"))
    woman = text(r.get("woman_reserved"))
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
        "caste_reservation_local": text(r.get("caste_reservation_local")),
        "woman_reserved": woman,
        # a blank bracket on the sheet states no reservation; left unknown
        "gender_stated": "1" if stated else "0",
        "reservation": label(caste, woman == "1") if stated else "",
        "reservation_raw": text(r.get("reservation_raw")),
        "winner": text(r.get("winner")),
        "winner_gender": text(r.get("winner_gender")),
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
