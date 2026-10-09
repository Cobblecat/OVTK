"""Interactive and redirected console input adapters."""

from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path
from typing import Protocol, TextIO

from prompt_toolkit import PromptSession
from prompt_toolkit.history import History, InMemoryHistory

MAX_PERSISTED_HISTORY = 500


class ConsoleInput(Protocol):
    def read(self, prompt: str, *, record_history: bool = True) -> str: ...

    def accept_history(self) -> None: ...

    def discard_history(self) -> None: ...


class BoundedFileHistory(History):
    """Small JSON-lines history store containing console commands only."""

    def __init__(self, path: Path, *, max_entries: int = MAX_PERSISTED_HISTORY) -> None:
        super().__init__()
        self._path = path
        self._max_entries = max_entries
        self._pending: str | None = None

    def append_string(self, string: str) -> None:
        self._pending = string

    def accept_pending(self) -> None:
        if self._pending is None:
            return
        value = self._pending
        self._pending = None
        super().append_string(value)

    def discard_pending(self) -> None:
        self._pending = None

    def load_history_strings(self) -> Iterable[str]:
        yield from reversed(self._read_entries())

    def store_string(self, string: str) -> None:
        entries = self._read_entries()
        entries.append(string)
        entries = entries[-self._max_entries :]
        self._path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = self._path.with_suffix(f"{self._path.suffix}.tmp")
        temporary_path.write_text(
            "".join(f"{json.dumps(value, ensure_ascii=True)}\n" for value in entries),
            encoding="utf-8",
        )
        temporary_path.replace(self._path)

    def _read_entries(self) -> list[str]:
        if not self._path.is_file():
            return []
        entries: list[str] = []
        for line in self._path.read_text(encoding="utf-8").splitlines():
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(value, str) and value:
                entries.append(value)
        return entries[-self._max_entries :]


class PromptToolkitInput:
    def __init__(self, history_path: Path) -> None:
        self._history = BoundedFileHistory(history_path)
        self._command_session: PromptSession[str] = PromptSession(
            history=self._history,
            enable_history_search=True,
        )
        self._menu_session: PromptSession[str] = PromptSession(history=InMemoryHistory())

    def read(self, prompt: str, *, record_history: bool = True) -> str:
        if record_history:
            self._history.discard_pending()
        session = self._command_session if record_history else self._menu_session
        return session.prompt(prompt)

    def accept_history(self) -> None:
        self._history.accept_pending()

    def discard_history(self) -> None:
        self._history.discard_pending()


class PlainStreamInput:
    def __init__(self, stdin: TextIO, stdout: TextIO) -> None:
        self._stdin = stdin
        self._stdout = stdout

    def read(self, prompt: str, *, record_history: bool = True) -> str:
        del record_history
        self._stdout.write(prompt)
        self._stdout.flush()
        line = self._stdin.readline()
        if line == "":
            raise EOFError
        if line.endswith("\n"):
            line = line[:-1]
            if line.endswith("\r"):
                line = line[:-1]
        return line

    def accept_history(self) -> None:
        pass

    def discard_history(self) -> None:
        pass


def create_console_input(stdin: TextIO, stdout: TextIO, history_path: Path) -> ConsoleInput:
    if stdin.isatty() and stdout.isatty():
        return PromptToolkitInput(history_path)
    return PlainStreamInput(stdin, stdout)
