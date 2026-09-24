"""Independent SEC controls for Gujarat's held 2020 PRI orders."""

# Order within each tuple: SC women/other, ST women/other, SEBC women/other,
# general women, and unreserved other.
_DISTRICT_PUBLISHED_COUNTS = {
    "zp_member_ahmedabad_dp_2020.pdf": (2, 2, 1, 0, 1, 2, 13, 13),
    "zp_member_amreli_dp_2020.pdf": (2, 1, 0, 1, 2, 1, 13, 14),
    "zp_member_bharuch_dp_2020.pdf": (0, 1, 7, 6, 2, 1, 8, 9),
    "zp_member_bhavnagar_dp_2020.pdf": (1, 1, 0, 1, 2, 2, 17, 16),
    "zp_member_dahod_dp_2020.pdf": (0, 1, 20, 19, 2, 3, 3, 2),
    "zp_member_gandhinagar_dp_2020.pdf": (1, 0, 0, 1, 2, 1, 11, 12),
    "zp_member_girsomnath_dp_2020.pdf": (1, 2, 1, 0, 2, 1, 10, 11),
    "zp_member_kutchh_dp_2020.pdf": (2, 3, 1, 0, 2, 2, 15, 15),
    "zp_member_morabi_dp_2020.pdf": (1, 1, 0, 1, 1, 1, 10, 9),
    "zp_member_navsari_dp_2020.pdf": (0, 1, 9, 9, 2, 1, 4, 4),
    "zp_member_patan_dp_2020.pdf": (2, 1, 0, 1, 2, 1, 12, 13),
    "zp_member_porbandar_dp_2020.pdf": (1, 1, 1, 0, 1, 1, 6, 7),
    "zp_member_rajkot_dp_2020.pdf": (2, 2, 0, 1, 2, 2, 14, 13),
    "zp_member_surat_dp_2020.pdf": (1, 0, 9, 10, 2, 2, 6, 6),
    "zp_member_surendranagar_dp_2020.pdf": (2, 2, 1, 0, 1, 2, 13, 13),
    "zp_member_vadodara_dp_2020.pdf": (1, 1, 3, 3, 2, 1, 11, 12),
}

# The SEC's Statistical Report 2021, section 4.3, supplies these taluka-wise
# election controls. Gandhinagar Taluka was not among the 231 bodies holding a
# February 2021 election; its values come from the summary table printed on
# page 1 of the held SEC rotation order.
_TALUKA_PUBLISHED_COUNTS = {
    "block_member_bharuch_tps_2020.pdf": (0, 1, 3, 4, 2, 1, 10, 9),
    "block_member_bhavnagar_tps_2020.pdf": (1, 0, 0, 1, 1, 1, 8, 8),
    "block_member_choryasi_tps_2020.pdf": (1, 0, 2, 2, 1, 1, 4, 5),
    "block_member_chotila_tps_2020.pdf": (1, 0, 0, 1, 1, 1, 7, 7),
    "block_member_daskroi_tps_2020.pdf": (1, 1, 0, 1, 2, 1, 11, 11),
    "block_member_gandhinagar_tps_2020.pdf": (1, 0, 1, 0, 1, 2, 11, 12),
    "block_member_girgadhda_tps_2020.pdf": (1, 0, 0, 1, 1, 1, 8, 8),
    "block_member_jesar_tps_2020.pdf": (0, 1, 1, 0, 1, 1, 6, 6),
    "block_member_kalol_tps_2020.pdf": (1, 1, 1, 0, 1, 2, 10, 10),
    "block_member_kamrej_tps_2020.pdf": (1, 0, 3, 4, 1, 1, 5, 5),
    "block_member_kodinar_tps_2020.pdf": (2, 2, 0, 1, 1, 1, 9, 8),
    "block_member_limkheda_tps_2020.pdf": (1, 0, 7, 8, 1, 1, 3, 3),
    "block_member_mansa_tps_2020.pdf": (1, 0, 0, 1, 1, 2, 11, 10),
    "block_member_morabi_tps_2020.pdf": (1, 2, 0, 1, 2, 1, 10, 9),
    "block_member_mundra_tps_2020.pdf": (2, 1, 0, 1, 1, 1, 6, 6),
    "block_member_navsari_tps_2020.pdf": (0, 1, 5, 4, 1, 1, 2, 2),
    "block_member_olpad_tps_2020.pdf": (0, 1, 3, 3, 1, 1, 8, 7),
    "block_member_palsana_tps_2020.pdf": (1, 0, 3, 3, 1, 1, 4, 5),
    "block_member_patan_tps_2020.pdf": (1, 1, 0, 1, 1, 1, 8, 7),
    "block_member_porbandar_tps_2020.pdf": (1, 1, 0, 1, 1, 1, 9, 8),
    "block_member_rajkot_tps_2020.pdf": (1, 1, 0, 1, 1, 1, 9, 8),
    "block_member_sanand_tps_2020.pdf": (1, 2, 1, 0, 1, 1, 9, 9),
    "block_member_sarsvati_tps_2020.pdf": (1, 1, 0, 1, 1, 1, 10, 9),
    "block_member_savkundala_tps_2020.pdf": (1, 1, 0, 1, 1, 1, 9, 8),
    "block_member_singavad_tps_2020.pdf": (0, 1, 6, 6, 1, 1, 2, 1),
    "block_member_una_tps_2020.pdf": (1, 1, 1, 0, 1, 2, 10, 10),
    "block_member_vadodara_tps_2020.pdf": (1, 1, 2, 1, 1, 2, 10, 10),
    "block_member_vagara_tps_2020.pdf": (0, 1, 3, 2, 1, 1, 5, 5),
    "block_member_vakaner_tps_2020.pdf": (1, 0, 0, 1, 1, 1, 10, 10),
}

CATEGORY_KEYS = (
    ("SC", 1),
    ("SC", 0),
    ("ST", 1),
    ("ST", 0),
    ("BC", 1),
    ("BC", 0),
    ("NONE", 1),
    ("NONE", 0),
)

DISTRICT_CATEGORY_COUNTS = {
    source: dict(zip(CATEGORY_KEYS, counts, strict=True))
    for source, counts in _DISTRICT_PUBLISHED_COUNTS.items()
}
DISTRICT_ROW_COUNTS = {
    source: sum(counts.values()) for source, counts in DISTRICT_CATEGORY_COUNTS.items()
}
TALUKA_CATEGORY_COUNTS = {
    source: dict(zip(CATEGORY_KEYS, counts, strict=True))
    for source, counts in _TALUKA_PUBLISHED_COUNTS.items()
}
TALUKA_ROW_COUNTS = {
    source: sum(counts.values()) for source, counts in TALUKA_CATEGORY_COUNTS.items()
}
