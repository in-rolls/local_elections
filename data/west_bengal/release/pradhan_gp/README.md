# Pradhan-office reservation for every GP

`pradhan_gp.csv` (and `.parquet`) has one row per gram panchayat (GP) and term, for each district
where a final Form 1B order for Pradhan offices is held. Built by `make wb-pradhan-gp`.

| District | Term | GPs | Named in order | Order |
|---|---|---|---|---|
| South 24 Parganas | 2018 | 310 | 233 | No. 6/P&RD/PGE/2018, 06/03/2018 |
| Nadia | 2018 | 185 | 138 | No. 95/PGE'18, 06.03.2018 |
| Purulia | 2018 | 170 | 128 | No. 95(170)/Panch' Elec./Prl', 06/03/2018 |
| Alipurduar | 2018 | 66 | 50 | Form 1B, signed 06/03/2018 |
| Malda | 2013 | 146 | 146 | No. 334/P/PGE'13, 15/03/2013 |
| Nadia | 2013 | 187 | 187 | Memo No. 404/P&RD, 15.03.2013; codes from the election handbook |

The 2013 Nadia handbook prints every GP with its code, and its codes add up to the order's
printed totals. One code (Taldaha Majdia) is blank. The other 186 already exhaust every printed
total, and the order does not name it, so it is coded unreserved (`BLANK_CODES` in
`pradhan_gp.py`). Three GP names occur in two blocks each; the handbook's block-by-block serial
order assigns them (see the overrides).

**The inference.** A Form 1B names the offices it reserves: column 4 for SC/ST/BC, column 5 for
women. A GP it does not name is unreserved on both axes. The GP universe is the MNREGA R3 list for
the same year (`../../reference/mnrega_gp_lists.csv`, from doi:10.7910/DVN/ZHF9WC). In each
district its count equals the total printed in column 2. Malda and the Nadia handbook print every
GP, so nothing is inferred there.

**The checks.** The build fails unless every named office resolves to a distinct GP, and the
parsed counts of offices, SC, ST, BC and women equal the printed totals (`checks.json`). A swap of
two GPs within a block would pass those checks, so `match` records how each printed name compares
with its matched GP.

| Column | Meaning |
|---|---|
| `block`, `gram_panchayat` | MNREGA spelling, the join key for spending data |
| `named_in_order` | the GP appears in the order; false means unreserved on both axes |
| `caste_reservation` | SC, ST, BC or UR |
| `woman_reserved` | the Pradhan office is reserved for a woman |
| `printed` | every reading of the name in the order, separated by `\|` |
| `match` | `exact` (ignoring case, punctuation and spacing), `transliteration`, `scan_misread` (OCR glyphs in the numeral), `fuzzy`, or `not_named` |
| `assigned_by` | `matcher`, or `override` (hand decision, with its reason in `../../reference/pradhan_match_overrides.csv`) |
| `source_file`, `source_page`, `source_row` | where the entry is printed; the files and their original URLs and archive captures are in the `gp_source_search` manifests |

`scan_cells.csv` holds the OCR readings of the two scanned orders (Nadia 2018, Malda 2013), cell
by cell. They are the evidence for those districts.
