"""Where the fine-tuned BGE-M3 lives, and its version (ADR 0024)."""

import hashlib
from pathlib import Path

MODEL = Path(__file__).resolve().parents[3] / "data" / "models" / "bge-m3-lex"


def weights_sha(path: Path = MODEL) -> str:
    """A hash of the weights: the model's version, in its embeddings' name."""
    digest = hashlib.sha256()
    with (path / "model.safetensors").open("rb") as weights:
        for block in iter(lambda: weights.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()
