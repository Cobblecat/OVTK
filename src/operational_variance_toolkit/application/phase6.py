"""Phase 6 reporting application workflow."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from operational_variance_toolkit.errors import DatabaseError, OutputExistsError
from operational_variance_toolkit.reporting.executive import build_executive_report
from operational_variance_toolkit.reporting.exhibits import build_exhibits
from operational_variance_toolkit.reporting.frozen import (
    load_frozen_statistics,
    load_reconciliation_summary,
    reporting_summary,
)
from operational_variance_toolkit.reporting.notebook import execute_release_notebook
from operational_variance_toolkit.version import get_version


@dataclass(frozen=True, slots=True)
class BuildReportingResult:
    output_path: Path
    run_id: str
    notebook_path: Path
    executive_report_path: Path
    figure_count: int
    reconciliation_rows: int
    reconciliation_difference_rows: int
    file_count: int
    manifest_sha256: str


def build_reporting_bundle(
    statistics_path: str | Path,
    reconstruction_path: str | Path,
    notebook_source_path: str | Path,
    output_path: str | Path,
    *,
    generated_at_utc: datetime | None = None,
) -> BuildReportingResult:
    """Build and execute all release reporting from frozen accepted inputs."""

    final_output = _require_available_output(output_path)
    statistics = load_frozen_statistics(statistics_path)
    reconciliation = load_reconciliation_summary(reconstruction_path)
    summary = reporting_summary(statistics, reconciliation)
    notebook_source = Path(notebook_source_path).resolve()
    if not notebook_source.is_file():
        raise DatabaseError(f"Release notebook source does not exist: {notebook_source}")

    temporary = final_output.parent / (
        f".{final_output.name}.tmp-{os.getpid()}-{uuid.uuid4().hex[:12]}"
    )
    try:
        final_output.parent.mkdir(parents=True, exist_ok=True)
        temporary.mkdir()
        figures = build_exhibits(statistics, temporary / "figures")
        report_paths = build_executive_report(statistics, summary, figures, temporary / "reports")
        notebook_dir = temporary / "notebook"
        notebook_dir.mkdir()
        source_copy = notebook_dir / notebook_source.name
        shutil.copy2(notebook_source, source_copy)
        executed_notebook = execute_release_notebook(
            source_copy,
            notebook_dir / f"{notebook_source.stem}_executed.ipynb",
            statistics.path,
            reconciliation.path,
            temporary,
        )
        files = _file_inventory(temporary)
        manifest = {
            "artifact_type": "phase6_release_reporting",
            "release_version": get_version(),
            "generated_at_utc": (generated_at_utc or datetime.now(tz=UTC))
            .astimezone(UTC)
            .isoformat()
            .replace("+00:00", "Z"),
            "run_id": statistics.run_id,
            "statistics_manifest_sha256": _sha256(statistics.path / "analysis_manifest.json"),
            "reconstruction_manifest_sha256": _sha256(
                reconciliation.path / "analysis_manifest.json"
            ),
            "synthetic_data": True,
            "ordinary_analysis_ground_truth_loaded": False,
            "frozen_findings_only": True,
            "reconciliation": {
                "rows": reconciliation.row_count,
                "difference_rows": reconciliation.difference_rows,
            },
            "outputs": files,
        }
        manifest_path = temporary / "reporting_manifest.json"
        manifest_path.write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        if final_output.exists():
            final_output.rmdir()
        temporary.rename(final_output)
        final_manifest = final_output / "reporting_manifest.json"
        return BuildReportingResult(
            output_path=final_output.resolve(),
            run_id=statistics.run_id,
            notebook_path=final_output / "notebook" / executed_notebook.name,
            executive_report_path=final_output / "reports" / report_paths[1].name,
            figure_count=len(figures),
            reconciliation_rows=reconciliation.row_count,
            reconciliation_difference_rows=reconciliation.difference_rows,
            file_count=len(files) + 1,
            manifest_sha256=_sha256(final_manifest),
        )
    except Exception as exc:
        if temporary.exists():
            shutil.rmtree(temporary, ignore_errors=True)
        if isinstance(exc, (OutputExistsError, DatabaseError)):
            raise
        raise DatabaseError(f"Failed to build Phase 6 reporting at {final_output}: {exc}") from exc


def _require_available_output(path: str | Path) -> Path:
    output = Path(path)
    if output.exists():
        if not output.is_dir():
            raise OutputExistsError(f"Reporting output exists and is not a directory: {output}")
        if any(output.iterdir()):
            raise OutputExistsError(
                f"Reporting output directory already exists and is not empty: {output}"
            )
    return output


def _file_inventory(root: Path) -> dict[str, dict[str, int | str]]:
    return {
        path.relative_to(root).as_posix(): {"bytes": path.stat().st_size, "sha256": _sha256(path)}
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
