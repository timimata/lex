import re
import tomllib
from pathlib import Path

from lex.eval import report

ROOT = Path(__file__).resolve().parents[1]


def test_citation_and_pyproject_name_one_version() -> None:
    """ADR 0021: the code's version moves in both files together."""
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    cff = (ROOT / "CITATION.cff").read_text(encoding="utf-8")
    cited = re.search(r"^version: (\S+)$", cff, re.MULTILINE)
    assert cited and cited.group(1) == project["version"]


def test_the_code_version_names_the_reported_benchmark() -> None:
    """ADR 0021: 0.N.P reports benchmark vN's runs."""
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    runs = report.leaderboard()
    if not runs:  # between a re-split and its test runs, nothing is reported
        return
    scored = runs[0]["bench"].get("scored") or runs[0]["bench"]["sha"]
    assert f"v{project['version'].split('.')[1]}" == report.VERSIONS[scored]
