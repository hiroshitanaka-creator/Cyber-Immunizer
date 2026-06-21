# タスク完了報告 — PR #156 Final Codex P2 Evidence-Hardening Pass

**日付**: 2026-06-21
**ブランチ**: claude/repository-progress-ni8lko

---

## 概要

"Request Changes Task Prompt — PR #156 final Codex P2 evidence-hardening pass" の全10要件を実装した。
GOOD example JSON修正・`cli/report.py` ガード強化・`cli/structured_eval.py` への total_corpus_entries / Exc 列 / 必須カテゴリ・必須 Tier 常時表示 / SHA-256 ダイジェスト / tier 重複排除追加・`docs/PROJECT_STATE.md` ロールアップ行整合・`fixtures/README.md` スコープ明確化を含む。

---

## 変更ファイル一覧

| ファイル | 種別 | 内容 |
|---|---|---|
| `scripts/propose_mutation.py` | 変更 | GOOD example replacement_code の `\"` → `\\"` 修正（16箇所）・ラベル短縮でヘッドルーム確保 |
| `cli/report.py` | 変更 | code-size-only ガード条件に `fn_rate==0` / `exceptions==0` を追加・該当段落を条件付き表示に変更 |
| `cli/structured_eval.py` | 変更 | `hashlib` import追加・`_sha256_file()` helper・`_REQUIRED_CATEGORIES`・`total_corpus_entries`・Exc列・必須カテゴリ常時表示・必須Tier常時表示・tier重複排除 |
| `docs/PROJECT_STATE.md` | 変更 | 「valid mutation patch produced / apply reached / evaluate reached」ロールアップ行にrun 11/12/13を追記 |
| `fixtures/README.md` | 変更 | Scope セクション追加（structured_eval CLI専用・active detector証明にならない旨を明記） |
| `tests/test_propose_mutation.py` | 変更 | GOOD example JSON有効性テスト追加（11テスト） |
| `tests/test_structured_eval_cli.py` | 変更 | 84 → 102テスト（total_corpus_entries / Exc列 / 必須カテゴリ / 必須Tier / SHA-256 / tier重複排除） |
| `tests/test_report_cli.py` | 変更 | 9 → 12テスト（fn_rate非ゼロ・例外非ゼロでcode-size-only抑制・全パーフェクトで表示） |

---

## 主な変更内容

### 1. GOOD example JSON修正（`scripts/propose_mutation.py`）

- `\"` (Python triple-quoted string内で `"` に展開 → JSON不正) を `\\"` (`\"` に展開 → 正当なJSON文字列エスケープ)に修正
- 修正箇所: `surface = \" \".join` / 5インジケーター名 / `reason=\"...\"` × 2 (計16箇所)
- ラベル `(this WILL be accepted)` → `(ACCEPTED)` に短縮してヘッドルーム回復（198 → 211 chars）
- 検証: `json.loads()` が正常にパースできることをテストで確認

### 2. `cli/report.py` code-size-only ガード修正

- 旧条件: `tp_rate==1.0 and fp_rate==0.0`
- 新条件: `tp_rate==1.0 and fp_rate==0.0 and fn_rate==0.0 and exceptions==0`
- 「code size reduction only」段落を `if _all_perfect:` 条件付き表示に変更（全条件が真のときのみ表示）

### 3. `cli/structured_eval.py` — 複数追加

- **`_sha256_file(path)`**: rules/corpus ファイルの SHA-256 ダイジェスト計算
- **`_REQUIRED_CATEGORIES`**: `("path-traversal", "xss", "sqli", "cmdi")`
- **total_corpus_entries vs classified cases**: `total_corpus_entries = len(corpus)` を Markdown ヘッダーと JSON output に追加
- **Per-Category Exc 列**: テーブルに `Exc` 列追加（exceptions カウント表示）
- **必須カテゴリ常時表示**: path-traversal/xss/sqli/cmdi は corpus に存在しなくても `*(absent)*` として常時表示
- **必須 Tier 常時表示**: holdout/drift/counterfactual は corpus に存在しなくても `*(absent)*` として常時表示（`if not per_tier` fallback を削除）
- **SHA-256 ダイジェスト**: Markdown ヘッダー（`Rules SHA-256`/`Corpus SHA-256`）および JSON output（`rules_sha256`/`corpus_sha256`）に追加
- **tier 重複排除**: `for _tag in tags:` → `_tier_tags_seen = {t for t in tags if ...}; for _tag in _tier_tags_seen:` に変更

### 4. `docs/PROJECT_STATE.md` ロールアップ行整合

- 「Valid mutation patch produced」: run 11/12/13 も `evaluate_rejected` パッチを生成した旨を追記
- 「apply reached」: run 11/12/13 も apply 到達を追記
- 「evaluate reached」: run 11/12/13 も evaluate 到達（rejected）を追記

### 5. `fixtures/README.md` スコープ明確化

- 「Scope of these fixtures」セクションを新規追加
- `cli/structured_eval` CLI 専用のフィクスチャであること
- `core/detector.py`（active runtime detector）とは別物であること
- structured_rules を提供することは active detector の能力証明ではないことを明記

---

## テスト結果

```
pytest tests/ -q
2776 passed, 5 warnings in 10.30s
```

（内訳: test_structured_eval_cli.py 102 / test_report_cli.py 12 / test_propose_mutation.py 11）

---

## 後検証結果

```bash
# GOOD example JSON 有効性確認
python3 -c "
import ast, json
with open('scripts/propose_mutation.py') as f:
    content = f.read()
idx = content.find('_LLM_SYSTEM_PROMPT = ')
s = content.find('\"\"\"', idx)
e = content.find('\"\"\"', s + 3) + 3
val = ast.literal_eval(content[s:e])
good_idx = val.find('GOOD example')
bi = val.find('{', good_idx)
be = val.find('}', bi) + 1
parsed = json.loads(val[bi:be])
print('VALID JSON:', bool(parsed.get('replacement_code')))
"
# → VALID JSON: True

# CLI smoke test — Markdown
python -m cli.structured_eval \
  --rules fixtures/structured_rules/symbolic_equivalent.json \
  --corpus fixtures/evaluation_corpus/symbolic_corpus.json
# → TP=5, FP=0, TN=5, FN=0
# → SHA-256 ダイジェスト表示
# → Total corpus entries: 10 / Classified cases: 10
# → Per-Category: Exc 列あり / path-traversal/xss/sqli/cmdi すべて表示
# → L2-V3 Tier: holdout/drift/counterfactual *(absent)* 表示

# CLI smoke test — JSON
python -m cli.structured_eval \
  --rules fixtures/structured_rules/symbolic_equivalent.json \
  --corpus fixtures/evaluation_corpus/symbolic_corpus.json --json | python -m json.tool | head -10
# → rules_sha256 / corpus_sha256 / overall.total_corpus_entries 含む
```

---

## 残存事項・注意点

- **Layer 2 は未達成**。フレームワーク完成のみ。Owner 提供の現実コーパスによる評価・承認が必要
- `fixtures/` はシンボリックプレースホルダのみ — per_tier が空（すべて `*(absent)*`）になるのは正常動作
- `scripts/propose_mutation.py` 修正は `main` にマージ後の次回 Evolution Loop から有効
- `docs/PROJECT_STATE.md` のロールアップ行更新はドキュメント整合のみ（data/** は変更なし）

---

## タスクレイヤー宣言

```
[x] None（フレームワーク品質向上・ドキュメント整合のみ。Layer 2 は Owner による現実コーパス評価・承認が必要）
```
