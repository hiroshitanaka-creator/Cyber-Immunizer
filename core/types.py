"""core/types.py — Immutable dataclasses for Project Cyber-Immunizer.

All types are frozen dataclasses to ensure determinism across evaluation runs.
Request.query and Request.headers are wrapped in MappingProxyType so that
even the *contents* of those mappings are read-only at runtime.
"""
from __future__ import annotations

import math
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
    __post_init__ enforces strict runtime type and value constraints so that
    wrong-type fields cannot silently flow through scoring.
    """

    blocked: bool
    reason: str
    confidence: float  # [0.0, 1.0]
    matched_signals: tuple[str, ...]

    def __post_init__(self) -> None:
        if type(self.blocked) is not bool:
            raise TypeError(
                f"DetectionResult contract violation: "
                f"blocked must be bool, got {type(self.blocked).__name__!r}"
            )
        if type(self.reason) is not str:
            raise TypeError(
                f"DetectionResult contract violation: "
                f"reason must be str, got {type(self.reason).__name__!r}"
            )
        # bool is a subclass of int, so check bool first to reject it explicitly
        if type(self.confidence) is bool or type(self.confidence) not in (int, float):
            raise TypeError(
                f"DetectionResult contract violation: "
                f"confidence must be int or float (not bool), "
                f"got {type(self.confidence).__name__!r}"
            )
        if not math.isfinite(self.confidence):
            raise ValueError(
                f"DetectionResult contract violation: "
                f"confidence must be finite, got {self.confidence!r}"
            )
        if not (0.0 <= self.confidence <= 1.0):
            raise ValueError(
                f"DetectionResult contract violation: "
                f"confidence must be in [0.0, 1.0], got {self.confidence!r}"
            )
        if type(self.matched_signals) is not tuple:
            raise TypeError(
                f"DetectionResult contract violation: "
                f"matched_signals must be tuple, "
                f"got {type(self.matched_signals).__name__!r}"
            )
        for i, sig in enumerate(self.matched_signals):
            if type(sig) is not str:
                raise TypeError(
                    f"DetectionResult contract violation: "
                    f"matched_signals[{i}] must be str, "
                    f"got {type(sig).__name__!r}"
                )


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

    Score is computed from TP/FP/FN rates, exception count, and code size —
    NOT from avg_latency_ms or changed_lines.
    - avg_latency_ms: reported and enforced as a hard gate; excluded from score
      so the score is bitwise-identical across repeated evaluations.
    - changed_lines: reported as a diagnostic field; excluded from score so the
      score is generation-invariant (a no-op candidate cannot pass by having
      changed_lines=0 when genome.json::best_score was set under a larger diff).
    score_components is optional; it is None for early-exit (policy-fail) reports.
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
    changed_lines: int  # diagnostic only; not used in score

    score: float  # generation-invariant; deterministic across repeated runs
    passed_adoption_gate: bool
    rejection_reasons: tuple[str, ...]

    score_components: dict | None = None  # None for early-exit reports
