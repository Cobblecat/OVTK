# Operational Variance Investigation Toolkit

A free, local, deterministic synthetic warehouse operations simulator, miniature WMS, and inventory-variance investigation project.

## Product identity

The project has two equally important responsibilities:

1. Provide a coherent, inspectable miniature WMS for the operational domains it models.
2. Generate fair synthetic investigations whose evidence can be examined through ordinary WMS files, reports, transactions, and analytical workflows.

The project does not attempt to implement the full breadth, security, scale, integration surface, or concurrency of a production enterprise WMS. It does require credible WMS semantics for:

- item and location profiles;
- live recorded inventory by location;
- picks and shorts;
- replenishment tasks and transfers;
- QA and damage records;
- inventory adjustments;
- immutable inventory audit history;
- scheduled snapshots and standard reports; and
- independent inventory reconstruction.

## Core design

```text
Independent mini-WMS
    item_master
    location_master
    inventory_master
    inventory_transaction
    operational workflow files
    standard reports and views

Physical simulator
    actual quantity and movement timing

Scenario drivers
    baseline and investigation protocols
    ordinary WMS commands
    restricted ground truth

Analysis
    reconstruction
    exposure and context tables
    statistical investigation
    management reporting
```

The WMS does not know which scenario is running. Scenario code cannot write WMS tables directly.

## Current status

The legacy implementation completed Phases 0 through 4 and proved deterministic generation, three controlled failure patterns, read-only reconstruction, and portable analytical exports.

Phase 4A introduced schema version `3.0.0`, live inventory by location,
immutable inventory transactions, independent WMS command services, external
scenario drivers, standard WMS reports, and three-way reconciliation.

Phase 4A is accepted. The corrected schema `3.0.0` WMS, independent scenario drivers, standard reports, and three-way reconciliation are available through the public commands below.

**Phases 5 and 6 are complete.** The frozen analyst workflow provides validated,
denominator-aware metrics, replenishment and QA evidence, crude and adjusted
selector comparisons, sensitivity results, diagnostics, and all six hypothesis
dispositions without accepting restricted ground truth. The release layer builds
the thin executed notebook, traceable figures, executive report, technical
appendix, and separate leakage-checked source and optional truth archives.

## Public command examples

Commands refuse to overwrite existing output files or directories. Choose new paths for each run.

```powershell
uv run operational-variance-toolkit config-check --config configs/baseline.toml
uv run operational-variance-toolkit init-wms --config configs/baseline.toml --output artifacts/data/schema3_wms.sqlite3

uv run operational-variance-toolkit generate --config configs/baseline.toml --output artifacts/data/schema3_baseline.sqlite3
uv run operational-variance-toolkit generate --config configs/investigation.toml --output artifacts/data/schema3_investigation.sqlite3 --ground-truth artifacts/restricted_ground_truth/schema3_investigation.json

uv run operational-variance-toolkit validate --database artifacts/data/schema3_baseline.sqlite3
uv run operational-variance-toolkit describe --database artifacts/data/schema3_baseline.sqlite3
uv run operational-variance-toolkit report --database artifacts/data/schema3_baseline.sqlite3 --name inventory-by-location --output artifacts/reports/schema3_baseline_inventory_by_location.csv
uv run operational-variance-toolkit scenario-check --database artifacts/data/schema3_investigation.sqlite3 --ground-truth artifacts/restricted_ground_truth/schema3_investigation.json
uv run operational-variance-toolkit reconstruct --database artifacts/data/schema3_investigation.sqlite3 --output artifacts/analysis/schema3_investigation
uv run operational-variance-toolkit analyze --database artifacts/data/schema3_investigation.sqlite3 --reconstruction artifacts/analysis/schema3_investigation --config configs/phase5_analysis.toml --output artifacts/analysis/RUN-ID/statistics
uv run operational-variance-toolkit build-reporting --statistics artifacts/analysis/RUN-ID/statistics --reconstruction artifacts/analysis/schema3_investigation --notebook notebooks/operational_variance_investigation.ipynb --output artifacts/release/v0.1.0/reporting
```

`init-db` is the legacy database initializer; use `init-wms` for the schema-3 WMS foundation.

## Interactive read-only console

Launch the Release 0.2.0 Phase 1 console from source:

```powershell
uv run operational-variance-toolkit console
```

The no-database start menu requires an explicit choice to open the included
sample, enter another schema-3 database path, view help, or exit. Direct startup
is also available:

```powershell
uv run operational-variance-toolkit console --database "C:\path with spaces\warehouse.sqlite3"
uv run operational-variance-toolkit console --sample
uv run operational-variance-toolkit console --no-style
```

Phase 1 provides `open`, `sample`, `close`, `status`, `validate`, `describe`,
`version`, `help`, `history`, `clear`, `exit`, and `quit`. Existing schema-3
databases are opened with SQLite read-only and query-only protections. Inquiry,
reports, exports, trace, sandboxes, CSV workflows, and WMS mutation remain later
release phases.

## Release Contents

A release reviewer can:

- generate a normal synthetic warehouse run;
- generate an investigation run with hidden process failures;
- inspect the SQLite WMS database directly;
- query item, location, live inventory, and audit files;
- run standard WMS reports;
- trace every current balance to immutable inventory transactions;
- reconstruct inventory independently;
- perform the statistical investigation;
- review the executed notebook, management-facing exhibits, executive PDF, and technical appendix;
- verify archive manifests and SHA-256 checksums; and
- reveal restricted ground truth only through a separately named optional spoiler archive.

## Technology

- Python `>=3.14`; release 0.1.0 was developed and acceptance-tested with Python 3.14
- `uv`
- SQLite
- standard-library SQL and serialization where practical
- NumPy for deterministic named random streams
- Pandas, SciPy, and Statsmodels for the tested Phase 5 statistical workflow
- Matplotlib, nbformat/nbclient, ReportLab, and pypdf for reproducible release reporting

## License

The project is released under the [MIT License](LICENSE). Version `0.1.0` is distributed as a local
versioned source ZIP plus a deliberately separate optional restricted-ground-truth ZIP. No XLSX
packet is included.

## Documentation

Start with:

1. `PROJECT_STATUS.md`
2. `docs/01_PROJECT_CHARTER.md`
3. `docs/02_REQUIREMENTS_AND_ACCEPTANCE.md`
4. `docs/03_ARCHITECTURE.md`
5. `docs/04_DATA_MODEL_AND_DICTIONARY.md`
6. `docs/09_IMPLEMENTATION_ROADMAP.md`
7. `docs/29_RELEASE_0_2_0_INTERACTIVE_CONSOLE_AND_CSV_WORKFLOWS_ROADMAP.md`
8. `docs/30_RELEASE_0_2_0_PHASE_0_AUDIT_AND_CONTRACTS.md`
9. `docs/14_STATISTICAL_GUARDRAILS.md`
10. `docs/26_PHASE_5_ANALYSIS_CONTRACT.md`
11. `docs/27_WMS_USER_AND_SQL_GUIDE.md`
12. `docs/28_RELEASE_AND_REPRODUCTION_GUIDE.md`

## Data policy

All data are synthetic. No real employer records, employee identities, proprietary screenshots, credentials, or confidential system details are used.
