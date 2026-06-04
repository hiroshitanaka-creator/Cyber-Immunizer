# PR #65 残タスク・問題点 統合リスト（4ソース統合 / 重複統合済み）

> 対象PR: #65 "clarify replacement_code 4-space indentation contract (prompt, validation, tests, runbook)"
> 統合元: **[Claude]** / **[Grok]** / **[GPT]**(thinking heavy) / **[GPT-old]**(旧スレッド版・汚染あり=要検証)
> 本リストは調査結果の統合のみ。コード変更・修正提案は含みません。
> タグ凡例: 指摘ソースを `[...]` で明記 / `※PO判断` = Project Owner 判断事項 / `※要検証` = 汚染/未確証で裏取り必須 / `※確定` = Claudeがコード読取で事実確認済み

---

## 0. 結論サマリ

- 全3アクティブソース（Claude/Grok/GPT）の総合評価は一致して **Yellow**。Critical（即時の実害）は無し。
- 最重要は **「propose段階のvalidator」と「core/policy.py（single source of truth）」の契約乖離**。複数ソースが独立に指摘。
- GPT-old（RT-65-01〜25）は粒度が細かいが汚染の疑いがあり、本リストでは該当箇所に統合しつつ `※要検証` を付与。

---

## 優先度【高】

### H-1. propose段階validator と core/policy.py(正本) の契約乖離（双方向） `※確定` `※PO判断`
- **内容**: `_validate_replacement_code`（propose段階）と `run_full_policy`/`check_disallowed_ast_constructs`（apply/validate段階の正本）で禁止ルールが一致していない。
  - propose段階を**通過するが**policy正本が**reject**する構文（Claudeが実証）: `while` / `with` / `try`/`except` / `raise` / walrus `:=` / nested `class` / `lambda` / `yield` / `await` / `global` / `nonlocal` / `del` / `assert` / `match`。
  - これは Codex CR-65-01/02 が消そうとした「unusable patchをproposeで書いてしまい後段で確定reject」と**同種のアンチパターン**が制御構文クラスで残存していることを意味する。
- **判断事項**: proposeでfull policy相当まで落とすか、proposeはindent/shape中心とし構文系はapply段階rejectで許容するか。`core/policy.py:3`は"single source of truth"を宣言しており、重複・劣化コピー化の是非も含む。
- **ソース**: [Claude] I-1（実証済み） / [GPT] Important-2・確認質問1 / [GPT-old] RT-65-12, RT-65-21（責務分離） `※要検証`

### H-2. 全実行パスでDetectionResultを返す保証（exhaustiveness / CFG完全性） `※PO判断`
- **内容**: validatorは「returnが1個以上あり、各returnがDetectionResult呼び出し」しか見ず、**全分岐return**は保証しない。`if 条件: return ...` でfallthrough無し→暗黙のNone返却が通り得る。
- **下流での捕捉状況（[Claude]確認済）**: `core/fitness.py:_contract_ok` は単一dummy `Request(GET,"/")` で実行し型/confidence範囲を検査→典型mutationなら捕捉。test caseでNone返却時は `evaluate_detector` が例外記録→adoption gate失格。**残存ギャップ**は「dummyにもtest caseにも出ない条件分岐のみNone」の狭いケース。propose段階ではfail-closeされず後段委譲である点は事実。
- **判断事項**: 簡易ルール（最後のtop-level文が `return DetectionResult`）で止めるか、full CFG証明か、現状（後段委譲）を明文化するか。
- **ソース**: [Claude] I-5（実証・確認済） / [Grok] semantic body limit / [GPT] Important-3 / [GPT-old] RT-65-09, RT-65-10 `※要検証`

### H-3. DetectionResult(...) コンストラクタ引数の検査範囲 `※PO判断`
- **内容**: validatorは `Return → Call → Name(id="DetectionResult")` の呼び出し名のみ確認。引数の個数・キーワード名・型・値域は未検証（dataclassは実行時型を強制しない）。
- **想定される未捕捉例**:
  - 引数欠落: `DetectionResult()` / `DetectionResult(blocked=False)`
  - 不正keyword: `DetectionResult(foo="bar")` / 余剰keyword `extra=True`
  - 型不整合: `blocked="yes"` / `blocked=1` / `reason=123` / `reason=None` / `confidence="high"` / `matched_signals=[]` / `matched_signals=("x",1)`
  - 値域: `confidence=-0.1` / `confidence=1.1` / `confidence=2`
  - positional/keyword 混在ルール（`DetectionResult(False,"x",0.0,())` の可否）
- **判断事項**: どこまでをproposeで静的検査し、どこからfitness/runtimeに委ねるか。`tuple(matched)`等の変数由来をどこまで許すか。
- **ソース**: [Grok] Important(return shape weakness) / [GPT] Important-4 / [GPT-old] RT-65-01〜07, RT-65-11 `※要検証`

### H-4. 「return DetectionResult は exactly 4-space」というPrompt/Runbook記述と、ネストreturn許容の矛盾
- **内容**: System Promptは `return DetectionResult(...) must be at exactly 4-space indentation` と記すが、同Promptの GOOD example は `if matched:` 内の8スペースreturnを含み、validatorもtestも8スペースのネストreturnを正常系として受理。実装バグではなく**契約文の曖昧さ**。
- **判断事項**: 「最終default returnのみ4-space」なのか「全returnを含む」のかを確定し、Prompt/Runbook/Testで文言統一。
- **ソース**: [GPT] Important-1

---

## 優先度【中】

### M-1. マルチライン文字列 / docstring / f-string / 括弧継続行のインデント誤拒否 `※確定`
- **内容**: validatorはAST意味ではなく**物理行ベース**で `splitlines()` 後にindent検査するため、以下の合法Pythonが誤拒否され得る（[Claude]実証済み）:
  - 括弧内継続行の視覚的整列（例: 開き括弧に揃えた18スペース）→ `mod4 fail`（REJECT）
  - triple-quote/f-string内部の列0行 → `min_indent<4`（REJECT）
- Prompt/Runbook/Testに文字列内インデントの扱いの明示が無い。`core/policy.py:7`「false rejection is acceptable」方針はあるが、**この具体検査の明示的受容 or tokenize精緻化計画は未確認** `※PO判断`。
- **ソース**: [Claude] I-2, I-3（実証） / [Grok] multiline string literal edge case / [GPT] Important-6

### M-2. 三項(IfExp)/論理式によるDetectionResult返却の扱い `※確定` `※PO判断`
- **内容**: `return DetectionResult(...) if c else DetectionResult(...)` は両枝ともDetectionResultでも、`Return.value` が `ast.IfExp` のため現契約で**拒否**（[Claude]実証）。`return None`等と区別できていない。
- **判断事項**: 拒否継続か、IfExp両枝検査を追加して許容するか。
- **ソース**: [Claude] I-4（実証）

### M-3. `_extract_mutation_region(...).strip()` とPrompt 4-space契約の整合
- **内容**: Promptに渡す「現在のmutation region」が `.strip()` で既存インデントを落とされるため、モデルへ提示する例が無インデント化し、4-space契約の誘導として弱い可能性。
- **ソース**: [GPT] Important-5 / [GPT-old] RT-65-06系 `※要検証`

### M-4. 深いネスト(12/16スペース)の**正常系**テスト不足
- **内容**: 4と8(ネスト)、6(拒否)はテスト済みだが、12/16スペースの受理ケースが明示テストに無い（ロジック上は%4でカバー）。
- **ソース**: [Claude] §3-4 / [Grok] Minor / [GPT] §4-Test

### M-5. テストカバレッジ不足（構文バリエーション）
- **内容**: 以下の明示テストが不足:
  - リスト/辞書/集合内包表記の複数行
  - `with`文 / `while` / 型ヒント付き代入 / decorator / nested class
  - docstring内部の複雑インデント
  - 2スペース/5スペース等の追加非4倍数
  - qualified name `core.types.DetectionResult(...)` の拒否確認
  - `return make_result()` / `return True` / `return False` の拒否確認
  - DetectionResult引数欠落・型違い（H-3関連）
  - propose段階で通る構文がpolicyでrejectされる事実（H-1関連の差分テスト）
- **ソース**: [Claude] §3-4 / [Grok] Minor / [GPT] §4-Test / [GPT-old] RT-65-22 `※要検証`

### M-6. matched_signals の内容制約（neutralized indicatorのみか） `※要検証` `※PO判断`
- **内容**: matched_signalsに入る文字列がneutralized symbolic indicator限定かを検査するか。`tuple(matched)`等の変数由来の扱い。
- **注記**: GPT-old単独指摘。提案範囲がproposeの責務を超える可能性があり要検証。
- **ソース**: [GPT-old] RT-65-08 `※要検証`

### M-7. Runbook記述の実装同期性
- **内容**: Runbookのwrapper説明 `def _candidate_body():\n...` は実装（`def _candidate_body(request):` + `_mutation_anchor = None`）と完全一致しない。「between markers inside inspect_request」の文言も、実際はSTART=関数内4スペース/END=列0である点をやや簡略化。
  - ※ [Claude]はrunbookのエラー分類文字列・対応フローは実装と一致と評価。**不一致はwrapper説明とreturn-indent記述に限定**（ソース間で評価差あり）。
- **ソース**: [GPT] Minor / [GPT-old] RT-65-18 `※要検証`

---

## 優先度【低】

### L-1. 禁止トークンの部分文字列マッチによる誤拒否 `※確定`
- **内容**: `_BLOCKED_CODE_TOKENS` はsubstring一致のため、文字列リテラル中の `import`/`os.` 等で誤拒否（[Claude]実証: `reason='important: no match'` → REJECT）。AST-baseのpolicy側と検出機構が異なる。
- **ソース**: [Claude] M-1（実証）

### L-2. nested class / lambda の契約上の扱い `※確定`
- **内容**: prompt/validatorはnested class/lambdaを明示禁止していないが、**下流 `check_disallowed_ast_constructs` が `ast.walk` 全走査で確実にreject**（[Claude]確認済）。よって実害は無いが、proposeで落ちずpatch書込みが起きる点はH-1に包含。
- **ソース**: [Claude] M-2（確認済・解決） / [GPT] Important-2

### L-3. Unicode / エンコーディング堅牢性
- **内容**: lone surrogateは既存テストあり・UnicodeError catch済み。**未検証**: NBSP / 全角スペース / BOM / NULLバイト / CRLF混在。文字数カウント vs Pythonトークナイザのカラム概念差（[Claude] M-3）。
- **ソース**: [Claude] M-3 / [Grok] Observation / [GPT] Observation

### L-4. 環境差分（Windows / Python 3.12+ / CRLF）未検証 `※PO判断`
- **内容**: CIはUbuntu+Python3.11。`requires-python>=3.11` で3.12+も対象になり得るが確認なし。Windows改行の実証テストなし。
- **判断事項**: 合格基準にこれらを含めるか。
- **ソース**: [Claude] §残タスク / [Grok] Observation / [GPT] Observation・確認質問5

### L-5. エラーメッセージのpayload漏洩安全性 `※要検証`
- **内容**: validation errorが replacement_code 全文やpayload断片をechoしないか確認（SyntaxError message含む）。
- **ソース**: [GPT-old] RT-65-23 `※要検証`

### L-6. blocked/confidence/matched_signals の意味的整合検査 `※要検証` `※PO判断`
- **内容**: `blocked=True`なのに`matched_signals=()`、`blocked=False`なのに`confidence=1.0` 等の意味矛盾を検査するか。
- **注記**: GPT-old単独。proposeの静的検査範囲を超え、fitness委譲が妥当な可能性。汚染の疑いありとして要検証。
- **ソース**: [GPT-old] RT-65-13, RT-65-14 `※要検証`

---

## プロセス / メタ（コード品質外）

### P-1. Codex P2スレッド(CR-65-01〜04)の状態整理 `※対応済`
- **状態**: GitHub上は未resolve表示だったが、**ユーザーがmerge前に手動resolveで運用確定済み**。CR-65-01/02はoutdated、03/04は対応コード確認済み。
- **ソース**: [Claude] M-4 / [GPT-old] RT-65-20 `※要検証`

### P-2. PR本文と実装の同期確認
- **内容**: PR本文の「DONE」「テスト数(23/122/1715)」「検査順序」「Codex status」が最新head(`f8b6202`)と一致するか。23テストは[Claude/Grok]が件数一致を確認済み。
- **ソース**: [Grok] §4 / [GPT] §3-8 / [GPT-old] RT-65-19 `※要検証`

### P-3. Prompt ↔ validator ↔ Runbook の三者完全同期 `※PO判断`
- **内容**: Promptに書いた禁止/必須が validator または後段policy で実際に検査されること、逆も成立することを固定。H-1/H-3/H-4/M-7と連動。
- **ソース**: [GPT-old] RT-65-17, RT-65-18 `※要検証` / [GPT] 各整合性項目 / [Claude] §3

### P-4. invalid応答で mutation_patch.json が書かれないことの統合テスト `※要検証`
- **内容**: validator単体テストに加え、Gemini応答(mock)→patch生成フロー全体で、invalid時にartifactが生成されない/ledger記録との関係を確認。
- **ソース**: [GPT-old] RT-65-16 `※要検証`

### P-5. detector品質評価（behavior test） `※要検証` `※PO判断`
- **内容**: 構文・契約だけでなく、生成detectorが評価データでTP/FP/FNを満たし退化しないか（adoption gate判定）。validatorテストとは別レイヤ。
- **ソース**: [GPT-old] RT-65-15 `※要検証`

### P-6. paid-credit再実行前の状態追跡 `※要検証`
- **内容**: merge後の再実行前に、前回run失敗理由・本PRの対応・確認すべきログ/ledger/artifactが追跡可能か。controlled rerunとして整理。
- **ソース**: [GPT-old] RT-65-24 `※要検証`

### P-7. 外部AI調査入力の標準化（メタ） `※要検証`
- **内容**: 複数AIに同一粒度で残タスク調査させるための観点固定（PR本文を鵜呑みにしない等）。本リスト自体がこれに該当。
- **ソース**: [GPT-old] RT-65-25 `※要検証`

---

## 付録: ソース別オリジナル項目 → 統合先 対応表

| ソース項目 | 統合先 |
|---|---|
| [Claude] I-1 (双方向乖離) | H-1 |
| [Claude] I-2/I-3 (継続行/文字列) | M-1 |
| [Claude] I-4 (三項return) | M-2 |
| [Claude] I-5 (exhaustiveness) | H-2 |
| [Claude] M-1 (substring token) | L-1 |
| [Claude] M-2 (nested class/lambda) | L-2 |
| [Claude] M-3 (Unicode/カラム) | L-3 |
| [Claude] M-4 (Codexスレッド) | P-1 |
| [Grok] return shape weakness | H-3 |
| [Grok] semantic body limit | H-2 |
| [Grok] multiline string edge | M-1 |
| [Grok] 深ネスト/内包表記/with テスト不足 | M-4, M-5 |
| [Grok] Windows/Unicode/3.12 | L-3, L-4 |
| [GPT] Important-1 (4-space return矛盾) | H-4 |
| [GPT] Important-2 (full policy差分) | H-1 |
| [GPT] Important-3 (全パスreturn) | H-2 |
| [GPT] Important-4 (constructor shape) | H-3 |
| [GPT] Important-5 (.strip()) | M-3 |
| [GPT] Important-6 (multiline string) | M-1 |
| [GPT] Minor (Runbook/marker文言) | M-7 |
| [GPT] Observation (Unicode/Win/3.12) | L-3, L-4 |
| [GPT-old] RT-65-01〜07, 11 | H-3 |
| [GPT-old] RT-65-08 | M-6 |
| [GPT-old] RT-65-09, 10 | H-2 |
| [GPT-old] RT-65-12, 21 | H-1 |
| [GPT-old] RT-65-13, 14 | L-6 |
| [GPT-old] RT-65-15 | P-5 |
| [GPT-old] RT-65-16 | P-4 |
| [GPT-old] RT-65-17, 18 | P-3, M-7 |
| [GPT-old] RT-65-19 | P-2 |
| [GPT-old] RT-65-20 | P-1 |
| [GPT-old] RT-65-22 | M-5 |
| [GPT-old] RT-65-23 | L-5 |
| [GPT-old] RT-65-24 | P-6 |
| [GPT-old] RT-65-25 | P-7 |
