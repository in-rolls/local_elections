# Haryana release data dictionary

| artifact | row unit | universe | missing policy | provenance |
|---|---|---|---|---|
| `modern_seats.parquet` | selected-printing seat | 2016/2022 rows with complete, unique source identity | no imputation | pooled master plus checksum-pinned sibling CSV literals |
| `modern_quarantine.parquet` | source row | incomplete or duplicated modern source identity | preserve null/blank literally | same as modern release |
| `historical_reviewed_occurrences.parquet` | printed occurrence | source-reviewed 2000 seat occurrences with body, tier, ward where required, and category | no imputation | frozen review snapshot and source-review hashes |
| `historical_quarantine.parquet` | printed occurrence | reviewed occurrences missing an essential release field | preserve null and reason | frozen review snapshot; includes exactly 32 missing-heading rows |
| `historical_provisional_observations.parquet` | OCR occurrence | unvalidated OCR and reviewed non-seat records | outside release universe | frozen review snapshot |
| `printing_reconciliation.parquet` | modern row carrying source `printings_agree=0` | all 1,536 such rows | status only, no value rewrite | sibling parser comparison plus pooled row provenance |

`source_*_raw` columns are literal sibling CSV fields. Existing modern master
columns remain unchanged. Historical raw OCR fields remain in every partition.
Blank source wards and null historical cells are unknown, not zero.
