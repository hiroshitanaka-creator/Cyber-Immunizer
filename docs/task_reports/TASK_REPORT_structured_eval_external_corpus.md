# タスク完了報告 — structured-rules 評価器に外部コーパス入力を追加（FROZEN 改善）

## 概要
Layer 2 を妨げていた FROZEN を1点改善した。`scripts/evaluate_structured_rules_candidate.py` は `core.test_attacker.load_test_cases()` を引数なしで呼び、本物の昇格グレード採点（score＋adoption gate＋adaptive floor＋parity guard）が symbolic な `data/` コーパスに固定されていた。`--corpus-dir` と per-tier パス上書きを追加し、Owner 供給の「現実的だが安全に中立化された」コーパス（リポジトリ外）を同じ採点経路に流せるようにした。Project Owner の事前承認（FROZEN 改修＋テスト追加）済み。`core/` は無改修。

## 変更ファイル一覧
- 変更（FROZEN, 承認済み）: `scripts/evaluate_structured_rules_candidate.py`
- 変更（FROZEN, 承認済み）: `tests/test_evaluate_structured_rules_candidate.py`（回帰テスト9件追加）
- 変更: `fixtures/README.md`（gate-grade 評価の使用法を追記）
- 追加: `docs/task_reports/TASK_REPORT_structured_eval_external_corpus.md`（本報告）

## 主な変更内容
- `evaluate_structured_rules(...)` に `corpus_paths: dict[str, Path] | None` を追加。
- ヘルパー `_resolve_corpus_paths` / `_load_test_cases_kwargs` を追加（`--corpus-dir` + per-tier 上書きを `load_test_cases` の引数へ変換）。
- CLI に `--corpus-dir` と `--benign-path` / `--attack-path` / `--regression-path` / `--holdout-path` / `--counterfactual-path` / `--drift-path` を追加。
- 未指定時は従来通り `data/` を使用（後方互換）。供給コーパスは read-only 入力。新たな exploit はコミットしない。
- `core/test_attacker.load_test_cases()` は既に per-tier パス引数を備えていたため core 改修は不要。

## 後検証結果
- `python scripts/evaluate_structured_rules_candidate.py --rules fixtures/structured_rules/symbolic_equivalent.json --baseline --json` → 既定で `data/` 使用、passed_gate=True（後方互換維持）。
- `--corpus-dir <外部dir>`（benign3/attack2/reg2）→ `total_cases=7`、tp=3、tn=4、adaptive 全 1.0、gate pass。供給ディレクトリが実際に使われることを確認。
- `--attack-path <1件>` のみ上書き → `total_cases` が「data benign + 上書き attack(1) + data regression」に変化（混在動作確認）。
- `--corpus-dir <存在しないdir>` → success=False / evaluation_completed=False / exit 1（fail-closed）。
- 新規回帰テスト: `python -m pytest tests/test_evaluate_structured_rules_candidate.py -q` → **116 passed**。
- 全体: `python -m pytest tests/ -q` → **2962 passed**（変更前 2953 + 新規 9）。
- `core/detector.py` は未編集（既存の分離検証テストも green 継続）。

## Which layer did this task advance?
- [x] Layer 1 — Research Foundation（昇格グレード採点経路を外部コーパスへ開放。Layer 2 評価の実行可能な前提条件を整備）
- [ ] Layer 2 — Value Validation（**未達**。実コーパスは Owner がリポジトリ外から供給し、証拠を Owner がレビュー・受理して初めて達成）
- [ ] Layer 3 — AI Operation Control
- [ ] None

## 残存事項・注意点
- 真の Layer 2 達成は Owner 供給の現実コーパス（外部・read-only・防御専用）での評価＋Owner 受理が必要。
- 衛生上の DoD 違反（ネスト空ディレクトリ `Cyber-Immunizer/`、スペース入り `text task-prompt-architect-gpt/`、拡張子なし `引き戻しプロンプト`）は本タスク範囲外、別途対応。
