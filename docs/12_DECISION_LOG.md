# 12 - Decision Log

## 1. Purpose

This log records material product and engineering decisions that resolve choices intentionally left open by the assignment brief. It prevents a later contributor from silently changing the investigation, trust model, or architecture.

Status values:

- **Accepted** - current project direction.
- **Proposed** - preferred but not yet implemented or confirmed.
- **Superseded** - replaced by a later decision.
- **Deferred** - intentionally postponed.

## Remediation interpretation

Decisions ADR-001 through ADR-028 preserve the project history. Where a later ADR supersedes an implementation detail, the earlier decision remains evidence of the legacy design but no longer controls schema `3.0.0` behavior.

## ADR-001 - Use a separate repository from the Gwent Deck Workbench

**Status:** Accepted
**Decision:** Build the Operational Variance Investigation Toolkit as a new repository and preserve the Gwent Deck Workbench as a paused project.
**Reason:** The products have different domains, data models, release goals, and documentation. Combining them would create misleading package boundaries and unnecessary history.
**Consequence:** No Gwent package, roadmap, or source code is renamed or overwritten.

## ADR-002 - Begin as a modular monolith

**Status:** Accepted
**Decision:** Use one Python package, one CLI, one source repository, and one release with internal domain, application, generation, storage, analysis, and reporting boundaries.
**Reason:** The project needs clear responsibilities but not distributed deployment, services, queues, or plugin infrastructure.
**Consequence:** Interfaces are introduced only where a concrete testing or second-implementation need exists.

## ADR-003 - Use SQLite as the canonical analyst-facing source

**Status:** Accepted
**Decision:** Persist the operational dataset in a versioned SQLite database and export stable CSVs for portability.
**Reason:** SQLite preserves relational joins, constraints, local reproducibility, and auditability without requiring a server.
**Consequence:** CSV is an export, not the authoritative state. Optional XLSX is presentation-only.

## ADR-004 - Use standard-library `sqlite3` initially

**Status:** Accepted
**Decision:** Write explicit SQL and use Python's `sqlite3` adapter for the first implementation.
**Reason:** The schema is controlled, the application is local, and explicit SQL makes transaction and reconciliation behavior transparent. An ORM would add concepts before a demonstrated need.
**Consequence:** Repositories own row translation and SQL access. Domain/application code does not consume raw SQLite rows.

## ADR-005 - Maintain dual inventory state during simulation

**Status:** Superseded in implementation detail by ADR-031 and ADR-036
**Decision:** Distinguish hidden simulator physical quantity from analyst-facing system quantity.
**Reason:** The investigation depends on timing and recording differences. A single quantity cannot represent both real item availability and system belief without destroying the mechanism being studied.
**Consequence:** The simulator may use physical state to prevent impossible movements while emitting only recorded transactions and snapshots to analyst tables.

## ADR-006 - Keep ground truth physically separate

**Status:** Accepted
**Decision:** Store injection metadata and true mechanism labels in a separate restricted artifact, not columns in analyst-facing tables.
**Reason:** The analysis must infer mechanisms from evidence. A hidden flag in the same database creates leakage risk and weakens the portfolio demonstration.
**Consequence:** Ordinary analyst loaders do not accept or discover the restricted path. Scenario acceptance tests may load both through a dedicated developer-only interface.

## ADR-007 - Prove baseline coherence before injecting failures

**Status:** Accepted
**Decision:** Complete and validate normal operations before implementing controlled patterns.
**Reason:** Generator defects can resemble variance mechanisms. Baseline-first development provides a control and isolates scenario effects.
**Consequence:** Phase 2 has baseline alert ceilings, and Phase 3 overlays failures through explicit scenario configuration.

## ADR-008 - Keep notebooks thin

**Status:** Accepted
**Decision:** Use the notebook as a narrative and orchestration layer; place reusable calculations in tested package modules.
**Reason:** Important metrics and report numbers need reviewable tests and must not depend on notebook execution history.
**Consequence:** Notebook cells call public analysis functions and display returned tables/figures.

## ADR-009 - Calibrate claims below causal certainty

**Status:** Accepted
**Decision:** Describe results as descriptive, comparative, inferential, or mechanism-consistent unless a design supports a stronger claim.
**Reason:** The synthetic scenario contains known truth for validation, but the analyst-facing exercise is observational and includes confounding, clustering, and timing dependence.
**Consequence:** The report may state that evidence is more consistent with a process-timing explanation than generalized selector error; it must not portray an adjusted coefficient as real-world causal proof.

## ADR-010 - Use deterministic identifiers and named random streams

**Status:** Accepted
**Decision:** Use stable human-readable IDs and explicitly seeded named random streams.
**Reason:** Reproducibility must survive refactors and must not depend on Python's randomized hash or unrelated function-call order.
**Consequence:** Persisted IDs never use `hash()`, and random generation never uses module-global random state.

## ADR-017 - Use NumPy SeedSequence-based named streams for Phase 1

**Status:** Accepted
**Decision:** Implement named random streams with a stable hash-derived seed material that is independent of request order, using `numpy.random.SeedSequence` underneath.
**Reason:** Later master-data generation needs separate deterministic streams without coupling to incidental draw order or unrelated stream creation.
**Consequence:** The initial slice adds NumPy as a runtime dependency and uses closed stream names such as `master_items`, `master_locations`, `operators`, `schedules`, and `opening_inventory`.

## ADR-018 - Reject ambiguous or nonexistent local wall times for New York conversions

**Status:** Accepted
**Decision:** Treat New York local times that fall into the DST gap or fold ambiguity as invalid rather than silently accepting them.
**Reason:** The slice requires deterministic time conversion helpers, and silently accepting ambiguous wall times would create non-repeatable downstream timestamps.
**Consequence:** The helpers raise a clear `ValueError` for unsupported local wall times, and the tests document the chosen behavior.

## ADR-019 - Use in-memory physical opening state for Phase 1

**Status:** Superseded for recorded system state by ADR-031; physical-state separation remains accepted
**Decision:** Initialize baseline physical inventory as an in-memory typed `PhysicalInventoryState` returned by the opening-inventory generator, while persisting only analyst-facing handling units and opening system snapshots to SQLite.
**Reason:** Phase 1 needs the system/physical distinction for deterministic later simulation, but it does not yet need a separate restricted artifact because no controlled failures or hidden labels exist.
**Consequence:** The analyst database has no hidden truth columns. Later phases may add a separate restricted ground-truth or physical-state artifact through a new decision if simulation restartability requires serialization.

## ADR-020 - Introduce schema version 2.0.0 for Phase 2 transactions

**Status:** Accepted
**Decision:** Treat Phase 2 normal transaction generation as a schema-version boundary, adding `trip`, `pick_event`, `replenishment_task`, `qa_event`, `inventory_adjustment`, `system_event`, and closing snapshot support under schema version `2.0.0` / SQLite `user_version = 2`.
**Reason:** Phase 1 artifacts contain only master/opening state. Transaction tables materially change the public database contract and validation requirements, so fresh Phase 2 artifacts should identify themselves explicitly.
**Consequence:** Version-routed validation is needed. Existing Phase 1 databases remain valid under Phase 1 rules, and Phase 2 generation should create new databases rather than migrating completed artifacts in place.

## ADR-021 - Use a deterministic state transition event processor for Phase 2

**Status:** Superseded by ADR-032 for schema `3.0.0`; retained as legacy Phase 2 design
**Decision:** Process Phase 2 inventory-affecting operations through a single deterministic state transition engine. Candidate events become persisted records only after the engine applies them to the current hidden physical state and analyst-facing system state, records required before/after facts, mutates state, and assigns a monotonically increasing `event_sequence`.
**Reason:** Phase 1 could safely keep physical state in memory because initialization was one bounded workflow. Phase 2 needs to explain exactly what physical inventory and recorded system inventory become after every pick, movement, confirmation, damage event, and adjustment. Table-local ordering or ad hoc generator updates would make equal-time behavior and ledger reconstruction ambiguous.
**Consequence:** Workflow design, state transition rules, and equal-time ordering stay under primary architecture review. Generators may draft candidate plans, but the event processor owns acceptance and state mutation. Validators must enforce event ordering and replay the analyst-facing system ledger against persisted before/after facts and closing snapshots.

## ADR-022 - Add a separate Phase 2 `generate` command

**Status:** Accepted
**Decision:** Keep `init-db --config <path>` as the Phase 1 initialization command and add `generate --config <path> --output <path>` for Phase 2 baseline generation.
**Reason:** Phase 2 generation materially expands behavior beyond database initialization. A separate command avoids silently changing `init-db`, gives acceptance runs a safe explicit output path, and prevents accidental overwrite of `artifacts/data/baseline.sqlite3`.
**Consequence:** `validate` and `describe` are version-routed and support both Phase 1 and Phase 2 databases. README examples now show both the Phase 1 initialization path and the Phase 2 generation path.

## ADR-023 - Use modest explicit baseline operation defaults for Phase 2

**Status:** Accepted
**Decision:** Add an optional `[operations]` configuration section and set the baseline config to 120 trips, 6-10 pick lines per trip, 0.5% baseline short probability, 8 QA events, 3 damage events, 4 adjustments, and 4 system events.
**Reason:** The baseline needs all required transaction families to appear in local acceptance runs without producing an oversized portfolio artifact before controlled failure patterns are designed.
**Consequence:** Phase 2 acceptance produces 969 pick events and 91 replenishment tasks with deterministic validation. Later portfolio calibration may increase row counts after Phase 3 scenario overlays and runtime targets are known.

## ADR-024 - Implement Phase 3 failures as overlays on normal operations

**Status:** Superseded by ADR-036
**Decision:** Implement replenishment timing gap, QA damage masking, and selector false lead as deterministic scenario overlays inside the existing Phase 2 event generator and state transition processor.
**Reason:** The approved mechanisms are operational changes to timing, exposure, and transaction coding. Overlaying normal event creation preserves the coherent chronology and avoids parallel failure-specific transaction models or post-hoc database mutation.
**Consequence:** Baseline behavior remains unchanged when failure sections are absent or disabled. Scenario effects share the same analyst-facing tables, validators, and state processor as normal operations.

## ADR-025 - Use restricted JSON ground truth for Phase 3

**Status:** Accepted
**Decision:** Write Phase 3 hidden labels and mechanism facts to a separate restricted JSON artifact rather than adding analyst-facing columns or a ground-truth table to the analyst database.
**Reason:** Phase 3 needs deterministic scenario validation, but ordinary analyst workflows must not see target selectors, pattern names, hidden relationships, or physical timing facts.
**Consequence:** `generate` requires `--ground-truth <path>` when failure overlays are enabled. `validate` and `describe` ignore ground truth. `scenario-check` requires both paths explicitly.

## ADR-026 - Preserve analyst schema version 2.0.0 for Phase 3

**Status:** Accepted
**Decision:** Do not bump the analyst-facing SQLite schema for Phase 3 because existing Phase 2 transaction tables can represent the required ordinary evidence.
**Reason:** The new hidden scenario labels belong in restricted ground truth, not in analyst-facing schema. A schema bump would imply a public data-contract change that is not needed.
**Consequence:** Phase 3 investigation databases validate under schema `2.0.0`; only configuration, generation behavior, and restricted artifact output change.

## ADR-027 - Export Phase 4 reconstruction as external derived artifacts

**Status:** Accepted
**Decision:** Keep the Phase 2/3 SQLite database immutable and write Phase 4 reconstruction outputs as run-scoped CSV files plus `analysis_manifest.json` outside the source database.
**Reason:** Inventory reconstruction is derived analytical evidence, not a source transaction. External artifacts preserve the raw/generated source layer, make reproducibility comparisons straightforward, and avoid a schema bump for tables that can be regenerated from existing analyst-facing records.
**Consequence:** The public `reconstruct --database <path> --output <analysis-directory>` command opens the source database read-only, validates source compatibility, exports deterministic derived files, and refuses existing nonempty output directories.

## ADR-028 - Defer Pandas until Phase 5 analytical preparation

**Status:** Accepted
**Decision:** Do not add Pandas for Phase 4 reconstruction.
**Reason:** The implemented Phase 4 transforms are explicit deterministic row replays, small contextual joins, and portable CSV/JSON serialization over moderate local data. Standard-library `sqlite3`, `csv`, and `json` keep inventory-delta semantics visible and easy to fixture-test. Pandas becomes more valuable in Phase 5 when statistical preparation, grouping, and modeling workflows need DataFrame ergonomics.
**Consequence:** Phase 4 adds no runtime dependency. Phase 5 may introduce Pandas when the analytical workflow uses it directly.

## ADR-011 - Target Python 3.14 and use `uv`

**Status:** Accepted for initial development
**Decision:** Use Python 3.14 or later and `uv`, matching the existing local development environment.
**Reason:** This avoids environment drift during implementation and retains the existing development toolchain.
**Consequence:** Broader Python compatibility may be evaluated before public release; do not use 3.14-only features without a real benefit.

## ADR-012 - Do not create an opaque associate risk score

**Status:** Accepted
**Decision:** Report transparent counts, denominators, rates, uncertainty, exposure, and conditional model estimates. Do not collapse findings into a single associate score or ranking product.
**Reason:** The assignment's central lesson is that raw labor attribution can be misleading. A score would hide assumptions and invite misuse.
**Consequence:** Any operator-level output includes context, denominators, and explicit limitations.

## ADR-013 - Use integer case quantities as the initial inventory unit

**Status:** Accepted
**Decision:** Model inventory and movement in whole cases for the initial release.
**Reason:** Case-level quantity is sufficient for the operational question and avoids false precision.
**Consequence:** Eaches, catch weight, and partial-case handling are excluded unless a later scenario requires them.

## ADR-014 - Preserve raw, derived, and presentation layers

**Status:** Accepted
**Decision:** Treat generated operational tables as immutable source records, build derived analytical tables from code, and generate presentation artifacts from derived results.
**Reason:** This mirrors the preparation materials' reproducible analytical chain and prevents spreadsheet-style silent edits.
**Consequence:** A report correction changes code/configuration and regenerates artifacts rather than editing a number manually.

## ADR-015 - Use event time in UTC and facility time for interpretation

**Status:** Accepted
**Decision:** Persist timezone-aware event timestamps normalized to UTC and retain the facility timezone in run metadata.
**Reason:** UTC provides unambiguous ordering; local operating day and shift interpretation still require facility time.
**Consequence:** Analysis utilities expose both UTC and derived local fields under documented rules.

## ADR-016 - Add runtime data dependencies only when used

**Status:** Accepted
**Decision:** Phase 0 has no analytical runtime dependencies. The only Phase 0 runtime dependency is `tzdata`, which provides portable IANA timezone data for `zoneinfo` on Windows Python installations that do not ship a system timezone database. NumPy, Pandas, Statsmodels, Matplotlib, and other data libraries will be added in the first phase that uses each package directly.
**Reason:** The initial CLI and configuration contract require IANA timezone validation, and the Windows Python 3.14 development environment does not resolve `America/New_York` without `tzdata`. Deferring analytical libraries keeps the lockfile and dependency surface tied to implemented behavior.
**Consequence:** Phase 1 must add NumPy before deterministic named random streams or stochastic master-data generation are implemented.

## Pending decisions

The following should be resolved only when the associated phase begins:

| ID | Decision | Needed by | Current preference |
|---|---|---:|---|
| P-001 | Physical-state restricted artifact format | Phase 1 | Resolved for Phase 1 by ADR-019; defer serialization until a later phase has a concrete need |
| P-002 | Whether runtime data dependencies are added up front or per phase | Phase 0 | Resolved by ADR-016 |
| P-003 | Exact portfolio-size row counts and runtime target | Phase 5 | Reassess after schema 3 remediation and corrected scenario generation |
| P-004 | Exact adjusted model family and cluster treatment | Phase 5 | Resolved by ADR-053 |
| P-005 | Optional XLSX output | Phase 6 | Add only if it improves management review |
| P-006 | Public-release Python compatibility floor | Phase 6 | Reevaluate 3.11-3.14 support after implementation |
| P-007 | Release format | Phase 6 | Source release first; packaged executable later if valuable |
| P-008 | Phase 2 public generation command shape | Phase 2 | Resolved by ADR-022 |
| P-009 | Phase 2 physical-state persistence | Phase 2 | Resolved for Phase 2 by ADR-021; keep in memory during generation |
| P-010 | Phase 2 baseline alert ceilings | Phase 2 | Resolved for local baseline by ADR-023; recalibrate for portfolio-sized Phase 3+ runs |
| P-011 | Phase 3 failure injection architecture | Phase 3/4A | Legacy approach superseded by ADR-036; migrate to external scenario drivers |
| P-012 | Phase 3 restricted ground-truth format | Phase 3 | Resolved by ADR-025 |
| P-013 | Phase 3 analyst schema version | Phase 3 | Resolved by ADR-026 |
| P-014 | Duplicate-command return behavior | Phase 4A Slice 2 | Resolved by ADR-047; reject an already accepted command ID without changing state |
| P-015 | Current assignment history file | Post-remediation | Defer until a re-slotting-history requirement exists |
| P-016 | Exact standard-report CLI shape | Phase 4A Slice 3 | Resolved by ADR-048; use one registered `report` command |
| P-017 | Legacy `init-db` versus new `init-wms` command | Phase 4A | Resolved by ADR-044; `init-wms` is canonical for schema 3 and `init-db` remains temporarily for legacy schema 1/2 |

## Decision procedure

A material decision entry should include:

1. Context and decision pressure.
2. Options considered.
3. Selected option.
4. Concrete reason.
5. Consequences and migration cost.
6. Date and status.

Routine refactors, local variable names, and obvious defect fixes do not require an ADR unless they change a public contract or analytical interpretation.


## ADR-029 - Require operational fidelity inside the modeled WMS scope

**Status:** Accepted
**Decision:** The project will not implement the full breadth of a production enterprise WMS, but every operational domain it does implement must follow credible WMS state, transaction, audit, and reporting semantics.
**Reason:** An experienced analyst must be able to trust the simulated source system before trusting an investigation built on it. Synthetic data and limited scope do not justify magical state changes or report-only balances.
**Consequence:** Phase 5 is paused while Phase 4A corrects the WMS core. The phrase “do not build a WMS” is interpreted as a breadth exclusion, not permission to weaken included inventory behavior.

## ADR-030 - Introduce schema version 3.0.0 for corrected WMS master files

**Status:** Accepted
**Decision:** Corrected generation will create fresh schema `3.0.0` databases containing `item_master`, `location_master`, `inventory_master`, and `inventory_transaction`.
**Reason:** The corrected live-state and audit contracts materially change the public WMS schema.
**Consequence:** Legacy schema `1.0.0` and `2.0.0` artifacts remain historical formats and are not migrated in place.

## ADR-031 - Persist live recorded inventory in inventory_master keyed by location

**Status:** Accepted
**Decision:** `inventory_master` is the authoritative mutable WMS balance file with exactly one row per location in the initial model. The location ID is the operational primary key and foreign key to `location_master`.
**Reason:** A warehouse analyst must be able to query what the WMS currently records at a location without replaying all transactions or relying on snapshots.
**Consequence:** In-memory state may continue for physical truth, but recorded system state is persisted and updated only through WMS application services.

## ADR-032 - Record every quantity change in an immutable inventory transaction audit

**Status:** Accepted
**Decision:** Every accepted post-initialization recorded quantity change writes append-only `inventory_transaction` rows in the same SQLite transaction that updates live inventory and the applicable workflow record. A transfer produces two signed rows under one transaction group.
**Reason:** Live balances require a complete audit trail, idempotency, atomicity, and independent replay.
**Consequence:** Workflow files do not substitute for the general audit. Reconstruction uses the audit file as the primary recorded inventory ledger.

## ADR-033 - Retain case dimensions and calculate cube and pallet quantity

**Status:** Accepted
**Decision:** `item_master` stores case length, width, height, and weight. The WMS calculates and stores case cube. It also stores cases per layer and layers per pallet and calculates or validates cases per pallet.
**Reason:** Dimensions are the source measurements and support slot fit, pallet construction, truck loading, and future operational logic. Cube alone discards information the user already had to collect.
**Consequence:** Generation and maintenance commands provide measurements; validators reject inconsistent calculated values.

## ADR-034 - Keep location_master as a stable location profile

**Status:** Accepted
**Decision:** `location_master` contains physical address metadata, location type, zone, pallet capacity, pickable status, and active status. It does not contain current item assignment, current quantity, fixed case capacity, equipment area, code date, replenishment controls, or last transaction.
**Reason:** Case capacity depends on the item; live assignment and quantity belong to the mutable inventory file; equipment area is not a required location-profile concept for the current WMS.
**Consequence:** Item-specific physical maximum is calculated from location pallet capacity and item pallet pattern.

## ADR-035 - Omit pallet IDs and handling-unit lifecycle from schema 3.0.0

**Status:** Accepted
**Decision:** The corrected initial model uses one item and one code date per location and does not include pallet IDs or a handling-unit file.
**Reason:** A pallet identifier is credible only with a complete creation, movement, split, merge, depletion, and status lifecycle. That complexity is not required for the initial investigation.
**Consequence:** Mixed items, mixed code dates, and pallet-level traceability are explicit post-release candidates.

## ADR-036 - Make scenarios external drivers of an independent WMS

**Status:** Accepted
**Decision:** Baseline and investigation scenarios generate ordered physical actions and ordinary WMS commands. Scenario code cannot write WMS storage. WMS core code cannot import scenario modules or branch on pattern identity.
**Reason:** This keeps the mini-WMS reusable and makes future scenarios scalable by changing transaction protocols rather than source-system internals.
**Consequence:** ADR-024 is superseded. Existing pattern logic is migrated outside the WMS and uses the same command interfaces as baseline activity.

## ADR-037 - Provide standard WMS reports over ordinary source files

**Status:** Accepted
**Decision:** The WMS will provide tested standard queries/views for inventory, locations, replenishment, transactions, adjustments, QA, code dates, and reconciliation.
**Reason:** Users should be able to inspect a realistic system through ordinary operational reports and ad hoc SQL.
**Consequence:** Report logic reads the same source files available to analysts and cannot read physical state or restricted truth.

## ADR-038 - Treat snapshots as scheduled report captures, not live inventory

**Status:** Accepted
**Decision:** Opening, closing, shift-end, and count snapshots are immutable captures of `inventory_master` at defined times.
**Reason:** Supervisory reports and checkpoints are common, but they do not replace live state or the transaction audit.
**Consequence:** Snapshot generation is a WMS service; reconstruction compares audit replay with both live inventory and snapshots.

## ADR-039 - Regenerate schema 3 artifacts rather than migrate generated databases

**Status:** Accepted
**Decision:** Existing schema `2.0.0` baseline and investigation databases remain historical acceptance artifacts. Corrected artifacts are regenerated from configuration under schema `3.0.0`.
**Reason:** Generated synthetic data are reproducible; in-place migration would add risk and produce less trustworthy provenance than clean regeneration.
**Consequence:** Version-routed legacy validation may remain, but Phase 5 uses corrected schema 3 artifacts.

## ADR-040 - Require three-way inventory reconciliation

**Status:** Accepted
**Decision:** Corrected reconstruction must prove opening snapshot plus immutable audit replay equals finalized live `inventory_master` and scheduled closing snapshot.
**Reason:** This independently verifies current WMS state, transaction history, and report capture.
**Consequence:** Any nonzero difference is a hard acceptance failure unless explicitly designed and separately scoped in a future scenario.

## ADR-041 - Use one item and one code date per location initially

**Status:** Accepted
**Decision:** Schema `3.0.0` uses one inventory-master row per location with at most one item and one code date.
**Reason:** This supports credible pick and reserve inventory without introducing incomplete pallet or lot-position complexity.
**Consequence:** A second item or conflicting code date is rejected until the location is empty or an explicit future model supports multiple positions.

## ADR-042 - Omit unsupported lot, status, and receipt fields

**Status:** Accepted
**Decision:** The initial corrected inventory master omits `lot_code`, a generic `inventory_status`, and `received_utc`. It retains `code_date`.
**Reason:** Lot, hold/status, and receipt timestamps require explicit receiving, lot-control, allocation, or status-transition workflows. Random fields without behavior create superficial realism.
**Consequence:** These fields may be added only with a documented domain and lifecycle.

## ADR-043 - Keep scenario identity outside schema-3 WMS metadata

**Status:** Accepted
**Decision:** Schema-3 `simulation_run` stores only neutral provenance: run ID, schema and generator versions, configuration hash, seed, facility timezone, simulation boundaries, and generation timestamp. It does not store scenario name, scenario version, controlled-pattern identity, or hidden intent.
**Reason:** The independent WMS must not know which external scenario is driving ordinary commands, and analyst-facing source data must not reveal restricted intent.
**Consequence:** Scenario identity remains in external simulator configuration and the restricted ground-truth artifact. Legacy schema 1/2 metadata remains unchanged.

## ADR-044 - Make init-wms canonical for schema 3

**Status:** Accepted
**Decision:** `init-wms` is the canonical schema-3 initialization command. `init-db` remains temporarily available for schema-1/2 compatibility and is labeled as the legacy path in CLI help and public documentation.
**Reason:** The corrected command name makes the new WMS boundary explicit without silently changing or removing successful legacy workflows.
**Consequence:** Schema-3 CLI work targets `init-wms`; compatibility routing and eventual `init-db` retirement require explicit tests and a later deprecation decision.

## ADR-045 - Keep transaction-replay reconciliation external to the WMS

**Status:** Accepted
**Decision:** A standard WMS reconciliation report may compare live `inventory_master` with a selected WMS snapshot. Full opening-plus-audit transaction replay remains an external read-only analytical workflow and is never imported into or written back into the WMS source database.
**Reason:** Operational reports should use ordinary WMS source files, while independent reconstruction must remain capable of auditing those files without becoming part of them.
**Consequence:** WMS views expose only live-versus-snapshot facts. Three-way replay reconciliation is produced as an external derived artifact.

## ADR-047 - Reject duplicate WMS command identifiers

**Status:** Accepted
**Decision:** Schema 3 records every accepted public command in a neutral `wms_command` registry. Reusing an accepted `command_id` raises `DuplicateCommandError` and commits no workflow, audit, or live-inventory changes.
**Reason:** An explicit rejection is deterministic and makes caller retry behavior visible. The registry also gives commands without a dedicated workflow command column, such as replenishment start and snapshot capture, the same idempotency boundary as quantity-changing commands.
**Consequence:** Callers that need the original result must retain it or query ordinary WMS records using the registry's result type and identifier. Scenario intent and command payload content are not stored; only a stable payload hash and neutral result references are retained.

## ADR-048 - Use one registered standard-report command

**Status:** Accepted
**Decision:** Expose schema-3 standard inquiry through one `report` command backed by a programmatic registry of stable report names, columns, and permitted parameters. Reusable parameterless inquiries also have read-only SQL views.
**Reason:** A single registry keeps validation, metadata, deterministic ordering, CSV safety, and CLI behavior consistent without creating a separate command and parser for every factual report.
**Consequence:** New standard reports require a registered definition, a storage query over ordinary WMS tables, stable output tests, and explicit parameters. Full transaction-replay reconstruction remains outside this registry.

## ADR-049 - Give external drivers a narrow WMS command gateway

**Status:** Accepted
**Decision:** Physical and scenario drivers receive preloaded read facts, an in-memory `PhysicalInventoryState`, and a protocol exposing only public WMS command methods. They do not receive a database connection or repository.
**Reason:** Removing storage handles from drivers makes the no-direct-write boundary structural while keeping physical action timing independent from recorded command timing.
**Consequence:** The application workflow alone constructs SQLite read adapters and `WmsService`. Physical actions execute in stable `(scheduled_utc, priority, action_id)` order, and closing physical-versus-recorded equality is checked before accepting a baseline artifact.

## ADR-050 - Implement investigation mechanisms as external policy overlays

**Status:** Accepted
**Decision:** The schema-3 investigation reuses the ordinary baseline protocol with a scenario-neutral policy contract for work allocation, physical timing, QA scheduling, and later corrections. The external investigation policy selects targets and records restricted chronology; it does not receive a database connection or repository. Pattern A records an ordinary replenishment confirmation before delayed physical completion, Pattern B submits ordinary QA and later unlinked count-correction commands, and Pattern C changes work exposure without changing selector-specific pick behavior.
**Reason:** A policy overlay preserves one transaction model and one public WMS command path while keeping hidden intent, physical chronology, and target identities outside analyst-facing WMS storage.
**Consequence:** The restricted ground-truth schema advances to `2.0.0` and contains task/record references plus confirmation-versus-physical timing evidence. The WMS remains scenario-independent, and baseline generation continues through the unchanged default policy.

## ADR-051 - Route reconstruction by source schema

**Status:** Accepted
**Decision:** The public `reconstruct` workflow retains the schema-2 reconstruction as a legacy compatibility path and routes schema-3 WMS sources to a separate audit-first builder. Schema 3 writes explicit opening-snapshot ledger lines followed by every immutable `inventory_transaction` row, then compares replayed closing quantity independently with live `inventory_master` and the selected closing WMS snapshot.
**Reason:** Schema-2 workflow rows were the only available movement evidence, while schema 3 has an authoritative audit file and live master. Separate builders preserve historical output behavior without weakening the corrected source contract or inferring quantity changes twice.
**Consequence:** Both routes retain the seven established output filenames. Schema-3 exports add transaction, transaction-group, and command traceability; its neutral manifest omits scenario identity. Reconstruction remains read-only and does not receive physical state or restricted ground truth.

## ADR-052 - Calibrate schema-3 opening occupancy outside scenario targets

**Status:** Accepted
**Decision:** The schema-3 foundation deterministically leaves every fifth B/C-velocity reserve position in the calibration sequence unassigned and empty. Small disjoint subsets of the paired pick assignments open at zero or at least 90% of dynamic maximum. A-velocity positions remain on the ordinary opening rule so controlled replenishment-gap target selection and calibration are unchanged.
**Reason:** The owner review required believable empty reserve capacity, assigned zero-quantity pick slots, and near-maximum inventory without adding location types, changing schema, or inserting scenario-specific WMS behavior.
**Consequence:** The configured 96-item artifacts retain 192 locations and close with 10-20% empty reserves, a small number of zero and near-maximum pick slots, and sufficient stocked reserves for ordinary replenishment. Physical state still preloads from the same WMS opening facts, and identical configuration and seed remain canonically reproducible.

## ADR-053 - Freeze a parsimonious clustered pick-event model

**Status:** Accepted
**Decision:** Use eligible pick event as the primary grain and a binomial-logit
model for `short_indicator`. Contrast the documented complaint selector
`OP-0002` with all peers while adjusting for the predefined ordinary
operational condition, centered requested quantity, A-versus-B/C velocity,
shift, operating-day index, and recorded active replenishment status. Use
trip-clustered covariance and report an average marginal risk difference. Use a
reduced HC3 linear-probability fallback only when the logit is rank-deficient,
unstable, nonconvergent, or inadequately supported.
**Reason:** The investigation has 33 short events over 1,133 eligible picks and
140 trips. The model must represent work mix without treating sparse selectors
or item/location cells as an associate score. Combining B/C avoids a separated
zero-short B nuisance coefficient while retaining the operational high-velocity
contrast.
**Consequence:** Material attenuation is frozen as at least 50% reduction in
the absolute crude contrast plus an adjusted residual no larger than two
percentage points. The accepted model converges without fallback and uses no
restricted truth. Sparse leave-one-item sensitivity fallback results remain
visible as limitations.

## ADR-054 - Keep Phase 5 outputs external, atomic, and truth-blind

**Status:** Accepted
**Decision:** The `analyze` workflow reads a schema-3 WMS and matching
reconstruction read-only, optionally reads a declared baseline negative-control
pair, and writes deterministic CSV/JSON statistics to a new external directory.
It validates source identity, grain, schemas, input checksums, output checksums,
and replay/live/snapshot equality; it has no ground-truth argument.
**Reason:** Statistical results are derived evidence and must not mutate source
records or gain hidden scenario knowledge. Atomic external outputs preserve the
auditable generated-to-derived chain.
**Consequence:** Existing nonempty output is refused, incomplete output is
cleaned, accepted source and reconstruction hashes are checked before and after
analysis, and only the manifest execution timestamp is non-deterministic.

## ADR-055 - Publish version 0.1.0 under the bounded local release policy

**Status:** Accepted
**Decision:** Release version `0.1.0` under the MIT License with Python `>=3.14`. Publish a local
versioned source ZIP and a separately named optional restricted-ground-truth spoiler ZIP, each with
manifest and SHA-256 verification. Include CSV, SQLite, notebook, figures, and PDF outputs; omit an
XLSX packet. Create a local `v0.1.0` Git tag only after acceptance and do not push or publish.
**Reason:** The source release must be reproducible and useful to reviewers without allowing hidden
truth to leak into analyst-facing data, reports, notebook inputs, or ordinary analysis.
**Consequence:** The primary archive contains no restricted truth or run-specific answer key. The
optional archive requires deliberate opening and is limited to developer validation or post-analysis
comparison. Compatibility below Python 3.14 requires a future full acceptance run.

## ADR-056 - Use prompt-toolkit as the focused interactive input dependency

**Status:** Accepted for release 0.2.0 engineering
**Decision:** Use `prompt-toolkit` 3.x for persistent input, command history,
completion, interrupt/EOF handling, and Windows terminal behavior. Keep table
and detail rendering application-owned in Phase 1 and do not add Rich unless
Phase 2 demonstrates a concrete unmet requirement.
**Reason:** Standard-library `input()` does not provide the roadmap's history and
completion experience. One focused BSD-licensed input dependency preserves a
small interface layer and packages successfully on Python 3.14.
**Consequence:** Interactive input degrades to plain, control-sequence-free text
for redirected or unsupported terminals. Business rules remain below the
console layer.

## ADR-057 - Build the Windows application with PyInstaller one-folder mode

**Status:** Accepted for release 0.2.0 engineering
**Decision:** Use PyInstaller 6.x as a development/build dependency and create a
Windows x64 one-folder application. Copy installed project metadata so frozen
version lookup uses the canonical package version.
**Reason:** A Python 3.14.6 proof bundled the selected input dependency, opened a
schema-3 SQLite database read-only, ran a standard report, and wrote a 192-row
CSV without Python or `uv` on the execution path. PyInstaller's license
exception permits distribution of the bundled MIT application.
**Consequence:** Phase 7 must prove the full dependency graph, generate
third-party notices, and record bundle size/startup behavior. Single-file mode,
installer work, code signing, and Nuitka are not selected.

## ADR-058 - Distribute release 0.2.0 as a portable Windows ZIP

**Status:** Proposed; owner presentation checkpoint pending
**Decision:** Package the one-folder executable, safe baseline sample, templates,
writable workspace, user documentation, license, notices, manifest, and
checksums as `Operational-Variance-Toolkit-0.2.0-Windows-x64.zip`.
**Reason:** The release objective is double-click use without Python, `uv`, VS
Code, installation, first-run downloads, or a repository checkout.
**Consequence:** The bundle contains no restricted truth. MSI/installer, Start
Menu registration, updates, and hosted distribution remain excluded.

## ADR-059 - Require a schema-3.1 sandbox marker and external provenance manifest

**Status:** Accepted for release 0.2.0 engineering
**Decision:** Accepted schema `3.0.0` databases remain read-only. Application-
created writable sandboxes receive an explicit additive schema `3.1.0`, a
database-side `sandbox_identity`, and a canonical JSON sidecar manifest with
source identity/hash, run/schema identity, creation metadata, and the initial
post-upgrade sandbox hash. Schema 3.1 adds narrow batch, row-map, and immutable
replenishment-control history tables.
**Reason:** Existing `wms_command` and adjustment/audit records support ordinary
inventory adjustments but cannot truthfully represent batch provenance or
before/after replenishment-control maintenance. Filename and filesystem
writability are not credible permission controls.
**Consequence:** Sandbox clone uses SQLite backup plus a transactional upgrade,
never changes the source, and cleans incomplete output. Preview remains external;
applied rows use public WMS commands and one atomic batch unit of work.

## ADR-060 - Make CSV preview identity deterministic and mandatory for apply

**Status:** Accepted for release 0.2.0 engineering
**Decision:** Define versioned exact headers for inventory adjustments and
replenishment controls, required expected-state fields, canonical normalization,
SHA-256 batch/row identities, external preview manifests, and a confirmation
token derived from the preview manifest. Blank expected values never mean
wildcard.
**Reason:** Spreadsheet edits are stale-prone and easy to submit twice. Stable
identity, state fingerprints, and immediate pre-apply revalidation provide
idempotency, traceability, and complete-batch refusal on drift.
**Consequence:** One invalid row blocks the batch, apply never creates an unseen
preview, repeated accepted batches do not double-post, and formula-safe CSV
serialization remains separate from the canonical hash payload.
