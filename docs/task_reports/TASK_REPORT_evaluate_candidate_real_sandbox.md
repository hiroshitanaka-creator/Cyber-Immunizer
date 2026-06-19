# Task Report: Real Docker Sandbox for Candidate Evaluation

## Summary

This task replaces the production `scripts/evaluate_candidate.py` fitness execution boundary with a Docker sandbox backend. AST validation, offline candidate contract checks, behavioral surface checks, benign-control checks, candidate hashing, report writing, and soft-reject semantics remain in the host-side evaluator before the untrusted fitness run.

## Canonical State Checked

- Current branch was created from local HEAD `1d86f09`, which is the merge commit for PR #124.
- `data/project_state.json` and `docs/PROJECT_STATE.md` were inspected before implementation.
- No paid-credit workflow, workflow dispatch, Gemini API call, promotion, or ledger/genome/history edit was performed.

## Sandbox Boundary

Production/default backend: `docker`.

Docker command controls:

- Image: `python:3.11-slim`
- Network: `--network none`
- Root filesystem: `--read-only`
- Capabilities: `--cap-drop ALL`
- Privilege escalation: `--security-opt no-new-privileges`
- User: `--user 65534:65534`
- PID limit: `--pids-limit 32`
- Memory limit: `--memory 768m`
- CPU limit: `--cpus 1`
- Writable filesystem: isolated `/tmp` only via `--tmpfs /tmp:rw,noexec,nosuid,nodev,size=64m`
- Project mount: repository mounted read-only at `/workspace`
- Candidate mount: candidate file mounted read-only at `/candidate/candidate_detector.py`
- Container environment: explicit `HOME=/tmp` and `PYTHONPATH=/workspace` only
- Docker launcher environment: stripped allowlist; no GitHub token, Gemini key, or cloud credentials are passed

## Fail-Closed Behavior

If Docker is unavailable for the default backend, evaluation returns and writes a report with:

- `success=false`
- `passed_adoption_gate=false`
- `is_tool_failure=true`
- Docker/sandbox availability text in `error`
- `sandbox_backend="docker"`

Timeouts and malformed sandbox stdout remain hard tool failures. The legacy POSIX rlimit backend remains available only through explicit `--sandbox-backend legacy-rlimit` local-dev/test opt-in.

## Changed Files

- `scripts/evaluate_candidate.py`: added sandbox backend abstraction, Docker command construction, fail-closed Docker execution, explicit legacy rlimit fallback, and sandbox report metadata.
- `tests/test_evaluate_candidate.py`: updated production-default tests to assert Docker hardening flags, env stripping, fail-closed Docker unavailable handling, timeout handling, malformed stdout handling, and explicit legacy backend restrictions.
- `.github/workflows/ci.yml`: added Docker availability verification before the evaluate_candidate smoke test so CI exercises the default Docker path.
- `.github/workflows/immunization_loop.yml`: updated evaluate job wording from subprocess-only language to Docker sandbox language.
- `README.md`: replaced stale subprocess-isolation wording with Docker sandbox wording.
- `docs/task_reports/TASK_REPORT_evaluate_candidate_real_sandbox.md`: records the sandbox boundary, verification, CI status, and residual risk for this task.

## Verification Commands and Results

- `python -m pytest tests/test_evaluate_candidate.py -q` — passed locally.
- `python -m pytest tests/test_ci_workflow.py tests/test_workflow.py -q` — passed locally.
- `python scripts/validate_mutation.py --candidate core/detector.py --json` — passed locally with `{"valid": true, "violations": []}`.
- `python -m pytest -q` — passed locally.
- `python scripts/evaluate_candidate.py --candidate core/detector.py --timeout 30 --json --soft-reject --baseline` — fail-closed locally because this container does not have the Docker CLI installed; the resulting report records `sandbox_backend="docker"` and `is_tool_failure=true`.

## CI Result

GitHub Actions was not run from this container because the local checkout has no configured `origin` remote. The CI workflow now includes a `docker version` step before `Smoke test: evaluate_candidate (soft-reject)` so hosted CI will fail explicitly if Docker is unavailable instead of silently falling back to host subprocess execution.

## Residual Risk

- Docker shares the host kernel; this is a stronger sandbox boundary than host subprocess rlimits but is not a VM boundary.
- Docker default seccomp is used; a custom seccomp profile and evaluation attestation are intentionally out of scope for this task.
- The Docker image is the official `python:3.11-slim`; image pinning/digest attestation is a future hardening step.
- Promotion attestation is intentionally out of scope and should be handled in the next phase.
