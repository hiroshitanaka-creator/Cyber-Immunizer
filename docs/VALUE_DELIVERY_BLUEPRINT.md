<!--
AI_DOC_META:
  doc_type: value_delivery_blueprint
  status: CANONICAL
  scope: project-wide mission / value definition (what "完成" and "価値" mean here)
  authority: |
    This document is CANONICAL for the VALUE MISSION and the definition of a
    "high-level deliverable". It does NOT override current-state SSOT.
    Current state remains governed by data/project_state.json, docs/PROJECT_STATE.md,
    data/genome.json, and machine evidence (per CLAUDE.md authority order).
    The deliverable specifics in カテゴリ3/4 are PLANNING (proposed, not yet implemented).
  must_read_for: all task participants (Claude / GPT / Codex / Project Owner)
  origin: Authored from a machine-verified As-Is analysis at main HEAD 552ccb5 (generation 4 baseline).
-->

# Cyber-Immunizer — Value Delivery Blueprint（価値創出の正典ブループリント）

> **このファイルの位置づけ**：本リポジトリで作業する全関係者（Claude / GPT / Codex / Project Owner）が、タスク着手前に読むべき**必読の正典**である。
> ここに書かれているのは「何を作れば価値があると言えるのか」の定義と、その実現方針。
> 現在状態（current state）の正典ではない。現在状態は `data/project_state.json` / `docs/PROJECT_STATE.md` / `data/genome.json` / 機械的証拠が定義する（CLAUDE.md の権威順序に従う）。

---

## 0. Project Owner の核心的意志（曲げてはならない）

- 大量のドキュメント・テスト・プロトコルを積み上げた状態は「研究用として聞こえは良い」が、**外部に価値を届けられないなら価値はない**。
- 目標が高くてよい。時間がかかってよい。しかし **「文書・テスト・プロトコルが自己目的化し、外に価値を届けられない状態」を決して『完成』と呼んではならない。**
- 最終的に生み出すべきは、**実際に誰かが使えて、その人のセキュリティ posture を測定可能に向上させられる高レベル成果物**。
- **却下対象**：「もっとドキュメントを増やす／テストを足す／プロトコルを強化する」だけで終わる提案。

> 補足：「不要な文章は書かない」という従来方針は *docs-only タスクで埋め尽くされた局面* に対する是正措置であり、**本ブループリントのような価値定義の固定には適用しない**（Project Owner 明示）。

---

## 1. 高レベル成果物の価値定義（これを満たさないものは「完成」と認めない）

次のいずれか（または複合）を満たすものだけを「高レベル成果物」と認める：

1. ローカルで実行でき、開発者が「自分のコード/検出器を免疫化」できる具体的な CLI / ツール / ライブラリ出力。
2. 進化した防御コードが、具体的な脅威パターンに対し **測定可能な改善**（before/after の検知率・FP/FN・進化前後の score 差）を示す。
3. Project Owner 以外の人が「これを使えばセキュリティが上がる」と実感できる形（デモ・ケーススタディ・エクスポート可能な detector モジュール・CI 統合例）。
4. 内部進化ループの成功が **外部価値として輸出**されている（単に internal genome が更新されるだけでない）。

---

## 2. 核心的診断 — なぜ今「価値がない」と感じるのか（技術的根拠）

機械検証（main HEAD `552ccb5` / generation 4 / `best_score=948.04`）の上でコードを読んだ結論：

> **進化ループは propose→apply→evaluate→promote まで実通過し、adoption gate も突破している。しかし検出器もコーパスも記号トークン（`PATH_TRAVERSAL_INDICATOR`, `SQLI_INDICATOR` 等）だけを対象にしている。** これは「リポジトリに実 exploit 文字列を置かない」という*正しい安全設計*の副作用であり、結果として **進化した検出器は現実の攻撃を1つも検知できない**。

- 根拠: `core/detector.py:39-65`（symbolic token のみ照合）, `data/attack_requests.json`（攻撃ケースが `*_INDICATOR` 記号のみ）。
- したがって score 383→948 の上昇は「symbolic corpus 上の内部数値」であり、**外部価値ではない**。
- **ボトルネックの本質（3層）**：
  1. **記号の壁**：検出器・コーパスが symbolic のみ → 現実脅威への検知力ゼロ。
  2. **出力の閉鎖**：成果が `genome.json` / `evolution_history.json` という内部状態にしか書き出されない。外部の人が触れる出力（CLI・レポート・パッケージ）が無い。
  3. **エンジンとコンテンツの未分離**：「安全に進化させる仕組み（普遍・公開可能）」と「何を検知するか（防御知識）」が混在し、前者を公開できていない。

この診断が、以下すべての方針の出発点である。

---

## カテゴリ1: 現在の強みと資産の希望的再解釈

| 既存資産 | 従来の見え方 | 希望的再解釈（＝価値の源泉） |
|---|---|---|
| CLAUDE.md ゲート群／監査プロトコル | 自己目的化した官僚機構 | **LLM がコードを自己書き換えする危険行為を、誤受理ゼロで運用できるガバナンス基盤**。競合が持たない参入障壁。安全だから内に閉じるのではなく、**安全だからこそ外へ開ける** |
| `core/policy.py`（17段 AST 検査）＋ Docker 隔離 | 検証コードの塊 | **「信頼できないコードを安全に実行・評価するエンジン」**。単体で `import` 可能なライブラリ価値（生成 AI 時代の汎用ニーズ） |
| `core/fitness.py` の `FitnessReport`（tier別 TP/FP/FN・score_components） | 内部スコア | **before/after 価値レポートの完成素材** |
| `core/structured_*`（宣言型ルール、未統合） | 重複した第2検出系 | **実 exploit を置かずに"本物の防御シグネチャ"を表現できる唯一の安全な器**。`contains_literal "../"` 等は WAF ルールと同じ防御コンテンツであり攻撃コードではない。**記号の壁を突破する正規の出口** |
| Generation 4 baseline（昇格実績） | 内部の数字 | **adoption gate を初めて突破した実物＝輸出可能な"製品の種"** |

**結論**：このリポジトリは「価値のない研究」ではなく、**価値輸出層（consumer layer）が欠けているだけの高完成度エンジン**。

---

## カテゴリ2: 価値創出を阻害する構造的ボトルネックと希望的克服策

（ボトルネックの本質は §2 を参照）。克服策は **FROZEN をほぼ触らずに反転させる**：

- **記号の壁 → ユーザー入力＋防御シグネチャで突破**
  - リポジトリは exploit-free を維持（symbolic corpus はそのまま）。
  - **CLI はユーザー自身のローカルなリクエストログ／フィクスチャを入力**にする。実データはユーザーのマシン上にあり、リポジトリには入らない → 安全境界を守ったまま現実検知を実証。
  - **`core/structured_*` に"本物の防御シグネチャ"をデータとして投入**（`../`, `<script`, `' or '1'='1`, `;|&&` 等＝防御側が書くシグネチャ。攻撃ペイロードではない）。既存の公開関数 `inspect_request_with_structured_rules` を呼ぶだけで **FROZEN の `detector.py` を編集せずに**現実パターン検知が動く。
- **出力の閉鎖 → consumer layer 新設で反転**：FROZEN を読むだけの新規パッケージを足し、`FitnessReport` と `evolution_history.json` を人間可読 before/after レポートに変換。
- **未分離 → ライブラリ公開で分離**：`pyproject.toml`（ルート、FROZEN 外）に console_scripts とオプション依存を足し、`cyber_immunizer.core` を import 可能な"安全実行エンジン"として公開。

> **重要**：MVP は FROZEN 領域（core/scripts/.github/data/tests）を **ゼロ編集**で達成できる。触るのはルートの `pyproject.toml` と新規ディレクトリのみ。これが「最小の変更で最大の外部価値」。

---

## カテゴリ3: 即時〜中期で実現可能な高レベル成果物（優先順位付き・PLANNING）

各成果物は「なぜ価値か（測定指標）／活用資産／FROZEN 扱い／最小変更ファイル／DoD」を持つ。

### 🥇 成果物A（即時・1〜2週間）— `cyber-immunize report`
進化の成功を before/after の価値証明に変換する read-only CLI。
- **価値（指標）**：gen0→gen4 の attack 検知率・FP/FN・score 383→948 を第三者が読める表に変換。
- **活用資産**：`core/fitness.py`, `data/evolution_history.json`, `core/test_attacker.py`。
- **FROZEN**：触れない（読むのみ）。
- **最小変更**：新規 `cli/__init__.py`・`cli/report.py`、`pyproject.toml`（console_scripts ＋ optional extra `cli=[rich]`）。
- **DoD**：`cyber-immunize report` が exit 0 で gen0→gen4 改善表を表示、`--export report.md` で Markdown 生成、FROZEN 差分ゼロ、`pytest tests/` 全 green 維持。

### 🥈 成果物B（即時〜中期・2〜4週間）— `cyber-immunize scan <file>`
ユーザーが自分のローカルなリクエスト集を渡すと、監査済み検出器＋防御シグネチャを適用し per-request verdict を出す。「自分のコードに免疫を当てる」最初の実体験。
- **価値（指標）**：ユーザー入力 N 件中の検知件数・FP 件数・レイテンシ（`max_avg_latency_ms ≤ 100` 保証）。
- **活用資産**：`core/detector.py::inspect_request`, `core/structured_detector.py::inspect_request_with_structured_rules`, `core/types.py`。
- **FROZEN**：`detector.py` は呼ぶだけ（編集しない）。
- **最小変更**：新規 `cli/scan.py`、新規 `rulesets/defensive_baseline.json`。
- **DoD**：サンプル入力に per-request verdict レポートを出力。README に「入力はユーザー所有・リポジトリに保存しない」と明記。exploit ペイロード混入ゼロ。

### 🥉 成果物C（中期・1〜2ヶ月）— 第一級「防御シグネチャ・ルールパック」＋構造化検出の昇格
未統合の `core/structured_*` を実運用ルールパック（path-traversal / XSS / SQLi / cmdi クラス別）として同梱。進化対象を symbolic から現実シグネチャへ拡張する布石。
- **価値（指標）**：各脅威クラスの検知率、ルールパック適用前後の coverage 差。
- **活用資産**：`core/structured_evaluator.py`・`structured_validator.py`、`tests/test_structured_detector_equivalence.py`。
- **FROZEN**：`core/structured_*` は読むだけ。`detector.py` 統合は任意・後回し（独立 opt-in 経路で価値が出るため FROZEN 編集を回避）。
- **最小変更**：新規 `rulesets/*.json`、`cli/scan.py` のローダ拡張。
- **DoD**：CLI に ruleset を渡すと現実シグネチャで検知が動作、既存 equivalence/validation テスト green、ルールパックは「防御シグネチャのみ・攻撃手順ゼロ」をレビューで確認。

### 🏔 成果物D（高レベル・3〜6ヶ月の本気の野心）— ローカル免疫化レポート＋CI 統合テンプレ＋配布パッケージ
(1) `cyber_immunizer_detectors` を installable 化（gen4 検出器＋ルールパック）、(2) GitHub Action テンプレ（repo の request fixtures に検出器を当て PR に before/after レポート自動投稿）、(3) 余力で軽量ローカルダッシュボード（Streamlit/Gradio）。
- **価値（指標）**：外部ユーザーが `pip install` → CI に組込 → 自プロジェクトの検知カバレッジ +X を体験。
- **活用資産**：`.github/workflows/ci.yml`（参照テンプレ）、core 全体、成果物 A〜C の出力。
- **FROZEN**：`.github/**` は新規別ファイル（`examples/github-action/`）として提供、既存ワークフロー不変。
- **DoD**：外部ユーザーがパッケージを入れ CI に組込み、PR 上に「この変更で検知カバレッジ +X」レポートが出る実例が1件動く。

---

## カテゴリ4: アーキテクチャ進化の方向性（PLANNING）

**設計原則：「FROZEN エンジン（不変・安全）」と「consumer layer（新設・価値輸出）」を物理的に分離する。**

```
┌─────────── 新設 consumer layer（FROZEN外・自由に進化）───────────┐
│  cli/        … report / scan エントリ                            │
│  rulesets/   … 防御シグネチャ（データ。攻撃コードではない）          │
│  examples/   … github-action テンプレ・CI統合例                  │
│  valuereport … FitnessReport → 人間可読 before/after 変換       │
└───────────────────────────┬───────────────────────────────────┘
                            │ import（読み取り専用）
┌───────────────────────────▼─────── FROZEN エンジン（不変）──────┐
│  core/policy.py    … 信頼できないコードの安全検証（17段AST）       │
│  core/fitness.py   … 決定論スコア＋tier別TP/FP/FN                │
│  core/detector.py  … gen4 baseline（呼ぶだけ）                   │
│  core/structured_* … 宣言型ルール評価（既存公開関数を呼ぶだけ）     │
│  scripts/*         … propose/apply/evaluate/promote（無改変）    │
└───────────────────────────────────────────────────────────────┘
```

- **依存方針（現状ほぼゼロを尊重）**：本体ランタイム依存ゼロは強み。consumer layer の追加依存は **optional extra に隔離**し、本体 `dependencies=[]` を死守。
  - 許容提案：`rich`（レポート可読性）、必要なら `typer`（CLI 体験）。新 extra `cli` に閉じる。Streamlit は成果物 D 限定の `dashboard` extra に隔離。
  - 不採用：tree-sitter/libcst（現 `ast` で十分、過剰）。
- **コア公開**：`pyproject` の packages に `cli*` を追加し `cyber_immunizer.core` を外部 import 可能に。エンジンは触らず"窓"だけ開ける。
- **進化ループの両モード化（将来）**：`scripts/` を「バッチ CI」「対話 CLI」両対応に拡張する場合のみ FROZEN 編集＝全ゲート＋Owner 承認。MVP では不要。

---

## カテゴリ5: 「研究スキャフォールド」→「価値生産システム」への転換

### マインドセット（最重要）
- **「安全 ⇔ 価値」はトレードオフではない。** 安全基盤があるからこそ大胆に輸出できる。内向きの規律を外向きの推進力へ反転させる。
- すべての変更を **「外部価値メトリクス」** で評価：その変更は「外の誰かが実行できる出力」を1つでも増やしたか？ 増やさないなら後回し。

### 体制（運用ルール）
1. 各タスクは「実行可能な外部出力（CLI/レポート/パッケージ）」を1つ以上前進させる。docs/tests のみの PR は原則却下。
2. FROZEN 編集は最終手段。まず「呼ぶだけ／新規ファイル」で達成できないか先に検討。
3. 既存の厳格ゲート（受信10項目・Source Evidence・PR 監査）は**そのまま流用**して consumer layer の品質を担保（ゲートは資産、捨てない）。

### 次の最初の1歩
**成果物A（`cyber-immunize report`）のプロトタイプを、FROZEN 差分ゼロ・既存全ゲート通過の形で実装する。**
これが1回成功すれば、プロジェクトの自己認識が「研究」から「製品」へ反転し、以降の意思決定基準が変わる。実装タスクプロンプト雛形は本ブループリント運用時に別途生成する。

---

## 安全制約（全成果物に常時適用）

- 防御専用。攻撃コード生成・実トラフィック接続・マルウェア技術・exploit ペイロードの追加を一切しない。
- paid-credit API / live model / workflow_dispatch は Project Owner の明示承認時のみ。
- FROZEN（`core/**`, `scripts/**`, `.github/**`, `data/**`, 既存 `tests/**`）は原則編集しない。触る場合は CLAUDE.md の全ゲートを通過。
- ルールパックは「防御シグネチャのみ」。攻撃手順・回避手法・PoC を含めない。

---

> 本ブループリントは As-Is 解析（main HEAD `552ccb5`, generation 4 baseline）から導出した価値定義の正典である。
> 現在状態の数値・状態の正典は `data/genome.json` / `data/project_state.json` / `docs/PROJECT_STATE.md` であり、矛盾時はそれらが優先する。
