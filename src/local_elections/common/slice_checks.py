"""One catalogue of checks, run per state x year x tier.

Each check declares what it **appeals to**, because that is what decides whether
it can catch anything real:

    internal   consistency of our own output with itself. Cheap, and it cannot
               catch a misread category - the file agrees with itself either way.
    declared   our own declarations in dictionary.py, reference.py, canon.py. It
               catches drift from what we said we expected.
    external   a published total, a statutory share, a population, a second
               printing. The only kind that reliably catches silent corruption,
               because every parser bug in this repository produced plausible
               values rather than an error.

`SKIP` is a first-class status and must render differently from `PASS`. That
distinction is not cosmetic: `rows_in_band` silently skipped Andhra Pradesh's
45,478 wards and Jharkhand's 6,174 - the two largest slices here - for as long
as they had no declared band, and a skip that renders as a pass is how nobody
noticed. So a skipped check on a slice over SKIP_FLOOR rows now fails.
"""

import collections
import pathlib

from local_elections.common import canon, dictionary, normalize, reference

FAIL_STATUSES = ("fail",)

PASS, WARN, FAIL, SKIP = "pass", "warn", "fail", "skip"

# Above this many rows, "no rule declared" stops being an acceptable answer.
SKIP_FLOOR = 1000

# Below this share of rows carrying a stated gender, a women's share cannot be
# estimated from the slice at all - see women_share_vs_statute.
STATED_FLOOR = 0.90

CHECKS = []


def check(check_id, appeals_to):
    def register(fn):
        CHECKS.append({"id": check_id, "appeals_to": appeals_to, "fn": fn})
        return fn

    return register


class Slice:
    """One state x year x tier, with the things every check wants."""

    def __init__(self, state, year, tier, rows, root):
        self.state, self.year, self.tier = state, year, tier
        self.rows, self.root = rows, pathlib.Path(root)
        self.n = len(rows)
        self.women = sum(1 for r in rows if str(r.get("woman_reserved")) == "1")
        self.tier_local = sorted({r.get("tier_local", "") for r in rows})
        # the row's own value wins where a source states one; otherwise the
        # declared default for the slice
        self.scope = rows[0].get("listing_scope") or reference.listing_scope(
            state, year, tier
        )

    def share(self, field, value):
        return sum(1 for r in self.rows if r.get(field) == value) / max(self.n, 1)

    def filled(self, column):
        return sum(1 for r in self.rows if (r.get(column) or "").strip())


def result(
    status: str, observed: object = "", expected: object = "", detail: str = ""
) -> dict[str, str]:
    """One check's verdict.

    `observed` and `expected` are typed as object rather than str because
    callers pass counts, shares and bands as often as strings - they are
    stringified here so a check never has to remember to. Without the
    annotation the defaults make them look like str-only, which is 26 of the
    32 things pyright had to say about this package.
    """
    return {
        "status": status,
        "observed": str(observed),
        "expected": str(expected),
        "detail": detail,
    }


# ------------------------------------------------------------------ declared


@check("rows_in_band", "declared")
def rows_in_band(s):
    band = dictionary.ROW_BANDS.get((s.state, s.tier))
    if not band:
        return result(SKIP, s.n, "", "no row band declared for this state and tier")
    low, high = band
    if any((row.get("election_duration") or "").strip() for row in s.rows):
        return result(PASS if s.n <= high else FAIL, s.n, f"<= {high} (event records)")
    if s.scope == "partial":
        return result(PASS if s.n <= high else FAIL, s.n, f"<= {high} (partial)")
    return result(PASS if low <= s.n <= high else FAIL, s.n, f"{low}..{high}")


@check("caste_scheme_respected", "declared")
def caste_scheme_respected(s):
    allowed = canon.allowed_castes(s.state)
    if not allowed:
        return result(SKIP, "", "", f"no caste scheme declared for {s.state}")
    # A blank is not a category outside the scheme, it is the absence of one:
    # 328 Bihar rows read "--select--" and state no reservation at all. Reading
    # blank as a violation would push a state to default them to unreserved,
    # which is the opposite of what this repository wants.
    seen = {
        r.get("caste_reservation")
        for r in s.rows
        if (r.get("caste_reservation") or "").strip()
    }
    unstated = sum(1 for r in s.rows if not (r.get("caste_reservation") or "").strip())
    extra = seen - allowed
    # Kerala reserves no backward-class seat in local bodies, so zero BC rows is
    # the law rather than a parsing failure. Declaring the scheme is what makes
    # that distinguishable from Goa suddenly losing its BC rows.
    return result(
        FAIL if extra else PASS,
        ",".join(sorted(seen)),
        ",".join(sorted(allowed)),
        f"outside the scheme: {sorted(extra)}"
        if extra
        else f"{canon.caste_scheme(s.state)}"
        + (f"; {unstated:,} rows state no category" if unstated else ""),
    )


@check("blank_share_within_tolerance", "declared")
def blank_share_within_tolerance(s):
    """Evaluated per slice, not per file.

    A column that is entirely blank for one tier inside a mixed file disappears
    into the file's average, which is how a wholly missing column can look like
    a tolerable blank rate.
    """
    over = []
    declared = []
    for column in s.rows[0]:
        spec = dictionary.BY_NAME.get(column)
        if not spec or spec.get("max_blank") is None:
            continue
        blank = 1 - s.filled(column) / max(s.n, 1)
        # entirely blank means the column is not in this source at all, which is
        # a fact about the document rather than a defect
        if spec["max_blank"] < blank < 1.0:
            reason = reference.declared_partial_blank(
                s.state,
                s.year,
                s.tier,
                column,
            )
            if reason:
                declared.append(f"{column}: {reason}")
            else:
                over.append(f"{column} {blank:.0%}>{spec['max_blank']:.0%}")
    return result(
        WARN if over else PASS,
        "; ".join(over[:4]),
        "",
        f"{len(over)} column(s) over tolerance"
        + (f"; declared source blanks: {'; '.join(declared)}" if declared else ""),
    )


# ------------------------------------------------------------------ external


@check("coverage_vs_published", "external")
def coverage_vs_published(s):
    spec = reference.published(s.state, s.year, s.tier)
    total = spec.get("total")
    if not total:
        return result(
            SKIP,
            s.n,
            "",
            # not truncated: the reason is the useful part, and a
            # 110-character cut removed it from six of the most
            # informative rows in slice_checks.csv
            spec.get("source", "no published total for this slice"),
        )
    counted = s.rows
    if spec.get("basis") == "elected":
        # an "elected" figure excludes seats nobody holds
        counted = [r for r in counted if str(r.get("vacant", "")) != "1"]
    # Matched on substring, not equality. Jharkhand declares its unit as
    # "gram panchayats" and the test read "panchayats", so it fell through to
    # counting rows: 4,378 mukhiya rows against 4,345 gram panchayats reported
    # as 101% coverage, when the parse names 3,155 distinct panchayats - 73%.
    # A completeness figure above 100% should never have been possible to print
    # without something drawing attention to it.
    if "panchayat" in (spec.get("unit") or "") or spec.get("unit") == "bodies":
        # keyed on the district too: two blocks in different districts share a
        # name often enough that (block, panchayat) merges real bodies, and
        # Kerala leaves `block` empty on every panchayat-ward row
        n = len(
            {(r.get("district"), r.get("block"), canon.unit_name(r)) for r in counted}
        )
    else:
        n = len(counted)
    share = 100.0 * n / total
    return result(
        PASS if share >= 90 else WARN,
        f"{n} ({share:.0f}%)",
        f"{total} {spec.get('unit', 'seats')}",
        spec.get("basis", ""),
    )


@check("women_share_vs_statute", "external")
def women_share_vs_statute(s):
    if s.scope != "all_seats":
        return result(
            SKIP,
            f"{s.women}/{s.n}",
            "",
            f"the document is a {s.scope} listing, so its share is a "
            f"property of the document rather than of the state",
        )
    kind, value = reference.women_rule(s.state, s.year)
    if not kind:
        return result(SKIP, f"{s.women}/{s.n}", "", "no statutory rule declared")

    # Measure only where the source stated a gender. Where a document marks
    # both the women's and the open seats, a code whose marker did not survive
    # the scan is unknown, not male - and woman_reserved is 0 there by default,
    # which drags the share down.
    #
    # But the filter cannot be trusted when much is missing, because the two
    # markers are not lost at equal rates: Prakasam loses (G) about twice as
    # often as (W), so its stated rows read 66% women where the truth is near
    # half. Neither the raw share nor the filtered one estimates it, so below
    # STATED_FLOOR the honest answer is that this slice cannot be measured.
    rows, note = s.rows, ""
    if "gender_stated" in s.rows[0]:
        stated = [r for r in s.rows if r.get("gender_stated") == "1"]
        share_stated = len(stated) / max(s.n, 1)
        if share_stated < STATED_FLOOR:
            return result(
                SKIP,
                f"{s.women / max(s.n, 1):.1%}",
                f"{kind} {value:.0%}",
                f"the source states a gender on only "
                f"{share_stated:.0%} of rows, and the missing markers "
                f"are not missing at random",
            )
        if len(stated) < s.n:
            rows = stated
            note = (
                f"over the {len(stated):,} rows whose gender the source "
                f"states; {s.women / max(s.n, 1):.1%} over all {s.n:,}"
            )
    women = sum(1 for r in rows if str(r.get("woman_reserved")) == "1")
    share = women / max(len(rows), 1)
    # "not less than one third" is the wording of the 73rd Amendment, so a
    # higher share is compliance. Haryana's half is an exact split. Passing the
    # wrong one of these turned J&K's compliant 48% into a failure once.
    ok = share >= value - 0.02 if kind == "floor" else abs(share - value) <= 0.05
    return result(PASS if ok else FAIL, f"{share:.1%}", f"{kind} {value:.0%}", note)


@check("women_share_by_block", "external")
def women_share_by_block(s):
    """A statutory share usually binds per block, not statewide.

    That is what makes it worth running: offsetting errors cannot satisfy a
    per-block check the way they can satisfy a state total, which is how
    Haryana's wrapped-label bug was found.
    """
    kind, value = reference.women_rule(s.state, s.year)
    if kind != "target" or s.scope == "reserved_only":
        return result(SKIP, "", "", "only applies where the share is an exact split")
    grouped = collections.defaultdict(list)
    for row in s.rows:
        grouped[(row.get("district", ""), row.get("block", ""))].append(row)
    off = [
        k
        for k, sub in grouped.items()
        if abs(
            sum(1 for r in sub if str(r.get("woman_reserved")) == "1") / len(sub)
            - value
        )
        > 0.06
    ]
    ok = len(off) <= 0.1 * max(len(grouped), 1)
    return result(
        PASS if ok else WARN,
        f"{len(off)} of {len(grouped)} blocks off",
        f"within 6pp of {value:.0%}",
    )


@check("caste_share_vs_population", "external")
def caste_share_vs_population(s):
    """Where the source prints populations, an SC-reserved seat should sit in a
    place with more SC people. The strongest check available in J&K.
    """
    with_pop = [
        r
        for r in s.rows
        if (r.get("pop_sc") or "").isdigit()
        and (r.get("pop_total") or "").isdigit()
        and int(r["pop_total"]) > 0
    ]
    if len(with_pop) < 50:
        return result(SKIP, len(with_pop), "", "no population columns in this source")

    def mean(rows):
        return sum(int(r["pop_sc"]) / int(r["pop_total"]) for r in rows) / len(rows)

    sc = [r for r in with_pop if r.get("caste_reservation") == "SC"]
    rest = [r for r in with_pop if r.get("caste_reservation") != "SC"]
    if not sc or not rest:
        return result(SKIP, "", "", "no SC-reserved seats with populations")
    holds = mean(sc) > mean(rest)
    # Where a state rotates, a panchayat reserved once is unavailable next
    # time, so each later cycle draws from a pool the earlier ones have already
    # taken the highest-share panchayats out of and the correlation decays by
    # construction. The first cycle is still held to the full standard.
    rotation = reference.rotates(s.state, s.tier)
    if not holds and rotation and s.year != rotation["from"]:
        return result(
            WARN,
            f"SC seats {mean(sc):.1%} vs others {mean(rest):.1%}",
            f"a later cycle of a rotating reservation, from {rotation['from']}",
            rotation["evidence"],
        )
    return result(
        PASS if holds else FAIL,
        f"SC seats {mean(sc):.1%} vs others {mean(rest):.1%}",
        "SC-reserved seats sit where more SC people live",
    )


# ------------------------------------------------------------------ internal


@check("label_agrees", "internal")
def label_agrees(s):
    def expected(row):
        prefix = {"SC": "SC", "ST": "ST", "BC": "BC"}.get(
            row.get("caste_reservation"), ""
        )
        woman = "Woman" if str(row.get("woman_reserved")) == "1" else "Other than Woman"
        return f"{prefix} {woman}".strip()

    # A row that states no category has no label to agree with. Bihar's 328
    # "--select--" rows are blank in all three columns, which is consistent.
    stated = [r for r in s.rows if (r.get("caste_reservation") or "").strip()]
    bad = [r for r in stated if r.get("reservation") != expected(r)]
    return result(
        FAIL if bad else PASS,
        len(bad),
        0,
        "the label is written separately from the two fields it "
        "summarises, so they can disagree",
    )


@check("winner_caste_is_not_the_seats", "internal")
def winner_caste_is_not_the_seats(s):
    """Where a source states both, they must not be the same column twice.

    A reservation is a property of the seat; the winner's category is a property
    of a person. The one way a parser silently destroys that distinction is by
    filling both from the same field, and the result looks perfectly well-formed
    - two populated columns, every count balancing, and the finding that a
    scheduled-caste person can win an unreserved seat quietly impossible.

    Uttar Pradesh 2005 states both and they agree on 19,324 of 51,872 rows.
    Exact agreement on every row would not be a tidy dataset, it would be one
    column copied.
    """
    both = [
        r
        for r in s.rows
        if (r.get("winner_caste") or "").strip()
        and (r.get("caste_reservation") or "").strip()
    ]
    if len(both) < 100:
        return result(
            SKIP, len(both), "", "this source states the seat's reservation only"
        )
    same = sum(
        1
        for r in both
        if normalize.caste_of(r["winner_caste"]) == r["caste_reservation"]
    )
    share = 100.0 * same / len(both)
    return result(
        FAIL if share > 99 else PASS,
        f"{same:,}/{len(both):,} agree ({share:.0f}%)",
        "under 99%",
        "the winner's own category and the seat's reservation are "
        "different facts; identical columns mean one was copied",
    )


@check("alias_family_exclusive", "internal")
def alias_family_exclusive(s):
    """No row may name the panchayat in two columns.

    The whole coalesce into a single master column rests on this, and until now
    it was assumed rather than checked.
    """
    bad = 0
    for row in s.rows:
        try:
            canon.unit_name(row)
        except ValueError:
            bad += 1
    return result(FAIL if bad else PASS, bad, 0, f"one of {canon.UNIT_COLUMNS}")


@check("seat_key_unique", "internal")
def seat_key_unique(s):
    counts = collections.Counter(canon.seat_identity(row) for row in s.rows)
    dup = sum(n for n in counts.values() if n > 1)
    worst = counts.most_common(1)[0] if counts else (None, 0)
    return result(
        WARN if dup else PASS,
        dup,
        0,
        f"largest group {worst[1]} at {worst[0]}" if dup else "",
    )


@check("tier_local_maps_to_one_tier", "internal")
def tier_local_maps_to_one_tier(s):
    bad = [local for local in s.tier_local if canon.tier_of(local, s.state) != s.tier]
    return result(
        FAIL if bad else PASS,
        ",".join(s.tier_local),
        s.tier,
        f"does not map here: {bad}" if bad else "",
    )


@check("reservation_constant_within_seat", "internal")
def reservation_constant_within_seat(s):
    """Every candidate for a seat contests the same seat, so they carry the
    same reservation. Two values under one key means the key is wrong.

    This is what makes a candidate-to-seat collapse safe, and it is the only
    check that can: a wrong key changes the row count by design, so nothing
    downstream can tell a good collapse from a bad one. Run against the sources
    before the collapse was written, it found 9 seats in Uttarakhand.

    Only meaningful on a collapsed slice; elsewhere every row is already a seat
    and the check is trivially true, so it skips rather than claiming a pass it
    has not earned.
    """
    if not s.rows or s.rows[0].get("unit_of_observation") != "seat_from_candidates":
        return result(
            SKIP, "", "", "the source is seat-level, so there is nothing to collapse"
        )
    # A row already flagged `shared_place_name` is one the adapter has said, in
    # so many words, that this key cannot identify: two panchayats in one block
    # printed under one name, told apart only by being reserved differently.
    # Nine of Uttarakhand's gram panchayat seats are like that. Failing them
    # here would be the check re-reporting a limit that has already been
    # recorded, and the pressure would be to merge two real seats to quiet it.
    #
    # A row that states no number at all is the same case, and is already
    # counted by seat_not_numbered. Rudraprayag prints eighteen zila parishad
    # constituencies by name and numbers none of them - त्रिजुगीनारायण,
    # गुप्तकाशी, कालीमठ - so they share one key and disagree about the
    # reservation, which is true and is exactly what that gap says. The only way
    # to quiet it here would be to invent numbers, and the Uttarakhand adapter
    # refuses to guess one for the same reason this check exists.
    numbered = s.tier in (
        "gp_ward",
        "ulb_ward",
        "block_member",
        "block_head",
        "zp_member",
        "zp_head",
    )
    named = [
        r
        for r in s.rows
        if str(r.get("shared_place_name") or "0") in ("0", "")
        and not (
            numbered
            and not (r.get("ward_no") or "").strip()
            and not (r.get("seat_no") or "").strip()
        )
    ]
    excluded = len(s.rows) - len(named)
    counts = collections.defaultdict(set)
    for row in named:
        counts[
            (
                row.get("election_type", ""),
                row.get("election_duration", ""),
                row.get("district", ""),
                row.get("block", ""),
                canon.unit_name(row),
                row.get("ward_no", ""),
                row.get("seat_no", ""),
            )
        ].add((row.get("caste_reservation", ""), row.get("woman_reserved", "")))
    varies = {k: v for k, v in counts.items() if len(v) > 1}
    if not varies and excluded:
        return result(
            PASS,
            0,
            0,
            f"{excluded} row(s) excluded as shared_place_name - "
            f"places this key cannot tell apart, already flagged",
        )
    return result(
        FAIL if varies else PASS,
        len(varies),
        0,
        f"e.g. {list(varies)[:1]}"
        if varies
        else f"{len(counts):,} seats, all internally consistent",
    )


@check("plausible_vs_registry", "external")
def plausible_vs_registry(s):
    """Does this slice hold more bodies than the state has?

    Against the Local Government Directory count, not against a figure published
    for this election - `coverage_vs_published` owns that comparison and is the
    stronger one wherever a contemporaneous total exists.

    This is the weaker question and it is asked because nothing was asking it.
    Jharkhand's mukhiya count read 102% of the gram panchayats the state has and
    survived months of checks, because every check compared the parse against
    itself. A gram panchayat elects one head; a state with 4,364 of them cannot
    return 4,429.

    **Only the ceiling is a failure.** A state creates panchayats over time, so a
    2019-20 registry is an upper bound on a 2005 cycle and falling short of it
    proves nothing: Rajasthan reads 81% of the current count in 2005 and 100% in
    2020, which is the state growing. Falling short is reported, never failed.
    """
    counts = reference.registry(s.state, s.tier)
    if not counts:
        return result(
            SKIP,
            "",
            "",
            "the register counts bodies, and only a head tier has one seat per body",
        )
    # A head tier has one row per body by construction, so more rows than the
    # state has bodies is the defect this exists to name.
    seats = len(s.rows)
    share = seats / counts
    detail = f"{seats:,} against {counts:,} in the register ({reference.REGISTRY_ASOF})"
    if share > 1.05:
        return result(
            FAIL,
            f"{share:.0%}",
            "<=105%",
            detail + " - more than the state has, so some rows are not distinct bodies",
        )
    # 101% is not a rounding error for a tier with one seat per body, but the
    # register is dated and a later cycle can outgrow it, so this warns rather
    # than fails. Written at 105% first, which let Jharkhand's 4,429 mukhiya
    # against 4,364 gram panchayats through - the exact count this check exists
    # to notice.
    if share > 1.00:
        return result(
            WARN,
            f"{share:.0%}",
            "<=100%",
            detail + " - above the register, which is either growth "
            "since it was compiled or rows that are not "
            "distinct bodies",
        )
    if share < 0.60:
        why = reference.registry_scope(s.state, s.year)
        if why:
            return result(PASS, f"{share:.0%}", "", f"{detail} - {why}")
        return result(
            WARN,
            f"{share:.0%}",
            ">=60%",
            detail + " - a small share with no recorded reason. "
            "Either the slice covers part of the state, in "
            "which case say so in REGISTRY_SCOPE, or rows "
            "are missing",
        )
    return result(PASS, f"{share:.0%}", "", detail)


@check("year_constant", "internal")
def year_constant(s):
    years = {r.get("year") for r in s.rows}
    return result(
        FAIL if len(years) > 1 else PASS,
        ",".join(sorted(years)),
        s.year,
        "two cycles merged into one slice" if len(years) > 1 else "",
    )


@check("provenance_resolves", "internal")
def provenance_resolves(s):
    """Every row must point at a document that is actually there.

    A sibling's source_path is relative to that sibling's root, not to this
    repository, so resolving it here reported every Haryana row as missing its
    document. And a slice whose provenance_level is `dataset` records no
    document at all - Rajasthan and Bihar were scraped, not read off a page - so
    there is nothing to resolve and saying so is the honest result.
    """
    level = (s.rows[0].get("provenance_level") or "page") if s.rows else "page"
    if level in ("dataset", "none"):
        return result(
            SKIP,
            "",
            "",
            f"provenance_level is {level}: this source records no "
            f"document, so there is no path to resolve",
        )

    repo = (s.rows[0].get("source_repo") or "") if s.rows else ""
    root = s.root if repo in ("", "local_elections") else s.root.parent / repo
    if not root.exists():
        return result(SKIP, "", "", f"{repo} is not checked out here")

    missing = {
        p
        for p in {r.get("source_path", "") for r in s.rows}
        if not p or not (root / p).exists()
    }
    return result(
        FAIL if missing else PASS,
        len(missing),
        0,
        f"e.g. {sorted(missing)[:1]}"
        if missing
        else f"{len({r.get('source_path') for r in s.rows})} documents",
    )


def run(a_slice):
    """Every check against one slice, with skips escalated where they matter."""
    out = []
    for spec in CHECKS:
        got = spec["fn"](a_slice)
        # A skip on a large slice is not an acceptable answer - it means a rule
        # nobody has declared, and it reads as a pass to anyone scanning.
        if (
            got["status"] == SKIP
            and spec["appeals_to"] == "declared"
            and a_slice.n > SKIP_FLOOR
        ):
            got["status"] = FAIL
            got["detail"] += f" (and {a_slice.n:,} rows is too many to leave unchecked)"
        out.append(dict(got, check_id=spec["id"], appeals_to=spec["appeals_to"]))
    return out
