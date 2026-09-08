# Tamil Nadu GP-president reservations

The [2011 CSV](gp_president_reservations.csv) and
[typed Parquet](gp_president_reservations.parquet) contain
**12,524 distinct named GP-president entries in 31 printed districts and 385
panchayat unions**, extracted from the complete GO61 roster in Gazette No.318.
There are 12,523 recorded reservation categories and one genuinely blank cell.
These are office reservations; the source does not report elected presidents
or their sex. This export is separate from the pooled master.

The source is the [9 September 2011 gazette](../../../source_search/early_heads/raw/tn_1_58_2011_318_en.pdf),
[official download](https://tnrd.tn.gov.in/project/go_files/1_58_2011_318_en.pdf).
PDF pages 3–153 contain the roster. The eight GO60 amendments on pages 1–2 are
separate operations and are not appended as eight additional GPs. Later
amendments and actual implementation at the election have not been established.

| Printed office category, normalized | GP entries |
|---|---:|
| General | 6,150 |
| General (Women) | 3,090 |
| SC (General) | 1,967 |
| SC (Women) | 1,165 |
| ST (General) | 113 |
| ST (Women) | 38 |
| Blank / unknown | 1 |

Every row retains the source URL, original PDF hash, PDF page, table column,
line, bounding box, raw text fragments, printed serial, raw GP name, raw
category and union heading evidence. `row_id` identifies a source occurrence;
it is not an LGD/Census code or a stable identifier across election cycles.
`union_key` removes whitespace/case differences and reconciles the explicitly
continued ALANKULAM/ALANGULAM section; both raw spellings remain. Printed
district spellings are retained apart from capitalization and the word District.
No modern geography crosswalk has been applied.

[The dictionary](dictionary.csv) specifies every output field.
The [category crosswalk](category_crosswalk.csv) gives each
raw spelling and its recode count. General is explicitly printed, not inferred
from nonlisting. `woman_reserved = false` describes the office category, not a
male winner. An empty source category yields null reservation fields in Parquet;
CSV readers must preserve it as missing and read identifiers as text.

## Verification and source anomalies

The layout parser accounts for every table page, including the single-column
Nilgiris page. A separate native reader agrees on all 12,524 GP names, printed
serials and reservation texts after whitespace/case normalization. Its
[controls and visual checks](../../../source_search/early_heads/tn_review/2011_controls/README.md)
include per-page, union and district counts. These checks do not claim that
all 12,524 names were visually transcribed or that the supplied notification
captures every subsequent administrative change.

- Ramakrishnarajupet, printed serial 14 on PDF page 15, has a blank category.
  It stays unknown; neighboring categories are not carried into it.
- Kaveripakkam prints serial 23 twice and omits 22. Ottapidaram repeats 33 and
  34 where sequence positions are 49 and 51. All entries and printed serials
  remain; serial alone is not a unique GP key.
- Five displaced native text cells are rejoined using their page coordinates.
  Each row retains both source fragments and a quality flag.
- Printed spelling variants such as Genaral and singular Woman are normalized
  only in derived category fields. The original text remains beside them.

Rebuild and test from the repository root:

```sh
uv run python -m local_reservations.states.tn.parse_heads_2011
uv run pytest tests/test_tn_heads_2011.py -q
```

The parser verifies the PDF against its acquisition hash and checks complete
page/row counts, source occurrence uniqueness and the Parquet roundtrip.
[validation.json](validation.json) records source and parser
hashes, library versions and limitations. Output Parquet types and nulls are
authoritative; CSV is provided for inspection and manual work.

## Earlier sources

The preserved 1996 notification, 2001 amendments and 2006 notification/errata
are described in the [historical source review](../../../source_search/early_heads/tn_source_review.md).
The [early-source ledger](../../../source_search/early_heads/README.md) distinguishes
full rosters, amendments and other office tiers. OCR readings are stored under
`data/tn/derived/scans/` with source images, engine/settings and checksums; they are not
verified GP observations. Substantial OCR errors in the 1996 pilot require
review and correction before semantic records are accepted.
