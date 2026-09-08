**Bottom line:** the full Beaman et al. replication package is reachable through the Dataverse API and its file list is fully inventoried, but every GP and block identifier in it is anonymized. It cannot yield named-GP reservation status for 2003, 1998, or 2008. No public named 2003 Pradhan reservation roster was found in this pass. WBSEC and its archive were both unreachable.

## What was inspected

**Dataverse O3UKFO via the JSON API** (the HTML inventory gives 403, the API does not):
`https://dataverse.harvard.edu/api/datasets/:persistentId/?persistentId=doi:10.7910/DVN/O3UKFO`

Version 4, released 2012-01-06, CC0, no file restricted, no access request required. Key files and IDs:

| File | File ID | Content per DDI metadata |
|---|---|---|
| reservation.tab | 13986341 | 165 Birbhum GPs. Pradhan-office reservation current (2003 term) and previous (1998 term): woman, SC, ST. |
| election_pradhan_alldist.tab | 13986379 | 1,316 GPs, six districts. Columns res1998, res2003, res2008, gender2003, gender2008, res_history. |
| nadia.tab / howrah.tab / hooghly.tab / burdwan.tab / s24para.tab | 13986285 / 13986350 / 13986337 / 13986358 / 13986347 | Per-district GP rows with res1998, res2003, res2008 (character), gender2003, gender2008, incumb2008. |
| election_pradhan_2008.tab | 13986308 | 168 Birbhum GPs, 2008 Pradhan reservation plus 1998/2003 history. |
| elections_ward2003.tab | 13986293 | 5,821 ward-seat records, Birbhum 2003: seat number, reservationstatus, party, votes, winner. |
| Readme.pdf, codebook_pradhan.pdf, Clean_Election_data_gp.do, CleanPradhanAll.do | 13986331 / 13986362 / 13986343 / 13986336 | Documentation and cleaning code. |

**Anonymization is total.** In the district files the identifier columns are blockname_code_anon, gpname_code_anon, name2003_code_anon, name2008_code_anon. The one unsuffixed column, name1998, is all-missing in every district file. Birbhum files use gp_code_anon and block_code_anon. The Birbhum ward file uses the same anonymized keys. So the reservation values exist, but cannot be joined to real GP names from this package alone.

**Direct file downloads** return HTTP 400 for every content-type tried (tab, do, pdf, with and without format=original). Only the per-file DDI metadata endpoint works:
`https://dataverse.harvard.edu/api/access/datafile/<id>/metadata/ddi`

This matches the 403 you saw on the inventory pages. The package may still download normally in a browser or with curl outside this tool.

## Unreachable or negative

- **archive.wbsec.org** and **wbsec.gov.in** refuse connections or present an expired certificate. The archive site has a Detailed_gp.aspx result page that, from memory, covers 2008 and 2013 with per-seat reservation status, not 2003.
- **Wayback Machine** cannot be fetched by this tool. Closest wbsec.org snapshot per the availability API is 2018-04-11.
- **openICPSR E112367V1** project page returns 403. Its file list was not inspected.
- **wbxpress.com panchayat page** hosts the 2003 Act, 2006 Rules, 1975 Constitution Rules and Forms 1 to 24, but no reservation rosters or district orders.
- **Bengali searches** for 2003 Pradhan-office reservation lists returned only 2023 material.
- **Calcutta High Court** searches returned 2023 cases only. Older judgments naming GPs with a 2003 reserved Pradhan office likely exist but need date-restricted Indian Kanoon queries.

## Next retrieval steps, in priority order

1. **Download the package outside this tool** with curl or a browser, using the file IDs above. Even anonymized, reservation.tab plus Readme.pdf and CleanPradhanAll.do will reveal the exact category coding and the cited source of the 2003 and 1998 rosters, which points at the original district orders.
2. **Wayback Machine, done from a browser:** nadia.nic.in, birbhum.gov.in, howrah.nic.in, hooghly.nic.in, bardhaman.nic.in and s24pgs.gov.in captures from 2004 to 2008. District portals of that era commonly carried "List of Pradhans" pages with category columns for the 2003 term. Also web.archive.org captures of wbsec.org from 2008 to 2012 for the Detailed_gp.aspx result pages.
3. **Indian Kanoon date-limited search** for Calcutta High Court 2003 to 2005 with terms like "office of Pradhan" "reserved" "Scheduled Caste woman" and each district name. Such orders quote the DM's reservation notification and name the GP.
4. **openICPSR E112367V1** from a browser to confirm whether the 57-GP Bardhan-Mookherjee file carries GP names and 1993/1998/2003 Pradhan reservation.
5. **Chattopadhyay-Duflo 1998 Birbhum file** you already hold can be used to de-anonymize Birbhum rows of reservation.tab by matching prev_res_woman, prev_res_sc, prev_res_st and block sizes against the 161 known GPs, which recovers 2003 status for most Birbhum GPs without any new source.

Sources: [Dataverse O3UKFO API](https://dataverse.harvard.edu/api/datasets/:persistentId/?persistentId=doi:10.7910/DVN/O3UKFO), [J-PAL Dataverse PXV79W](https://dataverse.harvard.edu/dataset.xhtml?persistentId=doi:10.7910/DVN/PXV79W), [NBER w14198](https://www.nber.org/papers/w14198), [WBSEC archive result page](https://archive.wbsec.org/(S(yk2ftt0ncqt2cqb2pfnxnjw1))/DetailedResult/Detailed_gp.aspx), [WBSEC orders](https://www.wbsec.gov.in/home/order/M3R4WXJhdVNYa05pMDBEbDhMRWh1OHVyYXg1UHpBZEM3UXZqbEdYR2dyWHlDNGgxcGlnODAzc2Z1QzlTc3MrNEdtRnZ1OG9JN0Q2NVk5WDdSa3ExUVVkaEQ4dHU1RDd6cjJsU1h3PT0=/7), [WB Panchayat Elections Act 2003](https://indiankanoon.org/doc/37972282/), [wbxpress panchayat documents](https://wbxpress.com/panchayat-election-acts-rules-guidelines/), [Bardhan-Mookherjee-Torrado paper](https://people.bu.edu/dilipm/publications/wbtreserv.pdf), [openICPSR 112367](https://www.openicpsr.org/openicpsr/project/112367/version/V1/view), [Supriya Shit v. State of WB 2023](https://indiankanoon.org/doc/198628785/), [Nadia district GP list](https://nadia.gov.in/village-panchayats/), [2008 GP directory on Scribd](https://www.scribd.com/document/691063909/Directoryof-District-Block-GPs-RevisedMarch-2008)
