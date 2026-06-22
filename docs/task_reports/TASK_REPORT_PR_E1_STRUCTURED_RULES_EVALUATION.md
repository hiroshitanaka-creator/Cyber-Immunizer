# Task Report — PR-E1 Structured Rules Candidate Evaluation

## Summary

- Added explicit structured-rules candidate evaluation script.
- Uses explicit `--rules` input only. No auto-load from `.cyber_immunizer/**` or environment variables.
- Evaluates through `core.runtime_selector.inspect_request_with_runtime_selector(..., mode="structured_rules", structured_rules_doc=...)`.
- Reuses `core.fitness` scoring/adoption helper semantics to avoid formula drift (`_compute_score`, `_adoption_gate`, `_adaptive_floor_gate`, `_compute_tier_pass_rate`).
- Does not change default detector behavior (`core/detector.py` unchanged).
- Does not promote, dispatch workflows, call APIs, or edit data.

## Project Owner Approval Boundary

Project Owner approval is limited to:

- `scripts/evaluate_structured_rules_candidate.py`
- `tests/test_evaluate_structured_rules_candidate.py`
- `docs/task_reports/TASK_REPORT_PR_E1_STRUCTURED_RULES_EVALUATION.md`

This approval does **not** authorize changes to:

- `core/**` (frozen)
- `data/**` (frozen)
- `.github/**` (frozen)
- `README.md`, `CLAUDE.md`, `AGENTS.md`
- model settings, paid-credit execution, workflow dispatch, promotion
- default detector behavior

## Changed Files

- `scripts/evaluate_structured_rules_candidate.py` — new evaluation script
- `tests/test_evaluate_structured_rules_candidate.py` — new test file (28 tests)
- `docs/task_reports/TASK_REPORT_PR_E1_STRUCTURED_RULES_EVALUATION.md` — this report

## Verification

All commands passed:

```
python -m pytest tests/test_evaluate_structured_rules_candidate.py -q
# → 28 passed

python -m pytest tests/test_runtime_selector.py tests/test_structured_detector_integration.py tests/test_structured_detector_equivalence.py -q
# → 49 passed

python -m pytest tests/ -q
# → 2859 passed

git diff --check
# → PASS (no whitespace errors)

git diff --name-only | grep -Ev '^(scripts/evaluate_structured_rules_candidate\.py|tests/test_evaluate_structured_rules_candidate\.py|docs/task_reports/TASK_REPORT_PR_E1_STRUCTURED_RULES_EVALUATION\.md)$'
# → no output (forbidden-path check PASS)

grep -n "runtime_selector|structured_detector|..." core/detector.py
# → no matches (default detector unchanged)

git status --short
# → only the three allowed files are untracked
```

## Script Behavior Summary

| Flag | Effect |
|---|---|
| `--rules PATH` | Required. Load structured rules JSON from explicit path. |
| `--genome PATH` | Optional. Defaults to `data/genome.json`. |
| `--json` | Print JSON report to stdout. |
| `--soft-reject` | Exit 0 for clean gate evaluation (even if failed). Exit 1 only for tool failures. |
| `--baseline` | Skip score-improvement requirement. |
| `--report-path PATH` | Write report to this path only. No default path written. |

### Exit Code Semantics

- Default: exit 0 = gate passed; exit 1 = tool failure or gate failed
- `--soft-reject`: exit 0 = evaluation completed; exit 1 = tool failure only
- Tool failures: malformed JSON, unreadable file, test-case load failure
- Candidate rejections (not tool failures): invalid schema, gate failed

## Safety

- No Gemini API call.
- No paid-credit run.
- No `workflow_dispatch`.
- No promotion.
- No `data/**` edit.
- No `.github/**` edit.
- No `core/**` edit.
- No default detector behavior change.
- No `.cyber_immunizer/**` default report write.
- No network calls. No subprocesses. No environment variables.

## Layer Declaration

- [x] Layer 1 — Research Foundation
- [ ] Layer 2 — Value Validation
- [x] Layer 3 — AI Operation Control
- [ ] None

**Reason:**
- Layer 1: Adds an executable local evaluation path for structured rules candidates (new capability that did not exist before).
- Layer 3: The path is explicit, gated, non-promotional, and uses no paid-credit or live API.
- Layer 2 is not claimed: the structured rules path is not yet connected to the default runtime or promotion workflow.
