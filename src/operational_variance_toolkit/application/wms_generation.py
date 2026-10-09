"""Schema-3 baseline generation workflow."""

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
    ToolkitError,
)
from operational_variance_toolkit.simulation.baseline import (
    BaselineGenerationCounts,
    run_baseline_protocol,
)
from operational_variance_toolkit.simulation.read_model import SimulationReadModel
from operational_variance_toolkit.storage.database import (
    connect_database,
    remove_database_artifacts,
)
from operational_variance_toolkit.validation.result import ValidationResult
from operational_variance_toolkit.validation.wms import validate_wms_dataset
from operational_variance_toolkit.wms.application.initialize import initialize_wms_foundation
from operational_variance_toolkit.wms.application.service import WmsService
from operational_variance_toolkit.wms.storage.repositories import (
    WmsFoundationRepository,
    WmsRunMetadata,
)


@dataclass(frozen=True, slots=True)
class GenerateWmsBaselineResult:
    database_path: Path
    run_metadata: WmsRunMetadata
    config_hash: str
    table_counts: dict[str, int]
    operation_counts: BaselineGenerationCounts
    validation: ValidationResult
    physical_recorded_equal: bool


def generate_wms_baseline(
    config_path: str | Path,
    output_path: str | Path,
    *,
    generated_at_utc: datetime | None = None,
) -> GenerateWmsBaselineResult:
    """Generate a fresh scenario-free schema-3 baseline through WMS commands."""

    config = load_project_config(config_path)
    if config.failures.any_enabled:
        raise ConfigurationError(
            "Schema-3 baseline generation requires all failure controls disabled"
        )
    database_path = Path(output_path)
    created_path: Path | None = None
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
            driver_result = run_baseline_protocol(
                config,
                initialized.run_metadata.run_id,
                inputs,
                WmsService(connection),
            )
            physical_recorded_equal = (
                driver_result.physical_quantities
                == read_model.recorded_quantities(initialized.run_metadata.run_id)
            )
            if not physical_recorded_equal:
                raise DataValidationError(
                    "Baseline physical and recorded closing quantities differ"
                )
            validation = validate_wms_dataset(connection)
            if not validation.passed:
                details = "; ".join(issue.message for issue in validation.hard_failures[:3])
                raise DataValidationError(
                    f"Generated schema-3 baseline failed validation: {details}"
                )
            repository = WmsFoundationRepository(connection)
            metadata = repository.run_metadata()
            counts = repository.table_counts()
        return GenerateWmsBaselineResult(
            database_path=created_path,
            run_metadata=metadata,
            config_hash=config.configuration_hash,
            table_counts=counts,
            operation_counts=driver_result.counts,
            validation=validation,
            physical_recorded_equal=physical_recorded_equal,
        )
    except Exception as exc:
        if created_path is not None:
            remove_database_artifacts(created_path)
        if isinstance(exc, ToolkitError):
            raise
        if isinstance(exc, sqlite3.DatabaseError):
            raise DatabaseError(
                f"Failed while generating schema-3 baseline at {database_path}: {exc}"
            ) from exc
        raise


def canonical_wms_content(
    database_path: str | Path,
) -> dict[str, list[tuple[object, ...]]]:
    """Return deterministic WMS content excluding execution timestamps."""

    with closing(connect_database(database_path)) as connection:
        return WmsFoundationRepository(connection).canonical_wms_rows()
