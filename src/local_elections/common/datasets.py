"""Read registered pooled inputs without admitting supplemental or research tables."""

import collections
import csv
import json

from local_elections.paths import ROOT

DATA = ROOT / "data"

from local_elections.common import (  # noqa: E402 - after DATA, which it needs
    canon,
    master,
)

DERIVED = {"master", "stats", "transliteration", "source_search", "integration"}


def registry():
    """Return the explicit local dataset catalog."""
    return json.loads((ROOT / "data/datasets.json").read_text(encoding="utf-8"))


def state_directories(exclude=DERIVED):
    return sorted(DATA / state for state in registry() if (DATA / state).is_dir())


def paths(exclude=DERIVED):
    """Yield only registered pooled inputs; supplemental tables stay separate."""
    for state, specification in registry().items():
        directory = DATA / state
        if not directory.is_dir():
            continue
        for relative in specification["pooled"]:
            path = directory / relative
            if not path.is_file():
                raise FileNotFoundError(f"Registered pooled input is missing: {path}")
            yield path


def read(path):
    with path.open(encoding="utf-8", errors="replace") as fh:
        return list(csv.DictReader(fh))


def parsed(exclude=DERIVED):
    """Yield (path, rows) for nonempty registered local pooled inputs."""
    for path in paths(exclude):
        rows = read(path)
        if rows:
            yield path, rows


def as_written(row):
    """A parsed row with every value the string it will be once written.

    `to_master` already does this for the columns it keeps, for a stated reason:
    an adapter that sets woman_reserved to the integer 1 makes a row that
    behaves differently in memory than after a round trip through the CSV, and
    the checks were written against rows read back from disk. The columns it
    drops need the same treatment, or the first check to call .strip() on one of
    them dies - which is exactly what happened.

    `seat_members` is dropped rather than stringified: it is the whole candidate
    list, it belongs in the candidate table, and str() of it would be a
    kilobyte of nothing per row.

    The panchayat's alias columns are dropped too. `to_master` has already
    coalesced them into `gram_panchayat`, and carrying `halqa` back alongside it
    re-creates exactly the ambiguity `alias_family_exclusive` exists to forbid -
    Jammu & Kashmir writes the same name in both, and `canon.unit_name` raises
    on a row that names the panchayat twice, as it should.
    """
    aliases = set(canon.UNIT_COLUMNS) - {"gram_panchayat"}
    return {
        k: "" if v is None else str(v)
        for k, v in row.items()
        if k not in aliases and not isinstance(v, (list, dict, tuple, set))
    }


def pooled():
    """Every row in the pooled master, this repository's and its siblings'.

    The checks and the worklist read this rather than parsed(), because
    otherwise they cannot see a single sibling row. Two thirds of the master
    comes from adapters, and a worklist that says "generated from the rows and
    cannot go stale" while being blind to most of the rows is worse than one
    that admits its scope: it reports a small number of problems and reads as
    though that is all there are.

    Yields (dataset_id, rows) rather than (path, rows) - a pooled slice has no
    single file behind it, and pretending otherwise is what would make
    provenance checks resolve against the wrong root.

    Each row is the master projection **over** the row it came from, not instead
    of it. The projection keeps 36 declared columns and drops everything else to
    master_extras.parquet, and the checks need what it drops: `caste_share_vs_
    population` reads pop_sc and pop_total, `no_ward_column_in_the_source` reads
    ward_count, `seat_id_drawn_as_an_image` reads seat_from_image. Yielding the
    projection alone silently turned the strongest external check available -
    reserved seats sitting where the reserved population lives - from 2 passes
    into 2 skips, and a skip on a large slice is meant to escalate to a failure
    but cannot when the column it needs is simply absent. It went unnoticed for
    a whole phase, including through a verification step that promised no
    existing number would move.
    """
    from local_elections.tools import (
        build_master,
    )

    grouped = collections.defaultdict(list)
    latin = master.transliterations(ROOT)
    for slice_ in list(build_master.local_slices()) + list(
        build_master.sibling_slices()
    ):
        for row in slice_["rows"]:
            got = master.to_master(
                row,
                slice_["dataset_id"],
                slice_["source_repo"],
                slice_["source_commit"],
                slice_["provenance_level"],
                row.get("unit_of_observation")
                or slice_.get("unit_of_observation", "seat"),
                row.get("seat_candidates", ""),
                latin,
            )
            if got is not None:
                grouped[slice_["dataset_id"]].append(dict(as_written(row), **got))
    yield from sorted(grouped.items())
