# 06 — Investigation and Statistical Plan

## 1. Purpose

This document defines the analytical reasoning chain after WMS operational fidelity is restored.

The analyst receives:

- the analyst-facing schema `3.0.0` WMS database;
- standard WMS reports;
- read-only reconstruction outputs; and
- no restricted ground truth.

## 2. Investigative sequence

```text
validate WMS source
    -> inspect master and live inventory files
    -> review standard reports
    -> reconstruct inventory transactions
    -> reconcile to live inventory and snapshots
    -> build factual context tables
    -> describe variance and exposure
    -> test competing hypotheses
    -> run adjusted and sensitivity analyses
    -> rank evidence
    -> communicate bounded findings
```

## 3. Source layers

### WMS operational source

- item and location masters;
- live inventory master;
- immutable inventory transactions;
- workflow files;
- snapshots;
- standard views.

### Derived factual layer

- transaction ledger;
- three-way reconciliation;
- pick context;
- replenishment context;
- QA-adjustment candidates;
- selector exposure.

### Statistical layer

- denominators and rates;
- intervals;
- crude comparisons;
- adjusted models;
- sensitivity checks;
- hypothesis evidence.

### Presentation layer

- notebook;
- tables and charts;
- executive report.

## 4. Population and units

The plan must explicitly define:

- simulation run and operating period;
- eligible pick attempts;
- pick-line and case denominators;
- selector, trip, item/location, and time-window units;
- exclusion rules;
- baseline versus investigation comparison.

Primary pick outcome:

```text
short_indicator = 1 when short_qty_cases > 0
```

Secondary outcomes:

- short cases;
- short cases per requested case;
- short lines per eligible pick line.

## 5. WMS integrity before statistics

Statistical work stops if:

- WMS validation has hard failures;
- inventory transaction replay does not match live inventory;
- live inventory does not match closing snapshot;
- report totals disagree with source queries;
- hidden-truth leakage exists; or
- source checksum changes during analysis.

Operational anomalies designed into the scenario are not structural validation failures.

## 6. Required hypotheses

At minimum:

1. Selector-specific accuracy problem.
2. Replenishment timing/availability problem.
3. High-velocity item concentration.
4. Location/zone/time concentration.
5. QA/damage masking through generic adjustments.
6. Recorded inventory eventually correct but inaccurate or unavailable at point of pick.

Each hypothesis receives:

- expected evidence;
- contradictory evidence;
- required denominators;
- primary metrics;
- uncertainty treatment;
- limitations; and
- disposition.

## 7. Descriptive evidence

Required summaries include:

- live and opening/closing inventory totals;
- transaction counts and types;
- short lines and cases by item, location, zone, aisle, day, shift, and selector;
- requested-case denominators;
- replenishment delay distributions;
- QA and adjustment timing;
- code-date and item-handling characteristics where relevant;
- raw selector rankings with exposure displayed beside them.

## 8. Replenishment analysis

Evaluate:

- task creation-to-start time;
- start-to-confirm time;
- creation-to-confirm time;
- picks and shorts while tasks are open;
- system quantity before pick;
- source and destination inventory before/after confirmation;
- high-velocity interaction;
- affected versus comparable item/location/time strata.

## 9. QA and adjustment analysis

Use candidate matching based on ordinary analyst evidence:

- same item;
- same location or documented related location;
- QA before adjustment;
- bounded time window;
- compatible quantity direction;
- generic versus specific reason.

Candidate matches are not declared causal without qualification.

## 10. Selector exposure analysis

For every selector report:

- trips;
- pick lines;
- requested cases;
- zone and aisle mix;
- high-velocity exposure;
- replenishment-adjacent exposure;
- operating-day and shift exposure;
- crude short counts and rates.

Do not publish a single risk score.

## 11. Primary adjusted analysis

The primary question is:

> After accounting for predefined measured operating conditions, how much of the crude target-selector association remains?

The Phase 5 plan selects the exact model after inspecting event counts and sparsity.

Candidate primary model:

- binary short outcome;
- target-selector contrast;
- item velocity;
- zone/aisle or affected-area exposure;
- time/shift controls;
- requested quantity;
- replenishment proximity/status;
- QA/system-event context;
- appropriate cluster-robust uncertainty.

Report interpretable predicted probabilities or marginal differences, not only log-odds.

## 12. Attenuation criterion

Before fitting the final model, Phase 5 must define a material attenuation rule using both:

- reduction in the target-selector point estimate; and
- movement of uncertainty toward a small or operationally trivial residual effect.

The criterion must not be chosen after seeing the most favorable model.

## 13. Sensitivity checks

At minimum:

- event versus case outcome;
- pick-line versus requested-case exposure;
- narrower and wider replenishment windows;
- alternative time controls;
- exclusion of one affected item/location group at a time;
- target selector outside affected conditions;
- exposed peers;
- alternate cluster strategy;
- high-leverage trip/item review;
- baseline-versus-investigation comparison.

## 14. Ground-truth use

Ground truth is unavailable to ordinary analysis.

After all analyst-facing findings are frozen, a developer-only validation may compare conclusions with restricted truth. That comparison cannot change the main model specification or reported findings without clearly restarting and documenting the analysis.

## 15. Claim levels

Allowed levels:

- descriptive;
- comparative;
- inferential under stated assumptions;
- mechanism-consistent.

Do not claim real-world causal proof from the synthetic observational investigation.

## 16. Deliverables

Phase 5 produces:

- documented analysis configuration;
- validated analytical tables;
- descriptive evidence tables;
- effect sizes and intervals;
- crude and adjusted selector comparison;
- sensitivity results;
- hypothesis evidence table; and
- machine-readable analysis manifest.

Phase 6 converts these into notebook and executive communication.
