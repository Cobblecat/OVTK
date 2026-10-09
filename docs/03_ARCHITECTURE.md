# 03 — Architecture

## 1. Architectural correction

The project remains a modular monolith, but its internal dependency boundaries are revised.

The legacy design combined normal generation, scenario overlays, physical state, and WMS recorded state inside one operations generator and state transition processor. That implementation produced valid analytical artifacts but gave the source system scenario-aware behavior and omitted a persistent live inventory master.

The corrected architecture treats the miniature WMS as an independent system. Simulation protocols operate it through ordinary application commands.

## 2. Architectural style

One repository, one Python distribution, one CLI, and one release with internally separated modules:

```text
WMS core
Physical simulation
Scenario drivers
Analysis
Reporting
```

Microservices, message brokers, cloud databases, required containers, and production integration are not justified.

Prefer explicit, testable behavior over abstractions that hide WMS semantics.
Architecture boundaries matter more than immediately matching a proposed package
tree.

## 3. Context diagram

```text
Configuration
    |
    v
Scenario driver -------------> Restricted ground truth
    |
    +----> Physical simulator
    |
    `----> WMS public application services
                  |
                  v
             WMS database
                  |
          +-------+---------+
          |                 |
          v                 v
    Standard reports   Read-only analysis
                            |
                            v
                   Derived analytical outputs
                            |
                            v
                    Notebook and reports
```

## 4. Dependency rules

### Allowed

```text
CLI -> application workflows
scenario -> simulation contracts
scenario -> WMS public commands
simulation runner -> scenario protocol
WMS application -> WMS domain + WMS storage
WMS reporting -> read-only WMS repositories/views
analysis -> read-only WMS storage + derived outputs
presentation -> completed analysis results
```

### Prohibited

```text
WMS core -> simulator
WMS core -> scenario modules
WMS core -> ground truth
WMS core -> statistical analysis
scenario -> WMS storage/SQL
scenario -> direct inventory_master mutation
analysis -> WMS writes
reports -> physical state or ground truth
CLI -> business rules or SQL
```

## 5. Corrected package organization

The target structure is directional. Migration may proceed incrementally.

```text
src/operational_variance_toolkit/
|-- cli.py
|-- config.py
|-- errors.py
|-- version.py
|
|-- wms/
|   |-- domain/
|   |   |-- enums.py
|   |   |-- item.py
|   |   |-- location.py
|   |   |-- inventory.py
|   |   |-- transactions.py
|   |   |-- operations.py
|   |   `-- invariants.py
|   |
|   |-- application/
|   |   |-- commands.py
|   |   |-- inventory_service.py
|   |   |-- pick_service.py
|   |   |-- replenishment_service.py
|   |   |-- qa_service.py
|   |   |-- adjustment_service.py
|   |   |-- snapshot_service.py
|   |   `-- report_service.py
|   |
|   |-- storage/
|   |   |-- database.py
|   |   |-- schema.py
|   |   |-- repositories.py
|   |   |-- unit_of_work.py
|   |   `-- read_models.py
|   |
|   `-- reporting/
|       |-- registry.py
|       |-- queries.py
|       `-- exporters.py
|
|-- simulation/
|   |-- clock.py
|   |-- physical_state.py
|   |-- actions.py
|   |-- runner.py
|   `-- context.py
|
|-- scenarios/
|   |-- protocol.py
|   |-- baseline.py
|   |-- investigation.py
|   |-- target_selection.py
|   |-- ground_truth.py
|   `-- patterns/
|       |-- replenishment_timing_gap.py
|       |-- qa_damage_masking.py
|       `-- selector_false_lead.py
|
|-- analysis/
|   |-- load.py
|   |-- reconstruction.py
|   |-- contexts.py
|   |-- metrics.py
|   |-- intervals.py
|   |-- models.py
|   |-- hypotheses.py
|   `-- evidence.py
|
|-- application/
|   |-- initialize_wms.py
|   |-- generate_run.py
|   |-- validate_dataset.py
|   |-- reconstruct_run.py
|   |-- analyze_run.py
|   `-- build_reports.py
|
`-- reporting/
    |-- charts.py
    |-- executive_report.py
    `-- provenance.py
```

Existing modules may be moved gradually. Avoid a giant rename-only commit mixed with behavior changes.

## 6. Independent mini-WMS

The WMS is a deterministic transactional application.

It owns:

- master-file validation;
- live recorded inventory state;
- workflow records;
- transaction IDs and event sequence;
- command idempotency;
- atomic database updates;
- immutable audit history;
- snapshots; and
- standard queries.

It does not own:

- physical truth;
- scenario target selection;
- why a command was delayed or miscoded;
- hidden root cause;
- model features; or
- analytical findings.

### 6.1 Command boundary

Commands are typed application inputs. Examples:

```text
AssignItemToLocation
RecordPickAttempt
CreateReplenishmentTask
StartReplenishmentTask
ConfirmReplenishmentTask
RecordQaEvent
AdjustInventory
RecordSystemEvent
CaptureInventorySnapshot
```

Every command includes:

- run ID;
- command ID;
- event time;
- recorded time where applicable; and
- required business identifiers.

Inventory-affecting commands are idempotent by command ID.

### 6.2 Unit of work

A WMS command that affects multiple records executes through one SQLite transaction.

```text
validate command
load current rows
apply domain invariants
write workflow record
write inventory transaction rows
update inventory_master
update last-change references
commit
```

Any failure rolls back the entire command.

## 7. WMS state model

### 7.1 Stable profile state

`item_master` and `location_master` are profile files. They change only through explicit master-data maintenance workflows, not ordinary picks or replenishments.

### 7.2 Live recorded state

`inventory_master` is the current WMS belief about each location.

It is mutable only through WMS commands and controlled initialization.
Generators, scenario drivers, CLI and presentation code, reports, analysis, and
test fixtures must not write `inventory_master` directly. Only public WMS
application services and controlled initialization helpers owned by the WMS may
mutate it.

### 7.3 Immutable audit state

`inventory_transaction` is append-only audit history. It records each signed location-level quantity effect with before/after balances and source references.

### 7.4 Workflow state

Operational tables represent business processes such as trips, picks, replenishment tasks, QA events, adjustments, and system events.

A workflow record is not a substitute for the inventory transaction audit. A confirmed replenishment has both:

- a workflow record describing the task; and
- audit rows describing the recorded balance effects.

### 7.5 Snapshot state

Snapshots are immutable captures of live state at defined times. They support scheduled reporting and independent reconciliation. They are not the live inventory master.

## 8. Item profile calculations

User or generator inputs:

- case length in inches;
- case width in inches;
- case height in inches;
- case weight;
- cases per layer;
- layers per pallet.

System calculations:

```text
case_cube_ft3 = length_in * width_in * height_in / 1728
cases_per_pallet = cases_per_layer * layers_per_pallet
```

Calculated values are stored for query convenience and validated against inputs.

## 9. Location profile and dynamic capacity

`location_master` contains pallet capacity, not case capacity.

For an assigned item:

```text
calculated_physical_max_cases
    = location_master.pallet_capacity
    * item_master.cases_per_pallet
```

Operational target may be lower than calculated physical maximum. Any stored maximum in `inventory_master` must not exceed that dynamic value.

No generic equipment-area field belongs in the location profile. Event scope is represented through zone, aisle, location, or event-specific fields.

## 10. Inventory-master model

The initial corrected model has exactly one `inventory_master` row per `location_master` row.

### Pick location

- item assignment remains when quantity reaches zero;
- replenishment controls are required;
- a second item cannot be placed there without explicit valid reassignment;
- quantity cannot exceed dynamic maximum.

### Reserve or staging location

- item may be null when empty;
- assignment can be established when inventory is placed;
- a different item cannot be added while occupied;
- item and code date are cleared when quantity becomes zero unless a documented reserve-slotting rule says otherwise.

### Non-inventory or inactive location

- quantity must be zero;
- item and code date must be null;
- replenishment controls must be null.

## 11. Inventory transaction model

The audit uses signed location-level rows.

### Pick

```text
location: pick slot
quantity delta: -picked cases
```

The short portion creates no audit delta.

### Replenishment confirmation

One transaction group:

```text
line 1: source reserve  -confirmed cases
line 2: destination pick +confirmed cases
```

The sum of deltas is zero.

### Adjustment

```text
location: affected location
quantity delta: signed adjustment
```

### QA event

No inventory transaction unless a separate accepted adjustment or movement occurs.

### System event

No inventory transaction.

## 12. Physical simulator

The physical simulator owns a separate in-memory state keyed by item and location under the same initial one-item-per-location simplification.

It can apply physical actions such as:

- physical pick;
- physical transfer;
- damage loss;
- product discovery; and
- temporary unavailability.

The WMS does not query this state. A scenario decides when to submit corresponding commands.

## 13. Scenario protocol

A scenario produces a deterministic ordered plan.

```text
ScenarioPlan
    scheduled physical actions
    scheduled WMS command actions
    scheduled external/system events
    ground-truth references
```

A scheduled action contains:

- action ID;
- scheduled UTC;
- deterministic priority for equal timestamps;
- action type;
- typed payload; and
- optional restricted-truth reference.

The runner executes actions in stable chronological order.

### Baseline scenario

Produces normal operations and uses the same WMS commands as every investigation.

### Investigation scenario

Composes baseline operations with external protocol changes:

- delayed command timing;
- work allocation;
- generic coding choices;
- physical events not immediately reflected in the WMS; and
- ordinary system events.

## 14. Ground-truth isolation

Ground truth is a separate restricted versioned JSON artifact.

It may contain:

- target entities;
- physical event times;
- hidden mechanism identifiers;
- scenario parameters;
- affected WMS source IDs; and
- expected signatures.

Ordinary WMS validation, standard reports, reconstruction, and statistical analysis do not accept a ground-truth path.

## 15. Reporting architecture

Standard WMS reports are registered queries over the WMS database.

```text
report registry
    -> parameter validation
    -> read-only SQL/query service
    -> typed rows
    -> console or CSV renderer
```

Reports must not duplicate business calculations in presentation code. Derived analytical reports remain separate from WMS operational reports.

## 16. Reconstruction architecture

Reconstruction is an independent read-only audit:

```text
opening snapshot
    + ordered inventory_transaction rows
    = reconstructed closing

compare to:
    live inventory_master
    closing snapshot
```

Reconstruction must not rely on workflow-table inference when the authoritative audit row exists. Workflow records remain evidence and context.

## 17. Database lifecycle

- One finalized run per generated SQLite database.
- Schema `3.0.0` databases are created fresh.
- Existing outputs are never overwritten silently.
- Generation uses temporary paths and atomic promotion where practical.
- Failed generation removes incomplete new artifacts.
- Finalized source databases are immutable analysis inputs.
- Legacy schema databases are preserved and validated under legacy rules.

## 18. CLI boundaries

Recommended corrected workflows:

```text
operational-variance-toolkit config-check --config <path>
operational-variance-toolkit init-wms --config <path> --output <db>
operational-variance-toolkit generate --config <path> --output <db> [--ground-truth <path>]
operational-variance-toolkit validate --database <db>
operational-variance-toolkit describe --database <db>
operational-variance-toolkit report --database <db> --name <report> [--output <csv>]
operational-variance-toolkit reconstruct --database <db> --output <dir>
```

Phase 4A command migration must not silently change successful existing commands.

The migration decision is now fixed: `init-wms` is the canonical schema-3
initializer. `init-db` remains temporarily available only for legacy schema-1/2
compatibility and must be identified as the legacy path in help and
documentation.

## 19. Architectural tests

Add tests that fail if:

- WMS modules import scenario or simulator modules;
- scenario modules import WMS storage modules;
- scenario code contains direct SQL;
- reports import ground-truth code;
- analysis opens the source database writable;
- inventory master changes without audit rows;
- audit rows exist without matching before/after balance logic; or
- a new scenario requires WMS-core modification.

## 20. Non-goals

Do not introduce microservices, event buses, production concurrency, network APIs, dependency-injection frameworks, or generic plugin systems during remediation.

The scenario protocol is a focused extension boundary, not a universal plugin architecture.
