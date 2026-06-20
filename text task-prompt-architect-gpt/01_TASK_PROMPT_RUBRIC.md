# 01_TASK_PROMPT_RUBRIC.md

# Task Prompt Quality Rubric

## 0. Purpose

この文書は、Codex / Claude / GPT Agent / その他AI実行者に渡すタスクプロンプトの品質を評価するための基準です。

目的は、見栄えのよい文章を作ることではありません。  
目的は、実行者が誤解せず、勝手にスコープを拡張せず、監査者が合否判定できるタスクプロンプトを作ることです。

高品質なタスクプロンプトは、以下を満たします。

- 目的が明確である
- 対象が明確である
- 変更範囲が明確である
- 禁止事項が明確である
- 検証方法が明確である
- 証跡要求が明確である
- 完了条件が客観的である
- 停止条件が明確である
- 実行者の勝手な判断を抑制できる
- 第三者が監査できる

---

## 1. Core Principle

良いタスクプロンプトとは、AIを励ます文章ではありません。  
良いタスクプロンプトとは、成果物の合否を判定できる作業契約です。

そのため、以下を必ず区別します。

| 種別 | 内容 |
|---|---|
| Goal | 最終的に達成したい状態 |
| Task | 実行者が行う具体作業 |
| Scope | 変更してよい範囲 |
| Constraint | 守るべき制約 |
| Validation | 成功を確認する方法 |
| Evidence | 成功を証明する材料 |
| Stop Condition | 作業を止める条件 |
| Definition of Done | 完了と認める条件 |

---

## 2. Mandatory Gates

以下のいずれかが欠けているタスクプロンプトは、不完全です。

### Gate 1: Target Clarity

タスク対象が明確であること。

必須項目:

- Repository URL
- Branch
- Base branch
- PR URL, if applicable
- Issue URL, if applicable
- Relevant files
- Out-of-scope files
- Expected deliverable

不明な場合は、以下のように書くこと。

```text
UNKNOWN — verify before editing.
```

不明な項目を、実行者に推測させてはいけません。

---

### Gate 2: Mission Clarity

目的が明確であること。

悪い例:

```text
この辺をいい感じに直してください。
```

良い例:

```text
このタスクの目的は、candidate evaluationで使用されるDocker imageをdigest-pinned形式に固定し、評価環境の再現性を高めることです。タグ参照のままでは将来同じ評価が同じimageで再現される保証がないため、CI、runtime constants、tests、docsを一貫して更新してください。
```

---

### Gate 3: Scope Control

変更してよい範囲と、変更してはいけない範囲が明確であること。

必須項目:

- Allowed files
- Forbidden files
- Allowed behavior changes
- Forbidden behavior changes
- Allowed dependency changes
- Forbidden dependency changes
- Allowed workflow changes
- Forbidden workflow changes

---

### Gate 4: Non-Negotiable Rules

実行者が絶対に破ってはいけない規則を明示すること。

最低限含めるべき規則:

- Do not make unrelated refactors.
- Do not weaken security checks.
- Do not remove tests to make CI pass.
- Do not bypass failing validations.
- Do not silently change public behavior.
- Do not introduce network calls unless explicitly allowed.
- Do not add dependencies unless explicitly allowed.
- Do not touch secrets, credentials, tokens, or API keys.
- Do not claim success without command output.
- Do not hide unresolved risks.

---

### Gate 5: Validation Requirements

成功確認のための検証が明確であること。

検証例:

- Unit tests
- Integration tests
- Regression tests
- Smoke tests
- Negative tests
- Snapshot tests
- Type check
- Lint
- Format check
- JSON schema validation
- YAML parse validation
- Docker-based evaluation
- CI status check
- Security boundary check
- Manual diff inspection

検証は、単に「テストしてください」では不十分です。  
以下を明示します。

- 実行するコマンド
- 成功条件
- 失敗時の扱い
- 実行不能時の報告方法

---

### Gate 6: Evidence Requirements

最終報告に必要な証跡を明示すること。

最低限必要な証跡:

- Changed files
- Git diff summary
- Exact commands run
- Command outputs or summaries
- Test results
- CI status, if available
- Relevant file paths
- Relevant line references, if applicable
- Before / after behavior
- Remaining risks
- Confirmation that forbidden files were not changed

---

### Gate 7: Stop Conditions

実行者が勝手に前進してはいけない条件を明示すること。

代表的なStop Conditions:

- Target branch cannot be verified
- Required file is missing
- Required artifact is unavailable
- Security boundary is unclear
- Required tests cannot be run
- CI cannot be checked
- Fix requires editing forbidden files
- Existing implementation contradicts task assumptions
- The task would require secrets or credentials
- The task would require unsafe or unauthorized behavior

Stopした場合は、以下を報告させます。

- どこまで確認したか
- 何が不明か
- どの条件で止まったか
- 次に必要な人間判断
- 勝手に進めなかった理由

---

### Gate 8: Definition of Done

完了条件がチェックリスト化されていること。

良い形式:

```markdown
The task is complete only if:

- [ ] Required files were inspected.
- [ ] Implementation was changed only within allowed scope.
- [ ] Security boundary was not weakened.
- [ ] Required tests were added or updated.
- [ ] Required commands passed.
- [ ] CI status was checked or inability to check was documented.
- [ ] Documentation was updated where required.
- [ ] Final report includes evidence.
- [ ] Remaining risks are documented.
```

---

## 3. Scoring Rubric

タスクプロンプトを100点満点で評価します。

| Category | Points | Criteria |
|---|---:|---|
| Mission and Context | 10 | 目的、背景、現状課題が明確 |
| Target Specificity | 10 | repo、branch、PR、対象ファイルが明確 |
| Scope Control | 15 | Allowed / Forbiddenが明確 |
| Non-Negotiable Rules | 10 | 禁止事項が十分 |
| Required Work | 15 | 実行作業が分解されている |
| Validation | 15 | テスト・CI・検証が具体的 |
| Evidence | 10 | 最終報告の証跡要求が明確 |
| Stop Conditions | 10 | 止まる条件が明確 |
| Final Report Contract | 5 | 報告形式が固定されている |

### Score Interpretation

| Score | Judgment | Meaning |
|---:|---|---|
| 95-100 | Excellent | 高リスクrepo作業に投入可能 |
| 85-94 | Good | 実用可能だが軽微な改善余地あり |
| 70-84 | Risky | 実行者の解釈余地が残る |
| 50-69 | Poor | スコープ逸脱や検証漏れが起きやすい |
| 0-49 | Reject | タスクプロンプトとして不適格 |

---

## 4. Required Prompt Anatomy

高品質タスクプロンプトは、原則として以下の構造を持ちます。

```markdown
# Task Title

## 0. Mission
## 1. Target
## 2. Current Facts
## 3. Non-Negotiable Rules
## 4. Required Reconnaissance
## 5. Required Work
## 6. Allowed Changes
## 7. Forbidden Changes
## 8. Validation Requirements
## 9. Evidence Requirements
## 10. Definition of Done
## 11. Stop Conditions
## 12. Final Report Format
## 13. Self-Audit Before Final Answer
```

---

## 5. Common Failure Modes

タスクプロンプト作成時に避けるべき失敗です。

### Failure Mode 1: Goal and Method Confusion

悪い例:

```text
テストを増やしてください。
```

問題点:

- なぜテストを増やすのか不明
- どのリスクを潰すのか不明
- 成功条件が不明

改善例:

```text
目的は、candidate promotionがevaluate artifactの真正性を確認せずに進むリスクを潰すことです。そのため、promotion前にattestation manifestを検証するgateを追加し、artifact mismatch、missing attestation、wrong commit SHA、wrong workflow run IDを拒否するnegative testsを追加してください。
```

---

### Failure Mode 2: No Forbidden Scope

悪い例:

```text
必要に応じて修正してください。
```

問題点:

- 実行者が無関係なrefactorを行う
- workflowやpolicyを勝手に変更する
- テストを弱める可能性がある

改善例:

```text
Forbidden changes:
- Do not edit .github/workflows/**
- Do not modify security policy checks except the specified function.
- Do not remove or weaken existing tests.
- Do not change public CLI behavior except documented error messages.
```

---

### Failure Mode 3: Validation Is Vague

悪い例:

```text
テストを通してください。
```

改善例:

```text
Validation requirements:
- Run: python -m pytest tests/test_candidate_contract.py tests/test_evaluate_candidate.py
- Run: python -m pytest
- Run: git diff --check
- Parse updated YAML files if any workflow file is touched.
- If Docker is required but unavailable, report BLOCKED and include the exact error.
```

---

### Failure Mode 4: Evidence Is Missing

悪い例:

```text
完了したら報告してください。
```

改善例:

```text
Final report must include:
- changed files table
- exact commands run
- test result summary
- CI run URL or reason CI could not be checked
- before/after behavior
- unresolved risks
- confirmation that no forbidden files were modified
```

---

### Failure Mode 5: No Stop Conditions

悪い例:

```text
できるところまで進めてください。
```

問題点:

- 実行者が危険な仮定で進む
- 権限や安全境界を無視する
- 検証不能でも完了扱いにする

改善例:

```text
Stop conditions:
- Stop if required repository state cannot be verified.
- Stop if fix requires editing forbidden files.
- Stop if tests cannot be run and no equivalent validation exists.
- Stop if the implementation would require secrets, credentials, or external production access.
```

---

## 6. GitHub Repository Task Requirements

GitHubリポジトリ向けタスクでは、必ず以下を含めます。

### Mandatory Context

- Repository URL
- Target branch
- Base branch
- PR URL, if applicable
- Current commit SHA, if known
- Expected changed files
- Related issue, if any
- Existing failure or audit finding
- Desired end state

### Mandatory Verification

- Read README.md
- Read relevant docs
- Read relevant source files
- Read relevant tests
- Read relevant workflow files if CI/workflow behavior is affected
- Check PR diff if PR exists
- Check CI status if PR exists
- Check review comments if PR exists

### Mandatory Report

- What was inspected
- What was changed
- What was not changed
- What tests were run
- What CI says
- What risks remain
- Whether merge is recommended

---

## 7. PR Audit Prompt Requirements

PR監査用プロンプトでは、必ず以下を要求します。

- Do not audit the diff only.
- Verify PR claims against implementation.
- Read relevant base files.
- Check changed file list.
- Check CI status.
- Check review comments, including bot reviews.
- Evaluate architecture impact.
- Evaluate security boundary impact.
- Evaluate regression risk.
- Evaluate test adequacy.
- Evaluate documentation consistency.
- Produce severity-ranked findings.
- End with exactly one verdict:
  - APPROVE
  - REQUEST CHANGES
  - BLOCKED

### Finding Format

```markdown
### Finding P1: Title

- Severity: P0 / P1 / P2 / P3
- Status: Blocking / Non-blocking
- Evidence:
  - File:
  - Line:
  - Quote:
- Problem:
- Impact:
- Required fix:
- Verification:
```

---

## 8. Implementation Task Requirements

実装タスク用プロンプトでは、必ず以下を含めます。

- Exact implementation goal
- Existing behavior to preserve
- New behavior to add
- Error behavior
- Backward compatibility requirements
- Tests to add
- Tests to update
- Documentation to update
- Task report to create or update
- Allowed files
- Forbidden files
- Validation commands
- Stop conditions

### Implementation Anti-Patterns

禁止すべき行動:

- Broad cleanup
- Formatting-only churn
- Silent dependency upgrades
- Test deletion
- CI bypass
- Security weakening
- Catch-all exception swallowing
- Overbroad allowlist
- Hardcoded local paths
- Hidden network dependency
- Hidden time dependency
- Hidden randomness
- Non-deterministic tests

---

## 9. Documentation Task Requirements

ドキュメントタスクでは、必ず以下を含めます。

- Source of truth
- Documents to update
- Documents not to update
- Claims that require verification
- Terminology to use
- Terminology to avoid
- Consistency checks
- No unsupported roadmap promises
- No speculative capability claims

### Documentation Quality Rules

- Implementationと矛盾する記述は禁止
- 将来実装予定を既実装のように書くことは禁止
- Security boundaryを曖昧にすることは禁止
- CIや評価条件を実態より強く書くことは禁止
- 「完全」「絶対安全」「自律的に解決」などの過大表現は禁止

---

## 10. Security and Safety Boundary

サイバーセキュリティ関連タスクでは、以下を明示します。

### Allowed

- Defensive analysis
- Static analysis
- Test-case hardening
- Secure coding
- CI security checks
- Sandbox boundary validation
- Detection rule validation
- Regression tests
- Documentation of defensive constraints

### Forbidden

- Credential theft
- Secret extraction
- Malware generation
- Exploit deployment
- Unauthorized scanning
- Bypass of access controls
- Persistence mechanisms
- Evasion mechanisms for real-world misuse
- Instructions that enable harm outside an authorized test environment

### Required Framing

サイバー関連タスクは、常に以下の前提で書きます。

```text
This task is limited to defensive, authorized, repository-local development and validation. Do not perform or instruct real-world exploitation, unauthorized access, credential handling, or deployment against third-party systems.
```

---

## 11. Final Self-Audit Checklist

タスクプロンプトを出力する前に、必ず以下を確認します。

- [ ] Mission is clear.
- [ ] Target is clear.
- [ ] Assumptions are explicit.
- [ ] Allowed changes are explicit.
- [ ] Forbidden changes are explicit.
- [ ] Required work is decomposed.
- [ ] Validation is concrete.
- [ ] Evidence requirements are concrete.
- [ ] Stop conditions are present.
- [ ] Definition of Done is objective.
- [ ] Final report format is specified.
- [ ] Security boundary is preserved.
- [ ] The task does not encourage unsafe behavior.
- [ ] A reviewer can judge success or failure.

---

## 12. Minimum Acceptable Output

最低品質ラインは以下です。

```markdown
# Task Title

## Mission
Clear purpose.

## Target
Repo, branch, PR, files.

## Non-Negotiable Rules
Hard constraints.

## Required Work
Specific actions.

## Allowed Changes
Explicit paths.

## Forbidden Changes
Explicit paths.

## Validation
Commands and success criteria.

## Evidence
Required proof.

## Definition of Done
Checklist.

## Stop Conditions
When to stop.

## Final Report
Required format.
```

これを満たさない出力は、タスクプロンプトとして不合格です。
