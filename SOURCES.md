# Where GP-level reservation data comes from, state by state

A feasibility survey, not a summary of what we hold. Every format claim below
comes from opening the file and measuring how much extractable text it has —
never from what a website says it publishes.

Two scripts back this document and both can be re-run:

```
make inventory
make probe
```

They write `data/inventory.csv` and `data/sources_probe.csv`.

## The one thing worth knowing first

**Whether a PDF has a text layer decides the cost of a state, and nothing on the
publisher's website tells you.** `local_elections_haryana` was cheap to build for
exactly one reason: its notifications were digitally generated text, so no OCR
was involved. That turned out to be unusual. Of the sources opened for this
survey, Punjab, Maharashtra, Chhattisgarh, West Bengal and Madhya Pradesh are
all images.

So the classification here is `digital-text` (≥800 chars/page), `mixed`,
`encoded-text`, or `scan`. `encoded-text` means a dense hidden glyph stream
exists but does not decode to the script visible on the page; Gujarat's 2020
orders are the concrete case. A scan is not a dead end — `savitr` (Surya on
MLX) and `parse_unsearchable_rolls` exist for exactly this — but it changes a
week of work into a month.

## The surprise: much of the acquisition is already done

`data/` already holds ~2 GB of source documents for states the coverage table in
[README.md](README.md) still shows as blank. For these the question is not "can
we get it" but "what is in it".

<!-- holdings:start -->
| state | text | scan | encoded | mixed | pages | what is held |
|---|---|---|---|---|---|---|
| Bihar | 290 | 0 | 0 | 0 | 9,193 | PRI winners 2006-2016; also `local_elections_bihar` |
| **Jharkhand** | 108 | 28 | 0 | 8 | 4,970 | **2015 mukhiya (GP head) reservation by district; 2022 Form-23 ZP members** |
| West Bengal | 279 | 285 | 0 | 4 | 4,149 | 2018 ZP gazettes parsed with drafts separate; named Birbhum 1998/2003 research reservations and 2013/2018/2023 office schedules parsed; ward, results and reference outputs retain review flags; [reservation gaps](data/wb/vintage_search/README.md); [GP source search](data/wb/gp_source_search.md), [derived GP data and review](data/wb/derived/README.md) |
| **Karnataka** | 236 | 202 | 0 | 2 | 1,552 | **2016 taluk & zilla panchayat winners with party**; plus `Karnataka_GP_ReservationHistory.dta`. 244 of the documents are deliberately unread - see data/karnataka/readme.md |
| **Jammu & Kashmir** | 105 | 8 | 0 | 0 | 1,488 | **2010/2016/2018 block-wise, panch-ward reservation with SC/ST/OC population** |
| **Andhra Pradesh** | 15 | 17 | 0 | 13 | 1,243 | **2020 district gazettes: GP, MPTC, ZPTC, MPP reservation** |
| Assam | 1 | 31 | 0 | 0 | 1,026 | 2020 municipal reservation parsed; all 27 district PRI notifications for 2025 acquired; 4 district notifications parsed |
| Chandigarh, Puducherry, Delhi | 7 | 2 | 0 | 0 | 707 | mostly urban local bodies |
| **Goa** | 37 | 4 | 0 | 0 | 687 | **2012/2017/2022 `panres_<taluka>` panchayat reservation + ward category** |
| Gujarat | 0 | 0 | 45 | 0 | 605 | **2020 SEC rotation orders: 16 district-panchayat and 29 taluka-panchayat PDFs; parsed into 1,178 seats** |
| Madhya Pradesh | 0 | 2 | 0 | 0 | 351 | two large OmniPage-OCR'd volumes |
| Odisha | 6 | 0 | 0 | 0 | 254 | 2017 reservation of sarpanch/ward member - **district totals, not seat-level** |
| Tamil Nadu | 11 | 1 | 0 | 0 | 74 | municipal/corporation gazettes plus GP-president reservations; [2011 roster and 2001 amendment exports](data/tn/readme.md) remain separate from pooled rows; originals and earlier leads are in the [cross-state source ledger](data/source_search/early_heads/README.md) |
| Himachal Pradesh | 0 | 1 | 0 | 0 | 3 | one source PDF |
| Rajasthan | 0 | 0 | 0 | 0 | 0 | sources and parsed data in [`local_elections_rajasthan`](https://github.com/in-rolls/local_elections_rajasthan) |
<!-- holdings:end -->

An India-egress review on 26 August 2026 changed two acquisition findings:

- [Assam SEC's 2025 panchayat page](https://sec.assam.gov.in/panchayat-election-2025)
  publishes 27 district reservation PDFs. All 27 are held under
  `data/assam/2025_reservation/`, with exact URLs, retrieval timestamps, byte
  counts, and SHA-256 values. They span several rural tiers and are scans; they
  are not represented in parsed slices yet.
- [Gujarat SEC's district-panchayat page](https://sec.gujarat.gov.in/district-panchayat-2020.htm)
  publishes 16 PDFs and its
  [taluka-panchayat page](https://sec.gujarat.gov.in/taluka-panchayat-2020.htm)
  publishes 29. All 45 are held under `data/gujarat/2020_reservation/`. The
  pages are visually clear Gujarati scans, but the hidden text is a misencoded
  glyph stream. They are now parsed as two source series: 532 district-
  panchayat and 646 taluka-panchayat seats. Acquisition, OCR, and parsing are
  separate stages; every source reproduces its published eight-category total.
  The independent controls come from section 4.3 of the SEC's 2021 Annual
  Statistical Report ([searchable mirror](https://www.scribd.com/document/766555637/Annual-Report-full-2021));
  Gandhinagar Taluka, which was outside that election series, is checked against
  the summary table printed in its held order.

Bold rows are the ones holding **GP-level reservation in machine-readable form
already on disk**. That is the shortest path to new coverage in this repo, and it
needs no network access at all.

**Karnataka's 439 documents are three groups and only one is parsed.** The 195
elected-member notifications carry seat, reservation, winner and party for the
2016 taluk and zilla panchayat cycle. The other two - 211 reservation gazettes
and 33 gram panchayat 2015 files - are held, provenanced and deliberately not
read: the gazettes restate a reservation the notifications already print, and
the 2015 files name nobody, being nomination counts, turnout and district x
taluk totals. That is a decision rather than a backlog; the reasoning is in
[data/karnataka/readme.md](data/karnataka/readme.md) so it does not have to be
made twice.

### What the held sources yielded

These four holdings now produce parsed slices without new acquisition. The
remaining gaps come from missing documents, incomplete rosters, or cells that
need a second reading; [WORKLIST.md](WORKLIST.md) records each one.

- **Jammu & Kashmir**: all 25 held 2016 PDFs are parsed into 12,300 panch-ward
  seats and 1,763 sarpanch seats. The plain English tables carry district,
  block, halqa, panch ward, SC/ST/OC population, percentages, and proposed
  reservation. Population alongside reservation makes the assignment rule
  auditable. The state now contributes 28,511 rows across 2010, 2016, and 2018;
  13 other held PDFs remain unparsed.
- **Goa**: `panres_2012_<Taluka>.pdf` is a "Report of Winning Candidate for V.P.
  Election" carrying taluka, panchayat, ward number, category of the ward
  (`G/ST/OBC/W/OBCW/STW`), the elected representative, their address, and votes
  polled. Three cycles are parsed (2012, 2017, and 2022), though the latter two
  rosters are incomplete. Reservation is at ward level because Goa's sarpanch
  is elected indirectly by the members.
- **Jharkhand**: the 2015 district notifications now yield 29,111 rows across
  mukhiya, panchayat-samiti, ward-member, and zila-parishad tiers. The documents
  mix scans, digital text, and legacy Kruti Dev-style Hindi. The source and OCR
  gaps are measured in [WORKLIST.md](WORKLIST.md), including the districts for
  which ward-level documents are not held.
- **Andhra Pradesh**: the held 2020 district gazettes now yield 80,021 GP-head
  and GP-ward seats across eight districts. The complete 13-district GP series
  is held; Chittoor, Guntur, Srikakulam, Visakhapatnam, and Vizianagaram remain
  acquired but unparsed.

### Traps in what is already held

- **Odisha's files are aggregates.** `2017_RESERVATION-OF-SARPANCH-DISTRICT-WISE.pdf`
  is one row per district with counts by category (SC 426, ST 1,237 … 6,794
  total), not one row per gram panchayat. Seat-level Odisha still has to be
  acquired.
- **Tamil Nadu's gazettes are urban.** Gazette 326 concerns municipalities and
  corporations. Village panchayat president reservation is not in what we hold.
- **Maharashtra is Mumbai only** — `data/maharashtra/mumbai/`, BMC 1997–2017.
  Two councils (2012, 2017) are parsed as `ulb_ward`; the ~28,000 rural GPs are
  absent entirely. And the one held sheet that states a reservation,
  `BMC-2007_raw.xlsx`, states the **2012** draw beside the 2007 winners: 115
  women's seats where 2007 had 76. Read at face value it mislabels every ward.
- **AP's tiers are mixed together.** Of its 45 documents, the GP-level set
  (`2020_res_gp/`) is 13; the other 32 are MPTC, ZPTC, MPP and MPL. Do not read
  the state-level text/scan split as applying to the GP files.

## States needing acquisition

Probed live; see `data/sources_probe.csv` for the machine-written record.

**Read that file with one caveat.** The probe opens the *first* document linked
from a seed URL. When the seed is a specific reservation page that is the right
document; when the seed is a district homepage it is whatever happens to be top
of the notice board. On the first run that produced two confident-looking
`digital-text` rows which turned out to be an NIC computer-disposal tender
(Chhattisgarh) and a Guntur staff transfer list (Andhra Pradesh) — neither has
anything to do with reservation.

So the probe records `topic_match`, and a row is only evidence when it says
`yes`. Getting that check right took three passes, which is itself the lesson:
bare `ward` matches *award*, `gram` matches *programme*, and the stem `reserv`
matches the tender boilerplate *"NIC reserves the right to reject any/all
quotations"*. It now requires a panchayat body term **and** a reservation
category term together. Seed specific pages, not homepages.

| state | ~GPs | source | format | verdict |
|---|---|---|---|---|
| Maharashtra | 27.9k | district portals (`washim.gov.in`), SEC reachable | **scan** (CamScanner) | OCR then build; biggest prize |
| Madhya Pradesh | 22.9k | SEC portal blocked; district portals reachable | **scan** | OCR then build |
| Punjab | 13.2k | district portals, 2024 election, block-wise | **scan** (CamScanner / print-to-image) | OCR then build |
| Chhattisgarh | 11.6k | district portals (`raigarh` notice page) | **scan** | OCR then build |
| Tamil Nadu | 12.5k | `tnsec.tn.gov.in` | unverified | needs India egress |
| Odisha (seat-level) | 6.8k | `sec.odisha.gov.in` | unverified | needs India egress |
| Himachal Pradesh | 3.6k | `sec.hp.gov.in` | unverified | needs India egress |

### Reachability

From ordinary non-India egress there is a clean split. **NIC-template district portals answer** — `washim.gov.in`,
`raigarh.gov.in`, `bilaspur.gov.in`, `dhule.gov.in`, `indore.nic.in`,
`guntur.ap.gov.in`, and the Punjab districts — and they serve their PDFs from
`cdn.s3waas.gov.in`, which also answers. **State-specific SEC domains refuse**:
`sec.odisha.gov.in`, `sec.gujarat.gov.in`, `tnsec.tn.gov.in`, `sec.hp.gov.in`,
`sec.assam.gov.in`, `panchayat.gujarat.gov.in`, `egramswaraj.gov.in`. The India
VPN confirmed that Assam and Gujarat are live and supplied the holdings above;
the refusal was the network path, not those sites being down.

Practical consequence: **most states are reachable through their district
collectorate portals even when the SEC is not.** That is more crawling surface —
20 to 36 districts per state instead of one index — but it is not blocked.

### The national shortcut, unverified

`egramswaraj.gov.in/ElectedRepresentativeReport.do` is a Ministry of Panchayati
Raj report covering every state, which would beat per-state scraping outright.
Two caveats before anyone gets excited: it is geo-blocked from here, and it very
likely carries the **representative's** caste and gender rather than the
**seat's** reservation. Those are different variables, and only the seat's
reservation is the assignment — a woman winning an unreserved seat is not a
reserved seat. Worth verifying behind a VPN; worth not assuming.

## Recommended order

1. **Jammu & Kashmir and Goa** — clean English text, already downloaded, and Goa
   gives three cycles. Days, not weeks.
2. **Jharkhand** — GP-level, already downloaded, and its legacy-Hindi encoding is
   a solved problem in this codebase.
3. **Andhra Pradesh** — the five held/unparsed district gazettes are the next
   clean continuation of an established parser and validation pipeline.
4. **Maharashtra** — the largest missing state by far. Requires OCR and a
   36-district crawl, so it is the first real project rather than a cleanup.
5. Anything behind the geo-block, once a VPN run confirms what is actually there.

## Caveat on what "reservation data" means

Two different artifacts get called this, and they are not interchangeable:

- the **seat reservation roster**, drawn by lot before the election, which is the
  assignment; and
- the **elected-members notification**, published after, which in some states
  (Haryana, Jharkhand) carries the seat's reservation *and* the winner's name in
  the same row, and in others carries only the winner.

Where both exist the second is better — it gives the outcome for free. Where only
a winners list exists without the seat's category, it does not substitute for the
roster, however tempting the caste and gender columns look.
