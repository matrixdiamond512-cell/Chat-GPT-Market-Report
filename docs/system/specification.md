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

## MR-RELIABILITY-20261113-01 — 改善計画・調査着手（2026-11-13 JST）

出典: ユーザー提示「マーケットレポート配信システム改善計画」2026-11-13 01:21 JST。状態: 計画受領、Phase 0調査中、今回の修復実装は未着手、運用受入は未検証。本記録は本番変更の承認ではない。

- 平日08:00/12:00/16:00/21:00 JST、週末なしを維持する。新規分析機能、画面刷新、大規模構造変更を凍結し、既存機能の配信安定化を優先する。
- Phase 0: main・未マージPR・Actions・実ChatGPTタスク・Drive・導入済みApps Scriptを照合。11月11日夕方のタスク変更について操作履歴を調査し、取得できなければ原因不明と監査証拠不足を分けて記録する。
- Phase 1: Actionsの認証主体による月別フォルダ一覧・Doc全文/親/revisionの読戻し、取得0件/拒否/認証不備の区別、正式公開資格と全インデックス整合、予定日時/実行開始/reportIdの分離を修復する。接続中のDrive利用者とActionsサービスアカウントを混同しない。
- Phase 2: 発行とは独立して15分後確認、30分後異常記録と再試行可否判定、45分後障害通知を目標とする。タスク実行、本文、Drive保存/全文読戻し、GitHub、公開URL本文、通知到達を別々に検証する。これは要求であり実装・稼働済みの主張ではない。
- Phase 3/4: 本計画の運用受入基準は修正後の5営業日・20枠連続。1件でも失敗すれば原因/影響箇所/回帰検証を記録し、連続計数を再開する。以前の10稼働日等の記載は過去の計画として保持する。20/20のタスク実行・本文作成とチャット表示・Docs保存/全文読戻し・資格判定結果確定、適格本文全件の公開、日時ずれ/重複/未検出障害/重大誤記0件を必要とする。PNGは独立状態とする。
- 停止/遅延/日付またぎ、Drive拒否/空Doc/同名重複、欠損/古い価格/方向誤り、部分成功/索引不整合、deploy成功だが公開本文なし、再実行の二重公開/上書き、通知失敗/検知漏れを検証対象にする。実タスク停止や本番障害注入は未承認・未実施であり、安全な隔離試験を先に行う。
- 本番タスク停止、時刻/保存先/配信方式/権限変更、破壊的データ変更には事前承認と記録を必要とする。文書追記からmain merge、公開workflow実行、Docs/Drive書込、Pages deployの権限を推論しない。過去枠の発行前証拠は再構成しない。

影響文書: requirements.md、specification.md、operations.md、DOCUMENT_CONTROL.md、project-control/EVIDENCE_LEDGER.md、OBJECTIVE_CARD.md、HANDOFF.md。固定Google Docs要件/仕様/本文作成/運用/台帳は同じIDを維持。今回の本文作成ルール変更なし（NO_CHANGE）だが本文作成/チャット表示/保存結果は受入対象。Google Docs現行revision照合・同期・読戻しはNOT_RUN、別名の要件/仕様/マニュアルを作成しない。

## MR-ZEROCOST-20261113-01 — 追加課金ゼロの経路整理（2026-11-13 JST）

出典：ユーザー提示03:16改訂指示書と同日の追加指示・タスク確認画像。受領テキストは `READY_FOR` の途中で終わるため、未受領の後続条項は補完しない。旧MR-RELIABILITY記録は当時の履歴として保持し、本追補の追加費用ゼロ・本文/図解品質維持を優先する。状態：ローカル実装候補、main未反映、定時発行・切替・連続運用受入は未達。

`config/report_delivery_policy.json` は mode=shadow、productionOwner=legacy、productionAdapter=null、課金許可4項目=falseに固定。`scripts/verify_zero_cost_delivery.py` はネットワークやSecretsを使用せず、ポリシーとソース内AI API接続先を走査する。旧API接続workflow4本は全jobに `if: ${{ false }}` を付け、checkout/Secrets/HTTPより前に停止する。旧main/旧SHAからの再実行を止めた証拠ではなく、候補差分として管理する。

単一shadow入口：`python scripts/run_report_delivery.py --report-id YYYY-MM-DD_HH-MM --source-bundle <受領フォルダー>`。日付/枠を実行時刻から推測せず、report_schedule.jsonの曜日と枠を検査。生成・Drive新規保存・GitHub push・Pages deploy・チャット投稿は実装していない。

受領bundleは `report.json`（原文全文・同一性）、`receipt.json`（既存v2）、`drive-file.json`（実metadata）、`bundle.json`（独立に特定したbodyMonthFolderId）、`evidence.json`（実在する枠前証拠）、`infographic.png`、`infographic-manifest.json`。欠落時に作成しない。bundleの主張は独立Drive観測の代わりにはならない。

1. 受領実バイトを固定し、既存 `validate_saved_body` / `validate_sop_body` を再利用。08時は既存 `verify_morning_report_qa.py` を隔離入出力で実行する。
2. 既存 `validate_receipt` / `verify_slot_evidence` でsource revision、本文hash、snapshot/context/source hash、枠前時刻とDocs保存窓を照合。枠前証拠の隔離コピーは元バイトの転記だけで、過去の証拠を新規構成しない。
3. PNG実バイト/CRC/構造を既存 `validate_png` で検査し、manifestのreport_id/revision/snapshot_id/body_hash/png_sha256/png_filenameを一致させる。これはレイアウト・数値内容の実画像QAを代替しない。
4. 固定の `logs/report-delivery-shadow/journal.sqlite3` だけへ、reportId/revisionを主キーに候補・全受領ファイルの実バイト・イベントを同一SQLiteトランザクションで格納。既存同revisionの変更、格納済み画像の欠落、入力の検証中変更はブロック。失敗時rollback、同一原本再実行は同じ記録を返す。
5. パス逸脱を拒否。SQLiteのロックは同じローカルDBに限る。GAS/複数PC/Actionsの分散ロックを実装・検証したとは扱わず、本番書込も許可しない。
6. 最大到達状態は `SHADOW_STAGED`、全工程は常に `NOT_VERIFIED`。独立Drive読戻し/本文の事実QA/図解内容/視覚QA/会話出力/保存/Pages/通知は別状態に保持。欠落は `WAITING_FOR_SOURCE_ARTIFACT`、不正/競合は `SHADOW_BLOCKED`。原本のreport_statusやreceiptを変更して合格させない。

`scripts/build_market_json.py` はPR #188 head `860ec370af7633a8ccadf393a474ee2614ce5430` の同一blobを再利用し、latestReport/reports内部へlive市場データを注入する処理を削除。dashboard.marketData、更新日時・出典・欠損警告は維持。既存の公開JSONの強制再生成や過去原本の補正はしない。

PR用CIは読取権限、public repositoryの標準ubuntu runner、外部API/Secrets/依存インストール/追加schedule/有料artifact保存なし。ホストCIは未実行。全既存writerの本番単一化は、所有者/導入版/停止影響/readbackが揃うまで未実装・切替保留。


## MR-SOURCE-HANDOFF-20261113-01｜非本番の実保存・原本受渡し境界（2026-11-13 JST）

本段階で追加のランタイム経路は実装していない。既存Drive connectorの `import_document(native_google_docs, parent_folder_id)` による実保存と、get_document/full text・get_file_metadata・revision readbackを手動実行した。

非本番folder `1JN-iq2Y2cmiYpiDIqOM7xtn53-_ztuIv`、Doc `1fRNyN1E2xzk0vj1GahLn5Xc4gupsEth7LZcNQYVLf6M`。元は11/12 08時補充Docの取得済み全文2495文字。変換直後2496文字で末尾改行1文字の不一致を検出。初回Docs revisionをrequiredRevisionIdに指定し、新規試験DocのUTF-16範囲2495:2496だけ削除。再読戻し2495文字、SHA-256 `2f9347fd286f3311040fe76fbd7911d669503dff2dde75d69e1a6e61e899259e` が入力と完全一致、親とMIMEも一致した。元Docは変更していない。

この試験結果はpublication receiptではなく非本番の観測証拠 `docs/project-control/evidence/source-handoff-save-readback.json`。Docsの実作成/更新日時と予定枠日時を分離し、元Doc revisionや枠前証拠を補作しない。既存shadowは引き続き本番adapterなし/全工程NOT_VERIFIED。タスクの実原文・画像を受け取るまで当該工程はWAITING/BLOCKED。

get_document_textの段落リストは空段落を省くため、単純join/trimを全文一致の根拠にしない。比較には実構造のtextRun（全対象tab・空段落を保持）を使用する。今回の限定的な末尾修正を一般のstrip/改行一括正規化へ拡大しない。
