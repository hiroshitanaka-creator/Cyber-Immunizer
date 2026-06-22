# Task Report — Layer 2 Structured Evaluation Latency Evidence

## Summary

- Added `cli/structured_eval_latency.py`, an Owner/auditor-facing structured rules evaluation CLI that records per-case latency and aggregate latency metrics.
- This complements `cli/structured_eval.py`, which already reports TP/FP/FN by category, kind, and tier but explicitly did not capture latency.
- The new CLI is read-only. It does not write repository state, call model APIs, dispatch workflows, promote candidates, or alter the default detector.
- The task advances Layer 2 evidence readiness by addressing the latency component of L2-V2, but it does **not** claim Layer 2 completion. Owner-accepted realistic, safely neutralized corpus evidence is still required.

## Why This Task

`docs/DEFINITION_OF_DONE.md` defines L2-V2 as requiring clear per-category TP/FP/FN and latency reporting. Existing `cli/structured_eval.py` produced TP/FP/FN but stated latency must be collected separately. This left an avoidable gap in the Owner/auditor value-validation path.

## Changed Files

- `cli/structured_eval_latency.py` — new latency-aware structured rules evaluator.
- `tests/test_structured_eval_latency_cli.py` — tests for deterministic latency capture, aggregate latency summaries, JSON/Markdown report fields, exception latency handling, and CLI behavior.
- `docs/task_reports/TASK_REPORT_L2_STRUCTURED_EVAL_LATENCY.md` — this report.

## Behavior Added

The new CLI supports:

```bash
python -m cli.structured_eval_latency --rules <rules.json> --corpus <corpus.json>
python -m cli.structured_eval_latency --rules <rules.json> --corpus <corpus.json> --json
```

It reports:

- per-case `latency_ms`
- overall `avg_latency_ms`, `min_latency_ms`, `max_latency_ms`, `latency_count`
- per-category latency summaries
- per-kind latency summaries
- holdout / drift / counterfactual tier latency summaries
- TP / FP / TN / FN / exception counts
- TP / FP / FN / pass-rate derivatives where applicable

## Safety Boundary

- No network calls.
- No Gemini or paid-credit API call.
- No workflow dispatch.
- No promotion.
- No `core/**` edit.
- No `data/**` edit.
- No `.github/**` edit.
- No default detector behavior change.
- No external-user product claim.

## Layer Declaration

- [ ] Layer 1 — Research Foundation
- [x] Layer 2 — Value Validation
- [ ] Layer 3 — AI Operation Control
- [ ] None

Reason: This task adds latency evidence capability required by L2-V2. It does not complete Layer 2 because realistic threat coverage, Owner review, improvement explanation, and no-overfitting evidence still remain required.

## Validation

Validation commands expected for this PR:

```bash
python -m pytest tests/test_structured_eval_latency_cli.py -q
python -m pytest tests/test_structured_eval_cli.py -q
python -m pytest tests/ -q
git diff --check
```

At creation time, commands were not run locally by GPT because this task was applied through the GitHub connector rather than a checked-out runner. CI must be used as the source of truth for command execution.

## Remaining Risks

- This adds a new CLI rather than modifying `cli.structured_eval.py`; users must intentionally call `cli.structured_eval_latency` when latency evidence is required.
- Latency is measured around local detector evaluation only. It does not represent production traffic, WAF deployment, or external system latency.
- Repository fixtures are symbolic / neutralized and do not constitute Layer 2 completion evidence by themselves.
