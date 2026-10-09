import datetime as dt
import json
from dataclasses import dataclass
from pathlib import Path

import pytest

from lex.bench.schema import Item
from lex.domain import Citation
from lex.eval import judge


@dataclass(frozen=True)
class Reply:
    text: str


class Scripted:
    name = "scripted-judge"

    def __init__(self, reply: str) -> None:
        self.reply = reply
        self.prompts: list[str] = []

    def complete(self, system: str, user: str) -> Reply:
        self.prompts.append(user)
        return Reply(self.reply)


def item() -> Item:
    return Item.model_validate(
        {
            "id": "ct-0001",
            "question": "Quantos dias de férias tem um trabalhador por ano?",
            "as_of": "2026-09-29",
            "type": "simple",
            "must_cite": [{"diploma": "lei-7-2009", "article": "238"}],
            "answer": "O período anual de férias tem a duração mínima de 22 dias úteis.",
            "source": {"url": "https://example.org", "title": "Fonte", "retrieved": "2026-09-29"},
            "reviewed_by": "test",
        }
    )


def test_the_judge_reads_the_reference_and_the_answer() -> None:
    model = Scripted('```json\n{"veredicto": "parcial", "razao": "Falta o mínimo."}\n```')
    verdict = judge.Judge(model).verdict(item(), "São 22 dias.", refused=False)

    assert verdict == "parcial"
    [sent] = model.prompts
    assert "Data: 29/09/2026" in sent
    assert "22 dias úteis" in sent and sent.endswith("São 22 dias.")


def test_a_refusal_is_wrong_without_asking_and_an_unreadable_verdict_is_counted() -> None:
    model = Scripted("sem JSON")
    j = judge.Judge(model)

    assert j.verdict(item(), "Não encontrei base.", refused=True) == "errada"
    assert model.prompts == []
    assert j.verdict(item(), "Resposta.", refused=False) == "errada"
    assert j.unparsed == 1
    assert judge.parse('{"veredicto": "certa"}') is None  # not one of the three


def test_correctness_is_shared_out_by_type() -> None:
    verdicts = {"a": "correta", "b": "errada", "c": "correta", "d": "parcial"}
    types = {"a": "simple", "b": "simple", "c": "composite", "d": "composite"}
    summary = judge.correctness(verdicts, types)

    assert list(summary) == ["answerable", "composite", "simple"]
    assert summary["answerable"] == {"items": 4, "correta": 0.5, "parcial": 0.25, "errada": 0.25}
    assert summary["simple"]["correta"] == 0.5


def test_agreement_discounts_what_chance_would_give() -> None:
    pairs = [
        ("correta", "correta"),
        ("correta", "correta"),
        ("parcial", "parcial"),
        ("errada", "correta"),
    ]
    # observed 3/4; chance (2*3 + 1*1 + 1*0) / 16 = 7/16; kappa (0.75 - 0.4375) / 0.5625
    assert judge.agreement(pairs) == {"items": 4, "agreement": 0.75, "kappa": 0.556}
    with pytest.raises(ValueError):
        judge.agreement([])


def test_labels_are_kept_per_answer_wording(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(judge, "LABELS", tmp_path / "dev.jsonl")
    judge.add_label("ct-0001", "sys", "Resposta A.", "correta", "Pessoa")

    labels = judge.load_labels()
    assert labels == {("ct-0001", judge.answer_sha("Resposta A.")): "correta"}
    assert ("ct-0001", judge.answer_sha("Resposta B.")) not in labels  # another wording
    with pytest.raises(ValueError):
        judge.add_label("ct-0001", "sys", "Resposta A.", "boa", "Pessoa")
    assert dt.date.today().isoformat() in (tmp_path / "dev.jsonl").read_text(encoding="utf-8")


def test_a_quantity_changes_but_never_an_article_a_law_a_date_or_a_decimal() -> None:
    assert (
        judge.changed_quantity("Tem 10 dias úteis (art. 355.º).")
        == "Tem 15 dias úteis (art. 355.º)."
    )
    assert (
        judge.changed_quantity("Pelo menos onze horas seguidas.")
        == "Pelo menos catorze horas seguidas."
    )
    assert judge.changed_quantity("Cinco dias úteis.") == "Oito dias úteis."
    assert judge.changed_quantity("De 37,5 % e 50 % em feriado.") == "De 37,5 % e 75 % em feriado."
    assert judge.changed_quantity("A Lei n.º 23/2012 mudou o art. 234.º em 1 de agosto.") is None
    assert judge.changed_quantity("Até 15 de dezembro, em setembro ou dezembro.") is None


def test_only_a_first_yes_or_no_is_turned_over() -> None:
    assert judge.flipped("Sim, pode recusar.") == "Não, pode recusar."
    assert judge.flipped("Não. A lei mudou em 2012.") == "Sim. A lei mudou em 2012."
    assert judge.flipped("Simultaneamente, ambos.") is None
    assert judge.flipped("Em regra não.") is None


def test_known_cases_expect_the_reference_right_and_its_alterations_not() -> None:
    yes = item().model_copy(update={"id": "ct-0002", "answer": "Sim, desde 2009."})
    elsewhere = item().model_copy(
        update={
            "id": "ct-0003",
            "answer": "Não há prazo.",
            "must_cite": [Citation(diploma="lei-7-2009", article="99")],
        }
    )
    cases = judge.known_cases([item(), yes, elsewhere])

    assert [(c.id, c.kind, c.expected) for c in cases] == [
        ("ct-0001", "reference", ("correta",)),
        ("ct-0001", "number", ("parcial", "errada")),
        ("ct-0001", "contradicted", ("parcial", "errada")),
        ("ct-0001", "other", ("errada",)),
        ("ct-0002", "reference", ("correta",)),
        ("ct-0002", "yes-no", ("parcial", "errada")),
        ("ct-0002", "contradicted", ("parcial", "errada")),
        ("ct-0002", "other", ("errada",)),
        ("ct-0003", "reference", ("correta",)),
        ("ct-0003", "yes-no", ("parcial", "errada")),
        ("ct-0003", "contradicted", ("parcial", "errada")),
        ("ct-0003", "other", ("errada",)),
    ]
    by = {(c.id, c.kind): c.answer for c in cases}
    assert by[("ct-0001", "number")].endswith("33 dias úteis.")
    assert by[("ct-0002", "yes-no")] == "Não, desde 2009."
    # The right answer is all there, then contradicted.
    assert by[("ct-0002", "contradicted")] == "Sim, desde 2009. Contudo, não, desde 2009."
    assert by[("ct-0001", "contradicted")].startswith(item().answer + " Contudo, o ")
    # Another question's answer: never one about the same article.
    assert by[("ct-0001", "other")] == "Não há prazo."
    assert by[("ct-0003", "other")] in (item().answer, "Sim, desde 2009.")


def test_the_judge_passes_its_check_only_if_each_group_reaches_the_bar() -> None:
    def checked(kind: str, right: int, wrong: int) -> list[judge.Checked]:
        verdict = "correta" if kind == "reference" else "errada"
        other = "parcial" if kind == "reference" else "correta"
        return [judge.Checked("ct-0001", kind, "", verdict, True)] * right + [
            judge.Checked("ct-0001", kind, "", other, False)
        ] * wrong

    passing = judge.check_summary(
        checked("reference", 9, 1) + checked("number", 5, 0) + checked("yes-no", 4, 1)
    )
    assert passing["passed"]
    assert passing["altered"] == {
        "cases": 10,
        "as_expected": 9,
        "share": 0.9,
        "correta": 1,
        "parcial": 0,
        "errada": 9,
    }
    failing = judge.check_summary(checked("reference", 8, 2) + checked("number", 10, 0))
    assert not failing["passed"]  # 8 of 10 references accepted is below the bar


def test_a_draft_verdict_in_the_judges_reasoning_is_not_its_verdict() -> None:
    reply = (
        '<thought>Primeiro pensei {"veredicto": "correta"}, mas o prazo difere.</thought>'
        '```json\n{"veredicto": "errada", "razao": "Prazo errado."}\n```'
    )
    assert judge.parse(reply) == "errada"
    assert judge.parse('<thought>{"veredicto": "correta"}</thought>sem veredicto') is None


def test_the_judge_keeps_its_reason_and_says_why_when_it_was_not_asked() -> None:
    model = Scripted('{"veredicto": "parcial", "razao": "Falta o mínimo."}')
    j = judge.Judge(model)

    assert j.judged(item(), "São 22 dias.", refused=False) == judge.Judged(
        "parcial", "Falta o mínimo."
    )
    assert j.judged(item(), "Não sei.", refused=True) == judge.Judged("errada", judge.REFUSED)
    assert judge.Judge(Scripted("sem JSON")).judged(item(), "R.", refused=False).reason == (
        judge.UNPARSED
    )


def test_a_lenient_judge_fails_its_check() -> None:
    def checked(kind: str, right: int, wrong: int) -> list[judge.Checked]:
        good, bad = ("correta", "parcial") if kind == "reference" else ("errada", "correta")
        return [judge.Checked("ct-0001", kind, "", good, True)] * right + [
            judge.Checked("ct-0001", kind, "", bad, False)
        ] * wrong

    strict = checked("reference", 10, 0) + checked("number", 10, 0)
    assert judge.check_summary(strict + checked("other", 9, 1))["passed"]
    lenient = judge.check_summary(strict + checked("contradicted", 4, 6) + checked("other", 9, 1))
    assert lenient["lenient"]["as_expected"] == 13 and not lenient["passed"]


def test_correctness_is_refused_when_the_judge_was_measured_on_another_dev(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from lex.eval import gates, results

    check = {
        "bench": {"items": 2, "sha": "s", "scored": "dev-v2"},
        "config": {
            "judge": judge.JUDGE_MODEL,
            "judge_prompt": gates.prompt_version(),
            "judge_params": gates.JUDGE_PARAMS,
        },
        "summary": {
            "passed": True,
            "reference": {"as_expected": 2, "cases": 2},
            "altered": {"as_expected": 1, "cases": 1},
        },
    }
    (tmp_path / "dev").mkdir()
    (tmp_path / "dev" / "judge-check.json").write_text(json.dumps(check), encoding="utf-8")
    monkeypatch.setattr(results, "RESULTS", tmp_path)
    monkeypatch.setattr(results, "bench_version", lambda split: {"scored": "dev-v3"})
    with pytest.raises(SystemExit, match="another version of dev"):
        gates.measured_judge("x")

    monkeypatch.setattr(results, "bench_version", lambda split: {"scored": "dev-v2"})
    assert gates.measured_judge("x") == {
        "known_answer_checks": {
            "reference": {"as_expected": 2, "cases": 2},
            "altered": {"as_expected": 1, "cases": 1},
        }
    }


def said(verdict: str) -> Scripted:
    return Scripted(json.dumps({"veredicto": verdict, "razao": f"Por isso, {verdict}."}))


def test_several_samples_give_their_median_and_count_when_they_differ() -> None:
    assert judge.median(["correta", "errada", "correta"]) == "correta"
    assert judge.median(["correta", "parcial", "errada"]) == "parcial"
    assert judge.median(["correta", "errada"]) == "errada"  # two that differ: the stricter

    j = judge.Judge(said("correta"), [said("parcial"), said("correta")])
    found = j.judged(item(), "São 22 dias.", refused=False)
    assert found == judge.Judged("correta", "Por isso, correta.", ("correta", "parcial", "correta"))
    assert j.disagreed == 1
    assert judge.Judge(said("errada")).judged(item(), "R.", False).verdicts == ()


def test_a_reply_without_a_verdict_is_asked_again_and_its_id_kept() -> None:
    retry = said("parcial")
    j = judge.Judge(Scripted("sem JSON"), retry=retry)
    assert j.judged(item(), "R.", refused=False).verdict == "parcial"
    assert len(retry.prompts) == 1 and j.retried_ids == ["ct-0001"]
    assert j.unparsed_ids == [] and j.unparsed == 0

    lost = judge.Judge(Scripted("sem JSON"), retry=Scripted("nada"))
    assert lost.judged(item(), "R.", refused=False).reason == judge.UNPARSED
    assert lost.unparsed == 1 and lost.unparsed_ids == ["ct-0001"]
