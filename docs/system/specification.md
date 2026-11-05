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


## MRF-0800-20261029 — G2 → Docs → portal transaction (Draft proposal)

1. Read the production evidence object at an explicit GCS generation and verify its byte SHA-256, evidence ID, report ID/revision, context, snapshot, source hash, 15-minute freshness, and pre-slot cutoff using the existing evidence validator. Reject TEST_ONLY project/bucket configuration.
2. Bind the frozen G2 fullText and bodyHash to that evidence. Require an independent human scenario review for main, alternative, and invalidation roles, each with exact source offsets/quotes for condition, development, and market impact; require explicit attestations that the alternative branches from the main case and that the invalidation item changes the decision.
3. Acquire a create-only GCS claim keyed by report ID/revision. Identical claims are idempotent; any body/evidence/snapshot difference blocks.
4. Save only the fixed fullText to one uniquely identified Docs file in the configured monthly folder. Re-read through the Docs API and verify document ID, revision ID, exact full text, SHA-256, Drive parent, and slot save-time window. A partial create or conflicting duplicate is quarantined for operator reconciliation; never create a second document to recover.
5. Only after Docs readback passes may the adapter invoke the existing target-scoped canonical importer/publication workflow. Require its independent readback to match report ID/revision, snapshot ID, Docs ID/revision, full text, and body hash before returning PUBLISHED. PR #188 implements this connection and an isolated rendered-DOM readback contract; production credential use, scheduled invocation and public deployment remain NOT_RUN.
6. No status returned by fixture adapters is evidence of live publication. A production rollout requires separate review, configured least-privilege identities, a verified G2 producer connection, and approved external E2E.


## MRF-0800-20261029 — existing importer compatibility and stop boundary

- Drive source file name is `マーケットレポート_YYYY-MM-DD_08-00`, which the existing importer discovers. The document body begins with the separate `title_for(date, slot)` title and must pass `report_source_contract.validate_saved_body`; exact fullText and SHA-256 remain unchanged.
- The existing `scripts/sync_reports_from_drive.py` reads its frozen evidence from the repository checkout at `data/report-evidence/<date>_08-00-r1.json`. The PR #188 bridge now stages the pinned bytes in an isolated importer checkout and calls the existing importer only for the exact Docs ID/report ID/revision. The standard three-day importer path is unchanged. Docs success remains insufficient for portal acceptance unless the strict importer and subsequent canonical/receipt/public readbacks all pass.
- The existing `publish-saved-google-docs-reports.yml` `workflow_dispatch` path checks out main, runs importer with `--apply`, commits eligible canonical files to main, and dispatches Pages deployment. It is a production write route. This PR did not dispatch or modify it. A later WIF-based evidence handoff, explicit identity binding, and approved publication switch are required before connecting it.



## MRF-0800-20261029 — strict staging importer behavior

- `scripts/reporting/importer_handoff.py` reads a caller-pinned TEST_ONLY GCS generation, validates its hash and stored slot identity, then writes the exact bytes create-only to `data/report-evidence/<date>_08-00-r<revision>.json` below a separate checkout containing a `.market-report-staging.json` marker (`LOCAL_STAGING_ONLY`, `TEST_ONLY`). It verifies exact byte readback and never overwrites conflicting evidence.
- `sync_reports_from_drive.py --root <isolated-checkout> --require-issuance-binding` is an explicit opt-in local staging path. It requires the marker, rejects the current importer checkout as a target, and enforces Docs appProperties binding for report ID, revision, exact readback body hash, evidence ID, and snapshot ID before issuing a readback receipt.
- The ordinary scheduled workflow calls the importer without either flag; its default root and behavior are unchanged. No workflow_dispatch or Pages action is part of staging. `--apply` writes only files under the selected isolated checkout; use the default dry-run first.
- The staging helper requires importer and staging roots to be disjoint in both directions. It accepts project and bucket identifiers only when `test` is a standalone token, and accepts GCS object names only under the exact `test-only/` prefix. Substring matches such as `contest` do not qualify. It resolves the evidence destination and verifies containment before creating directories, then checks containment again after creation. Its result is `LOCAL_STAGE_READBACK_PASS`, never `PUBLISHED` or `VERIFIED`. Production GCS, G2, Docs save/readback, portal publication, and public DOM remain separate gates.

## DELIVERY-CLOSEOUT-20261101-01 — source heading/parser contract (integration candidate)

`report_source_contract.heading()` recognizes explicit numbered prefixes with ASCII/full-width pipes, punctuation separators, or colons; it continues to recognize the existing plain and Markdown heading forms. An explicitly labeled inline conclusion (`結論：text`, `最終判断：text`, `まとめ：text`) is a section with the text after the label retained as that section's body. Unmarked prose remains ordinary body text. This changes source parsing only and preserves body bytes/hash and every issuance/publication gate. GitHub main and the fixed-ID Docs have not yet been updated.

## DELIVERY-CLOSEOUT-20261101-01 — retrospective archive identity

`validate_report_recovery.py` must require the three 2026-10-16 posthoc entries, pin `recoveryRecordedAt` to `2026-10-17T04:22:00+09:00`, and require `originalReportStatus=ORIGINAL_NOT_FOUND` plus `archiveType=RETROSPECTIVE_REPORT`. These entries remain non-official historical material and may not shadow canonical reports. The Pages workflow watches this validator. Candidate validation: 31 archive entries PASS; main/Drive production acceptance remains unverified.


## MRF-INGESTION-20261030-01｜取込段階ログ契約（2026-10-30 JST）
scripts/sync_reports_from_drive.pyの完了ログは、結果に対応する段階だけを示す。canonicalへの保存は CANONICAL_SOURCE_INGESTION_COMPLETE、証拠/receipt不足の本文は SOURCE_ARCHIVED_ONLY、Docs readback receiptありは DOC_READBACK_RECEIPT_RECORDED とする。Docs receiptはPages配備または公開DOMの証明として扱わない。未認識のreceipt/status組合せは CANONICAL_INGESTION_STATUS_UNKNOWN として、上位状態へ昇格しない。既存のeligibility gate、本文、canonical、receipt、公開投影のロジックは変更しない。

## 2026-11-04 現行差分統合 v2.2｜REPORT-ARCHIVE-CONTENT-AUDIT-20261104-01
- `data/report-archive-manifest.json` のschemaVersion/filesを検証し、各path/sourceFolderIdのJSONを個別取得する。対象ファイルのスキーマ、date/time、本文、archive statusを検証し、失敗はファイル単位で記録する。
- 正式発行可能データと履歴保存記録をdate + timeで統合し、同一slotでは正式データを優先する。全ソースの取得・検証・統合後に表示可否を判定する。正式ソースの取得失敗で保存記録を捨てない。
- `availableDates` は実レコードから生成し、`reportsForDate` は対象日だけ、time tabsは存在するslotだけを有効にする。存在しないdate/timeはmissing状態にし、別slotへfallbackしない。
- `isDashboardHistoricalArchive` 等の検証と `MarketReportPublicationPolicy` は別判定とする。formal sourceが同じslotなら優先する。archiveのstatus、verifiedAtSlot、source metadataをUI都合で変更しない。
- 08:00 QAは正式対象の28項目・順序・5列・基準日・必須行を検証する。HISTORICAL_ARCHIVEを正式QA合格に算入しない。QA未達ではrole=alertを表示し、対象市場表だけをDOMから除去する。本文と保存元statusを保持する。RECONSTRUCTED_UNVERIFIEDのquarantineは維持。
- エラー/デバッグ出力は対象path/date/time/HTTP status/検証結果を含め、秘密情報を除く。JS更新時はHTMLのquery versionも更新し、Pages deploy後に公開DOMと実ファイルを読み戻す。
- 実績：PR #193 98f3bcc、#194 025da7c、#195 8630b2c、#196 f870b22を統合。UI・アーカイブ関連CIとPages run 41836815631がSUCCESS。公開ブラウザで18日68slotを確認。

## MR-ISSUANCE-CONNECT-20261104-02 — PR #188 concrete adapter

`scripts/reporting/issuance_portal.py` implements a target-scoped bridge: create-only stage the same pinned evidence bytes; call `sync_reports_from_drive.import_exact_issuance_doc` for one report ID/revision and exact Docs ID; reuse `build_report`, `verify_slot_evidence`, Docs appProperties binding, and receipt validation; run existing latest/index/consistency projections; commit only the target canonical JSON, receipt, and resulting publication indexes as one GitHub main compare-and-swap commit; read those files back; then require the existing `deploy-pages.yml` run for that exact commit to succeed and fetch/compare the actual public JSON body and hash. The adapter uses a separately supplied `REPORT_ISSUANCE_GITHUB_TOKEN`, explicit `REPORT_ISSUANCE_WRITE_ENABLED=true`, a main checkout at the expected SHA, and configured Pages URL. Test-created adapters are labeled TEST_ONLY.

Invoke the explicit entry point as `python -m scripts.run_0800_issuance <bundle.json>` so imports resolve from the repository root. It binds G2 to `evidence_ref.object` and integer generation, reads that precise GCS generation, checks today's weekday 08:00 slot and 40-minute window, then calls `run_issuance()` with the production Docs writer, claim store, exact-document importer, and portal adapter. `--help` is available without production credentials; absent or malformed input must return `BLOCKED` before cloud clients are created. It does not modify the ChatGPT schedule or ordinary three-day importer. No latest-evidence lookup is permitted. Production publisher additionally requires the named `report-publication` Environment context, its approval, `refs/heads/main`, and an exact `GITHUB_SHA` checkout. It accommodates Actions detached HEAD checkouts.

`GitHubRestClient.publish_files(..., create_only_paths=(canonical, receipt))` rejects a conflicting canonical/receipt or one-sided pair before creating blobs. Exact retries reuse existing content; a moved main ref is reconciled only if the whole target canonical/receipt/index file set is byte-identical. Any nonidentical moved head or fast-forward ref update rejection stops for reconciliation. `report-core-v3.js` exposes the selected identity on rendered `#app`; `validate_issuance_report_dom.js` hashes the exact target body and checks identity/date/time/title/body in Chromium. The public-mode validator requires `reports.json` to contain exactly one row for the reportId and checks revision, date/time, fullText, body SHA-256, and rendered DOM. Isolated page fixtures retain the existing `reports/` corpus used by renderer/archive loaders, then add the exact target canonical detail beside the public index array. After JSON readback, the production Pages verifier invokes that validator in public mode against the actual HTTPS page; missing Chromium/Playwright or any mismatch blocks `PUBLISHED`. `issuance_preflight.py` performs read-only GitHub/Drive/GCS probes and checks the local Node/Playwright/Chromium runtime. GitHub read endpoints cannot certify a fine-grained token's exact `contents:write` grant; absent protected `REPORT_ISSUANCE_CONTENTS_WRITE_VERIFIED=true` admin attestation, that value is UNKNOWN and overall preflight cannot report READY. Fixture results are code evidence, not production E2E.

Partial state is explicit: an importer failure does not reach GitHub; a GitHub ref/readback uncertainty requires reconciliation; after canonical commit/readback, a Pages failure remains not published and can be retried only against the same canonical content/receipt. An identical remote file set reuses the current main SHA without creating a duplicate commit. This route does not use TEST_ONLY handoff markers or change the standard scheduled importer. Current implementation is 08:00-only by contract; other three slots remain NOT_RUN. CI/fixture results do not establish production credentials, real Docs, main write, Pages deployment, or public readback.\n\n## MR-ISSUANCE-PRODUCTION-READINESS-20261105-01｜本番接続制約（2026-11-05 JST）\n- PR #188のrun_0800_issuance.pyは入力JSONのG2およびgeneration指定evidenceを要求する。調査した現行Apps Script定時経路にはこのbundleの生成・handoffがなく、既存ChatGPT定時タスクがCLIを呼ぶ証拠もない。したがって定時本文生成元と発行CLIは未接続として扱う。\n- 発行CLIは08:00専用の当日時間窓、Evidence generation、G2 identity、Docs readback、strict importer、canonical/receipt/Pages readbackを順に検証する。今回それら本番外部工程は実行していない。\n- Read-only preflightのprotected_execution PASSはGitHub APIでrequired reviewersを確認したEnvironment保護設定の存在だけを示す。当該runが承認された事実は NOT_INFERRED。REPORT_ISSUANCE_APPROVED環境変数は承認根拠に使わない。\n- 1-slot手動preflightはworkflow_dispatch専用とし、reportId/revision/evidence object/generationを明示、contents:readのみ、発行Secretsなし、Docs/GitHub/Pages書込みなしとする。本番起動はNOT_READYのまま。

## MR-ISSUANCE-PRODUCTION-READINESS-20261105-01｜CI証拠追記
- CI code head 5538a8707f2179fcabde9ea5b4fa32239664a00e でissuance integration contract PASS：83 Python tests (17+39+16+11) とcompile/CLI smoke。https://github.com/matrixdiamond512-cell/Chat-GPT-Market-Report/actions/runs/41875493256
- isolated UI/DOM PASS：https://github.com/matrixdiamond512-cell/Chat-GPT-Market-Report/actions/runs/41875493440。その他8件も同じheadでPASS。これはActions隔離環境の結果で、本番Docs/GCS/GitHub canonical/receipt/PagesはNOT_RUN。
- main f43cc00f60d5a32fa96fa6cb4de440c7f971fc4a を2親同期commitに保持。main-only data/history変更はPR側の変更パスと重複なし。Google Docs固定IDへの同期はNOT_RUN。

## MR-ISSUANCE-ENTITY-20261105-02 — pinned G2 source and single owner

The 08:00 CLI may accept a G2 bundle from a local file or an explicit GCS generation. The production GCS handoff requires reportId, positive revision, Evidence object/generation, and exact G2 object/generation. It verifies the downloaded generation and G2 creation time, then requires the bundle and Evidence references to match before Docs work. A reader alone does not create the producer or establish provenance; the producer identity and bucket write policy still require administrator confirmation.

config/issuance_ownership.json currently assigns all four slots to apps_script_legacy. The new CLI therefore remains blocked for 08:00 until a separately reviewed ownership change; 12:00/16:00/21:00 remain on the legacy owner. Do not switch ownership until the Apps Script guard is deployed and tested, no legacy 08:30 attempt is in flight, the protected CLI is ready, and rollback ownership is agreed.

## MR-ISSUANCE-ENTITY-20261105-02 — G2 object input and ownership

The 08:00 consumer supports an exact GCS object generation and requires explicit reportId, positive revision, Evidence object/generation. It rejects a non-matching identity/reference, late object creation, invalid generation, and malformed owner config before Docs work. The producer adapter is implemented, but no external task caller or trusted source identity is connected. Preflight must remain blocked until that runtime handoff is verified; a hash match does not prove who authored the text.

The ownership file remains apps_script_legacy for all four report slots. Only a separately approved, reviewed transition after the Apps Script guard is deployed may assign 08:00 to g2_issuance_cli; all other slots retain their current owner. Actual installed time triggers and history are not inferred from source declarations.

## MR-ISSUANCE-G2-PRODUCER-20261105-03 — implementation and connection status

Implemented in the PR: `scripts/reporting/g2_bundle_producer.py` exposes `TrustedG2BundleProducer.freeze_and_store()`. It accepts final task-authored text plus the exact pre-slot Evidence envelope, binds reportId/revision/body SHA/frozen_at/evidenceId/snapshotId and scenario review, writes one create-only GCS object, and reads back its exact generation/bytes. Identical retry reuses the same generation; conflict or uncertain readback blocks. The 08:00 CLI consumes the returned object/generation with explicit report and Evidence references.

This adapter is not yet invoked by the existing ChatGPT task, and its production GCP workload identity/bucket IAM is not configured or verified. No task callback or installed schedule was inspected. Therefore preflight remains `NOT_READY` and production status remains `BLOCKED_G2_PRODUCER_MISSING` until the task-to-adapter handoff and trusted writer identity are established. Do not infer G2 from an existing Docs file or change the task schedule.

On code SHA `9fd7470606bbf2bdd9fbcc9fd1e9f250b63de736`, six isolated Python suites passed 110 tests (17+39+16+17+7+14); all 10 related Actions passed. This is fixture/CI evidence only, not a live task, GCS, Docs, GitHub, or Pages result.

## MR-ISSUANCE-G2-PRODUCER-20261105-03 — synchronized code acceptance

Executable tree on synchronized code SHA `a4641d4fa1d55120e1e95af0548d06a886dafb17` passed 110 Python tests under Actions Python 3.12: pipeline 17, portal 39, importer handoff 16, preflight 17, pinned G2 handoff 7, producer 14; compile and CLI smoke also passed. All ten related Actions passed: [issuance 41907967951](https://github.com/matrixdiamond512-cell/Chat-GPT-Market-Report/actions/runs/41907967951), [UI/DOM 41907968119](https://github.com/matrixdiamond512-cell/Chat-GPT-Market-Report/actions/runs/41907968119), [sync recovery 41907967813](https://github.com/matrixdiamond512-cell/Chat-GPT-Market-Report/actions/runs/41907967813), [Apps Script validation 41907967892](https://github.com/matrixdiamond512-cell/Chat-GPT-Market-Report/actions/runs/41907967892), [frozen cutoff 41907968232](https://github.com/matrixdiamond512-cell/Chat-GPT-Market-Report/actions/runs/41907968232), [delivery 41907968211](https://github.com/matrixdiamond512-cell/Chat-GPT-Market-Report/actions/runs/41907968211), [dashboard health 41907967835](https://github.com/matrixdiamond512-cell/Chat-GPT-Market-Report/actions/runs/41907967835), [eligibility 41907968113](https://github.com/matrixdiamond512-cell/Chat-GPT-Market-Report/actions/runs/41907968113), [historical recovery 41907968451](https://github.com/matrixdiamond512-cell/Chat-GPT-Market-Report/actions/runs/41907968451), and [saved-source QA 41907968393](https://github.com/matrixdiamond512-cell/Chat-GPT-Market-Report/actions/runs/41907968393).

Main `ba8d09a1b1170b56b42c8f33c125a19f120fb0dd` was synchronized in merge commit `a4641d4fa1d55120e1e95af0548d06a886dafb17`. Main's only change since the previous sync was `data/usdjpy-volume.json`; it did not overlap the 44 PR paths and is absent from the PR diff. PR #188 remains OPEN/Draft/unmerged. Live G2 task invocation, workload identity/IAM, installed trigger inventory, authenticated preflight, Docs, canonical/receipt and Pages writes remain NOT_RUN or UNKNOWN. The adapter's automated pass does not remove BLOCKED_G2_PRODUCER_MISSING.

## MR-ISSUANCE-TIME-CONTRACT-20261105-01｜08:00時刻契約修正

08:00枠の工程時刻を分離する。Evidenceの期限・鮮度条件は変更しない。

- 市場データ取得：定義済み06:30取得系およびT-13/T-7/T-3の当日枠取得。snapshotの生成時刻・鮮度は既存validator（15分以内）で検査する。
- Evidence生成・凍結：08:00:00 JST以前。generation、object SHA-256、reportId/revision、snapshot/context/source hashを固定し、発行後生成・再構成を拒否する。
- G2生成開始・レビュー・凍結：08:00:00〜08:40:00 JST。08:00に始まるレポート作成タスクが同時刻以前に本文を凍結することはできないため、G2はslot開始後に作成・人手レビューし、Docs保存前にfreezeする。reviewed_atは本文hashと同一reportIdに結び、slot開始以降かつfrozen_at以前とする。
- G2 object保存：凍結後、同じ08:00〜08:40枠でcreate-only。GCS作成時刻・generation・本文hashを読戻し、作成時刻がfreezeより前または枠終了後なら停止する。
- Docs保存・正式発行・公開照合：08:00:00〜08:40:00 JST。G2 freeze/review後に保存し、既存の全文読戻し、正式原本/receipt、Pages実DOMゲートを維持する。

変更理由：従来のproducerはG2を08:00以前にfreezeし、producerの現在時刻を08:00未満に限定していた。一方で発行CLIは08:00〜08:40にのみ起動する。定時タスクが08:00開始なら、そのtaskが開始前に本文をfreezeするのは不可能である（実際のtask開始時刻と出力経路はUNKNOWN）。従来条件では一つの08:00開始経路として成立しなかった。これはEvidence期限を緩めず、本文側のfreeze/review条件のみをslot内に明示する改訂である。過去Docs・本文・Evidenceは新たな発行前証拠として認定しない。コード/隔離CIの合格は実タスク接続や本番公開の証拠ではない。

### G2生成主体と実接続の証拠条件

G2生成主体の判定は環境変数やbundle内の申告を証拠にしない。認証付きpreflightは、正確に読戻したGCSのbucket/object/generationとSHA-256に対してCloud Audit Logsのstorage.objects.create記録を引き、principalEmail・resourceName・generation・記録時刻（G2 freeze〜08:40 JST）を照合する。照合が取れない、記録が未有効、Logging API権限がない、principalが違う場合はBLOCKEDとする。Cloud Storage Data Access監査ログは明示的に有効化が必要で、未設定ならここで止まる。有効化や課金影響の設定は管理者作業とし、この変更では行わない。

想定認証はGitHub Actionsの保護main/ref+EnvironmentからGoogle Workload Identity Federationで専用service accountをimpersonateし、G2 objectはcreate-only、Evidenceは指定generation read、claim prefixは既存の必要権限に限定する構成。GitHub側の期待service account名は保護環境の設定として扱い、監査ログの実principal一致が必要。service account keyをSecretsへ追加しない。

ChatGPT定時タスクの生成本文をこの実行環境から取得するコネクタ/APIは確認できていないため、TrustedG2BundleProducerは呼出し可能なアダプターであり、タスクへ実接続済みの生成主体ではない。
Cloud Audit Logsの`storage.objects.create`記録は、対象GCS object/generationを書き込んだGCP認証主体（principalEmail）と記録時刻を結び付ける証拠であり、ChatGPT定時タスクが本文を生成・作成・レビューし、その本文をG2へ渡した証拠ではない。本文の出所は別の同一実行記録で立証する。最低限、タスク実行識別子と完了時刻、reportId/revision、保存前本文SHA-256、Google Docs fileId/revision・全文読戻しSHA-256を同じG2 bundleへ結び付け、Evidence object/generationとG2 object/generationの対応を検証する。これらの同一実行対応が欠ける過去のDocs本文やGCS書込みログはG2生成証拠として扱わず、正式発行をBLOCKEDにする。既存taskは08:00開始とされ、task出力が08:00〜08:40内に人手レビュー・freezeされれば新時刻契約には適合するが、実出力・完了時刻は未確認。

実運用代替案は二つある。第一案は、本文を生成する既存ChatGPT taskを維持し、運用者が本文/revision/reviewを非公開の承認済み実行環境へ受け渡し、protected workflowがEvidence generationを読んでG2をfreeze/storeし、そのgenerationを発行CLIに渡す手動運用。早期の限定試験に向くが、手動受渡し記録が必要。第二案は、taskがOIDC/Webhookを実際に出せることを確認した後、専用の受信実行主体を作り、その主体がWIFで同じproducerを呼ぶ自動運用。taskのWebhook能力が未確認で、追加serviceの保護・費用確認も要るため現時点では実装可能と断定しない。公開GitHubのdispatch inputsへレポート本文を直接貼り付ける方法は監査イベントへの本文露出があるため採用しない。

### 08:00 ownerの切替条件

Git上のApps Scriptは08:00枠を含むDocs→GitHub発行コード/08:30付近のretry handlerを定義する。これは実際のApps Script deployment、installed trigger一覧、 timezone、直近実行履歴の証拠ではない。実状態はUNKNOWN。owner configは08:00をapps_script_legacyのまま維持し、新CLIは競合ガードにより発行を停止する。切替は承認後、(1)現行deployment版・trigger/last executionを読取り確認、(2)08:00旧triggerと08:30 retryのみ停止し12/16/21を維持、(3)停止状態を再読戻し、(4)08:00 owner configを新方式へ変更、(5)protected新方式を起動、(6)未来の08:00 slot 1件を承認付きE2Eで照合、の順とする。確認できないtrigger/historyはUNKNOWNのまま所有権を切り替えない。

## MR-EVIDENCE-GCS-WINDOW-20261105-01｜Evidence freeze契約
- `require_slot_window(report_date, report_time, now)` がJSTへ変換した実時計で `[target - 15 minutes, target)` と平日条件を検証する。日付は必ず明示し、cron表現から選んだslotと実行日が15分窓に合わない遅延runは停止する。
- 実行窓ガードを入力データ取得・書込み前に評価し、Evidence作成時刻も同窓内であること、market data generatedAtがEvidence作成より後でないことを検証する。既存artifact再読戻しにも枠同一性と時刻を要求する。
- GCS object名はreportId/revisionに固定し、create-only preconditionを用いる。同一内容の再試行のみ成功とし、異なる内容、generation、読戻しhash、時刻またはidentityの不一致は停止する。
- GCS canonical bytesに対するGitHub mirrorは同じEvidence本文とgeneration参照sidecarから構成する。部分成功時は現行15分窓内で既存の同一バイト列のみ再調整可能。GCS不在・不一致、期限後、異なるlocal bytesの場合は修復・再生成せず停止する。
- エラー分類: `SCHEDULE_NOT_OBSERVED` (run履歴にrunなし), `SCHEDULE_LATE` (実行時刻が許可窓外), `INPUT_STALE`, `INPUT_SLOT_MISMATCH`, `ACQUISITION_FAILED`, `EVIDENCE_WRITE_FAILED`。履歴欠落とrun内失敗を混同しない。


## MR-EVIDENCE-GCS-WIF-SLOT-ISOLATION-20261105-01 — 08:00 GCS isolation and WIF contract (2026-11-05)

- 新方式のGCS canonical Evidence保存・generation読戻しは08:00枠だけに適用する。08:00は対象日時の直前15分以内の実時間ガード、Evidenceの作成時刻・本文・取得データhashを保持し、GCSオブジェクトをcreate-onlyで保存してgenerationを固定読戻しする。GCS未設定・認証失敗・読戻し不一致は08:00をBLOCKEDとする。
- 12:00・16:00・21:00は従来のGitHub内ローカルEvidence経路を維持する。従来の「対象締切より前」ガードとデータ鮮度・同一reportIdのimmutable衝突停止を維持し、GCS bucket・GCS認証を要求しない。GCS操作APIからは08:00以外を拒否する。
- GCS認証はGitHub Actions OIDC→Google Cloud Workload Identity Federation→専用サービスアカウントのADCを使う。JSON鍵をGCSクライアントへ渡さない。既存の市場データ取得に使われるサービスアカウントSecretは別経路として扱い、本改修では変更しない。
- 管理者設定: GitHub Actions Environment/Repository VariablesにWIF provider resource name、専用SA email、明示的project ID、Evidence bucketを登録し、Google Cloud側でGitHub repository/ref/workflow条件を限定したWIF provider/trustを構成する。専用SAには対象bucket/prefixに限定したcreate/get（object create + generation-pinned object get）権限を付与する。object list/delete/update権限は要求しない。Cloud Storage Data Access監査ログを利用する場合は管理者が対象サービス/ログ種別を有効化し、監査閲覧主体を別に制限する。
- 検証状態: 実GCS書込み、IAM/WIF trust、Actions Environment設定は未実行。隔離テストとCIが通過しても本番Evidence READYとはしない。CI結果は同変更IDのEvidence Ledgerに追記する。


### Verification update — code head bc9d7cd7fca9aa52c1e6ffe7269788204d2b49d1

- Python 3.12 hosted CI: issuance contract suites PASS (18+40+16+18+9+17+23 = 141 tests); the 23-test Evidence suite includes 08:00 missing-GCS BLOCKED, non-08:00 cutoff-only behavior, immutable same-report conflict, late-run/date mismatch, GCS create-only/idempotent retry/conflict, and local-mirror retry/recovery cases.
- The initial run on 4cfad54 failed 3 assertions in the new/affected Evidence suite. Logs showed a now=None keyword-shape expectation mismatch in the mocked 08:00 guard and a historical non-08:00 fixture whose post-write live-clock recheck correctly rejected it. The helper now preserves the no-argument live call shape; the historical-fixture test isolates the clock guard while asserting immutable conflict behavior. No gate was weakened.
- Exact code-head Actions: issuance [41946722018](https://github.com/matrixdiamond512-cell/Chat-GPT-Market-Report/actions/runs/41946722018), frozen cutoff [41946722116](https://github.com/matrixdiamond512-cell/Chat-GPT-Market-Report/actions/runs/41946722116), delivery health [41946721817](https://github.com/matrixdiamond512-cell/Chat-GPT-Market-Report/actions/runs/41946721817), UI/DOM [41946722003](https://github.com/matrixdiamond512-cell/Chat-GPT-Market-Report/actions/runs/41946722003), Apps Script validation [41946721888](https://github.com/matrixdiamond512-cell/Chat-GPT-Market-Report/actions/runs/41946721888), sync recovery [41946721981](https://github.com/matrixdiamond512-cell/Chat-GPT-Market-Report/actions/runs/41946721981), dashboard health [41946722110](https://github.com/matrixdiamond512-cell/Chat-GPT-Market-Report/actions/runs/41946722110), dashboard eligibility [41946722083](https://github.com/matrixdiamond512-cell/Chat-GPT-Market-Report/actions/runs/41946722083), historical recovery [41946721805](https://github.com/matrixdiamond512-cell/Chat-GPT-Market-Report/actions/runs/41946721805), saved-source QA [41946721978](https://github.com/matrixdiamond512-cell/Chat-GPT-Market-Report/actions/runs/41946721978): all SUCCESS.
- Evidence level: E2 hosted isolated tests and workflow regression. GCS used a fake adapter in tests; real OIDC/WIF trust, IAM, GCS object/generation, production schedule and 08:00 issuance are NOT_RUN. PR #188 remains Draft/open/unmerged; no main, Docs, receipt, Pages, Secrets or schedule writes occurred.
