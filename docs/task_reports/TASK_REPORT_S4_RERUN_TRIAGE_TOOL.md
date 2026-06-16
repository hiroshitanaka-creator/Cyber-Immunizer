# 修正完了報告 — PR #95 S4 Rerun Triage Tool

## 1. 変更概要

PR #95 の triage tool を、現行 GitHub Actions workflow・evaluate_candidate.py 実出力・
promotion gate 運用・secret-safety 要件と整合する状態に修正した。
CI 失敗（ledger count drift）を修正し、全 1990 テストが通過。

---

## 2. 修正した Blocking Findings

| Finding | 対応内容 | 状態 |
|---|---|---|
| CI failure: ledger has 5 but project_state declares 4 | mainにrebase; project_state.json を 4→5; test assertion を 4→5 | ✅ 修正 |
| fitness_report.json 実artifact形式 (wrapper shape) 非対応 | `_extract_fitness_payload()` 追加、flat/wrapper 両対応 | ✅ 修正 |
| promote_eligible 推奨文が誤解を招く (新run=同候補promote誤示唆) | current workflowは同一run内promote-only と明示、trigger文削除 | ✅ 修正 |
| secret-safe rendering が一元化されていない | `_safe_text()` 追加、全dynamic文字列を経由させる | ✅ 修正 |
| artifact directory layout (flat/subdir) 非対応 | `_resolve_artifact()` 追加、flat優先/subdir fallback | ✅ 修正 |
| promote_result.json をcurrent workflow生成と誤記 | future-reserved明示、expected-artifacts表から削除 | ✅ 修正 |
| malformed JSON policy がdocs/impl/testsで不一致 | mutation_patch=propose_failed+warning / fitness=tool_failure で統一 | ✅ 修正 |
| 新テスト10件不足 | 合計19件追加 (wrapper shape/secret/subdir/semantics/unit tests) | ✅ 追加 |

---

## 3. 変更ファイル一覧

| ファイル | 内容 |
|---|---|
| `scripts/triage_s4_rerun.py` | 全改良（_extract_fitness_payload, _safe_text, _resolve_artifact, promote semantics修正） |
| `tests/test_s4_rerun_triage.py` | 18→37テスト（19件追加） |
| `docs/S4_RERUN_CHECKLIST.md` | Local Triage Tool セクション全面更新 |
| `data/project_state.json` | gemini_3_flash_preview_success_records: 4→5 (CI fix) |
| `tests/test_project_state_sync.py` | assert actual == 4 → assert actual == 5 (CI fix) |
| `docs/task_reports/TASK_REPORT_S4_RERUN_TRIAGE_TOOL.md` | 本報告（更新） |

原則変更禁止ファイル（変更なし）:
`core/policy.py` / `core/detector.py` / `data/api_usage_ledger.json` /
`data/genome.json` / `data/evolution_history.json` / `.github/workflows/immunization_loop.yml`

---

## 4. 実装詳細

### fitness_report normalization

```python
def _extract_fitness_payload(report: dict) -> dict | None:
    nested = report.get("fitness_report")
    payload = nested if isinstance(nested, dict) else report
    if not isinstance(payload, dict):
        return None
    gate = payload.get("passed_adoption_gate")
    if not isinstance(gate, bool):
        return None
    return payload
```

- `r.get("fitness_report") or r` の現行workflow実装と同じ戦略
- nested fitness_report がある場合は inner dict を使用（core.fitness のメトリクスを含む）
- `passed_adoption_gate` が bool でない場合は fail-closed で None を返す
- flat/wrapper 両形式のテスト: test 19/20（wrapper rejected/passed）

### promotion semantics

- 旧: `"before triggering a new workflow_dispatch with promote_approved=true"` （誤解を招く）
- 新: `"The current standard workflow promotes only within the same run when promote_approved=true; this local tool does not promote and does not preserve a promotion-capable artifact handoff."`
- `promote_result.json` を expected-artifacts 表から削除し future-reserved と明記
- test 29: trigger/workflow_dispatch の誤示唆がないことを確認

### secret-safe rendering

```python
_SECRET_REPLACEMENT = "[SUPPRESSED_SECRET_PATTERN]"

def _safe_text(value: object) -> str:
    text = value if isinstance(value, str) else str(value)
    return _SECRET_REPLACEMENT if _contains_secret(text) else text
```

全 user-visible dynamic 文字列（evidence/warnings/action/JSON/Markdown）が必ず `_safe_text()` を経由する。
secret 検出時は値全体を `[SUPPRESSED_SECRET_PATTERN]` に置換（部分置換不可、保守的設計）。

カバレッジ:
- `api_usage_ledger` の `model`・`api_mode` フィールド (test 23/24)
- `rejection_reasons` の各要素 (test 18/22)
- `passed_adoption_gate` の予期しない値の型名のみ出力し値は出さない (test 25)
- Markdown 出力 (test 26)

### artifact layout handling

```python
def _resolve_artifact(artifacts_dir: Path, filename: str) -> tuple[Path | None, str]:
    flat = artifacts_dir / filename
    if flat.exists():
        return flat, "flat"
    subdir_name = _ARTIFACT_SUBDIRS.get(filename)
    if subdir_name:
        sub = artifacts_dir / subdir_name / filename
        if sub.exists():
            return sub, f"subdir:{subdir_name}"
    return None, "not_found"
```

- flat 優先 / subdir fallback (test 27/28)
- 採用したパス種別を evidence に記録
- `actions/download-artifact` の subdir layout と compatible

### malformed JSON policy

| アーティファクト | 方針 | 理由 |
|---|---|---|
| `mutation_patch.json` malformed | `propose_failed` + warning | valid patch 未生成とみなせる |
| `fitness_report.json` malformed | `tool_failure` (fail-closed) | evaluate 結果不明、gate 値不確定 |
| `fitness_report.json` root が array | `tool_failure` (fail-closed) | 同上 |
| `passed_adoption_gate` が bool でない | `tool_failure` (fail-closed) | gate 値不確定 |

docs、impl、test すべてでこの方針が一致していることを確認済み。

---

## 5. テスト結果

```
pytest tests/test_s4_rerun_triage.py -q
→ 37 passed in 0.11s

pytest tests/test_project_state_sync.py -q
→ 16 passed in 0.04s

pytest -q
→ 1990 passed in 3.39s
```

テスト内訳（test_s4_rerun_triage.py）:
- Test 1-18: 元の18件（flat/basic scenarios、secret suppression、CLI）
- Test 19-20: wrapper shape rejected/passed
- Test 21-22: wrapper rejection_reasons（safe/secret）
- Test 23-24: ledger model/api_mode secret suppression
- Test 25: unexpected gate value secret suppression
- Test 26: Markdown output secret suppression
- Test 27-28: artifact subdir layout / flat priority
- Test 29-30: promote_eligible semantics
- Test 31-34: _extract_fitness_payload unit tests
- Test 35-37: _safe_text unit tests

---

## 6. セキュリティ制約確認

| 制約 | 遵守状況 |
|---|---|
| Gemini API 呼び出し禁止 | ✅ 標準ライブラリのみ、ネットワーク不使用 |
| workflow_dispatch 禁止 | ✅ CI トリガーコードなし |
| data/api_usage_ledger.json 編集禁止 | ✅ read-only 参照のみ |
| data/genome.json 等 FROZEN ファイル不変 | ✅ 変更なし |
| secret 出力禁止 | ✅ `_safe_text()` で全 dynamic 文字列をカバー |
| promotion 実行禁止 | ✅ promote_eligible は requires_owner_approval=true を返すのみ |
| core/policy.py 等 safety 弱化禁止 | ✅ 変更なし |

---

## 7. 残存リスク

1. **実アーティファクトでの検証未実施** — 次回 Owner-approved S4 rerun 後に
   実ファイルで `--artifacts-dir` を指定して動作確認が必要。
2. **project_state.json の apply/evaluate/promote フィールドが更新未済** —
   5件目の run の詳細結果（どのステージまで到達したか）は Owner が
   artifacts を確認してから project_state.json を更新すること。
3. **_safe_text の部分置換非対応** — 長い rejection_reason の一部にだけ
   secret が混入している場合、文字列全体が `[SUPPRESSED_SECRET_PATTERN]`
   になる。これは意図的な保守的設計だが、情報損失を伴う。
