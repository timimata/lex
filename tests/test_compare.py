from typing import Any

import pytest

from lex.eval import compare


def run(verdicts: dict[str, str], refused: tuple[str, ...] = ()) -> list[dict[str, Any]]:
    items = [
        {"id": i, "type": "simple", "verdict": v, "refused": i in refused}
        for i, v in verdicts.items()
    ]
    return [*items, {"id": "ct-0099", "type": "unanswerable", "verdict": None, "refused": True}]


def test_the_sign_test_is_exact_and_two_sided() -> None:
    assert compare.sign_test(0, 0) == 1.0
    assert compare.sign_test(5, 5) == 1.0
    assert compare.sign_test(0, 5) == pytest.approx(2 / 32)  # all five one way, either way
    assert compare.sign_test(1, 9) == pytest.approx(2 * 11 / 1024)
    assert compare.one_sided(5, 0) == pytest.approx(1 / 32)


def test_runs_are_paired_by_item_and_only_disagreements_count() -> None:
    before = run({f"ct-000{n}": "correta" for n in range(1, 9)} | {"ct-0009": "parcial"})
    # Two lost, one gained: the same total of right answers would hide this.
    after = run(
        {f"ct-000{n}": "correta" for n in range(1, 7)}
        | {"ct-0007": "parcial", "ct-0008": "errada", "ct-0009": "correta"}
    )
    p = compare.paired(before, after, "correct")
    assert (p.items, p.only_a, p.only_b) == (9, ["ct-0007", "ct-0008"], ["ct-0009"])
    assert compare.regressed(before, after) == []  # two against one is noise


def test_a_loss_too_one_sided_for_noise_is_a_regression() -> None:
    before = run({f"ct-00{n:02d}": "correta" for n in range(1, 21)})
    after = run({f"ct-00{n:02d}": "correta" if n > 5 else "parcial" for n in range(1, 21)})
    [why] = compare.regressed(before, after)
    assert why.startswith("correct on 5 items it no longer gets right and gained 0")

    refusing = run({f"ct-00{n:02d}": "correta" for n in range(1, 21)}, refused=("ct-0001",))
    assert compare.regressed(before, refusing) == []  # one more refusal is within the noise
