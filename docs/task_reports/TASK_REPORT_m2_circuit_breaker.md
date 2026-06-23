# タスク完了報告 — M2：サーキットブレーカー（連続失敗カウンタ／自動停止）

## 概要
自律ループを「安全に回し続ける」M2 の残りを実装した。**連続して失敗する構造化進化サイクル**を
カウントし、閾値に達したら**発動（trip）**して、以降の **paid 実行を fail-closed で拒否**する。
Owner が `--reset` するまで paid 不可。価値の出ないループに paid クレジットを焼かれ続けるのを防ぐ。
本タスクで API・live 実行・workflow_dispatch なし。

## Owner 設計判断（確認済み）
- 発動時の挙動：**paid 実行を自動拒否**（推奨案）。
- 失敗の定義：**昇格失敗すべて**（adoption-gate 不合格・pre-publish health check ロールバック・
  tool failure を失敗としてカウント）。健全な昇格で counter リセット。

## 追加・変更ファイル
- 追加: `scripts/circuit_breaker.py` — stdlib のみの状態機械＋CLI。
  - `record_outcome`（success で counter=0／failure で +1、閾値到達で trip）、`reset_state`、
    `decide_outcome`（CI ジョブ結果→success/failure/None を Python で判定＝単体テスト可能）、
    `load_state`（欠損→default、破損→ValueError）。
  - CLI: `--check`（trip もしくは破損で exit1＝gate）/ `--status` / `--record-success` /
    `--record-failure` / `--reset` / `--record-from-cycle` / `--threshold`。
  - **一度 trip したら success では trip 解除しない**（無料 offline success が paid 経路を勝手に
    再開しないよう、解除は Owner `--reset` のみ）。
- 追加: `data/circuit_breaker.json` — 初期 untripped 状態（threshold=3）。
- 変更: `.github/workflows/immunization_loop.yml`
  - propose に **paid モード限定の pre-flight gate**（`circuit_breaker.py --check`、fail-closed）。
  - 新ジョブ `persist-circuit-breaker`（contents:write・鍵なし）：構造化サイクル後に
    `--record-from-cycle` で結果を記録し `data/circuit_breaker.json` を commit/push（rebase-retry）。
- 追加: `docs/CIRCUIT_BREAKER_RUNBOOK.md` — Owner 向け操作マニュアル。
- 追加: `tests/test_circuit_breaker.py`（状態機械・load/save・decide_outcome 全分岐・CLI・
  committed state・workflow 配線）。
- 変更: `tests/test_repo_invariants.py` — `allowed_write_jobs` に `persist-circuit-breaker` 追加。

## 安全性
- gate は読取専用・fail-closed。破損状態でも refuse（fail-open しない）。
- `persist-circuit-breaker` は鍵なし・write は `data/circuit_breaker.json` のみ・生成コード非実行。
- noop / offline / preflight は無料なので gate しない。trip 解除は Owner のみ。
- canonical（genome/project_state/evolution_history）には一切触れない decoupled な運用状態。

## 後検証
- `pytest tests/ -q` → **3068 passed**。`validate_state.py` → PASS。
- CLI スモーク：threshold=2 で失敗2回 → `--check` exit=1（TRIPPED）→ `--reset` → `--check` exit=0。
- workflow 配線テスト：gate が paid step より前・`persist-circuit-breaker` ジョブ存在・
  `--record-from-cycle` 参照・hyphenated job id は bracket 記法。

## Which layer did this task advance?
- [x] Layer 3 — AI Operation Control（自律運用の安全制御：価値が出ない自走を自動停止し、
  paid クレジットを保護。Owner が明示的に再武装するまで止める）

## 残存・次アクション
- 実点火（`structured-gemini-paid-credit` ＋ `promote_approved=true` ＋ `structured_baseline`）は
  Owner トリガ。発動後の運用は本 runbook に従う。
- 失敗カウントの対象は構造化進化パス＋paid propose 失敗（mission の本線ループ）。legacy raw-Python
  パスは対象外（設計上のスコープ）。
