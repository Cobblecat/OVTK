# 01 — Project Charter

## 1. Project name

**Operational Variance Investigation Toolkit**

## 2. Project type

A self-directed occupational portfolio project and conventional local Python application centered on:

- a deterministic miniature warehouse management system;
- synthetic warehouse operations simulation;
- controlled inventory-variance investigations;
- relational data design;
- statistical root-cause analysis; and
- management-facing communication.

## 3. Product vision

Build a free, local, inspectable warehouse data laboratory in which an experienced operations analyst can:

1. operate or observe a credible miniature WMS;
2. inspect master files, live inventory, workflow files, transaction logs, and standard reports;
3. generate normal and investigation scenarios through independent simulation protocols;
4. reconstruct recorded inventory independently;
5. test competing explanations for variance; and
6. reproduce every analytical and management-facing conclusion.

The project is not a production WMS. It is a narrow but behaviorally credible WMS simulation and investigation environment.

## 4. Business problem

A synthetic grocery distribution center is experiencing rising variance signals:

- selector shorts;
- inventory discrepancies;
- replenishment exceptions;
- QA corrections;
- post-shift adjustments; and
- reduced trust in recorded inventory.

The initial management statement is:

> “The inventory is wrong.”

That statement identifies a symptom. The project must determine whether observed variance is random noise, labor-driven error, poor master data, transaction timing, replenishment delay, damage handling, system friction, or a combination.

## 5. Professional thesis

Inventory variance is often a state-and-transaction problem, not merely a count problem.

A credible investigation requires a source system that distinguishes:

- stable item and location profiles;
- live recorded inventory by location;
- physical activity that may precede system recording;
- immutable transaction history;
- scheduled reports and snapshots;
- operational workflow records; and
- hidden scenario truth.

A recorded selector short does not establish selector error. It may arise from late replenishment, inaccurate system state, damage, blocked inventory, delayed confirmation, or another process condition.

## 6. Corrected product objective

The product must provide two independent capabilities.

### 6.1 Mini-WMS

The mini-WMS must maintain a coherent recorded warehouse state through ordinary commands and atomic transactions. It must be independently usable and queryable without any investigation scenario.

### 6.2 Simulation and investigation

The simulator and scenarios must operate the WMS from outside. They create physical actions, work assignments, timings, and ordinary WMS commands. They do not alter WMS internals or insert answers into analyst-facing data.

The final analytical conclusion must emerge from realistic operational records.

## 7. Intended audiences

### Primary

- warehouse operations analysts;
- inventory-control and quality leaders;
- distribution-center operations managers;
- WMS implementation and support professionals;
- hiring managers reviewing operations-analytics capability.

### Secondary

- software and database reviewers;
- analysts learning WMS data relationships;
- educators or hobbyists exploring synthetic warehouse investigations.

An experienced warehouse professional should be able to inspect the database and recognize coherent operational files rather than a report-shaped dataset.

## 8. Product principles

1. **Operational fidelity over analytical convenience.** Source data must behave like a credible WMS even when a simpler analytical shortcut exists.
2. **Narrow breadth, strong semantics.** Omit entire enterprise domains when unnecessary, but implement included domains correctly.
3. **Independent layers.** WMS, physical simulation, scenarios, analysis, and reporting have distinct responsibilities.
4. **Live state plus immutable audit.** Current recorded inventory and transaction history must both exist.
5. **No answer leakage.** Scenario intent and physical truth remain outside ordinary WMS data.
6. **Determinism.** Configuration, seed, and code version reproduce equivalent content.
7. **Traceability.** Every report and finding traces to source records and tested calculations.
8. **Qualified conclusions.** Association and mechanism-consistent evidence are not presented as real-world causal proof.
9. **Local operation.** No required cloud service, account, or per-run fee.
10. **Preservation.** Material corrections build on and test existing work rather than discarding history without review.

## 9. In-scope WMS domains

- run and schema metadata;
- facility and temperature zones;
- warehouse-focused item master;
- location master;
- live inventory master keyed by location;
- operators, shifts, and work assignments;
- trips and pick events;
- replenishment tasks and confirmations;
- QA and damage observations;
- inventory adjustments;
- system and transaction-friction events;
- immutable inventory transaction history;
- opening, closing, and scheduled inventory snapshots;
- standard WMS inquiry views and exports.

## 10. In-scope simulator and scenario domains

- physical inventory state;
- deterministic simulation clock;
- normal demand and work scheduling;
- baseline operational protocols;
- replenishment timing gap scenario;
- QA damage masking scenario;
- selector false lead through exposure;
- restricted ground truth;
- scenario calibration and leakage checks.

## 11. In-scope analytical capabilities

- structural and operational validation;
- transaction-ledger reconstruction;
- three-way inventory reconciliation;
- standard-report validation;
- pick, replenishment, QA, adjustment, item, location, and operator context tables;
- denominator-aware descriptive analysis;
- exposure-adjusted comparison;
- confidence intervals and effect sizes;
- competing-hypothesis evaluation;
- sensitivity checks;
- evidence ranking;
- corrective-action and monitoring design.

## 12. Explicit exclusions

The initial product will not include:

- real employer data, employee names, credentials, screenshots, or proprietary documentation;
- receiving/ASN integration;
- full shipping or transportation execution;
- route accounting;
- labor-management scoring;
- production RF/voice-device integration;
- multi-user transactional concurrency;
- user accounts and enterprise authorization;
- ERP, TMS, WCS, PLC, carrier, or financial-system integration;
- cloud hosting;
- production cybersecurity certification;
- a complete enterprise WMS;
- real associate performance evaluation;
- loss-prevention casework;
- automated strategic recommendations outside the investigation scope.

These exclusions limit breadth. They do not permit unrealistic behavior in the included WMS domains.

## 13. Initial model simplifications

The corrected initial WMS intentionally uses:

- whole-case inventory quantities;
- one inventory record per warehouse location;
- one item and one code date per occupied location;
- no pallet IDs or handling-unit lifecycle;
- no mixed-item or mixed-code-date locations;
- no receiving timestamp without a receiving workflow;
- no generic inventory-status field without defined status transitions;
- one facility per generated database;
- one finalized run per generated database.

A later scope decision may expand these constraints.

## 14. Central analytical test

The selector false lead remains the central demonstration:

- one selector appears unfavorable in crude short totals;
- that selector has disproportionate exposure to an affected area and time window;
- exposed peers show compatible patterns;
- adjustment for operational exposure materially reduces the apparent selector association; and
- replenishment and QA evidence provide stronger process explanations.

The WMS must not contain any selector-specific hidden error parameter or scenario flag.

## 15. Success criteria

The project succeeds when a reviewer can:

1. inspect `item_master`, `location_master`, `inventory_master`, and transaction history directly;
2. determine what the WMS currently records at any location;
3. trace every live balance change to an immutable transaction;
4. run standard reports that agree with ad hoc SQL against the same files;
5. generate baseline and investigation runs through the same WMS services;
6. verify that scenario modules cannot write WMS tables;
7. reconstruct closing inventory from opening state and audit history;
8. reconcile reconstruction to live inventory and snapshots;
9. identify the three investigation signatures without ground truth;
10. reproduce statistical and report outputs from preserved code and artifacts; and
11. run the project locally without paid services.

## 16. Definition of complete product

The complete product is done when:

- schema `3.0.0` WMS generation is stable and documented;
- baseline and investigation scenarios use independent drivers;
- live inventory and transaction audit are coherent;
- standard reports are tested and exportable;
- reconstruction performs three-way reconciliation;
- statistical analysis tests all competing hypotheses;
- the selector false lead attenuates under the predefined analysis;
- the notebook and executive report are reproducible;
- hidden truth remains absent from analyst-facing outputs;
- a clean-environment reproduction succeeds; and
- the release includes an explicit open-source license.
