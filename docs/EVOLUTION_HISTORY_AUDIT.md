# Cyber-Immunizer Evolution History Audit Design

> **Phase 2-C: Evolution History Audit Specification**  
> This document defines the audit trail design for `data/evolution_history.json`.  
> Phase 2-C is design and specification only — no automatic repair, no workflow changes, no API connections.

---

## Purpose

- `data/evolution_history.json` を進化履歴・昇格履歴・拒否履歴・将来の rollback / backtrack 判断の監査証跡として扱う
- Phase 2-C では設計・監査仕様・テストを整備する
- 自動 rollback / backtrack やworkflow変更は行わない
- Human Owner が evolution history を信頼できる監査証跡として参照できるようにする

---

## Scope

### 対象

- `data/evolution_history.json`
- promote / reject / rollback / backtrack の将来記録仕様
- detector hash / score / generation / audit decision の整合性

### 対象外

- `data/api_usage_ledger.json`（API使用量台帳は別物であり、巻き戻さない）
- GitHub Secrets
- billing / API key
- `.github/workflows/*`
- 実 Gemini API call
- rollback CLI 実装
- promote ロジック変更

---

## Required record fields

将来の各 history record に必要な項目を以下に定義する。  
現行の履歴は旧スキーマで記録されており、これらのフィールドは将来の記録に対して適用される。

| フィールド名 | 型 | 説明 |
|---|---|---|
| `generation` | integer | 世代番号（単調増加が原則） |
| `timestamp` | string (ISO 8601) | 記録時刻 |
| `commit_sha` | string | 対応するgit commit SHA |
| `detector_hash` | string | 昇格後の検出器コードのSHA256ハッシュ（空不可） |
| `previous_detector_hash` | string | 直前世代の検出器ハッシュ（rollback検証用） |
| `score` | number | フィットネススコア |
| `previous_score` | number | 直前世代のスコア（スコア改善の検証用） |
| `passed_adoption_gate` | boolean | 採用ゲートを通過したか |
| `rejection_reasons` | array of string | 不採用理由のリスト（passed=falseの場合は必須） |
| `changed_lines` | integer | 変更行数 |
| `code_chars` | integer | 候補コードの文字数 |
| `fitness_summary` | object | 適合度評価のサマリ |
| `fitness_summary.true_positive` | integer | 真陽性数 |
| `fitness_summary.false_positive` | integer | 偽陽性数 |
| `fitness_summary.true_negative` | integer | 真陰性数 |
| `fitness_summary.false_negative` | integer | 偽陰性数 |
| `fitness_summary.total_cases` | integer | 総テストケース数 |
| `fitness_summary.fp_rate` | number | 偽陽性率 |
| `fitness_summary.fn_rate` | number | 偽陰性率 |
| `ast_policy_ok` | boolean | ASTポリシーを通過したか |
| `regression_passed` | boolean | リグレッションテストを全件通過したか |
| `source_mode` | string (enum) | 変異提案の生成元モード（下記参照） |
| `audit_gate_decision` | string (enum) | 監査ゲートの決定（下記参照） |
| `human_owner_approval` | boolean or null | Human Ownerが承認したか（null=未確認） |
| `rationale` | string | この昇格/拒否/rollbackの理由説明 |

### `source_mode` の値

| 値 | 意味 |
|---|---|
| `noop` | 変異なし（スケジュール実行デフォルト） |
| `offline-sample` | ビルトインサンプルパッチを使用（APIキー不要） |
| `gemini-paid-credit` | Gemini 有料クレジットAPIを使用 |
| `rollback` | rollback操作による世代復元 |
| `backtrack` | backtrack操作による前世代復帰 |

### `audit_gate_decision` の値

| 値 | 意味 |
|---|---|
| `APPROVE` | すべての採用ゲートを通過し、昇格を承認 |
| `REQUEST_CHANGES` | 一部条件を満たさず、変更要求 |
| `BLOCK` | 安全上の問題があり、昇格を阻止 |

---

## Integrity rules

以下の整合性ルールを将来の history 記録に適用する。

### 世代番号の整合性

- `generation` は単調増加が原則とする
- rollback / backtrack 時に `generation` が減少する場合は、`source_mode: rollback` または `source_mode: backtrack` と明示的な `rationale` を必要とする
- 世代番号の飛びや重複は不整合としてフラグを立てる

### ハッシュの整合性

- `detector_hash` は空文字であってはならない
- `detector_hash` は `null` であってはならない
- フィールドが存在する場合、有効なハッシュ文字列（16進数、非空）でなければならない

### 採用ゲートの整合性

- `passed_adoption_gate=true` の場合、以下のフィールドが必要:
  - `score`（数値）
  - `fitness_summary`（オブジェクト）
  - `ast_policy_ok: true`
  - `regression_passed: true`
- `passed_adoption_gate=false` の場合、以下のフィールドが必要:
  - `rejection_reasons`（空でないリスト）

### Rollback / Backtrack の整合性

- rollback / backtrack record は通常の promote record と区別する（`source_mode` フィールドで識別）
- rollback / backtrack 時も `detector_hash` は必須
- rollback / backtrack の結果は新しい history record として追記する（既存record削除禁止）

### API usage ledger との分離

- `data/api_usage_ledger.json` は `data/evolution_history.json` とは別物である
- API usage ledger は evolution history の rollback / backtrack 操作で巻き戻してはならない
- API 使用量記録の整合性は evolution history の整合性とは独立して管理する

### 追記原則

- history record は削除せず、追記を基本とする
- 記録の遡及修正は禁止（必要な訂正は新しい record として追記する）
- 欠損・破損・JSON不正はfail-closedで扱う

---

## Failure handling

### fail-closed の原則

history が壊れている場合、promote / rollback / backtrack を進めてはならない。

- historyファイルが**存在しない**場合: **BLOCK**（promote拒否・処理中断）— 欠損historyを自動初期化・上書きしてはならない
- historyファイルがJSONとして読めない場合 (**malformed JSON**): **BLOCK**（処理中断）— 破損historyを [] で上書きしてはならない
- **top-level が list でない場合**（dict / null / string / number 等）: **BLOCK** — 不正構造のhistoryを上書きしてはならない
- historyファイルが**読み取り不能**（権限エラー等）な場合: **BLOCK**
- 必須フィールドが欠損している場合: 将来の自動処理はfail-closed
- 不明な record type は安全側に倒す（BLOCK）
- 不整合を検出した場合: Human Owner 確認が必要

**promote が fail-closed になる場合の挙動**:

- `promote_candidate.py` は evolution_history.json の読み込みに失敗した場合、promote を拒否すること
- exit code は non-zero
- JSON output mode では機械可読な error を返すこと
- **破損・欠損・非list の evolution_history.json を [] で初期化・上書きしてはならない**
- promote 失敗時に `core/detector.py` / `data/genome.json` / `data/evolution_history.json` / `README.md` を変更してはならない
- promote 失敗理由に "evolution_history" / "fail-closed" / "malformed" / "missing" 等が含まれること

### 欠損フィールドの扱い

- Phase 2-C 時点の現行historyは旧スキーマで記録されており、新スキーマの必須フィールドが欠損している場合がある
- 現行historyに対しては「壊れていないことの最低限確認」に留める
- 将来の新規record追記時から新スキーマを適用する

### 不整合検出時のフロー

```
整合性チェック失敗
    ↓
Human Owner への通知
    ↓
Human Owner の確認・判断
    ↓
（修正が必要な場合）修正内容を新規recordとして追記
    ↓
再チェック通過後にpromote / rollback / backtrackを許可
```

---

## Relationship with rollback/backtrack

rollback / backtrack は `EVOLUTION_HISTORY_AUDIT.md` の記録仕様に従う。

### 記録の継続性

- rollback / backtrack 実行時も**過去の record は削除しない**
- rollback / backtrack の結果は**新しい history record として追記する**
- この追記記録には `source_mode: rollback` または `source_mode: backtrack` を設定する

### API usage ledger の不可逆性

- `data/api_usage_ledger.json` は**絶対に巻き戻さない**
- API 使用量は rollback / backtrack 操作に関わらず、消費済み記録として保持する
- これは課金・監査の証跡として不可逆である

### rollback / backtrack recordの必須フィールド

rollback / backtrack 操作を記録する場合、以下を必須とする:

- `generation`（世代番号）
- `timestamp`（実行時刻）
- `detector_hash`（復元後の検出器ハッシュ）
- `previous_detector_hash`（rollback前の検出器ハッシュ）
- `source_mode: rollback` または `source_mode: backtrack`
- `rationale`（rollback/backtrackの理由）
- `human_owner_approval: true`（Human Ownerの明示的承認が必要）

### 設計参照

rollback / backtrack の詳細な設計は [`docs/ROLLBACK_BACKTRACK_DESIGN.md`](./ROLLBACK_BACKTRACK_DESIGN.md) を参照すること。

---

## Non-goals

Phase 2-C では以下を実施しない。

| 対象外項目 | 理由 |
|---|---|
| evolution_history 自動修復 | 自動修復は監査証跡を損なうリスクがある。Phase 2-C では仕様定義のみ |
| promote 処理変更 | 実装変更はPhase 3以降で行う |
| rollback / backtrack 実装 | 設計は Phase 2-B で完了済み。CLI実装はPhase 3以降 |
| workflow 変更 | `.github/workflows/*` の変更は行わない |
| API 接続 | Phase 2 中は API 未接続を維持する |
| Gemini API 呼び出し | `live_model_enabled=false` を維持する |
| `live_model_enabled=true` | Phase 3 以降で Human Owner の判断のもと実施する |
| GitHub Secrets 操作 | `GEMINI_API_KEY` はリポジトリ内に含めない |
| offensive 機能追加 | このプロジェクトは防御専用である |

---

## Related documents

- [`data/evolution_history.json`](../data/evolution_history.json) — 進化履歴（監査対象）
- [`data/api_usage_ledger.json`](../data/api_usage_ledger.json) — API使用量台帳（evolution historyと別物、巻き戻し禁止）
- [`docs/ROLLBACK_BACKTRACK_DESIGN.md`](./ROLLBACK_BACKTRACK_DESIGN.md) — rollback / backtrack 設計文書（Phase 2-B）
- [`docs/PHASE_2_PLAN.md`](./PHASE_2_PLAN.md) — Phase 2 計画文書
- [`docs/AUDIT_CHARTER.md`](./AUDIT_CHARTER.md) — GPT Audit Gate 憲章

---

*このドキュメントは Project Cyber-Immunizer の Phase 2-C: Evolution History Audit 設計を記録します。*  
*作成日: 2026-05-26*
