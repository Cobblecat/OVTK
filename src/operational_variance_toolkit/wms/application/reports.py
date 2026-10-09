"""Application workflow for factual schema-3 WMS reports."""

from __future__ import annotations

import sqlite3
from collections.abc import Mapping
from contextlib import closing
from datetime import UTC, date, datetime
from pathlib import Path
from types import MappingProxyType

from operational_variance_toolkit.errors import (
    DatabaseError,
    DataValidationError,
    ToolkitError,
)
from operational_variance_toolkit.sandbox.storage import validate_sandbox_extension
from operational_variance_toolkit.storage.database import connect_readonly_database
from operational_variance_toolkit.storage.schema import WMS_SCHEMA_VERSION
from operational_variance_toolkit.validation.result import ValidationResult
from operational_variance_toolkit.validation.wms import validate_wms_dataset
from operational_variance_toolkit.wms.application.export import export_report_result
from operational_variance_toolkit.wms.domain.reports import (
    REPORT_SPECS,
    ReportResult,
    ReportSpec,
)
from operational_variance_toolkit.wms.storage.reports import WmsReportRepository
from operational_variance_toolkit.wms.storage.repositories import WmsFoundationRepository


def available_reports() -> tuple[ReportSpec, ...]:
    """Return registered reports in stable display order."""

    return tuple(REPORT_SPECS.values())


def run_wms_report(
    database_path: str | Path,
    report_code: str,
    parameters: Mapping[str, str | None] | None = None,
    *,
    generated_at_utc: datetime | None = None,
) -> ReportResult:
    """Validate a schema-3 source and execute one registered read-only report."""

    path = Path(database_path)
    if not path.is_file():
        raise DatabaseError(f"Database does not exist: {path}")
    spec = REPORT_SPECS.get(report_code)
    if spec is None:
        raise DataValidationError(f"Unknown WMS report: {report_code}")
    clean_parameters = _validate_parameters(spec, parameters or {})
    generated_at = generated_at_utc or datetime.now(tz=UTC)
    if generated_at.tzinfo is None:
        raise DataValidationError("Report generated_at_utc must be timezone-aware")

    try:
        with closing(connect_readonly_database(path)) as connection:
            user_version = int(connection.execute("PRAGMA user_version").fetchone()[0])
            if user_version not in {3, 4}:
                raise DatabaseError(
                    f"WMS reports require schema {WMS_SCHEMA_VERSION} or a verified "
                    f"schema-3.1.0 sandbox: {path}"
                )
            validation = validate_wms_dataset(connection, allow_sandbox=user_version == 4)
            if user_version == 4:
                sandbox_validation = validate_sandbox_extension(connection)
                validation = ValidationResult(
                    validation.hard_failures + sandbox_validation.hard_failures,
                    validation.warnings + sandbox_validation.warnings,
                )
            if not validation.passed:
                messages = "; ".join(issue.message for issue in validation.hard_failures[:3])
                raise DataValidationError(f"WMS source validation failed: {messages}")
            metadata = WmsFoundationRepository(connection).run_metadata()
            as_of_utc = clean_parameters.get("as_of_utc", metadata.simulation_end_utc)
            if report_code == "code-date-inventory":
                as_of_utc = f"{clean_parameters['as_of_date']}T00:00:00Z"
            rows = WmsReportRepository(connection).rows(report_code, clean_parameters, as_of_utc)
            if rows and report_code == "inventory-snapshot":
                as_of_utc = str(rows[0][2])
            elif rows and report_code == "inventory-reconciliation":
                as_of_utc = str(rows[0][4])
    except ToolkitError:
        raise
    except sqlite3.DatabaseError as exc:
        raise DatabaseError(f"Unable to run WMS report against {path}: {exc}") from exc

    return ReportResult(
        spec=spec,
        database_path=path.resolve(),
        run_id=metadata.run_id,
        schema_version=metadata.schema_version,
        as_of_utc=as_of_utc,
        generated_at_utc=_iso_utc(generated_at),
        parameters=MappingProxyType(dict(clean_parameters)),
        rows=rows,
    )


def export_report_csv(result: ReportResult, output_path: str | Path) -> Path:
    """Write deterministic report columns and rows to a new CSV file."""

    return export_report_result(result, output_path).path


def _validate_parameters(
    spec: ReportSpec,
    parameters: Mapping[str, str | None],
) -> dict[str, str]:
    clean = {
        key: value.strip()
        for key, value in parameters.items()
        if value is not None and value.strip()
    }
    unsupported = sorted(set(clean) - spec.parameters)
    if unsupported:
        raise DataValidationError(
            f"Report {spec.code} does not accept parameter(s): {', '.join(unsupported)}"
        )
    missing = sorted(spec.required_parameters - set(clean))
    if missing:
        raise DataValidationError(f"Report {spec.code} requires parameter(s): {', '.join(missing)}")
    if "as_of_date" in clean:
        try:
            date.fromisoformat(clean["as_of_date"])
        except ValueError as exc:
            raise DataValidationError("as_of_date must use YYYY-MM-DD") from exc
    for name in ("as_of_utc", "start_utc", "end_utc"):
        if name in clean:
            clean[name] = _iso_utc(_parse_aware(clean[name], name))
    if "start_utc" in clean and "end_utc" in clean:
        if _parse_aware(clean["start_utc"], "start_utc") > _parse_aware(
            clean["end_utc"], "end_utc"
        ):
            raise DataValidationError("start_utc cannot follow end_utc")
    return clean


def _parse_aware(value: str, name: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise DataValidationError(f"{name} must be an ISO 8601 timestamp") from exc
    if parsed.tzinfo is None:
        raise DataValidationError(f"{name} must be timezone-aware")
    return parsed


def _iso_utc(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")
