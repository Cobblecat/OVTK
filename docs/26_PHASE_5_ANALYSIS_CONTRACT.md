# 26 - Phase 5 Frozen Analysis Contract

**Status:** Frozen before acceptance of final model coefficients  
**Contract version:** 1.0.0  
**Configuration:** `configs/phase5_analysis.toml`

## 1. Decision and questions

The business concern is whether an unusually high recorded-short result for
selector `OP-0002` represents a generalized selector accuracy problem or is
better explained by measured work assignment, inventory availability, and
operational timing. The investigation also evaluates replenishment timing,
high-velocity concentration, place/time concentration, QA damage masking, and
eventual recorded-inventory correction.

This is an explanatory synthetic-data investigation. It does not rank
associates, estimate causal fault, or support disciplinary action.

## 2. Frozen sources and provenance

| Role | Run ID | Schema | Period (UTC) | Source SHA-256 |
|---|---|---|---|---|
| Baseline negative control | `RUN-0AA91A281BA99A73` | 3.0.0 | 2026-05-04 07:00 through 2026-05-14 19:00 | `4225d8472887037b73d8d50f0eb3756961f1bf46939522d89b97ac89918c83d4` |
| Investigation primary | `RUN-D4876095A8166078` | 3.0.0 | 2026-05-04 07:00 through 2026-05-14 19:00 | `104e2b903777b91ecdbde16fe5d4a7852925658c7e228a707416ac1ad7238aff` |

The paired reconstruction directories are
`artifacts/analysis/schema3_baseline_accepted` and
`artifacts/analysis/schema3_investigation_accepted`. The workflow validates
their manifests, source identity, file checksums, required schemas, and row
grain before analysis. The SQLite databases are opened read-only and checksums
are compared before and after execution.

Restricted ground truth is prohibited from the ordinary workflow. The CLI has
no truth argument, and analysis code must not import ground-truth storage or
scenario modules.

## 3. Population and grains

The target population is all schema-3 pick attempts with
`eligible_pick_flag = 1` in the selected complete synthetic run. The primary
grain is one unique `pick_event_id`. No eligible pick is excluded for its
outcome, selector, item, location, shift, or time.

Secondary grains are:

- trip for repeated-work clustering;
- selector for crude exposure summaries;
- item/pick location for localized condition and leverage review;
- replenishment task for timing evidence;
- QA event and candidate adjustment pair for mechanism-consistent evidence;
- operating date, shift, zone, aisle, and velocity for descriptive work mix;
- location for reconstruction reconciliation.

Baseline is a negative-control comparison because three short lines cannot
support a stable adjusted model. The investigation run is the inferential
population. Uncertainty describes model/superpopulation uncertainty around one
complete synthetic run, not sampling uncertainty about real workers or sites.

## 4. Outcomes, denominators, and exposures

Primary outcome:

```text
short_indicator = 1 when short_qty_cases > 0, otherwise 0
```

Primary denominator is eligible pick lines. Secondary denominators are
requested cases, eligible picks per 1,000, QA events, replenishment tasks, and
candidate event pairs as explicitly labeled.

Frozen metrics include requested, picked, and short cases; short lines;
short-line rate; short-case rate per requested case; short cases per 1,000
eligible picks; QA and generic-adjustment rates; adjustment quantity by reason;
and exact replay/live/snapshot reconciliation.

The target-selector contrast is `OP-0002` versus all other selectors. It is the
documented complaint contrast and is not a general selector ranking. Work-mix
exposure is always displayed beside selector outcomes.

The predefined ordinary operational-condition exposure is a pick in the
`CHILLED` zone, A velocity class, and aisle A1, A2, or A3. This condition was
fixed from the analyst-visible adequacy audit before accepting final model
coefficients. It is not a hidden scenario label. Additional measured exposures
are requested quantity, velocity, shift, operating-day index, recorded active
replenishment at pick, and recorded event proximity.

## 5. Evidence rules

Replenishment adjacency uses the reconstruction task link and recorded WMS
times. The primary window is 120 minutes around confirmation; sensitivity
windows are 60 and 240 minutes. Active-task status, confirmation duration,
high-velocity interaction, short context, subsequent replenishment, and
positive correction evidence are reported separately. Recorded confirmation
cannot prove when physical stock became available.

QA-adjustment candidates require QA before adjustment, the same item, a
negative adjustment, and a bounded time window. The primary rule also requires
the same location and a four-hour window. Sensitivities use one and 24 hours
and relax location while retaining same item. Quantity compatibility and
generic `COUNT_CORRECTION` reason are reported; a candidate is never described
as a proven causal link. Adjustment-before-QA and unmatched QA counts are
negative controls.

## 6. Primary model and uncertainty

The frozen primary model is a binomial-logit generalized linear model at pick
grain:

```text
short_indicator ~ target selector + operational condition
                + centered requested quantity + high-velocity indicator
                + shift + operating-day index
                + recorded active replenishment at pick
```

The target coefficient is converted to an average counterfactual probability
difference by setting only target-selector status to one versus zero across the
same observed work mix. Covariance is clustered by trip. The report includes
design rank, condition number, convergence, event count, cluster count,
influence summaries, coefficient stability, and the marginal contrast with a
delta-method interval.

The velocity contrast is A versus combined B/C. The adequacy audit found no
recorded short events in the standalone B cell, so separate B and C indicators
would create a separated nuisance coefficient without improving the business
contrast. This collapse was made before final model acceptance and does not
change the target, condition, outcome, or attenuation rules.

The model is rejected when the design is rank-deficient, does not converge,
has non-finite estimates, has fewer than 20 events or 20 clusters, or raises a
separation/estimation error. The frozen fallback is a reduced linear-probability
model with HC3 covariance using target selector, operational condition,
centered requested quantity, and recorded active replenishment. Its target
coefficient is the adjusted risk difference. Fallback use and its limitations
must be explicit.

Material attenuation requires both:

1. at least 50% proportional reduction in the absolute crude target-versus-peer
   risk difference; and
2. an absolute adjusted residual risk difference no greater than 2.0 percentage
   points.

The rule was fixed before final coefficient acceptance. Passing it supports an
exposure-adjusted association interpretation, not innocence or causality.

## 7. Sensitivity set

The workflow discloses:

- short indicator and short-case/requested-case outcomes;
- pick-line and requested-case exposure;
- 60-, 120-, and 240-minute replenishment windows;
- primary day-index and alternate no-day time controls;
- one predefined operational-condition item/location removed at a time;
- target-selector results outside the operational condition;
- exposed-peer results inside the condition;
- trip-clustered and HC3 uncertainty;
- highest-leverage trip and item review; and
- baseline-versus-investigation comparison.

Specifications are not searched for a favorable answer. Any contradictory
result remains in `sensitivity_results.csv`.

## 8. Adequacy audit

| Measure | Baseline | Investigation |
|---|---:|---:|
| Eligible picks | 969 | 1,133 |
| Requested cases | 1,462 | 1,771 |
| Picked cases | 1,459 | 1,732 |
| Short lines | 3 | 33 |
| Short cases | 3 | 39 |
| Selectors | 18 | 18 |
| Trips | 120 | 140 |
| Replenishment tasks | 59 | 78 |
| QA events | 8 | 18 |
| Adjustments | 4 | 22 |

Investigation selector exposure ranges from 44 to 278 picks (median 50), and
trip size ranges from 6 to 10 picks (median 8). All three zones, 12 aisles,
three velocity classes, 10 operating dates, and two shifts are represented.
The investigation operational condition has 140 picks and 31 short lines:
`OP-0002` has 65 picks/28 short lines; peers have 75 picks/3 short lines.
Outside it, `OP-0002` has 213 picks/1 short line and peers have 780/1.

All recorded replenishment tasks are confirmed and recorded creation-to-
confirmation time is seven minutes, so within-run WMS task-duration variation
cannot identify hidden physical delay. Recorded active-task exposure exists for
78 investigation picks. QA-adjustment candidates and generic corrections are
observable, but causal identity is not.

Thirty-three short events across 140 trip clusters support the parsimonious
primary model, with meaningful separation risk from concentration in eight
item/locations and five selectors. That risk is addressed through low model
dimension, explicit diagnostics, trip clustering, sensitivity checks, and the
frozen fallback. No additional simulation scale is required.

## 9. Frozen outputs

The statistics directory contains deterministic JSON/CSV artifacts defined in
the Phase 5 plan. Every row includes a source-table or source-artifact reference
where relevant. `analysis_manifest.json` records configuration, source, input,
and output checksums plus row counts. Only the manifest execution timestamp is
non-deterministic.

The six-hypothesis table schema is:

```text
hypothesis_id, evidence_item, source_metric_table, estimate, interval,
direction, operational_interpretation, evidence_status, limitation,
source_artifact_reference, disposition
```

Findings are frozen only after source preservation, no-truth, reproducibility,
model, sensitivity, hypothesis-completeness, tests, lint, format, and diff gates
all pass.

## 10. Frozen findings and acceptance

The definitive accepted statistics directory is
`artifacts/analysis/RUN-D4876095A8166078/statistics_accepted`.

- population: 1,133 eligible picks, 1,771 requested cases, 33 short lines, and
  39 short cases across 140 trips and 18 selectors;
- crude target rate: 29/278 = 10.4317%; peer rate: 4/855 = 0.4678%; crude risk
  difference: 9.9638 percentage points;
- adjusted target probability: 3.5178%; adjusted peer probability: 2.6701%;
  adjusted risk difference: 0.8477 percentage points (95% trip-clustered
  interval -1.1213 to 2.8167 points);
- attenuation: 91.49%, satisfying both frozen materiality thresholds;
- adjusted short-case rate sensitivity: 0.8034 percentage points (95% interval
  -0.5119 to 2.1188 points), consistent with the primary conclusion;
- recorded 120-minute confirmation-window short rate: 8.3333% versus 3.2995%
  outside that window; all 78 transfers conserve quantity, while recorded task
  duration is uniformly seven minutes and cannot identify physical delay;
- QA evidence: 13/18 same-item/location four-hour candidates, including 10
  generic count corrections and 13 quantity-compatible pairs; candidate mean
  fragility 0.3254 versus 0.3359 across all QA items does not support elevated
  fragility as an explanation;
- 30 short lines occurred while recorded pre-pick quantity was sufficient, and
  all 192 locations reconciled exactly at close; and
- all six hypotheses are represented. Generalized selector attribution is not
  supported; localized replenishment/availability, high-velocity, place/time,
  QA-masking, and eventual-correction evidence is descriptive or
  mechanism-consistent, not causal.

Sensitivity disclosure: removing `ITEM-0005` eliminates all exposed-peer short
events in the predefined condition, makes the clustered logit unstable, and
invokes the frozen HC3 fallback. Its 5.0811-point residual is contrary to the
primary threshold and demonstrates limited overlap; the target outside the
condition remains only 0.3413 points above peers. The result is retained in the
frozen output and limits generalization.

Accepted output row counts are 166 descriptive rows, 15 replenishment rows, 5
QA-adjustment rows, 18 crude selector rows, 1 adjusted selector row, 18
sensitivity rows, and 6 hypothesis rows. Ordinary analysis loaded no ground
truth, source checksums remained unchanged, and findings are frozen for Phase 6.
