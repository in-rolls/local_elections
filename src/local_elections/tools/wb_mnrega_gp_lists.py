"""West Bengal gram panchayat lists from the MNREGA R3 reports.

    uv run python -m local_elections.tools.wb_mnrega_gp_lists

A Form 1B order names only the Pradhan offices it reserves. Filling in the
unreserved remainder needs the list of every GP in the district for that term,
and the MNREGA R3 report for the same year supplies one: in each district
filled so far its GP count equals the total printed in the order (column 2).
It is also the table the spending analysis joins to, so matching against it
settles the join at the same time.

The R3 files are the published copies in doi:10.7910/DVN/ZHF9WC. They are
fetched by datafile id, checked against the md5 Dataverse records, cached under
INDIA_DATA_HOME, and never committed. Only the West Bengal GP rows are kept, in
data/wb/reference/mnrega_gp_lists.csv.
"""

import argparse
import gzip
import hashlib
import io
import os
import pathlib
import sys

import pandas as pd
import requests

from local_elections.common.runlog import command
from local_elections.paths import ROOT

OUT = ROOT / "data" / "wb" / "reference" / "mnrega_gp_lists.csv"

DOI = "doi:10.7910/DVN/ZHF9WC"

# file year -> (Dataverse datafile id, md5 recorded by Dataverse)
R3 = {
    2013: (10396541, "e6950bd317dabe3b41bf7738c248e7ee"),
    2018: (10396546, "fd3487254ae01b22b999d6425fa62309"),
}


def cached(year):
    """Bytes of the R3 file for `year`, downloaded once and md5-checked."""
    datafile, md5 = R3[year]
    home = pathlib.Path(os.environ.get("INDIA_DATA_HOME", "~/data")).expanduser()
    path = home / "mnrega_dataverse" / "r3" / f"r3-all-{year}.csv.gz"
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        url = f"https://dataverse.harvard.edu/api/access/datafile/{datafile}"
        response = requests.get(url, timeout=300)
        response.raise_for_status()
        path.write_bytes(response.content)
    body = path.read_bytes()
    if hashlib.md5(body).hexdigest() != md5:
        raise ValueError(f"{path} does not match the Dataverse md5 {md5}")
    return body


def coalesce(frame, name):
    """The report spells a column in different cases across years and levels."""
    columns = [c for c in frame.columns if c.lower() == name]
    return frame[columns].bfill(axis=1).iloc[:, 0]


def gp_rows(year):
    frame = pd.read_csv(
        io.BytesIO(gzip.decompress(cached(year))), dtype=str, low_memory=False
    )
    state = coalesce(frame, "state").str.upper()
    gp = coalesce(frame, "panchayat")
    # block- and district-level subtotal rows carry no panchayat name
    keep = state.str.contains("BENGAL", na=False) & gp.notna()
    datafile, md5 = R3[year]
    return pd.DataFrame(
        {
            "mnrega_file_year": year,
            "district": coalesce(frame, "district")[keep].str.strip(),
            "block": coalesce(frame, "block")[keep].str.strip(),
            "gram_panchayat": gp[keep].str.strip(),
            "source": f"{DOI} datafile {datafile} (r3-all-{year}.csv.gz, md5 {md5})",
        }
    )


@command("reference", source="mnrega_dataverse")
def main():
    argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0]).parse_args()
    table = pd.concat([gp_rows(year) for year in R3], ignore_index=True)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    table.to_csv(OUT, index=False, lineterminator="\n")
    for (year, district), group in table.groupby(["mnrega_file_year", "district"]):
        print(f"  {year}  {district:<40} {len(group):>4} GPs")
    print(f"{len(table)} rows -> {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
