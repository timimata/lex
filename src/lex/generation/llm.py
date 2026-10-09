"""The language model behind answers (ADR 0011), and the disk cache every eval call goes through.

Any OpenAI-compatible chat endpoint works: Google's Gemini layer by default, or a local
llama.cpp, Ollama or LM Studio server. Tests use a scripted model instead.
"""

import datetime as dt
import hashlib
import json
import os
import time
import urllib.parse
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from lex import atomic

GEMINI_OPENAI_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"
DEFAULT_MODEL = "gemini-3.1-flash-lite"
DEFAULT_PARAMS: dict[str, Any] = {"reasoning_effort": "low"}  # ADR 0011; not tuned on dev
RATE_LIMIT_WAITS = (30, 60, 120)  # seconds; free tiers limit requests per minute
# "The model is overloaded" (a 5xx) comes back at once and usually passes within seconds. Under a
# time budget (the demo's), one that took longer than this to come back is not tried again.
QUICK_FAILURE = 5.0  # seconds
OVERLOAD_WAITS = (15, 30, 60)  # seconds; for eval runs, which can wait out a busy hour


@dataclass(frozen=True)
class Completion:
    text: str
    prompt_tokens: int
    completion_tokens: int
    # Gemini's `completion_tokens` leaves out the model's thinking, which is billed as output;
    # it is the rest of `total_tokens`. None: not recorded (cached before 2026-10-06).
    thinking_tokens: int | None = None


# USD per million tokens on the paid tier, input and output (thinking is billed as output), from
# ai.google.dev/gemini-api/docs/pricing, read 2026-10-06. The demo runs on the free tier, so
# this is what its answers would cost, not what they cost.
PRICES = {
    "gemini-3.1-flash-lite": (0.25, 1.50),
    # Gemini Embedding 2: text input; read 2026-10-08. Gemma 4 has no paid tier, so no price.
    "gemini-embedding-2": (0.20, 0.0),
}


def usd(tokens: dict[str, int], model: str) -> float | None:
    """What some tokens cost at the paid prices, thinking counted as output; None for a model
    with no price (a local one)."""
    if model not in PRICES:
        return None
    per_input, per_output = PRICES[model]
    output = tokens.get("completion_tokens", 0) + tokens.get("thinking_tokens", 0)
    return (tokens.get("prompt_tokens", 0) * per_input + output * per_output) / 1_000_000


def spent(completions: list[Completion]) -> dict[str, int]:
    """What some calls cost in tokens; "thinking_unrecorded" counts calls whose thinking is not
    known, so a cost from them is a lower bound."""
    return {
        "calls": len(completions),
        "prompt_tokens": sum(c.prompt_tokens for c in completions),
        "completion_tokens": sum(c.completion_tokens for c in completions),
        "thinking_tokens": sum(c.thinking_tokens or 0 for c in completions),
        "thinking_unrecorded": sum(c.thinking_tokens is None for c in completions),
    }


LOCAL_HOSTS = ("127.0.0.1", "localhost", "::1")


# Models Google serves on the free tier only: "Not available" under the paid tier on
# ai.google.dev/gemini-api/docs/pricing, read 2026-10-08. A paid key does not change their terms.
FREE_ONLY = ("gemma-",)


def endpoint(base_url: str, model: str = "") -> dict[str, str]:
    """Where a model's requests go and on which terms (ADR 0016, amended): the URL, and the
    tier of the key in `.env` (LLM_KEY_TIER, "free" unless it says "paid"), "free" whatever the
    key for a model with no paid tier, or "local" for a server on this machine, from which
    nothing leaves."""
    host = urllib.parse.urlsplit(base_url).hostname or ""
    if not base_url or host in LOCAL_HOSTS:  # no URL: a model in this process (tests)
        return {"url": base_url, "tier": "local"}
    paid = os.environ.get("LLM_KEY_TIER", "").strip().lower() == "paid"
    tier = "paid" if paid and not model.startswith(FREE_ONLY) else "free"
    return (
        {"url": base_url, "tier": tier, "model": model}
        if model
        else {"url": base_url, "tier": tier}
    )


class Llm(Protocol):
    name: str  # the model id, as the endpoint knows it
    params: dict[str, Any]  # sent with every request, and part of the cache key

    def complete(self, system: str, user: str) -> Completion: ...


class OpenAiCompatible:
    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        base_url: str = GEMINI_OPENAI_URL,
        api_key: str = "",
        params: dict[str, Any] | None = None,
        waits: tuple[int, ...] = RATE_LIMIT_WAITS,  # () for a visitor who should not wait
        timeout: float = 180,  # seconds per request
        max_retries: int = 2,  # the client's own quick retries of transient errors
        overload_waits: tuple[float, ...] = (),  # pauses before asking an overloaded model again
        quick_failure: float | None = None,  # if set, only a refusal this fast is tried again
        system_as_user: bool = False,  # for models served without system instructions (Gemma)
    ) -> None:
        from openai import OpenAI  # the optional `llm` extra

        self.waits = waits
        self.overload_waits = overload_waits
        self.quick_failure = quick_failure
        self.system_as_user = system_as_user
        self.base_url = base_url
        self.name = model
        self.params = dict(DEFAULT_PARAMS if params is None else params)
        # A local server ignores the key but the client insists on one.
        self.client = OpenAI(
            base_url=base_url, api_key=api_key or "none", timeout=timeout, max_retries=max_retries
        )

    def complete(self, system: str, user: str) -> Completion:
        from openai import InternalServerError, RateLimitError

        messages = (
            [{"role": "user", "content": f"{system}\n\n{user}"}]
            if self.system_as_user
            else [{"role": "system", "content": system}, {"role": "user", "content": user}]
        )
        limited, overloaded = iter(self.waits), iter(self.overload_waits)
        while True:
            started = time.perf_counter()
            try:
                response = self.client.chat.completions.create(
                    model=self.name,
                    messages=messages,  # type: ignore[arg-type]
                    **self.params,
                )
                break
            except RateLimitError:
                wait: float | None = next(limited, None)
                if wait is None:
                    raise
            except InternalServerError:
                took = time.perf_counter() - started
                slow = self.quick_failure is not None and took > self.quick_failure
                wait = None if slow else next(overloaded, None)
                if wait is None:
                    raise
            time.sleep(wait)
        usage = response.usage
        prompt, completion = (usage.prompt_tokens, usage.completion_tokens) if usage else (0, 0)
        total = usage.total_tokens if usage else 0
        return Completion(
            text=response.choices[0].message.content or "",
            prompt_tokens=prompt,
            completion_tokens=completion,
            thinking_tokens=max(0, total - prompt - completion),
        )


def from_env(
    waits: tuple[int, ...] = RATE_LIMIT_WAITS,
    timeout: float = 180,
    max_retries: int = 2,
    overload_waits: tuple[float, ...] = (),
    quick_failure: float | None = None,
) -> OpenAiCompatible:
    """The model `.env` names (LLM_MODEL, LLM_BASE_URL, LLM_API_KEY, and LLM_PARAMS as a JSON
    object), Gemini by default."""
    params = os.environ.get("LLM_PARAMS")
    return OpenAiCompatible(
        model=os.environ.get("LLM_MODEL") or DEFAULT_MODEL,
        base_url=os.environ.get("LLM_BASE_URL") or GEMINI_OPENAI_URL,
        api_key=os.environ.get("LLM_API_KEY", ""),
        params=json.loads(params) if params else None,
        waits=waits,
        timeout=timeout,
        max_retries=max_retries,
        overload_waits=overload_waits,
        quick_failure=quick_failure,
    )


class Cached:
    """Answers a repeated (model, params, prompt) from disk, so re-running an eval is free and
    gives the same answers. Counts what the run cost, cached answers included."""

    def __init__(self, llm: Llm, directory: Path, repeat: int = 0, sample: str = "") -> None:
        self.llm = llm
        # A repeat (1, 2, ...) asks every prompt again, a fresh sample kept apart from the first:
        # what two runs of the same system differ by is the noise any comparison stands on.
        self.repeat = repeat
        # A named sample ("fresh-2026-10-08") asks every prompt again too, without renaming the
        # system: how a milestone gets answers made that day, which a re-run of it reuses.
        self.sample = sample
        self.name = llm.name
        self.params = llm.params
        self.base_url: str = getattr(llm, "base_url", "")
        self.directory = directory
        self.calls = 0
        self.cached = 0
        self.completions: list[Completion] = []
        self.made: list[str] = []  # when each response used was made, cached ones included
        self.broken = 0  # cache entries that no longer read, set aside and asked again

    def key(self, system: str, user: str) -> str:
        request: dict[str, object] = {
            "model": self.name,
            "params": self.params,
            "system": system,
            "user": user,
        }
        if self.repeat:
            request["repeat"] = self.repeat
        if self.sample:
            request["sample"] = self.sample
        return hashlib.sha256(json.dumps(request, sort_keys=True).encode()).hexdigest()

    def complete(self, system: str, user: str) -> Completion:
        key = self.key(system, user)
        path = self.directory / key[:2] / f"{key}.json"
        self.calls += 1
        record = self._read(path)
        if record is not None:
            completion = Completion(**record["completion"])
            self.cached += 1
        else:
            completion = self.llm.complete(system, user)
            record = {
                "model": self.name,
                "params": self.params,
                "system": system,
                "user": user,
                "completion": completion.__dict__,
                "made_at": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
            }
            atomic.write_text(path, json.dumps(record, ensure_ascii=False, indent=1))
        self.completions.append(completion)
        self.made.append(str(record.get("made_at", "")))
        return completion

    def _read(self, path: Path) -> dict[str, Any] | None:
        """The cached record, or None to ask the model: a missing entry, or one that no longer
        reads (written before writes were atomic), which is set aside unread and counted."""
        if not path.exists():
            return None
        try:
            record: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
            Completion(**record["completion"])
        except (ValueError, KeyError, TypeError):
            atomic.set_aside(path)
            self.broken += 1
            return None
        return record

    def usage(self) -> dict[str, int]:
        return {**spent(self.completions), "cached": self.cached}

    def dates(self) -> dict[str, Any]:
        """How many responses the run used, how many came from the cache, and when the oldest
        and newest were made: the cache key has no date, so a model its provider changed under
        the same name would answer from the past unseen (ROADMAP, Phase 9)."""
        made = sorted(m for m in self.made if m)
        return {
            "calls": self.calls,
            "cached": self.cached,
            "broken": self.broken,
            "sample": self.sample or None,
            "made_from": made[0] if made else None,
            "made_until": made[-1] if made else None,
        }
