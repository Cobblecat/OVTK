# 08 — Reporting and Portfolio Specification

## 1. Reporting layers

The project has three distinct reporting classes.

### WMS operational reports

Standard source-system inquiries over current WMS files.

### Analytical exhibits

Derived tables and figures supporting the investigation.

### Executive report

Management-facing interpretation, limitations, recommendations, and measurement plan.

These layers must not be conflated.

## 2. WMS operational reports

Required standard reports are defined in `docs/22_STANDARD_WMS_REPORTS_CONTRACT.md`.

They must:

- query ordinary WMS tables/views;
- be available through SQL and a tested report service;
- support console and CSV rendering where practical;
- state report name, run ID, as-of time, and parameters;
- reconcile to source totals;
- remain scenario-blind; and
- contain no analytical conclusions.

Examples:

- inventory by location;
- inventory by item;
- replenishment needs;
- open replenishment tasks;
- transaction inquiry;
- adjustment history;
- QA activity;
- code-date inventory;
- empty locations.

## 3. Scheduled snapshots

A snapshot is an immutable report capture of live WMS state.

Required captures:

- opening system inventory;
- closing system inventory;
- optional shift-end snapshots; and
- optional cycle-count/verified snapshots.

Snapshots do not replace live `inventory_master` or immutable `inventory_transaction` history.

## 4. Analytical output directory

Recommended layout:

```text
artifacts/analysis/<run_id>/
    analysis_manifest.json
    inventory_event_ledger.csv
    inventory_reconciliation.csv
    pick_context.csv
    replenishment_context.csv
    qa_adjustment_context.csv
    selector_exposure.csv
    descriptive_metrics.csv
    crude_adjusted_selector.csv
    sensitivity_results.csv
    hypothesis_evidence.csv
```

Phase 4A produces the factual reconstruction and context outputs. Phase 5 adds statistical outputs.

## 5. Manifest requirements

Every derived run records:

- source database path and checksum;
- run ID;
- schema version;
- generator version;
- source configuration hash;
- analysis/reconstruction version;
- generated-at timestamp;
- row counts;
- validation status;
- allowed reproducibility exclusions; and
- output checksums where practical.

Ground-truth path and scenario targets are omitted from ordinary analysis manifests.

## 6. Notebook standard

The notebook is thin and narrative.

It must:

- load validated derived outputs;
- call tested package functions;
- avoid manual corrections;
- show source and run identity;
- explain population, period, unit, and denominator;
- separate methods, results, limitations, and recommendations;
- execute from top to bottom in a clean environment.

## 7. Required analytical exhibits

Candidate final exhibits:

- WMS source and reconciliation summary;
- variance over time;
- short rates by area and item velocity;
- shorts relative to replenishment timing;
- QA-to-adjustment sequence;
- raw selector counts with exposure denominators;
- crude versus adjusted selector association;
- sensitivity summary;
- hypothesis evidence matrix;
- corrective-action measurement plan.

## 8. Executive report structure

1. Executive summary
2. Business problem
3. Data and WMS environment
4. Methods
5. Findings
6. Competing explanations
7. Operational impact
8. Recommendations
9. Monitoring plan
10. Limitations
11. Technical appendix and provenance

## 9. Claim requirements

Every material claim must state or link to:

- source metric;
- denominator;
- estimate;
- interval or uncertainty where applicable;
- comparison group;
- operational interpretation;
- limitation; and
- source artifact/table.

## 10. Recommendation requirements

A recommendation includes:

- process point;
- evidence;
- responsible functional role;
- implementation or observation window;
- leading measure;
- lagging measure;
- success threshold;
- escalation/rollback condition; and
- why the action is preferable to unsupported labor blame.

## 11. Portfolio release

The public release should include:

- source code;
- explicit open-source license;
- clean README;
- architecture and data dictionary;
- baseline and investigation generation instructions;
- SQL exploration guide;
- standard report guide;
- reconstruction and analysis instructions;
- executed example notebook;
- executive report;
- synthetic-data labeling;
- checksums/manifests; and
- versioned release notes.

Generated datasets may be provided as small examples, but the canonical workflow must regenerate them.

## 12. Prohibited reporting behavior

Do not:

- edit report numbers manually;
- present snapshots as live state;
- hide denominators;
- rank associates using raw totals;
- expose ground truth;
- let report logic diverge from source query logic;
- claim real-world causal proof; or
- imply the schema reproduces a specific employer’s proprietary WMS.
