"""The gates an eval run passes before it starts (ROADMAP, Phases 9 and 10): the dev run a test
run stands on, how the judge was measured and on which dev, the demo's committed dev run. Apart
from the CLI (lex.eval.__main__), which builds the systems, so each is tested on its own.
"""

import hashlib
import json
import os
from pathlib import Path
from typing import Any

from lex.eval import judge, results

JUDGED = "judge-{}"  # results/dev/judge-<system>.json: verdicts on dev and their agreement
CHECK = "judge-check"  # results/dev/judge-check.json: the judge on known-answer cases


def judge_name() -> str:
    """The judge's model id: ADR 0015's, or JUDGE_MODEL from `.env` (a local server's name for
    it, ADR 0016's amendment). Another id is another judge, measured on dev again."""
    return os.environ.get("JUDGE_MODEL") or judge.JUDGE_MODEL


# Temperature 0: three samples agreed on all 67 dev answers, against 8 split at the provider's
# default, with every known-answer case as expected at both (ADR 0011, amended 2026-10-08).
JUDGE_PARAMS: dict[str, Any] = {"temperature": 0}


def judge_params() -> dict[str, Any]:
    """What the judge's requests send besides the prompt: JUDGE_PARAMS from `.env` as a JSON
    object ({} for the provider's defaults), or this module's. Other parameters are another
    judge, measured on dev apart (`checked_as`)."""
    given = os.environ.get("JUDGE_PARAMS")
    params: dict[str, Any] = json.loads(given) if given else dict(JUDGE_PARAMS)
    return params


def checked_as(params: dict[str, Any]) -> str:
    """The name of the known-answer check of a judge with these parameters: judge-check for
    the default ones, judge-check-temperature1 for {"temperature": 1}, judge-check-provider for
    none sent."""
    if params == JUDGE_PARAMS:
        return CHECK
    return CHECK + ("".join(f"-{k}{v}" for k, v in sorted(params.items())) or "-provider")


def prompt_version() -> str:
    return hashlib.sha256(judge.SYSTEM.encode()).hexdigest()[:12]


def dev_run(system: str) -> dict[str, Any]:
    path = results.RESULTS / "dev" / f"{system}.json"
    if not path.exists():
        raise SystemExit(f"no dev answers for {system}: run python -m lex.eval answers first")
    run: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    if run["config"].get("task") != "answers":
        raise SystemExit(f"{path.name} is not an answers run")
    return run


def measured_judge(system: str) -> dict[str, Any]:
    """How the judge, with today's model and prompt, was measured on dev: its agreement with hand
    labels on this system's answers or, without them, the known-answer checks it passed (ADR
    0015). Without either, correctness is not reported (CLAUDE.md)."""
    current = (judge_name(), prompt_version())
    dev = results.bench_version("dev")["scored"]  # a measurement on another dev is stale

    def on_dev(run: dict[str, Any]) -> bool:
        return bool(run["bench"].get("scored") == dev)

    labelled = results.RESULTS / "dev" / f"{JUDGED.format(system)}.json"
    if labelled.exists():
        run = json.loads(labelled.read_text(encoding="utf-8"))
        if (run["config"]["judge"], run["config"]["judge_prompt"]) != current:
            raise SystemExit("the judge or its prompt changed since it was measured: judge again")
        if run["config"].get("judge_params", {}) != judge_params():
            raise SystemExit("the judge's parameters changed since it was measured: judge again")
        if not on_dev(run):
            raise SystemExit("the judge was measured on another version of dev: judge again")
        return {"hand_labels": run["summary"]["agreement"]}
    checked = results.RESULTS / "dev" / f"{checked_as(judge_params())}.json"
    if checked.exists():
        run = json.loads(checked.read_text(encoding="utf-8"))
        if (run["config"]["judge"], run["config"]["judge_prompt"]) != current:
            raise SystemExit("the judge or its prompt changed since its check: judge-check again")
        if run["config"].get("judge_params", {}) != judge_params():
            raise SystemExit("the judge's parameters changed since its check: judge-check again")
        if not on_dev(run):
            raise SystemExit("the judge's check ran on another version of dev: judge-check again")
        if not run["summary"]["passed"]:
            raise SystemExit(
                "the judge failed its known-answer checks: correctness is not reported"
            )
        s = run["summary"]
        return {
            "known_answer_checks": {
                group: {"as_expected": s[group]["as_expected"], "cases": s[group]["cases"]}
                for group in ("reference", "altered", "lenient")
                if group in s
            }
        }
    raise SystemExit(
        f"the judge is not measured: python -m lex.eval judge {system} (after hand labels), "
        "or python -m lex.eval judge-check"
    )


def justifying_dev_run(name: str, expected: dict[str, Any]) -> dict[str, Any]:
    """The dev run a test run stands on (ROADMAP, Phase 10): the same system's, on today's dev,
    made with the same configuration, prompts included. A test run is refused without one, so no
    test number comes from something never measured on dev first."""
    path = results.RESULTS / "dev" / f"{name}.json"
    if not path.exists():
        raise SystemExit(f"no dev run of {name}: run it on dev first")
    run = json.loads(path.read_text(encoding="utf-8"))
    if run["bench"].get("scored") != results.bench_version("dev")["scored"]:
        raise SystemExit(f"{path.name} ran on another version of dev: run it on dev again")
    differs = sorted(k for k, v in expected.items() if run["config"].get(k) != v)
    if differs:
        raise SystemExit(f"{path.name} was made with another {', '.join(differs)}: run dev again")
    config = run["config"]
    return {
        "file": path.name,
        "commit": run["commit"],
        "run_at": run["run_at"],
        "prompts": config.get("prompts"),
    }


def demo_dev_run() -> Path | None:
    """The demo's latest dev answers run, if there is one (not a --repeat)."""
    paths = [
        p
        for p in (results.RESULTS / "dev").glob("dense-gemini-embedding-2+refs+*+agent.json")
        if "+repeat-" not in p.name
    ]
    return paths[0] if len(paths) == 1 else None
