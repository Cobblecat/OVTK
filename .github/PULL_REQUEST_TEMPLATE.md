## Problem and resulting behavior

Describe the problem, the change, and how users or reviewers can verify the result. Link related issues.

## Validation

List the commands run and their outcomes. Explain any check that was not run.

- `uv sync --frozen`:
- `uv run pytest`:
- `uv run ruff check .`:
- `uv run ruff format --check .`:
- `git diff --check`:
- Focused workflow or regression checks, where relevant:

## Review checklist

- [ ] The change uses synthetic data and contains no credentials or confidential records.
- [ ] Source databases, historical artifacts, and no-overwrite output protections are preserved.
- [ ] Determinism, sandbox provenance, and the analyst/ground-truth boundary are preserved.
- [ ] Behavioral changes have appropriate regression coverage.
- [ ] Documentation, compatibility effects, and statistical claim limits are accurate.
- [ ] Generated artifacts, virtual environments, and scratch files are excluded.
- [ ] The change follows CONTRIBUTING.md and CODE_OF_CONDUCT.md.

## Risks or limitations

Describe remaining uncertainty, compatibility concerns, and any follow-up needed.
