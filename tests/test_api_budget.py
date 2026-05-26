"""tests/test_api_budget.py — Tests for scripts/api_budget.py.

All tests use only the standard library; no real API calls are made.
"""
from __future__ import annotations

import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

_PROJECT_ROOT = Path(__file__).parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from scripts import api_budget as budget  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def empty_ledger_file(tmp_path: Path) -> Path:
    """Write an empty ledger JSON array and return its path."""
    p = tmp_path / "ledger.json"
    p.write_text("[]", encoding="utf-8")
    return p


@pytest.fixture()
def safe_genome() -> dict:
    """A genome dict with both budgets set to sensible defaults."""
    return {
        "monthly_api_budget_usd": 10.0,
        "daily_api_budget_usd": 0.25,
    }


def _make_record(
    month: str,
    day: str,
    cost: float,
    provider: str = "gemini",
    success: bool = True,
) -> dict:
    """Build a minimal ledger record for testing."""
    return {
        "timestamp": f"{day}T00:00:00+00:00",
        "provider": provider,
        "api_mode": "gemini_paid_credit",
        "model": "gemini-2.0-flash",
        "estimated_input_chars": 100,
        "estimated_output_chars": 50,
        "estimated_input_tokens": 25,
        "estimated_output_tokens": 13,
        "actual_input_tokens": None,
        "actual_output_tokens": None,
        "estimated_cost_usd": cost,
        "budget_month": month,
        "budget_day": day,
        "request_count": 1,
        "success": success,
        "error": "",
    }


# ---------------------------------------------------------------------------
# 1. estimate_tokens_from_chars rounds up
# ---------------------------------------------------------------------------


class TestEstimateTokens:
    def test_exact_multiple_of_4(self) -> None:
        """400 chars → exactly 100 tokens."""
        assert budget.estimate_tokens_from_chars(400) == 100

    def test_rounds_up_1(self) -> None:
        """1 char → 1 token (ceil(1/4) = 1)."""
        assert budget.estimate_tokens_from_chars(1) == 1

    def test_rounds_up_partial(self) -> None:
        """5 chars → 2 tokens (ceil(5/4) = 2)."""
        assert budget.estimate_tokens_from_chars(5) == 2

    def test_rounds_up_3(self) -> None:
        """3 chars → 1 token (ceil(3/4) = 1)."""
        assert budget.estimate_tokens_from_chars(3) == 1

    def test_rounds_up_exactly_ceil(self) -> None:
        """Any n chars rounds up correctly."""
        for n in range(1, 20):
            expected = math.ceil(n / 4)
            assert budget.estimate_tokens_from_chars(n) == expected, (
                f"estimate_tokens_from_chars({n}) should be {expected}"
            )

    def test_zero_chars(self) -> None:
        """0 chars → 0 tokens."""
        assert budget.estimate_tokens_from_chars(0) == 0

    def test_negative_chars(self) -> None:
        """Negative chars → 0 tokens."""
        assert budget.estimate_tokens_from_chars(-10) == 0

    def test_large_input(self) -> None:
        """12000 chars → ceil(12000/4) = 3000 tokens."""
        assert budget.estimate_tokens_from_chars(12000) == 3000


# ---------------------------------------------------------------------------
# 2. Current month spend sums only same month
# ---------------------------------------------------------------------------


class TestCurrentMonthSpend:
    def test_sums_matching_month(self) -> None:
        """Only records with matching budget_month are summed."""
        records = [
            _make_record("2026-05", "2026-05-01", cost=0.01),
            _make_record("2026-05", "2026-05-15", cost=0.02),
            _make_record("2026-04", "2026-04-30", cost=99.99),  # different month
        ]
        total = budget.current_month_spend(records, "2026-05")
        assert abs(total - 0.03) < 1e-9

    def test_empty_ledger(self) -> None:
        assert budget.current_month_spend([], "2026-05") == 0.0

    def test_no_matching_month(self) -> None:
        records = [_make_record("2026-04", "2026-04-01", cost=5.00)]
        assert budget.current_month_spend(records, "2026-05") == 0.0

    def test_all_records_in_month(self) -> None:
        records = [_make_record("2026-05", f"2026-05-{d:02d}", cost=0.01) for d in range(1, 6)]
        total = budget.current_month_spend(records, "2026-05")
        assert abs(total - 0.05) < 1e-9

    def test_missing_budget_month_field(self) -> None:
        """Records without budget_month field are skipped (return 0 for that key)."""
        records = [{"estimated_cost_usd": 5.0}]  # no budget_month
        total = budget.current_month_spend(records, "2026-05")
        assert total == 0.0


# ---------------------------------------------------------------------------
# 3. Current day spend sums only same day
# ---------------------------------------------------------------------------


class TestCurrentDaySpend:
    def test_sums_matching_day(self) -> None:
        records = [
            _make_record("2026-05", "2026-05-15", cost=0.05),
            _make_record("2026-05", "2026-05-15", cost=0.10),
            _make_record("2026-05", "2026-05-14", cost=99.00),  # different day
        ]
        total = budget.current_day_spend(records, "2026-05-15")
        assert abs(total - 0.15) < 1e-9

    def test_empty_ledger(self) -> None:
        assert budget.current_day_spend([], "2026-05-15") == 0.0

    def test_no_matching_day(self) -> None:
        records = [_make_record("2026-05", "2026-05-14", cost=1.00)]
        assert budget.current_day_spend(records, "2026-05-15") == 0.0

    def test_missing_budget_day_field(self) -> None:
        records = [{"estimated_cost_usd": 5.0}]
        assert budget.current_day_spend(records, "2026-05-15") == 0.0


# ---------------------------------------------------------------------------
# 4. Budget accepts call under monthly and daily caps
# ---------------------------------------------------------------------------


class TestBudgetAccept:
    def test_accepts_when_well_under_budget(self, safe_genome: dict) -> None:
        """A tiny estimated cost should pass easily."""
        ok, reason = budget.assert_budget_available(safe_genome, [], 0.001)
        assert ok is True
        assert reason == ""

    def test_accepts_at_exact_boundary(self, safe_genome: dict) -> None:
        """A call that fits exactly within both monthly and daily budgets is accepted."""
        # Use a high daily limit so only the monthly boundary is relevant here.
        genome = {"monthly_api_budget_usd": 10.0, "daily_api_budget_usd": 100.0}
        # Spend 9.999 this month (and today, since we use current keys below).
        # 9.999 + 0.001 = 10.000 which is NOT > 10.000, so it should be accepted.
        month_key = budget.current_month_key()
        day_key = budget.current_day_key()
        records = [{
            **_make_record("2026-05", "2026-05-15", cost=9.999),
            "budget_month": month_key,
            "budget_day": day_key,
        }]
        ok, reason = budget.assert_budget_available(genome, records, 0.001)
        assert ok is True, f"Expected budget to be available at exact boundary, got: {reason}"

    def test_accepts_empty_ledger(self, safe_genome: dict) -> None:
        ok, reason = budget.assert_budget_available(safe_genome, [], 0.01)
        assert ok is True


# ---------------------------------------------------------------------------
# 5. Budget rejects monthly overflow
# ---------------------------------------------------------------------------


class TestBudgetRejectMonthly:
    def test_rejects_when_monthly_budget_exceeded(self) -> None:
        genome = {"monthly_api_budget_usd": 10.0, "daily_api_budget_usd": 1.0}
        month_key = budget.current_month_key()
        day_key = budget.current_day_key()
        # Already spent 9.99 this month
        records = [
            {
                **_make_record("2026-05", "2026-05-01", cost=9.99),
                "budget_month": month_key,
                "budget_day": day_key,
            }
        ]
        # Next call would cost 0.02 → 9.99 + 0.02 = 10.01 > 10.00
        ok, reason = budget.assert_budget_available(genome, records, 0.02)
        assert ok is False
        assert "monthly" in reason.lower() or "budget" in reason.lower()

    def test_rejects_when_monthly_budget_is_zero(self) -> None:
        genome = {"monthly_api_budget_usd": 0, "daily_api_budget_usd": 1.0}
        ok, reason = budget.assert_budget_available(genome, [], 0.001)
        assert ok is False
        assert "monthly" in reason.lower()

    def test_rejects_when_monthly_budget_is_negative(self) -> None:
        genome = {"monthly_api_budget_usd": -5.0, "daily_api_budget_usd": 1.0}
        ok, reason = budget.assert_budget_available(genome, [], 0.001)
        assert ok is False


# ---------------------------------------------------------------------------
# 6. Budget rejects daily overflow
# ---------------------------------------------------------------------------


class TestBudgetRejectDaily:
    def test_rejects_when_daily_budget_exceeded(self) -> None:
        genome = {"monthly_api_budget_usd": 100.0, "daily_api_budget_usd": 0.25}
        month_key = budget.current_month_key()
        day_key = budget.current_day_key()
        records = [
            {
                **_make_record("2026-05", "2026-05-15", cost=0.24),
                "budget_month": month_key,
                "budget_day": day_key,
            }
        ]
        # Next call: 0.24 + 0.02 = 0.26 > 0.25
        ok, reason = budget.assert_budget_available(genome, records, 0.02)
        assert ok is False
        assert "daily" in reason.lower() or "budget" in reason.lower()

    def test_rejects_when_daily_budget_is_zero(self) -> None:
        genome = {"monthly_api_budget_usd": 10.0, "daily_api_budget_usd": 0}
        ok, reason = budget.assert_budget_available(genome, [], 0.001)
        assert ok is False
        assert "daily" in reason.lower()

    def test_rejects_when_daily_budget_is_negative(self) -> None:
        genome = {"monthly_api_budget_usd": 10.0, "daily_api_budget_usd": -1.0}
        ok, reason = budget.assert_budget_available(genome, [], 0.001)
        assert ok is False


# ---------------------------------------------------------------------------
# 7. Budget rejects malformed ledger
# ---------------------------------------------------------------------------


class TestMalformedLedger:
    def test_load_ledger_raises_on_invalid_json(self, tmp_path: Path) -> None:
        bad = tmp_path / "bad.json"
        bad.write_text("this is not json", encoding="utf-8")
        with pytest.raises(ValueError, match="malformed"):
            budget.load_ledger(bad)

    def test_load_ledger_raises_on_non_array(self, tmp_path: Path) -> None:
        bad = tmp_path / "obj.json"
        bad.write_text('{"key": "value"}', encoding="utf-8")
        with pytest.raises(ValueError):
            budget.load_ledger(bad)

    def test_load_ledger_raises_on_array_with_non_dict(self, tmp_path: Path) -> None:
        bad = tmp_path / "arr.json"
        bad.write_text('[1, 2, 3]', encoding="utf-8")
        with pytest.raises(ValueError):
            budget.load_ledger(bad)

    def test_load_ledger_returns_empty_for_missing_file(self, tmp_path: Path) -> None:
        p = tmp_path / "nonexistent.json"
        result = budget.load_ledger(p)
        assert result == []

    def test_load_ledger_returns_valid_records(self, tmp_path: Path) -> None:
        records = [_make_record("2026-05", "2026-05-01", cost=0.01)]
        p = tmp_path / "ledger.json"
        p.write_text(json.dumps(records), encoding="utf-8")
        loaded = budget.load_ledger(p)
        assert len(loaded) == 1
        assert loaded[0]["estimated_cost_usd"] == 0.01


# ---------------------------------------------------------------------------
# 8. Unknown model uses conservative pricing
# ---------------------------------------------------------------------------


class TestUnknownModelCost:
    def test_unknown_model_higher_than_flash(self) -> None:
        """Unknown models should cost more than gemini-2.0-flash."""
        flash_cost = budget.estimate_cost_usd(1000, 500, "gemini-2.0-flash")
        unknown_cost = budget.estimate_cost_usd(1000, 500, "some-unknown-model-xyz")
        assert unknown_cost > flash_cost

    def test_unknown_model_uses_fallback_rates(self) -> None:
        """Unknown model should use the conservative fallback rates."""
        # input: 1M tokens → $1.00, output: 1M tokens → $5.00
        cost = budget.estimate_cost_usd(1_000_000, 1_000_000, "mystery-model-v99")
        expected = 1.00 + 5.00
        assert abs(cost - expected) < 1e-6

    def test_flash_uses_table_rates(self) -> None:
        """gemini-2.0-flash uses the known rate table."""
        # input: 1M tokens → $0.20, output: 1M tokens → $0.80
        cost = budget.estimate_cost_usd(1_000_000, 1_000_000, "gemini-2.0-flash")
        expected = 0.20 + 0.80
        assert abs(cost - expected) < 1e-6

    def test_flash_lite_uses_table_rates(self) -> None:
        cost = budget.estimate_cost_usd(1_000_000, 1_000_000, "gemini-2.0-flash-lite")
        expected = 0.10 + 0.40
        assert abs(cost - expected) < 1e-6


# ---------------------------------------------------------------------------
# 9. append_usage_record and ledger round-trip
# ---------------------------------------------------------------------------


class TestAppendUsageRecord:
    def test_creates_file_if_missing(self, tmp_path: Path) -> None:
        p = tmp_path / "ledger.json"
        budget.append_usage_record(
            p,
            model="gemini-2.0-flash",
            estimated_input_chars=1000,
            estimated_output_chars=500,
            success=True,
        )
        assert p.exists()
        data = json.loads(p.read_text())
        assert isinstance(data, list)
        assert len(data) == 1

    def test_record_has_required_fields(self, tmp_path: Path) -> None:
        p = tmp_path / "ledger.json"
        budget.append_usage_record(
            p,
            model="gemini-2.0-flash",
            estimated_input_chars=800,
            estimated_output_chars=400,
            success=True,
        )
        record = json.loads(p.read_text())[0]
        required_fields = [
            "timestamp", "provider", "api_mode", "model",
            "estimated_input_chars", "estimated_output_chars",
            "estimated_input_tokens", "estimated_output_tokens",
            "actual_input_tokens", "actual_output_tokens",
            "estimated_cost_usd", "budget_month", "budget_day",
            "request_count", "success", "error",
        ]
        for field in required_fields:
            assert field in record, f"Missing field: {field}"

    def test_appends_to_existing_records(self, tmp_path: Path) -> None:
        p = tmp_path / "ledger.json"
        # Write an existing record
        existing = [_make_record("2026-04", "2026-04-01", cost=0.01)]
        p.write_text(json.dumps(existing), encoding="utf-8")

        budget.append_usage_record(
            p,
            model="gemini-2.0-flash",
            estimated_input_chars=500,
            estimated_output_chars=200,
            success=True,
        )
        data = json.loads(p.read_text())
        assert len(data) == 2

    def test_failure_record_has_error_field(self, tmp_path: Path) -> None:
        p = tmp_path / "ledger.json"
        budget.append_usage_record(
            p,
            model="gemini-2.0-flash",
            estimated_input_chars=100,
            estimated_output_chars=50,
            success=False,
            error="API timeout",
        )
        record = json.loads(p.read_text())[0]
        assert record["success"] is False
        assert record["error"] == "API timeout"

    def test_actual_tokens_stored(self, tmp_path: Path) -> None:
        p = tmp_path / "ledger.json"
        budget.append_usage_record(
            p,
            model="gemini-2.0-flash",
            estimated_input_chars=100,
            estimated_output_chars=50,
            actual_input_tokens=30,
            actual_output_tokens=15,
            success=True,
        )
        record = json.loads(p.read_text())[0]
        assert record["actual_input_tokens"] == 30
        assert record["actual_output_tokens"] == 15

    def test_raises_on_malformed_existing_ledger(self, tmp_path: Path) -> None:
        """If existing ledger is malformed, append_usage_record raises ValueError.

        The corrupt file must NOT be silently overwritten.  A malformed ledger
        means past budget data is unknown; proceeding would make the budget cap
        fail-open.  The caller must treat this as a hard error.
        """
        p = tmp_path / "ledger.json"
        p.write_text("INVALID JSON", encoding="utf-8")
        with pytest.raises(ValueError):
            budget.append_usage_record(
                p,
                model="gemini-2.0-flash",
                estimated_input_chars=100,
                estimated_output_chars=50,
                success=True,
            )
        # Verify the corrupt file was NOT overwritten
        assert p.read_text(encoding="utf-8") == "INVALID JSON", (
            "append_usage_record must not overwrite a corrupt ledger file"
        )

    def test_raises_on_non_array_ledger(self, tmp_path: Path) -> None:
        """If existing ledger is a JSON object (not array), raises ValueError."""
        p = tmp_path / "ledger.json"
        p.write_text('{"key": "value"}', encoding="utf-8")
        with pytest.raises(ValueError):
            budget.append_usage_record(
                p,
                model="gemini-2.0-flash",
                estimated_input_chars=100,
                estimated_output_chars=50,
                success=True,
            )
        # Corrupt file must remain unchanged
        assert p.read_text(encoding="utf-8") == '{"key": "value"}'

    def test_appends_only_to_valid_ledger(self, tmp_path: Path) -> None:
        """append_usage_record appends to a valid ledger without error."""
        p = tmp_path / "ledger.json"
        existing = [_make_record("2026-05", "2026-05-01", cost=0.01)]
        p.write_text(json.dumps(existing), encoding="utf-8")

        # Should not raise
        budget.append_usage_record(
            p,
            model="gemini-2.0-flash",
            estimated_input_chars=500,
            estimated_output_chars=200,
            success=True,
        )
        data = json.loads(p.read_text())
        assert len(data) == 2, "Valid ledger should have 2 records after append"

    def test_estimated_cost_is_positive(self, tmp_path: Path) -> None:
        p = tmp_path / "ledger.json"
        budget.append_usage_record(
            p,
            model="gemini-2.0-flash",
            estimated_input_chars=4000,
            estimated_output_chars=2000,
            success=True,
        )
        record = json.loads(p.read_text())[0]
        assert record["estimated_cost_usd"] > 0

    def test_budget_month_and_day_keys(self, tmp_path: Path) -> None:
        p = tmp_path / "ledger.json"
        fixed_time = datetime(2026, 5, 15, 10, 30, 0, tzinfo=timezone.utc)
        budget.append_usage_record(
            p,
            model="gemini-2.0-flash",
            estimated_input_chars=100,
            estimated_output_chars=50,
            success=True,
            now=fixed_time,
        )
        record = json.loads(p.read_text())[0]
        assert record["budget_month"] == "2026-05"
        assert record["budget_day"] == "2026-05-15"


# ---------------------------------------------------------------------------
# 10. Date key helpers
# ---------------------------------------------------------------------------


class TestDateKeys:
    def test_current_month_key_format(self) -> None:
        """current_month_key returns 'YYYY-MM'."""
        dt = datetime(2026, 5, 15, tzinfo=timezone.utc)
        assert budget.current_month_key(dt) == "2026-05"

    def test_current_day_key_format(self) -> None:
        """current_day_key returns 'YYYY-MM-DD'."""
        dt = datetime(2026, 5, 15, tzinfo=timezone.utc)
        assert budget.current_day_key(dt) == "2026-05-15"

    def test_current_month_key_uses_utc_when_none(self) -> None:
        key = budget.current_month_key()
        assert len(key) == 7
        assert key[4] == "-"

    def test_current_day_key_uses_utc_when_none(self) -> None:
        key = budget.current_day_key()
        assert len(key) == 10
        assert key[4] == "-"
        assert key[7] == "-"

    def test_year_boundary(self) -> None:
        dt = datetime(2026, 12, 31, tzinfo=timezone.utc)
        assert budget.current_month_key(dt) == "2026-12"
        assert budget.current_day_key(dt) == "2026-12-31"

    def test_january(self) -> None:
        dt = datetime(2027, 1, 1, tzinfo=timezone.utc)
        assert budget.current_month_key(dt) == "2027-01"
        assert budget.current_day_key(dt) == "2027-01-01"
