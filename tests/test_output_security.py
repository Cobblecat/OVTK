from __future__ import annotations

from io import StringIO
from pathlib import Path

import pytest

from operational_variance_toolkit.cli import _print_report_result, main
from operational_variance_toolkit.console.commands import COMMAND_HELP, CommandDispatcher
from operational_variance_toolkit.console.output import terminal_text
from operational_variance_toolkit.console.rendering import ConsoleRenderer
from operational_variance_toolkit.console.resources import ResourceResolver
from operational_variance_toolkit.console.session import ConsoleSession
from operational_variance_toolkit.wms.domain.inquiry import InquiryResult, TraceResult
from operational_variance_toolkit.wms.domain.reports import ReportResult, ReportSpec

CONTROLS = "\x1b[2J\x1b]8;;link\x07\x9b31m\r\n\t\b\x00\x7f"


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("\x1b[2J", r"\x1b[2J"),
        ("\r", r"\r"),
        ("\n", r"\n"),
        ("\t", r"\t"),
        ("\x9b", r"\x9b"),
        ("\x00", r"\x00"),
        ("\x7f", r"\x7f"),
        ("café 漢字", "café 漢字"),
    ],
)
def test_cli_parser_errors_encode_argument_data_and_keep_usage(
    value: str, expected: str, capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(SystemExit) as exc:
        main(["console", f"--unknown=prefix{value}suffix"])

    assert exc.value.code == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.startswith("usage: operational-variance-toolkit ")
    assert "\n" in captured.err
    assert captured.err.endswith(
        f"error: unrecognized arguments: --unknown=prefix{expected}suffix\n"
    )
    assert all(
        character == "\n" or (ord(character) >= 32 and not 127 <= ord(character) <= 159)
        for character in captured.err
    )


def test_cli_subcommand_help_retains_structural_lines(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        main(["console", "--help"])

    assert exc.value.code == 0
    captured = capsys.readouterr()
    assert captured.err == ""
    assert captured.out.startswith("usage: operational-variance-toolkit console ")
    assert "\noptions:\n" in captured.out
    assert "--database DATABASE" in captured.out
    assert r"\n" not in captured.out


@pytest.mark.parametrize("code", [*range(32), *range(127, 160)])
def test_terminal_control_bytes_are_visible_text(code: int) -> None:
    encoded = terminal_text("café " + chr(code) + " 漢字")
    assert encoded.startswith("café ") and encoded.endswith(" 漢字")
    assert chr(code) not in encoded


@pytest.mark.parametrize("display_format", ["table", "vertical"])
def test_inquiry_encodes_controls_before_layout_and_emission(
    display_format: str, tmp_path: Path
) -> None:
    stdout, stderr = StringIO(), StringIO()
    renderer = ConsoleRenderer(stdout, stderr)
    session = ConsoleSession(tmp_path, tmp_path, display_format=display_format)
    # A marker near the table truncation boundary must never reach the stream as ESC.
    description = "x" * 26 + CONTROLS
    renderer.inquiry(
        InquiryResult("Item", ("item_description", "recorded_utc"), ((description, CONTROLS),), 1),
        session,
    )
    output = stdout.getvalue()
    assert "\x1b" not in output and "\x9b" not in output and "\r" not in output
    assert all(ord(character) >= 32 or character == "\n" for character in output)
    if display_format == "vertical":
        assert r"\x1b[2J" in output and r"\r\n\t" in output


def test_terminal_metadata_trace_errors_and_prompt_share_literal_encoding(tmp_path: Path) -> None:
    stdout, stderr = StringIO(), StringIO()
    renderer = ConsoleRenderer(stdout, stderr)
    session = ConsoleSession(tmp_path, tmp_path, database_path=Path("dataset\x1b[2J.sqlite3"))
    session.run_id = CONTROLS
    session.facility_name = CONTROLS
    renderer.status(session)
    command = InquiryResult(
        "Commands",
        (
            "command_id",
            "command_type",
            "result_record_type",
            "result_record_id",
            "event_sequence",
            "event_utc",
            "recorded_utc",
        ),
        ((CONTROLS, "Pick", "PICK", CONTROLS, 1, "2026-01-01T00:00:00Z", "2026-01-01T00:00:00Z"),),
        1,
    )
    empty = InquiryResult("Empty", (), (), 0)
    renderer.trace(
        TraceResult(CONTROLS, "command_id", command, empty, empty, empty, 0, "BALANCED"), session
    )
    renderer.error(CONTROLS)
    renderer.not_found(CONTROLS)
    combined = stdout.getvalue() + stderr.getvalue() + session.prompt
    assert "\x1b" not in combined and "\x9b" not in combined and "\r" not in combined
    assert r"\x1b[2J" in combined and r"\r\n\t" in combined
    assert session.prompt == r"WMS[RO:dataset\x1b[2J]> "


def test_trusted_help_retains_its_line_structure(tmp_path: Path) -> None:
    stdout, stderr = StringIO(), StringIO()
    dispatcher = CommandDispatcher(
        ConsoleSession(tmp_path, tmp_path),
        ConsoleRenderer(stdout, stderr),
        ResourceResolver(tmp_path),
    )
    assert dispatcher.dispatch_line("help export").succeeded
    assert stdout.getvalue() == COMMAND_HELP["export"] + "\n"
    assert stderr.getvalue() == ""


def test_cli_report_cells_are_literal_but_column_separators_remain_tabs(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    result = ReportResult(
        ReportSpec("test", "Test", ("item_id", "item_description")),
        tmp_path / "wms.sqlite3",
        CONTROLS,
        "3.0.0",
        "now",
        "now",
        {},
        (("ITEM-0001", CONTROLS),),
    )
    _print_report_result(result, None)
    output = capsys.readouterr().out
    assert "\x1b" not in output and "\x9b" not in output and "\r" not in output
    assert "Item ID\titem_description\n" in output
    assert f"ITEM-0001\t{terminal_text(CONTROLS)}\n" in output
