"""scripts/api_budget.py — API usage tracking and budget enforcement.

Standard-library-only module. No external dependencies required.

This module provides conservative cost estimation, per-month and per-day
spend tracking via a JSON ledger file, and a pre-call budget gate.

DESIGN NOTES:
  - All cost estimates deliberately over-count to provide a safety margin.
  - The ledger records estimated costs because actual billing data is not
    available synchronously at call time.
  - Actual token counts from the API response are stored when available,
    but cost accounting uses estimates for budget gating.
  - If the ledger is malformed, load_ledger() raises ValueError so that
    the caller can refuse the API call rather than proceeding with a broken
    budget view.
"""
from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Conservative cost table for text-only generation calls.
# These are deliberately overestimates to provide a safety margin.
# NOT official pricing — use only for conservative pre-call budgeting.
# ---------------------------------------------------------------------------
_COST_TABLE: dict[str, dict[str, float]] = {
    "gemini-2.0-flash": {
        "input_per_1m_tokens_usd": 0.20,
        "output_per_1m_tokens_usd": 0.80,
    },
    "gemini-2.0-flash-lite": {
        "input_per_1m_tokens_usd": 0.10,
        "output_per_1m_tokens_usd": 0.40,
    },
}

# Fallback pricing for unknown models — very conservative to avoid surprise costs
_UNKNOWN_MODEL_COST: dict[str, float] = {
    "input_per_1m_tokens_usd": 1.00,
    "output_per_1m_tokens_usd": 5.00,
}


# ---------------------------------------------------------------------------
# Ledger I/O
# ---------------------------------------------------------------------------


def load_ledger(path: Path) -> list[dict]:
    """Load the API usage ledger from a JSON file.

    Returns an empty list if the file does not exist.

    Raises:
        ValueError: if the file exists but contains malformed JSON or
                    its top-level structure is not a JSON array of objects.
    """
    if not path.exists():
        return []
    try:
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Ledger file is malformed JSON: {exc}") from exc
    if not isinstance(data, list):
        raise ValueError(
            f"Ledger must be a JSON array (got {type(data).__name__}). "
            "The file may be corrupted; inspect it manually."
        )
    for i, record in enumerate(data):
        if not isinstance(record, dict):
            raise ValueError(
                f"Ledger record [{i}] must be a JSON object "
                f"(got {type(record).__name__}). "
                "The file may be corrupted."
            )
    return data  # type: ignore[return-value]


def save_ledger(path: Path, records: list[dict]) -> None:
    """Write the ledger list to a JSON file, creating parent dirs as needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(records, indent=2, ensure_ascii=False), encoding="utf-8")


# ---------------------------------------------------------------------------
# Token and cost estimation
# ---------------------------------------------------------------------------


def estimate_tokens_from_chars(chars: int) -> int:
    """Conservatively estimate token count from character count.

    Uses ceil(chars / 4) as a conservative upper bound.
    Real tokenisation is model-specific; this formula errs toward
    over-counting to give a safe budget estimate.
    """
    if chars <= 0:
        return 0
    return math.ceil(chars / 4)


def estimate_cost_usd(
    input_tokens: int,
    output_tokens: int,
    model_name: str,
) -> float:
    """Estimate the cost in USD for a single API call.

    Uses the conservative _COST_TABLE; falls back to _UNKNOWN_MODEL_COST
    for models not in the table.  Always overestimates.
    """
    rates = _COST_TABLE.get(model_name, _UNKNOWN_MODEL_COST)
    input_cost = (input_tokens / 1_000_000) * rates["input_per_1m_tokens_usd"]
    output_cost = (output_tokens / 1_000_000) * rates["output_per_1m_tokens_usd"]
    return input_cost + output_cost


# ---------------------------------------------------------------------------
# Date key helpers
# ---------------------------------------------------------------------------


def current_month_key(now: datetime | None = None) -> str:
    """Return the current UTC month as 'YYYY-MM'."""
    if now is None:
        now = datetime.now(timezone.utc)
    return now.strftime("%Y-%m")


def current_day_key(now: datetime | None = None) -> str:
    """Return the current UTC day as 'YYYY-MM-DD'."""
    if now is None:
        now = datetime.now(timezone.utc)
    return now.strftime("%Y-%m-%d")


# ---------------------------------------------------------------------------
# Spend aggregation
# ---------------------------------------------------------------------------


def current_month_spend(records: list[dict], month_key: str) -> float:
    """Sum estimated_cost_usd for all records whose budget_month matches."""
    total = 0.0
    for record in records:
        if record.get("budget_month") == month_key:
            total += float(record.get("estimated_cost_usd", 0.0))
    return total


def current_day_spend(records: list[dict], day_key: str) -> float:
    """Sum estimated_cost_usd for all records whose budget_day matches."""
    total = 0.0
    for record in records:
        if record.get("budget_day") == day_key:
            total += float(record.get("estimated_cost_usd", 0.0))
    return total


# ---------------------------------------------------------------------------
# Budget gate
# ---------------------------------------------------------------------------


def assert_budget_available(
    genome: dict,
    ledger: list[dict],
    estimated_next_cost_usd: float,
) -> tuple[bool, str]:
    """Check whether the estimated next call fits within configured budgets.

    Args:
        genome:                   Genome configuration dict.
        ledger:                   Loaded ledger records (from load_ledger).
        estimated_next_cost_usd:  Conservative cost estimate for the next call.

    Returns:
        (True, "")  if budget is available.
        (False, reason)  if any budget limit would be exceeded.

    Budget rules:
        - monthly_api_budget_usd must be > 0; otherwise refused.
        - daily_api_budget_usd must be > 0; otherwise refused.
        - monthly_spend + estimated_next_cost_usd <= monthly_api_budget_usd
        - daily_spend + estimated_next_cost_usd <= daily_api_budget_usd
    """
    monthly_budget = float(genome.get("monthly_api_budget_usd", 0.0))
    if monthly_budget <= 0:
        return False, (
            "genome.monthly_api_budget_usd is 0 or negative. "
            "Set a positive budget to allow API calls."
        )

    daily_budget = float(genome.get("daily_api_budget_usd", 0.0))
    if daily_budget <= 0:
        return False, (
            "genome.daily_api_budget_usd is 0 or negative. "
            "Set a positive daily budget to allow API calls."
        )

    month_key = current_month_key()
    day_key = current_day_key()

    month_spend = current_month_spend(ledger, month_key)
    day_spend = current_day_spend(ledger, day_key)

    if month_spend + estimated_next_cost_usd > monthly_budget:
        return False, (
            f"Monthly budget cap reached: "
            f"${month_spend:.6f} already spent this month + "
            f"${estimated_next_cost_usd:.6f} estimated "
            f"> ${monthly_budget:.2f} monthly limit. "
            "Refusing API call."
        )

    if day_spend + estimated_next_cost_usd > daily_budget:
        return False, (
            f"Daily budget cap reached: "
            f"${day_spend:.6f} already spent today + "
            f"${estimated_next_cost_usd:.6f} estimated "
            f"> ${daily_budget:.2f} daily limit. "
            "Refusing API call."
        )

    return True, ""


# ---------------------------------------------------------------------------
# Usage record writer
# ---------------------------------------------------------------------------


def append_usage_record(
    path: Path,
    *,
    provider: str = "gemini",
    api_mode: str = "gemini_paid_credit",
    model: str,
    estimated_input_chars: int,
    estimated_output_chars: int,
    actual_input_tokens: int | None = None,
    actual_output_tokens: int | None = None,
    success: bool,
    error: str = "",
    now: datetime | None = None,
) -> None:
    """Append one usage record to the ledger file at *path*.

    Calculates estimated token counts and cost from char counts.
    If the file does not exist, a new ledger file is created.
    If the file exists but is malformed, a ValueError is raised and the
    corrupt file is NOT overwritten.  Callers must treat this as a hard
    error and refuse to proceed (fail closed).

    Args:
        path:                   Path to the ledger JSON file.
        provider:               API provider identifier ("gemini").
        api_mode:               Mode identifier ("gemini_paid_credit").
        model:                  Model name used for the call.
        estimated_input_chars:  Character count of input prompt.
        estimated_output_chars: Character count of expected/actual output.
        actual_input_tokens:    Actual input token count from response metadata,
                                or None if unavailable.
        actual_output_tokens:   Actual output token count from response metadata,
                                or None if unavailable.
        success:                True if the call succeeded.
        error:                  Error message string (empty if success).
        now:                    UTC datetime for the record (defaults to now).

    Raises:
        ValueError: if the existing ledger file is present but malformed.
                    The corrupt file is NOT overwritten; callers must treat
                    this as a hard error and refuse to proceed.
    """
    if now is None:
        now = datetime.now(timezone.utc)

    est_input_tokens = estimate_tokens_from_chars(estimated_input_chars)
    est_output_tokens = estimate_tokens_from_chars(estimated_output_chars)
    est_cost = estimate_cost_usd(est_input_tokens, est_output_tokens, model)

    record: dict = {
        "timestamp": now.isoformat(),
        "provider": provider,
        "api_mode": api_mode,
        "model": model,
        "estimated_input_chars": estimated_input_chars,
        "estimated_output_chars": estimated_output_chars,
        "estimated_input_tokens": est_input_tokens,
        "estimated_output_tokens": est_output_tokens,
        "actual_input_tokens": actual_input_tokens,
        "actual_output_tokens": actual_output_tokens,
        "estimated_cost_usd": est_cost,
        "budget_month": current_month_key(now),
        "budget_day": current_day_key(now),
        "request_count": 1,
        "success": success,
        "error": error,
    }

    # Load existing records — FAIL CLOSED on corrupt ledger.
    # If the ledger is malformed, raise ValueError rather than silently
    # overwriting it.  A corrupt ledger means past budget data is unknown;
    # proceeding would make the budget cap fail-open.
    try:
        records = load_ledger(path)
    except ValueError:
        raise  # propagate: caller must treat this as a hard error
    except OSError as exc:
        raise ValueError(f"Could not read ledger file: {exc}") from exc

    records.append(record)
    save_ledger(path, records)
