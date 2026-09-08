# Named-GP reservation search and coverage

Search date: 7 September 2026. The target is the **reservation status of a
named Gram Panchayat's Pradhan office**, separately recording women, SC and
ST. Ward reservations and Upa-Pradhan reservations are separate series.
Result pages without reservation fields are tabled, including Bardhaman's
archived `gpview.asp` pages. They contribute zero reservation coverage.

The new [Birbhum observations](../derived/birbhum_reservations/observations.parquet)
have **165 named GPs** with current and previous reservation fields. They
come from an openly posted [research-data mirror](https://github.com/in-rolls/beaman/blob/main/data/powerful_women_in_india_pradhan_seats_reserved_for_women.dta).
The original DTA and SHA-256 are preserved. These are research observations,
not independently verified official reservation orders.

| Election/period | District/source | Named GP records with all three fields | Qualification |
|---|---|---:|---|
| 2003 current term | Birbhum, Beaman mirror | 165 | 163 explicit 2003 codes; Ayas and Rudranagar have year exceptions |
| 1998 | Birbhum, Chattopadhyay–Duflo | 161 of 166 source rows | One SC/ST contradiction; three GPs conflict with the later source, leaving 158 under the current strict checks |
| Previous term | Birbhum, Beaman mirror | 165 | 152 explicitly say 1998–2003; 10 report shorter terms within that interval; 3 describe post-2003 incumbents and are not assigned to 1998 |

These rows overlap across sources. **Do not add the 1998 counts** or call
the 496 source-period observations a unique GP-election panel. The
[parser documentation](../derived/birbhum_reservations/README.md) explains
the year evidence, raw codes, conflicts and remaining linkage work.

The companion [Pradhan survey](raw/4c57614d02a35bc5.dta) is now preserved
from the same [research mirror](https://github.com/in-rolls/beaman/blob/main/data/powerful_women_in_india_pradhan_survey.dta).
It contains 316 interviews, including 161 marked as current Pradhan. These
are follow-up officeholder and public-goods observations, primarily from
2006, not additional GP reservation records or verified 2003 election winners.
Research identifiers, interview role, date exceptions and conflicting sex
fields require explicit checks. The separate sibling `quota/wb` and
`quota_raj/wb` R folders document and reproduce those checks; the broader
state-by-state extension assessment is in `quota_raj/local_elections_review`.

## District/year gaps

[reservation_gaps.csv](reservation_gaps.csv) and its typed
[Parquet counterpart](reservation_gaps.parquet) enumerate **168 district-cycle
combinations** for the ordinary statewide cycles from 1978 through 2023,
using historical district boundaries. The [holdings ledger](holdings.csv)
records acquired sources. Printed GP universes are separate from parsed
GP counts. A missing universe is unknown, not zero.

[Office parsing by source](office_parsing_by_source.csv) is generated from
the current office outputs. It distinguishes source cells from GP-office
rows, reports visual-review coverage, and keeps draft/final versions separate.
Distinct OCR name strings are not a count of harmonized GPs. The gap matrix
now uses these outputs to update parsing status automatically.

For **2003**, Birbhum is the only district with acquired named Pradhan
reservation observations. Official named-GP schedules remain outstanding
for all 17 ordinary-cycle districts. The other 16 are:

Bankura, Bardhaman, Cooch Behar, Dakshin Dinajpur, Hooghly, Howrah,
Jalpaiguri, Malda, Murshidabad, Nadia, North 24 Parganas, Paschim Medinipur,
Purba Medinipur, Purulia, South 24 Parganas and Uttar Dinajpur.

| Cycle | Ordinary-cycle districts | Pradhan reservation holdings | Remaining districts without acquired named Pradhan data |
|---|---:|---|---:|
| 1993 | 16 | None; earlier SC/ST office policy timing needs verification | 16 |
| 1998 | 16 | Birbhum research records | 15 |
| 2003 | 17 | Birbhum research records | 16 |
| 2008 | 17 | Two named judgment records in Purulia and North 24 Parganas; cycle inferred. Nadia files are ward reservations | 15 |
| 2013 | 17 | Nadia office schedules and a 187-GP handbook roster parsed; one Pradhan category blank | 16 |
| 2018 | 20 | Purulia, South 24 Parganas and Alipurduar office schedules parsed; positive lists leave absent offices unknown | 17 |
| 2023 | 22, including the two hill districts | Birbhum, Jalpaiguri, Cooch Behar and Alipurduar office schedules parsed; review status varies | 18 |

“Not acquired” describes this collection. It is not a finding that the
underlying data do not exist. No cell is marked district-complete merely
because its order has been downloaded. `head_gp_officially_verified` remains
a conservative verification field, not a measure of official-source holdings.
Official office schedules are now parsed, with source hashes, review status
and unresolved cells retained in the [office outputs](../derived/README.md).
Neither extraction nor agreement with a printed total certifies every GP name.

[court_observations.jsonl](court_observations.jsonl), also exported as
[Parquet](court_observations.parquet) and [CSV](court_observations.csv),
records two independently checked Pradhan-office statements:
**Bagmundi, Purulia: SC**; **Gachha Akharpur, North 24 Parganas: SC woman**.
The [first judgment](https://indiankanoon.org/doc/47825893/#blockquote_5)
is dated 7 July 2008 and refers to the last election; the
[second](https://indiankanoon.org/doc/44528410/#blockquote_7) describes the
office before July 2009 no-confidence proceedings. Their assignment to
the 2008 general-election cycle is explicitly an inference, not a printed
election-year label. Unmentioned category components remain null. Neither
judgment supplies the reservation-order date in the cited passage.
These isolated records do not establish district coverage, and are counted
only in `head_gp_judgment_evidence`, not the strict survey extraction count.

One court-observation row is one judgment's named-GP office statement.
`category_raw` preserves its wording; `reserved_sc`, `reserved_women` and
`reserved_st` record only explicitly stated category components. The
`judgment_date` and `election_year_inferred` fields distinguish observation
date from inferred cycle. `source_url`, `source_anchor`, `source_locator`,
`source_file` and `source_sha256` trace the reading to the fetched HTML.
`block` and `reservation_order_date` remain null when not stated.
`review_status` records the remaining date/order verification. The JSONL
is a curated transcription; `reservation_coverage.py` checks source hashes
and exports the typed table. No missing category is converted to No.

Darjeeling hills and Siliguri require their own election calendar. They
are **not silently treated as missing 2003 elections**. The
[special-cycle ledger](special_cycles.csv) separates confirmed cycles,
known gaps between elections and years still needing calendar verification.
The 2023 hill districts are included in the main matrix. Kolkata has no
rural GP universe. The district splits follow the
[state environmental report](https://www.wbpcb.gov.in/writereaddata/files/SOE_Report_2016_1.pdf),
[Paschim Bardhaman history](https://paschimbardhaman.gov.in/history/),
[Jhargram history](https://jhargram.gov.in/about-district/) and
[Kalimpong district](https://kalimpong.gov.in/).

The pre-1998 rows are a historical search backlog, not zero-valued head
reservation assignments. The **women's Pradhan quota** series began in
1998. Accounts of earlier SC/ST office reservation differ: the authors'
[earlier paper](https://people.bu.edu/dilipm/publications/wbtreserv.pdf)
explicitly dates SC/ST Pradhan reservation to 1993, while their
[later study](https://eml.berkeley.edu/~webfac/bardhan/papers/WBReserv1209finalverjgd_rev1.pdf)
describes the 1998 office reform more broadly. Contemporary orders are
needed to resolve the category-specific timing. The matrix leaves 1993
open rather than assuming every office was unreserved or out of scope.

## Search leads and retrieval limits

- **Six-district Beaman package:** the [full Dataverse inventory](https://dataverse.harvard.edu/api/datasets/:persistentId/?persistentId=doi:10.7910/DVN/O3UKFO)
  identifies `election_pradhan_alldist.tab` (file 13986379) and district
  files for Bardhaman, Hooghly, Howrah, Nadia and South 24 Parganas, in
  addition to Birbhum. Claude inspected metadata reporting 1,316 GP rows
  and 1998/2003/2008 reservation fields. The latest identifiers are
  anonymized; this is a lead, not acquired named-GP coverage. File downloads
  require guestbook 269. A request for the user's guestbook details is
  pending; no invented information has been submitted.
- **Bardhan–Mookherjee:** the [AER replication project](https://www.openicpsr.org/openicpsr/project/112367/version/V1/view)
  is E112367V1. Related studies describe 89 villages in 57 GPs; these are
  different units. The project file inventory remains uninspected because
  access returned 403. It remains a priority for 1993/1998/2003 variables.
- **QE 2024 replication:** the [Zenodo ZIP](https://zenodo.org/records/10805145)
  was acquired and its two main data tables inspected. The reservation
  variable found concerns Assembly constituencies, not GP Pradhans. It
  fills no GP reservation gap.
- **Wayback and district portals:** the fetch log retains both successes
  and timeouts/HTTP errors. WBSEC returned an expired TLS certificate and
  server errors. Old PRD searches found administrative reports rather than
  named office rosters. Retry reservation-specific archive queries and
  investigate district/block office lists; do not resume results-only pages.

The [2003 archive-search audit](archive_search_audit.csv) now covers broad
index requests for all **17 historical districts**, allowing captures through
2007 so that later snapshots of 2003 files can be found. Nine districts
returned indexes, containing 2,242 original URLs in total; eight districts'
requests failed. These are URL counts, including images and unrelated pages,
not GP counts or a claim that every indexed page was downloaded. The Howrah
NIC index contains only `robots.txt`, and its GOV-domain request failed.
No additional named 2003 Pradhan schedule was acquired in this pass.
The [query-expansion log](query_expansion.jsonl) records the additional
English/Bengali, research-repository and judgment queries and their outcomes.

The follow-up checks are preserved, including exclusions:

- Malda's index lists PDFs for all 15 blocks. The acquired Bamangola and
  Chanchal-I PDFs are one-page maps. The other 13 PDFs remain uninspected;
  the two checks do not establish their contents.
- Cooch Behar-I's block profile links GP names without reservation categories.
  Its district ZP profile concerns a different tier. Murshidabad's statistics
  page gives a 255-GP aggregate, and Nadia's Panchayati Raj page gives a
  187-GP universe corrected after the 2003 election; neither assigns named
  GPs to office categories.
- Requests to the SEC's separate `archive.wbsec.org` portal timed out over
  both HTTP and HTTPS. Focused Bardhaman/Birbhum reservation-index retries
  also failed. These remain retrieval tasks.
- Expanded English/Bengali searches and university-repository searches found
  district totals and leadership studies, but no further verified named
  2003 reservation assignments. The unnamed GP in the 2003 Bidhya Charan
  Sinha judgment remains unlinked; similarly named people are not a crosswalk.
- Two later judgment leads remain outside the curated table: Lovely Bibi
  (Akheriganj, 2018 election context, Backward Class woman) and the official
  2023 WPA 23176 judgment (ST Pradhan office). The former download redirected
  to a login page; the latter failed TLS negotiation. Their exact attempted
  URLs and outcomes are in the fetch log. Neither is counted as acquired data.

Actual **Claude and agy** searches were recruited. Their reports and public
briefs are in [agents/](agents/); read the [verification notes](agents/review.md)
before using their claims. In particular, agy's tool cancellation was an
access-permission failure, not evidence about data availability, and
matching reservation patterns is not an acceptable GP identity crosswalk.
The later agy court search completed and supplied the two leads above;
its mistaken paragraph locators and unsupported reservation-order date
were corrected in the curated table. Claude's additional follow-up hit a
session usage limit and produced no new evidence.

## Reproduction and source handling

Run `make wb-gp-reservations`. The parser verifies the acquired Beaman DTA
checksum, enforces one-to-one source joins and tests Parquet round trips.
Run `uv run pytest tests/test_wb_reservations.py tests/test_wb_gp.py -q`.

[fetch_log.jsonl](fetch_log.jsonl) gives original/retrieved URLs, dates,
HTTP outcomes, paths, byte counts and SHA-256. Raw files are immutable;
archived research code is excluded from repository linting. The previous
[manual-entry index](../gp_source_search/manual_entry_index.csv) continues
to locate reservation scans, document versions and exact duplicates.

The result-only tables already acquired are preserved as supplemental
files. They are excluded from this matrix and from the reservation parser
target. None of these new research observations has been added to the
pooled official-reservation data.
