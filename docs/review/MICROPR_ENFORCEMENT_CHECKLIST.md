# MicroPR Enforcement Checklist

Use this 1-page checklist for every MicroPR review. A MicroPR should have one purpose, minimal file changes, and enough attached evidence for reviewers to reproduce the safety decision without rerunning paid-credit workflows.

## Required MicroPR Evidence

Before requesting review, attach or link all required artifacts in the PR body:

- [ ] `reports/ruff.txt` from the exact lint command used for the PR.
- [ ] `reports/bandit.json` from the exact Bandit command used for the PR.
- [ ] `pytest-junit.xml` from the exact pytest run used for the PR.
- [ ] `fitness_report.json` when the PR affects candidate scoring, evaluation, promotion evidence, or detector safety claims.
- [ ] GitHub Actions CI Run ID for the workflow run that produced or validated the artifacts.

## Local Verification Gates

A MicroPR is not review-ready until the author confirms:

- [ ] Ruff completed and the saved output is attached as `reports/ruff.txt`.
- [ ] Bandit completed and the saved JSON output is attached as `reports/bandit.json`.
- [ ] Pytest completed and the JUnit report is attached as `pytest-junit.xml`.
- [ ] `fitness_report.json` is attached when required and matches the candidate or baseline discussed in the PR.
- [ ] No unrelated runtime, detector, ledger, model, budget, workflow, or promotion changes are included.

## GitHub Actions Artifact Gates

Reviewers should verify that CI evidence is traceable:

- [ ] The PR body lists the CI Run ID.
- [ ] The CI run has retained artifacts for Ruff, Bandit, pytest JUnit, and any required fitness report.
- [ ] Artifact filenames match the PR evidence list exactly.
- [ ] The artifacts correspond to the reviewed commit SHA, not an older run.

## Docker Digest Pinning Gate

For any Docker image introduced or changed by a MicroPR:

- [ ] Images are pinned by immutable digest (`image@sha256:...`) instead of mutable tags only.
- [ ] The PR explains any temporary tag-only exception and includes a follow-up owner decision.
- [ ] Reviewers request changes if a Docker image can drift silently across reruns.

## Reviewer Request Changes Behavior

Reviewers should use **Request Changes** when any item below is true:

- [ ] Required MicroPR Evidence is missing, stale, or not linked to the reviewed commit.
- [ ] Ruff, Bandit, pytest, or required fitness evidence failed without an accepted owner-scoped exception.
- [ ] GitHub Actions artifacts are missing, expired, renamed without explanation, or tied to the wrong commit SHA.
- [ ] Docker images are changed without digest pinning or a documented owner-approved exception.
- [ ] The PR changes runtime logic, detector behavior, paid-credit state, promotion state, ledger files, model names, budget settings, or workflows outside the approved scope.

If all gates pass, reviewers may approve subject to the repository's standard GPT Audit Gate and Project Owner final merge decision.
