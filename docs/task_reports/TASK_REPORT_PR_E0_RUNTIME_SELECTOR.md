# Task Report — PR-E0 Runtime Selector

## Summary

- Added explicit runtime selector `core/runtime_selector.py`.
- Default path remains legacy detector (`core.detector.inspect_request`).
- Structured rules require explicit `mode="structured_rules"` and explicit `structured_rules_doc`.
- No file/env/network auto-load.
- No silent fallback from structured mode to legacy.

## Project Owner approval

- `AGENTS.md` requires explicit Project Owner approval before changing `core/**`.
- This PR changes `core/**` only by adding `core/runtime_selector.py`.
- Project Owner approval is specific to PR-E0 / PR #165 and specific to adding the explicit runtime selector module.
- This approval does **not** authorize changes to `core/detector.py`, `core/structured_detector.py`, `core/structured_evaluator.py`, `core/structured_validator.py`, `data/**`, `.github/**`, scripts, model settings, paid-credit execution, workflow dispatch, or promotion.
- Approval record: Project Owner requested PR-E0 (`explicit structured-rules runtime selector behind gate`) and, after Codex P1 review, explicitly instructed that the approval-record gap be fixed for PR #165.

## Changed files

- `core/runtime_selector.py` — new module
- `tests/test_runtime_selector.py` — new test file (21 tests)
- `docs/task_reports/TASK_REPORT_PR_E0_RUNTIME_SELECTOR.md` — this file

## Verification

```
python -m pytest tests/test_runtime_selector.py -q          # 21 passed
python -m pytest tests/test_structured_detector_integration.py tests/test_structured_detector_equivalence.py -q  # 28 passed
python -m pytest tests/ -q                                   # 2831 passed
git diff --check
```

## Safety

- No Gemini API call.
- No paid-credit run.
- No workflow_dispatch.
- No promotion.
- No data edit.
- No default detector behavior change.
- `core/detector.py` unchanged and contains no structured integration references.

## Layer declaration

- [x] Layer 1 — Research Foundation
- [ ] Layer 2 — Value Validation
- [x] Layer 3 — AI Operation Control
- [ ] None

Reason:
- Layer 1: adds executable runtime selector for structured-rules research path without changing default detector.
- Layer 3: strengthens operational gate semantics and prevents accidental implicit structured-rules activation.
- Layer 2 is not claimed.
