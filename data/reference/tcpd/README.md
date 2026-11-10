# TCPD–CASI urban local elections

The complete public [Urban Local Body dataset](https://github.com/tcpd/Urban_Local_Body), version 1.1, is retained here at commit `96bca6692413ad57464df8bbe8b4a873a825ab31`. The original CSV, codebook and upstream README are preserved byte for byte. [manifest.csv](manifest.csv) records pinned URLs, Git blob identifiers, SHA-256 hashes, sizes and collection times. The codebook and source CSV include Delhi; the upstream README's eight-state description is outdated.

The source covers Bihar, Delhi, Kerala, Madhya Pradesh, Maharashtra, Rajasthan, Telangana, Uttar Pradesh and West Bengal. These are municipal ward-election records, including candidates and NOTA entries. Municipal corporation, council and nagar panchayat labels identify the body, not a mayoral or president-election outcome. Multiple seats within a ward and by-elections must remain distinct. The source field `Seat` is consequential in Maharashtra, and `Poll` distinguishes some repeated polls. Body and ward labels do not establish stable boundaries across years.

This is a cross-state reference source, like the adjacent OpenCity collection. It is not appended to the pooled master or to existing state releases: overlapping election records need source reconciliation first. The paper repositories should read these files directly rather than retain additional copies. No raw rows, source headers (including the trailing space in `Affidavit `), blank values or exact duplicate rows have been changed.

## Coverage and limitations

[coverage.csv](coverage.csv) reports source rows, named candidates, NOTA rows, recorded gender and reservation, first-place rows, and exact duplicate rows beyond the first, by state, year and body type. Gender and reservation counts exclude NOTA. First-place counts use the supplied `Position` field; they are not independently verified election winners. Blank years remain a separate group. [profile.json](profile.json) records the complete source-column list, states, missing years, duplicates, NOTA entries and source hash. The codebook supplies the variable definitions and state-specific exceptions.

Coverage is uneven. Bihar, Delhi, Kerala and UP each provide one election year in this version. Kerala, Maharashtra, Telangana and West Bengal have no recorded candidate gender; Bihar, Kerala, Madhya Pradesh and Maharashtra have no recorded ward reservation. Rajasthan contains records without a year. No missing gender or reservation is inferred from names, categories, winners or neighboring records. More municipalities in the file therefore do not automatically yield more usable reservation-history comparisons.

Regenerate the inventory and run its checks from the repository root:

```sh
uv run python -m local_elections.tools.tcpd_ulb_coverage
uv run pytest tests/test_tcpd_ulb_coverage.py -q
```

The inventory verifies every retained source hash before reading the CSV. It preserves NOTA and repeated records when counting source rows, and distinguishes missing gender from a recorded man or woman. A sequential record in the original CSV, together with its pinned source hash, locates an observation; no globally unique person or longitudinal ward identifier is asserted.

## Attribution

Data: *TCPD–CASI Urban Local Body Dataset (TCPD–CASI–ULB), 2008–2022*, Trivedi Centre for Political Data, Ashoka University, and Center for the Advanced Study of India, University of Pennsylvania.

Codebook: Neelesh Agrawal, Adam Auerbach, Mohammed Zahir Ali, Srishti Gupta, Mohit Kumar, Aditya Sarkar, Tariq Thachil, Gilles Verniers, and S. V. Sai Vikas (2023), *TCPD–CASI Urban Local Body Dataset, 2008–2022 Codebook 1.1*.

The provider permits noncommercial use with attribution and its stated conditions. Retained source material remains subject to [those conditions](UPSTREAM_README.md), rather than this repository's code license.
