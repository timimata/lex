# 0019. Every dependency locked with uv, one Python everywhere

Date: 2026-10-08
Status: accepted

## Context

`pyproject.toml` pins each direct dependency (CLAUDE.md), but not theirs: two installs on
different days could differ, and a result could not say which packages made it. CI tested
Python 3.14 while the demo ran on Vercel's default, 3.12, as nothing told Vercel otherwise; its
`vercel/requirements.txt` was a second list, kept by hand. Vercel's Python runtime reads
`.python-version` and supports 3.12, 3.13 and 3.14 (its documentation, read 2026-10-08).

## Decision

- uv locks every dependency, of every extra, in `uv.lock` (uv 0.12.23, pinned in the `dev`
  extra). A dependency is still added to `pyproject.toml`, pinned with a comment; then `uv lock`.
- One Python, 3.14, named in `.python-version`: CI's setup reads it, `vercel/assemble.py` copies
  it into the deployment, and a local environment follows it.
- CI installs what the lock says (`uv export --locked`, which fails when the lock is out of date
  with `pyproject.toml`), and checks that `vercel/requirements.txt` is the lock's export for the
  demo (`--extra llm --extra api`).
- Every run records the Python it ran on and a hash of `uv.lock` (`environment` in `results/`).

## Consequences

- An install is reproducible from a commit, and a result says what it ran on.
- `pip install -e ".[...]"` still works but resolves afresh; installs that must match CI use the
  lock: `uv sync --locked --extra dev --extra llm --extra api` (add `ingest`, `dense`, `mcp` as
  needed).
- The demo moves from Python 3.12 to 3.14 at its next deploy, the version every test has run on.
