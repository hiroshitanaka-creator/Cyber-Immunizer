# タスク完了報告 — PR #151

## 概要

PR #151（`codex/add-read-only-cli-for-evolution-report`）の "Request Changes" レビューに基づき、
read-only 進化レポート CLI の修正実装を `claude/pr-151-review-changes-8922ts` ブランチに作成した。
PR #150 はすでに merge 済み（`419c18a`）であり、blocking prerequisite は解消されている。

## 変更ファイル一覧

| ファイル | 操作 |
|---|---|
| `cli/__init__.py` | 新規作成 |
| `cli/report.py` | 新規作成 |
| `pyproject.toml` | 修正（`cli*` を include に追加） |
| `README.md` | 修正（CLI セクションを追加） |
| `tests/test_report_cli.py` | 新規作成 |
| `docs/task_reports/TASK_REPORT_PR151.md` | 新規作成（本ファイル） |

## 主な変更内容

### レビュー指摘 7 項目の対応状況

| # | 指摘 | 対応 |
|---|---|---|
| 1 | PR #150 を先にマージ | ✅ main に merge 済み (`419c18a`) |
| 2 | 外部ユーザー価値の主張を削除 | ✅ README・コード docstring ともに Owner/auditor 向けのみ |
| 3 | Generation 0 を計測改善として使わない | ✅ `_first_measured_generation()` が gen 0 をスキップ、`_score_for_display()` が "unevaluated placeholder" と表示 |
| 4 | 保護パスへの export を拒否 | ✅ `_is_protected_export_path()` が `data/**` 等を拒否、exit non-zero |
| 5 | データパスに明示的引数を要求 | ✅ `--repo-root` または `--history-path` が必須（`required=True` の mutually-exclusive group） |
| 6 | 未検証の console-script/rich を追加しない | ✅ `[project.scripts]` なし、`rich` 依存なし。`cli*` を setuptools include に追加のみ |
| 7 | Codex P2 スレッドを解決 | ✅ Gen 0 sentinel・export 保護・データパス要求の3つがコードで対応済み |

### cli/report.py 設計ポイント

- `_first_measured_generation()` — gen 0 をスキップし、最初の数値スコアを持つ世代を返す
- `_score_for_display()` — gen 0 には "unevaluated placeholder" を返し、スコア値を表示しない
- `_is_protected_export_path()` — `_PROTECTED_REPO_PATHS` に含まれるパスへの export を拒否
- `main()` — `--repo-root` / `--history-path` のいずれかが必須（package install 想定なし）
- 依存: stdlib のみ + `core.types.FitnessReport`。`rich` 不使用

### pyproject.toml 変更点

```
include = ["core*", "intelligence*", "scripts*", "cli*"]
```

`[project.scripts]` なし。`[project.optional-dependencies]` に `cli` extra なし。

### README.md 追加セクション

"進化レポートCLI（Owner / auditor validation only）" セクションを追加。
外部ユーザー価値・実世界防御価値を証明しないことを明記。
`python -m cli.report --repo-root .` による直接実行のみを案内。

## 後検証結果

```
python3 -m pytest tests/test_report_cli.py -x -q
7 passed in 0.04s

python3 -m pytest tests/ -x -q
2668 passed, 5 warnings in 13.52s
```

- Gen 0 が計測スコアデルタに使われないことを確認: ✅
- Gen 1 → current をデフォルト比較に使うことを確認: ✅
- `data/genome.json` への export が拒否されることを確認: ✅
- `data/evolution_history.json` への export が拒否されることを確認: ✅
- `--history-path` 明示指定が動作することを確認: ✅
- CLI 出力に symbolic corpus / real-world limitation 文言が含まれることを確認: ✅

## 残存事項・注意点

- console-script エントリポイント（`cyber-immunize` コマンド）は、install 検証が完了するまで追加しない。
  現時点では `python -m cli.report` による直接実行のみサポート。
- PR #151 の PR body（"externally visible"・"third parties can verify" の記述）は GitHub 上で更新済み。
- Layer 2 value validation が満たされるまで外部化（PyPI 配布・public demo・GitHub Action template）はブロック。

## 完了レイヤー宣言

`[ ] None`（本タスク報告ファイル自体はドキュメント整備）

CLI 実装は Layer 2 validation support tooling として機能するが、Layer 2 完了単独では宣言しない。
Owner の判断を要する。
