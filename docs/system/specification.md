# マーケットレポート配信システム 仕様書
現行文書版：2.1｜改訂：2026-10-19 JST｜変更ID：DOCCTRL-20261019-HISTORY。過去に記載した「PRレビュー用」「未実装」「未解決」はその時点の履歴。現在の確定業務契約は本ファイル末尾の「現行差分統合 v2.1」と固定ID Google Docs v2.1を参照。GitHub main静的確認と実稼働成功は別判定。
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

## MRFOLDER-20261019-01｜Google Drive本文・図解保存先契約（2026-10-19 JST）
- slotKey = YYYY-MM-DD_HH-MM（JSTの予定枠）。本文名 = マーケットレポート_YYYY-MM-DD_HH-MM、図解名 = マーケットレポート_YYYY-MM-DD_HH-MM.png。補充版では元枠と実作成/保存時刻を区別する。
- docFolder = マーケットレポートYYYY年M月、imageFolder = マーケットレポート図解YYYY年M月。2026年10月のdocFolderId=1qDOwDACdzWsGYcMaEobciDP3dFOdJ4Vz、imageFolderId=1Ma24qcksen9Ufqz1wIUYqSTdYFfpok2w。月の切替時は一意に検索し、なければ権限を確認した上で作成、重複フォルダーはBLOCKED_FOLDER_AMBIGUOUS。
- 書込み前：対象フォルダーIDと同名ファイルを照合。既存原本IDを保護し、重複候補は「同名ファイル確認待ち」へ退避。新規作成時は親フォルダーを作成リクエストに指定し、後からMy Drive直下に放置しない。
- 書込み後：Drive metadata再取得でid/name/mimeType/parents/webViewLinkを検査し、parentIdsに予定月フォルダーIDがないものはSAVE_MISPLACED。Docsは本文全文/revisionのreadback、PNGは実ファイルのbyte/hashと対象枠の照合を可能な範囲で行う。保存済みの判定はこの検証がPASSした場合のみ。
- 既存scripts/sync_reports_from_drive.pyは保存済みDocsの読込み・発行担当でありDocs/PNGの新規作成機構ではない。タスクプロンプト更新は適用したが、実ライブ発行での作成・フォルダー配置・読戻しはE2E未検証。既存の事前evidence/receipt/公開ゲートは変更しない。


## 現行差分統合 v2.1（2026-10-19、DOCCTRL-20261019-HISTORY）

Google Docs固定ID `1qL7f3yKwghuDb5PiAI3RhwFJUVUfLwGakC8z8EOJ9oI` へ対応するGitHub側の固定仕様。旧v1.6～1.9、旧2.x～3.40と10/19 mainの実装を区別して統合する。

- 事前取得：`.github/workflows/freeze-report-slot-evidence.yml` はT-13/T-7/T-3の試行設定。 `scripts/persist_report_slot_evidence.py` はreport slot、JST generatedAt、15分以内の鮮度、contextHash/snapshotHash/sourceHash/evidenceIdを検査し、発行後の新規凍結は禁止。 `scripts/run_market_data_window.py` は遅延取得をexpiredとして監査し、定時成功に含めない。
- 08:00 QA：`scripts/verify_morning_report_qa.py` のITEMS 28行（CME円/ドル、プライム売買代金/売買高を各々別行）×5列を正本とする。previous_close、比較営業日、重複、欠損理由、前回21時のライブ値混入を検証。理由付き取得不能はdegraded可、行落ち・空白やパーサー異常は拒否。
- 正本同一性：reportId/revision/context/snapshot/本文・bodyHash/原本DocIDを固定し、 `reports/<reportId>.json` と `reports.json`、 `data/latest-report.json`、dashboard.latestReportの候補整合を確認。履歴修復で同一revisionの本文を変更しない。
- Docs/PNG月別保存：対象年月の本文・図解フォルダーを親として直接作成。Google Drive parentIdsとfileId、name、mimeType、URL、Docs全文一致/ revision、PNG実体/manifestを読戻し検証。複数フォルダーは `BLOCKED_FOLDER_AMBIGUOUS`、親違いは `SAVE_MISPLACED`。取り込みスクリプトは原本の新規生成役ではない。
- `SOURCE_ARCHIVED`、`HISTORICAL_ARCHIVE`、`RECONSTRUCTED_UNVERIFIED`、`BLOCKED` とunknown statusは、発行時snapshot/receiptを偽装して正規公開へ昇格させない。10/16・10/19の非正規履歴タブやアーカイブ表示は視認性向上であって当時の正式発行を証明しない。
- 本文個別PUBLISHEDと図解READY/NOT_READYは別状態。ただし全工程VERIFIEDには図解PNG・Drive/readback・ライブ表示を含めた正式な完了証拠が必要。旧一律公開ゲートの適用差は実装読戻しで判定する。
- 12/16/21時は実出来事のJST時刻と同じ時間帯の市場反応、イベント未来時刻（夏冬時間換算）を適切に区別し、公開パーサー/DOM・6市場カードの銘柄別値を検証。
- 終値一覧：`scripts/audit_close_sheet_missing.py` のblank/unavailable/closed/filled区分、`scripts/backfill_verified_close_archives.py` の同日検証済み履歴からの空セルのみ補完、`close-sheet-integrity.yml` の18:25 JST検査。JP33業種とUS11セクターETFは独立の基準日管理。
- 金ETFはGLD/SPDR履歴、IAU履歴、WGC世界月次を対象範囲で区別。BOJ東京USDJPY spot volumeと為替OHLCは別ソース・基準日で表示。出典の異なる値を機械的に合算しない。
- 文書上のD2/Responses API shadow・draft PR・offline contractは本番課金や自動公開の承認ではない。


## DRIVESOURCE-20261020-01｜Drive同名ファイルの最新保存版とGitHub公開正本の分離（2026-10-20 JST）
- ユーザー指定の「同一日時・同一種別はDrive保存日時が遅い方」を、Google Drive createdTime の降順で判定する。modifiedTimeは編集・移動等で変わるため保存日時の代わりにしない。対象は18件のGoogle Docsと3件のPNG、計21対象日時。Drive月別通常フォルダーには各日時1件を残し、古い候補は「同名ファイル確認待ち」に保全した。
- GitHub `data/drive-source-selection.json` がGoogle Drive実測の選定結果を保持する。レポート画面のDrive保存版リンクと `drive-source-selection.html` はこの一覧を参照する。ユーザーに選定版のID・リンク・検証状態を示すが、**これはGitHubの正規発行原本を無条件に書き換える仕様ではない**。
- 最新保存版の本文18件のうち10件は構造・分量を点検可能、8件は空文書または短文。後者を既存の公開済み全文に上書きしない。前者も発行前snapshot、Google Docs revision/全文一致、原本revision、receipt、公開整合の証拠が揃わなければ既存canonicalは変更せず「正式公開保留」とする。後から発行前証拠を捏造しない。
- 図解3件はDrive上の最新保存日時・PNG MIMEを確認。GitHub Pagesでの画像実体、SHA-256、manifest、snapshot/本文との対応が未検証のため図解正式READYへ昇格させない。旧ファイルは削除しない。
- 公開ポータルの参照ページは正式公開と保存版の区別を表示し、公開中の本文全文・最新レポート・dashboard・receipt・公開ゲートを黙って切り替えない。E2E、正式canonical改訂、PNG正式公開の状態は引き続きUNVERIFIED/BLOCKEDと明記する。
- 変更確認対象：本書、上記3システム固定文書、`report.html`、`assets/js/report-drive-source-reference.js`、`drive-source-selection.html`、`data/drive-source-selection.json`。Google Driveの固定ID文書側の同期とライブPages確認は別工程として記録する。


## ISSUE-176-20261026｜08:00 recovery contract（Draft / TEST_ONLY）
`scripts/reporting/slot_recovery_contract.py` は外部連携境界をfail-closedで定義する。Trigger requestはcanonical JSONへのHMAC-SHA256署名、attempt ID、Asia/TokyoのreportDate/08:00 slot、scheduledAt、triggeredAt、direct-runner source、executionModeを持つ。対象は平日08:00だけで、開始時刻が08:00以後、起動遅延60秒超、署名・時刻・identity不正は拒否する。GitHub Actions dispatchを外部scheduler成功の代替証拠にしない。
G2WriteInputはproducerがDocs保存前に凍結したfullText/bodyHash/reportId/revision/runIdを保持する。Docs writerのbody引数はこのfullTextだけとする。独立readbackはdocumentId、documentRevisionId、fullTextを返し、完全一致とSHA-256を両方検査する。
本文不一致診断は本文を持たず、hash、文字数、firstDiffOffset、missingSections、writerStage、reasonCodes、run/slot identityを記録する。private durable sinkに限定し、14日で消去する。OSファイルmodeだけをクラウドACLの証明として扱わない。
本契約は接続可能性の型・検証ルールであり、外部scheduler/secret、market-data acquisition adapter、Docs create/update/readback adapterの稼働を意味しない。これらの外部要件が満たされるまでproduction E2E=BLOCKED。


## ISSUE-176｜runner・G2→Docs強化仕様（2026-10-26 JST）
TriggerはHMAC署名済みcanonical JSONを検証し、direct-runnerの起動遅延60秒以下、weekday 08:00枠、締切前開始を要求する。TEST_ONLY orchestrationは署名検証→acquisition bytes provider→既存build_slot_evidence（15分鮮度/slot/cutoff/context/snapshot/source/evidence hash検証）→private create-only sink→exact bytes readback→validate_stored_slot_evidenceを一transactionで実行する。07:47/07:53/07:57個別runをfixture acquisitionで回す。これはCloud Schedulerや実市場データの観測証拠ではない。
LIVE adapterは明示許可された場合だけ既存scripts.run_market_data_window.perform_attemptを呼び、従来の市場取得、snapshot freeze、GitHub mainへのcommit後のverify_main_evidence readbackを再利用する。allow_main_evidence_writeの既定値はfalse。TEST_ONLY、レビュー、CIからLIVE関数を呼ばない。15分freshnessやstrict cutoffは既存関数のまま維持。
DocsSaveEvidenceはrunId/reportId/revision/documentId/documentRevisionId/bodyHash/savedAtを保持し、G2 frozen_at < savedAt <= checkedAtを検査。Docs readerのdocument ID/revisionはこのreceiptと完全一致し、全文・SHA-256もpinned G2へ一致すること。writer adapter APIは save(pinned.full_text, body_hash, run_id, report_id, revision) のみを受け、別の本文生成値を受け付けない。現在はプロトコル/contractで、実Google Docs writer/APIは未構成。
診断保持期間は14日固定。filesystem TEST_ONLY purgeは実ファイルを期限境界で削除して検証する。Cloud storeではprivate IAMおよび14日lifecycle設定・期限後の実readbackが別途必要で、filesystem検査をクラウド削除証明に使わない。
