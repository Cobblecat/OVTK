"""Version-routed dataset validation."""

from __future__ import annotations

import sqlite3

from operational_variance_toolkit.sandbox.storage import validate_sandbox_extension
from operational_variance_toolkit.storage.repositories import Phase1DatasetRepository
from operational_variance_toolkit.validation.phase1 import validate_phase1_dataset
from operational_variance_toolkit.validation.phase2 import validate_phase2_dataset
from operational_variance_toolkit.validation.result import ValidationIssue, ValidationResult
from operational_variance_toolkit.validation.wms import validate_wms_dataset


def validate_dataset(connection: sqlite3.Connection) -> ValidationResult:
    """Validate a supported analyst-facing dataset by stored schema version."""

    repository = Phase1DatasetRepository(connection)
    try:
        user_version = repository.user_version()
    except sqlite3.DatabaseError:
        return ValidationResult((ValidationIssue("schema", "Unable to read schema version"),))

    if user_version == 1:
        return validate_phase1_dataset(connection)
    if user_version == 2:
        return validate_phase2_dataset(connection)
    if user_version == 3:
        return validate_wms_dataset(connection)
    if user_version == 4:
        wms = validate_wms_dataset(connection, allow_sandbox=True)
        sandbox = validate_sandbox_extension(connection)
        return ValidationResult(
            wms.hard_failures + sandbox.hard_failures,
            wms.warnings + sandbox.warnings,
        )
    return ValidationResult(
        (ValidationIssue("schema", f"Unsupported SQLite user_version: {user_version}"),)
    )
