# Local elections in India

Reservation and election-result data for India's local bodies. Coverage varies
by state, year, and tier; consult the [coverage tables](docs/coverage.md) before
combining records.

Download pooled Parquet tables from [GitHub releases](https://github.com/in-rolls/local_elections/releases)
(`pooled_data_*.tar.gz`). Start with the [pooled data guide](data/master/readme.md)
for row units, columns, joins and limitations. Python distributions contain code;
source-evidence archives are separate downloads for auditing and rebuilding.

- [Data dictionary](docs/dictionary.md): column definitions and allowed values.
- [Source survey](docs/sources.md): available sources and acquisition gaps.
- [Worklist](docs/worklist.md): detected defects, unresolved questions and accepted source limitations.
- [Changelog](CHANGELOG.md): corrections and release changes.

## Remaining work

The same row can trigger several diagnostics. These counts are not estimates
of missing seats and must not be added together.

<!-- worklist:start -->

| | Entries | Rows affected |
|---|---|---|
| [Open gaps](docs/worklist.md) | 83 | 114,283 |
| [Blocked](docs/worklist.md) | 2 | 50,013 |
| [Parked](docs/worklist.md) | 9 | 1,653 |
| [Undetermined](docs/worklist.md) | 33 | 15,901 |
| [Accepted properties of the sources](docs/worklist.md) | 24 | 141,030 |

<!-- worklist:end -->

## Reproduction and verification

State inputs are pinned by revision and SHA-256 in [data/sources.json](data/sources.json).
`INDIA_DATA_HOME` selects the shared input cache (default `~/data`).
[Registered datasets](data/datasets.json) separate pooled inputs from supplemental
exports. Cross-year GP matching belongs to the state repositories.

[MANIFEST.json](MANIFEST.json) records parsed and pooled file hashes and schemas.
Verify a checkout with `python3 src/local_elections/tools/verify_manifest.py`.
[SOURCE_MANIFEST.json](SOURCE_MANIFEST.json) records source evidence and archive
members. Historical source paths resolve through the [relocation ledger](data/relocations.csv);
record IDs remain unchanged when files move.

See the [development guide](docs/development.md) for setup, directory layout,
commands and checks, and the [state repository contract](docs/state_repositories.md)
for ownership and handoffs. Dataset READMEs describe source-specific limitations.
