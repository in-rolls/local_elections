# Tanushree Goyal replication deposit

Full public V1.0 deposit for *Local Political Representation as a Pathway to Power: A Natural Experiment in India*, DOI [10.7910/DVN/9XPV4I](https://doi.org/10.7910/DVN/9XPV4I). Retrieved November 8, 2026. All 53 deposited originals are indexed in `manifest.json`, with Dataverse file IDs, URLs, original-format MD5 checksums, SHA-256 hashes, and byte counts. `metadata.json` retains the full Dataverse description and file inventory.

The three original files already stored under `data/delhi/interim/qualification_audit/sources/` are referenced there, without copies. Original CSV/Stata formats are retained for ingested tabular files because Dataverse's metadata MD5 applies to those originals, not the API's default TSV conversion. The existing converted ward-mapping table remains in place for existing consumers.

The deposit includes raw municipal candidates and affidavits, assembly candidates, career matches, activist and councilor surveys, preparation/analysis scripts, codebooks, maps, and deposited outputs. Presence in this collection does not certify every deposited variable. The Delhi sister collection provides a [2012 comparison report](../../../../local_elections_delhi/report.md), with original SEC records and row-level checks.

Verify or restore missing originals with `python ../local_elections_delhi/scripts/fetch_deposits.py` from this repository's root. Source contents are unmodified; every original passed the Dataverse MD5 and original byte-count checks. No data from this reference collection are automatically appended to the pooled master dataset.
