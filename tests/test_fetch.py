"""The shared session, tested against the failure that produced it.

Nothing here reaches the internet. The 429 is served by a local HTTP server on
a loopback port, because a retry path that has never fired is decoration and
asserting on the configuration object only proves it was typed correctly.
"""

import http.server
import json
import threading
import time
from pathlib import Path

import pytest
import requests

from local_reservations.common import fetch
from local_reservations.tools import historical_harvest


def test_historical_download_pool_shares_limits_and_reuses_receipts(tmp_path):
    body = (
        Path(__file__).parent / "fixtures/haryana_historical/assandh_ps.pdf"
    ).read_bytes()
    with Server([(200, {"Content-Type": "application/pdf"}, body)]) as server:
        seeds = [
            {"url": f"{server.url}/{index}.pdf", "family": "block_member"}
            for index in range(3)
        ]
        seeds.append(seeds[0])
        historical_harvest.harvest(seeds, tmp_path, depth=0, workers=3)
        assert len(server.seen) == 3
        assert server.seen[-1] - server.seen[0] >= 1.8
        receipts = [
            json.loads(line)
            for line in (tmp_path / "requests.jsonl").read_text().splitlines()
        ]
        assert len(receipts) == 3
        assert all(r["status"] == "ok_pdf" and r["pages"] == 1 for r in receipts)
        assert all((tmp_path / r["path"]).read_bytes() == body for r in receipts)
        historical_harvest.harvest(seeds, tmp_path, depth=0, workers=3)
        assert len(server.seen) == 3
        assert len((tmp_path / "requests.jsonl").read_text().splitlines()) == 3


class Server:
    """A loopback server that answers with whatever the test tells it to."""

    def __init__(self, replies):
        # replies: list of (status, headers, body) consumed in order; the last
        # one repeats once exhausted
        self.replies = list(replies)
        self.seen = []
        test = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                test.seen.append(time.monotonic())
                index = min(len(test.seen) - 1, len(test.replies) - 1)
                status, headers, body = test.replies[index]
                self.send_response(status)
                for key, value in headers.items():
                    self.send_header(key, value)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args):
                pass

        self.httpd = http.server.HTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.httpd.server_port}/x"

    def __enter__(self):
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        return self

    def __exit__(self, *exc):
        self.httpd.shutdown()
        self.httpd.server_close()


@pytest.fixture(autouse=True)
def fresh_session():
    """Each test gets its own session, or one test's token bucket paces the
    next one and the suite takes minutes."""
    fetch._SESSION = None
    fetch._PROBE_SESSION = None
    yield
    fetch._SESSION = None
    fetch._PROBE_SESSION = None


@pytest.fixture
def without_the_wait(monkeypatch):
    """The real backoff is 0+4+8+16+32s. Tests that care whether a path is
    taken, rather than how long it waits, turn the wait off - the alternative
    is a suite nobody runs. The shipped values are asserted separately, below.
    """
    monkeypatch.setattr(fetch, "BACKOFF_FACTOR", 0)
    # pyrate_limiter requires generous-before-tight: strictly increasing
    # limits over strictly increasing intervals with non-increasing density,
    # so the two rates have to be raised together.
    monkeypatch.setattr(fetch, "PER_SECOND", 100)
    monkeypatch.setattr(fetch, "PER_MINUTE", 6000)
    fetch._SESSION = None
    fetch._PROBE_SESSION = None


def test_a_refused_connection_is_unanswered_and_not_an_empty_answer(without_the_wait):
    """The regression test for Gujarat 614 -> 0.

    The sweep's retry loop caught every transport error and returned [], so a
    state whose query failed was written down as a state with nothing archived.
    An unreachable host must not be able to masquerade as an empty one.
    """
    with Server([(200, {}, b"")]) as server:
        url = server.url
    # the server is now shut down, so the port refuses
    with pytest.raises(fetch.Unanswered):
        fetch.get(url, timeout=5)


def test_an_empty_body_is_an_answer(without_the_wait):
    with Server([(200, {}, b"")]) as server:
        assert fetch.get(server.url, timeout=5).content == b""


def test_a_404_is_an_answer_because_a_dead_link_is_a_finding(without_the_wait):
    with Server([(404, {}, b"gone")]) as server:
        assert fetch.get(server.url, timeout=5).status_code == 404
    # ... but body() refuses to hand back a 404's bytes as if they were data
    with Server([(404, {}, b"gone")]) as server, pytest.raises(fetch.Unanswered):
        fetch.body(server.url, timeout=5)


def test_a_429_is_retried_and_the_retry_after_header_is_obeyed():
    """Proves the retry path fires, and that we wait as long as we are asked.

    The archive blocks an IP at the firewall for an hour if 429s are ignored
    for more than a minute, so this is the behaviour that matters most and the
    one a configuration-only assertion cannot demonstrate.
    """
    with Server(
        [(429, {"Retry-After": "1"}, b"slow down"), (200, {}, b"ok")]
    ) as server:
        started = time.monotonic()
        response = fetch.get(server.url, timeout=10)
        waited = time.monotonic() - started
        assert response.content == b"ok"
        assert len(server.seen) == 2, "the 429 was not retried"
        assert waited >= 1, f"Retry-After: 1 was ignored, waited {waited:.2f}s"


def test_a_429_that_never_clears_is_unanswered(without_the_wait):
    with Server([(429, {"Retry-After": "0"}, b"no")]) as server:
        with pytest.raises(fetch.Unanswered):
            fetch.get(server.url, timeout=10)
        # five retries after the first attempt, and it gave up rather than
        # hammering on
        assert len(server.seen) == fetch.TOTAL + 1


def test_a_liveness_probe_does_not_retry(without_the_wait):
    with Server([(500, {}, b"no"), (200, {}, b"ok")]) as server:
        with pytest.raises(fetch.Unanswered):
            fetch.probe(server.url, timeout=10)
        assert len(server.seen) == 1


def test_the_shipped_settings_are_what_the_archive_asks_for():
    """The tests above turn the wait off to stay quick, so the values we
    actually ship are asserted here. The Internet Archive states 60/min, and
    sitting exactly on a limit is not respecting it."""
    assert fetch.PER_MINUTE < 60
    assert fetch.PER_SECOND <= 1, "a burst is what a server rate-limits on"
    assert fetch.BACKOFF_FACTOR >= 1, "retries would return before the server"
    assert fetch.TOTAL >= 3
    # constructing the session proves the two rates satisfy pyrate_limiter's
    # generous-before-tight ordering, which it enforces with a ValueError
    fetch.session()


def test_the_session_paces_requests():
    """A configuration assertion proves the argument was passed; this proves
    the bucket actually delays anything.

    The first version of this test failed, and was right to: `per_minute=50`
    on its own is a window, not a leak, and let five requests through in 0.01s.
    Five is under fifty and the minute had only just started, so the limit was
    satisfied arithmetically while the traffic was a burst. That is what a
    server rate-limits on, which is why `per_second` is also set.
    """
    with Server([(200, {}, b"ok")]) as server:
        started = time.monotonic()
        for _ in range(3):
            fetch.get(server.url, timeout=5)
        elapsed = time.monotonic() - started
    assert elapsed >= 2 / fetch.PER_SECOND, (
        f"three requests took {elapsed:.2f}s - unpaced"
    )


def test_the_adapter_carries_both_the_limiter_and_the_retry():
    """They have to be the same object; a limiter in front of a plain adapter
    would pace the first attempt and let every retry through unpaced."""
    adapter = fetch.session().get_adapter("http://example.org")
    retry = adapter.max_retries
    assert isinstance(retry, requests.adapters.Retry)
    assert retry.respect_retry_after_header is True
    assert 429 in retry.status_forcelist
    assert retry.backoff_jitter > 0, "parallel runs would resynchronise"
    assert hasattr(adapter, "limiter"), "the adapter is not rate limited"
