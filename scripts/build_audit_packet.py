"""scripts/build_audit_packet.py — Evidence Collector for the machine audit gate.

Collects primary evidence about a PR (PR state, head SHA, changed files, CI
check runs, review threads) plus repository-local facts (frozen-path touches,
SSOT consistency) and normalizes everything into an Audit Packet
(`schemas/gpt_audit_packet.schema.json`).

Trust model — read this before editing:

* ``machine_facts`` are produced ONLY by this script, from the GitHub API /
  injected raw data and from repository files. An LLM never writes them.
* ``judgment_inputs`` are ALWAYS emitted as null skeletons. This script never
  fills a judgment claim, and it deliberately ignores any judgment data smuggled
  into the raw input. A claim only becomes effective when an auditor fills it
  AND its evidence report passes ``scripts/validate_audit_evidence.py`` at
  policy-engine evaluation time. This is what prevents an LLM's self-report
  from being laundered into machine evidence.

Usage:
    # From the GitHub API (requires GITHUB_TOKEN or GH_TOKEN):
    python scripts/build_audit_packet.py --github hiroshitanaka-creator/Cyber-Immunizer --pr 86

    # From injected raw data (tests / offline):
    python scripts/build_audit_packet.py --from-raw raw.json

Exit codes:
    0  Packet written
    2  Collection failed (missing token, API error, bad raw input) — fail closed

Standard library only.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

# Ensure project root is on sys.path when run as a script
_PROJECT_ROOT = Path(__file__).parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

_API_ROOT = "https://api.github.com"

# Default frozen prefixes mirror the CLAUDE.md file-access table.
DEFAULT_FROZEN_PREFIXES = ["core/", "scripts/", ".github/", "data/", "tests/"]

_SEVERITY_RE = re.compile(r"\bP([123])\b")
_EXCERPT_LEN = 200

PACKET_SCHEMA_VERSION = 1
GENERATOR_NAME = "scripts/build_audit_packet.py"


# ---------------------------------------------------------------------------
# GitHub API access (stdlib urllib; fail closed on any error)
# ---------------------------------------------------------------------------


class CollectionError(Exception):
    """Raised when primary evidence cannot be collected. Always fatal."""


def _token() -> str:
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if not token:
        raise CollectionError(
            "GITHUB_TOKEN / GH_TOKEN is not set — refusing to build a packet "
            "without primary evidence (fail closed)"
        )
    return token


def _request(url: str, token: str, payload: dict | None = None) -> dict | list:
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode() if payload is not None else None,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "cyber-immunizer-audit-packet",
        },
        method="POST" if payload is not None else "GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except (urllib.error.URLError, json.JSONDecodeError, TimeoutError) as exc:
        raise CollectionError(f"GitHub API request failed for {url}: {exc}") from exc


def _rest_paginated(path: str, token: str) -> list:
    items: list = []
    page = 1
    while True:
        sep = "&" if "?" in path else "?"
        batch = _request(f"{_API_ROOT}{path}{sep}per_page=100&page={page}", token)
        if not isinstance(batch, list):
            raise CollectionError(f"unexpected non-list response for {path}")
        items.extend(batch)
        if len(batch) < 100:
            return items
        page += 1


_THREADS_QUERY = """
query($owner: String!, $repo: String!, $pr: Int!, $cursor: String) {
  repository(owner: $owner, name: $repo) {
    pullRequest(number: $pr) {
      reviewThreads(first: 100, after: $cursor) {
        pageInfo { hasNextPage endCursor }
        nodes {
          isResolved
          isOutdated
          comments(first: 1) { nodes { body } }
        }
      }
    }
  }
}
"""


def fetch_raw_from_github(owner: str, repo: str, pr_number: int) -> dict:
    """Fetch the raw inputs for one PR. Network access; fail closed on error."""
    token = _token()
    pr = _request(f"{_API_ROOT}/repos/{owner}/{repo}/pulls/{pr_number}", token)
    if not isinstance(pr, dict) or "head" not in pr:
        raise CollectionError(f"unexpected PR response for #{pr_number}")
    files = _rest_paginated(f"/repos/{owner}/{repo}/pulls/{pr_number}/files", token)
    head_sha = pr["head"]["sha"]
    check_resp = _request(
        f"{_API_ROOT}/repos/{owner}/{repo}/commits/{head_sha}/check-runs", token
    )
    check_runs = check_resp.get("check_runs", []) if isinstance(check_resp, dict) else []

    threads: list[dict] = []
    cursor = None
    while True:
        data = _request(
            f"{_API_ROOT}/graphql",
            token,
            payload={
                "query": _THREADS_QUERY,
                "variables": {"owner": owner, "repo": repo, "pr": pr_number, "cursor": cursor},
            },
        )
        try:
            conn = data["data"]["repository"]["pullRequest"]["reviewThreads"]
        except (KeyError, TypeError) as exc:
            raise CollectionError(f"unexpected GraphQL response: {data}") from exc
        for node in conn["nodes"]:
            comments = node.get("comments", {}).get("nodes", [])
            threads.append(
                {
                    "is_resolved": bool(node["isResolved"]),
                    "is_outdated": bool(node["isOutdated"]),
                    "first_comment_body": comments[0]["body"] if comments else "",
                }
            )
        if not conn["pageInfo"]["hasNextPage"]:
            break
        cursor = conn["pageInfo"]["endCursor"]

    return {
        "pr": {
            "number": pr["number"],
            "state": pr["state"],
            "merged": bool(pr.get("merged", False)),
            "draft": bool(pr.get("draft", False)),
            "base_ref": pr["base"]["ref"],
            "base_sha": pr["base"]["sha"],
            "head_ref": pr["head"]["ref"],
            "head_sha": head_sha,
        },
        "files": [{"path": f["filename"], "status": f["status"]} for f in files],
        "check_runs": [
            {
                "name": c.get("name", ""),
                "status": c.get("status", ""),
                "conclusion": c.get("conclusion"),
            }
            for c in check_runs
        ],
        "review_threads": threads,
    }


# ---------------------------------------------------------------------------
# Normalization (pure functions; unit-testable without network)
# ---------------------------------------------------------------------------


def classify_ci(check_runs: list[dict]) -> str:
    """Classify CI for a head SHA from its check runs (conservative)."""
    if not check_runs:
        return "NOT_TRIGGERED"
    conclusions = []
    for run in check_runs:
        if run.get("status") != "completed":
            return "PENDING"
        conclusions.append(run.get("conclusion"))
    if any(c in ("failure", "cancelled", "timed_out", "action_required") for c in conclusions):
        return "FAILURE"
    if all(c in ("success", "neutral", "skipped") for c in conclusions):
        return "SUCCESS"
    return "FAILURE"  # unknown conclusion — fail closed


def severity_tokens(body: str) -> list[str]:
    return sorted({f"P{m}" for m in _SEVERITY_RE.findall(body or "")})


def normalize_threads(raw_threads: list[dict]) -> dict:
    threads = []
    unresolved = 0
    unresolved_p1_p2 = 0
    for t in raw_threads:
        tokens = severity_tokens(t.get("first_comment_body", ""))
        is_resolved = bool(t.get("is_resolved", False))
        is_outdated = bool(t.get("is_outdated", False))
        if not is_resolved and not is_outdated:
            unresolved += 1
            if "P1" in tokens or "P2" in tokens:
                unresolved_p1_p2 += 1
        threads.append(
            {
                "is_resolved": is_resolved,
                "is_outdated": is_outdated,
                "severity_tokens": tokens,
                "first_comment_excerpt": (t.get("first_comment_body") or "")[:_EXCERPT_LEN],
            }
        )
    return {
        "total": len(threads),
        "unresolved": unresolved,
        "unresolved_p1_p2": unresolved_p1_p2,
        "threads": threads,
    }


def frozen_touches(changed_paths: list[str], frozen_prefixes: list[str]) -> list[str]:
    return sorted(
        p for p in changed_paths if any(p.startswith(pfx) for pfx in frozen_prefixes)
    )


def collect_ssot(root: Path) -> dict:
    """SSOT facts: state_id from data/project_state.json must appear verbatim
    in docs/PROJECT_STATE.md. Missing files mean inconsistent (fail closed)."""
    state_json = root / "data" / "project_state.json"
    state_md = root / "docs" / "PROJECT_STATE.md"
    state_id: str | None = None
    promote_approved: bool | None = None
    in_md = False
    try:
        state = json.loads(state_json.read_text(encoding="utf-8"))
        state_id = state.get("state_id")
        promote_approved = state.get("promotion", {}).get("promote_approved")
    except (OSError, json.JSONDecodeError):
        pass
    if state_id:
        try:
            in_md = state_id in state_md.read_text(encoding="utf-8")
        except OSError:
            in_md = False
    return {
        "state_id": state_id,
        "state_id_in_project_state_md": in_md,
        "promote_approved": promote_approved,
        "consistent": bool(state_id) and in_md and promote_approved is not None,
    }


def empty_judgment_inputs() -> dict:
    """Null skeleton. The collector NEVER fills these — see module docstring."""
    claim = {"claimed_by": None, "claim": None, "evidence_report": None}
    return {
        "task_conditions_met": dict(claim),
        "scope_semantics_ok": dict(claim),
        "code_findings_resolved": dict(claim),
    }


def build_packet(
    raw: dict,
    root: Path,
    frozen_prefixes: list[str] | None = None,
    source: str = "injected",
) -> dict:
    """Normalize raw inputs into an Audit Packet.

    Any ``judgment_inputs`` present in ``raw`` are ignored on purpose: judgment
    claims must never enter the packet through the collection path.
    """
    prefixes = frozen_prefixes if frozen_prefixes is not None else DEFAULT_FROZEN_PREFIXES
    try:
        pr_raw = raw["pr"]
        changed_files = [
            {"path": f["path"], "status": f["status"]} for f in raw.get("files", [])
        ]
        pr = {
            "number": int(pr_raw["number"]),
            "state": pr_raw["state"],
            "merged": bool(pr_raw["merged"]),
            "draft": bool(pr_raw["draft"]),
            "base_ref": pr_raw["base_ref"],
            "base_sha": pr_raw["base_sha"],
            "head_ref": pr_raw["head_ref"],
            "head_sha": pr_raw["head_sha"],
            "changed_files": changed_files,
        }
    except (KeyError, TypeError, ValueError) as exc:
        raise CollectionError(f"raw input is missing required PR fields: {exc}") from exc

    check_runs = [
        {
            "name": c.get("name", ""),
            "status": c.get("status", ""),
            "conclusion": c.get("conclusion"),
        }
        for c in raw.get("check_runs", [])
    ]
    return {
        "packet_schema_version": PACKET_SCHEMA_VERSION,
        "generated_by": GENERATOR_NAME,
        "source": source,
        "machine_facts": {
            "pr": pr,
            "ci": {
                "classification": classify_ci(check_runs),
                "head_sha": pr["head_sha"],
                "check_runs": check_runs,
            },
            "review_threads": normalize_threads(raw.get("review_threads", [])),
            "frozen_paths": {
                "frozen_prefixes": list(prefixes),
                "touched": frozen_touches([f["path"] for f in changed_files], prefixes),
            },
            "ssot": collect_ssot(root),
        },
        "judgment_inputs": empty_judgment_inputs(),
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Cyber-Immunizer audit packet builder")
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument("--github", metavar="OWNER/REPO", help="Collect from the GitHub API")
    src.add_argument("--from-raw", metavar="RAW_JSON", help="Build from injected raw inputs")
    parser.add_argument("--pr", type=int, help="PR number (required with --github)")
    parser.add_argument("--root", default=str(_PROJECT_ROOT), help="Repository root for SSOT facts")
    parser.add_argument("--out", default=None, help="Output file (default: stdout)")
    args = parser.parse_args(argv)

    try:
        if args.github:
            if args.pr is None:
                raise CollectionError("--pr is required with --github")
            if "/" not in args.github:
                raise CollectionError("--github expects OWNER/REPO")
            owner, repo = args.github.split("/", 1)
            raw = fetch_raw_from_github(owner, repo, args.pr)
            source = "github_api"
        else:
            raw = json.loads(Path(args.from_raw).read_text(encoding="utf-8"))
            source = "injected"
        packet = build_packet(raw, Path(args.root), source=source)
    except (CollectionError, OSError, json.JSONDecodeError) as exc:
        print(f"PACKET BUILD FAILED: {exc}", file=sys.stderr)
        return 2

    rendered = json.dumps(packet, indent=2, ensure_ascii=False)
    if args.out:
        Path(args.out).write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)
    return 0


if __name__ == "__main__":
    sys.exit(main())
