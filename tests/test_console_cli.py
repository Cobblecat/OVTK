from __future__ import annotations

import hashlib
import shutil
import subprocess
import sys
from io import StringIO
from pathlib import Path

import pytest

from operational_variance_toolkit.cli import build_parser
from operational_variance_toolkit.console.rendering import ConsoleRenderer
from operational_variance_toolkit.console.resources import ResourceResolver
from operational_variance_toolkit.console.session import ConsoleSession
from operational_variance_toolkit.console.startup import _run_command_loop, run_console

ONE_SHOT_COMMANDS = (
    "config-check",
    "init-db",
    "init-wms",
    "generate",
    "scenario-check",
    "reconstruct",
    "analyze",
    "build-reporting",
    "package-release",
    "validate",
    "describe",
    "report",
    "clone",
)


class ScriptedInput:
    def __init__(self, *actions: str | BaseException) -> None:
        self._actions = iter(actions)
        self.prompts: list[tuple[str, bool]] = []
        self.accepted_history = 0
        self.discarded_history = 0

    def read(self, prompt: str, *, record_history: bool = True) -> str:
        self.prompts.append((prompt, record_history))
        action = next(self._actions)
        if isinstance(action, BaseException):
            raise action
        return action

    def accept_history(self) -> None:
        self.accepted_history += 1

    def discard_history(self) -> None:
        self.discarded_history += 1


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_no_database_start_menu_is_explicit_and_exits_cleanly(tmp_path: Path) -> None:
    stdout = StringIO()
    stderr = StringIO()
    reader = ScriptedInput("5")

    result = run_console(
        stdout=stdout,
        stderr=stderr,
        resources=ResourceResolver(tmp_path),
        input_reader=reader,
    )

    output = stdout.getvalue()
    assert result == 0
    assert "Operational Variance Toolkit" in output
    assert "1. Open the included sample WMS read-only" in output
    assert "2. Open another WMS database" in output
    assert "3. Create or open a sandbox" in output
    assert "4. View quick help" in output
    assert "5. Exit" in output
    assert reader.prompts == [("Select an option: ", False)]
    assert "Goodbye." in output
    assert stderr.getvalue() == ""


def test_sandbox_menu_exposes_clone_open_and_back_options(tmp_path: Path) -> None:
    stdout = StringIO()

    run_console(
        stdout=stdout,
        stderr=StringIO(),
        resources=ResourceResolver(tmp_path),
        input_reader=ScriptedInput("3", "4", "5"),
    )

    output = stdout.getvalue()
    assert "Clone the included sample into a new sandbox" in output
    assert "Clone another schema-3 WMS into a new sandbox" in output
    assert "Open an existing verified sandbox" in output


def test_sample_selection_resolves_outside_cwd_and_preserves_checksum(
    console_wms_path: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    application_root = tmp_path / "bundle"
    sample = application_root / "sample-data" / "schema3_baseline.sqlite3"
    sample.parent.mkdir(parents=True)
    shutil.copy2(console_wms_path, sample)
    outside = tmp_path / "outside"
    outside.mkdir()
    monkeypatch.chdir(outside)
    before = _sha256(sample)
    stdout = StringIO()
    reader = ScriptedInput("1", "status", "exit")

    run_console(
        stdout=stdout,
        stderr=StringIO(),
        resources=ResourceResolver(application_root),
        input_reader=reader,
    )

    output = stdout.getvalue()
    assert "Database: schema3_baseline.sqlite3" in output
    assert "Mode: READ-ONLY" in output
    assert "WMS[RO:schema3_baseline]> " in [prompt for prompt, _ in reader.prompts]
    assert f"Working directory: {outside.resolve()}" in output
    assert _sha256(sample) == before


def test_command_loop_covers_lifecycle_factual_commands_and_quoted_path(
    console_wms_path: Path, tmp_path: Path
) -> None:
    spaced_path = tmp_path / "Warehouse Data" / "Console Sample.sqlite3"
    spaced_path.parent.mkdir()
    shutil.copy2(console_wms_path, spaced_path)
    before = _sha256(spaced_path)
    stdout = StringIO()
    stderr = StringIO()
    reader = ScriptedInput(
        "STATUS",
        "VaLiDaTe",
        "describe",
        "version",
        "help validate",
        "history",
        "close",
        f'OpEn "{spaced_path}"',
        "quit",
    )

    result = run_console(
        database_path=spaced_path,
        stdout=stdout,
        stderr=stderr,
        resources=ResourceResolver(tmp_path),
        input_reader=reader,
        no_style=True,
    )

    output = stdout.getvalue()
    assert result == 0
    assert "Schema: 3.0.0" in output
    assert "Validation status: PASS" in output
    assert "Schema-3 WMS description" in output
    assert "Run ID:" in output
    assert "Table counts:" in output
    assert "validate\n  Run hard schema-3 validation" in output
    assert "1: STATUS" in output
    assert "Database closed." in output
    assert output.count("Mode: READ-ONLY") == 3
    assert "Goodbye." in output
    assert "\x1b" not in output
    assert stderr.getvalue() == ""
    assert _sha256(spaced_path) == before


def test_ctrl_c_cancels_input_and_command_then_returns_to_prompt(
    console_wms_path: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def interrupt_validation(_session: ConsoleSession):
        raise KeyboardInterrupt

    monkeypatch.setattr(ConsoleSession, "validate_database", interrupt_validation)
    stdout = StringIO()
    reader = ScriptedInput(KeyboardInterrupt(), "validate", "status", "exit")

    run_console(
        database_path=console_wms_path,
        stdout=stdout,
        stderr=StringIO(),
        resources=ResourceResolver(tmp_path),
        input_reader=reader,
    )

    output = stdout.getvalue()
    assert output.count("Cancelled.") == 2
    assert "Session status" in output
    assert "Goodbye." in output


def test_eof_exits_cleanly_after_direct_open(console_wms_path: Path, tmp_path: Path) -> None:
    stdout = StringIO()

    result = run_console(
        database_path=console_wms_path,
        stdout=stdout,
        stderr=StringIO(),
        resources=ResourceResolver(tmp_path),
        input_reader=ScriptedInput(EOFError()),
    )

    assert result == 0
    assert "Goodbye." in stdout.getvalue()


@pytest.mark.parametrize(
    "submission",
    [
        "status\nhelp",
        "status\r\nhelp",
        "3: help\nhelp open\nhelp status\nhistory",
    ],
)
def test_multiline_submission_executes_nothing_and_preserves_active_session(
    submission: str, console_wms_path: Path, tmp_path: Path
) -> None:
    class NoDispatch:
        called = False

        def dispatch_line(self, _line: str):
            self.called = True
            raise AssertionError("multiline input reached command dispatch")

    source_hash = _sha256(console_wms_path)
    session = ConsoleSession(tmp_path, tmp_path / "workspace")
    session.open_database(console_wms_path)
    connection = session.connection
    state = (
        session.database_path,
        session.schema_version,
        session.run_id,
        session.facility_id,
        session.validation,
    )
    stdout = StringIO()
    stderr = StringIO()
    reader = ScriptedInput(submission, EOFError())
    dispatcher = NoDispatch()

    _run_command_loop(reader, ConsoleRenderer(stdout, stderr), session, dispatcher)

    assert not dispatcher.called
    assert reader.accepted_history == 0
    assert reader.discarded_history == 1
    assert list(session.command_history) == []
    assert session.connection is connection
    assert connection.execute("SELECT 1").fetchone()[0] == 1
    assert (
        session.database_path,
        session.schema_version,
        session.run_id,
        session.facility_id,
        session.validation,
    ) == state
    assert _sha256(console_wms_path) == source_hash
    assert stderr.getvalue() == (
        "Multiple commands in one submission are not supported.\n"
        "Enter or paste one command at a time.\n"
    )
    assert stdout.getvalue() == "Goodbye.\n"
    session.close()


def test_redirected_cli_output_has_no_ansi_and_runs_outside_repository(
    console_wms_path: Path, tmp_path: Path
) -> None:
    outside = tmp_path / "subprocess outside"
    outside.mkdir()

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "operational_variance_toolkit",
            "console",
            "--database",
            str(console_wms_path),
            "--no-style",
        ],
        input="status\nexit\n",
        capture_output=True,
        check=False,
        cwd=outside,
        text=True,
    )

    assert result.returncode == 0
    assert "WMS[RO:schema3_console]> " in result.stdout
    assert "Mode: READ-ONLY" in result.stdout
    assert "\x1b" not in result.stdout
    assert "\x1b" not in result.stderr


@pytest.mark.parametrize("command", ONE_SHOT_COMMANDS)
def test_existing_one_shot_subcommands_retain_help(command: str) -> None:
    parser = build_parser()

    with pytest.raises(SystemExit) as exit_info:
        parser.parse_args([command, "--help"])

    assert exit_info.value.code == 0
