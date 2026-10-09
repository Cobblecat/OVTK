# 04 — Data Model and Data Dictionary

## 1. Purpose

This document defines the corrected schema-version `3.0.0` analyst-facing WMS database.

The database is a credible miniature WMS source system, not a flat analytical dataset. It provides stable master files, live recorded inventory, workflow files, immutable inventory audit history, and scheduled snapshots.

The physical simulator and restricted ground truth remain outside the analyst-facing database.

## 2. Modeling principles

1. Item identity is separate from inventory state.
2. Location identity is separate from live item assignment and quantity.
3. `inventory_master` is the authoritative current WMS balance by location.
4. Every post-initialization quantity change is supported by immutable `inventory_transaction` rows.
5. Workflow files describe operational processes; audit rows describe recorded inventory effects.
6. Snapshots are report/checkpoint captures, not current state.
7. Physical truth is separate from recorded WMS state.
8. Scenario intent is separate from all WMS files.
9. The initial model uses integer cases, one item per location, one code date per location, and no pallet IDs.
10. Every business table includes `run_id` for provenance and safe joins.

Project documentation may use the AS/400-style term "file" for an operational
entity and "table" for its SQLite implementation. Code and SQL use the canonical
table names.

## 3. Entity overview

```text
simulation_run
    |
    +-- facility -- zone -- location_master -- inventory_master
    |                         |                    |
    |                         |                    `-- inventory_transaction
    |                         |
    |                         `-- inventory_snapshot
    |
    +-- item_master ---------> inventory_master
    |       |                 inventory_transaction
    |       |                 pick_event
    |       |                 replenishment_task
    |       |                 qa_event
    |       `---------------- inventory_adjustment
    |
    +-- operator -- shift -- work_assignment
    |                 |
    |                 `-- trip -- pick_event
    |
    +-- replenishment_task
    +-- qa_event
    +-- inventory_adjustment
    +-- system_event
    `-- event_sequence_registry

Restricted physical state and ground truth are outside this database.
```

## 4. Controlled enumerations

Python enums, SQLite checks, validators, report filters, and documentation must agree.

### Zone code

`FROZEN`, `CHILLED`, `AMBIENT`

### Location type

`PICK`, `RESERVE`, `STAGING`, `QA_HOLD`, `DOCK`, `INACTIVE`

### Operator role

`SELECTOR`, `REPLENISHMENT`, `QA`, `INVENTORY_CONTROL`, `SYSTEM`

### Velocity class

`A`, `B`, `C`

### Replenishment status

`CREATED`, `STARTED`, `CONFIRMED`, `CANCELED`, `INCOMPLETE`

### QA event type

`DAMAGE_FOUND`, `HOLD_PLACED`, `RESTACK`, `RELEASED`, `DISPOSED`, `COUNT_VERIFICATION`

### Adjustment reason

`COUNT_CORRECTION`, `DAMAGE`, `FOUND_PRODUCT`, `RECEIVING_VARIANCE`, `TRANSACTION_CORRECTION`, `OTHER`

### System event type

`SCANNER_INTERRUPTION`, `SYSTEM_LAG`, `EQUIPMENT_DELAY`, `BLOCKED_LOCATION`, `NETWORK_INTERRUPTION`

### Inventory transaction type

`PICK`, `TRANSFER_OUT`, `TRANSFER_IN`, `ADJUSTMENT`, `DAMAGE`, `FOUND_PRODUCT`, `COUNT_CORRECTION`, `ASSIGNMENT`, `CLEAR_LOCATION`

`ASSIGNMENT` and `CLEAR_LOCATION` may create zero-quantity audit records only when an explicit location-assignment workflow is implemented. Ordinary quantity reconstruction ignores zero-delta records.

### Snapshot type

`OPENING_SYSTEM`, `CLOSING_SYSTEM`, `SHIFT_END`, `CYCLE_COUNT`, `VERIFIED_COUNT`

## 5. Metadata and facility tables

### 5.1 `schema_metadata`

| Column | Type | Null | Rule |
|---|---|---:|---|
| `schema_version` | TEXT PK | No | `3.0.0` for corrected WMS artifacts. |
| `sqlite_user_version` | INTEGER | No | `3`. |
| `created_at_utc` | TEXT | No | Artifact schema creation time. |

### 5.2 `simulation_run`

| Column | Type | Null | Rule |
|---|---|---:|---|
| `run_id` | TEXT PK | No | Deterministic identity. |
| `seed` | INTEGER | No | Nonnegative. |
| `schema_version` | TEXT | No | `3.0.0`. |
| `generator_version` | TEXT | No | Package version. |
| `config_hash` | TEXT | No | Normalized configuration SHA-256. |
| `facility_timezone` | TEXT | No | IANA zone. |
| `simulation_start_utc` | TEXT | No | Inclusive. |
| `simulation_end_utc` | TEXT | No | Exclusive and later than start. |
| `generated_at_utc` | TEXT | No | Excluded from canonical equivalence. |

One row per database.

Schema-3 WMS run metadata is neutral provenance. It does not store scenario
name, scenario version, controlled-pattern identity, or hidden intent. Those
values remain in external simulator configuration and the restricted
ground-truth artifact. Legacy schema 1/2 metadata remains unchanged.

### 5.3 `facility`

| Column | Type | Null | Rule |
|---|---|---:|---|
| `run_id` | TEXT FK | No | Parent run. |
| `facility_id` | TEXT | No | Stable ID. |
| `facility_name` | TEXT | No | Generic synthetic name. |
| `timezone` | TEXT | No | Matches run timezone. |

Primary key: `(run_id, facility_id)`.

### 5.4 `zone`

| Column | Type | Null | Rule |
|---|---|---:|---|
| `run_id` | TEXT FK | No | Parent run. |
| `zone_id` | TEXT | No | Stable ID. |
| `facility_id` | TEXT FK | No | Parent facility. |
| `zone_code` | TEXT | No | Controlled enum. |
| `min_temp_f` | REAL | Yes | Descriptive synthetic range. |
| `max_temp_f` | REAL | Yes | Descriptive synthetic range. |
| `active_flag` | INTEGER | No | 0/1. |

Primary key: `(run_id, zone_id)`.

## 6. Master files

### 6.1 `item_master`

Purpose: stable warehouse-facing item profile.

| Column | Type | Null | Rule |
|---|---|---:|---|
| `run_id` | TEXT FK | No | Parent run. |
| `item_id` | TEXT | No | Stable synthetic Item ID. |
| `item_description` | TEXT | No | Generic invented description. |
| `category` | TEXT | No | Generic product family. |
| `required_zone_code` | TEXT | No | Storage requirement. |
| `case_length_in` | REAL | No | Positive user/generator input. |
| `case_width_in` | REAL | No | Positive user/generator input. |
| `case_height_in` | REAL | No | Positive user/generator input. |
| `case_cube_ft3` | REAL | No | System-calculated and validated. |
| `case_weight_lb` | REAL | No | Positive. |
| `cases_per_layer` | INTEGER | No | Positive. |
| `layers_per_pallet` | INTEGER | No | Positive. |
| `cases_per_pallet` | INTEGER | No | Equals layer × layers. |
| `fragility_score` | REAL | No | Synthetic 0.0-1.0 handling-sensitivity scale; higher values indicate greater sensitivity. |
| `shelf_life_days` | INTEGER | Yes | Positive when used. |
| `velocity_class` | TEXT | No | A/B/C. |
| `expected_cases_per_day` | REAL | No | Positive demand parameter. |
| `active_flag` | INTEGER | No | 0/1. |

Primary key: `(run_id, item_id)`.

Calculated rules:

```text
case_cube_ft3
  = case_length_in * case_width_in * case_height_in / 1728

cases_per_pallet
  = cases_per_layer * layers_per_pallet
```

Persisted calculations use documented rounding. Validation uses a documented tolerance for floating-point cube comparison.

The WMS may expose commands to create or update items. Calculated values are not independently accepted from an external user without validation.

### 6.2 `location_master`

Purpose: stable physical/logical location profile.

| Column | Type | Null | Rule |
|---|---|---:|---|
| `run_id` | TEXT FK | No | Parent run. |
| `location_id` | TEXT | No | Stable warehouse address. |
| `zone_id` | TEXT FK | No | Parent zone. |
| `location_type` | TEXT | No | Controlled enum. |
| `aisle_code` | TEXT | Yes | Required for ordinary pick/reserve addresses. |
| `bay_number` | INTEGER | Yes | Positive when used. |
| `level_number` | INTEGER | Yes | Nonnegative when used. |
| `position_number` | INTEGER | Yes | Positive when used. |
| `pallet_capacity` | INTEGER | Yes | Positive for pallet-bearing standard slots. |
| `pickable_flag` | INTEGER | No | 1 only for active pick locations. |
| `active_flag` | INTEGER | No | 0/1. |

Primary key: `(run_id, location_id)`.

Prohibited fields:

- item assignment;
- current quantity;
- case capacity;
- equipment area;
- code date;
- replenishment trigger/target;
- last transaction.

Location rules:

- `PICK` requires aisle, bay, pallet capacity, pickable = 1, active = 1.
- `RESERVE` requires aisle, bay, pallet capacity, pickable = 0.
- `QA_HOLD`, `DOCK`, `STAGING`, and `INACTIVE` are not pickable.
- inactive locations cannot contain recorded inventory.

## 7. Live inventory and audit files

### 7.1 `inventory_master`

Purpose: authoritative current WMS inventory and mutable location assignment state.

The initial corrected model contains exactly one row for every location.

| Column | Type | Null | Rule |
|---|---|---:|---|
| `run_id` | TEXT FK | No | Parent run. |
| `location_id` | TEXT FK | No | Same ID as `location_master`; operational primary key. |
| `item_id` | TEXT FK | Yes | Current assigned/contained item. |
| `qty_on_hand_cases` | INTEGER | No | Nonnegative. |
| `code_date` | TEXT | Yes | ISO date for current product position. |
| `reorder_trigger_cases` | INTEGER | Yes | Required for slotted pick location. |
| `minimum_qty_cases` | INTEGER | Yes | Required for slotted pick location. |
| `target_qty_cases` | INTEGER | Yes | Required for slotted pick location. |
| `maximum_qty_cases` | INTEGER | Yes | Required for slotted pick location; cannot exceed dynamic physical max. |
| `last_transaction_id` | TEXT FK | Yes | Last inventory audit line affecting this row. |
| `last_updated_utc` | TEXT | No | Opening timestamp or most recent accepted change. |

Primary key: `(run_id, location_id)`.

General rules:

- Exactly one inventory row per location.
- `qty_on_hand_cases` is integer and nonnegative.
- Quantity > 0 requires item ID.
- Null item requires quantity = 0 and code date null.
- An occupied location’s item required zone must match the location zone.
- No pallet ID or handling-unit field exists in schema `3.0.0`.

Pick-location rules:

- item ID is required even when quantity is zero;
- trigger/minimum/target/maximum are required and nonnegative;
- `minimum <= reorder_trigger <= target <= maximum`;
- `maximum <= pallet_capacity * item.cases_per_pallet`;
- ordinary pick and replenishment commands cannot change the item assignment.

Reserve/staging rules:

- replenishment controls are null;
- item may be null when empty;
- when quantity reaches zero, item and code date are cleared by default;
- a different item cannot enter until the location is empty.

Inactive/non-inventory rules:

- item null;
- quantity zero;
- code date null;
- replenishment controls null.

### 7.2 `inventory_transaction`

Purpose: immutable location-level WMS audit history.

| Column | Type | Null | Rule |
|---|---|---:|---|
| `run_id` | TEXT FK | No | Parent run. |
| `transaction_id` | TEXT | No | Unique immutable audit-line ID. |
| `transaction_group_id` | TEXT | No | Groups lines from one accepted command. |
| `command_id` | TEXT | No | Idempotency identifier. |
| `event_sequence` | INTEGER | No | Deterministic WMS command order. |
| `line_number` | INTEGER | No | Positive order inside transaction group. |
| `transaction_type` | TEXT | No | Controlled enum. |
| `location_id` | TEXT FK | No | Location whose balance changed or assignment was audited. |
| `related_location_id` | TEXT FK | Yes | Other side of a movement. |
| `item_id` | TEXT FK | No | Item affected. |
| `qty_delta_cases` | INTEGER | No | Signed; may be zero only for approved assignment records. |
| `balance_before_cases` | INTEGER | No | Nonnegative. |
| `balance_after_cases` | INTEGER | No | Nonnegative. |
| `operator_id` | TEXT FK | Yes | Acting user/role where applicable. |
| `event_utc` | TEXT | No | Operational effective time. |
| `recorded_utc` | TEXT | No | WMS recording time, at or after event under ordinary rules. |
| `reason_code` | TEXT | Yes | Controlled or documented code. |
| `source_record_type` | TEXT | No | `PICK`, `REPLENISHMENT`, `ADJUSTMENT`, or approved source. |
| `source_record_id` | TEXT | No | Workflow source identifier. |

Primary key: `(run_id, transaction_id)`.

Uniqueness:

- `(run_id, event_sequence, line_number)` unique.
- `(run_id, command_id, line_number)` unique.

Audit rules:

```text
balance_after_cases
    = balance_before_cases + qty_delta_cases
```

Rows are append-only after commit. Normal application services provide no update or delete path.

Transfer group rules:

- exactly two quantity lines for a completed one-source/one-destination transfer;
- same item and absolute quantity;
- source negative, destination positive;
- related locations point to each other;
- sum of deltas = 0.

## 8. Labor and schedule files

### 8.1 `operator`

| Column | Type | Null | Rule |
|---|---|---:|---|
| `run_id` | TEXT FK | No | Parent run. |
| `operator_id` | TEXT | No | Synthetic neutral ID. |
| `role` | TEXT | No | Controlled enum. |
| `home_zone_id` | TEXT FK | Yes | Typical area, not a restriction. |
| `shift_code` | TEXT | No | Stable label. |
| `experience_months` | INTEGER | No | Nonnegative synthetic covariate. |
| `active_flag` | INTEGER | No | 0/1. |

Primary key: `(run_id, operator_id)`.

### 8.2 `shift`

| Column | Type | Null | Rule |
|---|---|---:|---|
| `run_id` | TEXT FK | No | Parent run. |
| `shift_id` | TEXT | No | Stable ID. |
| `facility_id` | TEXT FK | No | Facility. |
| `shift_code` | TEXT | No | Stable label. |
| `start_utc` | TEXT | No | Inclusive. |
| `end_utc` | TEXT | No | Later than start. |
| `operating_date_local` | TEXT | No | ISO local date. |

### 8.3 `work_assignment`

| Column | Type | Null | Rule |
|---|---|---:|---|
| `run_id` | TEXT FK | No | Parent run. |
| `work_assignment_id` | TEXT | No | Stable ID. |
| `operator_id` | TEXT FK | No | Assigned operator. |
| `shift_id` | TEXT FK | No | Shift. |
| `role` | TEXT | No | Must match operator capability. |
| `zone_id` | TEXT FK | Yes | Assigned zone where applicable. |
| `start_utc` | TEXT | No | Within shift. |
| `end_utc` | TEXT | No | Later than start and within shift. |

## 9. Operational workflow files

### 9.1 `trip`

| Column | Type | Null | Rule |
|---|---|---:|---|
| `run_id` | TEXT FK | No | Parent run. |
| `trip_id` | TEXT | No | Stable ID. |
| `shift_id` | TEXT FK | No | Shift. |
| `selector_id` | TEXT FK | No | SELECTOR role. |
| `assigned_zone_id` | TEXT FK | No | Primary zone. |
| `start_utc` | TEXT | No | Within shift. |
| `end_utc` | TEXT | No | Later than start. |
| `continuation_flag` | INTEGER | No | 0/1. |
| `planned_pick_lines` | INTEGER | No | Positive. |
| `planned_cases` | INTEGER | No | Positive. |

### 9.2 `pick_event`

Purpose: attempted and confirmed pick workflow record.

| Column | Type | Null | Rule |
|---|---|---:|---|
| `run_id` | TEXT FK | No | Parent run. |
| `pick_event_id` | TEXT | No | Stable ID. |
| `command_id` | TEXT | No | WMS command identity. |
| `event_sequence` | INTEGER | No | Deterministic command order. |
| `trip_id` | TEXT FK | No | Parent trip. |
| `selector_id` | TEXT FK | No | Matches trip selector. |
| `item_id` | TEXT FK | No | Requested item. |
| `pick_location_id` | TEXT FK | No | PICK location. |
| `event_utc` | TEXT | No | Attempt time. |
| `recorded_utc` | TEXT | No | At or after event. |
| `requested_qty_cases` | INTEGER | No | Positive. |
| `picked_qty_cases` | INTEGER | No | Nonnegative. |
| `short_qty_cases` | INTEGER | No | Nonnegative. |
| `short_reason_code` | TEXT | Yes | Required when short > 0. |
| `system_qty_before_cases` | INTEGER | No | Live recorded balance before. |
| `system_qty_after_cases` | INTEGER | No | Live recorded balance after picked quantity. |
| `eligible_pick_flag` | INTEGER | No | Denominator eligibility. |

Rules:

```text
picked_qty_cases + short_qty_cases = requested_qty_cases
system_qty_after_cases = system_qty_before_cases - picked_qty_cases
```

A successful/partial pick with positive picked quantity has one matching negative `inventory_transaction` line. A full short has no quantity audit row.

### 9.3 `replenishment_task`

| Column | Type | Null | Rule |
|---|---|---:|---|
| `run_id` | TEXT FK | No | Parent run. |
| `replenishment_task_id` | TEXT | No | Stable ID. |
| `create_command_id` | TEXT | No | Task-create command. |
| `confirm_command_id` | TEXT | Yes | Confirmation command if completed. |
| `event_sequence` | INTEGER | Yes | Confirmation sequence when confirmed. |
| `item_id` | TEXT FK | No | Item moved. |
| `source_location_id` | TEXT FK | No | Reserve/staging source. |
| `destination_location_id` | TEXT FK | No | Pick destination. |
| `operator_id` | TEXT FK | Yes | REPLENISHMENT role. |
| `created_utc` | TEXT | No | Creation time. |
| `started_utc` | TEXT | Yes | Required when started. |
| `confirmed_utc` | TEXT | Yes | Required when confirmed. |
| `recorded_utc` | TEXT | No | Last WMS record time. |
| `requested_qty_cases` | INTEGER | No | Positive. |
| `confirmed_qty_cases` | INTEGER | No | Nonnegative. |
| `status` | TEXT | No | Controlled enum. |
| `delay_reason_code` | TEXT | Yes | Generic operational reason. |

A confirmed task has exactly two matching `inventory_transaction` rows in one group.

### 9.4 `qa_event`

| Column | Type | Null | Rule |
|---|---|---:|---|
| `run_id` | TEXT FK | No | Parent run. |
| `qa_event_id` | TEXT | No | Stable ID. |
| `command_id` | TEXT | No | WMS command identity. |
| `event_sequence` | INTEGER | No | Deterministic order. |
| `item_id` | TEXT FK | No | Item. |
| `location_id` | TEXT FK | No | Event location. |
| `operator_id` | TEXT FK | Yes | QA or system. |
| `event_type` | TEXT | No | Controlled enum. |
| `occurred_utc` | TEXT | No | Operational time. |
| `recorded_utc` | TEXT | No | At or after occurrence. |
| `qty_affected_cases` | INTEGER | No | Positive observational quantity. |
| `reason_code` | TEXT | No | Generic operational code. |
| `disposition_code` | TEXT | No | Hold/restack/return/dispose/release. |

The table intentionally has no direct inventory-delta field and no direct adjustment foreign key.

### 9.5 `inventory_adjustment`

| Column | Type | Null | Rule |
|---|---|---:|---|
| `run_id` | TEXT FK | No | Parent run. |
| `adjustment_id` | TEXT | No | Stable ID. |
| `command_id` | TEXT | No | WMS command identity. |
| `event_sequence` | INTEGER | No | Deterministic order. |
| `item_id` | TEXT FK | No | Item. |
| `location_id` | TEXT FK | No | Location. |
| `operator_id` | TEXT FK | Yes | Inventory-control/QA/system role. |
| `effective_utc` | TEXT | No | Inventory effective time. |
| `recorded_utc` | TEXT | No | At or after effective time under ordinary rules. |
| `qty_delta_cases` | INTEGER | No | Nonzero signed adjustment. |
| `reason_code` | TEXT | No | Controlled enum. |
| `reference_code` | TEXT | Yes | Generic source reference; never scenario truth. |

Each adjustment has exactly one matching `inventory_transaction` line.

### 9.6 `system_event`

| Column | Type | Null | Rule |
|---|---|---:|---|
| `run_id` | TEXT FK | No | Parent run. |
| `system_event_id` | TEXT | No | Stable ID. |
| `command_id` | TEXT | No | WMS command identity. |
| `event_sequence` | INTEGER | No | Deterministic order. |
| `event_type` | TEXT | No | Controlled enum. |
| `zone_id` | TEXT FK | Yes | Affected zone. |
| `location_id` | TEXT FK | Yes | Affected location. |
| `aisle_code` | TEXT | Yes | Optional event scope. |
| `start_utc` | TEXT | No | Start. |
| `end_utc` | TEXT | No | Later than start. |
| `severity_code` | TEXT | No | LOW/MEDIUM/HIGH. |
| `recorded_utc` | TEXT | No | Record time. |

At least one scope field must be populated. The location master does not carry an equipment-area field.

### 9.7 `event_sequence_registry`

Purpose: common deterministic ordering and source lookup across workflow records.

| Column | Type | Null | Rule |
|---|---|---:|---|
| `run_id` | TEXT FK | No | Parent run. |
| `event_sequence` | INTEGER | No | Unique monotonic order. |
| `event_type` | TEXT | No | Source family. |
| `source_record_id` | TEXT | No | Source identifier. |
| `event_utc` | TEXT | No | Operational timestamp. |
| `recorded_utc` | TEXT | No | WMS record timestamp. |

Primary key: `(run_id, event_sequence)`.

## 10. Snapshot file

### 10.1 `inventory_snapshot`

Purpose: immutable scheduled or verified capture of live inventory.

| Column | Type | Null | Rule |
|---|---|---:|---|
| `run_id` | TEXT FK | No | Parent run. |
| `snapshot_batch_id` | TEXT | No | Groups one report capture. |
| `snapshot_line_id` | TEXT | No | Unique detail ID. |
| `snapshot_utc` | TEXT | No | Capture time. |
| `snapshot_type` | TEXT | No | Controlled enum. |
| `location_id` | TEXT FK | No | Location. |
| `item_id` | TEXT FK | Yes | Captured current assignment. |
| `qty_on_hand_cases` | INTEGER | No | Nonnegative. |
| `code_date` | TEXT | Yes | Captured code date. |
| `last_transaction_id` | TEXT FK | Yes | Last audit line at capture. |
| `source_code` | TEXT | No | Report/snapshot generator code. |

Primary key: `(run_id, snapshot_line_id)`.

Unique: `(run_id, snapshot_batch_id, location_id)`.

A complete batch has one row per location.

## 11. Standard views

The SQL schema should expose stable read-only views or equivalent tested report queries.

### `vw_inventory_by_location`

One row per location with location profile, current item, item description, quantity, code date, replenishment values, calculated physical maximum, available case capacity for the current item, occupancy, last transaction, and update time.

### `vw_inventory_by_item`

One row per item/zone summary with total quantity, location count, pick quantity, reserve quantity, earliest code date, and last update.

### `vw_empty_locations`

Empty locations with location type, zone, pallet capacity, and whether a pick assignment remains.

### `vw_code_date_inventory`

Occupied inventory with code date and days to code date relative to an explicit report as-of date.

### `vw_replenishment_needs`

Pick locations at or below reorder trigger, including current quantity, target, recommended quantity, item velocity, and available compatible source quantity.

### `vw_open_replenishment_tasks`

Created or started tasks with age and timing fields.

### `vw_inventory_transaction_inquiry`

Audit rows enriched with item and location descriptions and source workflow references.

### `vw_adjustment_history`

Adjustments enriched with before/after balances from inventory transaction audit.

### `vw_qa_activity`

QA events with item, location, operator, timestamps, and disposition.

### `vw_inventory_reconciliation`

Factual comparison of live `inventory_master` with a selected WMS snapshot.
The view does not import, persist, or display external transaction-replay
results. Full transaction replay remains a read-only analysis output outside
the WMS source database.

## 12. Derived analytical outputs

Phase 4A rebuilds Phase 4 outputs around `inventory_transaction`:

- `inventory_event_ledger.csv` — normalized audit rows with source references;
- `inventory_reconciliation.csv` — opening + audit replay compared with live master and closing snapshot;
- `pick_context.csv`;
- `replenishment_context.csv`;
- `qa_adjustment_context.csv`;
- `selector_exposure.csv`; and
- `analysis_manifest.json`.

The source WMS database is never modified by reconstruction.

## 13. Restricted data

Not analyst-facing:

- physical quantity;
- physical movement and arrival times not recorded by WMS;
- hidden damage cause;
- scenario pattern identifiers;
- target selector identity as a scenario label;
- injected relationship mappings;
- scenario parameter truth.

Ground truth remains a versioned JSON artifact.

## 14. Frozen statistical outputs

Phase 5 writes a source-preserving statistics directory containing:

| File | Grain and purpose |
|---|---|
| `analysis_config.json` | One canonical frozen configuration payload |
| `analysis_manifest.json` | One provenance, checksum, validation, and row-count manifest |
| `descriptive_metrics.csv` | One row per grouped denominator/rate summary, plus event and reconciliation summaries |
| `replenishment_evidence.csv` | One row per task-status, confirmation-window, condition, velocity, balance, or correction group |
| `qa_adjustment_evidence.csv` | One row per predefined QA-adjustment candidate rule/window |
| `selector_crude.csv` | One row per selector with outcomes and work-mix denominators |
| `selector_adjusted.csv` | One frozen target-versus-peer crude/adjusted contrast |
| `sensitivity_results.csv` | One row per predefined alternate outcome, window, covariance, exclusion, leverage, or baseline comparison |
| `hypothesis_evidence.csv` | One disposition row for each of six required hypotheses |
| `model_diagnostics.json` | Model rank, coefficients, uncertainty, sparse-cell facts, leverage facts, limitations, and freeze status |

The primary grain is unique eligible `pick_event_id`; trip is the primary
uncertainty cluster. Rates preserve eligible-pick or requested-case
denominators. QA-adjustment rows are candidate relationships, not causal links.
The manifest validates both schema-3 source and reconstruction checksums. No
statistical output is written into the WMS source database.

## 15. Removed or superseded legacy concepts

### `item`

Superseded by `item_master` with retained dimensions and pallet-pattern calculation.

### `location`

Superseded by `location_master` without fixed case capacity or equipment area.

### `slot_assignment`

Current item assignment and replenishment controls move into `inventory_master`. A future assignment-history file may be introduced only when re-slotting history is implemented.

### `handling_unit`

Removed from corrected schema `3.0.0`. Pallet IDs and mixed-position inventory are deferred until a complete lifecycle is justified.

### In-memory WMS system quantity

Superseded by persisted `inventory_master`. Physical state remains separate in memory.

### Snapshot-only recorded inventory

Superseded by live inventory plus immutable audit. Snapshots remain report captures.

## 16. Index strategy

Create indexes supporting actual command and inquiry paths:

- inventory transaction by run/location/event sequence;
- inventory transaction by run/item/event sequence;
- inventory transaction by source record;
- pick by selector/time;
- pick by item/location/time;
- replenishment by status/destination/create time;
- QA by item/location/time;
- adjustment by item/location/time;
- snapshot by batch/location;
- work assignment by operator/shift;
- event registry by type/time.

Avoid speculative indexing.

## 16. Ownership

- Executable SQL is storage truth.
- This document defines business meaning.
- Domain records define typed behavior.
- Validators enforce cross-table semantics.
- Standard reports provide stable human-facing inquiries.
- Tests must detect divergence among all five.
