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
- `data/events/completed-records.json`: 終了した重要イベントの結果・市場反応記録表
- `data/events/history/YYYY-MM-DD.json`: 日付別履歴
- `data/events.json`: 既存画面との互換用
- `economic-calendar.json`: 既存ダッシュボードとの互換用

## 失敗時

取得元に接続できない場合は空データで上書きせず、直前の正常データを `isStale: true` として維持します。実績値の照合だけに失敗した場合も、予定データと以前保存した結果は残ります。

## 終了イベント記録

`events.html` の「終了した重要イベント｜結果・市場反応」は、`scripts/build_completed_event_records.py` が `completed.json` から生成します。

- 対象: 発表済み、重要度2以上、実績を確認できたイベント
- 並び順: 発表日時の新しい順
- 期間切替: 今日、過去7日、過去30日
- 予想差: 結果と予想の単位が一致する場合だけ算出
- 市場反応: `marketReactionRecord` に確認済み記録がある場合だけ表示
- 未確認反応: `反応確認困難`

結果と予想の単位・尺度が一致しない場合は `取得不能` とし、推測値や0で補完しません。発表前後の分足価格表は生成・表示しません。

## 定時更新

GitHub Actionsの `update-economic-calendar.yml` が5分ごとに更新します。重要指標の発表後は、次回実行で実績値と終了イベント記録を更新します。必要に応じてActions画面から手動実行できます。

## 関連文書

- [運用マニュアル](operation-manual.md)
- [現行仕様書](system-specification.md)
