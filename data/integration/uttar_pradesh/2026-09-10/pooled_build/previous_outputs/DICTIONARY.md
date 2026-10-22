# Data dictionary

Generated from `scripts/common/dictionary.py` by `make dictionary` — edit the
declarations, not this file.

Every column is checked against these rules by `make expect`, which writes
`data/expectations_report.csv`: one row per violated expectation, with the count
and the source document and page of the first offender, so a finding points at a
gazette page rather than at a number.

Severity is **error** when a value cannot be right (outside its enum or range),
**warn** when it is suspicious (blank more often than expected, an unusual
length), and **info** when it is known and accepted.

A column that is *entirely* blank in a file is reported as info, not warn: it
means the source has no such column — J&K's 2010 files carry no district, a
nomination list carries no winner — and that is a fact about the document rather
than a defect.


| Column | Type | Severity | Constraints | Notes |
|---|---|---|---|---|
| `state` | string | error | length 3–30; ≤0% blank | Printed name of the state or union territory. |
| `year` | integer | error | range 1990–2030; ≤0% blank | Election year. Four digits; a range would mean two cycles got merged into one file. |
| `tier` | enum | error | one of `gp_head`, `gp_vice_head`, `gp_ward`, `block_member`, `block_head`, `block_vice_head`, `zp_member`, `zp_head`, `kachahari_head`, `kachahari_member`, `ulb_ward`, `ulb_head`; ≤0% blank | Which office the seat is, canonically. The same office is printed under different names by different states, and worse, the same name means different offices - Bihar's sarpanch heads a village court, not the panchayat. See canon.py. |
| `tier_local` | string | warn | length 2–40; ≤0% blank | The office as the state printed it: sarpanch, mukhiya, ward_member. Kept so nothing is lost to the canonical mapping and any row can be checked against its gazette. |
| `district` | string | warn | length 3–30; ≤20% blank | J&K's 2010 files carry no district column at all, so a blank share above zero is expected there but not elsewhere. |
| `block` | string | warn | length 2–40; ≤35% blank | Block, taluka or mandal depending on the state. |
| `gram_panchayat` | string | warn | length 2–45; ≤10% blank; also called `halqa` | The panchayat. Called halqa in J&K. Jharkhand printed it inside a compound seat identifier until that was taken apart; see seat_id_raw. A value far over the length bound has usually swallowed the next column - that is how AP's broken mandal split was found. |
| `gram_panchayat_standardized` | string | info | length 2–45 | A source repository's standardized panchayat name, retained for linkage but excluded from seat identity because a many-to-one name crosswalk can merge distinct printed panchayats. |
| `ward_no` | roman_or_integer | warn | length 1–6; ≤30% blank | Blank on sarpanch and mukhiya rows by design. J&K and Goa number wards in Roman numerals, so this is not purely numeric. |
| `ward_name` | string | warn | length 2–40; ≤30% blank | A named ward or upper-tier constituency where the source names rather than numbers the seat. |
| `caste_reservation` | enum | error | one of `SC`, `ST`, `BC`, `NONE`; ≤0% blank | **The seat's reservation, never the winner's caste.** The two are different facts and this corpus keeps them apart: a scheduled-caste person can win an unreserved seat, and in Uttar Pradesh 2005 the winner's own category matches the seat's on only 19,324 of 51,872 rows. The winner's category, where a source states it, is `winner_caste` on a seat row and `candidate_caste` on a candidate row. Orthogonal to woman_reserved: a seat can be both. |
| `caste_reservation_local` | string | info | length 2–40 | The source's local-language category or source-specific code; `caste_reservation` is its canonical interpretation. |
| `woman_reserved` | boolean | error | ≤0% blank | 1 if **the seat** is reserved for a woman - not whether a woman won it. The winner's own gender is `candidate_gender` in the candidate table. A woman can and does win a seat that is not reserved for one. |
| `reservation` | enum | error | one of `Woman`, `Other than Woman`, `SC Woman`, `SC Other than Woman`, `ST Woman`, `ST Other than Woman`, `BC Woman`, `BC Other than Woman`; ≤0% blank | The two fields above, joined. Written separately from them, so it can disagree with them - which is checked as a row rule. |
| `reservation_raw` | string | error | length 1–120 | The source cell, untouched, so any row can be audited. Where a source prints separate category flags, this is a JSON array of the untouched cells in printed order. Blank is valid only when the source prints no mark for an open, non-woman-reserved seat; that relationship is checked. |
| `reservation_raw_original` | string | info | length 0–120 | The original source cell when a later official erratum changes the seat. Blank on rows with no correction. |
| `corrected` | boolean | info | — | 1 when a later official erratum replaces or supplies this seat's reservation. |
| `correction_for_raw` | string | info | length 0–120 | The erratum's printed `For` cell. A dash means the original gazette left the seat blank. |
| `correction_read_as_raw` | string | info | length 0–120 | The erratum's printed `Read as` cell, retained independently of its normalized reservation. |
| `correction_source_page` | integer | info | range 1–1000 | Page carrying the official correction; blank on uncorrected rows. |
| `seat_from_image` | boolean | info | — | Set where the seat identifier was OCR'd from an image because the document drew that column as pictures rather than text. The ward number in these rows comes from the ordering, not from the digits, which the OCR reads badly. |
| `district_declared` | boolean | info | — | Set where the district was declared from a roster outside the corpus rather than read from the document. Eight of J&K's 2010 blocks name no district anywhere in their file; saying so is the difference between a reading and an assertion. |
| `listing_scope` | enum | warn | one of `all_seats`, `reserved_only`, `partial` | J&K's 2018 documents list only reserved wards; Goa's 2017 and 2022 files are partial rosters. Absent means all_seats. |
| `winner` | string | warn | length 2–60; ≤60% blank | Only some states publish the elected member. |
| `winner_address` | string | info | length 2–200 | Address printed for the elected member, where published. |
| `winner_basis` | enum | info | one of `published`, `argmax_votes` | Why the person is treated as the winner rather than merely a candidate. |
| `votes` | integer | warn | range 0–100000; ≤60% blank | Goa 2012 only. |
| `vacant` | boolean | warn | ≤0% blank | Seat unfilled or the election countermanded. Official 'elected' totals exclude these. |
| `unopposed` | boolean | warn | ≤0% blank | A '*' against the name in the source. |
| `block_no` | integer | warn | range 1–99; ≤90% blank |  |
| `seat_no` | integer | warn | range 1–999; ≤90% blank |  |
| `serial` | integer | warn | range 1–9999; ≤10% blank | AP's per-mandal running number; gaps in it mean lost rows. |
| `halqa` | string | warn | length 2–45; ≤10% blank |  |
| `seat_id_raw` | string | info | length 1–90; ≤5% blank | Jharkhand. The seat identifier exactly as printed, before it was taken apart - a compound of district, block, gram panchayat and constituency number run together with @ and /. Kept because the split is the kind of thing worth being able to re-check against the page. |
| `gp_no` | string | warn | length 1–10; ≤60% blank | The gram panchayat's identifier within its block, where the source states one. J&K uses alphanumeric identifiers such as 14K. |
| `gp_identity_from_page_text` | boolean | info | — | J&K 2016 only. Set when a merged panchayat cell is visibly printed but the table extractor returns it empty, so the number and name are recovered from the source-faithful page text instead. |
| `pop_sc` | integer | warn | range 0–100000; ≤90% blank | J&K prints the populations the allocation was based on, which is the only place in this repo the rule can be checked against its own inputs. |
| `pop_st` | integer | warn | range 0–100000; ≤90% blank |  |
| `pop_oc` | integer | warn | range 0–100000; ≤90% blank |  |
| `pop_total` | integer | warn | range 0–200000; ≤90% blank |  |
| `ward_count` | integer | error | range 1–40; ≤75% blank | The number of wards the record itself states. Andhra Pradesh's gazette header numbers ward columns 1 to 20, so an AP value above that is an OCR misread - 72 and 74 are 12 and 14 in that font. Assam's municipal boards legitimately reach 28 wards. Blank for most of Andhra Pradesh because Anantapur's gazette is sarpanch-only and prints no ward column at all, which is why the blank tolerance is high. |
| `sc_reserved_ward_count` | integer | info | range 0–40 | Number of SC-reserved wards printed or counted from a complete source table; count_basis distinguishes the two. |
| `st_reserved_ward_count` | integer | info | range 0–40 | Number of ST-reserved wards printed or counted from a complete source table; count_basis distinguishes the two. |
| `women_reserved_ward_count` | integer | info | range 0–40 | Number of women-reserved wards printed or counted from a complete source table; count_basis distinguishes the two. |
| `count_basis` | enum | info | one of `printed_gp_summary`, `derived_from_complete_printed_ward_table` | Whether GP-level reservation counts are printed summary cells or derived from a source table that explicitly lists every ward. |
| `wards_parsed` | integer | warn | range 0–20; ≤0% blank |  |
| `ward_list_complete` | boolean | warn | ≤50% blank | 1 when the ward list matches the stated count. Only about a third of AP's ward rows qualify, so a consumer should filter on this rather than assume. |
| `ocr_repaired` | integer | warn | range 0–2; ≤0% blank | How many mends the row's category cell needed. A wrong mend is indistinguishable from a right one, so these stay findable. |
| `printings` | integer | warn | range 1–4; ≤0% blank | How many times the gazette states this seat. Anantapur prints the sarpanch reservation in two proformas - a sarpanch-only list and the ward table's first column - so where both carry a seat this is 2 and validate.py checks that the two agree rather than assuming it. |
| `gender_stated` | boolean | warn | ≤0% blank | Whether the source actually stated this seat's gender. Where a document marks only the women's seats a bare code is a man; where it marks both, a bare code is a marker that did not survive the scan, and woman_reserved=0 there is a guess. Filter on this before computing a women's share. |
| `printings_agree` | boolean | warn | — | Whether the gazette's separate statements of this seat say the same thing. Blank where the seat is stated only once - which is not the same as agreeing. Two independent typesettings agreeing is the strongest evidence available here that a row was read correctly. |
| `text_source` | enum | info | one of `ocr`, `embedded`, `embedded_positioned` | Whether the row came from our own OCR or the PDF's embedded text layer. `embedded_positioned` means word coordinates, not line order, determine the table cells. |
| `script` | enum | error | one of `latin`, `krutidev`, `devanagari`, `bengali`, `kannada`, `gujarati`; ≤0% blank | Which typesetting the row was read from. |
| `source_pdf` | string | error | length 4–80; ≤0% blank |  |
| `source_path` | path | error | ≤0% blank | Relative to data/, and checked by opening it rather than by matching a pattern - a first attempt at a filename regex rejected 1,783 perfectly good Jharkhand rows because one file is called 'Gomia_GPS, GPM & GPVM.pdf'. What matters is that the document is there, not what it is called. |
| `source_page` | integer | error | range 1–2000; ≤0% blank |  |
| `pop_female` | integer | info | range 0–10000000 | Census female population of the panchayat, from Karnataka. |
| `gp_code` | string | info | length 1–40 | The panchayat's own identifier in the source. An adapter may promote a stable source code into the shared gp_no identity field while retaining the original here. |
| `district_code` | string | info | length 1–12 |  |
| `block_code` | string | info | length 1–12 |  |
| `panchayat_code` | string | info | length 1–12 |  |
| `seat_id_printed` | string | info | length 1–80 | The compound identifier as printed - Bihar's 'Piprasi/SEMRA LABEDAHA/01'. Not a join key: it names no district, so two blocks sharing a name would merge. |
| `seat_no_from_serial` | boolean | info | — | Set where the constituency number was taken from the row's serial column because the seat cell printed only a name. Karnataka's 2016 notifications come in two shapes - one prints '1-ನೀರಬೂದಿಹಾಳ', the other a number column and a bare name - and 442 of the first 1,737 rows are the second. Only adopted where the serials run 1..N once across the whole document, since some restart per page and would otherwise renumber half a taluk onto seats that already exist. |
| `seat_no_ocr` | string | info | length 0–12 | Tesseract's reading of Gujarat's printed constituency number. The reviewed roster order supplies seat_no; this field keeps the fallible OCR output auditable rather than calling it raw. |
| `seat_no_from_order` | boolean | info | — | Set for Gujarat, whose final roster is printed once in strict 1..N order. The table grid proves that no row was skipped; seat_no_ocr retains the independent OCR reading. |
| `sc_rank_ocr` | string | info | length 0–12 | Tesseract's uncorrected reading of the source's SC ranking. |
| `st_rank_ocr` | string | info | length 0–12 | Tesseract's uncorrected reading of the source's ST ranking. |
| `reservation_match_score` | string | info | length 1–8 | Similarity of the selected source-cell OCR reading to the reviewed Gujarati reservation vocabulary. |
| `ocr_mean_confidence` | string | info | length 1–8 | Mean Tesseract confidence over the whole-page words assigned to this source row; not a probability of correctness. |
| `source_url` | string | info | length 8–300 | Where the document was fetched from. source_path says which file on disk a row came from and source_page which page of it; neither says where the file came from, which is the one question a reader outside this repository is most likely to ask. Recorded from the harvest manifest, so it is what was actually requested rather than what a URL pattern would reconstruct. |
| `source_capture` | string | info | length 8–40 | The web archive's capture timestamp, YYYYMMDDhhmmss. With source_url this refetches the exact bytes the row was read from - a live URL may since have changed or gone. Blank for documents that were not fetched from an archive. |
| `result_source_path` | string | info | length 1–120 | A second parsed input that supplies the result when source_path supplies the seat or candidates. |
| `nomination_source_path` | string | info | length 1–120 | The separate source table that supplies GP-event nomination totals. |
| `original_filename` | string | info | length 1–80 | The document a row was read from, where the parse kept it but the pooled schema has no column for it. |
| `party` | string | info | length 1–80 | The party the winner represented. Kerala prints it and so do Karnataka's 2016 taluk and zilla notifications; almost nothing else in the corpus does. Karnataka's is canonicalised against a fixed list and left blank where the cell does not settle which party - a reading truncated to ದಾರತೀಯ fits both of the two largest, so it is empty rather than guessed. party_local keeps what the page actually said. |
| `party_local` | string | info | length 1–80 | The party exactly as the document printed it, before any canonicalisation, so a row can be audited against its page. Kept for the same reason as reservation_raw. |
| `relation_name` | string | info | length 1–90 | Father's or husband's name, as the source prints it. |
| `winner_age` | string | info | length 1–12 |  |
| `winner_education` | string | info | length 1–90 |  |
| `winner_occupation` | string | info | length 1–90 |  |
| `winner_marital_status` | string | info | length 1–24 |  |
| `candidate_marital_status` | string | info | length 1–24 |  |
| `candidate_occupation` | string | info | length 1–90 |  |
| `candidate_total_assets` | string | info | length 1–30 |  |
| `candidate_children_before_1995_11_27` | string | info | length 1–4 |  |
| `candidate_children_after_1995_11_27` | string | info | length 1–4 |  |
| `winner_gender` | string | info | length 1–24 | The elected person's own gender. Not woman_reserved, which says whether the seat was reserved for a woman. |
| `winner_caste` | string | info | length 1–60 | The elected person's **own** category, where the source states it alongside the seat's. Not caste_reservation: that is what the seat was reserved for. Uttar Pradesh 2005 and 2010 are the only seat-level slices that carry both, and they disagree on 63% of rows - which is what makes them worth holding separately rather than a redundancy. |
| `winner_category_raw` | string | info | length 1–60 | The source's untouched winning-candidate category, retained even on a result row where the winner name is blank. |
| `election_type` | enum | info | one of `General Election`, `By Election` | Whether Rajasthan SEC labels the event as a general or by-election. |
| `election_duration` | string | info | length 5–20 | The event period exactly as Rajasthan SEC labels it. |
| `total_candidates_stated` | integer | info | range 0–100 |  |
| `electorate` | integer | info | range 0–100000 |  |
| `votes_polled` | integer | info | range 0–100000 |  |
| `rejected_votes` | integer | info | range 0–100000 |  |
| `valid_votes` | integer | info | range 0–100000 |  |
| `poll_percentage` | string | info | length 1–8 |  |
| `nota_votes` | integer | info | range 0–100000 |  |
| `tendered_votes` | integer | info | range 0–100000 |  |
| `winner_pledge_url` | string | info | length 8–300 |  |
| `result_remark` | string | info | length 1–120 |  |
| `nominations_filed` | integer | info | range 0–1000 |  |
| `nomination_candidates` | integer | info | range 0–1000 |  |
| `validly_nominated_candidates` | integer | info | range 0–1000 |  |
| `withdrawals` | integer | info | range 0–1000 |  |
| `nominated_unopposed` | integer | info | range 0–1000 |  |
| `contestants` | integer | info | range 0–1000 |  |
| `lgi_role` | string | info | length 1–40 | Kerala's Role column. An office the ward member also holds - President, Vice President - not a tier. |
| `body` | string | info | length 1–80 | The local body a seat belongs to, where it is not a gram panchayat. |
| `zilla_parishad_constituency` | string | info | length 2–80 | Named district-level constituency containing a GP, where printed. |
| `vote_percentage` | string | info | length 1–12 | Uttar Pradesh 2021 records a share of the poll and no vote total, so this cannot become a count. |
| `movable_property` | string | info | length 1–24 |  |
| `immovable_property` | string | info | length 1–24 |  |
| `criminal_history` | string | info | length 1–40 |  |
| `duplicate_candidacy` | integer | info | range 0–20 | The source stated this contest more than once, with vote counts that disagree. Folded on (serial, name) keeping the higher count; this says it happened. |
| `serial_not_unique` | integer | info | range 0–1 | One serial number carrying two different candidates. Not resolvable from the file, so both are kept. |
| `winner_candidate_ambiguous` | integer | info | range 0–1 | More than one candidate in the contest has the published winner's exact normalized name, so the seat winner is known but the winning candidate serial is not. |
| `shared_place_name` | integer | info | range 0–1 | Two places in one block printed under one name, told apart only by being reserved differently. |

## Plausible row counts

A file outside its band has lost rows or double counted them.

| State | Tier | Expected rows |
|---|---|---|
| Andhra Pradesh | gp_head | 500–13,200 |
| Andhra Pradesh | gp_ward | 5,000–130,000 |
| Assam | gp_ward | 1,254–1,254 |
| Bihar | block_member | 8,000–13,000 |
| Bihar | gp_head | 6,000–9,500 |
| Bihar | gp_ward | 80,000–125,000 |
| Bihar | kachahari_head | 6,000–9,500 |
| Bihar | kachahari_member | 80,000–125,000 |
| Bihar | zp_member | 500–1,400 |
| Goa | gp_ward | 400–1,800 |
| Gujarat | block_member | 646–646 |
| Gujarat | zp_member | 532–532 |
| Haryana | gp_head | 4,000–8,000 |
| Haryana | gp_ward | 40,000–80,000 |
| Jammu & Kashmir | gp_head | 100–4,500 |
| Jammu & Kashmir | gp_ward | 500–35,000 |
| Jharkhand | block_member | 1,000–5,500 |
| Jharkhand | gp_head | 1,000–5,000 |
| Jharkhand | gp_ward | 1,000–20,000 |
| Jharkhand | zp_member | 50–600 |
| Karnataka | block_member | 2,500–4,200 |
| Karnataka | gp_head | 4,000–7,000 |
| Karnataka | zp_member | 600–1,200 |
| Kerala | block_member | 1,500–2,500 |
| Kerala | gp_ward | 14,000–18,000 |
| Kerala | zp_member | 250–400 |
| Maharashtra | ulb_ward | 454–454 |
| Rajasthan | block_member | 5,257–5,273 |
| Rajasthan | gp_head | 8,000–14,000 |
| Rajasthan | gp_ward | 90,000–130,000 |
| Rajasthan | zp_member | 1,008–1,013 |
| Telangana | gp_head | 10,000–14,000 |
| Telangana | gp_ward | 40,000–60,000 |
| Uttar Pradesh | gp_head | 45,000–60,000 |
| Uttarakhand | block_member | 150–4,000 |
| Uttarakhand | gp_head | 200–9,000 |
| Uttarakhand | zp_member | 30–500 |
