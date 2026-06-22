# Task Report — PR-E1 Structured Rules Candidate Evaluation

## Summary

- Added explicit structured-rules candidate evaluation script.
- Uses explicit `--rules` input only. No auto-load from `.cyber_immunizer/**` or environment variables.
- Evaluates through `core.runtime_selector.inspect_request_with_runtime_selector(..., mode="structured_rules", structured_rules_doc=...)`.
- Reuses `core.fitness` scoring/adoption helper semantics to avoid formula drift (`_compute_score`, `_adoption_gate`, `_adaptive_floor_gate`, `_compute_tier_pass_rate`).
- Does not change default detector behavior (`core/detector.py` unchanged).
- Does not promote, dispatch workflows, call APIs, or edit data.

## Codex Review P2 Findings (PR #166, sixth pass) — All Fixed

One additional fail-closed hardening fix:

1. **`UnicodeDecodeError` in genome load call site**: `evaluate_structured_rules()` call site for `_load_genome()` previously caught `(OSError, json.JSONDecodeError, ValueError, RecursionError)` but NOT `UnicodeDecodeError`. When `_load_genome()` calls `read_text(encoding="utf-8")` on a non-UTF-8 binary genome file, the exception propagated as an unhandled traceback. Fixed by adding `UnicodeDecodeError` to the except tuple. Two new tests added to `TestGenomeFileGuard`: `test_non_utf8_genome_is_tool_failure` and `test_non_utf8_genome_soft_reject_still_exits_1`.

## Codex Review P2 Findings (PR #166, fifth pass) — All Fixed

Five additional fail-closed hardening fixes:

1. **Regular-file guard for `--genome`**: `_load_genome()` now calls `stat()` before `read_text()`, checks `stat.S_ISREG()` to reject FIFOs/directories/devices, and enforces `_MAX_GENOME_FILE_BYTES = 1_048_576` before reading. All via `OSError` raises that the call site catches as tool failures.

2. **Contain schema validation exceptions**: `validate_rules_schema(rules_doc)` is now wrapped in `try/except (OverflowError, RecursionError, TypeError, ValueError)`. Unexpected exceptions (e.g., `OverflowError` from extreme numeric values inside the rules doc) return `evaluation_completed=False` (tool failure), not a traceback.

3. **Genome threshold validation overflow-safe**: Extracted `_to_finite_float()` helper that catches `OverflowError` from `float(val)` (huge Python integers from JSON literals can exceed float range). `_validate_genome_thresholds()` now uses this helper for all numeric fields, so a `best_score: 10**400` in a genome file is a structured tool failure rather than an unhandled exception.

4. **Reject non-regular report targets before writing**: `main()` now checks `stat()` on the `--report-path` target (if it already exists) and rejects non-regular files (FIFOs, directories, devices) before evaluation begins. This prevents `write_text()` blocking indefinitely on a FIFO.

5. **Deterministic recursion tests via monkeypatch**: Added monkeypatch-based tests that force `RecursionError` from the `object_pairs_hook` during rules JSON parsing and from `_load_genome`, verifying structured tool failure output. Existing deep-nesting tests are kept alongside.

## Codex Review P2 Findings (PR #166, fourth pass) — All Fixed

Four additional fail-closed hardening fixes:

1. **Non-regular `--rules` path blocked**: Added `import stat`; after `rules_path.stat()`, check `stat.S_ISREG(st.st_mode)`. FIFOs, directories, and device nodes are rejected as tool failures before any read attempt, preventing indefinite blocking.

2. **Recursive genome JSON as tool failure**: Genome load call site exception handler expanded to `except (OSError, json.JSONDecodeError, ValueError, RecursionError)` — deeply nested genome JSON that causes RecursionError now returns a structured tool failure instead of an uncaught exception.

3. **All-tiers parity guard**: Parity guard now compares ALL evaluated case outcomes (main + holdout + counterfactual + drift). Previously only main-tier outcomes were compared, which would reject a candidate that improves only on adaptive tiers. Now: if structured rules differ from legacy on any tier, parity guard allows the candidate through.

4. **Report write failures as structured tool failures**: `main()` now writes the report file BEFORE emitting stdout JSON. `mkdir` and `write_text` are wrapped in `try/except OSError`. On failure, a consistent structured failure JSON is emitted to stdout (not a traceback) and the script exits 1. This applies even with `--soft-reject`.

## Codex Review P2 Findings (PR #166, third pass) — All Fixed

Five additional fail-closed hardening fixes:

1. **`.cyber_immunizer/**` report-path blocked**: Added `".cyber_immunizer"` to `_FORBIDDEN_REPORT_PREFIXES` so `--report-path .cyber_immunizer/fitness_report.json` and similar default report paths are rejected.

2. **Non-UTF-8 rules file**: `read_text(encoding="utf-8")` exception handler expanded to `except (OSError, UnicodeDecodeError)` — binary or invalid-encoding files are a tool failure, not a crash.

3. **Deeply nested JSON (RecursionError)**: `json.loads` exception handler expanded to `except (json.JSONDecodeError, ValueError, RecursionError)` — maliciously deep nesting returns a structured tool failure instead of a traceback.

4. **Genome JSON must be an object**: `_load_genome()` now uses `_reject_duplicate_keys` as `object_pairs_hook` and raises `ValueError` if the top-level parsed value is not a `dict`, preventing `.get()` crashes on `[]` or scalar genome files.

5. **Duplicate keys in genome JSON**: `_load_genome()` uses `object_pairs_hook=_reject_duplicate_keys`, so duplicate threshold keys (e.g. two `best_score` keys) are rejected as tool failures.

## Codex Review P2 Findings (PR #166, second pass) — All Fixed

Five additional P2 findings from the second Codex Review pass were addressed:

1. **Rules file size bound**: `_MAX_RULES_FILE_BYTES = 1_048_576`. `rules_path.stat().st_size` is checked before `read_text()`. Oversized files are a tool failure (exit 1, `evaluation_completed=False`) even with `--soft-reject`.

2. **Forbidden `--report-path` rejection**: `_is_forbidden_report_path()` checks whether the resolved path falls inside `data/`, `core/`, `.github/`, `scripts/`, `docs/audit_gate/`, `README.md`, `CLAUDE.md`, `AGENTS.md`, or `docs/PROJECT_STATE.md`. Forbidden targets exit 1 before evaluation starts.

3. **Parity guard**: `evaluate_detector(_legacy_inspect_request, cases)` is called (in non-baseline mode) after structured-rules evaluation. If per-case `actual_blocked` outcomes match the legacy detector's outcomes on all main-tier cases, the candidate is rejected with `"no_behavior_improvement_against_current_detector"`. Report includes `score_comparison_mode: "structured_rules_parity_guard"`.

4. **Genome threshold validation**: `_validate_genome_thresholds()` rejects `bool`, non-number, non-finite values, rates outside `[0.0, 1.0]`, and `max_avg_latency_ms <= 0`. Invalid thresholds are a tool failure.

5. **Duplicate key rejection**: `json.loads(..., object_pairs_hook=_reject_duplicate_keys)` raises `ValueError` on duplicate keys in any JSON object (top-level or nested). Duplicate keys are a tool failure before schema validation.

## Codex Review P2 Findings (PR #166, first pass) — All Fixed

Four P2 findings from the first Codex Review pass were addressed:

1. **Genome load fail-closed**: `_load_genome()` no longer silently returns `{}` on error. It raises `OSError` or `json.JSONDecodeError`, and the call site in `evaluate_structured_rules()` wraps it in try/except that returns a tool failure. A missing or malformed genome cannot silently substitute `previous_best_score=-1e9` and allow an under-performing candidate to pass the adoption gate.

2. **Adaptive-tier fail-closed**: `load_test_cases()` is called without `require_adaptive_tiers=False`. The default (`require_adaptive_tiers=True`) treats missing holdout/counterfactual/drift corpus files as tool failures, preventing the adaptive floor gate from being silently bypassed.

3. **Comparable scores**: `code_chars = len(raw_text)` (character count of the JSON document) is used in `_compute_score()`. Using `code_chars=0` would have inflated structured-rules scores vs Python-detector scores and could cause a candidate to falsely appear as an improvement over the current best.

4. **Invalid schema reports `success=False`**: When schema validation fails, the returned report has `success=False` and `evaluation_completed=True`. Previously `success=True` could mislead consumers that checked only `success`. The fix ensures `success` always equals `passed_adoption_gate`.

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

- `scripts/evaluate_structured_rules_candidate.py` — evaluation script (initial + P2 hardening)
- `tests/test_evaluate_structured_rules_candidate.py` — 101 tests (initial 28 + 10 first-pass P2 + 18 second-pass P2 + 10 third-pass P2 + 12 fourth-pass P2 + 21 fifth-pass P2 + 2 sixth-pass P2)
- `docs/task_reports/TASK_REPORT_PR_E1_STRUCTURED_RULES_EVALUATION.md` — this report

## Verification

All commands passed:

```
python -m pytest tests/test_evaluate_structured_rules_candidate.py -q
# → 101 passed

python -m pytest tests/test_runtime_selector.py tests/test_structured_detector_integration.py tests/test_structured_detector_equivalence.py -q
# → 49 passed

python -m pytest tests/ -q
# → 2932 passed

git diff --check
# → PASS (no whitespace errors)

git diff --name-only | grep -Ev '^(scripts/evaluate_structured_rules_candidate\.py|tests/test_evaluate_structured_rules_candidate\.py|docs/task_reports/TASK_REPORT_PR_E1_STRUCTURED_RULES_EVALUATION\.md)$'
# → no output (forbidden-path check PASS)

grep -n "runtime_selector\|structured_detector\|structured_evaluator\|inspect_request_with_structured_rules\|evaluate_structured_rules" core/detector.py
# → no matches (default detector unchanged)
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
- Tool failures: malformed JSON, unreadable file, genome load failure, test-case load failure
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
