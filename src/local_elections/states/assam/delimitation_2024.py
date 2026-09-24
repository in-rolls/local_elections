"""Held official final-delimitation gazettes used to review Hailakandi."""

from local_elections.common import harvest
from local_elections.paths import ROOT

OUT = ROOT / "data" / "assam" / "2024_delimitation"
MANIFEST = OUT / "manifest.csv"
SOURCE_ID = "assam_pnrd_final_delimitation_2024"
EXPECTED_DOCUMENTS = 4


def verify():
    """Verify all held gazettes against the standard source manifest."""
    return harvest.verify(MANIFEST, OUT, {SOURCE_ID: EXPECTED_DOCUMENTS})
