# マーケットレポート配信システム 仕様書
2026-10-13 / PRレビュー用。3文書は独立。GitHub mainの静的確認・本番稼働・未マージPRは区別する。
実装で確認した契約：config/report_schedule.jsonのmainはweekday=08/12/16/21、saturday=なし、sunday=なし（PR #99 mainマージ後）。実ChatGPTタスクも土曜なし。apps-script/MarketReportWebSync.gsは本文PUBLISHED/図解NOT_READYを許容し、図解READY時のmanifest・Drive PNG bytes hashを検査。scripts/verify_morning_report_qa.pyは08:00の28行データQA。scripts/validate_drive_publication_receipt.pyはdate/time/title、publisher=chatgpt、status=saved、driveFileId/URL、savedAtを検査。
図解manifestはreport_id、revision、snapshot_id、body_hash、manifest_id、drive_file_id、png_filename、png_sha256、manifest_hash、numeric_validation、renderer_status等を照合する。DEBUG_PREVIEWを正式画像として公開しない。
.github/workflows/build-reports.ymlは発行データ整合の検証。deploy-pages.ymlは公開前DOM、Pages deploy、公開後index/PNG/live DOM照合。PR #98で追加したReceipt validatorの公開ワークフロー直接呼出しは、実Receiptの旧型スキーマと不一致のため撤回済み。現時点で新ゲートは有効化されていない。
受入：既存のreceiptの実在とCIを確認する。mainにないPR #94/97の機能を現行機能として書かない。旧文書の一律PNG公開前必須ゲートとの不一致を残課題として明記する。

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

## 2026-10-15 ADD — TIMELINE_CHECK

時系列は08:00/12:00/16:00/21:00で同じ内容契約を使い、時間帯名は発行枠ごとに変える。時系列欄に次の列を持つ。

`時間帯 | JST時間範囲/観測制約 | 出来事・確認可能な市場状態 | 市場・業種・銘柄の反応 | 相場上の意味・主導要因 | 時刻・出典・観測制約 | 次の時間帯への引き継ぎ`

各発行枠の必須時間帯:
- 08:00: 開場前、寄り付き、序盤、中盤、終盤、東京への引き継ぎ。
- 12:00: 寄り付き前、寄り付き、前場序盤、前場中盤、前引け。
- 16:00: 寄り付き前、寄り付き、前場序盤、前場中盤、前引け、後場序盤、後場中盤、大引け、欧州への引き継ぎ。
- 21:00: 欧州開場前、欧州寄り付き、欧州序盤、欧州中盤、NY開場前。

出来事がない区間では、価格・業種・需給から観測できる状態、または観測制約を書く。原因を推測して補わない。出来事/反応欄に時刻がある場合は根拠欄で発生・発表・報道・市場観測の区別を記録する。21:00より後の時刻を発生済みとして記載せず、予定・未発表の材料と結果を分ける。

Python report validatorは最新/期限対象を厳格検査し、過去分は警告として扱う。Apps Script公開前検査は現行の日付適用基準に従って不合格にする。単なる時刻・価格行、必須区分欠落、意味・反応・根拠・引き継ぎ欄の欠落をTIMELINE_CHECKで拒否する。この検査は形式・手掛かりを機械判定するもので、情報源の真偽や因果の正しさを自動証明しない。

本文/図解の独立公開、既存図解の構成・レイアウト、公開Receipt/Manifestゲートの条件は変更しない。

## PR #133 のHosted検証記録

2026-10-15 head `994642c43af8aa42b5d1bb1650944595cb3abacd`: Apps Script Pre-Publish、見出し互換、朝の実ソース価格検査はPASS。Market Report Validation / Structure Market Reports / Source-backed 21hの最終全体検証は、最新`reports[0]`が時系列表未搭載のためFAIL。同期回復の回帰検査はPASSしたが、その後の公開整合検査が既存のdashboard/latest-report不一致でFAIL。PR #133はDraft維持。現在の市場データを推測で補わず、producer対応後に再実行する。


## 2026-10-15 PR #133 継続対応 — ダッシュボード最新レポート同一性
- `scripts/build_market_json.py` の `attach_market_data` は独立市場データをトップレベルの `marketData`／`marketDataUpdatedAt` にのみ更新する。旧コードが `dashboard.latestReport.marketData` や `dashboard.reports[*].marketData` に加えた複製を除去する。
- `verify_publication_consistency.py` の完全一致チェックは維持する。`tests/test_market_report_sync_contract.py` で本文正本の不変、トップレベルの保存、旧二重格納削除、元入力不変および繰返し実行の冪等を試験する。
- `data/dashboard.json` のDraft版では重複fieldだけを除去し、市場スナップショットと本文を保持した。run 38714305014 同期回復CI PASS。時系列の不足による独立のレポート検査FAILをPASSとは扱わない。
