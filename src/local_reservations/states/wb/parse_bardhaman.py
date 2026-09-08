"""Parse archived 2003 Bardhaman GP results and reconcile all block controls.

Election year comes from page headings, not the 2009 capture dates. Multiple
archived spellings of a block URL must produce identical GP records before
being deduplicated. Inconsistent source figures remain unchanged and flagged.
"""

import hashlib
import json
import re
from collections import defaultdict
from html.parser import HTMLParser
from urllib.parse import parse_qs, urlsplit

from local_reservations.common.runlog import command
from local_reservations.paths import ROOT
from local_reservations.states.wb.parse_results import write_table

BASE = ROOT / "data/wb/vintage_search"
OUT = ROOT / "data/wb/derived/bardhaman_2003"
PARTIES = [
    "CPI(M)",
    "CPI",
    "AIFB",
    "RSP",
    "INC",
    "AITC",
    "BJP",
    "CPI(ML)",
    "NCP",
    "IND",
]
FIELDS = [
    "seats_total",
    "seats_uncontested",
    "seats_election_held",
    "contesting_candidates",
    *PARTIES,
]


class Table(HTMLParser):
    def __init__(self):
        super().__init__()
        self.rows = []
        self.row = []
        self.cell = None
        self.inside = False
        self.done = False

    def handle_starttag(self, tag, attrs):
        if tag == "table" and not self.done:
            self.inside = True
        if not self.inside:
            return
        if tag == "tr":
            self.row = []
        if tag in {"td", "th"}:
            self.cell = []

    def handle_data(self, data):
        if self.cell is not None:
            self.cell.append(data)

    def handle_endtag(self, tag):
        if tag in {"td", "th"} and self.cell is not None:
            self.row.append(" ".join("".join(self.cell).split()))
            self.cell = None
        if tag == "tr" and self.inside:
            self.rows.append(self.row)
        if tag == "table" and self.inside:
            self.inside = False
            self.done = True


def parse(content, *, block_table=False):
    if not re.search(r"Panchayat\s+General\s+Election\s*-\s*2003", content):
        raise ValueError("Missing explicit 2003 election heading")
    table = Table()
    table.feed(content)
    expected = "Name of Block" if block_table else "Name of Gram Panchayat"
    if len(table.rows) < 3 or table.rows[0][0] != expected or table.rows[1] != PARTIES:
        raise ValueError("Unexpected table headers")
    expected_headers = [
        expected,
        "Total No. of Seats",
        "Total No. of seats declared elected uncontested",
        "Total No. of seats where election held",
        "Total No. of Contesting Candidates",
        "No. of Candidates declared elected with partywise break up "
        "including uncontested",
    ]
    if table.rows[0] != expected_headers:
        raise ValueError("Unexpected numeric column headers")
    rows = []
    for position, cells in enumerate(table.rows[2:], 3):
        if len(cells) != 15:
            raise ValueError(f"Unexpected row width at row {position}")
        if any(not re.fullmatch(r"\d+", c) for c in cells[1:]):
            raise ValueError(f"Non-integer or empty source count at row {position}")
        row = dict(zip(FIELDS, map(int, cells[1:]), strict=True))
        flags = []
        if row["seats_uncontested"] + row["seats_election_held"] != row["seats_total"]:
            flags.append("seat_components_mismatch")
        if sum(row[p] for p in PARTIES) != row["seats_total"]:
            flags.append("party_total_mismatch")
        row.update(name=cells[0], source_html_row=position, issues=flags)
        rows.append(row)
    if len({r["name"] for r in rows}) != len(rows):
        raise ValueError("Duplicate named row within table")
    return rows


def build(base=BASE):
    sources = [
        json.loads(line) for line in (base / "fetch_log.jsonl").read_text().splitlines()
    ]
    sources = {
        r["url"]: r for r in sources if r.get("file") and "/pan_result/" in r["url"]
    }
    blocks = defaultdict(list)
    control = None
    for url, source in sorted(sources.items()):
        path = base / source["file"]
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != source["sha256"]:
            raise ValueError(f"Source hash mismatch: {path}")
        original = url.split("id_/", 1)[-1]
        if original.endswith("/blgpview.asp"):
            control = (source, parse(raw.decode("cp1252"), block_table=True))
        elif "/gpview.asp?" in original:
            block = parse_qs(urlsplit(original).query)["blno"][0]
            blocks[block].append((source, parse(raw.decode("cp1252"))))
    if control is None or set(blocks) != {f"{n:02d}" for n in range(1, 32)}:
        raise ValueError("Missing block table or GP page for one of 31 blocks")
    control_source, controls = control
    if len(controls) != 31:
        raise ValueError("Unexpected block control count")
    # The block table links supply the district website's own block identifiers.
    content = (base / control_source["file"]).read_text(encoding="cp1252")
    linked = re.findall(
        r'gpview\.asp\?blno=(\d+)&(?:amp;)?blnm=[^"\']+["\'][^>]*>(.*?)</a>',
        content,
        re.I | re.S,
    )
    names = {key: re.sub("<[^>]+>", "", value).strip() for key, value in linked}
    if set(names) != set(blocks):
        raise ValueError("Block identifier links do not cover the GP pages")
    by_name = {r["name"]: r for r in controls}
    records, audit = [], []
    for block, variants in sorted(blocks.items()):
        source, rows = variants[0]
        expected = by_name[names[block]]
        if any(other != rows for _, other in variants[1:]):
            raise ValueError(f"Conflicting archived GP tables for block {block}")
        mismatches = {
            key: {"gp_sum": sum(r[key] for r in rows), "block_printed": expected[key]}
            for key in FIELDS
            if sum(r[key] for r in rows) != expected[key]
        }
        for row in rows:
            flags = row.pop("issues")
            if mismatches:
                flags.append("gp_sum_differs_from_block_control")
            row.update(
                state="West Bengal",
                year=2003,
                district="Bardhaman",
                block_code=block,
                block=names[block],
                gram_panchayat=row.pop("name"),
                source_url=source["url"],
                source_path=str((base / source["file"]).relative_to(ROOT)),
                source_sha256=source["sha256"],
                issues=";".join(flags),
                review_status="needs_review" if flags else "source_controls_passed",
            )
            records.append(row)
        audit.append(
            {
                "block_code": block,
                "block": names[block],
                "n_gps": len(rows),
                "source_variants": len(variants),
                "mismatches": mismatches,
            }
        )
    report = {
        "year": 2003,
        "district": "Bardhaman",
        "blocks": len(blocks),
        "gram_panchayats": len(records),
        "archived_gp_pages": sum(map(len, blocks.values())),
        "block_checks": audit,
        "needs_review": sum(r["review_status"] == "needs_review" for r in records),
        "gp_column_totals": {key: sum(r[key] for r in records) for key in FIELDS},
        "block_column_totals": {key: sum(r[key] for r in controls) for key in FIELDS},
        "limitation": (
            "Party seat counts including uncontested winners; no candidate names, "
            "votes or reservation categories. Tabled for reservation research."
        ),
    }
    return records, controls, report


@command("parse", state="West Bengal", source="bardhaman_2003")
def main():
    rows, controls, report = build()
    OUT.mkdir(parents=True, exist_ok=True)
    write_table(rows, OUT / "gp_party_counts")
    write_table(
        [{**r, "issues": ";".join(r["issues"])} for r in controls],
        OUT / "block_controls",
    )
    (OUT / "validation.json").write_text(json.dumps(report, indent=2) + "\n")
    print(
        json.dumps({k: v for k, v in report.items() if k != "block_checks"}, indent=2)
    )


if __name__ == "__main__":
    main()
