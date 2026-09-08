# Birbhum Pradhan reservation observations

One row of [observations.parquet](observations.parquet) is **one source GP
and reported period**. There are 496 rows: 166 from Chattopadhyay–Duflo and
330 from the Beaman mirror (165 current, 165 previous). This is an auditable
extraction, not a reconciled GP-election panel. [CSV](observations.csv) is
provided for inspection; Parquet retains nullable integers and booleans.

`source_gp_id` is a string in its source's identifier system, not an LGD
code. The unique key is `(source, source_gp_id, reported_period)`.
Pradhan office reservation is the construct; neither an incumbent's caste
or gender nor ward reservation is substituted for it.

## Codes and dates

All six Beaman reservation fields and the three older fields use **1=Yes,
2=No**. The parser converts them to nullable booleans and preserves the
numeric readings as `raw_women`, `raw_sc`, `raw_st`. Missing remains null;
an unexpected code raises an error. Category-by-source recode counts are
in [validation.json](validation.json), with the complete source labels in
[stata_labels.json](stata_labels.json). The
[dictionary](dictionary.csv) describes every observation column.

- The older survey refers to the **1998 election**, established by the
  summer-2000 fieldwork description in [NBER w8615](https://www.nber.org/system/files/working_papers/w8615/w8615.pdf),
  section 2.3. The study explains that five GPs were used for pre-testing.
  All 166 source rows survive; 161 have all reservation fields.
- The Beaman study concerns the 1998 and 2003 terms. Current `year=1` is
  explicitly labeled 2003 for 163 GPs. Ayas reports “not applicable”;
  Rudranagar reports “other year” with inconsistent 2004/2006 entries.
  Those two retain the study's 2003 term context but are flagged and
  excluded from the strict subset. The [study](https://www.nber.org/system/files/working_papers/w14198/w14198.pdf)
  provides the term context, not a GP-specific official order.
- Previous `prev_year=1` explicitly identifies 1998–2003 for 152 GPs.
  Ten others report shorter service intervals contained in 1998–2003;
  assigning these to the 1998 cycle is an explicit inference and fails
  the strict filter. Paikor-II, Kirnahar-II and Rudranagar report previous
  incumbents serving after the 2003 election. Their `election_year` is
  null; they are not treated as observations of 1998 reservation.

## Source joins and conflicts

The old Part A table is the left table for its name join to Part B.
Both have 166 unique `gpnum` values. A one-to-one left join is enforced,
requires identical identifier sets and preserves all 166 rows with 100%
matches. Names are retained verbatim, including blanks.

The cross-source audit uses only an exact key after uppercasing and removing
punctuation/whitespace from **both block and GP**. The audit is a one-to-one
outer join: 104 matches, 62 older-only rows and 61 later-only rows.
[cross_source_audit.parquet](cross_source_audit.parquet) preserves all
matched and unmatched rows, including source names and both readings.
The validation report shows match rates by the older source's block.
No fuzzy linkage, identifier substitution or category-based identity
inference has been performed. Unmatched spellings are not evidence that
GPs are absent. External match precision/recall has not been adjudicated.

Three matched GPs disagree on a caste-reservation field for a period
linked to 1998:

| GP | Older source | Later source's previous period |
|---|---|---|
| Ayas | SC=Yes and ST=Yes | SC=No and ST=No |
| Kusumba | ST=Yes | ST=No |
| Panrui | SC=Yes | SC=No |

All three agree on the women field. Ayas's older row independently fails
the within-source check because it reports both SC and ST reservation.
Kusumba and Panrui's later previous-year assignments are among the inferred
shorter terms. Kirnahar-II also differs between sources, but its later
previous incumbent is post-2003; it is not counted as a same-year conflict.

`eligible_within_source_strict` requires complete fields, place names, no
simultaneous SC/ST claim and explicit year evidence (or the dated older
study). `eligible_after_exact_name_audit` additionally excludes detected
1998 source conflicts. The resulting counts are 163 current Beaman rows,
151 previous Beaman rows, and 158 older rows. **These are source-specific
filters, not official certification or a deduplicated panel.** Many
cross-source names still require review.

[review_queue.csv](review_queue.csv) keeps missing data, date exceptions,
contradictions and detected source conflicts. Every reading remains in the
full observation table. A future reconciled panel needs documented name
crosswalks, adjudicated conflicts and preferably official orders.

## Reproduce

`make wb-gp-reservations` runs
[parse_birbhum.py](../../../../src/local_reservations/states/wb/parse_birbhum.py)
and rebuilds the reservation coverage matrix. The parser records original
paths and digests and checks the recovered Beaman file against its acquired
SHA-256. Each output is compared with its Parquet round trip.
