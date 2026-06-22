# MicroPR Request Changes Template

Use this when a PR is missing required MicroPR evidence or the evidence is stale, incomplete, or tied to the wrong commit SHA.

## Request Changes Comment

```markdown
Request Changes.

Blocking reason:
- Missing or invalid MicroPR evidence.

Required evidence:
- `reports/ruff.txt`
- `reports/bandit.json`
- `pytest-junit.xml`
- `fitness_report.json` when required by the checklist
- GitHub Actions CI Run ID

Please update the PR with:
1. Links to the relevant GitHub Actions run.
2. Uploaded artifacts or artifact links.
3. A short note explaining whether `fitness_report.json` is required for this PR.
4. Confirmation that artifacts correspond to the current head commit SHA.

Reference:
`docs/review/MICROPR_ENFORCEMENT_CHECKLIST.md`
```

## Approve Comment

```markdown
Audit result: Approve.

MicroPR evidence reviewed:
- Ruff evidence present.
- Bandit evidence present.
- Pytest evidence present.
- `fitness_report.json` requirement checked.
- CI Run ID provided.
- Artifacts correspond to the reviewed commit SHA.

No blocking MicroPR evidence issues remain.
```
