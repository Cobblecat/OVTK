# 05 — Synthetic Data, Simulation, and Scenario Specification

## 1. Purpose

This specification defines how synthetic warehouse activity is created without embedding scenario intent inside the WMS.

The corrected generation chain is:

```text
configuration
    -> master-data protocol
    -> WMS initialization
    -> scenario plan
    -> physical simulator and WMS commands
    -> analyst-facing WMS database
    -> separate restricted ground truth
```

## 2. Separation of responsibilities

### Mini-WMS

The WMS validates and records commands. It does not choose scenario targets or know why a transaction occurred.

### Physical simulator

The simulator represents actual product location and availability. It may differ from WMS recorded state when a command is delayed, omitted, or miscoded.

### Scenario driver

The scenario creates the ordered protocol: work assignment, physical actions, WMS commands, and hidden truth.

### Ground-truth writer

The ground-truth writer receives restricted scenario facts from the scenario layer. It cannot alter WMS data.

## 3. Configuration model

Configuration remains immutable and versioned.

Recommended top-level sections:

```toml
[run]
scenario_name = "investigation"
scenario_version = "2.0.0"
seed = 20260802
facility_timezone = "America/New_York"
start_local = "2026-05-04T03:00:00"
operating_days = 10

[scale]
items = 96
selectors = 18
replenishment_operators = 7
qa_operators = 2
inventory_control_operators = 2

[wms]
schema_version = "3.0.0"

[operations]
# normal demand, trip, pick, replenishment, QA, adjustment, and system-event settings

[scenario.replenishment_timing_gap]
enabled = true

[scenario.qa_damage_masking]
enabled = true

[scenario.selector_false_lead]
enabled = true
```

WMS rules are not configurable by scenario sections. Scenario configuration changes timing and action plans, not command validation.

## 4. Deterministic random streams

Named streams must be independent of request order.

Recommended names:

### Master profiles

- `master_items`
- `master_item_dimensions`
- `master_item_pallet_patterns`
- `master_locations`
- `operators`
- `schedules`
- `opening_inventory`

### Baseline operations

- `demand`
- `trip_assignment`
- `pick_quantities`
- `baseline_shorts`
- `replenishment_timing`
- `qa_events`
- `inventory_adjustments`
- `system_events`

### Investigation patterns

- `failure_replenishment_gap`
- `failure_qa_masking`
- `failure_selector_exposure`

Changing one scenario stream must not alter unrelated target selection through incidental random-call order.

## 5. Master-data generation

### 5.1 Items

Generate realistic synthetic warehouse item profiles.

The generator supplies:

- dimensions in inches;
- case weight;
- cases per layer;
- layers per pallet;
- storage zone;
- category;
- velocity;
- fragility;
- shelf life; and
- expected demand.

The WMS calculation service derives:

- cube; and
- cases per pallet.

Generation must avoid impossible combinations such as zero dimensions, zero pallet layers, or category-zone mismatches under documented rules.

### 5.2 Locations

Generate stable location profiles with:

- warehouse address components;
- location type;
- zone;
- pallet capacity where applicable;
- active and pickable flags.

Do not generate case capacity or equipment area.

### 5.3 Opening inventory assignment

The setup protocol assigns items and opening quantities through controlled WMS initialization services.

Rules:

- every pick location receives one assigned item;
- pick assignment remains visible at zero quantity;
- reserve locations may be empty or contain one item;
- opening quantity must fit the item-specific physical maximum;
- one code date per occupied location;
- no pallet IDs;
- every location receives one `inventory_master` row; and
- the opening snapshot is captured after initialization.

## 6. Scenario protocol

A scenario implements a stable interface equivalent to:

```text
build_plan(context, random_streams) -> ScenarioPlan
```

The plan contains typed scheduled actions.

### 6.1 Physical action

Changes physical simulator state only.

Examples:

- physical pick;
- physical transfer;
- damage loss;
- found product;
- temporary blocking/unavailability.

### 6.2 WMS command action

Invokes one public WMS application service.

Examples:

- record trip;
- record pick attempt;
- create/start/confirm replenishment;
- record QA event;
- adjust inventory;
- record system event;
- capture snapshot.

### 6.3 Restricted truth action

Records scenario metadata in the separate truth artifact. It cannot write the WMS database.

## 7. Action ordering

Every action has:

- scheduled UTC;
- stable action ID;
- action priority;
- action type; and
- typed payload.

Stable order:

```text
scheduled_utc
then action_priority
then stable action_id
```

Priority is defined explicitly so equal-time physical actions and WMS commands are reproducible.

## 8. Baseline normal operations

The baseline scenario must create all ordinary transaction families without controlled failures.

### 8.1 Demand and trips

- Assign trips to active selectors and valid shifts.
- Use item demand and zone assignments.
- Produce documented pick-line and case distributions.
- Do not assign hidden performance propensities by selector.

### 8.2 Pick attempts

The physical simulator determines physical availability. The scenario submits an ordinary pick command containing the recorded pick result.

The WMS:

- validates recorded state and quantities;
- decrements only picked quantity;
- writes workflow and audit records; and
- records short quantity without decrement.

### 8.3 Replenishment

The baseline scenario creates tasks when pick locations meet configured triggers, schedules physical and recorded movement close together, and confirms through ordinary WMS commands.

### 8.4 QA and damage

Normal QA events occur at a low configured rate. Damage may generate physical loss and a properly coded WMS adjustment under ordinary timing.

### 8.5 Adjustments

Routine count corrections and found-product adjustments occur at modest rates and must remain auditable.

### 8.6 System events

Benign scanner, lag, blocked-location, or network events create context without changing inventory directly.

## 9. Controlled Pattern A — Replenishment timing gap

### 9.1 Hidden mechanism

A scenario schedules physical and/or operational events so high-velocity pick demand interacts with delayed WMS replenishment recording or delayed usable availability.

### 9.2 External-driver behavior

The scenario may:

- create an ordinary replenishment task;
- delay physical movement;
- physically move product before WMS confirmation;
- delay the confirmation command;
- schedule picks in the affected interval;
- submit later ordinary correction or confirmation commands.

The WMS applies ordinary rules and never receives a failure-pattern identifier.

### 9.3 Analyst-visible evidence

- repeated shorts in affected locations;
- high-velocity item concentration;
- task creation/start/confirmation timing;
- shorts near delayed confirmation;
- later corrections or replenishment completion;
- normal transaction IDs, users, timestamps, and locations.

### 9.4 Negative controls

- comparable items and locations outside the target interval;
- affected selectors outside the target work;
- exposed peers in similar conditions.

## 10. Controlled Pattern B — QA damage masking

### 10.1 Hidden mechanism

Physical damage occurs and is observed through QA, but the later inventory correction is recorded under a generic reason.

### 10.2 External-driver behavior

The scenario:

- applies physical damage loss;
- submits an ordinary QA event;
- later submits an ordinary adjustment command using a generic valid reason;
- records the hidden QA-to-adjustment relationship only in ground truth.

The WMS does not infer or store the hidden causal link.

### 10.3 Analyst-visible evidence

- fragile-item concentration;
- QA events before generic negative adjustments;
- compatible item/location/quantity timing;
- ordinary reason codes that require joins to interpret.

### 10.4 Negative controls

- QA events without later masked adjustments;
- non-fragile items;
- generic adjustments without relevant QA history.

## 11. Controlled Pattern C — Selector false lead

### 11.1 Hidden mechanism

The scenario allocates one selector disproportionate exposure to affected work.

### 11.2 External-driver behavior

The scenario changes:

- trip assignment;
- zone/aisle exposure;
- item mix;
- timing;
- affected-window work share.

It does not change:

- WMS validation;
- selector-specific pick accuracy;
- hidden selector error probability;
- short generation merely because of identity.

### 11.3 Analyst-visible evidence

- target selector high or near-high in crude short totals;
- disproportionate affected exposure;
- compatible behavior among exposed peers;
- weaker selector association after later adjustment.

## 12. Ground-truth artifact

Ground truth remains JSON with an explicit schema version.

Recommended structure:

```json
{
  "ground_truth_version": "2.0.0",
  "run_id": "...",
  "config_hash": "...",
  "patterns": {
    "replenishment_timing_gap": {},
    "qa_damage_masking": {},
    "selector_false_lead": {}
  },
  "physical_events": [],
  "wms_source_references": [],
  "expected_signatures": {}
}
```

The artifact may reference WMS IDs but is never stored inside the WMS database or ordinary report directory.

## 13. Scenario calibration

Developer-only calibration confirms the scenario was created as designed.

Required checks:

- all enabled patterns have eligible targets;
- affected events remain a minority of operations;
- replenishment-gap shorts cluster in intended windows;
- recovery evidence exists;
- QA precedes masked adjustments;
- false-lead selector has high crude short count and high affected exposure;
- no selector-specific error parameter exists;
- comparable exposure yields compatible results;
- standard WMS validation passes;
- live inventory and audit history remain coherent;
- hidden truth does not leak.

Calibration does not constitute the final analyst investigation.

## 14. Scenario extensibility

A new scenario should require:

- new configuration;
- a scenario protocol implementation;
- target-selection logic;
- scheduled physical actions;
- scheduled ordinary WMS commands;
- optional external logs;
- ground-truth serialization; and
- calibration tests.

It should not require changes to WMS domain, application, storage, or standard-report code.

## 15. Prohibited shortcuts

Do not:

- edit a completed SQLite database to inject failures;
- issue SQL from scenario modules;
- pass scenario flags into WMS command handlers;
- create hidden target columns in WMS files;
- set selector-specific error probability;
- bypass WMS validation to force a scenario;
- use snapshots as live state;
- generate cube without retaining dimensions;
- assign fixed case capacity to locations; or
- add pallet IDs without implementing their lifecycle.

## 16. Reproducibility

Same code, normalized configuration, and seed must produce equivalent:

- WMS master files;
- live closing inventory;
- workflow records;
- inventory transactions;
- snapshots;
- standard report outputs;
- ground truth; and
- reconstruction outputs.

Documented execution timestamps are the only ordinary exclusions from canonical equivalence.
