"""Phase 2 dataset validation."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterable

from operational_variance_toolkit.storage.repositories import PHASE2_TABLES, Phase1DatasetRepository
from operational_variance_toolkit.storage.schema import PHASE2_SCHEMA_VERSION
from operational_variance_toolkit.validation.result import ValidationIssue, ValidationResult

_REQUIRED_COLUMNS: dict[str, set[str]] = {
    "trip": {
        "run_id",
        "trip_id",
        "shift_id",
        "selector_id",
        "assigned_zone_id",
        "start_utc",
        "end_utc",
        "planned_pick_lines",
        "planned_cases",
    },
    "pick_event": {
        "run_id",
        "pick_event_id",
        "event_sequence",
        "trip_id",
        "selector_id",
        "item_id",
        "pick_location_id",
        "event_utc",
        "recorded_utc",
        "requested_qty_cases",
        "picked_qty_cases",
        "short_qty_cases",
        "system_qty_before_cases",
        "system_qty_after_cases",
        "eligible_pick_flag",
    },
    "replenishment_task": {
        "run_id",
        "replenishment_task_id",
        "event_sequence",
        "item_id",
        "source_location_id",
        "destination_location_id",
        "created_utc",
        "recorded_utc",
        "requested_qty_cases",
        "confirmed_qty_cases",
        "status",
    },
    "qa_event": {
        "run_id",
        "qa_event_id",
        "event_sequence",
        "item_id",
        "location_id",
        "event_type",
        "occurred_utc",
        "recorded_utc",
        "qty_affected_cases",
        "reason_code",
        "disposition_code",
    },
    "inventory_adjustment": {
        "run_id",
        "adjustment_id",
        "event_sequence",
        "item_id",
        "location_id",
        "effective_utc",
        "recorded_utc",
        "qty_delta_cases",
        "reason_code",
    },
    "system_event": {
        "run_id",
        "system_event_id",
        "event_sequence",
        "event_type",
        "start_utc",
        "end_utc",
        "severity_code",
        "recorded_utc",
    },
}


def validate_phase2_dataset(connection: sqlite3.Connection) -> ValidationResult:
    """Validate a Phase 2 analyst-facing baseline database."""

    repository = Phase1DatasetRepository(connection)
    failures: list[ValidationIssue] = []
    warnings: list[ValidationIssue] = []

    failures.extend(_validate_schema(repository))
    if failures:
        return ValidationResult(tuple(failures), tuple(warnings))

    failures.extend(_validate_metadata(repository))
    failures.extend(_validate_foreign_keys(repository))
    failures.extend(_issues_from_counts("required_values", repository.null_violations()))
    failures.extend(_issues_from_counts("master_data", repository.master_data_violations()))
    failures.extend(
        _issues_from_counts("opening_inventory", repository.opening_inventory_violations())
    )
    failures.extend(_issues_from_counts("transactions", repository.phase2_transaction_violations()))
    failures.extend(_validate_hidden_truth_leakage(repository))
    warnings.extend(_issues_from_counts("dataset", repository.phase2_count_warnings()))
    return ValidationResult(tuple(failures), tuple(warnings))


def _validate_schema(repository: Phase1DatasetRepository) -> list[ValidationIssue]:
    failures: list[ValidationIssue] = []
    table_names = repository.table_names()
    missing_tables = [table_name for table_name in PHASE2_TABLES if table_name not in table_names]
    if missing_tables:
        failures.append(
            ValidationIssue("schema", f"Missing required table(s): {', '.join(missing_tables)}")
        )
        return failures

    if repository.user_version() != 2:
        failures.append(
            ValidationIssue(
                "schema", f"Unsupported SQLite user_version: {repository.user_version()}"
            )
        )
    schema_versions = repository.schema_versions()
    if schema_versions != [PHASE2_SCHEMA_VERSION]:
        failures.append(
            ValidationIssue(
                "schema",
                f"Unsupported schema_metadata version(s): {', '.join(schema_versions) or 'none'}",
            )
        )

    for table_name, required_columns in _REQUIRED_COLUMNS.items():
        missing_columns = sorted(required_columns - repository.table_columns(table_name))
        if missing_columns:
            failures.append(
                ValidationIssue(
                    "schema",
                    f"{table_name} missing required column(s): {', '.join(missing_columns)}",
                )
            )
    return failures


def _validate_metadata(repository: Phase1DatasetRepository) -> list[ValidationIssue]:
    rows = repository.run_metadata_rows()
    if len(rows) != 1:
        return [
            ValidationIssue(
                "metadata", f"Expected exactly one simulation_run row, found {len(rows)}"
            )
        ]

    row = rows[0]
    failures: list[ValidationIssue] = []
    if row.schema_version != PHASE2_SCHEMA_VERSION:
        failures.append(
            ValidationIssue("metadata", f"Run schema_version is unsupported: {row.schema_version}")
        )
    if row.simulation_start_utc >= row.simulation_end_utc:
        failures.append(
            ValidationIssue("metadata", "simulation_start_utc must be before simulation_end_utc")
        )
    return failures


def _validate_foreign_keys(repository: Phase1DatasetRepository) -> list[ValidationIssue]:
    violations = repository.foreign_key_violations()
    if not violations:
        return []
    return [ValidationIssue("foreign_keys", f"Foreign-key violation(s): {len(violations)}")]


def _validate_hidden_truth_leakage(repository: Phase1DatasetRepository) -> list[ValidationIssue]:
    forbidden = ("true_root_cause", "is_injected_anomaly", "hidden", "physical_arrival")
    failures: list[ValidationIssue] = []
    for table_name in repository.table_names():
        leaked = sorted(
            column
            for column in repository.table_columns(table_name)
            if any(token in column.lower() for token in forbidden)
        )
        if leaked:
            failures.append(
                ValidationIssue(
                    "hidden_truth",
                    f"{table_name} contains forbidden analyst-facing column(s): "
                    f"{', '.join(leaked)}",
                )
            )
    return failures


def _issues_from_counts(
    category: str, violations: Iterable[tuple[str, int]]
) -> list[ValidationIssue]:
    return [
        ValidationIssue(category, f"{message}: {count} row(s)") for message, count in violations
    ]
