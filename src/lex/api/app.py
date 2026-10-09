"""The HTTP service in front of a System, and the public demo's backend (ADRs 0013, 0014).

Everything is under /api; the web page, when built, is served from /. Answers are limited per
visitor and per day, so a free-tier model key is the budget cap, and a repeated question gets
its earlier answer without calling the model again. "Today" is Lisbon's date: the law asked
about is Portuguese, and a server's clock may be on UTC.
"""

import datetime as dt
import json
import threading
import time
from collections import OrderedDict, defaultdict, deque
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol
from zoneinfo import ZoneInfo

from fastapi import FastAPI, HTTPException, Request
from fastapi.exception_handlers import http_exception_handler
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from starlette.exceptions import HTTPException as StarletteHTTPException

# The disclaimer and Lisbon's date live in lex.domain, which the MCP server shares without FastAPI.
from lex.domain import DISCLAIMER, LISBON, Answer, System, lisbon_today
from lex.generation import llm
from lex.store.memory import excerpt

# From this day the corpus has every tenancy article's history (ADR 0017); the Código do
# Trabalho starts later, on 2009-02-17, and a question about it before then finds no article.
FIRST_DAY = dt.date(2006, 6, 27)
# Google's free quota counts days in the Pacific: it renews at midnight there, 08:00 or 07:00 in
# Lisbon as the two switch to summer time on different days. The gate counts the same days.
QUOTA_ZONE = ZoneInfo("America/Los_Angeles")
# Every error the page may show, by a code it words in its own language (web/src/i18n.ts,
# `errors`); here in Portuguese, for any other client. `{hour}`: when the day's quota renews.
ERRORS = {
    "future_date": "A data não pode ser futura: a lei desse dia não é conhecida.",
    "before_corpus": (
        "O Lex guarda a lei do arrendamento desde 27/06/2006 e o Código do Trabalho desde "
        "17/02/2009, quando entrou em vigor."
    ),
    "day_cap": "O Lex já respondeu a todas as perguntas que pode hoje. Volte depois das {hour}.",
    "visitor_hour": "Fez muitas perguntas na última hora. Tente de novo mais tarde.",
    "quota_day": (
        "O limite diário gratuito do modelo foi atingido; renova às {hour}, hora de Lisboa. "
        "Até lá, o separador Artigos continua a funcionar."
    ),
    "quota_minute": (
        "Há demasiados pedidos ao modelo neste minuto. Tente outra vez dentro de um minuto."
    ),
    "overloaded": (
        "O modelo está sobrecarregado neste momento, um problema passageiro do fornecedor. "
        "Tente outra vez dentro de instantes."
    ),
    "too_slow": "O modelo demorou demasiado a responder. Tente outra vez.",
    "unavailable": "O Lex não conseguiu responder agora. Tente mais tarde.",
    "no_articles": "Artigos indisponíveis.",
    "no_article": "Artigo não encontrado.",
    "no_search": "Pesquisa indisponível.",
    "no_changes": "Alterações indisponíveis.",
    "bad_period": "A data inicial tem de ser anterior à final.",
}


# Sent with every response, the page's and the API's: here, and written into vercel.json for
# the files Vercel's CDN serves (vercel/assemble.py). The page loads nothing from elsewhere and
# runs no inline script; its icon is a data: URI, and Preact sets styles from script.
SECURITY_HEADERS = {
    "Content-Security-Policy": (
        "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; connect-src 'self'; font-src 'self'; object-src 'none'; "
        "base-uri 'self'; form-action 'self'; frame-ancestors 'none'"
    ),
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "X-Frame-Options": "DENY",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
}


def renews(now: dt.datetime | None = None) -> str:
    """When the next quota day starts, as Lisbon's clock shows it: "08:00"."""
    here = (now or dt.datetime.now(dt.UTC)).astimezone(QUOTA_ZONE)
    midnight = dt.datetime.combine(here.date() + dt.timedelta(days=1), dt.time(), QUOTA_ZONE)
    return f"{midnight.astimezone(LISBON):%H:%M}"


def refuse(status: int, code: str, hour: str = "") -> HTTPException:
    """An error the page can word in either language: its code in X-Lex-Error, the hour the
    quota renews in X-Lex-Renews, and the Portuguese text as the detail."""
    headers = {"X-Lex-Error": code, **({"X-Lex-Renews": hour} if hour else {})}
    return HTTPException(status, ERRORS[code].format(hour=hour), headers=headers)


# The page's own paths besides /, which it routes on the client (web/src/App.tsx): each is served
# the page itself, so a link to the results or to an article opens on that view.
PAGES = ("/artigos", "/alteracoes", "/resultados", "/sobre")


def unavailable(error: Exception) -> str:
    """The code of what a visitor is told when the model or the embeddings fail, by the kind of
    failure. The client's errors carry the HTTP status, and Gemini names the quota it hit
    (...PerDay...)."""
    return {"timeout": "too_slow", "other": "unavailable"}.get(failure(error), failure(error))


def failure(error: Exception) -> str:
    """The kind of a failed answer, for the usage counts: the same reading as `unavailable`."""
    status = getattr(error, "status_code", None)
    if status == 429:
        return "quota_day" if "PerDay" in str(error) else "quota_minute"
    if isinstance(status, int) and status >= 500:
        return "overloaded"
    return "timeout" if "Timeout" in type(error).__name__ else "other"


def percentile(values: Sequence[float], share: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, round(share * (len(ordered) - 1)))]


class Usage:
    """What one instance of the API has answered since it started (Phase 8): counts by outcome,
    the latency of the answers it made, and their tokens and cost at paid prices. Vercel runs
    several instances and keeps none for long, so this is one instance's view, and says so."""

    def __init__(self, model: str, clock: Callable[[], dt.datetime]) -> None:
        self.model = model
        self.started = clock()
        self.counts: dict[str, int] = defaultdict(int)
        self.seconds: deque[float] = deque(maxlen=500)
        self.tokens: dict[str, int] = defaultdict(int)

    def record(self, outcome: str, seconds: float = 0.0, tokens: Mapping[str, int] = {}) -> None:
        self.counts[outcome] += 1
        if outcome == "answered":
            self.seconds.append(seconds)
        for name, value in tokens.items():
            self.tokens[name] += value
        cost = llm.usd(dict(tokens), self.model) if tokens else None
        line = {"event": "answer", "outcome": outcome, "seconds": seconds, **tokens}
        if cost is not None:
            line["usd"] = round(cost, 6)
        print(json.dumps(line), flush=True)  # one line per answer in the platform's log

    def report(self) -> dict[str, Any]:
        cost = llm.usd(dict(self.tokens), self.model)
        return {
            "scope": "this instance of the API, since it started; others count their own",
            "since": self.started.isoformat(timespec="seconds"),
            "counts": dict(self.counts),
            "latency_seconds": {
                "answers": len(self.seconds),
                "p50": percentile(self.seconds, 0.5),
                "p95": percentile(self.seconds, 0.95),
            },
            "tokens": dict(self.tokens),
            "usd_at_paid_prices": None if cost is None else round(cost, 6),
            "model": self.model,
        }


class Question(BaseModel):
    question: str = Field(min_length=3, max_length=1000)
    as_of: dt.date | None = None  # today when left out


class Reply(BaseModel):
    question: str
    as_of: dt.date
    system: str
    answer: Answer
    seconds: float  # how long the system took, measured on the server; 0 when cached
    cached: bool = False
    disclaimer: str = DISCLAIMER


class Version(Protocol):
    """An article version as the page shows it (lex.store's ArticleVersion fits)."""

    @property
    def heading(self) -> str: ...
    @property
    def text(self) -> str: ...
    @property
    def valid_from(self) -> dt.date: ...
    @property
    def valid_to(self) -> dt.date | None: ...
    @property
    def introduced_by(self) -> str: ...
    @property
    def source_url(self) -> str: ...


# Every version of an article, oldest first.
Library = Callable[[str, str], Sequence[Version]]


class Found(Protocol):
    """An article a word search found (lex.store's ArticleVersion fits)."""

    @property
    def diploma(self) -> str: ...
    @property
    def article(self) -> str: ...
    @property
    def heading(self) -> str: ...
    @property
    def text(self) -> str: ...
    @property
    def introduced_by(self) -> str: ...
    @property
    def valid_from(self) -> dt.date: ...


# Articles in force on a date whose words match a query, best first; no model involved.
Find = Callable[[str, dt.date, int], Sequence[Found]]


# A diploma's article versions that came into force in a period, with what each did.
Changes = Callable[[str, dt.date, dt.date], Sequence[tuple[Found, str]]]


class ChangedArticle(BaseModel):
    article: str
    heading: str
    kind: str  # "changed", "added", "revoked" or "original"


class ChangeGroup(BaseModel):
    """What one diploma changed on one day."""

    introduced_by: str
    valid_from: dt.date
    articles: list[ChangedArticle]


class ChangesView(BaseModel):
    diploma: str
    since: dt.date
    until: dt.date
    groups: list[ChangeGroup]


class Hit(BaseModel):
    diploma: str
    article: str
    heading: str
    # The line of the text that holds the words, and where they are in it, as [start, end).
    excerpt: str = ""
    marks: list[tuple[int, int]] = []


class Period(BaseModel):
    valid_from: dt.date
    valid_to: dt.date | None
    introduced_by: str


class ArticleView(BaseModel):
    diploma: str
    article: str
    as_of: dt.date
    heading: str | None  # None when no version was in force on as_of
    text: str | None
    source_url: str | None
    versions: list[Period]
    notes: list[str] = []  # the DR's notes on the version's effects (deferred, suspended, ruled on)
    disclaimer: str = DISCLAIMER


@dataclass(frozen=True)
class Limits:
    per_visitor_per_hour: int = 20
    per_day: int = 400  # all visitors together, under the free-tier quotas (ADR 0020)
    cached_answers: int = 1000


class Gate:
    """Counts answers per visitor over the last hour and in total per day."""

    def __init__(
        self, limits: Limits, clock: Callable[[], float], today: Callable[[], dt.date]
    ) -> None:
        self.limits = limits
        self.clock = clock
        self.today = today
        self.recent: dict[str, deque[float]] = defaultdict(deque)
        self.day = today()
        self.used_today = 0

    def admit(self, visitor: str) -> str | None:
        """None if the visitor may ask now, else why not, as an error code (ERRORS)."""
        now, today = self.clock(), self.today()
        if today != self.day:
            self.day, self.used_today = today, 0
        if self.used_today >= self.limits.per_day:
            return "day_cap"
        times = self.recent[visitor]
        while times and now - times[0] >= 3600:
            times.popleft()
        if len(times) >= self.limits.per_visitor_per_hour:
            return "visitor_hour"
        times.append(now)
        self.used_today += 1
        return None

    def refund(self, visitor: str) -> None:
        """Give back an admission whose answer failed: the visitor got nothing for it."""
        if self.recent[visitor]:
            self.recent[visitor].pop()
        self.used_today = max(0, self.used_today - 1)


def cache_key(question: str, as_of: dt.date) -> tuple[str, dt.date]:
    """Questions that differ only in spacing or case share an answer."""
    return " ".join(question.split()).lower(), as_of


def visitor(request: Request, behind_proxy: bool) -> str:
    """The client's address. Behind a proxy that sets them (Vercel's), from its headers:
    x-real-ip, else the last X-Forwarded-For entry, which the nearest proxy added (the first can
    be anything the client sent). Anywhere else a client can send those headers itself, to dodge
    the per-visitor limit, so only the connection's own address counts."""
    connection = request.client.host if request.client else "unknown"
    if not behind_proxy:
        return connection
    real = request.headers.get("x-real-ip", "").strip()
    forwarded = [a.strip() for a in request.headers.get("x-forwarded-for", "").split(",")]
    return real or forwarded[-1] or connection


def leaderboard(directory: Path) -> list[dict[str, Any]]:
    """The newest test run of each system and task, newest first; superseded runs (a subfolder)
    are left out. Correctness, where a judge scored it, comes with how the judge was measured."""
    newest: dict[tuple[str, str], dict[str, Any]] = {}
    for path in directory.glob("*.json"):
        run = json.loads(path.read_text(encoding="utf-8"))
        config = run["config"]
        summary = dict(run["summary"])
        judged = config.get("judge")
        entry = {
            "system": run["system"],
            "task": config.get("task", "retrieval"),
            "llm": config.get("llm"),
            "run_at": run["run_at"],
            "commit": run["commit"][:7],
            "summary": summary,
            "correctness": summary.pop("correctness", None),
            "judge": (
                {"model": judged["model"], "measured_on_dev": judged["measured_on_dev"]}
                if judged
                else None
            ),
        }
        key = (entry["system"], entry["task"])
        if key not in newest or _when(entry) > _when(newest[key]):
            newest[key] = entry
    return sorted(newest.values(), key=_when, reverse=True)


def _when(entry: dict[str, Any]) -> dt.datetime:
    return dt.datetime.fromisoformat(entry["run_at"])


def create_app(
    system: System,
    library: Library | None = None,
    find: Find | None = None,
    leaderboard: list[dict[str, Any]] | None = None,
    limits: Limits | None = None,
    static: Path | None = None,
    preload: Mapping[tuple[str, dt.date], Answer] | None = None,
    changes: Changes | None = None,
    today: Callable[[], dt.date] = lambda: lisbon_today(),
    clock: Callable[[], float] = time.monotonic,
    serial: bool = True,
    quota_day: Callable[[], dt.date] = lambda: dt.datetime.now(QUOTA_ZONE).date(),
    behind_proxy: bool = False,
    now: Callable[[], dt.datetime] = lambda: dt.datetime.now(dt.UTC),
    build: Mapping[str, Any] | None = None,
) -> FastAPI:
    """`serial` answers one question at a time, for systems whose parts are not safe to share
    between threads (a Postgres connection, local models); the serverless demo's are. `preload`
    seeds the answer cache, with answers made at deploy for the page's examples."""
    app = FastAPI(title="Lex", description=DISCLAIMER)

    @app.middleware("http")
    async def secured(request: Request, call_next: Callable[[Request], Any]) -> Response:
        response: Response = await call_next(request)
        response.headers.update(SECURITY_HEADERS)
        return response

    limits = limits or Limits()
    state = threading.Lock()  # the gate and the answer cache
    one_at_a_time = threading.Lock()
    gate = Gate(limits, clock, quota_day)  # its day is the quota's, not Lisbon's
    priced = next((m for m in llm.PRICES if m in system.name), "")
    usage = Usage(priced, lambda: dt.datetime.now(dt.UTC))
    answers: OrderedDict[tuple[str, dt.date], Answer] = OrderedDict(
        (cache_key(q, day), a) for (q, day), a in (preload or {}).items()
    )

    def run(question: str, as_of: dt.date) -> Answer:
        if not serial:
            return system.answer(question, as_of)
        with one_at_a_time:
            return system.answer(question, as_of)

    # When this instance started: a probe that finds it younger than its own requests met a
    # cold start (lex.probe). `build`: the commit and corpus deployed (vercel/assemble.py).
    started_at = now().isoformat(timespec="seconds")

    @app.get("/api/health")
    def health() -> dict[str, Any]:
        return {
            "status": "ok",
            "system": system.name,
            "today": today().isoformat(),
            "started_at": started_at,
            "build": dict(build) if build else None,
        }

    @app.post("/api/answer")
    def answer(question: Question, request: Request) -> Reply:
        as_of = question.as_of or today()
        if as_of > today():
            raise refuse(422, "future_date")
        if as_of < FIRST_DAY:
            raise refuse(422, "before_corpus")
        key = cache_key(question.question, as_of)
        who = visitor(request, behind_proxy)
        with state:
            result = answers.get(key)
            if result is not None:
                answers.move_to_end(key)
                usage.record("cached")
                return Reply(
                    question=question.question,
                    as_of=as_of,
                    system=system.name,
                    answer=result,
                    seconds=0,
                    cached=True,
                )
            refusal = gate.admit(who)
        if refusal:
            usage.record("limited")
            raise refuse(429, refusal, renews(now()))
        started = time.perf_counter()
        try:
            # The model's reason for a refusal cites nothing: never shown, never kept here.
            result = run(question.question, as_of).model_copy(update={"reason": ""})
        except Exception as error:  # the model's quota or service; the visitor sees why
            print(f"answer failed: {type(error).__name__}: {error}", flush=True)
            usage.record(f"failed_{failure(error)}")
            with state:
                gate.refund(who)
            raise refuse(503, unavailable(error), renews(now())) from error
        with state:
            answers[key] = result
            if len(answers) > limits.cached_answers:
                answers.popitem(last=False)
        seconds = round(time.perf_counter() - started, 2)
        usage.record("answered", seconds, result.tokens)
        return Reply(
            question=question.question,
            as_of=as_of,
            system=system.name,
            answer=result,
            seconds=seconds,
        )

    @app.get("/api/usage")
    def used() -> dict[str, Any]:
        """What this instance has answered since it started: outcomes, latency, tokens, cost."""
        with state:
            return usage.report()

    @app.get("/api/articles/{diploma}/{article}")
    def article(diploma: str, article: str, as_of: dt.date | None = None) -> ArticleView:
        if library is None:
            raise refuse(404, "no_articles")
        day = as_of or today()
        versions = library(diploma, article)
        if not versions:
            raise refuse(404, "no_article")
        current = next(
            (
                v
                for v in versions
                if v.valid_from <= day and (v.valid_to is None or day < v.valid_to)
            ),
            None,
        )
        return ArticleView(
            diploma=diploma,
            article=article,
            as_of=day,
            heading=current.heading if current else None,
            text=current.text if current else None,
            source_url=current.source_url if current else None,
            notes=list(getattr(current, "notes", [])),  # a version that keeps none: none
            versions=[
                Period(valid_from=v.valid_from, valid_to=v.valid_to, introduced_by=v.introduced_by)
                for v in versions
            ],
        )

    @app.get("/api/search")
    def search(
        q: str, as_of: dt.date | None = None, k: int = 20, diploma: str | None = None
    ) -> list[Hit]:
        """Browse the corpus by words, with no model and no quota; `diploma` keeps one."""
        if find is None:
            raise refuse(404, "no_search")
        k = max(1, min(k, 50))
        found = [
            f for f in find(q[:200], as_of or today(), 200) if diploma in (None, "", f.diploma)
        ][:k]
        hits = []
        for f in found:
            text, marks = excerpt(f.text, q[:200])
            hits.append(
                Hit(
                    diploma=f.diploma,
                    article=f.article,
                    heading=f.heading,
                    excerpt=text,
                    marks=marks,
                )
            )
        return hits

    @app.get("/api/changes")
    def changed(diploma: str, since: dt.date, until: dt.date | None = None) -> ChangesView:
        """What changed in a diploma after `since` and by `until` (today if left out), grouped
        by the diploma that changed it and the day it took effect; no model, no quota."""
        if changes is None:
            raise refuse(404, "no_changes")
        end = until or today()
        if not since < end:
            raise refuse(422, "bad_period")
        groups: dict[tuple[str, dt.date], list[ChangedArticle]] = {}
        for version, kind in changes(diploma, since, end):
            key = (version.introduced_by, version.valid_from)
            groups.setdefault(key, []).append(
                ChangedArticle(article=version.article, heading=version.heading, kind=kind)
            )
        return ChangesView(
            diploma=diploma,
            since=since,
            until=end,
            groups=[
                ChangeGroup(introduced_by=by, valid_from=day, articles=arts)
                for (by, day), arts in groups.items()
            ],
        )

    @app.get("/api/leaderboard")
    def board() -> list[dict[str, Any]]:
        return leaderboard or []

    if static is not None:
        index = static / "index.html"

        def page() -> FileResponse:
            return FileResponse(index, media_type="text/html")

        for path in PAGES:
            app.get(path, include_in_schema=False)(page)

        @app.exception_handler(StarletteHTTPException)
        async def not_found(request: Request, error: StarletteHTTPException) -> Response:
            """A path that is no page gets the page, which says so, with a 404; the API keeps
            its own errors."""
            if error.status_code == 404 and not request.url.path.startswith("/api/"):
                return FileResponse(index, status_code=404, media_type="text/html")
            return await http_exception_handler(request, error)

        app.mount("/", StaticFiles(directory=static, html=True), name="page")
    return app
