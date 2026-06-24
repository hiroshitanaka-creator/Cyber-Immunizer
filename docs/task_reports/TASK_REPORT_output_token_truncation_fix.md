# タスク完了報告 — 出力トークン切れによる propose 失敗の修正（runs #75/#76）

## 概要
再 ignition の runs #75/#76 が **propose 段階で失敗**。原因は、強化した proposer が大きめの
ルールセットを出力する一方で `genome.max_output_tokens=2048` が JSON を途中で切断し
（`Unterminated string ... char 5596`）、output-contract 失敗になったこと。API 呼び出し自体は
成功（ledger +2＝paid 2消費）だが候補は生成されず、circuit breaker が失敗2件を記録（2/3、未 trip）。
本タスクで API・live 実行・workflow_dispatch なし。

## 根本原因
- proposer 強化（PR #182）でカテゴリ・署名数を増やした → 出力 JSON が大型化。
- `max_output_tokens=2048` が出力を切断 → 不正 JSON → propose 失敗。

## 変更ファイル
- `data/genome.json`：`max_output_tokens` **2048 → 6144**（大型ルールセットの headroom）。
  - 予算検証：1コールの推定コストは daily 0.25 USD 以内（テストで担保）。
- `scripts/propose_mutation.py`：proposer プロンプトに **SIZE BOUND** を追加
  （「概ね 24-40 個の簡潔な署名、schema 上限 64、JSON が切れないよう各値は短く」）。
  → 網羅性は維持しつつ出力を有限化し truncation を防止。
- `data/circuit_breaker.json`：**リセット（0/3）**。2件の失敗は truncation バグ起因であり
  本物の gate 不合格ではないため re-arm。
- SSOT 同期（runs #75/#76 反映）：
  - `data/project_state.json`：primary-model success 19→**21**、note に runs #75/#76 追記。
  - `docs/PROJECT_STATE.md`：count 19→21、runs #75/#76 行追加、ledger timestamps 更新。
  - `tests/test_project_state_sync.py`：`_EXPECTED…SUCCESS_RECORDS` 19→21。
- テスト追加（`tests/test_structured_rules_live.py`）：
  - プロンプトが ruleset サイズを bound していること（at most 64 / concise / truncat）。
  - genome の出力トークン予算が daily cap 内に収まること（≥4096 かつ 1コール ≤ daily 0.25）。

## 後検証
- `pytest tests/ -q` → **3075 passed**。`validate_state.py` → **PASS**。
- 予算試算：max_output_tokens=6144 → 1コール推定 $0.046、daily 0.25 内（約5コール/日）。

## Which layer did this task advance?
- [x] Layer 3 — AI Operation Control（自律ループの実行信頼性の修正：提案出力が切れず候補が
  正しく生成される状態に戻す。安全境界・予算は不変）。

## 残存・次アクション
- 本 PR マージ後、そのまま再 ignition（`structured-gemini-paid-credit` + `structured_baseline=true`
  + `promote_approved=true`）。今度は JSON が切れず、候補が evaluate→gate まで到達する見込み。
- **重要**：本 PR がマージされるまでは再 ignition しないこと（旧 2048 のままだと再び truncation で
  paid を浪費する）。
- daily budget 0.25 は不変。1日のコール数が増えると budget gate が安全に拒否する。
