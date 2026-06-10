# タスク完了報告 — PR #87（番号は次PRの想定。実際の番号が異なる場合はリネームすること）

## 概要

GPT監査が「diffしか見ていない」と判明した問題への対策を、同一ブランチで2層実装した。

1. **Audit Evidence Ledger（監査証拠台帳）**: 監査者に「diffだけでは物理的に書けない成果物」（diffレビュー前の現状仕様の逐語引用＋関数名＋行番号、参照元一覧、否定証拠、読了マニフェスト）の添付を義務付け、受信側（Claude）が `scripts/validate_audit_evidence.py` で機械検証する。引用・件数が実リポジトリと1件でも不一致なら監査全体を無効とする fail-closed 設計。
2. **機械監査ゲート（Audit Packet + Policy Engine）**: head SHA・CI・レビュースレッド・FROZENパス・SSOT整合などの機械的事実は LLM に報告させず、`scripts/build_audit_packet.py` が収集・正規化し、`scripts/audit_policy_engine.py` が APPROVE 可否を機械計算する。パケットは `machine_facts`（スクリプト生成・直接信用）と `judgment_inputs`（LLM主張・証拠検証経由でのみ有効）に分離し、**LLMの自己申告が機械的証拠にロンダリングされる穴を構造的に塞いだ**。
3. **CI required check（`.github/workflows/gpt-audit-gate.yml`、Project Owner 明示承認済み）**: 正統なパケットは pull_request イベントごとに CI 上で生成・評価・artifact 化される（LLM の手元で作ったパケットは捏造可能なため）。`--mode ci-gate` は CI 時点で決定論的なルールのみ blocking とし、合格は `APPROVE_ALLOWED` と語彙を分離した `CI_GATE_PASS`（承認許可として引用不能）。

## 変更ファイル一覧

- 追加: `scripts/validate_audit_evidence.py` — 証拠台帳の機械検証バリデータ（標準ライブラリのみ）
- 追加: `scripts/build_audit_packet.py` — Audit Packet 収集・正規化（GitHub API / 注入raw両対応、標準ライブラリのみ）
- 追加: `scripts/audit_policy_engine.py` — APPROVE可否の機械計算（exit 0=APPROVE_ALLOWED / 1=HOLD / 2=PACKET_INVALID）
- 追加: `schemas/gpt_audit_packet.schema.json` — パケットスキーマ（machine_facts / judgment_inputs 分離）
- 追加: `tests/test_validate_audit_evidence.py` — バリデータのテスト42件
- 追加: `tests/test_audit_packet.py` — collector / policy engine のテスト39件
- 追加: `.github/workflows/gpt-audit-gate.yml` — 機械監査ゲートの required check（read-only・workflow_dispatch なし・GEMINI_API_KEY なし）
- 追加: `tests/test_gpt_audit_gate_workflow.py` — ワークフロー構造テスト12件（コメント除去後の実効内容で否定アサーション）
- 追加: `docs/audit_gate/AUDIT_PACKET_PROTOCOL.md` — 機械監査ゲートのプロトコル（3層構造・信頼境界・policy条件・ci-gate/full の enforcement 分担表・branch protection 手順）
- 変更: `docs/audit_gate/PR_AUDIT_PROTOCOL.md` — 「Machine audit gate (layer 0)」「Audit Evidence Ledger」セクション新設、APPROVE条件追加、Output structure に台帳セクション追加、AI_DOC_META 付与
- 変更: `CLAUDE.md` — 監査受信ゲートを10項目→12項目に拡張（#11 証拠台帳の存在、#12 受信側によるバリデータ実行）、差し戻し分類 `DIFF_ONLY_AUDIT` / `AUDIT_EVIDENCE_MISMATCH` 追加、プロトコル参照表に AUDIT_PACKET_PROTOCOL を追加
- 変更: `docs/audit_gate/CHANGELOG.md` — 教訓エントリ2件追加、AI_DOC_META 付与
- 変更: `README.md` — scripts/ ファイルツリーに3スクリプト、schemas/ を追記（生成ブロック `CYBER_IMMUNIZER_STATUS_START/END` の外側のみ。`scripts/update_readme.py` の変更は不要）

## 主な変更内容

### 層0: 機械監査ゲート（Audit Packet + Policy Engine）

- **collector は `judgment_inputs` を常に null スケルトンで出力**し、raw入力に紛れ込んだ judgment データは破棄する（アンチ・トロイの木馬。テストで担保）
- policy engine の APPROVE_ALLOWED 条件: PR open・非merged・非draft / `--current-head-sha` 一致（**未指定自体が HOLD 理由** — fail-closed の鮮度ロック）/ CI SUCCESS かつ head SHA 一致 / 未解決スレッド0・P1/P2未解決0 / FROZEN接触が `--allow-frozen`（Owner承認分）で全カバー / SSOT整合 / 全 judgment が証拠検証済み
- **judgment claim は `claim: true` だけでは無効**。`evidence_report` を policy engine 自身が `validate_audit_evidence.py` で再実行検証して初めて有効（記録された「検証済み」アサーションは信用しない）
- CI分類は未知の conclusion を FAILURE 扱い（fail-closed）。スレッド未解決数は resolved/outdated 除外後、P1/P2 は語境界regexで先頭コメントから検出
- SSOT整合 = `data/project_state.json` の `state_id` が `docs/PROJECT_STATE.md` に逐語出現（ファイル欠損・JSON破損は不整合扱い）

### 層1: Audit Evidence Ledger（監査証拠台帳）

- **Pre-diff spec recitation（Rule 1）**: diffレビュー**前に**、変更ファイルごとに diff外のコア処理を関数名＋行番号付きで逐語引用し現状仕様を説明。引用範囲が diff ハンクと重なると不合格。新規ファイルは免除、docs は見出し引用で代替可
- **Call-site evidence（Rule 2）**: 変更シンボルの参照元を `path:lineno:content` で全件列挙＋`COUNT`。バリデータが再カウント
- **Negative evidence（Rule 3）**: 「探して見つからなかったもの」最低2件。バリデータが再検索して照合
- **Read manifest（Rule 4）**: 全文読了 `FULL:` / diffのみ `DIFF_ONLY:（理由必須）` を全変更ファイルで列挙
- **失敗分類**: 台帳なし → `DIFF_ONLY_AUDIT`、不一致 → `AUDIT_EVIDENCE_MISMATCH`（1件で監査全体無効）。CHANGELOG 記録、再発時は `PULLBACK_PROMPT.md` 適用

### 層2: 受信ゲート

- CLAUDE.md 監査受信ゲート12項目。#12 により、バリデータ実行は監査者の自己申告ではなく受信側 Claude が必ず実施（Prompt Reception Gate と同じ「自己申告を信じない」構造）

### 層0.5: CI required check（gpt-audit-gate.yml）

- pull_request（opened / reopened / synchronize / ready_for_review）で発火。synchronize 再実行により head SHA 鮮度が自動追従。draft はスキップ
- permissions は read-only 3種のみ。`secrets.*` 参照なし（認証は workflow-scoped `github.token`）。`workflow_dispatch` なし（CLAUDE.md 禁止事項準拠）
- checkout は merge ref でなく PR head SHA を明示（SSOT 事実が監査対象 SHA を正確に記述するため）
- `--mode ci-gate` の blocking はパケット構造・PR open/非merged・head SHA 鮮度・SSOT整合のみ。兄弟チェックのCI状態（循環参照）・スレッド未解決（イベント再発火しない→branch protection の仕事）・FROZEN許可（Owner文脈）・judgment は警告として記録
- パケットを `gpt-audit-packet-<head SHA>` artifact としてアップロードし、受信ゲートはCI製パケットを評価する

### Codex Review 対応（P1×3 + P2×1。P1 はいずれも valid / IMPLEMENTATION_AGENT_FAILURE に分類）

0. **diff コンテキスト欠落（第2ラウンド P1）**: full モードを `--base-ref` なしで実行すると証拠バリデータの diff カバレッジ検証（変更ファイルの網羅・引用のdiff外判定）がスキップされ、無関係ファイルだけ引用した証拠で judgment が全有効になる欠陥。→ エンジンが `--base-ref` 未指定時はパケットの `pr.base_sha` から diff base を導出し、diff コンテキストが取得不能なら claim を却下（fail-closed）。回帰テスト2件追加（CALLSITE 欠落レポートの却下・base 解決不能時の却下）
0b. **兄弟チェック PENDING スナップショット（第2ラウンド P2）**: 対応はスナップショット意味論（前項）で設計済み — CI artifact は採取時点の記録で、full モード評価は受信側が評価時点で新規生成したパケットを使う。古い artifact を誤って full モードに食わせても PENDING → HOLD で fail-closed 側に倒れるため誤承認は構造的に起きない。スレッドに設計回答を返信

1. **自己参照 PENDING**: gate 実行中は check-runs に gate 自身（未完了）が含まれ、CI製パケットが恒久的に `ci_status=PENDING` を固定化する欠陥。→ builder に `--exclude-check`（ワークフローは `gpt-audit-gate` を指定）を追加し、除外名を `ci.excluded_checks` に透明記録。あわせてプロトコルに「CI artifact は採取時点スナップショット。full モード評価は受信側が評価時点で新規生成したパケットで行い、artifact は CI 採取の証明・突合記録」と明確化（兄弟チェック走行中という同類の staleness も解決）
2. **rename による FROZEN 迂回**: `status: renamed` のとき旧パス（`previous_filename`）を捨てていたため、`core/foo.py` → `docs/foo.py` の rename が凍結境界の検知をすり抜ける欠陥。→ `changed_files[].previous_path` として保持し、FROZEN 判定を新旧両パスで実施

## 後検証結果

- `python -m pytest tests/ -q` → **2030 passed**（新規110件を含む、既存テストの回帰なし）
- Dogfood（証拠台帳・実リポジトリ）: 正規レポート → `VALID` / exit 0、引用を1箇所改竄 → `INVALID: quote does not match scripts/validate_mutation.py:53` / exit 1
- アンチ・ロンダリングのテスト担保:
  - `test_raw_cannot_inject_judgment_inputs` — raw経由の judgment 注入は破棄される
  - `test_bare_true_claim_without_evidence_holds` — 裸の `claim: true` は HOLD
  - `test_claim_with_fabricated_evidence_holds` — 捏造証拠つき claim は HOLD
  - `test_collector_output_alone_never_allows_approve` — 機械事実が全緑でも judgment 未検証なら HOLD
- README の変更は生成マーカーの外側のみであることを確認（generator 更新不要）

## 残存事項・注意点

- **branch protection の設定は GitHub Settings での手動操作が必要（Project Owner）**: ①Settings → Branches → main の保護ルールで required status checks に `gpt-audit-gate` を追加、②「Require conversation resolution before merging」を ON（未解決スレッドの merge 禁止がコード0行で実現）。この2操作までは gate は「走るが merge を物理的には止めない」状態。手順は `AUDIT_PACKET_PROTOCOL.md` に記載。
- **ワークフローの実走はマージ後の次 PR が初回**: gpt-audit-gate.yml は base ブランチに入って初めて pull_request で発火する。初回実行で GitHub API レスポンス形状の差異が出た場合は fail-closed（check 赤）になるので誤通過はない。
- **GitHub API 収集は本セッションでは実線未検証**: collector の `--github` モードは GITHUB_TOKEN 必須・ネットワーク必要のため、テストは `--from-raw`（注入raw）で実施。初回実行時に REST/GraphQL レスポンス形状の差異が出る可能性がある（fail-closed なので誤通過はしない）。
- **証拠台帳の検索はリテラル部分一致（正規表現なし）**: 決定論的再現のため。汎用的すぎるシンボル名は `SCOPE:`（パスプレフィックス）で絞る。
- `unresolved_p1_p2` の P1/P2 検出はスレッド先頭コメントの語境界regexによる。表記変更で検出漏れし得るが、`unresolved` 総数も独立に0を要求するため二重に守られている。
- **GPT 側プロトコル（TASK_PROMPT_PROTOCOL.md / AUDIT_CHARTER.md）は未変更**: GPT に台帳・パケット運用を事前周知するプロンプト整備は次タスク候補。
- 本報告のファイル名は次 PR を #87 と想定したもの（#86 は Codex の task-prompt-protocol 強化 PR として使用済み）。実際の PR 番号が異なる場合はリネームが必要。
