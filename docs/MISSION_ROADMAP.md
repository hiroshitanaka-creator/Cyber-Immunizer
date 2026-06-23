<!--
AI_DOC_META
status: ROADMAP (Owner-directed)
scope: Mission-level sequencing toward the digital autonomous immune system.
authority: Owner-intent / planning record. Sequences executable work; does NOT
  change runtime state or current-state SSOT. Each phase names concrete steps.
do_not_use_for:
  - claiming any phase is complete without the stated done-criteria evidence
  - executing paid-credit / workflow_dispatch / threat-feed enablement without Owner approval
AI_DOC_META_END
-->

# Mission Roadmap — Digital Autonomous Immune System

## Mission (verbatim, from the repository purpose)

> 現実世界のサイバー脅威の進化スピードに対し、人間のエンジニアによるパッチ開発の限界を突破する。
> 不特定の脅威を自動検知し、自律的に防御コードを自己変異・適応させ続ける、
> 世界初の「デジタル自律免疫システム」を確立する。

Gloss: out-pace human patching against fast-evolving threats; detect unknown
threats; continuously self-mutate and adapt defensive code; a living autonomous
immune system.

## Three pillars

- **P-A — Autonomous self-mutation of defense code**: the LLM proposes defensive
  code/rule changes; the system safely validates and adopts them without a human
  writing the patch.
- **P-B — Unknown-threat detection**: detection generalizes to threats not
  hand-authored into the corpus (the "不特定の脅威" requirement).
- **P-C — Continuous self-operation**: the loop runs on a cadence, beyond human
  patch speed, with safety/budget governance.

## Honest current-state assessment

| Pillar | State | Evidence |
|---|---|---|
| P-A self-mutation | **Engine exists & hardened**, but each live run is human-triggered, and the committed realistic ruleset is **human-authored** (a baseline, not self-evolved). | propose→apply→evaluate→promote; structured path (gate-1, R3); `tests/test_realistic_ruleset.py` |
| P-B unknown threats | **Static & limited.** Threats are static fixtures; NVD/CVE intake permanently disabled (L1-F16). "Unknown" is only approximated by holdout/drift/counterfactual generalization tiers. | `data/active_threats.json`, `intelligence/threat_feeds.py` (disabled stub), adaptive floors |
| P-C continuous | **Not autonomous yet (by safety design).** Scheduled runs are hard-coded `noop`; live/paid runs are manual `workflow_dispatch` only. | `.github/workflows/immunization_loop.yml` |

**Summary**: the immune system's organs (a safety-governed self-mutation engine)
are built and proven to produce real detection, but it is not yet *living* —
self-running, adapting to genuinely new threats. That is the mission's heart and
the hard part.

## Roadmap (sequenced; each phase is executable)

### M0 — Foundation (DONE)
Safe self-mutation engine, structured detector path, R3 promotion path, and
committed realistic detection (100% / 0% FP on a realistic corpus). Evidence:
PRs #171–#173, `docs/value_validation/REALISTIC_DETECTION_RESULTS.md`.

### M1 — Autonomous structured evolution wiring (P-A) ← recommended next
- **Goal**: one trigger → LLM proposes a structured ruleset → evaluate against
  the realistic + adaptive corpora → auto-promote (R3) on gate pass. No human
  authors the rule.
- **Steps**: add a workflow mode that runs `propose_mutation.py --structured-rules
  --gemini-paid-credit`; wire evaluate (`--corpus-dir`) and auto-promote
  (`promote_structured_candidate --owner-approved`) on success; add an
  offline/preflight dry-run path.
- **No-API now**: build the wiring + an offline dry-run (`--structured-rules
  --offline-sample` end-to-end) + tests. **Owner-gated**: the paid run itself
  (the Owner-authorized ≤10/hr free-tier budget is the lever).
- **Done**: an offline dry-run promotes an offline-proposed ruleset end-to-end in
  CI logic; a single owner-approved paid run self-evolves and auto-promotes a
  structured ruleset that beats the gate.

### M2 — Continuous self-operation (P-C)
- **Goal**: move from one-shot manual dispatch to an owner-approved cadence with
  circuit breakers (budget gate, fp-rate guard, auto-rollback on regression).
- **Steps**: a guarded periodic/owner-approved run mode; per-run rollback hooks
  (`detector_mode` reset already supports instant rollback); budget/halt logic.
- **Owner-gated**: cadence + budget. **No-API now**: the guards, rollback, and
  halt logic + tests.
- **Done**: the loop can run repeatedly under budget without manual steps between
  runs, and auto-halts/rolls back on a bad candidate.

### M3 — Unknown-threat intake (P-B) ← the research-hard frontier
- **Goal**: stop relying on static hand-authored threats; feed evolving / unseen
  threat targets so the detector adapts to "不特定の脅威".
- **Options (within the safety line — defensive signatures/metadata only, no
  weaponized exploits)**:
  1. Owner-supplied evolving threat corpora (external, rotated over time).
  2. Defensive threat-feed integration (e.g., CVE/CWE *metadata* and pattern
     classes, not exploit payloads) — requires revisiting the L1-F16 disable
     decision (Owner call).
  3. Strengthen generalization measurement: expand holdout/drift/counterfactual
     with categories deliberately withheld from proposal, to measure true
     generalization to unseen patterns.
- **Honest limit**: genuine zero-day / never-seen-before detection is an open
  research problem. This project can target **measurable generalization to
  withheld threat classes**, not a guarantee of detecting all unknowns. Claims
  must stay bounded to measured generalization.
- **Done**: detection measured on threat classes withheld from the proposal
  inputs, with reported generalization rates (not just memorized corpus).

### M4 — Closed adaptive loop / memory (P-A × P-B)
- **Goal**: each generation's evidence (`evolution_history.json`, fitness,
  drift signals) informs the next proposal, so the system adapts over time.
- **Steps**: feed prior results + drift into the proposal prompt; optionally
  integrate the planning-only `docs/ADAPTIVE_SECURITY_GAME_MODEL.md` (currently
  not implemented) as the adaptation objective.
- **Done**: measurable generation-over-generation improvement on a *moving*
  threat distribution (not a fixed corpus).

### M5 — External value / distribution (after Layer 2 accepted)
Scan CLI / packaging / CI templates — blueprint step 3, only after value
validation is accepted. Not a near-term goal.

## Owner-gate summary

| Phase | Needs Owner approval for |
|---|---|
| M1 | the paid-credit run (wiring + dry-run need none) |
| M2 | run cadence + budget |
| M3 | threat-feed enablement (L1-F16 revisit) / external corpora policy |
| M4 | paid-credit runs over time |
| M5 | externalization (post Layer 2) |

## What "mission achieved" means (measurable, per pillar)

- **P-A**: a defense rule that **no human authored** is proposed by the LLM,
  passes the safety + adoption gate, and is auto-promoted to the active detector.
- **P-B**: the active detector blocks threat classes **withheld** from its
  proposal inputs, with a reported generalization rate.
- **P-C**: the loop runs on a cadence under budget, auto-rolling back regressions,
  without a human writing or selecting the patch.

Until all three hold on a *moving* threat distribution, the mission is "in
progress", and status claims must say so.

## Safety (unchanged)

Defensive only. Commit defensive detection signatures and standard test patterns;
never weaponized exploits, multi-stage chains, bypass/evasion guidance, attack
tooling, or live-traffic capture. Paid-credit / `live_model` / `workflow_dispatch`
/ threat-feed enablement only with explicit Project Owner approval.
