# State repository contract

## Ownership and isolation

A state repository owns its state-specific acquisition rules, parsers, source
manifests, corrections, and published state datasets. The central repository
owns shared tools, nationwide discovery and coverage tracking, harmonization,
and the pooled release. States without a dedicated repository use an isolated
state module centrally until an independent release or maintenance need
justifies a separate repository. Do not create a repository per jurisdiction
merely for symmetry.

A state build must not import another repository's private scripts or require
a particular sibling checkout layout. Shared functionality belongs in a
versioned dependency. LLM execution uses batchlane or the approved provider
integration, not independently maintained provider clients in every state.

Central reads a pinned, manifested state release. It does not silently consume
a moving checkout or independently correct a state's substantive data. A
correction belongs upstream, with the original value and evidence retained.

## Layout

| Location | Purpose |
| --- | --- |
| `data/discovery/YYYY-MM-DD/` | Search frames, acquisition experiments, and self-contained evidence bundles not admitted to production. |
| `data/raw/` | Immutable, explicitly registered production source bytes. |
| `data/interim/` | Rendered pages, extraction/OCR outputs, and reproducible intermediate tables. |
| `data/crosswalks/` | Reviewed identifier mappings and explicit correction decisions. |
| `data/release/` | Versioned consumer-facing tables, schema, dictionary, coverage, and manifest. |
| `src/<package>/` | Reusable Python acquisition and parsing logic. |
| `R/` | Reusable R functions where R is the implementation language. |
| `scripts/` | Thin pipeline entry points, not duplicated libraries. |
| `notebooks/` | Exploration, never an undocumented production dependency. |
| `tests/` | Parser, recode, grain, and provenance contracts. |

Use the language-native layout already appropriate to the project. Do not
create empty directories or introduce both R and Python to satisfy this table.
Existing published locations, such as UP's `data/fin/`, are migrated with their
consumers in one coordinated change, not renamed during a production run.

Discovery bundles may retain raw subdirectories alongside their inventories.
That is a research collection boundary, not permission for release builds to
recursively ingest discovery files. Admission to production is manifest-driven.
A preserved source blob can be referenced from more than one manifest without
creating independently maintained copies.

## Naming

Use descriptive lowercase snake_case names. Functions are actions:
`fetch_sources`, `parse_gp_heads`, `read_reservations`. Tables describe their
contents and grain: `gp_head_candidates_2021.parquet`,
`gp_head_winner_records_2021.parquet`, `seat_reservations.parquet`.

Use ISO dates for runs and zero-padded numbers only when script ordering is
meaningful: `2026-09-10/`, `01_fetch_sources.R`, `02_parse_results.R`.
Conventional names such as `README.md`, `Makefile`, and the `.R` extension
remain conventional. Do not force snake_case onto source-language strings or
external identifiers.

Avoid `final`, `fixed`, `new`, `latest`, `misc`, and correction histories embedded
in filenames. Record versions in releases and provenance, not suffix chains.
Do not encode state names repeatedly inside a state repository unless a
consumer-facing asset would otherwise be ambiguous.

These conventions follow the practical naming principles in the
[Tidyverse file guide](https://style.tidyverse.org/files.html) and
[object naming guide](https://style.tidyverse.org/syntax.html#object-names).
The directory and provenance contract here is our project policy, not a
claim that the Tidyverse prescribes this repository layout.

## Provenance is part of the data

Every released record must resolve through the following chain:

```text
released row
  -> source observation and transformation
  -> extraction response or parsed source location
  -> immutable source bytes
  -> acquisition URL, retrieval time, and archive capture where applicable
```

A URL alone is not provenance. The same URL can serve different documents.
A PDF filename alone is not a page reference. An archive capture timestamp
is not an election year. A row key is not necessarily a stable geographic ID.

Use a small set of explicit artifacts, not a new provenance service:

- A source manifest records source identity, content SHA-256, original and
  final URLs, publisher, local or durable asset location, and source scope.
- Append-only acquisition receipts record every attempt, UTC retrieval time,
  response status, content hash, archive capture, and any request context
  needed for reproduction. Never record credentials or sensitive headers.
- Extraction records link input hash and page/table/cell or HTML row locator
  to output hash, parser/model version, prompt hash, rendering settings, and
  raw response. Paid attempts retain request IDs, token usage, estimated cost,
  and billing status separately where available.
- Released observations carry a stable observation ID, source ID, source
  locator, raw category/value, normalized value, and unresolved flags. Rich
  extraction metadata may be joined by ID rather than repeated on every row.
- Correction decisions retain old value, new value, reason, supporting source,
  reviewer, and decision time. Never patch raw evidence to match a correction.
- A release manifest pins code revision, input hashes, output hashes, schema
  version, declared grain and keys, row counts, and coverage limitations.

Identity must survive relocation: link by source/observation IDs and hashes,
not by an absolute path on one laptop. Record moves in a handoff ledger. Keep
historical receipts unchanged; update current locators without rewriting the
history of where an acquisition originally occurred.

If a source cannot support page-level or row-level lineage, state the weaker
provenance level explicitly. Do not invent a locator to satisfy the schema.

## Grain and uncertainty

Keep candidates, winner-marked source records, unique seat events, and
reservation assignments distinct. Declare each table's row unit and expected
join cardinality. Missing, conflicting, absent from source, request failed,
and not searched are different states. Unknown reservation is not unreserved.

Retain local office names and reservation categories alongside pooled labels.
Historical district/block names and boundary versions must not be overwritten
with present-day geography. Reviewed crosswalks add mappings, not replacement
history. Conflicting winners stay visible until source evidence resolves them.

## Reproduction and publication

Fetching is the networked stage. Parsing reads saved bytes offline. Release
assembly reads declared inputs and reviewed corrections. A build must not
redownload sources, make paid calls, or select the newest file opportunistically.

Prefer a small Makefile with explicit `fetch`, `parse`, `release-data`, and
`check` targets, using standard language tools and a locked environment.
Declare secrets and external prerequisites; never commit keys. State repos
share contracts, not necessarily identical implementation languages.

Code tests and source-quality gates belong in the release workflow. A local
instruction to skip tests is not evidence that release checks passed; report
what was and was not run. Never publish research output as validated merely
because extraction completed.

Large immutable source bytes and expensive OCR responses belong in durable,
checksum-addressed release assets or object storage when unsuitable for Git.
The repository retains manifests and a documented restore command. A local
cache is not a backup, and an unuploaded bundle is not a published asset.

Retain raw public records as evidence where appropriate, but review access,
licensing, and personal-data exposure before publication. Unnecessary phone
numbers and credentials do not belong in public analytical tables or logs.

## Current UP transition

The 2026-09-10 parallel-search and archive-coverage collections now live in
`local_elections_up/data/discovery/2026-09-10/`. Central retains the handoff
manifest and statewide tracking, not a second mutable copy of those bundles.
Existing UP releases remain in `data/fin/` until the four-wave import contract,
2021 winner conflict, and existing document/page lineage are handled together.
Haryana's active production OCR files remain in place until a safe handoff.
