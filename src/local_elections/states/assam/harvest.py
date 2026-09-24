"""Discover Assam's 2025 PRI notifications and acquire immutable local copies."""

import argparse
import html
import re

from local_elections.common import fetch
from local_elections.common.harvest import (
    HEADERS,
    SourceDocument,
    acquire,
    require_count,
    slugged_pdf_name,
)
from local_elections.common.runlog import command
from local_elections.paths import ROOT

LANDING_URL = "https://sec.assam.gov.in/panchayat-election-2025"
SOURCE_ID = "assam_sec_pri_reservation_2025"
OUT = ROOT / "data" / "assam" / "2025_reservation"
MANIFEST = OUT / "manifest.csv"
EXPECTED_DOCUMENTS = 27

DISTRICT_OF_FILE = {
    "barpeta.pdf": "Barpeta",
    "biswanath.pdf": "Biswanath",
    "bongaigaon.pdf": "Bongaigaon",
    "cachar.pdf": "Cachar",
    "charaideo_reservation.pdf": "Charaideo",
    "darrang_reservation.pdf": "Darrang",
    "dhemaji.pdf": "Dhemaji",
    "dibrugarh.pdf": "Dibrugarh",
    "goalpara.pdf": "Goalpara",
    "golaghat_reservation.pdf": "Golaghat",
    "hojai_reservation.pdf": "Hojai",
    "kamrup_reservation.pdf": "Kamrup",
    "notification_of_reservation_morigaon.pdf": "Morigaon",
    "notification_reservation_hailakandi.pdf": "Hailakandi",
    "notification_reservation_jorhat.pdf": "Jorhat",
    "notification_reservation_sonitpur.pdf": "Sonitpur",
    "notifications_reservation_dhubri.pdf": "Dhubri",
    "reservation_kamrup_m.pdf": "Kamrup Metropolitan",
    "reservation_lakhimpur.pdf": "Lakhimpur",
    "reservation_nagaon.pdf": "Nagaon",
    "reservation_nalbari.pdf": "Nalbari",
    "reservation_notification_bajali.pdf": "Bajali",
    "reservation_notification_majuli.pdf": "Majuli",
    "reservation_of_pris_sribhumi.pdf": "Sribhumi",
    "sivasagar.pdf": "Sivasagar",
    "south_salmara_reservation.pdf": "South Salmara-Mankachar",
    "tinsukia_reservation.pdf": "Tinsukia",
}

PDF_LINK = re.compile(
    rb'href=["\'](https://sec\.assam\.gov\.in/pdf/panchayat-election/'
    rb'reservation/[^"\']+\.pdf)["\']',
    re.I,
)


def links_from(page):
    """Return only district reservation PDFs from the official landing page."""
    return sorted(
        {
            html.unescape(match.decode("utf-8", "replace"))
            for match in PDF_LINK.findall(page)
        }
    )


def local_name(url):
    """Return the stable local name used in the source manifest."""
    return slugged_pdf_name(url)


def district_of(url):
    """Return the source-stated district represented by one PDF."""
    name = local_name(url)
    try:
        return DISTRICT_OF_FILE[name]
    except KeyError as exc:
        raise RuntimeError(f"unmapped Assam district source: {name}") from exc


def discover():
    """Discover and count-check one reviewed Assam source series."""
    page = fetch.body(LANDING_URL, timeout=120, headers=HEADERS)
    documents = [
        SourceDocument(
            source_id=SOURCE_ID,
            state="Assam",
            year="2025",
            government_level="rural_local",
            tier="multiple",
            language="Assamese; English",
            document_format="scan",
            district=district_of(url),
            file=local_name(url),
            url=url,
            landing_url=LANDING_URL,
        )
        for url in links_from(page)
    ]
    require_count(documents, EXPECTED_DOCUMENTS, SOURCE_ID)
    return documents


def harvest(*, dry_run=False):
    """Acquire all reviewed Assam source documents, or only list them."""
    return acquire(discover(), OUT, MANIFEST, ROOT, dry_run=dry_run)


@command("harvest", state="Assam", source_id=SOURCE_ID)
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    harvest(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
