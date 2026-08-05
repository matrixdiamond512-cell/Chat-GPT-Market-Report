# ChatGPT向け検証済み市場データ連携

## 目的

ChatGPTがマーケットレポートを作るときに、本文や古い終値一覧から価格を推測せず、取得元と時刻を確認済みの市場データだけを使うための連携仕様です。

## 正本

- WEB側の正本: `data/market/latest.json`
- ChatGPTが読むGoogle Sheets: `ChatGPT_Market_Input`
- 履歴: `Market_Data_Verified`
- 利用ルール: `ChatGPT_Market_Rules`

`ChatGPT_Market_Input` は毎回最新スナップショットへ置き換えます。`Market_Data_Verified` は同じスナップショットIDを重複保存せず、時系列で残します。

## ChatGPTの利用規則

1. `利用判定=使用可` の値を確認済み最新値として使います。
2. `前回確認値（要注記）` は、現在値として断定せず、最終確認時刻を併記します。
3. `使用不可` は推測で埋めません。
4. `市場区分` と `セッション` を維持します。COMEX金先物をXAU/USD、CMEやCFDを大阪取引所先物として扱いません。
5. `対象時刻` が異なる値を、同じ基準時点の値として比較しません。
6. 価格変化だけを根拠に、日銀会合、介入、要人発言、ニュースを推測しません。イベントは別の確認済み情報源で照合します。

## 自動更新

GitHub Actions の `update-market-data.yml` が市場データを取得・検証した後、以下のSecretsが設定されていればGoogle Sheetsへ保存します。

- `MARKET_DATA_SPREADSHEET_ID`: 保存先スプレッドシートID
- `GOOGLE_SERVICE_ACCOUNT_JSON`: 編集権限を付けたサービスアカウントのJSON

サービスアカウントのメールアドレスには、対象スプレッドシートの編集権限が必要です。Secrets未設定時もWEB用JSONの更新は継続し、シート保存だけをスキップします。

認証情報がない場合も、同じActionsが次のCSVを生成します。

- `data/market/chatgpt_input.csv`: 最新の10項目（暗号資産のFear & Greedを含む）
- `data/market/verified_history.csv`: 検証済み履歴

Google Sheetsの2シートはこのCSVを `IMPORTDATA` で読み込めます。サービスアカウント方式は即時同期、CSV方式は認証不要の予備経路です。

Apps Scriptから手動で同期する場合は `VerifiedMarketDataSheetSync.gs` を同じプロジェクトへ追加し、`syncVerifiedMarketDataToChatGptSheets` を実行します。
