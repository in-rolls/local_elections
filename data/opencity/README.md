# OpenCity municipal election files

Municipal election results republished by [OpenCity](https://data.opencity.in/), downloaded on
2026-10-18 through its CKAN API. `manifest.csv` records each file's dataset, resource, URL and
SHA-256. The candidate files in Lok Dhaba's layout (`State_Name`, `Ward_No`, `Position`, ...) credit
[Lok Dhaba](https://lokdhaba.ashoka.edu.in/) (TCPD) as their source. The Delhi 2022 file was already
held at `data/delhi/qualification_audit/sources/opencity2022.csv` and is not copied again.

| City | Election | Coverage | Reservation | Sex |
| --- | --- | --- | --- | --- |
| Kolkata | 2010, 2015 | every candidate and their votes | yes | no; see below |
| Hyderabad | 2020 | every candidate and their votes | yes, including BC | no |
| Chennai | 2022 | every candidate | winners' rows only | winners' rows only |
| Bengaluru | 2015 | winner and runner-up; the 2010 councillor | women's seats | winners |
| Mumbai | 2017; 2026 | 2017 every candidate; 2026 winners and the gazette | no | no |
| Pune | 2017; 2026 | 2017 every candidate; 2026 winners and the gazette | 2026 only | no |

Kolkata kept its ward map from 2010 to 2015 for wards 1-141 (wards 142-144 were added): ward
electorates correlate at 0.96 between the two elections by ward number, against 0.55 with the
neighbouring number. Councillors do move between wards, usually when their own ward's category
changes.

`kolkata_winner_sex.csv` gives each Kolkata winner's `winner_female_probability_from_name`,
inferred from the name alone, never recorded: the tool is
`uv run --with naampy python -m local_elections.tools.kolkata_winner_sex`. Values are 1 or 0,
from naampy's first-name score, surname markers or a hand review, and
`winner_female_probability_method` says which. Names that serve either sex are blank. A
women's-seat winner is a woman by law, but that comes from `ward_reservation`, not from this
column; an analysis applies it.

Known defects in the Delhi 2022 file: in four wards the candidates' votes do not sum to the valid
votes. Ward 41 prints 3,070 valid votes for 30,704 cast; in ward 157 an independent repeats the
AAP candidate's 8,683 votes; wards 27 and 212 are off by 8 and 1. They have not been checked
against the commission's ward result sheets.
