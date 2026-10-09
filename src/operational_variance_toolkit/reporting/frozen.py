"""Validated read-only access to frozen Phase 5 reporting inputs."""

from __future__ import annotations

import csv
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from operational_variance_toolkit.errors import DataValidationError
from operational_variance_toolkit.storage.csv_codec import decode_csv_text, manifest_csv_codec

STATISTICAL_TABLES = (
    "descriptive_metrics.csv",
    "hypothesis_evidence.csv",
    "qa_adjustment_evidence.csv",
    "replenishment_evidence.csv",
    "selector_adjusted.csv",
    "selector_crude.csv",
    "sensitivity_results.csv",
)


@dataclass(frozen=True, slots=True)
class FrozenStatistics:
    """Checksum-verified statistical outputs accepted for publication."""

    path: Path
    manifest: dict[str, Any]
    diagnostics: dict[str, Any]
    tables: dict[str, tuple[dict[str, str], ...]]

    @property
    def run_id(self) -> str:
        return str(self.manifest["source"]["run_id"])

    def one(self, table: str, **criteria: str) -> dict[str, str]:
        matches = [
            row
            for row in self.tables[table]
            if all(row.get(key) == value for key, value in criteria.items())
        ]
        if len(matches) != 1:
            raise DataValidationError(
                f"Expected one row in {table} for {criteria}, found {len(matches)}"
            )
        return matches[0]


@dataclass(frozen=True, slots=True)
class ReconciliationSummary:
    """Closing reconciliation facts used by release reporting."""

    path: Path
    row_count: int
    opening_cases: int
    transaction_delta_cases: int
    reconstructed_closing_cases: int
    live_closing_cases: int
    snapshot_closing_cases: int
    difference_rows: int


def load_frozen_statistics(path: str | Path) -> FrozenStatistics:
    """Load and verify a complete frozen statistical output directory."""

    root = Path(path).resolve()
    manifest = _load_json(root / "analysis_manifest.json")
    codec = manifest_csv_codec(manifest, kind="statistics")
    diagnostics = _load_json(root / "model_diagnostics.json")
    validation = manifest.get("validation", {})
    if validation.get("status") != "PASS" or validation.get("findings_frozen") is not True:
        raise DataValidationError("Statistical outputs are not marked PASS and frozen")
    if validation.get("ordinary_analysis_ground_truth_loaded") is not False:
        raise DataValidationError("Ordinary statistical outputs are not ground-truth blind")
    if diagnostics.get("findings_frozen") is not True:
        raise DataValidationError("Model diagnostics are not marked frozen")
    if diagnostics.get("ordinary_analysis_ground_truth_loaded") is not False:
        raise DataValidationError("Model diagnostics report ground-truth access")

    outputs = manifest.get("outputs")
    if not isinstance(outputs, dict):
        raise DataValidationError("Statistical manifest has no output inventory")
    required = (*STATISTICAL_TABLES, "analysis_config.json", "model_diagnostics.json")
    for file_name in required:
        entry = outputs.get(file_name)
        if not isinstance(entry, dict) or not isinstance(entry.get("sha256"), str):
            raise DataValidationError(f"Statistical manifest omits {file_name}")
        file_path = root / file_name
        if not file_path.is_file():
            raise DataValidationError(f"Frozen statistical output is missing {file_name}")
        if _sha256(file_path) != entry["sha256"]:
            raise DataValidationError(f"Frozen statistical checksum mismatch: {file_name}")

    tables = {file_name: _load_csv(root / file_name, codec) for file_name in STATISTICAL_TABLES}
    run_id = str(manifest.get("source", {}).get("run_id", ""))
    if not run_id:
        raise DataValidationError("Statistical manifest has no run ID")
    for file_name, rows in tables.items():
        expected_count = manifest.get("row_counts", {}).get(file_name)
        if expected_count != len(rows):
            raise DataValidationError(f"Row count mismatch for {file_name}")
        if any(row.get("run_id") != run_id for row in rows):
            raise DataValidationError(f"Run identity mismatch in {file_name}")
    if {row["hypothesis_id"] for row in tables["hypothesis_evidence.csv"]} != {
        "H1",
        "H2",
        "H3",
        "H4",
        "H5",
        "H6",
    }:
        raise DataValidationError("Frozen outputs do not evaluate all six hypotheses")
    return FrozenStatistics(root, manifest, diagnostics, tables)


def load_reconciliation_summary(path: str | Path) -> ReconciliationSummary:
    """Validate and summarize the matching schema-3 reconciliation output."""

    root = Path(path).resolve()
    manifest = _load_json(root / "analysis_manifest.json")
    codec = manifest_csv_codec(manifest, kind="reconstruction")
    rows = _load_csv(root / "inventory_reconciliation.csv", codec)
    if not rows:
        raise DataValidationError("Reconciliation output is empty")
    required = {
        "opening_qty_cases",
        "total_transaction_delta_cases",
        "reconstructed_closing_qty_cases",
        "live_master_qty_cases",
        "closing_snapshot_qty_cases",
        "difference_to_live_cases",
        "difference_to_snapshot_cases",
        "reconciliation_status",
    }
    if not required <= set(rows[0]):
        raise DataValidationError("Reconciliation output has an unsupported schema")
    difference_rows = sum(
        row["reconciliation_status"] != "PASS"
        or int(row["difference_to_live_cases"]) != 0
        or int(row["difference_to_snapshot_cases"]) != 0
        for row in rows
    )
    if difference_rows:
        raise DataValidationError(
            f"Reconciliation contains {difference_rows} nonzero or failed row(s)"
        )
    return ReconciliationSummary(
        path=root,
        row_count=len(rows),
        opening_cases=sum(int(row["opening_qty_cases"]) for row in rows),
        transaction_delta_cases=sum(int(row["total_transaction_delta_cases"]) for row in rows),
        reconstructed_closing_cases=sum(
            int(row["reconstructed_closing_qty_cases"]) for row in rows
        ),
        live_closing_cases=sum(int(row["live_master_qty_cases"]) for row in rows),
        snapshot_closing_cases=sum(int(row["closing_snapshot_qty_cases"]) for row in rows),
        difference_rows=difference_rows,
    )


def reporting_summary(
    statistics: FrozenStatistics, reconciliation: ReconciliationSummary
) -> dict[str, Any]:
    """Return tested reader-facing values without recomputing the analysis."""

    overall = statistics.one(
        "descriptive_metrics.csv", group_dimension="overall", group_value="all eligible picks"
    )
    adjusted = statistics.tables["selector_adjusted.csv"][0]
    target = statistics.one("selector_crude.csv", is_target_contrast="1")
    qa = statistics.one("qa_adjustment_evidence.csv", window_hours="4", same_location_required="1")
    near_replenishment = statistics.one(
        "replenishment_evidence.csv",
        evidence_item="confirmation_proximity",
        exposure_group="within 120 minutes",
    )
    away_replenishment = statistics.one(
        "replenishment_evidence.csv",
        evidence_item="confirmation_proximity",
        exposure_group="outside 120 minutes",
    )
    leave_item_out = statistics.one(
        "sensitivity_results.csv", sensitivity_id="remove_high_leverage_item"
    )
    return {
        "run_id": statistics.run_id,
        "schema_version": statistics.manifest["source"]["schema_version"],
        "simulation_start_utc": statistics.manifest["source"]["simulation_start_utc"],
        "simulation_end_utc": statistics.manifest["source"]["simulation_end_utc"],
        "eligible_picks": int(overall["eligible_picks"]),
        "requested_cases": int(overall["requested_cases"]),
        "short_lines": int(overall["short_lines"]),
        "short_cases": int(overall["short_cases"]),
        "overall_short_line_rate": float(overall["short_line_rate"]),
        "target_selector": target["selector_id"],
        "target_picks": int(target["eligible_picks"]),
        "target_short_lines": int(target["short_lines"]),
        "target_crude_rate": float(adjusted["crude_target_rate"]),
        "peer_crude_rate": float(adjusted["crude_peer_rate"]),
        "crude_risk_difference_pp": float(adjusted["crude_risk_difference_pp"]),
        "adjusted_target_probability": float(adjusted["adjusted_target_probability"]),
        "adjusted_peer_probability": float(adjusted["adjusted_peer_probability"]),
        "adjusted_risk_difference_pp": float(adjusted["adjusted_risk_difference_pp"]),
        "adjusted_ci_lower_pp": float(adjusted["adjusted_ci_lower"]) * 100,
        "adjusted_ci_upper_pp": float(adjusted["adjusted_ci_upper"]) * 100,
        "proportional_attenuation": float(adjusted["proportional_attenuation"]),
        "material_attenuation": adjusted["material_attenuation"] == "1",
        "replenishment_near_picks": int(near_replenishment["eligible_picks"]),
        "replenishment_near_shorts": int(near_replenishment["short_lines"]),
        "replenishment_near_rate": float(near_replenishment["short_line_rate"]),
        "replenishment_away_picks": int(away_replenishment["eligible_picks"]),
        "replenishment_away_shorts": int(away_replenishment["short_lines"]),
        "replenishment_away_rate": float(away_replenishment["short_line_rate"]),
        "qa_events": int(qa["qa_events"]),
        "qa_candidates": int(qa["candidate_qa_events"]),
        "qa_generic_corrections": int(qa["generic_correction_pairs"]),
        "qa_quantity_compatible": int(qa["quantity_compatible_pairs"]),
        "qa_negative_controls": int(qa["negative_control_pairs"]),
        "reconciliation_rows": reconciliation.row_count,
        "reconstructed_closing_cases": reconciliation.reconstructed_closing_cases,
        "live_closing_cases": reconciliation.live_closing_cases,
        "snapshot_closing_cases": reconciliation.snapshot_closing_cases,
        "reconciliation_difference_rows": reconciliation.difference_rows,
        "model_kind": statistics.diagnostics["model_kind"],
        "covariance": statistics.diagnostics["covariance"],
        "model_events": int(statistics.diagnostics["events"]),
        "model_clusters": int(statistics.diagnostics["clusters"]),
        "leave_item_out_estimate_pp": float(leave_item_out["estimate"]) * 100,
        "leave_item_out_ci_lower_pp": float(leave_item_out["ci_lower"]) * 100,
        "leave_item_out_ci_upper_pp": float(leave_item_out["ci_upper"]) * 100,
        "ordinary_analysis_ground_truth_loaded": False,
    }


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DataValidationError(f"Cannot read required JSON {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise DataValidationError(f"Expected a JSON object in {path}")
    return value


def _load_csv(path: Path, codec: str | None) -> tuple[dict[str, str], ...]:
    try:
        with path.open(newline="", encoding="utf-8") as handle:
            return tuple(
                {
                    key: decode_csv_text(value, codec) if isinstance(value, str) else value
                    for key, value in row.items()
                }
                for row in csv.DictReader(handle)
            )
    except OSError as exc:
        raise DataValidationError(f"Cannot read required CSV {path}: {exc}") from exc


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
