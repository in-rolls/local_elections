"""One rate-limited HTTP session, shared by everything here that fetches.

Four scripts talk to the web - archive_sweep, harvest_archive, probe_sources,
build_coverage - and each used to roll its own retry loop. They all now come
through this module. Acquisitions use retrying `get()`; link liveness checks use
single-attempt `probe()` so one unreachable host cannot stall a release build.

**Why this exists rather than a sleep loop.** The archive sweep once reported
Gujarat at 614 archived PDFs and, an hour later, at 0; Odisha 817 then 0;
Mizoram 0 then 168. Nothing changed in the archive. Its retry loop caught every
transport error and returned an empty list, so a rate-limited query and a state
with no web presence produced the same value. That is the bug this module makes
unrepresentable: a request that could not be answered raises `Unanswered`, and
an empty answer is an empty answer.

**And the stakes are not a wrong CSV cell.** The Internet Archive states its
terms plainly - CDX requests are limited to an average of 60/min, and "if 429s
are ignored for more than a minute we block the IP at the firewall (no
connection) for 1 hour", doubling on each repeat. A hand-rolled
`sleep(5 * attempt)` never reads `Retry-After`, which is the one thing the
server tells you and the one thing that avoids the ban.

So the pacing and the backoff are the same object:

- `LimiterAdapter` subclasses `HTTPAdapter`, so `max_retries=Retry(...)` rides
  along with the token bucket rather than fighting it
- `Retry(respect_retry_after_header=True)` sleeps as long as the server asks
- `limit_statuses=(429,)`, its default, makes the limiter also rewind its own
  log when a 429 arrives - proactive pacing and reactive backoff together
- per-host buckets, so pacing web.archive.org does not throttle a liveness
  check against a state commission's own site

**Known limit: the bucket is per-process.** Two of these scripts running at once
each get their own budget and together exceed the ceiling - which is exactly how
the contradictory sweep happened, a hand query racing a background run. Do not
run two at once. If that stops being enough, pyrate_limiter.SQLiteBucket shares
a bucket across processes and is the next move.

Named `fetch` and not `http`: this directory goes on sys.path[0], and a module
called `http` here shadows the standard library's `http` package for every
import after it - including `requests`, which imports `http.client`.
"""

import requests
from requests_ratelimiter import LimiterAdapter
from urllib3.util import Retry

# The archive's stated ceiling is 60/min. Sitting on a limit is not respecting
# it, and the penalty for being wrong is an hour off the internet.
#
# Both rates, and the pair is not redundant. `per_minute` alone is a window
# rather than a leak: measured, it let five requests through in 0.01s, because
# five is under fifty and the minute had only just started. That satisfies
# "60/min" arithmetically while presenting as a burst, which is what a server
# rate-limits on. `per_second` smooths it - the same five requests then land at
# 0, 1.06, 2.11, 3.16, 4.21s - and `per_minute` still caps the average.
PER_SECOND = 1
PER_MINUTE = 50

# A status the server can plausibly recover from. 404 is not here: it is an
# answer, and a caller that wants to call it a dead link should be allowed to.
RETRY_ON = (429, 500, 502, 503, 504)

# 0, 4, 8, 16, 32s where the server sends no Retry-After, capped by urllib3 at
# backoff_max=120. Module constants so a test can turn the wait off and still
# exercise the path - a suite that waits out the real backoff gets skipped.
TOTAL = 5
BACKOFF_FACTOR = 2

TIMEOUT = 120

_SESSION = None
_PROBE_SESSION = None


class Unanswered(Exception):
    """The request could not be answered - not that the answer was empty.

    Keeping these apart is the whole point of the module. A caller that folds
    this into "nothing found" reintroduces the bug in the docstring above.

    `status` is the HTTP status where the server answered and kept refusing,
    and None where nothing answered at all. probe_sources.py needs the
    difference: a connection that never opens is evidence a site is
    geo-blocked, and a 429 that outlasted five backoffs is evidence of nothing
    except that we were asking too fast.
    """

    def __init__(self, message, status=None):
        super().__init__(message)
        self.status = status


def session():
    """The process-wide session. One, so callers share a token bucket."""
    global _SESSION
    if _SESSION is None:
        retry = Retry(
            total=TOTAL,
            backoff_factor=BACKOFF_FACTOR,
            backoff_jitter=1.0 if BACKOFF_FACTOR else 0.0,
            status_forcelist=RETRY_ON,
            allowed_methods=("GET", "HEAD"),
            respect_retry_after_header=True,
            # so an exhausted retry comes back as a response we can read,
            # rather than an exception that loses which status it was
            raise_on_status=False,
        )
        adapter = LimiterAdapter(
            per_second=PER_SECOND, per_minute=PER_MINUTE, max_retries=retry
        )
        _SESSION = requests.Session()
        _SESSION.mount("http://", adapter)
        _SESSION.mount("https://", adapter)
    return _SESSION


def probe_session():
    """Return a rate-limited session that makes one attempt per URL."""
    global _PROBE_SESSION
    if _PROBE_SESSION is None:
        adapter = LimiterAdapter(
            per_second=PER_SECOND,
            per_minute=PER_MINUTE,
            max_retries=0,
        )
        _PROBE_SESSION = requests.Session()
        _PROBE_SESSION.mount("http://", adapter)
        _PROBE_SESSION.mount("https://", adapter)
    return _PROBE_SESSION


def _get(active_session, url, timeout, headers):
    """Run one configured session and preserve answer/failure semantics."""
    try:
        response = active_session.get(
            url, timeout=timeout, headers=headers or {"User-Agent": "Mozilla/5.0"}
        )
    except requests.RequestException as exc:
        raise Unanswered(f"{type(exc).__name__}: {exc}") from exc
    if response.status_code in RETRY_ON:
        raise Unanswered(
            f"HTTP {response.status_code} after retries: {url}",
            status=response.status_code,
        )
    return response


def get(url, timeout=TIMEOUT, headers=None):
    """The response, whatever status the server gave - or `Unanswered`.

    A 404 comes back as a response, because "the state took this down" is a
    finding. A 429 that survived five backoffs does not, because "the archive
    would not talk to us" is not a finding about the archive's holdings.
    """
    return _get(session(), url, timeout, headers)


def probe(url, timeout=TIMEOUT, headers=None):
    """Make one rate-limited liveness attempt without acquisition retries."""
    return _get(probe_session(), url, timeout, headers)


def body(url, **kwargs):
    """The bytes of a 2xx response, or `Unanswered`."""
    response = get(url, **kwargs)
    if not response.ok:
        raise Unanswered(
            f"HTTP {response.status_code}: {url}", status=response.status_code
        )
    return response.content
