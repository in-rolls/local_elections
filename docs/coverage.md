# Data coverage

Generated from registered local tables and pinned state inputs by `make coverage`.
Counts describe the stated units and must not be added across overlapping tables.

## What we have

The table below covers slices parsed in this repository, with one row per
state, year and tier. The pooled files also include parsed sibling repositories
and have one row per seat event. Counts are generated from registered inputs; source limitations are reviewed separately.

Each state directory also has its own generated readme — what is in it, which
documents each row came from, what to be careful of, and how to rebuild it.

Read the notes before the numbers. J&K 2018's 82% women is a property of a
document that lists only the reserved wards, not a fact about J&K; Goa's 2017
and 2022 cycles are nomination lists and name no winner; Jharkhand's place names
are still in the legacy font they were printed in.

<!-- slices:start -->

| State | Year | Tier | Rows | Women | Districts | vs published | Notes | Where |
|---|---|---|---|---|---|---|---|---|
| Andhra Pradesh | 2020 | `gp_head` | 7,368 | 50% | 8 | — | no winner published; partial: 8 of 13 districts; ward list complete for 96% of rows with a stated count | [data/andhra_pradesh/](../data/andhra_pradesh/) |
| Andhra Pradesh | 2020 | `gp_ward` | 72,653 | 49% | 8 | — | no winner published; partial: 8 of 13 districts; ward list complete for 96% of rows with a stated count | [data/andhra_pradesh/](../data/andhra_pradesh/) |
| Assam | 2020 | `ulb_head` | 46 | 89% | 20 | — | no winner published; **reserved seats only** — shares are a property of the document, not of the state | [data/assam/](../data/assam/) |
| Assam | 2020 | `ulb_ward` | 564 | 88% | 23 | — | no winner published; **reserved seats only** — shares are a property of the document, not of the state | [data/assam/](../data/assam/) |
| Assam | 2025 | `block_head` | 13 | 62% | 4 | — | no winner published | [data/assam/](../data/assam/) |
| Assam | 2025 | `block_member` | 127 | 63% | 4 | — | no winner published | [data/assam/](../data/assam/) |
| Assam | 2025 | `block_vice_head` | 13 | 62% | 4 | — | no winner published | [data/assam/](../data/assam/) |
| Assam | 2025 | `gp_head` | 124 | 61% | 4 | — | no winner published | [data/assam/](../data/assam/) |
| Assam | 2025 | `gp_vice_head` | 125 | 61% | 4 | — | no winner published | [data/assam/](../data/assam/) |
| Assam | 2025 | `gp_ward` | 1,254 | 61% | 4 | — | no winner published | [data/assam/](../data/assam/) |
| Assam | 2025 | `zp_member` | 22 | 59% | 4 | — | no winner published | [data/assam/](../data/assam/) |
| Goa | 2012 | `gp_ward` | 1,471 | 32% | 2 | 99% of 186 panchayats | — | [data/goa/](../data/goa/) |
| Goa | 2017 | `gp_ward` | 684 | 27% | 2 | — | no winner published | [data/goa/](../data/goa/) |
| Goa | 2022 | `gp_ward` | 793 | 39% | 2 | — | no winner published | [data/goa/](../data/goa/) |
| Gujarat | 2020 | `block_member` | 646 | 50% | 16 | 100% of 646 seats | no winner published | [data/gujarat/](../data/gujarat/) |
| Gujarat | 2020 | `zp_member` | 532 | 50% | 16 | 100% of 532 seats | no winner published | [data/gujarat/](../data/gujarat/) |
| Jammu & Kashmir | 2010 | `gp_ward` | 13,016 | 34% | 10 | — | no winner published | [data/jammu_and_kashmir/](../data/jammu_and_kashmir/) |
| Jammu & Kashmir | 2016 | `gp_head` | 1,763 | 35% | 10 | — | no winner published | [data/jammu_and_kashmir/](../data/jammu_and_kashmir/) |
| Jammu & Kashmir | 2016 | `gp_ward` | 12,300 | 34% | 10 | — | no winner published | [data/jammu_and_kashmir/](../data/jammu_and_kashmir/) |
| Jammu & Kashmir | 2018 | `gp_ward` | 1,419 | 82% | 12 | — | no winner published; **reserved seats only** — shares are a property of the document, not of the state | [data/jammu_and_kashmir/](../data/jammu_and_kashmir/) |
| Karnataka | 1993 | `gp_head` | 5,264 | 32% | 27 | — | no winner published | [data/karnataka/](../data/karnataka/) |
| Karnataka | 2000 | `gp_head` | 5,320 | 36% | 27 | — | no winner published | [data/karnataka/](../data/karnataka/) |
| Karnataka | 2002 | `gp_head` | 5,320 | 36% | 27 | — | no winner published | [data/karnataka/](../data/karnataka/) |
| Karnataka | 2005 | `gp_head` | 5,322 | 32% | 27 | — | no winner published | [data/karnataka/](../data/karnataka/) |
| Karnataka | 2007 | `gp_head` | 5,322 | 33% | 27 | — | no winner published | [data/karnataka/](../data/karnataka/) |
| Karnataka | 2016 | `block_member` | 3,478 | 51% | 30 | — | — | [data/karnataka/](../data/karnataka/) |
| Karnataka | 2016 | `zp_member` | 888 | 48% | 26 | — | — | [data/karnataka/](../data/karnataka/) |
| Maharashtra | 2012 | `ulb_ward` | 227 | 51% | 1 | — | — | [data/maharashtra/](../data/maharashtra/) |
| Maharashtra | 2017 | `ulb_ward` | 227 | 50% | 1 | — | — | [data/maharashtra/](../data/maharashtra/) |
| West Bengal | 2018 | `zp_member` | 825 | 49% | 20 | — | no winner published | [data/west_bengal/](../data/west_bengal/) |

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
| Andhra Pradesh | gp_head, gp_ward | 2020 | 80,021 | parsed | all 13 GP district gazettes are held; 8 are parsed and 5 remain unparsed; 32 held PDFs cover MPTC, ZPTC, MPP, and MPL tiers and remain unparsed | [data/andhra_pradesh/](../data/andhra_pradesh/) |
| Arunachal Pradesh | - | - | - | not held | acquire and assess a seat-level rural source | - |
| Assam | block_head, block_member, block_vice_head, gp_head, gp_vice_head, gp_ward, ulb_head, ulb_ward, zp_member | 2020, 2025 | 2,288 | parsed | 23 held 2025 district PRI scans remain unparsed | [data/assam/](../data/assam/) |
| Bihar | gp_head, gp_ward, block_member, zp_member, kachahari_head, kachahari_member | 2016, 2021 | 2,778,202 | parsed | 30,764 seats of 2016 answer 'Record not Found' and print no reservation; 2021 winner education is transcribed for Arwal only | [local_elections_bihar](https://github.com/in-rolls/local_elections_bihar) |
| Chandigarh | - | - | - | no parsed rows | 5 held municipal and election-report PDFs need a rural-scope review | [data/chandigarh/](../data/chandigarh/) - 4 digital-text, 1 scan |
| Chhattisgarh | - | - | - | not held | acquire and assess a seat-level rural source | - |
| Dadra & Nagar Haveli and Daman & Diu | - | - | - | not held | acquire and assess a seat-level rural source | - |
| Goa | gp_ward | 2012, 2017, 2022 | 2,948 | parsed | the 2017 and 2022 rosters are incomplete; 10 held cycle files are not linked to parsed rows | [data/goa/](../data/goa/) |
| Gujarat | block_member, zp_member | 2020 | 1,178 | parsed | — | [data/gujarat/](../data/gujarat/) |
| Haryana | gp_head, gp_ward | 2000, 2005, 2010, 2016, 2022 | 325,109 | parsed | 2000 covers 5,932 of the commission's 6,035 GPs (113 of 114 blocks), transcribed from gazette scans; winner sex is name-inferred, as no record prints it; 2016 and 2022 cannot be compared after the 2020 change to the BC-A and women's quotas | [local_elections_haryana](https://github.com/in-rolls/local_elections_haryana) |
| Himachal Pradesh | - | - | - | no parsed rows | 1 held scan needs a seat-level scope review and OCR | [data/himachal_pradesh/](../data/himachal_pradesh/) - 1 scan |
| Jammu & Kashmir | gp_head, gp_ward | 2010, 2016, 2018 | 28,498 | parsed | 2016 is parsed from all 25 held PDFs; 13 files from 2010 and 2018 produce no rows | [data/jammu_and_kashmir/](../data/jammu_and_kashmir/) |
| Jharkhand | gp_head, gp_ward, block_member, zp_member | 2015, 2022 | 37,615 | parsed | 2015 ward and zila parishad seats from 11 of 24 districts; 2022 mukhiya seats only; winner sex is name-inferred | [local_elections_jharkhand](https://github.com/in-rolls/local_elections_jharkhand) |
| Karnataka | block_member, gp_head, zp_member | 1993, 2000, 2002, 2005, 2007, 2016 | 30,914 | parsed | 244 of 248 unlinked PDFs were reviewed as duplicate reservation statements or aggregate forms, not missing seats; 4 produce no rows | [data/karnataka/](../data/karnataka/) |
| Kerala | gp_ward, block_member, zp_member, ulb_ward | 2010, 2015, 2020 | 65,296 | parsed | see sibling repository | [local_elections_kerala](https://github.com/in-rolls/local_elections_kerala) |
| Ladakh | - | - | - | not held | acquire and assess a seat-level rural source | - |
| Lakshadweep | - | - | - | not held | acquire and assess a seat-level rural source | - |
| Madhya Pradesh | - | - | - | no parsed rows | 2 held scans need a seat-level scope review and OCR | [data/madhya_pradesh/](../data/madhya_pradesh/) - 2 scan |
| Maharashtra | ulb_ward | 2012, 2017 | 454 | parsed | Mumbai only: the 1997, 2002 and 2007 BMC councils lack a seat-reservation roster (2007 has the women's flag as a supplemental file); the ~28,000 rural gram panchayats are absent entirely | [data/maharashtra/](../data/maharashtra/) |
| Manipur | - | - | - | not held | acquire and assess a seat-level rural source | - |
| Meghalaya | - | - | - | not applicable | none | Sixth Schedule - autonomous district councils, no PRI |
| Mizoram | - | - | - | not applicable | none | Sixth Schedule - village councils, no PRI |
| Nagaland | - | - | - | not applicable | none | Article 371A - village councils, no PRI |
| NCT of Delhi | `ulb_ward` | 2007, 2012, 2017 | - | urban only | rural data are not held here | [data/delhi/](../data/delhi/) |
| Odisha | gp_head | 2017, 2022 | 13,434 | parsed | winners only, with no reservation per GP; no adapter, so nothing is pooled | [local_elections_odisha](https://github.com/in-rolls/local_elections_odisha) |
| Puducherry | - | - | - | no parsed rows | the 2021 panchayat notification is a 60-page scan that needs OCR; the other held notification is municipal | [data/puducherry/](../data/puducherry/) - 1 digital-text, 1 scan |
| Punjab | - | - | - | not held | acquire and assess a seat-level rural source | - |
| Rajasthan | gp_head, gp_ward, block_member, zp_member | 2005, 2010, 2015, 2020, 2021, 2022 | 255,474 | parsed | 162,502 rural seat events, 68,202 candidates, and 13,473 GP-event nomination summaries are standardized; the 2015 Panchayat Samiti book and the 2015 and 2020 Zila Parishad books remain unparsed; municipal material is held outside the rural master | [local_elections_rajasthan](https://github.com/in-rolls/local_elections_rajasthan) |
| Sikkim | - | - | - | not held | acquire and assess a seat-level rural source | - |
| Tamil Nadu | gp_head, gp_ward, block_member, zp_member | 2011, 2019, 2021 | 250,961 | parsed | the heads of the union and district panchayats are not collected; 2011 village ward sheets print winners only; the 2011 president reservation roster and the 2001 amendments are separate exports there, not pooled | [local_elections_tamil_nadu](https://github.com/in-rolls/local_elections_tamil_nadu) |
| Telangana | gp_head, gp_ward | 2019, 2025 | 149,030 | parsed | 24,753 sarpanch seats (2019 and 2025), 49,823 2019 and 62,990 2025 ward seats, and 11,464 seat links are standardized; the commission publishes about 56% of 2025 wards and no 2025 women's ward reservation; 2020-21 municipal results are held in the sibling but not parsed | [local_elections_telangana](https://github.com/in-rolls/local_elections_telangana) |
| Tripura | - | - | - | not held | acquire and assess a seat-level rural source | - |
| Uttar Pradesh | gp_head | 2005, 2010, 2015, 2021 | 535,848 | parsed | see sibling repository | [local_elections_up](https://github.com/in-rolls/local_elections_up) |
| Uttarakhand | gp_head, block_member, zp_member | 2008, 2014, 2019 | 116,514 | parsed | see sibling repository | [local_elections_uttarakhand](https://github.com/in-rolls/local_elections_uttarakhand) |
| West Bengal | zp_member | 2018 | 825 | parsed | Separate 1998–2023 GP office, ward and results data have source-linked parsers and review queues ([GP data](../data/west_bengal/release/README.md)); the final 2018 ZP gazettes are parsed, while their 19 drafts are not additional final seats | [data/west_bengal/](../data/west_bengal/) |

<!-- coverage:end -->


### Other Sources

* https://github.com/tcpd/Urban_Local_Body
