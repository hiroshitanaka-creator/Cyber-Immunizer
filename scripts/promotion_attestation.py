"""Create and verify evaluation-to-promotion attestations.

The attestation is a fail-closed handoff from the read-only evaluate job to the
write-capable promote job.  It binds the candidate artifact, fitness report,
evaluated main SHA, Docker sandbox posture, Docker image digest, and adoption
result so promote never blindly trusts downloaded artifacts.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

_PROJECT_ROOT = Path(__file__).parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from scripts.candidate_contract import (  # noqa: E402
    CONTAINER_CANDIDATE,
    CONTAINER_WORKSPACE,
    DOCKER_CPU_LIMIT,
    DOCKER_MEMORY_LIMIT,
    DOCKER_NON_ROOT_USER,
    DOCKER_PIDS_LIMIT,
    DOCKER_TMPFS,
)

SCHEMA_VERSION = 1
STAGE = "evaluation_promotion_attestation"

REQUIRED_SANDBOX_POSTURE: dict[str, Any] = {
    "sandbox_backend": "docker",
    "sandbox_network": "none",
    "sandbox_read_only_rootfs": True,
    "sandbox_user": DOCKER_NON_ROOT_USER,
    "sandbox_cap_drop": "ALL",
    "sandbox_no_new_privileges": True,
    "sandbox_pids_limit": int(DOCKER_PIDS_LIMIT),
    "sandbox_memory_limit": DOCKER_MEMORY_LIMIT,
    "sandbox_cpus": DOCKER_CPU_LIMIT,
    "sandbox_project_mount": f"{CONTAINER_WORKSPACE}:ro",
    "sandbox_candidate_mount": f"{CONTAINER_CANDIDATE}:ro",
    "sandbox_tmpfs": DOCKER_TMPFS,
    "sandbox_tmpfs_noexec": True,
    "sandbox_tmpfs_nosuid": True,
    "sandbox_tmpfs_nodev": True,
}

REPORT_TO_POSTURE_KEY = {
    "sandbox_backend": "sandbox_backend",
    "sandbox_network": "sandbox_network",
    "sandbox_read_only_rootfs": "sandbox_read_only",
    "sandbox_user": "sandbox_user",
    "sandbox_cap_drop": "sandbox_cap_drop",
    "sandbox_no_new_privileges": "sandbox_no_new_privileges",
    "sandbox_pids_limit": "sandbox_pids_limit",
    "sandbox_memory_limit": "sandbox_memory_limit",
    "sandbox_cpus": "sandbox_cpus",
    "sandbox_tmpfs": "sandbox_tmpfs",
}


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _extract_report_candidate_hash(report: dict[str, Any]) -> str | None:
    value = report.get("candidate_hash")
    if value:
        return value
    for key in ("fitness_report", "metrics"):
        inner = report.get(key)
        if isinstance(inner, dict) and inner.get("candidate_hash"):
            return inner["candidate_hash"]
    return None


def _load_allowed_digests(path: Path, docker_image: str) -> set[str]:
    data = _load_json(path)
    if not isinstance(data, dict):
        raise ValueError("Docker digest allowlist must be a JSON object")

    allowed_images = data.get("allowed_images")
    if isinstance(allowed_images, dict):
        image_digests = allowed_images.get(docker_image, [])
        if not isinstance(image_digests, list) or not all(
            isinstance(item, str) for item in image_digests
        ):
            raise ValueError(
                f"Docker digest allowlist allowed_images[{docker_image!r}] must be list[str]"
            )
        return set(image_digests)

    # Backward-compatible flat form for local tests / older allowlists.  The
    # committed allowlist uses image-scoped allowed_images so a digest approved
    # for one image cannot accidentally approve another image tag.
    digests = data.get("allowed_digests")
    if not isinstance(digests, list) or not all(isinstance(item, str) for item in digests):
        raise ValueError(
            "Docker digest allowlist must contain allowed_images or allowed_digests"
        )
    return set(digests)


def _report_sandbox_posture(report: dict[str, Any]) -> dict[str, Any]:
    posture = {
        attestation_key: report.get(report_key)
        for attestation_key, report_key in REPORT_TO_POSTURE_KEY.items()
    }
    tmpfs = posture.get("sandbox_tmpfs")
    tmpfs_parts = set(str(tmpfs).split(",")) if isinstance(tmpfs, str) else set()
    posture["sandbox_tmpfs_noexec"] = "noexec" in tmpfs_parts
    posture["sandbox_tmpfs_nosuid"] = "nosuid" in tmpfs_parts
    posture["sandbox_tmpfs_nodev"] = "nodev" in tmpfs_parts
    posture["sandbox_project_mount"] = f"{CONTAINER_WORKSPACE}:ro"
    posture["sandbox_candidate_mount"] = f"{CONTAINER_CANDIDATE}:ro"
    return posture


def build_attestation(
    *,
    candidate_path: Path,
    report_path: Path,
    evaluated_sha: str,
    base_main_sha: str,
    run_id: str,
    run_attempt: str,
    docker_image: str,
    docker_image_digest: str,
    digest_allowlist_path: Path,
) -> dict[str, Any]:
    report = _load_json(report_path)
    if not isinstance(report, dict):
        raise ValueError("fitness report must be a JSON object")

    candidate_sha256 = _sha256_file(candidate_path)
    report_candidate_hash = _extract_report_candidate_hash(report)
    posture = _report_sandbox_posture(report)

    return {
        "schema_version": SCHEMA_VERSION,
        "stage": STAGE,
        "attested_at": _dt.datetime.now(_dt.UTC).isoformat().replace("+00:00", "Z"),
        "evaluated_sha": evaluated_sha,
        "base_main_sha": base_main_sha,
        "run_id": run_id,
        "run_attempt": run_attempt,
        "candidate_path": str(candidate_path),
        "fitness_report_path": str(report_path),
        "candidate_sha256": candidate_sha256,
        "fitness_report_sha256": _sha256_file(report_path),
        "fitness_report_candidate_hash": report_candidate_hash,
        "passed_adoption_gate": report.get("passed_adoption_gate"),
        "docker_image": docker_image,
        "docker_image_digest": docker_image_digest,
        "docker_digest_allowlist_path": str(digest_allowlist_path),
        **posture,
    }


def verify_attestation(
    *,
    attestation_path: Path,
    candidate_path: Path,
    report_path: Path,
    expected_evaluated_sha: str,
    expected_base_main_sha: str,
    digest_allowlist_path: Path,
) -> list[str]:
    errors: list[str] = []

    if not attestation_path.exists():
        return [f"missing attestation: {attestation_path}"]
    try:
        attestation = _load_json(attestation_path)
    except json.JSONDecodeError as exc:
        return [f"attestation is malformed JSON: {exc}"]
    if not isinstance(attestation, dict):
        return ["attestation must be a JSON object"]

    attested_docker_image = attestation.get("docker_image")
    if not isinstance(attested_docker_image, str):
        return ["attestation docker_image must be a string"]

    try:
        allowed_digests = _load_allowed_digests(digest_allowlist_path, attested_docker_image)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return [f"could not load Docker digest allowlist: {exc}"]

    report: dict[str, Any] = {}
    if not report_path.exists():
        errors.append(f"missing fitness report: {report_path}")
    else:
        try:
            loaded_report = _load_json(report_path)
            if isinstance(loaded_report, dict):
                report = loaded_report
            else:
                errors.append("fitness report must be a JSON object")
        except json.JSONDecodeError as exc:
            errors.append(f"fitness report is malformed JSON: {exc}")

    expected_values: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "stage": STAGE,
        "evaluated_sha": expected_evaluated_sha,
        "base_main_sha": expected_base_main_sha,
        "candidate_path": str(candidate_path),
        "fitness_report_path": str(report_path),
        "docker_image": "python:3.11-slim",
        **REQUIRED_SANDBOX_POSTURE,
    }
    for key, expected in expected_values.items():
        actual = attestation.get(key)
        if type(expected) is bool:
            if type(actual) is not bool or actual is not expected:
                errors.append(f"attestation {key} expected strict bool {expected!r}, got {actual!r}")
        elif actual != expected:
            errors.append(f"attestation {key} expected {expected!r}, got {actual!r}")

    adoption_value = attestation.get("passed_adoption_gate")
    if type(adoption_value) is not bool or adoption_value is not True:
        errors.append(
            f"attestation passed_adoption_gate expected strict bool True, got {adoption_value!r}"
        )

    timestamp = attestation.get("attested_at")
    if not isinstance(timestamp, str) or not timestamp.endswith("Z"):
        errors.append("attestation attested_at must be an RFC3339 UTC timestamp ending in Z")
    else:
        try:
            _dt.datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        except ValueError:
            errors.append("attestation attested_at is not a valid RFC3339 timestamp")

    docker_digest = attestation.get("docker_image_digest")
    if not isinstance(docker_digest, str) or "@sha256:" not in docker_digest:
        errors.append("attestation docker_image_digest must be an image repo digest")
    elif docker_digest not in allowed_digests:
        errors.append("attestation docker_image_digest is not in the approved allowlist")

    if attestation.get("docker_digest_allowlist_path") != str(digest_allowlist_path):
        errors.append("attestation docker_digest_allowlist_path does not match verifier allowlist path")

    for artifact_path, key in (
        (candidate_path, "candidate_sha256"),
        (report_path, "fitness_report_sha256"),
    ):
        if not artifact_path.exists():
            errors.append(f"missing attested artifact: {artifact_path}")
            continue
        actual = _sha256_file(artifact_path)
        if attestation.get(key) != actual:
            errors.append(f"attestation {key} mismatch for {artifact_path}")

    if candidate_path.exists():
        actual_candidate_hash = _sha256_file(candidate_path)
        if attestation.get("fitness_report_candidate_hash") != actual_candidate_hash:
            errors.append("attestation fitness_report_candidate_hash does not match candidate artifact hash")
        report_candidate_hash = _extract_report_candidate_hash(report) if report else None
        if report_candidate_hash != actual_candidate_hash:
            errors.append("fitness report candidate_hash does not match candidate artifact hash")

    if report:
        report_gate = report.get("passed_adoption_gate")
        if type(report_gate) is not bool or report_gate is not True:
            errors.append("fitness report passed_adoption_gate must be strict bool true")

        for nested_key in ("fitness_report", "metrics"):
            nested = report.get(nested_key)
            if isinstance(nested, dict) and "passed_adoption_gate" in nested:
                nested_gate = nested.get("passed_adoption_gate")
                if type(nested_gate) is not bool or nested_gate is not True:
                    errors.append(f"fitness report {nested_key}.passed_adoption_gate must be strict bool true")

        report_image = report.get("sandbox_image")
        if report_image != attestation.get("docker_image"):
            errors.append("fitness report sandbox_image does not match attestation docker_image")

    for key, report_key in REPORT_TO_POSTURE_KEY.items():
        if report and report.get(report_key) != attestation.get(key):
            errors.append(f"fitness report {report_key} does not match attestation {key}")

    return errors


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Create or verify promotion attestation")
    subparsers = parser.add_subparsers(dest="command", required=True)

    write = subparsers.add_parser("write")
    write.add_argument("--candidate", required=True)
    write.add_argument("--report", required=True)
    write.add_argument("--out", required=True)
    write.add_argument("--evaluated-sha", required=True)
    write.add_argument("--base-main-sha", required=True)
    write.add_argument("--run-id", required=True)
    write.add_argument("--run-attempt", required=True)
    write.add_argument("--docker-image", required=True)
    write.add_argument("--docker-image-digest", required=True)
    write.add_argument("--digest-allowlist", required=True)

    verify = subparsers.add_parser("verify")
    verify.add_argument("--attestation", required=True)
    verify.add_argument("--candidate", required=True)
    verify.add_argument("--report", required=True)
    verify.add_argument("--expected-evaluated-sha", required=True)
    verify.add_argument("--expected-base-main-sha", required=True)
    verify.add_argument("--digest-allowlist", required=True)
    verify.add_argument("--json", action="store_true")

    args = parser.parse_args(argv)

    if args.command == "write":
        try:
            payload = build_attestation(
                candidate_path=Path(args.candidate),
                report_path=Path(args.report),
                evaluated_sha=args.evaluated_sha,
                base_main_sha=args.base_main_sha,
                run_id=args.run_id,
                run_attempt=args.run_attempt,
                docker_image=args.docker_image,
                docker_image_digest=args.docker_image_digest,
                digest_allowlist_path=Path(args.digest_allowlist),
            )
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 1
        _write_json(Path(args.out), payload)
        print(json.dumps({"success": True, "attestation": args.out}, indent=2))
        return 0

    errors = verify_attestation(
        attestation_path=Path(args.attestation),
        candidate_path=Path(args.candidate),
        report_path=Path(args.report),
        expected_evaluated_sha=args.expected_evaluated_sha,
        expected_base_main_sha=args.expected_base_main_sha,
        digest_allowlist_path=Path(args.digest_allowlist),
    )
    result = {"success": not errors, "errors": errors}
    if args.json:
        print(json.dumps(result, indent=2))
    elif errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
    else:
        print("Promotion attestation verified.")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
