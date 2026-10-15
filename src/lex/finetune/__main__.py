"""python -m lex.finetune generate | train

BGE-M3 fine-tuned on synthetic questions about the corpus (ADR 0024). `generate` asks the answer
model for questions a citizen could ask of each article in force, ten articles a call, through
the eval's LLM cache; `train` fine-tunes BGE-M3 on (question, article) pairs, in-batch negatives,
one epoch. Both write under data/ (not committed; rebuilt by these commands). No benchmark item
is read: the questions are synthetic and live outside bench/ (CLAUDE.md).
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from lex.finetune.model import MODEL, weights_sha
from lex.generation import llm
from lex.retrieval.dense import BGE_M3, BGE_M3_REVISION, PLAIN_DOCUMENT, document

ROOT = Path(__file__).resolve().parents[3]
PROCESSED = ROOT / "data" / "processed"
QUESTIONS = ROOT / "data" / "synthetic" / "questions.jsonl"
PER_CALL = 10  # articles a request: ~80 requests for the corpus, within a day's free quota
PER_ARTICLE = 3
# Fixed before any dev run, not tuned on dev (ADR 0024).
EPOCHS, BATCH, LEARNING_RATE, MAX_LENGTH, SEED = 1, 16, 1e-5, 384, 0

SYSTEM = (
    "És um gerador de perguntas para treinar um sistema de pesquisa de legislação portuguesa. "
    "Para cada artigo dado, escreve {n} perguntas diferentes, em português europeu, que um "
    "cidadão faria e a que esse artigo responde. Não cites o número do artigo nem o nome do "
    "diploma; escreve como quem não conhece a lei. Responde só com JSON: uma lista de objetos "
    '{{"id": ..., "perguntas": [...]}}, um por artigo, pela ordem dada.'
)


def in_force(processed: Path = PROCESSED) -> list[dict[str, Any]]:
    """The article versions in force today with text worth asking about: not revoked, not
    empty."""
    rows = []
    for path in sorted(processed.glob("*/versions.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            row = json.loads(line)
            text = row["text"].strip()
            if row["valid_to"] is None and len(text) > 40 and not text.startswith("(Revogad"):
                rows.append(row)
    return rows


def prompt(rows: list[dict[str, Any]]) -> str:
    return "\n\n".join(
        f'<artigo id="{r["diploma"]}:{r["article"]}">\n{r["heading"]}\n{r["text"]}</artigo>'
        for r in rows
    )


def parse(reply: str, rows: list[dict[str, Any]]) -> list[dict[str, str]]:
    """(question, article id) pairs from a reply; articles it skipped or garbled give none."""
    start, end = reply.find("["), reply.rfind("]")
    if start < 0 or end < start:
        return []
    try:
        found = json.loads(reply[start : end + 1])
    except json.JSONDecodeError:
        return []
    ids = {f"{r['diploma']}:{r['article']}" for r in rows}
    pairs = []
    for entry in found if isinstance(found, list) else []:
        article = str(entry.get("id", "")) if isinstance(entry, dict) else ""
        questions = entry.get("perguntas", []) if isinstance(entry, dict) else []
        if article in ids and isinstance(questions, list):
            pairs += [
                {"question": q.strip(), "article": article} for q in questions if str(q).strip()
            ]
    return pairs


def generate(model: llm.Llm, out: Path = QUESTIONS) -> int:
    rows = in_force()
    pairs: list[dict[str, str]] = []
    system = SYSTEM.format(n=PER_ARTICLE)
    for start in range(0, len(rows), PER_CALL):
        chunk = rows[start : start + PER_CALL]
        pairs += parse(model.complete(system, prompt(chunk)).text, chunk)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("".join(json.dumps(p, ensure_ascii=False) + "\n" for p in pairs), "utf-8")
    return len(pairs)


def train(questions: Path = QUESTIONS, out: Path = MODEL) -> str:
    """Fine-tune BGE-M3 on the pairs, the other questions of each batch as negatives; returns
    the weights' hash, the model's version. A plain loop: sentence-transformers' own trainer
    needs two more libraries for what these lines do."""
    import torch
    from sentence_transformers import SentenceTransformer
    from sentence_transformers.sentence_transformer.losses import MultipleNegativesRankingLoss

    torch.manual_seed(SEED)
    docs = {
        f"{r['diploma']}:{r['article']}": document(r["heading"], r["text"], PLAIN_DOCUMENT)
        for r in in_force()
    }
    rows = [json.loads(line) for line in questions.read_text(encoding="utf-8").splitlines()]
    pairs = [(r["question"], docs[r["article"]]) for r in rows if r["article"] in docs]
    model = SentenceTransformer(BGE_M3, revision=BGE_M3_REVISION, device="cpu")
    model.max_seq_length = MAX_LENGTH
    loss_of = MultipleNegativesRankingLoss(model)
    order = torch.randperm(len(pairs)).tolist()
    batches = [[pairs[i] for i in order[n : n + BATCH]] for n in range(0, len(order), BATCH)]
    optimizer = torch.optim.AdamW(model.parameters(), lr=LEARNING_RATE)
    steps = EPOCHS * len(batches)
    warmup = max(1, steps // 10)  # a tenth of the steps, then down to 0

    def rate(step: int) -> float:
        return step / warmup if step < warmup else max(0.0, (steps - step) / max(1, steps - warmup))

    schedule = torch.optim.lr_scheduler.LambdaLR(optimizer, rate)
    model.train()
    for step, batch in enumerate(batches * EPOCHS, start=1):
        features = [model.tokenize([q for q, _ in batch]), model.tokenize([d for _, d in batch])]
        loss = loss_of(features, torch.empty(0))
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        optimizer.step()
        schedule.step()
        optimizer.zero_grad()
        if step % 10 == 0 or step == steps:
            print(f"step {step} of {steps}: loss {loss.item():.4f}", flush=True)
    model.save(str(out))
    return weights_sha(out)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m lex.finetune")
    parser.add_argument("command", choices=["generate", "train"])
    args = parser.parse_args(argv)
    load_dotenv(ROOT / ".env")
    if args.command == "generate":
        model = llm.Cached(llm.from_env(), ROOT / ".cache" / "llm" / "synthetic")
        print(f"wrote {generate(model)} synthetic questions to {QUESTIONS}")
        print(f"llm usage: {model.usage()}")
        return 0
    print(f"trained {MODEL}, weights {train()[:12]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
