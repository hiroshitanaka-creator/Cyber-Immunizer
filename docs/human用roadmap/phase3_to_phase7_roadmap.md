# Human Roadmap: Phase 3〜7 の進行判断表

この文書は、Human Owner が Phase 2.5 closeout 後に、Phase 3〜7へ進む順序・判断点・禁止事項を確認するための人間向けロードマップです。

## 現在地

| 項目 | 状態 |
|---|---|
| 現在の段階 | Phase 2.5 hardening 完了後の closeout 準備 |
| 直近の完了 | PR #46〜#53 の hardening / regression / behavior tests |
| 次の正式タスク | PHASE2.5-CLOSEOUT-001 |
| Phase 3 activation | 未開始 |
| Gemini API接続 | 未接続 |
| `live_model_enabled` | `false` 維持 |
| GitHub Secrets使用開始 | 未開始 |
| 実Gemini API call | 未実行 |

## 原則

1. Phase 2.5 closeout は Phase 3 activation ではない。
2. Phase 3 activation には Human Owner の明示GOが必要。
3. API接続、`live_model_enabled=true`、GitHub Secrets使用、実Gemini API call は、専用PRで扱う。
4. Claude / Codex / Grok / Gemini の出力は補助情報であり、最終判断は Human Owner が行う。
5. GPT は Audit Gate として、PR・CI・diff・review thread・workflow・data変更を監査する。

## 固定ゲート質問

Phase 3 activation PRに入る前に、必ず以下をHuman Ownerへ確認する。

```text
ここからは Phase 3 activation PR です。
Gemini API接続、live_model_enabled、GitHub Secrets使用に関係します。
進めてよいですか？
```

この質問へのHuman Ownerの明示GOがない限り、Phase 3 activation PRを作成・指示・提案しない。

---

## Phase 2.5 closeout後の大まかな進行表

| 段階 | 目的 | 主なタスク | Human Owner判断 | 完了条件 | 禁止事項 |
|---|---|---|---|---|---|
| Phase 2.5 Closeout | hardening完了証跡を固定する | PR #46〜#53、Grok監査、Claude Code監査、GPT監査を整理し、docs/progressを更新 | Phase 2.5を正式に閉じるか | closeout doc作成、残リスク分類、Phase 3判断材料の整理 | API接続、Secrets追加、`live_model_enabled=true` |
| Phase 3 Go/No-Go Review | Phase 3 activationへ進むか判断する | checklist確認、Secrets方針確認、課金上限確認、運用頻度確認 | Phase 3 activation PRへ進むか | Human OwnerがGO/NO-GOを明示 | 勝手なactivation、実API call |
| Phase 3 Activation | Gemini APIを制御付きで接続する | GitHub Secret登録確認、preflight確認、`live_model_enabled`専用PR、最小実API call設計 | 固定ゲート質問への明示GO | live pathが最小範囲で有効化され、budget/ledgerがfail-closed | scheduleからの有料API、main外paid run、広範なsecret注入 |
| Phase 4 Controlled Evolution | 小規模な実進化ループを安全に回す | 1日少数回、1回少数mutation、ledger確認、CI確認、no auto-promote運用 | 実運用頻度と上限を許可するか | API call回数・ledger・candidate評価が安定 | 自動promotion、予算上限超過、失敗run放置 |
| Phase 5 Promotion Governance | 良い候補を安全に本体へ昇格する | promote gate、Human Owner承認、adoption gate、evidence ledger | promoteを許可するか | promote条件・証跡・rollback方針が明確 | 自動merge、自動release、未検証candidate昇格 |
| Phase 6 Observability / Audit Ledger | 長期運用の証跡を見える化する | usage ledger、evolution history、失敗分類、cost trend、test trend | 継続運用に耐えるか | 監査可能な履歴・予算・失敗傾向が残る | 証跡なし運用、手動メモ依存 |
| Phase 7 Scaled Autonomous Operation | より自律的な運用へ拡張する | 実行頻度拡大、policy強化、Stage C/D allowlist、外部review運用 | 自律度を上げるか | 予算・安全・品質・rollbackが揃う | 安全境界を超えた自律化 |

---

## Phase別の詳細

### Phase 3: Controlled API Activation

| 項目 | 内容 |
|---|---|
| 目的 | Gemini APIを、最小権限・最小頻度・予算上限付きで接続する |
| 実施前提 | Phase 2.5 closeout完了、Human Owner明示GO、GitHub Secrets方針確認 |
| 主なPR | Phase 3 activation専用PR |
| 触る可能性があるもの | GitHub Secrets、workflowのAPI step、`live_model_enabled`、preflight docs |
| 必須検査 | Secrets step-level injection、ledger strict load、budget pre-call gate、main-only paid run |
| Done | 1回の最小API接続がbudget/ledger/CIに記録され、fail-closedが崩れていない |

### Phase 4: Controlled Evolution Loop

| 項目 | 内容 |
|---|---|
| 目的 | 実APIを使った候補生成を小さく安全に回す |
| 実施前提 | Phase 3 activation成功、ledgerとCIが安定 |
| 運用例 | 1日少数回、1回1〜3 mutation程度から開始 |
| 主な監査点 | API call回数、ledger増分、candidate評価、resource limit、failure reason |
| Done | 一定期間、予算・CI・候補評価・ledgerが安定する |

### Phase 5: Promotion Governance

| 項目 | 内容 |
|---|---|
| 目的 | 採用候補を安全に本体へ昇格する |
| 実施前提 | Controlled Evolutionで候補品質と証跡が安定 |
| 主な監査点 | adoption gate、regression pass、latency、false positive、Human Owner承認 |
| Done | promote判断とrollback方針が明確になり、手動承認で昇格可能 |

### Phase 6: Observability / Audit Ledger

| 項目 | 内容 |
|---|---|
| 目的 | 長期運用の判断材料を蓄積する |
| 実施前提 | Phase 4〜5の運用ログが増える |
| 主なタスク | cost trend、test trend、failure taxonomy、evolution history、ledger監査 |
| Done | Human Ownerが「続ける・止める・増やす」を証跡で判断できる |

### Phase 7: Scaled Autonomous Operation

| 項目 | 内容 |
|---|---|
| 目的 | 自律度・実行頻度・探索範囲を拡張する |
| 実施前提 | Phase 3〜6の安全境界が実績で確認済み |
| 主なタスク | policy Stage C/D、より強いallowlist、review automation、cost cap強化 |
| Done | 予算・安全・品質・rollbackの全てが自律運用に耐える |

---

## 進行判断チェックリスト

| 判断 | Yesなら進む | Noなら止める |
|---|---|---|
| Phase 2.5 closeout docが最新か | Phase 3 Go/No-Goへ | closeout docs更新 |
| `live_model_enabled=false` が維持されているか | Phase 3判断へ | activation混入調査 |
| Gemini Secret方針が明確か | activation PR設計へ | Secrets方針整理 |
| budget/ledger fail-closedが維持されているか | preflightへ | ledger/budget修正 |
| main-only paid runが維持されているか | activation PR設計へ | workflow修正 |
| Human Ownerが固定ゲートにGOしたか | Phase 3 activation PRへ | activation禁止 |

## 現時点の推奨

1. PR #53 merge後のmainを基準に PHASE2.5-CLOSEOUT-001 を実施する。
2. Closeout docで、Grok / Claude Code / GPT監査結果を統合する。
3. Closeout完了後、Phase 3 Go/No-Go Reviewへ進む。
4. Human Ownerの明示GOがある場合だけ、Phase 3 activation PRを設計する。

## 注意

このロードマップはHuman Owner向けの判断補助資料であり、自動進行命令ではない。
