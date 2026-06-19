# Task Report — Evaluation / Promotion Attestation Gate

## Summary

PR #126 is finalized as an operational, fail-closed evaluation-to-promotion attestation gate. The promote job must verify an evaluate-job-generated attestation before promotion can run.

The approved Docker image digest for `python:3.11-slim` is:

```text
python@sha256:ae52c5bef62a6bdd42cd1e8dffef86b9cd284bde9427da79839de7a4b983e7ca
```

Digest resolution note: this execution environment does not provide a Docker CLI, so the Docker commands could not be run locally here. The digest above was resolved from Docker Hub metadata for `python:3.11-slim` and is committed in the image-scoped allowlist. In Docker-capable CI, the workflow pulls this exact digest, inspects it, and fails closed unless the resolved digest exactly equals the approved digest.

## Gate behavior

The gate verifies all of the following before promotion:

- candidate artifact hash
- fitness report artifact hash
- evaluated SHA and base/main SHA
- Docker backend and sandbox posture
- Docker runtime image (`python:3.11-slim@sha256:ae52c5bef62a6bdd42cd1e8dffef86b9cd284bde9427da79839de7a4b983e7ca`)
- approved Docker image digest via image-scoped allowlist
- rejection of unapproved Docker digests
- strict boolean values for hardening flags and adoption gates
- rejection of adoption gate contradictions, including nested `fitness_report` / `metrics` contradictions when present

The gate is now operationally enabled for the approved digest above. It remains fail-closed: if the digest is absent, malformed, unapproved, or resolved differently in CI, promotion is refused.

## Workflow pinning

The workflow now pulls the approved digest-pinned runtime image directly and exposes that digest-pinned image string to the evaluator and attestation writer. This prevents silent upstream drift without retagging execution back to the floating tag.

## Residual risk

- Docker is not a VM boundary.
- The attestation is CI-generated and is not cryptographically signed by Sigstore/Cosign.
- The Docker digest allowlist requires maintenance when the base image is intentionally updated.
- GitHub artifact transport is still trusted, but artifact tampering is detected by hash cross-checks.

## No-API confirmation

This task did not run paid-credit mode, did not run `workflow_dispatch`, did not call Gemini, and did not edit ledger/genome/detector state files.
