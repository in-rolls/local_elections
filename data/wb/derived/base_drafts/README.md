# West Bengal 2018 base gazettes: draft export and complete page audit

Run `.venv/bin/python -m local_reservations.states.wb.parse_base_drafts`.
The module is also included in `make wb-parse-all`.

The acquired base collection contains 39 PDFs and 181 pages: 20 final orders
(84 pages) and 19 draft orders (97 pages). The acquired tree has no Malda draft.
The separate draft export contains 787 Zilla Parishad **member-seat** records.
These are not Gram Panchayat head offices. The existing final output remains
`data/wb/zp_member_2018.csv`, with 825 records.

The legacy parser uses drafts for its agreement calculation but exports only
final records. On the current inputs it reads 449 draft rows, returns no rows
for eight drafts, and produces only 123 comparable district/seat keys because
several draft filenames use district spellings/patterns that do not match the
final filenames. This module does not alter the legacy final output or its
agreement field.

`visual_corrections.json` records eight visually checked header repairs and
11 restored seat identifiers. Every repair is pinned to both the original PDF
hash and the affected OCR TSV hash. The corrections preserve missing slashes
actually printed in the Burdwan-I and Bharatpur-I identifiers. Restoring a seat
anchor occurs before reservation markers are reassigned, preventing a marker
from leaking to the previous seat. No original PDF or OCR cache is rewritten.

Files:

- `records.csv`, `.parquet`, `.jsonl`: separate draft records, raw OCR, source and
  cache hashes, page, approximate row-band geometry, and review flags.
- `sources.csv`, `.parquet`, `.jsonl`: all 39 sources, including final output
  routing, page coverage, duplicate identifiers, and seat-number gaps.
- `page_review.csv`, `.parquet`, `.jsonl`, and `page_audit.json`: all 181 pages.
  The JSON audit is consumed by the combined parsing inventory. Final pages
  reference their existing OCR evidence; they are not labelled native text.
- `summary.json`: coverage and limitations.

All draft district seat-number sequences are contiguous with no duplicates.
That establishes identifier coverage, not reservation accuracy. Apart from the
specified header/identifier checks, these are unreviewed OCR records. The
separate caste and women columns remain separate axes: an absent OCR marker
is null, not a verified negative. The legacy parser's raw `NONE`/`0` readings
remain available for audit. No reservation implies a winner's gender.

The historical OCR cache lacks an original crop/settings fingerprint. Current
PDF and TSV hashes pin the inputs used here but cannot retrospectively certify
how that cache was produced. Row bands start near an identifier anchor and end
at the next anchor; they are approximate review regions, not ruled-cell boxes.
