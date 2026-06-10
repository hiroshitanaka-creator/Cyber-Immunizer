# タスク完了報告 — PR #87（番号は次PRの想定。実際の番号が異なる場合はリネームすること）

## 概要

GPT監査が「diffしか見ていない」と判明した問題への対策として、**Audit Evidence Ledger（監査証拠台帳）** を導入した。
監査者は「diffだけでは物理的に書けない成果物」（diffレビュー前の現状仕様の逐語引用＋関数名＋行番号、参照元一覧、否定証拠、読了マニフェスト）の添付を義務付けられ、受信側（Claude）が新設バリデータ `scripts/validate_audit_evidence.py` で機械検証する。引用・件数が実リポジトリと1件でも不一致なら監査全体を無効とする fail-closed 設計。

## 変更ファイル一覧

- 追加: `scripts/validate_audit_evidence.py` — 証拠台帳の機械検証バリデータ（標準ライブラリのみ）
- 追加: `tests/test_validate_audit_evidence.py` — バリデータのテスト42件
- 変更: `docs/audit_gate/PR_AUDIT_PROTOCOL.md` — 「Audit Evidence Ledger」セクション新設、APPROVE条件2項目追加、Output structure に台帳セクション追加、AI_DOC_META 付与
- 変更: `CLAUDE.md` — 監査受信ゲートを10項目→12項目に拡張（#11 証拠台帳の存在、#12 受信側によるバリデータ実行）、差し戻し分類 `DIFF_ONLY_AUDIT` / `AUDIT_EVIDENCE_MISMATCH` を追加
- 変更: `docs/audit_gate/CHANGELOG.md` — 教訓エントリ追加、AI_DOC_META 付与
- 変更: `README.md` — scripts/ ファイルツリーに新バリデータを追記（生成ブロック `CYBER_IMMUNIZER_STATUS_START/END` の外側のみ。`scripts/update_readme.py` の変更は不要）

## 主な変更内容

- **Pre-diff spec recitation（Rule 1）**: diffをレビューする**前に**、変更ファイルごとに diff に含まれないコア処理を関数名＋行番号付きで逐語引用し、現状仕様を自分の言葉で説明することを義務化。引用範囲が diff ハンクと重なると不合格。新規追加ファイルは免除（全体がdiffのため）、docs ファイルは見出し引用で代替可。
- **Call-site evidence（Rule 2）**: 変更シンボルごとに参照元を `path:lineno:content` 形式で全件列挙＋`COUNT` 明記。バリデータが再カウントし、不足・古い値は不合格。
- **Negative evidence（Rule 3）**: 「探して見つからなかったもの」を最低2件、リテラル `PATTERN`＋`COUNT`＋`NOTE` で記載。バリデータが再検索して照合。
- **Read manifest（Rule 4）**: 全文読了 `FULL:` / diffのみ `DIFF_ONLY:（理由必須）` を全変更ファイルについて列挙。
- **機械検証**: `python scripts/validate_audit_evidence.py --report <レポート> --base-ref origin/main` で、逐語引用の一致・件数の再計算・recitation の diff 外判定・変更ファイルの網羅を検証。exit 1 で監査却下。
- **失敗分類**: 台帳なし → `DIFF_ONLY_AUDIT`、引用・件数の不一致 → `AUDIT_EVIDENCE_MISMATCH`（1件で監査全体無効）。いずれも CHANGELOG 記録、再発時は `PULLBACK_PROMPT.md` 適用。
- **受信側強制**: CLAUDE.md 監査受信ゲート #12 により、バリデータ実行は監査者の自己申告ではなく受信側 Claude が必ず実施する（Prompt Reception Gate と同じ「自己申告を信じない」構造）。

## 後検証結果

- `python -m pytest tests/ -x -q` → **1962 passed**（新規42件を含む、既存テストの回帰なし）
- Dogfood（実リポジトリで実証）:
  - 正規の証拠台帳レポート → `VALID: audit evidence ledger verified (4 block(s))` / exit 0
  - 引用を1箇所改竄したレポート → `INVALID: quote does not match scripts/validate_mutation.py:53` / exit 1
- `git grep -n "validate_audit_evidence" README.md CLAUDE.md docs/audit_gate/` → README ツリー・受信ゲート#12・PR_AUDIT_PROTOCOL・CHANGELOG の全てに参照が存在
- README の変更は生成マーカー `<!-- CYBER_IMMUNIZER_STATUS_START -->` の外側のみであることを確認（generator 更新不要）

## 残存事項・注意点

- **検索はリテラル部分一致（正規表現なし）**: 決定論的に再現できるようあえて regex を不採用。汎用的すぎるシンボル名（例: `data`）は件数が膨れるため、監査者は `SCOPE:`（パスプレフィックス）で絞るか、より特定的な文字列を選ぶ必要がある。
- **CI ワークフローへのバリデータ組み込みは未実施**: `.github/**` は FROZEN のため触れていない。監査レポートを CI で自動検証したい場合は別タスクとして Project Owner の承認が必要。
- **GPT 側プロトコル（TASK_PROMPT_PROTOCOL.md / AUDIT_CHARTER.md）は未変更**: 今回は受信側ゲートと監査レポート要件のみ。GPT に台帳フォーマットを事前周知するプロンプト整備は次タスク候補。
- 本報告のファイル名は次 PR を #87 と想定したもの（#86 は Codex の task-prompt-protocol 強化 PR として使用済み）。実際の PR 番号が異なる場合はリネームが必要。
