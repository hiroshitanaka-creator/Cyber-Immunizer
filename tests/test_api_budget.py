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
# 1. estimate_tokens_from_chars — conservative multilingual/code-safe policy
# ---------------------------------------------------------------------------


class TestEstimateTokens:
    def test_zero_chars(self) -> None:
        """0 chars → 0 tokens (boundary: non-positive input)."""
        assert budget.estimate_tokens_from_chars(0) == 0

    def test_negative_chars(self) -> None:
        """Negative char count → 0 tokens (clamp at zero)."""
        assert budget.estimate_tokens_from_chars(-10) == 0

    def test_one_char_is_not_underestimated(self) -> None:
        """1 char must produce at least 2 tokens (conservative 2x multiplier)."""
        result = budget.estimate_tokens_from_chars(1)
        assert result >= 2, f"estimate_tokens_from_chars(1) must be >= 2, got {result}"
        assert result == 2, f"With _CONSERVATIVE_TOKENS_PER_CHAR=2.0, expected 2, got {result}"

    def test_ascii_chars_use_conservative_multiplier(self) -> None:
        """400 ASCII chars must produce at least 800 tokens (2x multiplier)."""
        result = budget.estimate_tokens_from_chars(400)
        assert result >= 800, (
            f"estimate_tokens_from_chars(400) must be >= 800 for multilingual safety, "
            f"got {result}"
        )
        assert result == 800, (
            f"With _CONSERVATIVE_TOKENS_PER_CHAR=2.0, expected 800, got {result}"
        )

    def test_large_prompt_no_longer_uses_chars_div_4(self) -> None:
        """12000 chars must produce at least 24000 tokens — NOT the stale 3000."""
        result = budget.estimate_tokens_from_chars(12000)
        assert result >= 24000, (
            f"estimate_tokens_from_chars(12000) must be >= 24000, got {result}"
        )
        assert result != 3000, (
            "estimate_tokens_from_chars(12000) must NOT return 3000 "
            "(that was the unsafe chars/4 formula)"
        )

    def test_mixed_japanese_symbols_and_code_estimates_at_least_2x_chars(self) -> None:
        """Multilingual/code/symbol prompt estimate must be >= 2x character count.

        Uses only neutralized symbolic indicators — no raw payload strings.
        """
        prompt = (
            "このコードはセキュリティの脆弱性を検出します。"
            "以下のPythonコードを分析してください:\n"
            "def check_request(req):\n"
            "    # neutralized indicators: path_traversal_indicator, sqli_indicator\n"
            "    surface = req.path.lower() + ' ' + req.body.lower()\n"
            "    indicators = [\n"
            "        'path_traversal_indicator',\n"
            "        'sqli_indicator',\n"
            "        'script_injection_indicator',\n"
            "        'command_delimiter_indicator',\n"
            "    ]\n"
            "    return any(s in surface for s in indicators)\n"
            "# 記号テスト !@#$%^&*()_+-=[]{}|;':\",./<>?\n"
            "# 攻撃パターンの指標: path_traversal_indicator, sqli_indicator\n"
        )
        n = len(prompt)
        result = budget.estimate_tokens_from_chars(n)
        assert result >= n * 2, (
            f"estimate_tokens_from_chars({n}) must be >= {n * 2} for multilingual prompt, "
            f"got {result}"
        )

    def test_estimate_is_monotonic(self) -> None:
        """Token estimates must never decrease as character count increases."""
        sizes = [0, 1, 2, 3, 5, 10, 50, 100, 400, 1000, 4000, 12000]
        estimates = [budget.estimate_tokens_from_chars(n) for n in sizes]
        for i in range(1, len(estimates)):
            assert estimates[i] >= estimates[i - 1], (
                f"estimate_tokens_from_chars not monotonic: "
                f"f({sizes[i]})={estimates[i]} < f({sizes[i-1]})={estimates[i-1]}"
            )

    def test_estimate_has_no_chars_div_4_regression(self) -> None:
        """Regression guard: estimate must strictly exceed ceil(chars/4) for all positive n.

        This test exists to permanently prevent reintroduction of the unsafe
        chars/4 formula, which underestimates for multilingual/code prompts.
        """
        for n in [1, 3, 5, 400, 12000]:
            result = budget.estimate_tokens_from_chars(n)
            old_formula = math.ceil(n / 4)
            assert result > old_formula, (
                f"estimate_tokens_from_chars({n})={result} must be > "
                f"ceil({n}/4)={old_formula}. "
                "The chars/4 formula is forbidden as a fallback."
            )


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


# ---------------------------------------------------------------------------
# 11. strict_load_ledger — fail-closed for live API / budget enforcement paths
# ---------------------------------------------------------------------------


class TestStrictLoadLedger:
    """Tests for budget.strict_load_ledger() which is used by all live API paths.

    Unlike load_ledger(), strict_load_ledger() must raise ValueError for a
    missing ledger file because a missing ledger means past spend is unknown
    and the budget cap would be fail-open.
    """

    def test_raises_on_missing_file(self, tmp_path: Path) -> None:
        """Missing ledger must raise ValueError (budget state unknown)."""
        p = tmp_path / "nonexistent.json"
        with pytest.raises(ValueError) as exc_info:
            budget.strict_load_ledger(p)
        assert "budget state unknown" in str(exc_info.value).lower() or \
               "not found" in str(exc_info.value).lower() or \
               "missing" in str(exc_info.value).lower()

    def test_missing_error_mentions_budget_state_unknown(self, tmp_path: Path) -> None:
        """Missing ledger error message must contain 'budget state unknown'."""
        p = tmp_path / "nonexistent.json"
        with pytest.raises(ValueError) as exc_info:
            budget.strict_load_ledger(p)
        assert "budget state unknown" in str(exc_info.value).lower()

    def test_raises_on_malformed_json(self, tmp_path: Path) -> None:
        """Malformed JSON must raise ValueError."""
        p = tmp_path / "bad.json"
        p.write_text("this is not json", encoding="utf-8")
        with pytest.raises(ValueError) as exc_info:
            budget.strict_load_ledger(p)
        assert "budget state unknown" in str(exc_info.value).lower()

    def test_raises_on_top_level_dict(self, tmp_path: Path) -> None:
        """Top-level JSON object (dict) must raise ValueError."""
        p = tmp_path / "obj.json"
        p.write_text('{"key": "value"}', encoding="utf-8")
        with pytest.raises(ValueError) as exc_info:
            budget.strict_load_ledger(p)
        assert "budget state unknown" in str(exc_info.value).lower()

    def test_raises_on_top_level_null(self, tmp_path: Path) -> None:
        """Top-level JSON null must raise ValueError."""
        p = tmp_path / "null.json"
        p.write_text("null", encoding="utf-8")
        with pytest.raises(ValueError) as exc_info:
            budget.strict_load_ledger(p)
        assert "budget state unknown" in str(exc_info.value).lower()

    def test_raises_on_top_level_string(self, tmp_path: Path) -> None:
        """Top-level JSON string must raise ValueError."""
        p = tmp_path / "str.json"
        p.write_text('"some string"', encoding="utf-8")
        with pytest.raises(ValueError) as exc_info:
            budget.strict_load_ledger(p)
        assert "budget state unknown" in str(exc_info.value).lower()

    def test_raises_on_top_level_number(self, tmp_path: Path) -> None:
        """Top-level JSON number must raise ValueError."""
        p = tmp_path / "num.json"
        p.write_text("42", encoding="utf-8")
        with pytest.raises(ValueError) as exc_info:
            budget.strict_load_ledger(p)
        assert "budget state unknown" in str(exc_info.value).lower()

    def test_missing_is_not_treated_as_empty(self, tmp_path: Path) -> None:
        """Missing ledger must NOT be silently treated as an empty ledger []."""
        p = tmp_path / "nonexistent.json"
        # strict_load_ledger must raise, not return []
        raised = False
        try:
            result = budget.strict_load_ledger(p)
        except ValueError:
            raised = True
        assert raised, (
            "strict_load_ledger must raise ValueError for a missing ledger, "
            "not return [] or any empty list"
        )

    def test_returns_valid_list(self, tmp_path: Path) -> None:
        """Valid ledger file must be returned as a list without raising."""
        records = [_make_record("2026-05", "2026-05-01", cost=0.01)]
        p = tmp_path / "ledger.json"
        p.write_text(json.dumps(records), encoding="utf-8")
        loaded = budget.strict_load_ledger(p)
        assert isinstance(loaded, list)
        assert len(loaded) == 1
        assert loaded[0]["estimated_cost_usd"] == 0.01

    def test_returns_empty_list_for_empty_array(self, tmp_path: Path) -> None:
        """An empty JSON array [] is valid and must be returned as []."""
        p = tmp_path / "empty.json"
        p.write_text("[]", encoding="utf-8")
        loaded = budget.strict_load_ledger(p)
        assert loaded == []

    def test_load_ledger_still_allows_missing(self, tmp_path: Path) -> None:
        """Original load_ledger() must still return [] for a missing file (not broken)."""
        p = tmp_path / "nonexistent.json"
        result = budget.load_ledger(p)
        assert result == [], (
            "load_ledger() must still return [] for missing files "
            "(used by append_usage_record to create the first ledger entry)"
        )


# ---------------------------------------------------------------------------
# 12. live API path uses strict_load_ledger (integration smoke tests)
# ---------------------------------------------------------------------------


class TestLiveBudgetPathFailsClosed:
    """Verify that the live API budget enforcement path (propose_mutation.py)
    refuses when the ledger is missing or malformed.

    These tests import propose_mutation and verify that missing/malformed ledger
    causes a refusal before any API call would be attempted.
    """

    @pytest.fixture()
    def live_paid_genome(self) -> dict:
        return {
            "project": "Test",
            "generation": 1,
            "best_score": -1000000.0,
            "max_model_requests_per_run": 1,
            "model_provider": "gemini",
            "api_mode": "gemini_paid_credit",
            "model_name": "gemini-2.0-flash",
            "fallback_model_name": "gemini-2.0-flash-lite",
            "live_model_enabled": True,
            "require_paid_tier": True,
            "free_tier_only": False,
            "monthly_api_budget_usd": 10.0,
            "daily_api_budget_usd": 0.25,
            "max_prompt_chars": 12000,
            "max_output_tokens": 2048,
            "temperature": 0.2,
            "allow_google_search_grounding": False,
            "allow_code_execution_tool": False,
            "allow_url_context": False,
            "send_repository_full_text": False,
            "send_raw_payloads": False,
            "send_secrets": False,
        }

    def _minimal_detector(self, tmp_path: Path) -> Path:
        code = '''\
from core.types import Request, DetectionResult


def inspect_request(request: Request) -> DetectionResult:
    # === MUTATION_START ===
    return DetectionResult(
        blocked=False,
        reason="no suspicious indicator matched",
        confidence=0.0,
        matched_signals=(),
    )
    # === MUTATION_END ===
'''
        p = tmp_path / "detector.py"
        p.write_text(code, encoding="utf-8")
        return p

    def test_missing_ledger_refuses_budget_check(
        self, tmp_path: Path, live_paid_genome: dict, monkeypatch: "pytest.MonkeyPatch"
    ) -> None:
        """Missing api_usage_ledger.json must cause the live paid path to refuse.

        A missing ledger means past spend is unknown; the budget cap must fail-closed.
        """
        import scripts.propose_mutation as pm

        genome_path = tmp_path / "genome.json"
        genome_path.write_text(json.dumps(live_paid_genome), encoding="utf-8")
        detector_path = self._minimal_detector(tmp_path)
        threats_path = tmp_path / "active_threats.json"
        threats_path.write_text('[{"id": "T-001"}]', encoding="utf-8")
        out_dir = tmp_path / "out"
        out_dir.mkdir()
        # Deliberately do NOT create the ledger file
        missing_ledger = tmp_path / "api_usage_ledger.json"

        monkeypatch.setattr(pm, "_GENOME_PATH", genome_path)
        monkeypatch.setattr(pm, "_DETECTOR_PATH", detector_path)
        monkeypatch.setattr(pm, "_THREATS_PATH", threats_path)
        monkeypatch.setattr(pm, "_LEDGER_PATH", missing_ledger)
        monkeypatch.setattr(pm, "_OUT_DIR", out_dir)
        monkeypatch.setattr(pm, "_OUT_PATCH", out_dir / "mutation_patch.json")
        monkeypatch.setenv("GEMINI_API_KEY", "fake-key-for-test")

        patch_result, err = pm.propose_mutation(
            gemini_paid_credit=True, allow_live_model=True
        )
        assert patch_result is None, "Must refuse when ledger is missing"
        assert err, "Must produce an error message"
        assert "budget state unknown" in err.lower() or "not usable" in err.lower() or \
               "not found" in err.lower() or "missing" in err.lower(), (
                   f"Error must mention ledger problem, got: {err}"
               )

    def test_malformed_ledger_refuses_budget_check(
        self, tmp_path: Path, live_paid_genome: dict, monkeypatch: "pytest.MonkeyPatch"
    ) -> None:
        """Malformed api_usage_ledger.json must cause the live paid path to refuse."""
        import scripts.propose_mutation as pm

        genome_path = tmp_path / "genome.json"
        genome_path.write_text(json.dumps(live_paid_genome), encoding="utf-8")
        detector_path = self._minimal_detector(tmp_path)
        threats_path = tmp_path / "active_threats.json"
        threats_path.write_text('[{"id": "T-001"}]', encoding="utf-8")
        out_dir = tmp_path / "out"
        out_dir.mkdir()
        bad_ledger = tmp_path / "api_usage_ledger.json"
        bad_ledger.write_text("{INVALID JSON!!!", encoding="utf-8")

        monkeypatch.setattr(pm, "_GENOME_PATH", genome_path)
        monkeypatch.setattr(pm, "_DETECTOR_PATH", detector_path)
        monkeypatch.setattr(pm, "_THREATS_PATH", threats_path)
        monkeypatch.setattr(pm, "_LEDGER_PATH", bad_ledger)
        monkeypatch.setattr(pm, "_OUT_DIR", out_dir)
        monkeypatch.setattr(pm, "_OUT_PATCH", out_dir / "mutation_patch.json")
        monkeypatch.setenv("GEMINI_API_KEY", "fake-key-for-test")

        patch_result, err = pm.propose_mutation(
            gemini_paid_credit=True, allow_live_model=True
        )
        assert patch_result is None, "Must refuse when ledger is malformed"
        assert err, "Must produce an error message"

    def test_non_list_ledger_refuses_budget_check(
        self, tmp_path: Path, live_paid_genome: dict, monkeypatch: "pytest.MonkeyPatch"
    ) -> None:
        """Non-list api_usage_ledger.json (e.g. dict) must cause the live path to refuse."""
        import scripts.propose_mutation as pm

        genome_path = tmp_path / "genome.json"
        genome_path.write_text(json.dumps(live_paid_genome), encoding="utf-8")
        detector_path = self._minimal_detector(tmp_path)
        threats_path = tmp_path / "active_threats.json"
        threats_path.write_text('[{"id": "T-001"}]', encoding="utf-8")
        out_dir = tmp_path / "out"
        out_dir.mkdir()
        dict_ledger = tmp_path / "api_usage_ledger.json"
        dict_ledger.write_text('{"this": "is a dict not a list"}', encoding="utf-8")

        monkeypatch.setattr(pm, "_GENOME_PATH", genome_path)
        monkeypatch.setattr(pm, "_DETECTOR_PATH", detector_path)
        monkeypatch.setattr(pm, "_THREATS_PATH", threats_path)
        monkeypatch.setattr(pm, "_LEDGER_PATH", dict_ledger)
        monkeypatch.setattr(pm, "_OUT_DIR", out_dir)
        monkeypatch.setattr(pm, "_OUT_PATCH", out_dir / "mutation_patch.json")
        monkeypatch.setenv("GEMINI_API_KEY", "fake-key-for-test")

        patch_result, err = pm.propose_mutation(
            gemini_paid_credit=True, allow_live_model=True
        )
        assert patch_result is None, "Must refuse when ledger is non-list"
        assert err, "Must produce an error message"

    def test_missing_ledger_not_treated_as_empty(
        self, tmp_path: Path, live_paid_genome: dict, monkeypatch: "pytest.MonkeyPatch"
    ) -> None:
        """Missing ledger must NOT be treated as [] (zero spend) in the budget check."""
        import scripts.propose_mutation as pm

        genome_path = tmp_path / "genome.json"
        genome_path.write_text(json.dumps(live_paid_genome), encoding="utf-8")
        detector_path = self._minimal_detector(tmp_path)
        threats_path = tmp_path / "active_threats.json"
        threats_path.write_text('[{"id": "T-001"}]', encoding="utf-8")
        out_dir = tmp_path / "out"
        out_dir.mkdir()
        missing_ledger = tmp_path / "api_usage_ledger.json"
        # DO NOT create the file

        monkeypatch.setattr(pm, "_GENOME_PATH", genome_path)
        monkeypatch.setattr(pm, "_DETECTOR_PATH", detector_path)
        monkeypatch.setattr(pm, "_THREATS_PATH", threats_path)
        monkeypatch.setattr(pm, "_LEDGER_PATH", missing_ledger)
        monkeypatch.setattr(pm, "_OUT_DIR", out_dir)
        monkeypatch.setattr(pm, "_OUT_PATCH", out_dir / "mutation_patch.json")
        monkeypatch.setenv("GEMINI_API_KEY", "fake-key-for-test")

        patch_result, err = pm.propose_mutation(
            gemini_paid_credit=True, allow_live_model=True
        )
        # If missing ledger were treated as [] the call would proceed to budget check
        # and potentially (if budget ok) to an API call.  We want it to fail
        # immediately with a ledger error.
        assert patch_result is None
        # Error message must NOT be purely about budget — it must mention the ledger
        assert err
        # Should not be a budget overflow error (which would imply ledger was treated as [])
        assert "ledger" in err.lower() or "budget state unknown" in err.lower() or \
               "not usable" in err.lower() or "not found" in err.lower()


# ---------------------------------------------------------------------------
# 13. noop/offline-sample non-API paths not broken
# ---------------------------------------------------------------------------


class TestNonApiPathsNotBroken:
    """Verify that noop and offline-sample paths are not affected by strict ledger logic.

    These paths do not perform API calls and must continue to work even when
    the ledger file is missing or malformed.
    """

    def test_noop_mode_ignores_ledger(self, tmp_path: Path, monkeypatch: "pytest.MonkeyPatch") -> None:
        """noop mode must succeed regardless of ledger state.

        noop is a CLI-only mode (via main()); it exits 0 without touching ledger.
        """
        import scripts.propose_mutation as pm

        genome = {"project": "Test", "generation": 1, "best_score": -1.0}
        genome_path = tmp_path / "genome.json"
        genome_path.write_text(json.dumps(genome), encoding="utf-8")
        missing_ledger = tmp_path / "api_usage_ledger.json"
        # DO NOT create the ledger

        monkeypatch.setattr(pm, "_GENOME_PATH", genome_path)
        monkeypatch.setattr(pm, "_LEDGER_PATH", missing_ledger)

        # noop is handled in main(), not in propose_mutation() directly
        exit_code = pm.main(["--noop"])
        assert exit_code == 0, "noop mode must exit 0 regardless of ledger state"

    def test_offline_sample_ignores_missing_ledger(
        self, tmp_path: Path, monkeypatch: "pytest.MonkeyPatch"
    ) -> None:
        """offline-sample mode must succeed even when ledger is missing."""
        import scripts.propose_mutation as pm

        minimal_detector = '''\
from core.types import Request, DetectionResult


def inspect_request(request: Request) -> DetectionResult:
    # === MUTATION_START ===
    return DetectionResult(
        blocked=False,
        reason="no suspicious indicator matched",
        confidence=0.0,
        matched_signals=(),
    )
    # === MUTATION_END ===
'''
        genome = {
            "project": "Test",
            "generation": 1,
            "best_score": -1.0,
            "max_prompt_chars": 12000,
            "max_output_tokens": 2048,
        }
        genome_path = tmp_path / "genome.json"
        genome_path.write_text(json.dumps(genome), encoding="utf-8")
        detector_path = tmp_path / "detector.py"
        detector_path.write_text(minimal_detector, encoding="utf-8")
        threats_path = tmp_path / "active_threats.json"
        threats_path.write_text('[{"id": "T-001"}]', encoding="utf-8")
        out_dir = tmp_path / "out"
        out_dir.mkdir()
        missing_ledger = tmp_path / "api_usage_ledger.json"
        # DO NOT create the ledger

        monkeypatch.setattr(pm, "_GENOME_PATH", genome_path)
        monkeypatch.setattr(pm, "_DETECTOR_PATH", detector_path)
        monkeypatch.setattr(pm, "_THREATS_PATH", threats_path)
        monkeypatch.setattr(pm, "_LEDGER_PATH", missing_ledger)
        monkeypatch.setattr(pm, "_OUT_DIR", out_dir)
        monkeypatch.setattr(pm, "_OUT_PATCH", out_dir / "mutation_patch.json")

        patch_result, err = pm.propose_mutation(offline_sample=True)
        # offline-sample must produce a patch (not None) — it does not use the ledger
        assert err == "", f"offline-sample should not error, got: {err}"
        assert patch_result is not None, "offline-sample must produce a patch regardless of ledger state"


# ---------------------------------------------------------------------------
# Date keys (moved from original position to after new test classes)
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
