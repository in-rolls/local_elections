# Public Web Research Report: Historical West Bengal Gram Panchayat Election Data (2003, 1998, 1993 & Earlier)

## 1. Search Infrastructure & Service Performance Notice

During the execution of this web research assignment:
* **Search Engine Outages (HTTP 503):** Two web search calls failed with `503 Service Unavailable` (`MODEL_CAPACITY_EXHAUSTED` on the `gemini-3.1-flash-lite` backend grounding service) when querying Birbhum and multi-district combinations. Subsequent retries after backoff intervals succeeded.
* **Direct Content Fetch Interruption:** A direct URL content read on the OpenICPSR repository (`project/114948/version/V1/view`) was canceled upon transitioning to this reporting phase.
* **No Unverified Claims or Hallucinations:** Per your instruction, no files were modified, no shell commands were executed, and no uninspected data has been fabricated. Everything below is explicitly divided into **directly verified data**, **bibliographic citations inspected via search snippets**, and **unverified archival leads**.

---

## 2. Core Academic Replication Datasets (Highest-Yield Pre-2008 GP Records)

The single most reliable public repositories for granular, pre-2008 Gram Panchayat-level data in West Bengal are academic replication archives from longitudinal political economy studies.

### Lead A: Bardhan & Mookherjee Longitudinal Panchayat Dataset (1978–1998)
* **Election Years Covered:** **1978, 1983, 1988, 1993, 1998** (with subsequent follow-up rounds up to 2004).
* **Coverage & Smallest Observed Unit:** **Gram Panchayat (GP)**. Longitudinal sample of **89 Gram Panchayats** distributed across **15 districts** of West Bengal.
* **Fields / Variables:** GP council party composition (Left Front vs. INC/TMC/Others), election year, seat shares, reservation status, village land distribution, and local public resource allocations.
* **Exact Archival URLs:**
  * **American Economic Association (AEA) Portal:** [`https://www.aeaweb.org/articles?id=10.1257/aer.100.4.1572`](https://www.aeaweb.org/articles?id=10.1257/aer.100.4.1572)
  * **OpenICPSR Project Repository:** [`https://www.openicpsr.org/openicpsr/project/114948/version/V1/view`](https://www.openicpsr.org/openicpsr/project/114948/version/V1/view)
  * **Associated Publication:** Pranab Bardhan & Dilip Mookherjee (2010), *"Determinants of Redistributive Politics: An Empirical Analysis of Land Reforms in West Bengal, India"*, *American Economic Review*, 100(4): 1572–1604.
* **Verification Status:**
  * **Verified:** The OpenICPSR repository ID `114948` and AEA replication linkage were confirmed.
  * **Unverified / Requires Download:** The full internal CSV/DTA codebook within the OpenICPSR bundle (whether GP names are explicitly string-named or masked by pseudo-IDs) could not be parsed before tool termination.

---

### Lead B: Chattopadhyay & Duflo Birbhum Panchayat Study (1998 Linkage)
* **Exact Election-Year Linkage (Verified):** **May 1998**.
  * *Institutional timeline verified from primary documentation:* The 1993 West Bengal Panchayat Constitution Amendment introduced a **one-third reservation for women among general GP councilors/members (ward-level)**. The **1998** modification specifically introduced **rotational reservation of the position of Pradhan (GP Head)** for women, Scheduled Castes (SC), and Scheduled Tribes (ST).
  * Field surveys were conducted in **2000**, measuring public goods outcomes from the elected 1998–2003 GP term.
* **Districts & Smallest Observed Unit:** **Birbhum** district only (in West Bengal; the parallel arm was in Udaipur, Rajasthan). Unit: **Gram Panchayat** (165 GPs sampled across Birbhum blocks).
* **Fields / Variables:** GP identification, gender/caste reservation of the Pradhan seat (`female`), investment in drinking water facilities (`water`), road construction/repair, and irrigation infrastructure.
* **Exact Archival URLs:**
  * **DOI / Econometrica:** [`https://doi.org/10.1111/j.1468-0262.2004.00539.x`](https://doi.org/10.1111/j.1468-0262.2004.00539.x)
  * **NBER Working Paper 8615:** [`https://www.nber.org/papers/w8615`](https://www.nber.org/papers/w8615)
  * **Public Teaching Replication CSV (`india.csv`):** Frequently hosted across academic syllabi (POLI 30D / QSS labs on AWS/GitHub/RPubs, e.g., derived from J-PAL data).
* **Verification Status:**
  * **Verified:** The 1998 election linkage and core variable scheme (`village`, `female`, `water`, `irrigation`) were confirmed.
  * **Important Caveat:** In the common educational `india.csv` extract, `village` is typically coded as an integer identifier (1 to 165) rather than the literal Bengali revenue village/GP string name. Accessing the literal GP names requires the un-anonymized primary J-PAL/MIT survey roster.

---

## 3. Official State & District Records: Findings & Distinctions

### A. West Bengal State Election Commission (WBSEC)
* **Official Domains:** `http://www.wbsec.gov.in` and `http://www.wbsec.org`.
* **Archival Reality for 2003, 1998, 1993:**
  * The modern WBSEC online portal does **not** maintain active, searchable web tables for the 2003, 1998, or 1993 GP ward/candidate returns. Modern dynamic result modules begin with the 2013 and 2018 cycles.
  * Web searches against Internet Archive Wayback snapshots (`wbsec.gov.in/*`) did not index static tabular GP returns from 2003 or 1998.
* **Verified Official Printed Reference (Commission Publication):**
  * Multiple political science treatises cite the formal bound commission volumes:
    * *West Bengal State Election Commission (2003): Panchayat General Elections, 2003, Results of Gram Panchayat Elections.* (WBSEC, Kolkata).
    * Political analysis volume: *CPI(M) West Bengal State Committee (2003): Paschimbanga Sastha Panchayat Nirbachan 2003: Tathya O Sameeksha (6th Panchayat Election 2003: Facts and Review).*

---

### B. District-Specific Breakdown & Traps (District Totals vs. GP Returns)

#### 1. Birbhum
* **2003 Aggregate Summary (Verified via official compendiums on Scribd):**
  * **Total Gram Sansads (Wards):** 2,096
  * **Total Gram Panchayats:** 167
  * **Total GP Seats:** 2,258
  * **Panchayat Samiti Members:** 412
  * **Zilla Parishad Seats:** 35
  * *Critical Rule Check:* These numbers represent **district-level aggregates**, not individual GP/candidate returns.
* **1998 GP-Level Data:** Best accessed via the Chattopadhyay-Duflo Birbhum survey files (165 GPs).

#### 2. Malda (Maldah) & Cooch Behar (Koch Bihar)
* **Verified Micro-Study (EPW 2009):**
  * Citation: Rajarshi Dasgupta (2009), *"The CPI(M) 'machinery' in West Bengal: Two village narratives from Kochbihar and Malda"*, *Economic and Political Weekly*, 44(9).
  * **Malda Block-Level Data Recorded:** In Harishchandrapur-I Block for the 2003 elections:
    * Electors: 82,849; Votes polled: 74,937; Reserved seats: 64.
    * Party seat distribution: CPI(M): 70; INC: 33; AIFB: 18.
  * *Unit:* Block/Panchayat Samiti summary and illustrative village narratives, but not a full state-wide GP directory.

#### 3. Nadia, Murshidabad, Uttar Dinajpur, Dakshin Dinajpur, Undivided Jalpaiguri, North & South 24 Parganas
* **District Portals (`nadia.nic.in`, `murshidabad.gov.in`, `uttardinajpur.gov.in`, `coochbehar.gov.in`, etc.):**
  * Current NIC district websites only host incumbent PRI directories or recent election schedules (2018/2023). Historical candidate-level sheets from 2003, 1998, and 1993 were not uploaded as machine-readable web pages.
  * *Historical Administrative Boundary Note:* Dinajpur was bifurcated into **Uttar (North) Dinajpur** and **Dakshin (South) Dinajpur** in April 1992. Elections prior to 1993 reflect undivided West Dinajpur. 24 Parganas was bifurcated into North and South 24 Parganas in 1986 (1988 was their first separate election). Undivided Jalpaiguri included Alipurduar until 2014.

#### 4. Darjeeling & Siliguri Mahakuma Parishad (Special Election Status)
* **Administrative Distinction:**
  * Under the **Darjeeling Gorkha Hill Council (DGHC) Act, 1988**, the three-tier Panchayati Raj system was modified in the hill subdivisions of Darjeeling district (Darjeeling Sadar, Kurseong, Kalimpong). The Zilla Parishad tier was replaced by the DGHC. Elections to Gram Panchayats and Panchayat Samitis in the hills were held irregularly (e.g., two-tier elections in 1995 and 2000).
  * For the plains subdivision of Darjeeling district, the state created the **Siliguri Mahakuma Parishad (SMP)** in 1989. SMP exercises the powers of a Zilla Parishad for the plains blocks (Matigara, Naxalbari, Phansidewa, Kharibari). GP elections under SMP ran on the standard statewide schedule (1993, 1998, 2003).

---

## 4. Summary Matrix: Verified Content vs. Unverified Leads

| Source / Entity | Election Year(s) | Smallest Unit | Verified Content | Unverified Lead / Archival Path |
| :--- | :--- | :--- | :--- | :--- |
| **Bardhan & Mookherjee Dataset** | 1978, 1983, 1988, 1993, 1998 | Gram Panchayat | AEA publication confirmed; OpenICPSR project `114948` registered. Longitudinal panel across 15 WB districts. | Exact GP name mapping inside the raw data bundle requires unzipping OpenICPSR `114948`. |
| **Chattopadhyay & Duflo Study** | 1998 | Gram Panchayat | Linkage verified: studied May 1998 Birbhum Pradhan reservations. Variable schema confirmed (`female`, `water`, `irrigation`). | Literal revenue GP names in public `india.csv` teaching cuts are anonymized as numeric codes. Full names require the J-PAL master survey key. |
| **WBSEC Published Volumes** | 2003 | Gram Panchayat / Ward | Document title verified: *Results of Gram Panchayat Elections (2003)* published in hardcopy by WBSEC. | Web/HTML portal copies are not currently hosted live on `wbsec.gov.in`. |
| **Birbhum PRI Compendium** | 2003 | District | Aggregate figures verified: 167 GPs, 2,096 Sansads, 2,258 seats. | District totals only; individual GP ward/candidate breakdown not included in this document. |
| **Dasgupta (EPW 2009)** | 2003 | Block / Village | Harishchandrapur-I (Malda) seat counts and Cooch Behar ethnographic village narratives verified. | Only covers selected case study areas. |
| **Kolkata Gazette (Extraordinary)** | 1993, 1998, 2003 | GP / Ward / Seat | Statutory notification mechanism for reservation orders and winning candidates by District Magistrates. | Online e-Gazette repository (`egazette.wb.gov.in`) primarily archives recent gazettes; physical volumes are held at the West Bengal State Archives/National Library. |

---

## 5. High-Value Next Leads for Primary Archival Extraction

For researchers seeking complete, named GP candidate and reservation schedules from 2003 and earlier:

1. **Direct Inspection of OpenICPSR Project 114948:**
   * URL: `https://www.openicpsr.org/openicpsr/project/114948/version/V1/view`
   * Download the primary survey replication package to extract the 89-GP panel dataset covering 1978–1998.
2. **Contacting J-PAL Dataverse Curators for Birbhum 1998 Key:**
   * Request the crosswalk file linking the anonymized village ID numbers in Chattopadhyay & Duflo (2004) to the official 1998 Birbhum Gram Panchayat and Block names.
3. **Physical / Microfiche Gazettes (Kolkata Gazette Extraordinary):**
   * Under the *West Bengal Panchayat Elections Act* and *Panchayat Constitution Rules*, notifications of reserved seats for Pradhans and lists of contesting/elected candidates are gazetted by the respective District Panchayat Election Officers (District Magistrates) 2–4 months prior to and immediately following each election (typically March–June of 1993, 1998, and 2003). Physical holdings are maintained at the **National Library of India (Belvedere, Kolkata)** and the **West Bengal State Archives (Shakespeare Sarani, Kolkata)**.
4. **Bureau of Applied Economics and Statistics (BAES):**
   * Review physical copies of the *District Statistical Handbooks (DSH)* published annually for Birbhum, Nadia, Murshidabad, Malda, North/South Dinajpur, Cooch Behar, Jalpaiguri, and 24 Parganas, which contain the official Local Bodies chapters.
