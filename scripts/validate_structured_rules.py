#!/usr/bin/env python3
"""Validate structured detector rule JSON/YAML files.

Usage:
    python scripts/validate_structured_rules.py [--json] RULE_FILE

This script performs static validation only. It does not evaluate detector rules,
call external APIs, or modify repository state.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

_PROJECT_ROOT = Path(__file__).parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from core.structured_validator import validate_rules_schema  # noqa: E402


class DuplicateKeyError(ValueError):
    """Raised when a JSON/YAML mapping contains a duplicate key."""


def _no_duplicate_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise DuplicateKeyError(f"duplicate key {key!r}")
        result[key] = value
    return result


def load_rules_file(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    suffix = path.suffix.lower()
    if suffix == ".json":
        return json.loads(text, object_pairs_hook=_no_duplicate_pairs)
    if suffix in {".yaml", ".yml"}:
        return _parse_simple_yaml(text)
    raise ValueError("unsupported file extension; expected .json, .yaml, or .yml")


def _parse_scalar(value: str) -> Any:
    if value in {"true", "false"}:
        return value == "true"
    if value == "[]":
        return []
    if value.startswith('"') and value.endswith('"'):
        return value[1:-1]
    if value.startswith("'") and value.endswith("'"):
        return value[1:-1]
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        return value


def _parse_simple_yaml(text: str) -> dict:
    """Parse the repository's documented YAML sketch subset.

    This intentionally small parser supports indented mappings, block lists, and
    scalar string/number/bool values. It rejects inline collections and advanced
    YAML features instead of attempting YAML-compatible interpretation.
    """
    root: dict[str, Any] = {}
    stack: list[tuple[int, Any]] = [(-1, root)]
    key_stack: list[tuple[int, str | None]] = [(-1, None)]

    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        if "\t" in raw_line:
            raise ValueError(f"line {line_number}: tabs are not supported")
        indent = len(raw_line) - len(raw_line.lstrip(" "))
        stripped = raw_line.strip()
        while stack and indent <= stack[-1][0]:
            stack.pop()
            key_stack.pop()
        parent = stack[-1][1]
        if stripped.startswith("- "):
            if not isinstance(parent, list):
                raise ValueError(f"line {line_number}: list item outside a list")
            item_text = stripped[2:].strip()
            if not item_text:
                item: Any = {}
                parent.append(item)
                stack.append((indent, item))
                key_stack.append((indent, None))
            elif ":" in item_text:
                key, value = item_text.split(":", 1)
                item = {}
                parent.append(item)
                _assign_yaml_key(item, key.strip(), value.strip(), line_number)
                stack.append((indent, item))
                key_stack.append((indent, key.strip()))
            else:
                parent.append(_parse_scalar(item_text))
            continue
        if ":" not in stripped:
            raise ValueError(f"line {line_number}: expected key/value mapping")
        key, value = stripped.split(":", 1)
        key = key.strip()
        value = value.strip()
        if not isinstance(parent, dict):
            raise ValueError(f"line {line_number}: mapping entry outside an object")
        if key in parent:
            raise DuplicateKeyError(f"line {line_number}: duplicate key {key!r}")
        if value:
            if value not in {"[]"} and (value.startswith("[") or value.startswith("{")):
                raise ValueError(f"line {line_number}: inline YAML collections are not supported")
            parent[key] = _parse_scalar(value)
            continue
        # Look ahead by structure is deliberately simple: plural/list-like keys are lists.
        child: Any = [] if key in {"fields", "normalization", "rules", "matched_signals"} else {}
        parent[key] = child
        stack.append((indent, child))
        key_stack.append((indent, key))
    return root


def _assign_yaml_key(item: dict[str, Any], key: str, value: str, line_number: int) -> None:
    if key in item:
        raise DuplicateKeyError(f"line {line_number}: duplicate key {key!r}")
    if not value:
        raise ValueError(f"line {line_number}: nested list-item mappings are not supported")
    item[key] = _parse_scalar(value)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate a structured detector rules file.")
    parser.add_argument("rules_file", type=Path)
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    args = parser.parse_args(argv)

    try:
        data = load_rules_file(args.rules_file)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        result = {"success": False, "violations": [f"{args.rules_file}: {exc}"]}
    else:
        result = validate_rules_schema(data)

    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    elif result["success"]:
        print(f"{args.rules_file}: structured detector rules schema validation passed")
    else:
        print(f"{args.rules_file}: structured detector rules schema validation failed")
        for violation in result["violations"]:
            print(f"- {violation}")
    return 0 if result["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
