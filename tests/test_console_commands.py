from __future__ import annotations

from io import StringIO
from pathlib import Path

import pytest

from operational_variance_toolkit.console.commands import (
    CommandDispatcher,
    ConsoleCommandError,
    MultilineSubmissionError,
    parse_command,
)
from operational_variance_toolkit.console.rendering import ConsoleRenderer
from operational_variance_toolkit.console.resources import ResourceResolver
from operational_variance_toolkit.console.session import ConsoleSession


def _dispatcher(tmp_path: Path) -> tuple[ConsoleSession, CommandDispatcher, StringIO, StringIO]:
    stdout = StringIO()
    stderr = StringIO()
    session = ConsoleSession(tmp_path, tmp_path / "workspace")
    dispatcher = CommandDispatcher(
        session,
        ConsoleRenderer(stdout, stderr),
        ResourceResolver(tmp_path),
    )
    return session, dispatcher, stdout, stderr


def test_parser_preserves_quoted_windows_path_and_normalizes_only_verb() -> None:
    command = parse_command(r'OpEn "C:\Warehouse Data\Mixed Case.sqlite3"')

    assert command is not None
    assert command.verb == "open"
    assert command.arguments == (r"C:\Warehouse Data\Mixed Case.sqlite3",)


def test_parser_rejects_unclosed_quote_and_ignores_blank_input() -> None:
    assert parse_command("   ") is None
    with pytest.raises(ConsoleCommandError, match="Unable to parse command"):
        parse_command('open "unfinished')


@pytest.mark.parametrize(
    "submission",
    ["status\nhelp", "status\rhelp", "status\r\nhelp"],
)
def test_parser_rejects_line_breaks_before_tokenization(submission: str) -> None:
    with pytest.raises(MultilineSubmissionError):
        parse_command(submission)


def test_dispatcher_renders_exact_multiline_rejection_without_dispatch(tmp_path: Path) -> None:
    session, dispatcher, stdout, stderr = _dispatcher(tmp_path)

    result = dispatcher.dispatch_line("3: help\nhelp open\nhelp status")

    assert not result.succeeded
    assert session.mode.value == "NO DB"
    assert not session.command_history
    assert stdout.getvalue() == ""
    assert stderr.getvalue() == (
        "Multiple commands in one submission are not supported.\n"
        "Enter or paste one command at a time.\n"
    )


def test_dispatch_reports_missing_arguments_unknown_commands_and_path_guidance(
    tmp_path: Path,
) -> None:
    _session, dispatcher, _stdout, stderr = _dispatcher(tmp_path)

    assert not dispatcher.dispatch_line("open").succeeded
    assert not dispatcher.dispatch_line("open a path with spaces.sqlite3").succeeded
    assert not dispatcher.dispatch_line("inventory unknown ITEM-0001").succeeded

    errors = stderr.getvalue()
    assert "Usage: open <database>" in errors
    assert "Quote paths that contain spaces" in errors
    assert "Usage: inventory location" in errors


def test_help_version_status_history_and_clear_are_plain_and_case_insensitive(
    tmp_path: Path,
) -> None:
    session, dispatcher, stdout, stderr = _dispatcher(tmp_path)
    session.record_command("HeLp open")
    session.record_command("STATUS")

    for command in ("HeLp OpEn", "VERSION", "STATUS", "history", "clear"):
        assert dispatcher.dispatch_line(command).succeeded

    output = stdout.getvalue()
    assert "open <database>" in output
    assert "Operational Variance Toolkit" in output
    assert "Mode: NO DATABASE" in output
    assert "Result limit: 25" in output
    assert "Display format: vertical" in output
    assert "Timestamp preference: utc" in output
    assert "1: HeLp open" in output
    assert "\x1b" not in output
    assert stderr.getvalue() == ""


def test_validate_describe_and_unknown_help_require_expected_context(tmp_path: Path) -> None:
    _session, dispatcher, _stdout, stderr = _dispatcher(tmp_path)

    assert not dispatcher.dispatch_line("validate").succeeded
    assert not dispatcher.dispatch_line("describe").succeeded
    assert not dispatcher.dispatch_line("help arbitrary-sql").succeeded

    errors = stderr.getvalue()
    assert errors.count("No database is open") == 2
    assert "Unknown help topic: arbitrary-sql" in errors


def test_history_defensively_renders_unexpected_line_breaks_on_one_line(tmp_path: Path) -> None:
    session, dispatcher, stdout, stderr = _dispatcher(tmp_path)
    session.command_history.append("3: help\r\nhelp open\nhelp status\rversion")

    assert dispatcher.dispatch_line("history").succeeded

    assert stdout.getvalue() == "1: 3: help help open help status version\n"
    assert "\r" not in stdout.getvalue()
    assert stderr.getvalue() == ""
