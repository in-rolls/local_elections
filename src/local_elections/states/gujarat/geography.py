"""Canonical geography carried by Gujarat's 2020 SEC source filenames."""

DISTRICT_PANCHAYATS = {
    "ahmedabad": "Ahmedabad",
    "amreli": "Amreli",
    "bharuch": "Bharuch",
    "bhavnagar": "Bhavnagar",
    "dahod": "Dahod",
    "gandhinagar": "Gandhinagar",
    "girsomnath": "Gir Somnath",
    "kutchh": "Kutch",
    "morabi": "Morbi",
    "navsari": "Navsari",
    "patan": "Patan",
    "porbandar": "Porbandar",
    "rajkot": "Rajkot",
    "surat": "Surat",
    "surendranagar": "Surendranagar",
    "vadodara": "Vadodara",
}

TALUKA_PANCHAYATS = {
    "bharuch": ("Bharuch", "Bharuch"),
    "bhavnagar": ("Bhavnagar", "Bhavnagar"),
    "choryasi": ("Surat", "Choryasi"),
    "chotila": ("Surendranagar", "Chotila"),
    "daskroi": ("Ahmedabad", "Daskroi"),
    "gandhinagar": ("Gandhinagar", "Gandhinagar"),
    "girgadhda": ("Gir Somnath", "Gir Gadhada"),
    "jesar": ("Bhavnagar", "Jesar"),
    "kalol": ("Gandhinagar", "Kalol"),
    "kamrej": ("Surat", "Kamrej"),
    "kodinar": ("Gir Somnath", "Kodinar"),
    "limkheda": ("Dahod", "Limkheda"),
    "mansa": ("Gandhinagar", "Mansa"),
    "morabi": ("Morbi", "Morbi"),
    "mundra": ("Kutch", "Mundra"),
    "navsari": ("Navsari", "Navsari"),
    "olpad": ("Surat", "Olpad"),
    "palsana": ("Surat", "Palsana"),
    "patan": ("Patan", "Patan"),
    "porbandar": ("Porbandar", "Porbandar"),
    "rajkot": ("Rajkot", "Rajkot"),
    "sanand": ("Ahmedabad", "Sanand"),
    "sarsvati": ("Patan", "Saraswati"),
    "savkundala": ("Amreli", "Savarkundla"),
    "singavad": ("Dahod", "Singvad"),
    "una": ("Gir Somnath", "Una"),
    "vadodara": ("Vadodara", "Vadodara"),
    "vagara": ("Bharuch", "Vagra"),
    "vakaner": ("Morbi", "Wankaner"),
}


def source_key(filename, tier):
    """Return the published geography slug embedded in a held filename."""
    prefix = f"{tier}_"
    suffix = "_dp_2020.pdf" if tier == "zp_member" else "_tps_2020.pdf"
    if not filename.startswith(prefix) or not filename.endswith(suffix):
        raise ValueError(f"unrecognised Gujarat source filename: {filename}")
    return filename[len(prefix) : -len(suffix)]


def places(filename, tier):
    """Return ``(district, body)`` for one source document."""
    key = source_key(filename, tier)
    if tier == "zp_member":
        district = DISTRICT_PANCHAYATS[key]
        return district, district
    return TALUKA_PANCHAYATS[key]
