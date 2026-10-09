"""Parsing and dispatch for the Phase 2 read-only console command surface."""

from __future__ import annotations

import re
import shlex
from dataclasses import dataclass
from pathlib import Path

from operational_variance_toolkit.console.rendering import ConsoleRenderer
from operational_variance_toolkit.console.resources import ResourceResolver
from operational_variance_toolkit.console.session import ConsoleSession
from operational_variance_toolkit.errors import RecordNotFoundError, ToolkitError
from operational_variance_toolkit.sandbox.application import clone_sandbox
from operational_variance_toolkit.version import get_version
from operational_variance_toolkit.wms.application.export import (
    export_master_csv,
    export_report_result,
    export_transactions_csv,
)
from operational_variance_toolkit.wms.application.inquiry import WmsInquiryService
from operational_variance_toolkit.wms.application.reports import available_reports, run_wms_report


class ConsoleCommandError(ValueError):
    """Expected command syntax or vocabulary error."""


class MultilineSubmissionError(ConsoleCommandError):
    """Raised before parsing when one submission contains line breaks."""


@dataclass(frozen=True, slots=True)
class ParsedCommand:
    verb: str
    arguments: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class DispatchResult:
    continue_running: bool = True
    succeeded: bool = True


COMMAND_HELP: dict[str, str] = {
    "open": "open <database>\n  Open an existing schema-3 WMS read-only.",
    "sample": "sample\n  Open the included sample WMS read-only.",
    "clone": (
        "clone <destination-database> | clone <source-database> <destination-database>\n"
        "  Create, verify, and open a schema-3.1.0 writable sandbox copy."
    ),
    "open-sandbox": (
        "open-sandbox <database>\n"
        "  Open only a schema-3.1.0 database with verified sandbox provenance."
    ),
    "close": "close\n  Close the active database and return to NO DB mode.",
    "status": "status\n  Show factual session settings and active database state.",
    "validate": "validate\n  Run hard schema-3 validation on the active database.",
    "describe": "describe\n  Show factual run metadata, counts, and inventory totals.",
    "item": "item <item-id> [--technical]\n  Show one item-master record.",
    "location": "location <location-id> [--technical]\n  Show one location-master record.",
    "inventory": (
        "inventory location <location-id> | inventory item <item-id> [--technical]\n"
        "  Show live recorded inventory by location or item."
    ),
    "trip": "trip <trip-id> [--technical]\n  Show one trip and factual recorded totals.",
    "pick": "pick <pick-event-id> [--technical]\n  Show one pick event.",
    "replenishment": ("replenishment <task-id> [--technical]\n  Show one replenishment task."),
    "qa": "qa <qa-event-id> [--technical]\n  Show one QA event.",
    "adjustment": ("adjustment <adjustment-id> [--technical]\n  Show one inventory adjustment."),
    "transactions": (
        "transactions item|location|group|command <id>\n"
        "  Show inventory transactions through an approved filter."
    ),
    "trace": (
        "trace <command-id | transaction-group-id | source-record-id>\n"
        "  Show command, workflow, transaction, and final recorded-state chronology."
    ),
    "reports": "reports\n  List the 12 registered standard WMS reports.",
    "report": (
        "report <report-name> [--parameter <value> ...]\n  Run a registered standard WMS report."
    ),
    "export": (
        "export report <report-name> <path> [--parameter <value> ...]\n"
        "export item-master|location-master|inventory-master <path>\n"
        "export inventory-transactions <path> [--filter <value> ...]"
    ),
    "set": (
        "set limit <n> | set format table|vertical | set timestamps utc|local|both\n"
        "  Change presentation settings for this session."
    ),
    "show": "show settings\n  Show active console presentation settings.",
    "version": "version\n  Show the installed toolkit version.",
    "help": "help [command]\n  Show all commands or detailed help for one command.",
    "history": "history\n  Show commands entered during this session.",
    "clear": "clear\n  Clear an interactive terminal; redirected output remains plain.",
    "exit": "exit\n  Close the active database and leave the console.",
    "quit": "quit\n  Alias for exit.",
}


def parse_command(line: str) -> ParsedCommand | None:
    if contains_line_break(line):
        raise MultilineSubmissionError
    if not line.strip():
        return None
    try:
        tokens = shlex.split(line, posix=False)
    except ValueError as exc:
        raise ConsoleCommandError(f"Unable to parse command: {exc}") from exc
    if not tokens:
        return None
    normalized = tuple(_remove_matching_quotes(token) for token in tokens)
    return ParsedCommand(normalized[0].lower(), normalized[1:])


class CommandDispatcher:
    def __init__(
        self,
        session: ConsoleSession,
        renderer: ConsoleRenderer,
        resources: ResourceResolver,
    ) -> None:
        self._session = session
        self._renderer = renderer
        self._resources = resources

    def dispatch_line(self, line: str) -> DispatchResult:
        try:
            command = parse_command(line)
            if command is None:
                return DispatchResult()
            return self.dispatch(command)
        except MultilineSubmissionError:
            self._renderer.multiline_submission_error()
            return DispatchResult(succeeded=False)
        except RecordNotFoundError as exc:
            self._renderer.not_found(str(exc))
            return DispatchResult(succeeded=False)
        except (ConsoleCommandError, ToolkitError) as exc:
            self._renderer.error(str(exc))
            return DispatchResult(succeeded=False)

    def dispatch(self, command: ParsedCommand) -> DispatchResult:
        handler = getattr(self, f"_handle_{command.verb.replace('-', '_')}", None)
        if handler is None or command.verb not in COMMAND_HELP:
            raise ConsoleCommandError(
                f"Unknown command: {command.verb}. Use help to list available commands."
            )
        return handler(command.arguments)

    def _handle_open(self, arguments: tuple[str, ...]) -> DispatchResult:
        _require_count("open", arguments, 1)
        path = self._resources.resolve_user_path(arguments[0], self._session.working_directory)
        self._session.open_database(path)
        self._renderer.opened_database(self._session)
        return DispatchResult()

    def _handle_sample(self, arguments: tuple[str, ...]) -> DispatchResult:
        _require_count("sample", arguments, 0)
        self._session.open_database(self._resources.sample_database(), provenance="included sample")
        self._renderer.opened_database(self._session)
        return DispatchResult()

    def _handle_clone(self, arguments: tuple[str, ...]) -> DispatchResult:
        if len(arguments) == 1:
            if self._session.database_path is None:
                raise ConsoleCommandError(
                    "clone <destination-database> requires an active source database"
                )
            source = self._session.database_path
            destination_value = arguments[0]
        elif len(arguments) == 2:
            source = self._resources.resolve_user_path(
                arguments[0], self._session.working_directory
            )
            destination_value = arguments[1]
        else:
            raise ConsoleCommandError(f"Usage: {COMMAND_HELP['clone'].splitlines()[0]}")
        destination = self._resources.resolve_user_path(
            destination_value, self._session.working_directory
        )
        result = clone_sandbox(source, destination)
        self._renderer.cloned_sandbox(result)
        self._session.open_sandbox(result.database_path)
        self._renderer.opened_database(self._session)
        return DispatchResult()

    def _handle_open_sandbox(self, arguments: tuple[str, ...]) -> DispatchResult:
        _require_count("open-sandbox", arguments, 1)
        path = self._resources.resolve_user_path(arguments[0], self._session.working_directory)
        self._session.open_sandbox(path)
        self._renderer.opened_database(self._session)
        return DispatchResult()

    def _handle_close(self, arguments: tuple[str, ...]) -> DispatchResult:
        _require_count("close", arguments, 0)
        if self._session.close_database():
            self._renderer.write("Database closed.")
        else:
            self._renderer.write("No database is open.")
        return DispatchResult()

    def _handle_status(self, arguments: tuple[str, ...]) -> DispatchResult:
        _require_count("status", arguments, 0)
        self._renderer.status(self._session)
        return DispatchResult()

    def _handle_validate(self, arguments: tuple[str, ...]) -> DispatchResult:
        _require_count("validate", arguments, 0)
        self._renderer.validation(self._session.validate_database())
        return DispatchResult()

    def _handle_describe(self, arguments: tuple[str, ...]) -> DispatchResult:
        _require_count("describe", arguments, 0)
        self._renderer.description(self._session.describe_database())
        return DispatchResult()

    def _handle_item(self, arguments: tuple[str, ...]) -> DispatchResult:
        identifier, technical = _detail_arguments("item", arguments)
        self._renderer.inquiry(
            self._inquiries().item(identifier), self._session, technical=technical
        )
        return DispatchResult()

    def _handle_location(self, arguments: tuple[str, ...]) -> DispatchResult:
        identifier, technical = _detail_arguments("location", arguments)
        self._renderer.inquiry(
            self._inquiries().location(identifier), self._session, technical=technical
        )
        return DispatchResult()

    def _handle_inventory(self, arguments: tuple[str, ...]) -> DispatchResult:
        if len(arguments) not in {2, 3} or (
            len(arguments) == 3 and arguments[2].lower() != "--technical"
        ):
            raise ConsoleCommandError(f"Usage: {COMMAND_HELP['inventory'].splitlines()[0]}")
        inquiry_type = arguments[0].lower()
        if inquiry_type == "location":
            result = self._inquiries().inventory_location(arguments[1])
        elif inquiry_type == "item":
            result = self._inquiries().inventory_item(arguments[1])
        else:
            raise ConsoleCommandError(f"Usage: {COMMAND_HELP['inventory'].splitlines()[0]}")
        self._renderer.inquiry(result, self._session, technical=len(arguments) == 3)
        return DispatchResult()

    def _handle_trip(self, arguments: tuple[str, ...]) -> DispatchResult:
        identifier, technical = _detail_arguments("trip", arguments)
        self._renderer.inquiry(
            self._inquiries().trip(identifier), self._session, technical=technical
        )
        return DispatchResult()

    def _handle_pick(self, arguments: tuple[str, ...]) -> DispatchResult:
        identifier, technical = _detail_arguments("pick", arguments)
        self._renderer.inquiry(
            self._inquiries().pick(identifier), self._session, technical=technical
        )
        return DispatchResult()

    def _handle_replenishment(self, arguments: tuple[str, ...]) -> DispatchResult:
        identifier, technical = _detail_arguments("replenishment", arguments)
        self._renderer.inquiry(
            self._inquiries().replenishment(identifier),
            self._session,
            technical=technical,
        )
        return DispatchResult()

    def _handle_qa(self, arguments: tuple[str, ...]) -> DispatchResult:
        identifier, technical = _detail_arguments("qa", arguments)
        self._renderer.inquiry(self._inquiries().qa(identifier), self._session, technical=technical)
        return DispatchResult()

    def _handle_adjustment(self, arguments: tuple[str, ...]) -> DispatchResult:
        identifier, technical = _detail_arguments("adjustment", arguments)
        self._renderer.inquiry(
            self._inquiries().adjustment(identifier),
            self._session,
            technical=technical,
        )
        return DispatchResult()

    def _handle_transactions(self, arguments: tuple[str, ...]) -> DispatchResult:
        _require_count("transactions", arguments, 2)
        filter_name = {
            "item": "item",
            "location": "location",
            "group": "transaction_group",
            "command": "command",
        }.get(arguments[0].lower())
        if filter_name is None:
            raise ConsoleCommandError(f"Usage: {COMMAND_HELP['transactions'].splitlines()[0]}")
        result = self._inquiries().transactions({filter_name: arguments[1]})
        self._renderer.inquiry(result, self._session)
        return DispatchResult()

    def _handle_trace(self, arguments: tuple[str, ...]) -> DispatchResult:
        _require_count("trace", arguments, 1)
        self._renderer.trace(self._inquiries().trace(arguments[0]), self._session)
        return DispatchResult()

    def _handle_reports(self, arguments: tuple[str, ...]) -> DispatchResult:
        _require_count("reports", arguments, 0)
        self._renderer.reports(available_reports())
        return DispatchResult()

    def _handle_report(self, arguments: tuple[str, ...]) -> DispatchResult:
        if not arguments:
            raise ConsoleCommandError(f"Usage: {COMMAND_HELP['report'].splitlines()[0]}")
        report_code = arguments[0].lower()
        parameters = _parse_options(arguments[1:])
        result = run_wms_report(self._database_path(), report_code, parameters)
        self._renderer.report(result, self._session)
        return DispatchResult()

    def _handle_export(self, arguments: tuple[str, ...]) -> DispatchResult:
        if len(arguments) < 2:
            raise ConsoleCommandError(f"Usage: {COMMAND_HELP['export'].splitlines()[0]}")
        export_type = arguments[0].lower()
        if export_type == "report":
            if len(arguments) < 3:
                raise ConsoleCommandError(f"Usage: {COMMAND_HELP['export'].splitlines()[0]}")
            report_code = arguments[1].lower()
            path = self._resolve_output_path(arguments[2])
            parameters = _parse_options(arguments[3:])
            report = run_wms_report(self._database_path(), report_code, parameters)
            result = export_report_result(report, path)
        elif export_type in {"item-master", "location-master", "inventory-master"}:
            if len(arguments) != 2:
                raise ConsoleCommandError(f"Usage: export {export_type} <path>")
            result = export_master_csv(
                self._session.connection,
                export_type,
                self._resolve_output_path(arguments[1]),
            )
        elif export_type == "inventory-transactions":
            path = self._resolve_output_path(arguments[1])
            filters = _parse_options(arguments[2:])
            result = export_transactions_csv(self._session.connection, path, filters)
        else:
            raise ConsoleCommandError(f"Unknown export type: {arguments[0]}")
        self._renderer.export(result)
        return DispatchResult()

    def _handle_set(self, arguments: tuple[str, ...]) -> DispatchResult:
        _require_count("set", arguments, 2)
        setting, value = arguments[0].lower(), arguments[1].lower()
        if setting == "limit":
            try:
                limit = int(value)
            except ValueError as exc:
                raise ConsoleCommandError("Result limit must be an integer from 1 to 1000") from exc
            if not 1 <= limit <= 1000:
                raise ConsoleCommandError("Result limit must be an integer from 1 to 1000")
            self._session.result_limit = limit
        elif setting == "format" and value in {"table", "vertical"}:
            self._session.display_format = value
        elif setting == "timestamps" and value in {"utc", "local", "both"}:
            self._session.timestamp_preference = value
        else:
            raise ConsoleCommandError(f"Usage: {COMMAND_HELP['set'].splitlines()[0]}")
        self._renderer.settings(self._session)
        return DispatchResult()

    def _handle_show(self, arguments: tuple[str, ...]) -> DispatchResult:
        _require_count("show", arguments, 1)
        if arguments[0].lower() != "settings":
            raise ConsoleCommandError("Usage: show settings")
        self._renderer.settings(self._session)
        return DispatchResult()

    def _handle_version(self, arguments: tuple[str, ...]) -> DispatchResult:
        _require_count("version", arguments, 0)
        self._renderer.write(f"Operational Variance Toolkit {get_version()}")
        return DispatchResult()

    def _handle_help(self, arguments: tuple[str, ...]) -> DispatchResult:
        if len(arguments) > 1:
            raise ConsoleCommandError("Usage: help [command]")
        if arguments:
            command_name = arguments[0].lower()
            help_text = COMMAND_HELP.get(command_name)
            if help_text is None:
                raise ConsoleCommandError(f"Unknown help topic: {arguments[0]}")
            for help_line in help_text.split("\n"):
                self._renderer.write(help_line)
            return DispatchResult()
        self._renderer.write("Available commands:")
        for command_name in COMMAND_HELP:
            self._renderer.write(f"  {COMMAND_HELP[command_name].splitlines()[0]}")
        self._renderer.write(
            'Quote database paths that contain spaces, for example: open "data files/wms.sqlite3"'
        )
        return DispatchResult()

    def _handle_history(self, arguments: tuple[str, ...]) -> DispatchResult:
        _require_count("history", arguments, 0)
        if not self._session.command_history:
            self._renderer.write("No commands in this session.")
            return DispatchResult()
        for number, line in enumerate(self._session.command_history, start=1):
            safe_line = re.sub(r"[\r\n]+", " ", line).strip()
            self._renderer.write(f"{number}: {safe_line}")
        return DispatchResult()

    def _handle_clear(self, arguments: tuple[str, ...]) -> DispatchResult:
        _require_count("clear", arguments, 0)
        self._renderer.clear()
        return DispatchResult()

    def _handle_exit(self, arguments: tuple[str, ...]) -> DispatchResult:
        _require_count("exit", arguments, 0)
        self._session.close()
        return DispatchResult(continue_running=False)

    def _handle_quit(self, arguments: tuple[str, ...]) -> DispatchResult:
        _require_count("quit", arguments, 0)
        self._session.close()
        return DispatchResult(continue_running=False)

    def _inquiries(self) -> WmsInquiryService:
        return WmsInquiryService(self._session.connection)

    def _database_path(self) -> Path:
        if self._session.database_path is None:
            self._session.connection
            raise AssertionError("unreachable")
        return self._session.database_path

    def _resolve_output_path(self, value: str) -> Path:
        return self._resources.resolve_user_path(value, self._session.working_directory)


def _remove_matching_quotes(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]
    return value


def contains_line_break(value: str) -> bool:
    return "\r" in value or "\n" in value


def _require_count(command: str, arguments: tuple[str, ...], count: int) -> None:
    if len(arguments) == count:
        return
    usage = COMMAND_HELP[command].splitlines()[0]
    if command == "open" and len(arguments) > 1:
        raise ConsoleCommandError(f"Usage: {usage}. Quote paths that contain spaces.")
    raise ConsoleCommandError(f"Usage: {usage}")


def _parse_options(arguments: tuple[str, ...]) -> dict[str, str]:
    parameters: dict[str, str] = {}
    index = 0
    while index < len(arguments):
        token = arguments[index]
        if "=" in token and not token.startswith("="):
            name, value = token.split("=", 1)
            name = name.removeprefix("--").replace("-", "_").lower()
            if not name or not value:
                raise ConsoleCommandError(f"Invalid parameter: {token}")
            index += 1
        elif token.startswith("--") and len(token) > 2:
            name = token[2:].replace("-", "_").lower()
            if index + 1 >= len(arguments):
                raise ConsoleCommandError(f"Missing value for parameter: {token}")
            value = arguments[index + 1]
            index += 2
        else:
            raise ConsoleCommandError(f"Invalid parameter syntax: {token}. Use --name <value>.")
        if name in parameters:
            raise ConsoleCommandError(f"Duplicate parameter: {name.replace('_', '-')}")
        parameters[name] = value
    return parameters


def _detail_arguments(command: str, arguments: tuple[str, ...]) -> tuple[str, bool]:
    if len(arguments) == 1:
        return arguments[0], False
    if len(arguments) == 2 and arguments[1].lower() == "--technical":
        return arguments[0], True
    raise ConsoleCommandError(f"Usage: {COMMAND_HELP[command].splitlines()[0]}")
