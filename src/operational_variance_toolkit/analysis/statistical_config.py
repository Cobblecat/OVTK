"""Frozen Phase 5 statistical-analysis configuration."""

from __future__ import annotations

import hashlib
import json
import tomllib
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from operational_variance_toolkit.errors import ConfigurationError


@dataclass(frozen=True, slots=True)
class OperationalCondition:
    zone_code: str
    velocity_class: str
    aisle_codes: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class EventWindows:
    primary_replenishment_minutes: int
    replenishment_sensitivity_minutes: tuple[int, ...]
    qa_primary_hours: int
    qa_sensitivity_hours: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class AttenuationRule:
    minimum_proportional_reduction: float
    maximum_residual_risk_difference_pp: float


@dataclass(frozen=True, slots=True)
class ModelSpecification:
    family: str
    covariance: str
    fallback: str
    include_day_index: bool
    include_shift: bool
    include_velocity: bool
    include_requested_quantity: bool
    include_recorded_replenishment_status: bool


@dataclass(frozen=True, slots=True)
class ComparisonSource:
    database: str
    reconstruction: str


@dataclass(frozen=True, slots=True)
class AnalysisConfig:
    contract_version: str
    target_selector_id: str
    eligible_pick_flag: int
    primary_outcome: str
    cluster_column: str
    confidence_level: float
    operational_condition: OperationalCondition
    event_windows: EventWindows
    attenuation: AttenuationRule
    model: ModelSpecification
    comparison: ComparisonSource | None

    def canonical_payload(self) -> dict[str, Any]:
        return asdict(self)

    def canonical_json(self) -> str:
        return json.dumps(self.canonical_payload(), indent=2, sort_keys=True) + "\n"

    def sha256(self) -> str:
        return hashlib.sha256(self.canonical_json().encode("utf-8")).hexdigest()


def load_analysis_config(path: str | Path) -> AnalysisConfig:
    """Load and validate the frozen TOML analysis configuration."""

    config_path = Path(path)
    if not config_path.is_file():
        raise ConfigurationError(f"Analysis configuration does not exist: {config_path}")
    try:
        raw = tomllib.loads(config_path.read_text(encoding="utf-8"))
        analysis = raw["analysis"]
        condition = raw["operational_condition"]
        windows = raw["event_windows"]
        attenuation = raw["attenuation"]
        model = raw["model"]
        comparison_raw = raw.get("comparison")
        config = AnalysisConfig(
            contract_version=str(analysis["contract_version"]),
            target_selector_id=str(analysis["target_selector_id"]),
            eligible_pick_flag=int(analysis["eligible_pick_flag"]),
            primary_outcome=str(analysis["primary_outcome"]),
            cluster_column=str(analysis["cluster_column"]),
            confidence_level=float(analysis["confidence_level"]),
            operational_condition=OperationalCondition(
                zone_code=str(condition["zone_code"]),
                velocity_class=str(condition["velocity_class"]),
                aisle_codes=tuple(str(value) for value in condition["aisle_codes"]),
            ),
            event_windows=EventWindows(
                primary_replenishment_minutes=int(windows["primary_replenishment_minutes"]),
                replenishment_sensitivity_minutes=tuple(
                    int(value) for value in windows["replenishment_sensitivity_minutes"]
                ),
                qa_primary_hours=int(windows["qa_primary_hours"]),
                qa_sensitivity_hours=tuple(int(value) for value in windows["qa_sensitivity_hours"]),
            ),
            attenuation=AttenuationRule(
                minimum_proportional_reduction=float(attenuation["minimum_proportional_reduction"]),
                maximum_residual_risk_difference_pp=float(
                    attenuation["maximum_residual_risk_difference_pp"]
                ),
            ),
            model=ModelSpecification(**model),
            comparison=(
                ComparisonSource(
                    database=str(comparison_raw["database"]),
                    reconstruction=str(comparison_raw["reconstruction"]),
                )
                if comparison_raw
                else None
            ),
        )
    except (KeyError, TypeError, ValueError, tomllib.TOMLDecodeError) as exc:
        raise ConfigurationError(f"Invalid analysis configuration at {config_path}: {exc}") from exc
    _validate_analysis_config(config)
    return config


def _validate_analysis_config(config: AnalysisConfig) -> None:
    if config.contract_version != "1.0.0":
        raise ConfigurationError(
            f"Unsupported analysis contract version: {config.contract_version}"
        )
    if not config.target_selector_id:
        raise ConfigurationError("target_selector_id must not be empty")
    if config.eligible_pick_flag != 1:
        raise ConfigurationError("eligible_pick_flag must be 1")
    if config.primary_outcome != "short_indicator":
        raise ConfigurationError("primary_outcome must be short_indicator")
    if config.cluster_column != "trip_id":
        raise ConfigurationError("cluster_column must be trip_id")
    if not 0.80 <= config.confidence_level < 1.0:
        raise ConfigurationError("confidence_level must be between 0.80 and 1.0")
    if not config.operational_condition.aisle_codes:
        raise ConfigurationError("operational condition requires at least one aisle")
    all_windows = (
        config.event_windows.primary_replenishment_minutes,
        *config.event_windows.replenishment_sensitivity_minutes,
        config.event_windows.qa_primary_hours,
        *config.event_windows.qa_sensitivity_hours,
    )
    if any(value <= 0 for value in all_windows):
        raise ConfigurationError("event windows must be positive")
    if not 0 <= config.attenuation.minimum_proportional_reduction <= 1:
        raise ConfigurationError("minimum proportional attenuation must be between 0 and 1")
    if config.attenuation.maximum_residual_risk_difference_pp < 0:
        raise ConfigurationError("maximum residual risk difference must be nonnegative")
    expected_model = ("binomial_logit", "cluster_trip", "linear_probability_hc3")
    actual_model = (config.model.family, config.model.covariance, config.model.fallback)
    if actual_model != expected_model:
        raise ConfigurationError(f"Unsupported frozen model specification: {actual_model}")
