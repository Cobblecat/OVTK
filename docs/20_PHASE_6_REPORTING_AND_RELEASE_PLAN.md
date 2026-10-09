# 20 — Phase 6 Reporting, Portfolio, and Open-Source Release Plan

## 1. Status and prerequisite

**Status:** Complete and accepted for release 0.1.0
**Prerequisite:** Phase 5 accepted and analyst findings frozen

## 2. Purpose

Transform the corrected mini-WMS and verified statistical investigation into a professional, reproducible portfolio product.

## 3. Deliverable

> A reviewer can clone or unzip the project, create the synthetic WMS datasets, inspect operational files and standard reports, reproduce reconstruction and statistical findings, run the notebook, and audit the executive report without proprietary data or paid services.

## 4. Phase 6 slices

### Slice 0 — Release-content inventory

Confirm accepted artifacts and versions:

- schema 3 baseline/investigation databases;
- restricted truth location and handling policy;
- standard WMS reports;
- reconstruction outputs;
- statistical outputs;
- frozen analysis configuration;
- current tests and runtime.

Define which generated artifacts are included, regenerated, or omitted from source control.

### Slice 1 — Notebook narrative

Create a thin notebook that:

1. identifies the synthetic WMS and run;
2. validates source/reconstruction/analysis manifests;
3. introduces the business complaint;
4. shows WMS master and live inventory context;
5. explains three-way reconciliation;
6. presents crude variance patterns;
7. evaluates replenishment evidence;
8. evaluates QA-adjustment evidence;
9. compares crude and adjusted selector results;
10. summarizes sensitivity checks;
11. ranks hypotheses;
12. states limitations and recommended actions.

The notebook calls tested package functions and uses completed artifacts. It does not redefine calculations.

### Slice 2 — Figures and exhibit tables

Create traceable figures/tables with stable source references.

Candidate exhibits:

- architecture/data-flow diagram;
- live inventory and reconciliation summary;
- short rate by zone/aisle/time;
- replenishment delay versus short evidence;
- QA-to-adjustment timing;
- crude selector result with exposure;
- adjusted selector attenuation;
- sensitivity summary;
- hypothesis evidence matrix;
- corrective-action measurement plan.

Every exhibit includes title, population, denominator, source, and appropriate uncertainty.

### Slice 3 — Executive report

Create a professional report containing:

- executive summary;
- problem statement;
- simulated WMS environment;
- data and methods;
- findings;
- alternative explanations;
- operational impact;
- corrective recommendations;
- monitoring plan;
- limitations;
- technical appendix and provenance.

The report should be understandable without reading code but must remain auditable.

### Slice 4 — WMS user and SQL exploration documentation

Provide:

- quick start;
- command reference;
- database/table overview;
- item/location/inventory master explanation;
- standard report guide;
- example SQL queries;
- transaction-tracing example;
- scenario generation guide;
- reconstruction guide;
- analyst workflow guide;
- ground-truth handling warning.

### Slice 5 — Open-source packaging

Add:

- explicit license, recommended MIT unless a different license is approved;
- contribution notes if useful;
- clean `.gitignore`;
- release manifest/checksums;
- versioned changelog/release notes;
- reproducible environment instructions;
- source archive or Git release;
- optional small example dataset.

Evaluate public Python compatibility floor. Do not widen support without running the full suite.

### Slice 6 — Clean-environment reproduction

From a clean clone or extracted source archive:

1. install with documented commands;
2. generate baseline and investigation WMS databases;
3. run standard reports;
4. validate and reconstruct;
5. run statistical analysis;
6. execute notebook top to bottom;
7. build executive report;
8. compare expected manifests/checksums where appropriate;
9. run full tests and quality checks.

Record exact environment and runtimes.

## 5. Standard report publication

The release should expose reports in two ways:

- direct SQL views/query documentation; and
- CLI CSV export.

Reports remain factual source-system outputs, separate from analytical exhibits.

## 6. Ground-truth release policy

**Selected:** Publish restricted truth only as a separately named optional archive with its own
spoiler warning, manifest, and SHA-256 checksums.

Considered policies:

1. Include restricted truth in a clearly separate developer/reveal directory.
2. Publish truth as a separate optional archive.
3. Provide a command that reveals truth only when the user explicitly supplies the restricted artifact.

Never package ground truth inside the analyst WMS database or ordinary report directory.

## 7. Executive recommendation standard

Each recommendation includes:

- process point;
- evidence;
- owner role;
- implementation/observation window;
- leading and lagging metrics;
- success threshold;
- escalation condition;
- known limitation.

Recommendations must not default to labor discipline when process evidence is stronger.

## 8. Optional XLSX exhibit packet

**Decision:** Omitted from release 0.1.0. CSV, SQLite, notebook, figures, and the executive PDF are
sufficient, and no spreadsheet dependency is added.

Add only if it improves management review.

If added:

- calculations remain in Python;
- workbook cells are presentation outputs;
- source manifest and refresh instructions are included;
- no manually keyed report results.

## 9. Acceptance criteria

Phase 6 passes when:

1. notebook runs from a clean kernel;
2. all figures/tables regenerate;
3. every executive number traces to an artifact;
4. standard reports match WMS source queries;
5. synthetic labeling is prominent;
6. no hidden truth leaks;
7. limitations and claim boundaries are explicit;
8. installation and full reproduction succeed;
9. license and release metadata are complete;
10. full tests, Ruff, formatting, and diff checks pass;
11. release archive excludes environment/cache clutter;
12. another reviewer can understand and inspect the system without private context.

## 10. Explicit exclusions

- production deployment;
- cloud service requirement;
- real company integration;
- unsupported claims of causation;
- complex GUI before the source/analysis release is stable;
- pallet tracking or new operational domains added solely for presentation.

## 11. Post-release options

After release, consider:

- local browser explorer;
- packaged executable;
- new scenarios;
- pallet lifecycle;
- receiving/putaway;
- migration reconciliation case;
- control-chart mode;
- teaching guides.
