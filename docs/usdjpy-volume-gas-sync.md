# USD/JPY出来高ページ GAS同期メモ

## 目的

Googleスプレッドシートの東京市場USD/JPYスポット出来高データから、Webサイトが読む `data/usdjpy-volume.json` を生成してGitHubへ反映する。

この段階ではGASの本番トリガーは設定しない。まず手動プレビューと手動同期で、出来高ページだけを試験対象にする。

## 対象

- 対象ページ: `usdjpy-volume.html`
- 出力JSON: `data/usdjpy-volume.json`
- GASファイル: `apps-script/UsdJpyVolumeJsonSync.gs`
- GAS補助ファイル: `apps-script/UsdJpyVolumeJsonStatus.gs`
- 使用データ: 日銀PDFのUSD/JPYスポット出来高のみ
- 使用しないデータ: スワップ出来高

## 入力シート

標準シート名は `USDJPY_Volume`。

必須列:

| JSON項目 | 推奨列名 | 内容 |
| --- | --- | --- |
| `targetDate` | 対象日 | 日銀PDFに掲載されたスポット出来高の対象日 |
| `publicationDate` | 公表日 | 日銀PDFの公表日 |
| `spotVolume` | USD/JPYスポット出来高 | 百万ドル単位 |
| `close` | 終値 | Investing.comのUSD/JPY日足終値 |
| `open` | 始値 | Investing.comのUSD/JPY日足始値 |
| `high` | 高値 | Investing.comのUSD/JPY日足高値 |
| `low` | 安値 | Investing.comのUSD/JPY日足安値 |

任意列:

| JSON項目 | 推奨列名 | 補足 |
| --- | --- | --- |
| `sourcePdfName` | 元PDF | 空欄なら公表日から `fxYYMMDD.pdf` を自動作成 |
| `sourcePdfUrl` | 元PDF URL | 空欄なら日銀PDFベースURLとPDF名から自動作成 |
| `volumeChange` | 出来高前営業日比 | 空欄なら前行との差分で自動計算 |
| `volumeChangePct` | 出来高前営業日比率 | 空欄なら前行比で自動計算 |
| `avg20` | 20営業日平均 | 空欄なら対象日を含む直近20行平均で自動計算 |
| `vs20` | 20日平均との差 | 空欄なら `spotVolume - avg20` で自動計算 |
| `vs20Pct` | 20日平均比 | 空欄なら `vs20 / avg20` で自動計算 |
| `priceChangePct` | 価格変化率 | 空欄なら前営業日の終値比で自動計算 |

## Script Properties

必須:

- `GITHUB_TOKEN`: GitHub Contents APIでJSONを更新するためのトークン

任意:

- `USDJPY_VOLUME_PRICE_RANGE_START`: ページに表示する価格データ範囲の開始日
- `USDJPY_VOLUME_PRICE_RANGE_END`: ページに表示する価格データ範囲の終了日
- `USDJPY_VOLUME_PRICE_RANGE_COUNT`: ページに表示する価格データ件数

任意プロパティを設定しない場合、価格範囲は出来高レコードの最古日・最新日・件数から作る。

## 実行関数

- `previewUsdJpyVolumeJson()`: JSONをプレビューする。GitHubは更新しない。
- `syncUsdJpyVolumeJsonToGitHub()`: `data/usdjpy-volume.json` をGitHubへ反映する。
- `showUsdJpyVolumeJsonSyncStatus()`: GitHubトークン、対象シート、価格範囲設定、前回実行結果を確認する。
- `buildUsdJpyVolumeJson_()`: JSON文字列を作る内部関数。

## バリデーション

- スワップ出来高らしい列名がある場合は停止する。
- 対象日より公表日が後でない場合は停止する。
- 対象日が重複している場合は停止する。
- 必須列がない場合は停止する。
- スポット出来高、始値、高値、安値、終値が数値でない場合は停止する。

## 試験手順

1. スプレッドシートに `USDJPY_Volume` シートを用意する。
2. 必須列を入れる。
3. `data/usdjpy-volume-sheet-template.csv` をインポートまたは貼り付けて初期データにする。
4. GASに `UsdJpyVolumeJsonSync.gs` と `UsdJpyVolumeJsonStatus.gs` を追加する。
5. 既存のGitHub連携スクリプト `MarketReportWebSync.gs` と同じプロジェクトに置く。
6. `MarketReportMenu.gs` の最新版も反映する。
7. `installMarketReportWebMenu()` を実行して、メニューを表示する。
8. メニューから `USD/JPY出来高JSON設定を確認` を実行する。
9. `previewUsdJpyVolumeJson()` を実行して、最新対象日・公表日・件数・JSON構造を確認する。
10. 問題なければ `syncUsdJpyVolumeJsonToGitHub()` を手動実行する。
11. 公開ページで `usdjpy-volume.html` を確認する。

## 注意

このスクリプトは既存の `tokyo-usdjpy-volume.json` ではなく、新しい `data/usdjpy-volume.json` を更新する。旧JSONは別ページ・旧仕様用として残し、今回の出来高ページには使わない。
