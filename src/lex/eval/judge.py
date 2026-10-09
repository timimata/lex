"""Answer correctness: a language model compares a system's answer with the benchmark's reference
answer, and says correct, partial or wrong.

CLAUDE.md: a judge's scores are reported only next to how the judge was measured on dev. Hand
labels live in bench/labels/dev.jsonl, one per (item, answer); `agreement` compares the judge
with them. Without them, `known_cases` builds answers whose verdict is known by construction, and
the judge must pass them first (ADR 0015). The judge is a different model from the one that
answers, so it does not grade its own writing.
"""

import datetime as dt
import hashlib
import json
import re
from collections import Counter, defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from lex.bench.schema import Item

VERDICTS = ("correta", "parcial", "errada")
# An open model, of another family than the answers' Gemini, free on the same API (ADR 0015).
JUDGE_MODEL = "gemma-4-26b-a4b-it"
LABELS = Path(__file__).resolve().parents[3] / "bench" / "labels" / "dev.jsonl"

SYSTEM = """\
Avalias respostas a perguntas sobre a lei portuguesa (o Código do Trabalho e o arrendamento). \
Recebes a pergunta, a data a que se refere, a resposta de referência (certa, escrita a partir da \
lei em vigor nessa data) e a resposta de um sistema. Julga só o conteúdo jurídico da resposta do \
sistema face à referência.

- "correta": diz o essencial da referência (os mesmos direitos, prazos, números e condições) e \
nada que a contradiga. Pode dizer mais, desde que não seja errado face à referência.
- "parcial": acerta em parte do essencial, mas falta algo que a pergunta pedia, ou tem um erro \
menor que não muda a conclusão.
- "errada": contradiz a referência, erra um número, prazo ou condição que muda a conclusão, ou \
não responde ao que foi perguntado.

A lista de fontes no fim da resposta do sistema não conta. Responde apenas com um objeto JSON:
{"veredicto": "correta" | "parcial" | "errada", "razao": "uma frase"}"""


class Reply(Protocol):
    @property
    def text(self) -> str: ...


class Model(Protocol):
    name: str

    def complete(self, system: str, user: str) -> Reply: ...


def answer_sha(text: str) -> str:
    """Identifies the answer a label or verdict is about: a label holds for that wording only."""
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def prompt(item: Item, answer: str) -> str:
    return (
        f"Pergunta: {item.question}\n"
        f"Data: {item.as_of:%d/%m/%Y}\n\n"
        f"Resposta de referência:\n{item.answer}\n\n"
        f"Resposta do sistema:\n{answer}"
    )


@dataclass(frozen=True)
class Judged:
    verdict: str
    reason: str  # the judge's sentence ("razao"), or why there is none
    verdicts: tuple[str, ...] = ()  # each sample's, where the judge was asked more than once


def median(verdicts: Sequence[str]) -> str:
    """The middle verdict, in the order correta, parcial, errada: with three samples, the
    majority's, or `parcial` when all three differ; with two that differ, the stricter."""
    ordered = sorted(verdicts, key=VERDICTS.index)
    return ordered[len(ordered) // 2]


# The reasons given where the judge was not asked, or gave no verdict.
REFUSED = "recusou: errada sem perguntar ao juiz"
UNPARSED = "sem veredicto legível na resposta do juiz: contada como errada"


def parse_reply(reply: str) -> Judged | None:
    """The verdict and reason in a judge's reply, or None if it gave no verdict. A reasoning
    block before them (<thought>...</thought>) is skipped: a draft verdict there is not the
    judge's."""
    reply = reply.rsplit("</thought>", 1)[-1]
    decoder = json.JSONDecoder()
    for start in (i for i, ch in enumerate(reply) if ch == "{"):
        try:
            data, _ = decoder.raw_decode(reply, start)
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict) and data.get("veredicto") in VERDICTS:
            reason = data.get("razao")
            return Judged(str(data["veredicto"]), reason.strip() if isinstance(reason, str) else "")
    return None


def parse(reply: str) -> str | None:
    """The verdict alone (`parse_reply`)."""
    found = parse_reply(reply)
    return found.verdict if found else None


class Judge:
    """The judge, asked once per answer, or once per sample (`samples`, models whose caches keep
    other draws), the verdict being the samples' median. A reply with no verdict is asked again of
    `retry`, if given, and an answer left with none is counted and its id kept."""

    def __init__(
        self, model: Model, samples: Sequence[Model] = (), retry: Model | None = None
    ) -> None:
        self.models = [model, *samples]
        self.retry = retry
        self.name = model.name
        self.unparsed = 0
        self.unparsed_ids: list[str] = []  # answers a sample gave no verdict on, even asked again
        self.retried_ids: list[str] = []  # answers a sample had to be asked again about
        self.disagreed = 0  # answers whose samples did not all say the same

    def _ask(self, model: Model, item: Item, answer: str) -> Judged | None:
        found = parse_reply(model.complete(SYSTEM, prompt(item, answer)).text)
        if found is None and self.retry is not None:
            self.retried_ids.append(item.id)
            found = parse_reply(self.retry.complete(SYSTEM, prompt(item, answer)).text)
        return found

    def judged(self, item: Item, answer: str, refused: bool) -> Judged:
        """A refusal of an answerable question answers nothing: it is wrong without asking."""
        if refused:
            return Judged("errada", REFUSED)
        found = [j for j in (self._ask(m, item, answer) for m in self.models) if j is not None]
        if len(found) < len(self.models):
            self.unparsed_ids.append(item.id)
        if not found:
            self.unparsed += 1
            return Judged("errada", UNPARSED)
        verdicts = tuple(j.verdict for j in found)
        if len(set(verdicts)) > 1:
            self.disagreed += 1
        verdict = median(verdicts)
        reason = next(j.reason for j in found if j.verdict == verdict)
        return Judged(verdict, reason, verdicts if len(self.models) > 1 else ())

    def verdict(self, item: Item, answer: str, refused: bool) -> str:
        return self.judged(item, answer, refused).verdict


def correctness(verdicts: dict[str, str], types: dict[str, str]) -> dict[str, dict[str, float]]:
    """Share of answers judged correct, partial and wrong, over all and per question type."""
    groups: dict[str, list[str]] = defaultdict(list)
    for item_id, verdict in verdicts.items():
        groups["answerable"].append(verdict)
        groups[types[item_id]].append(verdict)
    summary = {}
    for name, found in sorted(groups.items(), key=lambda g: (g[0] != "answerable", g[0])):
        counts = Counter(found)
        summary[name] = {"items": len(found), **{v: counts[v] / len(found) for v in VERDICTS}}
    return summary


def agreement(pairs: list[tuple[str, str]]) -> dict[str, float | int]:
    """How often the judge's verdict equals the hand label, and Cohen's kappa, which discounts
    the agreement two raters would reach by chance given how often each uses each verdict."""
    n = len(pairs)
    if n == 0:
        raise ValueError("no hand labels to compare with")
    observed = sum(h == j for h, j in pairs) / n
    humans, judges = Counter(h for h, _ in pairs), Counter(j for _, j in pairs)
    chance = sum(humans[v] * judges[v] for v in VERDICTS) / (n * n)
    kappa = 1.0 if chance == 1 else (observed - chance) / (1 - chance)
    return {"items": n, "agreement": round(observed, 3), "kappa": round(kappa, 3)}


# Known-answer checks (ADR 0015, amended 2026-10-01): a reference answer as it is must be judged
# correct; the same answer with a quantity changed, or its yes or no turned over, must not.

# A number word and the different one it becomes; "um" and "uma" stay, being also "a".
NUMBER_WORDS = {
    "dois": "quatro",
    "duas": "quatro",
    "três": "seis",
    "quatro": "oito",
    "cinco": "oito",
    "seis": "nove",
    "sete": "dez",
    "oito": "doze",
    "nove": "doze",
    "dez": "quinze",
    "onze": "catorze",
    "doze": "dezoito",
    "quinze": "vinte",
    "vinte": "trinta",
    "trinta": "quarenta",
    "sessenta": "noventa",
    "noventa": "cento e vinte",
    "terceiro": "quinto",
    "quinto": "oitavo",
    "sétimo": "décimo",
}
# A number followed by what it counts. Article and law numbers, dates and decimals are never
# followed by one of these, so they are never changed.
QUANTITY = re.compile(
    r"(?<![\w,])(\d+|" + "|".join(NUMBER_WORDS) + r")"
    r"(?=\s(?:dias?|horas?|semanas?|meses|mês|anos?|minutos?|trabalhadores|vezes)\b|\s%)",
    re.IGNORECASE,
)
# Set before the first check ran: references and altered answers must each reach it. The
# lenient cases (2026-10-08) must reach it too, a bar committed before they first ran.
CHECK_PASS = 0.9


def changed_quantity(answer: str) -> str | None:
    """The answer with its first quantity changed ("15 dias" -> "22 dias", "onze horas" ->
    "catorze horas"), or None if it states none."""
    match = QUANTITY.search(answer)
    if match is None:
        return None
    found = match.group(1)
    if found.isdigit():
        new = str(int(found) + max(2, int(found) // 2))
    else:
        new = NUMBER_WORDS[found.lower()]
        if found[0].isupper():
            new = new[0].upper() + new[1:]
    return answer[: match.start(1)] + new + answer[match.end(1) :]


def flipped(answer: str) -> str | None:
    """A yes-or-no answer with its first word turned over and the rest left as it was."""
    for word, other in (("Sim", "Não"), ("Não", "Sim")):
        if re.match(rf"{word}\b", answer):
            return other + answer[len(word) :]
    return None


def contradicted(answer: str) -> str | None:
    """The reference answer whole, then a sentence that contradicts it: its first sentence with
    a quantity changed or its yes or no turned over, after "Contudo,". A judge that accepts it
    accepts an answer for holding the right sentence somewhere."""
    for sentence in re.split(r"(?<=[.!?])\s+", answer.strip()):
        other = changed_quantity(sentence) or flipped(sentence)
        if other:
            return f"{answer.strip()} Contudo, {other[0].lower()}{other[1:]}"
    return None


@dataclass(frozen=True)
class Case:
    id: str  # the item whose reference answer it is built from
    kind: str  # "reference", "number", "yes-no", "contradicted" or "other"
    answer: str
    expected: tuple[str, ...]  # the verdicts that count as the judge getting it right


ALTERED = ("number", "yes-no")  # a right answer made wrong in one place
LENIENT = ("contradicted", "other")  # wrong answers a lenient judge would let through


def known_cases(items: Iterable[Item]) -> list[Case]:
    """Each answerable item's reference answer as it is, altered where it can be, followed by a
    sentence contradicting it, and another item's reference answer in its place (ADR 0015,
    amended 2026-10-08): that one answers another question, so it is wrong."""
    answerable = [item for item in items if item.type != "unanswerable"]
    cases = []
    for n, item in enumerate(answerable):
        cases.append(Case(item.id, "reference", item.answer, ("correta",)))
        for kind, alter in (("number", changed_quantity), ("yes-no", flipped)):
            altered = alter(item.answer)
            if altered is not None:
                cases.append(Case(item.id, kind, altered, ("parcial", "errada")))
        if (contradiction := contradicted(item.answer)) is not None:
            cases.append(Case(item.id, "contradicted", contradiction, ("parcial", "errada")))
        # Halfway round the list, the first item that shares no article with this one.
        for step in range(len(answerable) // 2, len(answerable) + len(answerable) // 2):
            other = answerable[(n + step) % len(answerable)]
            if other is not item and not set(other.must_cite) & set(item.must_cite):
                cases.append(Case(item.id, "other", other.answer, ("errada",)))
                break
    return cases


@dataclass(frozen=True)
class Checked:
    id: str
    kind: str
    answer: str
    verdict: str
    as_expected: bool
    reason: str = ""


def check_summary(checked: list[Checked]) -> dict[str, Any]:
    """Per kind of case, for the altered ones together and the lenient ones together: cases, how
    many the judge got right, and its verdicts; then whether it passed, each group at the bar."""
    groups: dict[str, list[Checked]] = defaultdict(list)
    for c in checked:
        groups[c.kind].append(c)
        if c.kind in ALTERED:
            groups["altered"].append(c)
        if c.kind in LENIENT:
            groups["lenient"].append(c)
    summary: dict[str, Any] = {}
    for name, found in groups.items():
        right = sum(c.as_expected for c in found)
        counts = Counter(c.verdict for c in found)
        summary[name] = {
            "cases": len(found),
            "as_expected": right,
            "share": round(right / len(found), 3),
            **{v: counts[v] for v in VERDICTS},
        }
    required = ["reference", "altered", *(["lenient"] if "lenient" in summary else [])]
    summary["passed"] = all(
        group in summary and summary[group]["share"] >= CHECK_PASS for group in required
    )
    return summary


def load_labels(path: Path | None = None) -> dict[tuple[str, str], str]:
    """(item id, answer sha) -> hand label."""
    path = path or LABELS
    if not path.exists():
        return {}
    labels = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            labels[(row["id"], row["answer_sha"])] = row["label"]
    return labels


def add_label(
    item_id: str, system: str, answer: str, label: str, by: str, path: Path | None = None
) -> None:
    path = path or LABELS
    if label not in VERDICTS:
        raise ValueError(f"not a verdict: {label!r}")
    row = {
        "id": item_id,
        "system": system,
        "answer_sha": answer_sha(answer),
        "label": label,
        "labeled_by": by,
        "labeled_on": dt.date.today().isoformat(),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
