"""Schema-3 investigation generation through external scenario policy."""

from __future__ import annotations

import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from operational_variance_toolkit.config import load_project_config
from operational_variance_toolkit.errors import (
    ConfigurationError,
    DatabaseError,
    DataValidationError,
    OutputExistsError,
    ToolkitError,
)
from operational_variance_toolkit.scenarios.investigation import InvestigationPolicy
from operational_variance_toolkit.simulation.baseline import (
    BaselineGenerationCounts,
    run_baseline_protocol,
)
from operational_variance_toolkit.simulation.read_model import SimulationReadModel
from operational_variance_toolkit.storage.database import (
    connect_database,
    remove_database_artifacts,
)
from operational_variance_toolkit.storage.ground_truth import write_ground_truth_artifact
from operational_variance_toolkit.validation.result import ValidationResult
from operational_variance_toolkit.validation.scenario import validate_scenario_artifacts
from operational_variance_toolkit.validation.wms import validate_wms_dataset
from operational_variance_toolkit.wms.application.initialize import initialize_wms_foundation
from operational_variance_toolkit.wms.application.service import WmsService
from operational_variance_toolkit.wms.storage.repositories import (
    WmsFoundationRepository,
    WmsRunMetadata,
)


@dataclass(frozen=True, slots=True)
class GenerateWmsInvestigationResult:
    database_path: Path
    ground_truth_path: Path
    run_metadata: WmsRunMetadata
    config_hash: str
    table_counts: dict[str, int]
    operation_counts: BaselineGenerationCounts
    validation: ValidationResult
    scenario_validation: ValidationResult
    physical_recorded_equal: bool


def generate_wms_investigation(
    config_path: str | Path,
    output_path: str | Path,
    ground_truth_path: str | Path,
    *,
    generated_at_utc: datetime | None = None,
) -> GenerateWmsInvestigationResult:
    """Generate a fresh schema-3 investigation WMS and restricted truth artifact."""

    config = load_project_config(config_path)
    if not config.failures.any_enabled:
        raise ConfigurationError(
            "Schema-3 investigation generation requires enabled failure controls"
        )
    database_path = Path(output_path)
    truth_path = Path(ground_truth_path)
    if truth_path.exists():
        raise OutputExistsError(f"Ground-truth artifact already exists: {truth_path}")

    created_path: Path | None = None
    created_truth: Path | None = None
    try:
        initialized = initialize_wms_foundation(
            config_path,
            database_path,
            generated_at_utc=generated_at_utc,
        )
        created_path = initialized.database_path
        with closing(connect_database(created_path)) as connection:
            read_model = SimulationReadModel(connection)
            inputs = read_model.baseline_inputs(initialized.run_metadata.run_id)
            policy = InvestigationPolicy(config, inputs)
            driver_result = run_baseline_protocol(
                config,
                initialized.run_metadata.run_id,
                inputs,
                WmsService(connection),
                policy,
            )
            physical_recorded_equal = (
                driver_result.physical_quantities
                == read_model.recorded_quantities(initialized.run_metadata.run_id)
            )
            if not physical_recorded_equal:
                raise DataValidationError(
                    "Investigation physical and recorded closing quantities differ"
                )
            validation = validate_wms_dataset(connection)
            if not validation.passed:
                details = "; ".join(issue.message for issue in validation.hard_failures[:3])
                raise DataValidationError(
                    f"Generated schema-3 investigation failed validation: {details}"
                )
            repository = WmsFoundationRepository(connection)
            metadata = repository.run_metadata()
            counts = repository.table_counts()

        payload = {**policy.ground_truth(metadata.run_id, config.configuration_hash)}
        payload["table_counts"] = counts
        created_truth = write_ground_truth_artifact(truth_path, payload)
        scenario_validation = validate_scenario_artifacts(created_path, created_truth)
        if not scenario_validation.passed:
            details = "; ".join(issue.message for issue in scenario_validation.hard_failures[:3])
            raise DataValidationError(
                f"Generated schema-3 investigation failed scenario validation: {details}"
            )
        return GenerateWmsInvestigationResult(
            database_path=created_path,
            ground_truth_path=created_truth,
            run_metadata=metadata,
            config_hash=config.configuration_hash,
            table_counts=counts,
            operation_counts=driver_result.counts,
            validation=validation,
            scenario_validation=scenario_validation,
            physical_recorded_equal=physical_recorded_equal,
        )
    except Exception as exc:
        if created_path is not None:
            remove_database_artifacts(created_path)
        if created_truth is not None:
            _remove_file(created_truth)
        if isinstance(exc, ToolkitError):
            raise
        if isinstance(exc, sqlite3.DatabaseError):
            raise DatabaseError(
                f"Failed while generating schema-3 investigation at {database_path}: {exc}"
            ) from exc
        raise


def _remove_file(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except OSError as exc:
        raise DatabaseError(f"Failed to remove incomplete artifact: {path}") from exc
