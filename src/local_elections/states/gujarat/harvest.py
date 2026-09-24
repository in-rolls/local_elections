"""Discover Gujarat's 2020 PRI rotation orders and acquire local copies."""

import argparse
import re
import urllib.parse

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
from local_elections.states.gujarat import geography

SERIES = {
    "zp_member": {
        "source_id": "gujarat_sec_district_panchayat_rotation_2020",
        "government_level": "district_panchayat",
        "landing_url": "https://sec.gujarat.gov.in/district-panchayat-2020.htm",
        "expected": 16,
    },
    "block_member": {
        "source_id": "gujarat_sec_taluka_panchayat_rotation_2020",
        "government_level": "taluka_panchayat",
        "landing_url": "https://sec.gujarat.gov.in/taluka-panchayat-2020.htm",
        "expected": 29,
    },
}
OUT = ROOT / "data" / "gujarat" / "2020_reservation"
MANIFEST = OUT / "manifest.csv"
PDF_LINK = re.compile(rb'href=["\']([^"\']+\.pdf)["\']', re.I)


def links_from(page, landing):
    """Return resolved PDF links from one official SEC landing page."""
    return sorted(
        {
            urllib.parse.urljoin(landing, value.decode("utf-8", "replace"))
            for value in PDF_LINK.findall(page)
        }
    )


def local_name(tier, url):
    """Prefix the published basename with the output seat tier."""
    return slugged_pdf_name(url, prefix=f"{tier}_")


def discover():
    """Discover and independently count-check both Gujarat source series."""
    documents = []
    for tier, series in SERIES.items():
        landing = series["landing_url"]
        page = fetch.body(landing, timeout=120, headers=HEADERS)
        found = []
        for url in links_from(page, landing):
            filename = local_name(tier, url)
            district, body = geography.places(filename, tier)
            found.append(
                SourceDocument(
                    source_id=series["source_id"],
                    state="Gujarat",
                    year="2020",
                    government_level=series["government_level"],
                    tier=tier,
                    language="Gujarati",
                    document_format="encoded-text",
                    file=filename,
                    url=url,
                    landing_url=landing,
                    district=district,
                    body=body,
                )
            )
        require_count(found, series["expected"], series["source_id"])
        documents.extend(found)
    return documents


def harvest(*, dry_run=False):
    """Acquire both Gujarat series, or only discover and list them."""
    return acquire(discover(), OUT, MANIFEST, ROOT, dry_run=dry_run)


@command("harvest", state="Gujarat")
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    harvest(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
