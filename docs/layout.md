# State repository layout

Every state repository (`local_elections_<state>`) lays out its data the same
way, so a reader who knows one knows all of them and the pooled repository's
adapters read every state from the same place. `tools/check_layout.py` checks
it (`make layout`). Column names follow [naming.md](naming.md).

## Folders

    data/
      raw/                  bytes exactly as received; never edited
        <source or year>/   grouped by publisher or election; files keep
                            the names they arrived with
        fetch_log.csv       one row per file under raw/
      reference/<dataset>/  third-party tables used as they came (LGD, Census)
      manual/               hand-entered readings and corrections the build reads
      extracted/            machine readings of raw/: OCR text, page caches
      build/                our intermediates: joins, transliteration caches,
                            model call records; rebuildable by code (some
                            only at a cost), never cited
      release/              the published tables
        <year>/<office>_<record>.parquet
        <office>_<record>.parquet   a table whose rows span elections
                                    (with a `year` column)
        linkage/            seats linked across elections
        inferred/           model outputs (`*_probability`)
        MANIFEST.json, CATALOG.md, DICTIONARY.md, CHECKSUMS.sha256
                            optional documents describing the release
      checks/               hand checks, review ledgers, check results
      search_log/           where we looked and what we found: site
                            catalogues, search queues, collector run logs
      MANIFEST.json         sha256, rows and schema of every released table
      README.md             what each released table holds, one row per what

Nothing else sits directly under `data/`. A folder is named for what it holds,
never for when or how it arrived (`recovery/`, `fin/`, `source/`, `interim/`,
`external/`, `historical_handoff/`, `v2/`). How it arrived goes in the fetch
log.

A repository whose sources are many separate crawls, each with parsed runs
checked against its own responses (Uttar Pradesh), may also keep
`data/collections/<collection>/`, named for publisher and contents
(`ballia_media_reservations_2021`), with the same stage words inside it:
`raw/`, `extracted/`, `checks/`, `search_log/`.

`release/` is the contract with the pooled repository: an adapter reads only
`data/release/`, and `data/sources.json` pins each file it reads by commit and
sha256. A released path is permanent; moving one means repinning the adapter in
the same change.

## The fetch log

`data/raw/fetch_log.csv` has a row for every file under `data/raw/`, plus a row
for each download that was byte-identical to a file already kept (not stored;
`duplicate_of` names the kept file). Required columns:

| Column | Holds |
|---|---|
| `path` | relative to the repository root |
| `url` | where the bytes came from; blank when nobody recorded it |
| `sha256` | of the file as committed |
| `bytes` | its size |
| `fetched_at_utc` | ISO 8601; blank when unknown |
| `method` | `live`, `wayback`, `request`, `manual`, `copy`, or `unknown` |

A file too large to commit as received is stored gzipped (`<path>.gz`) or split
into `<path>.part_a`, `.part_b`, ... ; its row keeps the received name and the
sha256 of the received bytes.

A file copied byte-identical from another repository has `method=copy` and a
`copied_from` column naming `<repo>@<commit>:<path>`. Other columns
(`referrer`, `http_status`, `content_type`, `duplicate_of`) may follow. A file
with no recorded URL keeps a blank `url`; the log never invents one.

## Code

    src/local_elections_<state>/
      paths.py   every folder above, named once
      collect/   download raw files and append to the fetch log
      extract/   raw/ -> extracted/ (OCR, page caches)
      parse/     raw/ and extracted/ -> release/<year>/
      linkage/   release/<year>/ -> release/linkage/
      infer/     release/<year>/ -> release/inferred/
      build/     manifests, checks, joins, review sheets
    tests/

Make targets: `sync`, `collect` (network), `data` (offline rebuild from
`raw/`, `extracted/` and `manual/`), `check` (lint, tests, fetch-log hashes,
manifest). `make check` must pass from a fresh clone without the network.
