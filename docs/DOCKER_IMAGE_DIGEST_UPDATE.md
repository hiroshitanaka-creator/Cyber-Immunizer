# Docker Sandbox Image Digest Update Procedure

## Current Canonical Image

- Tag: `python:3.11-slim`
- Repo digest: `python@sha256:ae52c5bef62a6bdd42cd1e8dffef86b9cd284bde9427da79839de7a4b983e7ca`
- Runtime image: `python:3.11-slim@sha256:ae52c5bef62a6bdd42cd1e8dffef86b9cd284bde9427da79839de7a4b983e7ca`

Candidate runtime evaluation uses the runtime image string above, not the bare tag. The repo digest is retained separately so CI and promotion attestations can compare Docker's `RepoDigests` value against the approved allowlist entry.

## Future Digest Update Steps

1. Resolve and review the new upstream digest for `python:3.11-slim` in a Docker-capable environment.
2. Update the canonical constants in `scripts/candidate_contract.py`:
   - `DOCKER_IMAGE_TAG`
   - `DOCKER_IMAGE_REPO_DIGEST`
   - `DOCKER_IMAGE_DIGEST`
   - `DOCKER_IMAGE`
3. Update workflow pull/inspection strings in:
   - `.github/workflows/ci.yml`
   - `.github/workflows/immunization_loop.yml`
4. Update the image-scoped allowlist in `security/docker_digest_allowlist.json` while keeping the key as `python:3.11-slim` unless the runtime tag intentionally changes.
5. Update documentation and reports:
   - `README.md`
   - `docs/task_reports/TASK_REPORT_evaluate_candidate_real_sandbox.md`
   - this file, if the canonical image changes
6. Update relevant tests that assert the approved digest string or digest-pinned image format.

## Verification Commands

Run these checks before requesting review:

```bash
python -m pytest tests/test_candidate_contract.py -q
python -m pytest tests/test_evaluate_candidate.py -q
python -m pytest tests/test_ci_workflow.py tests/test_workflow.py -q
python -m pytest tests/test_promotion_attestation.py -q
python -m pytest -q
python scripts/validate_mutation.py --candidate core/detector.py --json
grep -R "docker pull python:3.11-slim$" -n .github scripts tests || true
grep -R "DOCKER_IMAGE = \"python:3.11-slim\"" -n scripts tests || true
grep -R "python:3.11-slim" -n .github scripts tests docs README.md security || true
grep -R "@sha256:" -n .github scripts tests docs README.md security || true
```

In a Docker-capable environment, also run:

```bash
docker pull python:3.11-slim@sha256:ae52c5bef62a6bdd42cd1e8dffef86b9cd284bde9427da79839de7a4b983e7ca
python scripts/evaluate_candidate.py --candidate core/detector.py --timeout 60 --json --soft-reject --baseline
```

If Docker is unavailable locally, confirm the fail-closed report still records:

- `sandbox_backend == "docker"`
- `is_tool_failure == true`
- `sandbox_image` contains `@sha256:`

## Review Checklist

- Runtime image is not a bare tag.
- Fitness reports include `sandbox_image` with `@sha256:`.
- Promotion attestation `docker_image` matches the report `sandbox_image`.
- Promotion attestation `docker_image_digest` is a `python@sha256:<digest>` repo digest present in `security/docker_digest_allowlist.json`.
- CI and evolution workflows pull the digest-pinned runtime image and do not retag it back to a bare-tag execution image.
