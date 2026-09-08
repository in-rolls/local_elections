# Early GP-head source search

This first search wave preserves sources before full transcription. The Tamil
Nadu and Mau documents contain named GP-head reservation evidence. The full
Tamil Nadu 2011 schedule now has a parsed export with 12,524 distinct named
entries; other source and historical-coverage counts remain separately audited.
File, page and repeated-row counts must not be reported as unique GPs.

| State / geography | Early years supported or under investigation | Acquired evidence and next step |
|---|---|---|
| West Bengal, six research districts | 1998, 2003, 2008 | Public metadata for a combined 1,316-case election file confirms reservation fields and 1,141 valid 2003 sex values / 1,309 valid 2008 sex values. Microdata require guestbook details. Verify identifiers, sex coding, officeholder timing and jointly complete counts before analysis. See the [WB availability audit](../../wb/vintage_search/head_outcome_availability.md). |
| Tamil Nadu | 1996; 2001 amendments; 2006 and 2011 follow-up | Eight gazette PDFs preserved, 1,444 pages across several office tiers. The complete 2011 GO61 roster is parsed: 12,524 named entries, 12,523 observed categories, 31 districts and 385 unions. See the [typed export and dictionary](../../tn/readme.md). All 132 selected early scan pages have OCR evidence; The separate [2001 amendment export](../../tn/derived/amendments_2001/README.md) contains 456 operations (434 replacement rows, 17 insertions and five serial-addressed category changes); 451 names were checked against source images and five targets remain unnamed. Reconstruct 2001 from the 1996 base and its amendments; apply 2006 errata. No elected-person sex found on reviewed schedules. |
| Uttar Pradesh, Mau, nine blocks | Columns for 1995, 2000, 2005, 2010, 2015; partial 2021 | Nine PDFs preserved, 107 pages; 27 pages inspected. Named GPs recur in differently sorted lists. Extract each occurrence, reconcile histories, preserve literal NA and blanks, and verify category-code meanings before deriving reservation flags. No head-winner sex found. See the [review](up_mau_source_review.md) and [source profile](up_mau_source_profile.csv). |
| Rajasthan | 2000/2005 reservation histories; 2010/2015 outcomes reported by researchers | A preserved author paper describes a 382-GP study sample with election information. Its microdata have not been acquired in this wave. Find the replication deposit and verify the coverage and identifiers. Hanumangarh's gazetteer provides historical block/district totals only. |
| Bihar | 2001 chronology; 2006 onward head records | A preserved Sharan–Kumar paper describes Mukhiya data for 2006/2011/2016 and dates the introduction of head reservations to 2006. Inspect existing 2006 spreadsheets before treating absence from the current pooled master as missing raw data. The paper is source context, not acquired microdata or a contemporary 2001 assignment roster. |
| Madhya Pradesh | 1994 case evidence; broader early cycles under investigation | A preserved FAO case account names a GP and describes its reserved Sarpanch office. A separate field-report request returned HTTP 403. Neither establishes a representative GP series. Continue district, gazette and research-package searches. |
| Odisha | Early cycles under investigation | Two contextual source downloads failed: a compiled statute timed out, and a historical election article failed certificate verification. The URLs and failures are retained. No named early head roster was acquired in this wave. |

The [current-master baseline](current_master_head_coverage.csv) describes only
registered pooled GP-head records. It is not an inventory of all raw holdings,
and the master's lack of a sex column does not prove that every source lacks
one. The WB audit separately inspects source-specific datasets. No state in
this table has been declared exhaustively searched.

## Verify the evidence

[source_manifest.csv](source_manifest.csv) maps every retained raw response in
this folder to its original URL, final URL, retrieval time, HTTP status, byte
count and SHA-256. A retained HTTP error response is explicitly marked as an
error, not as acquired research data. The append-only
[acquisition log](acquisition_log.jsonl) also preserves failed requests without
a response body. The request queues retain discovery context and parent pages;
[search_queries.csv](search_queries.csv) records searches actually performed.

[SHA256SUMS](SHA256SUMS) covers all raw files in this folder, including the
retained error response. From the repository root, verify with:

```sh
shasum -a 256 -c data/source_search/early_heads/SHA256SUMS
```

This raw-file manifest supplements the repository's pooled-data manifest. It
does not claim to cover all WB evidence or all files in the repository. Page
images have separate hashes in [TN's page ledger](tn_review/page_review.csv)
and [Mau's source profile](up_mau_source_profile.csv). The original PDFs remain
unchanged; review images and native text are derivatives. Page references use
one-based PDF pages, with printed pagination recorded separately where known.

The review documents state exactly which pages were inspected. They do not
certify unreviewed pages or supply a transcription accuracy estimate. Subsequent
parsing must retain document hash, page, row/cell location, raw reading,
normalized value, parser/OCR settings and correction history. An unresolved
reading stays unresolved. Human review requests should show the relevant page
or crop and the competing readings, retaining the user's adjudication as a
separate record.

Sources remain available for manual entry even when automatic parsing fails.
Public availability alone is not a license determination. Preserve stated
reuse terms, and resolve redistribution requirements when preparing assets.
[SOURCE_MANIFEST.json](../../../SOURCE_MANIFEST.json) maps the preserved
evidence to downloadable release assets and records hashes for verification.

## Research order

Resolve the six-district WB election file first for `quota_raj`; retain the
Birbhum incumbent exercise as exploratory and Nadia's demand exercise under
`quota`. Establish coverage and measurement before selecting new analyses.
For each subsequent state, audit the unit, identifiers, long/wide structure,
historical geography, actual reservation assignment and observed head outcomes
in a separate analysis folder. Neither a reservation schedule nor a stated
rotation rule alone establishes random assignment.

Claude and AGY research briefs are retained under `agents/`; the external CLI
search was not run because repository-sharing authorization remains pending.
