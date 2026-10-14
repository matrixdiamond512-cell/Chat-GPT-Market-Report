# マーケットレポート配信システム 要件定義書
2026-10-13 / PRレビュー用。3文書は独立。GitHub mainの静的確認・本番稼働・未マージPRは区別する。
対象：データ取得→検証→本文・図解→ChatGPT表示→Drive保存→GitHub→Portal公開→公開後検証。
REQ-01: 日時、出典、reportId、revision、本文・図解、保存と公開の証跡を追跡する。
REQ-02: ChatGPT実タスクは平日08/12/16/21が有効、土曜08は無効。main configはPR #99マージにより土曜発行なしへ修正済み。
REQ-03: 本文のPUBLISHEDと図解のNOT_READYは同時に存在できる。本文公開と全工程完了を混同しない。
REQ-04: 08:00の28項目5列表の品質検査を要求。実データの全取得成功とは別。
REQ-05: Google Docs保存receiptとinfographicManifestを区別し、公開前後の検証証拠を保全する。
REQ-06: Draft PR #94/97は本番実装済みと認めない。
REQ-07: 要件定義書、仕様書、運用マニュアルを別ファイルとし、書込対象IDの照合を必須にする。
未解決：実行中トリガー、全旧版条項比較、PR本番採用、最新CI・Drive・公開URLの実検証。

## 2026-10-13 実検証で確定した事実
- 実ChatGPTタスクは平日4枠のみ有効。土曜日旧タスクは無効。Apps Script実トリガーは接続元から照会不可。
- PR #95/#96はマージ済み。PR #94/#97/#98はDraft・未マージ。
- PR #94のMOF検証はSTALE_DATA閾値の限定修正後、Actions run 38298392598でSUCCESS。ただしSheets/本番updateはSKIPPED。PR #97はデザインテストPASS、本番公開未確認。
- 2026-10-12 21:00 のDocはGoogle Driveに実在。旧Receiptにはstrict validator必須のtitle/status/publisher/driveFileId/driveUrl/savedAtが欠ける。保存主体や日時を推測補完しない。
- PR #98の公開workflowへの直接Receipt検査追加は撤回。新旧スキーマ移行と実テストまでは本番導入禁止。

## 2026-10-13 最終照合
- PR #99はmainにマージ済み。現行スケジュールは平日08/12/16/21のみ、土日なし。
- PR #94の修正後Actions run 38298392598はSUCCESS。Draft・未マージであり、本番データ書込を検証したものではない。
- この文書に記載するPR #98のReceipt強制ゲートは撤回済み。Docs保存証跡の旧スキーマ移行が未完了のため、公開ゲートの新設を完了とはしない。

## 2026-10-15 生成元証拠v2の要件追補（v1.12 / Draft）

- D1の非公開API-shadow用source証拠は、旧Python v1 snapshot IDを変更せず、別の`report-canonical-json/v2`形式で追加digestを保持すること。旧証拠や既存レポートを自動再署名しない。
- float値はJSON数値としての情報喪失を避けるため、生成元で型付きdecimal_v2文字列へ変換し、Python/GASでcanonical bytesおよびSHA-256一致を確認する。原文・market dataの真正性と署名権限は別途検証する。
- D1成功はE4相当のoff-line契約検証のみ。API費用、非公開永続保存先、issuer鍵、D2実運用は未承認。既存ChatGPTタスクは稼働継続、PR #130 Draft、本番レポート公開はBLOCKEDのまま。
- 変更実装：PR #130の`scripts/reporting/canonical_v2.py`、`apps-script/MarketReportProducerProof.gs`のv2 helper、およびgoldenテスト。変更仕様書のv2追補と対応づける。

## 2026-10-15 D2事前判定要件追補（Draft）
有料API実行の前に、固定モデル版・1slot/1attempt・入力/出力token上限・USD費用上限・private immutable store・readback・データ利用権・実承認の独立証拠が必須。文書内の宣言だけを実承認と見なさず、未確認ならAPI送信／公開とも禁止する。PR #130に`d2_preflight.py`とオフラインテストを追加した。ChatGPT既存タスク稼働・本番公開停止・PR Draft未マージは不変。
