# 07 — Validation and Test Strategy

## 1. Purpose

Validation must prove both data integrity and WMS behavior. A database can be relationally valid yet operationally impossible; a scenario can be statistically useful yet unfair because it bypassed the source system.

The corrected strategy has six layers:

1. configuration validation;
2. schema and master-file validation;
3. WMS command and transaction validation;
4. simulator/scenario boundary validation;
5. reconstruction/report validation; and
6. statistical/reporting validation.

## 2. Severity model

### Hard failure

The artifact or command is invalid and must return nonzero status.

Examples:

- orphaned foreign key;
- invalid cube calculation;
- missing inventory-master row;
- negative quantity;
- balance change without audit row;
- nonconserving transfer;
- scenario direct-write behavior;
- hidden-truth leakage;
- reconstruction difference.

### Warning

The artifact is structurally usable but contains a condition requiring review.

Examples:

- low event count for a statistical stratum;
- unusually old replenishment task;
- ambiguous QA-adjustment candidate match;
- unusually high but physically possible occupancy.

### Informational signal

Expected operational evidence, not a validation defect.

Examples:

- elevated short cluster in an investigation run;
- generic adjustment after QA;
- high selector exposure to affected work.

## 3. Configuration tests

Validate:

- required sections and versions;
- time boundaries and timezone;
- positive scale values;
- item dimension ranges;
- pallet-pattern ranges;
- location counts and pallet capacities;
- operation probabilities and timing ranges;
- scenario dependencies;
- output path safety;
- seed and named-stream configuration.

Invalid configuration must fail before database creation.

## 4. Schema tests

For schema `3.0.0`, verify:

- expected tables, columns, views, indexes, and constraints;
- SQLite `user_version = 3`;
- foreign keys enabled;
- no prohibited legacy fields in corrected masters;
- one run per database;
- analyst schema contains no hidden-truth fields;
- append-only audit behavior through application interface;
- version-routed support for legacy schemas.

## 5. Item-master tests

Test:

- positive dimensions;
- cube calculation and rounding tolerance;
- positive weight;
- cases-per-layer and layers-per-pallet;
- cases-per-pallet calculation;
- zone and category rules;
- active status;
- deterministic generation;
- rejection of inconsistent calculated fields.

Hand fixture:

```text
12 in × 10 in × 8 in = 960 cubic inches = 0.555555... ft³
10 cases/layer × 5 layers = 50 cases/pallet
```

## 6. Location-master tests

Test:

- address uniqueness;
- valid zone and location type;
- required aisle/bay/level fields;
- pallet capacity where applicable;
- active/pickable rules;
- absence of case capacity;
- absence of equipment-area field;
- absence of live item and quantity fields.

## 7. Inventory-master tests

Test:

- exactly one row per location;
- valid item references;
- quantity integer and nonnegative;
- null item only at zero quantity;
- code date consistency;
- required pick-location assignment;
- replenishment control ordering;
- dynamic maximum derived from item and location profiles;
- reserve item clearing at zero quantity;
- inactive/noninventory location constraints;
- last transaction and update timestamp consistency.

## 8. WMS command tests

Each command family requires unit, repository-integration, and end-to-end tests.

### Common command tests

- valid command success;
- invalid input rejection;
- command ID idempotency;
- deterministic IDs and event sequence;
- transaction rollback;
- source record and audit traceability;
- timestamp rules;
- role authorization within synthetic domain rules.

### Pick tests

- full pick;
- partial pick;
- full short;
- picked + short = requested;
- insufficient recorded quantity;
- wrong item/location;
- no audit row for short quantity;
- balance before/after.

### Replenishment tests

- create/start/confirm lifecycle;
- source/destination item compatibility;
- sufficient source quantity;
- destination dynamic capacity;
- two balanced audit lines;
- atomic rollback;
- duplicate confirmation prevention.

### QA tests

- ordinary event recording;
- no balance change by observation alone;
- valid operator and location;
- later separate adjustment.

### Adjustment tests

- positive and negative adjustment;
- negative-balance prevention;
- item/location consistency;
- one audit line;
- reason and source references.

### Snapshot tests

- one row per location;
- capture agrees with live inventory;
- immutable batch;
- opening/closing timestamp rules.

## 9. Simulator tests

Test physical state independently from WMS storage:

- physical pick;
- physical transfer;
- damage loss;
- physical negative prevention;
- deterministic action order;
- physical/WMS divergence without leakage;
- no direct WMS mutation.

## 10. Scenario boundary tests

Static and runtime tests must prove:

- WMS modules do not import scenarios or simulator;
- scenario modules do not import WMS storage;
- scenario modules contain no SQL;
- scenarios use public WMS services;
- baseline and investigation use the same service implementations;
- invalid commands are rejected identically in every scenario;
- a minimal new scenario can run without WMS changes;
- target pattern names do not appear in WMS source or analyst schema.

## 11. Scenario signature tests

Restricted developer tests preserve the three patterns:

### Pattern A

- intended item/location/window targets exist;
- affected shorts cluster before or around delayed WMS confirmation;
- high-velocity representation;
- recovery evidence;
- no impossible physical or recorded movement.

### Pattern B

- QA events precede generic negative adjustments;
- fragile item representation;
- ground-truth links resolve;
- no direct causal field in WMS.

### Pattern C

- target selector crude ranking is high;
- affected exposure is disproportionate;
- no selector-specific error parameter;
- exposed peers are compatible;
- target outside affected conditions is not uniquely poor.

## 12. Standard-report tests

For every standard report:

- stable columns and ordering;
- parameter validation;
- direct-query fixture agreement;
- no hidden-truth access;
- no physical-state access;
- correct empty-location behavior;
- current inventory totals equal `inventory_master`;
- transaction inquiry equals audit rows;
- report export reproducibility.

## 13. Reconstruction tests

Test:

- opening snapshot initialization;
- audit-line sign and order;
- transfer-group conservation;
- pick decrement;
- adjustment delta;
- zero-delta assignment exclusion where applicable;
- no double application;
- trace to source workflow record;
- live inventory comparison;
- closing snapshot comparison;
- source checksum preservation;
- deterministic exports;
- hidden-truth leakage scan.

The primary acceptance equation is:

```text
opening + audit replay = live master = closing snapshot
```

## 14. Legacy compatibility tests

Preserve version-routed validation for schema `1.0.0` and `2.0.0` where practical.

Classify every legacy test:

- binding and unchanged;
- binding but adapted;
- retained as legacy compatibility;
- superseded by documented schema `3.0.0` behavior.

Do not remove tests silently.

## 15. Statistical tests

Phase 5 adds:

- metric numerator/denominator fixtures;
- confidence interval hand calculations;
- crude comparison fixtures;
- model-design matrix tests;
- sparse-cell and separation checks;
- cluster/robust uncertainty tests;
- attenuation calculation;
- sensitivity configuration;
- hypothesis-evidence required rows;
- no ground-truth access.

## 16. Report QA

Phase 6 adds:

- notebook restart-and-run-all;
- claim-to-source mapping;
- table/figure regeneration;
- management-report content checklist;
- synthetic-data labeling;
- limitations prominence;
- clean environment reproduction.

## 17. Acceptance commands

Each phase plan defines exact commands. The general gate is:

```powershell
uv sync
uv run pytest
uv run ruff check .
uv run ruff format --check .
git diff --check
```

Phase-specific smoke commands must generate into safe nonexisting temporary or acceptance paths.

## 18. Performance

Record generation, report, reconstruction, and analysis runtimes for local and portfolio configurations. Performance optimization must not weaken auditability or deterministic semantics.
