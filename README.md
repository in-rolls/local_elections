# Local electoral body reservations

A versioned, checksummed data package of reservation and election-result data
for India's local bodies. Coverage varies by state, year and tier; the tables
below state those limits rather than implying nationwide completeness.

For comparable rural data with one row per seat event, start with the generated
**[pooled master guide](data/master/readme.md)**. State directories also retain
source-specific fields and urban rows that do not enter the rural master.

See **[SOURCES.md](SOURCES.md)** for a state-by-state feasibility survey: where
each state publishes its reservation data, whether the files are text or scans,
and what it would take to extend coverage.

The tables below are **generated**. `make coverage` rebuilds them from the
parsed files, `data/inventory.csv`, and the sibling repositories, then checks
every link. They drifted twice while hand-maintained, so they are no longer
hand-maintained.

## What is still missing

The state coverage table and the worklist answer different questions. The
coverage table says what has been parsed and distinguishes missing acquisition
from held source work. Its `Remaining work` column also says when unlinked PDFs
are drafts, duplicate statements, aggregates, manuals, or urban material rather
than missing rural seats.

The worklist describes defects and limits detected in the parsed rows. Open
gaps can be worked now. Blocked gaps need source access. Parked gaps are known
and deliberately deferred. Undetermined entries need source research before
they can be called gaps. Accepted source properties need no work, but remain
visible because they limit what the data can answer.

`Rows affected` is a diagnostic count, not an estimate of uncollected seats.
The same row can trigger more than one note, so those figures must not be added
into a national missing-seat total.

<!-- worklist:start -->

| | Entries | Rows affected |
|---|---|---|
| [Open gaps](WORKLIST.md) | 60 | 82,340 |
| [Blocked](WORKLIST.md) | 0 | 0 |
| [Parked](WORKLIST.md) | 9 | 1,653 |
| [Undetermined](WORKLIST.md) | 17 | 72,402 |
| [Accepted properties of the sources](WORKLIST.md) | 24 | 141,056 |

<!-- worklist:end -->

**[CHANGELOG.md](CHANGELOG.md)** says what moved between releases and why,
corrections first — if a number you used has changed, that is where it is
recorded, along with which analyses to redo.

**[MANIFEST.json](MANIFEST.json)** records SHA-256 hashes for the registered
parsed and pooled tables, the exact master column order, and the commit each
sibling repository was read at. Supplemental exports and raw source evidence
also have source-specific inventories and manifests; consult the state source
guides for their locations. Verify a checkout with `python3
src/local_reservations/tools/verify_manifest.py`, which is standard library
only and imports nothing else here, so it works from a bare checkout or an
unpacked tarball.

**[SOURCE_MANIFEST.json](SOURCE_MANIFEST.json)** separately inventories WB,
Tamil Nadu and the early-source search evidence, including original documents,
OCR readings and review images. Its archive map preserves files too large for
ordinary Git storage. After downloading source-evidence assets, verify every
archive member with `python3 src/local_reservations/tools/verify_manifest.py
--manifest SOURCE_MANIFEST.json --archives /path/to/assets`. See the
[Tamil Nadu extract](data/tn/readme.md) and [source ledger](data/source_search/early_heads/README.md)
for parsed coverage and unresolved readings. Release changes are recorded in the [changelog](CHANGELOG.md).

## What we have

The table below covers slices parsed in this repository, with one row per
state, year and tier. The pooled files also include parsed sibling repositories
and have one row per seat event. The notes are derived from the rows themselves
rather than written by hand, so they cannot drift from what is in the files.

Each state directory also has its own generated readme — what is in it, which
documents each row came from, what to be careful of, and how to rebuild it.

Read the notes before the numbers. J&K 2018's 82% women is a property of a
document that lists only the reserved wards, not a fact about J&K; Goa's 2017
and 2022 cycles are nomination lists and name no winner; Jharkhand's place names
are still in the legacy font they were printed in.

<!-- slices:start -->

| State | Year | Tier | Rows | Women | Districts | vs published | Notes | Where |
|---|---|---|---|---|---|---|---|---|
| Andhra Pradesh | 2020 | `gp_head` | 7,368 | 50% | 8 | — | no winner published; partial: 8 of 13 districts; ward list complete for 96% of rows with a stated count | [data/ap/](data/ap/) |
| Andhra Pradesh | 2020 | `gp_ward` | 72,653 | 49% | 8 | — | no winner published; partial: 8 of 13 districts; ward list complete for 96% of rows with a stated count | [data/ap/](data/ap/) |
| Assam | 2020 | `ulb_head` | 46 | 89% | 20 | — | no winner published; **reserved seats only** — shares are a property of the document, not of the state | [data/assam/](data/assam/) |
| Assam | 2020 | `ulb_ward` | 564 | 88% | 23 | — | no winner published; **reserved seats only** — shares are a property of the document, not of the state | [data/assam/](data/assam/) |
| Assam | 2025 | `block_head` | 13 | 62% | 4 | — | no winner published | [data/assam/](data/assam/) |
| Assam | 2025 | `block_member` | 127 | 63% | 4 | — | no winner published | [data/assam/](data/assam/) |
| Assam | 2025 | `block_vice_head` | 13 | 62% | 4 | — | no winner published | [data/assam/](data/assam/) |
| Assam | 2025 | `gp_head` | 124 | 61% | 4 | — | no winner published | [data/assam/](data/assam/) |
| Assam | 2025 | `gp_vice_head` | 125 | 61% | 4 | — | no winner published | [data/assam/](data/assam/) |
| Assam | 2025 | `gp_ward` | 1,254 | 61% | 4 | — | no winner published | [data/assam/](data/assam/) |
| Assam | 2025 | `zp_member` | 22 | 59% | 4 | — | no winner published | [data/assam/](data/assam/) |
| Goa | 2012 | `gp_ward` | 1,471 | 32% | 2 | 99% of 186 panchayats | — | [data/goa/](data/goa/) |
| Goa | 2017 | `gp_ward` | 684 | 27% | 2 | — | no winner published | [data/goa/](data/goa/) |
| Goa | 2022 | `gp_ward` | 793 | 39% | 2 | — | no winner published | [data/goa/](data/goa/) |
| Gujarat | 2020 | `block_member` | 646 | 50% | 16 | 100% of 646 seats | no winner published | [data/gujarat/](data/gujarat/) |
| Gujarat | 2020 | `zp_member` | 532 | 50% | 16 | 100% of 532 seats | no winner published | [data/gujarat/](data/gujarat/) |
| Jammu & Kashmir | 2010 | `gp_ward` | 13,016 | 34% | 10 | — | no winner published | [data/jk/](data/jk/) |
| Jammu & Kashmir | 2016 | `gp_head` | 1,763 | 35% | 10 | — | no winner published | [data/jk/](data/jk/) |
| Jammu & Kashmir | 2016 | `gp_ward` | 12,300 | 34% | 10 | — | no winner published | [data/jk/](data/jk/) |
| Jammu & Kashmir | 2018 | `gp_ward` | 1,432 | 82% | 12 | — | no winner published; **reserved seats only** — shares are a property of the document, not of the state | [data/jk/](data/jk/) |
| Jharkhand | 2015 | `block_member` | 5,132 | 52% | 24 | 95% of 5,423 seats | — | [data/jharkhand/](data/jharkhand/) |
| Jharkhand | 2015 | `gp_head` | 3,972 | 52% | 24 | 91% of 4,345 gram panchayats | — | [data/jharkhand/](data/jharkhand/) |
| Jharkhand | 2015 | `gp_ward` | 19,781 | 53% | 11 | — | partial: 11 of 24 districts | [data/jharkhand/](data/jharkhand/) |
| Jharkhand | 2015 | `zp_member` | 226 | 53% | 11 | 41% of 545 seats | partial: 11 of 24 districts | [data/jharkhand/](data/jharkhand/) |
| Karnataka | 1993 | `gp_head` | 5,264 | 32% | 27 | — | no winner published | [data/karnataka/](data/karnataka/) |
| Karnataka | 2000 | `gp_head` | 5,320 | 36% | 27 | — | no winner published | [data/karnataka/](data/karnataka/) |
| Karnataka | 2002 | `gp_head` | 5,320 | 36% | 27 | — | no winner published | [data/karnataka/](data/karnataka/) |
| Karnataka | 2005 | `gp_head` | 5,322 | 32% | 27 | — | no winner published | [data/karnataka/](data/karnataka/) |
| Karnataka | 2007 | `gp_head` | 5,322 | 33% | 27 | — | no winner published | [data/karnataka/](data/karnataka/) |
| Karnataka | 2016 | `block_member` | 3,478 | 51% | 30 | — | — | [data/karnataka/](data/karnataka/) |
| Karnataka | 2016 | `zp_member` | 888 | 48% | 26 | — | — | [data/karnataka/](data/karnataka/) |
| Maharashtra | 2012 | `ulb_ward` | 227 | 51% | 1 | — | — | [data/maharashtra/](data/maharashtra/) |
| Maharashtra | 2017 | `ulb_ward` | 227 | 50% | 1 | — | — | [data/maharashtra/](data/maharashtra/) |
| Telangana | 2019 | `gp_head` | 12,018 | 50% | 30 | 94% of 12,728 seats | — | [data/telangana/](data/telangana/) |
| Telangana | 2019 | `gp_ward` | 49,823 | 51% | 30 | 44% of 112,242 seats | — | [data/telangana/](data/telangana/) |
| West Bengal | 2018 | `zp_member` | 825 | 49% | 20 | — | no winner published | [data/wb/](data/wb/) |

<!-- slices:end -->

## Coverage by state

This table inventories every state, including completed sibling repositories.
`Rows` counts records in parsed source files; candidate-level sources may
contain several records per seat, and local files may include urban bodies that
the rural master excludes. Use the pooled master above for comparable
seat-event counts.

`Coverage` says whether rows are parsed, no rows are parsed, sources are not
held, or rural PRI data are not applicable. `Remaining work` records the next
source action or explains why held PDFs do not represent additional missing
seats. The state readme linked in `Where` gives the file-level inventory.


<!-- coverage:start -->

| State | Tier | Years | Rows | Coverage | Remaining work | Where |
|---|---|---|---|---|---|---|
| Andaman & Nicobar Islands | - | - | - | not held | acquire and assess a seat-level rural source | - |
| Andhra Pradesh | gp_head, gp_ward | 2020 | 80,021 | parsed | all 13 GP district gazettes are held; 8 are parsed and 5 remain unparsed; 32 held PDFs cover MPTC, ZPTC, MPP, and MPL tiers and remain unparsed | [data/ap/](data/ap/) |
| Arunachal Pradesh | - | - | - | not held | acquire and assess a seat-level rural source | - |
| Assam | block_head, block_member, block_vice_head, gp_head, gp_vice_head, gp_ward, ulb_head, ulb_ward, zp_member | 2020, 2025 | 2,288 | parsed | 23 held 2025 district PRI scans remain unparsed | [data/assam/](data/assam/) |
| Bihar | gp_head, gp_ward, block_member, zp_member, kachahari_head, kachahari_member | 2016, 2021 | 712,035 | parsed | 2021 mukhiya education and dated reservation linkage incomplete | [local_elections_bihar](https://github.com/in-rolls/local_elections_bihar) |
| Chandigarh | - | - | - | no parsed rows | 5 held municipal and election-report PDFs need a rural-scope review | [data/chandigarh/](data/chandigarh/) - 4 digital-text, 1 scan |
| Chhattisgarh | - | - | - | not held | acquire and assess a seat-level rural source | - |
| Dadra & Nagar Haveli and Daman & Diu | - | - | - | not held | acquire and assess a seat-level rural source | - |
| Goa | gp_ward | 2012, 2017, 2022 | 2,948 | parsed | the 2017 and 2022 rosters are incomplete; 10 held cycle files are not linked to parsed rows | [data/goa/](data/goa/) |
| Gujarat | block_member, zp_member | 2020 | 1,178 | parsed | — | [data/gujarat/](data/gujarat/) |
| Haryana | gp_head, gp_ward | 2016, 2022 | 135,073 | parsed | see sibling repository | [local_elections_haryana](https://github.com/in-rolls/local_elections_haryana) |
| Himachal Pradesh | - | - | - | no parsed rows | 1 held scan needs a seat-level scope review and OCR | [data/himachal/](data/himachal/) - 1 scan |
| Jammu & Kashmir | gp_head, gp_ward | 2010, 2016, 2018 | 28,511 | parsed | 2016 is parsed from all 25 held PDFs; 13 files from 2010 and 2018 produce no rows | [data/jk/](data/jk/) |
| Jharkhand | block_member, gp_head, gp_ward, zp_member | 2015 | 29,111 | parsed | GP-ward and ZP coverage reaches 11 of 24 districts; 29 rural and 3 municipal PDFs are not linked to parsed rows | [data/jharkhand/](data/jharkhand/) |
| Karnataka | block_member, gp_head, zp_member | 1993, 2000, 2002, 2005, 2007, 2016 | 30,914 | parsed | 244 of 248 unlinked PDFs were reviewed as duplicate reservation statements or aggregate forms, not missing seats; 4 produce no rows | [data/karnataka/](data/karnataka/) |
| Kerala | gp_ward, block_member, zp_member, ulb_ward | 2010, 2015, 2020 | 65,296 | parsed | see sibling repository | [local_elections_kerala](https://github.com/in-rolls/local_elections_kerala) |
| Ladakh | - | - | - | not held | acquire and assess a seat-level rural source | - |
| Lakshadweep | - | - | - | not held | acquire and assess a seat-level rural source | - |
| Madhya Pradesh | - | - | - | no parsed rows | 2 held scans need a seat-level scope review and OCR | [data/madhya_pradesh/](data/madhya_pradesh/) - 2 scan |
| Maharashtra | ulb_ward | 2012, 2017 | 454 | parsed | Mumbai only: the 1997, 2002 and 2007 BMC councils lack a seat-reservation roster (2007 has the women's flag as a supplemental file); the ~28,000 rural gram panchayats are absent entirely | [data/maharashtra/](data/maharashtra/) |
| Manipur | - | - | - | not held | acquire and assess a seat-level rural source | - |
| Meghalaya | - | - | - | not applicable | none | Sixth Schedule - autonomous district councils, no PRI |
| Mizoram | - | - | - | not applicable | none | Sixth Schedule - village councils, no PRI |
| Nagaland | - | - | - | not applicable | none | Article 371A - village councils, no PRI |
| NCT of Delhi | `ulb_ward` | 2007, 2012, 2017 | - | urban only | rural data are not held here | [data/delhi/](data/delhi/) |
| Odisha | - | - | - | no parsed rows | the 6 held PDFs are district aggregates, not seat rosters; acquire seat-level rural data | [data/odisha/](data/odisha/) - 6 digital-text |
| Puducherry | - | - | - | no parsed rows | the 2021 panchayat notification is a 60-page scan that needs OCR; the other held notification is municipal | [data/puducherry/](data/puducherry/) - 1 digital-text, 1 scan |
| Punjab | - | - | - | not held | acquire and assess a seat-level rural source | - |
| Rajasthan | gp_head, gp_ward, block_member, zp_member | 2005, 2010, 2015, 2020, 2021, 2022 | 255,474 | parsed | 162,502 rural seat events, 68,202 candidates, and 13,473 GP-event nomination summaries are standardized; the 2015 Panchayat Samiti book and the 2015 and 2020 Zila Parishad books remain unparsed; municipal material is held outside the rural master | [local_elections_rajasthan](https://github.com/in-rolls/local_elections_rajasthan) |
| Sikkim | - | - | - | not held | acquire and assess a seat-level rural source | - |
| Tamil Nadu | GP-president office / amendment operation | 2001, 2011 | - | source-specific exports | 2011 GP-president roster and 2001 amendment operations have separate source-specific exports; review earlier scans and subsequent amendments; observed GP-president sex remains unavailable | [data/tn/](data/tn/); separate from pooled schema |
| Telangana | gp_head, gp_ward | 2019 | 61,841 | parsed | the 4 unlinked PDFs are urban reservation orders or election manuals, not missing rural seats | [data/telangana/](data/telangana/) |
| Tripura | - | - | - | not held | acquire and assess a seat-level rural source | - |
| Uttar Pradesh | gp_head | 2005, 2010, 2015, 2021 | 535,848 | parsed | see sibling repository | [local_elections_up](https://github.com/in-rolls/local_elections_up) |
| Uttarakhand | gp_head, block_member, zp_member | 2008, 2014, 2019 | 116,514 | parsed | see sibling repository | [local_elections_uttarakhand](https://github.com/in-rolls/local_elections_uttarakhand) |
| West Bengal | zp_member | 2018 | 825 | parsed | Separate 1998–2023 GP office, ward and results data have source-linked parsers and review queues ([GP data](data/wb/derived/README.md)); the final 2018 ZP gazettes are parsed, while their 19 drafts are not additional final seats | [data/wb/](data/wb/) |

<!-- coverage:end -->

### Installed-wheel data location

The wheel contains code, not the corpus. Point `LOCAL_RESERVATIONS_ROOT` at a
separate checkout when running data utilities from a standalone installation:

```sh
LOCAL_RESERVATIONS_ROOT=/path/to/local_reservations verify-manifest
```

The selected directory must contain this project's `pyproject.toml` and `data/`.
An invalid setting raises an error rather than silently selecting another
repository. Editable installations still discover their own checkout without
this setting.


### Other Sources

* https://github.com/tcpd/Urban_Local_Body
