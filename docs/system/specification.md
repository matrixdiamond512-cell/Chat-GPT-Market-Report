# マーケットレポート配信システム 仕様書
現行文書版：2.2｜改訂：2026-11-04 JST｜変更ID：REPORT-ARCHIVE-CONTENT-AUDIT-20261104-01。過去の「未実装」「未解決」状態は当時の記録。現在のポータル保存記録・slot選択・QA表示契約は本ファイル末尾の「現行差分統合 v2.2」と固定ID Google Docsの同一追補を参照する。
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

## 2026-11-04 現行差分統合 v2.2｜REPORT-ARCHIVE-CONTENT-AUDIT-20261104-01
- `data/report-archive-manifest.json` のschemaVersion/filesを検証し、各path/sourceFolderIdのJSONを個別取得する。対象ファイルのスキーマ、date/time、本文、archive statusを検証し、失敗はファイル単位で記録する。
- 正式発行可能データと履歴保存記録をdate + timeで統合し、同一slotでは正式データを優先する。全ソースの取得・検証・統合後に表示可否を判定する。正式ソースの取得失敗で保存記録を捨てない。
- `availableDates` は実レコードから生成し、`reportsForDate` は対象日だけ、time tabsは存在するslotだけを有効にする。存在しないdate/timeはmissing状態にし、別slotへfallbackしない。
- `isDashboardHistoricalArchive` 等の検証と `MarketReportPublicationPolicy` は別判定とする。formal sourceが同じslotなら優先する。archiveのstatus、verifiedAtSlot、source metadataをUI都合で変更しない。
- 08:00 QAは正式対象の28項目・順序・5列・基準日・必須行を検証する。HISTORICAL_ARCHIVEを正式QA合格に算入しない。QA未達ではrole=alertを表示し、対象市場表だけをDOMから除去する。本文と保存元statusを保持する。RECONSTRUCTED_UNVERIFIEDのquarantineは維持。
- エラー/デバッグ出力は対象path/date/time/HTTP status/検証結果を含め、秘密情報を除く。JS更新時はHTMLのquery versionも更新し、Pages deploy後に公開DOMと実ファイルを読み戻す。
- 実績：PR #193 98f3bcc、#194 025da7c、#195 8630b2c、#196 f870b22を統合。UI・アーカイブ関連CIとPages run 41836815631がSUCCESS。公開ブラウザで18日68slotを確認。


## PORTAL-CONTENT-COMPLETENESS-20261116-01（2026-11-16 JST）

両画面は `data/report-archive-manifest.json` の同じ保存本文一覧と `assets/js/report-archive-source.js` の表示専用アダプターを使用する。Doc ID/URL、revision、本文長、日時、出典フォルダーを確認し、形式差（fileId/revision/URL形式/BOM）で有効な本文を落とさない。元本文と正式公開状態を変更しない。後日再構成版は定時原本に昇格せず、参考価格と実測資金フローを混同しない。

Driveから10枠を追加回復し、保存本文91枠を検証。見出し別の主導市場・シナリオ・結論・時系列表示を修正。未取得値を推測せず、残る原本欠落5枠は `data/report-content-gaps.json` に記録する（10/20 08、10/22 12、11/04 08、11/06 08・12）。10/20 08と10/22 12は復旧メモ、11/06 12は空Doc。

検証：Nodeの対象20テストPASS（E2、実保存本文を使ったアダプター/選択/表示回帰）。公開ブラウザは変更前を観測。変更後の公開DOM・Pages反映はNOT_RUN。Google Docs固定ID文書への同期は未実施。定時配信・正式原本・receipt・スケジュールは本変更の対象外。

## REPORT-SLOT-WINDOW-20261117-01｜時刻窓ガード仕様（2026-11-17）
- `scripts/run_market_data_window.py:acquisition_window_status()`：現在JSTが[最初の取得予定−15分, 対象発行枠+90分]の外なら `BLOCKED_FUTURE_ACQUISITION_WINDOW` / `BLOCKED_EXPIRED_ACQUISITION_WINDOW`。Git設定・待機・Git取得・市場データ書込より前に終了コード2で遮断する。
- `scripts/persist_report_slot_evidence.py:require_live_pre_slot_window()` と `.github/workflows/freeze-report-slot-evidence.yml`：対象のJST YYYY-MM-DD HH:MMに対し[T-15分,T)だけ実行。T以降・前日遅延の次日誤写像・早すぎる取得を拒否する。既存の生成済みimmutable evidence、sourceHash、contextHash、snapshotHash、evidenceIdと公開ゲートは無改変。
- 回帰：T-16拒否、T-15許可、T-1秒許可、T拒否、06:14の21:00誤取得拒否、正常な20:28の21:00取得許可、T+90分超拒否。実GitHub Actionsのスケジューラー遅延は別要因であり、定時E2E成功と混同しない。

## REPORT-SLOT-QUEUE-20261117-02｜時間帯別concurrency契約（2026-11-17 JST）

- `.github/workflows/freeze-report-slot-evidence.yml`: 実行待ち行列のキーを `github.event.schedule || inputs.report_slot || github.run_id` で分離。08/12/16/21時ごとの予定cronを混在させず、同じcronの試行は直列化する。
- `.github/workflows/market-data-intraday-{anchor,fallback,health}.yml`: 予定cronのUTC時刻帯と手動 `inputs.report_slot` を同じ08/12/16/21時制約に正規化。12時内・16時内・21時内の一次/補助/健全性確認は同じgroupを共有し、別の対象枠とは分離する。
- `cancel-in-progress: false` を維持。元データ内容、cutoff、immutable evidence、Docs、receipt、canonical、Pagesは変更しない。時計の正確さやGitHub cronの定時起動は保証しない。

## MR-STABILITY-REPAIR-20261117-03（2026-11-17 JST / 修正候補）
sync_reports_from_drive.pyは月別folder検索を全ページ走査し、一意のIDが得られなければBLOCKED_MONTHLY_FOLDER_ACCESS/AMBIGUOUSで書込前に停止。候補検索は当該parentに限定し、Docs全文取得前後のparentとMIMEを検証する。後続の本文/revision/hash/枠前証拠/receiptゲートは維持する。
検証: 新規7件を含む65回帰テストPASS（E1/E2）。本番SAのfolder読戻し・初期4枠・10営業日40枠は未実施。コード/CI成功を全面復旧としない。

## MR-DELIVERY-STABILITY-20261118-01｜コード実装差分・本番検証（2026-11-18 11:58 JST）
- PR #215（main dbc95b8cf613ecf6ef990149e58d66bb6f7bac78）：`scripts/verify_scheduled_report_delivery.py` で2026-10-16以降の新規枠に明示適格statusと `publication-receipts/<reportId>.json`、`validate_receipt()` のDocs本文/readback/hash/証拠ID一致を要求。旧status未指定/単なる参考archiveは正式成功扱いしない。`--require-infographic` 時は正式READY、本文・report/revision・snapshot/manifest/PNG hash・検証PASSの一致を要求し、遠隔PNG byte読戻しを代替したとは扱わない。`.github/workflows/check-scheduled-report-delivery.yml` は各枠+45分の健康検証で図解READYを必須とする。回帰は `tests/test_scheduled_report_delivery.py`。
- PR #216（main da71661a25a8dce65b0a75e8e27c6e9d10342504）：`.github/workflows/freeze-report-evidence-on-acquisition.yml` を追加。指定市場データ取得workflows完了時、main同一repositoryイベントのみから現在の検証済み取得snapshotを選び、reportSlot、平日、T-15<=now<T、generatedAt鮮度・source/context/snapshot hash一致を検証後、排他的なevidence固定とorigin/main byte読戻し。過去枠再生成・既存証拠上書き・force pushは禁止。回帰は `tests/test_report_slot_evidence.py`。
- 実本番：11/18 11:53:37 JST取得 `data/market/latest.json` はreportSlot=12:00、degraded。`data/report-evidence/2026-11-18_12-00-r1.json` はREADY_FOR_DRAFT。取得連動run44226581259は11:54頃既存証拠をNO_OPで確認し `VERIFIED_PRE_DRAFT_EVIDENCE_ON_MAIN` を出力（このrunが新規証拠を作成したとは主張しない）。
- 未受入：4枠本文→独立PNGのQA→Docs→canonical/receipt→Pages DOM→通知の本番一貫性、10営業日40枠、GitHub cron全遅延時の独立実行保証。固定ID Google Docs正本にも同変更ID追記済み。
