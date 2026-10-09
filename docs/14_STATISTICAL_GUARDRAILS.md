# 14 - Statistical Guardrails

> **Active governance notice:** These safeguards remain binding for Phase 5 and
> later analytical and reporting work. Schema-3 WMS remediation does not archive,
> supersede, or weaken them.

## 1. Purpose and source

These guardrails translate the preparation materials into project rules. They are not a substitute for the full study guide or workbook. Their purpose is to prevent implementation and reporting from drifting into familiar analytical mistakes while the generator and investigation are developed.

The required reasoning chain is:

```text
operational observation
    -> analytical question
    -> population, period, and unit
    -> data-generating process
    -> metric and eligibility definition
    -> descriptive evidence
    -> uncertainty or adjusted method when justified
    -> limitation
    -> operational decision and measurement plan
```

## 2. Define the study before calculating

Every primary analysis must state:

- the operational concern;
- the measurable analytical question;
- the target population;
- whether the observed synthetic run is treated as a population or a sample for the claim;
- the study period;
- the unit of analysis;
- the response variable;
- explanatory variables;
- eligibility and exclusion rules; and
- what the design cannot establish.

One row per pick supports pick-level analysis. It does not automatically make selectors, items, locations, trips, or days independent.

## 3. Model the data-generating process

The database is not a neutral mirror of operations. For each metric, identify:

1. the physical condition or process;
2. the event that creates a record;
3. any reporting or confirmation delay;
4. coding choices;
5. missing or generic records;
6. system-state effects; and
7. the difference between what happened and what is measurable.

For this project, a recorded short may reflect depleted usable inventory, delayed replenishment confirmation, a hold, system/equipment friction, transaction timing, selector action, or combinations of these. The short record alone cannot identify the cause.

## 4. Use an explicit metric dictionary

No primary metric should exist only as a column expression in code. Document:

- metric name;
- numerator;
- denominator;
- unit;
- eligibility rule;
- exclusions;
- time window;
- source tables and fields;
- treatment of duplicates or corrections;
- missing-data behavior; and
- known measurement limitation.

### Initial recorded-short metrics

At least distinguish:

- **short-event rate:** eligible pick attempts with `short_qty_cases > 0` divided by eligible pick attempts;
- **short-case rate:** total short cases divided by total requested cases; and
- **short cases per 1,000 picks:** total short cases divided by eligible pick attempts, multiplied by 1,000.

These metrics answer different questions and must not be substituted silently.

## 5. Preserve denominators and work mix

Raw totals are useful for workload and materiality, but weak for performance comparison.

Every operator, area, item, or time comparison must show the relevant exposure. Depending on the question, include:

- eligible picks;
- requested cases;
- trips;
- hours or shift assignments;
- affected-area picks;
- targeted-item picks;
- high-velocity-item share;
- continuation or work-type mix if later modeled;
- replenishment-event exposure; and
- QA/system-event exposure.

Do not publish “highest shorts” as an associate finding without denominators and assignment context.

## 6. Describe variation, not only averages

Use summaries appropriate to the distribution and question:

- mean and standard deviation when meaningful;
- median and interquartile range for skewed duration or quantity data;
- percentiles for tail risk;
- frequency distributions;
- time-ordered charts;
- rates with denominators; and
- loss or case magnitude alongside event frequency.

Equal averages do not imply equivalent processes. A process may have the same center and very different spread, tail risk, stability, or work composition.

## 7. Preserve time order

Inventory and process evidence is sequential. Do not rely solely on pooled tables.

Required time-aware views include:

- depletion and pick activity over time;
- replenishment need, task creation, start, confirmation, and usability;
- shorts relative to confirmation;
- QA events relative to adjustments;
- system events relative to affected picks; and
- closing corrections relative to earlier point-of-pick inaccuracy.

Use event-time windows that are defined before reviewing the final result where practical. Sensitivity checks may vary the windows transparently.

## 8. Separate standard deviation and standard error

- **Standard deviation** describes variation among observed units.
- **Standard error** describes estimated sampling variability of a statistic under stated assumptions.

Do not use standard error to portray ordinary operational variation as small. Do not use standard deviation as an interval for an estimated group difference.

## 9. Report effect size and uncertainty

Primary comparisons should include:

- absolute difference, preferably in percentage points or events/cases per meaningful exposure;
- relative comparison when interpretable;
- confidence interval under stated assumptions; and
- operational translation.

A p-value alone is never a finding. A small p-value does not imply a meaningful effect, a good model, an unbiased design, or a causal mechanism. A wide interval may show that the direction or size remains operationally uncertain even when a point estimate looks large.

## 10. Interpret confidence intervals carefully

For a reported interval:

- name the estimated quantity;
- state the method or model used;
- state independence or cluster assumptions;
- avoid saying there is a post-data probability that the fixed parameter lies in the interval; and
- discuss whether the range includes operationally trivial and important effects.

When the synthetic dataset is treated as the complete finite run, interval estimates may instead reflect a superpopulation/model perspective. State that perspective rather than presenting uncertainty as automatic.

## 11. Control p-value language

Allowed phrasing:

- “The estimate was imprecise.”
- “The interval excluded the null value under the model assumptions.”
- “The evidence against the null model was weak/moderate/strong under the stated analysis.”
- “The effect was statistically distinguishable but operationally small.”

Avoid:

- “proved”;
- “no effect” solely because `p > 0.05`;
- “important” solely because `p < 0.05`;
- “95% chance the null is false”; and
- selecting only favorable tests from many unreported comparisons.

Exploratory comparisons should be labeled exploratory. If many formal comparisons are made, address multiplicity or narrow the confirmatory set.

## 12. Audit bias, confounding, clustering, and time dependence

Before model interpretation, complete this audit:

### Selection and assignment

- Were selectors assigned randomly? No.
- Could affected-area assignment depend on time, role, experience, availability, or workload?
- Does the target selector have disproportionate exposure?

### Measurement

- Are shorts, QA events, adjustments, confirmations, and system events recorded consistently?
- Are generic adjustment reasons hiding mechanism detail?
- Can transaction posting lag alter event order?

### Confounding

- Zone and location.
- Item and velocity class.
- Time of day and operating day.
- Shift and work assignment.
- Replenishment status/delay.
- QA/system-event proximity.
- Requested quantity and workload.

### Clustering

- Multiple picks within one trip.
- Repeated picks by one selector.
- Repeated observations for one item/location.
- Shared conditions within a shift or day.

### Time

- Trends, startup/end-of-shift effects, depletion cycles, and event windows.

The model and interval method must reflect the most consequential structure or state the limitation when it cannot.

## 13. Use regression as an adjusted association tool

The primary model is intended to answer:

> After accounting for predefined measured operating conditions, how much of the crude selector association remains?

The model is not intended to assign fault.

### Minimum model discipline

- Define the response and link/model family.
- Predefine the target selector contrast and core operational covariates.
- Use meaningful reference categories.
- Check sparse cells and separation.
- Inspect influential or unusual patterns.
- Evaluate interactions only when operationally justified.
- Avoid high-dimensional “kitchen sink” adjustment without a causal or operational rationale.
- Report coefficients in interpretable units, such as predicted probability or marginal rate differences, not only log-odds.
- Compare crude and adjusted estimates directly.
- State residual confounding and measurement limits.

A target-selector coefficient near zero means the measured difference was largely explained by included variables. It does not prove that selector behavior never matters or that all unmeasured mechanisms have been removed.

## 14. Distinguish explanation, prediction, and causation

- **Explanation:** describe associations and mechanism-consistent sequences.
- **Prediction:** estimate outcomes for new observations and evaluate out-of-sample performance.
- **Causation:** estimate what would change under an intervention, requiring stronger design and assumptions.

This initial project is explanatory and diagnostic. It is not primarily predictive, and it does not claim that observational adjustment identifies a real-world causal effect.

## 15. Use process-control concepts correctly

If control charts are used:

- preserve time order;
- choose the chart based on data type and denominator;
- distinguish common-cause from special-cause signals;
- do not confuse control limits with management specifications or acceptable service levels;
- remember that a stable process may still be operationally unacceptable; and
- annotate known process events without moving limits merely to hide signals.

Control charts are optional unless they materially help the time-based investigation. They are not decorative trend lines.

## 16. Reproducible analytical layers

Maintain these layers:

| Layer | Contents | Minimum control |
|---|---|---|
| Generated source | Immutable analyst-facing SQLite and restricted ground truth | Configuration, seed, schema/generator version, checksums |
| Validated/clean | Typed records and validation results | Key, range, duplicate, missingness, sequence, and reconciliation checks |
| Feature | Denominators, event windows, exposure variables | Documented formulas and unit tests |
| Analysis | Summaries, intervals, models, sensitivity checks | Fixed code/config, assumptions, diagnostics |
| Report | Tables, figures, findings, limitations | Every displayed value traceable to generated output |

Never manually edit the SQLite source or a derived CSV to repair a report.

## 17. Separate report sections

The executive and technical reports must keep these functions distinct:

### Problem

What decision, risk, or complaint motivated the investigation?

### Methods

What population, period, unit, variables, exclusions, metrics, and methods produced the evidence?

### Results

What was observed, how large was it, and how uncertain was it?

### Limitations

What measurement, assignment, clustering, model, and generalization limits remain?

### Recommendation

What practical action follows, why is it proportionate to the evidence, and how will its effect be measured?

Do not mix recommendations into the results section or hide limitations in a footnote.

## 18. Claim calibration examples

Weak:

> Selector OP-SEL-004 caused the shortage problem.

Acceptable descriptive statement:

> OP-SEL-004 recorded the highest number of short cases during the investigation period, while also completing the largest share of picks in the affected locations and time windows.

Better adjusted statement:

> The crude short-rate difference associated with OP-SEL-004 was materially reduced after adjustment for affected-area exposure, item velocity, time, requested quantity, and replenishment-event proximity. The remaining estimate was small/imprecise under the stated model.

Mechanism-consistent conclusion:

> The combined timing, location, replenishment, and peer-comparison evidence is more consistent with a localized replenishment-availability problem than with a generalized selector-specific accuracy problem. Because assignments were observational and some operational conditions remain imperfectly measured, this conclusion should guide process verification rather than individual corrective action.

## 19. Required sensitivity checks

At minimum, assess whether the primary conclusion changes when:

- the short metric uses events versus cases;
- exposure uses picks versus requested cases;
- event windows are reasonably narrowed or widened;
- the target period boundary changes;
- targeted items or locations are excluded one group at a time;
- the model uses alternate reasonable time controls;
- standard errors use the selected cluster strategy;
- high-leverage trips/items are reviewed; and
- baseline-only versus investigation-run comparisons are shown.

Sensitivity analysis should clarify robustness, not become a search for the most favorable result.

## 20. Management recommendation standard

A recommendation must include:

- the process point to verify or change;
- the evidence that motivates it;
- why it is safer or more useful than labor attribution;
- an owner or functional role, not a real person;
- an implementation or observation window;
- leading and lagging measures;
- a success threshold; and
- a rollback/escalation condition where appropriate.

Example action categories include replenishment timing/confirmation review, QA disposition coding review, event-sequence auditing, targeted process observation, and metric-definition correction. The initial recommendation should not be discipline or performance scoring.

## 21. Final competency check for every major analysis

Before publishing a finding, answer yes to all applicable questions:

1. Is the operational question explicit?
2. Are population, period, and unit of analysis named?
3. Is the metric reproducible from a documented numerator and denominator?
4. Are work mix and exposure visible?
5. Is variation shown rather than hidden by an average?
6. Are effect size and uncertainty stated in operational units?
7. Are bias, confounding, clustering, measurement error, and time dependence addressed?
8. Is the claim level no stronger than the design permits?
9. Can another reviewer regenerate the result from preserved data and code?
10. Does the recommendation include a measurement plan and avoid unsupported labor blame?
