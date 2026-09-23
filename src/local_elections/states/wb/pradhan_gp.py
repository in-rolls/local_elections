"""Pradhan-office reservation for every GP in a district, from Form 1B orders.

    uv run python -m local_elections.states.wb.pradhan_gp

A Form 1B order (Rule 2A, WB Panchayat (Constitution) Rules 1975) names the
Pradhan offices reserved for SC, ST or BC in column 4 and those reserved for
women in column 5. An office it does not name is reserved on neither axis. So a
district's full list is the named offices plus the rest of its GPs, and "the
rest" needs the district's GP list for the same term: the MNREGA R3 list
(tools/wb_mnrega_gp_lists.py), whose count equals the order's printed total (column 2)
in every district filled here. Malda 2013 prints all of its GPs, so nothing is
inferred there.

Each name in an order is matched to one MNREGA GP, within its block where the
order gives one, and the I/II/III numeral must agree. Hand decisions live in
data/wb/reference/pradhan_match_overrides.csv, each with its reason. The build
fails unless every named office resolves to a distinct GP and the parsed counts
of offices, SC, ST, BC and women equal the totals printed in the order - a
misread category or a dropped row changes a count. A swap of two GPs within a
block does not, which is why every match is also labelled by how the printed
name compares with the matched one (`match`), so the doubtful ones can be read.

Inputs are the repository's own parses: office_native (text-layer PDFs),
alipurduar_offices (visual transcription) and pradhan_scans (OCR of two scans).
"""

import argparse
import difflib
import json
import os
import re
import sys

import pandas as pd

from local_elections.common.runlog import command
from local_elections.paths import ROOT

WB = ROOT / "data" / "wb"
OUT = WB / "derived" / "pradhan_gp"
GP_LISTS = WB / "reference" / "mnrega_gp_lists.csv"
OVERRIDES = WB / "reference" / "pradhan_match_overrides.csv"

ORDERS = {
    ("South 24 Parganas", 2018): {
        "order": "No. 6/P&RD/PGE/2018, dated 06/03/2018",
        "mnrega_district": "24 PARGANAS SOUTH",
        "source": "office_native",
        "printed": {"offices": 310, "SC": 105, "ST": 4, "BC": 46, "women": 155},
    },
    ("Purulia", 2018): {
        "order": "No. 95(170)/Panch' Elec./Prl', dated 06/03/2018 (one file per block)",
        "mnrega_district": "PURULIA",
        "source": "office_native",
        "printed": {"offices": 170, "SC": 31, "ST": 34, "BC": 20, "women": 85},
    },
    ("Alipurduar", 2018): {
        "order": "Form 1B, Offices of the Pradhan, signed 06/03/2018",
        "mnrega_district": "ALIPURDUAR",
        "source": "alipurduar_offices",
        "printed": {"offices": 66, "SC": 18, "ST": 15, "BC": 0, "women": 33},
    },
    ("Nadia", 2018): {
        "order": "No. 95/PGE'18, dated 06.03.2018",
        "mnrega_district": "NADIA",
        "source": "scan",
        "printed": {"offices": 185, "SC": 59, "ST": 5, "BC": 28, "women": 92},
    },
    ("Nadia", 2013): {
        "order": "Memo No. 404/P&RD, dated 15.03.2013; codes from the handbook",
        "mnrega_district": "NADIA",
        "source": "handbook",
        "printed": {"offices": 187, "SC": 60, "ST": 5, "BC": 28, "women": 93},
    },
    ("Malda", 2013): {
        "order": "No. 334/P/PGE'13, dated 15/03/2013",
        "mnrega_district": "MALDAH",
        "source": "scan",
        "printed": {"offices": 146, "SC": 35, "ST": 9, "BC": 29, "women": 73},
    },
}

# Handbook rows whose printed code is blank, and what the order settles them to.
# Taldaha Majdia (serial 123): the other 186 codes already exhaust the order's
# printed totals on both axes (SC 60, ST 5, BC 28, women 93), and the name is
# absent from the order's Pradhan pages, so the office is unreserved.
BLANK_CODES = {("Nadia", 2013, 123): (None, False)}

# What an empty cell OCRs as: a printed dash, or specks.
DASH = {"", "-", "“", "”", ".", ":", "'", ",", "—", "_", "~"}
STROKES = r"Il1!|\]\[\{\}ti"


# --- names -----------------------------------------------------------------


def split_suffix(raw):
    """(name, numeral) from a printed GP name.

    The numeral is counted in strokes, because OCR renders II as "ll", "Il",
    "!!", "H" or "l]": what survives is how many vertical strokes follow the
    hyphen.
    """
    text = re.sub(r"\((SC|ST|BC|OBC)\)?", "", str(raw), flags=re.I).strip()
    match = re.search(rf"(?:[-–]\s*|\s+)([{STROKES}H]{{1,3}}|III|II|I)\s*$", text)
    if not match:
        return text, ""
    glyphs = match.group(1)
    strokes = len(re.sub(rf"[^{STROKES}]", "", glyphs)) + 2 * glyphs.count("H")
    return text[: match.start()].strip(), str(min(max(strokes, 1), 3))


def stem(text):
    """A matching key that ignores the usual romanisations of Bengali."""
    text = text.lower()
    for old, new in [
        ("sh", "s"),
        ("oo", "u"),
        ("ou", "u"),
        ("w", "b"),
        ("v", "b"),
        ("j", "g"),
        ("z", "g"),
        ("y", "i"),
        ("o", "a"),
        ("e", "a"),
        ("ck", "k"),
        ("kh", "k"),
        ("th", "t"),
        ("dh", "d"),
        ("bh", "b"),
        ("ch", "c"),
        ("ph", "f"),
        ("h", ""),
    ]:
        text = text.replace(old, new)
    return re.sub(r"[^a-z]", "", text)


def canon(name):
    text = re.sub(r"\s*-\s*(III|II|I)$", lambda m: "-" + m.group(1), str(name).strip())
    base, numeral = split_suffix(text)
    return stem(base), numeral


def prepare(gps):
    keys = gps.gram_panchayat.map(canon)
    blocks = gps.block.map(canon)
    return gps.assign(
        key=keys.str[0], num=keys.str[1], bkey=blocks.str[0] + blocks.str[1]
    )


def match(raw, pool):
    """(index, how, numeral) of the one GP in `pool` a printed name can be."""
    base, numeral = split_suffix(raw)
    key = stem(base)
    if not key:
        return None, "empty", numeral
    candidates = pool[pool.num == numeral] if numeral else pool
    exact = candidates[candidates.key == key]
    if len(exact) == 1:
        return exact.index[0], "exact", numeral
    if len(exact) > 1 and not numeral and (exact.num == "").sum() == 1:
        # SHALKUMAR beside SHALKUMAR-I and -II is the one without a numeral
        return exact[exact.num == ""].index[0], "exact", numeral
    if len(exact) > 1:
        return None, "ambiguous", numeral
    close = difflib.get_close_matches(
        key, candidates.key.unique().tolist(), n=2, cutoff=0.75
    )
    if close:
        found = candidates[candidates.key == close[0]]
        margin = len(close) == 1 or (
            difflib.SequenceMatcher(None, key, close[0]).ratio()
            - difflib.SequenceMatcher(None, key, close[1]).ratio()
            > 0.08
        )
        if len(found) == 1 and margin:
            return found.index[0], "fuzzy", numeral
    return None, "unmatched", numeral


# --- how a printed name compares with the GP it was matched to --------------

TAG = r"\((SC|ST|BC)?W?\)|\((ST|SC|BC)\s*W\)|\((Ch|Kck|Kek)[^)]*\)"


def _parts(text):
    text = re.sub(TAG, "", text, flags=re.I).strip().replace("“", "").strip()
    text = re.sub(r"^U\s+", "UTTAR ", text)
    base, numeral = split_suffix(text)
    clean = not numeral or bool(re.search(r"[-\s](III|II|I)$", text))
    return base, numeral, clean


def _skeleton(text):
    text = text.lower().replace("x", "ks")
    for old, new in [
        ("sh", "s"),
        ("ch", "c"),
        ("ck", "k"),
        ("kh", "k"),
        ("gh", "g"),
        ("th", "t"),
        ("dh", "d"),
        ("bh", "b"),
        ("ph", "f"),
        ("z", "j"),
        ("v", "b"),
        ("q", "k"),
        ("y", "j"),
    ]:
        text = text.replace(old, new)
    text = re.sub(r"ge\b", "j", text)
    text = re.sub(r"[^a-z]", "", text)
    text = text[:1] + re.sub(r"[aeiouhwj]", "", text[1:]) if text else text
    return re.sub(r"(.)\1+", r"\1", text)


def label(printed, gram_panchayat):
    """exact, transliteration, scan_misread or fuzzy, from the two names alone.

    exact ignores case, punctuation and spacing; transliteration differs only
    in how Bengali is romanised; scan_misread is an OCR glyph error in the
    numeral. The label never depends on which step of `match` found the pair.
    """
    target, target_numeral, _ = _parts(gram_panchayat)
    rank = {"exact": 0, "transliteration": 1, "scan_misread": 2}
    best = None
    for part in [p for p in str(printed).split(" | ") if p]:
        base, numeral, clean = _parts(part)
        if numeral != target_numeral:
            continue
        if re.sub(r"[^a-z]", "", base.lower()) == re.sub(r"[^a-z]", "", target.lower()):
            found = "exact"
        elif _skeleton(base) == _skeleton(target):
            found = "transliteration"
        else:
            continue
        found = found if clean else "scan_misread"
        if best is None or rank[found] < rank[best]:
            best = found
    return best or "fuzzy"


# --- named offices, one entry per printed row --------------------------------


def _entry(district, term, file, page, row, block, readings, caste, women):
    return {
        "district": district,
        "term": term,
        "source_file": file,
        "source_page": int(page),
        "source_row": int(row),
        "block_printed": block,
        "readings": [r for r in readings if r],
        "caste": caste,
        "women": bool(women),
    }


def native_entries(district, term):
    cells = pd.read_csv(WB / "derived" / "office_native" / "cell_review.csv")
    cells = cells[
        (cells.district == district)
        & (cells.election_year == term)
        & (cells.tier == "gp_head")
        & (cells.stage == "final")
        & (cells.record_kind == "positive_office_reservation_mention")
    ]
    entries = []
    for (path, page, row), group in cells.groupby(
        ["source_path", "source_page", "table_row"], sort=True
    ):
        categories = set(group.category)
        caste = next((c for c in ("SC", "ST", "BC") if c in categories), None)
        entries.append(
            _entry(
                district,
                term,
                os.path.basename(path),
                page,
                row,
                group.block.iloc[0],
                list(dict.fromkeys(group.gram_panchayat_reading)),
                caste,
                "women" in categories,
            )
        )
    return entries


def alipurduar_entries(district, term):
    rows = pd.read_csv(
        WB / "derived" / "alipurduar_offices" / "office_reservations.csv"
    )
    rows = rows[(rows.tier == "gp_head") & (rows.year == term)].reset_index(drop=True)
    return [
        _entry(
            district,
            term,
            os.path.basename(r.source_path),
            r.source_page,
            number,
            None,
            [r.gram_panchayat],
            r.caste_reservation if isinstance(r.caste_reservation, str) else None,
            r.woman_reserved == 1,
        )
        for number, r in enumerate(rows.itertuples(), 1)
    ]


def handbook_entries(district, term):
    """The 2013 handbook prints every GP with its code; no inference is needed."""
    rows = pd.read_csv(
        WB / "derived" / "nadia_2013_handbook" / "office_reservations.csv"
    )
    rows = rows[(rows.tier == "gp_head") & (rows.year == term)]
    entries = []
    for r in rows.itertuples():
        code = r.reservation if isinstance(r.reservation, str) else ""
        if code:
            if code not in {"UR", "W", "SC", "SCW", "ST", "STW", "OBC", "OBCW"}:
                raise ValueError(f"unexpected handbook code {code!r}")
            caste = {"SC": "SC", "ST": "ST", "OBC": "BC"}.get(code.removesuffix("W"))
            women = code.endswith("W")
        elif (district, term, r.source_gp_serial) in BLANK_CODES:
            caste, women = BLANK_CODES[(district, term, r.source_gp_serial)]
        else:
            raise ValueError(f"blank handbook code, serial {r.source_gp_serial}")
        entries.append(
            _entry(
                district,
                term,
                os.path.basename(r.source_path),
                r.source_page,
                r.source_gp_serial,
                None,
                [r.gram_panchayat],
                caste,
                women,
            )
        )
    return entries


def scan_entries(district, term, gps):
    cells = pd.read_csv(OUT / "scan_cells.csv", dtype=str, keep_default_na=False)
    cells = cells[(cells.district == district) & (cells.term == str(term))]
    table = cells.pivot_table(
        index=["source_file", "page", "row"],
        columns="column",
        values="reading",
        aggfunc="first",
    ).reset_index()
    table["page"], table["row"] = table.page.astype(int), table.row.astype(int)
    table = table.sort_values(["page", "row"]).fillna("")
    return (
        _malda_rows(district, term, table)
        if "all" in table
        else _nadia_rows(district, term, table, gps)
    )


def _malda_rows(district, term, table):
    """Every GP printed in its own column; codes read SC/ST/BC and (..W)."""
    entries = []
    for r in table.itertuples():
        if not re.search(r"[A-Z]{3}", r.all) or "anchayat" in r.all.lower():
            continue  # the column-number header row

        def code(text):
            found = re.search(r"\(\s*([A-Z]{1,4})\s*[\):;]?", text.upper())
            return found.group(1) if found else ""

        caste_code, women_code = code(r.caste), code(r.women)
        caste = next((c for c in ("SC", "ST", "BC") if caste_code.startswith(c)), None)
        # women's cells print (W), (SCW), (BCW)...; one (W) scanned as (VY)
        women = "W" in women_code or women_code in {"VY", "VW"}
        readings = [r.all] + [x for x, k in ((r.caste, caste), (r.women, women)) if k]
        entries.append(
            _entry(
                district,
                term,
                r.source_file,
                r.page,
                r.row,
                None,
                readings,
                caste,
                women,
            )
        )
    return entries


def _nadia_rows(district, term, table, gps):
    """Block headings span both named columns; GP rows follow their heading."""
    blocks = gps.bkey.unique().tolist()
    entries, block = [], None
    for r in table.itertuples():
        caste_text, women_text = r.caste.strip(), r.women.strip()
        span = f"{caste_text} {women_text}".strip()
        if not span or span.startswith("(4)"):
            continue
        name = re.sub(
            r"[\]\[|]", "", re.sub(r"\s*(B|3)?\s*[l|]?\s*ock\s*$", "", span, flags=re.I)
        ).strip()
        base, numeral = split_suffix(name)
        heading = difflib.get_close_matches(
            stem(base) + numeral, blocks, n=1, cutoff=0.8
        )
        spans_both = caste_text not in DASH and women_text not in DASH
        if (
            spans_both
            and not re.search(r"\((SC|ST|BC)", span)
            and (re.search(r"ock\s*$", span, re.I) or heading)
        ):
            # "Nakaship | ara" and "Karimpur-II | Block": a GP of the same name
            # as its block (Karimpur-II) has a dash in one column instead
            block = heading[0] if heading else None
            continue
        found = (
            re.search(r"\((SC|ST|BC)", caste_text) if caste_text not in DASH else None
        )
        readings = [x for x in (caste_text, women_text) if x not in DASH]
        entries.append(
            _entry(
                district,
                term,
                r.source_file,
                r.page,
                r.row,
                block,
                readings,
                found.group(1) if found else None,
                women_text not in DASH,
            )
        )
    return entries


# --- resolution ---------------------------------------------------------------


def resolve(entries, gps, overrides):
    blocks = gps.bkey.unique().tolist()
    resolved, failures = [], []
    for e in entries:
        key = (e["source_file"], e["source_page"], e["source_row"])
        if key in overrides:
            o = overrides[key]
            hit = gps[(gps.gram_panchayat == o.gram_panchayat) & (gps.block == o.block)]
            if len(hit) != 1:
                raise ValueError(f"override names no single GP: {key}")
            resolved.append({**e, "gp_index": hit.index[0], "assigned_by": "override"})
            continue
        block = e["block_printed"]
        if block and block not in blocks:
            name, numeral = canon(block)
            close = difflib.get_close_matches(name + numeral, blocks, n=1, cutoff=0.7)
            block = close[0] if close else None
        hits = []
        for reading in e["readings"]:
            index, numeral = None, ""
            if block:
                index, _, numeral = match(reading, gps[gps.bkey == block])
            if index is None:
                index, _, numeral = match(reading, gps)
            hits.append((index, numeral))
        found = {i for i, _ in hits if i is not None}
        if len(found) > 1:
            # a reading that lost its numeral defers to one that kept it
            numbered = {i for i, n in hits if i is not None and n}
            found = numbered if len(numbered) == 1 else found
        if len(found) != 1:
            failures.append(f"{key} {e['readings']} ({len(found)} candidates)")
            continue
        resolved.append({**e, "gp_index": found.pop(), "assigned_by": "matcher"})
    if failures:
        raise ValueError("unresolved or conflicting:\n  " + "\n  ".join(failures))
    return resolved


def build_order(district, term, gp_lists, overrides):
    spec = ORDERS[(district, term)]
    gps = prepare(
        gp_lists[
            (gp_lists.mnrega_file_year == term)
            & (gp_lists.district == spec["mnrega_district"])
        ].reset_index(drop=True)
    )
    if spec["source"] == "office_native":
        entries = native_entries(district, term)
    elif spec["source"] == "alipurduar_offices":
        entries = alipurduar_entries(district, term)
    elif spec["source"] == "handbook":
        entries = handbook_entries(district, term)
    else:
        entries = scan_entries(district, term, gps)
    resolved = resolve(entries, gps, overrides)
    taken = [r["gp_index"] for r in resolved]
    if len(taken) != len(set(taken)):
        raise ValueError(f"{district} {term}: two named offices matched one GP")
    named = {r["gp_index"]: r for r in resolved}
    rows = []
    for index, gp in gps.iterrows():
        r = named.get(index)
        printed = " | ".join(r["readings"]) if r else ""
        rows.append(
            {
                "state": "West Bengal",
                "district": district,
                "term": term,
                "block": gp.block,
                "gram_panchayat": gp.gram_panchayat,
                "named_in_order": r is not None,
                "caste_reservation": (r["caste"] if r else None) or "UR",
                "woman_reserved": bool(r and r["women"]),
                "printed": printed,
                "match": label(printed, gp.gram_panchayat) if r else "not_named",
                "assigned_by": r["assigned_by"] if r else "",
                "order": spec["order"],
                "source_file": r["source_file"] if r else "",
                "source_page": r["source_page"] if r else None,
                "source_row": r["source_row"] if r else None,
                "gp_list": gp.source,
            }
        )
    return pd.DataFrame(rows)


def checks(table):
    """Parsed counts beside the printed ones, per order."""
    out = []
    for (district, term), group in table.groupby(["district", "term"], sort=False):
        printed = ORDERS[(district, term)]["printed"]
        parsed = {
            "offices": len(group),
            "SC": int((group.caste_reservation == "SC").sum()),
            "ST": int((group.caste_reservation == "ST").sum()),
            "BC": int((group.caste_reservation == "BC").sum()),
            "women": int(group.woman_reserved.sum()),
        }
        out.append(
            {
                "district": district,
                "term": term,
                "printed": printed,
                "parsed": parsed,
                "named_in_order": int(group.named_in_order.sum()),
                "agrees": parsed == printed,
            }
        )
    return out


def build():
    gp_lists = pd.read_csv(GP_LISTS)
    overrides = {
        (o.source_file, int(o.source_page), int(o.source_row)): o
        for o in pd.read_csv(OVERRIDES).itertuples()
    }
    table = pd.concat(
        [build_order(d, t, gp_lists, overrides) for d, t in ORDERS], ignore_index=True
    )
    used = set(
        zip(
            table.source_file,
            table.source_page.fillna(-1).astype(int),
            table.source_row.fillna(-1).astype(int),
            strict=True,
        )
    )
    unused = [k for k in overrides if k not in used]
    if unused:
        raise ValueError(f"overrides that matched no printed row: {unused}")
    return table, checks(table)


@command("parse", source="wb_pradhan_gp")
def main():
    argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0]).parse_args()
    table, report = build()
    OUT.mkdir(parents=True, exist_ok=True)
    table.to_csv(OUT / "pradhan_gp.csv", index=False, lineterminator="\n")
    table.to_parquet(OUT / "pradhan_gp.parquet", index=False)
    (OUT / "checks.json").write_text(json.dumps(report, indent=2) + "\n")
    for c in report:
        mark = "ok" if c["agrees"] else "DIFFERS"
        print(f"  {c['district']:<18} {c['term']}  {c['parsed']}  {mark}")
    if not all(c["agrees"] for c in report):
        print("parsed counts differ from the printed totals")
        return 1
    print(f"{len(table)} GPs -> {(OUT / 'pradhan_gp.csv').relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
