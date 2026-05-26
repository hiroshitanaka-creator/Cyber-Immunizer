"""scripts/validate_mutation.py — AST and contract validation for candidate detectors.

Usage:
    python scripts/validate_mutation.py --candidate core/detector.py [--json]

Exit codes:
    0  Validation passed
    1  Validation failed (see output for reasons)
"""
from __future__ import annotations

import argparse
import ast
import json
import sys
from pathlib import Path

# Ensure project root is on sys.path when run as a script
_PROJECT_ROOT = Path(__file__).parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# ---------------------------------------------------------------------------
# Policy constants
# ---------------------------------------------------------------------------

_FORBIDDEN_BUILTINS: frozenset[str] = frozenset(
    {
        "eval", "exec", "compile", "__import__", "open",
        "globals", "locals", "vars", "input",
        "getattr", "setattr", "delattr",
    }
)

_FORBIDDEN_MODULES: frozenset[str] = frozenset(
    {
        "os", "subprocess", "socket", "pathlib", "shutil",
        "requests", "urllib", "sys",
    }
)

_FORBIDDEN_DUNDERS: frozenset[str] = frozenset(
    {
        "__class__", "__dict__", "__globals__", "__subclasses__",
        "__builtins__", "__code__", "__bases__", "__mro__",
    }
)

_ALLOWED_IMPORT_MODULE = "core.types"
_MUTATION_START = "# === MUTATION_START ==="
_MUTATION_END = "# === MUTATION_END ==="


# ---------------------------------------------------------------------------
# Individual validation steps
# ---------------------------------------------------------------------------

def _check_syntax(source: str) -> list[str]:
    violations: list[str] = []
    try:
        ast.parse(source)
    except SyntaxError as exc:
        violations.append(f"SyntaxError: {exc}")
    return violations


def _check_mutation_markers(source: str) -> list[str]:
    violations: list[str] = []
    if _MUTATION_START not in source:
        violations.append(f"missing mutation marker: {_MUTATION_START!r}")
    if _MUTATION_END not in source:
        violations.append(f"missing mutation marker: {_MUTATION_END!r}")
    return violations


def _check_imports(tree: ast.Module) -> list[str]:
    """Only allow 'from core.types import Request, DetectionResult'."""
    violations: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                base = alias.name.split(".")[0]
                if base in _FORBIDDEN_MODULES:
                    violations.append(f"forbidden import: {alias.name!r}")
                elif alias.name != _ALLOWED_IMPORT_MODULE:
                    violations.append(
                        f"non-allowed bare import: {alias.name!r} "
                        f"(only 'from {_ALLOWED_IMPORT_MODULE} import ...' is allowed)"
                    )

        if isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            base = mod.split(".")[0]
            if base in _FORBIDDEN_MODULES:
                violations.append(f"forbidden import-from module: {mod!r}")
            elif mod != _ALLOWED_IMPORT_MODULE:
                violations.append(
                    f"non-allowed import-from: {mod!r} "
                    f"(only {_ALLOWED_IMPORT_MODULE!r} is allowed)"
                )
    return violations


def _check_forbidden_calls(tree: ast.Module) -> list[str]:
    violations: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name) and func.id in _FORBIDDEN_BUILTINS:
                violations.append(f"forbidden call: {func.id}()")
            if isinstance(func, ast.Attribute) and func.attr in _FORBIDDEN_BUILTINS:
                violations.append(f"forbidden attribute call: .{func.attr}()")
    return violations


def _check_forbidden_dunders(tree: ast.Module) -> list[str]:
    violations: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and node.attr in _FORBIDDEN_DUNDERS:
            violations.append(f"forbidden dunder access: .{node.attr}")
    return violations


def _check_top_level_structure(tree: ast.Module) -> list[str]:
    """Enforce that top-level contains only: docstring, allowed import, inspect_request def."""
    violations: list[str] = []
    for i, stmt in enumerate(tree.body):
        # First statement may be a module docstring
        if i == 0 and isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant):
            continue
        # Allowed: the single permitted import
        if isinstance(stmt, (ast.Import, ast.ImportFrom)):
            continue
        # Allowed: the inspect_request function definition
        if isinstance(stmt, ast.FunctionDef) and stmt.name == "inspect_request":
            continue
        # Anything else is a violation
        violations.append(
            f"unexpected top-level statement at line {stmt.lineno}: "
            f"{type(stmt).__name__}"
        )
    return violations


def _check_inspect_request_signature(tree: ast.Module) -> list[str]:
    """Verify inspect_request has exactly (request: Request) -> DetectionResult."""
    violations: list[str] = []
    fn_nodes = [
        n for n in tree.body
        if isinstance(n, ast.FunctionDef) and n.name == "inspect_request"
    ]
    if not fn_nodes:
        violations.append("inspect_request function not found")
        return violations

    fn = fn_nodes[0]
    args = fn.args

    # Exactly one positional argument named 'request'
    all_args = args.args + args.posonlyargs + args.kwonlyargs
    if len(all_args) != 1 or all_args[0].arg != "request":
        violations.append(
            f"inspect_request must have exactly one argument named 'request', "
            f"got: {[a.arg for a in all_args]}"
        )
    if args.vararg or args.kwarg:
        violations.append("inspect_request must not use *args or **kwargs")

    # Return annotation must reference DetectionResult
    if fn.returns is None:
        violations.append("inspect_request is missing a return annotation")
    else:
        ann_src = ast.unparse(fn.returns)
        if "DetectionResult" not in ann_src:
            violations.append(
                f"inspect_request return annotation must reference DetectionResult, "
                f"got: {ann_src!r}"
            )

    return violations


def _check_extra_function_defs(tree: ast.Module) -> list[str]:
    """Warn if top-level functions other than inspect_request are defined."""
    violations: list[str] = []
    for stmt in tree.body:
        if isinstance(stmt, ast.FunctionDef) and stmt.name != "inspect_request":
            violations.append(
                f"extra top-level function defined: {stmt.name!r} "
                f"(only inspect_request is permitted)"
            )
        if isinstance(stmt, ast.AsyncFunctionDef):
            violations.append(
                f"async function defined: {stmt.name!r} (not permitted)"
            )
        if isinstance(stmt, ast.ClassDef):
            violations.append(
                f"top-level class defined: {stmt.name!r} (not permitted)"
            )
    return violations


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def validate(candidate_path: Path) -> dict:
    """Validate a candidate detector file.

    Returns a dict with:
        valid: bool
        violations: list[str]
    """
    if not candidate_path.exists():
        return {"valid": False, "violations": [f"file not found: {candidate_path}"]}

    source = candidate_path.read_text(encoding="utf-8")
    violations: list[str] = []

    # 1. Syntax
    violations.extend(_check_syntax(source))
    if violations:
        return {"valid": False, "violations": violations}

    # 2. Mutation markers
    violations.extend(_check_mutation_markers(source))

    # Parse AST for remaining checks
    tree = ast.parse(source)

    # 3. Imports
    violations.extend(_check_imports(tree))

    # 4. Forbidden calls
    violations.extend(_check_forbidden_calls(tree))

    # 5. Dunder attribute access
    violations.extend(_check_forbidden_dunders(tree))

    # 6. Top-level structure
    violations.extend(_check_top_level_structure(tree))

    # 7. inspect_request signature
    violations.extend(_check_inspect_request_signature(tree))

    # 8. Extra function/class definitions
    violations.extend(_check_extra_function_defs(tree))

    valid = len(violations) == 0
    return {"valid": valid, "violations": violations}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Cyber-Immunizer mutation validator")
    parser.add_argument("--candidate", required=True, help="Path to candidate detector")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    args = parser.parse_args(argv)

    result = validate(Path(args.candidate))

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        if result["valid"]:
            print("VALID: candidate passes all AST policy checks")
        else:
            print(f"INVALID: {len(result['violations'])} violation(s)")
            for v in result["violations"]:
                print(f"  - {v}")

    return 0 if result["valid"] else 1


if __name__ == "__main__":
    sys.exit(main())
