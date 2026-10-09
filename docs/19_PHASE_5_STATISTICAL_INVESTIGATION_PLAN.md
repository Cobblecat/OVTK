# 19 — Phase 5 Statistical Investigation and Hypothesis Testing Plan

## 1. Status and prerequisite

**Status:** Complete and accepted
**Prerequisite:** Phase 4A complete with schema `3.0.0` baseline and investigation artifacts
**Successor:** Phase 6 reporting and release

The frozen contract is `docs/26_PHASE_5_ANALYSIS_CONTRACT.md`; definitive
outputs are under
`artifacts/analysis/RUN-D4876095A8166078/statistics_accepted`.

Do not begin this phase using legacy schema `2.0.0` artifacts as the primary analysis source.

## 2. Purpose

Use only analyst-facing WMS files, standard reports, and corrected reconstruction outputs to evaluate competing explanations for operational variance.

The phase must demonstrate why raw labor-level totals can be misleading and whether process timing, item velocity, location, QA, and exposure provide stronger explanations.

## 3. Deliverable

> A deterministic, tested statistical analysis package producing denominator-aware descriptive evidence, effect sizes and intervals, crude and adjusted selector comparisons, sensitivity results, and a ranked hypothesis evidence table.

## 4. Fixed analytical boundaries

- The ordinary workflow cannot read restricted ground truth.
- WMS source databases are read-only.
- Raw counts are never standalone labor-performance evidence.
- The analysis is explanatory/diagnostic, not a risk score or disciplinary system.
- Model specification is documented before final coefficients are accepted.
- Operational magnitude matters alongside statistical uncertainty.
- Causal language remains bounded.
- Notebook storytelling and final executive report are Phase 6.

## 5. Phase 5 slices

### Slice 0 — Data adequacy and analysis contract

Inspect corrected artifacts before choosing final models.

Required review:

- eligible pick observations;
- number of short events and short cases;
- selector counts and exposure distribution;
- target versus peer exposure;
- item/location/time strata;
- sparse categories;
- trips and repeated observations;
- replenishment timing distributions;
- QA-adjustment candidate counts;
- baseline versus investigation scale;
- runtime and memory needs.

Create:

- `docs/24_PHASE_5_ANALYSIS_CONTRACT.md` or equivalent frozen configuration;
- explicit population, period, unit, outcomes, denominators, exclusions, covariates, cluster strategy, sensitivity set, and attenuation criterion.

A review decision is required before progression if the corrected dataset does not support a stable transparent model at current scale.

### Slice 1 — Analytical dependencies and load layer

Add only directly used dependencies, likely:

- Pandas;
- SciPy where needed;
- Statsmodels for transparent statistical models;
- Matplotlib may remain deferred to Phase 6 unless diagnostic plots are required.

Implement typed loaders for:

- schema 3 WMS database/report outputs;
- reconstruction/context CSVs;
- analysis configuration.

Validate:

- run identity consistency;
- source checksum/manifest consistency;
- required columns and types;
- no hidden-truth fields;
- no duplicate analytical grain.

### Slice 2 — Metric definitions and descriptive evidence

Implement tested metrics:

- eligible pick lines;
- requested cases;
- picked cases;
- short lines;
- short cases;
- short-line rate;
- short cases per requested case;
- replenishment-adjacent exposure;
- affected-area/time exposure derived from ordinary evidence;
- QA-event and generic-adjustment rates;
- adjustment quantity by reason;
- live/reconstructed/snapshot reconciliation summary.

Every metric defines numerator, denominator, grain, and exclusions.

Produce descriptive tables by:

- zone and aisle;
- item and velocity class;
- operating date and shift;
- selector;
- replenishment status/timing;
- QA/system-event proximity.

### Slice 3 — Effect sizes and uncertainty

Implement:

- absolute differences;
- rate ratios or odds ratios where interpretable;
- confidence intervals under documented assumptions;
- cluster-aware or robust uncertainty where justified;
- operational translations.

Add hand-calculated fixtures.

Do not present p-values without effect size and interval.

### Slice 4 — Replenishment timing hypothesis

Evaluate Pattern A without truth labels.

Required evidence:

- short rates by replenishment timing window;
- open-task and confirmation-delay exposure;
- high-velocity interaction;
- affected versus comparable locations/items;
- balance and audit context around key events;
- later confirmation/correction evidence;
- sensitivity to event-window width.

Output a hypothesis evidence record with supporting and contradicting evidence.

### Slice 5 — QA damage masking hypothesis

Evaluate Pattern B using ordinary QA, adjustment, item, location, and audit records.

Required evidence:

- QA-before-adjustment candidate frequency;
- generic negative adjustment concentration;
- fragility/category comparison;
- timing and quantity compatibility;
- negative controls;
- sensitivity to match window and location rule.

Do not present candidate matches as proven causal links.

### Slice 6 — Crude selector analysis

Produce transparent crude results:

- short counts;
- short-line rates;
- short cases per requested case;
- confidence intervals;
- trips, requested cases, item/zone/time mix;
- target selector ranking;
- exposed-peer comparison;
- target outside affected conditions.

The table must make exposure visible beside crude outcome.

### Slice 7 — Adjusted selector model

Fit the predefined primary model.

Recommended response:

```text
short_indicator at eligible pick-event grain
```

Candidate covariates:

- target selector indicator or selector contrasts;
- affected-area/replenishment exposure;
- item velocity;
- requested quantity;
- zone/aisle controls;
- shift/day/time controls;
- replenishment proximity/status;
- QA/system context;
- predefined interactions only when operationally justified.

Uncertainty:

- use cluster-robust or another documented method appropriate to repeated trip/selector/item-location observations;
- avoid a model too complex for event count;
- detect separation and unstable coefficients;
- use transparent fallback if the preferred model is not estimable.

Report:

- crude target estimate;
- adjusted target estimate;
- absolute and proportional attenuation;
- interpretable predicted probabilities or marginal effects;
- interval;
- operational meaning;
- residual limitations.

### Slice 8 — Sensitivity and alternative specifications

Required checks:

- short indicator versus short-case outcome;
- pick-line versus requested-case exposure;
- event-window changes;
- alternate reasonable time controls;
- one affected item/location group removed at a time;
- target selector outside affected work;
- exposed peer comparison;
- alternate cluster strategy;
- high-leverage trip/item review;
- baseline-versus-investigation contrast.

Sensitivity results clarify robustness; they are not a search for the most favorable conclusion.

### Slice 9 — Hypothesis evidence table

Produce one or more rows per hypothesis with:

- hypothesis ID;
- evidence item;
- source metric/table;
- estimate;
- interval;
- direction;
- operational interpretation;
- supporting/contradicting status;
- limitation;
- source artifact reference;
- disposition.

Required hypotheses:

1. generalized selector accuracy problem;
2. replenishment timing/availability;
3. high-velocity concentration;
4. location/zone/time concentration;
5. QA damage masking;
6. recorded inventory eventually correct but inaccurate/unavailable at point of pick.

Rank evidence, not people.

### Slice 10 — Freeze analyst findings and optional truth evaluation

Before ground-truth review:

- freeze analysis configuration;
- save outputs/checksums;
- record conclusion and limitations;
- confirm no truth path was loaded.

Then a separate developer-only evaluation may compare detected mechanisms with restricted truth.

Truth evaluation must not silently rewrite the primary analysis. Any substantive reanalysis is documented as a new analysis version.

## 6. Output contract

Recommended directory:

```text
artifacts/analysis/<run_id>/statistics/
    analysis_config.json
    analysis_manifest.json
    descriptive_metrics.csv
    replenishment_evidence.csv
    qa_adjustment_evidence.csv
    selector_crude.csv
    selector_adjusted.csv
    sensitivity_results.csv
    hypothesis_evidence.csv
    model_diagnostics.json
```

## 7. Application workflow and CLI

Recommended command:

```text
operational-variance-toolkit analyze \
  --database <schema3.sqlite3> \
  --reconstruction <analysis-dir> \
  --config <analysis.toml> \
  --output <statistics-dir>
```

The workflow must:

- validate source/reconstruction identity;
- refuse unsafe overwrite;
- never accept ground truth;
- produce deterministic outputs except documented timestamps;
- clean partial output on failure;
- print factual completion and validation summaries.

## 8. Testing

At minimum:

- grain uniqueness;
- numerator/denominator fixtures;
- group-rate fixtures;
- interval calculations;
- cluster/robust configuration;
- crude estimate fixture;
- adjusted design-matrix fixture;
- attenuation calculation;
- sparse/separation handling;
- sensitivity configuration;
- required hypothesis rows;
- source provenance;
- same-input reproducibility;
- no source mutation;
- no ground-truth import/path;
- continued Phase 4A tests.

## 9. Acceptance criteria

Phase 5 passes when:

1. source and reconstruction validation pass;
2. data adequacy is documented;
3. all metrics have explicit denominators;
4. all six hypotheses are evaluated;
5. crude selector result is visible;
6. target exposure imbalance is quantified;
7. primary adjusted model is predefined and estimable or transparently replaced;
8. target selector association materially attenuates under the approved criterion;
9. replenishment and QA mechanism evidence is supported through ordinary records;
10. sensitivity checks do not reveal an undisclosed contradictory result;
11. intervals, diagnostics, and limitations are present;
12. hypothesis evidence table is complete;
13. truth was not used in ordinary analysis;
14. outputs are reproducible;
15. tests/Ruff/diff checks pass.

## 10. Decisions and blockers requiring review

Affected analysis remains blocked pending review and a decision when:

- event counts are inadequate for the planned model;
- attenuation criterion requires a material product decision;
- model alternatives lead to materially different conclusions;
- target false lead does not appear in crude results after remediation;
- WMS/source integrity issues emerge;
- a recommended analysis would become an associate ranking tool; or
- ground-truth knowledge appears necessary to select features.

## 11. Explicit exclusions

- final notebook narrative;
- final charts/exhibit styling;
- executive recommendations;
- public release packaging;
- WMS source changes driven by desired statistical results;
- hidden-truth feature engineering.
