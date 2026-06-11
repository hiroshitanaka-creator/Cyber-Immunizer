# Project Operating System

<!--
AI_DOC_META
document_id: project_operating_system
risk_class: S3
status: proposed
authority_scope: governance_process
scope: Project-wide minimum operating model. Defines roles, authority, PR risk classes, merge rules, WIP limit, S4 isolation, and project completion state machine.
current_state_authority: data/project_state.json and docs/PROJECT_STATE.md remain authoritative for runtime/current-state interpretation
activation: not an AI entrypoint until CLAUDE.md / AGENTS.md / docs/AI_ENTRYPOINT.md are updated in a separate PR
owner_approval_required: true
use_for:
  - determining roles and authority boundaries
  - classifying PR risk (S0–S4)
  - applying merge and HOLD/REJECT rules
  - understanding WIP limit and One PR = One Purpose constraints
  - navigating the project completion state machine
do_not_use_for:
  - executing paid-credit API runs
  - overriding machine evidence (data/api_usage_ledger.json, data/genome.json)
  - overriding current-state SSOT in data/project_state.json or docs/PROJECT_STATE.md
related:
  - docs/PROJECT_STATE.md
  - data/project_state.json
  - docs/audit_gate/PR_AUDIT_PROTOCOL.md
  - docs/audit_gate/TASK_PROMPT_PROTOCOL.md
  - CLAUDE.md
AI_DOC_META_END
-->

## 目的

この文書は、Project Owner が制御可能な最小限の運営モデルを定義する。

本プロジェクトでは、AIは作業支援者であり、最終判断者ではない。  
Project Owner は詳細な実装内容をすべて理解することを前提にせず、以下を制御する。

- 作業範囲
- 変更対象
- リスク分類
- 停止条件
- 承認条件
- 完了状態

この文書の目的は、複雑なルールを増やすことではなく、少数の明確な原則でプロジェクトを完了まで進めることである。

---

## Authority and Activation

This document defines the project governance operating model.
It does not replace the current-state SSOT.

Current-state authority remains:

1. Machine evidence
2. `data/project_state.json`
3. `docs/PROJECT_STATE.md`
4. Derived summaries

The STATE 1–10 machine in this document tracks the rollout of the operating model.
It does not change the runtime project phase, `state_id`, paid-credit status, promotion status, or release status.

Until `CLAUDE.md`, `AGENTS.md`, and/or `docs/AI_ENTRYPOINT.md` are updated in a later dedicated PR, this document is not the active AI entrypoint.

---

## 1. Roles

### Project Owner

Project Owner は、プロジェクトの最終責任者である。

Project Owner の責任は以下とする。

- 作業の目的を決める
- 1回の作業範囲を承認する
- PRのリスククラスを確認する
- S3以上の変更を承認または保留する
- S4を通常作業から分離する
- 不明点がある場合に HOLD を選択する
- プロジェクト完了状態を判断する

Project Owner は、すべての実装詳細を読める必要はない。  
ただし、どの範囲が変更されたか、どのリスクに該当するか、承認してよい状態かを確認する責任を持つ。

### Implementation AI

Implementation AI は、作業を実行する支援者である。

Implementation AI に許可されることは以下とする。

- 指定された範囲内で変更案を作る
- 必要な説明を作る
- 変更理由を整理する
- 検証結果を報告する
- 不明点を発見した場合に停止する

Implementation AI に許可されないことは以下とする。

- 作業範囲を自己判断で広げる
- Project Owner の承認が必要な判断を代行する
- S4に該当する内容を通常作業に混ぜる
- 未確認の内容を確認済みとして扱う
- 根拠のない安全判断を行う

### Audit AI

Audit AI は、変更内容を検査する支援者である。

Audit AI の責任は以下とする。

- 変更範囲を確認する
- リスククラスの妥当性を確認する
- 主張に根拠があるか確認する
- 不足している証拠を指摘する
- HOLD または REJECT の理由を明確にする

Audit AI は、承認者ではない。  
Audit AI の判断は参考情報であり、最終判断は Project Owner が行う。

### Machine Gate

Machine Gate は、明確な条件に基づいて危険な変更を検出するための機械的な判定層である。

Machine Gate の役割は以下とする。

- 変更対象が許可範囲内か確認する
- 禁止対象が変更されていないか確認する
- PR本文に必要な情報があるか確認する
- リスククラスと変更範囲の矛盾を検出する
- S4相当の変更が通常作業に混入していないか検出する

Machine Gate は、設計判断や品質判断の最終責任を持たない。  
Machine Gate は、Project Owner が判断する前の最低限の安全確認を担当する。

---

## 2. Authority Model

### 基本原則

本プロジェクトでは、権限を以下のように分離する。

| 項目 | Project Owner | Implementation AI | Audit AI | Machine Gate |
|---|---:|---:|---:|---:|
| 作業目的の決定 | Yes | No | No | No |
| 変更案の作成 | No | Yes | No | No |
| 変更範囲の確認 | Yes | Yes | Yes | Yes |
| リスク指摘 | Yes | Yes | Yes | Yes |
| S3承認 | Yes | No | No | No |
| S4承認 | Yes | No | No | No |
| 最終マージ判断 | Yes | No | No | No |
| HOLD判断 | Yes | Yes | Yes | Yes |
| REJECT提案 | Yes | Yes | Yes | Yes |

### AIの権限

AIは以下を行ってよい。

- 作業案を作る
- 変更案を作る
- 監査観点を出す
- リスクを列挙する
- 不明点を報告する
- 停止を提案する

AIは以下を行ってはならない。

- Project Owner の承認を代行する
- 自己判断で作業範囲を広げる
- S3またはS4の承認を行う
- 「問題ない」とだけ述べて根拠を省略する
- 未確認事項を確認済みとして扱う
- 不明点がある状態で作業を続ける

### Project Ownerの権限

Project Owner は以下を決定する。

- 作業を開始してよいか
- PRをHOLDするか
- PRをREJECTするか
- S3を承認するか
- S4を通常作業から分離するか
- 現在の状態から次の状態へ進めるか

### 根拠の扱い

以下の表現は根拠として扱わない。

- 確認済み
- 問題ありません
- 安全です
- 見ました
- 影響はありません
- おそらく大丈夫です
- 失敗しないはずです

有効な根拠には、少なくとも以下を含める。

- 対象ファイル
- 対象箇所
- 該当する引用
- 確認方法
- 確認結果
- その根拠が判断に関係する理由

---

## 3. PR Risk Class

すべてのPRは、作成時点でリスククラスを明記する。

自己申告されたリスククラスと実際の変更範囲が矛盾する場合は、より高いリスククラスを採用する。

### S0: Cosmetic

S0は、意味や動作に影響しない軽微な修正である。

例:

- 誤字修正
- 表現の軽微な修正
- コメントの明確化
- 既存文書の読みやすさ改善

条件:

- 状態判断に影響しない
- 運営ルールに影響しない
- 高リスク領域に触れない
- Project Owner の特別承認を不要とする

### S1: Protocol / Documentation

S1は、運営方針や説明文書に関する変更である。

例:

- 運営方針の明文化
- Owner向け手順の整理
- PR作成時の説明項目の整理
- 過去方針の整理
- 作業方針の簡素化

条件:

- 実装本体に触れない
- 高リスク領域に触れない
- 1PR = 1目的を守る
- Project Owner が内容を読んで判断できる

### S2: Guard / Validation Logic

S2は、機械的な確認ロジックや検証用の補助要素に関する変更である。

例:

- 変更範囲の検出
- PR本文の必須項目確認
- リスククラスの矛盾検出
- 禁止対象の混入検出
- 監査用の構造化確認

条件:

- 対象範囲が明示されている
- 確認方法が説明されている
- 失敗条件が明確である
- S3またはS4に該当する内容を含まない

### S3: Repository Control Surface

S3は、リポジトリ全体の制御面に影響する変更である。

例:

- PRテンプレート
- エージェント向け入口文書
- プロジェクト状態の正本
- 変更許可範囲の定義
- 高リスク領域の分類

条件:

- Project Owner の明示承認が必要
- 変更理由が明確である
- 変更範囲が最小である
- S4を含まない
- 不明点がある場合はHOLDする

### S4: Critical Owner-Only Area

S4は、Project Owner の明示判断なしに扱ってはならない最重要領域である。

S4に該当するものは、通常の開発作業から分離する。  
S4は、他の変更と同じPRに混ぜてはならない。

条件:

- Project Owner の明示承認が必要
- 通常PRとは分離する
- 目的を単独で定義する
- 成功条件と停止条件を事前に定義する
- AIの判断のみで進めてはならない

### S4 Concrete Triggers

以下のいずれかを含むPR・作業・操作はS4として扱う。

| Category | S4 trigger |
|---|---|
| API / paid-credit | Gemini API呼び出し、paid-credit run、paid-credit rerun、API budget変更 |
| GitHub Actions | `workflow_dispatch`実行、manual run、workflow permission変更、`.github/workflows/**`変更 |
| Promotion / release | `promote_approved`変更、candidate promotion、release/tag作成、release artifact変更 |
| State / ledger | `data/api_usage_ledger.json`、`data/project_state.json`、promotion/release/API実行結果を記録するledger/state変更 |
| Core safety boundary | `core/**`のsandbox、AST policy、secret scan、replacement validation、candidate hash検証の緩和 |
| Model / budget | `live_model_enabled`、`api_mode`、model provider/name、fallback model、budget/cost cap変更 |
| Secrets / permissions | secrets、tokens、repository permission、workflow permission、environment protection変更 |

不明な場合はS4候補としてHOLDする。

---

## 4. WIP Limit = 1

本プロジェクトでは、仕掛中の作業を1つに制限する。

### ルール

- 同時に進めるPRは1つだけとする
- 新しいPRを作る前に、現在のPRを完了、保留、または破棄する
- S2以上のPRを並行させない
- S3以上のPRは、他の作業と同時に進めない
- S4は常に単独で扱う

### 理由

Project Owner が制御できる範囲を超えると、AIが作業範囲を拡大しやすくなる。  
複数のPRが並行すると、どの変更がどの問題を起こしたか追跡しにくくなる。  
WIPを1に制限することで、判断対象を常に1つに固定する。

### 例外

例外は原則として認めない。

どうしても例外が必要な場合は、Project Owner が以下を明示する。

- なぜ例外が必要か
- どのPRが主作業か
- どのPRが保留扱いか
- どの作業を先に完了させるか

---

## 5. One PR = One Purpose

すべてのPRは、1つの目的だけを持つ。

### 許可されるPR

以下のようなPRは許可される。

- 1つの文書を作成する
- 1つの方針を明文化する
- 1つの確認ロジックを追加する
- 1つのテンプレートを整理する
- 1つの問題を修正する

### 禁止されるPR

以下のようなPRは禁止する。

- 文書整理と実装変更を同時に行う
- 方針変更と高リスク領域変更を同時に行う
- 複数の目的をまとめて処理する
- ついでの修正を含める
- 作業中に目的を追加する

### 判断基準

PRの目的は、1文で説明できなければならない。

良い例:

> Owner向けの最小運営モデルを1文書として定義する。

悪い例:

> ルールを整理し、監査を改善し、次の開発も進める。

1文で説明できないPRは、分割する。

---

## 6. Merge Rules

### 共通マージ条件

すべてのPRは、以下を満たす必要がある。

- Risk Class が明記されている
- 目的が1つである
- 変更範囲が明記されている
- 触ってはいけない範囲が守られている
- 検証結果が記録されている
- 不明点が残っていない
- AIの根拠なき主張に依存していない

### S0のマージ条件

S0は、以下を満たせばマージ可能とする。

- 変更が軽微である
- 意味や運営方針に影響しない
- 高リスク領域に触れていない
- 変更対象が明確である

### S1のマージ条件

S1は、以下を満たせばマージ可能とする。

- 文書目的が1つである
- Project Owner が内容を読んで理解できる
- S2以上の変更を含まない
- S4を含まない
- 次の作業が明確である

### S2のマージ条件

S2は、以下を満たす必要がある。

- 何を確認するための変更か明確である
- 成功条件と失敗条件が明確である
- 誤検出時の扱いが明確である
- S3以上の変更を含まない
- Project Owner がHOLD条件を理解できる

### S3のマージ条件

S3は、以下を満たす必要がある。

- Project Owner の明示承認がある
- 変更範囲が最小である
- 他の目的を含まない
- S4を含まない
- 変更前後でOwnerの制御性が下がらない
- 不明点があればHOLDする

### S4のマージ条件

S4は、通常のPRと同じ扱いにしない。

S4は以下を満たす必要がある。

- 単独のPRである
- Project Owner が明示承認している
- 目的が明確である
- 停止条件が明確である
- 他の変更と混在していない
- AIの判断のみで進行していない

### HOLD条件

以下に該当する場合はHOLDする。

- リスククラスが不明
- 目的が複数ある
- 変更範囲が不明
- 禁止対象に触れている可能性がある
- 根拠が不足している
- AIの「確認済み」だけで判断している
- Project Owner が理解できないまま承認を求められている
- S3またはS4の可能性があるが明示されていない

### REJECT条件

以下に該当する場合はREJECTする。

- 指示された範囲外を変更している
- S4を通常作業に混ぜている
- Project Owner の承認が必要な判断をAIが代行している
- 根拠のない安全判断で進めている
- 作業目的が途中で変わっている
- 停止条件に該当したのに作業を継続している

---

## 7. S4 Isolation

### 原則

S4は、通常作業から完全に分離する。

S4に該当する内容は、S0からS3のPRに混ぜてはならない。  
S4は、Project Owner が明示的に許可した場合のみ扱う。

### S4の扱い

S4を扱う場合は、以下を必須とする。

- 単独の目的として扱う
- 事前に成功条件を定義する
- 事前に停止条件を定義する
- 変更範囲を最小化する
- Project Owner が明示承認する
- AIは承認者にならない
- 他の改善作業を混ぜない

### S4を検出した場合

作業中にS4相当の内容が必要になった場合、Implementation AI は作業を停止する。

その場合、Implementation AI は以下を報告する。

- どの内容がS4に該当するか
- なぜ現在のPRでは扱えないか
- どの作業を保留すべきか
- Project Owner に何を判断してほしいか

### S4の禁止混入

以下は禁止する。

- S4を軽微な修正として扱う
- S4を別目的のPRに混ぜる
- S4をAI判断だけで進める
- S4を「ついで」に処理する
- S4をS3以下として自己申告する

---

## 8. Project Completion State Machine

プロジェクト完了までの状態を、以下の状態遷移で管理する。

各状態では、次に進める条件を明確にする。  
状態を飛ばして進めてはならない。

### STATE 1: RESET_RULES

目的:

- 旧方針のうち、現在の運営に不要なものを整理する
- 残す要件と捨てる要件を分ける
- 今後の最小運営モデルに移行する準備をする

完了条件:

- 破棄する方針が明記されている
- 継承する要件が明記されている
- 次に作る最小文書が明確である

次の状態:

- MINIMAL_OS

### STATE 2: MINIMAL_OS

目的:

- Project Owner が制御可能な最小運営モデルを定義する
- 役割、権限、リスククラス、マージ条件を明確にする
- WIP制限と1PR1目的の原則を固定する

完了条件:

- Roles が定義されている
- Authority Model が定義されている
- PR Risk Class が定義されている
- Merge Rules が定義されている
- S4 Isolation が定義されている
- Project Completion State Machine が定義されている

次の状態:

- OWNER_RUNBOOK

### STATE 3: OWNER_RUNBOOK

目的:

- Project Owner がPRを判断するための確認項目を定義する
- コード詳細に依存しない判断方法を明確にする
- HOLDとREJECTの基準を簡潔にする

完了条件:

- Owner確認項目が定義されている
- HOLD条件が定義されている
- REJECT条件が定義されている
- S3/S4の判断方法が定義されている

次の状態:

- AI_ENTRYPOINT_SIMPLIFIED

### STATE 4: AI_ENTRYPOINT_SIMPLIFIED

目的:

- AIが最初に読むべき入口を最小化する
- 複数の入口による混乱を防ぐ
- AIに許可することと禁止することを明確にする

完了条件:

- AI向けの読書順が明確である
- AIの停止条件が明確である
- 作業範囲の自己拡大が禁止されている
- S4を検出した場合の停止ルールが定義されている

次の状態:

- PR_TEMPLATE_MINIMAL

### STATE 5: PR_TEMPLATE_MINIMAL

目的:

- すべてのPRに必要な最小情報を定義する
- Project Owner がPR本文だけで一次判断できるようにする

完了条件:

- Risk Class欄がある
- Goal欄がある
- Allowed Paths欄がある
- Frozen Paths欄がある
- Verification欄がある
- State Impact欄がある
- Owner Decision欄がある

次の状態:

- GUARDRAIL_MINIMAL

### STATE 6: GUARDRAIL_MINIMAL

目的:

- 明確に危険な変更を機械的に検出できる状態にする
- Project Owner の見落としを減らす
- S3/S4混入を検出する

完了条件:

- 変更範囲を確認できる
- リスククラスの矛盾を検出できる
- S4混入を検出できる
- HOLD理由を説明できる

次の状態:

- OWNER_CONTROL_ENABLED

### STATE 7: OWNER_CONTROL_ENABLED

目的:

- Project Owner がPRを安全にHOLD、APPROVE、REJECTできる状態にする
- 高リスク作業を通常作業から分離できる状態にする

完了条件:

- WIP Limit = 1 が守られている
- One PR = One Purpose が守られている
- S3以上の判断基準が機能している
- S4 Isolation が守られている
- Project Owner が不明時にHOLDできる

次の状態:

- CORE_PROJECT_WORK

### STATE 8: CORE_PROJECT_WORK

目的:

- 本来のプロジェクト作業を、最小運営モデルの下で進める
- 変更を小さく分割する
- 完了条件に向けて状態を進める

完了条件:

- 主要な未完了項目が分類されている
- 次に進める作業が1つに絞られている
- 変更がリスククラスに従って処理されている
- S4が通常作業に混ざっていない

次の状態:

- FINAL_COMPLETION_REVIEW

### STATE 9: FINAL_COMPLETION_REVIEW

目的:

- プロジェクトが完了条件を満たしたか確認する
- 未完了項目と既知の制限を明確にする
- Project Owner が完了判断できる状態にする

完了条件:

- 完了した範囲が明確である
- 未完了の範囲が明確である
- 既知の制限が明確である
- Project Owner が最終判断できる

次の状態:

- COMPLETED

### STATE 10: COMPLETED

目的:

- Project Owner が定義した完了条件に到達した状態を固定する

完了条件:

- Project Owner が完了を承認している
- 完了範囲が説明可能である
- 未完了範囲が隠されていない
- 次の改善作業と現在の完了状態が分離されている

---

## 最終原則

このプロジェクトでは、複雑なルールよりも、少数の明確な制御点を優先する。

最重要原則は以下である。

1. AIは作業者であり、承認者ではない。
2. Project Owner はコードの全詳細ではなく、状態・範囲・リスクを制御する。
3. WIPは1に制限する。
4. 1PRは1目的に限定する。
5. S4は通常作業から分離する。
6. 不明ならHOLDする。
7. 根拠のない「確認済み」は無効とする。
8. Project Owner が理解できない状態では進めない。
