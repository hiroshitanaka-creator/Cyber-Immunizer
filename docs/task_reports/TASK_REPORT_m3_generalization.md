# タスク完了報告 — M3：未知脅威の検知（汎化の測定）

## 概要
ミッションの「不特定の脅威の自動検知」を **測定可能** にした。提案器に**与えていない脅威**
（既知クラスの回避変種＋新クラス）の held-out コーパスを用意し、検出器がどれだけ汎化するかを
誇張せず数値化。現状の静的ルールの正直な到達点と、自律ループが埋めるべきギャップを確定した。
API・live 実行なし。

## 実測（静的 realistic_baseline）
| コーパス | 攻撃検知率 | 誤検知率 |
|---|---:|---:|
| in-distribution（構築対象） | **100%** | 0% |
| held-out（未知） | **11%（1/9）** | **0%** |
| **汎化ギャップ** | **89pt** | — |

→ 手書き静的検出器は「作った対象には強いが、未知にはほぼ効かない（誤検知も出さない）」。これは
README の前提（人手パッチは進化する脅威に追いつけない）を数値で裏付け、**自律自己進化が埋めるべき
ギャップ＝89pt** を明確化したもの。

## 追加物
- `fixtures/generalization_corpus/heldout_threats.json`（12件）：回避変種（double-encode/backslash
  traversal、comment-obfuscated SQLi、spaceless cmd chaining）＋新クラス（SSRF/XXE/SSTI/NoSQL/LDAP）
  ＋held-out benign。すべて中立化された防御検知ターゲット（武器化攻撃ではない）。
- `scripts/generalization_report.py`：in-distribution と held-out を同一ルールで採点し、
  汎化率と gap を出力（`cli.structured_eval` の評価ロジックを再利用・読取専用）。
- `docs/value_validation/GENERALIZATION_REPORT.md`：正直な結果と解釈、改善の見え方。
- `tests/test_generalization.py`（4件）：held-out が未知（variant＋newclass）を網羅、in-dist=100%、
  **held-out 誤検知=0%（未知 benign を過剰ブロックしない品質バー）**、gap が報告されること。

## 安全性
- held-out コーパスは標準的・中立化された防御検知ターゲットのみ。武器化 exploit ではない。
- 測定は読取専用。本番状態（genome）変更なし。

## 後検証
- `python scripts/generalization_report.py --json` → in 1.00 / held-out 0.11 / fp 0.00 / gap 0.89。
- `pytest tests/ -q` → **3027 passed**。`validate_state.py` → PASS。

## Which layer did this task advance?
- [x] Layer 1（未知脅威への汎化を測定可能化。自律ループの改善対象＝メトリクスを確立）
- 補足：Layer 2 価値検証の「現実カバレッジ」を、未知方向へ拡張する測定基盤

## 残存（理念本線）
- ギャップを実際に**詰める**のは自律ループの役割：新脅威が現れたら LLM が検知を提案→評価（held-out 汎化も）
  →昇格→自己修復。これは実点火（paid）と将来の脅威フィード取り込みで進む。
- 真のゼロデイ網羅は研究的難問。報告は「測定された汎化」に限定し、過大主張しない。
