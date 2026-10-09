from __future__ import annotations

import base64
import csv
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from operational_variance_toolkit.application.phase6 import build_reporting_bundle
from operational_variance_toolkit.cli import main
from operational_variance_toolkit.errors import DataValidationError, OutputExistsError
from operational_variance_toolkit.reporting import executive
from operational_variance_toolkit.reporting.exhibits import Exhibit
from operational_variance_toolkit.reporting.frozen import (
    load_frozen_statistics,
    load_reconciliation_summary,
    reporting_summary,
)
from operational_variance_toolkit.reporting.notebook import create_release_notebook


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _inputs(tmp_path: Path) -> tuple[Path, Path, Path]:
    statistics = tmp_path / "statistics"
    reconstruction = tmp_path / "reconstruction"
    statistics.mkdir()
    reconstruction.mkdir()
    run_id = "RUN-TEST-001"
    common = {"run_id": run_id}
    tables: dict[str, list[dict[str, str]]] = {
        "descriptive_metrics.csv": [
            {
                **common,
                "group_dimension": "overall",
                "group_value": "all eligible picks",
                "eligible_picks": "10",
                "requested_cases": "20",
                "short_lines": "2",
                "short_cases": "3",
                "short_line_rate": "0.2",
            }
        ],
        "hypothesis_evidence.csv": [
            {
                **common,
                "hypothesis_id": f"H{i}",
                "evidence_item": "context",
                "evidence_status": "limited",
                "disposition": "investigate",
                "limitation": "synthetic",
                "source_artifact_reference": "table",
            }
            for i in range(1, 7)
        ],
        "qa_adjustment_evidence.csv": [
            {
                **common,
                "window_hours": "4",
                "same_location_required": "1",
                "qa_events": "5",
                "candidate_qa_events": "2",
                "generic_correction_pairs": "1",
                "quantity_compatible_pairs": "1",
                "negative_control_pairs": "3",
            }
        ],
        "replenishment_evidence.csv": [
            {
                **common,
                "evidence_item": "confirmation_proximity",
                "exposure_group": label,
                "eligible_picks": picks,
                "short_lines": shorts,
                "short_line_rate": rate,
                "ci_lower": "0.05",
                "ci_upper": "0.35",
            }
            for label, picks, shorts, rate in (
                ("inside predefined condition", "4", "1", "0.25"),
                ("outside predefined condition", "6", "1", "0.1667"),
                ("within 120 minutes", "4", "1", "0.25"),
                ("outside 120 minutes", "6", "1", "0.1667"),
            )
        ],
        "selector_adjusted.csv": [
            {
                **common,
                "crude_target_rate": "0.3",
                "crude_peer_rate": "0.1",
                "crude_risk_difference_pp": "20",
                "adjusted_target_probability": "0.2",
                "adjusted_peer_probability": "0.1",
                "adjusted_risk_difference_pp": "10",
                "adjusted_ci_lower": "-0.1",
                "adjusted_ci_upper": "0.3",
                "proportional_attenuation": "0.5",
                "material_attenuation": "1",
            }
        ],
        "selector_crude.csv": [
            {
                **common,
                "is_target_contrast": "1",
                "selector_id": "OP-0002",
                "eligible_picks": "4",
                "short_lines": "2",
            }
        ],
        "sensitivity_results.csv": [
            {
                **common,
                "sensitivity_id": key,
                "estimate": "0.1",
                "ci_lower": "-0.1",
                "ci_upper": "0.3",
                "conclusion_consistent": "1",
            }
            for key in (
                "primary",
                "case_outcome",
                "alternate_time_control",
                "alternate_covariance",
                "remove_high_leverage_item",
            )
        ],
    }
    for name, rows in tables.items():
        _write_csv(statistics / name, rows)
    (statistics / "analysis_config.json").write_text("{}\n", encoding="utf-8")
    (statistics / "model_diagnostics.json").write_text(
        json.dumps(
            {
                "findings_frozen": True,
                "ordinary_analysis_ground_truth_loaded": False,
                "model_kind": "logit",
                "covariance": "clustered",
                "events": 2,
                "clusters": 3,
            }
        ),
        encoding="utf-8",
    )
    outputs = {
        name: {"sha256": _sha256(statistics / name)}
        for name in (*tables, "analysis_config.json", "model_diagnostics.json")
    }
    (statistics / "analysis_manifest.json").write_text(
        json.dumps(
            {
                "source": {
                    "run_id": run_id,
                    "schema_version": "3.0.0",
                    "simulation_start_utc": "2026-01-01T00:00:00Z",
                    "simulation_end_utc": "2026-01-02T00:00:00Z",
                    "sha256": "source-checksum",
                },
                "analysis_configuration_sha256": "config-checksum",
                "artifact_type": "frozen_statistical_analysis",
                "statistics_version": "1.0.0",
                "analysis_contract_version": "1.0.0",
                "validation": {
                    "status": "PASS",
                    "findings_frozen": True,
                    "ordinary_analysis_ground_truth_loaded": False,
                },
                "outputs": outputs,
                "row_counts": {name: len(rows) for name, rows in tables.items()}
                | {"analysis_config.json": 0, "model_diagnostics.json": 0},
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    _write_csv(
        reconstruction / "inventory_reconciliation.csv",
        [
            {
                "opening_qty_cases": "10",
                "total_transaction_delta_cases": "2",
                "reconstructed_closing_qty_cases": "12",
                "live_master_qty_cases": "12",
                "closing_snapshot_qty_cases": "12",
                "difference_to_live_cases": "0",
                "difference_to_snapshot_cases": "0",
                "reconciliation_status": "PASS",
            }
        ],
    )
    (reconstruction / "analysis_manifest.json").write_text(
        json.dumps(
            {
                "artifact_type": "analysis_reconstruction",
                "reconstruction_version": "2.0.0",
                "source": {"schema_version": "3.0.0"},
            }
        ),
        encoding="utf-8",
    )
    notebook = create_release_notebook(tmp_path / "source.ipynb")
    return statistics, reconstruction, notebook


def test_frozen_validation_and_summary_are_ground_truth_blind(tmp_path: Path) -> None:
    statistics, reconstruction, _ = _inputs(tmp_path)
    loaded = load_frozen_statistics(statistics)
    summary = reporting_summary(loaded, load_reconciliation_summary(reconstruction))
    assert summary["run_id"] == "RUN-TEST-001"
    assert summary["eligible_picks"] == 10
    assert summary["adjusted_ci_lower_pp"] == -10.0
    assert summary["ordinary_analysis_ground_truth_loaded"] is False
    (statistics / "descriptive_metrics.csv").write_text("tampered", encoding="utf-8")
    with pytest.raises(DataValidationError, match="checksum mismatch"):
        load_frozen_statistics(statistics)


def test_declared_codec_frozen_inputs_preserve_canonical_values_and_summary(tmp_path: Path) -> None:
    statistics, reconstruction, _ = _inputs(tmp_path)
    original = load_frozen_statistics(statistics)
    original_summary = reporting_summary(original, load_reconciliation_summary(reconstruction))
    for root in (statistics, reconstruction):
        manifest_path = root / "analysis_manifest.json"
        manifest = json.loads(manifest_path.read_text())
        manifest.update(csv_codec="codec-v1", artifact_format_version="2.0.0")
        for path in root.glob("*.csv"):
            with path.open(newline="", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
            encoded = [
                {
                    key: "OVTK1_" + base64.urlsafe_b64encode(value.encode()).decode()
                    for key, value in row.items()
                }
                for row in rows
            ]
            _write_csv(path, encoded)
            if "outputs" in manifest:
                manifest["outputs"][path.name]["sha256"] = _sha256(path)
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    accepted = load_frozen_statistics(statistics)
    assert accepted.tables == original.tables
    assert (
        reporting_summary(accepted, load_reconciliation_summary(reconstruction)) == original_summary
    )


def test_legacy_reserved_prefix_is_never_decoded(tmp_path: Path) -> None:
    statistics, _, _ = _inputs(tmp_path)
    path = statistics / "hypothesis_evidence.csv"
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    rows[0]["disposition"] = "OVTK1_Zg=="
    _write_csv(path, rows)
    manifest_path = statistics / "analysis_manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["outputs"][path.name]["sha256"] = _sha256(path)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    assert load_frozen_statistics(statistics).tables[path.name][0]["disposition"] == "OVTK1_Zg=="


def test_reporting_bundle_writes_executed_notebook_pdf_and_refuses_existing_output(
    tmp_path: Path,
) -> None:
    statistics, reconstruction, notebook = _inputs(tmp_path)
    result = build_reporting_bundle(
        statistics,
        reconstruction,
        notebook,
        tmp_path / "release",
        generated_at_utc=datetime(2026, 1, 1, tzinfo=UTC),
    )
    assert result.figure_count == 4
    assert result.notebook_path.is_file()
    assert result.executive_report_path.with_suffix(".pdf").is_file()
    report_text = (result.output_path / "reports" / "executive_report.md").read_text()
    assert "10.00-point residual" in report_text
    assert "Only 2 short events" in report_text
    catalog_text = (result.output_path / "figures" / "exhibit_catalog.csv").read_text()
    assert "All 10 eligible investigation picks" in catalog_text
    assert (
        json.loads((result.output_path / "reporting_manifest.json").read_text())[
            "ordinary_analysis_ground_truth_loaded"
        ]
        is False
    )
    with pytest.raises(OutputExistsError):
        build_reporting_bundle(statistics, reconstruction, notebook, result.output_path)


def test_build_reporting_cli_success_and_missing_input_error(tmp_path: Path, capsys) -> None:
    statistics, reconstruction, notebook = _inputs(tmp_path)
    output = tmp_path / "cli-release"
    assert (
        main(
            [
                "build-reporting",
                "--statistics",
                str(statistics),
                "--reconstruction",
                str(reconstruction),
                "--notebook",
                str(notebook),
                "--output",
                str(output),
            ]
        )
        == 0
    )
    assert "Phase 6 reporting bundle complete" in capsys.readouterr().out
    assert (
        main(
            [
                "build-reporting",
                "--statistics",
                str(tmp_path / "missing"),
                "--reconstruction",
                str(reconstruction),
                "--notebook",
                str(notebook),
                "--output",
                str(tmp_path / "bad"),
            ]
        )
        == 6
    )
    assert "Cannot read required JSON" in capsys.readouterr().err


@pytest.mark.parametrize(
    "field",
    [
        "disposition",
        "limitation",
        "target_selector",
        "run_id",
        "schema_version",
        "sha256",
        "statistics_version",
        "caption",
    ],
)
@pytest.mark.parametrize(
    "text",
    [
        "<img src='https://invalid.example/image.png'/> & café",
        "<link href='https://invalid.example/'>café</link>",
        "&lt;img src='file:untrusted-image.png'/&gt;",
    ],
)
def test_every_pdf_data_boundary_renders_literal_text_without_resources(
    field: str, text: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from reportlab.platypus import Spacer, paraparser

    statistics_path, reconstruction, _ = _inputs(tmp_path)
    statistics = load_frozen_statistics(statistics_path)
    summary = reporting_summary(statistics, load_reconciliation_summary(reconstruction))
    if field in {"disposition", "limitation"}:
        statistics.tables["hypothesis_evidence.csv"][0][field] = text
    elif field == "sha256":
        statistics.manifest["source"][field] = text
    elif field == "statistics_version":
        statistics.manifest[field] = text
    elif field != "caption":
        summary[field] = text
    caption = text if field == "caption" else "ordinary caption"
    exhibits = tuple(
        Exhibit("figure.png", "Title", caption, caption, caption, caption) for _ in range(4)
    )
    original_state = repr((statistics.tables, statistics.manifest, summary))
    paragraphs = []
    original_paragraph = executive.Paragraph

    def capture_paragraph(value, style):
        paragraph = original_paragraph(value, style)
        paragraphs.append(paragraph)
        return paragraph

    def forbid_inline_resource(*_args, **_kwargs):
        pytest.fail("Dataset text attempted inline resource resolution")

    monkeypatch.setattr(paraparser, "ImageReader", forbid_inline_resource)
    monkeypatch.setattr(executive, "Paragraph", capture_paragraph)
    # App-owned figure placement and PDF emission are outside this parser-boundary check.
    monkeypatch.setattr(executive, "Image", lambda *_args, **_kwargs: Spacer(1, 1))
    monkeypatch.setattr(executive.SimpleDocTemplate, "build", lambda *_args, **_kwargs: None)
    executive._pdf(tmp_path / "report.pdf", summary, statistics, exhibits, tmp_path)

    assert any(text in paragraph.getPlainText() for paragraph in paragraphs)
    assert not any(
        getattr(fragment, "link", None) or getattr(fragment, "cbDefn", None)
        for paragraph in paragraphs
        for fragment in paragraph.frags
    )
    assert repr((statistics.tables, statistics.manifest, summary)) == original_state
    # Authored template formatting and line breaks still reach the parser as markup.
    bold = next(
        paragraph
        for paragraph in paragraphs
        if "The raw selector signal" in paragraph.getPlainText()
    )
    assert any(fragment.fontName.endswith("Bold") for fragment in bold.frags)
    questions = next(
        paragraph
        for paragraph in paragraphs
        if "1. Does direct observation" in paragraph.getPlainText()
    )
    assert any(getattr(fragment, "lineBreak", False) for fragment in questions.frags)
