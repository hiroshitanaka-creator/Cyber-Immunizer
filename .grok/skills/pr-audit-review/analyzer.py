"""
analyzer.py — Structured helper specification for pr-audit-review skill (v0.3.0)

This module is intended as a **detailed skeleton / mental model** for the agent.
It provides clear dataclasses and function signatures with rich docstrings
so that the agent can maintain consistency when orchestrating GitHub tool calls
and generating audit reports.

It is NOT expected to be fully executed as standalone code in all environments.
Some functions may later be made partially executable if needed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


# =============================================================================
# Core Data Structures
# =============================================================================

@dataclass
class AuditResult:
    """Container for all information collected and judged during a PR audit."""

    # --- Fixed audit context ---
    head_sha: str                          # The exact commit SHA being audited (frozen fact)
    owner: str
    repo: str
    pull_number: int

    # --- Extracted information ---
    purpose: str                           # Clear one-sentence purpose extracted from metadata
    changed_files: list[str] = field(default_factory=list)
    related_files: list[str] = field(default_factory=list)

    # --- Scope analysis ---
    scope_in: list[str] = field(default_factory=list)
    scope_out: list[str] = field(default_factory=list)   # Empty list means "None"

    # --- Analysis results ---
    ci_classification: str = ""            # One of the 9 strict categories
    doc_gate: dict[str, str] = field(default_factory=dict)  # 5 items: "yes/no — reason"

    findings: list[dict[str, Any]] = field(default_factory=list)
    positive_findings: list[str] = field(default_factory=list)

    # --- Self-audit ---
    self_audit_passed: bool = False
    self_audit_failures: list[str] = field(default_factory=list)

    # --- Decision ---
    verdict: dict[str, str] = field(default_factory=dict)  # 4-line merge decision format


# =============================================================================
# Helper Functions (Specification / Skeleton)
# =============================================================================

def extract_purpose(pr_metadata: dict[str, Any]) -> str:
    """
    Extract a clear, single-sentence purpose from PR metadata.

    Sources (in priority order):
    - PR title + body
    - Linked issue bodies (via issue_read if needed)

    Rules:
    - If purpose is ambiguous or missing → raise ValueError (do not guess)
    - Treat PR body as self-report. If it contradicts the diff, note it but still extract intent.
    - Return a concise, factual statement of what the PR claims to achieve.
    """
    ...


def classify_ci(
    check_runs: list[dict[str, Any]],
    audited_head_sha: str
) -> Literal[
    "NOT TRIGGERED",
    "WORKFLOW PARSE FAILURE",
    "RUNNER START FAILURE",
    "CHECKOUT FAILURE",
    "SETUP FAILURE",
    "INSTALL FAILURE",
    "TEST FAILURE",
    "DOMAIN FAILURE",
    "SUCCESS",
]:
    """
    Classify CI result using the strict 9-category taxonomy.

    Critical rules:
    - Only consider runs whose head_sha matches `audited_head_sha`.
      If no matching run exists → return "NOT TRIGGERED".
    - If pytest failed → "TEST FAILURE".
    - If pytest did not run at all → do NOT return "TEST FAILURE".
      Use the category that actually failed (e.g. SETUP FAILURE, INSTALL FAILURE).
    - "Complete job" success does not imply overall success.
    - Return exactly one of the 9 literal strings above.
    """
    ...


def discover_related_files(
    changed_files: list[str],
    file_contents: dict[str, str],
    additional_related_files: list[str],
    max_files: int = 15
) -> list[str]:
    """
    Discover high-impact related files beyond the changed files.

    Heuristics (examples):
    - foo.py → tests/test_foo.py, tests/test_*foo*.py
    - core/module.py → docs/ references, scripts/ that import it
    - README.md changed → check for generator scripts (e.g. scripts/update_readme.py)
    - Any file importing or being imported by changed files

    Merge results with `additional_related_files`.
    Respect `max_files` limit. Prioritize highest impact files.
    """
    ...


def identify_scope(
    changed_files: list[str],
    purpose: str,
    pr_body: str,
    diff: str
) -> tuple[list[str], list[str]]:
    """
    Separate changes into scope-in and scope-out (scope drift).

    Returns:
        (scope_in, scope_out)

    Rules:
    - scope_in: Changes that clearly serve the stated purpose.
    - scope_out: Changes outside the stated purpose (scope drift).
    - If no scope drift → return ([...], [])
    - The caller should display "None" when scope_out is empty.

    Note: This function focuses on detection. Auto-BLOCK decisions
    based on Cyber-Immunizer rules are handled in the main skill logic.
    """
    ...


def check_documentation_gate(
    changed_files: list[str],
    file_contents: dict[str, str]
) -> dict[str, str]:
    """
    Evaluate the 5-item Documentation / History Gate.

    Items:
    - README
    - docs/**
    - changelog / history
    - generator scripts (if README/docs are generated)
    - data ledger / history

    Returns:
        dict mapping item name → "yes/no — reason"

    Special rule:
    - If a generator script exists and README/docs were manually edited
      without updating the generator → recommend "REQUEST CHANGES".
    """
    ...


def run_self_audit(result: AuditResult) -> tuple[bool, list[str]]:
    """
    Execute the mandatory 16-item self-audit checklist defined in SKILL.md.

    Returns:
        (passed: bool, failures: list[str])

    Only when `passed=True` should the skill proceed to posting a review.
    """
    ...


def build_cyber_immunizer_scope_out_auto_block_list() -> list[str]:
    """
    Return the list of scope-out patterns that automatically trigger
    Merge Recommendation = BLOCK for the Cyber-Immunizer repository.

    Current items (Cyber-Immunizer specific):
    - Changes to .github/workflows/** execution logic
    - Unauthorized changes to core/** or data/**
    - Introduction or enabling of live_model_enabled=true
    - Any modifications related to GitHub Secrets configuration
    """
    return [
        ".github/workflows/** (execution logic)",
        "core/** (unauthorized)",
        "data/** (unauthorized)",
        "live_model_enabled=true",
        "GitHub Secrets configuration",
    ]


# =============================================================================
# Future Extension Points
# =============================================================================

# def analyze_cyber_immunizer_specific_risks(...):
#     """Repository-specific deeper analysis for Cyber-Immunizer."""
#     ...

# def generate_report(result: AuditResult) -> str:
#     """Generate the final structured review body string."""
#     ...