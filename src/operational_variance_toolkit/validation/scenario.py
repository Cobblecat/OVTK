"""Restricted scenario calibration checks for Phase 3."""

from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from operational_variance_toolkit.storage.database import connect_database
from operational_variance_toolkit.storage.ground_truth import read_ground_truth_artifact
from operational_variance_toolkit.validation.result import ValidationIssue, ValidationResult

_FORBIDDEN_TOKENS = (
    "is_anomaly",
    "is_injected",
    "target_selector",
    "true_root_cause",
    "failure_pattern",
    "hidden_arrival_time",
    "scenario_label",
    "ground_truth",
)


def validate_scenario_artifacts(
    database_path: str | Path,
    ground_truth_path: str | Path,
) -> ValidationResult:
    """Validate restricted Phase 3 scenario signatures."""

    ground_truth = read_ground_truth_artifact(ground_truth_path)
    failures: list[ValidationIssue] = []
    warnings: list[ValidationIssue] = []
    with connect_database(database_path) as connection:
        connection.row_factory = sqlite3.Row
        failures.extend(_validate_no_analyst_leakage(connection))
        failures.extend(_validate_ground_truth_references(connection, ground_truth))
        failures.extend(_validate_pattern_a(connection, ground_truth))
        failures.extend(_validate_pattern_b(connection, ground_truth))
        failures.extend(_validate_pattern_c(connection, ground_truth))
    return ValidationResult(tuple(failures), tuple(warnings))


def _validate_no_analyst_leakage(connection: sqlite3.Connection) -> list[ValidationIssue]:
    failures: list[ValidationIssue] = []
    table_rows = connection.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name"
    ).fetchall()
    for row in table_rows:
        table_name = str(row["name"])
        if _contains_forbidden(table_name):
            failures.append(ValidationIssue("leakage", f"Forbidden table name: {table_name}"))
        columns = [info["name"] for info in connection.execute(f"PRAGMA table_info({table_name})")]
        for column in columns:
            if _contains_forbidden(str(column)):
                failures.append(
                    ValidationIssue("leakage", f"Forbidden column name: {table_name}.{column}")
                )
        selected = ", ".join(columns)
        for value_row in connection.execute(f"SELECT {selected} FROM {table_name}").fetchall():
            for column in columns:
                value = value_row[column]
                if isinstance(value, str) and _contains_forbidden(value):
                    failures.append(
                        ValidationIssue(
                            "leakage",
                            f"Forbidden analyst-facing value in {table_name}.{column}",
                        )
                    )
                    return failures
    return failures


def _validate_ground_truth_references(
    connection: sqlite3.Connection, ground_truth: dict[str, Any]
) -> list[ValidationIssue]:
    failures: list[ValidationIssue] = []
    patterns = _patterns(ground_truth)
    reference_checks = (
        ("pick_event", "pick_event_id", patterns["replenishment_gap"]["affected_pick_event_ids"]),
        (
            "inventory_adjustment",
            "adjustment_id",
            patterns["replenishment_gap"]["recovery_adjustment_ids"],
        ),
        (
            "replenishment_task",
            "replenishment_task_id",
            patterns["replenishment_gap"].get("delayed_replenishment_task_ids", []),
        ),
        ("qa_event", "qa_event_id", patterns["qa_masking"]["qa_event_ids"]),
        (
            "inventory_adjustment",
            "adjustment_id",
            patterns["qa_masking"]["adjustment_ids"],
        ),
        ("trip", "trip_id", patterns["selector_false_lead"]["target_trip_ids"]),
        ("pick_event", "pick_event_id", patterns["selector_false_lead"]["target_pick_event_ids"]),
    )
    for table_name, id_column, values in reference_checks:
        for value in values:
            row = connection.execute(
                f"SELECT 1 FROM {table_name} WHERE {id_column} = ? LIMIT 1", (value,)
            ).fetchone()
            if row is None:
                failures.append(
                    ValidationIssue(
                        "ground_truth",
                        f"Ground-truth reference not found: {table_name}.{id_column}={value}",
                    )
                )
    return failures


def _validate_pattern_a(
    connection: sqlite3.Connection, ground_truth: dict[str, Any]
) -> list[ValidationIssue]:
    enabled = ground_truth.get("enabled_patterns", {}).get("replenishment_gap", False)
    if not enabled:
        return []
    pattern = _patterns(ground_truth)["replenishment_gap"]
    pick_ids = pattern["affected_pick_event_ids"]
    failures: list[ValidationIssue] = []
    if len(pick_ids) < 10:
        failures.append(ValidationIssue("pattern_a", "Too few affected replenishment-gap shorts"))
    total_picks = int(
        connection.execute("SELECT COUNT(*) AS count FROM pick_event").fetchone()["count"]
    )
    if len(pick_ids) >= total_picks // 2:
        failures.append(ValidationIssue("pattern_a", "Affected shorts are not a minority"))
    short_rows = _count_ids_with_condition(
        connection,
        "pick_event",
        "pick_event_id",
        pick_ids,
        "short_qty_cases > 0",
    )
    if short_rows != len(pick_ids):
        failures.append(ValidationIssue("pattern_a", "Affected pick IDs must all be shorts"))
    if not pattern["recovery_adjustment_ids"]:
        failures.append(ValidationIssue("pattern_a", "Missing later recovery adjustment evidence"))
    delayed_tasks = pattern.get("delayed_replenishment_task_ids", [])
    if _schema_version(connection) == 3 and not delayed_tasks:
        failures.append(
            ValidationIssue("pattern_a", "Missing delayed physical replenishment evidence")
        )
    if delayed_tasks:
        confirmed = _count_ids_with_condition(
            connection,
            "replenishment_task",
            "replenishment_task_id",
            delayed_tasks,
            "status = 'CONFIRMED'",
        )
        if confirmed != len(delayed_tasks):
            failures.append(
                ValidationIssue(
                    "pattern_a", "Delayed replenishments must be ordinary confirmed tasks"
                )
            )
    if _schema_version(connection) == 3:
        failures.extend(_validate_pattern_a_timing(connection, pattern, delayed_tasks))
    return failures


def _validate_pattern_a_timing(
    connection: sqlite3.Connection,
    pattern: dict[str, Any],
    delayed_tasks: list[str],
) -> list[ValidationIssue]:
    evidence_rows = pattern.get("timing_evidence", [])
    if len(evidence_rows) != len(delayed_tasks):
        return [ValidationIssue("pattern_a", "Delayed replenishment timing evidence is incomplete")]
    failures: list[ValidationIssue] = []
    for evidence in evidence_rows:
        task_id = evidence.get("replenishment_task_id")
        confirmed_utc = evidence.get("wms_confirmed_utc")
        physical_utc = evidence.get("physical_completed_utc")
        if task_id not in delayed_tasks or not confirmed_utc or not physical_utc:
            failures.append(
                ValidationIssue("pattern_a", "Invalid delayed replenishment timing evidence")
            )
            break
        task = connection.execute(
            "SELECT confirmed_utc FROM replenishment_task WHERE replenishment_task_id = ?",
            (task_id,),
        ).fetchone()
        if task is None or task["confirmed_utc"] != confirmed_utc:
            failures.append(
                ValidationIssue("pattern_a", "Truth confirmation time must match the WMS task")
            )
            break
        if _parse_utc(confirmed_utc) >= _parse_utc(physical_utc):
            failures.append(
                ValidationIssue(
                    "pattern_a", "Physical replenishment must follow recorded confirmation"
                )
            )
            break
    return failures


def _validate_pattern_b(
    connection: sqlite3.Connection, ground_truth: dict[str, Any]
) -> list[ValidationIssue]:
    enabled = ground_truth.get("enabled_patterns", {}).get("qa_masking", False)
    if not enabled:
        return []
    pattern = _patterns(ground_truth)["qa_masking"]
    failures: list[ValidationIssue] = []
    if len(pattern["qa_event_ids"]) < 5 or len(pattern["adjustment_ids"]) < 5:
        failures.append(ValidationIssue("pattern_b", "Too few masked QA/adjustment links"))
    for qa_id, adjustment_id in zip(
        pattern["qa_event_ids"], pattern["adjustment_ids"], strict=False
    ):
        row = connection.execute(
            """
            SELECT q.occurred_utc, ia.effective_utc, ia.reason_code, ia.qty_delta_cases
            FROM qa_event AS q
            JOIN inventory_adjustment AS ia ON ia.adjustment_id = ?
            WHERE q.qa_event_id = ?
            """,
            (adjustment_id, qa_id),
        ).fetchone()
        if row is None or row["occurred_utc"] >= row["effective_utc"]:
            failures.append(ValidationIssue("pattern_b", "QA must precede masked adjustment"))
            break
        if row["reason_code"] != "COUNT_CORRECTION" or int(row["qty_delta_cases"]) >= 0:
            failures.append(
                ValidationIssue("pattern_b", "Masked adjustment must be generic and negative")
            )
            break
    return failures


def _validate_pattern_c(
    connection: sqlite3.Connection, ground_truth: dict[str, Any]
) -> list[ValidationIssue]:
    enabled = ground_truth.get("enabled_patterns", {}).get("selector_false_lead", False)
    if not enabled:
        return []
    pattern = _patterns(ground_truth)["selector_false_lead"]
    target_selector_id = pattern["target_selector_id"]
    failures: list[ValidationIssue] = []
    if not target_selector_id:
        return [ValidationIssue("pattern_c", "Missing target selector")]
    rows = connection.execute(
        """
        SELECT selector_id, SUM(short_qty_cases) AS shorts, COUNT(*) AS picks
        FROM pick_event
        GROUP BY selector_id
        ORDER BY shorts DESC, picks DESC, selector_id
        """
    ).fetchall()
    rank = next(
        (
            index
            for index, row in enumerate(rows, start=1)
            if row["selector_id"] == target_selector_id
        ),
        None,
    )
    if rank is None or rank > 2:
        failures.append(ValidationIssue("pattern_c", "Target selector is not a raw short leader"))
    if len(pattern["target_trip_ids"]) < 10 or len(pattern["target_pick_event_ids"]) < 10:
        failures.append(ValidationIssue("pattern_c", "Target selector exposure is too small"))
    return failures


def _patterns(ground_truth: dict[str, Any]) -> dict[str, Any]:
    patterns = ground_truth.get("patterns")
    if not isinstance(patterns, dict):
        return {
            "qa_masking": {"adjustment_ids": [], "qa_event_ids": []},
            "replenishment_gap": {
                "affected_pick_event_ids": [],
                "recovery_adjustment_ids": [],
            },
            "selector_false_lead": {
                "target_pick_event_ids": [],
                "target_selector_id": None,
                "target_trip_ids": [],
            },
        }
    return patterns


def _count_ids_with_condition(
    connection: sqlite3.Connection,
    table_name: str,
    id_column: str,
    ids: list[str],
    condition: str,
) -> int:
    if not ids:
        return 0
    placeholders = ", ".join("?" for _ in ids)
    row = connection.execute(
        f"""
        SELECT COUNT(*) AS count
        FROM {table_name}
        WHERE {id_column} IN ({placeholders}) AND {condition}
        """,
        tuple(ids),
    ).fetchone()
    return int(row["count"])


def _contains_forbidden(value: str) -> bool:
    lowered = value.lower()
    return any(token in lowered for token in _FORBIDDEN_TOKENS)


def _schema_version(connection: sqlite3.Connection) -> int:
    return int(connection.execute("PRAGMA user_version").fetchone()[0])


def _parse_utc(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))
