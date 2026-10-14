# 承認16パネル図解 — DRAFTレビュー

正式版ではありません。08:00・12:00・21:00の入力はmainから撤回された履歴です。16:00は現行mainにも存在しますが、図解用の型付きsnapshot等が不足しています。全PNGに未検証・公開不可を表示しています。

デザイン正本は添付ZIPとバイト一致する `approved-reference.png`（SHA-256 `7a0df07274b2321f1772974abab036aed9b2298103e7f6399fb395c93c922fc5`）。画像内の価格は採用していません。文字を含まないヘッダー装飾のみ再利用し、全パネルの本文と表はHTMLで描画します。

| 時刻 | 最新レビューPNG | 768px専用PNG | 入力状態 | 正式生成 |
|---|---|---|---|---|
| 08:00 | [PNG](review-20261014-withdrawal-aware/2026-10-13_08-00/png/preview-2026-10-13_08-00.png) | [mobile](review-20261014-withdrawal-aware/2026-10-13_08-00/png/preview-2026-10-13_08-00-mobile.png) | 撤回済み履歴 | BLOCKED |
| 12:00 | [PNG](review-20261014-withdrawal-aware/2026-10-13_12-00/png/preview-2026-10-13_12-00.png) | [mobile](review-20261014-withdrawal-aware/2026-10-13_12-00/png/preview-2026-10-13_12-00-mobile.png) | 撤回済み・再構成履歴 | BLOCKED |
| 16:00 | [PNG](review-20261014-withdrawal-aware/2026-10-13_16-00/png/preview-2026-10-13_16-00.png) | [mobile](review-20261014-withdrawal-aware/2026-10-13_16-00/png/preview-2026-10-13_16-00-mobile.png) | 現行GitHub本文 | BLOCKED |
| 21:00 | [PNG](review-20261014-withdrawal-aware/2026-10-13_21-00/png/preview-2026-10-13_21-00.png) | [mobile](review-20261014-withdrawal-aware/2026-10-13_21-00/png/preview-2026-10-13_21-00-mobile.png) | 撤回済み履歴 | BLOCKED |

[正本との比較画像](review-20261014-withdrawal-aware/reference-comparison.png)。各時刻のフォルダーに、原文コピー、Gitコミット照合、観測hash、本文位置付き数値レジストリ、イベント、16パネル投影、既存ゲートの停止理由、HTML、描画契約、PNG・実Edge検査receiptを保存。

## 実行方法

Python 3.12、Pillow、tzdata、Node、`tools/morning-renderer/package.json`のPlaywrightを使用する。既存のrendererを再利用し、通信リクエストは遮断する。Linux CIにはNoto CJKフォントを導入する。Windowsでは既存Edgeの実行ファイルを `--browser` で指定できる。

```bash
python scripts/market_report.py render-infographic \
  --report docs/examples/approved-infographic/review-20261014-withdrawal-aware/2026-10-13_08-00/source-report.json \
  --source-path reports/2026-10-13_08-00.json \
  --source-ref a47ca3e9c2010d4c5d1eaaa4510bdb2961b2645a \
  --reference docs/examples/approved-infographic/approved-reference.png \
  --events templates/infographic/approved/events-2026-10-13.json \
  --draft --output validation/my-new-review
```

出力は新しいフォルダーに限定し、既存フォルダーや公開データ領域への書き込みを拒否する。`--draft`なしでは正式生成を停止する。このコマンドはpublication manifestを作らず、本文のrevision/bodyHash/snapshot_idを書き換えず、既存公開処理を呼ばない。

## デザイン・内容の受入未完了

正本と同じ5行のパネル順、色帯、役割、15番イベント表、13番6市場横一列を保持。幅比・位置は `templates/infographic/approved/layout.json`、主配色は同フォルダーのCSSで編集できる。05の見出しは時刻に応じてNY・東京前場・東京・欧州/NY開場前へ適応する。

全文保持により正本の1536×1024から縦に拡張している。フォント、写真調アイコン、原本4焦点/3条件の明確な構造、表の密度、フロー矢印の細部は一致未完了。原本に存在しない条件や時刻を画像から作っていない。空欄は取得不能/未確定として表示。作成者の目視では文字切れなしを確認したが、デザイン再現の受入はPENDING。PNG生成成功を完成判定にしない。

数値レジストリの `SOURCE_TEXT_ONLY` は転記証拠。raw_value・符号・本文位置は照合するが、独立した商品ID・限月・比較基準・出典との検証済み対応を作ったという意味ではない。不足する属性はnullと理由を保持する。正式snapshot等が復旧した後に既存spec/manifestゲートへ正式投影を接続する工程が残る。

イベントは原本に存在する予定のみを抽出。CPI/PPIは[BLS](https://www.bls.gov/schedule/2026/10_sched.htm)、小売売上高は[Census日程](https://www.census.gov/retail/release_schedule.html)および[公式リリース](https://www.census.gov/retail/marts/www/marts_current.pdf)を生成時に追補確認し、当該日のAmerica/New_YorkからJSTへ変換。10/14・10/15の08:30 EDTは21:30 JST。銀行決算は時刻未確定。重要度・影響市場は原本未指定を保ち、予定と実績を混在させない。
