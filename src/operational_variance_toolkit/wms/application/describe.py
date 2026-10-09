"""Factual schema-3 WMS description workflow."""

from __future__ import annotations

import sqlite3
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path

from operational_variance_toolkit.errors import DatabaseError, DataValidationError, ToolkitError
from operational_variance_toolkit.sandbox.storage import validate_sandbox_extension
from operational_variance_toolkit.storage.database import connect_readonly_database
from operational_variance_toolkit.validation.result import ValidationResult
from operational_variance_toolkit.validation.wms import validate_wms_dataset
from operational_variance_toolkit.wms.storage.repositories import (
    WmsFoundationRepository,
    WmsRunMetadata,
)


@dataclass(frozen=True, slots=True)
class DescribeWmsResult:
    database_path: Path
    run_metadata: WmsRunMetadata
    table_counts: dict[str, int]
    live_totals_by_zone: tuple[tuple[str, int], ...]
    snapshot_batches: tuple[tuple[str, str, str, int], ...]
    validation: ValidationResult


def describe_wms(database_path: str | Path) -> DescribeWmsResult:
    """Return neutral metadata and factual live/snapshot counts."""

    path = Path(database_path)
    try:
        with closing(connect_readonly_database(path)) as connection:
            repository = WmsFoundationRepository(connection)
            user_version = int(connection.execute("PRAGMA user_version").fetchone()[0])
            validation = validate_wms_dataset(connection, allow_sandbox=user_version == 4)
            if user_version == 4:
                extension = validate_sandbox_extension(connection)
                validation = ValidationResult(
                    validation.hard_failures + extension.hard_failures,
                    validation.warnings + extension.warnings,
                )
            if not validation.passed:
                raise DataValidationError("Cannot describe an invalid schema-3 WMS")
            return DescribeWmsResult(
                database_path=path.resolve(),
                run_metadata=repository.run_metadata(),
                table_counts=repository.table_counts(),
                live_totals_by_zone=repository.live_totals_by_zone(),
                snapshot_batches=repository.snapshot_batches(),
                validation=validation,
            )
    except ToolkitError:
        raise
    except sqlite3.DatabaseError as exc:
        raise DatabaseError(f"Unable to describe WMS database {path}: {exc}") from exc
