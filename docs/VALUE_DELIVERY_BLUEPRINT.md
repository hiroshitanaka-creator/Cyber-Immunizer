<!--
AI_DOC_META:
  doc_type: value_delivery_blueprint
  status: CANONICAL
  scope: project-wide mission / value definition
  authority: |
    CANONICAL for the VALUE MISSION and the definition of a "high-level deliverable."
    Does NOT override current-state SSOT.
    Current state is governed by data/project_state.json, docs/PROJECT_STATE.md,
    data/genome.json, and machine evidence (per CLAUDE.md authority order).
    Deliverable specifics marked PLANNING are proposed, not yet implemented.
  must_read_for:
    - value / deliverable / roadmap / completion tasks
    - PRs that claim practical defensive value
    - tasks that classify docs-only work
  read_alongside: docs/DEFINITION_OF_DONE.md
  origin: Authored from machine-verified As-Is analysis at main HEAD 552ccb5 (generation 4 baseline).
-->

# Cyber-Immunizer — Value Delivery Blueprint（価値創出の正典ブループリント）

> **このファイルの位置づけ**：価値・deliverable・roadmap・completion に関わるタスク、実用的防御価値を主張する PR、docs-only タスクを分類するタスクの**必読の正典**。ルーティンの実装・PR 監査・引き継ぎタスクに対するプロセス税にはしない。
> 「何を作れば価値があるか」の定義と実現方針を記録する。
> 現在状態の正典ではない。現在状態は `data/project_state.json` / `docs/PROJECT_STATE.md` / `data/genome.json` / 機械的証拠が定義する。

---

## 0. このドキュメントが存在する理由（Project Owner の核心的意志）

このドキュメントは、**これまでの AI アドバイスが繰り返しドキュメント・テスト・プロトコルを「進捗」として扱い続けた結果、外部に実質的な防御価値を届けられない状態が生まれたこと**を記録し、同じ失敗を防ぐために書かれた。

- GPT の提案によって大量のドキュメント・テスト・プロトコルが積み上がった。
- 結果として「研究用として聞こえが良い」リポジトリが生まれたが、**現実の防御システムとしての実用性は未検証のまま**である。
- ドキュメントとテストの量は Project Owner を安心させるためではなく、実際の防御価値を保証するために存在する。
- **「ドキュメントとテストを増やせば安全で完成に近い」という AI の思考パターンは、このプロジェクトでは明確に否定する。**

Project Owner の意志：
- **必要なドキュメントは残す。** 安全境界・Owner の意図・現在状態・監査証拠を守るドキュメントは価値がある。
- **不要なドキュメントは価値がない。** 網羅性を示すための文書、自己目的化したプロトコル、「完成らしく見える」だけの記述は進捗ではない。
- **実行可能な価値が先。** 外部の誰かが使って「セキュリティが上がった」と実感できるものが最終目標。

これは documentation bloat ではなく、**Owner intent / failure-mode record** である。このドキュメントは、将来の GPT / Claude / Codex が再び docs/tests/protocol accumulation を「進捗」と取り違えてドリフトすることを防ぐために存在する。

---

## 1. 高レベル成果物の価値定義（これを満たさないものは「完成」と認めない）

次のいずれか（または複合）を満たすものだけを「高レベル成果物」と認める：

1. 実際に実行でき、**実在する脅威カテゴリに対して測定可能な防御改善を示す**（TP/FP/FN の before/after）。
2. Project Owner または監査者が「この進化サイクルで何の脅威クラスが改善されたか、なぜか」を読める形で説明できる。
3. 上記の価値検証（Layer 2）を通過した後にのみ、外部への公開・配布・デモを検討する。

**「もっとドキュメントを増やす／テストを足す／プロトコルを強化する」だけで終わる提案は、明確に価値がないと判断し、却下する。**

---

## 2. README ミッションとの整合（誤ったフレーミングの修正）

README は本プロジェクトのミッションを以下のように定義している：
- 現実世界のサイバー脅威の進化スピードに対し、人間によるパッチ開発の限界を突破すること
- デジタル自律免疫システムの確立
- ローカルファーストの研究基盤（本番 WAF・実トラフィック接続ではない）

### 誤ったフレーミング（使ってはならない）

> 「研究として70%完成、実用的な価値はほぼゼロ」

このフレーミングは README ミッションに対して無効である。ミッションは「実用的なプロダクト」ではなく「防御コードの自律進化エンジン」だからである。

### 正しいフレーミング

- 安全性に統治された自律進化エンジンとしての**研究基盤は意味のある進捗**（Layer 1）を持つ。
- リポジトリは空の研究スキャフォールドではない。
- しかし、このエンジンが**現実の進化する脅威クラスに対して意味のある防御価値を提供できるかどうかはまだ検証されていない**（Layer 2 未達）。
- 「研究基盤の成熟度」と「README ミッションの達成度」は別の軸で評価する。
- **価値が検証される前に、外部向けの成果物でリポジトリを実用的に見せることは行わない。**

---

## 3. 核心的診断 — なぜ「価値が届いていない」のか（技術的根拠）

機械検証（main HEAD `552ccb5` / generation 4 / `best_score=948.04`）の上でコードを読んだ結論：

> `core/detector.py`（Generation 4）と `data/attack_requests.json` は、`PATH_TRAVERSAL_INDICATOR`・`SQLI_INDICATOR` のような**記号トークンだけ**を対象にしている。これは「リポジトリに実 exploit 文字列を置かない」という**正しい安全設計**の副作用であり、結果として進化した検出器は現実の攻撃パターンを1つも検知しない。

根拠：
- `core/detector.py:39-65`（symbolic token のみ照合）
- `data/attack_requests.json`（攻撃ケースが `*_INDICATOR` 記号のみ）

したがって score 383.67→948.04 の上昇（first evaluated generation である Generation 1 から Generation 4 まで）は「symbolic corpus 上の内部数値」であり、**外部防御価値ではない。**
なお Generation 0 は未評価プレースホルダであり、scored baseline には決して用いない。

### ボトルネックの本質（3層）

1. **記号の壁**：検出器・コーパスが symbolic のみ → 現実脅威への検知力が未検証。
2. **出力の閉鎖**：進化成果が `genome.json` / `evolution_history.json` という内部状態にしか書き出されない。価値検証に必要な per-category TP/FP/FN レポートが存在しない。
3. **価値検証の未実施**：「安全に進化させる仕組み」は整っているが、「何を検知できるか」の現実評価が行われていない。

---

## 4. 強みと資産の再解釈（希望的、かつ正確な評価）

| 既存資産 | 正確な評価 |
|---|---|
| CLAUDE.md ゲート群・監査プロトコル | LLM がコードを自己書き換えする危険行為を、誤受理ゼロで運用できるガバナンス基盤。これは強み。**ただし安全基盤と防御価値は別物。** |
| `core/policy.py`（17段 AST 検査）+ Docker 隔離 | 信頼できないコードを安全に実行・評価するエンジン。堅牢。 |
| `core/fitness.py` の `FitnessReport` | per-category TP/FP/FN を持つ。**価値検証ツール（Owner/監査者向け）のベースになり得る。** |
| `core/structured_*`（宣言型ルール、未統合） | 実 exploit を置かずに防御シグネチャ（`PATH_TRAVERSAL_SIGNATURE_PLACEHOLDER` 等の中立化プレースホルダで表現、WAF ルールと同等）を表現できる安全な器。記号の壁を突破する正規の経路候補。 |
| Generation 4 baseline（昇格実績） | adoption gate を通過した実物。symbolic corpus 上での完全検知（tp=1.0, fp=0.0）。価値検証のベースラインとして使える。 |

**結論**：このリポジトリは「価値のない研究」ではなく、**価値検証層（validation layer）が欠けているだけの高完成度エンジン**。エンジンは堅牢。次に必要なのは「外の誰かに届ける前に、まず価値を検証すること」。

---

## 5. 価値を阻害するボトルネックと克服策

### 記号の壁の克服（FROZEN 編集なし）

- `core/structured_*` に**防御シグネチャ（データ）**を投入する。シグネチャは防御側が書く検知ルールであり攻撃コードではないが、**リポジトリにコミットする例は中立化プレースホルダ**（`PATH_TRAVERSAL_SIGNATURE_PLACEHOLDER`・`SCRIPT_INJECTION_SIGNATURE_PLACEHOLDER`・`SQLI_SIGNATURE_PLACEHOLDER`・`COMMAND_DELIMITER_SIGNATURE_PLACEHOLDER`）で表す。
- 既存の公開関数 `inspect_request_with_structured_rules`（`core/structured_detector.py`）を呼ぶだけで `core/detector.py` を編集せずに現実パターン評価が動く。
- **リポジトリにコミットする rulesets / examples / fixtures は中立化・記号化されたものだけ。** Raw exploit payload・攻撃レシピ・bypass guidance・実トラフィックキャプチャはコミットしない。
- 現実的なシグネチャや request sample が必要な場合は、**リポジトリ外のユーザー提供ローカルファイル**として供給する。ユーザー提供ローカルデータは read-only かつ防御専用に限る。

### 出力の開放（価値検証ツール）

- `FitnessReport` の per-category 結果と `evolution_history.json` を読み、**Owner / 監査者向けに** gen1→genN の改善を説明する検証ツールを構築する（gen0 は未評価プレースホルダであり scored baseline には使わない）。
- これは**外部ユーザー向け製品ではない**。価値が検証されるまでは Owner と監査者のためのツールである。

### 外部化の禁止（Layer 2 達成まで）

以下は Layer 2（価値検証完了）まで**明示的に禁止**：

- `cyber-immunize scan` またはユーザー向けスキャン CLI
- パッケージ配布（PyPI その他）
- 外部プロジェクト向け GitHub Action テンプレート
- ダッシュボード（Streamlit / Gradio / その他）
- 公開デモまたはベンチマーク公表
- 「外部ユーザーが使える」と主張するいかなる成果物

**価値が検証されていない成果物を外部ユーザーに公開することは、高レベル成果物ではない。**

---

## 6. 段階的な価値創出の方向性（PLANNING）

Layer 1（研究基盤）が確立された上で、Layer 2（価値検証）へ進む道筋：

### ステップ 1（Owner / 監査者向け価値検証ツール）

- **目的**：symbolic corpus スコアを、脅威カテゴリ別の防御改善証拠に変換する。
- **手段**：`core/fitness.py` の `FitnessReport` と `evolution_history.json` を読み、gen1→gen4 の改善を per-category で説明するレポートを Owner / 監査者向けに出力（gen0 は未評価プレースホルダ）。
- **位置づけ**：これは**外部ユーザー向けではない**。Layer 2 達成の判断根拠となる内部ツール。
- **FROZEN 編集**：不要（読み取りのみ）。

### ステップ 2（現実脅威カテゴリの評価）

- 防御シグネチャ（中立化済み）を用いて、現実の脅威カテゴリ（path-traversal / XSS / SQLi / cmdi）に対する検知率を評価。
- 結果を Layer 2 基準（L2-V1〜L2-V5、`docs/DEFINITION_OF_DONE.md` 参照）で評価。

### ステップ 3（Layer 2 達成後の外部化、時期未定）

Layer 2 が Owner に受け入れられた後にのみ検討する：
- 外部ユーザー向けスキャンツール
- パッケージ配布
- CI 統合テンプレート

**これらはステップ 3 であり、今の目標ではない。**

---

## 7. 安全制約（全成果物に常時適用）

- 防御専用。攻撃コード生成・実トラフィック接続・マルウェア技術・exploit ペイロードの追加は一切しない。
- **コミットする examples / rulesets は中立化・記号化されたもののみ。** Raw exploit-looking literals をリポジトリにコミットしない。
- paid-credit API / live model / workflow_dispatch は Project Owner の明示承認時のみ。
- FROZEN（`core/**`, `scripts/**`, `.github/**`, `data/**`, 既存 `tests/**`）は原則編集しない。触る場合は CLAUDE.md の全ゲートを通過。
- Generation 1 を Generation 0 と誤表記しない（gen0 は初期 baseline でスコア未計算、gen1 は最初の有効な採用 generation）。
- `cyber_immunizer.core` として import 可能なパッケージ名前空間は**現時点では実装されていない**。将来のパッケージング判断であり、実装済みとして記述してはならない。

---

> 本ブループリントは As-Is 解析（main HEAD `552ccb5`, generation 4 baseline）から導出した価値定義の正典である。
> 現在状態の数値・状態の正典は `data/genome.json` / `data/project_state.json` / `docs/PROJECT_STATE.md` であり、矛盾時はそれらが優先する。
