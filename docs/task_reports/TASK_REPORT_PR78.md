# タスク完了報告 — PR #78

## 概要
PR #77 マージ後の未解決事項を、GitHub一次ソースとローカル実ファイルで照合した
事実ベースの棚卸しドキュメントを作成した。実装・修正・workflow実行は一切行わず、
docs のみを追加した（inventory-only タスク）。

## 変更ファイル一覧
- 追加: `docs/audit_gate/POST_PR77_UNRESOLVED_BACKLOG.md`（棚卸し本体）
- 追加: `docs/task_reports/TASK_REPORT_PR78.md`（本報告ファイル）

> core / scripts / tests / .github / data / ledger / genome.json への変更なし。

## 主な変更内容
- **検証済みリポジトリ状態**: main HEAD = `1da8018`（PR #77 マージコミット）。
  PR #72 / #73 / #76 / #77 はすべて MERGED。validator は checks 1–11。open PR なし。
  `.grok/**` の active ファイルは存在しない（`find .grok -type f` → なし）。
- **Source Evidence 5領域**（各バックログ項目に実ファイル行を引用）:
  - X-007 / check 11: PR #73 で実装・merge 済み。check 11 自体に未解決はない。
  - Category D runtime gap: `core/fitness.py:143-159` の `_contract_ok` は
    DetectionResult インスタンスと confidence 範囲のみ検証し、
    `blocked: bool` / `reason: str` / `matched_signals: tuple[str,...]` の型は
    runtime で強制していない。既知の residual gap・Project Owner-overridable。
  - Phase 3 paid-credit: activation PR #58–#62 merge 済み・`live_model_enabled=true`
    だが `gemini-3-flash-preview` の controlled run は未実行（`promote_approved=false`）。
  - X-002 / X-003 / X-006: policy 項目として deferred（spec Scope-Out + CHANGELOG + README）。
  - Grok 削除後の audit workflow: active workflow に Grok 参照なし。
    Codex（補助）+ GPT Audit Gate（統合）+ Project Owner（最終）で完結し機能的 gap なし。
- **検出した不整合（推測ではなく報告）**: `CLAUDE.md` 現在の状態テーブルと README は
  「Gemini API 未接続 / Phase 3 Go-No-Go 待ち」と記載するが、canonical な
  `docs/PHASE_3_GO_NO_GO_CHECKLIST.md` は #58–#62 merge 済み・`live_model_enabled=true`
  と記録しており矛盾。これを P0・次推奨 PR（docs-only の Phase 3 状態補正）とした。
- **バックログ表**を P0/P1/P2 で分類（Type・Owner approval・推奨アクション付き）。
- **推奨次 PR を1件**に限定: `CLAUDE.md` と README の Phase 3 状態補正（docs-only）。

## 後検証結果
- `git status --short` → `docs/audit_gate/POST_PR77_UNRESOLVED_BACKLOG.md` 追加のみ
  （本報告ファイル追加後は2ファイル）。
- `git diff --cached --stat` → 棚卸し本体 218 行追加、forbidden パスへの変更なし。
- `find .grok -type f` → ファイルなし（Grok 再導入していない）。
- forbidden パス（scripts/core/tests/.github/data/ledger）への変更ゼロを確認。

## 残存事項・注意点
- 本タスクは inventory のみ。Category D runtime hardening は **design-only** が次段階で、
  `core/**` の編集実装は Project Owner 承認が必要（YES_BEFORE_IMPLEMENTATION）。
- Phase 3 初回 controlled paid-credit run は Project Owner の手動 `workflow_dispatch`
  と外部ゲート（Secrets / billing / budget）確認が前提（YES_BEFORE_RUN）。本タスクでは実行していない。
- X-002 / X-003 / X-006 は具体的 validator 定義が未確定のため、実装前に policy-alignment
  inventory が必要。
- `CLAUDE.md` / README の Phase 3 状態補正（P0）は本 PR の scope 外。次 PR で対応すべき事項。

## Codex P1 対応（2026-06-07 追記）

**指摘（valid）**: `POST_PR77_UNRESOLVED_BACKLOG.md` が
「first gemini-3-flash-preview controlled paid-credit run is still pending /
 not yet executed / 次は workflow_dispatch で paid-credit run を1回実行」
と読める状態だった。しかし一次証跡 `data/api_usage_ledger.json` には
`gemini-3-flash-preview` / `gemini_paid_credit` / `success: true` の記録が
2026-06-03・2026-06-04 に複数存在し、矛盾していた。

**一次証跡の確認（read-only）**:
- `data/api_usage_ledger.json:74-93` — gemini-3-flash-preview / gemini_paid_credit / success=true（2026-06-03T23:36）
- `data/api_usage_ledger.json:94-113` — 同上（2026-06-04T00:34）
- `data/api_usage_ledger.json:114-133` — 同上（2026-06-04T01:33）
- `data/api_usage_ledger.json:56-73` — gemini-3.1-flash-lite / success=true（2026-06-02）

**修正内容（fix commit `8809cef`）**:
1. 「Gemini 3 Flash Preview paid-credit API call 未実行」という趣旨の表現を削除。
2. 正しい状態に分解:
   - gemini-3-flash-preview paid-credit API call: **success records exist** in `data/api_usage_ledger.json`。
   - promote_approved: **false**。
   - post-run review / candidate patch / apply / evaluate / promotion decision: **status must be verified separately**（本 inventory では断定しない）。
3. Backlog table の Phase 3 項目を修正: Type = `DOCS_CONTROL_PLANE + PAID_CREDIT_OPERATION`、
   Recommended action は `WAIT` ではなく `DESIGN_ONLY`（既存 run result の review inventory）。
   「manual workflow_dispatch をもう一度実行」が次アクションに見えないよう明記。
4. Recommended next PR を変更: CLAUDE.md / README に加え、relevant Phase 3 docs
   （`PHASE_3_GO_NO_GO_CHECKLIST.md` の "controlled run 未実行" 表現を含む）を
   ledger evidence に合わせて補正する docs-only PR を推奨。
5. `PHASE_3_GO_NO_GO_CHECKLIST.md:95` の "Not yet executed" 表現も stale として
   補正対象に追加（本 PR scope 外、次 PR で対応）。
6. core / scripts / tests / .github / **data（ledger 含む）** は変更なし。paid-credit workflow 実行なし。

**Codex P1 fix commit head SHA**: `8809cef20f2579354a79641e919ab2ed8dff324b`

## Definition of Done（プロンプト指定項目）
- [x] 実装変更なし
- [x] workflow 変更なし
- [x] paid-credit workflow 実行なし
- [x] Grok 再導入なし
- [x] 各バックログ項目に実 source 引用あり
- [x] runtime hardening の design と implementation を分離
- [x] Project Owner approval ゲートを明示
- [x] 推奨次 PR を1件に限定
- [x] 不確実点は推測せず報告（CLAUDE.md state drift を明記）
