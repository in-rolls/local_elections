# West Bengal GP-head outcome availability audit

Audit date: 2026-09-08 UTC. This is an availability and measurement audit, not an estimate or a representative sampling claim. The [CSV ledger](head_outcome_availability.csv) distinguishes acquired observations from metadata-only leads, physical rows from verified GP counts, and election outcomes from survey incumbency.

**Birbhum and Nadia were not two places with the same complete data combination.** The acquired Birbhum research surveys record Pradhan sex and reservation history. The acquired Nadia 2013 handbook records GP-head reservation but no head sex; the Nadia demand analysis addresses an administrative-demand question. Neither an administrative-demand outcome nor a women-reserved office can substitute for a recorded female election winner.

**The six-district Beaman election package is a higher-priority lead for the persistence question than the Nadia demand exercise.** Current official metadata confirms reservation fields for 1998, 2003 and 2008 and nonmissing sex fields for 2003 and 2008. The row-level data remain behind a guestbook requirement. Anonymous identifiers are not a reason to reject a within-source analysis.

## What was inspected

- All 42 current WB Parquet files: 39 under `data/wb/derived` and three under `data/wb/vintage_search`. Schemas and observed sex/winner fields were inspected, not just README descriptions. Both `winner_gender` columns found in reservation exports are entirely missing: 787 base-draft records and 941 office-scan mentions.
- All three held standalone research Stata files; all six Stata members of `chattopadhyaya_duflo.zip`; and the 258-variable VillageYear and 151-variable Household datasets inside the QE2024 replication ZIP. Variable labels and relevant observed values were inspected.
- The current source inventories, including `office_parsing_by_source.csv`, `artifact_index.csv`, and the 552-document parsing inventory. The CSV includes all 22 district/year/stage/GP-office-tier groups from the 60-row office parsing inventory. It does not turn source cells or overlapping reservation-axis mentions into GP counts.
- Public Dataverse DDI metadata for the combined six-district file and five additional district files, plus current guestbook metadata and an unauthenticated download response. No guestbook responses or personal details were submitted. The original cached Claude reports were preserved and their proposed identity reconstruction was not followed.

This audit found no acquired, explicitly recorded GP-head sex dataset beyond the Birbhum research sources. This is a statement about the audited holdings, not proof that such data do not exist elsewhere. Unparsed content and unacquired sources must remain distinct from absent variables in inspected datasets.

## Acquired evidence

| Source | Actual unit and coverage | Reservation and sex | Qualification |
|---|---|---|---|
| Chattopadhyay–Duflo Birbhum archive | 166 GP survey rows; `prsex` recorded for 161 | Current 1998-term reservation and surveyed Pradhan sex | Survey incumbent, not a verified election-winner registry; alone does not provide a subsequent outcome |
| Beaman Birbhum reservation roster and Pradhan survey | 165 roster GPs; 316 interview records, 161 marked current Pradhan | 1998/2003 reservation history, explicit respondent/Pradhan sex fields, mostly 2006 interviews | Current/previous role, spouse, IDs, conflicting sex reports and visit year require checks; restricted follow-up incumbency is not verified 2003 winning |
| Nadia 2013 handbook | 187 GP rows per head/deputy office | Complete office codes with explicit unrestricted categories; one blank head code | No observed head sex; source serial keys allow within-document office pairing |
| Alipurduar 2018; Purulia and South 24 Parganas 2018; Alipurduar, Birbhum, Cooch Behar and Jalpaiguri 2023 office schedules | Named positive-office rows or source cells, with drafts/finals and office tiers separated | Reservation assignments | No observed head sex; nonlisting and the unmarked opposite axis remain unknown |
| Alipurduar 2018 results | GP-member, PS-member and ZP-member seat/candidate records | Winner names and parties; no recorded sex | Wrong office unit for Pradhan persistence; names do not establish sex |
| Birbhum 2003 member composition | District-level elected-member aggregates by recorded sex | GP/PS/ZP member totals | No identified GP-head outcome |
| QE2024 multi-district replication archive | Village-year and household observations | GP party majorities and assembly reservation; household-head characteristics | No inspected GP-head reservation-plus-sex panel |

The existing Birbhum follow-up sample is a restricted subset of the acquired roster: 165 roster GPs, 151 with verified history, 99 not women-reserved in 2003, and 94 with usable follow-up sex measurements. Those restrictions need an explicit selection analysis; they do not make the district representative. Nadia was usable for a different analysis because its official office codes and source geography could be linked to administrative demand records. It should not be described as another Pradhan-winner-sex sample.

## Six-district Dataverse lead: current official evidence

Dataset: [Powerful women and aspirations in India, DOI 10.7910/DVN/O3UKFO](https://dataverse.harvard.edu/dataset.xhtml?persistentId=doi:10.7910/DVN/O3UKFO). The [combined file's public DDI](https://dataverse.harvard.edu/api/access/datafile/13986379/metadata/ddi) identifies `election_pradhan_alldist.tab`, 1,316 physical cases and 42 variables.

| Metadata file | Physical cases | Valid `gender2003` | Valid `gender2008` |
|---|---:|---:|---:|
| Combined six-district file | 1,316 | 1,141 | 1,309 |
| Nadia | 188 | 187 | 187 |
| Howrah | 158 | 156 | 156 |
| Hooghly | 211 | 210 | 210 |
| Burdwan | 278 | 277 | 277 |
| South 24 Parganas | 313 | 311 | 312 |

These are DDI case and valid-value counts, **not verified unique GP or jointly complete analysis counts**. District files overlap the combined file and must not be added to it. The combined file includes the Birbhum component; a new standalone Birbhum district DDI was not fetched in this follow-up.

The DDI confirms `res1998`, `res2003`, `res2008`, `gender2003`, `gender2008`, anonymous GP/block/name code fields and `incumb2008`. It reports zero valid `gender1998` values. The 2003 and 2008 sex fields have binary 0/1 statistics but no value labels in the retrieved DDI. The election-file context makes these relevant Pradhan outcome leads, but the meaning of 1 and exact winner-versus-incumbent definition still require the codebook, cleaning code and microdata. No value was recoded from metadata alone.

The [download endpoint](https://dataverse.harvard.edu/api/access/datafile/13986379) returned HTTP 400 requiring guestbook 269. This is an explicit guestbook requirement, not evidence of a restricted or nonexistent dataset. The dataset inventory endpoint returned HTTP 403 in this attempt, while all six DDI requests returned HTTP 200.

The [current guestbook metadata](https://dataverse.harvard.edu/api/guestbooks/269) requires a name and three custom responses: intended use, position/title, and the country of the institution. Email, institution name and the standard free-text position field are optional; the separate custom position question is required. The user's name, position and institution country have not been supplied for this submission. Intended use should reflect the research task and be confirmed rather than invented. No answers were submitted.

Raw HTTP responses, request URLs/statuses, retrieval times and SHA-256 hashes are preserved in [dataverse_o3ukfo_followup_20260908](dataverse_o3ukfo_followup_20260908/). The [metadata summary](dataverse_o3ukfo_followup_20260908/metadata_summary.json) records exact variable names and DDI valid/missing counts. The six-district conclusion comes from these current official responses, not only the cached agent report.

## Eligibility and source-priority policy

For a within-source persistence analysis, require a verified stable GP identifier; separately coded, dated GP-head reservations; independently recorded subsequent GP-head sex; and a documented election/officeholder definition. Anonymous stable identifiers are adequate if their scope, uniqueness and consistency across cycles can be verified. Real GP names are needed for external joins, not for every within-file comparison.

Never infer sex from names or quotas, infer UR from absence in positive lists, substitute ward outcomes for GP-head outcomes, or reconstruct anonymous identities from treatment patterns. Before estimating from the six-district package, inspect coding, duplicates, district-specific exceptions, cycle continuity, missingness and the assignment mechanism. Acquisition alone does not establish causal identification.

Accordingly, retain the Birbhum incumbent exercise as explicitly exploratory, prioritize acquisition and verification of the six-district election package for `quota_raj`, and keep Nadia's demand analysis separate under `quota`. The earlier acquisition and analysis sequence was not a pre-specified statewide sampling rule and must not be represented as one.

## Verification and reproducibility

The 34-row CSV includes all 22 official office groups, two Birbhum research source groups, six Dataverse metadata entries and four nonqualifying context sources. Local source/evidence hashes were verified. CSV row IDs are unique and exact round-trip checks pass. Blank verified-GP-count fields mean that no unique GP count was established; physical metadata/source-cell counts are retained separately. No models were run or changed for this availability audit.
