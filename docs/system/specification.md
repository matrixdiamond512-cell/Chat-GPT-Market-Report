# マーケットレポート配信システム 仕様書

## 2026-10-17 本文の同一画面表示（PR #97 Draft）
- 本文rendererは `index.html` のDOM内で動作し、市場サマリー直後の本文領域に全文を直接描画する。iframeや別の本文ページは作らない。日付・時刻選択はダッシュボードの一組を共用する。
- ダッシュボードが選択した同一report objectを描画し、公開または明示的な履歴archiveの適格性を再確認する。対象が不明または不適格なら本文表示を停止する。
- `report.html` は既存ブックマーク向けの互換入口とし、日時を保持して `index.html#report-detail` へ移動する。本文表示は移動先の同じDOMで行う。
- 既存のmanifest/hash/snapshot/数値検証および公開停止ゲートは維持する。ブラウザー実描画の受入はCI結果を確認するまでPENDINGとする。

2026-10-13 / PRレビュー用。3文書は独立。GitHub mainの静的確認・本番稼働・未マージPRは区別する。
実装で確認した契約：config/report_schedule.jsonのmainはweekday=08/12/16/21、saturday=なし、sunday=なし（PR #99 mainマージ後）。実ChatGPTタスクも土曜なし。apps-script/MarketReportWebSync.gsは本文PUBLISHED/図解NOT_READYを許容し、図解READY時のmanifest・Drive PNG bytes hashを検査。scripts/verify_morning_report_qa.pyは08:00の28行データQA。scripts/validate_drive_publication_receipt.pyはdate/time/title、publisher=chatgpt、status=saved、driveFileId/URL、savedAtを検査。
図解manifestはreport_id、revision、snapshot_id、body_hash、manifest_id、drive_file_id、png_filename、png_sha256、manifest_hash、numeric_validation、renderer_status等を照合する。DEBUG_PREVIEWを正式画像として公開しない。
.github/workflows/build-reports.ymlは発行データ整合の検証。deploy-pages.ymlは公開前DOM、Pages deploy、公開後index/PNG/live DOM照合。PR #98で追加したReceipt validatorの公開ワークフロー直接呼出しは、実Receiptの旧型スキーマと不一致のため撤回済み。現時点で新ゲートは有効化されていない。
受入：既存のreceiptの実在とCIを確認する。mainにないPR #94/97の機能を現行機能として書かない。旧文書の一律PNG公開前必須ゲートとの不一致を残課題として明記する。

## 2026-10-16 公開連携復旧追補（PR提出前）
- Drive取り込みはsource archiveとpublishable reportを区別し、`DOC_READBACK_PASS`はslot evidence、Docsの保存・更新時刻、Docs revision ID、完全一致本文SHA-256、snapshot/context identity/hashが一致した場合だけ付与する。
- receipt v2はDrive原本ID/URL、readback結果、revision、本文hash、evidence/snapshot/context hashと保存時刻を結合する。既存のレポート本文・検証ゲートは書き換えない。
- 2026-10-16以降の新規`DOC_READBACK_PASS`はv2 receipt必須。旧履歴は移行epoch以前の内容を変更せず grandfather する。
- importerは正本保存後、既存latest選択器、canonical-only index再構築、publication consistency verifierを実行する。PASSしたデータ差分がある場合だけPages deployを要求する。
- 本追補は未マージPRの実装仕様であり、Actions/Pagesの本番成功を意味しない。

## 2026-10-17 PR #97 08:00 図解接続（Draft仕様）
- `capture_morning_creation_evidence.py` がG0/G1/G2を通過した保存前本文を固定し、全文UTF-8 SHA-256、日時、report_id/revision、snapshot_id、context/snapshotとUTC `capturedAt` を記録する。成果物はDocs writerへ本文を渡す前に排他的に保存する。capture timestampは保存順の追加検査であり、単独で署名済み証明を意味しない。
- Docs保存後は既存Drive importerがDocs API本文を読み戻してcanonical reportを作り、receipt v2が同じdocument revision/bodyHashを示す。staging bridgeは保存前G2 artifact、importer本文、receiptを照合する。読み戻し本文はAPIアクセスしたと誤認させず、importerが観測した本文として記録する。
- `prepare_morning_infographic_inputs.py` は同一report/evidence/receipt/G2本文と、レビュー済みの `summary-authoring.json` / `view-authoring.json` を入力にsummary/view/specを組み立てる。source anchorの重複は明示された0始まりoccurrenceのみで解決し、パネル12三役の人間レビューは常に別のPENDING承認記録を要する。CLI manifestの時刻は、入力検証後にG2証跡とDocs receiptから取得する。正常系CLIが4成果物を生成しidentity/hashを一致させる回帰テストと、欠損・改変・時刻逆転で出力前に停止する異常系テストを必須とする。描画・公開・Drive書込みはこの準備コマンドの責務外。
- 全文本文はhash-boundで保存し続けるが、図解には全文章の転載を要求しない。必須source factの網羅、原文位置、snapshot結合、数値・方向・単位・時刻の検証で要約を受け入れる。
- 定時publisherからPR rendererへのhookは未実装。実装にはdefault branch側の段階的なTEST_ONLY workflow接続が必要。現在の制約によりmain、schedule、既存publish workflowは未変更。E2Eは同一runの実データと独立シナリオレビューがそろうまでNOT_RUN。

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

## 2026-10-16 追補（DOCSYNC-20261016-RPT）
- 凍結workflow：.github/workflows/freeze-report-slot-evidence.yml。07:47/53/57、11:47/53/57、15:47/53/57、20:47/53/57 JSTに対象枠の事前証拠を取得・保存。inputのreportSlot、generatedAt、overallStatus、15分以内、future asOf拒否、contextHash/snapshotHash/sourceHash/evidenceId、不変保存を検査。T以後のlive書込みはBLOCKED_LIVE_EVIDENCE_AFTER_SLOT。GitHub cronは定刻保証でない。
- Docs同期：.github/workflows/publish-saved-google-docs-reports.yml とscripts/sync_reports_from_drive.pyは保存済みDocsを読込・検証する。本文やDocsを生成しない。読戻し資料の不足はSOURCE_ARCHIVED/BLOCKEDに保持し、NO_NEW_REPORTSは配信成功と異なる。
- 非正式アーカイブ：data/report-recovery-2026-10.jsonにHISTORICAL_ARCHIVE／DRIVE_DOC_READBACK_NOT_SLOT_VERIFIED／verifiedAtSlot=falseとDoc ID・revision・fullTextを保管。通常のreports.json/latest/dashboard.latestReport、receiptは更新しない。
- 6市場表示：assets/js/top-dashboard.jsとdashboard-market-card-normalizer.js等で補充本文の銘柄別価格と見通しを固有スコープで抽出。COMEX金先物と金スポット、OSE夜間・日中、BTC時刻参考と日足確定を分け、原因・注目点・リスクを別表示。DOM回帰テスト scripts/validate_supplemental_oct16_dashboard.js。
- PR #152/#153/#154はmain反映済み。CI成功は、通常定時4枠の発行、通知、正本receiptのE2E成功を証明しない。旧来のPNG必須ゲートと現行独立状態の差は別途設計整合性確認の対象に留める。

## 2026-10-17 市場サマリーと本文の一画面統合（PR #97 Draft）
- `index.html` をレポート閲覧の単一画面とし、市場サマリー直後に選択中スロットの全文・正式条件を満たした図解を連続表示する。日付・時刻コントロールはダッシュボードの一組だけを使う。
- ダッシュボードが選択したreport objectを同一origin内で本文rendererへ渡す。本文renderer側で公開対象または明示的な履歴archiveかを再確認し、日時・全文・存在するreport_id/revision/bodyHash/snapshot_idの一致を親画面で照合できた場合のみ本文を表示する。不一致時はfail-closedで隠し、理由を表示する。
- `report.html` は既存リンクとの互換入口とし、`embedded=1`以外は同じ日時を保持して `index.html#report-detail` へ移動する。埋込み表示では本文renderer側のheader・navigation・日付/時刻選択を隠し、archive provenanceは表示したままにする。
- 正式図解の既存manifest/hash/slot/readiness条件、公開停止、snapshot・数値検証は変更しない。歴史archiveは正式発行・当時snapshot・公開承認済みと表示しない。
- 回帰はNode identity/mismatchテストと既存report-21-ui-validation Chromium workflowを使う。Chromium UI検査がNOT_RUNの間は実ブラウザー表示をPASSと報告しない。
