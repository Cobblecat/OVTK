# Release and Reproduction Guide

Version `0.1.0` is a local, synthetic-data-only release under the MIT License. It requires Python
`>=3.14` and was acceptance-tested with Python 3.14. No hosted service, paid data source, real
employer record, or XLSX dependency is required.

## Install

From the repository or extracted source archive:

```powershell
uv sync --frozen
uv run operational-variance-toolkit --version
uv run operational-variance-toolkit --help
```

## Regenerate the WMS Sources

Use fresh paths. Commands refuse to overwrite existing outputs.

```powershell
uv run operational-variance-toolkit generate --config configs/baseline.toml --output artifacts/data/schema3_baseline_accepted.sqlite3

uv run operational-variance-toolkit generate --config configs/investigation.toml --output artifacts/data/schema3_investigation_accepted.sqlite3 --ground-truth artifacts/restricted_ground_truth/schema3_investigation_accepted.json

uv run operational-variance-toolkit validate --database artifacts/data/schema3_baseline_accepted.sqlite3
uv run operational-variance-toolkit validate --database artifacts/data/schema3_investigation_accepted.sqlite3
```

The investigation generation step writes restricted truth because scenario calibration needs a
separate validation artifact. Ordinary reconstruction, statistics, notebook, reports, and WMS
queries never accept that path. Keep it closed until analysis is complete to preserve a blind review.

## Export Standard Reports

List the 12 registered report names, then export each report to a new CSV path:

```powershell
uv run operational-variance-toolkit report --database artifacts/data/schema3_baseline_accepted.sqlite3 --list
uv run operational-variance-toolkit report --database artifacts/data/schema3_baseline_accepted.sqlite3 --name inventory-by-location --output artifacts/reports/baseline/inventory-by-location.csv
```

Repeat the second command for every registered report and for the investigation database. Standard
reports remain factual WMS outputs and make no root-cause claim.

## Reconstruct and Analyze

```powershell
uv run operational-variance-toolkit reconstruct --database artifacts/data/schema3_baseline_accepted.sqlite3 --output artifacts/analysis/schema3_baseline_accepted

uv run operational-variance-toolkit reconstruct --database artifacts/data/schema3_investigation_accepted.sqlite3 --output artifacts/analysis/schema3_investigation_accepted

uv run operational-variance-toolkit analyze --database artifacts/data/schema3_investigation_accepted.sqlite3 --reconstruction artifacts/analysis/schema3_investigation_accepted --config configs/phase5_analysis.toml --output artifacts/analysis/RUN-D4876095A8166078/statistics_accepted
```

The frozen analysis configuration expects the accepted baseline paths shown above. It reads only the
analyst-facing WMS and reconstruction artifacts.

## Build the Notebook and Report

```powershell
uv run operational-variance-toolkit build-reporting --statistics artifacts/analysis/RUN-D4876095A8166078/statistics_accepted --reconstruction artifacts/analysis/schema3_investigation_accepted --notebook notebooks/operational_variance_investigation.ipynb --output artifacts/release/v0.1.0/reporting
```

This command validates the frozen manifest and checksums, verifies exact three-way reconciliation,
regenerates four figures and exhibit tables, executes the notebook in a fresh kernel, and builds the
executive Markdown/PDF and technical appendix. It does not fit a model.

## Package Local Archives

After exporting all standard reports under `artifacts/release/v0.1.0/standard_reports`, run:

```powershell
uv run operational-variance-toolkit package-release --workspace . --output artifacts/releases --baseline-database artifacts/data/schema3_baseline_accepted.sqlite3 --investigation-database artifacts/data/schema3_investigation_accepted.sqlite3 --baseline-reconstruction artifacts/analysis/schema3_baseline_accepted --investigation-reconstruction artifacts/analysis/schema3_investigation_accepted --statistics artifacts/analysis/RUN-D4876095A8166078/statistics_accepted --standard-reports artifacts/release/v0.1.0/standard_reports --reporting artifacts/release/v0.1.0/reporting --ground-truth artifacts/restricted_ground_truth/schema3_investigation_accepted.json
```

The command creates the versioned source ZIP, the separate optional spoiler ZIP, archive-specific
checksum files, and a combined `SHA256SUMS.txt`. It refuses existing outputs, sanitizes portable
provenance paths, scans analyst artifacts and SQLite schemas for hidden-truth leakage, and verifies
member checksums after ZIP creation.

## Verify Quality and Checksums

```powershell
uv run pytest
uv run ruff check .
uv run ruff format --check .
git diff --check

Get-FileHash artifacts/releases/operational-variance-toolkit-0.1.0-source.zip -Algorithm SHA256
Get-FileHash artifacts/releases/operational-variance-toolkit-0.1.0-ground-truth-optional.zip -Algorithm SHA256
```

Extract the source ZIP to a new directory and repeat installation, generation, validation, all
reports, both reconstructions, analysis, reporting, tests, Ruff, and checksum verification there.
Do not copy `.venv`, caches, existing generated data, Git internals, or the optional truth ZIP into
the extracted source tree.

## Ground-Truth Reveal Policy

The optional ground-truth ZIP is deliberately separate and prominently warns that it contains the
answer key. Never place its JSON in an analyst-facing WMS database, standard-report directory,
notebook input directory, or ordinary analysis workflow. Open it only for developer validation or
post-analysis comparison.
