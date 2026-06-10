# CLAUDE.md — Cyber-Immunizer

セッション開始時に必ずこのファイルを読む。その後 `docs/AI_ENTRYPOINT.md` を読んでタスクに合ったプロトコルに進む。

---

## プロジェクト概要

LLMを使って防御コードを自律的に進化させる研究プロジェクト。
ASTポリシー + サブプロセス隔離 + 適合度評価で候補コードを安全に検証・昇格する。
**防御専用。攻撃コード生成・実トラフィック接続・マルウェア技術は行わない。**

---

## 最初にやること

1. `docs/AI_ENTRYPOINT.md` を読む（タスク別プロトコル参照先の一覧がある）
2. タスクが実装プロンプト作成なら → `docs/audit_gate/TASK_PROMPT_PROTOCOL.md`
3. タスクがPR監査・マージ判断なら → `docs/audit_gate/PR_AUDIT_PROTOCOL.md`

---

## 現在の状態の正典（Current-State SSOT）

**プロジェクトの「今の状態」を解釈するとき、すべての歴史ドキュメントを相互に突き合わせて整合を取ろうとしてはいけない。** 以下の権威順序で判断する。

1. **機械的証拠（machine evidence）** — 最新 `main` HEAD / `data/api_usage_ledger.json` / `data/genome.json` / GitHub Actions・CI 結果
2. `data/project_state.json`（機械可読の current-state 正典）
3. `docs/PROJECT_STATE.md`（人間可読の current-state 正典）
4. 派生サマリ — `README.md` ステータスブロック / この `CLAUDE.md`

歴史ドキュメント（古い task report・roadmap スナップショット・古い PR 本文・古い phase docs）は **過去の状態の証拠** にすぎず、current state を独立に定義しない。マージ済みの PR 本文・task report は、その PR 固有の証拠であって current-state 正典ではない。
現在の状態は `docs/PROJECT_STATE.md` と `data/project_state.json` を見れば確定する。

---

## 絶対にやってはいけないこと

| 禁止事項 | 理由 |
|---|---|
| `scripts/**` / `core/**` / `.github/**` / `data/**` を無断で編集 | scope外・安全境界 |
| Gemini API 呼び出し・`live_model_enabled=true` 設定 | paid-credit は Project Owner が明示承認した場合のみ |
| `workflow_dispatch` / CI 手動トリガー | 同上 |
| `git push --force` / `git reset --hard` | 履歴破壊禁止 |
| PR を無断で APPROVE / マージ | Project Owner の最終判断が必要 |

---

## 現在の状態（要約 — 正典は `docs/PROJECT_STATE.md` / `data/project_state.json`）

> この表は派生サマリ。current state の確定は上記「現在の状態の正典」の権威順序に従うこと。
> 矛盾があれば `docs/PROJECT_STATE.md` と `data/project_state.json` が優先する。

| 項目 | 状態 |
|---|---|
| Phase | Phase 3 — paid-credit API call の success 記録が存在。3件の primary-model success に対し **有効な mutation patch は未生成**（propose/output-contract 失敗） |
| Gemini API | paid-credit path で接続済み。`gemini-3-flash-preview` / `gemini_paid_credit` の success 記録3件が `data/api_usage_ledger.json` に存在（API/token success のみ） |
| apply / evaluate / promote | いずれも未到達（3 runすべて） |
| promote_approved | `false` — 昇格は未承認。API call が未実行という意味ではない |
| Next focus | propose / output-contract の根本原因を修正してから次の paid-credit run（`state_id=phase3_paid_credit_api_success_patch_not_produced`） |

---

## タスクプロンプト受け取り時の必須確認（Source Evidence ゲート）

実装タスクプロンプトに `Source Evidence` ブロックがある場合：

1. 各 `file_path:start_line-end_line` 引用を実ファイルと照合する
2. 引用内容が実ファイルと一致しない → **作業を開始せず**、不一致箇所を報告して差し戻す
3. `Source Evidence` ブロックが空または「確認済み」などの assertion のみ → 無効なプロンプトとして差し戻す

---

## タスクプロンプト受け取り時の必須確認（受信側10項目ゲート）

GPTが出力したタスクプロンプトを受け取った際、以下10項目を客観的に採点する。
**GPTが記載した自己スコア（98/100等）は無視する。受信側（Claude）が独自に判定する。**

| # | 項目 | 合格基準 |
|---|---|---|
| 1 | 目的が1文で書かれているか | `# Task:` または `## Context` に完結した文がある |
| 2 | 禁止事項が書かれているか | `## Constraints` または `DO_NOT` が非空 |
| 3 | 編集対象ファイルが書かれているか | `ALLOWED` セクションに1行以上、かつ各ファイルに理由が付いている（`REFERENCE_ONLY` / `FROZEN` の有無は問わない） |
| 4 | 影響範囲確認があるか | `IMPACT` が非空（`なし（理由）` 形式も可） |
| 5 | diff以外の全体確認があるか | `Pre-Prompt Investigation Gate` セクション内の全フィールドが非空（空白・プレースホルダー禁止）、かつ `Source Evidence` ブロックが存在する（assertion のみは不可） |
| 6 | 破壊リスク確認があるか | `INVARIANT` フィールドが非空 |
| 7 | 完了報告形式が指定されているか | `Definition of Done` に「何が green であること」が明示されている |
| 8 | 勝手な追加実装禁止があるか | `DO_NOT` またはスコープ外停止条件の記載が非空 |
| 9 | テスト実行条件があるか | `Definition of Done` に `pytest` 等の実行コマンドが1つ以上 |
| 10 | 不明点停止条件があるか | `## On Ambiguity` または同等の記載が非空 |

**1項目でも欠けていたら作業を開始せず、以下の形式で差し戻す。**

```
タスクプロンプト受信ゲート — 差し戻し

不合格項目:
- #<番号> <項目名>: <何が欠けているか>

再提出要件:
- 上記項目を追記・修正してプロンプトを再提出してください。
- GPTの自己スコアの記載は不要です。
```

### 合格時：採点レシートを必ず出力する（省略禁止）

10項目が全て合格した場合も、作業開始前に必ず以下の形式で採点結果を出力する。省略・省エネ版の出力は禁止。

```
プロンプト受信ゲート — 採点結果
#1 目的 ✅  #2 禁止事項 ✅  #3 編集対象ファイル ✅  #4 影響範囲 ✅  #5 全体確認 ✅
#6 破壊リスク ✅  #7 完了形式 ✅  #8 追加禁止 ✅  #9 テスト条件 ✅  #10 停止条件 ✅
→ 10/10 合格。
```

このレシートを出力することで、Project Owner はゲートが実行されたことを目視確認できる。

### 合格後：作業開始前に意図確認を1文出力して待つ（省略禁止）

採点レシートの出力後、即座に作業を開始してはいけない。まず以下の形式で日本語1文を出力し、Project Owner の返答を待つ。

```
【意図確認】このタスクは「<タスクの目的を平易な日本語で1文に要約>」ものです。
続けてよいですか？
```

- Project Owner が「はい」または肯定的な返答をした場合のみ作業を開始する。
- 修正・中断の指示が来た場合はそれに従い、作業を開始しない。
- 意図確認を省略して作業を開始することは禁止。技術的な詳細を読まなくても意図のズレを確認できるよう、要約は平易な日本語で書く。

### GPTの自己スコア（98/100）について

`docs/audit_gate/TASK_PROMPT_PROTOCOL.md` の98点閾値はGPT自身の出力判断用ルールであり、
**Claude・その他のAIは参照しない。受信側は上記10項目のpresent/非空チェックのみを根拠に合否を判定する。**

---

## スレッド引き継ぎ受け取り時の必須確認（引き継ぎ受信ゲート）

スレッド引き継ぎプロンプトを受け取った際、以下10項目を確認する。
詳細ルールは `docs/audit_gate/THREAD_HANDOFF_PROTOCOL.md` を参照。

| # | 項目 | 合格基準 |
|---|---|---|
| 1 | ブランチ名が明記されているか | `branch:` が非空 |
| 2 | Head SHA が逐語的に記載されているか | `head SHA:` にハッシュ値（「未確認」の明示は可、空白・「要確認」のみは不可） |
| 3 | PR番号・状態が記載されているか | `PR number / state:` が非空 |
| 4 | Head SHA 対応の CI ステータスが記載されているか | `SUCCESS` / `FAILED` / `NOT TRIGGERED` / `未確認` のいずれか |
| 5 | テスト結果が実行値で記載されているか | 実行コマンドと結果が非空（「未確認」の明示は可） |
| 6 | 現在のタスクが1文で書かれているか | `Current task in one sentence` が非空 |
| 7 | Done 項目がコミット SHA またはファイルパスを引用しているか | assertion のみの「完了」は不可 |
| 8 | 次のアクションが列挙されているか | `Not done / next step` が非空 |
| 9 | Hard constraints が列挙されているか | 空白不可 |
| 10 | Assumptions / unverified が記載されているか | 空白不可（「なし」明示は可） |

**1項目でも欠けていたら作業を開始せず、以下の形式で差し戻す。**

```
引き継ぎ受信ゲート — 差し戻し

不合格項目:
- #<番号> <項目名>: <何が欠けているか>

再提出要件:
- 上記項目を追記・修正して引き継ぎプロンプトを再提出してください。
```

### 合格時：採点レシートを出力し、リポジトリで再検証してから作業を開始する（省略禁止）

```
引き継ぎ受信ゲート — 採点結果
#1 ブランチ ✅  #2 Head SHA ✅  #3 PR状態 ✅  #4 CI ✅  #5 テスト結果 ✅
#6 現タスク ✅  #7 Done引用 ✅  #8 次アクション ✅  #9 制約 ✅  #10 未確認事項 ✅
→ 10/10 合格。リポジトリ再検証を実行します。
```

レシート出力後、作業開始前に以下をリポジトリで必ず再検証する（引き継ぎ内容を盲信しない）：

- `git branch --show-current` と `git log --oneline -1` で branch と head SHA を照合する
- 引き継ぎの head SHA が実際の SHA と異なる → **作業を停止して不一致を報告する**
- 引き継ぎの head SHA が `未確認` → `git log --oneline -1` で実際の SHA を取得して記録し、作業を続行する（停止しない）
- 引き継ぎに記載されたテストコマンドを実行して結果を確認する
- `Hard constraints` をこのセッションでも継続適用する

---

## PR監査結果受け取り時の必須確認（監査受信ゲート）

GPT または他の AI が作成した PR 監査レポートを受け取った際、以下12項目を確認する。
詳細ルールは `docs/audit_gate/PR_AUDIT_PROTOCOL.md` を参照。

| # | 項目 | 合格基準 |
|---|---|---|
| 1 | 最新 Head SHA が明記されているか | `head SHA:` に逐語的なハッシュ値がある |
| 2 | 変更ファイルの全リストが記載されているか | `changed files:` が非空 |
| 3 | CI が規定9分類で分類されているか | `SUCCESS` / `TEST FAILURE` / `NOT TRIGGERED` 等9値のいずれか |
| 4 | Codex 状態が規定5値で報告されているか | `VERIFIED` / `VERIFIED BY REACTION ONLY` / `FAILED` / `NOT VERIFIED` / `UNRESOLVED THREAD PRESENT` のいずれか |
| 5 | スコープ内・スコープ外が両方識別されているか | `scope-in` と `scope-out` が両方記載されている |
| 6 | ドキュメント/履歴ゲートが5項目確認されているか | README/docs/changelog/generator/data の全項目に結果または「不要（理由）」がある |
| 7 | Findings が規定フォーマットで記載されているか | Severity/該当箇所/脅威/根本原因/修正 が各 Finding に存在する |
| 8 | scope 内の valid Codex findings が全て5分類で分類されているか | severity 問わず有効な finding があれば `GPT_PRE_PROMPT_FAILURE` 等5分類のいずれかが付いている |
| 9 | マージ決定が4行フォーマットで記載されているか | `Code Audit` / `CI Verification` / `Codex Verification` / `Merge Recommendation` の4行がある |
| 10 | APPROVE 時は全確認条件を満たしているか | APPROVE なら `PR_AUDIT_PROTOCOL.md` の「Do not give APPROVE unless all are true:」リストの全条件が確認済み |
| 11 | 監査証拠台帳（Audit Evidence Ledger）が添付されているか | `audit-evidence` ブロックが存在し、SPEC_RECITATION（変更ファイルごと・**diffレビュー前にdiff外のコア処理を関数名＋行番号で逐語引用し現状仕様を説明**）/ CALLSITE / NEGATIVE×2以上 / READ_MANIFEST が揃っている。「確認済み」等の assertion のみは不可 |
| 12 | 証拠が機械検証を通過したか | 受信側（Claude）が `python scripts/validate_audit_evidence.py --report <レポート> --base-ref origin/main` を**必ず実行**し exit 0 であること。監査者の自己申告では代替できない |

**1項目でも欠けていたら差し戻す。** 差し戻し時は不合格の種類を明記する：

- 台帳が無い・空・assertion のみ → `DIFF_ONLY_AUDIT`
- 引用・行番号・件数が実リポジトリと不一致 → `AUDIT_EVIDENCE_MISMATCH`（1件でも不一致があれば監査全体を無効とし、他の Findings も採用しない）
- いずれの場合も `docs/audit_gate/CHANGELOG.md` への記録要否を確認する

```
監査受信ゲート — 差し戻し

不合格項目:
- #<番号> <項目名>: <何が欠けているか>
- （該当時）分類: DIFF_ONLY_AUDIT / AUDIT_EVIDENCE_MISMATCH（validator 出力を逐語添付）

再提出要件:
- 上記項目を追記・修正して監査レポートを再提出してください。
```

### 合格時：採点レシートを出力する（省略禁止）

```
監査受信ゲート — 採点結果
#1 Head SHA ✅  #2 変更ファイル ✅  #3 CI分類 ✅  #4 Codex状態 ✅  #5 スコープ ✅
#6 Doc/履歴 ✅  #7 Findings形式 ✅  #8 Findings分類 ✅  #9 マージ決定 ✅  #10 APPROVE条件 ✅
#11 証拠台帳 ✅  #12 機械検証（validate_audit_evidence.py exit 0） ✅
→ 12/12 合格。監査結果を Project Owner に提示します。
```

---

## ファイルアクセスルール（デフォルト）

| 区分 | パス | 扱い |
|---|---|---|
| 実装コア | `core/**` | FROZEN — 明示許可なく編集禁止 |
| スクリプト | `scripts/**` | FROZEN — 明示許可なく編集禁止 |
| CI/ワークフロー | `.github/**` | FROZEN |
| データ・履歴 | `data/**` | FROZEN |
| テスト | `tests/**` | 通常 FROZEN（新規テストは明示スコープ内のみ可） |
| ドキュメント | `docs/**` | 原則 ALLOWED（スコープ明記の場合） |
| README | `README.md` | ALLOWED（スコープ明記の場合） |

> タスクプロンプトの `FROZEN` 指定が上記より広い場合はプロンプト優先。

---

## 主要プロトコル参照先

| 目的 | ファイル |
|---|---|
| タスクプロンプト構築ルール | `docs/audit_gate/TASK_PROMPT_PROTOCOL.md` |
| PR 監査・マージ判断 | `docs/audit_gate/PR_AUDIT_PROTOCOL.md` |
| 新スレッド引き継ぎ | `docs/audit_gate/THREAD_HANDOFF_PROTOCOL.md` |
| 運用教訓（P2 分類・回帰防止） | `docs/audit_gate/CHANGELOG.md` |
| GPT 引き戻し | `docs/audit_gate/PULLBACK_PROMPT.md` |
| Phase 3 Go-No-Go | `docs/PHASE_3_GO_NO_GO_CHECKLIST.md` |
| X-007 仕様（凍結済み） | `docs/REPLACEMENT_CODE_STATIC_VALUE_CHECKS_SPEC.md` |

---

## 作業完了前チェック

- [ ] `pytest tests/ -x -q` が全通過している
- [ ] 変更した docs に `AI_DOC_META` ブロックがある（既存文書の場合）
- [ ] `docs/audit_gate/CHANGELOG.md` の更新要否を確認した
- [ ] `README.md` の更新要否を確認した
- [ ] スコープ外ファイルを触っていない
- [ ] タスク完了報告 MD ファイルを `docs/task_reports/TASK_REPORT_<PR番号>.md` に作成した

---

## タスク完了報告ルール

**チャット出力だけで完了報告を終えることは禁止。必ず MD ファイルを作成すること。**

理由: モバイル環境ではチャット内の表・区切り線がコピーできないため。

### 報告ファイルの場所と命名

```
docs/task_reports/TASK_REPORT_PR<番号>.md
```

例: `docs/task_reports/TASK_REPORT_PR77.md`

### 報告ファイルの必須項目

```markdown
# タスク完了報告 — PR #<番号>

## 概要
（1〜3行でタスクの目的と結果）

## 変更ファイル一覧
（変更・追加・削除したファイルをリスト）

## 主な変更内容
（箇条書き）

## 後検証結果
（git grep 結果・find 結果など）

## 残存事項・注意点
（対応しなかった事項とその理由）
```

> タスクプロンプトが `Definition of Done` を指定している場合はその項目も含める。
