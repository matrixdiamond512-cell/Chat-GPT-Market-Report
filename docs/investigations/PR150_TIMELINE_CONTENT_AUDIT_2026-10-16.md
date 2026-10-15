# PR #150 時系列内容監査｜2026-10-16

## 判定

10/15の4レポートはすべて後日改訂追補として扱う。時系列データは保存本文の SHA-256 に結び付け、追補データは本文ハッシュの完全一致時だけ生成する。既存の発行状態、snapshot、receipt、公開資格は変更していない。

**内容品質の受入判定：4枠すべて INCOMPLETE。** 自動フィールド検査が個々のイベントを完全と判定する場合があっても、発行時のsnapshot/receipt、観測値の独立照合、因果の裏付けが不足しているため、枠全体の品質合格とはしない。

## 枠ごとの確認

| 枠 | 時系列に含む確認済み事項 | 残る欠損・制約 |
| --- | --- | --- |
| 08:00 | BLSの9月CPI公表値、米株引けの指数騰落、06:00大阪先物値を本文に紐付けた。 | 寄付き・序盤・中盤の個別反応に価格と観測時刻が不足。10年債5.33%等の正確な観測時刻なし。発行時snapshot/receipt・Drive発行版revisionなし。 |
| 12:00 | 08:45先物、09:00寄り付き、09:13–09:15、10:27頃、11:30–11:36の反応を時刻付きで構造化。指数・TOPIX・騰落数を市場反応欄に分離。 | 10:27の2,700円超安は正確な当該時刻値が本文にない。日銀発言と為替の因果は確認できず、発行時revision/snapshot/receiptも不足。 |
| 16:00 | 前場の数値を分離。韓国KOSPI売買停止を後日報道で12:38 KSTと照合。日経平均15:30終値を日経公式日次値で確認。TSMC決算は公式発表へのリンクを追加。 | 12:30の独立約定値なし。韓国株安から日本株への個別因果は未確認。TSMC決算公表と会見開始の前後関係、為替・金利の同時刻反応が不足。snapshot欠落状態は維持。 |
| 21:00 | Reutersの欧州07:09 GMT（16:09 JST）観測を明示。20:06先物、20:11金/WTI、20:21為替/BTCを別々の観測時刻として整理。 | 欧州序盤・中盤の継続観測が少ない。20:06–20:21値は原本単独記録で独立系統の再照合なし。原本と異なる回復本文は引き続き拒否される。 |

## 本文・図解・公開ゲート

- Google Docsから取得した現行本文の文字列ハッシュは、4枠ともローカル `reports/2026-10-15_*.json` の `bodyHash` と一致。これは現行Docs本文との一致であり、10/15発行時点の版・snapshot・receiptの証明ではない。
- 4件の `infographic_status` は `NOT_VERIFIED`。ローカルに10/15の図解画像/SVG等がなく、Drive画像検索でも該当画像を確認できなかったため、本文と画像の数値照合は **NOT_RUN**。
- 10/15 16:00 は `BLOCKED_SNAPSHOT_MISSING`、他の3枠は `SOURCE_ARCHIVED`。既存の公開資格・証跡ゲートを変更せず、いずれも公開可能データに昇格していない。
- canonical latest は引き続き10/13 16:00。古い状態の警告を維持し、10/15データを最新レポートに差し替えていない。

## 検証記録

| 検証 | 結果 | 範囲 |
| --- | --- | --- |
| Python timeline ingestion | PASS 5/5 | 4枠の抽出、後日追補ラベル、未知時刻非補作、品質欠損表示 |
| Node timeline archive | PASS 17/17 | 各枠フェーズ、本文ハッシュ束縛、公開不適格状態、レスポンシブ契約、アーカイブ再生成 |
| publication consistency | PASS | canonical `2026-10-13 16:00` と dashboard一致 |
| Python timeline ingestion | PASS 5/5 | 事後追補の本文ハッシュ束縛、未確認時刻の非補作、品質欠損表示 |
| Node publication policy | PASS | 8 eligibility states、blocked/archive・legacy/projection保護 |
| Node構文検査 | PASS | `market-timeline.js`、`build_market_timeline_archive.js` |
| GitHub Actions（current PR head） | PASS 7/7 | timeline contract、publication eligibility、Apps Script prepublish、delivery health、dashboard health、Drive recovery、Saved Docs dispatch contract |
| ローカルブラウザー操作 | PASS（E3、localhost preview） | 10/15の08/12/16/21を切替。追補スロット選択も同期。21:00の本文不一致拒否と追補閲覧、10/14・10/13過去日選択、10/13に時系列なし状態を確認 |
| スマートフォン相当幅 | PASS（先行確認） | 390x844で横はみ出しなし。今回CSS変更なし。localhost previewのみ |
| 実図解数値照合 | NOT_RUN | 図解ファイルがない |
| Pages本番実描画 | NOT_RUN | 本変更の本番公開は未実施 |

GitHub Actions run IDs（commit `82efbac7ce0b0b8fec1983ef68d18e8b4e96af12`）：`38803653277` Apps Script Pre-Publish Validation、`38803653299` Saved Docs Pages dispatch contract、`38803653300` Market timeline contract and dashboard checks、`38803653308` Report dashboard publication health regression、`38803653324` Dashboard report publication eligibility、`38803653356` Market report synchronization recovery CI、`38803653441` Delivery health regression CI。全runがcompleted/success。

この監査はコード・保存ファイル・ブラウザで観察できた範囲の記録であり、マーケットデータ全件の独立監査や本番配信成功を証明しない。
