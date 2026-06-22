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

## Fix Pass — Codex Review P2/P3 Remediation (PR #169)

This pass addresses the three Codex Review findings that were blocking PR #169
and were left because no GPT Audit Gate ran before the PR was opened. Scope was
limited to the three ALLOWED files; no `core/**`, `data/**`, `.github/**`, or
workflow change was made.

### Issues addressed

- **P2 — Exception outcomes were not counted under `exceptions`.**
  `_classify()` returns the singular `"exception"`, but `_record()` only
  incremented counters named in `_COUNT_KEYS` (which holds the plural
  `"exceptions"`), so aggregate buckets stayed at 0 and
  `test_exception_case_records_latency_and_exception` failed. `_record()` now
  maps a per-case `"exception"` outcome to the aggregate `exceptions` counter,
  so `overall`, `per_category`, `per_kind`, and `per_tier` all increment. The
  per-case `outcome` string remains `"exception"`.

- **P3 — Latency included `_make_request()` adapter overhead.**
  The `Request` is now built *before* the timer starts; the timer brackets only
  `inspect_request_with_structured_rules(...)`. Detector exceptions are still
  recorded as per-case `"exception"` with a measured latency. If
  `_make_request()` itself raises (rare; `load_corpus()` validates request
  shape), a safe `"exception"` outcome with `latency_ms = 0.0` is recorded
  rather than misrepresenting adapter time as detector-call latency.

- **P3 — Markdown lacked a per-kind section.**
  The Markdown report previously jumped from per-category rows to the L2-V3
  tier table even though `build_json_report()` computes `per_kind`. A
  `## Per-Kind Results` section now renders Kind, TP, FP, TN, FN, Exceptions,
  Pass rate, Avg latency ms, and Max latency ms, restoring the per-kind slice
  the original `cli.structured_eval` already exposed.

### Tests added / updated

- `test_exception_case_records_latency_and_exception` — now passes
  (`overall["exceptions"] == 1`).
- `test_exception_counts_increment_all_aggregate_buckets` — new; proves
  `overall`, `per_category["path-traversal"]`, `per_kind["attack"]`, and
  `per_tier["holdout"]` each increment `exceptions` on a forced detector
  exception, and that the per-case outcome stays `"exception"`.
- `test_latency_timer_starts_after_request_construction` — new; uses an injected
  counting clock plus a `_make_request` spy to prove request construction
  happens before the first clock tick and that the measured interval covers only
  the detector call.
- `test_markdown_has_per_kind_latency_section` — new; asserts the Markdown
  contains `## Per-Kind Results`, Pass rate / Avg latency ms / Max latency ms
  columns, the `attack` and `benign` kind rows, and that the per-kind heading
  precedes the tier section.
- `test_json_and_markdown_preserve_existing_latency_outputs` — new; guards that
  the existing overall / per-case / per-category / per-tier JSON latency fields
  and the existing Markdown sections remain present alongside the new section.

### Validation results (this fix pass)

```
python -m pytest tests/test_structured_eval_latency_cli.py -q   -> 15 passed
python -m pytest tests/test_structured_eval_cli.py -q           -> 102 passed
python -m pytest tests/ -q                                      -> 2953 passed
git diff --check                                               -> clean
forbidden-file check                                           -> only the 3 ALLOWED files changed
```

### Layer status after fix pass

Layer 2 is **still not complete**. This pass only restores the latency-evidence
capability to a mergeable, Codex-clean state. Layer 2 completion still requires
Project Owner review and acceptance of realistic, safely neutralized corpus
evidence across L2-V1 through L2-V5; this PR does not provide that and makes no
external-user-value claim.
