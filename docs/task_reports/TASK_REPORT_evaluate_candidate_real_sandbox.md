# Task Report: Real Docker Sandbox for Candidate Evaluation

## Summary

This task replaces all candidate runtime execution reachable from `scripts/evaluate_candidate.py` with the Docker sandbox boundary. The final `core.fitness` execution, behavioral request-surface check, and behavioral benign-control check now share the same Docker sandbox posture. Static AST validation and static contract checks remain host-side because they parse/read candidate source without importing or executing candidate code.

## Canonical State Checked

- Local base is PR #124 merge commit `1d86f09`.
- PR #125 pre-fix CI run `27804570551` failed at `Smoke test: evaluate_candidate (soft-reject)` after `Verify Docker sandbox availability` succeeded.
- No paid-credit workflow, workflow dispatch, Gemini API call, promotion, or ledger/genome/history edit was performed.

## CI Failure Before This Fix

- Run id: `27804570551`
- Workflow: `CI`
- Conclusion: `failure`
- Failed step: `Smoke test: evaluate_candidate (soft-reject)`
- Root cause: PR #125 Dockerized only the final fitness execution. The evaluator still invoked `run_behavioral_surface_check_subprocess()` and `run_behavioral_benign_control_check_subprocess()` before fitness, and those functions imported/executed candidate code through host subprocesses in `scripts/candidate_contract.py`. This left candidate runtime execution outside the Docker boundary and made the CI smoke path incomplete.

## Sandbox Boundary

Production/default backend: `docker`.

Shared Docker command controls for behavioral checks and final fitness:

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

## Fix Implemented

- Moved candidate behavioral runtime checks to the Docker sandbox runner in `scripts/candidate_contract.py`.
- Reused the same Docker command construction for behavioral checks and final fitness execution.
- Removed the unsafe `_docker_available()` JSON compatibility fallback; Docker availability is true only when `docker version --format "{{.Server.Version}}"` returns exit code 0.
- Added CI Docker image preparation via `docker pull python:3.11-slim` and increased evaluate_candidate smoke timeout to allow three sandboxed candidate-runtime checks.
- Preserved `--sandbox-backend legacy-rlimit` only as an explicit final-fitness local-dev/test fallback; behavioral checks still use Docker in the default evaluator path.

## Fail-Closed Behavior

If Docker launch fails for behavioral checks or final fitness, evaluation returns and writes a report with:

- `success=false`
- `passed_adoption_gate=false`
- `is_tool_failure=true`
- Docker/sandbox availability text in `error`
- `sandbox_backend="docker"`

Behavioral candidate failures remain soft rejections when the Docker harness runs and returns candidate-behavior failure data. Harness launch failures, Docker timeouts, and malformed JSON remain hard tool failures.

## Changed Files

- `scripts/candidate_contract.py`: added shared Docker sandbox command/runner helpers and moved behavioral surface/benign-control runtime checks into Docker.
- `scripts/evaluate_candidate.py`: reuses the shared Docker runner for final fitness, keeps strict Docker availability behavior, and records sandbox metadata for behavioral fail-closed paths.
- `tests/test_candidate_contract.py`: added Docker command, strict availability, and behavioral Docker runner coverage while keeping local tests deterministic when Docker is absent.
- `tests/test_evaluate_candidate.py`: updated fail-closed and behavioral integration tests for the Docker behavioral boundary.
- `.github/workflows/ci.yml`: pre-pulls `python:3.11-slim` and gives the Docker-backed evaluate_candidate smoke test a 60-second timeout.
- `.github/workflows/immunization_loop.yml`: pre-pulls `python:3.11-slim` and gives the Docker-backed evaluate job a 60-second timeout without changing permissions or secrets.
- `docs/task_reports/TASK_REPORT_evaluate_candidate_real_sandbox.md`: records the CI failure, root cause, fix, verification, and residual risk.

## Verification Commands and Results

- `python -m pytest tests/test_evaluate_candidate.py -q` — passed locally.
- `python -m pytest tests/test_candidate_contract.py -q` — passed locally.
- `python -m pytest tests/test_ci_workflow.py tests/test_workflow.py -q` — passed locally.
- `python scripts/validate_mutation.py --candidate core/detector.py --json` — passed locally with `{"valid": true, "violations": []}`.
- `python -m pytest -q` — passed locally.
- `docker version` — not available in this local container (`docker: command not found`); GitHub-hosted CI is expected to provide Docker.
- `docker pull python:3.11-slim` — not available in this local container for the same reason.
- `python scripts/evaluate_candidate.py --candidate core/detector.py --timeout 60 --json --soft-reject --baseline` — fail-closed locally because this container has no Docker CLI; report records `sandbox_backend="docker"` and `is_tool_failure=true`.

## CI Result

Final GitHub Actions CI succeeded.

- Run id: `27805863171`
- Workflow: `CI`
- Conclusion: `success`

Relevant successful steps:

- `Run pytest`: success
- `Validate baseline detector (AST policy)`: success
- `Evaluate baseline detector fitness`: success
- `Smoke test: propose_mutation --noop`: success
- `Smoke test: propose_mutation --offline-sample`: success
- `Smoke test: apply_mutation (offline sample patch)`: success
- `Verify Docker sandbox availability`: success
- `Prepare Docker sandbox image`: success
- `Smoke test: evaluate_candidate (soft-reject)`: success

## Residual Risk

- Docker shares the host kernel; this is stronger than host subprocess rlimits but is not a VM boundary.
- Docker default seccomp is used; a custom seccomp profile is out of scope.
- Image digest pinning is not implemented in this task.
- Evaluation/promotion attestation remains out of scope and should be handled in the next phase.
