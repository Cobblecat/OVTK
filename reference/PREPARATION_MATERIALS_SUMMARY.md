# Preparation Materials Summary

## 1. Purpose

Three preparation PDFs are separate project resources intended to build the statistical judgment required for the investigation. This summary preserves their role and major requirements for implementers and future reviewers. It does not replace the original PDFs; retain those originals as separate project resources.

The three sources are:

1. `01_14_Hour_Applied_Statistics_Sprint.pdf`
2. `02_Applied_Statistical_Analysis_for_Distribution_Operations_Study_Guide.pdf`
3. `03_Professional_Operations_Analytics_Workbook.pdf`

Project-specific engineering rules derived from these sources are consolidated in `docs/14_STATISTICAL_GUARDRAILS.md`.

## 2. 14-Hour Applied Statistics Sprint

### Source purpose

A finals-style intensive schedule designed to establish formal statistical fluency and apply it to a warehouse analysis in one bounded day.

### Operating rules

The sprint emphasizes:

- coverage before depth;
- adaptive depth based on a foundation check;
- learn, apply, and document within every block;
- professional language over unnecessary formula display; and
- controlled scope ending with one completed analysis memo.

### Schedule sequence

The sprint moves through:

1. orientation and diagnostic;
2. statistical language and data structure;
3. descriptive analysis, rates, denominators, and aggregation traps;
4. a floor-comparison application checkpoint;
5. probability distributions and simulation;
6. sampling, standard error, and confidence intervals;
7. a pre/post shortage-rate application;
8. hypothesis tests, effect size, power, and p-value interpretation;
9. regression, confounding, and adjusted comparison;
10. a model-specification checkpoint;
11. statistical process control and capability;
12. inventory and supply-chain metrics;
13. a capstone warehouse analysis; and
14. a one-page executive memo and follow-up backlog.

### End-of-day competency test

The learner should be able to identify the population, sample, unit, response, and explanatory variables; distinguish descriptive from inferential claims; report operational effect sizes with uncertainty; identify bias, confounding, clustering, and time dependence; distinguish statistical from operational significance; distinguish control from specification limits; and write a recommendation without overstating causality.

### Project implication

The application and report must make those competencies inspectable. It is not enough to generate a database or model coefficient; the artifact must show the complete analytical chain and calibrated conclusion.

## 3. Applied Statistical Analysis for Distribution Operations Study Guide

### Source purpose

A compact 16-lesson bridge from operational experience to formal applied statistical analysis in logistics and distribution settings.

### Professional analytical chain

The guide frames every case as:

```text
operational observation
    -> analytical question
    -> study design and unit
    -> statistical method
    -> evidence statement
    -> limitation
    -> operational decision
```

Its example shows how a large unadjusted floor difference can shrink after work-composition adjustment, and why management should not change an engineered standard based on the raw average.

### Course structure

#### Foundations, Lessons 1-4

- Convert an operational concern into a measurable analytical question.
- Define population, sample, parameter, statistic, period, and unit of analysis.
- Distinguish statistical variable type from storage type.
- Investigate data provenance and the process producing the records.
- Choose center, spread, shape, rates, and denominators that fit the question.
- Recognize aggregation traps and work-mix effects.

#### Inference, Lessons 5-8

- Select probability models based on the data-generating process.
- Distinguish individual variation from sampling variability.
- Construct and interpret confidence intervals.
- Interpret hypothesis tests, p-values, effect size, Type I/II errors, and power without substituting significance for importance.

#### Design and modeling, Lessons 9-11

- Identify selection bias, measurement bias, confounding, clustering, and time dependence.
- Interpret regression coefficients conditionally.
- Use interactions or nonlinear forms when operationally justified.
- Distinguish association, prediction, explanation, and causal claims.
- Avoid interpreting a near-zero adjusted coefficient as proof that the underlying operational factor never matters.

#### Operations statistics, Lessons 12-14

- Preserve time order for process monitoring.
- Distinguish common- and special-cause variation.
- Distinguish control limits from specifications.
- Evaluate inventory, replenishment, service, stockout, and forecast-error measures with explicit operational definitions.

#### Professional practice, Lessons 15-16

The guide defines reproducible layers:

- raw;
- clean;
- feature;
- analysis; and
- report.

It requires preserved source data, validation before modeling, documented formulas, fixed seeds, package/version records, and traceability from every displayed result back to code.

It also separates report sections into problem, methods, results, limitations, and recommendation. Formal writing is defined by explicit logic and calibrated claims rather than inflated language.

### Final competency standard

The reviewer should be able to reproduce the result, understand the study design and data quality, inspect methods and uncertainty, identify design threats, distinguish association/prediction/causation, and connect the evidence to a measured operational recommendation.

### Project implication

The study guide directly supports the project decision to maintain immutable generated data, validated analytical layers, explicit metric definitions, crude and adjusted comparisons, and an evidence-linked executive report.

## 4. Professional Operations Analytics Workbook

### Source purpose

A practice workbook that starts after the diagnostic and repeatedly turns warehouse observations into formal analytical work.

### Core protocol

For every calculation, write a one-sentence interpretation in operational units. For every conclusion, state at least one limitation. Keep exploratory observations separate from confirmatory claims.

The workbook's central template is:

```text
Observation
    -> question
    -> population/sample/unit
    -> variables
    -> method
    -> result
    -> uncertainty
    -> limitation
    -> decision
```

### Exercises and laboratories

The workbook includes:

- foundation definitions and statistical/programming meaning of “parameter”;
- unit-of-analysis selection for selector, slot, process-change, and SKU questions;
- statistical type versus storage type;
- a reproducible operational metric dictionary;
- damage totals versus rates and loss severity;
- same-average/different-variation process comparisons;
- aggregation and work-mix analysis;
- probability-model selection;
- standard deviation versus standard error;
- confidence intervals for shortage rates;
- effect size, significance, operational thresholds, Type I/II errors, and power;
- a bias and confounding audit;
- interpretation of adjusted regression;
- prediction versus causal explanation;
- process-control interpretation;
- inventory service measures;
- forecast error; and
- a final pick-slot shortage investigation.

### Capstone and writing requirements

The capstone requires a completed analytical worksheet, one-page management memo, Python project specification, and evaluation against a professional writing rubric. It expects a decision-focused result with calculations, uncertainty, limitations, and follow-up measurement.

### Project implication

The workbook is the immediate conceptual ancestor of this project. Its pick-slot shortage investigation supports the selected grain of one eligible pick attempt, the need for explicit short-rate definitions, the exposure-adjusted selector comparison, event-sequence analysis, and the final management memo.

## 5. Rules carried into implementation

Treat the following as required analytical behavior:

1. State what one row represents before calculating.
2. Preserve a meaningful denominator for every rate.
3. Do not compare associates using raw totals alone.
4. Preserve time order and event sequence.
5. Show variation, not only averages.
6. Separate standard deviation from standard error.
7. Report effect magnitude and uncertainty.
8. Address confounding, clustering, measurement error, and time dependence.
9. Interpret regression as conditional association unless the design supports more.
10. Keep raw/generated, clean, feature, analysis, and report layers separate.
11. Make every report number reproducible.
12. Separate methods, results, limitations, and recommendations.
13. Avoid unsupported causal or disciplinary language.
14. End recommendations with a measurement plan.

## 6. Source boundary

The preparation materials teach methods and judgment. They do not prescribe the exact SQLite schema, Python package structure, model formula, event-window width, or scenario calibration thresholds. Those are project design decisions documented in the architecture, data, synthetic-generation, analysis, and decision-log files.
