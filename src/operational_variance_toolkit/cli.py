"""Command-line interface for the Operational Variance Toolkit."""

from __future__ import annotations

import sys
from argparse import ArgumentParser, Namespace
from collections.abc import Sequence
from pathlib import Path

from operational_variance_toolkit.application.phase1 import (
    DescribeDatasetResult,
    InitializeDatabaseResult,
    ValidateDatasetResult,
    describe_phase1_database,
    initialize_phase1_database,
    validate_phase1_database,
)
from operational_variance_toolkit.application.phase2 import (
    GeneratePhase2Result,
)
from operational_variance_toolkit.application.phase4 import (
    ReconstructDatabaseResult,
    reconstruct_database,
)
from operational_variance_toolkit.application.phase5 import (
    AnalyzeDatabaseResult,
    analyze_database,
)
from operational_variance_toolkit.application.phase6 import (
    BuildReportingResult,
    build_reporting_bundle,
)
from operational_variance_toolkit.application.release import (
    PackageReleaseResult,
    package_release,
)
from operational_variance_toolkit.application.wms_generation import (
    GenerateWmsBaselineResult,
    generate_wms_baseline,
)
from operational_variance_toolkit.application.wms_investigation import (
    GenerateWmsInvestigationResult,
    generate_wms_investigation,
)
from operational_variance_toolkit.config import load_project_config
from operational_variance_toolkit.errors import (
    ConfigurationError,
    DataValidationError,
    ToolkitError,
)
from operational_variance_toolkit.sandbox.application import clone_sandbox
from operational_variance_toolkit.storage.database import database_user_version
from operational_variance_toolkit.storage.repositories import PHASE1_TABLES, PHASE2_TABLES
from operational_variance_toolkit.validation.result import ValidationResult
from operational_variance_toolkit.validation.scenario import validate_scenario_artifacts
from operational_variance_toolkit.version import get_version
from operational_variance_toolkit.wms.application.describe import (
    DescribeWmsResult,
    describe_wms,
)
from operational_variance_toolkit.wms.application.initialize import (
    InitializeWmsFoundationResult,
    initialize_wms_foundation,
)
from operational_variance_toolkit.wms.application.reports import (
    available_reports,
    export_report_csv,
    run_wms_report,
)
from operational_variance_toolkit.wms.domain.reports import ReportResult
from operational_variance_toolkit.wms.storage.repositories import WMS_TABLES


def build_parser() -> ArgumentParser:
    parser = ArgumentParser(
        prog="operational-variance-toolkit",
        description="Synthetic warehouse data and inventory variance investigation toolkit.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {get_version()}",
    )

    subparsers = parser.add_subparsers(dest="command")
    console = subparsers.add_parser(
        "console",
        help="launch the persistent read-only WMS console",
    )
    source = console.add_mutually_exclusive_group()
    source.add_argument(
        "--database",
        type=Path,
        help="open an existing schema-3 WMS read-only",
    )
    source.add_argument(
        "--sample",
        action="store_true",
        help="open the included sample WMS read-only",
    )
    console.add_argument(
        "--output-directory",
        type=Path,
        help="session output directory for later release phases",
    )
    console.add_argument(
        "--no-style",
        action="store_true",
        help="disable optional terminal styling",
    )
    console.set_defaults(handler=_handle_console)

    clone = subparsers.add_parser(
        "clone",
        help="create a verified schema-3.1.0 sandbox copy",
    )
    clone.add_argument(
        "--source",
        required=True,
        type=Path,
        help="accepted schema-3.0.0 source database",
    )
    clone.add_argument(
        "--destination",
        required=True,
        type=Path,
        help="new sandbox database path",
    )
    clone.set_defaults(handler=_handle_clone_sandbox)

    config_check = subparsers.add_parser(
        "config-check",
        help="validate a project configuration without generating data",
    )
    config_check.add_argument(
        "--config",
        required=True,
        type=Path,
        help="path to a TOML configuration file",
    )
    config_check.set_defaults(handler=_handle_config_check)

    init_db = subparsers.add_parser(
        "init-db",
        help="create a legacy schema-1/2 Phase 1 database",
    )
    init_db.add_argument(
        "--config",
        required=True,
        type=Path,
        help="path to a TOML configuration file",
    )
    init_db.set_defaults(handler=_handle_init_db)

    init_wms = subparsers.add_parser(
        "init-wms",
        help="create a fresh schema-3 WMS database from configuration",
    )
    init_wms.add_argument(
        "--config",
        required=True,
        type=Path,
        help="path to a TOML configuration file",
    )
    init_wms.add_argument(
        "--output",
        required=True,
        type=Path,
        help="path for the new schema-3 SQLite database",
    )
    init_wms.set_defaults(handler=_handle_init_wms)

    generate = subparsers.add_parser(
        "generate",
        help="generate a fresh operational database from configuration",
    )
    generate.add_argument(
        "--config",
        required=True,
        type=Path,
        help="path to a TOML configuration file",
    )
    generate.add_argument(
        "--output",
        required=True,
        type=Path,
        help="path for the new Phase 2 SQLite database",
    )
    generate.add_argument(
        "--ground-truth",
        type=Path,
        help="restricted ground-truth JSON path for enabled failure overlays",
    )
    generate.set_defaults(handler=_handle_generate)

    scenario_check = subparsers.add_parser(
        "scenario-check",
        help="validate restricted controlled-scenario signatures",
    )
    scenario_check.add_argument(
        "--database",
        required=True,
        type=Path,
        help="path to an existing analyst-facing SQLite database",
    )
    scenario_check.add_argument(
        "--ground-truth",
        required=True,
        type=Path,
        help="path to the restricted ground-truth JSON artifact",
    )
    scenario_check.set_defaults(handler=_handle_scenario_check)

    reconstruct = subparsers.add_parser(
        "reconstruct",
        help="reconstruct inventory from a supported operational database",
    )
    reconstruct.add_argument(
        "--database",
        required=True,
        type=Path,
        help="path to an existing schema-2 or schema-3 SQLite database",
    )
    reconstruct.add_argument(
        "--output",
        required=True,
        type=Path,
        help="path to a new or empty analysis output directory",
    )
    reconstruct.set_defaults(handler=_handle_reconstruct)

    analyze = subparsers.add_parser(
        "analyze",
        help="run the frozen Phase 5 statistical investigation",
    )
    analyze.add_argument(
        "--database",
        required=True,
        type=Path,
        help="path to an existing schema-3 analyst-facing WMS database",
    )
    analyze.add_argument(
        "--reconstruction",
        required=True,
        type=Path,
        help="path to the matching validated reconstruction directory",
    )
    analyze.add_argument(
        "--config",
        required=True,
        type=Path,
        help="path to the frozen Phase 5 analysis TOML configuration",
    )
    analyze.add_argument(
        "--output",
        required=True,
        type=Path,
        help="path to a new or empty statistics output directory",
    )
    analyze.set_defaults(handler=_handle_analyze)

    build_reporting = subparsers.add_parser(
        "build-reporting",
        help="build the frozen Phase 6 notebook, exhibits, and executive report",
    )
    build_reporting.add_argument(
        "--statistics",
        required=True,
        type=Path,
        help="path to the frozen accepted Phase 5 statistics directory",
    )
    build_reporting.add_argument(
        "--reconstruction",
        required=True,
        type=Path,
        help="path to the matching validated reconstruction directory",
    )
    build_reporting.add_argument(
        "--notebook",
        required=True,
        type=Path,
        help="path to the thin release notebook source",
    )
    build_reporting.add_argument(
        "--output",
        required=True,
        type=Path,
        help="path to a new or empty reporting output directory",
    )
    build_reporting.set_defaults(handler=_handle_build_reporting)

    package = subparsers.add_parser(
        "package-release",
        help="build leakage-checked local source and optional ground-truth archives",
    )
    package.add_argument("--workspace", required=True, type=Path)
    package.add_argument("--output", required=True, type=Path)
    package.add_argument("--baseline-database", required=True, type=Path)
    package.add_argument("--investigation-database", required=True, type=Path)
    package.add_argument("--baseline-reconstruction", required=True, type=Path)
    package.add_argument("--investigation-reconstruction", required=True, type=Path)
    package.add_argument("--statistics", required=True, type=Path)
    package.add_argument("--standard-reports", required=True, type=Path)
    package.add_argument("--reporting", required=True, type=Path)
    package.add_argument("--ground-truth", required=True, type=Path)
    package.set_defaults(handler=_handle_package_release)

    validate = subparsers.add_parser(
        "validate",
        help="validate an existing supported SQLite database",
    )
    validate.add_argument(
        "--database",
        required=True,
        type=Path,
        help="path to an existing SQLite database",
    )
    validate.set_defaults(handler=_handle_validate)

    describe = subparsers.add_parser(
        "describe",
        help="describe factual supported database contents",
    )
    describe.add_argument(
        "--database",
        required=True,
        type=Path,
        help="path to an existing SQLite database",
    )
    describe.set_defaults(handler=_handle_describe)

    report = subparsers.add_parser(
        "report",
        help="run a factual standard report against a schema-3 WMS",
    )
    report.add_argument("--database", required=True, type=Path)
    report.add_argument("--list", action="store_true", dest="list_reports")
    report.add_argument("--name")
    report.add_argument("--output", type=Path)
    report.add_argument("--item")
    report.add_argument("--location")
    report.add_argument("--operator")
    report.add_argument("--transaction-group")
    report.add_argument("--source-record")
    report.add_argument("--start-utc")
    report.add_argument("--end-utc")
    report.add_argument("--as-of-date")
    report.add_argument("--as-of-utc")
    report.add_argument("--snapshot-batch")
    report.set_defaults(handler=_handle_report)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    handler = getattr(args, "handler", None)
    if handler is None:
        parser.print_help()
        return 0

    try:
        return handler(args)
    except ConfigurationError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return exc.exit_code
    except ToolkitError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return exc.exit_code


def _handle_config_check(args: Namespace) -> int:
    config = load_project_config(args.config)
    print("Configuration valid")
    print(f"Scenario: {config.run.scenario_name} {config.run.scenario_version}")
    print(f"Seed: {config.run.seed}")
    print(
        "Operating period (UTC): "
        f"{_format_utc(config.run.start_utc)} to {_format_utc(config.run.end_utc)}"
    )
    print(f"Facility timezone: {config.run.facility_timezone}")
    print(f"Configuration SHA-256: {config.configuration_hash}")
    return 0


def _handle_console(args: Namespace) -> int:
    from operational_variance_toolkit.console import run_console

    return run_console(
        database_path=args.database,
        sample=args.sample,
        output_directory=args.output_directory,
        no_style=args.no_style,
    )


def _handle_init_db(args: Namespace) -> int:
    result = initialize_phase1_database(args.config)
    _print_initialize_result(result)
    return 0


def _handle_init_wms(args: Namespace) -> int:
    result = initialize_wms_foundation(args.config, args.output)
    _print_initialize_wms_result(result)
    return 0


def _handle_generate(args: Namespace) -> int:
    config = load_project_config(args.config)
    if config.failures.any_enabled:
        if args.ground_truth is None:
            raise ConfigurationError(
                "A separate --ground-truth path is required when failure controls are enabled"
            )
        result = generate_wms_investigation(
            args.config,
            args.output,
            args.ground_truth,
        )
        _print_generate_wms_investigation_result(result)
    else:
        if args.ground_truth is not None:
            raise ConfigurationError(
                "--ground-truth is only supported when failure controls are enabled"
            )
        wms_result = generate_wms_baseline(args.config, args.output)
        _print_generate_wms_result(wms_result)
    return 0


def _handle_scenario_check(args: Namespace) -> int:
    validation = validate_scenario_artifacts(args.database, args.ground_truth)
    print(f"Scenario validation status: {_validation_status(validation)}")
    _print_validation_details(validation)
    return 0 if validation.passed else DataValidationError.exit_code


def _handle_reconstruct(args: Namespace) -> int:
    result = reconstruct_database(args.database, args.output)
    _print_reconstruct_result(result)
    return 0


def _handle_analyze(args: Namespace) -> int:
    result = analyze_database(
        args.database,
        args.reconstruction,
        args.config,
        args.output,
    )
    _print_analyze_result(result)
    return 0


def _handle_build_reporting(args: Namespace) -> int:
    result = build_reporting_bundle(
        args.statistics,
        args.reconstruction,
        args.notebook,
        args.output,
    )
    _print_build_reporting_result(result)
    return 0


def _handle_package_release(args: Namespace) -> int:
    result = package_release(
        args.workspace,
        args.output,
        args.baseline_database,
        args.investigation_database,
        args.baseline_reconstruction,
        args.investigation_reconstruction,
        args.statistics,
        args.standard_reports,
        args.reporting,
        args.ground_truth,
    )
    _print_package_release_result(result)
    return 0


def _handle_validate(args: Namespace) -> int:
    result = validate_phase1_database(args.database)
    _print_validate_result(result)
    return 0 if result.validation.passed else DataValidationError.exit_code


def _handle_describe(args: Namespace) -> int:
    if database_user_version(args.database) in {3, 4}:
        _print_describe_wms_result(describe_wms(args.database))
    else:
        result = describe_phase1_database(args.database)
        _print_describe_result(result)
    return 0


def _handle_clone_sandbox(args: Namespace) -> int:
    result = clone_sandbox(args.source, args.destination)
    print("Sandbox created and verified")
    print(f"Sandbox database: {result.database_path}")
    print(f"Sandbox manifest: {result.manifest_path}")
    print(f"Sandbox ID: {result.manifest.sandbox_id}")
    print(f"Source SHA-256: {result.manifest.source_database_sha256}")
    print(f"Initial sandbox SHA-256: {result.manifest.initial_sandbox_sha256}")
    return 0


def _handle_report(args: Namespace) -> int:
    if args.list_reports:
        if args.name is not None:
            raise DataValidationError("Use either --list or --name, not both")
        print("Registered schema-3 WMS reports:")
        for spec in available_reports():
            print(f"  {spec.code}: {spec.name}")
        return 0
    if args.name is None:
        raise DataValidationError("report requires --list or --name")
    parameters = {
        "item": args.item,
        "location": args.location,
        "operator": args.operator,
        "transaction_group": args.transaction_group,
        "source_record": args.source_record,
        "start_utc": args.start_utc,
        "end_utc": args.end_utc,
        "as_of_date": args.as_of_date,
        "as_of_utc": args.as_of_utc,
        "snapshot_batch": args.snapshot_batch,
    }
    result = run_wms_report(args.database, args.name, parameters)
    output_path = export_report_csv(result, args.output) if args.output else None
    _print_report_result(result, output_path)
    return 0


def _print_initialize_result(result: InitializeDatabaseResult) -> None:
    print("Phase 1 database initialized")
    print(f"Run ID: {result.run_metadata.run_id}")
    print(f"Database path: {result.database_path}")
    print(f"Configuration SHA-256: {result.config_hash}")
    print("Entity counts:")
    for table_name in PHASE1_TABLES:
        if table_name in result.counts:
            print(f"  {table_name}: {result.counts[table_name]}")
    print(f"Validation status: {_validation_status(result.validation)}")


def _print_initialize_wms_result(result: InitializeWmsFoundationResult) -> None:
    print("Schema-3 WMS initialized")
    print(f"Run ID: {result.run_metadata.run_id}")
    print(f"Database path: {result.database_path}")
    print(f"Schema version: {result.run_metadata.schema_version}")
    print(f"Configuration SHA-256: {result.run_metadata.config_hash}")
    print("Entity counts:")
    for table_name in WMS_TABLES:
        if result.counts.get(table_name, 0) > 0:
            print(f"  {table_name}: {result.counts[table_name]}")
    print(f"Validation status: {_validation_status(result.validation)}")


def _print_generate_result(result: GeneratePhase2Result) -> None:
    if result.ground_truth_path is None:
        print("Phase 2 baseline database generated")
    else:
        print("Phase 3 investigation database generated")
    print(f"Run ID: {result.run_metadata.run_id}")
    print(f"Database path: {result.database_path}")
    if result.ground_truth_path is not None:
        print(f"Restricted ground-truth path: {result.ground_truth_path}")
    print(f"Configuration SHA-256: {result.config_hash}")
    print("Entity counts:")
    for table_name in PHASE2_TABLES:
        if table_name in result.counts:
            print(f"  {table_name}: {result.counts[table_name]}")
    print("Generated transaction counts:")
    print(f"  trips: {result.operation_counts.trips}")
    print(f"  pick_events: {result.operation_counts.pick_events}")
    print(f"  replenishment_tasks: {result.operation_counts.replenishment_tasks}")
    print(f"  qa_events: {result.operation_counts.qa_events}")
    print(f"  inventory_adjustments: {result.operation_counts.inventory_adjustments}")
    print(f"  system_events: {result.operation_counts.system_events}")
    print(f"  closing_snapshots: {result.operation_counts.closing_snapshots}")
    print(f"Validation status: {_validation_status(result.validation)}")


def _print_generate_wms_result(result: GenerateWmsBaselineResult) -> None:
    print("Schema-3 baseline WMS generated")
    print(f"Run ID: {result.run_metadata.run_id}")
    print(f"Database path: {result.database_path}")
    print(f"Schema version: {result.run_metadata.schema_version}")
    print(f"Configuration SHA-256: {result.config_hash}")
    print("Generated operation counts:")
    print(f"  trips: {result.operation_counts.trips}")
    print(f"  pick_events: {result.operation_counts.pick_events}")
    print(f"  replenishment_tasks: {result.operation_counts.replenishment_tasks}")
    print(f"  qa_events: {result.operation_counts.qa_events}")
    print(f"  inventory_adjustments: {result.operation_counts.inventory_adjustments}")
    print(f"  system_events: {result.operation_counts.system_events}")
    print(f"  closing_snapshots: {result.operation_counts.closing_snapshots}")
    print(f"Validation status: {_validation_status(result.validation)}")


def _print_generate_wms_investigation_result(
    result: GenerateWmsInvestigationResult,
) -> None:
    print("Schema-3 investigation WMS generated")
    print(f"Run ID: {result.run_metadata.run_id}")
    print(f"Database path: {result.database_path}")
    print(f"Restricted ground-truth path: {result.ground_truth_path}")
    print(f"Schema version: {result.run_metadata.schema_version}")
    print(f"Configuration SHA-256: {result.config_hash}")
    print("Generated operation counts:")
    print(f"  trips: {result.operation_counts.trips}")
    print(f"  pick_events: {result.operation_counts.pick_events}")
    print(f"  replenishment_tasks: {result.operation_counts.replenishment_tasks}")
    print(f"  qa_events: {result.operation_counts.qa_events}")
    print(f"  inventory_adjustments: {result.operation_counts.inventory_adjustments}")
    print(f"  system_events: {result.operation_counts.system_events}")
    print(f"  closing_snapshots: {result.operation_counts.closing_snapshots}")
    print(f"Validation status: {_validation_status(result.validation)}")
    print(f"Scenario validation status: {_validation_status(result.scenario_validation)}")


def _print_reconstruct_result(result: ReconstructDatabaseResult) -> None:
    print("Inventory reconstruction complete")
    print(f"Run ID: {result.run_metadata.run_id}")
    print(f"Source database: {result.database_path}")
    print(f"Output directory: {result.output_path}")
    print(f"Source SHA-256: {result.source_sha256_after}")
    print(f"Source preserved: {result.source_sha256_before == result.source_sha256_after}")
    print("Derived row counts:")
    for table_name in sorted(result.row_counts):
        print(f"  {table_name}: {result.row_counts[table_name]}")
    print(
        "Reconciliation status: "
        f"{result.reconciliation_status} "
        f"({result.reconciliation_failure_count} difference(s))"
    )
    print(f"Validation status: {_validation_status(result.validation)}")


def _print_analyze_result(result: AnalyzeDatabaseResult) -> None:
    print("Phase 5 statistical analysis complete")
    print(f"Run ID: {result.run_id}")
    print(f"Source database: {result.database_path}")
    print(f"Reconstruction: {result.reconstruction_path}")
    print(f"Output directory: {result.output_path}")
    print(f"Source SHA-256: {result.source_sha256_after}")
    print(f"Source preserved: {result.source_sha256_before == result.source_sha256_after}")
    print(f"Analysis configuration SHA-256: {result.configuration_sha256}")
    print(f"Primary model: {result.model_kind} ({result.covariance})")
    print(f"Crude target risk difference: {result.crude_risk_difference:.6f}")
    print(f"Adjusted target risk difference: {result.adjusted_risk_difference:.6f}")
    print(f"Proportional attenuation: {result.proportional_attenuation:.2%}")
    print(f"Material attenuation: {result.material_attenuation}")
    print(f"All six hypotheses present: {result.hypotheses_complete}")
    print(f"Ordinary analysis loaded ground truth: {result.ordinary_analysis_ground_truth_loaded}")
    print("Statistical output row counts:")
    for file_name in sorted(result.row_counts):
        print(f"  {file_name}: {result.row_counts[file_name]}")


def _print_build_reporting_result(result: BuildReportingResult) -> None:
    print("Phase 6 reporting bundle complete")
    print(f"Run ID: {result.run_id}")
    print(f"Output directory: {result.output_path}")
    print(f"Executed notebook: {result.notebook_path}")
    print(f"Executive report: {result.executive_report_path}")
    print(f"Figures: {result.figure_count}")
    print(
        "Reconciliation: "
        f"{result.reconciliation_rows} rows, "
        f"{result.reconciliation_difference_rows} differences"
    )
    print(f"Files: {result.file_count}")
    print(f"Reporting manifest SHA-256: {result.manifest_sha256}")


def _print_package_release_result(result: PackageReleaseResult) -> None:
    print(f"Release {result.version} packaged locally")
    print(f"Source archive: {result.source_archive_path}")
    print(f"Source SHA-256: {result.source_archive_sha256}")
    print(f"Source checksum: {result.source_checksum_path}")
    print(f"Optional ground-truth archive: {result.truth_archive_path}")
    print(f"Ground-truth SHA-256: {result.truth_archive_sha256}")
    print(f"Ground-truth checksum: {result.truth_checksum_path}")
    print(f"Combined checksums: {result.combined_checksum_path}")
    print(f"Primary files: {result.source_file_count}")
    print(f"Optional truth files: {result.truth_file_count}")
    print(f"Leakage status: {result.leakage_status}")


def _print_validate_result(result: ValidateDatasetResult) -> None:
    print(f"Validation status: {_validation_status(result.validation)}")
    print(f"Database path: {result.database_path}")
    _print_validation_details(result.validation)


def _print_describe_result(result: DescribeDatasetResult) -> None:
    metadata = result.run_metadata
    print("Dataset description")
    print(f"Database path: {result.database_path}")
    print(f"Run ID: {metadata.run_id}")
    print(f"Scenario: {metadata.scenario_name} {metadata.scenario_version}")
    print(f"Seed: {metadata.seed}")
    print(f"Schema version: {metadata.schema_version}")
    print(f"Generator version: {metadata.generator_version}")
    print(f"Configuration SHA-256: {metadata.config_hash}")
    print(
        f"Operating period (UTC): {metadata.simulation_start_utc} to {metadata.simulation_end_utc}"
    )
    print(f"Facility timezone: {metadata.facility_timezone}")
    print("Table counts:")
    for table_name in PHASE2_TABLES:
        if table_name in result.table_counts:
            print(f"  {table_name}: {result.table_counts[table_name]}")
    print("Opening inventory by zone:")
    for zone_code, qty_cases in result.opening_totals_by_zone:
        print(f"  {zone_code}: {qty_cases} cases")
    if result.closing_totals_by_zone:
        print("Closing inventory by zone:")
        for zone_code, qty_cases in result.closing_totals_by_zone:
            print(f"  {zone_code}: {qty_cases} cases")
    print(f"Validation status: {_validation_status(result.validation)}")


def _print_describe_wms_result(result: DescribeWmsResult) -> None:
    metadata = result.run_metadata
    print("Schema-3 WMS description")
    print(f"Database path: {result.database_path}")
    print(f"Run ID: {metadata.run_id}")
    print(f"Seed: {metadata.seed}")
    print(f"Schema version: {metadata.schema_version}")
    print(f"Generator version: {metadata.generator_version}")
    print(f"Configuration SHA-256: {metadata.config_hash}")
    print(
        f"Operating period (UTC): {metadata.simulation_start_utc} to {metadata.simulation_end_utc}"
    )
    print(f"Facility timezone: {metadata.facility_timezone}")
    print("Table counts:")
    for table_name in WMS_TABLES:
        print(f"  {table_name}: {result.table_counts[table_name]}")
    print("Live inventory by zone:")
    for zone_code, qty_cases in result.live_totals_by_zone:
        print(f"  {zone_code}: {qty_cases} cases")
    print("Snapshot batches:")
    for batch_id, snapshot_type, snapshot_utc, row_count in result.snapshot_batches:
        print(f"  {batch_id}: {snapshot_type}, {snapshot_utc}, {row_count} rows")
    print(f"Validation status: {_validation_status(result.validation)}")


def _print_report_result(result: ReportResult, output_path: Path | None) -> None:
    print(f"Report: {result.spec.code} ({result.spec.name})")
    print(f"Run ID: {result.run_id}")
    print(f"Database path: {result.database_path}")
    print(f"Schema version: {result.schema_version}")
    print(f"As of: {result.as_of_utc}")
    print(f"Generated at: {result.generated_at_utc}")
    print(f"Parameters: {dict(result.parameters)}")
    print(f"Row count: {result.row_count}")
    if output_path is not None:
        print(f"CSV output: {output_path}")
        return
    print("\t".join(result.spec.display_columns))
    for row in result.rows:
        print("\t".join("" if value is None else str(value) for value in row))


def _validation_status(result: ValidationResult) -> str:
    if result.passed:
        return "PASS"
    return f"FAIL ({len(result.hard_failures)} hard failure(s))"


def _print_validation_details(result: ValidationResult) -> None:
    if result.hard_failures:
        print("Hard failures:")
        for issue in result.hard_failures:
            print(f"  [{issue.category}] {issue.message}")
    else:
        print("Hard failures: none")

    if result.warnings:
        print("Warnings:")
        for issue in result.warnings:
            print(f"  [{issue.category}] {issue.message}")
    else:
        print("Warnings: none")


def _format_utc(value) -> str:
    return value.isoformat().replace("+00:00", "Z")
