"""OCR every PNG in a directory, writing <name>.txt beside each.

`ocr_seats.py` uses pdfplumber to find the pages whose seat column is drawn,
then calls this module under the Apple-Silicon Savitr environment once for the
whole directory.

Once, and not per page: loading the weights costs more than reading a page, so a
call per page would spend most of the run in startup.
"""

import pathlib
import sys

from local_elections.common import ocr_engine
from local_elections.common.runlog import command, get_logger

LOGGER = get_logger(__name__)


@command("extract", state="Jharkhand", method="surya_page_ocr")
def main():
    if len(sys.argv) != 2:
        return print(__doc__.strip()) or 2
    directory = pathlib.Path(sys.argv[1])
    pages = sorted(directory.glob("*.png"))
    if not pages:
        LOGGER.error(
            "No PNG inputs found",
            extra={"event": "ocr_input_missing", "input_directory": str(directory)},
        )
        return 1
    engine = ocr_engine.engine()
    for index, page in enumerate(pages, 1):
        out = page.with_suffix(".txt")
        if out.exists():
            continue
        text, _ = engine.ocr_image(str(page))
        out.write_text(text, encoding="utf-8")
        LOGGER.info(
            "OCR page completed",
            extra={
                "event": "ocr_page_completed",
                "source_file": page.name,
                "page": index,
                "pages": len(pages),
            },
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
