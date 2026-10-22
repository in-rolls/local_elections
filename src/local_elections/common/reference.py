"""Published figures used as denominators, with where each one comes from.

These were scattered across four validators. Keeping them together matters
because they are not all the same kind of number, and the last time that was
treated casually it produced a real error: Haryana's 2022 figure was announced
before polling and counts *seats*, while its 2016 figure was published afterwards
and counts *people elected*. Comparing seat rows against the second made 2016
look like a 102% over-count.

So every entry records its `basis`:

    seats     the number of seats to be filled, announced before the election
    elected   the number of people returned, published after - excludes seats
              left vacant or countermanded, so vacant rows must be dropped
              before comparing

`None` is a real answer. J&K has no reliable published total for its panchayat
seats and its holdings are an ad-hoc subset rather than a corpus, so inventing a
denominator there would be worse than admitting there isn't one.
"""

from local_elections.states.assam import controls_2025 as assam_controls

# (state, year, tier) -> {"total": int|None, "basis": str, "source": str}
PUBLISHED = {
    ("Rajasthan", "2005", "block_member"): {
        "total": 5257,
        "basis": "seats",
        "unit": "seats",
        "source": "Rajasthan SEC, Panchayat General Election 2005: the "
        "reservation controls and the Part-B member-result roster each "
        "account for all 5,257 Panchayat Samiti constituencies.",
    },
    ("Rajasthan", "2010", "block_member"): {
        "total": 5273,
        "basis": "seats",
        "unit": "seats",
        "source": "Rajasthan SEC, Panchayat General Election 2010: the "
        "institution table prints 5,273 Panchayat Samiti constituencies, "
        "and the Part-B member-result roster reproduces all 5,273.",
    },
    ("Rajasthan", "2005", "zp_member"): {
        "total": 1008,
        "basis": "seats",
        "unit": "seats",
        "source": "Rajasthan SEC, Panchayat General Election 2005: the "
        "reservation control and detailed Zila Parishad member-result roster "
        "each account for all 1,008 wards.",
    },
    ("Rajasthan", "2010", "zp_member"): {
        "total": 1013,
        "basis": "seats",
        "unit": "seats",
        "source": "Rajasthan SEC, Panchayat General Election 2010: the "
        "reservation control and detailed Zila Parishad member-result roster "
        "each account for all 1,013 wards.",
    },
    ("Gujarat", "2020", "zp_member"): {
        "total": 532,
        "basis": "seats",
        "unit": "seats",
        "source": "Gujarat SEC 2021 Annual Statistical Report, section 4.3: "
        "the 16 held district-panchayat orders sum to 532 seats.",
    },
    ("Gujarat", "2020", "block_member"): {
        "total": 646,
        "basis": "seats",
        "unit": "seats",
        "source": "Gujarat SEC 2021 Annual Statistical Report, section 4.3, "
        "plus the held Gandhinagar Taluka order: the 29 held orders sum to "
        "646 seats.",
    },
    ("Goa", "2012", "gp_ward"): {
        "total": 186,
        "basis": "seats",
        "unit": "panchayats",
        "source": "Goa SEC: 186 village panchayats went to poll in 2012. The "
        "parsed file reproduces this exactly, which is what gives "
        "confidence in the other two cycles' parsers.",
    },
    ("Jharkhand", "2015", "gp_head"): {
        "total": 4345,
        "basis": "seats",
        "unit": "gram panchayats",
        "source": "Jharkhand SEC, 2015 three-tier panchayat election.",
    },
    ("Jharkhand", "2015", "block_member"): {
        "total": 5423,
        "basis": "seats",
        "unit": "seats",
        "source": "Jharkhand SEC, 2015.",
    },
    ("Jharkhand", "2015", "zp_member"): {
        "total": 545,
        "basis": "seats",
        "unit": "seats",
        "source": "Jharkhand SEC, 2015.",
    },
    ("Jammu & Kashmir", "2010", "gp_ward"): {
        "total": None,
        "basis": "unknown",
        "unit": "panch constituencies",
        "source": "No reliable published total, and the holdings are an ad-hoc "
        "subset of districts rather than a full corpus. Measuring "
        "against a made-up denominator would be worse than not "
        "measuring.",
    },
    ("Jammu & Kashmir", "2016", "gp_head"): {
        "total": None,
        "basis": "unknown",
        "unit": "halqas",
        "source": "As above.",
    },
    ("Jammu & Kashmir", "2016", "gp_ward"): {
        "total": None,
        "basis": "unknown",
        "unit": "panch constituencies",
        "source": "As above.",
    },
    ("Jammu & Kashmir", "2018", "gp_ward"): {
        "total": None,
        "basis": "unknown",
        "unit": "panch constituencies",
        "source": "As above, and these documents list only the reserved wards, "
        "so a completeness figure would not mean what it looks like.",
    },
    # Uttar Pradesh and Uttarakhand: no denominator wired yet. Both states'
    # commissions publish per-cycle totals and neither is reachable in a form
    # that can be cited here without OCRing a scan, which is the same position
    # Bihar is in and is on the worklist for all three.
    ("Uttar Pradesh", "2005", "gp_head"): {
        "total": None,
        "basis": "unknown",
        "unit": "gram panchayats",
        "source": "No published total recovered for this cycle. The three "
        "cycles held here are internally comparable - 51,872, 51,861 "
        "and 49,772 panchayats - which is a statement about the "
        "parse but not about completeness.",
    },
    ("Uttar Pradesh", "2010", "gp_head"): {
        "total": None,
        "basis": "unknown",
        "unit": "gram panchayats",
        "source": "As above.",
    },
    ("Uttar Pradesh", "2021", "gp_head"): {
        "total": None,
        "basis": "unknown",
        "unit": "gram panchayats",
        "source": "As above.",
    },
    # Telangana 2019. The commission notified elections to 12,728 sarpanch
    # posts and 112,242 ward member posts across 12,751 gram panchayats, nearly
    # 4,000 of which had just been created and were polling for the first time.
    # Cited to the reporting of the notification: the commission's own report
    # (tsec.gov.in/pdf/news/G.P.ELECTIONS,2019_REPORT_15.pdf) would not open
    # from here, and that is stated rather than glossed.
    #
    # This is what a denominator is for. The sarpanch file holds 12,018 - 94%,
    # which reads like a near-complete roster. The 30 ward files hold 49,823 of
    # 112,242, which is 44%, and nothing internal to those files says so: they
    # are individually well-formed, they parse cleanly, and every count in them
    # balances.
    ("Telangana", "2019", "gp_head"): {
        "total": 12728,
        "basis": "seats",
        "unit": "seats",
        "source": "Telangana SEC notification for the 2019 gram panchayat "
        "general election: 12,728 sarpanch posts across 12,751 gram "
        "panchayats.",
    },
    ("Telangana", "2019", "gp_ward"): {
        "total": 112242,
        "basis": "seats",
        "unit": "seats",
        "source": "Telangana SEC notification, 2019: 112,242 ward member "
        "posts. The 30 district files held here cover 30 districts "
        "of 33 and 44% of the seats.",
    },
    # Karnataka: no external denominator. The file is a panel of the same 5,855
    # panchayats across five cycles, so counting its own rows would be circular.
    # What it supports instead is stronger than a coverage percentage: it is the
    # only source here carrying per-panchayat Census population, so
    # caste_share_vs_population - reserved seats sitting where the reserved
    # population lives - runs on all five cycles.
    ("Karnataka", "1993", "gp_head"): {
        "total": None,
        "basis": "unknown",
        "unit": "gram panchayats",
        "source": "A panel of 5,855 panchayats. No independent per-cycle total "
        "recovered; the file's Census columns support a stronger "
        "check than a coverage share would be.",
    },
    ("Karnataka", "2000", "gp_head"): {
        "total": None,
        "basis": "unknown",
        "unit": "gram panchayats",
        "source": "As 1993.",
    },
    ("Karnataka", "2002", "gp_head"): {
        "total": None,
        "basis": "unknown",
        "unit": "gram panchayats",
        "source": "As 1993.",
    },
    ("Karnataka", "2005", "gp_head"): {
        "total": None,
        "basis": "unknown",
        "unit": "gram panchayats",
        "source": "As 1993.",
    },
    ("Karnataka", "2007", "gp_head"): {
        "total": None,
        "basis": "unknown",
        "unit": "gram panchayats",
        "source": "As 1993.",
    },
    # Uttarakhand states its own denominator and this repository was throwing
    # it away. Every row carries two columns that are constant within a
    # (year, post, district) group: `घोषित परिणाम`, the number of results
    # declared, and `निर्विरोध निर्वाचित`, how many were unopposed. They are
    # district-level totals printed onto each row, which is why they read as
    # noise until you check whether they vary - they do not.
    #
    # This is the best kind of denominator available anywhere here: stated by
    # the same document the seats were read from, so it needs no outside source
    # and no assumption that a commission's website matches its notification.
    # Against it the parse holds 29,592 of 29,606 seats - 12 of the 15 slices
    # match exactly, and the three that do not are short by 3, 10 and 1.
    ("Uttarakhand", "2008", "block_member"): {
        "total": 2946,
        "basis": "seats",
        "unit": "seats",
        "source": "The notification's own column 'घोषित परिणाम' (results "
        "declared), summed over its 12 districts. "
        "128 of them were elected unopposed.",
    },
    ("Uttarakhand", "2008", "gp_head"): {
        "total": 6378,
        "basis": "seats",
        "unit": "seats",
        "source": "The notification's own column 'घोषित परिणाम' (results "
        "declared), summed over its 12 districts. "
        "852 of them were elected unopposed.",
    },
    ("Uttarakhand", "2008", "zp_member"): {
        "total": 371,
        "basis": "seats",
        "unit": "seats",
        "source": "The notification's own column 'घोषित परिणाम' (results "
        "declared), summed over its 12 districts. "
        "0 of them were elected unopposed.",
    },
    ("Uttarakhand", "2010", "block_member"): {
        "total": 219,
        "basis": "seats",
        "unit": "seats",
        "source": "The notification's own column 'घोषित परिणाम' (results "
        "declared), summed over its 1 districts. "
        "1 of them were elected unopposed.",
    },
    ("Uttarakhand", "2010", "gp_head"): {
        "total": 314,
        "basis": "seats",
        "unit": "seats",
        "source": "The notification's own column 'घोषित परिणाम' (results "
        "declared), summed over its 1 districts. "
        "1 of them were elected unopposed.",
    },
    ("Uttarakhand", "2010", "zp_member"): {
        "total": 42,
        "basis": "seats",
        "unit": "seats",
        "source": "The notification's own column 'घोषित परिणाम' (results "
        "declared), summed over its 1 districts. "
        "0 of them were elected unopposed.",
    },
    ("Uttarakhand", "2014", "block_member"): {
        "total": 2885,
        "basis": "seats",
        "unit": "seats",
        "source": "The notification's own column 'घोषित परिणाम' (results "
        "declared), summed over its 12 districts. "
        "169 of them were elected unopposed.",
    },
    ("Uttarakhand", "2014", "gp_head"): {
        "total": 6621,
        "basis": "seats",
        "unit": "seats",
        "source": "The notification's own column 'घोषित परिणाम' (results "
        "declared), summed over its 12 districts. "
        "1,011 of them were elected unopposed.",
    },
    ("Uttarakhand", "2014", "zp_member"): {
        "total": 386,
        "basis": "seats",
        "unit": "seats",
        "source": "The notification's own column 'घोषित परिणाम' (results "
        "declared), summed over its 12 districts. "
        "3 of them were elected unopposed.",
    },
    ("Uttarakhand", "2015", "block_member"): {
        "total": 221,
        "basis": "seats",
        "unit": "seats",
        "source": "The notification's own column 'घोषित परिणाम' (results "
        "declared), summed over its 1 districts. "
        "0 of them were elected unopposed.",
    },
    ("Uttarakhand", "2015", "gp_head"): {
        "total": 308,
        "basis": "seats",
        "unit": "seats",
        "source": "The notification's own column 'घोषित परिणाम' (results "
        "declared), summed over its 1 districts. "
        "0 of them were elected unopposed.",
    },
    ("Uttarakhand", "2015", "zp_member"): {
        "total": 47,
        "basis": "seats",
        "unit": "seats",
        "source": "The notification's own column 'घोषित परिणाम' (results "
        "declared), summed over its 1 districts. "
        "0 of them were elected unopposed.",
    },
    ("Uttarakhand", "2019", "block_member"): {
        "total": 2674,
        "basis": "seats",
        "unit": "seats",
        "source": "The notification's own column 'घोषित परिणाम' (results "
        "declared), summed over its 12 districts. "
        "300 of them were elected unopposed.",
    },
    ("Uttarakhand", "2019", "gp_head"): {
        "total": 5847,
        "basis": "seats",
        "unit": "seats",
        "source": "The notification's own column 'घोषित परिणाम' (results "
        "declared), summed over its 12 districts. "
        "1,514 of them were elected unopposed.",
    },
    ("Uttarakhand", "2019", "zp_member"): {
        "total": 347,
        "basis": "seats",
        "unit": "seats",
        "source": "The notification's own column 'घोषित परिणाम' (results "
        "declared), summed over its 12 districts. "
        "9 of them were elected unopposed.",
    },
    # Kerala 2020. Body counts rather than seat counts, which is what the
    # State Election Commission publishes and what the reporting of the result
    # repeats: 941 grama panchayats, 152 block panchayats, 14 district
    # panchayats went to poll. A ward roster that does not resolve to those
    # bodies is missing bodies, which is the thing worth catching.
    #
    # 2010 and 2015 are not wired: Kerala reorganised its panchayats between
    # cycles and the counts for those years are not the 2020 ones. Carrying
    # 2020's figure back would manufacture a completeness number.
    ("Kerala", "2020", "gp_ward"): {
        "total": 941,
        "basis": "seats",
        "unit": "bodies",
        "source": "Kerala SEC, 2020 local body general election: 941 grama "
        "panchayats polled.",
    },
    ("Kerala", "2020", "block_member"): {
        "total": 152,
        "basis": "seats",
        "unit": "bodies",
        "source": "Kerala SEC, 2020: 152 block panchayats polled.",
    },
    ("Kerala", "2020", "zp_member"): {
        "total": 14,
        "basis": "seats",
        "unit": "bodies",
        "source": "Kerala SEC, 2020: 14 district panchayats polled.",
    },
    # Bihar's six tiers, 2016. No denominator, and the reason is specific.
    #
    # The State Election Commission does publish per-tier totals, in a 434-page
    # scan with no text layer; OCR'd, its summary table reads "पंचायत आम
    # निर्वाचन, 2021 एक नजर में" - **2021**, not 2016. It gives 8,067 gram
    # panchayats, 533 blocks, 38 districts and 247,658 directly elected seats.
    # Those are the wrong cycle for this data and are recorded here as context
    # rather than as a total, because `coverage_vs_published` would treat a
    # total as authoritative and report a completeness figure against a
    # delimitation these rows were not drawn under.
    #
    # They are still worth having: against 2021's 8,067 panchayats the scrape's
    # 7,997 mukhiya seats are 99.1%, and its 10,837 panchayat samiti seats are
    # 97.7% of 2021's 11,094. The zila parishad tier is the one that does not
    # look like that.
    #
    # Recovering the 2016 totals means finding the 2016 report; that is on the
    # worklist. What is available without it is internal: the mukhiya and the
    # sarpanch are elected over the same set of panchayats, and the ward member
    # and the panch over the same set of wards, so each pair should agree. They
    # differ by 81 and 4,790 - a measurable statement about completeness that
    # needs no outside number at all.
    ("Bihar", "2016", "gp_head"): {
        "total": None,
        "basis": "unknown",
        "unit": "gram panchayats",
        "source": "Bihar SEC's published per-tier totals are for the 2021 "
        "cycle (8,067 gram panchayats), not 2016. No 2016 total "
        "recovered.",
    },
    ("Bihar", "2016", "gp_ward"): {
        "total": None,
        "basis": "unknown",
        "unit": "panchayat wards",
        "source": "As above.",
    },
    ("Bihar", "2016", "kachahari_head"): {
        "total": None,
        "basis": "unknown",
        "unit": "gram kachaharis",
        "source": "As above.",
    },
    ("Bihar", "2016", "kachahari_member"): {
        "total": None,
        "basis": "unknown",
        "unit": "kachahari wards",
        "source": "As above.",
    },
    ("Bihar", "2016", "block_member"): {
        "total": None,
        "basis": "unknown",
        "unit": "seats",
        "source": "As above.",
    },
    ("Bihar", "2016", "zp_member"): {
        "total": None,
        "basis": "unknown",
        "unit": "seats",
        "source": "As above. The scrape is visibly short here in a way the "
        "other five tiers are not: Sheikhpura holds 1 seat and "
        "Nawada 2, against 44 for Patna and 55 for Madhubani.",
    },
    ("Andhra Pradesh", "2020", "gp_head"): {
        "total": None,
        "basis": "per-district",
        "unit": "gram panchayats",
        "source": "Each gazette states its own district total in its FORMAT-I "
        "abstract, which is a better denominator than a state figure "
        "because only 6 of 13 districts are held. scripts/ap/"
        "validate.py reads it per district. Anantapur states each "
        "seat twice, in a sarpanch-only proforma and again as the "
        "first column of the ward table; the file holds their union "
        "deduplicated, and the two agree on 98.4% of the seats "
        "stated by both.",
    },
    ("Goa", "2017", "gp_ward"): {
        "total": None,
        "basis": "per-taluka",
        "unit": "wards",
        "source": "Measured against 2012, which is complete, taluka by taluka.",
    },
    ("Goa", "2022", "gp_ward"): {
        "total": None,
        "basis": "per-taluka",
        "unit": "wards",
        "source": "As above.",
    },
}

# How many districts each state-year should cover, for the "partial: N of M"
# note. Jharkhand had 24 districts in 2015; Goa's 12 talukas sit under 2
# districts; AP had 13 districts in 2020; J&K's holdings are a subset by
# construction so it has no target.
# How many panchayats each state has, from the Local Government Directory as
# reproduced in NIRD's Rural Development Statistics 2019-20, section 9:
# https://nirdpr.org.in/nird_docs/RDS/RDS2019-20/data/sec-9.pdf
#
# Extracted rather than typed, because thirty-two hand-copied numbers would
# produce a typo that reads as a data defect:
#
#   pdftotext -layout sec-9.pdf - | awk '/District Panchayats.*Village/,0' \
#     | grep -E "^ *[0-9]+ +[A-Z]"
#
# **This is not a denominator and PUBLISHED is.** A state creates panchayats, so
# a registry snapshot from 2019-20 is an upper bound on a 2005 cycle and says
# nothing about how complete that cycle's parse is: Rajasthan reads 81% of it in
# 2005, 87% in 2015 and 100% in 2020, which is the state growing rather than the
# parser improving. PUBLISHED holds figures contemporaneous with each election
# and is what coverage is measured against.
#
# What this is for is the other direction - noticing that a slice holds more
# panchayats than the state has, or a small fraction of them with nothing saying
# why. Jharkhand's mukhiya count read 102% of its gram panchayats for months and
# nothing objected.
#
# (district panchayats, intermediate panchayats, village panchayats); None where
# the tier does not exist in that state.
REGISTRY_ASOF = "2019-20"
REGISTRY = {
    "Andaman & Nicobar Islands": (2, 7, 70),
    "Andhra Pradesh": (13, 660, 13371),
    "Arunachal Pradesh": (25, 177, 1785),
    "Assam": (26, 191, 2197),
    "Bihar": (38, 534, 8387),
    "Chhattisgarh": (27, 146, 11664),
    "Dadra & Nagar Haveli and Daman & Diu": (3, None, 38),
    "Goa": (2, None, 191),
    "Gujarat": (33, 248, 14308),
    "Haryana": (21, 126, 6197),
    "Himachal Pradesh": (12, 78, 3226),
    "Jammu & Kashmir": (20, 275, 4289),
    "Jharkhand": (24, 263, 4364),
    "Karnataka": (30, 227, 6009),
    "Kerala": (14, 152, 941),
    "Ladakh": (2, 31, 192),
    "Lakshadweep": (1, None, 10),
    "Madhya Pradesh": (51, 313, 22812),
    "Maharashtra": (34, 351, 27881),
    "Manipur": (6, None, 161),
    "Odisha": (30, 314, 6798),
    "Puducherry": (None, 10, 108),
    "Punjab": (22, 150, 13263),
    "Rajasthan": (33, 352, 11316),
    "Sikkim": (4, None, 185),
    "Tamil Nadu": (36, 388, 12525),
    "Telangana": (32, 540, 12771),
    "Tripura": (8, 35, 591),
    "Uttar Pradesh": (75, 824, 58757),
    "Uttarakhand": (13, 95, 7791),
    "West Bengal": (22, 342, 3340),
}

# Which registry column a tier is counted in.
#
# Head tiers only, and that restriction is the whole point: the register counts
# *bodies*, and a body elects exactly one head. A body elects many members, so
# comparing 19,781 gram panchayat wards against 4,364 gram panchayats would read
# as 453% and mean nothing.
REGISTRY_TIER = {"gp_head": 2, "block_head": 1, "zp_head": 0}


# Why a slice holds far fewer bodies than the state has. Without these the
# registry check reports four mysteries; with them it reports four facts.
REGISTRY_SCOPE = {
    ("Assam", "2025"): assam_controls.REGISTRY_SCOPE,
    ("Uttarakhand", "2010"): "Haridwar alone, which polls on its own cycle - "
    "the state's other twelve districts voted in 2008 "
    "and 2014, and this slice is complete for the "
    "district it covers",
    ("Uttarakhand", "2015"): "Haridwar alone, which polls on its own cycle - "
    "the state's other twelve districts voted in 2014 "
    "and 2019, and this slice is complete for the "
    "district it covers",
    ("Andhra Pradesh", "2020"): "6 of 13 districts; sec.ap.gov.in refuses "
    "connections from outside India and the "
    "archive holds no more",
    ("Jammu & Kashmir", "2016"): "an ad-hoc subset of districts rather than a "
    "corpus, which is why no published total is "
    "declared for it either",
    ("Rajasthan", "2021"): "the SEC scrape identifies the January general "
    "election phase and that year's by-election events, not a new statewide "
    "cycle",
    ("Rajasthan", "2022"): "by-election events only, not a new statewide cycle",
}

# Partial blanks that follow the source's table design rather than extraction
# loss. These are narrow slice-and-column declarations so a global blank
# tolerance does not conceal a defect in another state or tier.
DECLARED_PARTIAL_BLANKS = {
    (
        "Assam",
        "2025",
        "gp_ward",
        "ward_name",
    ): "Charaideo numbers wards but does not name their villages; Kamrup "
    "Metropolitan prints a village-name cell for every ward",
}


def declared_partial_blank(state, year, tier, column):
    """Return the source-backed reason a slice column is partly blank."""
    return DECLARED_PARTIAL_BLANKS.get((state, str(year), tier, column))


def registry_scope(state, year):
    """A recorded reason this slice covers less of the state than the register."""
    return REGISTRY_SCOPE.get((state, str(year)))


def registry(state, tier):
    """How many bodies of this tier the state has, or None if unrecorded."""
    at = REGISTRY_TIER.get(tier)
    counts = REGISTRY.get(state)
    return counts[at] if counts and at is not None else None


DISTRICT_COUNT = {
    ("Goa", "2012"): 2,
    ("Goa", "2017"): 2,
    ("Goa", "2022"): 2,
    ("Jharkhand", "2015"): 24,
    ("Andhra Pradesh", "2020"): 13,
}

# Where the women's quota is a floor ("not less than one third", the wording of
# the 73rd Amendment) rather than an exact split. Passing the wrong one turned
# J&K's compliant 48% into a failure.
WOMEN_RULE = {
    ("Goa", "2012"): ("floor", 1 / 3),
    ("Goa", "2017"): ("floor", 1 / 3),
    ("Goa", "2022"): ("floor", 1 / 3),
    ("Jharkhand", "2015"): ("floor", 0.50),
    ("Jammu & Kashmir", "2010"): ("floor", 1 / 3),
    ("Jammu & Kashmir", "2016"): ("floor", 1 / 3),
    ("Jammu & Kashmir", "2018"): (None, None),  # reserved-only listing
    ("Andhra Pradesh", "2020"): ("target", 0.50),
}


# Whether a slice's document lists every seat. A statutory share cannot be
# checked against a subset, and the difference between "this state under-reserves"
# and "this document is a partial listing" is the whole finding.
#
#   all_seats      a full roster
#   reserved_only  only the reserved seats are listed, so the share is a
#                  property of the document (J&K 2018)
#   partial        a real but incomplete roster - Goa's 2017 and 2022 files are
#                  nomination-stage listings covering roughly half the wards
#                  that 2012 covers
LISTING_SCOPE = {
    ("Goa", "2017", "gp_ward"): "partial",
    ("Goa", "2022", "gp_ward"): "partial",
}


# What was actually done to answer a question, beside the answer itself.
#
# DOCUMENT_STAGE below records a conclusion and nothing else, so an absent entry
# means either "nobody has looked" or "somebody looked and could not tell", and
# a present one is an assertion with no visible basis. Both matter: not every
# document has a winner, and the useful distinction is not whether a slice has
# one but whether anyone established why.
#
# Keyed by (state, year, tier, question). `searched` has to be specific enough
# for a reader to judge - a URL and what was queried, not "looked online" -
# because an entry that merely asserts diligence is worse than no entry, it
# looks like evidence.
#
#   settled        the answer is known; a DOCUMENT_STAGE entry states it
#   nothing_found  searched properly and nothing surfaced. Not proof the
#                  document does not exist, so the slice stays undetermined -
#                  but nobody needs to repeat the search
#   inconclusive   partial, and worth resuming; say what was not covered
_KARNATAKA_SEARCH = {
    "on": "2026-08-11",
    "searched": "the Wayback CDX for karsec.gov.in - 828 archived PDFs, whose "
    "earliest election material is the 2015 gram panchayat phase "
    "files and the 2016 taluk/zilla gazettes",
    "found": "nothing for any cycle before 2015; these five predate the "
    "commission's web presence. The documents we do hold are "
    "Karnataka_GP_ReservationHistory.dta, a reservation history "
    "carrying the roster and populations, which names no winner by "
    "construction",
    "outcome": "settled",
}

_JHARKHAND_WARDS = {
    "on": "2026-08-13",
    "searched": "every document held for the thirteen districts without ward "
    "rows, read through its own text layer rather than the OCR "
    "cache, counting the ward tier's own name - and the Wayback "
    "CDX for sec.jharkhand.gov.in",
    "found": "not one of the eleven districts that hold a document has a "
    "single ward-tier mention in it; they are mukhiya and panchayat "
    "samiti notifications and nothing else. Hazaribag and Seraikela "
    "Kharsawan hold no document at all. The archive has six PDFs for "
    "the commission, captured in 2026, none of them a result or a "
    "reservation notification.\n"
    "One document invited a wrong conclusion and is worth naming: "
    "DHANBAD ZP PSS MUKHIYA GPS.pdf says GPS - gram panchayat "
    "sadasya, the ward tier - in its own filename and contains none. "
    "295 panchayat samiti, 256 mukhiya, 29 zila parishad rows, all "
    "already parsed. The commission mislabelled it",
    "outcome": "nothing_found",
}

_WEST_BENGAL_RESULTS = {
    "on": "2026-08-14",
    "searched": "the Wayback CDX for wbsec.gov.in - 5,000 captures, of which "
    "775 are PDFs - then the 123 that archive_sweep classifies as "
    "results, the archived copies of the commission's own result "
    "pages, and the two result files its menu links to",
    "found": "none of it is a seat-level result.\n"
    "The 123 'results' PDFs are candidate affidavits filed with "
    "nomination papers, under /writereaddata/Declarations/"
    "Municipal2015/. They match because the classifier reads the URL "
    "and the directory is called Declarations. Two were opened: a "
    "notarised Rs.20 stamp paper, then PAN and income tax for the "
    "candidate's whole family, pending criminal cases, assets. "
    "Municipal, nomination-stage, and silent on reservation.\n"
    "The result pages - FinalResult_zp_2013.aspx, Detailed_gp.aspx "
    "and the rest - archive as ASP.NET error pages. The crawler "
    "captured the URLs; the results came from a query it never made.\n"
    "The two files the menu links to are district x party seat "
    "counts: Election2003Total-2018.pdf is three pages, "
    "ELECTIONRESULT2008-updated_in_2018.pdf is four, for a state with "
    "tens of thousands of gram panchayat seats.\n"
    "The menu on one of those error pages named what the commission "
    "published - 2013/2008/2003 results for ZP, PS and GP, and "
    "contesting-candidate lists - and following it found the one "
    "endpoint the archive did capture with data in it: "
    "/contesting_candidate/details, 462 captures, GET with query "
    "parameters rather than the POST form the other pages use. 195 "
    "are PANCHAYAT, for 2013 and 2018, filtered by district and "
    "party.\n"
    "They still do not fit. The columns are #, OSN, Party Name, "
    "Candidate Name, Candidate Address, Declaration File - a district "
    "by party list of who stood. No constituency, so nothing joins to "
    "a seat; no reservation, which is what this corpus is; and no "
    "field saying who won - `final_result=1` is the name of a filter, "
    "not a column. The one substantive extra, the candidate's home "
    "address, is the class of data this repository deliberately drops.\n"
    "So the seat-level results exist and the archive does not hold "
    "them. Reaching them means the live site, which is a different "
    "question and was not attempted",
    "outcome": "nothing_found",
}

INVESTIGATED = {
    ("West Bengal", "2018", "zp_member", "results_notification"): _WEST_BENGAL_RESULTS,
    ("Jharkhand", "2015", "gp_ward", "missing_districts"): _JHARKHAND_WARDS,
    ("Karnataka", "1993", "gp_head", "results_notification"): _KARNATAKA_SEARCH,
    ("Karnataka", "2000", "gp_head", "results_notification"): _KARNATAKA_SEARCH,
    ("Karnataka", "2002", "gp_head", "results_notification"): _KARNATAKA_SEARCH,
    ("Karnataka", "2005", "gp_head", "results_notification"): _KARNATAKA_SEARCH,
    ("Karnataka", "2007", "gp_head", "results_notification"): _KARNATAKA_SEARCH,
    # The reservation panel alone carried no 2020 winners. The sibling's SEC
    # scrape does, and the adapter now joins every exact contest key it holds.
    ("Rajasthan", "2020", "gp_head", "results_notification"): {
        "on": "2026-08-29",
        "searched": "local_elections_rajasthan's standardized sarpanch panel "
        "and its Rajasthan SEC candidate and winner scrapes",
        "found": "11,300 calendar-2020 general-election contests join exactly "
        "to candidates and winners; four reservation-roster GPs have no "
        "scraped contest and remain winnerless",
        "outcome": "settled",
    },
}


# States whose remaining gaps are real and are deliberately not being worked on.
# Not "finished" - the rows below say what is still wrong - but "we have looked
# at this and chosen to spend the effort elsewhere", which is a decision worth
# writing down rather than rediscovering.
PARKED = {
    "Uttar Pradesh": {
        "on": "2026-08-11",
        "why": "1,718 rows across five entries, the largest being 1,300 of "
        "2005's gp_head with a caste stated and no gender. Real, and "
        "small against 153,505 UP rows; the state also sits at 85-88% "
        "of the register, so the bigger question there is the ~9,000 "
        "gram panchayats the sibling does not hold at all, which is a "
        "harvest rather than a parse",
    },
}


def parked(state):
    """Why this state's gaps are deliberately not being worked, or None."""
    return PARKED.get(state)


def investigated(state, year, tier, question):
    """What was done to answer this question here, or None if nobody has."""
    return INVESTIGATED.get((state, str(year), tier, question))


# What stage of document a slice came from. This decides whether "no winner
# recorded" is a fact about the document or a gap in our collecting: a pre-poll
# reservation roster names no winner and never will, while for anything else a
# results notification may exist that nobody has looked for. An absent entry is
# an open question, not a default.
#
#   pre_poll   a reservation roster drawn before the election
#   result     a notification published after, naming who won
DOCUMENT_STAGE = {
    ("Assam", "2020", "ulb_ward"): "pre_poll",
    ("Assam", "2020", "ulb_head"): "pre_poll",
    # The 2025 district notifications allocate reservations before the PRI
    # election. They are complete seat rosters, not result notifications.
    ("Assam", "2025", "gp_ward"): "pre_poll",
    ("Assam", "2025", "gp_head"): "pre_poll",
    ("Assam", "2025", "gp_vice_head"): "pre_poll",
    ("Assam", "2025", "block_member"): "pre_poll",
    ("Assam", "2025", "block_head"): "pre_poll",
    ("Assam", "2025", "block_vice_head"): "pre_poll",
    ("Assam", "2025", "zp_member"): "pre_poll",
    ("Goa", "2012", "gp_ward"): "result",
    ("Goa", "2017", "gp_ward"): "pre_poll",
    ("Goa", "2022", "gp_ward"): "pre_poll",
    # These are rotation/reservation orders issued before the February 2021
    # district- and taluka-panchayat election, not result notifications.
    ("Gujarat", "2020", "block_member"): "pre_poll",
    ("Gujarat", "2020", "zp_member"): "pre_poll",
    ("Jharkhand", "2015", "gp_head"): "result",
    ("Jharkhand", "2015", "gp_ward"): "result",
    ("Jharkhand", "2015", "block_member"): "result",
    ("Jharkhand", "2015", "zp_member"): "result",
    ("Andhra Pradesh", "2020", "gp_head"): "pre_poll",
    ("Andhra Pradesh", "2020", "gp_ward"): "pre_poll",
    # J&K's files are reservation *proposals*: they carry SC/ST/OC populations
    # and the reservation being proposed, and no winner column appears in any
    # of the 105 documents. A pre-poll roster names no winner and never will.
    ("Jammu & Kashmir", "2010", "gp_ward"): "pre_poll",
    ("Jammu & Kashmir", "2016", "gp_head"): "pre_poll",
    ("Jammu & Kashmir", "2016", "gp_ward"): "pre_poll",
    ("Jammu & Kashmir", "2018", "gp_ward"): "pre_poll",
    # Karnataka_GP_ReservationHistory.dta is a reservation history: the roster
    # per cycle plus populations, with no winner column in any year. See
    # INVESTIGATED for the search that established no results notification
    # exists for these cycles either - they predate the commission's web
    # presence, whose earliest archived material is 2015.
    ("Karnataka", "1993", "gp_head"): "pre_poll",
    ("Karnataka", "2000", "gp_head"): "pre_poll",
    ("Karnataka", "2002", "gp_head"): "pre_poll",
    ("Karnataka", "2005", "gp_head"): "pre_poll",
    ("Karnataka", "2007", "gp_head"): "pre_poll",
    ("Rajasthan", "2005", "gp_head"): "result",
    ("Rajasthan", "2005", "block_member"): "result",
    ("Rajasthan", "2005", "zp_member"): "result",
    ("Rajasthan", "2010", "gp_head"): "result",
    ("Rajasthan", "2010", "block_member"): "result",
    ("Rajasthan", "2010", "zp_member"): "result",
    ("Rajasthan", "2015", "gp_head"): "result",
    ("Rajasthan", "2020", "gp_head"): "result",
    ("Rajasthan", "2021", "gp_head"): "result",
    ("Rajasthan", "2022", "gp_head"): "result",
    ("Rajasthan", "2020", "gp_ward"): "result",
    ("Rajasthan", "2021", "gp_ward"): "result",
    ("Rajasthan", "2022", "gp_ward"): "result",
}


# Whether the documents that would close a state's coverage can be fetched from
# here at all. Recorded because "nobody has done it" and "nobody here can do it"
# are different things, and a worklist that mixes them is a worklist nobody
# trusts. Verified by request, not assumed: the state SEC domains below refuse
# connections from two independent egresses, which is the network path rather
# than the sites being down.
SOURCE_ACCESS = {
    # Blocked at the state election commission, not everywhere. The Wayback
    # Machine crawled sec.ap.gov.in in 2022 and served six of the thirteen
    # gazettes from anywhere - that is how West Godavari was recovered - and the
    # district collectorate portals answer directly: chittoor.ap.gov.in and
    # kurnool.ap.gov.in both return 200, as does cdn.s3waas.gov.in where they
    # host their PDFs. Those portals publish documents under opaque names across
    # seven years, so finding the 2020 rosters means crawling each district's
    # list rather than fetching a known URL. A project, but not a wall.
    "Andhra Pradesh": (
        "blocked",
        "sec.ap.gov.in refuses connections from "
        "outside India; the archive holds 6 of 13 "
        "and the district portals answer, so the "
        "rest is a crawl rather than an egress",
    ),
    "Jharkhand": ("reachable", ""),
    "Goa": ("reachable", ""),
    "Jammu & Kashmir": ("reachable", ""),
}


def source_access(state):
    return SOURCE_ACCESS.get(state, ("unknown", ""))


def document_stage(state, year, tier):
    return DOCUMENT_STAGE.get((state, year, tier))


def listing_scope(state, year, tier):
    return LISTING_SCOPE.get((state, year, tier), "all_seats")


def published(state, year, tier):
    return PUBLISHED.get((state, year, tier), {})


def districts_expected(state, year):
    return DISTRICT_COUNT.get((state, year))


# Article 243D(3) of the Constitution: "not less than one-third ... of the
# total number of seats to be filled by direct election in every Panchayat
# shall be reserved for women". Every state, every tier, since 1993.
#
# Declared as the default because the alternative was worse. Without it,
# women_share_vs_statute - the strongest external check this corpus has, and
# the only one comparing against a rule nothing here was tuned against -
# skipped 50 of its 63 slices for want of an entry, and a skip reads exactly
# like a pass in a green build.
#
# It is deliberately the floor rather than the stronger rule. Twenty states
# including West Bengal legislate one-half, and several entries above say so,
# but the amending statutes could not be retrieved to cite - and a share taken
# from the data it is meant to test is not a check. A weaker rule that is
# certainly right beats a stronger one that might not be; where a statute is
# confirmed, adding it to WOMEN_RULE tightens the check for that slice.
CONSTITUTIONAL_FLOOR = ("floor", 1 / 3)


def women_rule(state, year):
    return WOMEN_RULE.get((state, year), CONSTITUTIONAL_FLOOR)


# States that rotate reservation between cycles, with the cycle the rotation
# starts from. Declared because it changes what an external check can conclude,
# not as an excuse for one that fails.
#
# `caste_share_vs_population` asks whether SC-reserved seats sit where more SC
# people live. That is a statement about one allocation. Where a state rotates,
# a panchayat reserved once is unavailable next time, so each cycle draws from a
# pool the previous cycles have already taken the highest-share panchayats out
# of, and the correlation must decay by construction.
#
# Karnataka's rotation is close to absolute and was measured before this entry
# was written: of one cycle's ~960 SC-reserved panchayats, between 0.6% and 4.1%
# are SC-reserved again in the next, against 18% by chance. Across the five
# cycles 4,372 panchayats were SC-reserved exactly once and one was reserved
# three times. The check's observed values follow exactly: 25.5% against 16.5%
# in 1993, then 21.7/17.3, 18.0/18.2, 18.5/18.1, 17.2/18.4.
ROTATES = {
    ("Karnataka", "gp_head"): {
        "from": "1993",
        "evidence": "0.6-4.1% of a cycle's SC-reserved panchayats are SC "
        "again in the next, against 18% by chance; 4,372 of 5,322 "
        "were SC-reserved exactly once across five cycles.",
    },
}


def rotates(state, tier):
    return ROTATES.get((state, tier))
