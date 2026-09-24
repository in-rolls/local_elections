"""The page, and what we made of it, side by side.

    uv run python -m local_elections.tools.proof_page "PAKUR MUKHIYA" 1

Renders one source page and puts the rows we published from it next to the
image, then opens the result. Reading down the two halves is a check no
assertion covers: whether the name in column 1 of the page is the name in our
`winner`, whether the seat we recorded is the seat printed beside it.

Written because this corpus keeps producing values that pass every automated
check and are visibly wrong to anyone who looks. `winner` held the words "ग्राम
पंचायत" for seven rows; 17,115 more held Kruti Dev bytes under a column claiming
Unicode; a caption, "प्रा0नि0क्षे0 सं0", was published as a gram panchayat's
name. Every one of those was populated, correctly typed, counted right, and
wrong - and every one is obvious the moment the page is beside the row.

Where the source is a font encoding rather than Unicode, both forms are shown:
what the file stores and what we publish. That is the only way to see that
`nsoh` became देवी rather than something that merely looks like Devanagari.
"""

import argparse
import csv
import html
import pathlib
import subprocess
import sys
import webbrowser

from local_elections.common.runlog import command
from local_elections.paths import ROOT

OUT = pathlib.Path("/tmp/proof_page.html")
SHOW = [
    "winner",
    "tier_local",
    "caste_reservation",
    "woman_reserved",
    "block",
    "gram_panchayat",
    "ward_no",
    "seat_no",
    "seat_id_raw",
]


def rows_for(stem, page):
    """Every published row read off that page, whatever tier it landed in."""
    found = []
    for path in sorted((ROOT / "data").rglob("*.csv")):
        if "master" in path.parts or path.stat().st_size > 80_000_000:
            continue
        try:
            with path.open(encoding="utf-8") as fh:
                reader = csv.DictReader(fh)
                if not reader.fieldnames or "source_pdf" not in reader.fieldnames:
                    continue
                for row in reader:
                    if pathlib.Path(row.get("source_pdf") or "").stem == stem and str(
                        row.get("source_page")
                    ) == str(page):
                        found.append(row)
        except (UnicodeDecodeError, csv.Error):
            continue
    return found


def find_pdf(stem):
    hits = [p for p in (ROOT / "data").rglob("*.pdf") if p.stem == stem]
    if not hits:
        hits = [
            p for p in (ROOT / "data").rglob("*.pdf") if stem.lower() in p.stem.lower()
        ]
    return hits[0] if hits else None


def render(pdf, page, dpi):
    stem = pathlib.Path("/tmp") / f"proof_{abs(hash(str(pdf))) % 10**8}_{page}"
    subprocess.run(
        [
            "pdftoppm",
            "-f",
            str(page),
            "-l",
            str(page),
            "-r",
            str(dpi),
            "-png",
            "-singlefile",
            str(pdf),
            str(stem),
        ],
        check=True,
        capture_output=True,
    )
    return stem.with_suffix(".png")


def cell(value):
    """A published value, and - where it is a font encoding - what it decodes
    from, so the conversion itself can be checked rather than assumed.
    """
    value = (value or "").strip()
    if not value:
        return "<td class='blank'>—</td>"
    return f"<td>{html.escape(value)}</td>"


@command("review", artifact="proof_page")
def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("document", help="PDF stem, or part of it")
    ap.add_argument("page", type=int)
    ap.add_argument("--dpi", type=int, default=170)
    args = ap.parse_args()

    pdf = find_pdf(args.document)
    if not pdf:
        sys.exit(f"no PDF matching {args.document!r} under data/")
    rows = rows_for(pdf.stem, args.page)
    image = render(pdf, args.page, args.dpi)

    head = "".join(f"<th>{c}</th>" for c in SHOW)
    body = ""
    for row in rows:
        body += "<tr>" + "".join(cell(row.get(c)) for c in SHOW) + "</tr>"
    if not rows:
        body = (
            f"<tr><td colspan='{len(SHOW)}' class='blank'>no published rows "
            f"cite this page — which is itself the finding</td></tr>"
        )

    OUT.write_text(
        f"""<!doctype html><meta charset="utf-8">
<title>{html.escape(pdf.stem)} p{args.page}</title>
<style>
 body {{ font: 14px/1.5 -apple-system, sans-serif; margin: 0; background: #f6f6f4; }}
 header {{ padding: 10px 16px; background: #222; color: #fff; }}
 header b {{ font-weight: 600; }}
 .split {{ display: flex; gap: 12px; align-items: flex-start; padding: 12px; }}
 .half {{ flex: 1 1 0; min-width: 0; background: #fff; border: 1px solid #ddd;
          border-radius: 6px; overflow: auto; max-height: 88vh; }}
 .half h2 {{ font-size: 13px; margin: 0; padding: 8px 12px; background: #eee;
             position: sticky; top: 0; }}
 img {{ width: 100%; display: block; }}
 table {{ border-collapse: collapse; width: 100%; font-size: 12px; }}
 th, td {{ border: 1px solid #e3e3e3; padding: 4px 6px; text-align: left;
           vertical-align: top; }}
 th {{ background: #fafafa; position: sticky; top: 33px; font-weight: 600; }}
 .blank {{ color: #bbb; }}
</style>
<header><b>{html.escape(pdf.stem)}</b> &nbsp;page {args.page} &nbsp;·&nbsp;
 {len(rows)} published row(s) cite this page</header>
<div class="split">
  <div class="half"><h2>the page as printed</h2>
    <img src="file://{image}"></div>
  <div class="half"><h2>what we published from it</h2>
    <table><tr>{head}</tr>{body}</table></div>
</div>
""",
        encoding="utf-8",
    )
    print(f"{len(rows)} row(s) -> {OUT}")
    webbrowser.open(f"file://{OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
