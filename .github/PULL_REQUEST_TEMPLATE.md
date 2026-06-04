## 変更概要

<!-- 何を変更したか、なぜ変更したかを簡潔に説明してください -->

---

## 監査カテゴリ

該当するカテゴリすべてにチェックしてください（`docs/AUDIT_CHARTER.md` 参照）：

- [ ] **A: アーキテクチャ整合性** — MAPE-K ループ・3ジョブ分離・変異境界マーカー
- [ ] **B: セキュリティ境界** — シークレット管理・AST ポリシー・プリフライトスキャン・replacement_code 検証
- [ ] **C: フィットネス・リグレッション** — フィットネス計算式・リグレッション通過率・candidate_hash
- [ ] **D: コスト・API ガバナンス** — 予算キャップ・ledger・スケジュール実行・リクエスト数制限
- [ ] **E: ドキュメント整合性** — README・AUDIT_CHARTER・PR テンプレート
- [ ] **F: 法的・デュアルユース** — 攻撃コード不在・エクスプロイト不在・ネットワーク接続不在

---

## 安全チェックリスト

マージ前に以下をすべて確認してください：

- [ ] 攻撃コード・スキャナ・資格情報窃取ロジック・マルウェアを含まない
- [ ] 実際のエクスプロイトペイロード・CVE詳細・シェルコードを含まない
- [ ] `GEMINI_API_KEY` は propose ジョブのみに存在する（evaluate / promote には存在しない）
- [ ] 生成コードは evaluate ジョブの subprocess 隔離内でのみ実行される
- [ ] `core/policy.py` の AST 禁止パターンが削除・緩和されていない
- [ ] `_preflight_secret_scan` が削除・バイパスされていない
- [ ] `_validate_replacement_code` が削除・弱化されていない
- [ ] `candidate_hash` による SHA-256 検証が維持されている
- [ ] `api_budget.assert_budget_available` が削除・バイパスされていない
- [ ] スケジュール実行（cron）は `noop` モードのまま変更されていない
- [ ] symbolic indicator（`path_traversal_indicator` 等）に実エクスプロイト文字列が混入していない
- [ ] 新規テストが変更をカバーしており、既存テストが削除・弱化されていない

---

## GPT Audit Gate

> **手順**: このセクションに GPT Audit Gate のレポートを貼り付けてください。  
> フォーマットは `docs/AUDIT_CHARTER.md` の「4. GPT Audit Gate の出力フォーマット」を参照。

```
## GPT Audit Gate レポート

（ここに GPT のレポートを貼り付ける）
```

**GPT Audit Gate 決定**:

- [ ] ✅ APPROVE
- [ ] ⚠️ REQUEST CHANGES（修正後に再レビュー）
- [ ] ❌ BLOCK（Project Owner の明示的承認が必要）

---

## Project Owner 最終判断

> Project Owner（@hiroshitanaka-creator）のみがこのセクションを記入できます。

- [ ] **マージ承認** — すべてのチェックを確認し、GPT Audit Gate の決定を確認した
- [ ] **条件付き承認** — 以下の条件の下でマージを承認する：
- [ ] **マージ拒否** — 理由：

**備考**:

<!-- 必要に応じて Project Owner のコメントを記入 -->
