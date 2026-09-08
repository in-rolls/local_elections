# Final Gram Panchayat Reservation Research Report

## 1. Executive Status & Acquisition Summary

* **Target Priority:** Exact Pradhan (head office) reservation category (Women, SC, ST, overlaps) of named Gram Panchayats (GPs) for West Bengal in 2003, followed by 1998 and 1993.
* **Current Data Acquisition Status:** **Zero new named GP reservation records were fully ingested during this window.**
* **Previously Acquired Baseline:** The 161 named Birbhum GP reservation records for the 1998 election (originating from the Chattopadhyay–Duflo 2000 survey sample) remain verified and documented. No additional 2003 named GP rosters were parsed into plaintext records due to platform-level access blocks and query cutoffs.

---

## 2. Access Failures & Blocking Diagnoses

Direct automated scraping encountered access barriers on primary academic replication repositories:

1. **OpenICPSR (`10.3886/E112367V1` — Bardhan & Mookherjee AER 2010):**
   * **Target URL:** `https://www.openicpsr.org/openicpsr/project/112367/version/V1/view`
   * **Failure:** HTTP `403 Forbidden`. The OpenICPSR frontend employs Cloudflare/bot mitigation that rejects unauthenticated automated HTTP GET scrapers.
2. **Harvard Dataverse Root Inventories (`10.7910/DVN/PXV79W` and `10.7910/DVN/O3UKFO` — Beaman et al. / Topalova):**
   * **Target URLs:** `https://doi.org/10.7910/DVN/PXV79W`, `https://doi.org/10.7910/DVN/O3UKFO`
   * **Failure:** Root web landing pages and inventory browsers returned HTTP `403 Forbidden` to unauthenticated programmatic requests.
3. **External Platform Timeout / Tool Cancellation:**
   * **Target URL:** `https://redivis.com/datasets/o3ukfo-powerful-women-and-aspirations-in-india`
   * **Status:** Retrieval was canceled at the 10-minute cutoff window before table schemas could be extracted.

---

## 3. Inspected Candidates vs. Unverified Leads

| Repository / Source | Concrete URL / Identifier | Inspected Status | Classification | Reservation Coverage Potential |
| :--- | :--- | :--- | :--- | :--- |
| **Harvard Dataverse API (O3UKFO)** | `https://dataverse.harvard.edu/api/datasets/:persistentId/versions/:latest/files?persistentId=doi:10.7910/DVN/O3UKFO` | API endpoint confirmed responsive (JSON payload emitted, bypassing HTML 403) | **Unverified Lead** (Payload pending parsing) | Covers Beaman et al. (QJE 2009) 6 districts (Nadia, Howrah, Hooghly, Birbhum, South 24 Parganas, Burdwan) across 1998, 2003, 2008 Pradhan cycles. |
| **Redivis Mirror (O3UKFO)** | `https://redivis.com/datasets/o3ukfo-powerful-women-and-aspirations-in-india` | Exact URL confirmed indexed; unparsed due to runtime cutoff | **Unverified Lead** | Mirror of `DVN/O3UKFO` containing harmonized GP/village data tables and variable dictionaries without Dataverse UI blocks. |
| **OpenICPSR (112367 V1)** | `https://www.openicpsr.org/openicpsr/project/112367/version/V1/view` (DOI: `10.3886/E112367V1`) | Blocked (HTTP 403) | **Unverified Lead** | 57 Gram Panchayats (Bardhan-Mookherjee sample) with 1993, 1998, and 2003 reservation history (distinct from 89 villages). |
| **Chattopadhyay–Duflo (2000)** | *Known Reference* | Previously acquired | **Acquired Data** | 161 Birbhum GPs for 1998 Pradhan reservation status. |

---

## 4. Focused Next Retrieval Steps

1. **Query Dataverse API Directly by Persistent ID:**
   * Harvard Dataverse's web UI returns HTTP 403, but its REST API (`/api/datasets/:persistentId/versions/:latest/files`) responds.
   * *Next action:* Query the file metadata JSON to extract direct file IDs, then stream individual `.tab` or `.dta` files using `https://dataverse.harvard.edu/api/access/datafile/{file_id}`.
2. **Inspect the Redivis Tabular Interface for `O3UKFO`:**
   * Use the established Redivis dataset endpoint (`https://redivis.com/datasets/o3ukfo-powerful-women-and-aspirations-in-india`) to view column dictionaries and extract GP identifier lists and reservation variables (`res98`, `res03`, `res08`).
3. **Session-Authenticated Retrieval for OpenICPSR `112367`:**
   * Bypass Cloudflare 403 on OpenICPSR via an interactive browser session to download the replication package for the 57 GP longitudinal panel (1993–2003).
