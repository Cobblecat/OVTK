"""Console startup menu and persistent input loop."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TextIO

from operational_variance_toolkit.console.commands import CommandDispatcher, contains_line_break
from operational_variance_toolkit.console.input import ConsoleInput, create_console_input
from operational_variance_toolkit.console.rendering import ConsoleRenderer
from operational_variance_toolkit.console.resources import ResourceResolver
from operational_variance_toolkit.console.session import ConsoleSession


def run_console(
    *,
    database_path: str | Path | None = None,
    sample: bool = False,
    output_directory: str | Path | None = None,
    no_style: bool = False,
    stdin: TextIO | None = None,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
    resources: ResourceResolver | None = None,
    input_reader: ConsoleInput | None = None,
) -> int:
    stdin = stdin or sys.stdin
    stdout = stdout or sys.stdout
    stderr = stderr or sys.stderr
    resources = resources or ResourceResolver.discover()
    working_directory = Path.cwd().resolve()
    resolved_output = resources.resolve_user_path(
        output_directory or "workspace", working_directory
    )
    renderer = ConsoleRenderer(stdout, stderr, no_style=no_style)
    reader = input_reader or create_console_input(stdin, stdout, resources.history_path())

    with ConsoleSession(
        working_directory=working_directory,
        output_directory=resolved_output,
    ) as session:
        dispatcher = CommandDispatcher(session, renderer, resources)
        if database_path is None and not sample:
            if not _run_start_menu(reader, renderer, resources, session, dispatcher):
                return 0
        else:
            renderer.banner()
            if sample:
                startup_command = "sample"
            else:
                startup_path = resources.resolve_user_path(database_path, working_directory)
                startup_command = f'open "{startup_path}"'
            result = dispatcher.dispatch_line(startup_command)
            if not result.succeeded:
                renderer.write("Continuing without an open database.")
        _run_command_loop(reader, renderer, session, dispatcher)
    return 0


def _run_start_menu(
    reader: ConsoleInput,
    renderer: ConsoleRenderer,
    resources: ResourceResolver,
    session: ConsoleSession,
    dispatcher: CommandDispatcher,
) -> bool:
    while True:
        renderer.banner()
        renderer.write()
        renderer.write("1. Open the included sample WMS read-only")
        renderer.write("2. Open another WMS database")
        renderer.write("3. Create or open a sandbox")
        renderer.write("4. View quick help")
        renderer.write("5. Exit")
        renderer.write()
        try:
            selection = reader.read("Select an option: ", record_history=False)
        except KeyboardInterrupt:
            renderer.write("Cancelled.")
            continue
        except EOFError:
            renderer.write("Goodbye.")
            return False

        if contains_line_break(selection):
            reader.discard_history()
            renderer.multiline_submission_error()
            continue
        selection = selection.strip()

        if selection == "1":
            result = dispatcher.dispatch_line("sample")
            if result.succeeded:
                return True
        elif selection == "2":
            try:
                path = reader.read("Database path: ", record_history=False)
            except KeyboardInterrupt:
                renderer.write("Cancelled.")
                continue
            except EOFError:
                renderer.write("Goodbye.")
                return False
            if contains_line_break(path):
                reader.discard_history()
                renderer.multiline_submission_error()
                continue
            path = path.strip()
            if not path:
                renderer.error("Database path is required.")
                continue
            resolved = resources.resolve_user_path(path, session.working_directory)
            result = dispatcher.dispatch_line(f'open "{resolved}"')
            if result.succeeded:
                return True
        elif selection == "3":
            sandbox_result = _run_sandbox_menu(reader, renderer, resources, session, dispatcher)
            if sandbox_result is None:
                return False
            if sandbox_result:
                return True
        elif selection == "4":
            dispatcher.dispatch_line("help")
            return True
        elif selection == "5":
            renderer.write("Goodbye.")
            return False
        else:
            renderer.error("Select 1, 2, 3, 4, or 5.")


def _run_sandbox_menu(
    reader: ConsoleInput,
    renderer: ConsoleRenderer,
    resources: ResourceResolver,
    session: ConsoleSession,
    dispatcher: CommandDispatcher,
) -> bool | None:
    renderer.write("Sandbox options")
    renderer.write("1. Clone the included sample into a new sandbox")
    renderer.write("2. Clone another schema-3 WMS into a new sandbox")
    renderer.write("3. Open an existing verified sandbox")
    renderer.write("4. Back")
    try:
        selection = reader.read("Select a sandbox option: ", record_history=False)
    except KeyboardInterrupt:
        renderer.write("Cancelled.")
        return False
    except EOFError:
        renderer.write("Goodbye.")
        return None
    if contains_line_break(selection):
        reader.discard_history()
        renderer.multiline_submission_error()
        return False
    selection = selection.strip()
    if selection == "4":
        return False
    if selection not in {"1", "2", "3"}:
        renderer.error("Select 1, 2, 3, or 4.")
        return False

    try:
        if selection == "1":
            source = resources.sample_database()
            destination = reader.read("New sandbox path: ", record_history=False)
            values = (str(source), destination)
            command = "clone"
        elif selection == "2":
            source = reader.read("Source database path: ", record_history=False)
            destination = reader.read("New sandbox path: ", record_history=False)
            values = (source, destination)
            command = "clone"
        else:
            database = reader.read("Existing sandbox path: ", record_history=False)
            values = (database,)
            command = "open-sandbox"
    except KeyboardInterrupt:
        renderer.write("Cancelled.")
        return False
    except EOFError:
        renderer.write("Goodbye.")
        return None
    if any(contains_line_break(value) for value in values):
        reader.discard_history()
        renderer.multiline_submission_error()
        return False
    if any(not value.strip() for value in values):
        renderer.error("All sandbox paths are required.")
        return False
    resolved = tuple(
        resources.resolve_user_path(value.strip(), session.working_directory) for value in values
    )
    line = command + " " + " ".join(f'"{path}"' for path in resolved)
    return dispatcher.dispatch_line(line).succeeded


def _run_command_loop(
    reader: ConsoleInput,
    renderer: ConsoleRenderer,
    session: ConsoleSession,
    dispatcher: CommandDispatcher,
) -> None:
    while True:
        try:
            line = reader.read(session.prompt)
        except KeyboardInterrupt:
            renderer.write("Cancelled.")
            continue
        except EOFError:
            renderer.write("Goodbye.")
            return

        if contains_line_break(line):
            reader.discard_history()
            renderer.multiline_submission_error()
            continue
        if not line.strip():
            reader.discard_history()
            continue
        reader.accept_history()
        session.record_command(line)
        try:
            result = dispatcher.dispatch_line(line)
        except KeyboardInterrupt:
            renderer.write("Cancelled.")
            continue
        if not result.continue_running:
            renderer.write("Goodbye.")
            return
