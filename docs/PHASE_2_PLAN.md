# Cyber-Immunizer Phase 2 計画 — API未接続運用強化

> **このドキュメントは Phase 2 の計画と制約を記録します。**  
> Phase 2 は API 未接続のまま進行します。実 Gemini API 接続は Phase 3 以降です。  
> **Human Owner の明示的な判断なく Phase 3 へ移行してはなりません。**

---

## Phase 2 の目的

Phase 1 で確立した安全基盤（MAPE-K ループ・AST ポリシー・サブプロセス隔離・API 予算管理・fail-closed 設計）の上に、**API を接続しない状態での運用耐性**をさらに強化することです。

API 接続前に十分な運用品質・監査品質・ドキュメント品質を確保することで、Phase 3 での API 接続を安全かつ確実に実施できるようにします。

---

## API未接続のまま進める理由

1. **安全性の優先**: API 接続はコスト・プライバシー・意図しない実行リスクを伴います。接続前に運用プロセスを十分に検証します。
2. **段階的な信頼構築**: Phase 1 の安全基盤が実際の運用ストレスに耐えられることを、API なしで確認します。
3. **Human Owner の決定権を尊重**: API 接続タイミングは Human Owner の明示的な判断に委ねます。AI エージェントが自律的に接続タイミングを決定しません。
4. **fail-closed の検証**: API キー未登録状態での preflight fail-closed 挙動が、実際の運用で正しく機能することを確認します。

---

## Phase 2 でやること

以下の項目を Phase 2 の範囲として実施します。

### 1. README dashboard 精度向上

- ステータスブロック（`CYBER_IMMUNIZER_STATUS_START` / `CYBER_IMMUNIZER_STATUS_END`）の表示項目・精度の見直し
- Phase 2 計画ドキュメントへのリンク追加
- 現在のフェーズ（Phase 2: API未接続運用強化）の明示

### 2. rollback / backtrack 設計の文書化

- 変異昇格後の rollback 手順の設計と文書化
- backtrack（前世代への復帰）条件と手順の整理
- `evolution_history.json` を用いた復元可能性の確認

### 3. evolution_history の監査強化

- `data/evolution_history.json` の項目・スキーマの見直し
- 監査証跡（誰が・いつ・なぜ昇格させたか）の記録仕様の明確化
- evolution history の整合性チェック仕様の検討

### 4. offline-sample の dry-run / promote 分離検討

- `--offline-sample` モードにおける dry-run（評価のみ）と promote（昇格）の分離設計
- dry-run 結果を Human Owner が確認してから promote する運用フローの検討
- 分離設計の文書化

### 5. API接続前の運用チェックリスト整備

- Phase 3（API接続）開始前に確認すべき事項の網羅的なチェックリスト作成
- `docs/API_ACTIVATION_RUNBOOK.md` の補足・更新
- Human Owner がチェックリストを完了した後にのみ Phase 3 を開始できる運用フローの確立

---

## Phase 2 でやらないこと

以下の項目は Phase 2 の範囲外です。これらは Phase 3 以降に実施します。

| 禁止事項 | 理由 |
|---|---|
| **GEMINI_API_KEY 登録** | Phase 3 以降で Human Owner の判断のもと実施する |
| **`live_model_enabled=true` への変更** | API 接続前に変更してはならない |
| **実 Gemini API call の実行** | `live_model_enabled=false` を Phase 2 中は維持する |
| **cron でのAPI実行** | スケジュール実行は常に noop モードのまま |
| **複数候補生成** | API 接続後の Phase 3 以降の機能 |
| **自己修復 retry** | API 接続後の Phase 3 以降の機能 |

> ⚠️ **Phase 2 中に上記の禁止事項を含む PR は、GPT Audit Gate によって BLOCK または REQUEST CHANGES の対象になります。**  
> 詳細は `docs/AUDIT_CHARTER.md` の Phase 2 transition rule セクションを参照してください。

---

## Phase 3 へ進む条件

以下のすべてを満たした場合にのみ、Phase 3（実 Gemini API 接続）への移行を検討します。

### 必須条件（すべて満たすこと）

- [ ] Phase 2 の全実施項目が完了している
- [ ] CI が通過している（`python -m pytest` 全件 pass）
- [ ] `live_model_enabled=false` が維持されている（`data/genome.json` で確認）
- [ ] `GEMINI_API_KEY` がリポジトリ内のいかなるファイルにも含まれていない
- [ ] API 接続前の運用チェックリストが整備され、Human Owner が確認済みである
- [ ] `docs/API_ACTIVATION_RUNBOOK.md` の手順が最新状態に維持されている
- [ ] rollback / backtrack 手順が文書化されている

### Human Owner の明示的判断（必須）

Phase 3 への移行は、**Human Owner（hiroshitanaka-creator）が「Phase 3 へ移行する」と明示的に決定**した場合にのみ開始されます。

AI エージェント（Claude Code）は Phase 3 移行を自律的に判断・実施しません。

---

## 関連ドキュメント

- [`docs/PHASE_1_BASELINE.md`](./PHASE_1_BASELINE.md) — Phase 1 完了状態の固定記録
- [`docs/API_ACTIVATION_RUNBOOK.md`](./API_ACTIVATION_RUNBOOK.md) — API 有効化手順書（Phase 3 で実施）
- [`docs/AUDIT_CHARTER.md`](./AUDIT_CHARTER.md) — GPT Audit Gate 憲章（Phase 2 transition rule を含む）
- [`data/genome.json`](../data/genome.json) — ゲノム設定（`live_model_enabled=false` を維持）
- [`data/evolution_history.json`](../data/evolution_history.json) — 進化履歴

---

*このドキュメントは Project Cyber-Immunizer の Phase 2 計画を記録します。*  
*作成日: 2026-05-26*
