# Kolkata municipal election, 2015

The typed winner file contains all 144 ward winners from the West Bengal State Election Commission's archived results site. Eight party lists reconcile to the commission's dated April 18, 2015 summary. Every row retains its source HTML file, row, URL and SHA-256. The source describes these online results as informational rather than certified originals.

The separate official April 29, 2015 winner gazette was recovered from the Internet Archive. Two archived copies, captured May 5 and August 29, 2015, have identical bytes. The scan is retained under `raw/kolkata/reference/winner_gazette_2015.pdf`; its first page establishes the election and notification dates. It is not silently treated as a full row-by-row validation of the HTML extraction. KMC's contemporaneous May 2015 councilor list, the SEC municipal election manual and official order catalog are retained in the same reference folder, with receipts. The councilor list has spelling differences from the SEC results, so it does not replace them.

The [TCPD comparison](tcpd_comparison.csv) joins one first-place candidate per ward to the 144 official-source winners. All 144 names agree after whitespace normalization and case folding; five differ in whitespace as printed. This validates correspondence to the retained compilation, not independent collection of the underlying election results. TCPD records reservation categories for all 144 wards: 92 unreserved, 45 women, five SC and two SC-women. Those categories are left in the comparison file pending primary roster verification. Neither source records candidate or winner sex. The winner handoff therefore leaves sex and reservation missing rather than inferring either from personal names or silently transferring a different source's field.

The existing TCPD source also contains 1,044 candidate rows for 141 Kolkata wards in 2010, compared with 1,084 rows and 144 wards in 2015. Those counts do not establish a longitudinal ward link. No post-quota effect is estimated here: independent sex measurement, primary reservation verification and historical ward continuity are still required.

## Files and definitions

- `winners.parquet`: one declared winner per `(year, body, ward_no)`; 144 rows.
- `tcpd_comparison.csv`: one joined pair per ward, with the original TCPD logical data-record number, source path and hash.
- `schema.json`: Parquet field types and nullability.
- `dictionary.csv`: column definitions, transformations and missing-value meanings.
- `checksums.json`: counts, source references and output hashes.

Original winner pages and their acquisition manifest live in `data/west_bengal/raw/kolkata/2015/`. The dated summary is retained once in `data/reference/urban_sources/raw/west_bengal/kolkata-results-2015.html`. The parser pins that file's hash. No candidate names are transliterated or sex-classified.

From the repository root, `make kolkata-harvest` acquires the reviewed eight-page source frame; `make kolkata` rebuilds offline. Run `pytest tests/test_kolkata.py -q` for the affected tests. Error pages, missing table cells, unexpected headers, duplicate or omitted wards, source-hash mismatches and party-count disagreements stop the build. Tests also verify the Parquet round trip and that unknown sex remains missing.
