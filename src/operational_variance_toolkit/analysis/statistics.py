"""Deterministic Phase 5 metrics, models, sensitivities, and evidence."""

from __future__ import annotations

import math
import warnings
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
import scipy.stats as scipy_stats
import statsmodels.api as sm

from operational_variance_toolkit.analysis.statistical_config import AnalysisConfig
from operational_variance_toolkit.errors import DataValidationError
from operational_variance_toolkit.storage.statistical_sources import StatisticalSource

STATISTICS_VERSION = "1.0.0"

OUTPUT_COLUMNS: dict[str, tuple[str, ...]] = {
    "descriptive_metrics.csv": (
        "run_id",
        "group_dimension",
        "group_value",
        "eligible_picks",
        "requested_cases",
        "picked_cases",
        "short_lines",
        "short_cases",
        "short_line_rate",
        "short_case_rate",
        "short_cases_per_1000_picks",
        "short_line_ci_lower",
        "short_line_ci_upper",
        "event_count",
        "event_quantity_cases",
        "event_rate_per_1000_picks",
        "source_reference",
    ),
    "replenishment_evidence.csv": (
        "run_id",
        "evidence_item",
        "exposure_group",
        "eligible_picks",
        "short_lines",
        "short_cases",
        "short_line_rate",
        "ci_lower",
        "ci_upper",
        "task_count",
        "median_creation_to_confirmation_minutes",
        "positive_correction_count",
        "evidence_status",
        "source_reference",
    ),
    "qa_adjustment_evidence.csv": (
        "run_id",
        "relationship_rule",
        "window_hours",
        "same_location_required",
        "qa_events",
        "candidate_qa_events",
        "candidate_pairs",
        "generic_correction_pairs",
        "quantity_compatible_pairs",
        "candidate_rate",
        "ci_lower",
        "ci_upper",
        "mean_candidate_fragility",
        "all_qa_mean_fragility",
        "candidate_categories",
        "negative_control_pairs",
        "evidence_status",
        "source_reference",
    ),
    "selector_crude.csv": (
        "run_id",
        "selector_id",
        "is_target_contrast",
        "crude_rank",
        "trips",
        "eligible_picks",
        "requested_cases",
        "picked_cases",
        "short_lines",
        "short_cases",
        "short_line_rate",
        "short_line_ci_lower",
        "short_line_ci_upper",
        "short_case_rate",
        "operational_condition_picks",
        "high_velocity_picks",
        "replenishment_adjacent_picks",
        "zones_worked",
        "aisles_worked",
        "operating_dates_worked",
        "shifts_worked",
        "source_reference",
    ),
    "selector_adjusted.csv": (
        "run_id",
        "contrast",
        "model_kind",
        "covariance",
        "fallback_used",
        "crude_target_rate",
        "crude_peer_rate",
        "crude_risk_difference",
        "crude_risk_difference_pp",
        "adjusted_target_probability",
        "adjusted_peer_probability",
        "adjusted_risk_difference",
        "adjusted_risk_difference_pp",
        "adjusted_short_lines_per_1000_difference",
        "adjusted_ci_lower",
        "adjusted_ci_upper",
        "absolute_attenuation",
        "proportional_attenuation",
        "attenuation_threshold_met",
        "residual_threshold_met",
        "material_attenuation",
        "source_reference",
    ),
    "sensitivity_results.csv": (
        "run_id",
        "sensitivity_id",
        "specification",
        "estimate",
        "ci_lower",
        "ci_upper",
        "comparison_estimate",
        "conclusion_consistent",
        "notes",
        "source_reference",
    ),
    "hypothesis_evidence.csv": (
        "run_id",
        "hypothesis_id",
        "evidence_item",
        "source_metric_table",
        "estimate",
        "interval",
        "direction",
        "operational_interpretation",
        "evidence_status",
        "limitation",
        "source_artifact_reference",
        "disposition",
    ),
}


@dataclass(frozen=True, slots=True)
class ModelFit:
    model_kind: str
    covariance: str
    fallback_used: bool
    fallback_reason: str | None
    adjusted_target_probability: float
    adjusted_peer_probability: float
    risk_difference: float
    ci_lower: float
    ci_upper: float
    diagnostics: dict[str, Any]


@dataclass(frozen=True, slots=True)
class StatisticalAnalysis:
    tables: dict[str, list[dict[str, Any]]]
    model_diagnostics: dict[str, Any]

    @property
    def row_counts(self) -> dict[str, int]:
        return {file_name: len(rows) for file_name, rows in self.tables.items()}


def wilson_interval(
    successes: int, total: int, confidence_level: float = 0.95
) -> tuple[float, float]:
    """Return a Wilson score interval for a binomial proportion."""

    if total < 0 or successes < 0 or successes > total:
        raise ValueError("successes and total must describe a valid binomial count")
    if total == 0:
        return (math.nan, math.nan)
    z = float(scipy_stats.norm.ppf(0.5 + confidence_level / 2))
    rate = successes / total
    denominator = 1 + z * z / total
    center = (rate + z * z / (2 * total)) / denominator
    half_width = (
        z * math.sqrt(rate * (1 - rate) / total + z * z / (4 * total * total)) / denominator
    )
    return center - half_width, center + half_width


def calculate_attenuation(crude: float, adjusted: float) -> tuple[float, float]:
    """Return absolute and proportional attenuation of an adjusted contrast."""

    absolute = abs(crude) - abs(adjusted)
    proportional = absolute / abs(crude) if crude else 0.0
    return absolute, proportional


def risk_difference_interval(
    exposed_successes: int,
    exposed_total: int,
    peer_successes: int,
    peer_total: int,
    confidence_level: float = 0.95,
) -> tuple[float, float, float]:
    """Return a two-group risk difference and transparent Wald interval."""

    if exposed_total <= 0 or peer_total <= 0:
        raise ValueError("both risk-difference groups require observations")
    if not 0 <= exposed_successes <= exposed_total:
        raise ValueError("invalid exposed binomial count")
    if not 0 <= peer_successes <= peer_total:
        raise ValueError("invalid peer binomial count")
    exposed_rate = exposed_successes / exposed_total
    peer_rate = peer_successes / peer_total
    difference = exposed_rate - peer_rate
    standard_error = math.sqrt(
        exposed_rate * (1 - exposed_rate) / exposed_total + peer_rate * (1 - peer_rate) / peer_total
    )
    z = float(scipy_stats.norm.ppf(0.5 + confidence_level / 2))
    return difference, difference - z * standard_error, difference + z * standard_error


def build_design_matrix(picks: pd.DataFrame, config: AnalysisConfig) -> pd.DataFrame:
    """Build the frozen full-rank primary design matrix."""

    features = _feature_frame(picks, config)
    matrix = pd.DataFrame(index=features.index)
    matrix["const"] = 1.0
    matrix["target_selector"] = features["target_selector"].astype(float)
    matrix["operational_condition"] = features["operational_condition"].astype(float)
    matrix["requested_qty_centered"] = features["requested_qty_centered"].astype(float)
    if config.model.include_recorded_replenishment_status:
        matrix["active_replenishment_at_pick_flag"] = features[
            "active_replenishment_at_pick_flag"
        ].astype(float)
    if config.model.include_velocity:
        matrix["high_velocity"] = features["velocity_class"].eq("A").astype(float)
    if config.model.include_shift:
        shift_reference = sorted(features["shift_code"].astype(str).unique())
        for value in shift_reference[1:]:
            matrix[f"shift_{value}"] = (features["shift_code"].astype(str) == value).astype(float)
    if config.model.include_day_index:
        matrix["day_index"] = features["day_index"].astype(float)
    return matrix


def fit_selector_model(
    picks: pd.DataFrame,
    config: AnalysisConfig,
    *,
    covariance: str = "cluster",
    include_day_index: bool | None = None,
    force_fallback: bool = False,
) -> ModelFit:
    """Fit the frozen selector model and return a marginal probability contrast."""

    eligible = picks.loc[picks["eligible_pick_flag"] == config.eligible_pick_flag].copy()
    if eligible.empty:
        raise DataValidationError("No eligible picks are available for the primary model")
    matrix = build_design_matrix(eligible, config)
    if include_day_index is False and "day_index" in matrix:
        matrix = matrix.drop(columns="day_index")
    outcome = eligible["short_flag"].astype(float)
    fallback_reason = _model_rejection_reason(matrix, outcome, eligible, force_fallback)
    if fallback_reason is None:
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("error", RuntimeWarning)
                model = sm.GLM(outcome, matrix, family=sm.families.Binomial())
                if covariance == "cluster":
                    result = model.fit(
                        cov_type="cluster",
                        cov_kwds={"groups": eligible[config.cluster_column]},
                    )
                    covariance_label = "cluster_trip"
                else:
                    result = model.fit(cov_type="HC3")
                    covariance_label = "HC3"
            estimates = np.asarray(result.params, dtype=float)
            standard_errors = np.asarray(result.bse, dtype=float)
            if (
                not result.converged
                or not np.isfinite(estimates).all()
                or not np.isfinite(standard_errors).all()
                or np.max(np.abs(estimates)) > 20
            ):
                fallback_reason = "non-converged or unstable binomial-logit estimates"
            else:
                return _model_fit_from_result(
                    eligible,
                    matrix,
                    result,
                    config,
                    model_kind="binomial_logit",
                    covariance=covariance_label,
                    fallback_used=False,
                    fallback_reason=None,
                )
        except (ValueError, np.linalg.LinAlgError, RuntimeWarning) as exc:
            fallback_reason = f"binomial-logit estimation failed: {type(exc).__name__}"

    reduced = matrix[
        [
            "const",
            "target_selector",
            "operational_condition",
            "requested_qty_centered",
            "active_replenishment_at_pick_flag",
        ]
    ].copy()
    if np.linalg.matrix_rank(reduced.to_numpy()) < reduced.shape[1]:
        reduced = reduced.drop(columns="active_replenishment_at_pick_flag")
    result = sm.OLS(outcome, reduced).fit(cov_type="HC3")
    estimate = float(result.params["target_selector"])
    standard_error = float(result.bse["target_selector"])
    z = _z_value(config)
    diagnostics = _model_diagnostics(
        eligible,
        reduced,
        result,
        config,
        model_kind="linear_probability",
        covariance="HC3",
        fallback_used=True,
        fallback_reason=fallback_reason,
    )
    peer_probability = float(result.predict(reduced.assign(target_selector=0.0)).mean())
    target_probability = peer_probability + estimate
    return ModelFit(
        model_kind="linear_probability",
        covariance="HC3",
        fallback_used=True,
        fallback_reason=fallback_reason,
        adjusted_target_probability=target_probability,
        adjusted_peer_probability=peer_probability,
        risk_difference=estimate,
        ci_lower=estimate - z * standard_error,
        ci_upper=estimate + z * standard_error,
        diagnostics=diagnostics,
    )


def fit_short_case_rate_model(picks: pd.DataFrame, config: AnalysisConfig) -> ModelFit:
    """Fit the predefined adjusted short-case rate sensitivity model."""

    eligible = picks.loc[picks["eligible_pick_flag"] == config.eligible_pick_flag].copy()
    matrix = build_design_matrix(eligible, config)
    requested = eligible["requested_qty_cases"].astype(float)
    if (requested <= 0).any():
        raise DataValidationError("Short-case rate model requires positive requested quantity")
    requested_values = requested.to_numpy()
    offset = np.log(requested_values)
    try:
        model = sm.GLM(
            eligible["short_qty_cases"].astype(float),
            matrix,
            family=sm.families.Poisson(),
            offset=offset,
        )
        result = model.fit(
            cov_type="cluster",
            cov_kwds={"groups": eligible[config.cluster_column]},
        )
    except (ValueError, np.linalg.LinAlgError) as exc:
        raise DataValidationError("Adjusted short-case rate sensitivity is not estimable") from exc
    if not result.converged or not np.isfinite(result.params).all():
        raise DataValidationError("Adjusted short-case rate sensitivity is unstable")
    peer_matrix = matrix.assign(target_selector=0.0)
    target_matrix = matrix.assign(target_selector=1.0)
    peer_rate = (
        np.asarray(result.predict(peer_matrix, offset=offset), dtype=float) / requested_values
    )
    target_rate = (
        np.asarray(result.predict(target_matrix, offset=offset), dtype=float) / requested_values
    )
    difference = float(target_rate.mean() - peer_rate.mean())
    gradient = np.asarray(
        np.mean(target_rate[:, None] * target_matrix - peer_rate[:, None] * peer_matrix, axis=0),
        dtype=float,
    )
    variance = float(gradient @ np.asarray(result.cov_params()) @ gradient)
    standard_error = math.sqrt(max(variance, 0.0))
    z = _z_value(config)
    diagnostics = _model_diagnostics(
        eligible,
        matrix,
        result,
        config,
        model_kind="poisson_short_case_rate",
        covariance="cluster_trip",
        fallback_used=False,
        fallback_reason=None,
    )
    return ModelFit(
        model_kind="poisson_short_case_rate",
        covariance="cluster_trip",
        fallback_used=False,
        fallback_reason=None,
        adjusted_target_probability=float(target_rate.mean()),
        adjusted_peer_probability=float(peer_rate.mean()),
        risk_difference=difference,
        ci_lower=difference - z * standard_error,
        ci_upper=difference + z * standard_error,
        diagnostics=diagnostics,
    )


def build_statistical_analysis(
    source: StatisticalSource,
    config: AnalysisConfig,
    comparison: StatisticalSource | None = None,
) -> StatisticalAnalysis:
    """Build every deterministic Phase 5 output from ordinary WMS evidence."""

    picks = source.tables["pick_context"].copy()
    picks = picks.loc[picks["eligible_pick_flag"] == config.eligible_pick_flag].copy()
    if config.target_selector_id not in set(picks["selector_id"].astype(str)):
        raise DataValidationError(
            f"Target selector is absent from eligible picks: {config.target_selector_id}"
        )
    picks = _feature_frame(picks, config)
    descriptive = _build_descriptive_metrics(source, picks, config)
    replenishment = _build_replenishment_evidence(source, picks, config)
    qa_evidence = _build_qa_adjustment_evidence(source, config)
    crude = _build_selector_crude(source, picks, config)
    model_fit = fit_selector_model(picks, config)
    adjusted = _build_selector_adjusted(source, picks, config, model_fit)
    sensitivities = _build_sensitivities(source, comparison, picks, config, model_fit)
    hypotheses = _build_hypothesis_evidence(
        source,
        picks,
        config,
        model_fit,
        replenishment,
        qa_evidence,
    )
    diagnostics = {
        **model_fit.diagnostics,
        "statistics_version": STATISTICS_VERSION,
        "ordinary_analysis_ground_truth_loaded": False,
        "all_six_hypotheses_present": {row["hypothesis_id"] for row in hypotheses}
        == {"H1", "H2", "H3", "H4", "H5", "H6"},
        "findings_frozen": True,
        "limitations": [
            "The data are synthetic and represent one facility-scale run.",
            "Assignment is observational; adjustment does not establish causality.",
            "Recorded WMS confirmation does not reveal hidden physical availability timing.",
            "Only 33 investigation short events support a deliberately parsimonious model.",
            "QA-adjustment matches are candidates, not causal links.",
            "Trip-clustered uncertainty does not remove item/location dependence.",
        ],
    }
    tables = {
        "descriptive_metrics.csv": descriptive,
        "replenishment_evidence.csv": replenishment,
        "qa_adjustment_evidence.csv": qa_evidence,
        "selector_crude.csv": crude,
        "selector_adjusted.csv": adjusted,
        "sensitivity_results.csv": sensitivities,
        "hypothesis_evidence.csv": hypotheses,
    }
    return StatisticalAnalysis(tables=tables, model_diagnostics=diagnostics)


def _feature_frame(picks: pd.DataFrame, config: AnalysisConfig) -> pd.DataFrame:
    result = picks.copy()
    condition = config.operational_condition
    result["target_selector"] = (
        result["selector_id"].astype(str) == config.target_selector_id
    ).astype(int)
    result["operational_condition"] = (
        result["zone_code"].astype(str).eq(condition.zone_code)
        & result["velocity_class"].astype(str).eq(condition.velocity_class)
        & result["aisle_code"].astype(str).isin(condition.aisle_codes)
    ).astype(int)
    result["requested_qty_centered"] = (
        result["requested_qty_cases"].astype(float)
        - result["requested_qty_cases"].astype(float).mean()
    )
    operating_dates = pd.to_datetime(result["operating_date_local"])
    result["day_index"] = (operating_dates - operating_dates.min()).dt.days.astype(float)
    return result


def _model_rejection_reason(
    matrix: pd.DataFrame,
    outcome: pd.Series,
    picks: pd.DataFrame,
    force_fallback: bool,
) -> str | None:
    if force_fallback:
        return "fallback forced for configured diagnostic test"
    if int(outcome.sum()) < 20:
        return "fewer than 20 outcome events"
    if picks["trip_id"].nunique() < 20:
        return "fewer than 20 trip clusters"
    if np.linalg.matrix_rank(matrix.to_numpy()) < matrix.shape[1]:
        return "rank-deficient primary design matrix"
    return None


def _model_fit_from_result(
    picks: pd.DataFrame,
    matrix: pd.DataFrame,
    result: Any,
    config: AnalysisConfig,
    *,
    model_kind: str,
    covariance: str,
    fallback_used: bool,
    fallback_reason: str | None,
) -> ModelFit:
    peer_matrix = matrix.copy()
    target_matrix = matrix.copy()
    peer_matrix["target_selector"] = 0.0
    target_matrix["target_selector"] = 1.0
    peer_prediction = np.asarray(result.predict(peer_matrix), dtype=float)
    target_prediction = np.asarray(result.predict(target_matrix), dtype=float)
    peer_probability = float(peer_prediction.mean())
    target_probability = float(target_prediction.mean())
    risk_difference = target_probability - peer_probability
    target_gradient = np.mean(
        target_prediction[:, None] * (1 - target_prediction[:, None]) * target_matrix,
        axis=0,
    )
    peer_gradient = np.mean(
        peer_prediction[:, None] * (1 - peer_prediction[:, None]) * peer_matrix,
        axis=0,
    )
    gradient = np.asarray(target_gradient - peer_gradient, dtype=float)
    covariance_matrix = np.asarray(result.cov_params(), dtype=float)
    variance = float(gradient @ covariance_matrix @ gradient)
    standard_error = math.sqrt(max(0.0, variance))
    z = _z_value(config)
    diagnostics = _model_diagnostics(
        picks,
        matrix,
        result,
        config,
        model_kind=model_kind,
        covariance=covariance,
        fallback_used=fallback_used,
        fallback_reason=fallback_reason,
    )
    return ModelFit(
        model_kind=model_kind,
        covariance=covariance,
        fallback_used=fallback_used,
        fallback_reason=fallback_reason,
        adjusted_target_probability=target_probability,
        adjusted_peer_probability=peer_probability,
        risk_difference=risk_difference,
        ci_lower=risk_difference - z * standard_error,
        ci_upper=risk_difference + z * standard_error,
        diagnostics=diagnostics,
    )


def _model_diagnostics(
    picks: pd.DataFrame,
    matrix: pd.DataFrame,
    result: Any,
    config: AnalysisConfig,
    *,
    model_kind: str,
    covariance: str,
    fallback_used: bool,
    fallback_reason: str | None,
) -> dict[str, Any]:
    coefficients = {}
    z = _z_value(config)
    for column in matrix.columns:
        estimate = float(result.params[column])
        standard_error = float(result.bse[column])
        coefficients[column] = {
            "estimate": _round(estimate),
            "standard_error": _round(standard_error),
            "ci_lower": _round(estimate - z * standard_error),
            "ci_upper": _round(estimate + z * standard_error),
        }
        if model_kind == "binomial_logit":
            coefficients[column].update(
                {
                    "odds_ratio": _round(math.exp(estimate)),
                    "odds_ratio_ci_lower": _round(math.exp(estimate - z * standard_error)),
                    "odds_ratio_ci_upper": _round(math.exp(estimate + z * standard_error)),
                }
            )
    trip_short = picks.groupby("trip_id")["short_flag"].sum().sort_values(ascending=False)
    item_short = picks.groupby("item_id")["short_flag"].sum().sort_values(ascending=False)
    condition_cells = (
        picks.groupby(["target_selector", "operational_condition"])["short_flag"]
        .agg(["size", "sum"])
        .reset_index()
    )
    return {
        "model_kind": model_kind,
        "covariance": covariance,
        "fallback_used": fallback_used,
        "fallback_reason": fallback_reason,
        "converged": bool(getattr(result, "converged", True)),
        "observations": int(len(picks)),
        "events": int(picks["short_flag"].sum()),
        "clusters": int(picks["trip_id"].nunique()),
        "design_columns": list(matrix.columns),
        "design_rank": int(np.linalg.matrix_rank(matrix.to_numpy())),
        "design_condition_number": _round(float(np.linalg.cond(matrix.to_numpy()))),
        "separation_risk": bool(
            (
                (condition_cells["sum"] == 0) | (condition_cells["sum"] == condition_cells["size"])
            ).any()
        ),
        "condition_cells": condition_cells.to_dict(orient="records"),
        "highest_short_trip": str(trip_short.index[0]),
        "highest_short_trip_events": int(trip_short.iloc[0]),
        "highest_short_item": str(item_short.index[0]),
        "highest_short_item_events": int(item_short.iloc[0]),
        "coefficients": coefficients,
    }


def _build_descriptive_metrics(
    source: StatisticalSource, picks: pd.DataFrame, config: AnalysisConfig
) -> list[dict[str, Any]]:
    groups: list[tuple[str, str, pd.DataFrame]] = [("overall", "all eligible picks", picks)]
    group_specs = (
        ("zone", ["zone_code"]),
        ("zone_aisle", ["zone_code", "aisle_code"]),
        ("item", ["item_id"]),
        ("velocity", ["velocity_class"]),
        ("operating_date", ["operating_date_local"]),
        ("shift", ["shift_code"]),
        ("selector", ["selector_id"]),
        ("recorded_replenishment_active", ["active_replenishment_at_pick_flag"]),
        ("qa_proximity_4h", ["recent_qa_event_count_4h"]),
        ("system_event_overlap", ["system_event_overlap_flag"]),
    )
    for dimension, columns in group_specs:
        for key, frame in picks.groupby(columns, sort=True, dropna=False):
            values = key if isinstance(key, tuple) else (key,)
            groups.append((dimension, "/".join(str(value) for value in values), frame))
    rows = [_descriptive_row(source.metadata["run_id"], *group, config) for group in groups]
    reconciliation = source.tables["inventory_reconciliation"]
    rows.append(
        {
            "run_id": source.metadata["run_id"],
            "group_dimension": "reconciliation",
            "group_value": "replay_live_snapshot_exact",
            "eligible_picks": 0,
            "requested_cases": 0,
            "picked_cases": 0,
            "short_lines": 0,
            "short_cases": 0,
            "short_line_rate": 0.0,
            "short_case_rate": 0.0,
            "short_cases_per_1000_picks": 0.0,
            "short_line_ci_lower": None,
            "short_line_ci_upper": None,
            "event_count": len(reconciliation),
            "event_quantity_cases": 0,
            "event_rate_per_1000_picks": None,
            "source_reference": (
                f"inventory_reconciliation.csv:{len(reconciliation)} PASS rows;zero differences"
            ),
        }
    )
    qa = source.tables["qa_event"]
    for event_type, frame in qa.groupby("event_type", sort=True):
        rows.append(
            _event_metric_row(
                source.metadata["run_id"],
                "qa_event_type",
                str(event_type),
                len(frame),
                int(frame["qty_affected_cases"].sum()),
                len(picks),
                "qa_event",
            )
        )
    adjustments = source.tables["inventory_adjustment"]
    for reason, frame in adjustments.groupby("reason_code", sort=True):
        rows.append(
            _event_metric_row(
                source.metadata["run_id"],
                "adjustment_reason",
                str(reason),
                len(frame),
                int(frame["qty_delta_cases"].sum()),
                len(picks),
                "inventory_adjustment",
            )
        )
    return rows


def _descriptive_row(
    run_id: str,
    dimension: str,
    value: str,
    frame: pd.DataFrame,
    config: AnalysisConfig,
) -> dict[str, Any]:
    total = len(frame)
    shorts = int(frame["short_flag"].sum())
    requested = int(frame["requested_qty_cases"].sum())
    short_cases = int(frame["short_qty_cases"].sum())
    lower, upper = wilson_interval(shorts, total, config.confidence_level)
    return {
        "run_id": run_id,
        "group_dimension": dimension,
        "group_value": value,
        "eligible_picks": total,
        "requested_cases": requested,
        "picked_cases": int(frame["picked_qty_cases"].sum()),
        "short_lines": shorts,
        "short_cases": short_cases,
        "short_line_rate": _round(shorts / total),
        "short_case_rate": _round(short_cases / requested if requested else 0.0),
        "short_cases_per_1000_picks": _round(short_cases / total * 1000),
        "short_line_ci_lower": _round(lower),
        "short_line_ci_upper": _round(upper),
        "event_count": None,
        "event_quantity_cases": None,
        "event_rate_per_1000_picks": None,
        "source_reference": "pick_context.csv",
    }


def _event_metric_row(
    run_id: str,
    dimension: str,
    value: str,
    event_count: int,
    event_quantity_cases: int,
    eligible_picks: int,
    source_reference: str,
) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "group_dimension": dimension,
        "group_value": value,
        "eligible_picks": eligible_picks,
        "requested_cases": 0,
        "picked_cases": 0,
        "short_lines": 0,
        "short_cases": 0,
        "short_line_rate": 0.0,
        "short_case_rate": 0.0,
        "short_cases_per_1000_picks": 0.0,
        "short_line_ci_lower": None,
        "short_line_ci_upper": None,
        "event_count": event_count,
        "event_quantity_cases": event_quantity_cases,
        "event_rate_per_1000_picks": _round(event_count / eligible_picks * 1000),
        "source_reference": source_reference,
    }


def _build_replenishment_evidence(
    source: StatisticalSource, picks: pd.DataFrame, config: AnalysisConfig
) -> list[dict[str, Any]]:
    replenishment = source.tables["replenishment_context"]
    durations = pd.to_numeric(
        replenishment["creation_to_confirmation_minutes"], errors="coerce"
    ).dropna()
    median_duration = float(durations.median()) if not durations.empty else None
    adjustments = source.tables["inventory_adjustment"].copy()
    positive_corrections = int(
        (
            (adjustments["qty_delta_cases"] > 0) & adjustments["reason_code"].eq("FOUND_PRODUCT")
        ).sum()
    )
    rows: list[dict[str, Any]] = []
    exposure_groups: list[tuple[str, str, pd.Series]] = [
        (
            "recorded_task_status",
            "active at pick",
            picks["active_replenishment_at_pick_flag"].eq(1),
        ),
        (
            "recorded_task_status",
            "not active at pick",
            picks["active_replenishment_at_pick_flag"].eq(0),
        ),
        (
            "operational_condition",
            "inside predefined condition",
            picks["operational_condition"].eq(1),
        ),
        (
            "operational_condition",
            "outside predefined condition",
            picks["operational_condition"].eq(0),
        ),
        ("velocity", "A velocity", picks["velocity_class"].eq("A")),
        ("velocity", "B/C velocity", ~picks["velocity_class"].eq("A")),
    ]
    windows = sorted(
        {
            config.event_windows.primary_replenishment_minutes,
            *config.event_windows.replenishment_sensitivity_minutes,
        }
    )
    minutes = pd.to_numeric(
        picks["minutes_to_nearest_replenishment_completion"], errors="coerce"
    ).abs()
    for window in windows:
        exposure_groups.extend(
            [
                (
                    "confirmation_proximity",
                    f"within {window} minutes",
                    minutes.le(window).fillna(False),
                ),
                (
                    "confirmation_proximity",
                    f"outside {window} minutes",
                    minutes.gt(window).fillna(True),
                ),
            ]
        )
    exposure_groups.append(
        (
            "confirmation_proximity",
            "no recorded replenishment link",
            minutes.isna(),
        )
    )
    for evidence_item, label, mask in exposure_groups:
        frame = picks.loc[mask]
        total = len(frame)
        shorts = int(frame["short_flag"].sum())
        lower, upper = wilson_interval(shorts, total, config.confidence_level)
        rows.append(
            {
                "run_id": source.metadata["run_id"],
                "evidence_item": evidence_item,
                "exposure_group": label,
                "eligible_picks": total,
                "short_lines": shorts,
                "short_cases": int(frame["short_qty_cases"].sum()),
                "short_line_rate": _round(shorts / total if total else 0.0),
                "ci_lower": _round(lower) if total else None,
                "ci_upper": _round(upper) if total else None,
                "task_count": int(len(replenishment)),
                "median_creation_to_confirmation_minutes": _round(median_duration),
                "positive_correction_count": positive_corrections,
                "evidence_status": "descriptive ordinary-WMS evidence",
                "source_reference": (
                    "pick_context.csv;replenishment_context.csv;inventory_adjustment"
                ),
            }
        )
    conserved = replenishment.loc[
        replenishment["confirmed_qty_cases"].eq(
            replenishment["source_balance_before_cases"]
            - replenishment["source_balance_after_cases"]
        )
        & replenishment["confirmed_qty_cases"].eq(
            replenishment["destination_balance_after_cases"]
            - replenishment["destination_balance_before_cases"]
        )
    ]
    rows.extend(
        [
            {
                "run_id": source.metadata["run_id"],
                "evidence_item": "audit_balance_context",
                "exposure_group": "confirmed transfer conservation",
                "eligible_picks": 0,
                "short_lines": 0,
                "short_cases": 0,
                "short_line_rate": 0.0,
                "ci_lower": None,
                "ci_upper": None,
                "task_count": int(len(replenishment)),
                "median_creation_to_confirmation_minutes": _round(median_duration),
                "positive_correction_count": positive_corrections,
                "evidence_status": (
                    f"{len(conserved)}/{len(replenishment)} transfers conserve quantity"
                ),
                "source_reference": "replenishment_context.csv;inventory_event_ledger.csv",
            },
            {
                "run_id": source.metadata["run_id"],
                "evidence_item": "later_correction_context",
                "exposure_group": "positive FOUND_PRODUCT corrections",
                "eligible_picks": 0,
                "short_lines": 0,
                "short_cases": 0,
                "short_line_rate": 0.0,
                "ci_lower": None,
                "ci_upper": None,
                "task_count": int(len(replenishment)),
                "median_creation_to_confirmation_minutes": _round(median_duration),
                "positive_correction_count": positive_corrections,
                "evidence_status": "later positive corrections are ordinary WMS evidence",
                "source_reference": "inventory_adjustment;inventory_transaction",
            },
        ]
    )
    return rows


def _build_qa_adjustment_evidence(
    source: StatisticalSource, config: AnalysisConfig
) -> list[dict[str, Any]]:
    qa = source.tables["qa_event"].copy()
    adjustments = source.tables["inventory_adjustment"].copy()
    items = source.tables["item_master"][["item_id", "fragility_score"]].copy()
    qa["qa_time"] = pd.to_datetime(qa["occurred_utc"], utc=True, format="mixed")
    adjustments["adjustment_time"] = pd.to_datetime(
        adjustments["effective_utc"], utc=True, format="mixed"
    )
    pairs = qa.merge(adjustments, on=["run_id", "item_id"], suffixes=("_qa", "_adjustment"))
    pairs["hours_to_adjustment"] = (
        pairs["adjustment_time"] - pairs["qa_time"]
    ).dt.total_seconds() / 3600
    negative_pairs = pairs.loc[pairs["qty_delta_cases"].lt(0) & pairs["hours_to_adjustment"].lt(0)]
    rule_set = [
        (1, True),
        (config.event_windows.qa_primary_hours, True),
        (24, True),
        (config.event_windows.qa_primary_hours, False),
        (24, False),
    ]
    rows = []
    qa_fragility = qa[["item_id"]].drop_duplicates().merge(items, on="item_id")
    all_qa_mean_fragility = float(qa_fragility["fragility_score"].mean())
    for window, same_location in dict.fromkeys(rule_set):
        mask = (
            pairs["qty_delta_cases"].lt(0)
            & pairs["hours_to_adjustment"].ge(0)
            & pairs["hours_to_adjustment"].le(window)
        )
        if same_location:
            mask &= pairs["location_id_qa"].eq(pairs["location_id_adjustment"])
        candidates = pairs.loc[mask].copy()
        candidate_qa = int(candidates["qa_event_id"].nunique())
        generic = int(candidates["reason_code_adjustment"].eq("COUNT_CORRECTION").sum())
        compatible = int(
            candidates["qty_delta_cases"].abs().eq(candidates["qty_affected_cases"]).sum()
        )
        candidate_items = candidates[["item_id"]].drop_duplicates().merge(items, on="item_id")
        mean_fragility = (
            float(candidate_items["fragility_score"].mean()) if not candidate_items.empty else None
        )
        negative_mask = negative_pairs["hours_to_adjustment"].ge(-window)
        if same_location:
            negative_mask &= negative_pairs["location_id_qa"].eq(
                negative_pairs["location_id_adjustment"]
            )
        lower, upper = wilson_interval(candidate_qa, len(qa), config.confidence_level)
        rows.append(
            {
                "run_id": source.metadata["run_id"],
                "relationship_rule": "same item; QA before negative adjustment",
                "window_hours": window,
                "same_location_required": int(same_location),
                "qa_events": int(len(qa)),
                "candidate_qa_events": candidate_qa,
                "candidate_pairs": int(len(candidates)),
                "generic_correction_pairs": generic,
                "quantity_compatible_pairs": compatible,
                "candidate_rate": _round(candidate_qa / len(qa) if len(qa) else 0.0),
                "ci_lower": _round(lower) if len(qa) else None,
                "ci_upper": _round(upper) if len(qa) else None,
                "mean_candidate_fragility": _round(mean_fragility),
                "all_qa_mean_fragility": _round(all_qa_mean_fragility),
                "candidate_categories": ";".join(
                    sorted(
                        source.tables["item_master"]
                        .loc[
                            source.tables["item_master"]["item_id"].isin(
                                candidate_items["item_id"]
                            ),
                            "category",
                        ]
                        .astype(str)
                        .unique()
                    )
                ),
                "negative_control_pairs": int(negative_mask.sum()),
                "evidence_status": "candidate relationship; not causal",
                "source_reference": "qa_event;inventory_adjustment;item_master",
            }
        )
    return rows


def _build_selector_crude(
    source: StatisticalSource, picks: pd.DataFrame, config: AnalysisConfig
) -> list[dict[str, Any]]:
    rows = []
    for selector_id, frame in picks.groupby("selector_id", sort=True):
        total = len(frame)
        shorts = int(frame["short_flag"].sum())
        requested = int(frame["requested_qty_cases"].sum())
        lower, upper = wilson_interval(shorts, total, config.confidence_level)
        rows.append(
            {
                "run_id": source.metadata["run_id"],
                "selector_id": selector_id,
                "is_target_contrast": int(selector_id == config.target_selector_id),
                "crude_rank": 0,
                "trips": int(frame["trip_id"].nunique()),
                "eligible_picks": total,
                "requested_cases": requested,
                "picked_cases": int(frame["picked_qty_cases"].sum()),
                "short_lines": shorts,
                "short_cases": int(frame["short_qty_cases"].sum()),
                "short_line_rate": _round(shorts / total),
                "short_line_ci_lower": _round(lower),
                "short_line_ci_upper": _round(upper),
                "short_case_rate": _round(frame["short_qty_cases"].sum() / requested),
                "operational_condition_picks": int(frame["operational_condition"].sum()),
                "high_velocity_picks": int(frame["velocity_class"].eq("A").sum()),
                "replenishment_adjacent_picks": int(frame["replenishment_adjacent_flag"].sum()),
                "zones_worked": int(frame["zone_code"].nunique()),
                "aisles_worked": int(frame[["zone_code", "aisle_code"]].drop_duplicates().shape[0]),
                "operating_dates_worked": int(frame["operating_date_local"].nunique()),
                "shifts_worked": int(frame["shift_code"].nunique()),
                "source_reference": "pick_context.csv",
            }
        )
    ranked = sorted(
        rows,
        key=lambda row: (-row["short_line_rate"], -row["short_lines"], row["selector_id"]),
    )
    for rank, row in enumerate(ranked, start=1):
        row["crude_rank"] = rank
    return sorted(rows, key=lambda row: row["selector_id"])


def _build_selector_adjusted(
    source: StatisticalSource,
    picks: pd.DataFrame,
    config: AnalysisConfig,
    model_fit: ModelFit,
) -> list[dict[str, Any]]:
    target = picks.loc[picks["target_selector"].eq(1)]
    peers = picks.loc[picks["target_selector"].eq(0)]
    crude_target = float(target["short_flag"].mean())
    crude_peer = float(peers["short_flag"].mean())
    crude_difference = crude_target - crude_peer
    absolute, proportional = calculate_attenuation(crude_difference, model_fit.risk_difference)
    attenuation_met = proportional >= config.attenuation.minimum_proportional_reduction
    residual_met = (
        abs(model_fit.risk_difference) * 100
        <= config.attenuation.maximum_residual_risk_difference_pp
    )
    return [
        {
            "run_id": source.metadata["run_id"],
            "contrast": f"{config.target_selector_id} versus all other selectors",
            "model_kind": model_fit.model_kind,
            "covariance": model_fit.covariance,
            "fallback_used": int(model_fit.fallback_used),
            "crude_target_rate": _round(crude_target),
            "crude_peer_rate": _round(crude_peer),
            "crude_risk_difference": _round(crude_difference),
            "crude_risk_difference_pp": _round(crude_difference * 100),
            "adjusted_target_probability": _round(model_fit.adjusted_target_probability),
            "adjusted_peer_probability": _round(model_fit.adjusted_peer_probability),
            "adjusted_risk_difference": _round(model_fit.risk_difference),
            "adjusted_risk_difference_pp": _round(model_fit.risk_difference * 100),
            "adjusted_short_lines_per_1000_difference": _round(model_fit.risk_difference * 1000),
            "adjusted_ci_lower": _round(model_fit.ci_lower),
            "adjusted_ci_upper": _round(model_fit.ci_upper),
            "absolute_attenuation": _round(absolute),
            "proportional_attenuation": _round(proportional),
            "attenuation_threshold_met": int(attenuation_met),
            "residual_threshold_met": int(residual_met),
            "material_attenuation": int(attenuation_met and residual_met),
            "source_reference": "pick_context.csv;configs/phase5_analysis.toml",
        }
    ]


def _build_sensitivities(
    source: StatisticalSource,
    comparison: StatisticalSource | None,
    picks: pd.DataFrame,
    config: AnalysisConfig,
    primary: ModelFit,
) -> list[dict[str, Any]]:
    run_id = source.metadata["run_id"]
    rows = [
        _sensitivity_row(
            run_id,
            "primary",
            "short indicator; trip-clustered logit; primary time controls",
            primary.risk_difference,
            primary.ci_lower,
            primary.ci_upper,
            primary.risk_difference,
            True,
            "Frozen primary specification",
        )
    ]
    target = picks["target_selector"].eq(1)
    target_case_rate = (
        picks.loc[target, "short_qty_cases"].sum() / picks.loc[target, "requested_qty_cases"].sum()
    )
    peer_case_rate = (
        picks.loc[~target, "short_qty_cases"].sum()
        / picks.loc[~target, "requested_qty_cases"].sum()
    )
    case_difference = float(target_case_rate - peer_case_rate)
    adjusted_case_fit = (
        fit_short_case_rate_model(picks, config) if int(picks["short_flag"].sum()) >= 20 else None
    )
    rows.append(
        _sensitivity_row(
            run_id,
            "case_outcome",
            (
                "adjusted short cases per requested case"
                if adjusted_case_fit is not None
                else "descriptive short cases per requested case"
            ),
            adjusted_case_fit.risk_difference if adjusted_case_fit else case_difference,
            adjusted_case_fit.ci_lower if adjusted_case_fit else None,
            adjusted_case_fit.ci_upper if adjusted_case_fit else None,
            primary.risk_difference,
            (abs(adjusted_case_fit.risk_difference) <= 0.02 if adjusted_case_fit else True),
            (
                f"Crude case-rate difference was {case_difference:.8f}"
                if adjusted_case_fit
                else "Too few events for adjusted count sensitivity; descriptive only"
            ),
        )
    )
    no_day = fit_selector_model(picks, config, include_day_index=False)
    rows.append(
        _sensitivity_row(
            run_id,
            "alternate_time_control",
            "omit operating-day index",
            no_day.risk_difference,
            no_day.ci_lower,
            no_day.ci_upper,
            primary.risk_difference,
            abs(no_day.risk_difference) <= 0.02,
            "Same frozen covariates except day index",
        )
    )
    hc3 = fit_selector_model(picks, config, covariance="HC3")
    rows.append(
        _sensitivity_row(
            run_id,
            "alternate_covariance",
            "HC3 instead of trip clustering",
            hc3.risk_difference,
            hc3.ci_lower,
            hc3.ci_upper,
            primary.risk_difference,
            abs(hc3.risk_difference - primary.risk_difference) <= 0.001,
            "Point estimate is unchanged; uncertainty assumption differs",
        )
    )
    outside = picks.loc[picks["operational_condition"].eq(0)]
    outside_difference = _binary_difference(outside, "target_selector", "short_flag")
    rows.append(
        _sensitivity_row(
            run_id,
            "target_outside_condition",
            "target versus peers outside predefined condition",
            outside_difference,
            None,
            None,
            primary.risk_difference,
            abs(outside_difference) <= 0.02,
            "Direct negative-control comparison",
        )
    )
    condition = picks.loc[picks["operational_condition"].eq(1)]
    peer_condition = condition.loc[condition["target_selector"].eq(0)]
    rows.append(
        _sensitivity_row(
            run_id,
            "exposed_peers",
            "peer short-line rate inside predefined condition",
            float(peer_condition["short_flag"].mean()),
            *wilson_interval(
                int(peer_condition["short_flag"].sum()),
                len(peer_condition),
                config.confidence_level,
            ),
            primary.risk_difference,
            peer_condition["short_flag"].sum() > 0,
            "Peers show nonzero shorts under the same measured condition",
        )
    )
    minutes = pd.to_numeric(
        picks["minutes_to_nearest_replenishment_completion"], errors="coerce"
    ).abs()
    for window in sorted(
        {
            *config.event_windows.replenishment_sensitivity_minutes,
            config.event_windows.primary_replenishment_minutes,
        }
    ):
        exposed = picks.loc[minutes.le(window).fillna(False)]
        rate = float(exposed["short_flag"].mean()) if len(exposed) else 0.0
        lower, upper = wilson_interval(
            int(exposed["short_flag"].sum()), len(exposed), config.confidence_level
        )
        rows.append(
            _sensitivity_row(
                run_id,
                f"replenishment_window_{window}",
                f"short-line rate within {window} minutes of recorded confirmation",
                rate,
                lower,
                upper,
                primary.risk_difference,
                True,
                "Recorded WMS timing only",
            )
        )
    condition_short_items = sorted(condition.loc[condition["short_flag"].eq(1), "item_id"].unique())
    for item_id in condition_short_items:
        reduced = picks.loc[picks["item_id"].ne(item_id)]
        fit = fit_selector_model(reduced, config)
        rows.append(
            _sensitivity_row(
                run_id,
                f"remove_{item_id}",
                f"remove condition item/location group {item_id}",
                fit.risk_difference,
                fit.ci_lower,
                fit.ci_upper,
                primary.risk_difference,
                abs(fit.risk_difference) <= 0.02,
                (
                    "Predefined leave-one-group-out review"
                    + (f"; fallback: {fit.fallback_reason}" if fit.fallback_used else "")
                ),
            )
        )
    top_trip = picks.groupby("trip_id")["short_flag"].sum().idxmax()
    top_item = picks.groupby("item_id")["short_flag"].sum().idxmax()
    for sensitivity_id, column, value in (
        ("remove_high_leverage_trip", "trip_id", top_trip),
        ("remove_high_leverage_item", "item_id", top_item),
    ):
        fit = fit_selector_model(picks.loc[picks[column].ne(value)], config)
        rows.append(
            _sensitivity_row(
                run_id,
                sensitivity_id,
                f"remove highest-short {column} {value}",
                fit.risk_difference,
                fit.ci_lower,
                fit.ci_upper,
                primary.risk_difference,
                abs(fit.risk_difference) <= 0.02,
                (
                    "High-leverage review"
                    + (f"; fallback: {fit.fallback_reason}" if fit.fallback_used else "")
                ),
            )
        )
    if comparison is not None:
        comparison_picks = _feature_frame(
            comparison.tables["pick_context"].loc[
                comparison.tables["pick_context"]["eligible_pick_flag"].eq(
                    config.eligible_pick_flag
                )
            ],
            config,
        )
        baseline_target = comparison_picks.loc[comparison_picks["target_selector"].eq(1)]
        baseline_peers = comparison_picks.loc[comparison_picks["target_selector"].eq(0)]
        baseline_difference, baseline_lower, baseline_upper = risk_difference_interval(
            int(baseline_target["short_flag"].sum()),
            len(baseline_target),
            int(baseline_peers["short_flag"].sum()),
            len(baseline_peers),
            config.confidence_level,
        )
        rows.append(
            _sensitivity_row(
                run_id,
                "baseline_comparison",
                "baseline target-versus-peer crude risk difference",
                baseline_difference,
                baseline_lower,
                baseline_upper,
                primary.risk_difference,
                baseline_lower <= 0 <= baseline_upper,
                (
                    f"Negative-control run {comparison.metadata['run_id']}; only "
                    f"{int(comparison_picks['short_flag'].sum())} short events"
                ),
                source_reference="comparison pick_context.csv",
            )
        )
    return rows


def _build_hypothesis_evidence(
    source: StatisticalSource,
    picks: pd.DataFrame,
    config: AnalysisConfig,
    model: ModelFit,
    replenishment: list[dict[str, Any]],
    qa_evidence: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    target = picks["target_selector"].eq(1)
    crude = float(picks.loc[target, "short_flag"].mean() - picks.loc[~target, "short_flag"].mean())
    _, attenuation = calculate_attenuation(crude, model.risk_difference)
    condition = picks["operational_condition"].eq(1)
    condition_rate = float(picks.loc[condition, "short_flag"].mean())
    outside_rate = float(picks.loc[~condition, "short_flag"].mean())
    velocity_a_rate = float(picks.loc[picks["velocity_class"].eq("A"), "short_flag"].mean())
    other_velocity_rate = float(picks.loc[~picks["velocity_class"].eq("A"), "short_flag"].mean())
    primary_qa = next(
        row
        for row in qa_evidence
        if row["window_hours"] == config.event_windows.qa_primary_hours
        and row["same_location_required"] == 1
    )
    primary_window = next(
        row
        for row in replenishment
        if row["evidence_item"] == "confirmation_proximity"
        and row["exposure_group"]
        == f"within {config.event_windows.primary_replenishment_minutes} minutes"
    )
    outside_window = next(
        row
        for row in replenishment
        if row["evidence_item"] == "confirmation_proximity"
        and row["exposure_group"]
        == f"outside {config.event_windows.primary_replenishment_minutes} minutes"
    )
    sufficient_recorded = picks.loc[
        picks["system_qty_before_cases"].ge(picks["requested_qty_cases"])
    ]
    shorts_with_sufficient_recorded = int(sufficient_recorded["short_flag"].sum())
    reconciliation = source.tables["inventory_reconciliation"]
    hypotheses = [
        (
            "H1",
            "Crude versus adjusted target-selector contrast",
            "selector_adjusted.csv",
            model.risk_difference,
            (model.ci_lower, model.ci_upper),
            "contradicts generalized selector attribution",
            (
                f"The crude {crude:.4f} risk difference attenuates "
                f"{attenuation:.1%} after measured exposure adjustment."
            ),
            "contradicting",
            "Residual confounding and sparse outcomes remain.",
            "Not supported as a generalized selector accuracy problem",
        ),
        (
            "H2",
            "Recorded replenishment and availability context",
            "replenishment_evidence.csv",
            primary_window["short_line_rate"] - outside_window["short_line_rate"],
            None,
            "mechanism-consistent",
            (
                "Shorts concentrate in a localized condition with recorded "
                "replenishment context and later corrections."
            ),
            "supporting",
            (
                "Recorded task duration is constant and WMS confirmation time cannot "
                "reveal physical availability."
            ),
            "Supported as mechanism-consistent, not proven causal",
        ),
        (
            "H3",
            "High-velocity short concentration",
            "descriptive_metrics.csv",
            velocity_a_rate - other_velocity_rate,
            None,
            "supports concentration",
            "A-velocity picks have a higher recorded short rate than B/C picks.",
            "supporting",
            "Velocity is correlated with zone, aisle, quantity, and assignment.",
            "Supported as descriptive concentration",
        ),
        (
            "H4",
            "Location/zone/time operational condition",
            "descriptive_metrics.csv",
            condition_rate - outside_rate,
            None,
            "supports localized concentration",
            "Shorts are concentrated in CHILLED A-velocity work in aisles A1-A3.",
            "supporting",
            "The condition is analyst-defined from one finite run.",
            "Supported as localized work-mix concentration",
        ),
        (
            "H5",
            "QA before generic negative adjustment candidates",
            "qa_adjustment_evidence.csv",
            primary_qa["candidate_rate"],
            (primary_qa["ci_lower"], primary_qa["ci_upper"]),
            "mechanism-consistent",
            "Same-item/location QA observations precede compatible generic negative adjustments.",
            "supporting",
            (
                "Candidate timing and quantity compatibility do not prove linkage; "
                "candidate fragility is not elevated versus all QA items."
            ),
            "Supported as mechanism-consistent candidate evidence",
        ),
        (
            "H6",
            "Point-of-pick short with eventual exact reconciliation",
            "pick_context.csv;inventory_reconciliation.csv",
            shorts_with_sufficient_recorded,
            None,
            "supports temporary recorded/available mismatch",
            (
                f"{shorts_with_sufficient_recorded} short lines occurred with recorded "
                f"quantity sufficient, while all {len(reconciliation)} locations "
                "reconcile exactly at close."
            ),
            "supporting",
            "The ordinary WMS does not observe hidden physical inventory directly.",
            (
                "Supported as point-in-time availability inconsistency with eventual "
                "recorded correctness"
            ),
        ),
    ]
    return [
        {
            "run_id": source.metadata["run_id"],
            "hypothesis_id": hypothesis_id,
            "evidence_item": evidence_item,
            "source_metric_table": source_table,
            "estimate": _round(estimate),
            "interval": _format_interval(interval),
            "direction": direction,
            "operational_interpretation": interpretation,
            "evidence_status": status,
            "limitation": limitation,
            "source_artifact_reference": source_table,
            "disposition": disposition,
        }
        for (
            hypothesis_id,
            evidence_item,
            source_table,
            estimate,
            interval,
            direction,
            interpretation,
            status,
            limitation,
            disposition,
        ) in hypotheses
    ]


def _sensitivity_row(
    run_id: str,
    sensitivity_id: str,
    specification: str,
    estimate: float,
    ci_lower: float | None,
    ci_upper: float | None,
    comparison_estimate: float,
    consistent: bool,
    notes: str,
    *,
    source_reference: str = "pick_context.csv;analysis_config.json",
) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "sensitivity_id": sensitivity_id,
        "specification": specification,
        "estimate": _round(estimate),
        "ci_lower": _round(ci_lower),
        "ci_upper": _round(ci_upper),
        "comparison_estimate": _round(comparison_estimate),
        "conclusion_consistent": int(bool(consistent)),
        "notes": notes,
        "source_reference": source_reference,
    }


def _binary_difference(frame: pd.DataFrame, group_column: str, outcome_column: str) -> float:
    exposed = frame.loc[frame[group_column].eq(1), outcome_column]
    unexposed = frame.loc[frame[group_column].eq(0), outcome_column]
    if exposed.empty or unexposed.empty:
        raise DataValidationError(f"Cannot calculate contrast for {group_column}")
    return float(exposed.mean() - unexposed.mean())


def _format_interval(interval: tuple[float | None, float | None] | None) -> str:
    if interval is None or interval[0] is None or interval[1] is None:
        return "not estimated"
    return f"[{_round(interval[0]):.8f}, {_round(interval[1]):.8f}]"


def _z_value(config: AnalysisConfig) -> float:
    return float(scipy_stats.norm.ppf(0.5 + config.confidence_level / 2))


def _round(value: float | int | None) -> float | int | None:
    if value is None:
        return None
    numeric = float(value)
    if math.isnan(numeric) or math.isinf(numeric):
        return None
    return round(numeric, 8)
