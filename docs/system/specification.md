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


## ARCH-20261020-REPORT-CONTINUITY｜新アーキテクチャ設計変更案（2026-10-20 JST、未承認・未実装）
本章は設計提案であり、現行v2.1の実行・正式公開・履歴・証拠ゲートを変更する発効規程ではない。Google Cloud・OpenAI APIのプロビジョニング、ChatGPTタスク設定変更、PR #165マージ、過去枠の証拠生成・正式昇格は未承認。段階的な受入・明示的な切替承認までは現行運用と発行条件を維持する。
### モジュール境界（目標構成、すべて未実装）
(1) SlotPlanner: config/report_schedule.jsonを唯一のスロット定義とする。Cloud Schedulerの「予定実行日時」(X-CloudScheduler-ScheduleTime)又は明示入力からAsia/Tokyoのreport_date/report_slotを確定。スケジュールID→対象枠の固定写像で解決し、now_jst().date()による再計算を禁止。検証不能なcronは拒否。
(2) JobCoordinator: reportId単位の永続台帳、冪等キー、工程別状態、lease/CASを管理。異なる枠をグローバルconcurrency groupで不必要に直列化しない。リトライはジョブの同一IDを再利用。
(3) MarketDataAdapter: 現行の市場取得・CSV/JSON・対象銘柄・出典を再利用。source eventTime/asOf、取得時刻、営業日、価格単位、限月、verified/degraded/blockedを分離し、クロスチェックする。
(4) ImmutableEvidenceStore: Cloud Storage等の保管先へcreate-only（例: ifGenerationMatch=0）、記録されたgenerationで再読戻し、内容SHA-256一致・サーバ確定時刻<T・snapshot/context/source hash・15分鮮度を検証。タイムアウトやアップロード遅延でTを跨いだ保存は公式証拠にしない。旧GitHub mainの事前読戻し要件の廃止は移行承認があるまで禁止。
(5) DraftGenerator: 証拠statusと本文生成可否を分離。検証済み情報があれば一意のdraftRevision/bodyHash付き非正式原稿を作成可能。データを補作せず、出典・観測日時・「取得不能（理由）」を記録。ChatGPTタスク障害時の独立生成にはAPI契約・費用上限・実テストが必要。
(6) DocsWriter/ImageWriter: 原稿/PNGの保存先月フォルダーID、名前、fileId、parents、revision、全本文/bytes hashを独立で再取得。同一名前の別ID競合はBLOCKED_FOLDER_AMBIGUOUS又はBLOCKED_SOURCE_CONFLICT等で停止。図解はその本文だけを用いる。
(7) PublicationGate: 正式公開に必要な現行証拠集合を検証し、成功した原稿revisionのみcanonical→receipt→Pagesへ投影。原稿保存済みとpublishedを別集計。旧SOURCE_ARCHIVED/HISTORICAL_ARCHIVEやfixtureを公開一覧に混入させない。
(8) DeliveryAdapter: 指定ChatGPT会話への投稿/図解表示・通知は独立な観測対象。外部APIから指定会話へ投稿する能力はUNKNOWNのため「実装済み」としない。Docs/別ポータルの閲覧経路は指定チャット送信の達成と混同しない。
### 台帳スキーマ（設計案）
reportId, scheduledAtJST, sourceScheduleTimeUTC, reportDate, reportSlot, statusVersion, leaseOwner/leaseExpiry, snapshotHash, contextHash, evidenceRef, evidenceGeneration, evidenceCreatedAtServer, evidenceHash, evidenceStatus, draftRevision, draftBodyHash, draftCreatedAt, draftStatus, chatStatus, docsFileId, docsRevision, docsReadbackHash, docsStatus, imageFileId, pngHash, imageStatus, receiptId, publicationStatus, publicUrl, publicReadbackHash, notificationStatus, failureStage, lastAttemptAt, actualCreatedAt.
各stageはNOT_STARTED/RUNNING/SUCCESS/FAIL/UNKNOWN/BLOCKED（適宜より細かいerrorCode）を持つ。暫定原稿は公開状態と別フィールドでDRAFT_VIEW_ONLY。canonical statusや正式receiptを代用しない。
### ガード・再試行契約
- 08:00・12:00・16:00・21:00のT-30以前に事前準備を開始可能とし、T-13/T-7/T-3の候補取得を維持。T以前の最終確定のみ正式証拠として扱う。scheduler deliveryは少なくとも1回で重複があり得るので冪等処理必須。
- スロットのUTC/JST変換はZoneInfo(Asia/Tokyo)とScheduleTimeを使用。取得スクリプトに--report-date/--slotを明示し、環境変数からの上書きも禁止。予定時刻、取得基準時刻、実行時刻を混同しない。
- 書込元が異なる二つのジョブで同一reportIdの生成物が衝突したら、最初の証拠を保持し内容差分はCONFLICTへ。遅延開始で現在日付に繰り越すことは絶対にしない。
- 原稿生成に失敗してもevidenceを破棄しない。Docs保存に失敗しても原稿のバイト列を再生成せず保持。GitHub push/Pages dispatchの曖昧な結果はremote readbackで照合してから再試行。
- 既存ワークフローとの二重公開を避けるため、shadow段階では新系統の公開書込みを禁止。段階的に旧publish writerを停止する切替はE2E承認後のみ。
### 実装順序と回帰試験
P0: スケジュール・日付跨ぎ・concurrency問題の回帰テスト（PR #165はこれを満たさない）。P1: 独立スケジューラと不変証拠保存のshadow実装。P2: Stage台帳/原稿のview-only生成・Docs保存試験。P3: 既存原本照合・receipt・正式公開へのゲート接続。P4: 4枠×5営業日E2E、遅延/重複/過去遡及/Docs喪失/PNG不一致/通知失敗/トリガー停止の注入試験と撤回試験。
受入前のGCP/OpenAI認証鍵や本番権限は追加せず、テストは原則fixture/shadowで実施。発行前証拠の基準・Docs/PNG公開ゲート・旧履歴は無断変更しない。
