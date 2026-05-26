"""core/types.py — Immutable dataclasses for Project Cyber-Immunizer.

All types are frozen dataclasses to ensure determinism across evaluation runs.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


@dataclass(frozen=True)
class Request:
    """An inbound HTTP-like request (local simulation only, no real traffic)."""

    method: str
    path: str
    query: dict[str, str]
    headers: dict[str, str]
    body: str
    source_ip: str | None = None

    def __post_init__(self) -> None:
        # Coerce mutable dict to frozenset-backed equivalent so the object
        # remains hashable; we store them as dicts per spec but validate types.
        object.__setattr__(self, "query", dict(self.query))
        object.__setattr__(self, "headers", dict(self.headers))


@dataclass(frozen=True)
class DetectionResult:
    """Result returned by the detector for a single request.

    confidence is intended to be in the range [0.0, 1.0].
    """

    blocked: bool
    reason: str
    confidence: float  # [0.0, 1.0]
    matched_signals: tuple[str, ...]


@dataclass(frozen=True)
class TestCase:
    """A deterministic test case for evaluating a detector candidate."""

    id: str
    kind: Literal["benign", "attack", "regression"]
    request: Request
    expected_blocked: bool
    tags: tuple[str, ...]
    description: str


@dataclass(frozen=True)
class FitnessReport:
    """Full fitness report for a candidate detector."""

    syntax_ok: bool
    ast_policy_ok: bool
    contract_ok: bool
    timed_out: bool
    exception_count: int

    true_positive: int
    false_positive: int
    true_negative: int
    false_negative: int
    total_cases: int

    tp_rate: float
    fp_rate: float
    fn_rate: float
    avg_latency_ms: float

    code_chars: int
    changed_lines: int

    score: float
    passed_adoption_gate: bool
    rejection_reasons: tuple[str, ...]
