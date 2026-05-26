"""core/types.py — Immutable dataclasses for Project Cyber-Immunizer.

All types are frozen dataclasses to ensure determinism across evaluation runs.
Request.query and Request.headers are wrapped in MappingProxyType so that
even the *contents* of those mappings are read-only at runtime.
"""
from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Literal, Mapping


@dataclass(frozen=True)
class Request:
    """An inbound HTTP-like request (local simulation only, no real traffic).

    query and headers are stored as MappingProxyType — they accept plain
    ``dict[str, str]`` in the constructor but become read-only on storage.
    Attempting to write ``request.query["x"] = "y"`` after construction
    raises TypeError.
    """

    method: str
    path: str
    query: Mapping[str, str]
    headers: Mapping[str, str]
    body: str
    source_ip: str | None = None

    def __post_init__(self) -> None:
        # Convert any incoming mapping to an immutable MappingProxyType.
        # object.__setattr__ is required because the dataclass is frozen.
        object.__setattr__(self, "query", MappingProxyType(dict(self.query)))
        object.__setattr__(self, "headers", MappingProxyType(dict(self.headers)))


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
    """Full fitness report for a candidate detector.

    Score is computed from TP/FP/FN rates, exception count, code size, and
    changed lines — NOT from avg_latency_ms.  Latency is reported separately
    and enforced as a hard gate (see genome.json max_avg_latency_ms).
    """

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
    avg_latency_ms: float  # reported; enforced as gate, not in score

    code_chars: int
    changed_lines: int

    score: float  # deterministic across repeated runs for same candidate + data
    passed_adoption_gate: bool
    rejection_reasons: tuple[str, ...]
