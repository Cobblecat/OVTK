# 15 - Phase 2 Implementation Plan

> **Historical implementation record.** This plan describes the completed
> legacy schema-2 baseline. The canonical corrected baseline now uses schema 3,
> external physical simulation, and public WMS commands under the Phase 4A
> contracts. Do not use this document as the corrected source-system contract.

## 1. Purpose, Deliverable, and Exclusions

Phase 2 creates the baseline normal-operations simulator. Its purpose is to generate coherent routine warehouse transaction flows after the Phase 1 opening state and before any controlled failure patterns exist.

Historical implementation status: complete. The legacy workflow used `generate --config <path> --output <path>`, schema version `2.0.0`, an `event_sequence_registry`, a deterministic state transition processor, and version-routed `validate`/`describe` behavior. Phase 3 was subsequently completed and then migrated to external schema-3 scenario drivers during Phase 4A.

Deliverable:

> Given a valid baseline configuration and seed, the application creates a fresh SQLite database with Phase 1 master/opening data plus deterministic normal-operation trips, pick attempts, replenishment tasks, QA/damage events, routine inventory adjustments, benign system/equipment events, and operational closing snapshots that pass hard validation and reproduce from the same inputs.

Explicit exclusions:

- no controlled failure injection;
- no deliberate replenishment timing gap;
- no QA damage masking scenario;
- no selector false-lead targeting;
- no hidden scenario labels in analyst-facing data;
- no inventory reconstruction analysis as a user-facing analytical layer;
- no statistical modeling;
- no notebooks;
- no charts;
- no dashboards; and
- no executive reporting.

Normal operations may include occasional legitimate shorts, damage, adjustments, delays, and system events. They must arise from documented baseline processes and must not reproduce the controlled failure scenarios by design.

## 2. Current Baseline and Extension Constraints

Phase 1 provides:

- immutable configuration loading with unknown-section and unknown-key rejection;
- deterministic run identity, IDs, UTC timestamps, and named NumPy streams;
- SQLite schema version `1.0.0` / `PRAGMA user_version = 1`;
- `simulation_run`, master data, work assignments, handling units, and opening system snapshots;
- an in-memory `PhysicalInventoryState` returned during initialization;
- `init-db`, `validate`, and `describe` workflows for Phase 1 data;
- canonical content comparison that excludes execution timestamps; and
- Phase 1 validation for persisted analyst-facing data.

Constraints for Phase 2:

- The current schema contains no operational transaction tables.
- The current config parser rejects Phase 2 sections until they are explicitly added.
- Current shifts span the full configured period; Phase 2 must either refine shift generation or document trip scheduling against the current shift representation before generating trip times.
- Current locations include only `PICK` and `RESERVE`; QA hold, staging, and dock locations must not be assumed unless master generation is extended in a Phase 2 slice.
- The in-memory physical state is available during initialization but is not persisted after workflow exit.
- Phase 2 cannot treat in-memory physical state as a one-time initialization artifact. It needs an explicit event-processing model that can replay normal operations and explain physical and recorded system inventory after every accepted inventory-affecting event.
- CLI and application workflows must stay thin; SQL belongs in storage adapters, and state transition logic belongs in domain/generation services.

## 3. Transaction Dependency Graph and Generation Order

Dependency graph:

```text
configuration + run metadata
    -> Phase 1 schema/master/opening inventory
    -> in-memory physical/system inventory state
    -> operating calendar and trip plan
    -> baseline system/equipment events
    -> deterministic state-transition event loop
        -> replenishment trigger detection
        -> replenishment task create/start/confirm
        -> trip start/end
        -> pick attempts
        -> QA/damage events
        -> routine inventory adjustments
    -> closing system snapshots
    -> optional closing verified snapshots
    -> Phase 2 validation
    -> describe/row-count summary
```

Required generation order:

1. Validate Phase 2 configuration.
2. Create a fresh Phase 2 schema.
3. Generate Phase 1 foundation and opening inventory.
4. Initialize physical and system state from opening snapshots.
5. Build deterministic trip/demand plans by shift, zone, selector, and item.
6. Pre-generate benign system-event windows.
7. Process all operational events through a deterministic state transition loop with a global `event_sequence`.
8. Emit closing system snapshots after all system-affecting events.
9. Run hard Phase 2 validators before reporting success.

State chronology is the primary architecture constraint for Phase 2. Candidate plans are only intentions until the event loop accepts them against the current state. The loop must:

- read the current hidden physical state and analyst-facing system state;
- apply exactly one event transition;
- record required before/after quantities on the emitted analyst-facing row when the table contract calls for them;
- update physical and system state according to the documented event rule;
- allocate the final `event_sequence`; and
- expose enough transition evidence for validation to replay the analyst-facing system ledger.

Repositories persist completed records only. They do not decide whether an event is physically possible, choose quantities, repair invalid states, or infer event order.

## 4. Proposed Schema-Version Strategy

Recommendation:

- Introduce schema version `2.0.0` and SQLite `PRAGMA user_version = 2` for Phase 2.
- Do not migrate existing Phase 1 artifacts in place.
- Create fresh generated databases for Phase 2.
- Keep Phase 1 validation available for existing version `1.0.0` databases, or add a version-routed validator that chooses Phase 1 or Phase 2 rules.

New analyst-facing tables:

### `trip`

Fields:

- `run_id` TEXT NOT NULL
- `trip_id` TEXT NOT NULL
- `shift_id` TEXT NOT NULL
- `selector_id` TEXT NOT NULL
- `assigned_zone_id` TEXT NOT NULL
- `start_utc` TEXT NOT NULL
- `end_utc` TEXT NOT NULL
- `continuation_flag` INTEGER NOT NULL CHECK 0/1
- `planned_pick_lines` INTEGER NOT NULL CHECK > 0
- `planned_cases` INTEGER NOT NULL CHECK > 0

Keys and constraints:

- primary key `(run_id, trip_id)`;
- foreign key `(run_id, shift_id)` to `shift`;
- foreign key `(run_id, selector_id)` to `operator`;
- foreign key `(run_id, assigned_zone_id)` to `zone`;
- check `start_utc < end_utc`;
- selector role must be validated as `SELECTOR`.

Indexes:

- `(run_id, shift_id)`;
- `(run_id, selector_id, start_utc)`;
- `(run_id, assigned_zone_id, start_utc)`.

### `pick_event`

Fields:

- `run_id` TEXT NOT NULL
- `pick_event_id` TEXT NOT NULL
- `event_sequence` INTEGER NOT NULL
- `trip_id` TEXT NOT NULL
- `selector_id` TEXT NOT NULL
- `item_id` TEXT NOT NULL
- `pick_location_id` TEXT NOT NULL
- `event_utc` TEXT NOT NULL
- `recorded_utc` TEXT NOT NULL
- `requested_qty_cases` INTEGER NOT NULL CHECK > 0
- `picked_qty_cases` INTEGER NOT NULL CHECK >= 0
- `short_qty_cases` INTEGER NOT NULL CHECK >= 0
- `short_reason_code` TEXT
- `system_qty_before_cases` INTEGER NOT NULL CHECK >= 0
- `system_qty_after_cases` INTEGER NOT NULL CHECK >= 0
- `eligible_pick_flag` INTEGER NOT NULL CHECK 0/1

Keys and constraints:

- primary key `(run_id, pick_event_id)`;
- unique `(run_id, event_sequence)`;
- foreign key `(run_id, trip_id)` to `trip`;
- foreign key `(run_id, selector_id)` to `operator`;
- foreign key `(run_id, item_id)` to `item`;
- foreign key `(run_id, pick_location_id)` to `location`;
- check `picked_qty_cases + short_qty_cases = requested_qty_cases`;
- check `recorded_utc >= event_utc`;
- check `short_reason_code IS NOT NULL` when `short_qty_cases > 0`.

Indexes:

- `(run_id, event_utc)`;
- `(run_id, item_id, pick_location_id, event_utc)`;
- `(run_id, selector_id, event_utc)`;
- `(run_id, trip_id, event_sequence)`.

### `replenishment_task`

Fields:

- `run_id` TEXT NOT NULL
- `replenishment_task_id` TEXT NOT NULL
- `event_sequence` INTEGER NOT NULL
- `item_id` TEXT NOT NULL
- `source_location_id` TEXT NOT NULL
- `destination_location_id` TEXT NOT NULL
- `operator_id` TEXT
- `created_utc` TEXT NOT NULL
- `started_utc` TEXT
- `confirmed_utc` TEXT
- `recorded_utc` TEXT NOT NULL
- `requested_qty_cases` INTEGER NOT NULL CHECK > 0
- `confirmed_qty_cases` INTEGER NOT NULL CHECK >= 0
- `status` TEXT NOT NULL CHECK in `CREATED`, `STARTED`, `CONFIRMED`, `CANCELED`, `INCOMPLETE`
- `delay_reason_code` TEXT

Keys and constraints:

- primary key `(run_id, replenishment_task_id)`;
- unique `(run_id, event_sequence)` if event sequence remains globally unique across tables, or unique within table plus a global event order table if that alternative is chosen;
- foreign keys to item, source location, destination location, and operator;
- source location must validate as `RESERVE` or `STAGING`;
- destination location must validate as active `PICK`;
- confirmed tasks require `created_utc <= started_utc <= confirmed_utc <= recorded_utc`;
- canceled tasks require `confirmed_utc IS NULL` and `confirmed_qty_cases = 0`;
- operator role must be `REPLENISHMENT` when populated.

Indexes:

- `(run_id, item_id, destination_location_id, created_utc)`;
- `(run_id, item_id, destination_location_id, confirmed_utc)`;
- `(run_id, status, created_utc)`.

### `qa_event`

Fields:

- `run_id` TEXT NOT NULL
- `qa_event_id` TEXT NOT NULL
- `event_sequence` INTEGER NOT NULL
- `item_id` TEXT NOT NULL
- `location_id` TEXT NOT NULL
- `handling_unit_id` TEXT
- `operator_id` TEXT
- `event_type` TEXT NOT NULL CHECK in the documented QA enum
- `occurred_utc` TEXT NOT NULL
- `recorded_utc` TEXT NOT NULL
- `qty_affected_cases` INTEGER NOT NULL CHECK > 0
- `reason_code` TEXT NOT NULL
- `disposition_code` TEXT NOT NULL

Keys and constraints:

- primary key `(run_id, qa_event_id)`;
- unique event sequence under the selected event order strategy;
- foreign keys to item, location, handling unit, and operator;
- check `recorded_utc >= occurred_utc`;
- operator role must be `QA` or `SYSTEM` when populated.

Indexes:

- `(run_id, item_id, location_id, occurred_utc)`;
- `(run_id, event_type, occurred_utc)`;
- `(run_id, handling_unit_id)`.

### `inventory_adjustment`

Fields:

- `run_id` TEXT NOT NULL
- `adjustment_id` TEXT NOT NULL
- `event_sequence` INTEGER NOT NULL
- `item_id` TEXT NOT NULL
- `location_id` TEXT NOT NULL
- `operator_id` TEXT
- `effective_utc` TEXT NOT NULL
- `recorded_utc` TEXT NOT NULL
- `qty_delta_cases` INTEGER NOT NULL CHECK != 0
- `reason_code` TEXT NOT NULL CHECK in the documented adjustment enum
- `reference_code` TEXT

Keys and constraints:

- primary key `(run_id, adjustment_id)`;
- unique event sequence under the selected event order strategy;
- foreign keys to item, location, and operator;
- check `recorded_utc >= effective_utc`;
- operator role must be `QA`, `INVENTORY_CONTROL`, or `SYSTEM` when populated.

Indexes:

- `(run_id, item_id, location_id, effective_utc)`;
- `(run_id, reason_code, effective_utc)`.

### `system_event`

Fields:

- `run_id` TEXT NOT NULL
- `system_event_id` TEXT NOT NULL
- `event_type` TEXT NOT NULL CHECK in the documented system-event enum
- `zone_id` TEXT
- `location_id` TEXT
- `equipment_area` TEXT
- `start_utc` TEXT NOT NULL
- `end_utc` TEXT NOT NULL
- `severity_code` TEXT NOT NULL CHECK in `LOW`, `MEDIUM`, `HIGH`
- `recorded_utc` TEXT NOT NULL

Keys and constraints:

- primary key `(run_id, system_event_id)`;
- foreign keys to zone and location;
- check `start_utc < end_utc`;
- check `recorded_utc >= start_utc`;
- check at least one scope field is populated.

Indexes:

- `(run_id, start_utc, end_utc)`;
- `(run_id, zone_id, start_utc)`;
- `(run_id, location_id, start_utc)`;
- `(run_id, equipment_area, start_utc)`.

Changed table:

- `inventory_snapshot.snapshot_type` must permit `CLOSING_SYSTEM` and, if implemented in Phase 2, `CLOSING_VERIFIED` or `CYCLE_COUNT_VERIFIED`.

Schema design choice needing approval:

- Prefer one globally unique `event_sequence` across all inventory-affecting event tables and `pick_event`, plus deterministic source-table tie-breakers for non-inventory system events. If SQLite uniqueness across tables becomes awkward, use a small `event_sequence_registry` table instead.

## 5. Typed Domain Records and Boundaries

Recommended typed records:

- `TripRecord`: planned selector work period and trip metadata.
- `PickEventRecord`: one pick attempt and its observed system quantities.
- `ReplenishmentTaskRecord`: analyst-facing replenishment lifecycle.
- `QaEventRecord`: QA, damage, hold, restack, release, or count-verification event.
- `InventoryAdjustmentRecord`: signed system correction.
- `SystemEventRecord`: time-bounded friction context.
- `InventoryPosition`: quantity by item/location and optional handling unit.
- `SimulatorInventoryState`: hidden physical state plus analyst-facing system state during generation.
- `StateTransitionProcessor`: deterministic event acceptance, state mutation, before/after capture, and sequence allocation.
- `BaselineGenerationSummary`: row counts, rates, and validation summary.

Responsibility boundaries:

- Domain models express data contracts and state transitions.
- Generation modules choose deterministic baseline events from configuration and RNG streams.
- Repositories persist and read records but do not decide business values.
- Application workflows coordinate config, schema, generation, persistence, validation, and CLI-facing result objects.
- Validators reject invalid data and report warnings; they do not repair generated records.

## 6. Lifecycle and State Transition Rules

### Trips

- A trip belongs to one shift, one selector, and one assigned zone.
- Start/end must lie within the parent shift and run period.
- Planned lines and planned cases are positive.
- The selector must have role `SELECTOR`.
- `continuation_flag` captures work-mix context only; it must not encode scenario targeting.

### Pick Attempts and Outcomes

- Each pick references an active slot assignment for the item and pick location at the event time.
- Pick timestamps must lie within the trip.
- Requested quantity is positive.
- Picked and short quantities are nonnegative integers.
- `picked_qty_cases + short_qty_cases = requested_qty_cases`.
- `system_qty_before_cases` equals system state immediately before the pick.
- `system_qty_after_cases = system_qty_before_cases - picked_qty_cases`.
- A short reason is required when `short_qty_cases > 0`.
- Baseline shorts are allowed only from documented ordinary causes such as true depletion, temporary access restriction, or low-rate recording mismatch.

### Replenishment Tasks

- A task is created when a pick slot falls at or below trigger, or when planned demand indicates likely depletion before the next cycle.
- Source must be reserve or staging for the same item and zone-compatible storage.
- Destination must be the active pick location for the item.
- Requested quantity is bounded by source quantity and destination capacity.
- Status progresses through legal states:
  - `CREATED -> STARTED -> CONFIRMED`
  - `CREATED -> CANCELED`
  - `CREATED -> STARTED -> INCOMPLETE`
- Normal confirmed tasks have narrow delay distributions with occasional benign tails.
- Analyst-facing records omit hidden physical arrival time.

### Replenishment Movements and Confirmations

- Physical source decreases when product leaves reserve.
- Physical destination increases at hidden physical arrival.
- System source and destination change at confirmation.
- In baseline, hidden arrival and confirmation are usually close.
- Temporary physical/system differences are allowed between arrival and confirmation or between departure and confirmation, but must be brief and generated from baseline timing, not targeted failure logic.

### QA Inspections and Damage Events

- QA events reference item, location, optional handling unit, event type, operator or system source, time, quantity, reason, and disposition.
- QA recording time is at or after occurrence.
- `DAMAGE_FOUND` or `DISPOSED` may reduce usable physical quantity.
- QA alone does not change system quantity unless paired with an adjustment or documented disposition rule.
- Baseline damage frequency is low, tied to fragility and handling volume, and normally uses explicit damage-coded adjustments when system quantity changes.

### Inventory Adjustments

- Adjustments are signed nonzero system changes.
- Effective time is when the adjustment changes system inventory.
- Recorded time is at or after effective time.
- Negative adjustments must not drive system quantity below zero in baseline unless an explicitly documented warning-level system discrepancy is allowed.
- Routine positive adjustments may represent found product or count correction.
- Adjustment-to-physical-state rule must be explicit:
  - count correction changes system only;
  - damage disposition changes physical and system when recorded;
  - found product may add physical and system if it represents previously unavailable product.

### System/Equipment Events

- Events have valid type, severity, start/end, recorded time, and scope.
- Scope must include at least one of zone, location, or equipment area.
- Normal events may affect pick pace, recording lag, or temporary access.
- Normal events must be low frequency and not concentrated enough to imitate Pattern A or Pattern C.

### Operational Inventory Snapshots

- `CLOSING_SYSTEM` snapshots are created after all system-affecting events.
- Optional verified snapshots may sample item/location positions for validation context.
- Closing snapshots are comparison targets, not transaction deltas.
- Snapshot quantities must be nonnegative and deterministic.

## 7. Physical and System State Update Rules

State is maintained during generation as two maps:

- physical quantity by item/location/handling unit where needed;
- system quantity by item/location, with handling-unit linkage where persisted.

At opening:

- physical and system states agree.

Pick:

- physical pick location decreases by `picked_qty_cases`;
- system pick location decreases by `picked_qty_cases`;
- short quantity does not change state;
- physical quantity must never go negative.

Replenishment:

- physical source decreases when movement begins;
- physical destination increases at hidden arrival;
- system source decreases and system destination increases at confirmation;
- normal baseline gaps are brief and bounded by configuration.

QA/damage:

- inspection-only events do not change state;
- damage found may move physical usable quantity to held/unusable state;
- system changes only through adjustment unless the disposition explicitly records a system movement.

Adjustment:

- system quantity changes by signed `qty_delta_cases`;
- physical quantity changes only under the documented reason/disposition rule;
- quantity conservation exceptions are limited to damage/disposal or found product.

System event:

- no direct inventory state change;
- may alter timing, accessibility, or recording lag within baseline bounds.

Closing:

- closing system snapshot equals final system state;
- optional verified snapshot equals final physical state or a sampled observable verification.

When they agree:

- opening state;
- after ordinary picks with no timing lag;
- after confirmed replenishment once physical arrival and system confirmation have both occurred;
- after adjustments whose reason changes both physical and system state.

When they may temporarily differ in baseline:

- during normal replenishment travel/confirmation lag;
- during QA hold/disposition before adjustment posting;
- during benign system recording lag.

These differences must be transient, low-rate, and not targeted by selector, affected aisle, or controlled scenario parameters.

## 8. Normal-Operation Assumptions and Distributions

Required behavior:

- demand varies by item velocity, operating date, shift, and zone;
- most picks fill completely;
- ordinary shorts are low-rate and explainable by state/access conditions;
- replenishment responds to trigger/target logic;
- QA/damage and adjustments occur at low plausible rates;
- benign system events occur but do not dominate;
- no selector gets hidden adverse behavior propensity.

Tunable assumptions for proposed `baseline.toml` additions:

- target pick attempts: default 30,000, valid 10,000-60,000;
- trip planned lines: default 18-42 lines;
- requested quantity per pick: mostly 1-4 cases, with velocity-based tail;
- demand multipliers by velocity:
  - A: 1.00;
  - B: 0.45;
  - C: 0.18;
- day multiplier range: 0.85-1.15;
- shift multiplier range: 0.90-1.10;
- replenishment trigger check interval: 10-20 minutes;
- normal creation-to-start delay: 2-12 minutes;
- normal start-to-confirm delay: 5-25 minutes;
- occasional routine delay tail: under 3% of tasks, capped at 60 minutes;
- background short event rate target: 0.2%-1.0% of eligible picks;
- damage event probability: base 0.03%-0.15% per handled case, scaled by fragility;
- adjustment probability: low and reason-coded, normally below QA/damage frequency plus routine count corrections;
- system-event frequency: 0-3 brief events per day, duration 5-30 minutes, low/medium severity dominant.

These defaults should be calibrated with a small configuration first, then the portfolio-size baseline.

## 9. Proposed `baseline.toml` Additions

Do not edit configuration until Phase 2 implementation begins.

Proposed sections:

```toml
[operations]
target_pick_attempts = 30000
max_pick_attempts = 60000
trip_min_lines = 18
trip_max_lines = 42
max_requested_cases_per_pick = 8
closing_snapshot_enabled = true
verified_snapshot_sample_rate = 0.05

[operations.demand]
velocity_a_weight = 1.0
velocity_b_weight = 0.45
velocity_c_weight = 0.18
day_multiplier_min = 0.85
day_multiplier_max = 1.15
shift_multiplier_min = 0.90
shift_multiplier_max = 1.10

[operations.replenishment]
trigger_check_minutes = 15
creation_to_start_min_minutes = 2
creation_to_start_max_minutes = 12
start_to_confirm_min_minutes = 5
start_to_confirm_max_minutes = 25
routine_delay_tail_probability = 0.03
routine_delay_tail_max_minutes = 60

[operations.background_rates]
short_event_probability = 0.005
damage_per_handled_case_probability = 0.0008
adjustment_per_item_day_probability = 0.01
system_events_per_day_max = 3
```

Validation rules:

- counts and maximums must be positive integers;
- probabilities must be between 0 and 1;
- min values must be less than or equal to max values;
- target pick attempts must fit the release envelope;
- routine delay tail maximum must stay below any future controlled timing-gap threshold;
- background rates must stay below baseline alert ceilings;
- no Pattern A/B/C configuration appears in baseline Phase 2 config.

## 10. Named Deterministic Random Streams

Add streams only when used:

- `operations_demand`
- `operations_trips`
- `operations_picks`
- `operations_replenishment`
- `operations_qa`
- `operations_adjustments`
- `operations_system_events`
- `operations_snapshots`

Isolation requirements:

- one component drawing extra random values must not alter unrelated components;
- stream names must be closed and tested;
- IDs, timestamps, and row order must not depend on dictionary iteration or Python hash order;
- a different seed should change stochastic operation rows while preserving schema and invariants.

## 11. Deterministic State-Chronology Strategy

Recommendation:

- Generate candidate events from deterministic plans, then process them through a single state transition engine.
- The engine owns event acceptance, physical/system state mutation, before/after quantity capture, and final sequence assignment.
- The engine processes a priority queue ordered by:
  1. event UTC timestamp;
  2. event priority;
  3. deterministic source type order;
  4. source identifier; and
  5. insertion ordinal within the generator.
- Assign one monotonically increasing `event_sequence` only when the event is accepted into state.

State transition contract:

- `PickAttempt`: consumes pick-location physical and system quantity at pick time; emits pick before/after system quantities; cannot drive physical or system state below zero.
- `ReplenishmentDeparture`: reserves or removes physical quantity from source according to the selected movement rule; emits a task state change but no destination system increment.
- `ReplenishmentArrival`: increases hidden destination physical quantity at the arrival time; analyst-facing tables must not expose hidden arrival time unless it is represented by an ordinary recorded status.
- `ReplenishmentConfirmation`: updates recorded system source/destination quantities at confirmation time.
- `QaDamageDisposition`: changes physical usable quantity when the disposition physically removes, holds, or releases product; changes system quantity only through a documented recorded movement or paired adjustment.
- `InventoryAdjustment`: changes recorded system quantity at effective time; changes physical state only when the reason/disposition explicitly represents a physical find, disposal, or release.
- `SystemEvent`: affects timing, accessibility, or recording lag only; it does not directly change inventory quantities.
- `ClosingSnapshot`: materializes final recorded system state after all system-affecting events.

Every state transition should be deterministic, local, and auditable: given opening state, configuration, seed, candidate events, and accepted prior events, the next state is fixed.

Proposed event priority:

1. system-event starts;
2. replenishment starts/departures;
3. QA physical occurrences;
4. replenishment physical arrivals;
5. replenishment confirmations;
6. inventory adjustments;
7. pick attempts;
8. system-event ends;
9. closing snapshots.

Equal timestamp handling:

- `event_sequence` is the final deterministic tiebreaker for inventory-affecting events.
- Table-specific IDs remain stable but do not replace event order.
- Validators check uniqueness and monotonic order within run.
- Equal-time behavior is part of the state transition contract because it determines which before/after quantities are true for the accepted event.

Decision required:

- Whether pick attempts at the exact same timestamp as a replenishment confirmation should see pre-confirmation or post-confirmation system quantity. Recommendation: process confirmation before pick at identical timestamps to avoid artificial shorts from equal-time collisions.

## 12. Inventory and Transaction Invariants

Hard invariants:

- no impossible physical movement;
- no negative physical inventory;
- no negative persisted system quantity in baseline;
- valid item/location/operator relationships;
- valid event chronology;
- legal lifecycle transitions;
- requested, picked, short, confirmed, affected, and adjustment quantities obey integer rules;
- replenishment movement conserves quantity between source and destination;
- damage/disposal quantity changes are traceable;
- handling-unit item matches event item when handling unit is populated;
- system-ledger reconstruction from opening snapshots and signed transactions reconciles to closing system snapshots;
- deterministic ordering for all persisted transaction rows;
- analyst-facing tables contain no `true_root_cause`, `is_injected_anomaly`, hidden physical arrival, or scenario target labels.

Warning-level conditions:

- long but baseline-allowed recording lag;
- sparse operator-zone coverage;
- high but non-scenario-dominant short rate by area;
- incomplete/canceled replenishment tasks within configured low ceiling;
- optional missing reason text where the data dictionary permits null.

## 13. Baseline Validators and Warnings

Extend validation from Phase 1 to Phase 2:

- schema version and required transaction tables;
- enum consistency;
- foreign keys and required values;
- UTC timestamp format and order;
- trip within shift and run;
- pick within trip and assignment;
- pick quantity identity;
- selector and trip selector match;
- replenishment source/destination roles;
- replenishment status lifecycle and chronology;
- replenishment quantity bounded by source and destination capacity;
- QA role, time, disposition, and positive affected quantity;
- adjustment nonzero signed quantity and role;
- system-event scope and time order;
- closing snapshot reconciliation;
- no hidden-truth leakage.

Warnings:

- background short rate above configured baseline warning threshold but below hard failure;
- system-event or adjustment rates near baseline ceiling;
- unusually long normal replenishment duration;
- sparse selector exposure by zone;
- closing verified sample absent if optional sample disabled.

## 14. Test Inventory

Unit tests:

- state transition arithmetic for pick, replenishment, QA/damage, and adjustment;
- state transition processor ordering and equal timestamp behavior;
- replay fixture showing physical and system state after each accepted event;
- config parsing and rejection for Phase 2 sections;
- random stream independence;
- lifecycle transition validators;
- reason/status enum synchronization.

Integration tests:

- tiny baseline generation produces trips, picks, replenishments, QA, adjustments, system events, and closing snapshots;
- generated row counts satisfy config ranges;
- generated events pass Phase 2 validation;
- corrupted temporary database returns categorized hard failures;
- failed generation rolls back and removes incomplete artifacts.

CLI tests:

- generation command success if a new command is added;
- `init-db` behavior if existing semantics are expanded instead;
- `validate` supports schema version 2;
- `describe` includes transaction counts and opening/closing totals without analytical claims;
- expected exit codes remain stable.

Reproducibility tests:

- same config/seed into two temp roots produces identical canonical analyst-facing content excluding execution timestamps and physical file metadata;
- different seed changes designated stochastic transaction tables while retaining invariants.

Hand-calculated fixtures:

- opening 20, pick 4, replenish 10, adjustment -2 gives closing 24;
- replenishment source/destination signs conserve quantity;
- QA event alone does not change system quantity;
- equal-time ordering fixture proves deterministic event sequence and before/after state.

## 15. Vertical-Slice Implementation Sequence

Phase 2 is implemented in small slices that each produce independently testable behavior. Progression requires completion of the review checkpoint for each slice.

## 16. Slice Details

### Slice 1 - Schema Version 2 and Transaction/State Domain Contracts

Goal:

- Add schema support plus typed transaction and state transition contracts for Phase 2 without generating transactions yet.

Included entities and behavior:

- `trip`, `pick_event`, `replenishment_task`, `qa_event`, `inventory_adjustment`, `system_event`;
- schema version routing;
- domain record dataclasses, enum constants, and state transition input/output contracts.

Files likely affected:

- `storage/schema.py`;
- `storage/repositories.py`;
- `domain/operations.py` or focused domain modules;
- `validation/phase1.py` or new version-routed validation module;
- tests for schema and records.

Acceptance criteria:

- schema version `2.0.0` creates all transaction tables with constraints and indexes;
- Phase 1 schemas still validate under Phase 1 rules;
- invalid FK, enum, quantity, and timestamp examples fail.

Required verification:

```powershell
uv run pytest tests/test_storage_schema.py tests/test_validation_rules.py
uv run ruff check .
uv run ruff format --check .
```

Strict exclusions:

- no transaction generation;
- no controlled failure fields;
- no analysis ledger.

Review checkpoint:

- Progression requires review of the tested schema, typed records, and state transition contracts.

### Slice 2 - Phase 2 Configuration Contract and State Transition Processor

Goal:

- Add validated baseline operations configuration and the deterministic state transition processor contract.

Included entities and behavior:

- operations config dataclasses;
- validation of probabilities, ranges, and row-count targets;
- named streams for operations;
- global event processor and sequencing helper.

Files likely affected:

- `config.py`;
- `generation/random_source.py`;
- `domain/time.py` or new event-processing module;
- config tests and random-stream tests.

Acceptance criteria:

- baseline config can express normal operations settings;
- invalid rates/ranges fail clearly;
- equal timestamp events sort and transition deterministically;
- adding draws in one operation stream does not alter another.

Required verification:

```powershell
uv run operational-variance-toolkit config-check --config configs/baseline.toml
uv run pytest tests/test_config.py tests/test_identity_and_primitives.py
uv run ruff check .
uv run ruff format --check .
```

Strict exclusions:

- no transaction generation;
- no CLI semantic changes beyond config validation output if needed.

Review checkpoint:

- Progression requires acceptance of the config, event order, and state transition contracts.

### Slice 3 - Trips and Pick Attempts With Basic State Updates

Goal:

- Generate deterministic trips and pick events from opening inventory with valid state changes.

Included entities and behavior:

- trip plans by shift, selector, and zone;
- pick attempts by assigned item/location;
- system and physical pick-state decrement;
- low or zero short rate initially if needed to prove state mechanics.

Files likely affected:

- `application/phase1.py` or a new Phase 2 workflow;
- `generation/baseline_operations.py`;
- `storage/repositories.py`;
- `validation` modules;
- tests for trips and picks.

Acceptance criteria:

- trips reference valid shifts/selectors/zones;
- picks occur within trips;
- selector matches trip;
- pick quantities balance;
- no negative physical/system quantity;
- deterministic generation passes validation.

Required verification:

```powershell
uv run pytest tests/test_phase2_trips_and_picks.py tests/test_phase1_workflows.py
uv run ruff check .
uv run ruff format --check .
```

Strict exclusions:

- no replenishment tasks;
- no QA, adjustments, system events;
- no deliberate scenario shorts.

Review checkpoint:

- Progression requires review of the validated trip/pick state updates.

### Slice 4 - Replenishment Trigger, Movement, and Confirmation

Goal:

- Add normal replenishment tasks that keep pick slots supplied and preserve physical/system state rules.

Included entities and behavior:

- trigger detection;
- task creation/start/confirmation;
- reserve source decrement;
- pick destination increment;
- bounded normal physical/system timing gaps.

Files likely affected:

- `domain/inventory_state.py`;
- `generation/baseline_operations.py`;
- repositories;
- validation modules;
- replenishment tests.

Acceptance criteria:

- source/destination roles are valid;
- task lifecycle chronology is legal;
- quantity movement is conserved;
- destination capacity is not exceeded;
- physical state never goes negative;
- baseline timing gaps stay within configured normal limits.

Required verification:

```powershell
uv run pytest tests/test_phase2_replenishment.py tests/test_phase2_trips_and_picks.py
uv run ruff check .
uv run ruff format --check .
```

Strict exclusions:

- no delayed replenishment timing-gap pattern;
- no scenario targeting.

Review checkpoint:

- Progression requires review of replenishment after it validates independently.

### Slice 5 - QA/Damage, Routine Adjustments, and System Events

Goal:

- Add low-rate normal QA, adjustment, and benign system/equipment events.

Included entities and behavior:

- QA events tied to fragility and handling volume;
- routine damage/found/count adjustments;
- system events with valid scope and bounded duration;
- documented state effects.

Files likely affected:

- `generation/baseline_operations.py`;
- `domain/inventory_state.py`;
- repositories;
- validation modules;
- QA/adjustment/system-event tests.

Acceptance criteria:

- QA events have valid operators, quantities, times, reasons, and dispositions;
- adjustments are signed, nonzero, and role-valid;
- system events have valid scope and time order;
- baseline rates remain under configured warning/hard ceilings;
- no hidden labels or Pattern B masking logic appears.

Required verification:

```powershell
uv run pytest tests/test_phase2_quality_adjustments_system_events.py
uv run ruff check .
uv run ruff format --check .
```

Strict exclusions:

- no QA damage masking scenario;
- no root-cause labels.

Review checkpoint:

- Progression requires review of the validated low-rate normal events.

### Slice 6 - Closing Snapshots, Validation, and CLI Integration

Goal:

- Produce a complete Phase 2 baseline database through public workflow behavior.

Included entities and behavior:

- closing system snapshots;
- optional verified snapshot sample;
- version-routed validation;
- factual describe counts for transaction tables;
- reproducibility comparison.

Files likely affected:

- application workflow modules;
- CLI;
- validation modules;
- README only if public commands change;
- integration and CLI tests.

Acceptance criteria:

- opening plus signed system events reconciles to closing system snapshots;
- `validate` returns 0 for clean Phase 2 baseline and 6 for hard failures;
- describe prints factual transaction counts and opening/closing totals;
- same config/seed reproduces canonical content;
- generated row counts are plausible and within configured bounds.

Required verification:

```powershell
uv run operational-variance-toolkit --help
uv run operational-variance-toolkit config-check --config configs/baseline.toml
uv run operational-variance-toolkit init-db --config configs/baseline.toml
uv run operational-variance-toolkit validate --database artifacts/data/baseline.sqlite3
uv run operational-variance-toolkit describe --database artifacts/data/baseline.sqlite3
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

Strict exclusions:

- no Phase 3 controlled failures;
- no analytical reconstruction feature beyond validator-internal reconciliation;
- no notebooks, charts, dashboards, or reports.

Review checkpoint:

- Progression requires review after the Phase 2 completion gate passes and status is updated.

## 17. Proposed Public Workflow and CLI Behavior

Alternative A: extend current `init-db`.

- `init-db --config configs/baseline.toml` creates the highest supported schema for the config.
- Pros: preserves existing command surface.
- Cons: the command name understates that it now generates transactions.

Alternative B: add `generate`.

- `generate --config configs/baseline.toml --output <db>` creates full configured dataset.
- Pros: aligns with architecture docs' eventual CLI, separates schema initialization from generation.
- Cons: adds a public command and requires README/status updates.

Recommendation:

- For Phase 2, add `generate --config <path> --output <db>` only if configuration no longer owns the database path.
- If configuration remains the source of output path, extend `init-db` behavior but update help text to say it initializes the configured generated dataset.
- Keep `validate --database` and `describe --database` unchanged in shape, but make them version-routed.

Decision required:

- Whether Phase 2 should keep config-owned output paths or introduce an explicit CLI `--output` override.

## 18. Phase 2 Completion Gate

Required commands:

```powershell
uv run operational-variance-toolkit --help
uv run operational-variance-toolkit config-check --config configs/baseline.toml
uv run operational-variance-toolkit init-db --config configs/baseline.toml
uv run operational-variance-toolkit validate --database artifacts/data/baseline.sqlite3
uv run operational-variance-toolkit describe --database artifacts/data/baseline.sqlite3
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

If a new `generate` command is approved, replace the `init-db` smoke step with the approved command and update this plan before implementation.

Reproducibility comparison:

- create two Phase 2 databases from the same config and seed in separate temporary roots;
- compare canonical analyst-facing table content;
- exclude execution timestamps, schema creation timestamp, physical file metadata, and output paths;
- assert identical content;
- repeat with a different seed and assert stochastic transaction tables differ while invariants pass.

## 19. Risks, Unresolved Questions, and Required Decisions

Risks:

- Baseline rates could accidentally mimic Pattern A, B, or C if delays, QA, or shorts cluster too strongly.
- Full transaction generation may exceed the target row envelope if trip volume and event rates are calibrated late.
- Physical/system timing gaps can create confusing point-in-time behavior unless the event order contract is precise.
- Current Phase 1 shift/work-assignment simplifications may be too coarse for realistic trip scheduling.
- Handling-unit updates may become complex if partial replenishment and damage events split stock.

Unresolved questions:

- Should Phase 2 add explicit `STAGING`, `QA_HOLD`, and `DOCK` locations now, or defer until a specific event requires them?
- Should Phase 2 persist any restricted physical-state artifact for restartability, or keep physical state in memory until Phase 3 ground truth exists?
- What background short-rate ceiling should fail baseline validation versus warn?
- Should adjustment reasons include only the data-model enum or a narrower baseline reason vocabulary?
- Should the public command remain `init-db` or should Phase 2 introduce `generate`?
- Should exact portfolio pick count target be closer to 25,000, 30,000, or 60,000?

Decisions required before implementation:

- approval of schema version `2.0.0` as the Phase 2 boundary;
- approval of the deterministic state transition event-processing strategy;
- approval of the config-owned output path versus CLI `--output` approach;
- approval of baseline rate ceilings and row-count target;
- approval of whether Phase 2 should persist restricted physical state.

Recommended first implementation slice:

- Slice 1: Schema Version 2 and Transaction/State Domain Contracts.
