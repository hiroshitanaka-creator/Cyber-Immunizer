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

## 解決方針（Codex PR #183 P1 反映 — 設定は一切変更しない別解）
当初は `max_output_tokens` を 2048→6144 に引き上げたが、Codex P1（paid/モデル設定の変更は
Owner 承認が必要）と Owner 指示「他の方法を探す」を受け、**設定を変えない別解**に切替：
**proposer に COMPACT（最小化）JSON を出力させる**。プリティ印字が truncation の主因で、
最小化すれば 1署名あたりのトークンが大幅に減り、網羅的ルールセットが **2048 のまま**収まる。

## 変更ファイル
- `data/genome.json`：`max_output_tokens` は **2048 のまま据え置き**（変更なし）。
- `scripts/propose_mutation.py`：
  - 例（shape example）を **minified**（`separators=(",",":")`）に変更 → モデルが compact を模倣。
  - SIZE BOUND を「**COMPACT/minified JSON 必須**・概ね 24-40 簡潔署名・schema 上限64・各値短く」に。
  → 網羅性を維持しつつ 2048 内に収め truncation を防止。
- `data/circuit_breaker.json`：**リセット（0/3）**。2件の失敗は truncation バグ起因であり re-arm。
- SSOT 同期（runs #75/#76 反映）：
  - `data/project_state.json`：primary-model success 19→**21**、note に runs #75/#76 ＋ 解決方針追記。
  - `docs/PROJECT_STATE.md`：count 19→21、runs #75/#76 行追加。
  - `tests/test_project_state_sync.py`：`_EXPECTED…SUCCESS_RECORDS` 19→21、doc-count テストを
    **動的化**（宣言値と一致を要求・stale `**15**` 不在を検査）。
- テスト（`tests/test_structured_rules_live.py`）：
  - プロンプトが size bound ＋ **compact 出力**を要求していること。
  - 例が minified であること。
  - 1コールが daily cap 内（現行 2048）に収まること。

## 後検証
- `pytest tests/ -q` → 全通過。`validate_state.py` → PASS。
- max_output_tokens=2048 据え置き。compact 出力で網羅的ルールセットが 2048 内に収まる設計。

## Which layer did this task advance?
- [x] Layer 3 — AI Operation Control（自律ループの実行信頼性の修正：提案出力が切れず候補が
  正しく生成される状態に戻す。安全境界・予算は不変）。

## 残存・次アクション
- 本 PR マージ後、再 ignition（`structured-gemini-paid-credit` + `structured_baseline=true`）。
  compact 出力で JSON が切れず、候補が evaluate→gate まで到達する見込み。
- **`promote_approved` は既定で `false`** にして再実行すること。これは truncation 修正の
  retry であり、`promote_approved=true` にすると evaluate 合格時に structured ルールが
  main の active detector へ**自動昇格**されてしまう（`.github/workflows/immunization_loop.yml`
  の promote ジョブが `--owner-approved` で発火）。**その特定の run について Project Owner が
  昇格を明示承認した場合に限り** `promote_approved=true` を指定する。
- **重要**：本 PR がマージされるまでは再 ignition しないこと（compact 化前は再び truncation で
  paid を浪費する）。
- paid/モデル/予算設定は一切変更していない（max_output_tokens=2048 据え置き、daily 0.25 不変）。
