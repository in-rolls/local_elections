# Haryana release recode ledger

| derived field | source | definition | count check | reason |
|---|---|---|---|---|
| `printing_reconciliation` | `source_printings_agree_raw`, tier | ward `0` = inherited GP-head comparison; head `0` = retained source variation | 1,392 + 144 = 1,536 | stop a GP-head diagnostic from masquerading as a ward defect |
| `release_source_key` | source provenance and printed identity fields | year, tier, district, block, PDF, notification, GP serial/name, ward | unique in modern release | distinguish same-named printed offices without fuzzy matching |
| `release_quarantine_reason` | source identity fields | blank ward and/or duplicated source seat key | input = included + quarantined | never choose among ambiguous seats |
| `release_disposition` | review status and required fields | reviewed release, reviewed quarantine, reviewed non-seat, or provisional | four-way row conservation | keep occurrence-level validation claims bounded |

No source literal, reservation category, winner, ward, or body heading is recoded.
