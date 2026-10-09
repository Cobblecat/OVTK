# 02 — Requirements and Acceptance Criteria

## 1. Requirement language

- **Must** indicates a release requirement.
- **Should** indicates an expected design choice that may change through a recorded decision.
- **May** indicates an optional enhancement.

Requirement identifiers are stable and must be reflected in the traceability matrix.

## 2. WMS identity and provenance

### FR-001 — Run metadata

Every generated database must contain one run record with:

- run ID;
- seed;
- facility timezone;
- simulation start and end;
- schema version;
- generator version;
- normalized configuration hash; and
- generation timestamp.

Schema-3 WMS run metadata is neutral and must not contain scenario name,
scenario version, controlled-pattern identity, targets, or hidden intent.
Scenario identity belongs only in external simulator configuration and the
restricted ground-truth artifact where applicable. Legacy schema-1/2 metadata
remains unchanged for historical compatibility.

**Acceptance:** A reviewer can identify exactly what created the database and compare two runs canonically.

### FR-002 — Schema versioning

Corrected WMS generation must use schema version `3.0.0`. Legacy schema `1.0.0` and `2.0.0` databases must not be silently upgraded in place.

**Acceptance:** Validators route by schema version; generation refuses unsafe overwrites; new artifacts identify `3.0.0`.

## 3. Master files

### FR-003 — Item master

The WMS must maintain an `item_master` file with warehouse-relevant item profile data.

Required fields include:

- item ID and description;
- category;
- required storage zone;
- case length, width, and height;
- system-calculated case cube;
- case weight;
- cases per layer;
- layers per pallet;
- cases per pallet;
- fragility, shelf life, velocity, expected demand, and active status.

**Acceptance:** Dimensions are positive; cube equals dimensions divided by 1,728 cubic inches per cubic foot within documented tolerance; cases per pallet equals cases per layer times layers per pallet.

### FR-004 — Location master

The WMS must maintain a `location_master` file containing stable location profile data.

Required fields include:

- location ID;
- zone;
- location type;
- aisle, bay, level, and position where applicable;
- pallet capacity where applicable;
- pickable flag; and
- active flag.

The file must not contain live item assignment, current quantity, fixed case capacity, equipment-area metadata, code date, or last transaction.

**Acceptance:** Schema inspection and validators confirm prohibited fields are absent and location-type rules are enforced.

### FR-005 — Live inventory master

The WMS must maintain an `inventory_master` file keyed by the same `location_id` defined in `location_master`.

The initial corrected model must contain exactly one inventory row for every location.

Required fields include:

- location ID;
- current item ID, nullable when legitimately empty;
- recorded quantity on hand in cases;
- code date where applicable;
- replenishment trigger, minimum, target, and maximum for slotted pick locations;
- last inventory transaction ID; and
- last update timestamp.

**Acceptance:** Every location joins to exactly one inventory row; quantities are nonnegative integers; item and replenishment rules match location type.

### FR-006 — Initial one-position rule

The initial WMS must model at most one item and one code date per location and must omit pallet IDs.

**Acceptance:** A command attempting to introduce a second item or conflicting code date into an occupied location fails without partial changes.

## 4. WMS transaction and command behavior

### FR-007 — Public WMS commands

Inventory-affecting behavior must occur only through public WMS application services.

Required command families include:

- initialize or assign location inventory;
- record pick attempt;
- create, start, and confirm replenishment;
- record QA event;
- adjust inventory;
- record system event; and
- capture inventory snapshot.

**Acceptance:** Scenario and CLI code do not call WMS repositories or issue SQL directly.

### FR-008 — Immutable inventory transaction audit

Every accepted post-initialization recorded quantity change must write immutable `inventory_transaction` rows.

Each row must preserve:

- transaction ID;
- transaction group ID;
- command ID;
- event sequence and line number;
- transaction type;
- location and related location;
- item;
- signed quantity delta;
- balance before and after;
- operator where applicable;
- event and recorded timestamps;
- reason code; and
- source record type and ID.

**Acceptance:** Every live balance change is traceable to one or more audit rows; audit rows cannot be updated or deleted through normal application services.

### FR-009 — Atomic movement

A source-to-destination movement must update:

- source inventory;
- destination inventory;
- transaction audit rows;
- replenishment workflow state; and
- last-change references

inside one database transaction.

**Acceptance:** Forced failure at any intermediate step leaves all affected tables unchanged.

### FR-010 — Idempotent commands

Inventory-affecting commands must carry stable command IDs. Reprocessing the same accepted command must not post inventory twice.

**Acceptance:** Duplicate command submission returns the documented idempotent result or explicit duplicate error and preserves balances.

### FR-011 — Pick behavior

A pick attempt must enforce:

- valid selector, trip, item, and pick location;
- picked plus short quantity equals requested quantity;
- picked quantity does not exceed recorded available quantity;
- only picked quantity decrements live inventory; and
- a short quantity does not create an inventory decrement.

**Acceptance:** Hand-calculated fixtures prove live balance and transaction rows.

### FR-012 — Replenishment behavior

A replenishment workflow must support creation, optional start, and confirmation. Confirmation must validate item compatibility and sufficient recorded source quantity.

**Acceptance:** Confirmed quantity moves atomically from source to destination and creates balanced audit lines.

### FR-013 — QA behavior

QA observations must be recorded independently from inventory adjustment.

**Acceptance:** A QA event by itself does not alter `inventory_master`; a later accepted adjustment does and is separately auditable.

### FR-014 — Adjustment behavior

An inventory adjustment must preserve signed quantity, reason, operator, event time, recorded time, and source reference.

**Acceptance:** The adjustment updates live inventory and writes an immutable audit row exactly once.

### FR-015 — System-event behavior

System and equipment-friction events must be recorded without directly changing inventory unless a separate inventory command occurs.

**Acceptance:** Event records exist and live inventory remains unchanged.

## 5. Snapshot and report requirements

### FR-016 — Inventory snapshots

Opening, closing, cycle-count, or scheduled inventory snapshots must be immutable captures of `inventory_master` at a defined time.

Snapshots must not serve as the live balance file.

**Acceptance:** A snapshot can be regenerated from live inventory at capture time and later compared without changing the source balance.

### FR-017 — Standard WMS reports

The WMS must provide tested standard queries or views for:

- inventory by location;
- inventory by item;
- location profile with live contents;
- empty and available locations;
- code-date inventory;
- replenishment needs;
- open replenishment tasks;
- inventory transaction inquiry;
- adjustment history;
- QA activity; and
- inventory reconciliation.

**Acceptance:** Each report agrees with hand-authored SQL fixtures and reads only ordinary WMS files.

### FR-018 — Report transparency

Standard reports and ad hoc SQL must derive from the same source tables and rules.

**Acceptance:** No report reads hidden physical state, scenario configuration, or ground truth; report totals reconcile to direct table queries.

## 6. Simulator and scenario requirements

### FR-019 — Independent physical simulator

The simulator must maintain physical state separately from WMS recorded state.

**Acceptance:** Physical movement can occur before a WMS confirmation without changing `inventory_master` until an ordinary WMS command is submitted.

### FR-020 — External scenario drivers

Baseline and investigation scenarios must schedule physical actions and submit public WMS commands. They must not write WMS storage directly.

**Acceptance:** Dependency tests and code review show no scenario-to-storage imports; a deliberately blocked repository call is unavailable to scenario code.

### FR-021 — WMS scenario ignorance

The WMS core must contain no scenario-specific branches, target selection, hidden labels, or pattern names.

**Acceptance:** Static source scan and dependency tests find no prohibited scenario concepts in WMS modules.

### FR-022 — Scenario extensibility

A new scenario must be addable by implementing the scenario protocol without modifying WMS domain, application, or storage modules.

**Acceptance:** A small test scenario generates valid WMS records using the existing public interface.

### FR-023 — Baseline normal operations

Normal operation must be generated before controlled scenarios and must remain valid when investigation patterns are disabled.

**Acceptance:** Baseline passes all WMS, reporting, transaction, and reconstruction checks without controlled signatures.

### FR-024 — Controlled investigation patterns

The investigation scenario must preserve:

- replenishment timing gap;
- QA damage masking; and
- selector false lead through differential exposure.

**Acceptance:** Restricted calibration confirms each pattern while ordinary WMS validation remains ground-truth-free.

### FR-025 — Ground-truth isolation

Restricted truth must remain outside the WMS database and ordinary reports.

**Acceptance:** Schema, value, identifier, CSV, and report leakage scans return no findings.

## 7. Reconstruction and analysis requirements

### FR-026 — Transaction replay

Reconstruction must use opening inventory and immutable `inventory_transaction` rows to calculate recorded closing inventory.

**Acceptance:** Every audit row is applied exactly once in deterministic order.

### FR-027 — Three-way reconciliation

Reconstructed closing inventory must match both:

- finalized live `inventory_master`; and
- scheduled closing snapshot.

**Acceptance:** Differences are zero for accepted baseline and investigation artifacts or are reported as hard failures.

### FR-028 — Read-only analysis

Reconstruction and analysis must not modify the WMS database.

**Acceptance:** Source checksum is unchanged after every analysis workflow.

### FR-029 — Analyst-ready outputs

The project must export factual, reproducible context tables for picks, replenishments, QA-adjustment candidates, selector exposure, inventory transactions, and reconciliation.

**Acceptance:** Outputs have stable schemas, ordering, source references, and manifests.

### FR-030 — Statistical investigation

Phase 5 must define denominators, estimate crude and adjusted selector associations, quantify uncertainty, test competing hypotheses, and run sensitivity checks.

**Acceptance:** Raw labor counts are never the sole evidence; predefined adjusted results and limitations are reproducible.

### FR-031 — Evidence and reporting

The project must produce a hypothesis evidence table, thin notebook, figures, and management-facing report.

**Acceptance:** Every displayed number traces to a generated source or tested derived artifact.

### FR-032 - Interactive WMS console

Release 0.2.0 must provide a persistent console that reuses application
workflows for database lifecycle, inquiry, reports, export, and trace.

**Acceptance:** Source and standalone launches expose equivalent command
behavior; interface code contains no SQL or WMS business rules.

### FR-033 - Read-only source protection

Every existing database must open read-only by default. Application write
permission must not be inferred from filesystem permissions or filenames.

**Acceptance:** Inquiry and report sessions preserve source bytes, and mutation
commands are unavailable outside a verified application-created sandbox.

### FR-034 - Protected sandbox lifecycle

Writable copies must retain verifiable source/run/schema/hash provenance and use
an explicit additive sandbox schema without modifying accepted schema-3 sources.

**Acceptance:** Clone/upgrade is atomic, existing destinations are refused,
incomplete output is cleaned, and only a valid sandbox identity plus matching
manifest can enter write mode.

### FR-035 - Versioned CSV preview workflow

Inventory-adjustment and replenishment-control CSV files must use stable
headers, deterministic normalization, typed validation, expected-state checks,
and a non-mutating preview artifact.

**Acceptance:** Every row receives a validation result; one invalid row blocks
the batch; preview modifies no database and produces a checksum manifest.

### FR-036 - Atomic idempotent CSV apply

Apply must consume an accepted preview, revalidate source state immediately,
and submit public WMS commands under one complete-batch transaction.

**Acceptance:** Drift or row failure rolls back the whole batch, repeated batch
identity cannot double-post, and every accepted row maps to command and result
audit records.

### FR-037 - Inventory-adjustment maintenance

Writable sandboxes must apply signed case adjustments through the existing
adjustment semantics and immutable inventory audit.

**Acceptance:** Role, item/location, quantity, capacity, reason, and expected
state rules are enforced, with post-batch validation and snapshot evidence.

### FR-038 - Replenishment-control maintenance

Writable sandboxes must maintain pick-slot minimum, trigger, target, and maximum
through a public WMS command with immutable before/after history and no inventory
movement.

**Acceptance:** Ordered controls, item assignment, pick-location type, dynamic
physical maximum, role, and expected state validate atomically.

### FR-039 - Standalone Windows distribution

Release 0.2.0 must provide a portable Windows 10/11 x64 ZIP that launches
without Python, `uv`, VS Code, a repository checkout, first-run installation,
or internet access after extraction.

**Acceptance:** The bundle opens a safe sample read-only, supports its documented
workspace workflows, includes licenses/manifests/checksums, and passes clean
standalone reproduction.

### FR-040 - Restricted-truth exclusion

The interactive console and primary Windows bundle must not contain, expose, or
depend on restricted scenario truth.

**Acceptance:** Bundle and ordinary workflow leakage scans are empty; only the
separate optional 0.1.0-style truth policy may distribute restricted truth.

### FR-041 - Release 0.1.0 compatibility

All accepted source commands, schema-version routes, analysis, reporting, and
release workflows from 0.1.0 must remain supported during 0.2.0 development.

**Acceptance:** The full prior regression suite remains green at each release
phase gate and `v0.1.0` remains unchanged.

## 8. Nonfunctional requirements

### NFR-001 — Local and free

The complete workflow must run locally after dependency installation without required network access or per-use charges.

### NFR-002 — Deterministic

Equivalent code, configuration, seed, and platform assumptions must produce equivalent canonical content.

### NFR-003 — Inspectable

An analyst must be able to inspect the SQLite database, SQL schema, source code, reports, and validation rules.

### NFR-004 — Testable

Every WMS state rule, transaction rule, scenario rule, reconstruction rule, and statistical calculation must have appropriate automated tests.

### NFR-005 — Maintainable

Dependency direction must remain explicit; WMS, simulation, scenario, analysis, and reporting responsibilities must not collapse into one generator.

### NFR-006 — Safe failure

Invalid commands, partial failures, existing outputs, incompatible schemas, and corrupt data must fail explicitly without silent repair or partial posting.

### NFR-007 — Practical performance

Portfolio-sized generation, reports, reconstruction, and analysis must complete within documented local runtime targets.

### NFR-008 — Privacy and professional safety

All data are synthetic and must not resemble real employee identities or disclose proprietary system information.

### NFR-009 — Portable outputs

The release must provide SQLite and stable CSV outputs; optional XLSX is presentation-only.

### NFR-010 — Backward preservation

Legacy artifacts and tests must remain preserved until corrected equivalents pass. Historical generated databases are not modified in place.

## 9. Phase 4A release acceptance

Phase 4A is complete only when:

1. schema `3.0.0` is generated from configuration;
2. every location has one live inventory row;
3. item dimensions and calculated cube validate;
4. location profiles contain no fixed case capacity or equipment-area field;
5. inventory changes occur only through WMS services;
6. every quantity change has immutable audit evidence;
7. transfers are atomic and idempotent;
8. WMS core runs without scenario imports;
9. scenarios cannot write storage;
10. standard reports match direct queries;
11. baseline and investigation scenarios preserve required signatures;
12. three-way reconciliation passes;
13. hidden-truth leakage is empty;
14. deterministic reproduction passes;
15. all applicable legacy and new tests pass; and
16. documentation and traceability are current.
