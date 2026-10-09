from __future__ import annotations

import json
from io import StringIO
from pathlib import Path

import pytest

from operational_variance_toolkit.console import input as input_module
from operational_variance_toolkit.console.input import BoundedFileHistory, PlainStreamInput
from operational_variance_toolkit.console.resources import ResourceResolver
from operational_variance_toolkit.errors import DatabaseError


def test_resource_resolver_finds_bundle_sample_outside_process_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    application_root = tmp_path / "bundle"
    sample = application_root / "sample-data" / "schema3_baseline.sqlite3"
    sample.parent.mkdir(parents=True)
    sample.write_bytes(b"sample")
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)

    resolver = ResourceResolver(application_root)

    assert resolver.sample_database() == sample.resolve()
    assert (
        resolver.resolve_user_path("relative.sqlite3", elsewhere)
        == (elsewhere / "relative.sqlite3").resolve()
    )
    assert (
        resolver.resolve_user_path('"path with spaces.sqlite3"', elsewhere)
        == (elsewhere / "path with spaces.sqlite3").resolve()
    )


def test_resource_resolver_reports_missing_sample(tmp_path: Path) -> None:
    with pytest.raises(DatabaseError, match="Included sample WMS is unavailable"):
        ResourceResolver(tmp_path).sample_database()


def test_bounded_history_persists_only_recent_json_lines(tmp_path: Path) -> None:
    history_path = tmp_path / "history.jsonl"
    history = BoundedFileHistory(history_path, max_entries=2)

    history.store_string("status")
    history.store_string('open "database.sqlite3"')
    history.store_string("validate")

    assert list(BoundedFileHistory(history_path).load_history_strings()) == [
        "validate",
        'open "database.sqlite3"',
    ]
    assert all(isinstance(json.loads(line), str) for line in history_path.read_text().splitlines())


def test_bounded_history_defers_persistence_until_submission_is_accepted(tmp_path: Path) -> None:
    history_path = tmp_path / "history.jsonl"
    history = BoundedFileHistory(history_path)

    history.append_string("status\nhelp")
    history.discard_pending()
    assert not history_path.exists()
    assert history.get_strings() == []

    history.append_string("status")
    history.accept_pending()
    assert list(BoundedFileHistory(history_path).load_history_strings()) == ["status"]


@pytest.mark.parametrize("stream_value", ["status\n", "status\r\n"])
def test_redirected_stream_uses_plain_input_without_terminal_sequences(
    stream_value: str, tmp_path: Path
) -> None:
    stdin = StringIO(stream_value)
    stdout = StringIO()

    reader = input_module.create_console_input(stdin, stdout, tmp_path / "history")

    assert isinstance(reader, PlainStreamInput)
    assert reader.read("WMS[NO DB]> ") == "status"
    assert stdout.getvalue() == "WMS[NO DB]> "
    assert "\x1b" not in stdout.getvalue()


def test_interactive_stream_selects_prompt_toolkit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class TtyStream(StringIO):
        def isatty(self) -> bool:
            return True

    sentinel = object()
    monkeypatch.setattr(input_module, "PromptToolkitInput", lambda _path: sentinel)

    assert (
        input_module.create_console_input(TtyStream(), TtyStream(), tmp_path / "history")
        is sentinel
    )
