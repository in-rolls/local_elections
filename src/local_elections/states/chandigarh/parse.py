"""Extract dated Chandigarh municipal records from retained official reports.

The 2006 report also covers later by-elections. Its final winner table is a
mixed-vintage list, so this parser uses the contemporaneous results and the
separately documented deferred ward-7 election. Winner sex is never inferred
from seat reservation or personal names.
"""

import argparse
import collections
import hashlib
import json
import re
import subprocess
from functools import cache
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from local_elections.common.runlog import command
from local_elections.paths import ROOT

DATA = ROOT / "data/chandigarh"
REPORTS = {year: DATA / f"raw/election-report-{year}.pdf" for year in (2006, 2011)}
GAZETTE = DATA / "raw/winner_gazette_2021.pdf"
PARTIES = {
    "Congress": "INC",
    "B.J.P": "BJP",
    "S.A.D": "SAD",
    "B.S.P": "BSP",
    "Independent": "IND",
    "INC": "INC",
    "BJP": "BJP",
    "SAD": "SAD",
    "BSP": "BSP",
    "Indian National Congress": "INC",
    "Bhartiya Janata Party": "BJP",
    "Bharatiya Janata Party": "BJP",
    "Shiromani Akalidal": "SAD",
    "Shriomani Akali Dal": "SAD",
    "Shiromani Akali Dal": "SAD",
    "Bahujan Samaj Party": "BSP",
    "Aam Aadmi Party": "AAP",
}
CATEGORIES = {
    "General": ("GEN", False),
    "Women": ("GEN", True),
    "SC": ("SC", False),
    "S.C.": ("SC", False),
    "SCW": ("SC", True),
    "Scheduled Caste": ("SC", False),
    "Scheduled Caste (Women)": ("SC", True),
    "Scheduled Caste (Women )": ("SC", True),
    "Scheduled Caste (Women": ("SC", True),
}


def relative(path):
    return str(path.relative_to(ROOT))


@cache
def pages(path):
    output = subprocess.run(
        ["pdftotext", "-layout", str(path), "-"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    return output.split("\f")


def name_key(value):
    return re.sub(r"[^a-z0-9]", "", value.lower())


def unique_wards(rows, expected):
    wards = [r["ward_no"] for r in rows]
    if len(wards) != len(set(wards)) or set(wards) != set(expected):
        raise ValueError(f"Unexpected ward coverage: {wards}")


def category(raw):
    if raw not in CATEGORIES:
        raise ValueError(f"Unrecognized reservation: {raw!r}")
    caste, woman = CATEGORIES[raw]
    return {"reservation_raw": raw, "caste_reservation": caste, "woman_reserved": woman}


def row_base(year, ward, path, page, raw):
    return {
        "election_year": year,
        "ward_no": ward,
        "body": "Municipal Corporation of Chandigarh",
        "poll_date": {2006: "2006-12-20", 2011: "2011-12-17", 2021: "2021-12-24"}[year],
        "source_path": relative(path),
        "source_page": page,
        "source_raw": raw,
        "winner_sex": None,
        "winner_sex_basis": "not_recorded_in_selected_source",
        "sex_source_path": None,
        "sex_source_page": None,
        "winner_votes": None,
        "total_votes": None,
        "votes_source_path": None,
        "votes_source_page": None,
        "quality_flags": [],
    }


def summaries(year):
    page = {2006: 112, 2011: 118}[year]
    pattern = re.compile(
        r"^\s*(\d+)\.?\s+(Women|General|SCW|SC)\s+(\d+)\s{2,}"
        r"(.+?)\s{2,}(Congress|B\.J\.P|S\.A\.D|B\.S\.P|INC|BJP|SAD|BSP|"
        r"Independent)\s+(\d+)\s{2,}(.+?)\s{2,}(.+?)\s+(\d+)\s+(\d+)\s*$"
    )
    rows = {}
    for line in pages(REPORTS[year])[page - 1].splitlines():
        match = pattern.match(line)
        if not match:
            continue
        ward = int(match[1])
        if ward in rows or int(match[6]) - int(match[9]) != int(match[10]):
            raise ValueError(f"Invalid result summary: {line}")
        rows[ward] = {
            "ward_no": ward,
            "reservation_raw": match[2],
            "total_votes": int(match[3]),
            "winner_name_raw": match[4],
            "party": PARTIES[match[5]],
            "winner_votes": int(match[6]),
            "votes_source_page": page,
        }
    expected = set(range(1, 27)) - ({7} if year == 2006 else set())
    if set(rows) != expected:
        raise ValueError(f"Incomplete {year} result summary: {sorted(rows)}")
    return rows


def winner_table(year):
    page = {2006: 114, 2011: 120}[year]
    body = pages(REPORTS[year])[page - 1]
    if "NAMES OF WINNING CANDIDATES" not in body:
        raise ValueError("Winner table heading missing")
    pattern = re.compile(r"^\s*(\d+)\.?\s*(.+?)\s{2,}(.+?)\s{2,}(.+)$")
    rows = []
    votes = summaries(year)
    aliases = {(2006, 3): ("Pradeep Chhabra", "Pradeep Chabra")}
    for line in body.splitlines():
        match = pattern.match(line)
        if not match:
            continue
        ward = int(match[1])
        row = row_base(year, ward, REPORTS[year], page, line)
        row.update(category(match[2].strip()))
        row.update(winner_name=match[3].strip(), party=PARTIES[match[4].strip()])
        summary = votes[ward]
        if (
            category(summary["reservation_raw"])["woman_reserved"]
            != row["woman_reserved"]
        ):
            raise ValueError("Summary and winner reservations disagree")
        if summary["party"] != row["party"]:
            raise ValueError("Summary and winner parties disagree")
        names = (row["winner_name"], summary["winner_name_raw"])
        if name_key(names[0]) != name_key(names[1]):
            if aliases.get((year, ward)) != names:
                raise ValueError(f"Unreviewed winner spelling: {names}")
            row["quality_flags"].append("winner_spelling_differs_across_report_tables")
        row.update(
            winner_votes=summary["winner_votes"],
            total_votes=summary["total_votes"],
            votes_source_path=relative(REPORTS[year]),
            votes_source_page=summary["votes_source_page"],
        )
        if year == 2011:
            row["quality_flags"].append("winner_table_heading_misprints_year_2006")
        rows.append(row)
    unique_wards(rows, set(range(1, 27)) - ({7} if year == 2006 else set()))
    return rows


def deferred_winner():
    report = pages(REPORTS[2006])
    detailed, notification = report[155], report[156]
    if "14.01.2007" not in detailed or "held on 14th January, 2007" not in notification:
        raise ValueError("Deferred-election date evidence missing")
    match = re.search(
        r"^\s*07\s+\d+\s+\d+\s+(\d+)\s+--\s+--\s+(.+?)\s{2,}"
        r"(Indian National Congress)\s+(\d+)\s+",
        detailed,
        re.M,
    )
    notice = re.search(r"^\s*7\s+(S\.C\.)\s+Sh\.\s+(.+?),\s+", notification, re.M)
    if not match or not notice or name_key(match[2]) != name_key(notice[2]):
        raise ValueError("Deferred winner notification and result disagree")
    row = row_base(2006, 7, REPORTS[2006], 157, notice[0].strip())
    row.update(category(notice[1]))
    row.update(
        winner_name=match[2],
        party="INC",
        poll_date="2007-01-14",
        winner_votes=int(match[4]),
        total_votes=int(match[1]),
        winner_sex="Male",
        winner_sex_basis="printed_honorific",
        sex_source_path=relative(REPORTS[2006]),
        sex_source_page=157,
        votes_source_path=relative(REPORTS[2006]),
        votes_source_page=156,
        quality_flags=[
            "deferred_general_election",
            "notification_heading_predates_poll_in_error",
        ],
    )
    return row


def candidates_2011():
    rows, controls = [], []
    ward = None
    for page in range(100, 105):
        body = pages(REPORTS[2011])[page - 1]
        header = next(
            line for line in body.splitlines() if "Name of the Candidate" in line
        )
        start, end = header.index("Name of the Candidate"), header.index("Party")
        for line in body.splitlines():
            match = re.match(r"^\s*(\d+)\s+(\d+)\s+(Smt\.|Sh\.|Ms\.|Dr\.)", line)
            if match:
                ward = int(match[1])
                counts = re.search(r"\s+(\d+)\s+(\d+)\s*$", line)
                if not counts:
                    raise ValueError("Missing candidate-sex control totals")
                controls.append(
                    {
                        "election_year": 2011,
                        "ward_no": ward,
                        "total_candidates": int(match[2]),
                        "male_candidates": int(counts[1]),
                        "female_candidates": int(counts[2]),
                        "source_path": relative(REPORTS[2011]),
                        "source_page": page,
                    }
                )
            raw = line[start:end].strip()
            title = re.match(r"^(Smt\.|Sh\.|Ms\.|Dr\.)\s*(.+)$", raw)
            if not title:
                if (
                    rows
                    and rows[-1]["ward_no"] == ward
                    and re.fullmatch(r"[A-Za-z]+\)", raw)
                ):
                    rows[-1]["candidate_name_raw"] += " " + raw
                continue
            if ward is None:
                raise ValueError("Candidate without ward context")
            sex = {"Smt.": "Female", "Ms.": "Female", "Sh.": "Male"}.get(title[1])
            name = re.split(r"\s*\(", title[2])[0].rstrip(" ,")
            rows.append(
                {
                    "election_year": 2011,
                    "ward_no": ward,
                    "candidate_order": 1 + sum(r["ward_no"] == ward for r in rows),
                    "candidate_name": name,
                    "candidate_name_raw": raw,
                    "honorific_raw": title[1],
                    "candidate_sex": sex,
                    "sex_basis": "printed_honorific"
                    if sex
                    else "title_not_sex_specific",
                    "source_path": relative(REPORTS[2011]),
                    "source_page": page,
                }
            )
    unique_wards(controls, range(1, 27))
    if len(rows) != 152:
        raise ValueError(f"Expected 152 candidates, extracted {len(rows)}")
    for control in controls:
        subset = [r for r in rows if r["ward_no"] == control["ward_no"]]
        observed = collections.Counter(r["candidate_sex"] for r in subset)
        if len(subset) != control["total_candidates"]:
            raise ValueError("Candidate count disagrees with printed ward total")
        if control["male_candidates"] + control["female_candidates"] != len(subset):
            raise ValueError("Male/female counts do not sum to printed candidate total")
        if (
            observed["Male"] > control["male_candidates"]
            or observed["Female"] > control["female_candidates"]
        ):
            raise ValueError("Printed titles contradict aggregate gender counts")
        if not observed[None] and (
            observed["Male"] != control["male_candidates"]
            or observed["Female"] != control["female_candidates"]
        ):
            raise ValueError("Title classifications disagree with gender counts")
    if (
        sum(r["male_candidates"] for r in controls) != 102
        or sum(r["female_candidates"] for r in controls) != 50
    ):
        raise ValueError("Candidate counts disagree with report grand total")
    return rows, controls


def attach_sex(winners, candidates):
    aliases = {22: ("Davesh Modgil", "Davesh Moudgil")}
    for row in winners:
        expected = aliases.get(row["ward_no"], (row["winner_name"], row["winner_name"]))
        if expected[0] != row["winner_name"]:
            raise ValueError("Reviewed name alias no longer matches")
        matches = [
            c
            for c in candidates
            if c["ward_no"] == row["ward_no"]
            and name_key(c["candidate_name"]) == name_key(expected[1])
        ]
        if len(matches) != 1 or matches[0]["candidate_sex"] is None:
            raise ValueError(f"Winner lacks unique sex-source match: {row['ward_no']}")
        c = matches[0]
        row.update(
            winner_sex=c["candidate_sex"],
            winner_sex_basis=c["sex_basis"],
            sex_source_path=c["source_path"],
            sex_source_page=c["source_page"],
        )
        if expected[0] != expected[1]:
            row["quality_flags"].append("winner_candidate_spelling_alias")
    return winners


def winners_2021():
    rows, pending = [], None
    pattern = re.compile(
        r"^\s*(?:(\d+)\.\s+)?(Scheduled Caste \(Women\)|"
        r"Scheduled Caste|General|Women)\s{2,}(.+?)\s{2,}(.+?)\s*$"
    )
    for page, body in enumerate(pages(GAZETTE)[:4], 1):
        for line in body.splitlines():
            only_number = re.fullmatch(r"\s*(\d+)\.\s*", line)
            if only_number:
                pending = int(only_number[1])
            match = pattern.match(line)
            if not match:
                continue
            ward = int(match[1]) if match[1] else pending
            if ward is None:
                raise ValueError("Gazette row lacks ward identifier")
            pending = None
            row = row_base(2021, ward, GAZETTE, page, line)
            row.update(category(match[2]))
            row.update(winner_name=match[3].rstrip(" ,"), party=PARTIES[match[4]])
            rows.append(row)
    unique_wards(rows, range(1, 36))
    return rows


def panel_2006_2011(winners):
    from local_elections.states.chandigarh.panel import build_rows

    return build_rows(winners)


def write_table(rows, filename, integers=(), booleans=(), lists=()):
    fields = [
        pa.field(
            name,
            pa.int32()
            if name in integers
            else pa.bool_()
            if name in booleans
            else pa.list_(pa.field("element", pa.string()))
            if name in lists
            else pa.string(),
        )
        for name in rows[0]
    ]
    table = pa.Table.from_pylist(rows, schema=pa.schema(fields))
    pq.write_table(table, filename)
    if not pq.read_table(filename).equals(table):
        raise ValueError(f"Parquet round-trip mismatch: {filename}")
    return {
        "rows": len(rows),
        "columns": {f.name: str(f.type) for f in fields},
        "sha256": hashlib.sha256(filename.read_bytes()).hexdigest(),
    }


@command("process", artifact="parse")
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=DATA / "release")
    out = ap.parse_args().out
    held = json.loads((DATA / "release/manifest.json").read_text())
    for source in held["sources"]:
        path = ROOT / source["path"]
        if hashlib.sha256(path.read_bytes()).hexdigest() != source["sha256"]:
            raise ValueError(f"Source checksum changed: {path}")
    candidates, controls = candidates_2011()
    winners = [*winner_table(2006), deferred_winner()]
    winners += attach_sex(winner_table(2011), candidates)
    winners += winners_2021()
    winners.sort(key=lambda r: (r["election_year"], r["ward_no"]))
    for year, expected, women, sc in [
        (2006, 26, 9, 5),
        (2011, 26, 9, 5),
        (2021, 35, 12, 7),
    ]:
        subset = [r for r in winners if r["election_year"] == year]
        unique_wards(subset, range(1, expected + 1))
        if (
            sum(r["woman_reserved"] for r in subset) != women
            or sum(r["caste_reservation"] == "SC" for r in subset) != sc
        ):
            raise ValueError(f"Reservation totals disagree in {year}")
    out.mkdir(parents=True, exist_ok=True)
    schemas = {}
    schemas["winners.parquet"] = write_table(
        winners,
        out / "winners.parquet",
        integers=(
            "election_year",
            "ward_no",
            "source_page",
            "sex_source_page",
            "winner_votes",
            "total_votes",
            "votes_source_page",
        ),
        booleans=("woman_reserved",),
        lists=("quality_flags",),
    )
    schemas["candidates_2011.parquet"] = write_table(
        candidates,
        out / "candidates_2011.parquet",
        integers=("election_year", "ward_no", "candidate_order", "source_page"),
    )
    schemas["candidate_counts_2011.parquet"] = write_table(
        controls,
        out / "candidate_counts_2011.parquet",
        integers=(
            "election_year",
            "ward_no",
            "total_candidates",
            "male_candidates",
            "female_candidates",
            "source_page",
        ),
    )
    from local_elections.states.chandigarh import dictionary

    dictionary.write(out)
    panel = panel_2006_2011(winners)
    from local_elections.states.chandigarh import panel as panel_module

    schemas["ward_panel_2006_2011.parquet"] = panel_module.write(panel, out)
    sources = [
        {
            "path": relative(p),
            "sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
            "bytes": p.stat().st_size,
        }
        for p in [*REPORTS.values(), GAZETTE]
    ]
    (out / "manifest.json").write_text(
        json.dumps(
            {
                "files": schemas,
                "sources": sources,
                "metadata": {
                    name: hashlib.sha256((out / name).read_bytes()).hexdigest()
                    for name in (
                        "dictionary.csv",
                        "ward_panel_2006_2011.schema.json",
                        "panel_audit.json",
                    )
                },
            },
            indent=2,
        )
        + "\n"
    )
    from local_elections.states.chandigarh import extension

    extension.write(extension.build_rows(panel), out)
    print(
        json.dumps(
            {
                "winners": len(winners),
                "candidates_2011": len(candidates),
                "unknown_candidate_sex_2011": sum(
                    r["candidate_sex"] is None for r in candidates
                ),
                "linked_wards_2006_2011": len(panel),
                "later_nonquota_wards": sum(r["is_eligible"] for r in panel),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
