"""core/policy.py — Authoritative AST safety policy for candidate detectors.

This is the single source of truth for all policy checks.
Both scripts/validate_mutation.py and core/fitness.py MUST import from here.
Defining separate, divergent policy copies is prohibited.

Policy philosophy: false rejection is acceptable; false acceptance is not.
"""
from __future__ import annotations

import ast
from pathlib import Path

# ---------------------------------------------------------------------------
# Policy constants
# ---------------------------------------------------------------------------

#: Builtins that are forbidden inside a candidate detector.
FORBIDDEN_BUILTINS: frozenset[str] = frozenset({
    # Code execution / compilation
    "eval", "exec", "compile",
    # Import machinery
    "__import__",
    # File I/O
    "open",
    # Introspection / reflection
    "globals", "locals", "vars", "input",
    "getattr", "setattr", "delattr",
    # Type / meta introspection — unsafe in generated code
    "type", "dir", "super", "breakpoint", "callable",
})

#: Module names whose import is forbidden (base module only, e.g. "os" catches "os.path").
FORBIDDEN_MODULES: frozenset[str] = frozenset({
    "os", "subprocess", "socket", "pathlib", "shutil",
    "requests", "urllib", "sys",
})

#: The only import allowed in a candidate detector.
ALLOWED_IMPORT_MODULE: str = "core.types"

#: Mutation boundary markers.
MUTATION_START: str = "# === MUTATION_START ==="
MUTATION_END: str = "# === MUTATION_END ==="

# ---------------------------------------------------------------------------
# AST complexity limits — fail-closed DoS guard
# ---------------------------------------------------------------------------

#: Maximum source text length (characters) before ast.parse is attempted.
MAX_POLICY_SOURCE_CHARS: int = 20_000

#: Maximum number of AST nodes in a candidate.
MAX_AST_NODES: int = 1_500

#: Maximum AST nesting depth.
MAX_AST_DEPTH: int = 50

#: Maximum length (characters) of any single string or bytes literal.
MAX_LITERAL_CHARS: int = 5_000

#: Maximum number of elements in any single list/tuple/set/dict literal.
MAX_COLLECTION_ITEMS: int = 1_000


# ---------------------------------------------------------------------------
# Individual check functions (each returns a list of violation strings)
# ---------------------------------------------------------------------------

def check_syntax(source: str) -> list[str]:
    """Return a SyntaxError description, or [] if source parses cleanly."""
    try:
        ast.parse(source)
        return []
    except SyntaxError as exc:
        return [f"SyntaxError: {exc}"]


def check_mutation_markers(source: str) -> list[str]:
    """Require exactly one MUTATION_START and one MUTATION_END marker."""
    violations: list[str] = []
    for marker in (MUTATION_START, MUTATION_END):
        count = source.count(marker)
        if count == 0:
            violations.append(f"missing mutation marker: {marker!r}")
        elif count > 1:
            violations.append(
                f"duplicate mutation marker: {marker!r} "
                f"(found {count}, expected exactly 1)"
            )
    return violations


def check_imports(tree: ast.Module) -> list[str]:
    """Only 'from core.types import ...' is allowed; all others are violations."""
    violations: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                base = alias.name.split(".")[0]
                if base in FORBIDDEN_MODULES:
                    violations.append(f"forbidden import: {alias.name!r}")
                elif alias.name != ALLOWED_IMPORT_MODULE:
                    violations.append(
                        f"non-allowed bare import: {alias.name!r} "
                        f"(only 'from {ALLOWED_IMPORT_MODULE} import ...' is allowed)"
                    )
        if isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            base = mod.split(".")[0]
            if base in FORBIDDEN_MODULES:
                violations.append(f"forbidden import-from module: {mod!r}")
            elif mod != ALLOWED_IMPORT_MODULE:
                violations.append(
                    f"non-allowed import-from: {mod!r} "
                    f"(only {ALLOWED_IMPORT_MODULE!r} is allowed)"
                )
    return violations


def check_forbidden_calls(tree: ast.Module) -> list[str]:
    """Reject calls to any forbidden builtin (as Name or Attribute)."""
    violations: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name) and func.id in FORBIDDEN_BUILTINS:
                violations.append(f"forbidden call: {func.id}()")
            if isinstance(func, ast.Attribute) and func.attr in FORBIDDEN_BUILTINS:
                violations.append(f"forbidden attribute call: .{func.attr}()")
    return violations


def check_dunder_access(tree: ast.Module) -> list[str]:
    """Reject ANY dunder attribute access (attr starts and ends with '__').

    This is stricter than the previous finite-list approach: it rejects
    __len__, __str__, __class__, __dict__, __globals__, and any other
    double-underscore attribute access without enumeration.
    """
    violations: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute):
            attr = node.attr
            if attr.startswith("__") and attr.endswith("__"):
                violations.append(f"forbidden dunder attribute access: .{attr}")
    return violations


def check_top_level_structure(tree: ast.Module) -> list[str]:
    """Only docstring, allowed import, and inspect_request def at top level."""
    violations: list[str] = []
    for i, stmt in enumerate(tree.body):
        # First statement may be a module docstring
        if i == 0 and isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant):
            continue
        if isinstance(stmt, (ast.Import, ast.ImportFrom)):
            continue
        if isinstance(stmt, ast.FunctionDef) and stmt.name == "inspect_request":
            continue
        violations.append(
            f"unexpected top-level statement at line {stmt.lineno}: "
            f"{type(stmt).__name__}"
        )
    return violations


def check_inspect_request_signature(tree: ast.Module) -> list[str]:
    """inspect_request must have exactly (request: Request) -> DetectionResult."""
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
    all_args = args.args + args.posonlyargs + args.kwonlyargs
    if len(all_args) != 1 or all_args[0].arg != "request":
        violations.append(
            f"inspect_request must have exactly one argument named 'request', "
            f"got: {[a.arg for a in all_args]}"
        )
    if args.vararg or args.kwarg:
        violations.append("inspect_request must not use *args or **kwargs")
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


def check_extra_defs(tree: ast.Module) -> list[str]:
    """Reject extra top-level functions, async functions, or class definitions."""
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
# Complexity guards (DoS hardening)
# ---------------------------------------------------------------------------

def check_source_size(source: str) -> list[str]:
    """Reject source text that exceeds MAX_POLICY_SOURCE_CHARS before parsing."""
    if len(source) > MAX_POLICY_SOURCE_CHARS:
        return [
            f"source too large: {len(source)} chars "
            f"(limit MAX_POLICY_SOURCE_CHARS={MAX_POLICY_SOURCE_CHARS})"
        ]
    return []


def _ast_depth(tree: ast.AST) -> int:
    """Return the maximum depth of the AST using an explicit stack (no recursion)."""
    if tree is None:
        return 0
    max_depth = 0
    # Stack entries: (node, depth)
    stack: list[tuple[ast.AST, int]] = [(tree, 1)]
    while stack:
        node, depth = stack.pop()
        if depth > max_depth:
            max_depth = depth
        for child in ast.iter_child_nodes(node):
            stack.append((child, depth + 1))
    return max_depth


def check_ast_complexity(tree: ast.AST) -> list[str]:
    """Reject ASTs that exceed node count or depth limits."""
    violations: list[str] = []
    try:
        node_count = sum(1 for _ in ast.walk(tree))
        if node_count > MAX_AST_NODES:
            violations.append(
                f"AST too complex: {node_count} nodes "
                f"(limit MAX_AST_NODES={MAX_AST_NODES})"
            )
        depth = _ast_depth(tree)
        if depth > MAX_AST_DEPTH:
            violations.append(
                f"AST too deep: depth={depth} "
                f"(limit MAX_AST_DEPTH={MAX_AST_DEPTH})"
            )
    except Exception as exc:  # noqa: BLE001
        violations.append(f"AST complexity check failed (fail-closed): {exc}")
    return violations


def check_literal_sizes(tree: ast.AST) -> list[str]:
    """Reject giant string/bytes literals and oversized collection literals."""
    violations: list[str] = []
    try:
        for node in ast.walk(tree):
            # String / bytes literal size
            if isinstance(node, ast.Constant):
                if isinstance(node.value, (str, bytes)):
                    length = len(node.value)
                    if length > MAX_LITERAL_CHARS:
                        violations.append(
                            f"literal too large: {length} chars "
                            f"(limit MAX_LITERAL_CHARS={MAX_LITERAL_CHARS})"
                        )
            # Collection element count
            if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
                count = len(node.elts)
                if count > MAX_COLLECTION_ITEMS:
                    violations.append(
                        f"{type(node).__name__} literal has {count} elements "
                        f"(limit MAX_COLLECTION_ITEMS={MAX_COLLECTION_ITEMS})"
                    )
            if isinstance(node, ast.Dict):
                count = len(node.keys)
                if count > MAX_COLLECTION_ITEMS:
                    violations.append(
                        f"Dict literal has {count} keys "
                        f"(limit MAX_COLLECTION_ITEMS={MAX_COLLECTION_ITEMS})"
                    )
    except Exception as exc:  # noqa: BLE001
        violations.append(f"literal size check failed (fail-closed): {exc}")
    return violations


# ---------------------------------------------------------------------------
# Unified policy runner
# ---------------------------------------------------------------------------

def run_full_policy(candidate_path: Path) -> dict:
    """Run all policy checks against a candidate detector file.

    Returns:
        {"valid": bool, "violations": list[str]}
    """
    if not candidate_path.exists():
        return {"valid": False, "violations": [f"file not found: {candidate_path}"]}

    source = candidate_path.read_text(encoding="utf-8")
    violations: list[str] = []

    # 0. Source size — reject before ast.parse to prevent parse-time DoS
    violations.extend(check_source_size(source))
    if violations:
        return {"valid": False, "violations": violations}

    # 1. Syntax — must pass before AST can be built
    violations.extend(check_syntax(source))
    if violations:
        return {"valid": False, "violations": violations}

    # 2. Mutation markers (source-level check)
    violations.extend(check_mutation_markers(source))

    # Build AST for remaining checks
    tree = ast.parse(source)

    # 3. AST complexity — fail-closed before any policy traversal
    violations.extend(check_ast_complexity(tree))
    if violations:
        return {"valid": False, "violations": violations}

    # 4. Literal sizes
    violations.extend(check_literal_sizes(tree))
    if violations:
        return {"valid": False, "violations": violations}

    # 5. Imports
    violations.extend(check_imports(tree))

    # 6. Forbidden calls (eval, exec, type, dir, super, …)
    violations.extend(check_forbidden_calls(tree))

    # 7. Any dunder attribute access
    violations.extend(check_dunder_access(tree))

    # 8. Top-level structure
    violations.extend(check_top_level_structure(tree))

    # 9. inspect_request signature
    violations.extend(check_inspect_request_signature(tree))

    # 10. Extra definitions
    violations.extend(check_extra_defs(tree))

    return {"valid": len(violations) == 0, "violations": violations}
