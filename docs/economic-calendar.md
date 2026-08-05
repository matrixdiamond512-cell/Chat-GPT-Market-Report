# 重要イベント自動更新

`events.html` とダッシュボードの重要イベント欄は、マーケットレポート本文から抽出した予定ではなく、専用の経済カレンダーJSONを優先して表示します。

## 取得と保存

- 予定日時、通貨、重要度、予想、前回値: Forex Factory weekly calendar
- 実績値: TradingView Economic Calendarで日時・国・指標名を照合
- 主要指標の確認先: BLS、BEA、FRB、日銀、ECB、EIA、米財務省、財務省などの公式日程
- 保存期間: 365日
- 保存対象: 正規化して選別したイベントだけ。取得元の生JSONは保存しない

## 公開ファイル

- `data/events/latest.json`: 履歴を含む正本
- `data/events/upcoming.json`: 今後7日分
- `data/events/completed.json`: 実績値を確認できたイベント
- `data/events/history/YYYY-MM-DD.json`: 日付別履歴
- `data/events.json`: 既存画面との互換用
- `economic-calendar.json`: 既存ダッシュボードとの互換用

## 失敗時

取得元に接続できない場合は空データで上書きせず、直前の正常データを `isStale: true` として維持します。実績値の照合だけに失敗した場合も、予定データと以前保存した結果は残ります。

## 定時更新

GitHub Actionsの `update-economic-calendar.yml` が日本時間の00:30、06:00、12:00、18:00、22:30に更新します。必要に応じてActions画面から手動実行できます。
