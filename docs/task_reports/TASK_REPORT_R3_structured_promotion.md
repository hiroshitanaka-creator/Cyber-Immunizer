# タスク完了報告 — R3：構造化ルールを本番検出器へ昇格する経路（キーストーン）

## 概要
「検出器そのものを現実能力へ進化させる」ゴールの最大の障害だった **「構造化ルールを本番検出器に昇格させる経路が存在しない」** を解消した。runtime リゾルバ（`core/active_detector.py`）と fail-closed な昇格スクリプト（`scripts/promote_structured_candidate.py`）を追加し、構造化ルールセットを「動いている検出器」に切り替えられるようにした。**既定は legacy のままで挙動不変**。paid-credit 不使用。Project Owner 承認済みの FROZEN 改修。

## 変更ファイル一覧
- 追加: `core/active_detector.py`（runtime リゾルバ）
- 追加: `scripts/promote_structured_candidate.py`（構造化ルール昇格、fail-closed）
- 変更: `data/genome.json`（`"detector_mode": "legacy"` を追加。既定で挙動不変）
- 追加: `tests/test_active_detector.py`（12件）
- 追加: `tests/test_promote_structured_candidate.py`（6件）
- 変更: `docs/PROJECT_STATE.md`（R3 経路の存在を current-state に記録）
- 追加: `docs/task_reports/TASK_REPORT_R3_structured_promotion.md`（本報告）

## 設計のポイント
- **runtime リゾルバ**：`inspect_active(request)` が genome の `detector_mode` を見て legacy / structured_rules を分岐。構造化モードでルールが読めない/不正な場合は**安全に legacy へフォールバック**（例外を出さず DetectionResult 契約維持）。
- **昇格の fail-closed 強化**：別ファイルの fitness レポートを信用せず、**昇格スクリプト自身が現実ゲート（score＋adoption gate＋adaptive floor＋parity guard）を再評価**し、合格時のみ昇格。さらに `--owner-approved` 必須。偽装レポートの余地なし。
- **昇格の副作用**：`data/active_structured_rules.json` を atomic 書き込み → genome を `detector_mode="structured_rules"`・hash・best_score・generation++ に更新 → evolution_history に `mode="structured_rules"` を追記。既存 `promote_candidate.py` と同じ fail-closed 順序。

## 後検証結果
- 新規テスト: `pytest tests/test_active_detector.py tests/test_promote_structured_candidate.py -q` → **18 passed**。
- 全体: `pytest tests/ -q` → **2980 passed**（変更前 2962 + 新規 18）。
- `python scripts/validate_state.py` → PASS（genome の新フィールドは検証を壊さない）。
- スモーク: `--owner-approved` 無し→拒否、有り→再評価合格で genome が legacy→structured_rules、generation++、active rules 書込、history 追記を確認。

## Which layer did this task advance?
- [x] Layer 1 — Research Foundation（自律ループの欠落部品＝構造化ルール昇格経路を実装）
- [ ] Layer 2 — Value Validation（本経路を使って現実能力の検出器を昇格させるのは R4 以降）

## 残存事項・注意点
- 既定 `detector_mode="legacy"` のため、本番検出器の挙動は本 PR では一切変わらない。
- 実際に「現実能力の検出器」を昇格させるには、現実ルールセット（Owner 外部供給）＋現実コーパスで `promote_structured_candidate.py --owner-approved` を実行する（R4：Gemini 自律提案は別途 paid-credit 承認）。
- 生Python 進化経路の retirement（設計文書 Phase 7）は将来作業。
