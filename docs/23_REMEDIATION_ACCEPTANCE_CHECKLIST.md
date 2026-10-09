# 23 — Phase 4A Remediation Acceptance Checklist

Use this as the final go/no-go checklist before Phase 5.

## A. Preservation

- [x] Legacy Phase 4 checkpoint committed.
- [x] Canonical Git tag `wms-remediation-safety-checkpoint` exists.
- [x] Remediation branch exists.
- [x] Legacy schema 1/2 artifacts remain unchanged.
- [x] Legacy test baseline recorded.
- [x] Existing generated databases were not migrated in place.

## B. Documentation and decisions

- [x] Corrected charter, requirements, architecture, data model, roadmap, and phase plan installed.
- [x] ADR-024 marked superseded.
- [x] New WMS-fidelity ADRs recorded.
- [x] Traceability matrix matches implemented behavior.
- [x] Project status identifies Phase 5 as paused until acceptance.
- [x] README reflects independent WMS and external scenarios.

## C. Schema 3

- [x] SQLite `user_version = 3`.
- [x] Schema metadata reports `3.0.0`.
- [x] `item_master` exists.
- [x] `location_master` exists.
- [x] `inventory_master` exists.
- [x] `inventory_transaction` exists.
- [x] Workflow files exist.
- [x] Snapshot file exists.
- [x] Required views/indexes exist.
- [x] Hidden-truth fields are absent.
- [x] Pallet/handling-unit fields are absent from corrected schema.

## D. Item master

- [x] Length, width, height, and weight are stored.
- [x] Cube is system-calculated and validated.
- [x] Cases per layer and layers per pallet are stored.
- [x] Cases per pallet is calculated/validated.
- [x] Zone, velocity, fragility, shelf-life, and active rules pass.
- [x] Deterministic generation passes.

## E. Location master

- [x] Stable address/profile fields are present.
- [x] Pallet capacity is present where applicable.
- [x] Fixed case capacity is absent.
- [x] Equipment area is absent.
- [x] Current item and quantity are absent.
- [x] Pickable/active/type rules pass.

## F. Inventory master

- [x] Exactly one row per location.
- [x] Quantity is integer and nonnegative.
- [x] Null item implies zero quantity and null code date.
- [x] Pick slots retain assigned item at zero.
- [x] Reserve locations clear item/code date at zero under documented rule.
- [x] One item and one code date per location enforced.
- [x] Replenishment controls valid for pick locations.
- [x] Dynamic maximum uses pallet capacity × cases per pallet.
- [x] Last transaction and update fields reconcile.

## G. WMS commands

- [x] WMS operates without simulator/scenario imports.
- [x] Typed commands and command IDs implemented.
- [x] Duplicate commands cannot double-post.
- [x] Pick full/partial/short behavior passes.
- [x] Short quantity does not decrement inventory.
- [x] Replenishment lifecycle passes.
- [x] Confirmed transfer writes balanced source/destination audit rows.
- [x] QA event alone does not change inventory.
- [x] Adjustment updates live inventory and audit.
- [x] System event does not change inventory.
- [x] Snapshot service captures live state.
- [x] Failure injection proves atomic rollback.

## H. Audit file

- [x] Every post-initialization quantity change has audit evidence.
- [x] Before + delta = after for every line.
- [x] Transfer groups conserve quantity.
- [x] Source workflow references resolve.
- [x] Event/line order is deterministic.
- [x] Normal application exposes no audit update/delete.

## I. Standard reports

- [x] Inventory by location.
- [x] Inventory by item.
- [x] Location profile/current contents.
- [x] Empty locations.
- [x] Code-date inventory.
- [x] Replenishment needs.
- [x] Open replenishment tasks.
- [x] Transaction inquiry.
- [x] Adjustment history.
- [x] QA activity.
- [x] Reports agree with direct SQL fixtures.
- [x] CSV exports are deterministic.
- [x] Reports use no physical state or ground truth.

## J. Simulation and scenario independence

- [x] Physical state is separate from WMS state.
- [x] Scenario modules do not import WMS storage.
- [x] Scenario modules contain no SQL.
- [x] Baseline uses public WMS commands.
- [x] Investigation uses the same public WMS commands.
- [x] Invalid commands are rejected identically across scenarios.
- [x] WMS core contains no pattern-specific names or branches.
- [x] Minimal new scenario test requires no WMS-core changes.

## K. Controlled patterns

- [x] Pattern A calibration passes.
- [x] Pattern B calibration passes.
- [x] Pattern C calibration passes.
- [x] Pattern C has no hidden selector propensity.
- [x] Target selector crude result remains plausible.
- [x] Pattern evidence uses ordinary WMS files.
- [x] Ground-truth references resolve.
- [x] Leakage scan returns empty.

## L. Reconstruction

- [x] Reconstruction uses `inventory_transaction` as primary audit source.
- [x] Every ledger row traces to an audit/source record.
- [x] Opening + audit = reconstructed closing.
- [x] Reconstructed closing = live inventory master.
- [x] Reconstructed closing = closing snapshot.
- [x] Baseline differences = 0.
- [x] Investigation differences = 0.
- [x] Source database checksums preserved.
- [x] Ground truth not loaded.
- [x] Derived outputs deterministic.

## M. Reproducibility and quality

- [x] Same config/seed produces equivalent WMS database content.
- [x] Same config/seed produces equivalent ground truth.
- [x] Same source produces equivalent reconstruction.
- [x] Different seed differs and remains valid.
- [x] Full Pytest suite passes.
- [x] Ruff lint passes.
- [x] Ruff format check passes.
- [x] `git diff --check` passes.
- [x] Local runtimes recorded.
- [x] No caches, virtual environments, or generated clutter added to release files.

## N. Final review

- [x] Sample item master rows were reviewed.
- [x] Sample location master rows were reviewed.
- [x] Sample inventory master rows were reviewed.
- [x] Sample transaction history was reviewed.
- [x] Standard report usefulness/terminology was reviewed.
- [x] Known limitations documented.
- [x] Phase 5 plan references corrected schema 3 outputs.
- [x] Project status marks Phase 4A technically complete.

Technical and owner acceptance evidence is recorded in `PROJECT_STATUS.md` and
`docs/25_PHASE_4A_OWNER_REVIEW_PACKET.md`. Phase 4A is accepted. Phase 5 Slice 0
planning is the next checkpoint; Phase 5 implementation has not started.
