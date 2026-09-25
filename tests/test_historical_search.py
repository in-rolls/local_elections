"""Historical search: benchmark scoring and harvest link and download checks."""

import json
from typing import ClassVar

from local_elections.tools import historical_harvest as harvest
from local_elections.tools.bench_up_history import category, score


def test_history_benchmark_does_not_reward_filling_unknown_categories():
    assert category(" SC L\n") == "SCL"
    assert category("SC extra") is None
    assert category("-") is None
    readings = [
        {"printed_category": "SC", "recognized_category": "SC"},
        {"printed_category": "SCL", "recognized_category": "SC"},
        {"printed_category": "UR", "recognized_category": None},
        {"printed_category": "-", "recognized_category": "UR"},
        {"printed_category": "-", "recognized_category": None},
    ]
    result = score(readings)
    assert result["correct_printed_categories"] == 1
    assert result["wrong_printed_categories"] == 1
    assert result["abstained_printed_categories"] == 1
    assert result["false_categories_on_missing"] == 1
    assert result["errors_by_printed_category"] == {"SCL": 1, "UR": 1}


def test_main_links_keep_missing_targets_and_district_heading():
    html = '<a href="/nav">Navigation</a><h1>Results</h1><a href="#">share</a>'
    html += '<h2>KARNAL</h2><a href="/404.html">ASSANDH</a>'
    html += '<footer><a href="/footer">Footer</a></footer>'
    links = harvest.links_from_html(html, "https://example.gov.in/")
    assert len(links) == 1
    assert links[0]["heading"] == "KARNAL"
    assert links[0]["url"] == "https://example.gov.in/404.html"


def test_pdf_link_returning_html_is_not_a_document(tmp_path, monkeypatch):
    class Response:
        content = b"<html>not found</html>"
        headers: ClassVar[dict[str, str]] = {"Content-Type": "text/html"}
        status_code = 200
        ok = True
        url = "https://example.gov.in/file.pdf"

    class Session:
        @staticmethod
        def get(*_args, **_kwargs):
            return Response()

    monkeypatch.setattr(harvest.fetch, "session", Session)
    (tmp_path / "raw").mkdir()
    result = harvest.acquire(Response.url, tmp_path, {})
    assert result["status"] == "pdf_link_returned_non_pdf"
    assert (tmp_path / result["path"]).read_bytes() == Response.content
    assert json.loads((tmp_path / "requests.jsonl").read_text())["http_status"] == 200
