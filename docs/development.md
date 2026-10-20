# Development and data layout

Install the locked environment with `uv sync --frozen --group dev`. Python 3.12
or later, Poppler and Tesseract are required for the full test suite. Bengali
OCR checks also require Tesseract Bengali data. Model OCR has separate optional
dependencies; ordinary parsing reads retained evidence offline.

State data live under `data/<full_state_name>/`: `raw/` contains acquired
sources, `interim/` contains extraction and review artifacts, `release/` contains
consumer tables, and `discovery/` contains unadmitted research collections.
Discovery bundles retain their own acquisition records and source bytes.
Pooled tables remain in `data/master/`; cross-state discovery, integration
receipts, statistics and transliteration each have separate shared directories.

`data/datasets.json` explicitly lists pooled inputs and supplemental tables.
A table does not enter the pooled build because it resembles another table or
sits in a release folder. Additions require registration and validation.
The registered state directories also control generated state documentation.

`source_path` is a historical source identity. `data/relocations.csv` records
its current location and the SHA-256 at relocation. Use
`local_elections.paths.resolve_path(source_path)` to open relocated evidence.
Do not replace historical identities in analytical rows: row and candidate IDs
must survive a directory move. Acquisition receipts and historical snapshots
retain the locations recorded at the time; the relocation ledger resolves them.

Run `make <state>` to parse and validate a state, using the command in its
README. `make master` builds pooled tables from registered local files and
pinned sibling inputs in `data/sources.json`. `INDIA_DATA_HOME` selects the
shared input cache; its default is `~/data`. `make coverage` rebuilds the
coverage tables, state guides, source holdings and worklist. `make dictionary`
regenerates the column definitions. Edit generators instead of their outputs.

Run `uv run ruff check .`, `uv run ruff format --check .`, `uv run pyright`,
`uv run pytest tests -q`, and `make ci-docker` before submitting changes.
The Docker target also checks docstrings and package builds. Run `make verify`
for pooled and parsed file hashes. `make evidence` inventories current source
evidence; `make evidence-archives` packages it. Keep previously published
archives with their original manifests. Verify an archive set with
`uv run verify-manifest --manifest SOURCE_MANIFEST.json --archives /path/to/assets`.

Keep documentation close to its purpose: the root README introduces the data,
`docs/` holds project guides, and dataset READMEs explain source units,
limitations and reproduction. Consolidate research findings into source guides
and structured ledgers. Session reports and repeated progress summaries belong
in Git history, not the current checkout.
