# Contributing

Thank you for taking an interest in OVTK. Read the [README](README.md), [project status](PROJECT_STATUS.md), and [code of conduct](CODE_OF_CONDUCT.md) before proposing a change.

## Choose and discuss a change

Search existing issues first. Report a reproducible defect with the bug template, or explain a proposed feature and its acceptance criteria with the feature template. Discuss substantial architecture, schema, dependency, or statistical-method changes before implementing them.

For usage questions, see [SUPPORT.md](SUPPORT.md). Report potential vulnerabilities privately using [SECURITY.md](SECURITY.md).

## Set up a development copy

Use Python 3.14 or newer and `uv`. Fork the repository, clone your fork, and create a branch for your change. From the repository root:

```powershell
uv sync --frozen
uv run pytest
uv run ruff check .
uv run ruff format --check .
git diff --check
```

Use the locked environment for routine work. If a change requires updating dependencies, explain the reason and include the corresponding manifest and lockfile changes.

## Preserve the project contracts

This project uses synthetic data only. Contributions must not introduce real employer records, personal information, proprietary system details, credentials, or confidential operating information.

Preserve:

- the analyst/ground-truth boundary and separate optional truth artifacts;
- named deterministic random streams and reproducible outputs;
- source database and historical artifact immutability;
- verified sandbox provenance and no-overwrite output behavior;
- literal handling of supplied text at output boundaries; and
- the claim-strength limits in the [statistical guardrails](docs/14_STATISTICAL_GUARDRAILS.md).

Follow the [architecture](docs/03_ARCHITECTURE.md) and applicable phase contracts. New metrics or report claims require tested package functions and traceable source references. Keep generated databases, reports, restricted truth, virtual environments, and scratch files out of commits.

## Submit a pull request

Keep the change focused. Explain the problem, resulting behavior, and relevant compatibility or migration effects. Add regression coverage for behavioral changes and update documentation when users need different instructions.

Run the checks above and record the commands and outcomes in the pull request. Use disposable synthetic copies and new output paths for verification. Note any checks that were not run and why. Avoid implying that local tests establish a distributed release or production readiness.

Review feedback may request a smaller change, additional evidence, or a revision to the approach. Maintain the existing MIT license and attribution.
