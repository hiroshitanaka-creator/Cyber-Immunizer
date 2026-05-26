# 🧬 Project Cyber-Immunizer

> **現実世界のサイバー脅威の進化スピードに対し、人間のエンジニアによるパッチ開発の限界を突破する。**
> 不特定の脅威を自動検知し、自律的に防御コードを自己変異・適応させ続ける、世界初の「デジタル自律免疫システム」を確立する。

A safe, deterministic, testable foundation for an autonomous **defensive**-code evolution loop.

---

## ⚠️ Defensive-Only Scope

**This project is a defensive security research tool only.**

| ✅ In scope | ❌ Out of scope |
|---|---|
| Detector logic mutation | Offensive exploit generation |
| Local request simulation | Real traffic interception |
| Fitness-gated promotion | Live WAF deployment |
| Static test-case evaluation | Credential theft or persistence |
| AST policy enforcement | Evasion techniques |
| Deterministic regression testing | Destructive behavior |

**No live network calls, no real attack automation, no working exploit payloads.**
Test payloads are inert static strings used only to validate detector coverage.

---

## 🏗️ Architecture

The evolution loop follows four phases:

```
┌─────────────────────────────────────────────────────────────┐
│                  CYBER-IMMUNIZER LOOP                       │
│                                                             │
│  1. MONITOR / ANALYZE                                       │
│     intelligence/threat_feeds.py                           │
│     └── loads active_threats.json (safe stubs)             │
│                                                             │
│  2. PROPOSE (scripts/propose_mutation.py)                   │
│     └── LLM proposes a mutation_patch.json                  │
│         • Restricted prompt: defensive logic only           │
│         • Max 1 API call per run                            │
│         • No code execution here                            │
│                                                             │
│  3. EVALUATE (scripts/evaluate_candidate.py)                │
│     ├── scripts/apply_mutation.py → candidate file          │
│     ├── scripts/validate_mutation.py → AST policy check     │
│     └── core/fitness.py → subprocess evaluation            │
│         • Timeout enforced                                  │
│         • No secrets in subprocess                          │
│         • Adoption gate: regression + FP + score           │
│                                                             │
│  4. PROMOTE (scripts/promote_candidate.py)                  │
│     ├── copies candidate → core/detector.py                 │
│     ├── updates data/genome.json                            │
│     ├── appends to data/evolution_history.json              │
│     └── updates README status block                         │
└─────────────────────────────────────────────────────────────┘
```

---

## 📁 Project Structure

```
cyber-immunizer/
├── core/
│   ├── types.py            # Immutable dataclasses (Request, DetectionResult, …)
│   ├── detector.py         # Stable detector interface (mutation boundary here)
│   ├── fitness.py          # Deterministic fitness evaluation
│   └── test_attacker.py    # Local request simulator (NOT an attacker)
├── data/
│   ├── benign_requests.json
│   ├── attack_requests.json
│   ├── regression_cases.json
│   ├── active_threats.json
│   ├── genome.json          # Current generation metadata
│   └── evolution_history.json
├── intelligence/
│   └── threat_feeds.py     # Safe threat record stubs
├── scripts/
│   ├── validate_mutation.py # AST policy enforcement
│   ├── apply_mutation.py    # Patch application
│   ├── evaluate_candidate.py# Subprocess evaluation
│   ├── promote_candidate.py # Promotion gate
│   ├── propose_mutation.py  # LLM stub / offline sample
│   └── update_readme.py     # README status updater
├── tests/                   # pytest test suite
└── .github/workflows/
    └── immunization_loop.yml
```

---

## 🚀 Local Commands

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run full test suite
python -m pytest

# Validate the baseline detector
python scripts/validate_mutation.py --candidate core/detector.py --json

# Evaluate baseline fitness
python -m core.fitness --candidate core/detector.py --baseline --json

# Propose a local sample mutation (no API key required)
python scripts/propose_mutation.py --offline-sample --json

# Apply the proposed patch
python scripts/apply_mutation.py \
    --patch .cyber_immunizer/mutation_patch.json \
    --base core/detector.py \
    --out .cyber_immunizer/candidate_detector.py \
    --json

# Evaluate the candidate in a subprocess
python scripts/evaluate_candidate.py \
    --candidate .cyber_immunizer/candidate_detector.py \
    --timeout 5 \
    --json

# Update the README status block
python scripts/update_readme.py
```

---

## 🔬 How Mutation Patches Work

1. A `mutation_patch.json` is produced by `scripts/propose_mutation.py`.
2. The patch's `replacement_code` field contains **only** the body of `inspect_request()`.
3. `scripts/apply_mutation.py` replaces only the code between:
   ```python
   # === MUTATION_START ===
   # === MUTATION_END ===
   ```
4. `scripts/validate_mutation.py` runs a strict AST policy check:
   - No `import os`, `subprocess`, `socket`, `pathlib`, `sys`, …
   - No `eval()`, `exec()`, `open()`, `globals()`, `locals()`, …
   - No dunder access (`__class__`, `__dict__`, `__globals__`, …)
   - Signature of `inspect_request(request: Request) -> DetectionResult` must be preserved
5. If validation passes, `scripts/evaluate_candidate.py` runs `core.fitness` in a **separate subprocess** with a timeout.
6. Only if the adoption gate passes (no regressions, FP ≤ 5%, score improved) does `scripts/promote_candidate.py` copy the candidate to `core/detector.py`.

---

## 🛡️ Why Generated Code Is Not Trusted

- LLM output is treated as untrusted input, not executable code.
- Candidate code is never `exec()`'d or `eval()`'d.
- Candidate code runs in a subprocess with no secrets and no write permissions.
- AST validation rejects entire categories of dangerous patterns before execution.
- False rejection (over-conservative) is preferred to false acceptance.
- The `promote` GitHub Actions job has write permissions but **no model API secrets**.
- The `evaluate` GitHub Actions job has model-generated code but **no write permissions**.

---

## ⚙️ GitHub Actions

The workflow (`.github/workflows/immunization_loop.yml`) has three separated jobs:

| Job | Permissions | Secrets | Executes generated code? |
|---|---|---|---|
| `propose` | `contents: read` | GEMINI_API_KEY (optional) | ❌ No |
| `evaluate` | `contents: read` | None | ✅ Yes (in subprocess, sandboxed) |
| `promote` | `contents: write` | None | ❌ No |

---

## ⚠️ Not Production WAF Software

This is an **MVP research scaffold**.  It does not:
- Intercept real HTTP traffic
- Deploy to any WAF or reverse proxy
- Make live network calls during tests
- Provide production-grade security guarantees

Always review promoted detector changes before deploying to any real environment.

---

<!-- CYBER_IMMUNIZER_STATUS_START -->
## 🧬 Cyber-Immunizer Status

| Field | Value |
|---|---|
| Generation | 1 |
| Best Score | 383.67051093329087 |
| Detector Hash | `cbd6bdee7f8f4c19…` |
| Last Updated | 2026-05-26T01:09:22.856943Z |
| Total Test Cases | 15 |
| TP / FP / TN / FN | 8 / 0 / 7 / 0 |
| Adoption Gate | ✅ Passed (generation 1) |
| Active Threat IDs | `THREAT-2024-001` `THREAT-2024-002` `THREAT-2024-003` `THREAT-2024-004` `THREAT-2024-005` |
| Status Block Updated | 2026-05-26 01:09 UTC |

<!-- CYBER_IMMUNIZER_STATUS_END -->
