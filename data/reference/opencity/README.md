# OpenCity city election tables

Urban candidate and winner lists for six city corporations (Bengaluru BBMP
2015, Chennai GCC 2022, Hyderabad GHMC 2020, Kolkata KMC 2010-2018, Mumbai BMC
2017 and 2026, Pune PMC 2017 and 2026), downloaded from the OpenCity data portal
(data.opencity.in) and kept as they came. [manifest.csv](manifest.csv) gives
each file's dataset, resource URL, sha256, size and retrieval time.

They are reference tables, not a state, and nothing pools them: the master is
rural. The one file made here is `kolkata_winner_sex.csv`, written by
`src/local_elections/tools/kolkata_winner_sex.py`.
