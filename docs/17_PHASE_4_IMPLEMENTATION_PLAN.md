# 17 - Phase 4 Implementation Plan

> **Historical implementation record.** This plan describes the completed
> legacy schema-2 reconstruction, including workflow-inferred ledger effects
> and closing-snapshot reconciliation. Canonical schema-3 reconstruction now
> replays immutable `inventory_transaction` rows and compares the result with
> both live `inventory_master` and the selected closing snapshot. The legacy
> route remains supported for historical regression only.

## 1. Purpose, Deliverable, And Boundary

Phase 4 converts a validated analyst-facing Phase 2/3 SQLite database into deterministic derived analytical files. The deliverable is a reconstruction workflow that creates a signed inventory ledger, reconciles reconstructed closing system inventory to persisted closing system snapshots, and exports factual context tables for later analysis.

The phase stops at analytical foundation work. It does not calculate anomaly scores, confidence intervals, adjusted models, root-cause rankings, charts, notebooks, recommendations, or executive reports.

## 2. Existing Phase 3 Source Contracts

Phase 3 source databases use analyst schema `2.0.0` and SQLite `user_version = 2`. They contain one `simulation_run`, opening and closing system snapshots, deterministic `event_sequence_registry` rows, trips, picks, replenishments, QA events, inventory adjustments, and system events.

The ordinary analyst-facing database intentionally excludes hidden scenario labels, true root causes, physical-arrival timestamps, and simulator physical state. Restricted ground truth is a separate JSON artifact used only by scenario checks.

## 3. Read-Only Analytical Access Boundaries

The source SQLite database is immutable evidence. Phase 4 opens it read-only where practical, validates source compatibility before reconstruction, and verifies that the source file checksum is unchanged after the workflow.

Derived outputs are written outside the source database under `artifacts/analysis/<run-id>/` or another caller-provided analysis directory. No derived tables are inserted into the SQLite source, and no source transaction is repaired or overwritten.

## 4. Canonical Normalized Event Representation

The canonical ledger row represents one signed system-inventory effect:

- `run_id`;
- `ledger_sequence`;
- `event_sequence`;
- `event_type`;
- `source_table`;
- `source_record_id`;
- `source_line`;
- event and recorded timestamps;
- item, location, related location, operator, and trip identifiers;
- signed quantity delta;
- balance before and after;
- reason and status codes; and
- compact source evidence.

One source event may create more than one ledger row. Confirmed replenishment creates a source-location decrement and a destination-location increment.

## 5. Inventory-Delta Semantics

Opening system snapshots initialize balances and are not deltas.

Picks decrement only `picked_qty_cases` at the pick location. Short quantity is an unmet request and does not decrement system inventory.

Confirmed replenishments decrement the source location and increment the destination location by `confirmed_qty_cases`. Non-confirmed tasks provide context only.

QA events do not change system inventory by themselves. Damage affects the ledger only when an analyst-facing inventory adjustment records a signed system quantity change.

Inventory adjustments apply `qty_delta_cases` exactly once at the adjustment location.

System and equipment events provide context only and never create inventory deltas.

Closing system snapshots are reconciliation targets, not ledger deltas.

## 6. Deterministic Event Ordering

`event_sequence_registry` is the primary chronology. Ledger rows sort by:

1. `event_sequence`;
2. source-table order;
3. source record identifier; and
4. a stable source-line order.

For a confirmed replenishment, `source` precedes `destination`. The exported `ledger_sequence` is assigned after this ordering is fixed.

## 7. Opening-State Initialization

Opening balances are aggregated from `inventory_snapshot` rows where `snapshot_type = 'OPENING_SYSTEM'`, grouped by run, item, and location.

Every item/location touched by a ledger delta must have an opening system state row. Missing opening state is a hard reconstruction validation failure.

## 8. Per-Event Balances

The reconstruction service copies opening system balances into an in-memory balance map, applies each signed ledger row in deterministic order, and records balance before and after for the affected item/location.

Negative reconstructed balances are hard failures. The service does not infer physical inventory or use hidden simulator state.

## 9. Closing-State Reconciliation

Reconciliation groups opening state, signed deltas, and closing system snapshots by run, item, and location. It reports:

- opening quantity;
- total reconstructed delta;
- reconstructed closing quantity;
- reported closing quantity;
- difference;
- reconciliation status; and
- source-record counts.

Any unexplained difference between reconstructed and reported closing system quantity is a hard failure.

## 10. Derived Contextual Tables

Phase 4 exports:

1. `inventory_event_ledger.csv`;
2. `inventory_reconciliation.csv`;
3. `pick_context.csv`;
4. `replenishment_context.csv`;
5. `qa_adjustment_context.csv`; and
6. `selector_exposure.csv`.

The context tables contain factual fields only: item, location, zone, aisle, selector, trip, shift, timestamps, requested/picked/short quantities, velocity/handling facts, reconstructed balances, replenishment timing, recent QA/adjustment counts, system-event overlap indicators, candidate QA-adjustment relationships, and selector exposure denominators.

They do not contain hidden-truth scenario labels or root-cause claims.

## 11. Output And Manifest Contract

The default output layout is run-scoped:

```text
artifacts/analysis/<run-id>/
|-- analysis_manifest.json
|-- inventory_event_ledger.csv
|-- inventory_reconciliation.csv
|-- pick_context.csv
|-- replenishment_context.csv
|-- qa_adjustment_context.csv
`-- selector_exposure.csv
```

The manifest records source path, run ID, schema version, configuration hash, generator version, reconstruction version, source checksum, generated-at timestamp, output file checksums, row counts, and validation status.

CSV column order, row ordering, numeric serialization, and timestamp serialization are stable. Execution timestamps are excluded from reproducibility comparisons.

## 12. Validation Rules

Hard reconstruction validation covers:

- compatible schema `2.0.0`;
- exactly one run;
- valid source validation result;
- unique ledger identity;
- valid event sequence references;
- complete opening state for transacted item/location pairs;
- legal signed deltas;
- source traceability;
- no duplicate application of source rows;
- nonnegative reconstructed balances;
- exact closing reconciliation;
- output key uniqueness and stable ordering;
- absence of hidden-truth columns or values; and
- source checksum preservation.

Warnings may be used later for ambiguous contextual relationships. Phase 4 should not reinterpret analytical signals as structural failures.

## 13. Testing Strategy

Tests cover explicit sign and ordering fixtures, hand-calculated ledger and reconciliation results, baseline and investigation reconstruction, context relationships, selector exposure denominators, existing-output refusal, partial-output cleanup, source preservation, reproducibility, changed-source difference detection, hidden-truth leakage scanning, CLI behavior, and continued Phase 0-3 compatibility.

Generated analysis outputs remain temporary test artifacts.

## 14. Application Workflow And CLI

Add:

```powershell
uv run operational-variance-toolkit reconstruct --database <source.sqlite3> --output <analysis-directory>
```

The CLI parses arguments and prints factual run ID, source path, output path, row counts, and reconciliation status. The application workflow owns orchestration. Storage adapters own SQLite reads and CSV/JSON writes. Analysis services own ledger semantics and context construction.

## 15. Vertical Implementation Slices

1. Add the Phase 4 plan and decision-log entry.
2. Add read-only source access and repository reads.
3. Implement normalized ledger and reconciliation services with unit fixtures.
4. Implement context-table builders.
5. Add output writer, manifest, output validation, and cleanup.
6. Add application workflow and CLI command.
7. Add integration, CLI, reproducibility, and leakage tests.
8. Update README, roadmap, data dictionary, traceability, and project status.
9. Run final acceptance.

## 16. Phase 4 Acceptance Gate

At completion:

```powershell
uv run operational-variance-toolkit --help
uv run operational-variance-toolkit validate --database artifacts/data/phase3_baseline_acceptance.sqlite3
uv run operational-variance-toolkit validate --database artifacts/data/phase3_investigation.sqlite3
uv run operational-variance-toolkit reconstruct --database artifacts/data/phase3_baseline_acceptance.sqlite3 --output artifacts/analysis/<baseline-run-id>
uv run operational-variance-toolkit reconstruct --database artifacts/data/phase3_investigation.sqlite3 --output artifacts/analysis/<investigation-run-id>
uv run pytest
uv run ruff check .
uv run ruff format --check .
git diff --check
```

Also run same-source reproducibility comparison into two temporary output roots, excluding execution timestamps, and confirm a different valid source dataset produces different derived content.

## 17. Explicit Exclusions

Phase 4 excludes statistical modeling, confidence intervals, adjusted selector effects, root-cause ranking, ground-truth comparison, notebooks, charts, dashboards, reports, recommendations, and any source-database mutation.

## Plan Review

This plan was checked against the assignment brief, architecture, data model, investigation plan, validation strategy, statistical guardrails, Phase 2 and Phase 3 implementation plans, decision log, and current implementation.

No source-schema change, ground-truth dependency, or destructive migration is required.

## Dependency Decision

Pandas is not introduced in Phase 4. The implemented tables are deterministic row transforms and CSV exports over moderate local data, and standard-library `sqlite3`, `csv`, and `json` keep the semantics explicit and easy to fixture-test. Pandas remains appropriate for Phase 5 statistical preparation and modeling if the analysis workflow benefits from DataFrame operations.

## Implementation Result

Phase 4 is complete. The implemented workflow is:

```powershell
uv run operational-variance-toolkit reconstruct --database <source.sqlite3> --output <analysis-directory>
```

It exports the six planned CSV tables plus `analysis_manifest.json`, validates
ledger traceability and closing reconciliation, preserves the source database,
and keeps restricted ground truth outside ordinary reconstruction.
