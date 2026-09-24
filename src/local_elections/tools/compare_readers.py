"""One page, both readers, side by side with the page itself.

    uv run python -m local_elections.tools.compare_readers "RANCHI ZP PSS MUKHIYA
    GPS" 37

Every Jharkhand document is now read twice - out of its own text layer, and by
the model out of a rendered image - and the two disagree about how many seats a
page holds. Ranchi's text layer finds 305 mukhiya where the model finds 287, and
its ward tier the other way round: 3,539 against 3,584.

Counts cannot settle that. The page can. This puts the rendered page beside both
readings so the question becomes "which of these matches what is printed", which
is a question a person answers in seconds and a script cannot answer at all.

The Kruti Dev side is shown transliterated, because comparing मुखिया against
eqf[k;k is comparing encodings rather than readings.
"""

import argparse
import html
import pathlib
import re
import subprocess
import sys
import webbrowser

from local_elections.common import krutidev
from local_elections.common.runlog import command
from local_elections.paths import ROOT
from local_elections.states.jharkhand import parse

OUT = pathlib.Path("/tmp/compare_readers.html")
DEVA = re.compile(r"[ऀ-ॿ]")
SHOW = [
    "winner",
    "tier_local",
    "caste_reservation",
    "woman_reserved",
    "gram_panchayat",
    "ward_no",
    "seat_no",
    "seat_id_raw",
]


def readable(value):
    value = str(value or "").strip()
    if value and not DEVA.search(value) and not value.isascii():
        return krutidev.to_unicode(value)
    return value


def find_pdf(stem):
    hits = [p for p in (ROOT / "data").rglob("*.pdf") if p.stem == stem]
    if not hits:
        hits = [
            p for p in (ROOT / "data").rglob("*.pdf") if stem.lower() in p.stem.lower()
        ]
    return hits[0] if hits else None


def from_text_layer(pdf, page, district):
    """What pdfplumber makes of the page: ruled tables, then the line reader."""
    import pdfplumber

    rows = []
    with pdfplumber.open(str(pdf)) as doc:
        target = doc.pages[page - 1]
        block = ""
        found = parse.RE_BLOCK.search(target.extract_text() or "")
        if found:
            block = parse.clean(found.group(1))
        for table in target.find_tables():
            for raw in table.extract():
                cells = [parse.clean(c) for c in raw]
                if len(cells) < 5:
                    continue
                got = parse.table_row(cells)
                if got:
                    tier, caste, woman, seat, winner, label = got
                    rows.append(
                        parse.seat_row(
                            district, block, tier, caste, woman, seat, winner, label
                        )
                    )
        rows += [dict(r) for r in parse._from_text(target, pdf, district, block)]
    return rows


def from_model(stem, page, district):
    cache = ROOT / "data" / "jharkhand" / "ocr" / f"{stem}.txt"
    if not cache.exists():
        return []
    pages = cache.read_text(encoding="utf-8").split("\f")
    if page > len(pages):
        return []
    return parse.html_rows(pages[page - 1], pathlib.Path(f"{stem}.pdf"), district, page)


def table(rows):
    head = "".join(f"<th>{c}</th>" for c in SHOW)
    body = ""
    for row in rows:
        body += (
            "<tr>"
            + "".join(
                f"<td>{html.escape(readable(row.get(c))) or '<i>—</i>'}</td>"
                for c in SHOW
            )
            + "</tr>"
        )
    if not rows:
        body = f"<tr><td colspan='{len(SHOW)}'><i>no rows</i></td></tr>"
    return f"<table><tr>{head}</tr>{body}</table>"


@command("review", artifact="reader_comparison")
def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("document")
    ap.add_argument("page", type=int)
    ap.add_argument("--district", default="")
    ap.add_argument("--dpi", type=int, default=170)
    args = ap.parse_args()

    pdf = find_pdf(args.document)
    if not pdf:
        sys.exit(f"no PDF matching {args.document!r}")
    stem = pathlib.Path("/tmp") / f"cmp_{abs(hash(pdf.stem)) % 10**7}_{args.page}"
    subprocess.run(
        [
            "pdftoppm",
            "-f",
            str(args.page),
            "-l",
            str(args.page),
            "-r",
            str(args.dpi),
            "-png",
            "-singlefile",
            str(pdf),
            str(stem),
        ],
        check=True,
        capture_output=True,
    )

    text_rows = from_text_layer(pdf, args.page, args.district)
    model_rows = from_model(pdf.stem, args.page, args.district)

    OUT.write_text(
        f"""<!doctype html><meta charset="utf-8">
<title>{html.escape(pdf.stem)} p{args.page}</title>
<style>
 body {{ font: 13px/1.45 -apple-system, sans-serif; margin: 0; background: #f6f6f4; }}
 header {{ padding: 9px 14px; background: #222; color: #fff; }}
 .split {{ display: flex; gap: 10px; padding: 10px; align-items: flex-start; }}
 .pane {{ flex: 1 1 0; min-width: 0; background: #fff; border: 1px solid #ddd;
          border-radius: 6px; overflow: auto; max-height: 90vh; }}
 .pane h2 {{ font-size: 12px; margin: 0; padding: 7px 10px; position: sticky;
             top: 0; background: #eee; }}
 .text h2 {{ background: #fde8c8; }} .model h2 {{ background: #d7ecd9; }}
 img {{ width: 100%; display: block; }}
 table {{ border-collapse: collapse; width: 100%; font-size: 11px; }}
 th, td {{ border: 1px solid #e6e6e6; padding: 3px 5px; text-align: left;
           vertical-align: top; }}
 th {{ background: #fafafa; position: sticky; top: 30px; }}
 i {{ color: #bbb; }}
</style>
<header><b>{html.escape(pdf.stem)}</b> page {args.page} &nbsp;·&nbsp;
 text layer <b>{len(text_rows)}</b> rows &nbsp;·&nbsp;
 model <b>{len(model_rows)}</b> rows</header>
<div class="split">
  <div class="pane"><h2>the page as printed</h2>
    <img src="file://{stem}.png"></div>
  <div class="pane text"><h2>text layer — {len(text_rows)} rows
    (Kruti Dev shown transliterated)</h2>{table(text_rows)}</div>
  <div class="pane model"><h2>model — {len(model_rows)} rows</h2>
    {table(model_rows)}</div>
</div>
""",
        encoding="utf-8",
    )
    print(f"text layer {len(text_rows)} rows, model {len(model_rows)} rows -> {OUT}")
    webbrowser.open(f"file://{OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
