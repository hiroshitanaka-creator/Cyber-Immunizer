# タスク完了報告 — L1-F14（structured detector 統合判断）の決定記録

## 概要
DoD で唯一未解決だった Layer 1 項目 `L1-F14`（structured detector を「統合」か「実験的・非統合と明記」かを決定し記録する）を決着させた。現状は **option (b)：structured_* は明示呼び出しのオプトイン経路であり、昇格対象の runtime detector には意図的に自動統合しない** ことがコードとテストで確立済みだったが、確定した「決定記録（DECISION）」が存在しなかった。`docs/STRUCTURED_DETECTOR_RULES_DESIGN.md` に日付・証拠付きの正式な決定記録セクションを追記した。

## 変更ファイル一覧
- 変更: `docs/STRUCTURED_DETECTOR_RULES_DESIGN.md`（「L1-F14 Decision Record」セクションを追加）
- 追加: `docs/task_reports/TASK_REPORT_L1F14_decision.md`（本報告）

## 主な変更内容
- 決定: option (b)。`core/detector.py::inspect_request` は structured rules に未配線のまま維持。structured 経路は `core/runtime_selector.py` または `core/structured_detector.py` を明示呼び出しした場合のみ到達。
- 機械検証可能な証拠を引用:
  - 分離: `tests/test_structured_detector_integration.py::test_default_detector_source_has_no_structured_integration_references`（detector に structured 参照が混入したら失敗）
  - 暗黙起動なし: `...::test_default_detector_still_requires_no_explicit_structured_rules`
  - 等価性: `tests/test_structured_detector_equivalence.py::test_corpus_level_equivalence_for_main_and_adaptive_tiers`（全6ティアで blocked / matched_signals が legacy と一致）
- 未決定事項を明記: Phase 5–7（proposer 出力の structured 化／自動 runtime 統合／raw-Python 経路の retirement）は Owner ゲートの将来作業であり、本記録は authorize しない。

## 後検証結果
- 引用テスト実行: `python -m pytest tests/test_structured_detector_integration.py tests/test_structured_detector_equivalence.py -q` → **28 passed**（引用の正確性を確認）。
- `core/**` `scripts/**` `.github/**` `data/**` は未編集（docs のみ）。

## Which layer did this task advance?
- [x] Layer 1 — Research Foundation（DoD の未解決項目 L1-F14 を解決）
- [ ] Layer 2 — Value Validation
- [ ] Layer 3 — AI Operation Control
- [ ] None

docs-only 分類:
- [x] Current-State SSOT / Audit Evidence（DoD が要求する「決定の記録」。証拠引用付きで現在状態を確定）

## 残存事項・注意点
- 対象文書には旧来 AI_DOC_META ブロックが無い（規約以前の文書）。フル meta ブロックの後付けは scope 過剰と判断し見送った。必要なら別タスクで整備可能。
- option (a)（自動 runtime 統合）への移行は Owner 判断（Phase 6）。本記録は現状を option (b) として固定するのみ。
