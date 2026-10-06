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
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from lex.domain import Answer, System

DISCLAIMER = (
    "Os textos consolidados não têm valor legal: só faz fé a publicação no Diário da República. "
    "O Lex não é aconselhamento jurídico."
)
# From this day the corpus has every tenancy article's history (ADR 0017); the Código do
# Trabalho starts later, on 2009-02-17, and a question about it before then finds no article.
FIRST_DAY = dt.date(2006, 6, 27)
LISBON = ZoneInfo("Europe/Lisbon")
UNAVAILABLE = "O Lex não conseguiu responder agora. Tente mais tarde."
DAILY_LIMIT = (
    "O limite diário gratuito do modelo foi atingido; renova por volta das 8h, hora de Lisboa. "
    "Até lá, o separador Artigos continua a funcionar."
)
MINUTE_LIMIT = "Há demasiados pedidos ao modelo neste minuto. Tente outra vez dentro de um minuto."
OVERLOADED = (
    "O modelo está sobrecarregado neste momento, um problema passageiro do fornecedor. "
    "Tente outra vez dentro de instantes."
)
TOO_SLOW = "O modelo demorou demasiado a responder. Tente outra vez."
# The page's own paths besides /, which it routes on the client (web/src/App.tsx): each is served
# the page itself, so a link to the results or to an article opens on that view.
PAGES = ("/artigos", "/resultados", "/sobre")


def unavailable(error: Exception) -> str:
    """What a visitor is told when the model or the embeddings fail, by the kind of failure. The
    client's errors carry the HTTP status, and Gemini names the quota it hit (...PerDay...)."""
    status = getattr(error, "status_code", None)
    if status == 429:
        return DAILY_LIMIT if "PerDay" in str(error) else MINUTE_LIMIT
    if isinstance(status, int) and status >= 500:
        return OVERLOADED
    if "Timeout" in type(error).__name__:
        return TOO_SLOW
    return UNAVAILABLE


def lisbon_today(now: dt.datetime | None = None) -> dt.date:
    """The date in Lisbon at `now` (a timezone-aware instant, the current one by default)."""
    return (now or dt.datetime.now(dt.UTC)).astimezone(LISBON).date()


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


# Articles in force on a date whose words match a query, best first; no model involved.
Find = Callable[[str, dt.date, int], Sequence[Found]]


class Hit(BaseModel):
    diploma: str
    article: str
    heading: str


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
    disclaimer: str = DISCLAIMER


@dataclass(frozen=True)
class Limits:
    per_visitor_per_hour: int = 20
    per_day: int = 500  # all visitors together; keep it under the model's free-tier quota
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
        """None if the visitor may ask now, else why not (in PT-PT, shown on the page)."""
        now, today = self.clock(), self.today()
        if today != self.day:
            self.day, self.used_today = today, 0
        if self.used_today >= self.limits.per_day:
            return "O Lex já respondeu a todas as perguntas que pode hoje. Volte amanhã."
        times = self.recent[visitor]
        while times and now - times[0] >= 3600:
            times.popleft()
        if len(times) >= self.limits.per_visitor_per_hour:
            return "Fez muitas perguntas na última hora. Tente de novo mais tarde."
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


def visitor(request: Request) -> str:
    """The client's address, from headers the platform sets rather than the client: Vercel's
    x-real-ip, else the last X-Forwarded-For entry, which the nearest proxy added (the first can be
    anything the client sent), else the connection's own address."""
    real = request.headers.get("x-real-ip", "").strip()
    forwarded = [a.strip() for a in request.headers.get("x-forwarded-for", "").split(",")]
    return real or forwarded[-1] or (request.client.host if request.client else "unknown")


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
    today: Callable[[], dt.date] = lambda: lisbon_today(),
    clock: Callable[[], float] = time.monotonic,
    serial: bool = True,
) -> FastAPI:
    """`serial` answers one question at a time, for systems whose parts are not safe to share
    between threads (a Postgres connection, local models); the serverless demo's are. `preload`
    seeds the answer cache, with answers made at deploy for the page's examples."""
    app = FastAPI(title="Lex", description=DISCLAIMER)
    limits = limits or Limits()
    state = threading.Lock()  # the gate and the answer cache
    one_at_a_time = threading.Lock()
    gate = Gate(limits, clock, today)
    answers: OrderedDict[tuple[str, dt.date], Answer] = OrderedDict(
        (cache_key(q, day), a) for (q, day), a in (preload or {}).items()
    )

    def run(question: str, as_of: dt.date) -> Answer:
        if not serial:
            return system.answer(question, as_of)
        with one_at_a_time:
            return system.answer(question, as_of)

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "system": system.name, "today": today().isoformat()}

    @app.post("/api/answer")
    def answer(question: Question, request: Request) -> Reply:
        as_of = question.as_of or today()
        if as_of > today():
            raise HTTPException(422, "A data não pode ser futura: a lei desse dia não é conhecida.")
        if as_of < FIRST_DAY:
            raise HTTPException(
                422,
                "O Lex guarda a lei do arrendamento desde 27/06/2006 e o Código do Trabalho desde "
                "17/02/2009, quando entrou em vigor.",
            )
        key = cache_key(question.question, as_of)
        who = visitor(request)
        with state:
            result = answers.get(key)
            if result is not None:
                answers.move_to_end(key)
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
            raise HTTPException(429, refusal)
        started = time.perf_counter()
        try:
            result = run(question.question, as_of)
        except Exception as error:  # the model's quota or service; the visitor sees why
            print(f"answer failed: {type(error).__name__}: {error}", flush=True)
            with state:
                gate.refund(who)
            raise HTTPException(503, unavailable(error)) from error
        with state:
            answers[key] = result
            if len(answers) > limits.cached_answers:
                answers.popitem(last=False)
        seconds = round(time.perf_counter() - started, 2)
        print(f"answered in {seconds} s", flush=True)  # in the platform's logs, for latency
        return Reply(
            question=question.question,
            as_of=as_of,
            system=system.name,
            answer=result,
            seconds=seconds,
        )

    @app.get("/api/articles/{diploma}/{article}")
    def article(diploma: str, article: str, as_of: dt.date | None = None) -> ArticleView:
        if library is None:
            raise HTTPException(404, "Artigos indisponíveis.")
        day = as_of or today()
        versions = library(diploma, article)
        if not versions:
            raise HTTPException(404, "Artigo não encontrado.")
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
            versions=[
                Period(valid_from=v.valid_from, valid_to=v.valid_to, introduced_by=v.introduced_by)
                for v in versions
            ],
        )

    @app.get("/api/search")
    def search(q: str, as_of: dt.date | None = None, k: int = 20) -> list[Hit]:
        """Browse the corpus by words, with no model and no quota."""
        if find is None:
            raise HTTPException(404, "Pesquisa indisponível.")
        found = find(q[:200], as_of or today(), max(1, min(k, 50)))
        return [Hit(diploma=f.diploma, article=f.article, heading=f.heading) for f in found]

    @app.get("/api/leaderboard")
    def board() -> list[dict[str, Any]]:
        return leaderboard or []

    if static is not None:
        index = static / "index.html"

        def page() -> FileResponse:
            return FileResponse(index, media_type="text/html")

        for path in PAGES:
            app.get(path, include_in_schema=False)(page)
        app.mount("/", StaticFiles(directory=static, html=True), name="page")
    return app
