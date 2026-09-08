# Tamil Nadu 2001 village-panchayat president amendments

This extraction records all GP-president amendment operations in Gazette No. 636, dated 15 September 2001, G.O. Ms. No. 227 dated 14 September 2001. The immutable source is [the official PDF](https://tnrd.tn.gov.in/project/go_files/1_58_2001_636_en.pdf), preserved at `data/source_search/early_heads/raw/tn_1_58_2001_636_en.pdf`, SHA256 `5cc758b6cc8ad025f284276c61ce3f24302890783ea0a0233a6f2d4d76051bf3`.

The GP provisions occupy clauses 1–10 on PDF pages 1–16. Clause 11 begins the union-chair amendments on page 16 and continues on page 17; clause 12 covers district chairs on pages 17–18. These other tiers appear in the page and clause audit, without entering the GP table. Page 19 begins a separate ward amendment outside this extraction.

## Counts and interpretation

`gp_president_amendment_operations` contains 456 row statements:

- 434 named rows in 16 replacement sections, including all 42 Devakottai rows;
- 17 named insertions, with their printed insertion anchors;
- five category replacements addressed by old serial, whose GP names are not printed and remain null.

The 451 named statements are source occurrences, not a deduplicated statewide GP count. `context_operations` separately retains 19 district-heading substitutions and the clause 9 heading/section replacement context. Clause 9 supplies the replacement Perambalur and Ariyalur sections. All GP clauses in scope have been parsed.

These instructions have **not been applied to the 1996 base notification** and do not constitute a complete 2001 roster. Resolving the five unnamed targets requires the corresponding base rows. The printed General category supplies an unrestricted reservation category; it does not identify an officeholder's caste or sex. Officeholder name and sex are always null.

## Evidence and review

`manual_readings.json` holds the source readings, clause/union/serial locators, document and page-image hashes, operation context and eight recorded spelling corrections. Category punctuation and spacing are standardized; operation boilerplate is paraphrased in `operation_text_reading`. Printed name spellings are retained, including unusual spellings. Curved-table category alignment is explicitly flagged where relevant.

`independent_name_review.json` records a second visual pass over all 451 named entries, with per-entry JSON pointers and original image hashes. It supports the eight corrections and records a rejected spelling proposal. Reviewers communicated during correction, so this is a disclosed independent check, not blinded gold or an estimated accuracy rate. The five serial-only category targets were reviewed in the primary transcription, outside that named-entry audit. No source name remains unresolved after review; this does not certify perfect accuracy.

`machine_ocr_provenance.json` links the separately preserved 300 dpi Tesseract text, TSV, images and stderr for all 18 pages. Machine OCR has not been substituted for manual readings. The 176 entries in `review/ocr_name_disagreements.json` are an earlier substring-based triage list; they include OCR/layout errors and pre-correction human readings, and are not 176 unresolved errors.

## Files and reproduction

The main operations, replacement-section controls, context operations and page audit are available as CSV, Parquet and JSONL. Empty CSV fields represent nulls; Parquet preserves nulls and Boolean types. `data_dictionary.json` and `.csv` define the main table; `verification.json` provides scope and count controls. Source occurrence keys are not administrative GP identifiers.

From the repository root, run:

```sh
python -m local_reservations.states.tn.parse_amendments_2001
pytest tests/test_tn_amendments_2001.py
ruff check src/local_reservations/states/tn/parse_amendments_2001.py tests/test_tn_amendments_2001.py
```

The exporter verifies the original PDF, visual evidence, independent-review identity and existing OCR artifact hashes before completing. It does not download or rewrite the source. `provenance.json` pins the frozen inputs and outputs for this extraction.
