# Contributing

This project uses synthetic data only. Contributions must not introduce real employer records,
proprietary system details, credentials, or confidential operating information.

Use Python 3.14 and `uv`. Before proposing a change, run:

```powershell
uv sync
uv run pytest
uv run ruff check .
uv run ruff format --check .
git diff --check
```

Preserve the analyst/ground-truth boundary, deterministic random streams, source immutability, and
claim-strength limits in `docs/03_ARCHITECTURE.md` and
`docs/14_STATISTICAL_GUARDRAILS.md`. New metrics or report claims require tested package functions
and traceable source references.
