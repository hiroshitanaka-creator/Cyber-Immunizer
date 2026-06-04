<!--
AI_DOC_META
status: HISTORICAL
scope: Phase 1 baseline and foundational safety invariants.
use_for:
  - understanding the original safety baseline
  - checking whether later work contradicts Phase 1 assumptions
do_not_use_for:
  - current task selection
  - Phase 3 activation decision
  - current API readiness judgment
related:
  - docs/PHASE_2_PLAN.md
  - docs/PHASE_2_COMPLETION_CHECKPOINT.md
last_reviewed: 2026-05-30
AI_DOC_META_END
-->
# Cyber-Immunizer Phase 1 Baseline

> このドキュメントは Phase 1 の完了状態を固定します。  
> **Project Owner の決定なく Phase 2 へ移行してはなりません。**

---

## Phase 1 完了範囲

以下が Phase 1 において完了済みです。

- Architecture baseline（MAPE-K ループ設計・propose / evaluate / promote 分離）
- GPT Audit Gate（AUDIT_CHARTER.md・PR テンプレート・6カテゴリ監査体制）
- Security boundary（AST ポリシー・シークレットスキャン・subprocess 隔離）
- AST policy（`core/policy.py` による import / eval / exec / os / dunder 禁止）
- deterministic fitness / regression（スコア計算式確定・リグレッション通過率 1.0 強制）
- API budget ledger（`scripts/api_budget.py` / `data/api_usage_ledger.json` による月次・日次予算管理）
- fail-closed budget governance（不正 ledger → 即拒否の fail-closed 動作）
- CI workflow（`.github/workflows/ci.yml` — pytest による自動テスト）
- noop workflow（`workflow_dispatch mode=noop` — API 呼び出しなしの動作確認）
- offline-sample workflow（`workflow_dispatch mode=offline-sample` — APIキー不要の変異サンプル適用）
- gemini-paid-credit-preflight（`workflow_dispatch mode=gemini-paid-credit-preflight` — 実 API 未呼び出しの準備状態確認）
- API Activation Runbook（`docs/API_ACTIVATION_RUNBOOK.md` — キー登録から有効化までの手順書）

---

## Phase 1 で意図的に未実施のもの

以下は Phase 1 において未実施です。これらは Phase 2 への移行後にのみ実施されます。

- GEMINI_API_KEY registration（GitHub Secrets へのキー登録は未実施）
- live_model_enabled=true（`data/genome.json` の `live_model_enabled` は `false` のまま）
- real Gemini API call（実際の Gemini API 呼び出しは一度も行っていない）
- automatic scheduled API call（スケジュール実行は常に noop モード）
- multi-candidate generation（複数候補の生成は未実施）
- self-repair retry（自己修復リトライは未実施）
- high-frequency schedule（高頻度スケジュール実行は未実施）
- free-tier operation（フリーティア API 運用は未実施）

---

## Verified paths

Phase 1 において以下の動作パスが確認済みです。

- **CI / Test Suite success** — `python -m pytest` が全件通過（367 passed）
- **workflow_dispatch mode=noop success** — propose / evaluate / promote をすべてスキップ、API 呼び出しゼロ
- **workflow_dispatch mode=offline-sample success** — 組み込みサンプルパッチを使用、API 呼び出しゼロ
- **workflow_dispatch mode=gemini-paid-credit-preflight failure when GEMINI_API_KEY is missing**
  - `GEMINI_API_KEY` が未登録の場合、このモードは失敗（exit 1）する
  - これは正常な fail-closed 挙動であり、意図した動作である
  - preflight 失敗は「システムが安全に停止している」ことの証明である

---

## Safety invariants

Phase 1 完了時点における安全不変条件です。これらは Phase 2 移行前も後も変更してはなりません。

| 不変条件 | 値 / 状態 |
|---|---|
| `live_model_enabled` | `false`（`data/genome.json` で確認） |
| `max_model_requests_per_run` | `1`（API 呼び出し数の上限） |
| `max_commits_per_run` | `1`（コミット数の上限） |
| schedule（スケジュール実行） | 常に `noop` モードに解決される |
| `GEMINI_API_KEY` | GitHub Secrets にのみ属し、リポジトリ内ファイルには存在しない |
| 生成コードの実行 | 書き込み権限を持つジョブでは実行されない（subprocess 隔離） |
| promote ジョブ | API 使用 ledger を扱わない（ledger は persist-ledger ジョブが担当） |
| 不正 ledger | fail-closed — 拒否して実行を中断する |
| `ci.yml` | 読み取り専用・Gemini を呼び出さない |

---

## Exit criteria

**Phase 1 は以下のすべてを満たした場合にのみ完了と見なされます。**

- [ ] CI が通過している（`python -m pytest` 全件 pass）
- [ ] noop パスが通過している（`workflow_dispatch mode=noop`）
- [ ] offline-sample パスが通過している（`workflow_dispatch mode=offline-sample`）
- [ ] preflight が存在している（`workflow_dispatch mode=gemini-paid-credit-preflight`）
- [ ] API Activation Runbook が存在している（`docs/API_ACTIVATION_RUNBOOK.md`）
- [ ] API キーがコミットされていない（`GEMINI_API_KEY` はリポジトリ内に存在しない）
- [ ] `live_model_enabled=false` が維持されている（`data/genome.json` で確認）

**✅ 上記すべての条件が Phase 1 完了時点で満たされています。**

---

## Phase 1 → Phase 2 への移行条件

Phase 2（実 Gemini API 接続）への移行は、**Project Owner の明示的な決定**によってのみ開始されます。

詳細は `docs/AUDIT_CHARTER.md` の **Phase transition rule** セクションを参照してください。

---

*このドキュメントは Project Cyber-Immunizer の Phase 1 完了状態を永続的に記録します。*  
*作成日: 2026-05-26*
