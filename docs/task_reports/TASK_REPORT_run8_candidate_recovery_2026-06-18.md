# タスク完了報告 — run 8 candidate recovery (2026-06-18)

## 概要

run 8 (GitHub Actions run id 27683267711) で adoption gate を通過した候補コードを、
push-race による promote 失敗から回復し、`core/detector.py` generation 3 として昇格した。
Gemini API 呼び出し・新たな paid-credit run は行っていない。

## 変更ファイル一覧

| ファイル | 種別 | 変更内容 |
|---|---|---|
| `core/detector.py` | 変更 | generation 3 候補コード (hash c488855e…) を書き込み |
| `data/genome.json` | 変更 | generation → 3, best_score → 947.66, current_detector_hash → c488855e… |
| `data/evolution_history.json` | 変更 | generation 3 エントリ追加 (score=947.66, passed_adoption_gate=true) |
| `data/project_state.json` | 変更 | state_id / run_8_triage / promote_approved / next_action 更新 |
| `docs/PROJECT_STATE.md` | 変更 | 現在状態を generation 3 昇格済みに更新 |
| `scripts/update_readme.py` | 変更 | 新 state_id・next_action・promote_approved=true のワーディング追加 |
| `tests/test_project_state_sync.py` | 変更 | 旧 state_id / next_action / promote_approved=false のハードコード値を新状態に更新 |
| `README.md` | 変更 | `scripts/update_readme.py` 経由でステータスブロック更新 |

## 主な変更内容

- **候補ハッシュ検証**: SHA-256 = `c488855e44411912a0efee50fcecc2e5575b3b51e6a128a0c6f0b8df4e78a0b6` を確認してから昇格
- **replacement_stripped 復元**: 26行 + blank line 3箇所 (after `surface = ...`, after `matched.append(token)`, between True/False return) = 1126 chars
- **promote_candidate.py 実行**: exit 0, generation=3, score=947.66, detector_hash=c488855e…
- **後検証**: `evaluate_candidate.py --soft-reject` → is_tool_failure=false (soft rejection expected — genome.best_score=947.66 と同値のため)
- **project_state.json**: state_id → `phase3_run8_candidate_recovered_generation3_pending_owner_merge`
- **promote_approved**: false → true (run 8 candidate promoted to generation 3 via owner-audited recovery)

## 後検証結果

```
core/detector.py hash = c488855e44411912a0efee50fcecc2e5575b3b51e6a128a0c6f0b8df4e78a0b6  ✓
data/genome.json: generation=3, best_score=947.66                                         ✓
data/evolution_history.json: last entry generation=3, passed_adoption_gate=true           ✓
pytest tests/ -q: 2179 passed, 5 warnings                                                 ✓
diff --name-only: api_usage_ledger.json 未変更, .github/workflows/ 未変更                  ✓
```

## 残存事項・注意点

- この PR はオーナーマージ待ち。マージ後、次の paid-credit run (オーナー承認時) は `previous_best=947.66` を上回る必要がある。
- `data/api_usage_ledger.json` は変更していない (run 8 の ledger 記録は既存のまま)。
- run 7 は API/token success のみで未トリアージのまま (このタスクスコープ外)。
