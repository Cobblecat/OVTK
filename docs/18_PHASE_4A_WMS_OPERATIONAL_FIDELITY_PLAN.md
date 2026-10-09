# 18 — Phase 4A WMS Operational Fidelity Remediation Plan

## 1. Phase status

**Status:** Phase 4A accepted; Phase 5 Slice 0 planning is next
**Predecessor:** Legacy Phase 4 complete
**Successor:** Phase 5 statistical investigation
**Schema target:** `3.0.0`

## 2. Purpose

Correct the operational architecture before statistical analysis.

The legacy application successfully generates and reconstructs a synthetic investigation, but it treats the source system too much like an analytics-oriented generator. Phase 4A builds a coherent miniature WMS that an experienced warehouse analyst can inspect and trust.

## 3. Deliverable

> A deterministic schema `3.0.0` mini-WMS with realistic item and location master files, live inventory by location, immutable inventory audit history, atomic command services, standard WMS reports, independent physical simulation, external scenario drivers, and three-way reconstruction.

## 4. Fixed design decisions

These decisions must not be revisited unless implementation reveals a direct contradiction that cannot be resolved.

1. One SQLite database per finalized WMS run.
2. `item_master` retains case dimensions; cube is calculated and stored.
3. `location_master` is a stable profile and has pallet capacity, not case capacity.
4. `location_master` does not contain equipment area or live item/quantity state.
5. `inventory_master` is keyed by location and is the live recorded WMS state.
6. One item and one code date per location in schema `3.0.0`.
7. No pallet IDs or handling-unit lifecycle in schema `3.0.0`.
8. Every post-initialization quantity change creates immutable audit rows.
9. Transfers write balanced source/destination rows atomically.
10. WMS core is independent from physical simulator and scenarios.
11. Scenarios submit ordinary WMS commands and cannot write storage.
12. Snapshots are report captures, not live state.
13. Standard reports use ordinary WMS files.
14. Corrected artifacts are regenerated, not migrated in place.
15. Reconstruction must match live inventory and closing snapshot.
16. Phase 5 remains paused.

## 5. Preservation strategy

Before implementation:

- ensure all current changes are committed;
- tag the checkpoint `wms-remediation-safety-checkpoint`;
- create branch `refactor/wms-operational-fidelity`;
- record current test count and acceptance commands;
- preserve legacy databases and analysis outputs outside any cleanup action;
- do not delete schema `1.0.0` or `2.0.0` support until version-routing tests pass.

A generated artifact is not migrated. A code module may be adapted or replaced while retaining tests and Git history.

`wms-remediation-safety-checkpoint` is the single canonical preservation tag;
no alternate alias is required.

## 6. Target implementation flow

```text
config
    -> generate item/location profiles
    -> initialize independent WMS
    -> capture opening snapshot
    -> build scenario plan
    -> run physical actions and WMS commands
    -> capture closing snapshot
    -> validate WMS
    -> run standard reports
    -> reconstruct from audit
    -> three-way reconcile
```

## 7. Slice 0 — Documentation installation and code audit

### Goal

Create a verified migration inventory without changing runtime behavior.

### Included work

1. Install replacement documentation.
2. Read current source and tests.
3. Classify each relevant module:
   - retain unchanged;
   - adapt;
   - split;
   - supersede; or
   - remove only after replacement.
4. Classify each test:
   - still binding;
   - adapt to schema 3;
   - legacy compatibility;
   - explicitly superseded.
5. Map current public commands and artifacts.
6. Confirm current tests and quality checks remain green.
7. Create or update a concrete implementation checklist inside `PROJECT_STATUS.md` or a dedicated audit appendix.

### Likely files inspected

- `src/.../domain/*`
- `src/.../generation/*`
- `src/.../application/*`
- `src/.../storage/*`
- `src/.../validation/*`
- `src/.../analysis/*`
- `tests/*`
- CLI/config files

### Prohibited work

- no schema changes;
- no source moves;
- no dependency changes;
- no deleted tests;
- no Phase 5 work.

### Acceptance

- legacy full test suite passes;
- Ruff and diff checks pass;
- migration inventory names exact files/symbols;
- no runtime behavior changes;
- Review is required before Slice 1.

## 8. Slice 1 — Schema 3 and corrected master files

### Goal

Create schema `3.0.0` and typed records for credible item, location, live inventory, audit, and snapshot files.

### Included work

#### 8.1 Item master

Implement typed item profile with:

- dimensions;
- calculated cube;
- case weight;
- pallet pattern;
- calculated cases per pallet;
- storage and analytical attributes.

Provide a single canonical calculation service.

#### 8.2 Location master

Implement stable location profile with pallet capacity and no prohibited live fields.

#### 8.3 Inventory master

Implement one row per location with current item, quantity, code date, pick replenishment controls, last audit reference, and last update.

#### 8.4 Inventory transaction

Implement immutable signed audit rows, transaction groups, command IDs, before/after balances, source references, and deterministic ordering.

#### 8.5 Snapshot contract

Add snapshot batch and detail identity while preserving opening/closing concepts.

#### 8.6 Schema lifecycle

- SQLite user version 3;
- schema metadata `3.0.0`;
- explicit version routing;
- fresh creation only;
- foreign keys and checks;
- indexes required by WMS commands and inquiry.

### Initialization behavior

The Slice 1 initializer may create master profiles and an opening inventory state through a controlled WMS-owned setup workflow. It need not yet implement normal operations.

It must:

- create one inventory row per location;
- assign items to pick locations;
- assign valid reserve inventory;
- calculate dynamic maximum cases;
- reject item/location zone mismatch;
- capture opening snapshot;
- omit pallet IDs.

### Tests

At minimum:

- item dimension and cube fixtures;
- pallet-pattern fixtures;
- invalid calculation rejection;
- location prohibited-field/schema test;
- one inventory row per location;
- pick and reserve state rules;
- dynamic max calculation;
- code-date rules;
- schema version routing;
- legacy schemas remain valid;
- deterministic initialization;
- no hidden-truth columns.

### Acceptance commands

```powershell
uv run pytest <targeted schema/master tests>
uv run ruff check <changed paths>
uv run ruff format --check <changed paths>
```

Then full test suite before review.

### Progression prerequisites

Operational transaction services require prior review of the schema and sample rows.

## 9. Slice 2 — Independent WMS command core

### Goal

Make the mini-WMS operable through public commands without simulator or scenario code.

### 9.1 Foundation

Implement:

- typed command objects;
- command IDs;
- event-sequence allocation;
- transaction-group IDs;
- unit-of-work or transaction boundary;
- repository methods that return typed records;
- domain validators;
- consistent application errors.

### 9.2 Location assignment/setup service

Support controlled assignment and clearing rules.

- Pick location assignment remains at zero quantity.
- Reserve location may clear item/code date at zero.
- Reassignment requires valid empty state and explicit command.
- Dynamic maximum and replenishment controls recalculate/validate.

### 9.3 Pick service

Input:

- command ID;
- trip/selector;
- item/location;
- requested, picked, short quantities;
- event and recorded times;
- short reason.

Atomic result:

- `pick_event` row;
- one negative audit row when picked quantity > 0;
- updated `inventory_master`;
- event registry entry;
- no inventory effect for short quantity.

### 9.4 Replenishment service

Commands:

- create task;
- start task;
- confirm task.

Confirmation atomically:

- validates lifecycle;
- validates item/source/destination;
- validates source quantity;
- validates destination dynamic maximum;
- writes source negative audit row;
- writes destination positive audit row;
- updates both inventory rows;
- confirms task;
- updates last references.

### 9.5 QA service

Records QA workflow only. No balance change without separate inventory command.

### 9.6 Adjustment service

Atomically:

- validates item/location and signed delta;
- prevents negative balance;
- writes adjustment workflow row;
- writes audit row;
- updates inventory master.

### 9.7 System-event service

Records system context only.

### 9.8 Snapshot service

Captures one immutable row per location from live inventory.

### Idempotency

Every inventory-affecting command must be safe against duplicate submission.

Recommended behavior:

- repeated identical accepted command returns the original result; or
- explicit duplicate-command error with no changes.

Choose one and document it.

### Tests

- direct service operation with no simulator imports;
- all command happy paths;
- invalid role, item, location, time, and quantity;
- full/partial/short pick;
- replenishment lifecycle;
- atomic rollback at injected failure points;
- transfer conservation;
- duplicate command behavior;
- audit before/after balances;
- append-only interface;
- source-reference traceability;
- snapshot equality;
- WMS import graph.

### Progression prerequisites

Do not migrate scenarios until the WMS can be tested directly and all command acceptance tests pass.

## 10. Slice 3 — Standard WMS reports

### Goal

Provide practical operational inquiry using the same files available to SQL users.

### Included reports

Detailed contracts appear in `docs/22_STANDARD_WMS_REPORTS_CONTRACT.md`.

Implement at least:

- inventory by location;
- inventory by item;
- location profile and contents;
- empty locations;
- code-date inventory;
- replenishment needs;
- open replenishment tasks;
- transaction inquiry;
- adjustment history;
- QA activity.

### Interface

Recommended CLI:

```text
operational-variance-toolkit report \
  --database <db> \
  --name <report-name> \
  [--output <csv>] \
  [report parameters]
```

Also expose report names and column definitions programmatically.

### Tests

- direct SQL fixture comparison;
- stable columns/order;
- report parameters;
- live inventory totals;
- empty location semantics;
- dynamic capacity/occupancy calculation;
- no ground-truth or physical-state dependency;
- CSV reproducibility;
- useful CLI errors.

### Domain review

Slice completion requires review of sample report output for names, columns, and warehouse usefulness.

## 11. Slice 4 — Physical simulator and baseline migration

### Goal

Run normal warehouse operations through the independent WMS.

### 11.1 Physical state

Create a typed physical inventory state separate from WMS repositories.

It must:

- initialize from opening state;
- prevent negative physical quantity;
- support physical picks, transfers, damage, and found product;
- expose no SQL or WMS mutation.

### 11.2 Scenario action protocol

Implement typed scheduled actions:

- physical action;
- WMS command action;
- external/system event action;
- restricted-truth action where applicable.

### 11.3 Runner

Execute actions by timestamp, priority, and action ID.

The runner receives WMS application services through a narrow interface. It does not receive repositories.

### 11.4 Baseline driver

Migrate current normal-operation generation into a baseline scenario that:

- assigns trips;
- schedules physical picks;
- submits pick commands;
- creates and confirms replenishments;
- records QA, adjustments, and system events;
- captures closing snapshot.

The baseline driver must not contain controlled-failure target logic.

### 11.5 Baseline acceptance artifact

Generate a safe schema 3 baseline database.

Validate:

- live inventory;
- audit history;
- workflow records;
- standard reports;
- opening/closing snapshots;
- determinism;
- no controlled signatures beyond background ranges.

### Tests

- scenario cannot import storage;
- same WMS services work in direct and scenario tests;
- physical and recorded states can differ temporarily;
- baseline command failures are handled, not bypassed;
- no direct inventory master writes;
- deterministic action ordering;
- report and audit coherence.

### Progression prerequisites

Do not migrate controlled patterns until the corrected baseline is coherent.

## 12. Slice 5 — Investigation scenario migration

### Goal

Recreate the three controlled patterns as external protocols without changing WMS rules.

### 12.1 Pattern A

Migrate target selection and timing logic into scenario actions.

The scenario may vary:

- physical movement time;
- WMS task/confirmation time;
- pick scheduling;
- later correction timing.

The WMS receives ordinary task, pick, confirmation, and adjustment commands.

### 12.2 Pattern B

The scenario applies physical damage, records ordinary QA, and later submits a generic valid adjustment.

The WMS has no hidden link.

### 12.3 Pattern C

The scenario allocates the target selector to affected work. It does not change WMS or physical pick-error propensity by selector.

### 12.4 Ground truth

Update truth schema/version only as needed to represent:

- physical actions;
- WMS command timing;
- target entities;
- source references;
- expected signatures.

### 12.5 Calibration

Re-run restricted scenario checks and add WMS-fidelity checks:

- every referenced WMS ID resolves;
- all quantity changes are audited;
- no scenario term leaks;
- no scenario direct write;
- target selector false lead remains exposure-driven.

### Acceptance artifact

Generate new schema 3 investigation database and restricted truth file into safe paths.

### Progression prerequisites

Do not adapt statistical analysis. First migrate reconstruction.

## 13. Slice 6 — Reconstruction migration

### Goal

Rebuild Phase 4 around the authoritative WMS audit.

### Ledger source

Use `inventory_transaction` as the primary signed ledger.

Workflow tables enrich context but do not infer quantity deltas already represented by audit rows.

### Reconciliation

For every location:

```text
opening snapshot quantity
+ sum inventory_transaction deltas after opening
= reconstructed closing quantity
```

Compare with:

- final `inventory_master.qty_on_hand_cases`;
- closing snapshot quantity.

### Derived output changes

Update:

- inventory ledger columns to include transaction group/command IDs;
- reconciliation to include live-master quantity and two differences;
- pick context to source live/audit fields;
- replenishment context to link audit groups;
- QA-adjustment context to use workflow and audit evidence;
- selector exposure to preserve prior denominators;
- manifests to identify schema 3.

### Tests

- hand-calculated audit replay;
- transfer lines applied exactly once;
- live master comparison;
- snapshot comparison;
- source workflow traceability;
- standard-report totals;
- baseline and investigation reconstruction;
- source read-only checksum;
- reproducibility;
- no ground truth.

### Progression prerequisites

Do not start Phase 5 until full remediation regression passes.

## 14. Slice 7 — Full regression and release checkpoint

### Goal

Prove the refactor preserved intended behavior and improved source-system credibility.

### Required work

1. Run all legacy tests and classify failures.
2. Adapt tests where requirements remain binding.
3. Retain legacy schema validation tests.
4. Remove obsolete code only after no supported path references it.
5. Generate final schema 3 baseline and investigation artifacts.
6. Run standard reports.
7. Run restricted scenario calibration.
8. Reconstruct both artifacts.
9. Run three-way reconciliation.
10. Compare same-seed reproducibility.
11. Verify changed seed differs but remains valid.
12. Scan source and outputs for hidden truth.
13. Verify import/dependency boundaries.
14. Record local runtimes.
15. Update all docs and status.

## 15. Phase 4A full acceptance commands

Exact paths may be adjusted, but the final gate must be equivalent to:

```powershell
uv sync
uv run operational-variance-toolkit --help
uv run operational-variance-toolkit config-check --config configs/baseline.toml
uv run operational-variance-toolkit config-check --config configs/investigation.toml

uv run operational-variance-toolkit generate \
  --config configs/baseline.toml \
  --output artifacts/data/schema3_baseline.sqlite3

uv run operational-variance-toolkit validate \
  --database artifacts/data/schema3_baseline.sqlite3

uv run operational-variance-toolkit describe \
  --database artifacts/data/schema3_baseline.sqlite3

uv run operational-variance-toolkit report \
  --database artifacts/data/schema3_baseline.sqlite3 \
  --name inventory-by-location \
  --output artifacts/reports/schema3_baseline_inventory_by_location.csv

uv run operational-variance-toolkit generate \
  --config configs/investigation.toml \
  --output artifacts/data/schema3_investigation.sqlite3 \
  --ground-truth artifacts/restricted_ground_truth/schema3_investigation.json

uv run operational-variance-toolkit validate \
  --database artifacts/data/schema3_investigation.sqlite3

uv run operational-variance-toolkit scenario-check \
  --database artifacts/data/schema3_investigation.sqlite3 \
  --ground-truth artifacts/restricted_ground_truth/schema3_investigation.json

uv run operational-variance-toolkit reconstruct \
  --database artifacts/data/schema3_baseline.sqlite3 \
  --output artifacts/analysis/schema3_baseline

uv run operational-variance-toolkit reconstruct \
  --database artifacts/data/schema3_investigation.sqlite3 \
  --output artifacts/analysis/schema3_investigation

uv run pytest
uv run ruff check .
uv run ruff format --check .
git diff --check
```

Use safe nonexisting paths. Do not overwrite legacy artifacts.

## 16. Required acceptance evidence

Final status must record:

- schema version and table counts;
- sample item dimensions/cube validation;
- sample location profile;
- sample live inventory rows;
- sample audit trail;
- report row counts;
- baseline and investigation scenario counts;
- scenario calibration;
- three-way reconciliation differences;
- source checksums before/after analysis;
- same-seed equivalence;
- changed-seed validity;
- test count and runtimes;
- hidden-truth leakage result;
- import/dependency audit result;
- known limitations.

## 17. Decisions and blockers requiring review

Affected implementation remains blocked pending review and a decision when:

- the one-row-per-location model cannot support a required existing scenario without hidden corruption;
- item dimensions or pallet pattern require a disputed domain rule;
- a WMS command cannot be made atomic under the current storage layer;
- scenario separation would require changing the central investigation thesis;
- statistical calibration fails because source-system correction changes the intended evidence materially;
- direct report usefulness requires a material new operational domain;
- a destructive legacy migration appears necessary; or
- hard failures remain after focused debugging.

Routine module naming, private helper structure, test organization, and reversible implementation details may proceed within the approved scope.

## 18. Final boundary

Phase 4A does not implement statistical conclusions. It ends when the corrected source system, scenarios, reports, and reconstruction are credible and verified.
