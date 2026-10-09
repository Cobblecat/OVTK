"""Phase 0 configuration loading and validation."""

from __future__ import annotations

import hashlib
import json
import re
import tomllib
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from operational_variance_toolkit.errors import ConfigurationError

_SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?$")
_SCENARIO_RE = re.compile(r"^[a-z][a-z0-9_-]*$")
_STABLE_ID_RE = re.compile(r"^[A-Z0-9][A-Z0-9_-]*$")

_EXPECTED_SECTIONS = {
    "run": {
        "scenario_name",
        "scenario_version",
        "seed",
        "start_local",
        "end_local",
        "facility_timezone",
    },
    "facility": {"facility_id", "name"},
    "dimensions": {
        "zone_count",
        "item_count",
        "selector_count",
        "replenisher_count",
        "qa_operator_count",
        "shift_count",
    },
    "storage": {"database_path", "ground_truth_directory", "export_directory"},
    "operations": {
        "trip_count",
        "pick_lines_per_trip_min",
        "pick_lines_per_trip_max",
        "short_probability",
        "qa_event_count",
        "damage_event_count",
        "adjustment_count",
        "system_event_count",
    },
    "failures": {
        "replenishment_gap",
        "qa_masking",
        "selector_false_lead",
    },
}

_FAILURE_SECTION_KEYS = {
    "replenishment_gap": {
        "enabled",
        "target_item_count",
        "forced_short_count",
        "recovery_adjustment_count",
    },
    "qa_masking": {
        "enabled",
        "event_count",
        "generic_adjustment_count",
    },
    "selector_false_lead": {
        "enabled",
        "exposure_trip_count",
    },
}


@dataclass(frozen=True, slots=True)
class RunConfig:
    scenario_name: str
    scenario_version: str
    seed: int
    start_utc: datetime
    end_utc: datetime
    facility_timezone: str


@dataclass(frozen=True, slots=True)
class FacilityConfig:
    facility_id: str
    name: str


@dataclass(frozen=True, slots=True)
class DimensionConfig:
    zone_count: int
    item_count: int
    selector_count: int
    replenisher_count: int
    qa_operator_count: int
    shift_count: int


@dataclass(frozen=True, slots=True)
class StorageConfig:
    database_path: Path
    ground_truth_directory: Path
    export_directory: Path


@dataclass(frozen=True, slots=True)
class OperationsConfig:
    trip_count: int = 120
    pick_lines_per_trip_min: int = 6
    pick_lines_per_trip_max: int = 10
    short_probability: float = 0.005
    qa_event_count: int = 8
    damage_event_count: int = 3
    adjustment_count: int = 4
    system_event_count: int = 4


@dataclass(frozen=True, slots=True)
class ReplenishmentGapConfig:
    enabled: bool = False
    target_item_count: int = 6
    forced_short_count: int = 28
    recovery_adjustment_count: int = 8


@dataclass(frozen=True, slots=True)
class QaMaskingConfig:
    enabled: bool = False
    event_count: int = 10
    generic_adjustment_count: int = 10


@dataclass(frozen=True, slots=True)
class SelectorFalseLeadConfig:
    enabled: bool = False
    exposure_trip_count: int = 28


@dataclass(frozen=True, slots=True)
class FailuresConfig:
    replenishment_gap: ReplenishmentGapConfig = ReplenishmentGapConfig()
    qa_masking: QaMaskingConfig = QaMaskingConfig()
    selector_false_lead: SelectorFalseLeadConfig = SelectorFalseLeadConfig()

    @property
    def any_enabled(self) -> bool:
        return (
            self.replenishment_gap.enabled
            or self.qa_masking.enabled
            or self.selector_false_lead.enabled
        )


@dataclass(frozen=True, slots=True)
class ProjectConfig:
    run: RunConfig
    facility: FacilityConfig
    dimensions: DimensionConfig
    storage: StorageConfig
    operations: OperationsConfig = OperationsConfig()
    failures: FailuresConfig = FailuresConfig()

    @property
    def configuration_hash(self) -> str:
        return hash_project_config(self)


def load_project_config(path: str | Path) -> ProjectConfig:
    """Load and validate a TOML project configuration file."""

    config_path = Path(path)
    try:
        with config_path.open("rb") as config_file:
            raw_config = tomllib.load(config_file)
    except FileNotFoundError as exc:
        raise ConfigurationError(f"Configuration file not found: {config_path}") from exc
    except tomllib.TOMLDecodeError as exc:
        raise ConfigurationError(f"Invalid TOML in {config_path}: {exc}") from exc

    return parse_project_config(raw_config)


def parse_project_config(raw_config: Mapping[str, Any]) -> ProjectConfig:
    """Validate raw TOML data and return immutable configuration objects."""

    if not isinstance(raw_config, Mapping):
        raise ConfigurationError("Configuration root must be a TOML table.")

    _reject_unknown_sections(raw_config)
    run_section = _section(raw_config, "run")
    facility_section = _section(raw_config, "facility")
    dimension_section = _section(raw_config, "dimensions")
    storage_section = _section(raw_config, "storage")
    operations_section = _optional_section(raw_config, "operations")
    failures_section = _optional_section(raw_config, "failures")

    timezone_name = _required_str(run_section, "run", "facility_timezone")
    timezone = _parse_timezone(timezone_name)
    start_utc = _required_local_datetime(run_section, "run", "start_local", timezone)
    end_utc = _required_local_datetime(run_section, "run", "end_local", timezone)
    if start_utc >= end_utc:
        raise ConfigurationError("run.start_local must be before run.end_local.")

    scenario_name = _required_str(run_section, "run", "scenario_name")
    if not _SCENARIO_RE.fullmatch(scenario_name):
        raise ConfigurationError(
            "run.scenario_name must start with a lowercase letter and contain only "
            "lowercase letters, digits, underscores, or hyphens."
        )

    scenario_version = _required_str(run_section, "run", "scenario_version")
    if not _SEMVER_RE.fullmatch(scenario_version):
        raise ConfigurationError("run.scenario_version must use semantic version format.")

    seed = _required_int(run_section, "run", "seed")
    if seed < 0:
        raise ConfigurationError("run.seed must be nonnegative.")

    facility_id = _required_str(facility_section, "facility", "facility_id")
    if not _STABLE_ID_RE.fullmatch(facility_id):
        raise ConfigurationError(
            "facility.facility_id must contain only uppercase letters, digits, "
            "underscores, or hyphens."
        )

    facility_name = _required_str(facility_section, "facility", "name")

    return ProjectConfig(
        run=RunConfig(
            scenario_name=scenario_name,
            scenario_version=scenario_version,
            seed=seed,
            start_utc=start_utc,
            end_utc=end_utc,
            facility_timezone=timezone_name,
        ),
        facility=FacilityConfig(
            facility_id=facility_id,
            name=facility_name,
        ),
        dimensions=DimensionConfig(
            zone_count=_required_positive_int(dimension_section, "dimensions", "zone_count"),
            item_count=_required_positive_int(dimension_section, "dimensions", "item_count"),
            selector_count=_required_positive_int(
                dimension_section, "dimensions", "selector_count"
            ),
            replenisher_count=_required_positive_int(
                dimension_section, "dimensions", "replenisher_count"
            ),
            qa_operator_count=_required_positive_int(
                dimension_section, "dimensions", "qa_operator_count"
            ),
            shift_count=_required_positive_int(dimension_section, "dimensions", "shift_count"),
        ),
        storage=StorageConfig(
            database_path=_required_path(storage_section, "storage", "database_path"),
            ground_truth_directory=_required_path(
                storage_section, "storage", "ground_truth_directory"
            ),
            export_directory=_required_path(storage_section, "storage", "export_directory"),
        ),
        operations=_parse_operations_config(operations_section),
        failures=_parse_failures_config(failures_section),
    )


def canonical_project_config(config: ProjectConfig) -> dict[str, Any]:
    """Return a stable serializable representation for hashing and provenance."""

    return {
        "dimensions": {
            "item_count": config.dimensions.item_count,
            "qa_operator_count": config.dimensions.qa_operator_count,
            "replenisher_count": config.dimensions.replenisher_count,
            "selector_count": config.dimensions.selector_count,
            "shift_count": config.dimensions.shift_count,
            "zone_count": config.dimensions.zone_count,
        },
        "facility": {
            "facility_id": config.facility.facility_id,
            "name": config.facility.name,
        },
        "run": {
            "end_utc": _iso_utc(config.run.end_utc),
            "facility_timezone": config.run.facility_timezone,
            "scenario_name": config.run.scenario_name,
            "scenario_version": config.run.scenario_version,
            "seed": config.run.seed,
            "start_utc": _iso_utc(config.run.start_utc),
        },
        "storage": {
            "database_path": config.storage.database_path.as_posix(),
            "export_directory": config.storage.export_directory.as_posix(),
            "ground_truth_directory": config.storage.ground_truth_directory.as_posix(),
        },
        "operations": {
            "adjustment_count": config.operations.adjustment_count,
            "damage_event_count": config.operations.damage_event_count,
            "pick_lines_per_trip_max": config.operations.pick_lines_per_trip_max,
            "pick_lines_per_trip_min": config.operations.pick_lines_per_trip_min,
            "qa_event_count": config.operations.qa_event_count,
            "short_probability": config.operations.short_probability,
            "system_event_count": config.operations.system_event_count,
            "trip_count": config.operations.trip_count,
        },
        "failures": {
            "qa_masking": {
                "enabled": config.failures.qa_masking.enabled,
                "event_count": config.failures.qa_masking.event_count,
                "generic_adjustment_count": (config.failures.qa_masking.generic_adjustment_count),
            },
            "replenishment_gap": {
                "enabled": config.failures.replenishment_gap.enabled,
                "forced_short_count": config.failures.replenishment_gap.forced_short_count,
                "recovery_adjustment_count": (
                    config.failures.replenishment_gap.recovery_adjustment_count
                ),
                "target_item_count": config.failures.replenishment_gap.target_item_count,
            },
            "selector_false_lead": {
                "enabled": config.failures.selector_false_lead.enabled,
                "exposure_trip_count": config.failures.selector_false_lead.exposure_trip_count,
            },
        },
    }


def hash_project_config(config: ProjectConfig) -> str:
    """Return the SHA-256 hash of the canonical configuration."""

    canonical_bytes = json.dumps(
        canonical_project_config(config),
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(canonical_bytes).hexdigest()


def _reject_unknown_sections(raw_config: Mapping[str, Any]) -> None:
    unknown_sections = sorted(set(raw_config) - set(_EXPECTED_SECTIONS))
    if unknown_sections:
        joined = ", ".join(unknown_sections)
        raise ConfigurationError(f"Unknown top-level configuration section(s): {joined}.")


def _section(raw_config: Mapping[str, Any], section_name: str) -> Mapping[str, Any]:
    if section_name not in raw_config:
        raise ConfigurationError(f"Missing required configuration section: {section_name}.")
    section = raw_config[section_name]
    if not isinstance(section, Mapping):
        raise ConfigurationError(f"Configuration section {section_name} must be a table.")

    missing_keys = sorted(_EXPECTED_SECTIONS[section_name] - set(section))
    if missing_keys:
        joined = ", ".join(missing_keys)
        raise ConfigurationError(f"Missing required key(s) in {section_name}: {joined}.")

    unknown_keys = sorted(set(section) - _EXPECTED_SECTIONS[section_name])
    if unknown_keys:
        joined = ", ".join(unknown_keys)
        raise ConfigurationError(f"Unknown key(s) in {section_name}: {joined}.")

    return section


def _optional_section(raw_config: Mapping[str, Any], section_name: str) -> Mapping[str, Any]:
    if section_name not in raw_config:
        return {}
    section = raw_config[section_name]
    if not isinstance(section, Mapping):
        raise ConfigurationError(f"Configuration section {section_name} must be a table.")
    unknown_keys = sorted(set(section) - _EXPECTED_SECTIONS[section_name])
    if unknown_keys:
        joined = ", ".join(unknown_keys)
        raise ConfigurationError(f"Unknown key(s) in {section_name}: {joined}.")
    return section


def _parse_failures_config(section: Mapping[str, Any]) -> FailuresConfig:
    if not section:
        return FailuresConfig()
    for pattern_name, pattern_value in section.items():
        if not isinstance(pattern_value, Mapping):
            raise ConfigurationError(f"failures.{pattern_name} must be a table.")
        unknown_keys = sorted(set(pattern_value) - _FAILURE_SECTION_KEYS[pattern_name])
        if unknown_keys:
            joined = ", ".join(unknown_keys)
            raise ConfigurationError(f"Unknown key(s) in failures.{pattern_name}: {joined}.")

    replenishment_defaults = ReplenishmentGapConfig()
    qa_defaults = QaMaskingConfig()
    selector_defaults = SelectorFalseLeadConfig()
    replenishment_section = section.get("replenishment_gap", {})
    qa_section = section.get("qa_masking", {})
    selector_section = section.get("selector_false_lead", {})
    return FailuresConfig(
        replenishment_gap=ReplenishmentGapConfig(
            enabled=_optional_bool(
                replenishment_section,
                "failures.replenishment_gap",
                "enabled",
                replenishment_defaults.enabled,
            ),
            target_item_count=_optional_positive_int(
                replenishment_section,
                "failures.replenishment_gap",
                "target_item_count",
                replenishment_defaults.target_item_count,
            ),
            forced_short_count=_optional_positive_int(
                replenishment_section,
                "failures.replenishment_gap",
                "forced_short_count",
                replenishment_defaults.forced_short_count,
            ),
            recovery_adjustment_count=_optional_nonnegative_int(
                replenishment_section,
                "failures.replenishment_gap",
                "recovery_adjustment_count",
                replenishment_defaults.recovery_adjustment_count,
            ),
        ),
        qa_masking=QaMaskingConfig(
            enabled=_optional_bool(
                qa_section,
                "failures.qa_masking",
                "enabled",
                qa_defaults.enabled,
            ),
            event_count=_optional_positive_int(
                qa_section,
                "failures.qa_masking",
                "event_count",
                qa_defaults.event_count,
            ),
            generic_adjustment_count=_optional_positive_int(
                qa_section,
                "failures.qa_masking",
                "generic_adjustment_count",
                qa_defaults.generic_adjustment_count,
            ),
        ),
        selector_false_lead=SelectorFalseLeadConfig(
            enabled=_optional_bool(
                selector_section,
                "failures.selector_false_lead",
                "enabled",
                selector_defaults.enabled,
            ),
            exposure_trip_count=_optional_positive_int(
                selector_section,
                "failures.selector_false_lead",
                "exposure_trip_count",
                selector_defaults.exposure_trip_count,
            ),
        ),
    )


def _parse_operations_config(section: Mapping[str, Any]) -> OperationsConfig:
    defaults = OperationsConfig()
    trip_count = _optional_positive_int(section, "operations", "trip_count", defaults.trip_count)
    min_lines = _optional_positive_int(
        section,
        "operations",
        "pick_lines_per_trip_min",
        defaults.pick_lines_per_trip_min,
    )
    max_lines = _optional_positive_int(
        section,
        "operations",
        "pick_lines_per_trip_max",
        defaults.pick_lines_per_trip_max,
    )
    if min_lines > max_lines:
        raise ConfigurationError(
            "operations.pick_lines_per_trip_min must be less than or equal to "
            "operations.pick_lines_per_trip_max."
        )
    short_probability = _optional_probability(
        section, "operations", "short_probability", defaults.short_probability
    )
    return OperationsConfig(
        trip_count=trip_count,
        pick_lines_per_trip_min=min_lines,
        pick_lines_per_trip_max=max_lines,
        short_probability=short_probability,
        qa_event_count=_optional_nonnegative_int(
            section, "operations", "qa_event_count", defaults.qa_event_count
        ),
        damage_event_count=_optional_nonnegative_int(
            section, "operations", "damage_event_count", defaults.damage_event_count
        ),
        adjustment_count=_optional_nonnegative_int(
            section, "operations", "adjustment_count", defaults.adjustment_count
        ),
        system_event_count=_optional_nonnegative_int(
            section, "operations", "system_event_count", defaults.system_event_count
        ),
    )


def _required_str(section: Mapping[str, Any], section_name: str, key: str) -> str:
    value = section[key]
    if not isinstance(value, str) or not value.strip():
        raise ConfigurationError(f"{section_name}.{key} must be a nonempty string.")
    return value.strip()


def _required_path(section: Mapping[str, Any], section_name: str, key: str) -> Path:
    return Path(_required_str(section, section_name, key))


def _required_int(section: Mapping[str, Any], section_name: str, key: str) -> int:
    value = section[key]
    if not isinstance(value, int) or isinstance(value, bool):
        raise ConfigurationError(f"{section_name}.{key} must be an integer.")
    return value


def _optional_positive_int(
    section: Mapping[str, Any], section_name: str, key: str, default: int
) -> int:
    if key not in section:
        return default
    value = _required_int(section, section_name, key)
    if value <= 0:
        raise ConfigurationError(f"{section_name}.{key} must be positive.")
    return value


def _optional_nonnegative_int(
    section: Mapping[str, Any], section_name: str, key: str, default: int
) -> int:
    if key not in section:
        return default
    value = _required_int(section, section_name, key)
    if value < 0:
        raise ConfigurationError(f"{section_name}.{key} must be nonnegative.")
    return value


def _optional_probability(
    section: Mapping[str, Any], section_name: str, key: str, default: float
) -> float:
    if key not in section:
        return default
    value = section[key]
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ConfigurationError(f"{section_name}.{key} must be numeric.")
    parsed = float(value)
    if parsed < 0.0 or parsed > 1.0:
        raise ConfigurationError(f"{section_name}.{key} must be between 0 and 1.")
    return parsed


def _optional_bool(section: Mapping[str, Any], section_name: str, key: str, default: bool) -> bool:
    if key not in section:
        return default
    value = section[key]
    if not isinstance(value, bool):
        raise ConfigurationError(f"{section_name}.{key} must be true or false.")
    return value


def _required_positive_int(section: Mapping[str, Any], section_name: str, key: str) -> int:
    value = _required_int(section, section_name, key)
    if value <= 0:
        raise ConfigurationError(f"{section_name}.{key} must be positive.")
    return value


def _parse_timezone(timezone_name: str) -> ZoneInfo:
    try:
        return ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError as exc:
        raise ConfigurationError(f"run.facility_timezone is not valid: {timezone_name}.") from exc


def _required_local_datetime(
    section: Mapping[str, Any],
    section_name: str,
    key: str,
    timezone: ZoneInfo,
) -> datetime:
    raw_value = _required_str(section, section_name, key)
    try:
        parsed = datetime.fromisoformat(raw_value)
    except ValueError as exc:
        raise ConfigurationError(f"{section_name}.{key} must be an ISO 8601 datetime.") from exc

    if parsed.tzinfo is not None:
        raise ConfigurationError(
            f"{section_name}.{key} must be a local wall-clock datetime without an offset."
        )

    aware_local = parsed.replace(tzinfo=timezone)
    utc_value = aware_local.astimezone(UTC)
    local_round_trip = utc_value.astimezone(timezone).replace(tzinfo=None)
    if local_round_trip != parsed:
        raise ConfigurationError(f"{section_name}.{key} is not valid in {timezone.key}.")
    return utc_value


def _iso_utc(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")
