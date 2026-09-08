"""
Codebook for Beaman et al. (2012) replication.

Single source of truth for all variable construction, recoding logic,
and expected baseline values for validation.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Housewife occupation strings (for B1_3 free-text coding)
# ---------------------------------------------------------------------------

HOUSEWIFE_STRINGS = {
    "House Wife",
    "Housewife",
    "House Hold Work",
    "Household Work",
    "What In-Laws Want",
    "What In Laws Want",
    "What Husband Wants",
    "What Husband & In-Laws Want",
    "What Parents Want",
    "Parents Know",
    "Parent'S Know",
}

# ---------------------------------------------------------------------------
# Gender attitude items (E_1 to E_10)
# ---------------------------------------------------------------------------

E_SIGNS = {
    "E_1": +1,
    "E_2": -1,
    "E_3": -1,
    "E_4": +1,
    "E_5": -1,
    "E_6": -1,
    "E_7": 0,
    "E_8": 0,
    "E_9": 0,
    "E_10": 0,
}

E_LABELS = {
    "E_1": "Hitting wife never OK",
    "E_2": "Stricter to daughter than son",
    "E_3": "Better to be man than woman",
    "E_4": "Woman president good idea",
    "E_5": "Wife shouldn't contradict husband",
    "E_6": "Preschool child suffers if mom works",
    "E_7": "Rescue women first",
    "E_8": "Cherish/protect women",
    "E_9": "Women superior moral sense",
    "E_10": "Men sacrifice for women",
}

E_ITEMS = {
    "E_1": {
        "label": "Hitting wife never OK",
        "direction": "+1",
        "coding": "5-point Likert, top-2 = agree",
        "interpretation": "Higher = more progressive",
    },
    "E_2": {
        "label": "Stricter to daughter than son",
        "direction": "-1",
        "coding": "5-point Likert, top-2 = agree",
        "interpretation": "Lower = more progressive",
    },
    "E_3": {
        "label": "Better to be man than woman",
        "direction": "-1",
        "coding": "5-point Likert, top-2 = agree",
        "interpretation": "Lower = more progressive",
    },
    "E_4": {
        "label": "Woman president good idea",
        "direction": "+1",
        "coding": "5-point Likert, top-2 = agree",
        "interpretation": "Higher = more progressive",
    },
    "E_5": {
        "label": "Wife shouldn't contradict husband",
        "direction": "-1",
        "coding": "5-point Likert, top-2 = agree",
        "interpretation": "Lower = more progressive",
    },
    "E_6": {
        "label": "Preschool child suffers if mom works",
        "direction": "-1",
        "coding": "5-point Likert, top-2 = agree",
        "interpretation": "Lower = more progressive",
    },
    "E_7": {
        "label": "Rescue women first",
        "direction": "0",
        "coding": "5-point Likert, top-2 = agree",
        "interpretation": "Benevolent sexism (ambiguous)",
    },
    "E_8": {
        "label": "Cherish/protect women",
        "direction": "0",
        "coding": "5-point Likert, top-2 = agree",
        "interpretation": "Benevolent sexism (ambiguous)",
    },
    "E_9": {
        "label": "Women superior moral sense",
        "direction": "0",
        "coding": "5-point Likert, top-2 = agree",
        "interpretation": "Benevolent sexism (ambiguous)",
    },
    "E_10": {
        "label": "Men sacrifice for women",
        "direction": "0",
        "coding": "5-point Likert, top-2 = agree",
        "interpretation": "Benevolent sexism (ambiguous)",
    },
}

# ---------------------------------------------------------------------------
# Adolescent outcomes (Table 2)
# ---------------------------------------------------------------------------

TEEN_OUTCOMES = {
    "no_housewife": {
        "source": "B1_3",
        "type": "binary",
        "coding": "1 if occupation != housewife/in-laws set (free text)",
        "paper_ref": "Table 2, Col 1",
        "baseline_boys": 0.998,
        "baseline_girls": 0.600,
        "note": "Ceiling effect for boys",
    },
    "wish_graduate": {
        "source": "B1_1",
        "type": "binary",
        "coding": "1 if B1_1 == 13 (graduate level)",
        "paper_ref": "Table 2, Col 4",
        "baseline_boys": 0.296,
        "baseline_girls": 0.195,
        "note": "13 = graduate on education scale",
    },
    "marry_after18": {
        "source": "B1_2",
        "type": "binary",
        "coding": "1 if B1_2 >= 19 (age at marriage)",
        "paper_ref": "Table 2, Col 2",
        "baseline_boys": 0.980,
        "baseline_girls": 0.660,
        "note": "Ceiling effect for boys; 99/999 = missing",
    },
    "wish_pradhan": {
        "source": "B1_4",
        "type": "binary",
        "coding": "1 if B1_4 == 1 (yes), 0 if B1_4 == 2 (no)",
        "paper_ref": "Table 2, Col 5",
        "baseline_boys": 0.499,
        "baseline_girls": 0.485,
        "note": "Small baseline gap",
    },
}

OUTCOMES = list(TEEN_OUTCOMES.keys())

# ---------------------------------------------------------------------------
# Adult outcomes (mechanism tests)
# ---------------------------------------------------------------------------

ADULT_OUTCOMES = {
    "approached": {
        "source": "D1_7",
        "type": "binary",
        "coding": "1=yes, 2=no",
        "description": "Approached pradhan in last year",
    },
    "easy_meet": {
        "source": "D1_9",
        "type": "binary",
        "coding": "1=yes, 2=no",
        "description": "Easy to meet pradhan",
    },
    "knows_pradhan": {
        "source": "D1_1a_rem",
        "type": "binary",
        "coding": "1=correct, 2=wrong, 999=don't know",
        "description": "Correctly names current pradhan",
    },
    "knows_prev_pradhan": {
        "source": "D1_1b_rem",
        "type": "binary",
        "coding": "1=correct, 2=wrong, 999=don't know",
        "description": "Correctly names previous pradhan",
    },
    "knows_mla": {
        "source": "D1_1c_rem",
        "type": "binary",
        "coding": "1=correct, 2=wrong, 999=don't know",
        "description": "Correctly names MLA",
    },
    "heard_gs": {
        "source": "D3_1",
        "type": "binary",
        "coding": "1=yes, 2=no",
        "description": "Has heard of gram sabha",
    },
    "spoke_gs": {
        "source": "D3_12",
        "type": "binary",
        "coding": "1=yes, 2=no",
        "description": "Spoke at last gram sabha attended",
    },
    "voted_gp": {
        "source": "D1_3",
        "type": "binary",
        "coding": "1=yes, 2=no",
        "description": "Voted in last GP election",
    },
    "reads_paper": {
        "source": "D1_2",
        "type": "binary",
        "coding": "1=yes, 2=no",
        "description": "Reads newspaper",
    },
    "any_gs_activity": {
        "source": "D3_11_1 to D3_11_6",
        "type": "binary",
        "coding": "1 if any activity = 1",
        "description": "Participated in any gram sabha activity",
    },
}

# ---------------------------------------------------------------------------
# Parent aspiration outcomes (Table 1)
# ---------------------------------------------------------------------------

PARENT_OUTCOMES = {
    "want_daughter_graduate": {
        "source": "A2_1",
        "type": "binary",
        "coding": "1 if A2_1 == 13 (graduate)",
        "description": "Wants daughter to graduate",
        "baseline_boys": 0.318,
        "baseline_girls": 0.176,
    },
    "want_daughter_marry_after18": {
        "source": "A2_3",
        "type": "binary",
        "coding": "1 if A2_3 >= 19",
        "description": "Wants daughter to marry after 18",
        "baseline_boys": 0.992,
        "baseline_girls": 0.756,
    },
    "want_daughter_pradhan": {
        "source": "A2_5",
        "type": "binary",
        "coding": "1=yes, 2=no",
        "description": "Wants daughter to be pradhan someday",
        "baseline_boys": 0.688,
        "baseline_girls": 0.588,
    },
}

# ---------------------------------------------------------------------------
# Educational outcomes (Table 3)
# ---------------------------------------------------------------------------

EDU_OUTCOMES_DICT = {
    "attends_school": {
        "source": "A1_5",
        "type": "binary",
        "coding": "1 if A1_5 == 1",
        "baseline_boys": 0.744,
        "baseline_girls": 0.684,
    },
    "can_read_write": {
        "source": "A1_6",
        "type": "binary",
        "coding": "1 if A1_6 == 1",
        "baseline_boys": 0.947,
        "baseline_girls": 0.908,
    },
    "grade_completed": {
        "source": "A1_7",
        "type": "continuous",
        "coding": "Grade level; 99/999 = missing",
        "baseline_boys": 5.538,
        "baseline_girls": 5.409,
    },
    "time_domestic": {
        "source": "C2_2, C2_3, C2_7, C2_8, C2_9, C2_10",
        "type": "continuous",
        "coding": "Sum of minutes on domestic chores",
        "baseline_boys": 29.298,
        "baseline_girls": 108.231,
    },
}

EDU_OUTCOMES = ["attends_school", "can_read_write", "grade_completed"]

PARENT_OUTCOMES_LIST = list(PARENT_OUTCOMES.keys())

# ---------------------------------------------------------------------------
# Time use activities (Table 3)
# ---------------------------------------------------------------------------

TIME_USE_ACTIVITIES = {
    "C1_1": "Went to school yesterday",
    "C1_3": "Helped to cook",
    "C1_7": "Cleaned home",
    "C1_8": "Cleaned clothes",
    "C1_9": "Cared for kids/elderly",
    "C1_10": "Gathered fuel/firewood",
}

# ---------------------------------------------------------------------------
# Treatment variables
# ---------------------------------------------------------------------------

TREATMENT = {
    "twice_res": {
        "construction": "(res_woman == 1) & (prev_res_woman == 1)",
        "description": "Both cycles reserved for woman",
        "n_gps": 20,
    },
    "once_res": {
        "construction": "(ever_res == 1) & (twice_res == 0)",
        "description": "Exactly one cycle reserved for woman",
        "n_gps": 70,
    },
    "never_res": {
        "construction": "(twice_res == 0) & (once_res == 0)",
        "description": "Neither cycle reserved for woman",
        "n_gps": 72,
    },
}

# ---------------------------------------------------------------------------
# Standard formula
# ---------------------------------------------------------------------------

FORMULA = "{y} ~ Once + Twice + Female + Once:Female + Twice:Female"


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def validate_baselines(
    df, outcomes_dict: dict, gender_col: str = "girl", tol: float = 0.05
) -> dict:
    """
    Check reproduced baselines against paper values.

    Parameters
    ----------
    df : DataFrame
        Data with never_res indicator and gender column
    outcomes_dict : dict
        Dictionary of outcomes with baseline_boys and baseline_girls
    gender_col : str
        Column indicating female (1=girl, 0=boy)
    tol : float
        Tolerance for match (absolute difference)

    Returns
    -------
    dict : {outcome: {"match": bool, "paper": (b, g), "reproduced": (b, g)}}
    """
    nr = df[df["never_res"] == 1]
    results = {}

    for outcome, spec in outcomes_dict.items():
        if "baseline_boys" not in spec or "baseline_girls" not in spec:
            continue

        if outcome not in df.columns:
            results[outcome] = {"match": None, "error": "Column not found"}
            continue

        boys_paper = spec["baseline_boys"]
        girls_paper = spec["baseline_girls"]

        boys_repro = nr[nr[gender_col] == 0][outcome].mean()
        girls_repro = nr[nr[gender_col] == 1][outcome].mean()

        boys_match = abs(boys_repro - boys_paper) < tol
        girls_match = abs(girls_repro - girls_paper) < tol

        results[outcome] = {
            "match": boys_match and girls_match,
            "paper": (boys_paper, girls_paper),
            "reproduced": (boys_repro, girls_repro),
        }

    return results
