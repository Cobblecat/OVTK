"""Deterministic, atomic CSV exports for schema-3 read models."""

from __future__ import annotations

import csv
import hashlib
import os
import sqlite3
import tempfile
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path

from operational_variance_toolkit.errors import DataValidationError, OutputExistsError
from operational_variance_toolkit.wms.application.inquiry import validate_transaction_filters
from operational_variance_toolkit.wms.domain.inquiry import ExportResult
from operational_variance_toolkit.wms.domain.reports import ReportResult
from operational_variance_toolkit.wms.storage.inquiry import (
    INVENTORY_COLUMNS,
    ITEM_COLUMNS,
    LOCATION_COLUMNS,
    TRANSACTION_COLUMNS,
    WmsInquiryRepository,
)

_DATASET_COLUMNS = {
    "item-master": ITEM_COLUMNS,
    "location-master": LOCATION_COLUMNS,
    "inventory-master": INVENTORY_COLUMNS,
}


def export_master_csv(
    connection: sqlite3.Connection, dataset: str, output_path: str | Path
) -> ExportResult:
    columns = _DATASET_COLUMNS.get(dataset)
    if columns is None:
        raise DataValidationError(f"Unsupported export dataset: {dataset}")
    repository = _readonly_repository(connection)
    rows = repository.export_rows(dataset)
    return write_csv_atomic(output_path, columns, rows)


def export_transactions_csv(
    connection: sqlite3.Connection,
    output_path: str | Path,
    filters: Mapping[str, str],
) -> ExportResult:
    clean = validate_transaction_filters(filters)
    rows = _readonly_repository(connection).transactions(clean)
    return write_csv_atomic(output_path, TRANSACTION_COLUMNS, rows)


def export_report_result(result: ReportResult, output_path: str | Path) -> ExportResult:
    return write_csv_atomic(output_path, result.spec.display_columns, result.rows)


def write_csv_atomic(
    output_path: str | Path,
    columns: Sequence[str],
    rows: Iterable[Sequence[object]],
) -> ExportResult:
    """Create a CSV without overwriting and promote one complete temporary file."""

    path = Path(output_path).resolve()
    if path.exists():
        raise OutputExistsError(f"CSV output already exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    materialized = tuple(tuple(row) for row in rows)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="",
            prefix=f".{path.name}.",
            suffix=".tmp",
            dir=path.parent,
            delete=False,
        ) as handle:
            temporary_path = Path(handle.name)
            writer = csv.writer(handle, lineterminator="\n")
            writer.writerow(columns)
            for row in materialized:
                writer.writerow(
                    _spreadsheet_safe_value(column, value)
                    for column, value in zip(columns, row, strict=True)
                )
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temporary_path, path)
        except FileExistsError as exc:
            raise OutputExistsError(f"CSV output already exists: {path}") from exc
        temporary_path.unlink()
        temporary_path = None
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
    return ExportResult(
        path=path,
        row_count=len(materialized),
        sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
    )


def _spreadsheet_safe_value(column: str, value: object) -> object:
    if not isinstance(value, str) or not value.startswith(("=", "+", "-", "@")):
        return value
    normalized = column.lower().replace(" ", "_")
    if normalized.endswith("_id") or normalized in {
        "item_id",
        "location_id",
        "source_reference",
        "transaction_group",
        "snapshot_batch",
    }:
        return value
    return f"'{value}"


def _readonly_repository(connection: sqlite3.Connection) -> WmsInquiryRepository:
    repository = WmsInquiryRepository(connection)
    if not repository.query_only_enabled():
        raise DataValidationError("CSV exports require a query-only connection")
    return repository
