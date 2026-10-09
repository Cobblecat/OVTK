# Phase 4A Slice 0 Current-Code Audit

**Status:** Slice 0 audit complete; implementation has not begun.
**Scope:** Documentation-only preservation audit and remediation migration mapping.
**Runtime code changed:** No.

## Repository State

Phase 1 through Phase 4 implementation and the WMS remediation documentation package currently coexist in one preserved mixed checkpoint.

The active branch is `refactor/wms-operational-fidelity`. The preserved safety checkpoint is commit `6f6b49a` with tag `wms-remediation-safety-checkpoint` and branch `rescue/phase4-remediation-mixed-checkpoint`.

At the start of this audit, `git status --short` was clean. The checkpoint contains completed legacy Phase 0-4 runtime implementation, tests, baseline/investigation configuration, and the remediation contract documents for Phase 4A.

No runtime code, tests, configuration, schema, dependency files, or generated artifacts were modified during Slice 0.

## Document Inventory And Preservation

### Completed Legacy Phase 0-4 Implementation

The current tracked implementation includes legacy Phase 0-4 package code under `src/operational_variance_toolkit/`, tests under `tests/`, baseline and investigation configuration under `configs/`, and documentation through Phase 4 completion.

Legacy schema `2.0.0` behavior remains the working acceptance baseline and must be preserved until schema `3.0.0` has equivalent or superior coverage.

### Newly Installed Remediation Contracts

The remediation package is represented by:

- `REMEDIATION_CHANGE_SUMMARY.md`
- `MANIFEST.md`
- `SHA256SUMS.txt`
- `docs/18_PHASE_4A_WMS_OPERATIONAL_FIDELITY_PLAN.md`
- `docs/19_PHASE_5_STATISTICAL_INVESTIGATION_PLAN.md`
- `docs/20_PHASE_6_REPORTING_AND_RELEASE_PLAN.md`
- `docs/21_SCHEMA_AND_CODE_MIGRATION_MAP.md`
- `docs/22_STANDARD_WMS_REPORTS_CONTRACT.md`
- `docs/23_REMEDIATION_ACCEPTANCE_CHECKLIST.md`

The governing Phase 4A order should be:

1. `docs/18_PHASE_4A_WMS_OPERATIONAL_FIDELITY_PLAN.md` for phase sequencing and slice gates.
2. `docs/03_ARCHITECTURE.md` and `docs/04_DATA_MODEL_AND_DICTIONARY.md` for architecture and schema.
3. `docs/21_SCHEMA_AND_CODE_MIGRATION_MAP.md` for legacy-to-target migration.
4. `docs/22_STANDARD_WMS_REPORTS_CONTRACT.md` for report behavior.
5. `docs/23_REMEDIATION_ACCEPTANCE_CHECKLIST.md` for final acceptance.

`REMEDIATION_CHANGE_SUMMARY.md` is a rationale document. It does not override the detailed plan and contract files.

### Obsolete, Replaced, Or Deleted Documents

| File | Current state | Recommendation | Rationale |
| --- | --- | --- | --- |
| `MANIFEST.txt` | Restored concurrently as an untracked historical file | Supersede with `MANIFEST.md` and `SHA256SUMS.txt`; preserve the old manifest only as legacy provenance | The restored file exactly matches the pre-remediation Git blob. |
| `docs/10_PHASE_0_1_IMPLEMENTATION_PLAN.md` | Restored from the pre-remediation commit | Preserve at its original path as historical Phase 0-1 traceability | Its notice states that schema-3 remediation is governed by the Phase 4A contracts. |
| `docs/14_STATISTICAL_GUARDRAILS.md` | Restored from the pre-remediation commit | Keep as active Phase 5 governance | The safeguards remain binding and are not superseded by schema-3 remediation. |
| `docs/15_PHASE_2_IMPLEMENTATION_PLAN.md` | Restored concurrently from a recoverable legacy Git blob | Preserve as an untracked legacy implementation record pending a tracking decision | It documents completed schema-2 Phase 2 behavior and does not govern schema 3. |
| `docs/16_PHASE_3_IMPLEMENTATION_PLAN.md` | Restored concurrently from a recoverable legacy Git blob | Preserve as an untracked legacy implementation record pending a tracking decision | It documents the superseded Phase 3 overlay design. |
| `docs/17_PHASE_4_IMPLEMENTATION_PLAN.md` | Restored concurrently from a recoverable legacy Git blob | Preserve as an untracked legacy implementation record pending a tracking decision | It documents completed legacy reconstruction behavior. |

### Resolved Slice 0 Decisions

- `wms-remediation-safety-checkpoint` is the single canonical preservation tag. Conflicting preservation-tag references were corrected; no alias tag will be added.
- Schema-3 `simulation_run` excludes `scenario_name` and `scenario_version`. Scenario identity and hidden intent remain external to the WMS.
- Standard WMS reconciliation compares live `inventory_master` with a selected WMS snapshot. Full transaction replay remains an external read-only analysis output and is never imported into or written back into the WMS.
- `init-wms` is canonical for schema 3. `init-db` remains temporarily as a clearly labeled legacy schema-1/2 path.

### Generated Or Local-Only Content

No untracked generated artifacts were present at the start of the audit. Existing ignore rules exclude common generated databases, reconstruction exports, caches, and virtual environments.

`MANIFEST.md` and `SHA256SUMS.txt` are package-provenance files, not runtime-generated project outputs.

During final decision-resolution verification, four historical files appeared
concurrently as untracked content: `MANIFEST.txt` and docs 15-17. The audit
process did not create or modify them. Their Git blob IDs
match the pre-remediation commit or recoverable legacy blobs, so they are
preserved and reported separately from this audit's documentation edits.

## Current Versus Target Dependency Diagram

Current legacy dependency shape:

```text
CLI
  -> application phase workflows
    -> generation modules
      -> domain state processors
        -> in-memory physical and system dictionaries
      -> storage repositories
        -> schema 1/2 operational tables
        -> opening/closing snapshots
    -> validation and reconstruction readers
```

The current operations generator combines baseline operations, controlled failure overlays, physical truth, analyst-facing system state, persistence, restricted truth construction, and closing snapshots.

Target schema-3 dependency shape:

```text
CLI / notebooks / reports
  -> application workflows
    -> scenario drivers
      -> public WMS command services
    -> physical simulator
      -> public WMS command services when recorded action occurs
    -> WMS reports and validators
      -> WMS read models

WMS command services
  -> live inventory_master
  -> immutable inventory_transaction
  -> workflow/audit tables
  -> snapshots derived from live state

Analysis
  -> read-only WMS source data
  -> derived reconstruction outputs outside source WMS tables
```

Required boundary: WMS core must not depend on scenarios, physical simulator, ground truth, notebooks, or analysis outputs. Scenario drivers must not write WMS storage directly.

## Module Inventory And Classification

| Module | Classification | Slice 1+ migration note |
| --- | --- | --- |
| `src/operational_variance_toolkit/__init__.py` | Retain substantially unchanged | Package plumbing only. |
| `src/operational_variance_toolkit/__main__.py` | Retain substantially unchanged | Keep thin CLI entry point. |
| `src/operational_variance_toolkit/version.py` | Retain substantially unchanged | Version metadata remains useful. |
| `src/operational_variance_toolkit/errors.py` | Retain substantially unchanged | Extend only if schema-3 WMS errors need named types. |
| `src/operational_variance_toolkit/config.py` | Adapt behind the new WMS interface | Retain deterministic loading and hashing; separate WMS, simulator, and scenario configuration. |
| `src/operational_variance_toolkit/cli.py` | Adapt behind the new WMS interface | Preserve thin parsing/formatting; route schema versions and add WMS/report commands later. |
| `src/operational_variance_toolkit/domain/identifiers.py` | Retain substantially unchanged | Deterministic identifiers remain valid. |
| `src/operational_variance_toolkit/domain/time.py` | Retain substantially unchanged | Timezone and UTC rules remain valid. |
| `src/operational_variance_toolkit/domain/run.py` | Retain substantially unchanged | Run metadata and configuration hash remain valid. |
| `src/operational_variance_toolkit/domain/opening_inventory.py` | Refactor substantially | Remove corrected-path handling-unit semantics; split physical opening state from WMS live opening inventory. |
| `src/operational_variance_toolkit/domain/operations.py` | Refactor substantially | Split workflow records and WMS commands from physical simulator state; retire in-memory recorded-system balances for schema 3. |
| `src/operational_variance_toolkit/generation/random_source.py` | Retain substantially unchanged | Named RNG streams remain valid. |
| `src/operational_variance_toolkit/generation/master_data.py` | Refactor substantially | Generate schema-3 `item_master` dimensions and clean `location_master`; remove fixed case capacity and equipment area. |
| `src/operational_variance_toolkit/generation/opening_inventory.py` | Refactor substantially | Split WMS initialization from physical simulator initialization; remove schema-3 handling-unit path. |
| `src/operational_variance_toolkit/generation/operations.py` | Retire after compatibility migration | Responsibilities should move into WMS services, simulator, baseline drivers, and external scenario drivers. |
| `src/operational_variance_toolkit/application/phase1.py` | Adapt behind the new WMS interface | Keep legacy initialization path; route corrected initialization to WMS services. |
| `src/operational_variance_toolkit/application/phase2.py` | Adapt behind the new WMS interface | Orchestrate simulator and scenario drivers without coordinating direct generator writes. |
| `src/operational_variance_toolkit/application/phase4.py` | Adapt behind the new WMS interface | Route schema 3 reconstruction to immutable audit replay while preserving source outputs. |
| `src/operational_variance_toolkit/storage/database.py` | Retain substantially unchanged | Extend for schema-3 lifecycle and transaction/unit-of-work support. |
| `src/operational_variance_toolkit/storage/schema.py` | Refactor substantially | Preserve schema 1/2 definitions; add schema `3.0.0` tables and views. |
| `src/operational_variance_toolkit/storage/repositories.py` | Refactor substantially | Split legacy repositories from WMS command repositories, read models, and report queries. |
| `src/operational_variance_toolkit/storage/reconstruction.py` | Adapt behind the new WMS interface | Read `inventory_transaction`, `inventory_master`, and snapshots for schema 3. |
| `src/operational_variance_toolkit/storage/reconstruction_outputs.py` | Retain substantially unchanged | Derived-output writer remains useful. |
| `src/operational_variance_toolkit/storage/ground_truth.py` | Adapt behind the new WMS interface | Keep restricted artifact isolation; connect to external scenario drivers. |
| `src/operational_variance_toolkit/validation/result.py` | Retain substantially unchanged | Result model remains useful. |
| `src/operational_variance_toolkit/validation/phase1.py` | Adapt behind the new WMS interface | Preserve legacy validation; add schema-3 master/live/audit checks separately. |
| `src/operational_variance_toolkit/validation/phase2.py` | Adapt behind the new WMS interface | Preserve legacy validation; add schema-3 workflow/audit/current-state checks separately. |
| `src/operational_variance_toolkit/validation/dataset.py` | Adapt behind the new WMS interface | Version-route validation and describe behavior. |
| `src/operational_variance_toolkit/validation/scenario.py` | Adapt behind the new WMS interface | Keep restricted validation; update around external scenario protocols. |
| `src/operational_variance_toolkit/analysis/reconstruction.py` | Refactor substantially | Replace workflow-inferred ledger with immutable transaction replay for schema 3. |
| `src/operational_variance_toolkit/reporting/__init__.py` | Replace empty surface | Add tested standard WMS report service layer later. |

No module requires an immediate wholesale deletion before compatibility migration. Several legacy paths should remain available for schema 1/2 regression coverage until schema 3 reaches parity.

## Current Architecture Conflicts

| Conflict | Current location | Target remediation |
| --- | --- | --- |
| Scenario logic embedded in generation behavior | `generation/operations.py` contains `_ScenarioOverlay`, forced shorts, skipped replenishment, masked damage, selector false-lead allocation, recovery adjustments, and restricted truth assembly. | Move all scenario-specific behavior to external scenario drivers that submit ordinary WMS commands. |
| In-memory system inventory substitutes for live inventory master | `domain/operations.py` stores `physical` and `system` dictionaries in `SimulatorInventoryState`; `StateTransitionProcessor` mutates both. | Persist analyst-facing current state in `inventory_master`; keep physical state outside WMS. |
| Snapshots substitute for operational current state | `storage/repositories.py` builds opening system state from `inventory_snapshot`; `generation/operations.py` writes closing snapshots from in-memory state. | Treat snapshots as derived scheduled report captures from `inventory_master`, not as live state. |
| Handling-unit assumptions conflict with corrected model | `domain/opening_inventory.py`, `generation/opening_inventory.py`, `storage/schema.py`, and tests model `handling_unit`. | Remove pallet/HU lifecycle from schema 3; keep only legacy compatibility readers/tests. |
| Slot assignment substitutes for live assignment | `slot_assignment` drives item-location assignment and replenishment behavior. | Store current assignment and replenishment controls in `inventory_master`, one row per location. |
| Fixed location case capacity conflicts with item-dependent cube | `location.capacity_cases` appears in schema and master-data generation. | Use `location_master.pallet_capacity`; calculate case/cube fit through item dimensions and rules. |
| Equipment-area field conflicts with target location model | `location.equipment_area` and system-event use of equipment area appear in legacy model. | Remove equipment area; use aisle/zone/location fields only. |
| Runtime code writes operational tables directly | Generation modules write through repositories and raw SQL rather than WMS command services. | All recorded quantity changes must pass through WMS application services that update live state and immutable audit rows atomically. |

## Source And Schema Migration Table

| Legacy source or table | Target schema-3 destination | Action |
| --- | --- | --- |
| `item` | `item_master` | Add retained dimensions, calculated cube, cases-per-layer, layers-per-pallet, and validation. |
| `location` | `location_master` | Remove `capacity_cases` and `equipment_area`; retain location geometry and pallet capacity. |
| `slot_assignment` | Assignment fields in `inventory_master` | Retire as current-state source after compatibility migration. |
| `handling_unit` | No schema-3 equivalent | Retire for corrected model; preserve legacy regression coverage. |
| `inventory_snapshot` | `inventory_snapshot` with batch and detail identifiers | Convert to report capture from live WMS state. |
| In-memory `system` quantities | `inventory_master.qty_on_hand_cases` | Replace with persisted live inventory by location. |
| Workflow-inferred quantity ledger | `inventory_transaction` | Every quantity change writes immutable audit rows. |
| `pick_event` and trip workflow tables | WMS command result/audit-linked workflow tables | Preserve operational concepts; link to transaction IDs where quantity changes occur. |
| `replenishment_event` | WMS transfer/confirmation command records plus audit rows | Split task lifecycle from inventory movement. |
| `qa_event` and adjustment rows | QA command records plus adjustment transactions | Preserve QA facts; record quantity changes only through WMS transaction service. |
| `system_event` with equipment area | Neutral system-event model using location or aisle context | Remove equipment-area dependency. |
| `event_sequence_registry` | Retain or adapt for deterministic event ordering | Keep deterministic ordering across WMS transactions and workflow records. |
| `ground_truth` JSON artifact | Restricted scenario-validation artifact | Preserve outside analyst-facing WMS database. |
| Phase 4 reconstruction exports | Schema-3 reconstruction from `inventory_transaction` | Preserve output names where practical, but change source semantics. |

## Test Classification

| Test file | Classification | Needed schema-3 equivalent or adaptation |
| --- | --- | --- |
| `tests/conftest.py` | Valid with schema-3 adaptation | Add schema-3 fixture factories while retaining legacy fixtures. |
| `tests/test_config.py` | Still valid unchanged | Keep config load/hash coverage; add WMS/scenario config tests later. |
| `tests/test_identity_and_primitives.py` | Still valid unchanged | Deterministic IDs, time, and run metadata remain valid. |
| `tests/test_master_data_generation.py` | Legacy regression test | Add schema-3 item dimensions and clean location master tests. |
| `tests/test_opening_inventory.py` | Legacy regression test | Add schema-3 opening `inventory_master` and physical simulator initialization tests. |
| `tests/test_storage_schema.py` | Legacy regression test | Add schema `3.0.0` table, constraint, and version routing tests. |
| `tests/test_phase1_workflows.py` | Legacy regression test | Add corrected WMS initialization tests without HU/snapshot-as-state assumptions. |
| `tests/test_phase2_operations_domain.py` | Valid with schema-3 adaptation | Recast state transition coverage around WMS commands and simulator state. |
| `tests/test_phase2_workflows.py` | Valid with schema-3 adaptation | Replace direct generator-write assertions with WMS command/audit/current-state assertions. |
| `tests/test_phase3_workflows.py` | Valid with schema-3 adaptation | Keep scenario pattern validation, but require external scenario-driver boundaries. |
| `tests/test_phase4_reconstruction.py` | Valid with schema-3 adaptation | Reconstruct from `inventory_transaction` and compare with live master and snapshots. |
| `tests/test_phase4_workflow.py` | Valid with schema-3 adaptation | Route workflow to schema-3 reconstruction outputs while preserving source files. |
| `tests/test_reproducibility.py` | Valid with schema-3 adaptation | Continue equivalent-output comparison excluding timestamps and physical metadata. |
| `tests/test_validation_rules.py` | Legacy regression test | Add schema-3 validation for master data, live state, immutable audit, reports, and no leakage. |
| `tests/test_cli.py` | Valid with schema-3 adaptation | Add command routing, report command, unsupported schema behavior, and useful errors. |

Missing corrected-model tests:

- Schema `3.0.0` creation and metadata.
- `item_master` dimensions and calculated cube.
- `location_master` pallet capacity with no fixed case capacity and no equipment area.
- `inventory_master` keyed by location with one item/code date per occupied location.
- Atomic WMS commands that update `inventory_master` and `inventory_transaction` together.
- Immutable inventory audit history and deterministic replay.
- Physical simulator state external to WMS storage.
- Scenario drivers unable to write WMS operational tables directly.
- Snapshot/report derivation from live WMS state.
- Standard WMS reports from `docs/22_STANDARD_WMS_REPORTS_CONTRACT.md`.
- Three-way reconciliation: audit replay, live master, and scheduled closing snapshot.
- No scenario-specific logic inside WMS modules.

Obsolete tests should not be deleted in Slice 1. Mark them as legacy regression tests or migrate them only when their schema-3 equivalents exist.

## Remediation Contract Consistency

The remediation documents consistently establish these target rules:

- independent mini-WMS;
- external physical simulator;
- external scenario drivers;
- live `inventory_master` keyed by `location_id`;
- immutable `inventory_transaction` audit history;
- item dimensions with calculated cube;
- location pallet capacity but no fixed case capacity;
- no equipment-area field;
- no pallet IDs in the initial corrected model;
- reports and snapshots derived from live WMS state;
- no scenario-specific logic inside the WMS.

The Slice 0 contradictions and ambiguities listed above are resolved in the governing documents before implementation begins.

## Risks And Sequencing Constraints

- Preserve legacy schema 1/2 readers, validators, and tests until schema 3 reaches acceptance parity.
- Do not migrate or edit existing generated schema 2 artifacts in place.
- Add schema 3 beside legacy schema definitions before redirecting workflows.
- Build WMS services before moving scenario behavior so there is a stable command boundary.
- Keep physical simulator and restricted ground truth out of analyst-facing WMS tables.
- Avoid introducing report views that read derived reconstruction outputs from the source WMS database.
- Apply the resolved neutral run-metadata contract when schema 3 is implemented.
- Add `init-wms` without changing the legacy `init-db` meaning.

## Exact Proposed Slice 1 File Changes

Slice 1 should be limited to schema-3 core source and tests:

- `src/operational_variance_toolkit/storage/schema.py`: add schema `3.0.0` creation for `simulation_run`, `item_master`, `location_master`, `inventory_master`, `inventory_transaction`, `inventory_snapshot` with batch/detail identity, and required metadata; preserve schema 1/2.
- `src/operational_variance_toolkit/storage/database.py`: add or expose schema-version routing needed to initialize schema 3 without changing legacy behavior.
- `src/operational_variance_toolkit/storage/repositories.py` or new storage modules under `storage/`: add minimal schema-3 insert/read helpers for master files only if required by tests; do not add business-generation logic.
- `src/operational_variance_toolkit/generation/master_data.py` or a new WMS master-data module: generate schema-3 `item_master` dimensions and `location_master` pallet capacity without equipment area or fixed case capacity.
- `src/operational_variance_toolkit/validation/dataset.py` plus a new schema-3 validation module if needed: validate schema version and corrected master-data constraints.
- `tests/test_storage_schema.py`: add schema-3 DDL, constraints, and version metadata tests.
- `tests/test_master_data_generation.py`: add deterministic item-dimension and location-master tests.
- `tests/test_validation_rules.py`: add schema-3 rejection tests for equipment area, fixed case capacity, missing calculated cube, invalid location inventory cardinality, and malformed audit metadata.
- `PROJECT_STATUS.md`: update only after Slice 1 verification.

Slice 1 should not add WMS command services, normal operations generation, scenarios, reconstruction, or reports unless the approved Slice 1 contract is changed.

## Slice 1 Acceptance Criteria

- Schema `3.0.0` can be created in a fresh temporary SQLite database.
- Legacy schema 1/2 creation and validation tests still pass.
- `item_master` stores retained dimensions and system-calculated cube.
- `location_master` stores pallet capacity and excludes equipment area and fixed case capacity.
- Initial `inventory_master` shape is present and keyed by `location_id`.
- `inventory_transaction` shape is present for immutable audit history, even if command services are not implemented yet.
- Schema-3 validation rejects prohibited legacy columns and malformed master records.
- No scenario driver, physical simulator, report generation, reconstruction, or Phase 5 analytical behavior is implemented.
- `uv run pytest`, `uv run ruff check .`, and `uv run ruff format --check .` pass.

## Review Decisions Resolved

1. Keep `wms-remediation-safety-checkpoint` as the only canonical preservation tag.
2. Restore docs 10 at its original path as clearly superseded historical traceability.
3. Restore docs 14 as active Phase 5 statistical governance.
4. Remove scenario name and version from schema-3 WMS metadata; retain only neutral provenance.
5. Use `init-wms` for schema 3 and retain a labeled legacy `init-db` compatibility path.
6. Limit standard WMS reconciliation to live-master versus selected-snapshot facts; keep full replay external.

## Slice 0 Acceptance Statement

Slice 0 and its decision-resolution follow-up changed documentation only. Runtime code, tests, configuration, schema, dependencies, and generated artifacts were not changed.

## Documentation-Only Verification

Executed after resolving the Slice 0 review decisions:

| Command | Result |
| --- | --- |
| `git status --short` | Exit 0; 11 modified documentation files and eight untracked historical/audit documents. No runtime files are changed. |
| `git diff --check` | Exit 0; no whitespace errors. Git reported expected LF-to-CRLF working-copy warnings for modified tracked Markdown files. |
| `uv run pytest` | Exit 0; 106 collected, 106 passed in 57.67 seconds. |
| `uv run ruff check .` | Exit 0; all checks passed. |
| `uv run ruff format --check .` | Exit 0; 89 files already formatted. |
