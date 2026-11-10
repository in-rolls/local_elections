"""Source-checked extension of the unchanged Chandigarh wards through 2016."""

import argparse
import csv
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from local_elections.common.runlog import command
from local_elections.states.chandigarh import panel, parse

DATA = parse.DATA
SOURCE = DATA / "raw/urban_expansion/election_report_2016.pdf"
REVIEW = DATA / "manual/urban_expansion/winner_honorific_review_2016.csv"
NAME = "ward_panel_2011_2016"
SOURCE_HASH = "fc760e2cfc19478a983c02809acd769d46910641099f932f62e66bf3daf3b048"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_pages():
    if digest(SOURCE) != SOURCE_HASH:
        raise ValueError("2016 source checksum changed")
    return parse.pages(SOURCE)


def reservation_rows():
    body = source_pages()[19]
    rows = {}
    for line in body.splitlines():
        match = re.match(r"^([1-3])\.\s+.+?\s+(\d+(?:\s*[, &]\s*\d+)+)\s*$", line)
        if match:
            rows[int(match[1])] = {int(x) for x in re.findall(r"\d+", match[2])}
    if {k: len(v) for k, v in rows.items()} != {1: 7, 2: 5, 3: 2}:
        raise ValueError("2016 reservation notification is incomplete")
    if rows[1] & rows[2] or not rows[3] <= rows[2]:
        raise ValueError("Reservation categories overlap")
    return {
        str(w): ("SC" if w in rows[2] else "NONE", int(w in rows[1] | rows[3]))
        for w in range(1, 27)
    }


def detailed_results():
    results, totals = [], {}
    ward = None
    for page in range(161, 169):
        for line in source_pages()[page - 1].splitlines():
            match = re.match(r"^\s*(\d+)\.?\s+(\d{3,})\s+(\d+)\s+", line)
            if match:
                ward = str(int(match[1]))
                if ward in totals:
                    raise ValueError("Repeated ward result header")
                totals[ward] = int(match[3])
            cells = re.split(r"\s{2,}", line.strip())
            if len(cells) < 3 or not cells[-1].isdigit():
                continue
            if cells[-2].lower() not in {
                *(p.lower() for p in parse.PARTIES),
                "nationalist congress party",
                "--",
            }:
                continue
            results.append(
                {
                    "ward_no": ward,
                    "candidate": cells[-3],
                    "party_raw": cells[-2],
                    "votes": int(cells[-1]),
                    "source_page": page,
                }
            )
    if len(results) != 148 or Counter(r["candidate"] == "NOTA" for r in results) != {
        False: 122,
        True: 26,
    }:
        raise ValueError("Final candidate and NOTA row counts disagree")
    if set(totals) != {str(w) for w in range(1, 27)}:
        raise ValueError("Ward returns are incomplete")
    for ward, total in totals.items():
        subset = [r for r in results if r["ward_no"] == ward]
        if (
            sum(r["votes"] for r in subset) != total
            or sum(r["candidate"] == "NOTA" for r in subset) != 1
        ):
            raise ValueError(f"Ward {ward} vote totals or NOTA disagree")
    return results


def verified_review():
    with REVIEW.open() as stream:
        reviews = list(csv.DictReader(stream))
    parse.unique_wards(reviews, {str(w) for w in range(1, 27)})
    pages = source_pages()
    for review in reviews:
        title = review["candidate_honorific_raw"]
        first = review["candidate_first_line_raw"]
        if title not in {"Sh.", "Smt."} or not first.startswith(title):
            raise ValueError("Unknown or inconsistent candidate honorific")
        page = int(review["candidate_source_page"])
        lines = pages[page - 1].splitlines()
        matches = [i for i, line in enumerate(lines) if first in line[:34]]
        if len(matches) != 1:
            raise ValueError("Honorific is not uniquely in the candidate column")
        i = matches[0]
        if "Accept" not in lines[i] and "Accep" not in lines[i]:
            raise ValueError("Winner nomination was not accepted")
        # The first column is a candidate name, not the adjacent father's title.
        name = first.removeprefix(title).strip()
        j = i + 1
        while (
            parse.name_key(name) != parse.name_key(review["candidate_name_raw"])
            and j < len(lines)
            and not re.match(r"^\s*\d+\.", lines[j])
        ):
            continuation = lines[j][lines[i].index(first) : 30].strip()
            if continuation:
                name += " " + continuation
            if not lines[j].strip():
                break
            j += 1
        if parse.name_key(name) != parse.name_key(review["candidate_name_raw"]):
            raise ValueError(f"Candidate name continuation changed: {name}")
        preceding = "\n".join([*pages[95 : page - 1], "\n".join(lines[:i])])
        wards = re.findall(r"Ward No\.\s*(\d+)", preceding)
        if not wards or str(int(wards[-1])) != review["ward_no"]:
            raise ValueError("Candidate belongs to a different ward")
        notified = pages[int(review["winner_source_page"]) - 1]
        if review["winner_notification_raw"] not in notified:
            raise ValueError("Winner notification does not match")
        if review["ward_no"] != "1" and parse.name_key(
            review["winner"]
        ) != parse.name_key(name):
            raise ValueError("Unreviewed winner/candidate name difference")
        if review["ward_no"] == "1":
            if (
                review["winner"] != "Mahesh Inder Singh"
                or name != "Maheshinder Singh Sidhu"
            ):
                raise ValueError("Reviewed ward-one name alias changed")
            if "1067" not in "\n".join(lines[i : i + 2]) or "1067" not in notified:
                raise ValueError("Ward-one alias address check failed")
    return reviews


def build_rows(prior_rows=None):
    if prior_rows is None:
        prior_rows = pq.read_table(
            DATA / "release/ward_panel_2006_2011.parquet"
        ).to_pylist()
    parse.unique_wards(prior_rows, {str(w) for w in range(1, 27)})
    panel.validate(pa.Table.from_pylist(prior_rows, schema=panel.SCHEMA))
    prior = {r["ward_no"]: r for r in prior_rows}
    for year in (2006, 2011):
        for r in prior_rows:
            if (
                digest(parse.ROOT / r[f"source_path_{year}"])
                != r[f"source_sha256_{year}"]
            ):
                raise ValueError("Prior-wave source hash changed")
    reservations = reservation_rows()
    results = detailed_results()
    rows = []
    for review in verified_review():
        ward = review["ward_no"]
        candidates = [
            r for r in results if r["ward_no"] == ward and r["candidate"] != "NOTA"
        ]
        winner = max(candidates, key=lambda r: r["votes"])
        if sum(r["votes"] == winner["votes"] for r in candidates) != 1:
            raise ValueError("Tied winning vote total")
        if winner["candidate"] != review["winner"]:
            raise ValueError("Notification winner differs from detailed returns")
        previous = prior[ward]
        caste, woman = reservations[ward]
        row = {
            "body": previous["body"],
            "ward_no": ward,
            "prior_year": 2011,
            "year": 2016,
        }
        for year in (2006, 2011):
            for concept in (
                "reserved_woman",
                "reserved_caste",
                "reserved_raw",
                "reserved_source_page",
                "source_path",
                "source_sha256",
            ):
                row[f"{concept}_{year}"] = previous[f"{concept}_{year}"]
        row.update(
            {
                "reserved_woman_2016": woman,
                "reserved_caste_2016": caste,
                "reserved_raw_2016": "Scheduled Caste (Women)"
                if caste == "SC" and woman
                else "Women"
                if woman
                else "Scheduled Caste"
                if caste == "SC"
                else "General",
                "winner_2016": winner["candidate"],
                "winner_votes_2016": winner["votes"],
                "winner_party_2016": {k.lower(): v for k, v in parse.PARTIES.items()}[
                    winner["party_raw"].lower()
                ],
                "winner_woman_2016": None,
                "winner_woman_from_honorific_2016": int(
                    review["candidate_honorific_raw"] == "Smt."
                ),
                "winner_honorific_raw_2016": review["candidate_honorific_raw"],
                "winner_candidate_name_raw_2016": review["candidate_name_raw"],
                "winner_link_basis_2016": review["winner_link_method"],
                "winner_woman_source_page_2016": int(review["candidate_source_page"]),
                "winner_source_page_2016": int(review["winner_source_page"]),
                "result_source_page_2016": winner["source_page"],
                "reserved_source_page_2016": 20,
                "boundary_source_pages_2016": "9-10",
                "assignment_rule_source_pages_2016": "9-10",
                "source_path_2016": parse.relative(SOURCE),
                "source_sha256_2016": SOURCE_HASH,
                "is_eligible": woman == 0,
                "is_eligible_without_2006_quota": woman == 0
                and previous["reserved_woman_2006"] == 0,
                "caste_transition": f"{previous['reserved_caste_2011']}_to_{caste}",
                "poll_date_2016": "2016-12-18",
                "repoll_date_2016": "2016-12-19" if ward == "7" else None,
            }
        )
        rows.append(row)
    validate(rows)
    return rows


def validate(rows):
    parse.unique_wards(rows, {str(w) for w in range(1, 27)})
    for r in rows:
        if r["winner_woman_2016"] is not None:
            raise ValueError("Recorded sex is absent; preserve null")
        for year in (2006, 2011, 2016):
            if r[f"reserved_woman_{year}"] not in (0, 1):
                raise ValueError("Unknown reservation flag")
        if r["winner_woman_from_honorific_2016"] != int(
            r["winner_honorific_raw_2016"] == "Smt."
        ):
            raise ValueError("Honorific outcome changed")
        if r["winner_honorific_raw_2016"] not in {"Sh.", "Smt."}:
            raise ValueError("Unknown honorific")
        if r["is_eligible"] != (r["reserved_woman_2016"] == 0):
            raise ValueError("Eligibility differs from later reservation")
        if r["is_eligible_without_2006_quota"] != (
            r["is_eligible"] and r["reserved_woman_2006"] == 0
        ):
            raise ValueError("Earlier-history restriction differs")
        if r["reserved_woman_2006"] and r["reserved_woman_2011"]:
            raise ValueError("2011 assignment violates rotation exclusion")
    counts = Counter((r["reserved_woman_2011"], r["reserved_woman_2016"]) for r in rows)
    if counts != {(0, 0): 11, (0, 1): 6, (1, 0): 6, (1, 1): 3}:
        raise ValueError("Reservation transitions changed")


def description(column):
    if column == "winner_woman_2016":
        return "Recorded individual sex; absent from selected source, all null."
    if column == "winner_woman_from_honorific_2016":
        return (
            "Smt.=1, Sh.=0 in a separately printed, uniquely linked candidate "
            "row; never inferred from name or quota."
        )
    if column.startswith("reserved_woman_"):
        return (
            "Women-only quota=1; open to both sexes=0, including caste-reserved seats."
        )
    if column.startswith("reserved_caste_"):
        return (
            "Seat caste reservation: SC or NONE; NONE is observed absence, not missing."
        )
    if column.startswith("reserved_raw_"):
        return "Preserved or fully expanded official seat reservation label."
    if "source_page" in column:
        return (
            "One-based PDF page(s) in the corresponding year's retained "
            "official report."
        )
    if "source_path" in column:
        return "Official report path relative to repository root."
    if "source_sha256" in column:
        return "SHA-256 of the complete retained official report."
    return {
        "body": "Municipal institution, identical to earlier panel.",
        "ward_no": "Stable ward identifier on unchanged 2006 geography; string.",
        "prior_year": "Earlier quota-assignment election, 2011.",
        "year": "Outcome election, 2016.",
        "winner_2016": "Winner name in detailed official returns.",
        "winner_votes_2016": (
            "Winner votes in detailed returns; all ward totals reconcile."
        ),
        "winner_party_2016": "Normalized party of elected candidate.",
        "winner_honorific_raw_2016": (
            "Printed candidate's title, independent of reservation."
        ),
        "winner_candidate_name_raw_2016": (
            "Printed candidate name after joining wrapped lines; title "
            "retained separately."
        ),
        "winner_link_basis_2016": (
            "Reviewed name/ward/party linkage; ward 1 address corroborates "
            "name variant."
        ),
        "is_eligible": (
            "Later seat open to both sexes; no restriction on winner sex or "
            "earlier exposure."
        ),
        "is_eligible_without_2006_quota": (
            "Later nonquota and not reserved for women in 2006; respects 2011 "
            "draw risk pool."
        ),
        "caste_transition": (
            "2011 to 2016 caste reservation stratum; rankings use different censuses."
        ),
        "poll_date_2016": (
            "Scheduled polling date; ward 7 has an additional station repoll."
        ),
        "repoll_date_2016": (
            "Repoll at polling station 14 of ward 7; null means no documented repoll."
        ),
    }[column]


def write(rows, out):
    validate(rows)
    out.mkdir(parents=True, exist_ok=True)
    fields = []
    for column in rows[0]:
        if column.startswith("reserved_woman_") or column in {
            "winner_woman_2016",
            "winner_woman_from_honorific_2016",
        }:
            dtype = pa.int8()
        elif column.startswith("is_eligible"):
            dtype = pa.bool_()
        elif isinstance(rows[0][column], int):
            dtype = pa.int32()
        else:
            dtype = pa.string()
        fields.append(
            pa.field(
                column,
                dtype,
                nullable=column in {"winner_woman_2016", "repoll_date_2016"},
            )
        )
    schema = pa.schema(fields)
    table = pa.Table.from_pylist(rows, schema=schema)
    path = out / f"{NAME}.parquet"
    pq.write_table(table, path, compression="zstd")
    if not table.equals(pq.read_table(path)):
        raise ValueError("Parquet round trip changed values")
    contract = {
        "primary_key": ["body", "ward_no", "prior_year", "year"],
        "row_unit": (
            "One outcome-election ward on unchanged 2006 geography, joined 1:1"
            " to 2011 and 2006."
        ),
        "fields": [
            {
                "name": f.name,
                "type": str(f.type),
                "nullable": f.nullable,
                "description": description(f.name),
            }
            for f in schema
        ],
    }
    (out / f"{NAME}.schema.json").write_text(json.dumps(contract, indent=2) + "\n")
    with (out / f"{NAME}_dictionary.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(
            stream, fieldnames=["column", "type", "nulls", "description"]
        )
        writer.writeheader()
        for f in schema:
            writer.writerow(
                {
                    "column": f.name,
                    "type": str(f.type),
                    "nulls": table[f.name].null_count,
                    "description": description(f.name),
                }
            )
    strata = defaultdict(Counter)
    history = Counter()
    for r in rows:
        if r["is_eligible"]:
            strata[r["caste_transition"]][str(r["reserved_woman_2011"])] += 1
            history[
                str(r["reserved_woman_2006"]) + str(r["reserved_woman_2011"]) + "0"
            ] += 1
    audit = {
        "left_universe": "26 outcome-election wards",
        "join_cardinality": "1:1",
        "rows": 26,
        "unmatched": 0,
        "eligible": 17,
        "eligible_without_2006_quota": 13,
        "eligible_caste_transition_arms": strata,
        "eligible_histories_2006_2011_2016": history,
        "final_candidates": 122,
        "nota_rows": 26,
        "all_ward_vote_totals_reconcile": True,
        "source_discrepancies": [
            "PDF 96 nomination heading prints 2011; all 26 winners match dated"
            " 2016 returns.",
            "PDF 156 labels 186 as contesters; detailed returns have 122 plus "
            "26 NOTA rows.",
        ],
    }
    (out / f"{NAME}_audit.json").write_text(json.dumps(audit, indent=2) + "\n")
    sources = [
        SOURCE,
        REVIEW,
        DATA / "release/ward_panel_2006_2011.parquet",
        *parse.REPORTS.values(),
    ]
    files = [
        path,
        out / f"{NAME}.schema.json",
        out / f"{NAME}_dictionary.csv",
        out / f"{NAME}_audit.json",
    ]
    manifest = {
        "sources": [
            {"path": parse.relative(p), "sha256": digest(p), "bytes": p.stat().st_size}
            for p in sources
        ],
        "outputs": [
            {"path": p.name, "sha256": digest(p), "bytes": p.stat().st_size}
            for p in files
        ],
    }
    (out / f"{NAME}_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return audit


@command("process", artifact="extension")
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=DATA / "release")
    args = ap.parse_args()
    print(json.dumps(write(build_rows(), args.out), indent=2))


if __name__ == "__main__":
    main()
