# PR #65 — ※要検証項目の確定/却下 判定 ＆ 次PRスコープ提案（調査のみ・変更提案なし）

> 本書は PR65_consolidated_remaining_tasks.md の続編。
> (1) GPT-old(RT-65-xx)由来の `※要検証` 項目を**実コードで裏取り**し「確定/却下」へ振り分け。
> (3) 確定項目を**優先度別の次PRスコープ**に再編（実装指示ではなく「未検証/未対応の観点」の整理）。
> 参照正本: PR head `f8b6202`。判定はコード読取＋隔離ハーネス実証に基づく。

---

## Part 1. ※要検証項目の確定/却下 判定表

| RT番号 | 項目 | 判定 | 根拠（実コード確認） |
|---|---|---|---|
| RT-65-08 | matched_signals を neutralized indicator 限定にする検査 | **却下（低/過剰仕様）** | propose/policy/fitness のいずれも未強制。だが `tuple(matched)` 等**動的値**で静的AST検査は不適。契約の主旨(format/safety)外の「signal語彙」制約であり、enforceするなら fitness/runtime 領域。汚染源の過剰仕様。 |
| RT-65-13 | `blocked`⟺`matched_signals` の意味整合検査 | **却下（fitness領域）** | 静的AST不適（値が動的）。意味品質は `core/fitness.py` の評価対象。propose段階で証明不能。 |
| RT-65-14 | `blocked`⟺`confidence` の意味整合検査 | **却下（fitness領域）** | 同上。`confidence` は計算式になり得る。静的検査は誤拒否を量産。 |
| RT-65-15 | detector品質評価(TP/FP/FN・adoption gate) | **却下（既存実装/別段階）** | `core/fitness.py:_compute_score`(1000·tp −2000·fp −1500·fn …) と `_adoption_gate`(`fp_rate>max_fp_rate`/`regression_pass_rate<min`/`contract_ok`/`exception_count` 等) が**既に存在**。PR#65 の propose ギャップではない。 |
| RT-65-16 | invalid応答で mutation_patch.json が書かれない**統合**テスト | **確定（中・テスト不足）** | `_validate_replacement_code` は単体テスト済み、`--noop` 非書込みテスト(`assert not patch_path.exists()`)あり。但し既存の `patch_result is None` 群は**呼出前ゲート**(live-model/budget)のテストで、「**model応答が invalid replacement_code → post-validation reject → 成果物非生成**」のend-to-end assertは未確認。 |
| RT-65-17 | prompt ↔ validator 同期 | **確定（低・継続/一部H-1,H-3と重複）** | PR#65で大幅前進。残: H-1(while/with/try等は prompt にも validator にも無く後段policyのみ)、H-3(引数契約は prompt が "exactly" と主張するが validator 未検査)。 |
| RT-65-18 | runbook ↔ validator 同期 | **確定（低/限定的）** | エラー分類・対応フローは実装と一致([Claude]確認済)。**不一致は wrapper 説明のみ**(M-7)。 |
| RT-65-19 | PR本文 ↔ 実装 同期 | **確定（低・プロセス/概ね正確）** | 23テスト件数は一致確認済。122/1715は自己申告だが CI(Test Suite) green。検査順序表も実装一致。 |
| RT-65-20 | Codex thread 状態整理 | **却下（完了）** | ユーザーが merge 前に手動 resolve 運用で確定済み。 |
| RT-65-22 | テスト体系の整理 | **確定（低・任意保守）** | 主観的リファクタ。M-5(カバレッジ)とは別軸。必須ではない。 |
| RT-65-23 | エラーメッセージの payload 漏洩安全性 | **却下（実証上 漏洩なし）** | 実証: `SyntaxError` 文字列は `"'(' was never closed (<unknown>, line 4)"` / `"invalid syntax (<unknown>, line 4)"` で **replacement_code 本文を含まない**(ファイル名`<unknown>`・ソース行非表示)。`UnicodeError` は class 名のみに別途 sanitize。漏洩リスク無し。 |
| RT-65-24 | paid-credit 再実行前の状態追跡 | **確定（低・プロセス/一部対応済）** | PR#65 が runbook に「再実行禁止→ログ/ledger確認→契約修正」を追記済。run履歴の追跡可能性は別タスクとして残る。 |
| RT-65-25 | 外部AI調査入力の標準化（メタ） | **却下（コードタスク外/達成済）** | 本統合リスト作成自体で実質達成。コード変更タスクではない。 |

### 補足: 構成要素 RT-65-01〜07, 11（H-3 = DetectionResult引数検査）
H-3は Grok/GPT も独立指摘のため `※要検証` ではなく **確定**。ただし実コード確認により内部で線引きが必要:
- **静的に妥当（実装可能）**: 引数個数(RT-65-01)、keyword名の正当性/余剰拒否(RT-65-02)、positional/keyword混在ルール(RT-65-11)。`core/policy.py` は `inspect_request` の**自身の**signatureしか見ず、`DetectionResult(...)` の**呼出引数**は未検査 → ギャップは実在。
- **fitness委譲が妥当（静的検査不適）**: `blocked`/`reason`/`confidence` の型・値域(RT-65-03〜06) は動的値が多く、`_contract_ok`/`_adoption_gate` が runtime で confidence∈[0,1] 等を既に検査。静的強制は過剰。

### 判定サマリ
- **確定**: RT-65-16, 17, 18, 19, 22, 24 ＋（H-3内の静的検査可能分）
- **却下**: RT-65-08, 13, 14, 15, 20, 23, 25

---

## Part 2. 次PRスコープ提案（優先度別・調査のみ）

> 各Scopeは「未検証/未対応として残る観点」の束。実装着手前に `※PO判断` の意思決定が前提。変更内容そのものは指示しない。

### Scope A 【高・最優先】propose ↔ policy 契約整合
- **H-1** propose段階validatorとcore/policy.py正本の双方向乖離（`while/with/try/raise/walrus/lambda/nested class` 等が propose を通過し後段で確定reject）`※確定` `※PO判断`
- **H-4** 「return DetectionResult は exactly 4-space」というprompt/runbook記述と、ネストreturn許容の文言矛盾の確定
- **RT-65-17**(一部) prompt↔validator の禁止事項同期
- **前提判断**: 「propose段階で full policy 相当まで fail-close するか／構文系はapply段階rejectで許容するか」。決定後は1PRで実装＋差分テスト可能。

### Scope B 【高】return契約の意味的強化（Scope Aと独立可）
- **H-2** 全実行パスでDetectionResult返却（exhaustiveness）の方針確定 `※PO判断`（簡易ルール「最終top-level文がreturn DetectionResult」か／full CFGか／現状の後段委譲を明文化か）
- **H-3** `DetectionResult(...)` 引数の**静的検査**（個数・keyword名・余剰・混在ルール）。型/値域はfitness委譲を明文化 `※PO判断`

### Scope C 【中】物理行インデント検査の false rejection 是正
- **M-1** 文字列リテラル内/括弧継続行の視覚整列が誤拒否される（実証済）→ `tokenize` 化 or「false rejection明示受容」の文書化 `※確定` `※PO判断`
- **M-2** 三項(IfExp)/論理式 return の許容是非（実証済）`※確定` `※PO判断`
- **M-3** `_extract_mutation_region(...).strip()` とprompt 4-space例示の整合

### Scope D 【中】テストカバレッジ拡充
- **M-4** 12/16スペース深ネストの**正常系**テスト
- **M-5** 内包表記/with/型ヒント/decorator/docstring内/2・5スペース/qualified name拒否/`make_result()`・`True`/`False`拒否/引数欠落（Scope B連動）
- **RT-65-16** invalid model応答→patch非生成の**end-to-end**統合テスト `※確定`
- **RT-65-22** テスト体系の整理（任意）`※確定（任意）`

### Scope E 【低】ドキュメント/プロセス整合
- **M-7 / RT-65-18** runbook の wrapper 説明（`_candidate_body(request)` + `_mutation_anchor`）の実装同期 `※確定`
- **RT-65-19** PR本文（DONE/テスト数/検査順序/Codex status）の実装同期 `※確定`
- **RT-65-24** paid-credit 再実行前の run 履歴・ledger・artifact 追跡整理 `※確定`
- **L-1** 禁止トークンの substring 誤検出（`import`/`os.`）→ AST-base 化の検討（実証済）`※確定`

### Scope F 【低】環境差分・堅牢性
- **L-3** Unicode（NBSP/全角スペース/BOM/NULL/CRLF）堅牢性テスト
- **L-4** Windows / Python 3.12+ の CI 確認 `※PO判断`
- **L-5 / RT-65-23** エラー漏洩 → **却下**（実証上 漏洩なし）。残すなら「SyntaxError と UnicodeError の sanitize 非対称」を docstring 注記する程度

### 次PRスコープから除外（却下項目）
RT-65-08 / 13 / 14（意味整合=fitness領域・過剰仕様）、RT-65-15（品質評価=既存fitness）、RT-65-20（完了）、RT-65-23（漏洩なし）、RT-65-25（メタ/達成済）

---

## Part 3. 推奨着手順（参考・判断は保留）

1. **Scope A の PO判断**（propose の責務範囲）を最初に確定 → これが H-1/H-4/RT-65-17 と Scope D の差分テストの前提。
2. Scope B（return意味契約）を A と並行 or 直後に。H-3 の「静的 vs fitness」線引きも PO判断。
3. Scope C は「false rejection をどこまで許容するか」の方針次第。許容なら docstring 注記のみで close 可能、是正なら tokenize 実装。
4. Scope D/E/F は A〜C の決定に追従。
