"""The page's colour contrast, measured from the tokens in src/styles.css (WCAG 2.2: 4.5:1 for
text, 3:1 for large text and for the borders of fields and the focus ring).

    python web/contrast.py            # prints the table; exit 1 if any pair is under its bar
    python web/contrast.py --md FILE  # also writes it as Markdown, for docs/checks/

Every pair the page draws is listed by hand below, so a new token or a new use is added here.
"""

import argparse
import re
import sys
from pathlib import Path

STYLES = Path(__file__).resolve().parent / "src" / "styles.css"

# (name, foreground token, background token, bar). Opacities are folded into the foreground.
PAIRS = [
    ("body text on paper", "ink", "paper", 4.5),
    ("secondary text on paper", "ink-2", "paper", 4.5),
    ("muted text on paper", "muted", "paper", 4.5),
    ("muted text on paper-2 (the reader, the basis)", "muted", "paper-2", 4.5),
    ("muted text on paper-3 (the footer)", "muted", "paper-3", 4.5),
    ("notice on paper-3", "ink-2", "paper-3", 4.5),
    ("links on paper", "cobalt", "paper", 4.5),
    ("links on paper-2", "cobalt", "paper-2", 4.5),
    ("links on paper-3 (the footer)", "cobalt", "paper-3", 4.5),
    ("refusal and removed text on paper", "vermilion", "paper", 4.5),
    ("removed text on paper-2 (the reader)", "vermilion", "paper-2", 4.5),
    ("button text on cobalt", "on-accent", "cobalt", 4.5),
    ("button text on cobalt-strong (hover)", "on-accent", "cobalt-strong", 4.5),
    ("wordmark and nav on the header", "on-cobalt", "cobalt-deep", 4.5),
    ("nav links at 85% on the header", "on-cobalt@0.85", "cobalt-deep", 4.5),
    ("language switch at 80% on the header", "on-cobalt@0.8", "cobalt-deep", 4.5),
    ("field border on paper", "field", "paper", 3.0),
    ("field border on paper-2", "field", "paper-2", 3.0),
    ("focus ring (cobalt) on paper", "cobalt", "paper", 3.0),
    ("focus ring (cobalt) on paper-2", "cobalt", "paper-2", 3.0),
    ("the share bar (cobalt) on its track", "cobalt", "rule", 3.0),
]


def tokens(css: str) -> dict[str, dict[str, str]]:
    """The hex tokens of the light scheme (:root) and the dark one (the media block)."""
    light_block = re.search(r":root \{(.*?)\n\}", css, re.S)
    dark_block = re.search(r"prefers-color-scheme: dark\) \{\s*:root \{(.*?)\n  \}", css, re.S)
    assert light_block and dark_block, "styles.css changed shape"
    read = lambda block: dict(re.findall(r"--([\w-]+): (#[0-9a-fA-F]{6})", block))  # noqa: E731
    light = read(light_block.group(1))
    return {"light": light, "dark": light | read(dark_block.group(1))}


def rgb(hex_: str) -> tuple[float, float, float]:
    h = hex_.lstrip("#")
    return tuple(int(h[i : i + 2], 16) / 255 for i in (0, 2, 4))  # type: ignore[return-value]


def luminance(c: tuple[float, float, float]) -> float:
    lin = [v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4 for v in c]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def over(fg: tuple[float, float, float], bg: tuple[float, float, float], alpha: float):
    return tuple(f * alpha + b * (1 - alpha) for f, b in zip(fg, bg, strict=True))


def ratio(fg: tuple[float, float, float], bg: tuple[float, float, float]) -> float:
    a, b = luminance(fg), luminance(bg)
    hi, lo = max(a, b), min(a, b)
    return (hi + 0.05) / (lo + 0.05)


def rows(scheme: dict[str, str]) -> list[tuple[str, float, float, bool]]:
    out = []
    for name, fg_token, bg_token, bar in PAIRS:
        token, _, alpha = fg_token.partition("@")
        bg = rgb(scheme[bg_token])
        fg = rgb(scheme[token])
        if alpha:
            fg = over(fg, bg, float(alpha))
        r = ratio(fg, bg)
        out.append((name, r, bar, r >= bar))
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--md", type=Path)
    args = parser.parse_args()
    schemes = tokens(STYLES.read_text(encoding="utf-8"))
    lines = ["| Pair | Light | Dark | Bar |", "|---|---|---|---|"]
    failed = False
    for (name, light, bar, ok_l), (_, dark, _, ok_d) in zip(
        rows(schemes["light"]), rows(schemes["dark"]), strict=True
    ):
        mark = "" if ok_l and ok_d else " **fails**"
        lines.append(f"| {name} | {light:.2f} | {dark:.2f} | {bar:.1f}{mark} |")
        failed |= not (ok_l and ok_d)
    table = "\n".join(lines)
    print(table)
    if args.md:
        head = (
            "# The page's colour contrast\n\n"
            "Produced by `python web/contrast.py --md docs/checks/web-contrast.md` from the "
            "tokens in `web/src/styles.css`: every pair of colours the page draws, in the light "
            "and the dark scheme, against the WCAG 2.2 bar for it (4.5:1 for text, 3:1 for large "
            "text, field borders and the focus ring). Opacities are folded into the foreground.\n\n"
        )
        args.md.write_text(head + table + "\n", encoding="utf-8", newline="\n")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
