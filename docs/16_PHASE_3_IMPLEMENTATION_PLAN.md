# 16 - Phase 3 Implementation Plan

> **Historical implementation record.** This plan describes the completed
> legacy schema-2 controlled-overlay implementation. Phase 4A supersedes its
> in-generator overlay/state transition architecture with external scenario
> drivers that submit ordinary public commands to the independent schema-3 WMS.
> The controlled mechanisms and restricted-truth purpose remain historical
> traceability, not the corrected runtime contract.

## 1. Purpose, Deliverable, and Exclusions

Phase 3 creates the investigation scenario by adding controlled failure overlays to the Phase 2 baseline generator. Normal operations remain the starting point.

Deliverable:

> Given an investigation configuration and seed, the application creates a fresh analyst-facing SQLite database with ordinary operational records plus three controlled mechanisms, and separately writes restricted ground truth sufficient to validate those mechanisms without leaking labels into analyst-facing tables.

Explicit exclusions:

- no inventory-ledger reconstruction for analysis;
- no anomaly-detection service;
- no Pandas investigation workflow;
- no confidence intervals or adjusted models;
- no notebooks, charts, dashboards, ranked findings, recommendations, or executive reports.

## 2. Phase 2 Extension Points

Phase 2 already provides the required transaction surface:

- schema version `2.0.0`;
- trips, pick events, replenishment tasks, QA events, adjustments, system events, and closing snapshots;
- a deterministic `StateTransitionProcessor`;
- version-routed `validate` and `describe`;
- canonical content comparison;
- safe output refusal and cleanup.

Phase 3 extends the generator, not the analyst schema. The existing `generate --config --output` workflow gains an optional restricted ground-truth output path. Baseline behavior is preserved when all failure sections are absent or disabled.

## 3. Overlay Architecture

Implementation follows this model:

1. Generate the Phase 1 foundation and opening state.
2. Build normal Phase 2 operating plans.
3. Select eligible targets from ordinary master/slot/operator data.
4. Apply scenario overlays while the existing event processor creates records.
5. Persist only ordinary analyst-facing transaction rows.
6. Persist hidden labels and mechanism facts in a separate restricted JSON artifact.
7. Run hard dataset validation and restricted scenario calibration.

The overlays do not mutate a completed SQLite database and do not create parallel failure-only transaction models.

## 4. Configuration

`configs/baseline.toml` remains baseline-only.

`configs/investigation.toml` enables:

- `[failures.replenishment_gap]`;
- `[failures.qa_masking]`;
- `[failures.selector_false_lead]`.

Each section has an `enabled` flag and deterministic count/rate parameters. Missing failure sections default to disabled.

## 5. Random Streams

Phase 3 adds isolated streams:

- `failure_replenishment_gap`;
- `failure_qa_masking`;
- `failure_selector_exposure`.

Target selection for one pattern must not depend on random calls from another pattern. Downstream inventory interactions are allowed and documented because all accepted events share one state processor.

## 6. Pattern A - Replenishment Timing Gap

Target selection:

- one zone selected from active zones;
- several high-velocity slot assignments in that zone;
- one mid-run operating window.

Overlay behavior:

- target slot trips are overrepresented during the affected window;
- replenishment is delayed or skipped before affected picks when forward quantity reaches the trigger;
- affected picks can short from true depletion or delayed visibility;
- later confirmed replenishments and positive corrections provide ordinary observable recovery evidence.

Ground truth records affected zone, items, window, altered pick IDs, replenishment IDs, and correction IDs.

## 7. Pattern B - QA Damage Masking

Target selection:

- fragile eligible items, locations, and plausible event times.

Overlay behavior:

- QA damage events occur before related generic negative adjustments;
- adjustments use ordinary generic reason codes rather than explicit causal labels;
- the analyst database has no direct hidden QA-adjustment causal key.

Ground truth records the hidden QA-to-adjustment relationship and affected quantities.

## 8. Pattern C - Selector False Lead

Target selection:

- one selector selected from active selectors using deterministic eligibility.

Overlay behavior:

- target selector receives disproportionate trips in the Pattern A zone/window;
- no selector-specific error propensity is added;
- exposed peers may also receive affected trips and shorts.

Ground truth records the target selector, exposed peer selectors, and trip/pick exposure counts.

## 9. Ground Truth

Ground truth is a restricted JSON artifact with:

- schema version;
- run/config identity;
- enabled patterns;
- affected entities and windows;
- injected or altered event IDs;
- hidden pattern relationships;
- calibration summaries.

The ordinary `validate` and `describe` commands never read this artifact.

## 10. Validation and Calibration

Dataset validation remains analyst-facing and schema-version routed.

Scenario calibration verifies:

- all enabled patterns are present;
- affected records are a minority of total operations;
- Pattern A shorts cluster in the target zone/window and high-velocity items;
- later recovery evidence exists;
- Pattern B QA events precede masked generic adjustments;
- Pattern C target selector ranks highest or near-highest by raw shorts;
- selector exposure, not selector-specific error propensity, explains the false lead;
- ground-truth references resolve;
- no forbidden labels leak into analyst-facing schema or values.

## 11. CLI and Workflows

`generate` gains:

```powershell
--ground-truth <path>
```

When failures are enabled, this path is required. The command refuses to overwrite either the analyst database or ground-truth artifact and cleans up newly created outputs on failure.

Add:

```powershell
scenario-check --database <path> --ground-truth <path>
```

This restricted developer validation is separate from ordinary analyst validation.

## 12. Test Strategy

Add tests for:

- failure config parsing and rejection;
- baseline generation with failures disabled;
- each pattern independently enabled;
- all patterns enabled;
- ground-truth overwrite refusal and cleanup;
- leakage scanning;
- scenario calibration;
- same-seed reproducibility for analyst and ground-truth outputs;
- different-seed valid variation.

## 13. Completion Gate

Phase 3 is complete when:

- full tests pass;
- Ruff lint and format checks pass;
- baseline generation still contains no controlled failures;
- investigation generation writes both safe outputs;
- analyst validation passes;
- restricted scenario calibration passes;
- reproducibility checks pass for analyst and ground truth;
- documentation and status are updated.
