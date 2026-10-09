# 10 - Phase 0 and Phase 1 Implementation Plan

> **Historical traceability notice:** This document records the completed legacy
> Phase 0-1 implementation for schema versions `1.0.0` and `2.0.0`. It is not the
> active schema-3 remediation plan. For schema `3.0.0`, the governing plan is
> `docs/18_PHASE_4A_WMS_OPERATIONAL_FIDELITY_PLAN.md`, interpreted with the
> corrected architecture, data model, and migration map in docs 03, 04, and 21.

## 1. Purpose

This was the active implementation plan for the legacy Phase 0-1 work. It covers only:

- **Phase 0:** repository and application foundation; and
- **Phase 1:** relational schema, deterministic master data, assignments, handling units, and opening inventory.

The plan intentionally stops before generating trips, picks, replenishments, QA events, adjustments, system events, or controlled failures.

## 2. Phase 0 target state

At Phase 0 completion, the repository must install with `uv`, expose a console command, load and validate TOML configuration, and pass tests and Ruff checks. No business data are generated yet.

## 3. Phase 0 repository structure

Create this initial structure:

```text
.
|-- .gitignore
|-- .python-version
|-- PROJECT_STATUS.md
|-- README.md
|-- configs/
|   `-- baseline.toml
|-- docs/
|-- pyproject.toml
|-- reference/
|-- src/
|   `-- operational_variance_toolkit/
|       |-- __init__.py
|       |-- __main__.py
|       |-- cli.py
|       |-- errors.py
|       |-- version.py
|       |-- application/
|       |   `-- __init__.py
|       |-- domain/
|       |   `-- __init__.py
|       |-- generation/
|       |   `-- __init__.py
|       |-- analysis/
|       |   `-- __init__.py
|       |-- reporting/
|       |   `-- __init__.py
|       `-- storage/
|           `-- __init__.py
|-- tests/
|   |-- conftest.py
|   |-- test_cli.py
|   `-- test_config.py
`-- uv.lock
```

Empty package directories are acceptable in Phase 0 only where they communicate the dependency boundaries already approved in `docs/03_ARCHITECTURE.md`. Do not add speculative classes or protocols to fill them.

## 4. Phase 0 package and tool configuration

### 4.1 Project metadata

Use these defaults unless a conflict is discovered:

```toml
[project]
name = "operational-variance-toolkit"
version = "0.1.0"
description = "Deterministic synthetic warehouse data and inventory variance investigation toolkit"
requires-python = ">=3.14"
```

Expose this console script:

```toml
[project.scripts]
operational-variance-toolkit = "operational_variance_toolkit.cli:main"
```

Initial runtime dependencies should remain minimal. Phase 0 may use only the standard library. Add NumPy, Pandas, Statsmodels, and Matplotlib in the phase that actually uses each dependency unless the lockfile workflow makes a single deliberate initial dependency declaration preferable. Record either choice in the decision log.

Development dependencies:

- `pytest>=9`
- `ruff>=0.16`

Configure Pytest to use `tests` as the test path and importlib import mode. Configure Ruff to check `src`, `tests`, and project scripts, include import sorting, and target Python 3.14.

### 4.2 Version source

Use one canonical version source. Preferred implementation:

- keep the package version in `pyproject.toml`;
- read installed metadata through `importlib.metadata.version()`; and
- expose it through a small `version.py` helper that handles an editable-source fallback only if necessary.

Do not duplicate a manually maintained version string in multiple files.

### 4.3 `.python-version`

Set:

```text
3.14
```

A more specific patch may be used if required by `uv`, but avoid coupling the project to an exact local patch version without need.

### 4.4 `.gitignore`

Ignore at minimum:

- `.venv/`
- Python caches and test caches
- Ruff cache
- local IDE settings unless intentionally shared
- generated SQLite databases and WAL/SHM files
- generated CSV/XLSX exports
- generated reports and images
- notebook checkpoints and executed notebook output artifacts
- local scratch files

Do not ignore small test fixtures or checked-in reference documents.

## 5. Phase 0 configuration contract

### 5.1 Configuration file

Create `configs/baseline.toml` as a valid but not-yet-executed configuration. It should establish the contract needed by Phase 1 without including unimplemented operational-rate details.

Recommended sections:

```toml
[run]
scenario_name = "baseline"
scenario_version = "0.1.0"
seed = 20260801
start_local = "2026-05-04T03:00:00"
end_local = "2026-05-14T15:00:00"
facility_timezone = "America/New_York"

[facility]
facility_id = "FAC-001"
name = "Synthetic Grocery Distribution Center"

[dimensions]
zone_count = 3
item_count = 96
selector_count = 18
replenisher_count = 7
qa_operator_count = 3
shift_count = 10

[storage]
database_path = "artifacts/data/baseline.sqlite3"
ground_truth_directory = "artifacts/restricted_ground_truth"
export_directory = "artifacts/exports"
```

The configuration should be treated as source input, never modified by a generation run.

### 5.2 Typed configuration objects

Use immutable dataclasses for Phase 0 configuration values. Recommended objects:

- `RunConfig`
- `FacilityConfig`
- `DimensionConfig`
- `StorageConfig`
- `ProjectConfig`

Loading responsibilities:

1. Read TOML with `tomllib`.
2. Reject unknown top-level sections and unknown keys within known sections.
3. Convert paths to `pathlib.Path` without touching the filesystem during pure parsing.
4. Parse local timestamps as naive local wall-clock inputs, then validate them using `zoneinfo.ZoneInfo` and convert to aware UTC boundaries.
5. Validate `start < end`, nonnegative or positive counts as appropriate, valid scenario version format, and nonempty stable identifiers.
6. Produce a canonical serializable representation for hashing.
7. Hash canonical configuration using SHA-256.

No global configuration object is allowed. Pass `ProjectConfig` into workflows explicitly.

### 5.3 Error behavior

Create application-specific exceptions sufficient for clean CLI handling:

- `ToolkitError` - base expected application error;
- `ConfigurationError`;
- `OutputExistsError`;
- `DataValidationError`; and
- `DatabaseError`.

Unexpected programmer errors should not be swallowed. The CLI may print a concise error for known exceptions and return a nonzero code, while unexpected exceptions should remain visible during development.

Recommended exit codes:

- `0` success;
- `2` command-line usage error, aligned with `argparse`;
- `3` configuration error;
- `4` unsafe output or existing-output conflict;
- `5` database operation failure;
- `6` validation failure.

## 6. Phase 0 CLI contract

Use standard-library `argparse` for the initial CLI.

Required Phase 0 commands:

```text
operational-variance-toolkit --help
operational-variance-toolkit --version
operational-variance-toolkit config-check --config configs/baseline.toml
```

`config-check` must:

- load the configuration;
- validate it;
- print a stable, concise summary;
- print the configuration hash; and
- perform no data generation or output-directory creation.

Example successful output shape:

```text
Configuration valid
Scenario: baseline 0.1.0
Seed: 20260801
Operating period (UTC): ... to ...
Facility timezone: America/New_York
Configuration SHA-256: ...
```

Tests should assert semantic fields, not terminal spacing that has no contract value.

## 7. Phase 0 tests

At minimum, test:

### CLI

- `--help` succeeds.
- `--version` succeeds and contains the installed version.
- `config-check` succeeds for the checked-in baseline configuration.
- Invalid configuration returns the configured nonzero code and a useful message.

### Configuration

- Valid TOML maps to the expected immutable objects.
- Unknown keys fail.
- Missing required keys fail.
- Invalid time zones fail.
- End before start fails.
- Zero or negative required dimensions fail.
- Equivalent semantic configuration produces the same hash.
- A meaningful value change produces a different hash.
- Path parsing does not create directories.

## 8. Phase 0 acceptance checkpoint

Do not begin Phase 1 until all commands below succeed:

```powershell
uv sync
uv run operational-variance-toolkit --help
uv run operational-variance-toolkit --version
uv run operational-variance-toolkit config-check --config configs/baseline.toml
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

Update `PROJECT_STATUS.md` with the exact results and commit a Phase 0 completion checkpoint.

---

## 9. Phase 1 target state

Given the baseline configuration, the application creates a fresh versioned SQLite database with:

- run metadata;
- facility, zones, and locations;
- items and item-location assignments;
- synthetic operators and roles;
- shifts and work assignments;
- handling units;
- opening system inventory snapshots; and
- an equivalent hidden simulator physical opening state.

The database must pass all Phase 1 validators and be reproducible from the same configuration and seed.

## 10. Phase 1 Slice 1 - Run identity and deterministic primitives

### Goal

Create the deterministic services that every later generator uses.

### Files

Recommended additions:

```text
src/operational_variance_toolkit/
|-- domain/
|   |-- identifiers.py
|   |-- run.py
|   `-- time.py
|-- generation/
|   `-- random_source.py
`-- tests or matching test modules
```

### Requirements

#### Run identity

Define a run record containing:

- `run_id`;
- scenario name and version;
- seed;
- simulation start and end in UTC;
- facility timezone;
- configuration SHA-256;
- schema version;
- generator/package version;
- generation timestamp; and
- optional source-code revision when available.

The `run_id` must be deterministic for the same scenario version, configuration hash, and seed. A truncated SHA-256 with an explicit prefix is acceptable, for example:

```text
RUN-4A7C2E19B51F
```

Generation timestamp is metadata about execution and should not be part of content-equivalence comparisons.

#### Random source

- Construct one root `numpy.random.Generator` once NumPy is introduced.
- Derive named child streams deterministically using `SeedSequence.spawn` or another documented method.
- Suggested stream names: `master_items`, `master_locations`, `operators`, `schedules`, `opening_inventory`.
- Do not make outcomes dependent on incidental function-call order across unrelated components.

A stable named-stream registry is preferred over passing one mutable generator through the entire application when independent streams reduce accidental coupling.

#### Identifiers

Identifiers must be human-readable, stable within a run, and not encode facts that analysts are expected to infer.

Recommended forms:

- `FAC-001`
- `ZONE-FRZ`, `ZONE-CLD`, `ZONE-AMB`
- `LOC-FRZ-001`
- `ITEM-0001`
- `OP-SEL-001`
- `SHIFT-20260504-A`
- `ASSIGN-000001`
- `HU-000001`

Do not use Python's randomized `hash()` for persisted identifiers.

### Tests

- Same seed/configuration yields the same deterministic run ID and generated ID sequences.
- Named random streams reproduce independently.
- Adding a draw in one stream does not alter another stream.
- UTC/local conversion is correct across the configured period.

## 11. Phase 1 Slice 2 - SQLite schema and lifecycle

### Goal

Create the schema and safe database lifecycle before generating rows.

### Files

Recommended additions:

```text
src/operational_variance_toolkit/storage/
|-- database.py
|-- schema.py
|-- schema.sql
`-- repositories/
    |-- __init__.py
    `-- phase1_repository.py
```

### Database lifecycle rules

- The default workflow creates a new file.
- Refuse to overwrite an existing database.
- Create parent directories only after configuration validation and immediately before the write workflow.
- Enable SQLite foreign keys on every connection.
- Use explicit transactions.
- Roll back and remove a newly created incomplete database if initialization fails.
- Set a documented journal mode. WAL is acceptable for development, but do not leave WAL/SHM artifacts in release fixtures.
- Store `schema_version` in both run metadata and a schema metadata table or `PRAGMA user_version`.
- Do not implement migrations until a second schema version exists; do define the version boundary now.

### Phase 1 schema

Create the Phase 1 form of these tables:

- `schema_metadata`
- `simulation_run`
- `facility`
- `zone`
- `location`
- `item`
- `operator`
- `shift`
- `slot_assignment`
- `work_assignment`
- `handling_unit`
- `inventory_snapshot`

Use the field definitions and constraints in `docs/04_DATA_MODEL_AND_DICTIONARY.md`. Operational transaction tables may be added in later schema versions; do not create empty speculative tables merely to make the final diagram appear complete.

### Constraint expectations

- Primary keys on all entities.
- Foreign keys for all parent relationships.
- Unique natural relationships where duplicates would be invalid.
- `CHECK` constraints for nonnegative quantities, valid enumerated values where stable, and time ordering where SQLite permits meaningful enforcement.
- Indexes on foreign keys and future common joins where justified.
- All persisted timestamps are UTC ISO 8601 strings with explicit `Z` or offset.
- No floating-point case quantities; use integers for case-level quantities in Phase 1.

### Repository behavior

The repository translates domain records to database rows. It must not generate business values, decide CLI text, or read TOML.

Use `sqlite3.Row` for reads if helpful, but convert rows into typed domain records before returning them to application services.

### Tests

- Schema creates successfully in a temporary path.
- Foreign keys are enabled.
- Invalid parent references fail.
- Duplicate location or assignment constraints fail as designed.
- Negative inventory fails.
- Schema version is readable.
- Existing-output protection works.
- Failed initialization does not leave a misleading completed database.

## 12. Phase 1 Slice 3 - Master-data generation

### Goal

Generate a compact but believable grocery-distribution center master dataset.

### Facility and zones

Use one facility and three default operating zones:

- frozen;
- chilled; and
- ambient.

Zone codes should be stable and readable. Zone characteristics may include default temperature class, location count, aisle pattern, and operating profile, but do not model engineering detail unnecessary to the investigation.

### Locations

Generate locations with explicit attributes rather than encoding all meaning in the location ID:

- zone;
- aisle;
- bay;
- level;
- location type;
- active status;
- capacity in cases;
- replenishment eligibility; and
- pick eligibility.

Phase 1 should include forward pick slots and reserve locations sufficient to support later replenishment. Include QA/hold locations only if their Phase 1 existence is necessary to establish valid future foreign keys; otherwise introduce them with the corresponding operational phase.

### Items

Generate item records with distributions that support later analysis:

- item description;
- storage zone;
- velocity class;
- cases per pallet;
- case volume or normalized size;
- fragility class;
- shelf-life or perishability class if used later;
- active status; and
- standard forward-slot capacity requirement.

Generation must preserve plausible relationships. For example, cases per pallet, case size, slot capacity, and opening quantity must not conflict.

Do not generate scenario-target flags in the item table. Scenario targeting belongs in hidden configuration/ground truth.

### Operators

Generate synthetic operators using neutral IDs and optional synthetic display labels. Required roles for the complete project are selector, replenisher, QA, inventory control, and system/process. Phase 1 should create at least selector, replenisher, and QA operators if they are needed by the checked-in dimension counts.

Do not create realistic personal names. Do not include protected-class attributes, demographic variables, or employment-performance scores.

### Shifts and work assignments

Create shifts covering the configured operating days. Work assignments connect operators to role, zone, and shift. Assignments must make later differential exposure possible while remaining plausible.

Phase 1 may establish the schedule pattern but must not deliberately designate the false-lead selector in analyst-facing tables.

### Slot assignments

Each active item must have a valid forward slot. Selected items may have multiple allowable storage relationships where needed, but one primary forward location should be explicit. Reserve capacity should be sufficient for opening stock.

### Tests

- Counts match configuration.
- Every item has a valid active slot assignment.
- Every location belongs to one valid zone.
- Operator role values are valid.
- Work assignments fall within shifts and use compatible roles/zones.
- No real names or forbidden fields appear.
- Same seed produces equivalent master tables.
- Different seeds alter stochastic attributes while retaining all constraints.

## 13. Phase 1 Slice 4 - Opening handling units and inventory

### Goal

Create a coherent opening state that later transactions can safely modify.

### State model

At initialization, system and physical quantity should normally agree. Maintain the conceptual distinction even when values are equal:

- **system opening quantity** is persisted in analyst-facing `inventory_snapshot` records;
- **physical opening quantity** initializes an internal simulator state or restricted state store; and
- **handling units** represent pallet or case groupings when used.

Do not add artificial opening variance merely to make future analysis interesting.

### Opening quantity logic

Opening stock should reflect:

- item velocity;
- cases per pallet;
- forward-slot capacity;
- reserve capacity;
- configured days or hours of supply; and
- zone-appropriate constraints.

Use integer quantities. Ensure:

- quantity is nonnegative;
- location capacity is not exceeded;
- an item occupies only valid assigned locations;
- handling-unit quantity sums reconcile where handling units are used;
- the forward slot contains a plausible working amount; and
- reserve stock supports later replenishment simulation.

### Snapshot records

Each opening snapshot should include:

- run ID;
- snapshot ID;
- snapshot timestamp;
- item ID;
- location ID;
- quantity in cases;
- snapshot kind, such as `system_opening`;
- source or generation method; and
- verification status where relevant.

### Hidden physical state

The simulator physical state must not be placed in the analyst-facing SQLite tables as a `true_quantity` column. Acceptable Phase 1 implementations include:

- an in-memory typed state reconstructed from a restricted initialization artifact; or
- a separate restricted SQLite/JSON/Parquet artifact outside the analyst database.

Choose the simpler implementation that supports deterministic later simulation and record the choice in the decision log.

### Tests

- System opening totals reconcile to handling units.
- Physical opening state equals system opening state in baseline initialization.
- No capacity violations.
- No invalid item/location pair.
- No negative quantity.
- Same seed/configuration reproduces opening quantities.
- Physical-state serialization, if used, is excluded from ordinary analyst loading.

## 14. Phase 1 Slice 5 - Application workflows and CLI

### Goal

Connect configuration, generation, persistence, and validation through thin application services and CLI commands.

### Application services

Recommended workflows:

- `CheckConfiguration`
- `InitializeDatabase`
- `ValidateDataset`
- optionally `DescribeDataset`

A workflow coordinates domain services and repositories. It does not contain SQL strings, terminal formatting, or random generation details.

### CLI commands

Add:

```text
operational-variance-toolkit init-db --config configs/baseline.toml
operational-variance-toolkit validate --database artifacts/data/baseline.sqlite3
operational-variance-toolkit describe --database artifacts/data/baseline.sqlite3
```

#### `init-db`

- validates configuration;
- refuses unsafe overwrite;
- creates the schema;
- generates deterministic Phase 1 records;
- persists them in one controlled workflow;
- runs hard Phase 1 validation before success;
- prints run ID, database path, counts, and configuration hash; and
- returns nonzero on failure.

Do not add `--force` casually. A safer later approach is an explicit `--replace` that first validates the target as a generated artifact and uses an atomic replacement strategy. For Phase 1, refusal is sufficient.

#### `validate`

- reads schema and run metadata;
- executes applicable validators;
- prints errors and warnings by category;
- returns `0` when no hard failures exist;
- returns the validation exit code when hard failures exist.

#### `describe`

Provide a factual summary only:

- run metadata;
- table row counts;
- master-data counts;
- opening inventory totals by zone;
- validation status.

It must not make analytical claims.

## 15. Phase 1 validation checklist

### Structural

- Database opens and schema version is supported.
- Required tables and columns exist.
- Foreign-key check returns no violations.
- Required values are non-null.
- Stable uniqueness constraints hold.

### Master data

- Configured counts match actual counts.
- All zones belong to the configured facility.
- All locations have valid roles and positive capacities.
- Every item has a valid zone and at least one active slot assignment.
- Operators and assignments use valid roles.
- Shifts and assignments fall within the run boundaries.

### Opening state

- All quantities are integer and nonnegative.
- Item-location relationships are valid.
- Location capacity is respected.
- Handling-unit sums reconcile to snapshots under the documented representation.
- System and physical opening state agree for baseline initialization.

### Reproducibility

Generate into two separate temporary paths using the same configuration and seed. Compare canonical table extracts while excluding execution timestamp and physical file metadata. They must match.

## 16. Phase 1 test organization

Recommended tests:

```text
tests/
|-- unit/
|   |-- test_config.py
|   |-- test_identifiers.py
|   |-- test_random_source.py
|   |-- test_master_generation.py
|   |-- test_opening_inventory.py
|   `-- test_validation_rules.py
|-- integration/
|   |-- test_schema.py
|   |-- test_phase1_repository.py
|   |-- test_initialize_database.py
|   `-- test_reproducibility.py
|-- fixtures/
|   `-- minimal_config.toml
`-- test_cli.py
```

Use temporary directories and temporary databases. Keep a tiny hand-authored fixture for state-validation arithmetic. Do not commit a large generated database as a golden file.

## 17. Phase 1 completion commands

Run, at minimum:

```powershell
uv run operational-variance-toolkit config-check --config configs/baseline.toml
uv run operational-variance-toolkit init-db --config configs/baseline.toml
uv run operational-variance-toolkit validate --database artifacts/data/baseline.sqlite3
uv run operational-variance-toolkit describe --database artifacts/data/baseline.sqlite3
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

Also run a reproducibility check into two temporary output paths and report the comparison result.

## 18. Phase 1 definition of done

Phase 1 is complete only when:

- every Phase 0 and Phase 1 acceptance criterion passes;
- the generated database contains only Phase 1 scope;
- all data are synthetic and neutral;
- configuration and seed are preserved;
- the output is deterministic;
- validation is clean;
- the schema and actual implementation agree;
- public commands are documented in `README.md`;
- `PROJECT_STATUS.md` records exact commands and results; and
- no Phase 2 logic has been smuggled into the implementation.

## 19. Initial implementation milestone

**Phase 0, Slice 1: Python package and quality tooling** establishes the initial
repository foundation and CLI help/version behavior. Its scope is governed by
the project charter, requirements, architecture, active plan, and inspection of
the current repository before changes.

Milestone completion requires:

- the Phase 0 package, tooling, and CLI foundation only;
- tests for the implemented behaviors;
- execution of all applicable commands, tests, and quality checks; and
- a `PROJECT_STATUS.md` completion record covering changes, exact commands and
  results, and the next uncompleted slice.

SQLite schema work is a separate milestone. Continuation requires explicit
product-owner approval after review of the Phase 0 checkpoint. Schema work may
join the same change only if that checkpoint has been reviewed and continuation
has been explicitly approved.
