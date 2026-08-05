# WEBマーケットレポート 市場データ取得基盤 現状調査メモ

作成日: 2026-08-05

## 現状

- ダッシュボード画面は `data/dashboard.json` を読み、`assets/js/top-dashboard.js` が6市場カードと市場温度カードを描画している。
- `data/dashboard.json` は主に `reports.json` とGoogle Sheetsの終値一覧から作られている。
- そのため、マーケットレポート本文や終値一覧に値がない項目は、画面でも「取得不能」になりやすい。
- 既存の `data/market-temperature.json` と `data/rates-bonds.json` はページ構造用の初期JSONであり、実データ連携済みではない。
- 既存の `data/usdjpy-volume.json` は日銀外国為替市況とUSD/JPY日足OHLCを持っており、今回の市場カード基盤とは別の専門ページデータとして扱う。

## 今回追加する層

- `data/market/latest.json`: 直近の市場データ取得結果。
- `data/market/last_verified.json`: 前回正常値。取得失敗時に「取得不能」で上書きしないために使う。
- `data/market/history/*.json`: 実行ごとの履歴。
- `config/market_data_sources.json`: 取得先、予備取得先、市場区分、出所URL。
- `config/market_data_validation.json`: 単位、範囲、鮮度、前回比しきい値。

## 表示の優先順位

1. `marketData.markets[*].verificationStatus === "verified"` の値。
2. `verificationStatus === "fallback"` の前回確認値。
3. 既存のレポート本文・終値一覧由来の表示。
4. 理由つきの取得不能表示。

## 注意

- OSE日経225先物が取れない場合、CMEやCFDを「大阪取引所」として表示しない。
- 金はCOMEX先物とXAU/USDスポットを区別する。
- VIX、日経VI、Fear & Greedは日次または遅延値として扱い、リアルタイム値のように表示しない。
