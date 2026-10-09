# 21 — Schema and Code Migration Map

## 1. Purpose

This document translates the legacy implementation into the corrected schema `3.0.0` architecture. It is a migration guide, not permission for a wholesale rewrite.

## 2. Migration principles

- Preserve working deterministic infrastructure.
- Add corrected contracts before removing legacy behavior.
- Generate new artifacts rather than migrating generated databases.
- Keep legacy schema validation where practical.
- Split behavior along WMS/simulation/scenario boundaries.
- Avoid mixing large file moves with semantic changes when possible.
- Classify tests before deletion or adaptation.

## 3. Schema mapping

| Legacy schema concept | Corrected schema concept | Action |
|---|---|---|
| `item` | `item_master` | replace in schema 3; add dimensions/pallet pattern; calculate cube |
| `location` | `location_master` | replace in schema 3; remove case capacity/equipment area/live state |
| `slot_assignment` | assignment fields in `inventory_master` | supersede as current-state source; retain history only if later required |
| `handling_unit` | none in schema 3 | remove from corrected path; retain legacy reader/tests |
| `inventory_snapshot` | `inventory_snapshot` report capture | adapt to batch/detail and live-master capture |
| in-memory system quantity | `inventory_master` | persist recorded WMS state |
| event-derived ledger | `inventory_transaction` | write audit at command time; reconstruct from audit |
| `pick_event` | `pick_event` | retain/adapt with command ID and audit linkage |
| `replenishment_task` | `replenishment_task` | retain/adapt; confirmation writes two audit rows |
| `qa_event` | `qa_event` | retain/adapt; no direct inventory effect |
| `inventory_adjustment` | `inventory_adjustment` | retain/adapt; one matching audit row |
| `system_event` | `system_event` | retain/adapt; no equipment-area master dependency |
| `event_sequence_registry` | retain | adapt to WMS command chronology |

## 4. Domain-code mapping

The exact current repository may differ from the earlier snapshot. Inspect current symbols before acting.

| Likely legacy module | Corrected destination/responsibility | Migration guidance |
|---|---|---|
| `domain/run.py` | shared run metadata | retain |
| `domain/identifiers.py` | shared deterministic IDs | retain |
| `domain/time.py` | shared time rules | retain |
| `domain/opening_inventory.py` | `wms/domain/inventory.py` | adapt records/invariants; separate physical state |
| `domain/operations.py` | `wms/domain/operations.py` + commands | split workflow records from scenario generation |
| `generation/master_data.py` | profile generators + WMS initialization | adapt item dimensions/location fields |
| `generation/opening_inventory.py` | WMS initializer + physical initializer | split recorded and physical responsibilities |
| `generation/operations.py` | baseline scenario + simulation runner + WMS calls | major split; remove storage/state ownership |
| `generation/random_source.py` | shared deterministic streams | retain |
| `application/phase1.py` | initialization workflow | adapt to schema 3 |
| `application/phase2.py` | `generate_run.py` orchestration | retain orchestration only; call scenario/WMS services |
| Phase 3 overlay modules | `scenarios/patterns/*` | move scenario intent outside WMS |
| `storage/schema.py` | version-routed schema 1/2/3 | extend, do not overwrite legacy definitions |
| `storage/repositories.py` | split WMS repositories/read models | adapt; scenarios cannot import |
| `storage/database.py` | database lifecycle/unit of work | retain and extend atomic command support |
| `validation/phase1.py` | legacy validator | retain for schema 1 |
| `validation/phase2.py` | legacy schema 2 validator | retain/adapt as legacy |
| dataset validation | schema 3 WMS validator | add separate corrected validator |
| Phase 4 reconstruction | audit-based reconstruction | adapt source from workflow inference to inventory audit |
| CLI | version-routed commands/report command | adapt without silent behavior changes |

## 5. Recommended target modules

A practical incremental target:

```text
src/operational_variance_toolkit/
    wms/
        domain/
        application/
        storage/
        reporting/
    simulation/
    scenarios/
    analysis/
```

Do not require moving every legacy utility immediately. Shared deterministic/time/config modules may remain at package root.

## 6. Migration sequence

### Step 1 — Add schema 3 alongside legacy schemas

Do not modify existing schema constants in place. Introduce explicit version selection.

### Step 2 — Add corrected records and validators

Keep legacy domain records until schema 3 workflows no longer depend on them.

### Step 3 — Add WMS command services

Directly test services against temporary schema 3 databases.

### Step 4 — Add standard reports

Reports prove live inventory is independently useful before simulation migration.

### Step 5 — Add simulator/scenario protocol

Migrate baseline behavior first.

### Step 6 — Migrate investigation patterns

Preserve scenario calibration but remove generator-internal overlays.

### Step 7 — Adapt reconstruction

Use inventory audit and three-way reconciliation.

### Step 8 — Retire superseded corrected-path code

Remove only after no supported schema 3 path references it and tests classify the deletion.

## 7. Test migration matrix

Record one classification for each current test file.

| Classification | Meaning | Action |
|---|---|---|
| Binding unchanged | requirement remains exact | keep |
| Binding adapted | requirement remains, schema/API changed | update assertions/fixtures |
| Legacy compatibility | validates schema 1/2 behavior | retain under legacy name |
| Superseded | requirement explicitly replaced | replace with new test and document removal |

Likely examples:

- identity/random/time tests: binding unchanged;
- schema creation: binding adapted plus legacy compatibility;
- master-data generation: binding adapted;
- handling-unit tests: legacy compatibility or superseded;
- opening snapshot tests: binding adapted;
- phase 2 workflow tests: binding adapted through WMS commands;
- phase 3 scenario tests: binding adapted through external drivers;
- phase 4 reconstruction tests: binding adapted to audit/live-master comparison.

## 8. Public command migration

Preserve existing commands unless a documented transition is needed.

Recommended approach:

- `config-check` unchanged;
- `generate` creates the schema version declared by configuration;
- `validate` and `describe` route by schema;
- `scenario-check` remains developer-only;
- `reconstruct` routes by schema and produces corrected outputs for schema 3;
- add `report` for standard WMS inquiries;
- use `init-wms` as the canonical schema-3 initialization command; and
- preserve `init-db` temporarily for schema-1/2 compatibility, labeled as the
  legacy path in CLI help and public documentation.

Do not silently change a command’s meaning in a way that could overwrite existing artifacts.

## 9. Artifact migration

Do not transform these in place:

- legacy baseline SQLite;
- legacy investigation SQLite;
- legacy restricted truth;
- legacy reconstruction directories.

Generate new names such as:

```text
artifacts/data/schema3_baseline.sqlite3
artifacts/data/schema3_investigation.sqlite3
artifacts/restricted_ground_truth/schema3_investigation.json
artifacts/analysis/schema3_baseline/
artifacts/analysis/schema3_investigation/
```

Legacy artifacts remain comparison references.

## 10. Data-generation migration details

### Item generator

Legacy cube generation becomes dimension generation plus WMS calculation.

### Location generator

Remove case-capacity generation. Generate pallet capacity and profile fields only.

### Inventory initializer

Create every inventory-master row, assign pick items, populate reserve inventory, set code dates, and capture opening snapshot.

### Operation generator

Recorded state must not be mutated directly. Baseline generation produces scenario actions and WMS commands.

### Scenario overlays

Move target selection and protocol timing outside WMS. Preserve named streams and calibration.

## 11. Reconstruction migration details

Legacy reconstruction likely derives deltas from picks, replenishments, and adjustments. Corrected reconstruction:

1. loads opening snapshot;
2. loads ordered `inventory_transaction` rows;
3. applies signed deltas;
4. validates before/after values;
5. enriches from workflow files;
6. compares with live inventory master;
7. compares with closing snapshot.

The old workflow-derived calculation may remain as a diagnostic cross-check but is not authoritative for schema 3.

## 12. Code-removal rules

Before deleting a legacy module or field:

- identify all imports and tests;
- confirm schema 1/2 readers do not require it;
- confirm corrected replacement is accepted;
- record the removal in the implementation summary;
- avoid deleting historical docs/artifacts needed for context.

## 13. Migration completion evidence

The final remediation report must include:

- old-to-new table map;
- module move/split summary;
- test classification counts;
- legacy validators retained;
- obsolete paths removed;
- new schema and report samples;
- artifact comparison;
- unresolved technical debt.
