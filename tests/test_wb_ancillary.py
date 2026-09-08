"""Keep administration counts separate from reservation or winner data."""

import json
from types import SimpleNamespace

from local_reservations.states.wb import parse_ward_schedules
from local_reservations.states.wb.parse_ancillary import (
    parse_candidate_reports,
    parse_polling_infrastructure,
    parse_single_nomination_rows,
)


def ocr_record(text):
    words = []
    for i, line in enumerate(text.splitlines(), 1):
        for j, token in enumerate(line.split(), 1):
            words.append(
                {
                    "text": token,
                    "block_num": "1",
                    "par_num": "1",
                    "line_num": str(i),
                    "left": str(j * 20),
                    "top": str(i * 20),
                    "width": "20",
                    "height": "10",
                }
            )
    return {"source_sha256": "hash", "source_page": 1, "words": words}


def test_uncontested_report_is_not_reservation_or_winner_data():
    rows = parse_candidate_reports(
        ocr_record("ALIPURDUAR 999 45 0 188 7 0 18 0 0"), "TotalUncontested.pdf"
    )
    assert len(rows) == 3
    assert json.loads(rows[0]["counts_json"])["uncontested_seats"] == 45
    assert rows[0]["record_kind"] == "uncontested_seat_totals_after_withdrawal"
    assert "caste_reservation" not in rows[0]
    assert rows[0]["review_status"] == "needs_review"


def test_single_nomination_rejects_truncated_ocr_identity():
    rows = parse_single_nomination_rows(
        ocr_record(
            "GRAM PANCHAYAT\n1 Block Lankapara/Il-2 Nil\n2 Block Lankapara/III-3 Nil"
        ),
        "ReportonSingleNIL.pdf",
    )
    assert len(rows) == 1
    assert rows[0]["constituency_raw"] == "Lankapara/III-3"
    assert rows[0]["record_kind"] == "single_valid_nomination_after_scrutiny"


def test_polling_infrastructure_printed_totals_detect_missing_block():
    values = ["1"] * 11
    record = {
        "sha256": "hash",
        "pages": [
            {
                "page": 1,
                "tables": [
                    {
                        "bbox": [0, 0, 100, 100],
                        "rows": [
                            ["BLOCK", "No. of Premises", "Total Elector"],
                            ["Block A", *values],
                            ["TOTAL", *values],
                        ],
                    }
                ],
            }
        ],
    }
    rows = parse_polling_infrastructure(record, "source.pdf")
    assert all(r["review_status"] == "source_controls_passed" for r in rows)
    record["pages"][0]["tables"][0]["rows"][-1][-1] = "2"
    rows = parse_polling_infrastructure(record, "source.pdf")
    assert all("printed_total_mismatch" in r["quality_flags"] for r in rows)


def test_ocr_tsv_quotes_do_not_merge_words(tmp_path, monkeypatch):
    monkeypatch.setattr(parse_ward_schedules, "ROOT", tmp_path)
    monkeypatch.setattr(parse_ward_schedules, "OUT", tmp_path / "out")
    raw = (
        "level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\t"
        "left\ttop\twidth\theight\tconf\ttext\n"
        '5\t1\t1\t1\t1\t1\t0\t0\t5\t5\t90\t"\n'
        "5\t1\t1\t1\t1\t2\t6\t0\t5\t5\t90\tSC\n"
    )

    def run(args, **kwargs):
        if args[0] == "pdftoppm":
            parse_ward_schedules.Image.new("RGB", (20, 30)).save(args[-1] + ".png")
        return SimpleNamespace(stdout=raw, stderr="")

    monkeypatch.setattr(parse_ward_schedules.subprocess, "run", run)
    cache = parse_ward_schedules.ocr_page(("source.pdf", "hash", 1))
    record = json.loads((tmp_path / cache).read_text())
    assert [w["text"] for w in record["words"]] == ['"', "SC"]
    assert record["tsv_raw"] == raw
