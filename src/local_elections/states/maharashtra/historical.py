"""Typed Mumbai research handoffs; no joins across unverified ward boundaries."""

import csv
import hashlib
import json
import re
from pathlib import Path

import pandas as pd

from local_elections.states.maharashtra import parse

BHAVNANI_DIR = parse.DATA / "raw/mumbai/bhavnani_2009"
BHAVNANI = BHAVNANI_DIR / "Bhavnani APSR 2009 replication data.dta"
OUT = parse.DATA / "release/mumbai"
KEY = ["body", "year", "ward_no"]


DESCRIPTIONS = {
    "body": (
        "Municipal corporation name; no cross-election geographic identity implied."
    ),
    "year": "Outcome election year.",
    "prior_year": "Prior reservation election year.",
    "ward_no": (
        "Ward identifier in the outcome election geography; not a longitudinal ID."
    ),
    "reserved_woman": (
        "Outcome office reserved for women, independently of winner sex; 1 yes, 0 no."
    ),
    "reserved_raw": (
        "Unmodified source reservation code or phrase; numeric Stata value "
        "rendered as text."
    ),
    "prior_reserved_woman": (
        "Author controltreat within the selected open-office comparison; "
        "other rows null."
    ),
    "controltreat_raw": (
        "Original numeric Stata treatment classification including missing values."
    ),
    "winner_woman": (
        "Independently recorded winner sex: 1 female, 0 male, null "
        "unavailable or unlinked."
    ),
    "winner_woman_raw": (
        "Adopted source sex value; no imputation from reservation or names."
    ),
    "groups_raw": (
        "Original groups variable for article Figure 1; source empty strings preserved."
    ),
    "is_eligible": (
        "Nonmissing author controltreat; selected open-office comparison only."
    ),
    "source_path": "Repository-relative original source file.",
    "reserved_basis": "Source variable supplying outcome reservation.",
    "prior_reserved_basis": (
        "Source and sample restriction supplying prior reservation."
    ),
    "winner_woman_basis": (
        "Source of recorded sex, separate from identity-matching method."
    ),
    "geographic_basis": (
        "Author's sample restriction; not independent validation of a general "
        "ward bridge."
    ),
    "exclusion_reason": (
        "Empty if eligible; otherwise current women reservation or "
        "unclassified treatment."
    ),
    "winner": (
        "Winner name retained from existing election-result parser; blank "
        "names become null."
    ),
    "winner_basis": "Existing result parser's winner identification method.",
    "winner_source_path": "Repository-relative election winner source.",
    "profile_year": (
        "Later observation year of the research profile; not election year."
    ),
    "profile_name_raw": "Unmodified name in the research profile.",
    "profile_woman_raw": (
        "Unmodified sex in the research profile, including unlinked values "
        "and empty strings."
    ),
    "profile_source_path": "Repository-relative research profile source.",
    "identity_match": (
        "Exact multiset of ASCII name tokens matches within the same ward; "
        "nonempty names required."
    ),
    "identity_match_method": (
        "Deterministic identity rule, not sex inference from a name."
    ),
    "reserved_caste": (
        "Outcome reservation caste: NONE, SC, ST, BC; BC standardizes OBC."
    ),
    "reserved_source_path": (
        "Repository-relative reservation source; ward1722012 uses official correction."
    ),
}


def verify_bhavnani_sources():
    receipts = json.loads((BHAVNANI_DIR / "receipt.json").read_text())
    for receipt in receipts:
        path = BHAVNANI_DIR / receipt["file"]
        if hashlib.sha256(path.read_bytes()).hexdigest() != receipt["sha256"]:
            raise ValueError(f"Bhavnani source changed: {path.name}")
    return receipts


def bhavnani_comparison():
    """Keep every 2002 ward; missing treatment classification stays missing."""
    verify_bhavnani_sources()
    raw = pd.read_stata(BHAVNANI, convert_categoricals=False)
    frame = pd.DataFrame(
        {
            "body": parse.BODY,
            "year": 2002,
            "prior_year": 1997,
            "ward_no": raw.wardno02.astype("string"),
            "reserved_woman": raw.reservedforwomen.astype("Int8"),
            "reserved_raw": raw.reservedforwomen.astype("string"),
            "prior_reserved_woman": raw.controltreat.astype("Int8"),
            "controltreat_raw": raw.controltreat.astype("Float64"),
            "winner_woman": raw.genderofwinner.astype("Int8"),
            "winner_woman_raw": raw.genderofwinner.astype("string"),
            "groups_raw": raw.groups,
            "is_eligible": raw.controltreat.notna(),
            "source_path": str(BHAVNANI.relative_to(parse.ROOT)),
            "reserved_basis": "replication_reservedforwomen",
            "prior_reserved_basis": "replication_controltreat_selected_open_sample",
            "winner_woman_basis": "replication_genderofwinner",
            "geographic_basis": (
                "author_selected_largely_unchanged_wards_article_p26_note8"
            ),
        }
    )
    frame["exclusion_reason"] = ""
    frame.loc[~frame.is_eligible, "exclusion_reason"] = "treatment_unclassified"
    frame.loc[~frame.is_eligible & frame.reserved_woman.eq(1), "exclusion_reason"] = (
        "outcome_office_reserved_for_women"
    )
    return typed(frame)


def name_tokens(name):
    return tuple(sorted(re.findall(r"[a-z]+", name.lower())))


def recorded_winner_sex():
    """Link later research profiles only on exact name tokens within each ward.

    Profiles are observed in 2013 and 2018, not on election day. Both names
    and profile sex remain visible even when the identity check fails.
    """
    deposit = parse.read_tsv(parse.DEPOSIT)
    rows = []
    for year, wave_year, winners in (
        (2012, 2013, parse.rows_2012()),
        (2017, 2018, parse.rows_2017(deposit)),
    ):
        wave_rows = [r for r in deposit if parse.clean(r["year"]) == str(wave_year)]
        if len(wave_rows) != 227 or len({r["ward"] for r in wave_rows}) != 227:
            raise ValueError("Research profile wave does not have 227 unique wards")
        profiles = parse.deposit_wave(deposit, str(wave_year))
        for winner in winners:
            profile = profiles[winner["ward_no"]]
            tokens = name_tokens(winner["winner"])
            linked = bool(tokens) and tokens == name_tokens(profile["name"])
            sex = profile["sex"]
            if sex not in ("", "Male", "Female"):
                raise ValueError(f"Unrecognized recorded sex: {sex}")
            adopted = linked and bool(sex)
            rows.append(
                {
                    "body": parse.BODY,
                    "year": year,
                    "ward_no": winner["ward_no"],
                    "winner": winner["winner"] or None,
                    "winner_basis": winner["winner_basis"] or None,
                    "winner_source_path": winner.get("result_source_path")
                    or winner["source_path"],
                    "profile_year": wave_year,
                    "profile_name_raw": profile["name"],
                    "profile_woman_raw": sex,
                    "profile_source_path": parse.DEPOSIT,
                    "identity_match": linked,
                    "identity_match_method": "exact_sorted_ascii_name_tokens_same_ward",
                    "winner_woman": int(sex == "Female") if adopted else None,
                    "winner_woman_raw": sex if adopted else None,
                    "winner_woman_basis": "independently_recorded_research_profile_sex"
                    if adopted
                    else None,
                    "reserved_woman": int(winner["woman_reserved"]),
                    "reserved_caste": winner["caste_reservation"],
                    "reserved_raw": winner["reservation_raw"],
                    "reserved_source_path": winner["source_path"],
                }
            )
    return typed(pd.DataFrame(rows))


def typed(frame):
    ints = {"year", "prior_year", "profile_year"}
    indicators = {"winner_woman", "reserved_woman", "prior_reserved_woman"}
    for col in frame:
        if col in ints:
            frame[col] = frame[col].astype("int64")
        elif col in indicators:
            frame[col] = frame[col].astype("Int8")
        elif col in {"is_eligible", "identity_match"}:
            frame[col] = frame[col].astype("bool")
        elif col != "controltreat_raw":
            frame[col] = frame[col].astype("string")
    validate(frame)
    return frame


def validate(frame):
    if frame[KEY].isna().any().any() or frame.duplicated(KEY).any():
        raise ValueError("Incomplete or duplicate Mumbai ward keys")
    if frame.ward_no.str.fullmatch(r"[1-9][0-9]*").ne(True).any():
        raise ValueError("Invalid ward identifier")
    for col in ("winner_woman", "reserved_woman", "prior_reserved_woman"):
        if col in frame and (
            str(frame[col].dtype) != "Int8"
            or not frame[col].dropna().isin([0, 1]).all()
        ):
            raise ValueError(f"Invalid binary indicator: {col}")
    if "is_eligible" in frame:
        expected = frame.prior_reserved_woman.notna() & frame.reserved_woman.eq(0)
        if not frame.is_eligible.equals(expected.astype(bool)):
            raise ValueError(
                "Comparison eligibility differs from classified open sample"
            )
    if (
        "identity_match" in frame
        and frame.loc[~frame.identity_match, "winner_woman"].notna().any()
    ):
        raise ValueError("Unmatched profile supplied winner sex")


def build(out=OUT):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    tables = {
        "bhavnani_comparison_1997_2002.parquet": bhavnani_comparison(),
        "winner_sex_source_audit_2012_2017.parquet": recorded_winner_sex(),
    }
    manifest = {}
    sources = set()
    dictionary = []
    for filename, frame in tables.items():
        for column in frame:
            if column.endswith("source_path"):
                sources.update(frame[column].dropna().unique())
            dictionary.append(
                {
                    "file": filename,
                    "field": column,
                    "dtype": str(frame[column].dtype),
                    "description": DESCRIPTIONS[column],
                    "missing": (
                        "Parquet null; raw source empty strings preserved where present"
                    ),
                }
            )
        path = out / filename
        frame.to_parquet(path, index=False)
        restored = pd.read_parquet(path)
        validate(restored)
        pd.testing.assert_frame_equal(frame, restored)
        manifest[filename] = {
            "rows": len(frame),
            "primary_key": KEY,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "columns": [
                {
                    "name": c,
                    "dtype": str(frame[c].dtype),
                    "nullable": c not in KEY
                    and c
                    not in {
                        "year",
                        "prior_year",
                        "profile_year",
                        "is_eligible",
                        "identity_match",
                    },
                    "missing_count": int(frame[c].isna().sum()),
                }
                for c in frame
            ],
        }
    (out / "historical_schema.json").write_text(json.dumps(manifest, indent=2) + "\n")
    with (out / "historical_dictionary.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(dictionary[0]))
        writer.writeheader()
        writer.writerows(dictionary)
    source_hashes = {
        path: hashlib.sha256((parse.ROOT / path).read_bytes()).hexdigest()
        for path in sorted(sources)
    }
    (out / "historical_sources.json").write_text(
        json.dumps(source_hashes, indent=2) + "\n"
    )
    return tables


def verify_release(out=OUT):
    """Check held outputs and inputs without refreshing their checksums."""
    out = Path(out)
    schema = json.loads((out / "historical_schema.json").read_text())
    expected = {
        "bhavnani_comparison_1997_2002.parquet",
        "winner_sex_source_audit_2012_2017.parquet",
    }
    if set(schema) != expected:
        raise ValueError("Historical release inventory changed")
    for name, contract in schema.items():
        path = out / name
        if hashlib.sha256(path.read_bytes()).hexdigest() != contract["sha256"]:
            raise ValueError(f"Historical output checksum mismatch: {name}")
        frame = pd.read_parquet(path)
        validate(frame)
        if len(frame) != contract["rows"] or contract["primary_key"] != KEY:
            raise ValueError("Historical row/key contract changed")
        columns = [(c["name"], c["dtype"]) for c in contract["columns"]]
        if columns != [(c, str(frame[c].dtype)) for c in frame]:
            raise ValueError("Historical column schema mismatch")
        for column in contract["columns"]:
            if not column["nullable"] and frame[column["name"]].isna().any():
                raise ValueError("Null in a required historical column")
    sources = json.loads((out / "historical_sources.json").read_text())
    for path, expected_hash in sources.items():
        if (
            hashlib.sha256((parse.ROOT / path).read_bytes()).hexdigest()
            != expected_hash
        ):
            raise ValueError(f"Historical source checksum mismatch: {path}")
    verify_bhavnani_sources()
    return True


if __name__ == "__main__":
    for name, frame in build().items():
        print(f"{name}: {len(frame)} rows")
