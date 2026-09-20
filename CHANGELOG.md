# Changelog

What changed, and what it means for a number you may already have used. Entries
say when a figure moved and why, because a corpus that silently restates itself
is worse than one that does not change at all.

Corrections are listed first in each release, not last. The most useful thing
here is usually the thing that was wrong.

## v0.6.0 — 2026-09-20

### Corrected

- The evidence archives now include the national source collection and the
  pinned historical Haryana build input: 39,317 files in total. Earlier
  archives omitted these inputs despite the repository documentation.

- Bihar 2016 candidate rows now identify the 210,717 resolved winners by both
  source serial and row. Other candidates on those seats receive `elected=0`;
  unresolved seats retain missing flags. Previously all 2016 candidate elected
  flags were missing, although seat-level winners were retained.

- **Seats reserved for Scheduled Tribes were reading as open seats.** Bihar's
  2021 feed prints the category as "अनुसूचित जन - जाति", and the shared reader
  only allowed the two halves of *janjati* to be adjacent or separated by a
  space. A dash between them fell through to the unreserved test: 2,033 tribal
  seats carried no reservation and 672 reserved for tribal women read as open.
  If you counted ST seats in Bihar 2021, redo it.
- **A backward-class seat lost its stated gender.** "पिछड़ा वर्ग  (अन्य)" marks a
  seat as not reserved for a woman, but every backward-class label was ruled out
  before that word was read, because "अन्य पिछड़ा वर्ग" is itself a caste. Only
  the label that opens with अन्य is ruled out now. Uttarakhand's abbreviated
  "अन्य पि0वर्ग" still states no gender, which is correct.
- Haryana's comparison of its two GP-head reservation printings was carried onto
  every ward row of the GP, raising 1,392 ward-level `printings_disagree` flags
  for a comparison never made about a ward seat.
- Kruti Dev's shifted quote keys are स् and ष्, the half consonants, not the bare
  letters. सुषमा and सुष्मा are different names, and so are कश्मीरी and कशमीरी.

### Added

- UP inputs now come from its v2 release, with the exact state manifest and file hashes pinned. The separate office observations retain their provisional status and are not added to pooled seat counts.

- **Bihar 2021 enters as all six offices with the reservations it states**:
  247,671 seats, 924,708 candidates and 244,475 winners, against 8,067 mukhiya
  seats carrying no reservation at all before. The reservation comes from the
  portal's 2021-2026 term feed, which is undated; reservations are fixed for the
  term, and the adapter says so rather than letting the year pass unexamined.
- **Bihar 2016 is read from the sibling's re-collection** rather than the six
  loose CSVs: 227,317 seats against 219,117, each identified by the codes the
  form itself uses and pointing at the saved page it was read from. The scrape's
  651 double-captured seats are settled at the source, which fetches each form
  code once.
- Bihar is now the corpus's largest state at 474,988 seat events; the pooled
  total is 1,307,418 across 15 states.
- `winner_basis` gains `uncontested`, `lot` and `sole_candidate`. A seat nobody
  contested, a tie decided by drawing lots and a seat won by one vote are
  different facts, and calling them all `argmax_votes` said the count decided
  something it did not.

### Known limits

- 30,764 of Bihar's 2016 seats answer "Record not Found" and print no
  reservation. They are counted per tier and left out rather than entering as
  open seats.
- 402 of its 2016 seats name no winner: a shared top vote with no lot drawn, a
  serial listed twice with different counts, or two uncontested candidates.
- 21 samiti and zila parishad seat numbers are listed under two dropdown codes
  differing only in zero padding ("Tardih/01" and "Tardih/1"). In nineteen,
  exactly one code carries results and the other answers "Record not Found".
  Both rows are kept, flagged, and recorded in the collision ledger.

## v0.5.1 preparation — unpublished, included in v0.6.0

These notes record the September 10 preparation; its pooled total predates the Bihar additions above.

### Corrected

- UP's pooled adapter now includes the missing 59,019 GP-head records from 2015.
  Each record retains its source-file SHA-256 and one-based source-row locator.
  UP has 212,524 seat records across four election years; the pooled total is
  1,051,560. This does not add new states or establish complete UP coverage.
- One 2021 UP contest has two publisher-marked winners. The winner remains
  unknown, all 25 candidates are retained, and their elected indicators are null.
  The conflict flag and marked publisher IDs make the ambiguity explicit.
- The candidate table retains publisher candidate IDs instead of replacing them
  with within-contest positions. UP still has 373,096 candidate records.

### Source stewardship

- State repositories own state-specific evidence and parsers; the central
  repository consumes pinned outputs. The UP discovery archive preserves source
  bytes and acquisition receipts outside ordinary Git storage, with compact
  catalogs and member hashes retained in the state repository.
- Unfinished Haryana OCR and the experimental Sitapur parser are excluded.

## v0.5.0 — 2026-09-08

### Corrected

- Source preservation now covers raw WB, Tamil Nadu and early-search evidence,
  including originals and review images omitted by the parsed-table manifest
  or ordinary Git storage. `SOURCE_MANIFEST.json` maps every evidence file to
  a checksummed release asset; the standalone verifier checks archive members.
- Release validation checks live repository state and sibling commit pins,
  refusing stale provenance, missing files, changed bytes and incomplete archives.
- Native extraction caches now require matching source hashes. Frozen OCR
  review samples are checked against their recorded hash before reuse, so edits
  or reordered cells cannot silently change the review population.


- **The one Mumbai sheet that states a seat reservation states the 2012 draw,
  not 2007's.** `data/maharashtra/mumbai/BMC-2007_raw.xlsx` pairs the 2007
  council's winners ("Sitting Corporator") with a "Present Reservation" column
  listing 115 women's seats, the half quota in force from 2012, where the 2007
  council had 76. Ward by ward it agrees with the independently digitised 2012
  flag on 226 of 227 wards and with 2007 on 38. Nothing downstream had used the
  sheet, so no published figure moves, but any reader who had taken the column
  at face value had every ward's reservation attached to the wrong council.

### Added

- West Bengal source-specific exports cover historical Birbhum GP-head
  reservations, Nadia's 2013 head/deputy roster, later office and ward schedules,
  and election results. Office, ward, candidate and aggregate units remain
  separate; source pages, raw readings and review decisions are retained.
- Tamil Nadu's complete 2011 GO61 GP-president roster: 12,524 named entries,
  31 printed districts and 385 unions. One printed reservation cell remains
  blank, and source serial errors are flagged rather than silently repaired.
- Tamil Nadu's 2001 GP-president amendments: 456 operations (434 replacement
  rows, 17 insertions and five unnamed serial targets). All 451 named entries
  received a second visual check. These amendments have not been applied to the
  1996 base and are not a complete statewide 2001 roster. Both TN exports ship
  as CSV and Parquet with dictionaries and source-linked evidence; they remain
  outside the common master and do not identify winner sex.
- All 132 selected pages of the 1996/2001 early TN scans have preserved OCR
  artifacts. OCR alone is not a parsed roster. Additional early-state sources
  are preserved with acquisition and exclusion ledgers.
- The pooled rural master now contains 992,541 seat events, including the
  2,021 Rajasthan Zila Parishad seats added since v0.4.0. Supplemental WB and
  TN exports have distinct row units and are not added to that total.


- **Maharashtra enters the schema with Mumbai's 2012 and 2017 councils: 454
  `ulb_ward` seats, 227 per council.** The 2012 reservation comes from the sheet
  above, the 2017 reservation from the Karekurve-Ramachandra & Lee (2025)
  replication deposit (Harvard Dataverse doi:10.7910/DVN/IO9SLQ, CC0), which the
  authors digitised from the State Election Commission's handbooks and which is
  held under `mumbai/dataverse_IO9SLQ/` with a manifest. Winners come from a
  2012 scan transcription (202 of 227 named) and the 2017 result export (226 of
  227; ward 78's name is lost to encoding, ward 220's tie is settled by the
  deposit). The validator checks the statutory women's and Backward Class
  shares, the 2012 reservation against the deposit's flag (ward 172 is the one
  disagreement and is kept as printed), and winner names against the deposit's
  councillors. Urban rows are excluded from the pooled master by design, so the
  rural total is unaffected by the Mumbai addition.

- **Supplemental Mumbai files that carry no reservation column and stay out of
  the pooled machinery:** the 2007 seats with the women's flag only
  (`bmc_seats_2007.csv`; caste reservation unknown), candidate tables for 1997,
  2002, 2012 and 2017, and the Praja Foundation's ward-by-wave citizen ratings
  of councillors for 2011 to 2018 (`praja_ward_ratings_2011_2018.csv`). In the
  ratings the satisfaction item is inverted in the 2018 wave (its correlation
  with the thirteen service items is +0.44 in 2016 and -0.33 in 2018); the
  row carries `satisfaction_inverted` rather than a repair.

- `openpyxl` and `xlrd` join the runtime dependencies; the Mumbai files are the
  first spreadsheets the package reads.

## v0.4.0 — 2026-08-30

### Added

- **Rajasthan adds all 10,530 Panchayat Samiti member seats from the 2005 and
  2010 general-election result books.** Each seat retains its reservation
  separately from the elected member's name, sex, category, party, votes, and
  margin where the source prints them. Rajasthan now has 160,481 rural seat
  events and the pooled corpus has 990,520, up from 979,990 in v0.3.0. The 2005
  parser accounts for 5,257 seats, 32 districts, 237 Panchayat Samitis, one
  vacancy, and 127 uncontested winners. The 2010 parser accounts for 5,273
  seats, 33 districts, and 248 Panchayat Samitis.

- **The source pipeline separates extraction from parsing.** Retained JSONL
  artifacts store 117,595 positioned words from 214 source pages. The parsers
  read only those artifacts and emit structured JSON logs. Each year has a data
  dictionary declaring the seat key, fields, recodes, and validation controls.

### Corrected

- **Source anomalies remain visible rather than silently changing the
  record.** The 2005 roster prints Parbatsar ward 19 as `OBC W`, while its body
  control and the statewide control imply `OBC`; the roster value remains and
  the pooled row is flagged. One filled seat has a blank winner name, and three
  margins exceed the printed winner votes. Shahbad ward 11 remains in the data
  as a vacant seat. In 2010, Rajsamand–Bhim's 16-row roster prints its last ward as 17 after
  wards 1–15; `ward_no_raw=17` is retained and the seat key uses 16, consistent
  with the publication's independent 16-constituency control. Serial 71 prints
  winner sex `M` but winner category `OBCW`; neither is overwritten, and the
  pooled row carries `winner_category_sex_disagree`.

### Changed

- **The remaining Rajasthan work is now stated precisely.** The held 2015
  Panchayat Samiti book and all held Zila Parishad books remain unparsed;
  municipal holdings remain outside the rural master.

## v0.3.0 — 2026-08-29

### Corrected

- **Rajasthan's structured SEC scrape is no longer left outside the pooled
  data.** The earlier adapter read only four sarpanch reservation panels. It
  now uses all 68,202 sarpanch-candidate records, 11,432 sarpanch-result
  records, 110,296 ward-result records, and 13,473 nomination summaries. The
  two result files link on exact event and place keys; no fuzzy match is used.
  Four 2020 roster seats have no scraped contest, and thirteen by-election
  contests have candidates but no result, so both limits remain explicit.

- **Gram-panchayat identifiers now survive the pooled projection.** The shared
  schema carries `gp_no` as a string, including J&K identifiers such as `14K`,
  rather than relegating 31,939 values to the extras table. This resolves 108
  false seat-key collisions without adding or dropping a row.

- **Uttar Pradesh and Rajasthan no longer merge distinct panchayats that share
  a cleaned name.** UP now promotes its published `gp_code` into `gp_no`,
  resolving 359 of its 363 collision rows. Rajasthan uses the printed GP name
  for seat identity and retains the sibling repository's standardized name as
  a non-key linkage field, resolving 34 of its 41 collision rows. No record is
  dropped; the remaining four UP and seven Rajasthan rows stay in the collision
  report for source review.

- **Karnataka's published GP identifier now controls pooled seat identity.**
  All five president cycles promote `gp_code` into the shared `gp_no` field,
  resolving all 82 Karnataka GP-head collision rows across 35 groups without
  adding or dropping a record.

- **Kadapa applies the gazette's own 41-row errata instead of silently
  overwriting the original cells.** The positioned parser reads 807 GP heads
  and 7,903 wards,
  checks every mandal against the gazette's printed 807-GP/50-mandal
  abstracts, and applies all 41 rows in the later errata only after each `For`
  value agrees with the original table. Corrected rows retain the original
  cell, `For`, `Read as`, and correction page.

### Added

- **Rajasthan adds 110,431 rural seat-event records.** Its pooled file now
  contains 39,655 GP-head and 110,296 GP-ward records for 2005--2022, up from
  39,520 GP-head rows alone. A 68,202-row candidate sidecar retains gender,
  age, caste, education, occupation, marital status, assets, and child-count
  fields; public contact fields are deliberately excluded. The 13,473 GP-event
  nomination summaries remain a separate typed table because they are not seat
  or candidate records. The pooled corpus grows from 869,559 to 979,990
  seat-event records, with 1,202,319 candidate records.

- **Andhra Pradesh and Jammu & Kashmir add 36,637 pooled seats.** Kurnool adds
  972 GP heads and 9,987 wards; Kadapa adds 807 heads and 7,903 wards. After
  the reviewed parser also removes a net 35 rows from the six earlier AP
  districts, AP grows by 19,634 rows to 80,021 across 8 of 13 held district
  gazettes. J&K grows by 17,003 rows: 5,676 wards from 2010, plus 1,353 GP
  heads and 9,974 wards from the complete set of 25 held 2016 PDFs.

- **Assam and Gujarat add 2,856 rural seats.** Assam contributes 1,678 seats
  from the 2025 Charaideo, Kamrup Metropolitan, South Salmara-Mankachar, and
  Hailakandi
  orders; Gujarat contributes all 1,178 block- and district-panchayat seats in
  the 2020 rotation orders.

  Assam's local files also retain 610 reserved-only municipal rows from 2020,
  which are excluded from the rural master. All 27 Assam district PDFs are
  held; four are parsed and 23 remain explicitly marked held/unparsed rather
  than being presented as statewide coverage.

- **The source documents now retain distinctions that a single reservation
  label loses.** Assam keeps the printed SC and ST counts independently,
  including `0/0`, `0/1`, and `1/0`, and expands merged gram-panchayat cells
  over every ward they span. Named constituencies, vice-head offices, and the
  block and gram-panchayat hierarchy survive into the common schema.

### Changed

- **The optional Apple-Silicon OCR environment now uses Savitr 0.3.0.** This
  removes the obsolete Pillow 10.4 compatibility pin and resolves the Pillow
  security advisories reported against the lock file.

- **The pooled key now distinguishes election events.** `election_type` and
  `election_duration` are shared seat and candidate columns and part of the
  seat key. Rajasthan seats that recur in later by-elections therefore remain
  separate events rather than false duplicate seat-years.

- **Acquisition, text extraction, and parsing are separate stages.** New
  source pipelines can fetch once, inspect or replace the extracted text, and
  re-run deterministic parsers without touching the network. Commands emit
  structured JSON run records with source, stage, counts, duration, and
  outcome, and source-specific expectations fail on missing pages, rows, seat
  runs, or reservation combinations.

- **Coverage reporting now distinguishes source records from pooled seat
  events.**
  Candidate-level sibling files can contain several records for one seat; the
  state table reports those source records, while the master remains the
  comparable one-row-per-seat-event view. Parquet counts come from file
  metadata. Other held PDFs are distinguished from rows they do not source,
  and Bihar remains correctly shown as parsed.

- **Rajasthan now comes from `local_elections_rajasthan`.** Its four published
  sarpanch panels and 2020--2022 SEC scrape now point to the maintained state
  repository instead of the paper-specific `quota_raj` repository.

- **Development installs and CI now use uv's native build backend and shared
  checks.** Hatchling is gone; dependencies use the canonical `test` group,
  CI covers Python 3.12 and 3.14, and formatting is enforced. The project is
  marked `Private :: Do Not Upload`: the released product is the GitHub data
  package pinned by `MANIFEST.json`, not a PyPI distribution.

- **The master has 976,936 distinct seat-event keys (99.7%) and 3,054
  collisions,**
  compared with 824,987 (99.4%) and 5,079 in v0.2.8. The release checks the
  declared seat-event grain, provenance, hierarchy, and reservation fields
  before writing the manifest.

## v0.2.8 — 2026-08-14

### Corrected

- **Haryana 2022 was publishing a phantom copy of some seats.** Palwal/Prithla
  prints its notification twice, English then Hindi, and pdfplumber returned the
  Hindi pages as *two* tables over one fully-ruled seven-column grid. The
  right-hand half holds `[father, office, reservation]`, so the parser — which
  anchors on the office cell — read every one of those rows happily, taking the
  **father as the winner with no ward number**. Prithla held 68 gram panchayats
  in a block that has 34, and one of the 68 was a person's name.

  **If you counted Haryana 2022 ward seats or joined on winner, redo it.**

      rows with no ward number   719 -> 259
      ward-number holes          713 -> 576
      Haryana rows in the master 135,460 -> 135,073

  The row count falls because the phantom printing is gone, not because seats
  were lost. 2016 is byte-identical.

  The 26 affected pages are now read with Surya, which returns them as rows of
  seven with the wrapped cells merged, and the reading is cached and committed
  so a re-parse never needs the model. 26 pages of 1,606 — the damage was
  concentrated in two documents rather than spread across the state.

  Verified across languages: page 2's Hindi rows for अमरपुर map onto the parsed
  English ones exactly. The one disagreement found is real and already carried
  in the data — a sarpanch seat reads `Backward Class 'A' Women` in English and
  `पिछड़ा वर्ग क महिला के सिवाय` in Hindi, and the row has `printings_agree = 0`.

## v0.2.7 — 2026-08-14

### Added

- **West Bengal is complete: 825 zila parishad seats**, up from 819. That is
  the state's published total, and it was not a number available to the parser.

  The six were all numbered ZP-1 or ZP-2, in three districts. `column_edges`
  reads the column boundaries off the gazette's own `(1)(2)(3)(4)(5)` marker
  row and the caller carried them only forward, so a page whose markers the OCR
  did not resolve had none and was skipped whole. Bankura page 1 holds
  `Saltora/ZP-1` and `Saltora/ZP-2`, both read perfectly, both dropped.

  Three outside numbers hold: 825 published, women **49.5%** against a
  statutory half, SC **26.7%** and ST **6.2%** against roughly 23% and 6% of
  the state's population.

### Changed

- **One name per block.** The block name is printed on every one of its
  constituency rows and did not survive identically each time — `Beldanga-II`
  and `Beldanga -II`, `Suti - II` and `Suti - Il` with a capital i for the
  second numeral. Each variant became a block of its own, which is what made
  the gazette's own arithmetic disagree on 20 blocks. **If you grouped West
  Bengal rows by `block`, you had up to three groups per block.**

  The published spelling follows the page: Murshidabad page 2 prints `Suti-I`
  and `Raghunathganj-II` with no space around the hyphen.

- **The parser distinguishes a misfiled seat from a missing one.** Every
  district enumerates a complete `ZP-1..N` run, so the 12 blocks whose stated
  member count still disagrees are seats attributed to the wrong block, not
  seats lost — `Suti-I` states 2 and enumerates 3 while `Suti-II` states 3 and
  enumerates 2, the totals matching exactly. Previously "20 blocks disagree"
  read as 20 missing constituencies.

  14 blocks state a member count that did not survive the scan — Bankura's
  Indpur reads `Zz` where the page prints 2. Left unreadable rather than
  guessed: the only certain repair is the number of constituencies enumerated,
  which is the very thing the check tests.

## v0.2.6 — 2026-08-14

### Added

- **West Bengal: 819 zila parishad seats across all 20 districts**, from the
  2018 delimitation-and-reservation gazettes. The thirteenth state, and
  830,447 pooled seats.

  Three external numbers agree with it, none of which anything here was tuned
  against: women 49.3% against a statutory half, SC 26.7% and ST 6.1% against
  roughly 23% and 6% of the state's population. 123 seats are printed in both
  a draft and a final gazette and 117 agree, which is two independent scans of
  two independently typeset documents saying the same thing.

  **Known and not hidden:** the gazette states how many members each block
  elects, and that disagrees with the constituencies enumerated on 20 blocks of
  about 340. A further 13 blocks state a count that did not survive the scan —
  Bankura's Indpur reads `Zz` where the page prints 2. Neither is guessed at:
  the only repair certain to be right is the number of constituencies we
  enumerated, which is the very thing that check exists to test independently.

### Changed

- **51 slices stopped skipping their strongest check.**
  `women_share_vs_statute` compares a slice's women's share against a legal
  requirement, so agreement is evidence rather than circularity. It was running
  on 10 of 63 slices; the other 53 skipped for want of a declared rule, and a
  skip reads exactly like a pass in a green build.

  Article 243D(3) of the Constitution is now the default — *not less than
  one-third of the seats filled by direct election in every Panchayat shall be
  reserved for women*, every state, every tier, since 1993.

      women_share_vs_statute:  10 pass / 53 skip  ->  61 pass / 3 skip

  Every slice passes at that floor. This is deliberately the floor and not the
  stronger rule: about twenty states including West Bengal legislate one-half,
  but those amending statutes could not be retrieved to cite, and a share taken
  from the data it is meant to test is not a check. Declaring a confirmed
  statute in `reference.WOMEN_RULE` tightens any slice.

## v0.2.5 — 2026-08-14

### Corrected

- **7,248 Bihar rows said `script = devanagari` while every word in the row
  read Latin.** v0.2.4 stopped adapters hardcoding the value, but it was then
  derived per *candidate*, and `collapse.to_seats` merges many candidates into
  one seat — so a seat could carry the script of a name it does not show.
  `script` is now derived in one place, from the row it labels. **If you
  filtered Bihar on `script`, redo it.**

  Rows whose script contradicts their own text: 304,823 before v0.2.4, 7,267
  after it, **0 now**, across all 829,628 rows. A test holds them there.

### Changed

- **Three copies of `page_count` became one**, and three identical copies of
  `pct` moved to `common/checks.py`. Checked and left alone: `clean` appears in
  five parsers with five different bodies, because each strips what its own
  documents carry. Same name is not the same function.

## v0.2.4 — 2026-08-13

### Corrected

- **304,689 rows said the wrong script — 36.7% of the corpus.** Every adapter
  hardcoded the value, `"script": "latin"` on one row builder and
  `"devanagari"` on the next, so Uttar Pradesh declared latin over 103,729 rows
  of Devanagari and Bihar declared devanagari over 200,960 rows reading
  `RAMADHAR YADAV`. It is now read from the row. **If you filtered or grouped
  on `script`, redo it.** 0.88% remain mislabelled, only 22 of them a winner
  rather than a place name.

  Found by a check written to prove something else: "a row whose script is
  latin must not acquire a Latin reading" failed on 102,395 UP rows. The join
  was right; the column was wrong.

- **`name_untransliterated` now lifts where a row has a Latin reading.** It
  fires on 12,103 rows, of which 4,366 are Karnataka's Kannada. Previously it
  tracked the script label; now it tracks the difficulty it names.

### Added

- **Latin readings for 227,903 rows** — `winner_latin`, `district_latin`,
  `block_latin`, `gram_panchayat_latin`, from the transliteration stage added
  in this release. Names that were only in Devanagari can now be searched,
  joined and compared against an outside register.

  These are **machine-generated and never replace what a source printed** — the
  gazette's text stays exactly as it was, and the Latin form sits beside it.
  158,931 distinct names were transliterated with `indicate`'s offline model,
  chosen over its LLM backend because it is deterministic and a release pins a
  SHA-256 for every file. 2.7% of readings were flagged and are **withheld from
  the master**, kept in `data/transliteration/` with the reason.

  Kannada is deliberately not done: no offline model exists and the LLM backend
  is not reproducible, so 7,781 strings stay untransliterated rather than put a
  non-deterministic stage behind a manifest that promises reproducibility.

### Changed

- **Transliteration is a stage, not a step inside a parser** — `collect →
  parse → transliterate → pool`. It writes a committed lookup keyed on the
  name, so the work happens once per name rather than once per row, and a
  correction to one name fixes every row that carries it. `make transliterate`.

## v0.2.3 — 2026-08-13

### Corrected

- **Andhra Pradesh under-counted women's seats, and it was a bias rather than a
  shortfall.** 1,754 ward rows stated a caste and no gender. Nellore, Prakasam
  and Anantapur mark *both* the women's and the open seats, so a bare `UR`
  there is unknown rather than male — and the markers are not lost at equal
  rates, so a women's share computed over those districts was wrong in a
  direction. **If you computed a women's share for AP 2020, redo it.**

  The cause is the OCR mode. `--psm 4` preserves the layout the parser reads
  positionally and pays for it by gluing the ruled table's own lines onto the
  cells: the marker arrives as `IBC)`, `|URW)`, `[URW`, `JURG)`, the opening
  bracket read as `I`, `|`, `[` or `J`. A second pass at `--psm 11` reads the
  same page far more cleanly and is matched back **by position** — a cell takes
  a reading only where exactly one clean token sits in the same place, so it
  can never assert a gender the document does not state.

      gender unstated                                 1,754 -> 1,174
      ward_list_complete = 1                         36,858 -> 37,642
      panchayats parsed short of their stated count      223 -> 203

### Known, and not fixed here

- **`ward_list_complete` can report a panchayat complete against a misread
  count.** Tesseract reads the "No. of Wards" column wrongly on 23 lines —
  Alurupadu prints 8 and reads 4 — and the parser truncates the ward list to
  it. Those rows then satisfy the completeness check while holding half their
  wards. This predates the correction above and is why Alurupadu now holds 4
  wards where a misaligned parse used to spill 7 of its 8.

## v0.2.2 — 2026-08-13

No data changed. Every value in every master table was compared against v0.2.1
column by column; only `source_commit`, the build's own provenance stamp, moved.

### Changed

- **The scripts are a package.** `scripts/` became
  `src/local_reservations/{common,states,tools}`, tests moved to `tests/`, and
  no file manipulates `sys.path` any more. 32 of 74 did, and it was not
  cosmetic: it is why a module named `http.py` in the shared layer would have
  shadowed the standard library's `http` package and broken `requests`, and why
  one named `surya.py` would have shadowed the real `surya` package.

- **One repository root.** 42 modules each worked it out by counting parent
  directories, which is a silent assertion about where a file sits. It is now
  `local_reservations.paths.ROOT`, found by walking up for a marker. The proof
  it was needed: a test located a sibling repository by counting parents and,
  after the move, did not fail but **skipped** — reporting a checked-out
  sibling as absent.

- **pyproject + uv.lock.** The `pyarrow==23.0.1` pin was documented as
  load-bearing and enforced by nothing. Parquet stamps its writer into every
  footer, so a different version rewrites every hash in MANIFEST.json without
  changing a value.

- **The OCR dependencies are a conflicting dependency group.** savitr pins
  `pillow<11` where pdfplumber needs `>=12.2`;
  `uv run --no-default-groups --group ocr` replaces the hand-made `ocrenv/`,
  and uv refuses to install both rather than leaving whichever came second
  broken.

- **Fleet tooling via preen**, minus the parts built for shipping a package.
  The release workflow was removed rather than left in place: it fires on `v*`
  tags and can publish to PyPI, and this repository's tags are data releases
  gated by `release_check.py`. ruff went from 741 findings to zero.

### Corrected

- **A `TypeError` that had not fired yet.** `collapse.py` computed a
  two-candidate seat's margin as `top - runner`, where `votes_of()` returns
  `None` where a source recorded no count — its own docstring insists None is
  not zero, and Bihar writes 24 seats with no numeric vote plus one reading
  `"986+1 (BY LOT)"`. Found by pyright; a margin against an unknown is now
  blank, which is what blank already meant there.

- **An undeclared dependency that was silently dropping rows.** The first build
  inside a locked environment reported `quota_raj: pandas is not importable, so
  the parquet slices are skipped` and produced 39,520 fewer Rajasthan rows. The
  system interpreter happened to have pandas; nothing said the corpus needed
  it. It is declared now.

## v0.2.1 — 2026-08-12

### Corrected

**Haryana ward reservations were wrong in three ways, and every version up to
and including v0.2.0 shipped them.** The gazettes are clean — this was ours.

- **1,678 rows named a person "Ward 1".** Karnal and Palwal 2022 print each
  notification twice, Hindi then English, and the English ward column reads
  `Ward 1` where the Hindi reads `1`. The parser tested `isdigit()`, which is
  false there, so the cell stayed put and every field after it shifted one
  place right: the ward label landed in `winner` and the winner's name in
  `father_husband`. **If you counted distinct winners in Haryana 2022, 1,678 of
  them were column labels.**

- **1,014 rows carried the neighbouring seat's reservation.** Where a category
  wraps, the ward digit and the category are top-aligned in their cells while
  the name sits lower, so one printed line comes out as two rows. `split_row`
  anchors on the office cell, so the half holding the ward was discarded — and
  the continuation logic, which is correct for tails that belong to the row
  *above*, then attached that category to the **previous** seat. Ajit Nagar's
  ward 1 was published as Unreserved; the gazette says Backward Class. **If you
  used Kaithal, Mewat or Sirsa 2016 ward reservations, redo it.**

- **Rows were deleted by a typo in the gazette.** `normalize_reservation`
  returned `None` for `Unresreved`, and a `None` reservation does not blank a
  field — it discards the whole row, the elected member's name with it. Ambala
  prints that misspelling 79 times. Barnala shipped five of its nine panches
  and every count said the table was full.

  2016: 61,618 → 61,879 ward rows, 1,014 → 164 without a ward number
  2022: 1,678 → 719 without a ward number, 639 → 0 named "Ward N"
  Pooled seats: 829,351 → 829,593

### What made these invisible

None of the three appeared on any gap list, because a gap list counts rows that
have a problem and these rows had been deleted or silently rewritten. The check
that finds them is the one Karnataka already had and Haryana did not: **a
panchayat's wards are numbered 1..N, so a seat nobody read shows up as a hole.**
`validate.py` now runs it, along with checks that no ward number repeats, that
every seat states one, and that no winner is a column label.

It reports what is still wrong rather than hiding it: 159 panchayats in 2016
and 344 in 2022 still have a gap. Some of those are real — a seat can go
unfilled — and some are still ours.

Duplicate ward keys rose by 10 in 2022, which is not a regression. Those rows
had no ward number before and so collided with nothing; numbering them
correctly revealed that Chirao and Babain each hold two panchayats sharing a
name — a separate defect that was invisible while the rows were unnumbered.

## v0.2.0 — 2026-08-12

### Added

- **Karnataka's 2016 taluk and zilla panchayat members: 4,366 seats across
  30 districts and 166 taluks.** Two tiers the corpus held no row for, and the
  state's first winners — everything Karnataka had before was a gram panchayat
  reservation roster for 1993–2007, which names nobody by construction. 3,478
  taluk panchayat seats against the 3,884 the state polled, and 888 zilla
  panchayat against 1,083; the archive holds 169 of 176 taluks and 26 of 30
  zilla panchayats, so the rest was never captured rather than lost here.

- **A `party` column with something in it.** These notifications print the
  party the winner represented, which almost nothing else in the corpus does:
  Congress 1,852, BJP 1,460, JD(S) 632, Independent 178, JD(U) 5. It is
  canonicalised against a fixed list and left **blank rather than guessed**
  where the cell does not settle the question — a reading truncated to
  ಭಾರತೀಯ fits both of the two largest parties. 237 rows are blank on that
  basis, and `party_local` keeps what the page actually said.

- **Every row says where its document came from.** `source_url` and
  `source_capture` join from the harvest manifest, so a row refetches the exact
  bytes it was read from. `source_path` and `source_page` already said which
  file and which page; nothing said which URL.

- **`scripts/archive_sweep.py`** asks all 31 state election commissions what
  the web archive holds for them — 23 resolve, ~14,000 PDFs. Karnataka's 828
  are what this release came from, and they were found by accident before this
  existed.

### What to know before using the Karnataka rows

- **50.1% of seats are reserved for women**, against the 50% the Karnataka
  Panchayat Raj Act requires. That comes from a column nothing here was tuned
  against and is the best evidence available that the reservation is read
  correctly. Caste: 2,224 unreserved, 864 BC, 854 SC, 424 ST, with BC split
  A/B in `caste_reservation_local` because Karnataka reserves for them
  separately.

- **6.6% of rows have no resolved party.** That is the honest measure of how
  many cells did not read cleanly, not a claim that those seats were
  independent — `Independent` is a value in its own right, 178 of them.

- **Three of 195 documents contribute nothing, and 25 of 586 pages.** Both are
  printed by the parser rather than left to be inferred from a row count.

- **~100 rows carry no constituency number**, so they share a seat key within
  their taluk. Those documents print only a name where others print `1-name`;
  where a document's serials run 1..N they are adopted and flagged
  `seat_no_from_serial`, and where they do not, the number is left empty rather
  than invented. Carried on the worklist.

- **24 documents lose a seat**, usually where a row straddles a page break, and
  Bidar loses two more to three washed-out rows at the top of a page. Every gap
  is reported: a taluk's constituencies are numbered consecutively, so a lost
  row shows as a hole rather than as a plausibly short table.

### Changed

- **Uttar Pradesh and Rajasthan are `parked`, not open gaps.** Their remaining
  entries are real and are deliberately not being worked; open gaps fell from
  60 entries to 51. Rajasthan's 2020 is the clearest case — quota_raj declares
  `winner_name_2020` and never fills it, 0 of 7,882 rows where 2015 is filled
  on all 7,882 — so no amount of parsing here closes it.

- **All archive traffic is rate-limited properly.** `requests-ratelimiter` and
  urllib3's `Retry`, in one adapter, honouring `Retry-After`. The Internet
  Archive firewalls an IP for an hour if 429s are ignored for a minute, and the
  previous hand-rolled sleep loop never read the header.

- **Karnataka's other 244 harvested documents are deliberately not parsed.**
  211 reservation gazettes restate a reservation these notifications already
  print; 33 gram panchayat 2015 files name nobody, being nomination counts,
  turnout and district totals. Recorded in `data/karnataka/readme.md` and
  `SOURCES.md` so the decision is not made twice.

### Corrected

- **The archive sweep could report a state as holding nothing when the archive
  had simply not answered.** Gujarat came back as 614 PDFs and then 0, Odisha
  817 then 0, Mizoram 0 then 168. An unanswered question and an empty answer
  now cannot share a value, and a state whose query fails carries its previous
  number forward marked stale.

## Unreleased — v0.1.1

### Corrected

- **17,115 winner names shipped as mojibake, labelled as Unicode.** Jharkhand's
  parser transliterated `block` and `gram_panchayat` from Kruti Dev and never
  `winner`, then stamped `script = devanagari` on the row regardless. So
  अनिता देवी appeared 92 times as `vfurk nsoh` and 55 times as अनिता देवी — the
  same woman, counted as two people, in a column that said the encoding was
  clean. **If you joined v0.1.0 on winner name, redo it.** She is now one person,
  147 times, and `script` describes the row rather than asserting about it.

- **A caption was published as a place name.** The seat identifier puts its
  number after "territorial constituency no.", and only the Kruti Dev spelling of
  that label was recognized, so on a Devanagari page the caption itself became
  the gram panchayat. 18 rows named `प्रा0नि0क्षे0 सं0` instead of a place.

- **501 seats were published twice.** Two readers of the same page rendered one
  person differently — `1 रेखा देवी` against `रेखा देवी` — and the dedupe keyed
  on the name. Panchayat samiti read 109% of the seats Jharkhand has.

### Changed

- **Jharkhand is read per document by whichever reader worked.** All 117
  documents were OCR'd with Surya and scored against their own text layer. The
  model wins on 88 and fails on 29 — those PDFs set Devanagari in Kruti Dev
  without embedding it, so the page renders as raw Latin codepoints and the model
  transcribes the wreckage. Preferring OCR everywhere would have cost 3,206 rows;
  the text layer everywhere would have cost about 1,500.

  | | v0.1.0 | v0.1.1 |
  |---|---|---|
  | Jharkhand rows | 23,599 | 27,698 |
  | mukhiya, of published | 84.1% | 93.3% |
  | panchayat samiti | 91.5% | 94.2% |
  | `gp_ward` seats that cannot be told apart | 8.1% | 3.2% |
  | seat identifiers still drawn as pictures | 1.9% | 0.7% |

  **The trade, so nobody has to find it themselves:** rows naming no panchayat
  rise from 2.9% to 3.5% of `gp_ward`, and rows with no seat number from 2.3% to
  3.9%. 4,099 seats were recovered that did not exist in the corpus before, and a
  larger share of *those* are incompletely identified.

### How to read "94% of published"

Not as precision. Coverage compares rows we hold against the seat count a state publishes, and
a reader that **invents** rows scores better on it than one that does not. Jharkhand's mukhiya
count read 102% of the gram panchayats the state has before any of this work — impossible, and
it looked like excellent coverage.

Both readers here get pages wrong in both directions. On one Ranchi page the model returned
nothing, the text layer returned four rows, and the page holds three. So coverage is a
floor-and-ceiling sanity check, not an accuracy measure, and the honest error bar on any
per-state figure in this release is wider than the figure's own precision suggests.

### Known and not fixed

- **`seat_id_raw` is still Kruti Dev on 66% of rows** — `I x<+ok@01@01&lq.Mh`.
  It is the raw record, and for the 29 documents whose render is broken it is the
  only form available. Installing the font and re-rendering those would close it.

## v0.1.0 — 2026-08-10

The first tagged release, and the first time the whole corpus is pinned by hash.

### Corrected

- **A worklist note had been false for two commits.** `panchayat_not_named` told
  every reader that Jharkhand's scanned districts named the panchayat on 34% of
  rows against 92% for the typeset ones, and prescribed re-OCR. Measured against
  the parse it shipped with: **99.9% against 96.2%** — the scanned districts were
  the *better* arm, and 519 of the 524 rows still unnamed were in digital-text
  documents that re-OCR would never touch. The claim outlived the two commits
  that made it false (`1c858f4`, `5144d09`). WORKLIST.md is generated from these
  notes, so the false statement shipped with the data. Now rewritten, and the
  three defects behind those rows named separately.

- **Koderma's 261 unnamed rows were not a naming failure.** On pages 30–35 of its
  notification the seat column is *drawn*, 33–51 embedded images a page, so the
  text layer keeps only the district's roman numeral and every row reads `VI`.
  This is the same defect already documented for Lohardaga, and it is now read:
  drawn seats recovered across the state go from 135 to **1,235**.

- **18 rows named a caption rather than a place.** The identifier puts its number
  after "territorial constituency no.", and only the Kruti Dev spelling of that
  label was recognized, so on a Devanagari page the caption itself was published
  as the gram panchayat. A reader joining on the name got a match that was not a
  place. `बगदा` and its neighbours are now read correctly.

### Changed

- **The per-state tables are parquet, not gzipped CSV.** Reading a state table
  drops from 0.80 s to 0.06 s, which a consumer pays on every grouping. Types come
  from `dictionary.py` rather than inference, so a ward number of `07` cannot be an
  integer in one state and a string in another, and **null is now distinct from
  blank** — `woman_reserved` unknown and `woman_reserved` false are different
  facts, and CSV could only write both as the empty string.

  A value that will not cast now stops the build. That found two real parser
  defects rather than two reasons to loosen a type: Uttarakhand was writing whole
  constituency strings such as `17-गुलडिया` into `seat_no`, declared an integer,
  and Goa was writing `Unopposed` into `votes`.

  `pyarrow` is pinned, and the manifest records the version that wrote it, because
  parquet stamps its writer into every footer — upgrading it rewrites every
  SHA-256 without a single value changing.

- **`master_dropped.csv` and `master_key_collisions.csv` stay CSV.** Neither is the
  published product; they exist to be opened by someone chasing a defect, and a
  format you cannot grep is the wrong one for that.

- **Jharkhand's scans are read with Surya, not tesseract.** Tesseract read this
  form's Devanagari reliably and its numerals badly — the separators of a seat
  identifier survived and the digits between them came back as commas, so
  `IV/चतरा /5/18/सलैया –(1)` was read as `[४/चतरा /5,//8,//सलैया -(7)`. Worse than a
  blank: `18` arriving as `8` is a plausible wrong value pointing at a different
  seat.

  Measured on a seeded sample of 22 pages across 10 documents, scored by whether
  the identifier resolves to a complete seat identity:

  | | tesseract | Surya |
  |---|---|---|
  | complete seat identities | 106 | 350 |
  | recovery rate | 28.6% | 91.4% |

  No document scored worse. Chatra went from 4/133 to 133/133.

  **Checked against known answers, not only against itself.** Parseability is
  not accuracy: a wrong digit parses as happily as a right one, which is how
  tesseract's reading of सलैया's panchayat as 8 rather than 18 passed every
  check for so long. The digital-text districts are the only pages here whose
  answers are already known — a typesetter wrote them, so their block, panchayat
  and ward numbers come out of the file rather than out of a camera. Rendered to
  images and re-read, Surya got **245 of 245 digits right**. Those pages are
  cleaner than a photocopy of the same form, so this bounds scan accuracy from
  above rather than measuring it; it is a necessary result, not a sufficient one.

  What moved in the corpus:

  | | before | after |
  |---|---|---|
  | Jharkhand rows | 23,599 | 26,555 |
  | `gp_ward` rows that cannot be told apart | 1,161 | 92 |
  | open gaps, excluding the missing-district estimate | 3,828 | 3,032 |
  | districts holding more heads than gram panchayats | 292 | 131 |
  | seats uniquely keyed, whole corpus | 99.1% | 99.2% |

  Mukhiya falls from 4,429 to 3,654 and that is the correction, not a loss. The
  old figure was 102% of the 4,345 gram panchayats Jharkhand has, which cannot
  happen; Latehar alone claimed 407 heads for about 116 panchayats.

- **`data/jharkhand/ocr/` is now committed** (~4 MB). It was ignored while
  tesseract produced it, on the grounds that anyone could regenerate it from the
  committed PDFs in forty minutes. Surya needs an Apple-Silicon Mac and about six
  hours, so ignoring it would have left one machine in the world able to rebuild
  the state.

### Fixed

- **Seat numbers printed with a trailing hyphen** were not read. `SEAT_TAIL`
  recognized `(01)`, `¼01½` and `&01`, but the panchayat samiti form prints
  `XII दुमका/04/काठीकुण्ड-01`. Three documents resolved no seat number at all for
  want of it — on tesseract and on Surya alike, so it was a parser gap rather than
  a scan one. **+393 seat numbers, no row whose value changed.**

- **Kruti Dev place names split down the middle.** `/` is both a separator and the
  letter ध, guarded by "a separator is never followed by `k`" — but ध is written
  `/k` in खरौंधी and `/;` in `e/; ckxcsM+k`, which is मध्य बागबेड़ा. East Singhbhum's
  names came apart in half and the rows named no panchayat while the name sat in
  the string. **+116 panchayat names, no row whose value changed.**

### Notes for anyone holding earlier numbers

Jharkhand's seat-level figures move in this release, and they move because rows
that previously identified no seat now identify one. Row counts and reservation
shares are not intended to move; the release check requires that no other state
moves at all.
