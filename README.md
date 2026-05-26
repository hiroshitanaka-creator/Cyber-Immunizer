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
│   ├── types.py            # イミュータブルなデータクラス群
│   ├── detector.py         # 検出器インターフェース（変異境界マーカーあり）
│   ├── fitness.py          # 決定論的な適合度評価エンジン
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
│   └── test_promote_candidate.py   # 昇格ゲートテスト
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
| 偽陽性率 | `fp_rate ≤ 0.05` |
| スコア改善 | `score > 現世代のbest_score` |

### フィットネススコア計算式

```
score =
  1000 × tp_rate
- 2000 × fp_rate
- 1500 × fn_rate
-   50 × exception_count
-    2 × avg_latency_ms
- 0.02 × code_chars
-   10 × changed_lines
```

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

`GEMINI_API_KEY` を設定すると、Gemini API 経由で変異を提案します。設定がない場合はオフラインサンプルにフォールバックします。

```bash
export GEMINI_API_KEY=your_api_key_here
python scripts/propose_mutation.py --json
```

> 注意: MVP では Gemini API の実呼び出しはスタブ状態です。次スプリントで実装予定。

---

## GitHub Actions ワークフロー

`.github/workflows/immunization_loop.yml` は **propose / evaluate / promote** の3ジョブを意図的に分離しています。

| ジョブ | 権限 | シークレット | 生成コードを実行するか |
|---|---|---|---|
| `propose` | `contents: read` | GEMINI_API_KEY（任意） | ❌ しない |
| `evaluate` | `contents: read` | なし | ✅ する（サブプロセス隔離） |
| `promote` | `contents: write` | なし | ❌ しない |

**生成コードが実行されるジョブには書き込み権限もAPIシークレットも付与しません。**

トリガー：
- 手動実行（`workflow_dispatch`）
- 毎日 02:00 UTC（`schedule`）

昇格成功時のコミット対象ファイル：
- `core/detector.py`
- `data/genome.json`
- `data/evolution_history.json`
- `README.md`

---

## テスト構成

| テストファイル | カバレッジ |
|---|---|
| `test_contract.py` | 検出器の関数シグネチャ・戻り値型・信頼度範囲・無害リクエストの非ブロック |
| `test_ast_policy.py` | `os` / `subprocess` / `eval` / `exec` / dunder等の拒否、安全なコードの受理 |
| `test_fitness.py` | ベースライン評価、全ブロック器の失敗、全許可器の失敗、リグレッション強制、スコア決定論性 |
| `test_mutation_boundaries.py` | マーカー外の不変性、マーカーの存在、マーカー含有コードの拒否、不正パッチの拒否 |
| `test_promote_candidate.py` | 採用失敗時の昇格拒否、スコア改善なし時の拒否、レポート欠損時の拒否 |

```bash
python -m pytest -v
# 70 passed, 1 skipped
```

---

## 今後のロードマップ

| フェーズ | 内容 |
|---|---|
| **v0.1（現在）** | ローカルファーストの MVP スキャフォールド |
| **v0.2** | Gemini API 実呼び出し実装、プロセス隔離強化（`resource.setrlimit`） |
| **v0.3** | テストケース自動拡張、スコア履歴ダッシュボード |
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
