"""Adapters that bring a sibling repository's parse into the pooled schema.

Each module exposes:

    REPO      the sibling's directory name, looked for next to this repository
    URL       where it lives
    slices()  yields {dataset_id, state, rows, provenance_level,
                      unit_of_observation}, with rows already in master shape
    DECLARED  the row counts its committed files are known to hold

`DECLARED` is what makes an adapter safe to leave running unattended. A sibling
is a separate repository on somebody else's schedule; if it gains or loses rows,
pooling a different number without noticing is precisely the failure this
repository keeps meeting. A mismatch stops the build.

Siblings are read where they sit and never vendored - the pack here is already
1.9 GiB - and the commit they were read at is recorded on every row.
"""

from . import bihar, haryana, kerala, rajasthan, uttar_pradesh, uttarakhand

REGISTRY = {
    "Bihar": bihar,
    "Haryana": haryana,
    "Kerala": kerala,
    "Rajasthan": rajasthan,
    "Uttar Pradesh": uttar_pradesh,
    "Uttarakhand": uttarakhand,
}
