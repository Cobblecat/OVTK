"""AST routing contracts; existing deferred routes have explicit G0 owners."""

from __future__ import annotations

import ast
import hashlib
import json
from collections import Counter
from pathlib import Path


def raw_routes(source: str) -> Counter[str]:
    tree = ast.parse(source)
    aliases = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            aliases.update({item.asname or item.name: item.name for item in node.names})
        elif isinstance(node, ast.ImportFrom):
            aliases.update(
                {item.asname or item.name: f"{node.module}.{item.name}" for item in node.names}
            )
    routes = Counter()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        call = ast.unparse(node.func)
        first = call.split(".")[0]
        canonical = call.replace(first, aliases.get(first, first), 1)
        base = canonical.rsplit(".", 1)[-1]
        category = None
        if canonical == "sqlite3.connect" or base in {
            "connect_database",
            "connect_readonly_database",
        }:
            category = "database"
        elif base in {"read_csv", "to_csv", "DictReader", "DictWriter", "reader", "writer"}:
            category = "analytical_csv"
        elif base == "Paragraph":
            category = "pdf_parser"
        elif base in {"print", "print_formatted_text", "_print_message"}:
            category = "terminal"
        elif base == "write" and ("stdout" in canonical or "stderr" in canonical):
            category = "terminal"
        elif base in {
            "rename",
            "replace",
            "unlink",
            "rmdir",
            "rmtree",
            "mkdir",
            "makedirs",
            "write_text",
            "write_bytes",
            "savefig",
            "copyfile",
            "copy2",
            "MoveFileExW",
            "mkdtemp",
            "mkstemp",
            "link",
            "open",
            "ZipFile",
        }:
            category = "publication_or_file_io"
        if category:
            signature = hashlib.sha256(
                ast.dump(node, include_attributes=False).encode()
            ).hexdigest()
            routes[f"{category}:{canonical}:{signature}"] += 1
    return routes


def test_raw_operations_match_reviewed_owners():
    root = Path(__file__).resolve().parents[1]
    contract = json.loads((root / "tests/security_routes.json").read_text())
    current = {}
    for path in sorted((root / "src").rglob("*.py")):
        routes = raw_routes(path.read_text(encoding="utf-8"))
        if routes:
            current[path.relative_to(root).as_posix()] = dict(routes)
    assert current == {path: record["routes"] for path, record in contract["files"].items()}, (
        "New or changed raw operation requires an explicit boundary/phase disposition"
    )


def test_aliases_new_sinks_and_modified_arguments_are_detected():
    baseline = raw_routes("import sqlite3; sqlite3.connect(path)")
    assert baseline != raw_routes("import sqlite3 as db; db.connect(path)")
    assert raw_routes("from sqlite3 import connect as open_db; open_db(path)")
    assert baseline != raw_routes("import sqlite3; sqlite3.connect(path, uri=False)")
    for source in [
        "print(data)",
        "sys.stderr.write(data)",
        "pd.read_csv(path)",
        "csv.DictWriter(handle)",
        "Paragraph(data, style)",
        "path.rename(final)",
    ]:
        assert raw_routes(source)
