<!--
AI_DOC_META
status: EXECUTION CHECKLIST（実行タスク分解）
scope: ミッション M0–M5 と Definition of Done（Layer 1–3）を、実ファイル・スクリプト・DoD条件に紐づけた実行タスクへ分解する。
authority: |
  本書は派生・従属文書である。
  - ミッション定義の正典: docs/MISSION_ROADMAP.md（M0–M5）
  - 完成条件の正典:       docs/DEFINITION_OF_DONE.md（Layer 1–3）
  - current-state の正典: 機械的証拠 > data/project_state.json > docs/PROJECT_STATE.md > 派生サマリ
  本書は current-state を独立に定義しない。矛盾時は上記正典が優先する。
do_not_use_for:
  - ミッションの希薄化・恒久的「進行中」化
  - 証拠なしで phase / task を done と主張すること
  - paid-credit / workflow_dispatch / threat-feed を Owner 承認なく実行すること
AI_DOC_META_END
-->

# Cyber-Immunizer — 完成に向けた実行タスクリスト（Execution Checklist）

## 本書の位置づけ

本書は **新しいロードマップではない**。既存の `docs/MISSION_ROADMAP.md`（M0–M5）と
`docs/DEFINITION_OF_DONE.md`（Layer 1–3）を、**実ファイル・スクリプト・DoD条件に紐づけた
実行タスクへ分解した checklist** である。ミッションの縮小・新プロトコルの増設は行わない。

current-state を解釈するときは CLAUDE.md の権威順序に従う:
**機械的証拠 > `data/project_state.json` > `docs/PROJECT_STATE.md` > 派生サマリ（本書を含む）。**

---

## 現在地スナップショット（正典引用）

| 項目 | 値 | 出典 |
|---|---|---|
| state_id | `phase3_generation4_paid_credit_promotion_active` | `data/project_state.json`（`state_id`） |
| next_action | `generation4_audited_baseline_owner_decide_next_phase3_step` | `data/project_state.json`（`next_action`） |
| generation / score | generation 4 / score 948.04 / `promote_approved=true` | `data/project_state.json`（`promotion`） |
| detector_mode | `structured_rules` | `data/genome.json`（`detector_mode`） |
| live_model_enabled | `true` | `data/project_state.json`（`live_model_enabled`） |
| Layer 1（研究基盤） | 達成 | `docs/DEFINITION_OF_DONE.md:53` |
| Layer 2（価値検証） | `owner_accepted_bounded`（**完全達成ではない**） | `data/project_state.json`（`layer_2_value_validation.status`） |
| Layer 3（AI運用統制） | docs 整備済み・L3-A4 は提案段階 | `docs/DEFINITION_OF_DONE.md:133` |

> Layer 2 の bounded 受理の意味（逐語要約）: 「評価経路は小さな中立化コーパスで検証された。
> gen-4 の **symbolic detector は realistic threat を 0.0% しか検知せず**、structured ruleset は
> 100.0%（FP 0.0%）検知した。受理は限定的で、評価経路の妥当性と『symbolic の壁』の定量化、
> およびそれを閉じる安全な経路を確認したにとどまる」 — 出典 `data/project_state.json`
> （`layer_2_value_validation.meaning` / `evidence: docs/value_validation/LAYER2_REALISTIC_EVALUATION_SUMMARY.md`）。

### 調査で判明した docs/code の不整合（M1-T0 でタスク化）

`scripts/propose_mutation.py` は **`--structured-rules --gemini-paid-credit --allow-live-model`
（LLM による構造化ルール生成）経路を実装済み**（`propose_structured_rules`、`scripts/propose_mutation.py:2111-2154`）。
Evolution Loop run #80（mode=`structured-gemini-paid-credit`）がこの経路を実使用し、構造化ルールを promote した。
一方 `docs/R4_LLM_AUTONOMOUS_PROPOSAL_PLAN.md:30-43` は「`--structured-rules --gemini-paid-credit`
path は存在しない」と記述しており、**現行コードと矛盾している**。コードが正典であるため、M1 の主要残課題は
「LLM 提案経路の新規実装」ではなく、**auto-promotion ゲートの自動化**と**SSOT 整合の解消**である。

---

## タスク表

凡例: **[Owner-gate]** = Project Owner の明示承認が必須 / **[FROZEN]** = scope外コア（編集に Owner 承認必須） /
各タスクに紐づく DoD・主担当ファイル・Done-when を付す。

### M0 — Foundation（DONE・参照のみ、再作業しない）

安全な自己変異エンジン（propose→apply→evaluate→promote）、structured detector 経路、R3 promotion、
realistic corpus 上の実検知（100% / FP 0%）。証拠: PR #171–#173、`docs/value_validation/REALISTIC_DETECTION_RESULTS.md`。

### M1 — The loop authors its own defense（← 次の実行ブレークスルー）

| ID | タスク | DoD | 主担当ファイル | Done-when |
|---|---|---|---|---|
| M1-T0 | **[SSOT]** docs/code 不整合の解消。live structured proposal が実装済みである事実を反映し、古い「未実装」記述を訂正。**scripts は変更せず docs/state のみ。** | Current-State SSOT | `docs/R4_LLM_AUTONOMOUS_PROPOSAL_PLAN.md`・`docs/PROJECT_STATE.md`・`data/project_state.json` | R4 plan と PROJECT_STATE が現行コードと一致 |
| M1-T1 | 1トリガー → LLM 構造化提案 → eval → 採用ゲートのオフライン end-to-end dry-run（**API 不要**） | L1-F3/F5、M1 | `scripts/evaluate_structured_rules_candidate.py`・既存 workflow job | API を呼ばず full cycle が緑、採用ゲート判定が再現 |
| M1-T2 | **[FROZEN][Owner-gate]** 現状の手動 `promote_approved=true` を、ゲート通過時に自動昇格する経路として設計・実装提案 | M1（auto-promote） | `.github/workflows/immunization_loop.yml`・`scripts/promote_structured_candidate.py` | ゲート通過候補が人手なしで active detector に昇格 |
| M1-T3 | **[Owner-gate]** live paid-credit run の点火（GEMINI_API_KEY / live_model_enabled / workflow_dispatch） | L1-F13、M1 | workflow_dispatch | Owner が点火し、LLM 著作の防御が記録される |

**Done-when（M1）**: Owner が一切書いていない LLM 著作の防御が、ゲート通過で active detector に自動昇格する。

### M2 — It runs itself（P-C / 自己運転）

| ID | タスク | DoD | 主担当ファイル | Done-when |
|---|---|---|---|---|
| M2-T1 | 既存 self-healing の end-to-end 自動 revert 検証 | M2 | `scripts/post_promote_healthcheck.py`・`scripts/rollback_to_legacy_detector.py` | 不健全 promote が自動 rollback されることを再現確認 |
| M2-T2 | **[FROZEN][Owner-gate]** L1-F15 rollback/backtrack の実装タスク化（設計→実装は別タスク） | L1-F15 | `docs/ROLLBACK_BACKTRACK_DESIGN.md` → 実装 | 設計から実装への移行が承認・着手 |
| M2-T3 | **[Owner-gate]** cadence + budget 設定での連続サイクル運転 | M2 | workflow schedule / `scripts/api_budget.py`・`scripts/circuit_breaker.py` | 人手なしで世代改善、不良候補は自動 revert |

**Done-when（M2）**: 連続サイクルが人手介入なしで防御を改善し、不良候補は自動 revert される。

### M3 — It detects the unknown（P-B / 未知脅威）

| ID | タスク | DoD | 主担当ファイル | Done-when |
|---|---|---|---|---|
| M3-T1 | realistic + moving corpus、withheld threat class 評価（symbolic 指標を超える） | L2-V1 / L2-V3 | `core/test_attacker.py`・Owner 提供 corpus | 与えていない脅威クラスをブロック |
| M3-T2 | **[Owner-gate]** defensive threat-feed（CVE/CWE メタデータのみ、武器化なし）の Owner 再判断 | L1-F16 | `intelligence/threat_feeds.py`（disabled stub） | Owner が L1-F16 を再判断 |
| M3-T3 | adaptive tier（T3+）の実装タスク化 | M3 | `docs/ADAPTIVE_SECURITY_GAME_MODEL.md` → 実装 | tier 分離評価が稼働 |

**Done-when（M3）**: active detector が入力に与えていない脅威クラスをブロックし、その率が時間とともに上昇する。

### M4 — It remembers and co-evolves（P-A × P-B）

| ID | タスク | DoD | 主担当ファイル | Done-when |
|---|---|---|---|---|
| M4-T1 | 各世代の証拠（fitness / drift / 勝敗）を次提案へ供給するメモリ経路 | M4 | `data/evolution_history.json`・proposer prompt | 過去世代の証拠が次提案に反映 |
| M4-T2 | adaptive security game の生稼働 | M4 | `docs/ADAPTIVE_SECURITY_GAME_MODEL.md` | 移動する脅威分布で co-evolution が動作 |

**Done-when（M4）**: 移動する脅威分布上で世代間の測定可能なゲインが得られる。

### M5 — It defends the world（externalization）

| ID | タスク | DoD | Done-when |
|---|---|---|---|
| M5-* | **[BLOCKED]** scan tooling / packaging / CI templates。**Layer 2 完全達成 + Owner 受理まで着手禁止**（`docs/DEFINITION_OF_DONE.md:64-70` の禁止リスト準拠: scan CLI / 配布 / Action テンプレート / ダッシュボード / 公開デモ / PyPI） | M5 | Layer 2 ゲート通過後にのみ外部化を検討 |

---

## 横断タスク（ミッションと並行）

| ID | タスク | DoD | 現状 |
|---|---|---|---|
| X-L2 | **[Owner-gate]** Layer 2 完成: L2-V1〜V5 の証拠収集 + Owner 最終受理。Owner 提供の realistic corpus が必要 | `docs/DEFINITION_OF_DONE.md:80-87` | `owner_accepted_bounded`（完全達成は未） |
| X-L3 | L3-A4: Skill / Custom GPT / Codex post-task classifier | `docs/DEFINITION_OF_DONE.md:131,133` | **提案済み**（[`docs/audit_gate/L3A4_POSTASK_CLASSIFIER_PROPOSAL.md`](audit_gate/L3A4_POSTASK_CLASSIFIER_PROPOSAL.md)）。実装は別タスク・Owner 承認 |
| X-HY | **[FROZEN][Owner-gate]** `config.backup.toml` 除去（衛生） | `docs/DEFINITION_OF_DONE.md:172` | 未処理 |

---

## Owner ゲート一覧（`docs/MISSION_ROADMAP.md:107-113` より）

| Phase | Owner が承認する事項 |
|---|---|
| M1 | live paid-credit run（配線・dry-run は不要） |
| M2 | run cadence + budget |
| M3 | threat-feed / external-corpora 有効化（L1-F16 再判断） |
| M4 | 継続的 paid-credit 運用 |
| M5 | externalization（value gate 通過後） |

これらのゲートは「大胆かつ安全」に走るための統治であり、ブレーキではない。
防御専用（検知シグネチャと標準テストパターンのみ。武器化 exploit・多段チェーン・回避指南・攻撃ツール・実トラフィック捕捉は行わない）。

---

> Authority: 本書は `docs/MISSION_ROADMAP.md`・`docs/DEFINITION_OF_DONE.md` に従属し、
> current-state は機械的証拠 / `data/project_state.json` / `docs/PROJECT_STATE.md` が決定する。
> 本書はそれらを独立に上書きしない。
