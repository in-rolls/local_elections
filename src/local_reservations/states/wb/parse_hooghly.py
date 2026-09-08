"""Read the complete archived 2003 Hooghly GP party-count table.

The HTML labels are retained: seats_contested sums to 2,033 and
seats_declared to 3,440. Party counts sum to seats_contested, so the table
does not establish party control of all 3,440 seats or complete results.
"""

import hashlib
import json
from html.parser import HTMLParser

from local_reservations.common.runlog import command
from local_reservations.paths import ROOT
from local_reservations.states.wb.parse_results import write_table

SOURCE = ROOT / "data/wb/gp_source_search/hooghly_2003_total.htm"
OUT = ROOT / "data/wb/derived/hooghly_2003"
URL = "https://web.archive.org/web/20041117101744/http://hooghly.nic.in:80/hzp/Panch_election1/total.htm"
PARTIES = ["AIFB", "AITC", "BJP", "BSP", "CPI", "CPI(M)", "INC", "MFB", "RSP", "OTHERS"]


class Rows(HTMLParser):
    def __init__(self):
        super().__init__()
        self.rows = []
        self.row = []
        self.cell = None

    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            self.row = []
        if tag in {"td", "th"}:
            if tag == "td" and any(
                k in {"rowspan", "colspan"} and v != "1" for k, v in attrs
            ):
                raise ValueError("Unexpected merged body cell")
            self.cell = []

    def handle_data(self, value):
        if self.cell is not None:
            self.cell.append(value)

    def handle_endtag(self, tag):
        if tag in {"td", "th"} and self.cell is not None:
            self.row.append(" ".join("".join(self.cell).split()))
            self.cell = None
        if tag == "tr":
            self.rows.append(self.row)


def parse(content):
    reader = Rows()
    reader.feed(content)
    if reader.rows[:2] != [
        [
            "Block Name",
            "GP Name",
            "seats_contested",
            "seats_declared",
            "Party wise Breakup",
        ],
        PARTIES,
    ]:
        raise ValueError("Unexpected source headers")
    body = reader.rows[2:]
    if any(len(row) != 14 for row in body) or body[-1][:2] != ["TOTAL", "-"]:
        raise ValueError("Unexpected body shape or missing total")
    numeric = [[int(v) for v in row[2:]] for row in body]
    totals = numeric[-1]
    if [sum(row[i] for row in numeric[:-1]) for i in range(12)] != totals:
        raise ValueError("Column totals do not reconcile with printed TOTAL")
    rows = []
    for position, (raw, numbers) in enumerate(
        zip(body[:-1], numeric[:-1], strict=True), 3
    ):
        if min(numbers) < 0 or sum(numbers[2:]) != numbers[0]:
            raise ValueError(f"Party total does not reconcile at HTML row {position}")
        if numbers[0] > numbers[1]:
            raise ValueError(f"Contested exceeds declared at HTML row {position}")
        rows.append(
            {
                "state": "West Bengal",
                "year": 2003,
                "district": "Hooghly",
                "block": raw[0],
                "gram_panchayat": raw[1],
                "seats_contested_printed": numbers[0],
                "seats_declared_printed": numbers[1],
                "party_counts_sum": sum(numbers[2:]),
                "declared_minus_party_counts": numbers[1] - sum(numbers[2:]),
                "party_counts_cover_declared": numbers[0] == numbers[1],
                **dict(zip(PARTIES, numbers[2:], strict=True)),
                "source_html_row": position,
            }
        )
    if len({(r["block"], r["gram_panchayat"]) for r in rows}) != len(rows):
        raise ValueError("Duplicate GP within block")
    return rows, totals


@command("parse", state="West Bengal", source="hooghly_2003")
def main():
    raw = SOURCE.read_bytes()
    rows, totals = parse(raw.decode("cp1252"))
    if len(rows) != 210 or len({r["block"] for r in rows}) != 18:
        raise ValueError("Archived source row-count contract failed")
    digest = hashlib.sha256(raw).hexdigest()
    for row in rows:
        row.update(
            source_path=str(SOURCE.relative_to(ROOT)),
            source_sha256=digest,
            source_url=URL,
        )
    OUT.mkdir(parents=True, exist_ok=True)
    write_table(rows, OUT / "gp_party_counts")
    report = {
        "gram_panchayats": len(rows),
        "blocks": 18,
        "seats_contested_printed": totals[0],
        "seats_declared_printed": totals[1],
        "party_counts_sum": sum(totals[2:]),
        "gp_with_party_counts_covering_declared": sum(
            r["party_counts_cover_declared"] for r in rows
        ),
        "source_sha256": digest,
        "checks": [
            "All 210 GP rows parsed",
            "All 12 numeric column sums match printed TOTAL",
            "All 210 party sums equal printed seats_contested",
            "Unique block/GP keys",
            "Parquet round trip preserves values",
        ],
        "limitation": (
            "Source party counts cover 2,033 of 3,440 printed declared seats. "
            "No reservation, candidate or vote data. Missing party counts "
            "are not assigned to a party."
        ),
    }
    (OUT / "validation.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
