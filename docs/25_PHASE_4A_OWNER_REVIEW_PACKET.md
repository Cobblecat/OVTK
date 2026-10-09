# 25 - Phase 4A Owner Review Packet

## 1. Review purpose and evidence

This packet records the Phase 4A owner review and the bounded inventory
realism calibration required for final acceptance. Sections 2-6 preserve the
original review evidence. Section 10 records the definitive calibrated
artifacts and acceptance result. Phase 5 implementation is not authorized here.

Initial evidence inspected read-only:

- `artifacts/data/schema3_baseline.sqlite3`;
- `artifacts/data/schema3_investigation.sqlite3`;
- `artifacts/reports/schema3_baseline_inventory_by_location.csv`;
- `docs/04_DATA_MODEL_AND_DICTIONARY.md`; and
- `docs/22_STANDARD_WMS_REPORTS_CONTRACT.md`.

The representative owner-review rows below use the scenario-neutral baseline:

| Field | Value |
|---|---|
| Run ID | `RUN-0AA91A281BA99A73` |
| Schema | `3.0.0`; SQLite `user_version = 3` |
| Seed | `20260801` |
| Configuration hash | `bfad772a0171c842edcc3d0aeb4de5ba6fa4c6f4e2423ae13198c200d6563bf9` |
| Simulation period | `2026-05-04T07:00:00+00:00` through `2026-05-14T19:00:00+00:00` |
| Foundation counts | 96 items, 192 locations, 192 live inventory rows |
| Audit count | 1,055 immutable inventory transaction lines |

The investigation artifact is run `RUN-D4876095A8166078`, also schema `3.0.0`,
with the same item, location, inventory, and audit column contracts. It contains
1,289 audit lines. Restricted scenario intent is not used in this packet.

## 2. Item master review - approved

Cube is independently recalculated as
`length_in x width_in x height_in / 1,728`. Cases per pallet is independently
recalculated as `cases_per_layer x layers_per_pallet`.

| Item | Description | L x W x H (in) | Stored cube (ft3) | Recalculated cube (ft3) | Weight (lb) | Cases/layer | Layers/pallet | Stored cases/pallet | Recalculated cases/pallet | Zone | Velocity | Fragility score | Shelf life (days) |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---|---:|---:|
| `ITEM-0001` | Synthetic item 1 | 16 x 12 x 15 | 1.666667 | 1.666667 | 29.66 | 12 | 7 | 84 | 84 | FROZEN | A | 0.03 | 31 |
| `ITEM-0035` | Synthetic item 35 | 21 x 10 x 6 | 0.729167 | 0.729167 | 40.58 | 11 | 6 | 66 | 66 | CHILLED | B | 0.28 | 65 |
| `ITEM-0066` | Synthetic item 66 | 23 x 9 x 8 | 0.958333 | 0.958333 | 20.61 | 12 | 7 | 84 | 84 | AMBIENT | C | 0.59 | 51 |

### Owner decision

- The sampled stored cube and cases-per-pallet values recalculate exactly.
- Dimensions, weight, pallet pattern, zone, velocity, and shelf-life fields are
  recognizable WMS master-data concepts and include their units in the schema.
- The existing schema and calculation rules are approved unchanged.
- `fragility_score` is a synthetic 0.0-1.0 handling-sensitivity scale; higher
  values indicate greater sensitivity.
- Generic descriptions are approved for Phase 4A. Plausible synthetic grocery
  descriptions are a Phase 6 presentation improvement.

## 3. Location master review - approved

Only stable profile fields are shown.

| Location | Zone | Type | Aisle | Bay | Level | Position | Pallet capacity | Pickable | Active |
|---|---|---|---|---:|---:|---:|---:|---:|---:|
| `LOC-00001` | FROZEN | PICK | A1 | 1 | 1 | 1 | 1 | 1 | 1 |
| `LOC-00003` | AMBIENT | PICK | A1 | 3 | 1 | 1 | 1 | 1 | 1 |
| `LOC-05001` | FROZEN | RESERVE | A1 | 1 | 2 | 1 | 2 | 0 | 1 |
| `LOC-05002` | CHILLED | RESERVE | A1 | 2 | 2 | 1 | 2 | 0 | 1 |
| `LOC-05003` | AMBIENT | RESERVE | A1 | 3 | 2 | 1 | 2 | 0 | 1 |

All three zones contain 32 pick and 32 reserve locations. Pick locations have
pallet capacity 1 and reserve locations have pallet capacity 2. All 192
locations are active. There are no inactive, staging, dock, QA-hold, or other
special location types in the current generated baseline.

Schema inspection confirms that `location_master` contains none of the
following:

- current item assignment;
- current quantity;
- fixed case capacity;
- equipment area;
- replenishment controls;
- code date; or
- transaction or last-change metadata.

### Owner decision

- The separation between stable profile and live inventory is clean.
- `pallet_capacity` remains the approved term; case capacity remains dynamic.
- PICK and RESERVE are the complete Phase 4A location-type scope. No special
  location types are added merely for demonstration.

## 4. Initial inventory master review - calibration required

The evidence below records the pre-calibration inventory distribution, which
was not approved. Section 10 contains the corrected, accepted distribution.

`inventory_master` has exactly one row for each of the 192 locations.

| Selection | Location | Item | Qty | Code date | Minimum | Trigger | Target | Dynamic maximum | Last transaction | Last update UTC |
|---|---|---|---:|---|---:|---:|---:|---:|---|---|
| Occupied pick | `LOC-00001` | `ITEM-0001` | 36 | 2026-06-04 | 8 | 21 | 50 | 84 | `TXN-001227-01` | `2026-05-14T18:05:32.479320Z` |
| Occupied reserve | `LOC-05001` | `ITEM-0001` | 84 | 2026-06-04 | N/A | N/A | N/A | N/A | N/A | `2026-05-04T07:00:00+00:00` |
| Below trigger | `LOC-00019` | `ITEM-0019` | 7 | 2026-06-22 | 3 | 8 | 21 | 35 | `TXN-001122-01` | `2026-05-13T22:50:54.793371Z` |
| Highest pick utilization | `LOC-00041` | `ITEM-0041` | 23 | 2026-07-14 | 4 | 10 | 24 | 40 | `TXN-001116-01` | `2026-05-13T21:25:57.272710Z` |
| Second-highest pick utilization | `LOC-00046` | `ITEM-0046` | 23 | 2026-06-04 | 4 | 10 | 24 | 40 | `TXN-001154-01` | `2026-05-14T05:15:47.355354Z` |

There are no zero-quantity assigned pick locations and no empty reserve
locations. The two fullest pick slots are only `23 / 40 = 57.5%` of their
dynamic maximum, so this baseline does not contain a genuinely near-maximum
pick example. Fifteen pick locations are at or below their replenishment
trigger, including `LOC-00003` at 3 cases against a trigger of 3 and
`LOC-00019` below trigger as shown above.

### Empty-location interpretation

The zero-row `empty-locations` result is valid under the implemented generator:
every pick and reserve location starts assigned and every location still has a
positive recorded quantity at close. It is not a schema or report defect.

It is operationally thin, however. A warehouse with 100% occupied reserve
locations exposes no available-location capacity and cannot demonstrate the
empty-location inquiry. The review recommends a decision on whether a future
generation revision should retain deterministic but nonzero empty reserve
capacity. No generation change is made by this review.

## 5. Transaction history review - approved

The traces are ordered by event sequence and time. An audit balance is the
inventory state immediately after that command. The closing live-master value
is also shown where later commands changed the same location.

### 5.1 Full pick

| Step | Evidence |
|---|---|
| Command | `BASE-PICK-000001`, `RecordPickAttempt`, sequence 6, accepted `2026-05-04T09:15:27.520661Z` |
| Workflow | `PICK-000006`, trip `TRIP-000005`, selector/operator `OP-0001`, `ITEM-0003` at `LOC-00003` |
| Outcome | Requested 1, picked 1, short 0; full pick; no reason code |
| Event / recorded | `2026-05-04T09:14:57.520661Z` / `2026-05-04T09:15:27.520661Z` |
| Audit | Group `TXG-000006`; `TXN-000006-01`, PICK `-1`, balance `9 -> 8`, source `PICK-000006` |
| Resulting state | 8 cases immediately after the pick; closing live master is 3 after later audited activity, last transaction `TXN-001096-01` |

### 5.2 Partial pick

| Step | Evidence |
|---|---|
| Command | `BASE-PICK-000015`, `RecordPickAttempt`, sequence 21, accepted `2026-05-04T12:10:25.041322Z` |
| Workflow | `PICK-000021`, trip `TRIP-000015`, selector/operator `OP-0002`, `ITEM-0017` at `LOC-00017` |
| Outcome | Requested 2, picked 1, short 1; reason `BASELINE_ACCESS` |
| Event / recorded | `2026-05-04T12:09:55.041322Z` / `2026-05-04T12:10:25.041322Z` |
| Audit | Group `TXG-000021`; `TXN-000021-01`, PICK `-1`, balance `36 -> 35`, reason `BASELINE_ACCESS` |
| Resulting state | Only the picked case decrements inventory; closing live master is 22 after later audited activity, last transaction `TXN-001216-01` |

### 5.3 Replenishment lifecycle and transfer group

All three commands resolve to workflow record `REPL-000473` for `ITEM-0048`,
source `LOC-05048`, destination `LOC-00048`, operator `OP-0019`.

| Sequence | Command | Accepted UTC | Workflow evidence |
|---:|---|---|---|
| 473 | `BASE-REPL-CREATE-000001` (`CreateReplenishmentTask`) | `2026-05-08T20:20:51.074372Z` | Created for 6 cases |
| 474 | `BASE-REPL-START-000001` (`StartReplenishmentTask`) | `2026-05-08T20:22:51.074372Z` | Started UTC matches command acceptance |
| 475 | `BASE-REPL-CONFIRM-000001` (`ConfirmReplenishmentTask`) | `2026-05-08T20:28:21.074372Z` | Confirmed 6 at `20:27:51.074372Z`, recorded at `20:28:21.074372Z`, final status CONFIRMED, no delay reason |

Confirmation writes one atomic transaction group:

| Group / line | Type | Location | Related location | Delta | Before -> after | Operator | Event / recorded UTC |
|---|---|---|---|---:|---|---|---|
| `TXG-000475` / `TXN-000475-01` | TRANSFER_OUT | `LOC-05048` | `LOC-00048` | -6 | `15 -> 9` | `OP-0019` | `20:27:51.074372Z` / `20:28:21.074372Z` |
| `TXG-000475` / `TXN-000475-02` | TRANSFER_IN | `LOC-00048` | `LOC-05048` | +6 | `3 -> 9` | `OP-0019` | `20:27:51.074372Z` / `20:28:21.074372Z` |

The group sums to zero. Later audited activity leaves the closing live source at
3 cases (`TXN-000889-01`) and destination at 6 (`TXN-001137-01`). One traceability
question remains: `replenishment_task` stores create and confirm command IDs but
not `start_command_id`; the start is still resolvable through `wms_command`.

### 5.4 Inventory adjustment

| Step | Evidence |
|---|---|
| Command | `BASE-ADJ-000001`, `AdjustInventory`, sequence 141 |
| Workflow | `ADJ-000141`, `ITEM-0022` at `LOC-00022`, operator `OP-0029`, delta -1, reason DAMAGE, reference `BASE-QA-000001` |
| Event / recorded | Both `2026-05-05T14:45:23.809915Z` |
| Audit | Group `TXG-000141`; `TXN-000141-01`, DAMAGE `-1`, balance `33 -> 32`, source `ADJ-000141` |
| Resulting state | 32 cases immediately after adjustment; closing live master is 19 after later audited activity, last transaction `TXN-001123-01` |

### 5.5 QA event with no direct quantity change

| Step | Evidence |
|---|---|
| Command | `BASE-QA-000001`, `RecordQaEvent`, sequence 140 |
| Workflow | `QA-000140`, `DAMAGE_FOUND`, `ITEM-0022` at `LOC-00022`, operator `OP-0026`, affected quantity 1 |
| Event / recorded | Both `2026-05-05T14:45:22.809915Z` |
| Reason / disposition | `DAMAGED_CASE` / `DISPOSE` |
| Audit | No transaction group and zero `inventory_transaction` lines |
| Resulting state | QA alone leaves recorded quantity unchanged. The separate adjustment command above occurs one second later and carries its own audit line. The reference does not by itself prove a causal relationship. |

### 5.6 Snapshot capture

| Step | Evidence |
|---|---|
| Command | `BASE-CLOSING-SNAPSHOT`, `CaptureInventorySnapshot`, sequence 1229, accepted `2026-05-14T19:00:00Z` |
| Workflow record | Batch `SNAPSHOT-001229`, type `CLOSING_SYSTEM`, source `BASELINE_DRIVER`, 192 lines |
| Operator / reason | System service; no operator. Snapshot type and source identify purpose. |
| Audit | No transaction group and zero quantity-audit lines because capture is read-only |
| Representative result | `SNAPLINE-001229-0001`: `LOC-00001`, `ITEM-0001`, quantity 36, code date `2026-06-04`, last transaction `TXN-001227-01` |
| Resulting state | Live `LOC-00001` remains 36 with the same item and last transaction; capture does not mutate inventory |

### 5.7 Atomicity and audit checks

| Direct SQL check | Result |
|---|---:|
| Audit lines where `before + delta != after` | 0 |
| Transfer groups not containing two balanced lines | 0 |
| Audit lines with missing command | 0 |
| Audit lines with missing workflow source | 0 |
| QA commands with audit lines | 0 |
| Snapshot commands with audit lines | 0 |
| Live rows whose last transaction does not resolve | 0 |

Every persisted quantity change is therefore represented by an immutable,
balanced audit line or balanced transfer group in this artifact. The existing
command tests separately prove rollback under injected storage failure.

## 6. Standard report review - approved with terminology cleanup

All 12 registered schema-3 reports were run against the baseline. Direct SQL
agreement means either exact agreement with the registered reusable view or an
exact/spot-checked agreement with the report's documented source query. The
existing `schema3_baseline_inventory_by_location.csv` also agrees with the
registered inventory-by-location output.

Parameters used where required:

- code-date as-of date: `2026-05-14`;
- snapshot batch: `SNAPSHOT-001229`; and
- reconciliation snapshot batch: `SNAPSHOT-001229`.

Audience abbreviations are SS (shift supervisor), IC (inventory control
analyst), and WA (WMS analyst).

| Report | Purpose and grain | Rows | Direct SQL agreement | Useful to |
|---|---|---:|---|---|
| `inventory-by-location` | Current profile and recorded contents; one row/location | 192 | Exact reusable-view and CSV agreement | SS, IC, WA |
| `inventory-by-item` | Recorded stock summary; one row/item | 96 | Exact reusable-view agreement | IC, WA; summary use for SS |
| `location-profile` | Profile plus derived current occupancy; one row/location | 192 | Exact reusable-view agreement | IC, WA |
| `empty-locations` | Zero-quantity locations; one row/empty location | 0 | Exact reusable-view agreement | SS, IC, WA when nonempty |
| `code-date-inventory` | Code-date aging; one row/occupied coded location | 192 | Source SQL agreement | SS, IC |
| `replenishment-needs` | Pick slots at/near trigger; one row/qualifying slot | 15 | Source SQL agreement | SS, IC |
| `open-replenishment-tasks` | CREATED/STARTED tasks; one row/open task | 0 | Source SQL agreement | SS, IC, WA when nonempty |
| `inventory-transaction-inquiry` | Immutable audit; one row/audit line | 1,055 | Direct audit-table agreement | IC, WA |
| `adjustment-history` | Recorded adjustments; one row/adjustment | 4 | Exact reusable-view agreement | IC, WA |
| `qa-activity` | Recorded QA activity; one row/QA event | 8 | Exact reusable-view agreement | SS, IC |
| `inventory-snapshot` | Selected recorded snapshot; one row/location | 192 | Snapshot-table agreement | IC, WA |
| `inventory-reconciliation` | Live master versus selected snapshot; one row/location | 192 | Direct live/snapshot join agreement | IC, WA |

### 6.1 Representative report rows

| Report | Representative evidence |
|---|---|
| `inventory-by-location` | `LOC-00003`, AMBIENT PICK, `ITEM-0003`, qty 3, physical maximum 15, occupancy 20.0%, trigger 3; `LOC-00006`, qty 11, maximum 45, occupancy 24.44%, trigger 11 |
| `inventory-by-item` | `ITEM-0001`, FROZEN/A, total 120 = pick 36 + reserve 84, 2 locations, 1.429 pallet equivalents; `ITEM-0002`, CHILLED/A, total 119, 1.417 pallet equivalents |
| `location-profile` | `LOC-00003` and `LOC-00006`, AMBIENT PICK, active/pickable, capacity 1, recorded occupied flag 1 |
| `empty-locations` | No rows. Output fields still include address, pallet capacity, assigned item, active/pickable flags, and last update. |
| `code-date-inventory` | `ITEM-0045` at `LOC-00045`, qty 14, and `LOC-05045`, qty 18; both code date `2026-06-03`, 20 days from as-of date, AMBIENT/B, Category 5 |
| `replenishment-needs` | `ITEM-0003` at `LOC-00003`: qty 3, target 9, recommend 6, compatible reserve 8; `ITEM-0006` at `LOC-00006`: qty 11, target 27, recommend 16, compatible reserve 45 |
| `open-replenishment-tasks` | No rows. Output fields include task, item, source/destination, status, operator, requested quantity, times, age, current quantities, and delay reason. |
| `inventory-transaction-inquiry` | `TXN-000006-01`, PICK `-1`, `9 -> 8`, `OP-0001`; `TXN-000007-01`, PICK `-1`, `27 -> 26`, `OP-0001` |
| `adjustment-history` | `ADJ-000141`, `ITEM-0022`, DAMAGE `-1`, `33 -> 32`; `ADJ-000278`, `ITEM-0034`, DAMAGE `-1`, `37 -> 36` |
| `qa-activity` | `QA-000140`, `ITEM-0022`, DAMAGE_FOUND, affected 1, DISPOSE; `QA-000277`, `ITEM-0034`, same event/disposition |
| `inventory-snapshot` | `LOC-00001`, `ITEM-0001`, qty 36; `LOC-00002`, `ITEM-0002`, qty 35; both closing batch at `2026-05-14T19:00:00Z` |
| `inventory-reconciliation` | `LOC-00001` and `LOC-00002`: live equals selected snapshot, difference 0, status MATCH |

### 6.2 Questions resolved by owner terminology

| Report | Owner-facing terminology question |
|---|---|
| `inventory-by-location` | Owner decision: use `Item ID`; Item is the canonical project term and the contract example now uses `ITEM-0001`. |
| `inventory-by-item` | Is `required zone` preferable to `required_zone_code`, and is pallet-equivalent quantity familiar enough for supervisor use? |
| `location-profile` | `occupied_flag` is recorded-WMS occupancy, not observed physical occupancy; should the label say `recorded occupied`? |
| `empty-locations` | Should the report name or display distinguish unassigned reserve from a zero-quantity assigned pick slot? |
| `code-date-inventory` | `days_to_code_date` is relative to an explicit date and does not itself mean days to expiration. Is `code-date age/status` clearer? |
| `replenishment-needs` | `compatible reserve quantity` is recorded compatible stock, not a guarantee of physical availability. Should `recorded` be included in the label? |
| `open-replenishment-tasks` | Task age is calculated against an explicit as-of timestamp. Is that sufficiently clear in normal output? |
| `inventory-transaction-inquiry` | Event time and recorded time have different meanings. Should output labels expand to `operational event time` and `WMS recorded time`? |
| `adjustment-history` | `reference_code` is a source reference, not causal proof. Should it be labeled `source reference`? |
| `qa-activity` | The report correctly avoids claiming a linked adjustment. Is `affected quantity` clear as observed/recorded QA scope rather than an inventory delta? |
| `inventory-snapshot` | Should the title explicitly say `Recorded Inventory Snapshot` to avoid confusion with physical truth? |
| `inventory-reconciliation` | Recommend the display title `Live-versus-Snapshot Reconciliation`; full transaction replay is external and must remain excluded. |

External transaction replay was not run or treated as a standard WMS report in
this review.

## 7. Owner decision record

| Review area | Owner decision | Implemented consequence | Status |
|---|---|---|---|
| Item master | Approve existing fields/calculations; define fragility scale; defer grocery descriptions to Phase 6 | Documentation clarified; no schema change | Approved |
| Location master | Approve PICK/RESERVE-only scope and `pallet capacity` | No location-type or schema change | Approved |
| Inventory master | Require one bounded realism calibration | Deterministic empty reserves, zero pick slots, and near-maximum slots added without schema/scenario changes | Approved after Section 10 verification |
| Transaction history | Approve normalized `wms_command` trace | No `start_command_id` added | Approved |
| Standard reports | Approve with exact owner-facing terminology | CLI/CSV labels and empty-location classification updated | Approved |

## 8. Owner review checkpoint

All five areas were reviewed and approved after the inventory calibration:

1. representative item-master rows;
2. representative location-master rows;
3. representative inventory-master rows;
4. representative transaction history; and
5. standard-report usefulness and terminology.

The five checklist boxes are complete. Phase 4A is accepted. Phase 5 Slice 0
planning is next; Phase 5 implementation has not started.

## 9. Initial review-task verification

- All 12 registered reports: passed against the schema-3 baseline using
  temporary outputs; existing acceptance output was not overwritten.
- Targeted direct-SQL comparisons: passed for report rows/counts, master
  calculations, prohibited location fields, transaction balances, transfer
  conservation, workflow references, and non-quantity QA/snapshot behavior.
- `git diff --check`: passed.
- `uv run ruff format --check .`: passed (124 files already formatted).
- Runtime code and tests changed: no.
- Full Pytest suite: intentionally not run because only documentation changed.
- Phase 5 implementation: not started.

## 10. Inventory calibration and final acceptance

Definitive regenerated artifacts:

- `artifacts/data/schema3_baseline_accepted.sqlite3`;
- `artifacts/data/schema3_investigation_accepted.sqlite3`;
- `artifacts/restricted_ground_truth/schema3_investigation_accepted.json`;
- `artifacts/reports/schema3_baseline_accepted`; and
- `artifacts/analysis/schema3_baseline_accepted` and
  `artifacts/analysis/schema3_investigation_accepted`.

The generator keeps 96 pick and 96 reserve locations. It deterministically
selects B/C-velocity pairs only: the reserve is unassigned and empty, while
small disjoint paired-pick subsets remain assigned at zero or at least 90% of
dynamic maximum. A-velocity target candidates and scenario logic are unchanged.

| Closing measure | Baseline | Investigation | Acceptance |
|---|---:|---:|---|
| Empty reserves | 14/96 (14.6%) | 18/96 (18.8%) | PASS: both within 10-20% |
| Assigned zero-quantity picks | 4 | 5 | PASS: small and nonzero |
| Pick slots at least 90% of maximum | 3 | 3 | PASS: small and nonzero |
| Stocked reserve locations | 82 | 78 | PASS |
| Recorded reserve cases | 3,057 | 2,764 | PASS |
| Confirmed replenishments | 59 | 78 | PASS |

The reserve-clearing rule now clears item and code date atomically when a
non-pick transfer source reaches zero. The baseline empty-location report has
18 rows: 14 `Unassigned Empty Reserve` and 4
`Assigned Zero-Quantity Pick Slot`, with no unclassified zero state.

All owner-approved presentation labels are active in CLI and CSV output while
canonical technical fields remain unchanged. Item is the canonical term; SKU
is not used for schema-3 presentation.

All 12 accepted baseline reports passed with row counts: inventory by location
192, inventory by item 96, location profile 192, empty locations 18, code-date
inventory 174, replenishment needs 12, open replenishment tasks 0, transaction
inquiry 1,091, adjustment history 4, QA activity 8, recorded inventory snapshot
192, and live-versus-snapshot reconciliation 192.

Scenario calibration passed unchanged: Pattern A has 28 affected shorts, 2
delayed confirmations, and 8 recoveries; Pattern B has 10 QA events and 10
generic adjustments; Pattern C has 28 target trips and 229 target picks.

Reconstruction passed with zero differences at all 192 locations. Baseline has
1,283 ledger rows and source SHA-256
`4225d8472887037b73d8d50f0eb3756961f1bf46939522d89b97ac89918c83d4`;
investigation has 1,499 ledger rows and source SHA-256
`104e2b903777b91ecdbde16fe5d4a7852925658c7e228a707416ac1ad7238aff`.
Both sources were preserved byte-for-byte.

Final verification:

- baseline and investigation validation: PASS, no failures or warnings;
- all 12 standard reports: PASS;
- scenario check: PASS, no failures or warnings;
- baseline and investigation reconstruction: PASS, zero differences;
- same-seed reproducibility and changed-seed validity: PASS through Pytest;
- `uv run pytest`: 160 passed in 68.26 seconds;
- `uv run ruff check .`: passed (`All checks passed!`);
- `uv run ruff format --check .`: passed (124 files already formatted);
- `git diff --check`: passed (line-ending conversion warnings only); and
- Phase 5 implementation: not started.
