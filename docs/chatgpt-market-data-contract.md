# ChatGPT向け検証済み市場データ連携

## 目的

ChatGPTがマーケットレポートを作るときに、本文や古い終値一覧から価格を推測せず、取得元・対象時刻・検証状態を確認できる市場データだけを使うための連携仕様です。

## 正本

- 独立取得中の市場データ: `data/market/latest.json`
- 発行済みレポート時点のChatGPT入力: `data/market/chatgpt-input.json`
- Google Sheets用CSV: `data/market/chatgpt_input.csv`
- ChatGPTが読むGoogle Sheets: `ChatGPT_Market_Input`
- 検証済み履歴: `Market_Data_Verified`
- 利用ルール: `ChatGPT_Market_Rules`

## 08:00レポートの固定契約

08:00レポートは `data/latest-report.json` の `marketDataTable` を正本とし、必ず **28項目・5列** の構造化表を保持します。

発行時に `scripts/build_chatgpt_report_input.py` が、その28項目を `data/market/chatgpt-input.json` と `data/market/chatgpt_input.csv` に変換します。既存Apps Scriptとの互換性のため、発行時点では `data/market/latest.json` にも同じ28項目スナップショットを公開します。次の定時取得枠が始まると、`latest.json` はその時間帯の独立取得データに更新されます。

08:00の28項目は、NYダウ、NASDAQ総合、S&P500、Russell 2000、日経225現物、CME日経225先物（円建て・ドル建て）、日経225先物（大阪取引所）、USD/JPY、EUR/USD、COMEX金先物、WTI原油、BTCUSD、VIX、日経VI、Fear & Greed Index、米10年債利回り、日本10年国債利回り、日経225予想PER・PBR・EPS、25日・200日移動平均乖離率、東証プライム売買代金・売買高・値上がり銘柄数・値下がり銘柄数・25日騰落レシオです。

Crypto Fear & Greed はこの08:00固定28項目には含めません。

## 欠損値の扱い

28行という表構造が揃っていても、数値取得が完了しているとは限りません。

- 数値を確認できた行: `verificationStatus=verified` / `利用判定=使用可`
- 確認できない行: `verificationStatus=unavailable` / `利用判定=使用不可`
- 確認できない行は必ず `取得不能（理由）` を保持する
- レポート発行後に取得できた別時刻の値を、08:00時点の値として遡及上書きしない
- `data/market/morning_report_qa.json` の `structureReady` と `dataComplete` を別々に確認する

これにより、「28行揃った」ことと「28項目すべての数値が取れた」ことを混同しません。

## ChatGPTの利用規則

1. `利用判定=使用可` の値を確認済み値として使います。
2. `前回確認値（要注記）` は、現在値として断定せず、最終確認時刻を併記します。
3. `使用不可` は推測で埋めません。
4. `市場区分` と `セッション` を維持します。COMEX金先物をXAU/USD、CMEやCFDを大阪取引所先物として扱いません。
5. `対象時刻` が異なる値を、同じ基準時点の値として比較しません。
6. 価格変化だけを根拠に、日銀会合、介入、要人発言、ニュースを推測しません。イベントは別の確認済み情報源で照合します。
7. 08:00では `morning_report_qa.json` の `actualRowCount=28`、`chatgptInputMarketCount=28`、`structureReady=true` を確認します。
8. `dataComplete=false` の場合は `unavailableLabels` を確認し、取得不能項目を隠しません。

## Google Sheets同期

GitHub Actions のサービスアカウント同期には `MARKET_DATA_SPREADSHEET_ID` と `GOOGLE_SERVICE_ACCOUNT_JSON` を利用できます。Secrets未設定時でもGitHub側のJSON/CSV生成とWEB表示は継続します。

Google Sheets側は `data/market/chatgpt_input.csv` を `IMPORTDATA` で参照できるため、サービスアカウントがなくても28項目契約を維持できます。`ChatGPT_Market_Input` はこのCSVを参照し、GitHubの発行済み入力とGoogle Sheetsが別内容にならないようにします。

## 公開前QA

`Sync latest market report publication` は08:00発行時に、本文のSOP、28行の `marketDataTable`、5列契約、`chatgpt-input.json` の28市場、`chatgpt_input.csv` のヘッダー+28行を検証し、`morning_report_qa.json` に構造完成度とデータ完成度を記録します。

構造不良とデータ欠損は別の障害として記録し、短い本文・10行入力・別時刻の後追い値で正常扱いにしません。
