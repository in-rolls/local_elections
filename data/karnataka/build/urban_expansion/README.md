# Bengaluru ward panel, 2010–2015

The panel retains all 198 wards on the July 2009 boundaries. Among the 101 wards
not reserved for women in 2015, 25 were reserved for women in 2010 and 76 were
not. The former group has 24 observed winner outcomes, no recorded women, and
one unresolved outcome (ward 112). The latter has 76 observed outcomes and three
women (wards 52, 94, and 126). These are source-checked counts, not causal estimates.

`ward_panel_2010_2015.parquet` has string ward identifiers and nullable Int8
0/1 outcome and reservation fields. `dictionary.csv` and the adjacent schema
specify every column. `audit.json` records input/output hashes, source
conflicts, treatment support, denominators, and the Parquet round-trip check.
`recode_ledger.json` preserves consequential differences among source readings.

## Sources and measurement

The retained originals are in `../../raw/urban_expansion/`. Their acquisition
URLs, times, and hashes are in that directory's `manifest.jsonl`.

- **2010 assignment:** the April 16, 2010 elected-member gazette, all 16 pages.
  Every caste category and women-reservation flag was visually re-reviewed.
- **2015 assignment:** the April 13 roster reinstated by the June 23 notification,
  all five table pages (physical PDF pages 3–7). The winner gazette agrees on all
  women-reservation flags but differs on caste labels for wards 16, 59, 69, 98,
  and 161. The pre-election notification takes priority for those caste labels.
- **2015 outcomes:** all 198 winner titles on all 19 pages of the August 29
  gazette were visually reviewed and compared with the complete OpenCity
  election return's explicit Gender field. Shri maps to 0, Shrimati and Kumari
  to 1, and Dr. to unknown. The title transcription retains the lexical
  honorific without trailing punctuation. It does not infer sex from names,
  seat reservations, addresses, or aggregate counts.
- **Unresolved outcomes:** ward 112 prints Shrimati but the OpenCity field is M;
  ward 197 prints Shri but the OpenCity field is F. Both reconciled outcomes
  remain null. Ward 197 is reserved in 2015 and is outside the persistence
  sample. The individual source values remain in the panel and in
  `../../manual/urban_expansion/bbmp_winner_sex_conflicts.csv`.
- **Ward 132:** the gazette prints Dr. S. Raju. Its title-only outcome is null;
  the reconciled outcome uses the explicit OpenCity M. The retained 2017–18
  ward budget, physical page 263, independently prints Shri Dr S Raju for
  the same ward, Attiguppe. That selected same-person corroboration does not
  transfer the later council roster wholesale to the earlier election.

The primary 2010 gazette prints 66 women-reservation flags, compared with 68 in
the secondary paired roster. Wards 5 and 189 account for the difference. The
first review mistakenly counted a women flag in ward 189; the second review
corrected it to the printed BC-B category without women. Ward 189 is reserved
in 2015, so this correction leaves the 101-ward comparison frame unchanged.
The 2015 notification prints 97 women-reserved wards, versus 98 in the secondary
roster; ward 4 accounts for that difference. The original readings and
secondary readings remain separate. Excluding eligible wards with conflicting
women-assignment sources (4 and 5) is a useful source sensitivity check.

## Geography and interpretation

The 2015 implementing notification's physical page 2, paragraph 3, refers to
UDD 59 MLR 2009, dated July 15, 2009. The retained 2009 notification specifies
198 single-member wards and supplies boundary descriptions. This documentary
link, rather than equal ward counts alone, supports linking ward identifiers.

The files establish reservation histories and outcomes, not a lottery protocol.
The [March 30, 2015 High Court judgment, paragraphs 22(b) and 53](https://indiankanoon.org/doc/148532327/?type=print)
recounts the December 2009 order to redo reservation using population data while
preserving wards, and directs the 2015 election on existing boundaries.
Caste assignment therefore cannot be treated as unrestricted random allocation.
The acquired sources do not establish how women reservations were randomized
within caste categories in 2010. Caste-adjusted comparisons and restrictions
remain conditional comparisons; adjustment alone does not establish randomization.
The comparison group includes seats previously won by women without a quota.
The exposure is assignment to reservation, not exposure to a woman leader.

## Join and missing-value contract

The left universe is the 198 reviewed 2015 winner-gazette ward rows. Join both
reservation years, the complete secondary winner return, and the secondary
paired reservation roster by their ward identifier, expecting one-to-one
cardinality and all 198 matches. The builder checks uniqueness and the exact
ward universe before creating keyed dictionaries. It rejects duplicate or
missing wards and altered primary-source bytes; no fuzzy name linkage occurs.
It keeps the two unresolved outcome rows and all current reserved wards.
Use `is_eligible` for the 2015 nonquota sample and keep missing outcomes when
calculating bounds. `winner_woman_from_honorific_2015` is an unadjudicated
source measurement; `winner_woman_2015` is the reconciled analysis outcome.

## Reproduction and checks

From the repository root:

```sh
python -m local_elections.states.karnataka.urban_panel
python -m pytest tests/test_karnataka_urban_panel.py
```

The builder consumes human-reviewed CSV transcriptions under
`data/karnataka/manual/urban_expansion/`; the scans remain authoritative.
Nine affected parser tests pass, covering duplicate keys, changed source bytes,
source conflict handling, denominator preservation, assignment priority, and
nullable Parquet round trips. Ruff lint and formatting checks pass. No effect
estimation or pooled release replacement is performed by this builder.
