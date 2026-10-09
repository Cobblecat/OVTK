# Operational Variance Investigation Toolkit

## Recovered Project Package

**Author:** Andrew Nelson  
**Project type:** Self-directed occupational portfolio project  
**Data policy:** Synthetic data only

This package restores the authoritative assignment brief and the later applied-statistics preparation materials developed for the project. The objective is to build a believable grocery distribution center data environment, introduce controlled operational failure patterns, and use transaction evidence to distinguish symptoms from root causes.

The project is deliberately written like a professor-issued assignment. The brief defines the scenario, boundaries, required operational domains, deliverables, and evaluation standards without prescribing the database schema or analytical solution. Designing and defending those choices is part of the work.

## Package Contents

### 01_Assignment

- **Operational_Variance_Assignment_Brief_v2.pdf** - Primary reading copy of the assignment.
- **Operational_Variance_Assignment_Brief_v2.md** - Editable source of the same authoritative brief.

### 02_Preparation

- **01_14_Hour_Applied_Statistics_Sprint.pdf** - Time-boxed preparation schedule.
- **02_Applied_Statistical_Analysis_for_Distribution_Operations_Study_Guide.pdf** - Revised reference guide for the statistical concepts needed to support defensible operational findings.
- **03_Professional_Operations_Analytics_Workbook.pdf** - Revised practice workbook with distribution-focused exercises, including confounding, exposure, adjusted comparisons, and the distinction between prediction and causal explanation.

## Recommended Start Sequence

1. Read the assignment brief once from beginning to end.
2. Define the investigative claim and the strongest competing hypotheses before designing tables.
3. Design the relational architecture and integrity rules.
4. Generate normal operations before injecting the three controlled failure patterns.
5. Preserve optional ground-truth labels separately from the analyst-facing data.
6. Validate, reconstruct, segment, and test the evidence before drafting conclusions.
7. Produce the management-facing report only after the technical findings survive competing-hypothesis review.

Use the preparation material just in time. The goal is **learn, apply, document** - not to delay the project until every statistical topic has been studied in isolation.

## Central Analytical Test

The most important scenario is the selector false lead. Raw totals should initially make one selector appear responsible for elevated shorts. A defensible analysis should then test whether the apparent effect weakens after accounting for assignment exposure, operating area, time window, item velocity, replenishment delay, QA activity, and transaction timing.

The project succeeds when it can explain the operational mechanism behind the variance, not merely count discrepancies or produce a dashboard.
