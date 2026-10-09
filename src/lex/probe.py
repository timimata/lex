"""The deployed demo, probed from outside (Phase 8):
`python -m lex.probe URL [--live] [--record FILE]`.

Health, an article on a date, a word search, every page example's answer (made at deploy, so
served from the cache and free of quota), an unknown path and the instance's usage, each timed.
`--live` (once a day) also asks a question no cache holds, which spends one answer and is the
only check that sees a revoked key or a model that no longer answers. `--record` appends what was
measured, as one JSON line, so the cold starts it met can be counted (ROADMAP, Phase 11). Exits 1
on an error or a request slower than its bar, which in a scheduled GitHub workflow is an email to
the repository's owner: the alert. Standard library only, so the workflow installs nothing.
"""

import argparse
import datetime as dt
import json
import sys
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

# Seconds a request may take: generous for the first, which may wake a cold function, and for
# the answers, which are served from the cache but sit behind the same function.
COLD_BAR = 20.0
BAR = 5.0
LIVE_BAR = 30.0  # a real answer: Vercel's own ceiling
# The page's examples, each with its date, so each is answered at deploy and kept (Phase 11).
EXAMPLES = Path(__file__).resolve().parents[2] / "web" / "src" / "examples.json"
# Asked about the day of the run, which no cache holds: the live check's question.
LIVE_QUESTION = "Quantos dias de férias tem um trabalhador por ano?"


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


def examples(path: Path = EXAMPLES) -> list[dict[str, str]]:
    """The page's examples as the API is asked them."""
    return [
        {"question": e["question"], "as_of": e["asOf"]}
        for e in json.loads(path.read_text(encoding="utf-8"))
    ]


def probe(
    base: str, live: bool = False, asked: list[dict[str, str]] | None = None
) -> tuple[list[Check], dict[str, Any] | None, dict[str, Any] | None]:
    """The checks, the instance's usage and its health reply."""
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
    for n, body in enumerate(examples() if asked is None else asked, start=1):
        reply = check(f"example {n}", "/api/answer", 200, BAR, body)
        if reply is not None and not reply.get("cached"):
            checks[-1].problem = "the example was not served from the cache: it spent the quota"
    check("unknown path", "/nada-que-exista", 404, BAR)
    usage = check("usage", "/api/usage", 200, BAR)
    if live:
        today = dt.datetime.now(dt.UTC).date().isoformat()  # never after Lisbon's
        reply = check(
            "live answer", "/api/answer", 200, LIVE_BAR, {"question": LIVE_QUESTION, "as_of": today}
        )
        if reply is not None and reply.get("cached"):
            checks[-1].problem = "the live question came from a cache: the model was not asked"
    return checks, usage, health


def record(path: Path, base: str, checks: list[Check], health: dict[str, Any] | None) -> None:
    """One JSON line of what was measured. A request that met an instance started during it
    met a cold start: the instance's age when it answered health is under that request's time."""
    now = dt.datetime.now(dt.UTC)
    started = (health or {}).get("started_at")
    age = (now - dt.datetime.fromisoformat(started)).total_seconds() if started else None
    took = sum(c.seconds for c in checks)  # the whole probe, health first
    line = {
        "at": now.isoformat(timespec="seconds"),
        "url": base,
        "build": (health or {}).get("build"),
        "instance_age_s": None if age is None else round(age, 1),
        "cold": None if age is None else age <= took + 1,
        "checks": [asdict(c) for c in checks],
    }
    with path.open("a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(line, ensure_ascii=False) + "\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m lex.probe")
    parser.add_argument("url", help="e.g. https://lex-beryl.vercel.app")
    parser.add_argument("--live", action="store_true", help="also spend one real answer")
    parser.add_argument("--record", type=Path, help="append the measurements to this file")
    args = parser.parse_args(argv)
    checks, usage, health = probe(args.url, args.live)
    for c in checks:
        mark = "FAIL" if c.problem else "ok"
        print(f"{mark:>4}  {c.name:<15} {c.status:>3}  {c.seconds:>6.2f} s  {c.problem}")
    if usage is not None:
        print("usage:", json.dumps(usage, ensure_ascii=False))
    if args.record:
        record(args.record, args.url, checks, health)
    failed = [c for c in checks if c.problem]
    print(f"{len(failed)} of {len(checks)} checks failed" if failed else "all checks passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
