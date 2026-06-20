<!--
AI_DOC_META:
  doc_type: definition_of_done
  scope: project-wide (research MVP + autonomous immune loop)
  authority: derived (subordinate to data/project_state.json and docs/PROJECT_STATE.md)
  generated_from: As-Is Map analysis (uploaded repository snapshot)
  note: 数値・状態は genome.json / project_state.json を正典とする派生サマリ。矛盾時は正典が優先。
-->

# Cyber-Immunizer — 完成条件（Definition of Done）

> **適用範囲**：本DoDは「研究MVP＋自律免疫ループ運用基盤」としての完成を定義する。各基準は `合格/不合格` を機械的または目視で判定できる形で記述する。スコープ判断（攻撃機能は永久に対象外）は CLAUDE.md / README の安全方針に従う。

---

## 1. 機能要件（Functional Requirements）

### 1-A. 既存機能の完成条件（実装済み機能の「完了」定義）

| ID | 機能 | 入力 | 処理 | 出力 | 完成判定基準 |
|---|---|---|---|---|---|
| F1 | AST安全ポリシー検証 | 候補 `.py` パス | `run_full_policy` で17検査 | 違反コード文字列リスト | 禁止 builtins/modules/dunder/eval系を**100%遮断**、`tests/test_ast_policy.py` 全パス、誤受理0件 |
| F2 | ベースライン検出器 | `Request` | 表層走査 | `DetectionResult`（boolを返さない） | gen4で `tp_rate=1.0, fp_rate=0.0, fn_rate=0.0`、`inspect_request` が例外を投げない |
| F3 | 適合度評価 | 候補 + コーパス | `score=1000·tp−2000·fp−1500·fn` | `FitnessReport` | 同一入力で**ビット同一スコア**（決定論性）、latency/changed_linesはランキング除外 |
| F4 | 変異提案 | genome + detector | noop/offline/live/paid/preflight の5モード | `mutation_patch.json` | 各モードが exit 0、秘密鍵スキャン通過、スキーマ検証パス |
| F5 | 変異適用 | patch + base | MUTATION領域のみ書換 | `candidate_detector.py` | 領域外バイト不変、適用後 F1 再検証パス |
| F6 | 候補評価（隔離） | candidate | digest-pinned Docker内実行 | `fitness_report.json` + 採用ゲート | `--soft-reject` でツール故障(exit1)とゲート不合格(exit0)を区別 |
| F7 | 昇格 | candidate + report + attestation | core更新 + 履歴記録 | `detector.py`/`genome.json`/`evolution_history.json` | アテステーション検証なしでは昇格不可（fail-closed） |
| F8 | API予算ゲート | ledger | 月次/日次コスト推計 | 可否 | 推計が常に過大計上、予算超過で**API呼出を阻止** |
| F9 | 状態スキーマ検証 | data/*.json | 厳格スキーマ照合 | exit code | 全11 JSONが検証パス、`validate_state.py` exit 0 |
| F10 | READMEステータス更新 | genome/history | STATUSブロックのみ更新 | README | マーカー外バイト不変 |

> 上記 F1〜F10 は**現状でほぼ達成済み**。「完了」確定の最終条件は「§5のテスト要件を満たし、§3の静的解析基準をクリアすること」。

### 1-B. 未実装・統合待ち機能の完成条件

| ID | 機能 | 入力 | 処理 | 出力 | 完成判定基準 |
|---|---|---|---|---|---|
| F11 | 構造化検出系の統合 | `Request` + rules_doc | `inspect_request` 経路で宣言型ルールを評価可能にする | `DetectionResult` | (a)統合する場合：`detector.py` から構造化評価を呼べる経路が1本存在し等価テストパス、または (b)非統合確定：README と docs に「実験的・非統合」と明記し、未統合であることがテストで保証される |
| F12 | Rollback/Backtrack | 昇格履歴 + 対象generation | 直前以前の検出器へ復帰し履歴整合を保つ | 復帰後 `detector.py`/`genome.json` | `ROLLBACK_BACKTRACK_DESIGN.md` の設計通りCLIが実装され、任意generationへの復帰が成功、復帰後 F9 パス |
| F13 | NVD/CVEライブフェッチ | CVE ID | レート制限・秘密管理下で取得 | `ThreatRecord` | セキュリティレビュー完了の記録があり、無効化解除後も**exploit payloadを保存しない**ことがテストで保証（※スコープ判断は Owner 承認必須） |

> F13 はスコープ外維持（恒久無効のまま）も「完成」として許容する。その場合の完成条件は「無効化が意図的であることがコメント＋テストで明示されている」こと。

---

## 2. 非機能要件（Non-Functional Requirements）

| 区分 | 要件 | 測定可能基準 |
|---|---|---|
| **パフォーマンス（速度）** | 検出器レイテンシ | `avg_latency_ms ≤ 100.0`（genome `max_avg_latency_ms`）。実測gen4は0.003ms→十分マージン |
| | 候補評価 | Docker評価が `timeout=5秒` 以内に完了（タイムアウトは故障扱い） |
| | テストスイート | `pytest tests/` がCI上 `timeout-minutes: 10` 以内に完走 |
| **メモリ** | ポリシー検査 | `check_runtime_allocation_risks`/`check_literal_sizes` でリテラル・割当上限を強制（既存値を維持） |
| **スループット** | 進化サイクル | 1 run = 最大1コミット/1モデル呼出（genome `max_commits_per_run=1`, `max_model_requests_per_run=1`） |
| **セキュリティ** | 外部依存 | 本体ランタイム依存ゼロ（stdlibのみ）を維持。`pyproject` の `dependencies=[]` を保持 |
| | 秘密情報 | リポジトリ内にAPIキー・個人パス・実環境設定が**0件**（`config.backup.toml` 除去後、secret scan合格） |
| | 隔離 | 候補実行は常にdigest-pinned Docker内。host network無効、書込資格情報非伝播 |
| | 入力不変性 | `Request.query/headers` が `MappingProxyType` で実行時read-only |
| **可用性・信頼性** | 決定論性 | 同一候補・同一コーパスでスコアがビット同一（再現性100%） |
| | Fail-closed | 評価→昇格はアテステーション必須。malformed入力は全て安全側（非ブロック or 拒否）に倒れる |
| **拡張性・保守性** | 単一ファイル上限 | 新規/改修モジュールは**1ファイル1500行以内**を目標（`propose_mutation.py` 2653行は分割対象） |
| | ポリシーSSOT | AST検査ロジックは `core/policy.py` のみ。複製定義0件 |
| **ロギング・監視** | API台帳 | 全paid-credit呼出が `api_usage_ledger.json` に記録（http_200+token使用量） |
| | 秘密抑制 | 全出力文字列が秘密サニタイズを通過（`triage_s4_rerun.py` の `_safe_text` 同等基準） |
| **設定管理** | 状態正典 | `data/project_state.json`（機械可読）と `docs/PROJECT_STATE.md`（人間可読）が一致。権威順序がドキュメント化済 |
| | API有効化 | `live_model_enabled=true`/paid-credit設定は Owner 明示承認時のみ。scheduleは常にnoop |

---

## 3. 品質基準（Quality Criteria）

| 区分 | 完成基準（測定可能） |
|---|---|
| **コード品質：命名** | 文字化けファイル名0件／空白入りパス0件／拡張子なしソース・ドキュメント0件。`test_` 接頭辞は pytest対象のみ（`core/test_attacker.py` をリネーム or 除外設定明記） |
| **コード品質：構造** | 循環依存0件（`core.types` を底辺とする一方向DAGを維持） |
| **コード品質：依存** | 本体ランタイム外部依存0件。AST policy複製0件 |
| **型アノテーション** | `core/`・`scripts/` の全public関数に引数・戻り値型注釈あり（`from __future__ import annotations` 一貫使用を維持） |
| **静的解析：type check** | `mypy`（または同等）を導入し、`core/`・`scripts/`・`intelligence/` で**エラー0件**（設定をpyproject/CIに追加） |
| **静的解析：lint** | `ruff`（または `flake8`）導入、CIで**違反0件**。現状未導入のため新規追加が完成条件 |
| **例外処理** | `except: pass`/`except Exception: pass` は意図を1行コメントで明記、または握りつぶし→ログ化。新規コードで無言の汎用握りつぶし0件 |
| **セキュリティチェック** | CIに secret scanning ステップを追加し、main で検出0件。Docker digest allowlist が最新 |
| **テストカバレッジ** | §5参照（行カバレッジ目標値を設定） |

---

## 4. ドキュメント要件（Documentation Requirements）

| ドキュメント | 完成状態（必須項目） | 現状ギャップ |
|---|---|---|
| **README** | 概要／安全方針／アーキ図／**最新の正確なプロジェクト構成ツリー**（structured系・全scripts含む）／セットアップ／全CLIコマンド／CI構成／現フェーズ状態 | 構成ツリーが構造化検出系・一部scriptsを反映していない→**更新が完成条件** |
| **アーキテクチャ説明** | `AUTONOMOUS_IMMUNE_LOOP_ARCHITECTURE.md` が propose→apply→evaluate→promote の各境界と信頼モデルを記述 | 概ね完成。structured系の位置づけ追記が必要 |
| **API仕様** | `inspect_request`/`DetectionResult` の契約、変異パッチJSONスキーマ、構造化ルールスキーマを1箇所に集約 | スキーマは `STRUCTURED_DETECTOR_RULES_DESIGN.md` 等に分散→索引化が望ましい |
| **設定方法** | genome全フィールドの意味・許容値・デフォルトの一覧表 | 部分的。genomeフィールド辞書の整備が完成条件 |
| **開発手順** | クローン→`pip install -e .[dev]`→`pytest`→lint/typecheck の手順、ブランチ運用、PR監査ゲート | CLAUDE.md/AGENTS.mdに分散。開発者向けCONTRIBUTING相当の集約が望ましい |
| **運用手順** | 進化ループ実行手順、paid-credit承認フロー、ロールバック手順、トリアージ手順 | runbook類は充実。Rollback運用手順は F12 実装後に追記 |
| **セキュリティポリシー** | 攻撃機能非対象の宣言、秘密管理、隔離方針、脆弱性報告先（SECURITY.md） | 安全方針はREADME内に有り。独立した `SECURITY.md` が不在→新規作成が完成条件 |

**完成定義**：上記7種すべてが存在し、§8相当（README↔コード差分）のドリフトが0件であること。各docに `AI_DOC_META` ブロック（既存規約）があること。

---

## 5. テスト要件（Testing Requirements）

| 区分 | 完成基準 |
|---|---|
| **単体テスト** | `core/`・`scripts/`・`intelligence/` の全public関数にテストあり。現状2,488関数を維持・拡張 |
| **結合テスト** | propose→apply→evaluate→promote の連結が `test_workflow.py`/`test_evaluate_promote_contract.py` でカバー |
| **E2E（オフライン）** | offline-sample モードで1進化サイクルが完走するE2Eがgreen（API不要、CI実行可能） |
| **負荷/性能テスト** | `test_detector_performance.py` が `avg_latency_ms ≤ 100` を保証。コーパス拡大時の劣化検知テストあり |
| **セキュリティテスト** | AST bypass（alias/dunder/comprehension等）の回帰テスト、秘密サニタイズテスト、Docker隔離テストがgreen |
| **カバレッジ目標** | 行カバレッジ：`core/` **≥95%**、`scripts/` **≥85%**、全体 **≥90%**。`pytest --cov` をCIに追加し閾値を強制（現状カバレッジ計測未導入→導入が完成条件） |
| **クリティカルパス必須項目** | (1)誤受理0の証明、(2)決定論スコア、(3)fail-closed昇格、(4)予算超過時のAPI阻止、(5)MUTATION領域外不変、(6)秘密非出力 |
| **自動化範囲** | 上記すべてがCI（`ci.yml`）で自動実行。paid-creditのみ手動承認 |
| **手動テストが必要な領域** | 実Gemini paid-credit呼出（課金発生のため Owner 承認下で手動）、本番昇格のmerge判断 |

**「テスト完了」定義**：`pytest tests/ -x -q` 全パス＋カバレッジ閾値達成＋CI green＋クリティカルパス6項目すべてに対応テストが存在。

---

## 6. 完成条件の総合まとめ（最重要）

### 6-1. 「完成」とみなせる総合定義
本プロジェクトは、以下が**同時に**満たされたとき「完成（v1.0）」とみなす：

1. 機能要件 F1〜F10 が §3静的解析・§5テストをクリアした状態で確定
2. F11（構造化検出系）が「統合済み」または「非統合と明示」のいずれかで決着
3. リポジトリ衛生：秘密情報・文字化け名・命名不整合が**0件**
4. lint/type check/secret scan/カバレッジ閾値がCIで**強制**され全green
5. §4のドキュメント7種が揃い、README↔コードのドリフトが0件
6. `SECURITY.md` と genomeフィールド辞書が存在

> F12（Rollback実装）と F13（NVDフェッチ）は **v1.1スコープ**に分離可能。v1.0完成には F12 は「設計凍結のまま」、F13 は「無効化維持」でも可とする。

### 6-2. 完成までの作業一覧（優先度付き）

| 優先 | 作業 | 対応DoD | 区分 |
|---|---|---|---|
| **High** | `config.backup.toml` 削除＋`.gitignore`追加＋secret scan CI導入 | 2,3 | 衛生/安全 |
| **High** | 文字化け・空白・拡張子なしファイル名の正規化 | 3,4 | 衛生 |
| **High** | lint(ruff)＋type check(mypy)＋coverage閾値をCIに追加・強制 | 3,5 | 品質基盤 |
| **Medium** | F11：構造化検出系の統合 or 非統合の決着＋テスト | 1-B | 機能 |
| **Medium** | README構成ツリー最新化＋README↔コードdrift解消 | 4 | ドキュメント |
| **Medium** | `SECURITY.md` 作成＋genomeフィールド辞書整備 | 4 | ドキュメント |
| **Medium** | `propose_mutation.py`（2653行）責務分割 | 2,3 | 保守性 |
| **Medium** | `core/test_attacker.py` リネーム or pytest除外明記 | 3 | 命名 |
| **Low** | F12 Rollback/Backtrack 実装（v1.1可） | 1-B | 機能 |
| **Low** | `task_reports/` 整理・状態同期自動化強化 | 2 | 保守性 |
| **Low** | F13 NVDフェッチ（Owner承認下、v1.1+） | 1-B | 機能 |

### 6-3. 現在地マップとのギャップ

| 領域 | 現在地 | 完成条件 | ギャップ |
|---|---|---|---|
| コア免疫ループ | 約90%実装・gen4実績 | F1-F10確定 | 小（テスト/静的解析の形式化のみ） |
| 品質基盤 | テストは厚いがlint/type/cov未強制 | CI強制 | **中**（ツール未導入） |
| リポジトリ衛生 | 設定混入・文字化け名あり | 0件 | **中**（即着手可） |
| 構造化検出系 | 実装あり・未統合 | 統合 or 明示 | 中（方針決定が先） |
| ドキュメント | 量は豊富だがドリフト・SECURITY不在 | 7種完備・drift0 | 中 |
| Rollback/NVD | 設計のみ/無効化 | v1.1へ分離可 | 小（スコープ調整で吸収） |

### 6-4. 推定工数（ざっくり）

| フェーズ | 内容 | 規模感 |
|---|---|---|
| 衛生・安全（High） | 設定除去・命名正規化・secret scan | **1〜2人日** |
| 品質基盤（High） | ruff/mypy/coverage導入・既存違反修正 | **3〜5人日** |
| 機能決着（Medium） | F11統合判断・実装/明示 | **3〜8人日**（統合する場合上振れ） |
| ドキュメント（Medium） | README更新・SECURITY.md・genome辞書 | **2〜4人日** |
| リファクタ（Medium） | propose_mutation分割・rename | **3〜5人日** |
| **v1.0合計** | | **約12〜24人日（2.5〜5週間／1人想定）** |
| v1.1（Low） | Rollback実装・NVD検討 | +5〜10人日 |

### 6-5. リスクと対策

| リスク | 影響 | 対策 |
|---|---|---|
| `propose_mutation.py` 分割でAST検証ロジックを破損 | 誤受理混入＝安全境界崩壊 | 分割前に該当テスト（`test_ast_policy`/`test_propose_*`）をgreen固定し、リファクタ後も全パスを必須条件化 |
| lint/type導入で大量の既存違反が露出 | 工数膨張 | 段階導入（まずcore/→scripts/）、baseline許容→新規のみ厳格化 |
| 構造化検出系の統合がdetector契約を変える | gen4ベースライン劣化 | 統合は等価テスト（`test_structured_detector_equivalence`）で `DetectionResult` 不変を保証、不可なら非統合明示に切替 |
| FROZENファイル（core/scripts/data/.github）への無断変更 | 安全境界・履歴破壊 | 変更は必ずタスクプロンプト＋Owner承認下。data/genomeは触らない |
| paid-credit誤実行による課金 | コスト・安全方針違反 | scheduleはnoop固定、live設定は Owner 明示承認のみ、予算ゲートで二重防止 |
| ドキュメント整合テスト（`test_*_docs.py`）の破綻 | CI赤化 | README/docs更新時は対応docsテストを同一PRで更新 |

---

> 本DoDは As-Is Map（アップロードされたリポジトリスナップショット解析）から導出した派生ドキュメントである。数値・状態の正典は `data/genome.json` / `data/project_state.json` / `docs/PROJECT_STATE.md` であり、矛盾時はそれらが優先する。
