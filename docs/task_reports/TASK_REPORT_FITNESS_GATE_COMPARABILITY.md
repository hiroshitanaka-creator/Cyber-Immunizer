# タスク完了報告 — Fitness Gate Comparability & Score Diagnostics Design

## 概要

候補コードの適合度ゲートが世代間で比較不可能になっている問題を調査し、
`changed_lines` ペナルティの生成不変性問題を特定した。
設計ドキュメントとして残存リスク・推奨実装変更・必要テストをまとめる。
本報告は design-only。FROZEN ファイルへの変更なし。

---

## 1. 現在の問題点：score の非生成不変性

### 1.1 スコア計算式（現行）

`core/fitness.py:_compute_score`（行 44–64）:

```python
def _compute_score(tp_rate, fp_rate, fn_rate, exception_count, code_chars, changed_lines):
    return (
        1000.0 * tp_rate
        - 2000.0 * fp_rate
        - 1500.0 * fn_rate
        - 50.0 * exception_count
        - 0.02 * code_chars
        - 10.0 * changed_lines       # ← 問題の根本
    )
```

### 1.2 `changed_lines` の意味とベースラインのずれ

`core/fitness.py:_count_changed_lines`（行 124–136）は候補コードを
**現在の `core/detector.py`** と行単位で比較する。

| 世代 | 評価時の `changed_lines` ベースライン | スコア |
|---|---|---|
| Gen 1 | Gen 0 の `core/detector.py` | 383.67 |
| Gen 2 | Gen 1 の `core/detector.py` | **729.34 ← genome.json に保存** |
| 候補 (run 5/6) | **Gen 2** の `core/detector.py`（現在） | 494.48 / 478.12 |

`best_score=729.34` には **Gen 1 vs Gen 2 差分に由来する `changed_lines` ペナルティが含まれている**。  
候補は現在の Gen 2 detector を差分ベースにするため、両者のスコアは **異なる意味の `changed_lines`** を基に計算されており、直接比較できない。

### 1.3 ゼロデイ証明：no-op 候補は採用ゲートを通過する

現在の Gen 2 detector (`code_chars=3033`) と **完全に同一のファイル** を候補として提出した場合:

```
changed_lines = 0           (自分自身との差分なのでゼロ)
code_chars    = 3033
tp_rate       = 1.0
fp_rate       = 0.0
fn_rate       = 0.0
exception_count = 0

score_noop = 1000.0 - 0.02 × 3033 - 10.0 × 0
           = 1000.0 - 60.66 - 0
           = 939.34
```

**採用ゲート判定**: `939.34 > 729.34` → **PASS**  
no-op（何も改善していないコピー）が採用されてしまう。

逆算すると、Gen 2 が評価されたとき Gen 1 に対して **21 行が変更されていた**:

```
best_score  = 1000 - 0.02 × 3033 - 10 × L2 = 729.34
→ L2 = (1000 - 60.66 - 729.34) / 10 = 21.0 行
```

no-op の優位性は `10 × 21 = 210 点`。

---

## 2. `changed_lines` の扱い：設計オプション比較

| オプション | 説明 | 利点 | 欠点 |
|---|---|---|---|
| **A. スコアから除外（推奨）** | スコア計算から削除し、診断専用フィールドとして保持 | 完全に生成不変。no-op 脆弱性を排除 | 変更最小化シグナルが弱まる。code_chars でカバー可能 |
| B. 固定ベースライン | gen 0 detector を常に差分ベースとして使う | シグナルを保持できる | ベースラインファイル保管が必要。世代が進むほど全 diff が巨大化 |
| C. ゲノムに "baseline snapshot" を保存 | 前世代の `changed_lines` 相当値を genome に格納して normalize | 精度が高い | genome スキーマ変更が必要。複雑性増大 |

**推奨：オプション A**  
`changed_lines` は診断情報として `score_components` に残すが、ゲートスコアには含めない。

---

## 3. 生成不変スコア式（提案）

```python
def _compute_score(tp_rate, fp_rate, fn_rate, exception_count, code_chars):
    """Generation-invariant fitness score.

    changed_lines は diagnositcs のみ。ゲートスコアには含めない。
    """
    return (
        1000.0 * tp_rate
        - 2000.0 * fp_rate
        - 1500.0 * fn_rate
        - 50.0 * exception_count
        - 0.02 * code_chars
    )
```

生成不変スコアの最大値は `1000.0`（完全検知・FP ゼロ・コードゼロ）。  
Gen 2 の検知性能（TP=1.0, FP=0.0, FN=0.0）に基づく生成不変スコア = `1000 - 60.66 = 939.34`。

### genome.json の `best_score` 更新が必要

| 項目 | 現在値（changed_lines 込み） | 生成不変値（changed_lines 除外） |
|---|---|---|
| Gen 2 best_score | 729.34 | **939.34** |

`data/genome.json` は FROZEN なので、Owner 承認後に更新が必要。  
更新前は genome の best_score を「生成不変ベースに変換」しないと false rejection が続く。

---

## 4. 候補と現行 detector の同一コンテキスト比較

候補と現行 detector を公平に比較するには以下が必要：

1. **同一テストスイート**（`data/test_cases.json` + `data/regression_cases.json`）で両者を評価
2. **`changed_lines` を除いたスコア**で比較（生成不変スコア）
3. `changed_lines` は「何行変えたか」の診断情報として fitness_report に保持

実装方法: `core/fitness.py` の `evaluate()` 関数が呼び出す `_compute_score` から `changed_lines` 引数を除去し、`changed_lines` は FitnessReport の診断フィールドとしてのみ保持する。

---

## 5. `score_components` 追加仕様

現在の `fitness_report.json` に以下の `score_components` オブジェクトを追加する（後方互換の追加フィールド）:

```json
{
  "score_components": {
    "tp_contribution":         1000.0,
    "fp_penalty":                 0.0,
    "fn_penalty":                 0.0,
    "exception_penalty":          0.0,
    "code_size_penalty":         60.66,
    "changed_lines_diagnostic":  210.0,
    "gate_score":               939.34
  }
}
```

| フィールド | 計算式 | ゲートに使用 |
|---|---|---|
| `tp_contribution` | `1000.0 × tp_rate` | ✅ |
| `fp_penalty` | `2000.0 × fp_rate` | ✅ |
| `fn_penalty` | `1500.0 × fn_rate` | ✅ |
| `exception_penalty` | `50.0 × exception_count` | ✅ |
| `code_size_penalty` | `0.02 × code_chars` | ✅ |
| `changed_lines_diagnostic` | `10.0 × changed_lines` | ❌（診断のみ） |
| `gate_score` | 上 5 つの合計（`changed_lines` 除外） | ✅ これが `score` フィールドに相当 |

後方互換：`score_components` は完全に新規フィールドであり、既存コードへの影響なし。  
`score` フィールドは旧来の場所・型で保持する。

---

## 6. 必要テスト仕様

すべてのテストは `tests/test_fitness.py` に追加し、FROZEN の実装ファイルを変更しない前提で設計する。

### 6.1 no-op 候補はゲートを通過しない

```python
def test_noop_candidate_does_not_pass_gate():
    """現行 detector と完全に同一の候補は採用ゲートを通過しない。

    changed_lines=0 の no-op が score > previous_best になって PASS するのは誤り。
    この問題が修正されている (changed_lines をスコアから除外) ことを検証する。
    """
    detector_path = _PROJECT_ROOT / "core" / "detector.py"
    # 現行 detector を候補として提出
    report = evaluate(detector_path, baseline_mode=False)
    # no-op はゲートを通過すべきでない
    assert not report.passed_adoption_gate, (
        f"no-op candidate must not pass adoption gate, "
        f"score={report.score:.2f} vs previous_best from genome"
    )
```

**現在の期待動作（修正前）**: FAIL（no-op が 939.34 で通過してしまう）  
**修正後の期待動作**: PASS（no-op は previous_best の生成不変スコアを上回れない）

### 6.2 score-worse 候補はゲートを通過しない

```python
def test_score_worse_candidate_does_not_pass_gate(tmp_path):
    """score が previous_best を下回る候補は採用ゲートを通過しない。"""
    # 実装: TP rate が 0 (all-allowing) の候補を評価
    body = "return DetectionResult(False, 'allow all', 0.0, ())"
    p = _write_candidate(body)
    report = evaluate(p, baseline_mode=False)
    assert not report.passed_adoption_gate
    assert any("score" in r or "fn_rate" in r for r in report.rejection_reasons)
```

### 6.3 strictly better 候補は通過できる

```python
def test_strictly_better_candidate_can_pass_gate(tmp_path, monkeypatch):
    """previous_best を確実に上回るスコアを持つ候補は採用ゲートを通過できる。

    genome の best_score を -1e9 に設定して生成不変スコアが任意の候補に対して
    previous_best を超えることを確認する。
    """
    import tempfile, json, shutil
    from pathlib import Path

    # genome を best_score=-1e9 で上書き (isolated copy)
    real_genome = json.loads((_PROJECT_ROOT / "data" / "genome.json").read_text())
    real_genome["best_score"] = -1e9
    tmp_genome = tmp_path / "genome.json"
    tmp_genome.write_text(json.dumps(real_genome))

    # baseline detector を候補として評価
    detector_path = _PROJECT_ROOT / "core" / "detector.py"
    report = evaluate(detector_path, baseline_mode=False, genome_path=tmp_genome)

    assert report.passed_adoption_gate, (
        f"baseline detector should pass gate when previous_best=-1e9, "
        f"score={report.score:.2f}, reasons={report.rejection_reasons}"
    )
```

### 6.4 旧レポートスキーマ後方互換性

```python
def test_score_components_additive_and_backward_compatible():
    """score_components が fitness_report に追加されても
    既存フィールド (score, tp_rate, fp_rate, changed_lines 等) が維持されていること。"""
    baseline = _PROJECT_ROOT / "core" / "detector.py"
    report = evaluate(baseline, baseline_mode=True)
    # 既存フィールドが維持されていること
    for field in ("score", "tp_rate", "fp_rate", "fn_rate", "changed_lines", "code_chars"):
        assert hasattr(report, field), f"FitnessReport missing existing field: {field}"
    # score_components が存在すれば内容を検証
    if hasattr(report, "score_components"):
        sc = report.score_components
        assert "tp_contribution" in sc
        assert "fp_penalty" in sc
        assert "fn_penalty" in sc
        assert "code_size_penalty" in sc
        assert "changed_lines_diagnostic" in sc
```

---

## 7. 実装変更が必要なファイル（Owner 承認必要）

| ファイル | 変更内容 | 優先度 |
|---|---|---|
| `core/fitness.py` | `_compute_score` から `changed_lines` を除外。`score_components` を `FitnessReport` に追加 | P0 |
| `core/types.py` | `FitnessReport` に `score_components: dict` フィールドを追加（optional, デフォルト `None`） | P1 |
| `data/genome.json` | `best_score` を 729.34 → 939.34（生成不変スコア）に更新 | P0（スコア変更と同時） |
| `tests/test_fitness.py` | 上記 6.1〜6.4 のテスト追加（`test_noop_candidate_does_not_pass_gate` 等） | P0（実装と同時） |
| `scripts/evaluate_candidate.py` | `_write_report` が `score_components` を保存するよう更新（診断用） | P2 |

---

## 8. 後検証：既存テスト通過確認

```
pytest tests/test_fitness.py -q
pytest tests/test_evaluate_candidate.py -q
pytest tests/test_promote_candidate.py -q
pytest tests/ -q
```

実行結果：**127 passed** (ベースライン確認済み)

---

## 9. 残存リスク・注意点

### R1: genome.json 更新と実装変更の順序

`core/fitness.py` のスコア式を変更する前に `genome.json` の `best_score` を更新すると、
新候補が生成不変スコアで評価されるが、比較対象の `previous_best` は旧スコア（729.34）のまま。  
`1000 - 0.02 × code_chars = 939.34` が正しい生成不変ベースラインなので、  
**スコア式変更と genome.json 更新は同一 PR・同一 commit で行うべき**。

### R2: runs 5/6 の rejection が正当だったかの検証不能

runs 5/6 の詳細な fitness_report.json は artifact download blocked（project_state.json 記載）のため、
実際の `tp_rate/fp_rate/changed_lines/code_chars` の内訳が不明。  
もし TP=1.0, FP=0.0, FN=0.0 で `changed_lines` が大きかっただけなら、
生成不変スコアでは十分合格できた可能性がある。  
**実装後の初回 rerun で成否を確認する必要がある。**

### R3: no-op 候補の最終防衛ライン

`changed_lines` 除外後も、**no-op 候補の生成不変スコア = 939.34** が `previous_best=939.34` と等しくなるため、
`score <= previous_best` の厳格な不等号（`<=`）で正しく弾かれる（厳密改善が必要）。  
この点は現行の `_adoption_gate` の比較演算子（`score <= previous_best_score`）が正しい。

### R4: `changed_lines` 診断値のゼロ化

候補が現行 detector と同一の場合、`changed_lines_diagnostic=0.0` となり診断として分かりやすい。  
run 5/6 のような「大幅書き換え」では `changed_lines` が高くなり、
LLM が広い変更をしている可能性を示す診断として役立つ。

### R5: FitnessReport の型変更と promote_candidate.py

`FitnessReport` に `score_components` フィールドを追加する場合、
`promote_candidate.py` の `_validate_fitness_schema` は新フィールドを知らない。  
**後方互換のため `score_components` は optional フィールドとし、missing でも schema error としない**。

---

## 10. 次の推奨アクション

1. **Owner 承認**: `core/fitness.py` の `_compute_score` から `changed_lines` 除外 + `data/genome.json` の `best_score=939.34` 更新を承認する
2. **テスト先行実装**: `tests/test_fitness.py` に `test_noop_candidate_does_not_pass_gate` を追加し、
   修正前に RED になることを確認（スペックとして明示）
3. **実装**: `core/fitness.py` 変更（`_compute_score` シグネチャ変更、`score_components` 追加）
4. **data 更新**: `data/genome.json` の `best_score` を `939.34` に更新
5. **rerun**: Owner 承認の rerun で新しい生成不変スコア下での候補評価を確認

---

## 変更ファイル一覧（本 PR）

| ファイル | 種別 |
|---|---|
| `docs/task_reports/TASK_REPORT_FITNESS_GATE_COMPARABILITY.md` | 新規（本ファイル） |

FROZEN ファイル変更: **なし**
