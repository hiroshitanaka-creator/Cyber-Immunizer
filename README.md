# 🧬 Project Cyber-Immunizer

> **現実世界のサイバー脅威の進化スピードに対し、人間のエンジニアによるパッチ開発の限界を突破する。**
> 不特定の脅威を自動検知し、自律的に防御コードを自己変異・適応させ続ける、世界初の「デジタル自律免疫システム」を確立する。

[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Defensive Only](https://img.shields.io/badge/scope-defensive--only-green.svg)](#安全方針)

---

## 概要

**Cyber-Immunizer** は、LLM（大規模言語モデル）を活用して防御コードを自律的に進化させる研究プロジェクトです。生物の免疫システムが未知の病原体に適応するように、このシステムは新たな脅威パターンに対して検出ロジックを自動的に変異・評価・採用します。

人間のエンジニアがパッチを書いてデプロイするサイクルは、現代の脅威の進化速度に追いつけません。Cyber-Immunizer はその課題に対し、以下を自動化します：

1. **脅威の観測** — ローカルのテストコーパスから脅威パターンを読み込む
2. **変異の提案** — LLM が防御ロジックの改善案を JSON 形式で出力する
3. **安全な評価** — AST検証 + サブプロセス隔離 + タイムアウトで候補を評価する
4. **条件付き昇格** — 全ての採用ゲートを通過した候補のみを本番ロジックに反映する

> ⚠️ これはローカルファーストの研究スキャフォールドです。本番WAFや実トラフィックへの接続は行いません。

---

## 安全方針

このプロジェクトは**防御専用**です。以下の制約は交渉の余地がありません。

| ✅ 許可されること | ❌ 行わないこと |
|---|---|
| 検出ロジックの変異・評価 | 攻撃コードの生成 |
| ローカルリクエストのシミュレーション | 実トラフィックの傍受 |
| 静的テストケースによる検証 | 資格情報の窃取ロジック |
| ASTポリシーによる安全検証 | マルウェア・持続性・回避技術 |
| サブプロセス隔離での候補実行 | ネットワーク越しの攻撃スキャン |
| リグレッションテストによる品質保証 | 実際のエクスプロイト実行 |

テストペイロードはすべて**不活性な静的文字列**であり、検出器の動作確認のみに使用されます。

---

## アーキテクチャ

```
┌────────────────────────────────────────────────────────────────────┐
│                    CYBER-IMMUNIZER 進化ループ                       │
│                                                                    │
│  ① MONITOR / ANALYZE（観測・分析）                                  │
│     intelligence/threat_feeds.py                                  │
│     └── data/active_threats.json から脅威レコードを読み込む          │
│                                                                    │
│  ② PROPOSE（変異提案）                                              │
│     scripts/propose_mutation.py                                   │
│     ├── LLM に防御ロジックの改善を JSON で依頼                       │
│     ├── max_model_requests_per_run でAPI呼び出し数を制限             │
│     └── 出力: .cyber_immunizer/mutation_patch.json                 │
│                                                                    │
│  ③ EVALUATE（評価）                                                 │
│     scripts/apply_mutation.py   → 候補ファイルを生成                │
│     scripts/validate_mutation.py → ASTポリシー検証                 │
│     scripts/evaluate_candidate.py → サブプロセスで隔離評価          │
│     core/fitness.py             → 適合度レポート生成                │
│     └── 採用ゲート: リグレッション通過率・FP率・スコア改善             │
│                                                                    │
│  ④ PROMOTE（昇格）                                                  │
│     scripts/promote_candidate.py                                  │
│     ├── core/detector.py を更新                                    │
│     ├── data/genome.json を更新                                    │
│     ├── data/evolution_history.json に追記                         │
│     └── README ステータスブロックを更新                              │
└────────────────────────────────────────────────────────────────────┘
```

### なぜ生成コードを信頼しないのか

LLM の出力はユーザー入力と同様に**信頼できない外部データ**として扱います。

- 候補コードは `exec()` / `eval()` で実行しない
- 候補コードはサブプロセスで実行し、シークレットや書き込み権限を持たせない
- ASTポリシーが `os` / `subprocess` / `socket` / `eval` / `exec` / dunder属性などを事前に拒否する
- 誤拒否（過保守）は許容する。誤受理（過緩容）は許容しない

---

## プロジェクト構成

```
Cyber-Immunizer/
├── core/
│   ├── policy.py           # ASTポリシーの唯一の正典（validate_mutation.py / fitness.py が共有）
│   ├── types.py            # イミュータブルなデータクラス群（MappingProxyType使用）
│   ├── detector.py         # 検出器インターフェース（変異境界マーカーあり）
│   ├── fitness.py          # 決定論的な適合度評価エンジン（レイテンシはスコア外）
│   └── test_attacker.py    # ローカルリクエストシミュレーター（攻撃器ではない）
├── data/
│   ├── benign_requests.json    # 無害なリクエストのテストケース
│   ├── attack_requests.json    # 攻撃パターンのテストケース（不活性文字列）
│   ├── regression_cases.json   # リグレッションテストケース
│   ├── active_threats.json     # 脅威レコード（安全なスタブ）
│   ├── genome.json             # 現世代のメタデータ
│   ├── evolution_history.json  # 進化の全履歴
│   └── api_usage_ledger.json   # Gemini API 使用量台帳（gemini-paid-credit モード）
├── docs/
│   ├── AI_ENTRYPOINT.md                        # AI作業開始時の入口（task別参照先・status label定義）
│   ├── audit_gate/                             # docs/audit_gate/
│   │   ├── README.md                           # docs/audit_gate/README.md — Audit Gate protocol群の索引
│   │   ├── PULLBACK_PROMPT.md                  # docs/audit_gate/PULLBACK_PROMPT.md — GPT引き戻し用の短縮プロンプト
│   │   ├── PR_AUDIT_PROTOCOL.md                # docs/audit_gate/PR_AUDIT_PROTOCOL.md — PR監査・merge判断の詳細手順
│   │   ├── TASK_PROMPT_PROTOCOL.md             # docs/audit_gate/TASK_PROMPT_PROTOCOL.md — タスクプロンプト構築ルール（Task Prompt Gate v2 / Source Evidence）
│   │   ├── THREAD_HANDOFF_PROTOCOL.md          # docs/audit_gate/THREAD_HANDOFF_PROTOCOL.md — 新スレッド引き継ぎプロンプト構築・受領ルール
│   │   ├── TOOL_EXECUTION_ANOMALY_PROTOCOL.md  # docs/audit_gate/TOOL_EXECUTION_ANOMALY_PROTOCOL.md — tool failure / blocked / fallback / low-level GitHub操作の報告ルール
│   │   └── CHANGELOG.md                        # docs/audit_gate/CHANGELOG.md — Audit Gate運用教訓（PR #33/#34/#36/#35/#28 由来）
│   ├── AUDIT_CHARTER.md                        # GPT Audit Gate 憲章（役割・カテゴリ・決定基準・Phase 2/3 transition rule）
│   ├── PHASE_1_BASELINE.md                     # Phase 1 完了状態の固定記録（Safety invariants・Exit criteria）
│   ├── PHASE_2_PLAN.md                         # Phase 2 計画文書（historical）
│   ├── ROLLBACK_BACKTRACK_DESIGN.md            # rollback/backtrack 設計文書（Phase 2-B: design-only）
│   ├── EVOLUTION_HISTORY_AUDIT.md              # evolution history 監査仕様（Phase 2-C: design and audit spec only）
│   ├── OFFLINE_SAMPLE_PROMOTE_SEPARATION.md    # offline-sample dry-run / promote 分離設計（Phase 2-D: design-only）
│   ├── API_ACTIVATION_CHECKLIST.md             # API有効化チェックリスト・GEMINI_API_KEY用語正本
│   ├── PHASE_2_COMPLETION_CHECKPOINT.md        # Phase 2完了チェックポイント・pre-Phase-3現在状態
│   ├── PHASE_3_GO_NO_GO_CHECKLIST.md           # Phase 3 activation前のGo/No-Go readiness audit
│   ├── PHASE_2_5_CLOSEOUT_AUDIT.md             # Phase 2.5 hardening closeout audit（PR #46–#53 ledger）
│   ├── REPLACEMENT_CODE_STATIC_VALUE_CHECKS_SPEC.md  # X-007 static value-check policy spec（PR #69 frozen / PR #73 で実装済み）
│   ├── human用roadmap/
│   │   └── phase3_to_phase7_roadmap.md         # Project Owner roadmap for Phase 3–7（thread handoff）
│   └── API_ACTIVATION_RUNBOOK.md               # API有効化手順書（Phase 3 runbook）
├── intelligence/
│   └── threat_feeds.py     # 脅威インテリジェンスモジュール（スタブ）
├── scripts/
│   ├── validate_mutation.py    # ASTポリシー検証
│   ├── apply_mutation.py       # 変異パッチの適用
│   ├── evaluate_candidate.py   # サブプロセスによる候補評価
│   ├── promote_candidate.py    # 採用ゲート通過時の昇格
│   ├── propose_mutation.py     # LLM変異提案（noop/offline-sample/live-model/paid-credit）
│   ├── api_budget.py           # API 予算管理（標準ライブラリのみ、fail-closed）
│   ├── update_readme.py        # READMEステータスブロック更新
│   ├── validate_audit_evidence.py  # PR監査の証拠台帳を機械検証（PR_AUDIT_PROTOCOL の Audit Evidence Ledger）
│   ├── build_audit_packet.py   # Audit Packet 収集・正規化（機械監査ゲート layer 0）
│   └── audit_policy_engine.py  # APPROVE可否の機械計算（AUDIT_PACKET_PROTOCOL）
├── schemas/
│   └── gpt_audit_packet.schema.json  # Audit Packet スキーマ（machine_facts / judgment_inputs 分離）
├── tests/
│   ├── test_contract.py              # 検出器インターフェース契約テスト（20件）
│   ├── test_ast_policy.py            # ASTポリシー検証テスト（32件）
│   ├── test_fitness.py               # 適合度評価テスト（22件）
│   ├── test_mutation_boundaries.py   # 変異境界テスト（12件）
│   ├── test_promote_candidate.py     # 昇格ゲートテスト（tmp_path使用、実ファイル非破壊）（15件）
│   ├── test_types.py                 # Request イミュータビリティテスト（24件）
│   ├── test_gemini_integration.py    # Gemini API 統合テスト（131件、モック使用）
│   ├── test_api_budget.py            # API 予算管理テスト（51件）
│   ├── test_gemini_paid_credit.py    # Gemini 有料クレジットモードテスト（48件）
│   ├── test_audit_docs.py            # 監査ドキュメント存在・内容テスト（36件）
│   ├── test_workflow.py              # immunization_loop ワークフロー構造テスト（54件）
│   ├── test_ci_workflow.py           # CI ワークフロー構成テスト（13件）
│   ├── test_preflight_mode.py        # gemini-paid-credit-preflight モードテスト（39件）
│   ├── test_preflight_workflow.py    # preflight ワークフロー統合テスト（14件）
│   ├── test_api_activation_docs.py   # API Activation Runbook 存在・内容テスト（19件）
│   ├── test_phase1_baseline_docs.py  # Phase 1 baseline 文書存在・Safety invariants テスト（25件）
│   ├── test_phase2_plan_docs.py      # Phase 2 計画文書・定義整合性テスト（28件）
│   ├── test_phase2_progress_docs.py  # Phase 2-A/B/C/D 完了・Phase 2-E next 進捗記載テスト
│   ├── test_offline_sample_promote_separation_docs.py  # offline-sample dry-run / promote 分離設計文書の検証（Phase 2-D）
│   └── test_pyproject.py             # pyproject.toml 設定・依存関係テスト（15件）
├── .github/
│   ├── PULL_REQUEST_TEMPLATE.md  # PR 監査チェックリスト（GPT Audit Gate 用）
│   └── workflows/
│       ├── immunization_loop.yml # propose / evaluate / promote 分離ワークフロー
│       └── gpt-audit-gate.yml    # 機械監査ゲート required check（Audit Packet をCIで生成・評価）
├── pyproject.toml
├── LICENSE
└── README.md
```

---

## コアコンセプト

### 変異境界マーカー

`core/detector.py` には以下のマーカーが含まれています：

```python
def inspect_request(request: Request) -> DetectionResult:
    # === MUTATION_START ===
    # ↑ここから↓ここまでのみ、自動ツールによる変更が許可される
    ...
    # === MUTATION_END ===
```

マーカーの外側は**不変のインターフェース契約**であり、変異ツールはこの領域を変更できません。

### 変異パッチ形式

```json
{
  "mutation_rationale": "変異の理由（短い説明）",
  "target_threats": ["THREAT-2024-002"],
  "expected_improvement": "期待される改善内容",
  "risk": "リスクの概要",
  "replacement_code": "# MUTATION_START〜MUTATION_END の間に入るPythonコード"
}
```

### 採用ゲート

以下の**全条件**を満たした候補のみが昇格されます：

| ゲート条件 | 基準値 |
|---|---|
| 構文チェック | `syntax_ok == True` |
| ASTポリシー | `ast_policy_ok == True` |
| インターフェース契約 | `contract_ok == True` |
| タイムアウト | `timed_out == False` |
| 例外数 | `exception_count == 0` |
| リグレッション通過率 | `== 1.0`（全件通過） |
| 偽陽性率 | `fp_rate ≤ max_fp_rate`（デフォルト 0.05） |
| レイテンシ（ハードゲート） | `avg_latency_ms ≤ max_avg_latency_ms`（デフォルト 100ms） |
| スコア改善 | `score > 現世代のbest_score` |

> レイテンシはスコアに含まれませんが、独立したハードゲートとして採用可否に影響します。

### フィットネススコア計算式

```
score =
  1000 × tp_rate
- 2000 × fp_rate
- 1500 × fn_rate
-   50 × exception_count
- 0.02 × code_chars
-   10 × changed_lines
```

**スコアは決定論的**です。`avg_latency_ms` はスコアに含まれません。レイテンシは採用ゲートの別途ハードリミット（`genome.json::max_avg_latency_ms`）で管理されます。これにより、同一の候補と同一のテストデータで評価した場合、実行環境の速度に関わらず常に同一のスコアが得られます。

偽陽性（FP）のペナルティが最も大きく（係数2000）、低FPを優先する設計です。

---

## セットアップ・実行方法

### 必要要件

- Python 3.11 以上
- pytest（開発用）

```bash
# リポジトリをクローン
git clone https://github.com/hiroshitanaka-creator/Cyber-Immunizer.git
cd Cyber-Immunizer

# 依存関係をインストール
pip install -e ".[dev]"
```

### ローカルコマンド

```bash
# テストスイートを全件実行
python -m pytest

# ベースライン検出器のAST検証
python scripts/validate_mutation.py --candidate core/detector.py --json

# ベースライン検出器の適合度評価
python -m core.fitness --candidate core/detector.py --baseline --json

# オフラインサンプル変異を提案（APIキー不要）
python scripts/propose_mutation.py --offline-sample --json

# 提案された変異パッチを適用
python scripts/apply_mutation.py \
    --patch .cyber_immunizer/mutation_patch.json \
    --base core/detector.py \
    --out .cyber_immunizer/candidate_detector.py \
    --json

# 候補をサブプロセスで評価（5秒タイムアウト）
python scripts/evaluate_candidate.py \
    --candidate .cyber_immunizer/candidate_detector.py \
    --timeout 5 \
    --json

# 採用ゲートを通過した候補を昇格
python scripts/promote_candidate.py \
    --candidate .cyber_immunizer/candidate_detector.py \
    --report .cyber_immunizer/fitness_report.json \
    --json

# READMEのステータスブロックを更新
python scripts/update_readme.py
```

### LLM連携（Gemini）

ライブ API 呼び出しは**明示的なオプトイン**が必要です。複数の安全ゲートをすべてクリアした場合のみ API が呼び出されます。

#### 推奨コマンド

```bash
# 推奨: オフラインサンプル（APIキー不要、デフォルト推奨）
python scripts/propose_mutation.py --offline-sample --json

# ライブモデル呼び出し（明示的ダブルオプトイン必須）
export GEMINI_API_KEY=your_api_key_here
python scripts/propose_mutation.py --live-model --allow-live-model --json

# noop モード（パッチ生成なし、スケジュール実行のデフォルト）
python scripts/propose_mutation.py --noop --json
```

#### Gemini API フリーティア運用ガイド

> ⚠️ **重要: Google AI Pro アプリのサブスクリプションと Gemini API プロジェクトクォータは別物です。**
> Google One AI Premium / Google AI Pro のアプリサブスクリプションは Gemini アプリ（gemini.google.com）で使用するものであり、API プロジェクトの無料クォータとは独立しています。API コールには別途 Google AI Studio / Google Cloud のプロジェクトが必要です。

| 項目 | 推奨設定 |
|---|---|
| **モデル選択** | Flash / Flash-Lite 系（例: `gemini-2.0-flash`）を使用。Pro Preview は避ける |
| **free_tier_only** | `true`（デフォルト）— Pro 系モデルを自動拒否 |
| **live_model_enabled** | `false`（デフォルト）— 明示的に `true` にするまで API 呼び出し不可 |
| **monthly_api_budget_usd** | `0`（デフォルト）— 無料枠のみ使用 |
| **スケジュール実行** | 常に `noop` モード — 意図しない API コールを防ぐ |

> ⚠️ **プライバシー注意: Gemini API の無料クォータで送信したデータは、Google によるモデル改善に使用される場合があります。**
> シークレット、APIキー、環境変数、プライベートな脆弱性情報、実ユーザーログを絶対にプロンプトに含めないでください。
> このシステムはプロンプト送信前に自動スキャンを実行し、機密トークンを検出した場合は送信を拒否します。

#### 安全ゲート一覧（ライブモード）

| ゲート | 条件 |
|---|---|
| 明示的オプトイン | `--live-model` + `--allow-live-model` の両フラグ必須 |
| API キー | `GEMINI_API_KEY` 環境変数が設定されていること |
| ゲノム設定 | `genome.live_model_enabled == true` |
| リクエスト数制限 | `genome.max_model_requests_per_run <= 1` |
| モデル安全性 | `free_tier_only=true` の場合、`model_name` に `"pro"` を含まないこと |
| グラウンディング無効 | `genome.allow_google_search_grounding == false` |
| コード実行無効 | `genome.allow_code_execution_tool == false` |
| プロンプト長制限 | プロンプト全体が `genome.max_prompt_chars`（デフォルト 12000）以下 |
| プリフライトスキャン | プロンプトに機密トークンが含まれないこと |

#### Gemini へ送信するコンテキストの最小化

Cyber-Immunizer が Gemini へ送信するのは以下の**最小限のコンテキスト**のみです：

| 送信するもの | 内容 |
|---|---|
| 検出器の変異領域コード | `# === MUTATION_START ===` 〜 `# === MUTATION_END ===` の間のコードのみ |
| 検出器インターフェース要約 | 関数シグネチャと戻り値型の説明（静的テキスト） |
| 中和された脅威 ID | `THREAT-2024-001` のような安全な識別子のみ（ペイロード・署名は除外） |

| **絶対に送信しないもの** |
|---|
| シークレット・APIキー・環境変数 |
| フルリポジトリテキスト（`send_repository_full_text: false` で強制） |
| 実ユーザーログ・実トラフィックデータ |
| プライベートな脆弱性情報・CVE詳細 |
| 生のエクスプロイトペイロード（`send_raw_payloads: false` で強制） |

#### Gemini オプション依存関係のインストール

```bash
# ライブモードを使用する場合のみ（通常の pytest 実行には不要）
pip install "cyber-immunizer[gemini]"
# または
pip install "google-genai>=1.0.0" "pydantic>=2.0"
```

通常の `python -m pytest` 実行には `google-genai` は不要です。

---

## Google AI Pro / $10 GenAI & Cloud クレジット戦略

### Google AI Pro の GenAI & Cloud クレジットとは

Google AI Pro（旧 Google One AI Premium）または Google Developer Program への参加により、毎月 $10 の GenAI & Cloud 開発者クレジットが提供される場合があります。このクレジットは **Gemini アプリの使用制限とは別物**です。

> ⚠️ **重要な区別:**
> - **Google AI Pro アプリのサブスクリプション**（gemini.google.com）：Gemini チャットアプリの使用枠
> - **Gemini API プロジェクトクォータ**（Google AI Studio / Cloud Billing）：API 呼び出し用の別枠
>
> API を呼び出すには、Cloud Billing にリンクされた Google Cloud / AI Studio プロジェクトが必要です。

### データプライバシーの重要な注意点

| API 種別 | データの扱い |
|---|---|
| **Gemini API 無料クォータ** | Google によるモデル改善に使用される可能性あり |
| **Gemini API 有料クォータ** | プロンプト・レスポンスはモデル改善に使用されない |

> **Cyber-Immunizer は、有料クォータを使用している場合でも、シークレット・APIキー・環境変数・プライベートな脆弱性情報・実ユーザーログ・フルリポジトリテキスト・生のエクスプロイトペイロードをプロンプトに含めません。**
> プロンプトに含まれるのは：検出器の変異領域コード・検出器インターフェースの要約・中和された脅威IDのみです。

### `gemini-paid-credit` モードの設定と使用方法

#### 前提条件

1. **Google AI Pro の GenAI & Cloud クレジットをアクティベート**
   - Google Developer Program にて確認・有効化
2. **Cloud Billing リンク済みプロジェクトの設定**
   - Google AI Studio または Google Cloud Console でプロジェクトを作成
3. **GEMINI_API_KEY を GitHub Secrets に登録**
4. **`data/genome.json` の設定変更**（レビュー済みコミットで実施）:
   ```json
   { "live_model_enabled": true }
   ```
5. **workflow_dispatch で `mode=gemini-paid-credit` を選択**

#### 推奨ワークフローモード一覧

| モード | 動作 | API 消費 |
|---|---|---|
| `noop`（デフォルト・スケジュール実行） | パッチ生成なし | ゼロ |
| `offline-sample` | ビルトインサンプルパッチを使用 | ゼロ |
| `live-model` | Gemini API 呼び出し（基本フリーティア用） | あり |
| `gemini-paid-credit` | Gemini API 呼び出し（月次・日次予算キャップ付き） | あり（課金） |

#### 予算管理（`data/api_usage_ledger.json`）

`gemini-paid-credit` モードは呼び出しごとにコストを推定し、`data/api_usage_ledger.json` に記録します。

- 月次上限（`monthly_api_budget_usd`）と日次上限（`daily_api_budget_usd`）を超える場合は呼び出しを拒否
- コスト推定は**保守的な過大見積もり**（`ceil(chars / 4)` トークン換算）
- 実際のトークン数は API レスポンスメタデータから取得（利用可能な場合）

#### ローカル実行コマンド

```bash
# 安全なローカル開発（APIキー不要）
python scripts/propose_mutation.py --offline-sample --json

# 有料クレジットモード（明示的ダブルオプトイン + genome 設定が必要）
export GEMINI_API_KEY=your_api_key_here
python scripts/propose_mutation.py --gemini-paid-credit --allow-live-model --json

# noop（スケジュール実行のデフォルト）
python scripts/propose_mutation.py --noop --json
```

#### 安全ゲート一覧（`gemini-paid-credit` モード）

| ゲート | 条件 |
|---|---|
| 明示的オプトイン | `--gemini-paid-credit` + `--allow-live-model` の両フラグ必須 |
| API キー | `GEMINI_API_KEY` 環境変数が設定されていること |
| ライブモード有効 | `genome.live_model_enabled == true` |
| 有料ティア確認 | `genome.require_paid_tier == true` |
| 無料専用モード無効 | `genome.free_tier_only == false` |
| 月次予算 | `genome.monthly_api_budget_usd > 0` かつ月次支出 + 推定コスト ≤ 上限 |
| 日次予算 | `genome.daily_api_budget_usd > 0` かつ日次支出 + 推定コスト ≤ 上限 |
| リクエスト数制限 | `genome.max_model_requests_per_run <= 1` |
| グラウンディング無効 | `genome.allow_google_search_grounding == false` |
| コード実行無効 | `genome.allow_code_execution_tool == false` |
| URL コンテキスト無効 | `genome.allow_url_context == false` |
| フルリポジトリ送信禁止 | `genome.send_repository_full_text == false` |
| 生ペイロード送信禁止 | `genome.send_raw_payloads == false` |
| シークレット送信禁止 | `genome.send_secrets == false` |
| プロンプト長制限 | プロンプト全体が `genome.max_prompt_chars`（デフォルト 12000）以下 |
| プリフライトスキャン | プロンプトに機密トークンが含まれないこと |

---

## Phase 1-C: gemini-paid-credit preflight

### 概要

`gemini-paid-credit-preflight` モードは、実際のGemini API呼び出しを行う前に、Google AI Pro / $10 GenAI & Cloud クレジット運用の準備状態を安全に検証するための事前確認モードです。

**このモードではGemini APIを絶対に呼びません。**

### 確認項目

| 確認項目 | 内容 |
|---|---|
| `data/genome.json` 読み込み | ファイルが存在し読める |
| `core/detector.py` 読み込み | ファイルが存在し読める |
| `GEMINI_API_KEY` 存在確認 | 環境変数の存在のみ確認（値は絶対に表示しない） |
| `genome.api_mode` | `"gemini_paid_credit"` であること |
| `genome.model_provider` | `"gemini"` であること |
| `genome.live_model_enabled` | **`false` であること**（まだ実API実行前なので `true` なら失敗） |
| `genome.require_paid_tier` | `true` であること |
| `genome.free_tier_only` | `false` であること |
| `genome.monthly_api_budget_usd` | `> 0` であること |
| `genome.daily_api_budget_usd` | `> 0` であること |
| `genome.max_model_requests_per_run` | `<= 1` であること |
| `allow_google_search_grounding` | `false` であること |
| `allow_code_execution_tool` | `false` であること |
| `allow_url_context` | `false` であること |
| `send_repository_full_text` | `false` であること |
| `send_raw_payloads` | `false` であること |
| `send_secrets` | `false` であること |
| `data/api_usage_ledger.json` | 存在し `load_ledger()` で読める |
| プロンプト構築 | エラーなく構築できる |
| プロンプト長 | `max_prompt_chars` 以内 |
| シークレットスキャン | `_preflight_secret_scan` を通過する |
| コスト推定 | `api_budget.estimate_cost_usd` で推定できる |
| 予算確認 | `api_budget.assert_budget_available` が `true` を返す |

### 実行方法

**workflow_dispatch で実行（推奨）:**

```
GitHub Actions → Cyber-Immunizer Evolution Loop
→ Run workflow → mode: gemini-paid-credit-preflight
```

**ローカルで実行（GEMINI_API_KEY必須）:**

```bash
export GEMINI_API_KEY=your_api_key_here  # 値はログに出ない
python scripts/propose_mutation.py --gemini-paid-credit-preflight --json
```

### 期待される出力 (JSON)

```json
{
  "success": true,
  "mode": "gemini-paid-credit-preflight",
  "api_call_performed": false,
  "patch_path": null,
  "ledger_written": false,
  "live_model_enabled": false,
  "gemini_api_key_present": true,
  "monthly_api_budget_usd": 10.0,
  "daily_api_budget_usd": 0.25,
  "estimated_next_cost_usd": 0.000000,
  "budget_available": true,
  "warnings": []
}
```

### workflow_dispatch での期待結果

| ジョブ | 期待結果 |
|---|---|
| **Propose Mutation** | ✅ success |
| **Persist API Usage Ledger** | ⏭ skipped（ledger未変更） |
| **Finalize Propose Status** | ✅ success |
| **Apply and Evaluate Candidate** | ⏭ skipped（patch未生成） |
| **Promote Candidate** | ⏭ skipped（candidate未評価） |

### preflight後の手順

preflight が成功した場合、以下を Project Owner が確認・実施してください：

1. **Billing確認** — Cloud Billing リンク済みプロジェクトへのアクセスを確認
2. **Secret確認** — GitHub Secrets に `GEMINI_API_KEY` が正しく登録されていることを確認
3. **`live_model_enabled` 設定** — レビュー済みコミットで `data/genome.json` の `live_model_enabled` を `true` に変更
4. **`mode=gemini-paid-credit` で実行** — workflow_dispatch で実際のAPI呼び出しを実施

> ⚠️ preflight が成功しても、自動的にAPIを呼び出すことはありません。`live_model_enabled=true` への変更と `gemini-paid-credit` モードの手動実行は、Project Owner の判断と操作が必要です。

### Phase 1-D: API Activation Runbook

API キー登録から実際の Gemini API 呼び出し有効化までの詳細手順は **[docs/API_ACTIVATION_RUNBOOK.md](docs/API_ACTIVATION_RUNBOOK.md)** を参照してください。

| 重要ルール | 内容 |
|---|---|
| **APIキー保管場所** | `GEMINI_API_KEY` はリポジトリに保存せず **GitHub Secrets のみ**に登録する |
| **`live_model_enabled=true` のタイミング** | preflight 成功後、**レビュー済みPR**でのみ変更する |
| **cron 実行禁止** | `gemini-paid-credit` は **workflow_dispatch の手動実行のみ** |

---

## GPT Audit Gate

すべての PR はマージ前に **GPT Audit Gate** レビューを通過しなければなりません。詳細は `docs/AUDIT_CHARTER.md` を参照してください。

| 役割 | 担当 |
|---|---|
| **GPT Audit Gate** | 6カテゴリの構造的レビュー（アーキテクチャ・セキュリティ・フィットネス・コスト・ドキュメント・法的） |
| **Project Owner** | 最終マージ判断（GPT の推薦を覆す権限あり） |
| **Claude Code** | 実装・テスト・Audit Gate 支援情報の提供 |

Audit Gate の決定: **APPROVE / REQUEST CHANGES / BLOCK**  
PR テンプレート（`.github/PULL_REQUEST_TEMPLATE.md`）に GPT Audit Gate レポートの貼り付け欄があります。

---

## CI ワークフロー構成

このリポジトリには2つの GitHub Actions ワークフローがあります。用途・権限・動作がまったく異なります。

| 項目 | `ci.yml`（通常CI） | `immunization_loop.yml`（進化ループ） |
|---|---|---|
| **トリガー** | `push` / `pull_request` | `workflow_dispatch` / `schedule`（毎日 02:00 UTC） |
| **目的** | コードの健全性確認（テスト・AST検証・スモークテスト） | 検出器の自律進化（propose → evaluate → promote） |
| **`permissions`** | `contents: read`（読み取り専用） | propose/evaluate: `read` / persist-ledger/promote: `write` |
| **`GEMINI_API_KEY`** | ❌ 使用しない | ⚠️ `propose` ジョブのみ（手動モード選択時のみ） |
| **`promote_candidate.py`** | ❌ 呼ばない | ✅ `promote` ジョブで呼ぶ（採用ゲート通過時のみ） |
| **`git commit` / `git push`** | ❌ しない | ✅ `persist-ledger` / `promote` ジョブでのみ実施 |
| **`live-model` / `gemini-paid-credit`** | ❌ 実行しない | ✅ `workflow_dispatch` で手動選択時のみ |
| **`timeout-minutes`** | `10`（ジョブ全体） | 設定なし（進化サイクルは長時間になりうる） |

### `ci.yml` — 通常 CI（read-only）

- **`push` / `pull_request` で自動実行**される軽量な安全チェックです
- `contents: read` のみ — リポジトリへの書き込みは一切行いません
- `GEMINI_API_KEY` は環境変数に存在しません
- `promote_candidate.py` は呼び出しません
- `git commit` / `git push` はしません
- `live-model` / `gemini-paid-credit` は実行しません
- 実行内容: `pytest` → `validate_mutation` → `core.fitness --baseline` → `propose_mutation --noop` → `propose_mutation --offline-sample` → `apply_mutation` → `evaluate_candidate --soft-reject`

### `immunization_loop.yml` — 進化ループ（workflow_dispatch / schedule）

`.github/workflows/immunization_loop.yml` は **propose / persist-ledger / finalize-propose-status / evaluate / promote** の5ジョブを意図的に分離しています。

| ジョブ | 権限 | シークレット | 生成コードを実行するか | 責務 |
|---|---|---|---|---|
| `propose` | `contents: read` | GEMINI_API_KEY（任意） | ❌ | 変異提案・ledger artifact生成・exit code出力（`propose_failed`） |
| `persist-ledger` | `contents: write` | GITHUB_TOKEN のみ | ❌ | **ledgerのみ**をcommit（candidate採用/不採用に関係なく） |
| `finalize-propose-status` | `contents: none` | なし | ❌ | ledger永続化後にpropose失敗をworkflow失敗として表現 |
| `evaluate` | `contents: read` | なし | ✅ する（サブプロセス隔離） | 候補評価 |
| `promote` | `contents: write` | GITHUB_TOKEN のみ | ❌ | 検出器・genome・READMEのcommit（`persist-ledger`完了後のみ） |

**`persist-ledger` ジョブは `propose` 直後に実行されます。** `propose_mutation.py` がAPI呼び出し後に失敗しても、`set +e` によりledger artifact uploadには必ず到達します。candidate が `evaluate` で不採用になっても、API使用記録は必ずリポジトリに永続化されます。これにより月次・日次 budget cap が fail-open になりません。

**`propose` 失敗はledger永続化後に `finalize-propose-status` ジョブがworkflow失敗として表現します。** ledger永続化とpropose失敗の表現を分離することで、API使用記録が確実に保存されます。

**`promote` は `persist-ledger` の完了を待ってから実行されます。** これにより `persist-ledger` と `promote` が同一branchへ並列write commitする競合を防ぎます。

**生成コードが実行されるジョブには書き込み権限もモデルAPIシークレットも付与しません。**  
**`persist-ledger` と `promote` は GITHUB_TOKEN（リポジトリへの書き込み用）のみを保持し、GEMINI_API_KEY は持ちません。**  
**`persist-ledger` は候補detector・変異パッチをダウンロードしません。ledger ファイルのみを扱います。**

### ワークフロートリガーとモード

`workflow_dispatch` は `mode` 入力を受け付けます：

| モード | 動作 |
|---|---|
| `noop` | propose / evaluate / promote をすべてスキップ（ブランチテスト用） |
| `offline-sample` | 組み込みサンプルパッチを使用（APIキー不要） |
| `live-model` | Gemini API を呼び出す（GEMINI_API_KEY 必須） |
| `gemini-paid-credit` | Gemini API を呼び出す（月次・日次予算キャップ付き、Google AI Pro クレジット用） |

**スケジュール実行（毎日 02:00 UTC）は常に `noop` モード**で動作します。意図しないAPI呼び出しを防ぎ、`offline-sample` や `live-model` は手動 `workflow_dispatch` でのみ使用します。

### 採用ゲートと soft-reject

`evaluate` ジョブは `--soft-reject` フラグ付きで実行されます。これにより：
- **ツール障害**（AST違反・タイムアウト・クラッシュ）→ ジョブ失敗（exit 1）
- **採用ゲート失敗**（スコア不足・FP超過など）→ ジョブ成功（exit 0）、`passed_adoption_gate=false`

`promote` ジョブは `passed_adoption_gate == 'true'` のときのみ実行されます。候補が採用ゲートで拒否されることは**正常な動作**であり、ワークフローのエラーではありません。

昇格成功時のコミット対象ファイル：
- `core/detector.py`
- `data/genome.json`
- `data/evolution_history.json`
- `README.md`

---

## テスト構成

| テストファイル | 件数 | カバレッジ |
|---|---|---|
| `test_contract.py` | 20 | 検出器の関数シグネチャ・戻り値型・信頼度範囲・無害リクエストの非ブロック・シンボリック指標の検出 |
| `test_ast_policy.py` | 32 | `os` / `subprocess` / `eval` / `exec` / dunder・type/dir/super/breakpoint等の拒否、安全なコードの受理 |
| `test_fitness.py` | 22 | ベースライン評価、全ブロック器の失敗、全許可器の失敗、リグレッション強制、スコア完全決定論性（レイテンシ除外を検証） |
| `test_mutation_boundaries.py` | 12 | マーカー外の不変性、マーカーの存在、重複マーカーの拒否、マーカー含有コードの拒否、不正パッチの拒否 |
| `test_promote_candidate.py` | 15 | ハッシュ検証・スキーマ検証・採用失敗時の拒否・ast_policy_ok=False時の拒否・fp_rate超過時の拒否（すべて `tmp_path` 使用、実ファイル非破壊） |
| `test_types.py` | 24 | `Request.query` / `Request.headers` の MappingProxyType イミュータビリティ、構築後のソースdict変更の影響なし |
| `test_gemini_integration.py` | 131 | noop・offline-sample・live-model モード、プリフライトスキャン、スキーマ検証、replacement_code 検証（モック使用） |
| `test_api_budget.py` | 51 | トークン推定・月次/日次集計・月次/日次超過拒否・ledger 破損 fail-closed（上書き禁止）・不明モデル保守的コスト |
| `test_gemini_paid_credit.py` | 48 | paid-credit ゲート拒否・予算超過拒否・シークレットスキャン・スキーマ検証・ledger 追記・ledger 書き込み失敗→hard error |
| `test_audit_docs.py` | 36 | AUDIT_CHARTER.md 存在・PR テンプレート存在・BLOCK/REQUEST CHANGES/APPROVE 条件・symbolic indicator 整合性 |
| `test_workflow.py` | 54 | persist-ledger ジョブ存在・権限・if条件に always() 必須・GEMINI_API_KEY 不在・promote の ledger 責務分離・concurrency・propose `set +e` 構造・finalize-propose-status の != success 厳格化・persist-ledger sequencing |
| `test_ci_workflow.py` | 13 | CI ワークフロー構成（read-only 権限・Gemini 不呼び出し・promote 不実行・timeout 設定） |
| `test_preflight_mode.py` | 39 | gemini-paid-credit-preflight モード（GEMINI_API_KEY が GitHub Secrets に存在しない場合 fail-closed・live_model_enabled=false 確認・API未呼び出し） |
| `test_preflight_workflow.py` | 14 | preflight ワークフロー統合（ジョブ構成・権限・シークレット分離・skip 条件） |
| `test_api_activation_docs.py` | 19 | API Activation Runbook 存在・GEMINI_API_KEY 登録禁止・live_model_enabled 手順・cron 禁止・README リンク |
| `test_phase1_baseline_docs.py` | 25 | Phase 1 baseline 文書の存在・Safety invariants 記載・Exit criteria・Phase 2 移行条件 |
| `test_phase2_plan_docs.py` | 28 | Phase 2 計画文書存在・API未接続制約・AUDIT_CHARTER 旧表現不在・README 表現整合性 |
| `test_phase2_progress_docs.py` | — | Phase 2-A/B/C/D 完了・Phase 2-E next の記載検証・Phase 3 未着手／API 未接続の誤表現不在確認 |
| `test_offline_sample_promote_separation_docs.py` | — | offline-sample dry-run / promote 分離設計文書の存在・内容・安全境界・fail-closed 検証（Phase 2-D） |
| `test_pyproject.py` | 15 | pyproject.toml 設定・パッケージメタデータ・依存関係・dev/gemini オプション |

```bash
python -m pytest -v
```

テストはすべて `tmp_path` インジェクションまたはファイルシステム参照（読み取り専用）を使用し、`core/detector.py` や `data/genome.json` などの実リポジトリファイルを変更しません。

---

## Phase 1 Baseline（完了・固定）

**Phase 1 の安全基盤完了状態は [`docs/PHASE_1_BASELINE.md`](docs/PHASE_1_BASELINE.md) に永続的に記録されています。**

| 状態 | 内容 |
|---|---|
| Phase 1 baseline is frozen | `docs/PHASE_1_BASELINE.md` にすべての完了範囲・Safety invariants・Exit criteria が記録されている |
| API is intentionally not connected yet | `GEMINI_API_KEY` は未登録・`live_model_enabled=false` のまま |
| Phase 3 (API activation) starts only after Project Owner decides | GEMINI_API_KEY 登録・`live_model_enabled=true`・実 Gemini API call は Phase 3 以降。Project Owner の明示的決定が必要 |

> ⚠️ **CI テスト・noop・offline-sample・preflight は Phase 1 の範囲で動作確認済みです。**  
> 実際の Gemini API 呼び出しは Phase 3 以降であり、Project Owner の決定なく開始してはなりません。

詳細は [`docs/PHASE_1_BASELINE.md`](docs/PHASE_1_BASELINE.md) および [`docs/AUDIT_CHARTER.md`](docs/AUDIT_CHARTER.md) の Phase transition rule を参照してください。

---

## Phase 2: API未接続運用強化（現在進行中）

**Phase 2 は API を接続しないまま、運用耐性・ドキュメント品質・監査品質を強化するフェーズです。**

| 項目 | 内容 |
|---|---|
| **現在のフェーズ** | Phase 2: API未接続運用強化 |
| **API接続状態** | 未接続（`live_model_enabled=false` を維持） |
| **GEMINI_API_KEY** | 未登録（Phase 3 以降で Project Owner の判断のもと登録） |
| **API接続予定** | Phase 3 以降（Project Owner の明示的決定が必要） |

Phase 2 の計画・実施内容・禁止事項の詳細は **[`docs/PHASE_2_PLAN.md`](docs/PHASE_2_PLAN.md)** を参照してください。

### Phase 2 Progress Checkpoint (as of PR #22 / #23 / #24 / #25 / #26 / Phase 2-E)

Phase 2 API activation checklist: **[`docs/API_ACTIVATION_CHECKLIST.md`](docs/API_ACTIVATION_CHECKLIST.md)**

| Phase item | Status |
|---|---|
| Phase 2-A: README dashboard accuracy improvement | ✅ Completed |
| Phase 2-B: rollback / backtrack design documentation | ✅ Completed |
| Phase 2-C: evolution_history audit specification | ✅ Completed |
| Phase 2-D: offline-sample dry-run / promote separation design | ✅ Completed |
| Phase 2-E: API activation checklist hardening | ✅ Completed |

> ℹ️ **Phase 2 is complete as a readiness milestone.**  
> Phase 2-E (API activation checklist hardening) is completed (docs/tests only).  
> Phase 3 is not started. Phase 3 requires explicit Project Owner decision.  
> API remains not connected. live_model_enabled remains false.

### Phase 2-A: README Dashboard Accuracy Improvement (completed)

README dashboard accuracy improvement was completed in PR #22.

- Status block fields and display accuracy reviewed and updated
- Phase 2 plan document linked from README
- Current phase (Phase 2: API-disconnected operation) explicitly stated

### Phase 2-B: Rollback / Backtrack Design (design-only, completed)

Rollback / backtrack design is documented in **[`docs/ROLLBACK_BACKTRACK_DESIGN.md`](docs/ROLLBACK_BACKTRACK_DESIGN.md)**.

- Phase 2-B is design-only — no rollback automation is implemented yet
- Defines trigger conditions, safety invariants, future CLI design, and audit log fields
- `data/api_usage_ledger.json` is explicitly excluded from rollback/backtrack scope
- dry-run is the default; `--apply` requires Project Owner approval

### Phase 2-C: Evolution History Audit (design and audit spec only)

Evolution history audit design is documented in **[`docs/EVOLUTION_HISTORY_AUDIT.md`](docs/EVOLUTION_HISTORY_AUDIT.md)**.

- Phase 2-C is design and specification only — no implementation changes, no workflow changes, no API connections
- Defines required record fields, integrity rules, fail-closed policy, and relationship with rollback/backtrack
- `data/api_usage_ledger.json` is explicitly excluded from rollback/backtrack scope (never rolled back)

### Phase 2-D: Offline-Sample Dry-run / Promote Separation Design (design-only, completed)

Offline-sample dry-run / promote separation design is documented in **[`docs/OFFLINE_SAMPLE_PROMOTE_SEPARATION.md`](docs/OFFLINE_SAMPLE_PROMOTE_SEPARATION.md)**.

- Phase 2-D is design-only — no workflow changes, no promote implementation, no API connections
- Defines CI smoke path, dry-run evaluation path, and promote path as three clearly separated flows
- offline-sample success is NOT promote approval
- dry-run artifact is NOT promote artifact; dry-run is non-promotable by default
- promote requires explicit Project Owner approval and GPT Audit Gate APPROVE
- CI smoke path is read-only (contents: write なし), no GEMINI_API_KEY, no live_model_enabled=true
- fail-closed: unknown / missing / corrupt artifacts are rejected at promote gate
- `data/api_usage_ledger.json` is not changed in Phase 2-D

### Phase 2-E: API Activation Checklist Hardening (docs/tests only, completed)

API activation checklist is documented in **[`docs/API_ACTIVATION_CHECKLIST.md`](docs/API_ACTIVATION_CHECKLIST.md)**.

- Phase 2-E is docs/tests only — no API connection, no GEMINI_API_KEY registration, no live_model_enabled=true, no Gemini API call
- Documents all pre-activation checks: repository safety, billing/budget, ledger/cost governance, runtime/workflow, privacy/data minimization, promotion/generated code safety
- Defines Project Owner approval gate that must be satisfied before Phase 3 begins
- Defines fail-closed conditions that block Phase 3
- Phase 3 activation must use a dedicated PR reviewed by GPT Audit Gate

> ⚠️ **Phase 2 中は `live_model_enabled=true` への変更・`GEMINI_API_KEY` 登録・実 Gemini API call は行いません。**  
> これらの変更を含む PR は GPT Audit Gate によって BLOCK または REQUEST CHANGES の対象になります。

---

---

## Phase 3: Paid-Credit API 実行待機中

> **⚠️ Phase 3 activation PR (#58–#62) は main に merge 済み。**  
> **paid-credit path は準備完了。過去の paid-credit API call 記録は存在する（`data/api_usage_ledger.json` 参照）。**  
> **gemini-3-flash-preview での controlled paid-credit run は未実行。次のステップ: Project Owner が 1 回だけ手動実行する。**  
> **promote_approved=true はまだ禁止。Apply / Evaluate / Promote の自動昇格はまだ許可しない。**

### PR #60–#62 反映内容

| PR | 変更内容 |
|---|---|
| **PR #60** | 停止済み Gemini 2.0 Flash 系から移行。404 NOT_FOUND 主因の model_name を `gemini-3.1-flash-lite` に更新し API 疎通前進 |
| **PR #61** | `replacement_code` の構文検証を Propose 段階に追加（`ast.parse()` のみ、実行なし）。不正 Python 構文・無インデント・lone surrogate を fail-closed に |
| **PR #62** | primary model を `gemini-3-flash-preview` に変更。`ThinkingConfig(thinking_level="low")` を Gemini 3 系に注入。`thoughts_token_count` を `actual_thinking_tokens` として取得し ledger/cost に反映 |

### PR #63–#66 Hardening Progress

| PR | 変更内容 | 状態 |
|---|---|---|
| **PR #63** | `replacement_code` AST 意味検証強化（空 body・pass-only・return なし拒否）、`_LLM_SYSTEM_PROMPT` 調整 | ✅ merged |
| **PR #64** | Project Owner 用語統一（terminology standardization） | ✅ merged |
| **PR #65** | indentation contract 検証追加（check 5a/5b/5c）、return shape validation（check 8）追加。すべての return が `return DetectionResult(...)` 形式でなければ拒否。runbook wrapper description を実装と一致させた（`_candidate_body(request)` / `_mutation_anchor = None`） | ✅ merged |
| **PR #66** | **H-2 fallthrough guard**: check 9 を追加。最後のトップレベル文が `return DetectionResult(...)` でなければ拒否。nested-only return は fallthrough して `None` を返す可能性があるため fail-closed に。 | ✅ merged |
| **PR #67** | **H-3 DetectionResult 引数形式チェック**: check 10 を追加。`DetectionResult(...)` のすべての呼び出しは keyword-only 引数で、正確に `blocked`, `reason`, `confidence`, `matched_signals` の 4 フィールドを指定しなければならない。positional 引数・**kwargs 展開・duplicate keyword・keyword 名不足/過剰を拒否。`_LLM_SYSTEM_PROMPT` rule 10 および FORBIDDEN section を更新。 | ✅ merged |
| **PR #68** | **Task Prompt Gate v2 / Codex pre-emption requirement**: GPT task prompt の Adversarial Validation Matrix を必須化。Self-score gate（98/100 以上）追加。valid Codex P2 findings の分類ルール整備。docs/audit_gate/TASK_PROMPT_PROTOCOL.md を Audit Gate エントリポイント全体で必須化。 | ✅ merged |
| **PR #69** | **X-007 static value-check policy specification freeze**: `DetectionResult` フィールドの型・値レンジ静的チェックポリシーを凍結（docs-only）。check 11 は未実装。PR #70 向けの安全サブセット契約と 31-case adversarial test matrix を定義。詳細: [`docs/REPLACEMENT_CODE_STATIC_VALUE_CHECKS_SPEC.md`](docs/REPLACEMENT_CODE_STATIC_VALUE_CHECKS_SPEC.md) | ✅ spec frozen (docs-only) |
| **PR #73** | **X-007 safe-subset static implementation**: Category A obvious invalid literal rejection（check 11）を実装。`blocked`/`reason`/`confidence`/`matched_signals` の obvious invalid literal を AST のみで検証・拒否。field-domain allowlist 方式で bytes/ellipsis/complex/set/container なども網羅。signed numeric literal（`-1`, `+3.14`）・unary constant 式（`-True`）・container literal tuple element（`(['sql'],)` 等）・top-level unary constant（`matched_signals=-1` 等）も対象。Category B 動的式は引き続き defer。`_LLM_SYSTEM_PROMPT` rule 11 更新。114-case regression test suite 追加。 | ✅ merged |

> ℹ️ **PR #63–#73 は main に merge 済み。PR #72 は thread handoff protocol、PR #73 は X-007 check 11 実装です。**  
> PR #69 は X-007 type/value-range static checks のポリシー凍結（docs-only）です。  
> PR #73 で Category A obvious invalid literal rejection（check 11）を実装済み。X-002/X-003/X-006 policy alignment は Project Owner-overridable 推奨事項として保留。

### Gemini 3 技術詳細（PR #62）

| 項目 | 内容 |
|---|---|
| Primary model | `gemini-3-flash-preview` |
| Fallback model | `gemini-3.1-flash-lite` |
| Thinking config | `ThinkingConfig(thinking_level="low")` — Gemini 3 系のみ |
| `thinking_budget` | 使用しない（Gemini 3 API 非対応、`thinking_level` で代替） |
| `_GEMINI3_THINKING_ESTIMATE_LOW_TOKENS` | pre-call budget estimate 専用。API hard cap ではない |
| Actual thinking tokens | `response.usage_metadata.thoughts_token_count` から取得 |
| Billable tokens | `actual_output_tokens + actual_thinking_tokens`（片方 None なら fallback） |
| Cost 記録 | `max(pre-call estimate, actual billable response tokens)` で過小記録を防止 |
| 超過時の動作 | actual > estimate の場合、usage 記録後に patch 返却を拒否（fail-closed） |
| SDK guard | `ThinkingConfig` 構築失敗は `except Exception as exc` で fail-closed |

### Phase 3 安全境界

| 禁止事項 | 理由 |
|---|---|
| `promote_approved=true` | 最初の run 結果確認前に昇格禁止 |
| paid-credit run の連続実行 | 1 回実行し結果を確認してから次 PR を判断する |
| workflow / scripts / data / ledger の変更 | docs PR の対象外 |
| GEMINI_API_KEY の表示・確認・推測 | Secret 境界 |

### check 11 実装状況（PR #73 merge 済み）

- PR #73 で Category A obvious invalid literal rejection（check 11）を実装・merge 済み。
- validator は check 1–11 をすべて網羅。
- Category B dynamic expressions は引き続き defer。
- 次のフォーカスは Phase 3 Gemini API 初回 paid-credit run。

---

## 今後のロードマップ

| フェーズ | 内容 |
|---|---|
| **v0.1** | ローカルファーストの MVP スキャフォールド |
| **v0.2** | Gemini API 統合基盤（安全なフリーティア戦略・スキーマ拘束・プリフライトスキャン・API予算管理） |
| **v0.2.x（Phase 2）** | API未接続運用強化（rollback設計・evolution_history監査・offline-sample dry-run分離・運用チェックリスト整備）— **完了** |
| **v0.3（Phase 3 / 現在）** | 実 Gemini API 接続 — activation PR #58–#62 merge 済み、hardening PR #63–#68 完了、X-007 spec frozen (PR #69)、X-007 check 11 implemented (PR #73)、初回 paid-credit run 待機中 |
| **v0.4** | 複数検出器の並列評価、アンサンブル昇格 |
| **将来** | 実WAFへの統合（別途セキュリティレビュー必須） |

---

## 免責事項

- これは**研究用スキャフォールド**であり、本番環境のセキュリティソフトウェアではありません
- 実トラフィックの傍受、WAFへの直接接続、ライブ攻撃の自動化は行いません
- 昇格された検出器変更は、実環境にデプロイする前に必ず人間のレビューを経てください
- テストペイロードは学習・検証目的の静的文字列であり、実際の攻撃には使用できません

---

<!-- CYBER_IMMUNIZER_STATUS_START -->
## 🧬 Cyber-Immunizer Status

| Field | Value |
|---|---|
| Current Phase | Phase 3 — paid-credit API success records exist; no valid mutation patch produced (propose/output-contract failure) |
| Phase 3 Activation | Complete (PR #58-#62) |
| Phase 3 Paid-Credit API Calls | Executed (3 successful / 3 attempt(s)) |
| Gemini Primary Model | gemini-3-flash-preview |
| Gemini Fallback Model | gemini-3.1-flash-lite |
| promote_approved | false (promotion not approved — API executed; no valid candidate patch produced) |
| Next Focus | Project Owner review of the propose/output-contract fix (PR #84) before any owner-approved paid-credit rerun |
| live_model_enabled | true |
| API Mode | gemini_paid_credit |
| Model Provider | gemini |
| Max Model Requests / Run | 1 |
| Max Commits / Run | 1 |
| Monthly API Budget | 10.0 USD |
| Daily API Budget | 0.25 USD |
| Send Full Repository Text | false |
| Send Raw Payloads | false |
| Send Secrets | false |
| Schedule Mode | noop only |
| CI Status | Manual check required / see Actions |
| Noop Path | Verified |
| Offline Sample Path | Verified |
| Paid-Credit Preflight | Fail-closed when GEMINI_API_KEY missing |
| Phase 3 Gate | Project Owner explicit decision required |
| Generation | 2 |
| Best Score | 729.34 |
| Detector Hash | `69aebceeaebf6f80…` |
| Last Updated | 2026-05-26T07:28:45.915764Z |
| Total Test Cases | N/A |
| TP / FP / TN / FN | N/A / N/A / N/A / N/A |
| Fitness Report | Not available — run baseline fitness to populate TP/FP/TN/FN |
| Adoption Gate | ✅ Passed (generation 2) |
| Active Threat IDs | `THREAT-2024-001` `THREAT-2024-002` `THREAT-2024-003` `THREAT-2024-004` `THREAT-2024-005` |
| Status Block Updated | 2026-06-10 04:25 UTC |

<!-- CYBER_IMMUNIZER_STATUS_END -->
