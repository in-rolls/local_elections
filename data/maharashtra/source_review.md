# Mumbai reservation and later-election source review

## Ward 172 in 2012

The research workbook `raw/mumbai/BMC-2007_raw.xlsx` labels ward 172 “Schedule Caste Women.” The Karekurve-Ramachandra–Lee deposit instead records `genderquota = 0` for the 2012 term in each of its 2013–2016 survey waves. We resolve this discrepancy using BMC's own bilingual ward description, [PDF page 17](raw/mumbai/source_review/f_north_2012.pdf) (printed page 172 of 227). Its reservation column says **“Reserved for members of Schedule Castes”**, without a women-only restriction. The Marathi column also identifies SC reservation without a women-only condition.

The release now codes **SC, not reserved for women**. This reduces the women's reservation count from 115 to 114 and brings all 227 women's flags into agreement with the deposit. The original workbook is unchanged. [The correction ledger](reference/reservation_review.csv) records its label, the selected label, source page, and SHA-256. This correction rests on the reservation document, not an inference from the winner's name or sex.

A contemporaneous February 11, 2012 Times of India article independently describes ward 172 losing its women's reservation. Its HTML is retained in the same source folder. The separately saved one-page 2012 ward chart does not color ward 172 as SC, despite the explicit reservation in its detailed ward description; the detailed description is the selected source. The chart is not treated as a complete or authoritative reservation table.

## The later election is 2026

The expected 2022 election did not take place. BMC's next completed general election was January 15, 2026. The official January 19 gazette states that date and declares winners for wards 1–227. A copy of the gazette and OpenCity's English transcription are retained in `raw/mumbai/source_review/`, with their original URLs, collection timestamps, and hashes in [the source manifest](raw/mumbai/source_review/manifest.csv).

[The 2026 winner file](release/mumbai/bmc_winners_2026.csv) has one row per elected ward, keyed by `(year, ward_no)`. All **227 vote counts match the gazette**, including three counts that wrap onto a continuation line in its extracted text. Names and party labels are the OpenCity English transcription and have not been independently checked across all rows; the PDF's Marathi text has broken glyph extraction. The file records its separate source for those fields. The final November 28, 2025 reservation gazette supplies the reservation of all 227 wards: 114 are reserved for women. The parser checks every caste-category total and its women-reserved subset against the gazette summary. Reservation is separate from winner sex; no education, winner-sex, or losing-candidate coverage is asserted. Ward numbers alone do not establish a link to 2017.

The 2022 documents already present elsewhere under Maharashtra concern Beed and Jalna, not completed Mumbai election results. Proposed 2022 ward and reservation materials must not be labeled as realized election outcomes.

The October 6, 2025 final boundary gazette and ADR's affidavit-based report on all 227 winners are also retained. They provide sources for geographic linkage and winner characteristics, but those fields have not yet been validated at the individual level.

## Rebuild and checks

`make maharashtra` regenerates the affected releases offline. The parser checks unique coverage of all 227 gazette and compiled ward identifiers and exact agreement on votes. Regression tests pin the official ward-172 correction, retain its original conflicting label, and check the wrapped 2026 rows. The validator now requires exact agreement with the 114-seat women's total and the deposit's women's flags. Original sources remain unchanged.


## Historical comparison eligibility

The typed [Bhavnani handoff](release/mumbai/bhavnani_comparison_1997_2002.parquet) retains all 227 rows of the author's original 2002 data. `is_eligible` selects the 118 wards with nonmissing `controltreat`: 81 controls and 37 treated wards, with 3 and 8 women elected. The 33 other open offices have missing treatment classification and remain excluded. `prior_reserved_woman` preserves that missingness; it is not a general 1997 reservation roster. The author's article, page 26 note 8, limits geographic comparisons to 173 wards with largely unchanged boundaries. The original DTA and DO files and article are retained under `raw/mumbai/bhavnani_2009/`; `receipt.json` records original URLs and hashes and distinguishes the original retrieval date from this upstream copy. The DTA retains all 35 original variables.

| Transition | Current eligibility | Decisive limitation or evidence |
|---|---|---|
| 1997–2002 | Author-selected 118 open-office comparisons | Article page 26 note 8 and original nonmissing `controltreat`; no generalized ward-number bridge |
| 2002–2007 | Not established | No held primary crosswalk linking the 2002 geography to the 2007 geography; equal ward counts do not establish identity |
| 2007–2012 | Not established | Research workbook combines 2007 sitting corporators and 2012 quotas, but is not a boundary-continuity order; primary continuity evidence and fuller verified 2012 winner sex are still required |
| 2012–2017 | Not established | No validated primary geographic crosswalk; do not join identical ward numbers |
| 2017–2026 | Not established | October 6, 2025 gazette, printed/PDF page 154, sets the extent of the wards for the next election after considering objections to the August 2025 draft; there is no validated crosswalk to 2017 |

The [winner sex source audit](release/mumbai/winner_sex_source_audit_2012_2017.parquet) preserves all 227 wards in each election. It compares the election winner's name with the later research profile in the same ward (2013 for 2012 winners; 2018 for 2017 winners). Only an exact multiset of lowercase ASCII name tokens, ignoring order and punctuation, permits adoption of the independently recorded `sex` field. This yields 69 recorded outcomes for 2012 and 199 for 2017. Unmatched names, missing profile sex, and unnamed winners remain null, including in women-reserved offices. Both source names and the unadopted profile sex remain visible. This is a conservative linkage audit, not a validated complete election-sex roster, and neither these match rates nor the later profile observation dates establish a cross-election geographic link.

The ADR 2026 report records **137 women and 90 men in aggregate** on printed/PDF page 17. Its individual winner table does not provide a sex column. Those totals therefore do not fill individual winner-sex values or establish a post-quota effect. The 2025 boundary gazette also cannot supply those values.

The historical handoffs rebuild offline with `PYTHONPATH=src python -m local_elections.states.maharashtra.historical`, and are included in the existing Maharashtra parser. `historical_schema.json` records the actual Parquet types, nullability, primary keys, row counts, missingness and hashes. Tests cover the 33 unclassified open wards, exact sample counts, quota-independent missingness, roundtrip preservation, and rejected key, indicator and eligibility errors.


The official 2017 ward-description map and detailed A-ward document (wards 225–227) are now held in `raw/mumbai/boundary_review/`, with source URL/time/hash receipts. The live official files are under `/Election-Documents/`; the older root-level URLs return 404. The A-ward document explicitly introduces a 2016–2017 ward-formation exercise on PDF page 2. Its three ward population totals also recur in the 2025 gazette. That limited agreement does not certify all 227 boundary descriptions or an identity crosswalk. The held documents make further comparison possible without substituting a repeated ward count for geographic verification.


For the 2007–2012 bridge specifically, the official `Election-Documents/` index, its 2012 boundary index and its `Other Documents/` index were checked and retained as HTML with receipts in `raw/mumbai/boundary_review/`. The first exposes 2012 and 2017 boundary collections but no 2007 boundary collection. The 2012 root lists CITY, EASTERN SUB, WESTERN SUB and Other Documents; Other Documents contains only the ward chart already held. The detailed F-North 2012 source establishes individual 2012 boundary descriptions and quotas, but no reviewed passage states that all 2007 boundaries were reused. Thus the outstanding evidence is a primary 2007–2012 continuity notification or a ward-by-ward comparison to the 2007 boundary descriptions, alongside fuller independently verified 2012 winner sex. No new Mumbai persistence estimate is released from these incomplete ingredients.
