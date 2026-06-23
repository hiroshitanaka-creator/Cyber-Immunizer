<!--
AI_DOC_META
status: ROADMAP (Owner-directed, mission-first)
scope: Mission-level sequencing toward the world's first digital autonomous immune system.
authority: Owner-intent / vision record. Holds the FULL mission as the target.
  Current-state facts are accurate; the goal is never scaled down.
  Sequences executable work; does NOT change runtime state or current-state SSOT.
do_not_use_for:
  - watering down the mission, or reframing it as permanently "in progress"
  - claiming a phase is done without its evidence
  - executing paid-credit / workflow_dispatch / threat-feed enablement without Owner approval
AI_DOC_META_END
-->

# Mission Roadmap — The World's First Digital Autonomous Immune System

## The mission (the only target)

> 現実世界のサイバー脅威の進化スピードに対し、人間のエンジニアによるパッチ開発の限界を突破する。
> 不特定の脅威を自動検知し、自律的に防御コードを自己変異・適応させ続ける、
> 世界初の「デジタル自律免疫システム」を確立する。

This is the goal in full. We build **toward this, not toward a smaller version of
it.** Threats evolve faster than humans can patch; this system is designed to
out-evolve them — detecting the unknown, rewriting its own defenses, and adapting
continuously. As AI models grow more capable, **the same safe loop produces
stronger defenses automatically.** Safety governance here is not a brake — it is
the seatbelt that lets us drive fast. We will not trade away the ambitious future;
we will reach it without losing control.

## Three pillars (all achievable, all targeted in full)

- **P-A — Autonomous self-mutation of defense code**: the LLM writes and rewrites
  the defense; no human authors the patch.
- **P-B — Unknown-threat detection**: the system detects threats nobody wrote into
  it — the "不特定の脅威" — by generalizing and co-evolving against a moving threat
  frontier.
- **P-C — Continuous self-operation**: the loop runs and adapts on its own,
  faster than human patch cycles, governed so it can run boldly and safely.

## Where we are now (facts, not a ceiling)

This is the launch point, not the limit.

| Pillar | Built | Still to break through |
|---|---|---|
| P-A | Full safe self-mutation engine (propose→apply→evaluate→promote), structured-rule path, R3 auto-promotion, proven real detection. | Make the LLM — not a human — the author of the promoted defense, on every cycle. |
| P-B | Generalization tiers (holdout/drift/counterfactual) and a realistic corpus. | Feed a moving, partly-unknown threat frontier and detect classes withheld from the system. |
| P-C | A loop workflow with full safety/budget governance and instant rollback. | Let it run on a cadence and adapt without a human in the inner loop. |

The organs are built and proven. **Now we make it live.**

## Roadmap — each phase is a real breakthrough, executable and safe

### M0 — Foundation (DONE)
Safe self-mutation engine, structured detector path, R3 promotion, and committed
**real** detection (100% / 0% FP on a realistic corpus). Evidence: PRs #171–#173,
`docs/value_validation/REALISTIC_DETECTION_RESULTS.md`.

### M1 — The loop authors its own defense (P-A) ← next
One trigger → the LLM proposes a structured defense → it is evaluated against
real + generalization corpora → it is **auto-promoted** when it beats the gate.
No human writes or picks the rule. We build the full wiring and an offline
dry-run now (no API); the Owner fires the live run (the authorized free-tier
budget is the ignition). **Done when**: an LLM-authored defense the Owner never
wrote is auto-promoted to the active detector.

### M2 — It runs itself (P-C)
The loop runs on an Owner-approved cadence, under budget, with automatic
rollback on any regression (`detector_mode` reset gives instant, lossless
revert). We build the guards/rollback/halt now; the Owner sets the cadence and
budget. **Done when**: successive cycles improve the defense with no human between
runs, and a bad candidate is auto-reverted.

### M3 — It detects the unknown (P-B)
We move off static hand-authored threats and put the system against a **moving,
partly-unknown threat frontier**: rotating/external threat corpora, a defensive
threat-feed (threat *intelligence* — pattern classes and CVE/CWE metadata, never
weaponized exploits; revisits the L1-F16 decision with Owner approval), and
deliberately **withheld** threat classes to prove the system catches what it was
never shown. We measure generalization not to cap the goal, but to **prove we are
closing the gap to full unknown-threat detection** — and we keep pushing until it
closes. **Done when**: the active detector blocks threat classes withheld from its
inputs, and that rate climbs over time.

### M4 — It remembers and co-evolves (P-A × P-B)
Each generation's evidence (fitness, drift, prior wins/losses) feeds the next
proposal, so the system adapts to a threat distribution that moves against it —
a true attacker/defender co-evolution (the
`docs/ADAPTIVE_SECURITY_GAME_MODEL.md` objective, brought to life). **Done when**:
measurable generation-over-generation gains on a moving threat distribution.

### M5 — It defends the world (externalization)
Once value is validated and accepted, the engine ships: scan tooling, packaging,
CI integration — real defense in others' hands. This is the point of the whole
system, sequenced after the value gate so what we ship is genuinely strong.

## How AI's own progress accelerates this

Every pillar gets **stronger for free as models improve**: a better proposer
(M1/M4) writes better defenses; better reasoning (M3) generalizes to more unknown
classes. The safe loop is model-agnostic, so upgrading the model upgrades the
immune system. We are explicitly building for that future — not foreclosing it.

## Owner-gate summary (governance that enables bold operation)

| Phase | Owner approves |
|---|---|
| M1 | the live paid-credit run (wiring + dry-run need none) |
| M2 | run cadence + budget |
| M3 | threat-feed / external-corpora enablement (L1-F16 revisit) |
| M4 | ongoing paid-credit operation |
| M5 | externalization (post value gate) |

These gates are how we run hard **and** safe — defensive only (detection
signatures and standard test patterns, never weaponized exploits, multi-stage
chains, bypass/evasion guidance, attack tooling, or live-traffic capture).

## Mission status discipline

We state current state accurately (done vs not) **and** we keep the full mission
as the standing target. "Not yet" is a build instruction, never a lowered goal.
The mission is achieved when, on a moving threat frontier: the LLM authors the
promoted defense (P-A), the system catches threats withheld from it (P-B), and it
runs and adapts continuously under governance (P-C). We are building straight at
that — and the next executable step is M1.
