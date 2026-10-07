"""The deployed demo, probed from outside (Phase 8): `python -m lex.probe URL`.

Health, an article on a date, a word search, a page example's answer (made at deploy, so served
from the cache and free of quota), an unknown path and the instance's usage, each timed. Exits 1
on an error or a request slower than its bar, which in a scheduled GitHub workflow is an email
to the repository's owner: the alert. Standard library only, so the workflow installs nothing.
"""

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

# Seconds a request may take: generous for the first, which may wake a cold function, and for
# the answer, which is served from the cache but sits behind the same function.
COLD_BAR = 20.0
BAR = 5.0
EXAMPLE = {
    "question": "Quantos dias de férias tinha um trabalhador por ano?",
    "as_of": "2011-06-01",
}


@dataclass
class Check:
    name: str
    status: int
    seconds: float
    problem: str = ""


def fetch(url: str, body: dict[str, Any] | None = None) -> tuple[int, Any, float]:
    """The status, the JSON reply (or None) and the seconds a request took."""
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            raw, status = response.read(), response.status
    except urllib.error.HTTPError as error:
        raw, status = error.read(), error.code
    except (urllib.error.URLError, TimeoutError) as error:
        return 0, str(error), time.perf_counter() - started
    seconds = time.perf_counter() - started
    try:
        return status, json.loads(raw), seconds
    except ValueError:
        return status, None, seconds


def probe(base: str) -> tuple[list[Check], dict[str, Any] | None]:
    base = base.rstrip("/")
    checks: list[Check] = []

    def check(name: str, path: str, want: int, bar: float, body: Any = None) -> Any:
        status, reply, seconds = fetch(base + path, body)
        problem = ""
        if status != want:
            problem = f"status {status}, expected {want}"
        elif seconds > bar:
            problem = f"{seconds:.1f} s, over the {bar:.0f} s bar"
        checks.append(Check(name, status, round(seconds, 2), problem))
        return reply if status == want else None

    health = check("health", "/api/health", 200, COLD_BAR)
    if health is not None and health.get("status") != "ok":
        checks[-1].problem = f"health says {health.get('status')!r}"
    article = check("article", "/api/articles/lei-7-2009/238?as_of=2011-06-01", 200, BAR)
    if article is not None and not article.get("text"):
        checks[-1].problem = "article 238 has no text on 2011-06-01"
    hits = check("search", "/api/search?q=f%C3%A9rias&k=3", 200, BAR)
    if hits is not None and not hits:
        checks[-1].problem = "a search for «férias» found nothing"
    reply = check("example answer", "/api/answer", 200, BAR, EXAMPLE)
    if reply is not None and not reply.get("cached"):
        checks[-1].problem = "the example was not served from the cache: it spent the quota"
    check("unknown path", "/nada-que-exista", 404, BAR)
    usage = check("usage", "/api/usage", 200, BAR)
    return checks, usage


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m lex.probe")
    parser.add_argument("url", help="e.g. https://lex-beryl.vercel.app")
    args = parser.parse_args(argv)
    checks, usage = probe(args.url)
    for c in checks:
        mark = "FAIL" if c.problem else "ok"
        print(f"{mark:>4}  {c.name:<15} {c.status:>3}  {c.seconds:>6.2f} s  {c.problem}")
    if usage is not None:
        print("usage:", json.dumps(usage, ensure_ascii=False))
    failed = [c for c in checks if c.problem]
    print(f"{len(failed)} of {len(checks)} checks failed" if failed else "all checks passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
