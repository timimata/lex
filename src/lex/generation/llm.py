"""The language model behind answers (ADR 0011), and the disk cache every eval call goes through.

Any OpenAI-compatible chat endpoint works: Google's Gemini layer by default, or a local
llama.cpp, Ollama or LM Studio server. Tests use a scripted model instead.
"""

import datetime as dt
import hashlib
import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

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
        return Completion(
            text=response.choices[0].message.content or "",
            prompt_tokens=usage.prompt_tokens if usage else 0,
            completion_tokens=usage.completion_tokens if usage else 0,
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

    def __init__(self, llm: Llm, directory: Path) -> None:
        self.llm = llm
        self.name = llm.name
        self.params = llm.params
        self.directory = directory
        self.calls = 0
        self.cached = 0
        self.prompt_tokens = 0
        self.completion_tokens = 0

    def key(self, system: str, user: str) -> str:
        request = {"model": self.name, "params": self.params, "system": system, "user": user}
        return hashlib.sha256(json.dumps(request, sort_keys=True).encode()).hexdigest()

    def complete(self, system: str, user: str) -> Completion:
        key = self.key(system, user)
        path = self.directory / key[:2] / f"{key}.json"
        self.calls += 1
        if path.exists():
            record = json.loads(path.read_text(encoding="utf-8"))
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
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(record, ensure_ascii=False, indent=1), encoding="utf-8")
        self.prompt_tokens += completion.prompt_tokens
        self.completion_tokens += completion.completion_tokens
        return completion

    def usage(self) -> dict[str, int]:
        return {
            "calls": self.calls,
            "cached": self.cached,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
        }
