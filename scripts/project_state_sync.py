"""Utilities for reconciling project-state SSOT with paid-credit ledger evidence."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

PAID_CREDIT_API_MODE = "gemini_paid_credit"
GEMINI_PROVIDER = "gemini"


@dataclass(frozen=True)
class PaidCreditLedgerSummary:
    """Aggregate of Gemini paid-credit ledger records.

    ``success_count`` counts only records with ``success is True``. Failed API
    records are retained in ``attempt_count`` but never included as successes.
    """

    attempt_count: int
    success_count: int
    latest_success_timestamp: str | None
    latest_success_model: str | None
    latest_success_record: dict[str, Any] | None


def is_gemini_paid_credit_record(record: Any) -> bool:
    """Return whether *record* is a Gemini paid-credit ledger entry."""
    return (
        isinstance(record, dict)
        and record.get("provider") == GEMINI_PROVIDER
        and record.get("api_mode") == PAID_CREDIT_API_MODE
    )


def is_success_record(record: Any) -> bool:
    """Return whether *record* is a successful Gemini paid-credit ledger entry.

    The ledger schema uses these fields as follows:
    - ``provider`` identifies the API provider, e.g. ``gemini``.
    - ``api_mode`` / legacy callers' ``mode`` identify paid-credit mode. This
      project-state check requires current ``api_mode=gemini_paid_credit``.
    - ``model`` is the exact model that handled the paid request.
    - ``timestamp`` is an ISO-8601 timestamp used for latest-success ordering.
    - ``success`` must be the JSON boolean ``true`` to count as a success.
    - ``error`` is informational; failed records with an error never count.
    """
    return is_gemini_paid_credit_record(record) and record.get("success") is True


def summarize_paid_credit_ledger(records: Iterable[Any]) -> PaidCreditLedgerSummary:
    """Summarize Gemini paid-credit attempts and successes from ledger records."""
    paid_records = [record for record in records if is_gemini_paid_credit_record(record)]
    success_records = [record for record in paid_records if record.get("success") is True]
    latest_success = max(
        success_records,
        key=lambda record: str(record.get("timestamp", "")),
        default=None,
    )
    latest_timestamp = None
    latest_model = None
    if latest_success is not None:
        raw_timestamp = latest_success.get("timestamp")
        raw_model = latest_success.get("model")
        latest_timestamp = raw_timestamp if isinstance(raw_timestamp, str) else None
        latest_model = raw_model if isinstance(raw_model, str) else None

    return PaidCreditLedgerSummary(
        attempt_count=len(paid_records),
        success_count=len(success_records),
        latest_success_timestamp=latest_timestamp,
        latest_success_model=latest_model,
        latest_success_record=latest_success,
    )
