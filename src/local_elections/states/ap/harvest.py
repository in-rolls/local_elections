"""Acquire Andhra Pradesh's 2020 gram-panchayat reservation gazettes."""

import argparse

from local_elections.common.harvest import SourceDocument, acquire, verify
from local_elections.common.runlog import command
from local_elections.paths import ROOT

SOURCE_ID = "andhra_pradesh_sec_gp_reservations_2020"
LANDING_URL = "https://sec.ap.gov.in/"
SOURCE_BASE = "https://sec.ap.gov.in/Uploads/Documents/Notifications/SP_and_WM/"
OUT = ROOT / "data" / "ap" / "2020_res_gp"
MANIFEST = OUT / "manifest.csv"
EXPECTED_DOCUMENTS = 13

# The AP SEC publishes one document for each of the 13 districts that existed
# for this election. These are source identifiers, not reservation data: every
# seat and place name is read from the held documents downstream.
DISTRICTS = {
    "atp": "Anantapur",
    "ctr": "Chittoor",
    "est": "East Godavari",
    "guntur": "Guntur",
    "kdp": "Kadapa",
    "knl": "Kurnool",
    "kri": "Krishna",
    "nlr": "Nellore",
    "pkm": "Prakasam",
    "skl": "Srikakulam",
    "vsk": "Visakhapatnam",
    "vzm": "Vizianagaram",
    "wg": "West Godavari",
}


def documents():
    """Return the reviewed, count-checked AP SEC source series."""
    found = [
        SourceDocument(
            source_id=SOURCE_ID,
            state="Andhra Pradesh",
            year="2020",
            government_level="rural_local",
            tier="multiple",
            language="English; Telugu",
            document_format="mixed",
            district=district,
            file=f"{code}_res_gp.pdf",
            url=f"{SOURCE_BASE}{code}_res_gp.pdf",
            landing_url=LANDING_URL,
        )
        for code, district in DISTRICTS.items()
    ]
    if len(found) != EXPECTED_DOCUMENTS:
        raise RuntimeError(
            f"{SOURCE_ID}: expected {EXPECTED_DOCUMENTS} documents, found {len(found)}"
        )
    return found


def harvest(*, dry_run=False):
    """Acquire all 13 official district documents."""
    return acquire(documents(), OUT, MANIFEST, ROOT, dry_run=dry_run)


def verify_held():
    """Verify the complete held series without making a network request."""
    return verify(MANIFEST, OUT, {SOURCE_ID: EXPECTED_DOCUMENTS})


@command("harvest", state="Andhra Pradesh", source_id=SOURCE_ID)
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    if args.verify:
        verify_held()
        return
    harvest(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
