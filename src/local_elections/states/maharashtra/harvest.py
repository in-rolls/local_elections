"""Acquire the Karekurve-Ramachandra & Lee (2025) Mumbai deposit from Dataverse.

The Brihanmumbai Municipal Corporation files already held in
``data/maharashtra/mumbai/`` are result tables. They state which seat a woman
was elected to, not which seat was reserved for one, for every cycle but one -
and that one (the 2007 sheet) carries the *2012* reservation beside the 2007
winners. The seat reservation for the 2007 and 2017 councils is public only in
the replication deposit for

    Karekurve-Ramachandra, Varun and Alexander Lee (2025). "Can Gender Quotas
    Improve Public Service Provision? Evidence from Indian Local Government."
    Comparative Political Studies 58(5). Harvard Dataverse,
    doi:10.7910/DVN/IO9SLQ, version 1, CC0 1.0.

which the authors digitised from the Maharashtra State Election Commission's
result handbooks. It also carries the Praja Foundation's ward-level citizen
ratings of councillors for six survey waves, which is why the whole deposit is
mirrored rather than the two columns the parser needs. Seven files, about 1 MB.
"""

import argparse

from local_elections.common.harvest import SourceDocument, acquire, require_count
from local_elections.common.runlog import command
from local_elections.paths import ROOT

SOURCE_ID = "harvard_dataverse_IO9SLQ_karekurve_lee_2025"
DOI = "doi:10.7910/DVN/IO9SLQ"
LANDING = f"https://dataverse.harvard.edu/dataset.xhtml?persistentId={DOI}"
API = "https://dataverse.harvard.edu/api/access/datafile"
OUT = ROOT / "data" / "maharashtra" / "mumbai" / "dataverse_IO9SLQ"
MANIFEST = OUT / "manifest.csv"

# Dataverse file id -> (label as deposited, format)
FILES = {
    7345308: ("mumbai_full.tab", "tabular"),
    7345306: ("fulldata_reshaped.tab", "tabular"),
    7345307: ("1. mumbai_std.do", "stata-do"),
    7345303: ("6.fulldata_days_analysis.do", "stata-do"),
    7345304: ("genindex1.do", "stata-do"),
    7345305: ("Readme.pdf", "digital-text"),
    7345309: ("Research_Proposal.bib", "bibtex"),
}
EXPECTED_DOCUMENTS = len(FILES)


def discover():
    """The deposit's seven files, addressed by their stable Dataverse ids."""
    documents = [
        SourceDocument(
            source_id=SOURCE_ID,
            state="Maharashtra",
            year="2007-2017",
            government_level="municipal_corporation",
            tier="ulb_ward",
            language="English",
            document_format=document_format,
            file=label,
            url=f"{API}/{file_id}",
            landing_url=LANDING,
            district="Mumbai",
            body="Brihanmumbai Municipal Corporation",
        )
        for file_id, (label, document_format) in sorted(FILES.items())
    ]
    require_count(documents, EXPECTED_DOCUMENTS, SOURCE_ID)
    return documents


def harvest(*, dry_run=False):
    """Fetch the deposit, or only list it."""
    return acquire(discover(), OUT, MANIFEST, ROOT, dry_run=dry_run)


@command("harvest", state="Maharashtra")
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    harvest(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
