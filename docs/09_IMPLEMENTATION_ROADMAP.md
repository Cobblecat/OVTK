# 09 — Implementation Roadmap

## 1. Purpose

This roadmap supersedes the previous forward plan while preserving completed work as historical implementation evidence.

The project originally completed Phases 0 through 4 under an analytics-first operational model. A domain review determined that the source system must be refactored into an independent, credible miniature WMS before statistical analysis proceeds.

The revised roadmap inserts **Phase 4A — WMS Operational Fidelity Remediation** between completed legacy Phase 4 and future Phase 5.

## 2. Governance

### Authority and conflict resolution

The product owner provides warehouse/WMS domain authority. Explicit domain
corrections, once recorded in current project documents, are binding when the
assignment brief leaves implementation details open.

Use this order when requirements conflict:

1. Explicit product-owner decisions recorded in current project documents.
2. `reference/Operational_Variance_Assignment_Brief_v2.md` for fixed business
   purpose and required deliverables.
3. `docs/01_PROJECT_CHARTER.md` and
   `docs/02_REQUIREMENTS_AND_ACCEPTANCE.md`.
4. `docs/03_ARCHITECTURE.md`, `docs/04_DATA_MODEL_AND_DICTIONARY.md`, and
   `docs/05_SYNTHETIC_DATA_SPECIFICATION.md`.
5. The active phase plan and `PROJECT_STATUS.md`.
6. Remaining project specifications and `docs/12_DECISION_LOG.md`.
7. Existing code and tests.

The assignment brief intentionally leaves exact schema design open. A broad
recommendation in the brief does not override a later explicit domain decision
recorded through this authority chain. Record material changes in
`docs/12_DECISION_LOG.md` before implementation.

Every phase or remediation slice follows these execution requirements:

1. Scope is defined by its purpose, deliverable, inclusions, exclusions, and acceptance criteria.
2. A passing baseline is preserved before behavior changes.
3. Implementation proceeds in the smallest complete vertical slices.
4. Tests cover valid behavior and rejected invalid states.
5. Targeted checks pass before implementation continues.
6. Project status and decisions are updated only after checks pass.
7. Required reviews are completed at the explicit review checkpoints before progression.
8. Later analytical outcomes must not weaken source-system rules.

A phase is complete only when behavior is executed and verified and its required
reviews are complete.

## 3. Historical Phase 0 — Repository foundation

**Status:** Complete and retained.

Delivered:

- Python/`uv` project;
- CLI foundation;
- immutable configuration;
- deterministic identity and named random streams;
- expected application errors;
- Pytest and Ruff;
- project documentation and contributor guidance.

No remediation is expected beyond normal refactoring.

## 4. Historical Phase 1 — Relational opening state

**Status:** Complete under legacy schema; partially superseded by Phase 4A.

Reusable work:

- facility, zone, item, location, operator, shift, and assignment generation;
- deterministic opening quantities;
- schema lifecycle;
- version-routed validation;
- CLI workflows;
- tests and reproducibility framework.

Superseded assumptions:

- cube without retained dimensions;
- fixed location case capacity;
- snapshot-centered recorded inventory;
- handling-unit opening model;
- separate slot-assignment file as current assignment source.

## 5. Historical Phase 2 — Normal operations simulator

**Status:** Complete under legacy architecture; partially refactored by Phase 4A.

Reusable work:

- trips, picks, replenishments, QA, adjustments, system events;
- deterministic chronology;
- operation configuration;
- event and role validators;
- baseline generation and acceptance tests.

Superseded assumptions:

- WMS recorded state primarily in memory;
- simulator-owned state transition processor as the source-system core;
- no persistent live inventory master and immutable general audit file.

## 6. Historical Phase 3 — Controlled failure injection

**Status:** Complete under legacy integration; scenario behavior retained and integration refactored by Phase 4A.

Reusable work:

- target selection;
- three pattern definitions;
- calibration;
- restricted JSON ground truth;
- leakage checks;
- baseline/investigation configurations.

Superseded assumption:

- failure overlays inside the normal operations generator and state transition processor.

Corrected approach:

- external scenario drivers schedule physical actions and ordinary WMS commands.

## 7. Historical Phase 4 — Reconstruction foundation

**Status:** Complete under legacy schema; reconstruction semantics adapted by Phase 4A.

Reusable work:

- read-only source access;
- source checksum preservation;
- deterministic ledger exports;
- context tables;
- reconciliation and manifest infrastructure;
- 106-test legacy checkpoint.

Corrected approach:

- reconstruct from `inventory_transaction`;
- reconcile to live `inventory_master` and closing snapshot.

# 8. Phase 4A — WMS Operational Fidelity Remediation

**Status:** Slices 0-7 technically complete and owner accepted. Phase 5 Slice 0
planning is next; Phase 5 implementation has not started.

## Purpose

Replace the analytics-first operational core with a coherent schema-version `3.0.0` miniature WMS while preserving successful deterministic simulation, controlled scenarios, reconstruction, and traceability.

## Deliverable

> A user can generate a schema `3.0.0` baseline or investigation database, inspect stable item and location masters, query live inventory by location, trace every recorded quantity change through immutable transactions, run standard WMS reports, and independently reconcile opening inventory, transaction history, live inventory, and closing snapshots.

## Phase 4A slices

### Slice 0 — Preservation, documentation, and code audit (complete)

- tag completed legacy checkpoint;
- install corrected specifications;
- classify existing modules and tests;
- identify reusable, adaptable, and superseded behavior;
- retain green legacy test baseline;
- produce no WMS behavior changes.

**Review boundary:** Approval of the concrete migration inventory is required.

### Slice 1 — Schema `3.0.0` and corrected master files (complete)

- `item_master` with dimensions and calculated cube;
- `location_master` with pallet capacity and no case capacity/equipment area;
- one-row-per-location `inventory_master`;
- `inventory_transaction` contract;
- updated snapshots;
- version-routed schema support;
- master-file validators and tests.

**Review boundary:** schema and master semantics pass before transaction services.

### Slice 2 — Independent WMS application core (complete)

- typed commands and command IDs;
- unit-of-work/atomic transaction boundary;
- inventory assignment and initialization;
- pick service;
- replenishment lifecycle and atomic transfer;
- QA recording;
- inventory adjustment;
- snapshot service;
- immutable audit and idempotency;
- WMS independence tests.

**Review boundary:** WMS works through direct tests with no simulator/scenario modules.

### Slice 3 — Standard WMS reports and inquiry surface (technically complete)

- tested SQL views/query services;
- report registry;
- CLI report command;
- console/CSV output;
- report-source reconciliation;
- no hidden-state access.

**Review boundary:** Review of report usefulness and warehouse terminology is required.

### Slice 4 — Physical simulator and baseline-driver migration (complete)

- separate physical state;
- scenario action protocol and runner;
- baseline plan generation;
- ordinary WMS commands;
- no direct scenario writes;
- baseline schema `3.0.0` artifact;
- live inventory and audit validation.

**Review boundary:** corrected baseline passes before investigation patterns.

### Slice 5 — Investigation scenario-driver migration (complete)

- external Pattern A, B, and C drivers;
- preserved target selection and calibration;
- restricted truth version update;
- no WMS scenario branches;
- investigation schema `3.0.0` artifact;
- leakage and fairness tests.

**Review boundary:** scenario signatures and source-system integrity both pass.

### Slice 6 — Reconstruction and analytical-output migration (complete)

- reconstruct from immutable audit;
- three-way reconciliation;
- update context tables;
- update manifests;
- baseline and investigation outputs;
- source preservation and deterministic exports.

**Review boundary:** zero differences across replay, live master, and snapshot.

### Slice 7 — Full regression, cleanup, and remediation release (technically complete)

- legacy compatibility classification complete;
- obsolete code paths retired deliberately;
- full acceptance artifact generation;
- runtime and reproducibility checks;
- documentation finalization;
- schema and SQL exploration examples;
- Phase 4A release checkpoint.

## Explicit exclusions

- statistical models;
- confidence intervals;
- root-cause ranking;
- notebook narrative;
- charts and dashboards;
- corrective recommendations;
- executive report;
- receiving, shipping, route accounting, or production integrations;
- pallet/LPN lifecycle.

## Completion gate

Detailed in `docs/18_PHASE_4A_WMS_OPERATIONAL_FIDELITY_PLAN.md` and `docs/23_REMEDIATION_ACCEPTANCE_CHECKLIST.md`.

# 9. Phase 5 — Statistical Investigation and Hypothesis Testing

**Status:** Complete and accepted. Findings are frozen from ordinary schema-3
WMS and reconstruction evidence; Phase 6 reporting is next.

## Purpose

Use only analyst-facing schema `3.0.0` WMS data and corrected reconstruction outputs to test competing explanations for variance.

## Deliverable

> A reproducible statistical investigation containing denominator-aware descriptive evidence, uncertainty, crude and adjusted selector comparisons, sensitivity checks, and a ranked hypothesis evidence table.

## Included work

- analytical dependency additions when used;
- analysis configuration;
- portfolio-scale adequacy review;
- descriptive WMS and variance evidence;
- replenishment timing analysis;
- QA-adjustment sequence analysis;
- selector exposure analysis;
- effect sizes and confidence intervals;
- predefined adjusted model;
- cluster/robust uncertainty;
- sensitivity checks;
- hypothesis evidence table;
- frozen analyst conclusions before ground-truth review.

## Exclusions

- final notebook storytelling;
- final charts and executive report;
- public release packaging;
- changes to WMS source semantics;
- model-driven scenario tuning after primary specification is frozen.

## Completion gate

- all six hypotheses evaluated;
- selector crude association visible and materially attenuated after predefined adjustment;
- replenishment and QA evidence supported through ordinary records;
- intervals, diagnostics, sensitivity, and limitations documented;
- no ground-truth dependency;
- all numbers reproducible.

Detailed in `docs/19_PHASE_5_STATISTICAL_INVESTIGATION_PLAN.md`.

# 10. Phase 6 — Reporting, Portfolio, and Open-Source Release

## Purpose

**Status:** Complete and accepted for release 0.1.0

Convert the verified WMS and analysis into a professional, auditable, freely reproducible portfolio product.

## Deliverable

> A reviewer can clone or unzip the project, generate the WMS datasets, inspect standard reports and SQL files, run reconstruction and analysis, execute the notebook, read the executive report, and audit every claim without proprietary data or paid services.

## Included work

- thin executed notebook;
- final figures and evidence tables;
- executive report and technical appendix;
- SQL exploration guide;
- standard report guide;
- complete README and clean-environment instructions;
- open-source license;
- release manifest and checksums;
- example artifacts;
- CSV, SQLite, notebook, figure, and PDF release artifacts; no initial XLSX packet;
- release archive/tag.

## Exclusions

- production WMS deployment;
- real integrations;
- user accounts/cloud hosting;
- large GUI application;
- unsupported causal claims.

## Completion gate

- clean-environment reproduction passes;
- all report claims trace to source;
- WMS and analyst data are clearly synthetic;
- ground truth remains restricted;
- limitations are prominent;
- license and release files are complete.

Detailed in `docs/20_PHASE_6_REPORTING_AND_RELEASE_PLAN.md`.

# 11. Release 0.2.0 - Interactive console and CSV workflows

**Status:** Active roadmap; Phase 0 engineering complete pending owner checkpoint

Release 0.2.0 is an operability and Windows distribution release. It adds a
persistent read-only-first WMS console, inquiry/report/export/trace commands,
verified writable sandboxes, exactly two previewed CSV maintenance workflows,
and a portable Windows x64 application bundle. It preserves every accepted
0.1.0 source and analytical workflow.

The governing integrated plan is
`docs/29_RELEASE_0_2_0_INTERACTIVE_CONSOLE_AND_CSV_WORKFLOWS_ROADMAP.md`.
The Phase 0 interface audit and frozen contracts are in
`docs/30_RELEASE_0_2_0_PHASE_0_AUDIT_AND_CONTRACTS.md`.

# 12. Post-release candidates

Not initial commitments:

- pallet IDs and complete pallet lifecycle;
- mixed item/code-date locations;
- receiving and putaway simulation;
- route-return reconciliation;
- migration/count reconciliation scenario;
- unit-of-measure conversion failure scenario;
- duplicate confirmation scenario;
- mis-slotting scenario;
- control-chart monitoring mode;
- local browser explorer;
- multi-scenario comparison;
- additional training cases.

A candidate enters active work only through a written scope decision.

# 13. Project success chain

```text
credible mini-WMS
    -> independent normal simulation
    -> external controlled scenarios
    -> inspectable live inventory and audit files
    -> standard operational reports
    -> three-way reconstruction
    -> exposure-adjusted evidence
    -> bounded root-cause finding
    -> practical corrective actions
    -> reproducible open-source release
```

The strongest success criterion is whether an experienced warehouse analyst can trust the simulated source system enough to consider the investigation accurate and fair.
