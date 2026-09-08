# Independent controls: Tamil Nadu 2011 village-president schedule

All **151 table pages (PDF3–153; table footer1–151)** were counted from native text. Expected output: **12,524 printed GP row occurrences,385 union sections,31 district sections**. This audits the contents of the supplied schedule; it does not certify external administrative completeness or every name spelling.

Source SHA-256: `340e18bc66c484a97c9ea7634f3ba6aa12ab715f2b73745c1d96f1b25bcf3ffd`.

Reproduce from repository root:

```sh
.venv/bin/python data/source_search/early_heads/tn_review/count_2011_tables.py
```

The script checks the source hash, splits each page by its table layout, retains raw side text, reconciles five visually verified split-line records, and includes the one genuinely blank category. `pages.csv` supplies151 per-page counts; `union_counts.csv` and `district_counts.csv` provide group controls; `rows.csv` preserves every enumerated source row's page,side,serial,name and raw category. These are independent audit readings, not pooled analysis records. Diagnostic line numbers refer to repaired side text; the raw text remains in `page-N-side.txt`.

| Canonical control category | Rows |
|---|---:|
| General |6150|
| General women |3090|
| SC general |1967|
| SC women |1165|
| ST general |113|
| ST women |38|
| Unknown: printed blank |1|

The six substantive categories plus blank exhaust all12,524 rows. Women-reserved rows total4293; caste-reserved rows3283; their overlap1203. Exact punctuation/case vocabulary is retained in `summary.json`; the control normalization removes punctuation/spacing, maps the printed typo **Genaral** to General and singular **Woman** to women. Raw spellings remain untouched. These are reservation axes, not elected-person caste or sex.

**Source anomalies requiring explicit handling:**

- PDF15 left, RamakrishnarajuPet union serial14 **Ramakrishnarajupet** has a visually blank category. Preserve unknown; no user guess is needed. An authoritative corrected source would be needed to resolve its actual reservation.
- PDF38 left: Kaveripakkam **Minnal** prints23 where sequential position is22; **Palayapalayam** next also prints23. Both rows are real; do not deduplicate on serial.
- PDF151 left: Ottapidaram **Kodiayankulam** prints33 at position49; **Kollambarambu** prints34 at position51. The original33/34 entries occur earlier in the same union. Preserve printed values and distinguish row occurrences.
- PDF143: **ALANKULAM** left1–21 and **ALANGULAM ... Contd.** right22–28 are one continued section, not two unions. PDF15 likewise uses **RamakrishnarajuPet** / **Ramakrishnaraju Pet** across the two sides. PDF6 prints **THIRUPORUR .PANCHAYAT UNION**.
- PDF79 is a single full-width Nilgiris table with35 rows (union subsections13+6+5+11). PDF77 has a misleading long vertical rule at the right serial/name boundary; the correct central divider is x331.6 PDFpoints.
- Five displaced text baselines were visually reconciled: PDF99 Okkarai5; PDF100 Thirumangalam11 and Athikudi16; PDF127 Thavalaikulam30; PDF128 Pillaiyarkulam2. Literal split/repair strings are in the reproducer.
- Printed category typos/variants were visually confirmed on PDF26 (SC Woman, Genaral Women), PDF27 (Genaral), and PDF125 (General(Woman)). They are not OCR conjectures.

The31 district boundaries were read in native text;14 diagnostic pages were rendered and visually inspected:6,15,26,27,38,77,79,99,100,125,127,128,143,151. Earlier scope review also visually inspected3and153. `visual_findings.json` pins each diagnostic finding to its source and rendered-image hash. None of this claims a12,524-name visual transcription. There are no repeated names within a union after casefold and whitespace normalization; this is a duplicate-screen result, not an identity crosswalk.

Independence disclosure: initial native count/layout diagnostics preceded exposure to the root parser's12,524 count. Root then supplied its count and three serial anomalies; these were independently confirmed against the rendered source. No root parser output rows were read. Matching totals therefore complement, rather than replace, the page/category/union controls and explicit source anomaly evidence.

| Printed district heading | Union sections | GP rows | PDF pages |
|---|---:|---:|---|
|Kancheepuram District|13|633|3–9|
|TIRUVALLUR DISTRICT|14|526|10–15|
|CUDDALORE DISTRICT|13|683|16–23|
|VILUPPURAM DISTRICT|22|1099|24–33|
|VELLORE DISTRICT|20|743|34–42|
|TIRUAVANNAMALAI DISTRICT|18|860|43–53|
|SALEM DISTRICT|20|385|54–58|
|NAMAKKAL DISTRICT|15|322|59–62|
|DHARMAPURI DISTRICT|8|251|63–66|
|KRISHNAGIRI DISTRICT|10|333|67–70|
|ERODE DISTRICT|14|225|71–72|
|COIMBATORE DISTRICT|12|228|73–75|
|TIRUPUR DISTRICT|13|265|76–78|
|NILGIRIS DISTRICT|4|35|79–79|
|THANJAVUR DISTRICT|14|589|80–85|
|NAGAPATTINAM DISTRICT|11|434|86–89|
|TIRUVARUR DISTRICT|10|430|90–94|
|TIRUCHIRAPALLI DISTRICT|14|404|95–101|
|KARUR DISTRICT|8|157|102–103|
|PERAMBALUR DISTRICT|4|121|104–105|
|ARIYALUR DISTRICT|6|201|106–108|
|PUDUKKOTTAI DISTRICT|13|497|109–113|
|MADURAI DISTRICT|13|420|114–118|
|Theni District|8|130|119–120|
|DINDIGUL DISTRICT|14|306|121–124|
|RAMANATHAPURAM DISTRICT|11|429|125–129|
|VIRUDHUNAGAR DISTRICT|11|450|130–135|
|SIVAGANGAI DISTRICT|12|445|136–140|
|Tirunelveli District|19|425|141–146|
|THOOTHUKUDI DISTRICT|12|403|147–151|
|KANNIYAKUMARI DISTRICT|9|95|152–153|

Validation: source SHA guard, all151 page counts, group totals, three serial anomalies and one blank-category control pass. The reproducer passes Ruff formatting and lint checks. Originals and root parser files remain unchanged.
