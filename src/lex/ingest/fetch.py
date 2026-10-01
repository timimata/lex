"""A polite, caching HTTP client.

Every response is kept under data/raw, so a rebuild never touches the network and nothing is
downloaded twice. Requests go one at a time, at least MIN_INTERVAL_S apart. When a server drops
the connection or answers 429/5xx, we back off and retry a few times before giving up.
"""

import datetime as dt
import hashlib
import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

USER_AGENT = "lex-pt/0.0.1 (research on question answering over Portuguese legislation)"
MIN_INTERVAL_S = 2.0
BACKOFF_S = (30.0, 60.0, 120.0)


@dataclass(frozen=True)
class Page:
    url: str
    body: bytes
    fetched: dt.date


class Fetcher:
    def __init__(
        self, cache_dir: Path, *, offline: bool = False, min_interval: float = MIN_INTERVAL_S
    ) -> None:
        self.cache_dir = cache_dir
        self.offline = offline
        self.min_interval = min_interval
        self.requests = 0
        self._last = 0.0

    def get(self, url: str, accept: str | None = None) -> Page:
        """The response body for url, from the cache if it is there. `accept` sets the Accept
        header, e.g. for an API that answers JSON only when asked; it is part of the cache key."""
        cache_key = url if accept is None else f"{url}\n{accept}"
        key = hashlib.sha256(cache_key.encode()).hexdigest()[:24]
        body_path, meta_path = self.cache_dir / f"{key}.body", self.cache_dir / f"{key}.json"
        if meta_path.exists():
            fetched = json.loads(meta_path.read_text(encoding="utf-8"))["fetched"]
            return Page(url, body_path.read_bytes(), dt.date.fromisoformat(fetched))
        if self.offline:
            raise LookupError(f"not in the raw cache: {url}")

        body = self._download(url, accept)

        # The metadata is written last, so an interrupted write never counts as cached.
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        body_path.write_bytes(body)
        today = dt.date.today()
        meta_path.write_text(json.dumps({"url": url, "fetched": today.isoformat()}), "utf-8")
        return Page(url, body, today)

    def _download(self, url: str, accept: str | None) -> bytes:
        headers = {"User-Agent": USER_AGENT} | ({"Accept": accept} if accept else {})
        for attempt in range(len(BACKOFF_S) + 1):
            wait = self._last + self.min_interval - time.monotonic()
            if wait > 0:
                time.sleep(wait)
            request = urllib.request.Request(url, headers=headers)
            try:
                with urllib.request.urlopen(request, timeout=60) as response:
                    body: bytes = response.read()
                return body
            except urllib.error.HTTPError as e:
                if e.code != 429 and e.code < 500:
                    raise
                error: Exception = e
            except (ConnectionError, TimeoutError, urllib.error.URLError) as e:
                error = e
            finally:
                self._last = time.monotonic()
                self.requests += 1
            if attempt == len(BACKOFF_S):
                raise error
            print(f"  {error!r}; retrying in {BACKOFF_S[attempt]:.0f}s", flush=True)
            time.sleep(BACKOFF_S[attempt])
        raise AssertionError("unreachable")
