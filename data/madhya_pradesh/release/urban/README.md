# Bhopal and Indore municipal sources

The handoff retains 170 reported 2022 ward-councilor winners: 85 each in Bhopal and Indore. It also preserves a separate official current Indore council roster. No persistence estimates are produced and neither table enters the pooled master.

## Sources and coverage

The [Indore list](https://hindi.webdunia.com/madhya-pradesh/indore-corporator-list-2022-122071800018_1.html), published July 18, 2022, and [Bhopal list](https://www.naidunia.com/madhya-pradesh/bhopal-mp-bhopal-nagar-nigam-election-2022-results-who-will-become-the-ruler-of-the-city-in-the-capital-decision-today-7681063), published July 17, 2022, are contemporaneous news reports. They contain names and parties for numbered wards 1–85 in each city. The Bhopal article labels its list as winners but also describes counting still in progress; the records remain provisional until checked against official returns. Spellings and party labels are retained verbatim alongside the normalized party codes. The Bhopal spellings `कांग्रेस` and `कांग्र्रेस` both map to INC; `भाजपा` maps to BJP and `निर्दलीय` to IND.

| City | Rows | BJP | INC | Independent | Recorded sex | Recorded reservation |
|---|---:|---:|---:|---:|---:|---:|
| Bhopal | 85 | 58 | 22 | 5 | 0 | 0 |
| Indore | 85 | 64 | 19 | 2 | 0 | 0 |

No votes, sex or reservation values are supplied by these lists. Missing values remain null; names and seat numbers are not used to infer sex or historical exposure. The source URLs, original HTML, retrieval times and hashes are retained under `../../raw/urban/`. The party totals agree with the Bhopal article's summary and [contemporaneous Indore reporting](https://timesofindia.indiatimes.com/city/indore/mayor-councillors-wait-for-first-salary-jobless-mill-workers-in-a-fix/articleshow/95329488.cms); agreement on totals is not row-level verification.

The official [Indore council page](https://imcindore.mp.gov.in/councillors) embeds its records in `__NEXT_DATA__`. Its source metadata reports an update on June 15, 2026; it was retrieved November 9, 2026 UTC. The separate roster contains 85 CMS entries, 84 printed ward labels and 82 interpretable Mr./Mrs./Ms. honorifics. One entry has no ward label; ward 62 is absent from the identified ward set, but the blank entry is not assigned that number. Ward 44 says “Court Decision Pending”; ward 58 has no name; ward 83 names Jitendra Rathore, whereas the 2022 news list names Kamal Laddha. These differences demonstrate why a current roster must not silently replace election-time winners. The honorific-derived field applies only to the roster entry; it is not merged into the 2022 outcome.

The retained [February 1, 2023 municipal bond offer document](https://archives.nseindia.com/content/equities/DEBT_IPO_RHP_IMC.pdf), printed page 41, independently states that Indore has 85 wards and 85 elected councilors. It does not independently validate the 85 winner identities. It is a primary supporting document issued by the municipality and hosted by the exchange.

## Acquisition limits

The live MP commission publication/archive endpoints timed out, as did their `www` hostname and the tested MP Information Department phase-one results URL. These are access failures, not evidence of absent records. A January 31, 2023 Internet Archive capture of the old commission publication index is retained with its receipt. The catalog lists historical municipal reports but its download controls are ASP.NET postbacks. A bounded archived-PDF search returned 2017 result files rather than the target city's general-election returns; its result records are retained, without treating those files as Bhopal/Indore 2022 data.

The existing `../../raw/NN-V-2014-15final.pdf` remains in place and was not duplicated. Its inspected pages include administrative and aggregate election tables; no ward-level winner handoff is claimed from that scan. The 2022 commission report, original reservation notifications and dated ward-boundary links remain to be acquired and reconciled. These missing sources prevent a longitudinal quota comparison from this handoff.

## Reproduction and fields

`winners.parquet` has one row per `(year, body, ward_no)`. `indore_council_roster.parquet` has one row per source CMS entry, keyed by `source_entry_id`, with nullable ward labels. `dictionary.csv` defines both tables; the adjacent schema files record types. `audit.json` pins output hashes and reports coverage. Primary and secondary originals remain in `../../raw/urban/`, with a shared source manifest and initial acquisition receipts.

```sh
PYTHONPATH=src python -m local_elections.states.mp.urban build
PYTHONPATH=src python -m pytest -q tests/test_mp_urban.py
ruff check src/local_elections/states/mp tests/test_mp_urban.py
```

`fetch` uses the existing shared acquisition client, reuses verified files and refuses to overwrite changed source bytes. The parser reads only retained files, checks hashes, rejects incomplete or duplicated winner frames and verifies typed Parquet round trips. It preserves all original row text and source links. No cross-election join or winner-to-current-roster identity link has been asserted.

## Schema normalization

The unpublished handoff `reported_winners_2022.parquet` is now `winners.parquet`. Columns follow the shared [naming contract](../../../../docs/naming.md): `election_year → year`, `city → body`, `office → tier`, `ward_number → ward_no`, `winner_name_raw → winner`, `woman_reserved → reserved_woman`, `winner_votes → votes`, and `source_file → source_path`. The roster's `woman_from_honorific` is now `member_woman_from_honorific` to identify whose attribute it describes. `ward_no` and `source_entry_id` are strings; woman indicators are nullable Int8 values (0/1/null). The canonical tier is `ulb_ward`. Source values and missingness were compared row by row before removing the old files.

The `*.schema.json` files specify fields, required values, allowed values and primary keys; `dictionary.csv` is generated from those same definitions. Run the parser's `verify` command to check the contracts, keys, output hashes and row-level source hashes. The repository manifest also includes these supplemental tables and their release metadata.
