# West Bengal GP extraction and review data

These files extend the GP source search. They are separate from the pooled
reservation corpus. The raw PDFs and HTML remain unchanged in the
[source collection](../gp_source_search.md).

For **GP Pradhan-office reservation status**, start with these separate outputs.
None has been added to the pooled reservation dataset or used to assume a
random assignment mechanism.

| Output | Unit and coverage | Main limitation |
| --- | --- | --- |
| [Birbhum research data](birbhum_reservations/README.md) | Named 1998/2003 GP research observations, with source IDs and raw coding | Survey samples, year exceptions and conflicting source values |
| [Nadia 2013 handbook](nadia_2013_handbook/office_reservations.csv) | 187 named GPs per office; 374 Pradhan/deputy rows with source serials | One Pradhan category is genuinely blank; repeated names require the source serial |
| [Alipurduar 2018 offices](alipurduar_offices/office_reservations.csv) | 50 named Pradhan rows, 16 deputy rows, 6 block-office rows | Lists name reserved offices; absent offices and blank other axes remain unknown |
| [Purulia/South 24/Jalpaiguri offices](office_native/mentions.csv) | 1,197 positive reservation mentions from 81 pages; all 1,982 detected cells reviewed, including blanks/headings | Mentions are separate axes, tiers and draft/final stages; they are not a count of unique GPs |
| [Scanned office schedules](office_scans/mentions.csv) | GP, block and district-office mentions from 50 pages, with separate tiers and stages | OCR names remain flagged; several printed summary counts contradict named lists |

The [full Nadia office audit](nadia_2013_handbook/full_office_visual_audit.json)
checks all 374 office rows against the printed serial, GP name and category
(1,122 fields). This is a single-assistant, non-blinded source review; it
supersedes the earlier 32-row sample in scope. The parser validates the frozen
audit hash and every source-row pin before applying its full-review status.
Original native readings, repeated-name serials and the blank Pradhan category
at serial 123 remain intact. See the [parse report](nadia_2013_handbook/parse_report.json)
for validation results and audit methodology.

The separate [Nadia GP-to-block membership table](nadia_2013_handbook/gp_block_membership.csv)
transcribes 186 printed GP occurrences across 17 blocks from handbook PDF
pages 71–74. The [full membership audit](nadia_2013_handbook/membership_visual_audit.json)
records source text, page coordinates and all four reviewed images. These are
constituency-list occurrences, not a complete 187-GP crosswalk: repeated
Ramnagar-Barachupria-II and Chapra/ZP-19 entries, an absent Haringhata-I entry,
and shortened names remain as printed. The table supplies source geography;
it does not assign blocks to ambiguous office names or establish national GP
codes and cross-year boundary continuity.

The [separate Nadia order comparison](nadia_2013_handbook/independent_order_comparison.json)
finds 202 matching positive reservation mentions (151 Pradhan, 51 deputy),
all agreeing with the handbook. Matching uses office and unique exact names
after case/whitespace normalization; repeated names remain unjoined. These
mentions cover 157 handbook office rows, not 202 distinct GPs. Serial 123's
blank Pradhan category remains unknown.

Full source reviews cover the held native-office schedules for
[Purulia](office_native/purulia_independent_audit.json),
[South 24 Pradhans](office_native/s24_head_independent_audit.json),
[South 24 deputies](office_native/s24_deputy_independent_audit.json), and
Jalpaiguri (cell-level entries in
[source transcriptions](office_native/source_transcriptions.csv)).
South 24's Pradhan totals matched even before review, masking an omitted
Jangalia women reservation and a signature misread as a reserved office.
Both are corrected with pinned source evidence. The deputy source's named
lists disagree with its printed totals; those contradictions remain visible.
The [draft Pradhan audit](office_native/s24_draft_head_independent_audit.json)
covers 468 data/blank cells and 58 heading fragments; the
[draft deputy audit](office_native/s24_draft_deputy_independent_audit.json)
covers 154 data/blank cells and 56 heading fragments. They correct 32 further
name/suffix readings after checks against larger source crops. The
[final deputy blank supplement](office_native/s24_deputy_blank_audit.json)
pins all 39 dash cells. Reviews preserve the source's own spellings and do
not establish a cross-district GP identifier or infer unreserved status from
an absent listing. Full source reviews disclose prior parser/sample exposure;
they are not human double entry or uniformly blinded reviews.

The [complete PDF-page ledger](parsing_inventory/pages.csv) connects every
acquired page to its parser audit, native extraction and available ward OCR.
[Output counts and schemas](parsing_inventory/outputs.csv) are generated from
the files themselves. These counts are labelled by unit: candidate rows,
seat rows and positive office mentions must not be summed as GPs. The ledger
can be refreshed while a resumable OCR batch is running.

The ledger accounts for 552 distinct acquired PDFs and 4,094 pages. This
includes reference documents and does not mean every table is structurally
parsed. The [ward semantic coverage report](ward_schedules/semantic_backlog.json)
records 1,046 of 1,523 OCR pages yielding candidate rows, 458 still raw-only,
and 19 visually verified nondata pages. Of the candidate pages, 689 contain
at least one recovered reservation field. The
[page-level backlog](ward_schedules/semantic_backlog.csv) links each remaining
page to its raw source, OCR cache and diagnostic reason. Candidate pages can
still be incomplete; all newly recovered OCR rows require field review.

The ward repairs increased GP-member rows from 3,237 to 8,196 and other-tier
rows from 379 to 928. A [five-page source check](ward_schedules/semantic_review/heldout/evaluation.json)
recovered 29 of 31 printed constituencies with no unexpected rows. These pages
helped diagnose and develop parser fixes, so they are development validation,
not an untouched test set. Emitted
reservation fields agreed with those source readings; two GP spelling errors
and missed fields remain explicitly flagged. This small check is not a corpus
accuracy estimate. A separate
[204-page Jalpaiguri orientation audit](ward_schedules/semantic_review/orientation_audit.json)
supports page-specific OCR repairs; original OCR attempts remain in the cache.

The subsequent [fresh four-page validation](ward_schedules/semantic_review/fresh_validation/evaluation.json)
is more cautionary: only 15 of 49 allocated seats were recovered. Among those
matched rows, emitted reservation fields agreed with the source, but five
positive fields were omitted and one GP name was wrong. The 49 seats span
46 Roman-numbered constituencies; these units must not be interchanged.
This is a small, nonrandom test of challenging layouts, not a population
accuracy estimate. It shows substantial remaining omissions despite improved
page coverage. Source readings were frozen before opening candidate outputs;
the parser was not tuned to these fresh readings.
The [49 frozen source readings](ward_schedules/semantic_review/fresh_validation/gold_rows.csv)
are also available as CSV for manual-review reuse, with allocated seats,
Roman constituencies and PS identifiers in separate fields.

| Other output | Unit and purpose |
| --- | --- |
| [Nadia 2008](nadia_2008/gp_seats.csv) | Allocated GP-member seats, with printed GP-level control checks |
| [Ward schedules](ward_schedules/gp_seats.csv) | GP-member reservation readings; PS/ZP rows are in a separate table |
| [Nadia 2013 ward aggregates](nadia_2013_handbook/ward_aggregates.csv) | GP-level counts for verification, not Pradhan-office assignments |
| [Alipurduar 2018 seats](alipurduar_2018/gp_seats.csv) and [candidates](alipurduar_2018/gp_candidates.csv) | Constituency results, votes and printed seat reservation |
| [Ancillary reports](ancillary/parse_report.json) | Nomination, withdrawal and polling-infrastructure reports, kept in distinct tables |
| [Reference tables](reference_tables/parse_report.json) | District/block statistics and handbook controls, with raw native tables |
| [Older gazette audit](base_drafts/page_audit.json) | All 39 held 2018 ZP gazettes; draft seat rows remain separate from final rows and GP-office data |
| [Hooghly 2003](hooghly_2003/gp_party_counts.csv) and [Bardhaman 2003](bardhaman_2003/gp_party_counts.csv) | Previously extracted party seat counts; tabled for reservation research |
| [Native document index](native/index.json) | All acquired PDFs, including references, aliases and reader failures |

The [historical district/year gap matrix](../vintage_search/README.md) tracks
acquisition gaps. A downloaded source, an extracted page and a validated
reservation record are different coverage measures.

Each structured table is available as Parquet, CSV and JSONL. Use Parquet to
preserve integer, boolean and null types. CSV empty cells do not mean zero.
The [GP results schema inventory](quality/schemas.json) records types and null
counts for its narrower scope; the full parsing inventory lists all output schemas.

**Start with the review records:**

- [Full parsing inventory](parsing_inventory/documents.csv) accounts for all
  acquired PDFs. The older [GP results quality report](quality/document_coverage.csv)
  has a narrower set of parser integrations; use the full inventory for coverage.
- [Row review queue](quality/row_review_queue.csv) links flagged seats and
  candidates to source pages and stable row IDs.
- [Scanned-office cell review](office_scans/row_review.csv) retains the
  remaining office transcription work. Filter `review_status` for
  `pending_cell_review` or `visually_read_ambiguous_exact_name`; blank cells
  and headings are explicitly distinguished after review. The corresponding
  positive-mention table contains 780 unreviewed OCR names and one unresolved
  exact name. These names have not been silently accepted through Qwen agreement.
- [Page review queue](quality/page_review_queue.csv) identifies failed GP
  layouts and unresolved constituency bands, including rows without IDs.
- [Alipurduar page audit](alipurduar_2018/page_audit.json) includes unparsed
  layouts, unresolved grids, summary/other-tier pages and rejected row bands.
- [Nadia document audit](nadia_2008/document_audit.json) retains GP control
  totals, unsupported rows, missing summaries and reconciliation failures.
- [Visual validation](quality/validation.json) compares fixed held-out
  readings with parsed fields, including missing rows and candidate votes.
  The [transcriptions](quality/heldout_gold.json) were made by one Codex
  reviewer from rendered originals. This small convenience sample is not a
  population accuracy estimate or human double-entry verification.
- [Block controls](quality/block_controls.json) preserve the six printed
  Alipurduar Annexure IA totals. Their comparison with extracted records is
  in the validation report. Total seats, seats where election was held and
  contesting candidates are different universes; do not equate them.

`source_controls_passed` and `automated_checks_passed` describe checks, not
certified accuracy. Draft/final status and district-wide completeness require
separate verification. A missing row or failed download is not evidence that
the underlying record does not exist.

## Reproduce

From the repository root, install the locked environment with
`uv sync --group dev --group table-ocr`. Image extraction also requires
Poppler (`pdfinfo`, `pdftoppm`, `pdftotext`) and Tesseract with English, Bengali
and orientation data. The development dependency group includes table-OCR
libraries so source-fixture tests run in a fresh environment.

```sh
make wb-parse-all
make wb-ocr-all
make wb-parsing-inventory
uv run pytest tests -q
```

Extraction resumes from source hashes and cache versions. Native caches are
keyed by PDF SHA-256; OCR caches retain source SHA-256, page, engine version,
rotation, deskew angle, ruling coordinates and word readings where applicable.
Alipurduar result OCR uses three Tesseract passes: original page, grid-removed
page and separate columns.
These share an engine and can share errors. They are not independent model
votes. Conflicting numeric readings are never resolved by forcing totals.

GP detail documents have explicit page scopes in `parse_results`.
Continuation pages may omit the GP title. PS results may reuse GP column
headings, so headings alone cannot safely identify the tier. In the mixed
Madarihat-Birpara PDF, GP details occupy pages 4–20; pages 21–23 are PS and
page 24 is ZP. All 176 archive pages are audited, including the other tiers.

The local Surya pilot was rejected: generation reached its token limit and
repeated rows. It was not used to populate or validate these tables.

## Interpretation and dictionary

Common provenance fields are `source_path` (repository-relative original),
`source_sha256` (original bytes) and `source_page` (one-based PDF page).
`source_html_row` is the one-based table row, including the two header rows.
Nadia additionally identifies `source_table` and `source_row`, both one-based.
`source_table_bbox` uses PDF points from pdfplumber. Alipurduar `source_bbox`
uses pixels after recorded rotation and deskew, in the OCR cache's DPI.
Coordinates are `[left, top, right, bottom]` with the origin at top left.

Identifiers (`row_id`, `candidate_row_id`, `seat_row_id`) are source-derived
hashes, not official GP or constituency codes. `seat_no` is the printed seat
number within a GP, with valid Roman suffixes converted to integers;
`seat_no_basis` records that conversion in Alipurduar. Do not join it without geography and election year.
No fuzzy name matching, historical boundary harmonization or external LGD
crosswalk has been applied. Duplicate keys are flagged rather than dropped.

In Hooghly, `seats_contested_printed` and `seats_declared_printed` retain the
HTML's own labels. Party columns contain seat counts, not votes or GP control.
`party_counts_sum` adds those ten columns, and
`declared_minus_party_counts` measures the gap to printed declared seats.
The party counts cover 2,033 of 3,440 declared seats; only 93 of 210 GP rows
have party counts covering all declared seats. Do not treat this as complete
party results or assign the gap to a party.

In Nadia, `block_printed` and `gram_panchayat` preserve document names.
`constituency_area_raw` retains the full locality description. `allocated_raw`,
`caste_raw` and `women_raw` retain the corresponding table cells. Multiple
allocated seats produce multiple rows, with reservation assigned only to
the referenced seat number. Blank or dash reservation cells mean no such
reservation within an identified Form A1 schedule. Unread or ambiguous
markers instead produce nulls and review flags.

Reservation values in Alipurduar are `SC`, `SCW`, `ST`, `STW`, `BC`, `BCW`,
`W` or `UR`; `reservation_raw` retains the reading. `caste_reservation` strips
the women suffix, with `UR` for an otherwise unreserved women's seat.
`woman_reserved` is 1 or 0 only when the category was interpretable. An `X`
or blank in the result scan remains unresolved; it is not mapped to `UR`.
Reservation describes the seat, not a person's inferred identity.

`gram_panchayat_printed` preserves Alipurduar's GP-column reading;
`gram_panchayat_basis` records whether the GP name instead came from the
printed constituency prefix. `seat_id_printed` preserves the constituency
reading. `serial_printed` is populated only when the serial cell spans the
seat; Alipurduar-I often numbers candidates instead, so this value is null.

`electors`, `votes_polled`, `votes_rejected` and candidate `votes` are integer
counts. `candidate_votes_sum` is null if any candidate vote is unread.
`candidate_count` counts recovered candidate rows, not an independently
known total. Names and parties are OCR readings; `winner_name` and
`winner_party` come from the printed declaration. A tied maximum is allowed.
Some Alipurduar-I totals disagree even in the printed source; the extraction
does not alter them. Its stale 2008 footer does not override the 2018 archive
and result heading.

`quality_flags` is a semicolon-separated set of unresolved conditions.
`review_status` summarizes those flags. Preserve the source and original
reading when correcting a field; record the reviewer, corrected value and
source page separately. Office outputs apply explicit source-pinned visual transcriptions, stored
separately from their original OCR readings. Numeric agreement and matching totals cannot certify names,
reservation labels, constituency identity or complete source coverage.

Office `quality_flags` retain disagreements observed in the original OCR even
after a source reading resolves them. Consult `review_status`, `review_note`
and the linked adjudication to distinguish resolved readings from open work.
The native-office `name_ambiguous` field is null for cells without a name review.
Its `evidence_references` field contains a JSON list of repository-relative
paths and SHA-256 hashes, validated before corrections are applied. Direct
manual entries without separate audit files retain their source pins and
review method with an empty evidence-reference list.

## Local Qwen evaluation

[Qwen review evidence](qwen_review/evaluation.json) records small, selected
pilots using the locally installed `qwen2.5vl:7b` through Ollama. Larger
source crops improved the first pilot; those small results are not a general
accuracy estimate. The [expanded sample design](qwen_review/expanded/design.json)
freezes 200 new GP-office cells before inference, excludes previous pilot
cells, and retains strata and inclusion weights. Source readers receive
blinded manifests. Predictions, reference readings, ambiguous cells and
adjudications remain separate; model agreement never silently replaces a
reservation value.

The sample frame consists of cells in the two office-grid parsers. It excludes
the separate Nadia handbook and visually transcribed Alipurduar 2018 roster,
and does not represent districts or years for which no source was acquired.
The two reference readers are visual agents, not human double-entry operators.

The [completed 200-cell evaluation](qwen_review/expanded/evaluation.json)
contains 106 positive cells and 94 blanks. Qwen matches 102/105 unambiguous
positive-cell names and 105/106 positive reservation categories. One name is
excluded as source-ambiguous. Whole-cell agreement is 182/199; nine invalid
JSON responses count as extraction failures. Among the 85 blank cells with
valid responses, four contain spurious model readings. The frozen Tesseract
baseline matches 82/105 names, 106/106 positive categories and 175/199 whole
cells. Qwen therefore helps identify name errors but does not justify
automatically replacing category or blank readings. All 20 cells read by both
reference agents agree. Raw counts are sample results; the JSON separately
reports design-weighted fractions for the acquired eligible frame, without
claiming statewide accuracy.

Source review identified one scoring artifact: `RAKHERA-BISPURIA- ST` had
left the category-separator hyphen attached to the GP name. The evaluator
now accepts whitespace after that separator while preserving internal name
hyphens. The [initial scoring report](qwen_review/expanded/evaluation_before_separator_fix.json)
is retained; no frozen reference or model prediction was edited.

Re-score the frozen references and cached predictions offline with:

```sh
uv run python -m local_reservations.states.wb.evaluate_qwen
```

The local inference runner is `local_reservations.tools.wb_qwen_review`;
it accepts the inference manifest and an `--output` cache directory. Its
network calls are kept outside the offline state parsers.

The runner uses Ollama's documented [local vision API](https://docs.ollama.com/api/generate).
Its cache pins image bytes, model digest, prompt and generation settings.
The office OCR caches additionally check crop fingerprints and Tesseract/TSV
reader versions, preventing old text from being reused against new geometry.
