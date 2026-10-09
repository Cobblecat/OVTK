# 11 — Requirements Traceability Matrix

## 1. Purpose

This matrix connects the corrected requirements to specifications, phases, verification, and final evidence.

## 2. Functional requirement traceability

| ID | Capability | Primary specification | Phase | Verification | Final evidence |
|---|---|---|---|---|---|
| FR-001 | Run metadata | Data model §5 | 1/4A | schema, CLI, manifest tests | `simulation_run`, manifests |
| FR-002 | Schema versioning | Architecture §17; Phase 4A | 4A | version-routing tests | schema `3.0.0`, legacy validators |
| FR-003 | Item master with dimensions/cube | Data model §6.1 | 4A | calculation fixtures | `item_master` |
| FR-004 | Stable location master | Data model §6.2 | 4A | schema/prohibited-field tests | `location_master` |
| FR-005 | Live inventory master | Data model §7.1 | 4A | one-row-per-location and state tests | `inventory_master` |
| FR-006 | One item/code date per location | Data model §7.1 | 4A | conflict rejection tests | WMS invariant results |
| FR-007 | Public WMS commands | Architecture §6 | 4A | application-service tests | WMS command API |
| FR-008 | Immutable audit history | Data model §7.2 | 4A | traceability and immutability tests | `inventory_transaction` |
| FR-009 | Atomic movements | Architecture §6.2 | 4A | rollback/failure injection tests | transfer audit groups |
| FR-010 | Idempotent commands | Data model §7.2 | 4A | duplicate-command tests | command IDs/audit |
| FR-011 | Pick behavior | Data model §9.2 | 2/4A | full/partial/short fixtures | `pick_event` + audit |
| FR-012 | Replenishment behavior | Data model §9.3 | 2/4A | lifecycle/conservation tests | task + two audit rows |
| FR-013 | QA separation | Data model §9.4 | 2/4A | QA no-delta tests | `qa_event` |
| FR-014 | Adjustments | Data model §9.5 | 2/4A | signed-delta tests | adjustment + audit |
| FR-015 | System events | Data model §9.6 | 2/4A | no-inventory-effect tests | `system_event` |
| FR-016 | Inventory snapshots | Data model §10 | 1/4A | capture-equality tests | `inventory_snapshot` |
| FR-017 | Standard WMS reports | Report contract | 4A | report fixture tests | views/CSV reports |
| FR-018 | Report transparency | Reporting spec §2 | 4A | direct SQL reconciliation | report audit results |
| FR-019 | Independent physical simulator | Architecture §12 | 4A | state-divergence tests | simulation module |
| FR-020 | External scenario drivers | Architecture §13 | 4A | dependency/runtime tests | scenario modules |
| FR-021 | WMS scenario ignorance | Architecture §4 | 4A | static prohibited-name/import scan | architecture audit |
| FR-022 | Scenario extensibility | Synthetic spec §14 | 4A | minimal new-scenario test | protocol fixture |
| FR-023 | Baseline normal operations | Synthetic spec §8 | 2/4A | baseline end-to-end gate | schema 3 baseline DB |
| FR-024 | Three controlled patterns | Synthetic spec §§9–11 | 3/4A | restricted calibration | investigation DB/truth |
| FR-025 | Ground-truth isolation | Architecture §14 | 3–6 | schema/value/export scans | restricted JSON |
| FR-026 | Transaction replay | Architecture §16 | 4A | hand-calculated reconstruction | event ledger |
| FR-027 | Three-way reconciliation | Requirements §7 | 4A | baseline/investigation equality | reconciliation CSV |
| FR-028 | Read-only analysis | Architecture §16 | 4–6 | source checksum tests | preserved source checksums |
| FR-029 | Analyst-ready outputs | Data model §12 | 4A | schema/order/repro tests | context CSVs |
| FR-030 | Statistical investigation | Analysis plan; frozen contract | 5 | metric/model/sensitivity/reproducibility tests | accepted statistical outputs and manifest |
| FR-031 | Evidence and reporting | Reporting spec | 5–6 | six-hypothesis and claim-to-source audit | hypothesis table; Phase 6 notebook/report |

| FR-032 | Interactive WMS console | Release 0.2.0 roadmap; Phase 0 contract | 0.2 Phase 1-2 | parser/session/subprocess tests | source and standalone console |
| FR-033 | Read-only source protection | Release 0.2.0 roadmap section 5.3 | 0.2 Phase 1-3 | query-only/checksum/mode tests | read-only sessions |
| FR-034 | Protected sandbox lifecycle | Phase 0 contract section 7 | 0.2 Phase 3 | provenance/cleanup/upgrade tests | sandbox database and manifest |
| FR-035 | Versioned CSV preview | Phase 0 contract section 8 | 0.2 Phase 4 | parser/state/drift/nonmutation tests | preview batch directory |
| FR-036 | Atomic idempotent CSV apply | Phase 0 contract section 8.6 | 0.2 Phase 5-6 | rollback/retry/trace tests | batch and command maps |
| FR-037 | Inventory-adjustment maintenance | WMS adjustment contract; Phase 0 CSV headers | 0.2 Phase 5 | service/batch/reconciliation tests | adjustment/audit/live state |
| FR-038 | Replenishment-control maintenance | Phase 0 schema/CSV contract | 0.2 Phase 6 | rule/audit/no-movement tests | control history/live controls |
| FR-039 | Standalone Windows distribution | Release 0.2.0 roadmap section 11 | 0.2 Phase 7-8 | fresh-machine/path/launch tests | portable Windows ZIP |
| FR-040 | Restricted-truth exclusion | Data policy; release 0.2.0 roadmap | 0.2 Phase 7-8 | bundle/workflow leakage scans | safe primary bundle |
| FR-041 | Release 0.1.0 compatibility | Phase 0 preservation contract | 0.2 all phases | full regression/tag/hash checks | unchanged v0.1.0 surfaces |

## 3. Nonfunctional requirement traceability

| ID | Requirement | Verification |
|---|---|---|
| NFR-001 | Local and free | clean local run after dependencies; no required network |
| NFR-002 | Deterministic | canonical same-seed/config comparisons |
| NFR-003 | Inspectable | SQLite, SQL views, source, report definitions, docs |
| NFR-004 | Testable | unit/integration/scenario/end-to-end suites |
| NFR-005 | Maintainable | dependency tests, module responsibility review, Ruff |
| NFR-006 | Safe failure | rollback, invalid input, existing output, cleanup tests |
| NFR-007 | Practical performance | recorded local and portfolio runtimes |
| NFR-008 | Privacy/safety | synthetic identity and prohibited-data scan |
| NFR-009 | Portable outputs | SQLite/CSV manifest validation |
| NFR-010 | Backward preservation | legacy tags, validators, test classification |

## 4. Architecture-correction mapping

| Legacy concept | Corrected concept | Reason | Verification |
|---|---|---|---|
| `item` with cube only | `item_master` with dimensions and calculated cube | preserve gathered measurements and broader utility | cube fixture |
| `location` with case capacity | `location_master` with pallet capacity | case capacity depends on item | schema scan/dynamic max test |
| separate current `slot_assignment` | current item assignment in `inventory_master` | live mutable location record | pick/re-slot tests |
| opening `handling_unit` | no pallet IDs in schema 3 | avoid incomplete pallet lifecycle | absence tests |
| system inventory in memory | persisted `inventory_master` | WMS must expose current recorded state | direct query tests |
| snapshots as main balance | snapshots as scheduled captures | live state and audit are primary | snapshot tests |
| simulator state processor | WMS command services/unit of work | independent WMS semantics | direct WMS tests |
| failure overlays inside generator | external scenario drivers | scalable/fair scenarios | dependency tests |
| workflow inference as ledger | immutable `inventory_transaction` | complete audit source | reconciliation tests |
| closing snapshot reconciliation | replay = live master = snapshot | stronger audit | three-way gate |

## 5. Controlled-pattern traceability

| Pattern | Hidden external protocol | Analyst-visible WMS evidence | Negative control | Acceptance |
|---|---|---|---|---|
| A: Replenishment timing gap | physical/WMS timing or availability divergence | task timing, shorts, audit rows, later correction | comparable items/areas/windows | intended cluster without WMS rule bypass |
| B: QA damage masking | physical damage + QA + generic later adjustment | QA records, generic adjustment, audit rows | nonfragile items and unmatched QA | temporal/dimensional signal without direct link |
| C: Selector false lead | work allocation to affected conditions | trips, picks, exposure, crude shorts | exposed peers and target outside affected work | high crude ranking, no hidden propensity, later attenuation |

## 6. Assignment deliverables

| Deliverable | Planning documents | Implementation evidence | Acceptance |
|---|---|---|---|
| Project brief/scope | Charter, requirements, roadmap | README/status | scope checklist |
| Data architecture | Architecture, data model, ADRs | schema 3 SQLite and SQL views | schema/WMS integrity tests |
| Synthetic generator | Synthetic spec, Phase 4A | baseline/investigation drivers | deterministic end-to-end gate |
| Analyst notebook | Analysis plan, Phase 5/6 | executed thin notebook | restart-and-run-all |
| Executive report | Reporting spec, Phase 6 | report/exhibit packet | claim-to-source audit |

## 7. Statistical claim traceability

| Claim level | Allowed evidence | Required qualifier | Prohibited leap |
|---|---|---|---|
| Descriptive | WMS counts, rates, timelines | population/period/denominator | causation from totals |
| Comparative | group differences/effect size | exposure/comparison groups | labor ranking from raw counts |
| Inferential | predefined models and intervals | assumptions/clustering | p-value as importance |
| Mechanism-consistent | time-ordered multi-file evidence | alternatives and synthetic design | real-world causal proof |
| Predictive | held-out validation if added | target/method | prediction as explanation |

## 8. Update rule

When a requirement changes:

1. update requirements;
2. update architecture/data specification;
3. update this matrix;
4. add or adapt tests;
5. record the decision;
6. update status and downstream claims.

A code change is incomplete when its requirement and verification trail are inaccurate.
