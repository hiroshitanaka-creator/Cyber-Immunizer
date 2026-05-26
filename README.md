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
│   └── evolution_history.json  # 進化の全履歴
├── intelligence/
│   └── threat_feeds.py     # 脅威インテリジェンスモジュール（スタブ）
├── scripts/
│   ├── validate_mutation.py    # ASTポリシー検証
│   ├── apply_mutation.py       # 変異パッチの適用
│   ├── evaluate_candidate.py   # サブプロセスによる候補評価
│   ├── promote_candidate.py    # 採用ゲート通過時の昇格
│   ├── propose_mutation.py     # LLM変異提案（スタブ＋オフラインサンプル）
│   └── update_readme.py        # READMEステータスブロック更新
├── tests/
│   ├── test_contract.py            # 検出器インターフェース契約テスト
│   ├── test_ast_policy.py          # ASTポリシー検証テスト
│   ├── test_fitness.py             # 適合度評価テスト
│   ├── test_mutation_boundaries.py # 変異境界テスト
│   ├── test_promote_candidate.py   # 昇格ゲートテスト（tmp_path使用、実ファイル非破壊）
│   └── test_types.py               # Request イミュータビリティテスト
├── .github/workflows/
│   └── immunization_loop.yml   # propose / evaluate / promote 分離ワークフロー
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

`.github/workflows/immunization_loop.yml` は **propose / evaluate / promote** の3ジョブを意図的に分離しています。

| ジョブ | 権限 | シークレット | 生成コードを実行するか |
|---|---|---|---|
| `propose` | `contents: read` | GEMINI_API_KEY（任意） | ❌ しない |
| `evaluate` | `contents: read` | なし | ✅ する（サブプロセス隔離） |
| `promote` | `contents: write` | GITHUB_TOKEN のみ | ❌ しない |

**生成コードが実行されるジョブには書き込み権限もモデルAPIシークレットも付与しません。**  
**`promote` ジョブは GITHUB_TOKEN（リポジトリへの書き込み用）のみを保持し、GEMINI_API_KEY は持ちません。**

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

| テストファイル | カバレッジ |
|---|---|
| `test_contract.py` | 検出器の関数シグネチャ・戻り値型・信頼度範囲・無害リクエストの非ブロック・シンボリック指標の検出 |
| `test_ast_policy.py` | `os` / `subprocess` / `eval` / `exec` / dunder・type/dir/super/breakpoint等の拒否、安全なコードの受理 |
| `test_fitness.py` | ベースライン評価、全ブロック器の失敗、全許可器の失敗、リグレッション強制、スコア完全決定論性（レイテンシ除外を検証） |
| `test_mutation_boundaries.py` | マーカー外の不変性、マーカーの存在、重複マーカーの拒否、マーカー含有コードの拒否、不正パッチの拒否 |
| `test_promote_candidate.py` | ハッシュ検証・スキーマ検証・採用失敗時の拒否・ast_policy_ok=False時の拒否・fp_rate超過時の拒否（すべて `tmp_path` 使用、実ファイル非破壊） |
| `test_types.py` | `Request.query` / `Request.headers` の MappingProxyType イミュータビリティ、構築後のソースdict変更の影響なし |

```bash
python -m pytest -v
# 125 passed
```

テストはすべて `tmp_path` インジェクションを使用し、`core/detector.py` や `data/genome.json` などの実リポジトリファイルを変更しません。

---

## 今後のロードマップ

| フェーズ | 内容 |
|---|---|
| **v0.1** | ローカルファーストの MVP スキャフォールド |
| **v0.2（現在）** | Gemini API 実呼び出し実装（安全なフリーティア戦略、スキーマ拘束、プリフライトスキャン） |
| **v0.3** | プロセス隔離強化（`resource.setrlimit`）、テストケース自動拡張、スコア履歴ダッシュボード |
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
| Generation | 1 |
| Best Score | 383.67051093329087 |
| Detector Hash | `cbd6bdee7f8f4c19…` |
| Last Updated | 2026-05-26T01:09:22.856943Z |
| Total Test Cases | 15 |
| TP / FP / TN / FN | 8 / 0 / 7 / 0 |
| Adoption Gate | ✅ Passed (generation 1) |
| Active Threat IDs | `THREAT-2024-001` `THREAT-2024-002` `THREAT-2024-003` `THREAT-2024-004` `THREAT-2024-005` |
| Status Block Updated | 2026-05-26 01:19 UTC |

<!-- CYBER_IMMUNIZER_STATUS_END -->
