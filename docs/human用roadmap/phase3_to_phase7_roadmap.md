<!--
AI_DOC_META
status: CURRENT
scope: Human Owner roadmap for Phase 3 to Phase 7 planning and thread handoff.
use_for:
  - explaining Phase 3 to Phase 7 sequence to Human Owner
  - preparing new thread handoff before Phase 3
  - identifying Human Owner decision points
  - preventing accidental Phase 3 activation
do_not_use_for:
  - executing Phase 3 activation
  - setting live_model_enabled=true
  - registering or modifying GitHub Secrets
  - calling Gemini API
  - replacing docs/PHASE_3_GO_NO_GO_CHECKLIST.md
related:
  - docs/AI_ENTRYPOINT.md
  - docs/PHASE_2_5_CLOSEOUT_AUDIT.md
  - docs/PHASE_3_GO_NO_GO_CHECKLIST.md
  - docs/API_ACTIVATION_CHECKLIST.md
last_reviewed: 2026-05-31
AI_DOC_META_END
-->

# Human Roadmap: Phase 3〜7 の進行判断表

この文書は、Human Owner が Phase 2.5 closeout 後に Phase 3〜7へ進む順序・判断点・禁止事項を確認するための人間向けロードマップです。

この文書は **実行命令ではありません**。  
この文書は **Phase 3 activationではありません**。  
この文書は **Gemini API接続・GitHub Secrets設定・`live_model_enabled=true` を許可しません**。

---

## 0. この文書の使い方

| 使い方 | 内容 |
|---|---|
| Human Owner向けの地図 | Phase 3〜7で何をするか、どこで判断するかを確認する |
| スレッド切替用の共通認識 | Phase 3前に新しいGPTスレッドへ移るときの引き継ぎ資料にする |
| GPT Audit Gateの参照資料 | GPTが勝手に進めず、Human Ownerへ相談すべき判断点を確認する |
| Claude / Codex / Grok監査の補助 | 実装AIやレビューAIがPhaseの目的を誤読しないようにする |

この文書で最も重要なこと:

1. **Phase 2.5 closeout後に自動でPhase 3 activationへ進まない。**
2. **Phase 3 activationにはHuman Ownerの明示GOが必要。**
3. **API接続・Secrets・`live_model_enabled=true`は専用PRで扱う。**
4. **Phase 3以降も、全ての段階でHuman Ownerが最終判断者。**

---

## 1. 現在地

| 項目 | 状態 |
|---|---|
| 現在の段階 | Phase 2.5 hardening 完了後の closeout 準備 |
| 直近の完了 | PR #46〜#53 の hardening / regression / behavior tests |
| 現在のPR | PR #54: Phase 2.5 closeout audit and human roadmap |
| 次の正式タスク | PHASE2.5-CLOSEOUT-001 |
| Phase 3 activation | 未開始 |
| Gemini API接続 | 未接続 |
| `live_model_enabled` | `false` 維持 |
| GitHub Secrets使用開始 | 未開始 |
| 実Gemini API call | 未実行 |
| Phase 3判断 | まだ未実施 |

---

## 2. 絶対原則

| 原則 | 内容 |
|---|---|
| Repository owner | Human Owner |
| GPTの役割 | Audit Gate。監査・分類・提案。所有者ではない |
| Claude Codeの役割 | 実装担当。ただしHuman Ownerが許可したタスクのみ |
| Codexの役割 | 反証・レビュー補助。GPT監査の代替ではない |
| Grok / Geminiの役割 | 必要時のみ外部監査・セカンドオピニオン |
| Merge判断 | Human Owner |
| Phase移行判断 | Human Owner |
| API接続判断 | Human Owner |
| Secrets登録判断 | Human Owner |
| `live_model_enabled=true`判断 | Human Owner |

### 禁止事項

以下は、Human Ownerの明示GOなしに行ってはならない。

- Phase 3 activation PRの作成
- `live_model_enabled=true` への変更
- GitHub Secretsの登録・変更・参照を前提にした実行
- Gemini APIの実call
- `gemini-paid-credit` 実運用開始
- scheduleからの有料API実行
- main以外からのpaid-credit実行
- 自動promotion有効化
- 未検証candidateの昇格
- Phase activationと無関係な変更を混ぜたPR

---

## 3. 固定ゲート質問

Phase 3 activation PRに入る前に、GPT Audit Gateは必ず以下をHuman Ownerへ確認する。

```text
ここからは Phase 3 activation PR です。
Gemini API接続、live_model_enabled、GitHub Secrets使用に関係します。
進めてよいですか？
```

この質問へのHuman Ownerの明示GOがない限り、Phase 3 activation PRを作成・指示・提案してはならない。

---

## 4. Phase 2.5 closeout後の全体進行表

| 段階 | 目的 | 主なタスク | Human Owner判断 | 完了条件 | 禁止事項 |
|---|---|---|---|---|---|
| Phase 2.5 Closeout | hardening完了証跡を固定する | PR #46〜#53、Grok監査、Claude Code監査、GPT監査を整理し、docs/progressを更新 | Phase 2.5を正式に閉じるか | closeout doc作成、残リスク分類、Phase 3判断材料の整理 | API接続、Secrets追加、`live_model_enabled=true` |
| Phase 3 Go/No-Go Review | Phase 3 activationへ進むか判断する | checklist確認、Secrets方針確認、課金上限確認、運用頻度確認 | Phase 3 activation PRへ進むか | Human OwnerがGO/NO-GOを明示 | 勝手なactivation、実API call |
| Phase 3 Activation | Gemini APIを制御付きで接続する | GitHub Secret登録確認、preflight確認、`live_model_enabled`専用PR、最小実API call設計 | 固定ゲート質問への明示GO | live pathが最小範囲で有効化され、budget/ledgerがfail-closed | scheduleからの有料API、main外paid run、広範なsecret注入 |
| Phase 4 Controlled Evolution | 小規模な実進化ループを安全に回す | 1日少数回、1回少数mutation、ledger確認、CI確認、no auto-promote運用 | 実運用頻度と上限を許可するか | API call回数・ledger・candidate評価が安定 | 自動promotion、予算上限超過、失敗run放置 |
| Phase 5 Promotion Governance | 良い候補を安全に本体へ昇格する | promote gate、Human Owner承認、adoption gate、rollback方針 | promoteを許可するか | promote条件・証跡・rollback方針が明確 | 自動merge、自動release、未検証candidate昇格 |
| Phase 6 Observability / Audit Ledger | 長期運用の証跡を見える化する | usage ledger、evolution history、失敗分類、cost trend、test trend | 継続運用に耐えるか | 監査可能な履歴・予算・失敗傾向が残る | 証跡なし運用、手動メモ依存 |
| Phase 7 Scaled Autonomous Operation | より自律的な運用へ拡張する | 実行頻度拡大、policy強化、Stage C/D allowlist、外部review運用 | 自律度を上げるか | 予算・安全・品質・rollbackの全てが揃う | 安全境界を超えた自律化 |

---

# Phase 2.5 Closeout 詳細

## 5. Phase 2.5 Closeout の目的

Phase 2.5 closeout の目的は、Phase 3 activation ではなく、Phase 3へ進む判断材料を固定すること。

### 5.1 Closeoutでやること

| タスク | 内容 |
|---|---|
| hardening PR整理 | PR #46〜#53の目的・変更・安全境界を一覧化する |
| 外部監査整理 | Grok監査・Claude Code監査・GPT監査を採用 / 不採用 / 後回しに分類する |
| 残リスク整理 | indirect dunder、custom output_root、実billing未検証などを記録する |
| Go/No-Go準備 | Phase 3でHuman Ownerが確認すべき外部事項を整理する |
| docs更新 | Closeout doc、Go/No-Go checklist、Human roadmap、AI_ENTRYPOINTを同期する |

### 5.2 Closeoutでやらないこと

- Gemini API接続
- GitHub Secrets登録
- `live_model_enabled=true`
- 実API call
- workflow activation
- detector挙動変更
- budget cap変更
- 自動promotion変更

### 5.3 Closeout完了条件

| 条件 | 完了判定 |
|---|---|
| PR #46〜#53がmainに反映済み | Yes / No |
| closeout audit docが存在する | Yes / No |
| human roadmapが存在する | Yes / No |
| Phase 3 Go/No-Go checklistがPhase 2.5完了後の状態に更新されている | Yes / No |
| AI_ENTRYPOINTがcloseout / roadmapへ誘導する | Yes / No |
| Phase 3 activationが混入していない | Yes / No |
| CIがgreen | Yes / No |
| GPT Audit GateがPR #54を監査済み | Yes / No |

---

# Phase 3 詳細: Controlled API Activation

## 6. Phase 3の目的

Phase 3の目的は、Gemini APIを **最小権限・最小頻度・予算上限付きで接続し、fail-closedを保ったまま最初の実API経路を確認すること**。

Phase 3は「大量に進化ループを回す段階」ではない。  
Phase 3は「API接続の安全確認段階」。

## 7. Phase 3開始前の判断

Phase 3へ進む前に、Human Ownerが以下を判断する。

| 判断項目 | 内容 | 判断者 |
|---|---|---|
| API接続を試すか | Gemini APIをrepo workflowから使う段階へ進むか | Human Owner |
| Secretsを登録するか | GitHub Secretsに `GEMINI_API_KEY` を登録するか | Human Owner |
| 課金上限を許容するか | daily/monthly budget capとGoogle側billing alertを確認するか | Human Owner |
| 最初のrunを監視できるか | 初回実行時にHuman Ownerが画面を見て止められるか | Human Owner |
| Phase 3 activation PRへ進むか | 固定ゲート質問へGOするか | Human Owner |

## 8. Phase 3の推奨タスク分解

| Task ID | タスク | 種別 | 目的 | Done |
|---|---|---|---|---|
| PHASE3-GONO-001 | Phase 3 Go/No-Go review | 監査 | closeout後にactivation条件を確認 | GO/NO-GO表が埋まる |
| PHASE3-SECRET-001 | GitHub Secrets外部確認 | Human Owner外部作業 | `GEMINI_API_KEY`が登録済みか確認 | secret値をrepo/PR/chatに出さず確認完了 |
| PHASE3-BILLING-001 | Billing / budget alert確認 | Human Owner外部作業 | Google側課金・alertを確認 | 月次/日次上限を人間が把握 |
| PHASE3-PREFLIGHT-001 | paid-credit preflight実行 | workflow確認 | API callなしでkey存在・ledger・budgetを確認 | preflight成功、ledger変更なし |
| PHASE3-ACTIVATION-PR-001 | activation専用PR設計 | PR | `live_model_enabled`やAPI step境界を専用PRで扱う | unrelated変更なし |
| PHASE3-FIRST-LIVE-001 | 最小実API run | 手動実行 | 1回だけ実API経路を確認 | ledger記録、CI、failure handling確認 |
| PHASE3-POSTRUN-001 | 初回run監査 | 監査 | cost/ledger/log/CIを確認 | fail-openなしを確認 |

## 9. Phase 3で触る可能性があるファイル

| ファイル | 触る可能性 | 注意 |
|---|---|---|
| `data/genome.json` | あり | `live_model_enabled`は専用activation PRでのみ変更可 |
| `.github/workflows/immunization_loop.yml` | 可能性あり | Secret injectionはstep-levelのみ。workflow全体envは禁止 |
| `docs/API_ACTIVATION_CHECKLIST.md` | あり | 手順更新のみ。secret値は書かない |
| `docs/API_ACTIVATION_RUNBOOK.md` | あり | 実行手順更新のみ。activationと混ぜすぎない |
| `docs/PHASE_3_GO_NO_GO_CHECKLIST.md` | あり | Go/No-Go判断記録 |

## 10. Phase 3で触ってはいけないもの

- detector改善
- AST policy大改造
- apply_mutation改造
- evaluate_candidate改造
- budget/ledger仕様変更
- unrelated docs cleanup
- release / tag / publish
- 自動promotion有効化

## 11. Phase 3の停止条件

| 停止条件 | 対応 |
|---|---|
| secretがログやPR本文に出た | 即停止、secret rotation、該当ログ調査 |
| ledgerが更新されない | 即停止、API usage記録の不整合調査 |
| budget capを超えそう | 即停止、Google側billing確認 |
| workflowがmain外でpaid run可能 | 即停止、workflow修正 |
| generated codeがwrite jobで実行される | 即停止、permission境界修正 |
| CIがred | 原因分類まで停止 |
| Human Ownerが監視できない | 実行しない |

## 12. Phase 3完了条件

| 条件 | 完了判定 |
|---|---|
| preflightが成功する | Yes / No |
| activation PRが専用PRとしてmergeされる | Yes / No |
| 初回実API callが最小回数で完了する | Yes / No |
| ledgerにusage recordが残る | Yes / No |
| budget capが維持される | Yes / No |
| generated codeがwrite permissionやSecretsを持たない | Yes / No |
| failure時にpatchが返らない | Yes / No |
| Human Ownerが結果を確認する | Yes / No |

---

# Phase 4 詳細: Controlled Evolution Loop

## 13. Phase 4の目的

Phase 4の目的は、API接続済みの状態で、進化ループを小さく安全に回し、候補生成・評価・ledger・CIが安定するかを確認すること。

Phase 4は「自律運用」ではない。  
Phase 4は「制限付き実験運用」。

## 14. Phase 4の推奨運用制限

| 項目 | 初期推奨 |
|---|---|
| 実行頻度 | 1日1回〜3回程度 |
| 1回のAPI request cap | `max_model_requests_per_run=1` 維持から開始 |
| mutation候補数 | 1件から開始 |
| promotion | 原則OFF、またはHuman Owner承認必須 |
| schedule | 最初はpaid modeでは使わない |
| 監視 | Human OwnerまたはGPT監査でrunごとに確認 |

## 15. Phase 4の推奨タスク分解

| Task ID | タスク | 種別 | 目的 | Done |
|---|---|---|---|---|
| PHASE4-RUN-001 | 手動controlled run | 実行 | 1回の実進化loopを確認 | ledger/CI/logが正常 |
| PHASE4-LEDGER-001 | ledger増分監査 | 監査 | 使用量が正しく記録されるか確認 | cost/attempt数が整合 |
| PHASE4-CANDIDATE-001 | candidate評価監査 | 監査 | 生成candidateがpolicy/evaluateを通るか確認 | pass/fail理由が分類済み |
| PHASE4-FAILURE-001 | failure taxonomy作成 | docs/test | 失敗原因を分類する | timeout/budget/schema/policy/API/ledger分類 |
| PHASE4-LIMIT-001 | 実行上限調整判断 | Human Owner判断 | frequencyやbudgetを増やすか決める | 証跡に基づきGO/NO-GO |

## 16. Phase 4で見るべき証跡

| 証跡 | 見る理由 |
|---|---|
| API usage ledger | 予算がfail-openになっていないか |
| workflow run logs | API/ledger/evaluateの境界が守られているか |
| candidate patch artifact | raw payloadやsecret混入がないか |
| evaluation report | regression / FP / latency / adoption gate |
| CI result | repository全体の安全性維持 |
| Codex/GPT review | 見落とし反証 |

## 17. Phase 4の停止条件

| 停止条件 | 対応 |
|---|---|
| ledger recordが欠落 | 実行停止、ledger/persist調査 |
| API call数が上限を超える | 実行停止、retry/cap調査 |
| candidateがraw secretやraw payloadを含む | 実行停止、prompt/scan調査 |
| evaluateがrunner不安定化 | 実行停止、resource limit調査 |
| false positiveが増加 | candidate不採用、fitness/threshold確認 |
| scheduleが勝手にpaid run | workflow即修正 |

## 18. Phase 4完了条件

| 条件 | 完了判定 |
|---|---|
| 複数回のcontrolled runでledgerが安定 | Yes / No |
| 失敗runの分類が可能 | Yes / No |
| budget capが守られる | Yes / No |
| candidate評価が安定 | Yes / No |
| Human Ownerが運用頻度を判断できる | Yes / No |

---

# Phase 5 詳細: Promotion Governance

## 19. Phase 5の目的

Phase 5の目的は、生成candidateの中から採用候補を安全に本体へ昇格する手順を確立すること。

Phase 5は「良いcandidateが出たら自動でmergeする段階」ではない。  
Phase 5は「promotionの判断と証跡を厳格化する段階」。

## 20. Phase 5の主な判断

| 判断項目 | 内容 | 判断者 |
|---|---|---|
| candidateをpromote候補にするか | adoption gate結果を見て判断 | GPT + Human Owner |
| promote workflowを実行するか | Human Ownerが明示承認 | Human Owner |
| mergeするか | PR監査結果を見て判断 | Human Owner |
| rollback方針はあるか | 悪化時に戻せるか確認 | GPT + Human Owner |

## 21. Phase 5の推奨タスク分解

| Task ID | タスク | 種別 | 目的 | Done |
|---|---|---|---|---|
| PHASE5-PROMOTE-001 | promote gate再監査 | 監査 | promote条件が厳格か確認 | adoption gate/permission/ledger整合 |
| PHASE5-CANDIDATE-REVIEW-001 | candidate diff監査 | 監査 | detector変更が安全か確認 | AST/policy/fitness/regression確認 |
| PHASE5-HUMAN-GATE-001 | Human Owner承認記録 | docs/protocol | promote承認を記録する | promote_approved=trueの根拠あり |
| PHASE5-ROLLBACK-001 | rollback手順確認 | docs/test | 悪化時に戻せるか確認 | rollback pathが明確 |
| PHASE5-MERGE-001 | promoted detector PR監査 | PR audit | 本体反映可否を判断 | GPT Primary Audit完了 |

## 22. Phase 5の禁止事項

- 自動promotion
- 未監査candidateのmerge
- Human Owner承認なしのpromote
- test/fitness悪化の無視
- evolution_historyなしの昇格
- rollback不能な変更

## 23. Phase 5完了条件

| 条件 | 完了判定 |
|---|---|
| promote条件が明文化されている | Yes / No |
| Human Owner承認ゲートが機能している | Yes / No |
| promoted candidateのPR監査手順が固定されている | Yes / No |
| rollback/backtrack方針が確認済み | Yes / No |
| 実際に安全なcandidate昇格を1回以上実施 | Yes / No |

---

# Phase 6 詳細: Observability / Audit Ledger

## 24. Phase 6の目的

Phase 6の目的は、長期運用で「続ける・止める・増やす・戻す」を判断できる証跡を整備すること。

Phase 6は「もっと回す段階」ではない。  
Phase 6は「運用判断できる観測基盤を作る段階」。

## 25. Phase 6で可視化するもの

| 観測対象 | 内容 |
|---|---|
| cost trend | 日次/月次使用額、上限接近率 |
| request trend | runごとのAPI request数 |
| failure taxonomy | schema/API/budget/ledger/policy/evaluate/CI failure分類 |
| candidate quality | adoption gate通過率、FP率、regression pass rate |
| latency trend | detector latencyの増減 |
| promotion history | どのcandidateがなぜ採用されたか |
| rollback history | いつ何を戻したか |

## 26. Phase 6の推奨タスク分解

| Task ID | タスク | 種別 | 目的 | Done |
|---|---|---|---|---|
| PHASE6-LEDGER-VIEW-001 | ledger summary作成 | script/docs | ledgerを人間が読める形にする | cost/day/monthが見える |
| PHASE6-FAILURE-TAXONOMY-001 | failure分類表 | docs/tests | 失敗の意味を統一 | failure classが固定 |
| PHASE6-HISTORY-001 | evolution history監査 | docs/tests | 採用・不採用履歴を追える | history整合性確認 |
| PHASE6-DASHBOARD-001 | summary artifact | workflow/docs | runごとの簡易summary | Human Ownerが判断可能 |
| PHASE6-STOP-RULE-001 | stop rule明文化 | protocol | いつ止めるかを固定 | stop criteriaあり |

## 27. Phase 6完了条件

| 条件 | 完了判定 |
|---|---|
| cost trendを見られる | Yes / No |
| failure taxonomyがある | Yes / No |
| promotion / rollback historyを追える | Yes / No |
| Human Ownerが運用判断できるsummaryがある | Yes / No |
| stop ruleが明文化されている | Yes / No |

---

# Phase 7 詳細: Scaled Autonomous Operation

## 28. Phase 7の目的

Phase 7の目的は、自律度・実行頻度・探索範囲を拡張すること。

Phase 7は、Phase 3〜6で安全境界が実績として確認された後にだけ検討する。

## 29. Phase 7で初めて検討すること

| 検討項目 | 内容 |
|---|---|
| 実行頻度拡大 | 1日複数回、条件付きscheduleなど |
| mutation数拡大 | 1run複数候補の比較 |
| policy Stage C/D | より厳密なallowlist移行 |
| review automation | GPT/Codex/外部AIレビューの標準化 |
| budget自動警戒 | cap接近時の自動停止 |
| rollback automation | 悪化時の自動rollback候補提示 |
| multi-model review | Gemini/Grok等の外部監査の節目利用 |

## 30. Phase 7で絶対に必要な前提

| 前提 | 理由 |
|---|---|
| budget capが長期的に安定 | 自律度拡大で課金事故を防ぐため |
| ledgerが信頼できる | 使用量・失敗・判断が追えないと危険 |
| promote governanceが確立 | 自動候補を本体に入れるリスクを管理するため |
| rollbackが機能 | 自律変更の悪影響を戻せる必要がある |
| Human Ownerが停止できる | 完全自律ではなく制御付き自律にするため |

## 31. Phase 7の禁止事項

- 無制限API実行
- Human Ownerなしの自動merge
- budget capなしの探索
- rollbackなしの自律更新
- generated codeへの過信
- external reviewをGPT監査の代替にすること

## 32. Phase 7完了条件

| 条件 | 完了判定 |
|---|---|
| 長期budgetが安定している | Yes / No |
| reviewとrollbackが機能している | Yes / No |
| 自律実行の停止条件が明確 | Yes / No |
| Human Ownerが許可した自律範囲内で動いている | Yes / No |
| 異常時に人間へ戻れる | Yes / No |

---

# スレッド切替準備

## 33. Phase 3前にスレッドを変える理由

Phase 3は、API・Secrets・課金・`live_model_enabled`に関わるため、文脈の混濁を避ける必要がある。

Phase 3前に新スレッドへ移ることで、以下を固定できる。

- Phase 2.5がどこまで完了したか
- どのPRが何を守っているか
- 何が未開始か
- Phase 3 activationに必要な固定ゲート
- Human Ownerが最終判断者であること
- GPTがAudit Gateであること

## 34. 新スレッド開始時に貼るべき情報

新しいGPTスレッドを開始する場合、以下を貼る。

```text
Cyber-Immunizer Phase 3 preparation thread start.

Repository:
https://github.com/hiroshitanaka-creator/Cyber-Immunizer

Current state:
- Phase 2 complete.
- Phase 2.5 hardening complete through PR #53.
- Phase 2.5 closeout docs are in PR #54.
- Phase 3 is not started.
- Gemini API is not connected.
- live_model_enabled is false.
- GitHub Secrets are Human Owner controlled and not asserted by repository files.
- Real Gemini API calls have not been executed by repository work.

Required docs to read first:
1. docs/PHASE_2_5_CLOSEOUT_AUDIT.md
2. docs/human用roadmap/phase3_to_phase7_roadmap.md
3. docs/PHASE_3_GO_NO_GO_CHECKLIST.md
4. docs/API_ACTIVATION_CHECKLIST.md
5. docs/audit_gate/PR_AUDIT_PROTOCOL.md

Fixed gate question before Phase 3 activation:
ここからは Phase 3 activation PR です。
Gemini API接続、live_model_enabled、GitHub Secrets使用に関係します。
進めてよいですか？

Do not proceed to Phase 3 activation without Human Owner explicit GO.
```

## 35. 新スレッドで最初に確認すること

| 確認 | 方法 |
|---|---|
| mainの最新commit | GitHubで確認 |
| PR #54がmerge済みか | PR状態確認 |
| `live_model_enabled=false` | `data/genome.json`確認 |
| Phase 3未開始 | closeout doc / Go-No-Go checklist確認 |
| Secrets状態 | Human Ownerが外部確認 |
| CI green | current mainのActions確認 |

## 36. 新スレッドで禁止すること

- 過去ログを推測で補う
- PR本文だけで完了扱いする
- Claude自己申告だけで判断する
- Codex reviewをGPT監査の代替にする
- Phase 3 activationへ勝手に進む
- Human OwnerのGOなしにSecrets/API/live_model_enabledを扱う

---

# Human Owner用の進行判断チェックリスト

| 判断 | Yesなら進む | Noなら止める |
|---|---|---|
| Phase 2.5 closeout docが最新か | Phase 3 Go/No-Goへ | closeout docs更新 |
| PR #54がmerge済みか | Phase 3 Go/No-Goへ | PR #54監査/修正 |
| `live_model_enabled=false` が維持されているか | Phase 3判断へ | activation混入調査 |
| Gemini Secret方針が明確か | activation PR設計へ | Secrets方針整理 |
| billing / budget alertが確認済みか | activation PR設計へ | Google側確認 |
| budget/ledger fail-closedが維持されているか | preflightへ | ledger/budget修正 |
| main-only paid runが維持されているか | activation PR設計へ | workflow修正 |
| Human Ownerが固定ゲートにGOしたか | Phase 3 activation PRへ | activation禁止 |

---

## 現時点の推奨

1. PR #54を監査する。
2. PR #54でcloseout docsとhuman roadmapをmergeする。
3. 新スレッドに切り替える。
4. 新スレッドでPhase 3 Go/No-Go Reviewを行う。
5. Human Ownerが明示GOした場合のみ、Phase 3 activation PRを設計する。

## 注意

このロードマップはHuman Owner向けの判断補助資料であり、自動進行命令ではない。

後続のPhaseで細部がズレた場合は、その時点のmain・CI・budget・ledger・Human Owner判断を優先して更新する。
