# West Bengal GP data recovered from district and web archives

**Current priority:** [named-GP Pradhan reservation data and district/year
gaps](vintage_search/README.md). The new Birbhum research extraction has
165 named GPs with current reservation fields, including 163 explicit
2003 year codes. [Year exceptions and source conflicts](derived/birbhum_reservations/README.md)
are preserved. Results-only pages, including Bardhaman's `gpview.asp`
series and Hooghly party tallies, are tabled and contribute no reservation
coverage. The acquisition history below includes those earlier searches.

Searched 6–7 September 2026. **518 PDFs totaling 2,886 pages** are now
saved, alongside original ZIP/RAR files and HTML result tables. There are
**503 distinct PDF hashes**; the [manual-entry index](gp_source_search/manual_entry_index.csv)
flags exact duplicates. Three administrative-notice PDFs are marked reference
only, leaving 500 distinct PDFs available for review. The index contains both
seat-level sources and useful district/block summaries; document counts are
not counts of GPs or usable observations.

The strongest results acquisition is **Alipurduar's 2018 candidate-level GP
results archive**. Reservation sources now include 2023 orders from four
districts, 2018 schedules from Purulia, Alipurduar, Cooch Behar and South 24
Parganas, and older Nadia/Malda documents. A **2003 results table names
210 Hooghly GPs**. These acquisitions are preserved for manual entry and
have not been added to the pooled reservation dataset.

## Initial 2023 reservation acquisitions

All 32 PDFs are in [2023/gp_sources/](2023/gp_sources/). The
[manifest](2023/gp_sources/manifest.csv) records each original URL, landing
page, district, election year, draft/final stage, byte count, SHA-256, page
count and extractable-text size. The files total 125,301,112 bytes.

| District | Election | Source | What was recovered |
|---|---|---|---|
| Birbhum | 2023 | [Final ward orders, 25 November 2022](https://birbhum.gov.in/notice/district-magistrate-district-panchayat-election-officer-birbhum-2/) | All 19 linked block Form A1 PDFs, 240 pages; the covering notice identifies 167 GPs |
| Birbhum | 2023 | [Final office orders, 30 December 2022](https://birbhum.gov.in/notice/district-magistrate-district-panchayat-election-officer-birbhum-3/) | Pradhan Form 1B, 6 pages, and Upa-Pradhan Form 1B, 2 pages |
| Jalpaiguri | 2023 | [District notice archive](https://jalpaiguri.gov.in/past-notices/announcements/page/11/) and [Kranti notice](https://jalpaiguri.gov.in/notice/notice-from-office-of-the-district-magistrate-district-panchayat-election-officer-for-delimitation-of-constituencies-and-reservation-of-seats-of-kranti/) | Nine block Form A PDFs, 204 pages; these are **drafts** from October 2022 |
| Jalpaiguri | 2023 | [Final office order, 30 December 2022](https://cdn.s3waas.gov.in/s3fccb60fb512d13df5083790d64c4d5dd/uploads/2022/12/2022123049.pdf) | Five pages covering Pradhan, Upa-Pradhan, Sabhapati and Sahakari Sabhapati |
| Cooch Behar | 2023 | [District notice archive, final Form 1B](https://coochbehar.gov.in/past-notices/announcements/page/11) | Nine-page final office reservation order, dated 30 December 2022 |

The Pradhan schedules state the following district totals. These are printed
controls, not counts from a completed extraction. Women overlap the caste
categories and must not be added to them.

| District | Pradhan offices | SC | ST | BC | Women | PDF page |
|---|---:|---:|---:|---:|---:|---:|
| Birbhum | 167 | 47 | 12 | 20 | 81 | 1 |
| Jalpaiguri | 80 | 29 | 11 | 0 | 40 | 1 |
| Cooch Behar | 128 | 63 | 1 | 0 | 64 | 2 |

The schedules identify reserved GPs by name in separate caste and women's
columns. Their combined universe is 375 Pradhan offices, but they are not
375 already parsed rows. A complete roster needs the unreserved GP universe
and block identifiers too. Birbhum's printed women's total is 81; do not
replace it with a number calculated from an assumed quota. Jalpaiguri's
embedded text misreads the printed ST total of 11 as 17, demonstrating why
the page image must control the extraction.

The ward forms contain actual constituency identifiers. On page 1 of
Birbhum's Bolpur-Sriniketan order, Sattore/I-1 is SC and women-reserved,
Sattore/II-2 is women-reserved, and Sattore/IV-4 is SC. The page prints a
20-member GP total and category controls. Jalpaiguri's Rajganj document
explicitly invites objections to its draft; it must not be pooled as final.

All files opened successfully with `pdfinfo`; hashes and byte counts were
checked locally. Selected ward and office pages were rendered and visually
inspected. Thirty-one PDFs have no extractable text. Jalpaiguri's final
office order has a text layer with OCR errors. Acquiring these files solves
source access, while OCR, reconciliation and row-level validation remain.

## Hooghly: GP-level election results from 2003

Wayback preserved the district's
[Gram Panchayat Status on Contesting Seats](https://web.archive.org/web/20041117101744/http://hooghly.nic.in:80/hzp/Panch_election1/total.htm).
The original HTML is saved as
[hooghly_2003_total.htm](gp_source_search/hooghly_2003_total.htm), with its
capture timestamp and checksum in the
[historical source manifest](gp_source_search/manifest.csv).

The table contains 210 distinct block/GP pairs across 18 blocks, followed by
a total row. Columns are block, GP, `seats_contested`, `seats_declared`, and
counts for AIFB, AITC, BJP, BSP, CPI, CPI(M), INC, MFB, RSP and Others.
For example, Kodalia-II has 20 contested seats and party counts of 1 AIFB,
6 AITC, 11 CPI(M) and 2 Others.

The total row reports 2,033 contested seats and 3,440 declared seats. The
party columns sum to 2,033, so this is not a complete allocation of all seats
to parties. GPs with zero contested seats can have positive declared seats
and zero party counts. Preserve that distinction when extracting or computing
party shares. The source has no candidate names, vote totals or reservation
fields. It is useful GP-level electoral data, but cannot supply a reservation
roster on its own.

## Historical reservation survey already on disk

[chattopadhyaya_duflo.zip](chattopadhyaya_duflo.zip) contains named GP data
that the current parsed coverage does not use:

- `womenpolicymakers_parta.dta`: 166 rows, 121 columns, unique `gpnum`.
  `womres`, `scres` and `stres` record Pradhan reservation, each with 161
  nonmissing observations and five missing values.
- `womenpolicymakers_partb.dta`: 166 rows, 258 columns, unique `gpnum`, with
  `gpnamep`, `blockp` and `subdiv`. Its GP identifiers match all 166 Part A
  identifiers. The first names are Bahiri Panchsora, Kankalitala and Kasba,
  in Bolpur-Sriniketan.
- The Part A codebook explicitly defines **1 = yes, 2 = no**. Counts are
  women 54 yes / 107 no; SC 55 yes / 106 no; ST 19 yes / 142 no. Missing
  responses must remain missing.
- `womenpolicymakers_resurveya.dta`: 114 rows, including Pradhan and
  Upa-Pradhan reservation questions. Variables asking whether the GP *will*
  be reserved at the next election in 2003 are prospective survey responses,
  not verified final 2003 orders.

The underlying [study description](https://poverty-action.org/study/impact-women-policy-makers-public-goods-india)
identifies Birbhum as the West Bengal study location. Establish the exact
survey/election linkage and acquisition provenance before creating a dated
administrative slice. The ZIP's 2022 member timestamps are not election dates.

J-PAL also links a [public Dataverse deposit](https://doi.org/10.7910/DVN/PXV79W)
from its [Powerful Women study page](https://www.povertyactionlab.org/evaluation/perceptions-female-leaders-india).
This is a further historical lead: the study discusses exposure to reservations
in 1998 and 2003 and subsequent elections. Dataverse metadata requests returned
HTTP 403 in this search, so its file contents and geographic identifiers have
not been verified here.

## Archive routes checked and remaining gaps

The saved [probe log](gp_source_search/probes.json) records URLs, outcomes and
the search date. Four CDX responses are saved alongside it. These were targeted
queries for URLs containing panchayat/reservation/Pradhan/delimitation terms,
not exhaustive inventories of every district file.

- The old Birbhum domain yielded a 2003 PDF, now held, but it contains only
  district totals. It does not name GPs.
- The old Hooghly domain yielded the useful GP table above, plus coarser
  block/party tables. Some other archived pages returned HTTP 503.
- The Jalpaiguri archive index exposed Kranti's notice, completing the nine
  linked block drafts. The same query on `jalpaiguri.nic.in` returned an
  empty response; this does not establish that no old PDFs are archived.
- SEC's `archive.wbsec.org` 2013/2018 result menus and the 2018 GP results
  endpoint timed out. The current `wbsec.gov.in` request failed certificate
  verification because its certificate had expired. Neither outcome is
  evidence that the underlying data do not exist.
- [Cooch Behar's 2018 GP result link](https://coochbehar.gov.in/pge-2018/)
  resolves to a one-page PDF containing 12 **block** totals, despite the GP
  link label. It is retained as useful block-level electoral data. The PDF itself is dated
  22 May 2018; its 2023 upload path does not change the election year.
- Hooghly's current 2023 election page concerns election staff management.
  The Jangipara block page mentions Pradhan reservation, but no usable
  download was established in this search.

Statewide GP coverage remains incomplete. The acquisitions below substantially
extend the historical and district coverage; failed downloads remain explicit
retry leads. Raw acquisition is prioritized over parsing for manual entry.

## Expanded acquisitions for manual entry

The search continued across old and current district domains, archive indexes,
election handbooks, result annexures, office-reservation ZIPs and linked cloud
storage. Parsing is not a condition of acquisition. Original scans, HTML and
archives are retained, and PDFs inside the main ZIP/RAR bundles are extracted
for direct access. The [manual-entry index](gp_source_search/manual_entry_index.csv)
records file paths, source URLs, container/member relationships, page counts,
hashes, document classifications and duplicate files. `verify_per_document`
means the file is acquired but its exact form or stage still needs review.

### Alipurduar: actual 2018 candidate results

The district's [archived final-results ZIP](http://web.archive.org/web/20220703131738id_/http://alipurduar.gov.in/PanchayatGeneralElection2018/FinalResultofPGE2018.zip)
was recovered and is held in
[alipurduar_2018_results/](gp_source_search/alipurduar_2018_results/).
It contains **27 PDFs, 176 pages**, arranged under Alipurduar-I, Alipurduar-II,
Falakata, Kalchini, Kumargram, Madarihat and a district directory.
The ZIP is 42,966,509 bytes. Its archive capture is from 2022; the forms
explicitly concern the **2018 election**.

This is the strongest new results source. Annexure IIA, labelled Gram
Panchayat election results, contains GP name, constituency/seat identifier,
reservation status, electors, votes polled, rejected votes, every listed
candidate's name, party and votes, and the declared winner and party.
For example, PDF page 1 of `APD-II GP IIA.PDF` lists Chaparerpar-I seats;
Chaparerpar I/I-1 is SC and the declared winner is Rabindra Das (AITC),
with 394 votes. Candidate/seat coverage and arithmetic have not been audited.
Some PDFs combine annexures and some appear to be corrected or overlapping
PS reports: use the original forms to resolve duplicates before pooling.

Separate Alipurduar 2018 `OfficeBearer.pdf` and `SeatReservation.pdf` files
were also acquired in [historical_expansion/](gp_source_search/historical_expansion/).
`OfficeBearer.pdf` has **12 pages**: it opens with a state ZP office gazette,
then includes final Alipurduar GP Pradhan/Upa-Pradhan schedules. PDF pages
4–5 contain the Pradhan order and named GPs. `SeatReservation.pdf` has
**104 pages** of final GP/PS orders dated 28 December 2017. Its first page
is PS Form B1; its last page lists Sishujhumra GP's 18 seats, including
SC/ST and women's reservations. These sources allow reservation and results
to be linked within the same district/election after manual entry.

### More 2023 sources

- **Alipurduar:** [official ward page](https://alipurduar.gov.in/information-window-pge-2023-form-a-form-b/)
  and [office-order page](https://alipurduar.gov.in/information-window-pge-2023-2/)
  yielded **82 PDFs, 217 pages**, saved in [2023/alipurduar/](2023/alipurduar/).
  They include 64 GP ward PDFs across six blocks, six PS PDFs, and 12
  office/ZP documents. Of the 82, 76 are classified as final and six as draft
  from their publication labels. Preserve the separate draft and final orders.
- **Cooch Behar:** the [final A1/B1 notice](https://coochbehar.gov.in/notice/final-publication-of-form-a-and-form-b-of-all-g-p-p-s-and-zilla-parishad-of-cooch-behar/)
  links a [public RAR archive](https://drive.google.com/file/d/1Q3YxcYKOnbFIoqI4RfEWFgse1M8rJ3NF/view).
  The 135,658,951-byte archive is saved in [2023/cooch_behar/](2023/cooch_behar/),
  with **126 extracted PDFs, 426 pages**, arranged in all 12 block directories.
  It mixes individual-GP PDFs, combined-GP PDFs, PS orders and repeated ZP
  orders. Thus 126 files is not a count of distinct GPs or independent orders.

### Earlier reservation sources and handbooks

- **Purulia 2018:** [Pradhan ZIP](https://web.archive.org/web/20190404175359id_/http://purulia.gov.in/services/notice/general/1B_Pradhan.zip)
  and [Upa-Pradhan ZIP](https://web.archive.org/web/20190404211110id_/http://purulia.gov.in/services/notice/general/1B_Upa-Pradhan.zip)
  contain **20 block PDFs each**, 40 pages in total. Both ZIPs and their
  extracted PDFs are held in [archived_district_files/](gp_source_search/archived_district_files/).
  The inspected Arsha Pradhan order is final Form 1B dated **6 March 2018**,
  naming GPs reserved for SC/ST/BC and women. It prints district controls:
  170 offices, SC 31, ST 34, BC 20, women 85. These district controls repeat
  on block schedules and must not be summed across the 20 files.
- **Nadia 2008:** the archive exposed individual-GP and block Form A1/B1
  schedules under `PanchayatElection08/Delimitation/`. Recovered files are
  in [historical_expansion/](gp_source_search/historical_expansion/), with the
  exact GP/block path retained in each manifest URL. The inspected Badkulla-II
  Form A1 names constituencies and shows 13 GP seats, two SC seats and five
  women's seats. Acquisition is partial; the manifest explicitly records
  unsuccessful requests. A file's presence does not establish full block coverage.
- **Nadia 2013:** the [Pradhan/Upa-Pradhan PDF](https://web.archive.org/web/20140703221117id_/http://nadia.nic.in/Election/Pradhan%20&%20Upa-Pradhan.pdf)
  is final Form 1B dated **15 March 2013**. The separately acquired
  [district election handbook](https://web.archive.org/web/20140703205812id_/http://nadia.nic.in/Election/Panchayat%20General%20Election%20-%20final%20book(election%202013).pdf)
  contains **named GP reservation tables**, 2008/2013 constituency and seat
  totals, and block electoral statistics. Its contents identify reservation
  tables at printed pages 45–71; PDF page numbering differs. For example,
  PDF page 50 names Chhitka, Kanainagar, Raghunathpur and other GPs with
  SC/ST/OBC and women's reservation counts. Column definitions distinguish
  caste-with-women seats from the other women's seats.
- **Malda 2013:** 14 of the 15 identified block PDFs were recovered,
  **390 pages**: Bamongola, Chanchal-I, Chanchal-II, English Bazar, Gazole,
  Habibpur, Harishchandrapur-I, Harishchandrapur-II, Kaliachak-I,
  Kaliachak-II, Kaliachak-III, Manikchak, Old Malda and Ratua-I.
  Ratua-II remains unretrieved. Most are in
  [archived_district_files/](gp_source_search/archived_district_files/);
  [Old Malda](gp_source_search/followed_links/malda_696e786383.pdf) was
  recovered using an alternate archive rendition. A separate ZP reservation
  PDF is also preserved.
  The inspected Bamongola PDF mixes PS and GP forms: page 1 is PS Form B1;
  page 14 lists Jagdalaya GP constituencies and SC/women reservations,
  with a **14 February 2013** verification stamp. Retain both tiers.
- **South 24 Parganas 2018:** final [Pradhan Form 1B](https://web.archive.org/web/20180508055743id_/http://s24pgs.gov.in/s24p/pelec2018/642_Form-1B_Pradhan_1.pdf)
  and [Upa-Pradhan Form 1B](https://web.archive.org/web/20180508184043id_/http://s24pgs.gov.in/s24p/pelec2018/643_Form-1B_Upa-Pradhan_1.pdf)
  were downloaded after normalizing the archived URL's explicit `:80` port.
  They have 12 and six pages respectively. The inspected Pradhan order is
  dated **6 March 2018**, with district controls of 310 offices, SC 105,
  ST 4, BC 46 and women 155. Separate draft Form 1A schedules and two
  related gazettes are retained, making six PDFs / 45 pages for this district.
  They are held in [historical_expansion/](gp_source_search/historical_expansion/).
- **Cooch Behar 2018:** all **24 discovered Form A/B PDFs, 207 pages**
  were recovered, with twelve Form A and twelve Form B links. They include
  **draft** reservation orders. The inspected Cooch Behar-I Form A is dated
  **15 November 2017** and explicitly invites objections. Do not label these
  as final merely because the archive directory is named for the 2018 election.
- **Bardhaman 2008:** a [107-page election information book](https://web.archive.org/web/20110722093353id_/http://bardhaman.gov.in/election/paninfo_book08.pdf)
  is held in [bardhaman/](gp_source_search/bardhaman/). It contains block-level
  GP/PS/ZP reservation totals and a district synopsis of **2003** election
  results. It is a pre-election 2008 book, not a 2008 winner list. The separately
  archived version with a `www` hostname returned a truncated response;
  the successfully saved version opens locally.

### Aggregate results are retained too

[summaries/](gp_source_search/summaries/) holds Hooghly's additional 2003
HTML tables, Cooch Behar's 2018 GP/PS/ZP result PDFs, and SEC's live 2018
home/district summary pages from `wbsec.org`. These are useful sources in
addition to the GP-level files. The Cooch Behar GP-labelled PDF has twelve
block rows; its unit remains block rather than GP.

SEC's `VotingResult2018.aspx` page was also saved, but its header says 2018
while the selector offers **29 June 2022 / Siliguri Mahakuma Parishad** and
contains no candidate result rows. It is an unresolved interface lead,
not recovered statewide 2018 candidate data.

### Search coverage and retry leads

The [district archive indexes](gp_source_search/district_indexes/) and query
log preserve searches across more than 20 historical/current district and
state domains, including Bankura, Malda, Purulia, Nadia, Murshidabad, both
24 Parganas districts, Howrah, both Medinipurs, both Dinajpurs, Cooch Behar,
Alipurduar, Jhargram and alternative Bardhaman domains. Queries expanded
across `panch`, `reserv`, `pradhan`, `prodhan`, `delimit`, `pge`, `election`,
`electn` and `result`, followed by exact files found in links and references.
Some domain queries failed. Nadia's broad query hit the 5,000-row cap, so
that index is explicitly not exhaustive.

Connection failures, timeouts and archive capture dates are recorded in the
manifests. HTTPS-to-HTTP retries and removal of explicit `:80` from original
URLs recovered additional files; neither method recovered every target.
The [retry list](gp_source_search/retry_urls.txt) contains discovered file
URLs still missing locally. A failed request is not evidence of absent data.
The source hunt remains open, especially for missing Malda blocks, unrecovered
Nadia schedules, and statewide GP results and reservation rosters.

Local validation checked 326 downloaded CSV-manifest records against file
sizes and SHA-256 hashes, tested ZIP CRC integrity, and accounted for all
518 PDFs / 2,886 pages using Poppler. The
[validation record](gp_source_search/validation.json) and manual-entry index
preserve the checks. The refreshed retry list contains 45 still-missing
recognized document URLs. Additional failed domain probes remain in the logs.

The continued recovery pass saved 110 files, followed by Old Malda through
an alternate archive rendition. Bankura's recovered election landing page
exposed nomination, office-reservation and delimitation links; four targeted
follow-ups were unsuccessful. Its other recovered HTML is a June 2008
Bankura-I administration report, not an election results table. Follow-up
requests and failures are retained in
[followed_links/manifest.csv](gp_source_search/followed_links/manifest.csv)
and [continued_acquisition.jsonl](gp_source_search/continued_acquisition.jsonl).

## Parsing and quality review

[Derived GP data](derived/README.md) now includes complete Hooghly 2003 HTML
extraction, Nadia 2008 Form A1 seat tables, and Alipurduar 2018 seat/candidate
extractions. Tables are supplied as typed Parquet, CSV and JSONL with source
hashes, page or HTML-row references, raw fields and review flags. Printed
controls and a small held-out visual sample are checked; these are not yet
part of the pooled reservation dataset.

Native text and ruled tables have been extracted from every acquired PDF.
An independent page-count check found that pdfplumber returned zero pages
for 13 Birbhum PDFs; Poppler recovered their 151 page records. Nonempty text
is not assumed accurate: the Alipurduar scans contain corrupt embedded OCR
and use a separate image-based extraction. Unresolved layouts, missing
fields and documents without semantic parsers remain explicitly listed in
the [document coverage audit](derived/quality/document_coverage.csv) and
[row review queue](derived/quality/row_review_queue.csv).
