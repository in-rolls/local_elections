# North and central urban election evidence

## Can Chandigarh's verified series extend through 2016?

### Takeaway
Yes: a new official 180-page report supplies unchanged geography, prior/current quotas, final returns, and candidate honorifics for every winner. The research handoff has 26 wards, including 17 current non-quota wards (six previously reserved and 11 previously non-quota). It extends the existing Chandigarh series; it is not a new independent locality.

### Cited Findings
- The September 19, 2016 signed administration letter No.6/1/45/FII(8)-2016/8768 explicitly retains the 2006 delimitation used in 2006 and 2011. It restarts SC reservation on Census 2011 population ranks and provides women’s allocation by lottery. PDF 9–10; narrative PDF 6. The actual October 14 draw and allocation order are PDF 20. [Official report](https://chandigarh.gov.in/files/GEMCC-2021/election-report-2016.pdf).
- The election was December 18, 2016; polling station 14 in ward 7 repolled December 19; declaration December 20. PDF 6. Current women quotas:2,4,5,6,9,12,13,15,17; current SC:5,6,7,11,23. Prior women quotas printed in the same report:1,4,7,9,12,14,21,23,24. Thus the full prior/current quota transition is 0→0:11,0→1:6,1→0:6,1→1:3. [Official report PDF6/20](https://chandigarh.gov.in/files/GEMCC-2021/election-report-2016.pdf).
- All 26 notified winners link to explicit Sh./Smt. in the candidate-name column of nomination lists, PDF 96–123. This is a separately labeled honorific measurement, not a recorded sex field and not an inference from names or quotas. Ward 1 nomination says Maheshinder Singh Sidhu while notification says Mahesh Inder Singh; ward, party and address agree. Multiline names were joined explicitly. [Report](https://chandigarh.gov.in/files/GEMCC-2021/election-report-2016.pdf); [standalone elected notification](https://chandigarh.gov.in/files/documents/NO07.pdf).
- Detailed returns PDF 161–168 contain 122 candidate rows plus 26 NOTA rows; all 26 ward vote totals reconcile. PDF 156 labels 186 as contesting candidates, an inconsistent summary total. Nomination records include rejected/covering/withdrawn persons and cannot be substituted for final contesters. PDF 96 incorrectly retains a 2011 election-date heading although all 26 winner names/parties correspond to 2016. These source errors are retained in the audit. [Report](https://chandigarh.gov.in/files/GEMCC-2021/election-report-2016.pdf); [standalone detailed results](https://chandigarh.gov.in/files/documents/NO09.pdf).

### Inferences
- This supplies a defensible exact-geography extension, but not proof that the conditional prior-quota comparison is an unrestricted randomized experiment. Prior 2011 rotation and changed 2016 SC strata must remain in the design assessment. Shared wards and successive cohorts require dependence-aware pooling.
- Unknown recorded winner sex remains null in every row. `winner_woman_from_honorific` is complete; no name model or quota-based recode was used. No effect estimate or outcome-by-treatment contrast was computed.

### Gaps
- The panel is promoted to the release directory with its own schema, dictionary, audit and manifest. The 2006–2011 files remain unchanged. Full 2006 history is retained; the source review documents the 2016 allocation reset and earlier rotation exclusions.
- Handoff: `data/chandigarh/release/ward_panel_2011_2016.parquet`; adjacent schema, dictionary, detailed-results CSV and `audit.json`. Manual candidate evidence: `data/chandigarh/manual/urban_expansion/winner_honorific_review_2016.csv`. Offline builder: `python -m local_elections.states.chandigarh.extension` from the repository root. Local checks passed: exact 26 keys,122+26 returns, all vote totals,26 candidate-column title matches,26 notification matches, quota transitions, null recorded sex, Parquet roundtrip, Ruff check/format and optimized-Python execution. All three raw PDFs have URL/time/hash receipts.

## Is Rajasthan's smaller-city evidence recoverable?

### Takeaway
Strong retained outcome sources exist for 2009 and 2014 across 46 municipal bodies, including explicit winner sex and quota categories. The decisive missing evidence is the actual 2014 municipal delimitation order/list or matched original ward descriptions. No ward link is certified merely because counts match.

### Cited Findings
- The retained official 2009 report covers 1,612 ward winners and 46 municipal bodies; its existing CSV explicitly separates ward category, winner sex and winner’s personal category. The retained official 2014 report states 1,696 wards across 46 bodies, with polling November 22 and counting November 25; PDF 39–62 have winner name, ward quota, age, M/F, personal category and party. PDF 39 visibly contains 45 Beawar and 20 Pushkar rows. [Held2009 report](../../../../../local_elections_rajasthan/data/raw/municipal/municipal_2009.pdf); [held2014 report, PDF2–4/39](../../../../../local_elections_rajasthan/data/raw/municipal/municipal_2014.pdf). The original download URLs were not recorded; the upstream fetch log honestly records unknown provenance. No duplicates were downloaded.
- Contemporary July 1,2014 reporting identifies a June 30 state program to redraw 14 urban bodies, including Jaipur and Kota, with work throughJuly 30. This is a precise lead to an official order, not verified evidence that all remaining bodies were unchanged. [Times of India](https://timesofindia.indiatimes.com/city/jaipur/govt-to-begin-delimitating-wards-today/articleshow/37536276.cms).
- Citywide chairperson outcomes are a separate promising office:2009 report PDF 35–36 includes office reservation and elected/runner-up names and personal categories;2014 report PDF 63 lists 46 chairpersons and PDF 64–65 their council votes. The 2014 report schedules chairperson election November 26 after ward results; its small vote totals confirm an indirect council election. [Held2009 report](../../../../../local_elections_rajasthan/data/raw/municipal/municipal_2009.pdf); [held2014 report](../../../../../local_elections_rajasthan/data/raw/municipal/municipal_2014.pdf).

### Inferences
- A documented unchanged subset could support substantial new urban ward evidence. Within-state dependence and shared assignment rules mean 46 bodies would not automatically become 46 independent meta-analysis studies.
- Citywide chairpersons avoid dependence on ward-level boundaries but still need municipal-scope continuity and 2014 office quotas. The 2009 direct-election versus 2014 indirect-election change is substantively consequential and must be stated as a separate comparison.

### Gaps
- No official June 2014 delimitation notification was recovered in this pass. Two bounded Wayback index queries and three successful catalog replays recovered the 2016 orders, circulars and annual-report pages. The annual-report page has no document link; the orders/circulars pages list later or unrelated materials. Raw catalogs are in `local_elections_rajasthan/data/raw/urban_expansion/`; archive records are in `data/search_log/urban_expansion/rajasthan_archive_queries.jsonl`. [Archived orders catalog](https://web.archive.org/web/20160306220927id_/http://lsg.urban.rajasthan.gov.in/content/raj/udh/lsg-jaipur/en/cug-zone-/orders-/lsg-order-s.html). Targeted English/Hindi searches found the contemporaneous news lead; no stable subset is yet certified.
- Local `quota_assignment` and `local_elections_delimitation_rajasthan` were searched; the latter's 2014/2019 documents concern rural GPs, not municipal ward boundaries.
-2014 chairperson reservation is absent from the inspected result tables. Winner sex can be linked to explicit 2014 ward winner M/F after extracting all returns; this is not yet done. Source 2014 is scanned and requires reviewed OCR. Do not infer chairperson sex from names or quotas.

## What did Punjab and Haryana add?

### Takeaway
Actual additional sources were acquired, but neither state yet yields a verified new persistence pair. Punjab has partial 2012 candidate coverage; Haryana has full official reports and winner lists but the inspected rows lack individual sex.

### Cited Findings
- ADR's 2012 Punjab catalog lists 75 Ludhiana wards and only 30 Jalandhar wards. The acquired Ludhiana page is paginated; it is not a complete candidate dataset. An inspected candidate profile (Aarti, ward 17) gives age, education and assets but no explicit sex. [Catalog](https://www.myneta.info/punjab_mc_2012/); [Ludhiana candidate page](https://www.myneta.info/punjab_mc_2012/index.php?action=show_constituencies&state_id=1); [profile](https://www.myneta.info/punjab_mc_2012/candidate.php?candidate_id=69).
- Punjab High Court CWP 9222/2012,June 6,2012 identifies April 20,2012 corporation election/reservation notifications and a challenge that some 2007 reserved wards were again reserved in 2012. The court did not impose exact rotation. This does not establish lottery assignment or unchanged geography. [Judgment text, inspected via browser; direct download403](https://indiankanoon.org/doc/67923536/).
- Haryana 2013 report PDF 135–138 contains the June 7 notification naming 144 elected members in seven corporations from June 2 elections:Ambala,Hisar,Karnal,Panchkula,Panipat,Rohtak,Yamuna Nagar. The table's title says Shri/Smt./Km. collectively, but individual name cells do not carry those honorifics; its category field describes the seat, not sex. Aggregate sex tables cannot identify individual outcomes. [Official2013 report](https://cdnbbsr.s3waas.gov.in/s31c6a0198177bfcc9bd93f6aab94aad3c/uploads/2023/05/2023050228.pdf).
- The acquired 246-page Haryana 2016–18 report covers later municipal phases, reservation information and aggregate candidate/elected sex summaries. Its annex 17.1 lists ward reservation; no complete individual sex linkage was validated in this pass. [Official2016–18report](https://cdnbbsr.s3waas.gov.in/s31c6a0198177bfcc9bd93f6aab94aad3c/uploads/2023/05/2023050283.pdf); [SEC publication catalog](https://secharyana.gov.in/publications/).

### Inferences
- Punjab cities share state legislation and political waves; lottery independence across bodies has not been verified. Pooling should not silently treat their estimates as independent replications.
- Haryana municipal and rural reservation rules must remain separate. No rural 2022 male-only rule was applied to urban records; actual eligibility in each urban wave still needs its municipal notification.

### Gaps
- Punjab needs 2007/2012 ward quota rosters, individual recorded sex or candidate honorifics, and geography evidence. The IndiaCode 1995 delimitation order timed out; a government-hosted 2012 circular at `https://files.pspcl.in/bye_election_5739_1454.pdf` timed out after a partial transfer and was not retained as a complete PDF.
- Haryana needs individual nomination forms/lists or sex-coded returns and documented city/ward continuity. Citywide mayor/president histories remain a separate possible design; no qualifying pair is certified.
- MP 2022 report catalog identifies `urban_prativedan2022.pdf` (document 10506,postedOctober 14,2024), but the portal request timed out. [SEC catalog](https://mplocalelection.mp.gov.in/PublicationM-Nirvachanprativedan.aspx). Held 2014–15 report was not duplicated.
- UP's held councilor evidence was checked against central coverage; no new continuity document was acquired. Uttarakhand,HP,J&K andChhattisgarh were not investigated deeply in this bounded pass; absence of a result here is not evidence of no usable data.

## What was actually saved?

### Takeaway
Thirteen complete new raw source files were retrieved, with receipts: three Chandigarh PDFs; two Haryana PDFs plus its catalog; four Punjab HTML files; three archived Rajasthan government catalog pages. Five unsuccessful requests are logged (four access failures and one HTML response masquerading as aPDF). All raw payloads remain in their owning repository.

### Cited Findings
- `data/search_log/urban_expansion/north_central_requests.jsonl` records every acquisition attempt with URL/time/status/hash for successes. Each retained source has a neighboring `.receipt.json`. [Request log](../north_central_requests.jsonl).
- The neighboring `north_central.csv` inventories downloads, inspected held evidence and key unresolved leads. [Inventory](north_central.csv).

### Inferences
- Chandigarh 2016 is ready for substantive review of a new cohort. Rajasthan 2009→2014 is the strongest next independent-locality collection target; geographic proof is the bottleneck, not existence of sex-coded outcomes.

### Gaps
- The acquisition pass computed no effects. Subsequent source validation promoted Chandigarh and Bengaluru handoffs; effect estimation is maintained separately in the manuscript repository.
