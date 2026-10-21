# Column names

One rule set for every table this repository publishes and every state
repository it pools. A column's name says what it describes, which concept, and
how the value was obtained. `tools/naming.py` checks it.

## 1. Shape

    <subject>_<concept>[_<form>][_<year>]

| Part | Values |
|---|---|
| subject | `reserved` (the seat's quota) · `winner` · `candidate` · `runner_up` |
| concept | `caste` · `woman` |
| form | see section 3 |
| year | only in wide panels, always last: `reserved_woman_2015`, `winner_woman_2020` |

The seat and the person never share a name: `reserved_woman` is the quota,
`winner_woman` is who won; `reserved_caste` is the seat's category,
`winner_caste` the person's own.

## 2. Words that are not column names

`gender`, `sex`, `female`, `women`, `category`, `quota`, and `reservation` on
its own. Their meaning goes into the subject and concept.

Raw source files keep their own headers (`CategoryOfGramPanchayat`, `sex`).
Names change once, where a source is first parsed, never in the source file.
Frozen inputs keep theirs too - content-addressed snapshots, `raw_archive/`,
and outside datasets transposed as they came (UP's Weaver preparations) - and
are read under the new names.

## 3. How a value was obtained

A **bare** name is a value read from the row's own source cell, normalized:

| Form | Type | Meaning |
|---|---|---|
| (none) | `*_woman`: Int8 1 / 0 / null · `*_caste`: the state's category enum (`NONE`, `SC`, `ST`, `BC`, `BC_A`, …) | normalized reading of the cell. `*_woman` is null when unknown, unstated, or recorded as other |
| `_raw` | string | the cell exactly as printed, women's part included |
| `_local` | string | the printed **caste part** only (`UR`, `अनारक्षित`, `பொது`) |
| `_code` | string | a state's compact code (`GENW`, `SCW`) |
| `_label` | string | pooled display label (`SC Woman`) |
| `_stated` | Int8 | 1 if the source states it |

Anything **not** read from the row's own cell says how in its name, and has a
method column beside it:

| Form | Mechanism | Paired column |
|---|---|---|
| `_from_<evidence>` | deterministic, from another field or document: `winner_woman_from_honorific`, `seat_no_from_serial`, `winner_woman_from_candidates` | — (the evidence is in the name) |
| `_latin` | transliteration into Latin script: `winner_latin`, `gram_panchayat_latin` | `<column>_method`: `source` where the record printed Latin, else tool and version (`indicate 1.2 model`) |
| `_probability` | statistical inference: `winner_woman_probability` | `<column>_method`: model, versions, training labels |
| `_basis` | which of several recorded sources or rules supplied a bare value: `winner_basis`, `winner_woman_basis` | — (the column is itself the record) |

Method columns are per row, because pooled tables mix states and a state can
mix methods. Where a run did not record its tool version, the method says so
(`indicate model; version not recorded`) rather than guessing one. A true/false
flag about a name (`winner_printed_in_latin`) is not a reading and needs no
method.

`*_woman` values are stored as Int8 (`reserved_woman`, `candidate_woman`,
`winner_woman`); a raw `other` stays in `*_woman_raw` and leaves the value null. An inferred value never overwrites a recorded one: `winner_woman`
(recorded) and `winner_woman_probability` (inferred) are separate columns.

## 4. The full set

| Seat | Person (`winner_`, `candidate_`, `runner_up_`) |
|---|---|
| `reserved_caste`, `reserved_caste_local`, `reserved_caste_scheme` | `<p>_caste`, `<p>_caste_raw` |
| `reserved_woman`, `reserved_woman_stated` | `<p>_woman`, `<p>_woman_raw`, `<p>_woman_basis` |
| `reserved_raw`, `reserved_raw_original`, `reserved_code`, `reserved_label` | `<p>_woman_probability`, `<p>_woman_probability_method` |
| checks: `reserved_caste_conflict`, `reserved_woman_conflict`, `reserved_source_conflict` | `<p>_latin`, `<p>_latin_method` |

## 5. Earlier names

| Before | Now |
|---|---|
| `caste_reservation` | `reserved_caste` |
| `caste_reservation_local` | `reserved_caste_local` |
| `caste_scheme` | `reserved_caste_scheme` |
| `woman_reserved`, `women_reserved`, `female_reserved` | `reserved_woman` |
| `gender_stated` | `reserved_woman_stated` |
| `reservation` (pooled label) | `reserved_label` |
| `reservation_raw`, `seat_reservation`, `gp_reservation_status` | `reserved_raw` |
| `reservation_raw_original` | `reserved_raw_original` |
| `reservation_match_score`, `reservation_source_conflict` | `reserved_match_score`, `reserved_source_conflict` |
| `sc_reserved_ward_count`, `st_…`, `women_…` | `reserved_sc_ward_count`, `reserved_st_ward_count`, `reserved_woman_ward_count` |
| `winner_gender`, `winner_female`, `female_winner` | `winner_woman` (Int8 1/0) |
| `winner_gender_raw`, `winner_sex_raw` | `winner_woman_raw` |
| `winner_gender_basis` | `winner_woman_basis` |
| `winner_female_probability_from_name`, `…_method` | `winner_woman_probability`, `winner_woman_probability_method` |
| `candidate_gender`, `candidate_female`, `gender` (candidate) | `candidate_woman` (Int8 1/0) |
| `candidate_gender_raw`, `sex_raw`, `gender_raw` | `candidate_woman_raw` |
| `category`, `candidate_category` (person) | `candidate_caste` |

## 6. Where the pooled repository renames

The pooled tables are written under these names. The in-tree parsers
(`states/*`) and the adapters still emit the older row vocabulary
(`caste_reservation`, `woman_reserved`, `winner_gender`, ...), and
`common/master.py`'s `PUBLISHED` map translates it as the tables are written
(`build_master.write`, `common/contract.py`). `DICTIONARY.md` documents the
row vocabulary the parsers write; `schemas/*.json` documents the published
tables. Once the parsers are restructured, the row vocabulary takes the
published names and the map goes.

`make naming` checks every published table and every pinned sibling file
(0 violations at the time of writing).
