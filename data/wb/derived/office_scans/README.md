# Scanned West Bengal office schedules

Rebuild with `uv run --group table-ocr python -m local_reservations.states.wb.parse_office_scans`.
Local Poppler and Tesseract must be installed. No paid OCR is used.

`mentions.csv`, `.parquet`, and `.jsonl` contain positive reservation mentions,
not a roster of Gram Panchayats. Category and women columns are read separately.
The same office can occur once for caste reservation and once for women
reservation. Draft and final sources remain separate. A missing mention does
not establish that an office was unreserved; winner gender is always unknown.
The `name` field also names Panchayat Samitis and Zilla/Mahakuma Parishads; use
`tier` before treating any name as a Gram Panchayat. Statewide ZP schedules have
an empty `district` field because the source site is Alipurduar or South 24 Parganas, but the schedule
covers West Bengal. The actual named jurisdiction is in `name`.

The eight GP/mixed scanned sources cover 34 pages. Seven additional
block/statewide ZP office sources add 16 pages, including the 2018 final
statewide Form 1D acquired from South 24 Parganas. `page_review.csv` accounts for
all 50 pages, including order covers and forwarding letters. `row_review.csv`
retains every detected GP table cell, including blanks, headings and unresolved
readings. The four small block schedules and three statewide ZP schedules were
visually transcribed; their complete positive listings are in
`curated_schedules.json`. Their page OCR, including cover text, is retained in
hash-addressed caches.

The GP extraction uses direct 3600-pixel rendering, table rectification, ruled
cell boundaries, grid removal and fixed-threshold cleanup. Nadia pages 2–6 are
rotated clockwise before extraction. Tesseract PSM 6 and 7 readings are retained
separately. Cell caches fingerprint the crop bytes, engine version, language,
PSM settings and TSV parser. A changed crop invalidates its cache. Full source
PDF hashes are checked before extraction. Bounding boxes use the original
page orientation, in pixels at a longest edge of 1800. They enclose the source
cell or the manually transcribed line; they are not PDF-point coordinates.

Most GP names remain unreviewed OCR. Agreement between OCR passes and agreement
with published counts do not establish spelling accuracy. Use `quality_flags`
and `name_review_status`; review the crop and original page before linking an
uncertain spelling to a geographic identifier. Two missed bold Cooch Behar
women-column readings were visually corrected in `cell_overrides.json`, with
source and geometry checks. No fuzzy geographic matching or name imputation is
performed here. Block labels in Alipurduar were visually identified and are
checked against the current heading cells.

Frozen blinded visual references cover 109 additional sampled cells: 51 blanks
and 58 positive category readings. Their sample IDs, source geometry, inspected
image hashes and reference-file hashes are retained in `cell_overrides.json`
and the exported review evidence. These are visual-agent readings, not human
double entry. Original OCR remains in `raw_reading` and `second_reading`.
One women-listed office has an unresolved exact suffix: its `name` is null,
its women reservation remains true, and `name_review_status` is
`unresolved_exact_name`. Blank cells retain unknown reservation negatives.
Qwen predictions remain separate evaluation evidence and do not replace these
source readings.

`printed_controls.json` preserves visually read summary counts, including the
reversed SC/ST column order in the statewide draft. `control_reconciliation.csv`
compares them with extracted mentions. A blank printed count remains unknown.
The following discrepancies are retained rather than forced to agree:

- Both Alipurduar GP deputy schedules print eight ST offices but list seven ST
  names. The seven SC names and eight women names are retained independently.
- Birbhum Pradhan prints 81 women offices; its named column contains 82 positive
  mentions. Names are not deduplicated without block identities or other evidence.
- The statewide draft deputy schedule prints four SC and one BC office, but its
  named list marks five SC offices and no BC office. The final schedule prints
  five SC offices and leaves the BC summary blank.

All 50 pages were inspected for layout. This is an auditable extraction and a
review queue, not a claim of certified accuracy. `source_counts.csv` reports
source coverage and extraction counts; it is not an accuracy score.
