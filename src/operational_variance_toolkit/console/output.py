"""Literal text encoding at terminal output boundaries."""

from __future__ import annotations

from typing import TextIO


def terminal_text(value: object) -> str:
    """Make C0, DEL and C1 controls visible without changing printable text."""

    escapes = {"\n": r"\n", "\r": r"\r", "\t": r"\t"}
    return "".join(
        escapes.get(character, f"\\x{ord(character):02x}")
        if ord(character) < 32 or 127 <= ord(character) <= 159
        else character
        for character in str(value)
    )


def write_line(message: object = "", *, file: TextIO | None = None) -> None:
    """Write one data-safe line; the terminating newline belongs to the renderer."""

    print(terminal_text(message), file=file)
