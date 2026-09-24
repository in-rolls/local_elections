"""Contracts for the Gujarat 2020 source harvester."""

from local_elections.states.gujarat import geography, harvest


def test_only_pdf_links_are_collected_and_resolved():
    landing = "https://sec.gujarat.gov.in/district-panchayat-2020.htm"
    page = b"""<a href="images/pdf/Ahmedabad-DP-2020.pdf">A</a>
    <a href="downloads.htm">downloads</a>
    <a href="https://sec.gujarat.gov.in/images/pdf/Amreli-DP-2020.pdf">B</a>"""
    assert harvest.links_from(page, landing) == [
        "https://sec.gujarat.gov.in/images/pdf/Ahmedabad-DP-2020.pdf",
        "https://sec.gujarat.gov.in/images/pdf/Amreli-DP-2020.pdf",
    ]


def test_tier_and_published_name_make_the_local_name():
    url = "https://sec.gujarat.gov.in/images/pdf/Ahmedabad-DP-2020.pdf"
    assert harvest.local_name("zp_member", url) == ("zp_member_ahmedabad_dp_2020.pdf")


def test_every_discoverable_filename_has_hierarchical_geography():
    for tier, mapping in (
        ("zp_member", geography.DISTRICT_PANCHAYATS),
        ("block_member", geography.TALUKA_PANCHAYATS),
    ):
        for key in mapping:
            suffix = "dp" if tier == "zp_member" else "tps"
            filename = f"{tier}_{key}_{suffix}_2020.pdf"
            district, body = geography.places(filename, tier)
            assert district
            assert body
