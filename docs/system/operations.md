# マーケットレポート配信システム 運用マニュアル
現行文書版：2.2｜改訂：2026-11-04 JST｜変更ID：REPORT-ARCHIVE-CONTENT-AUDIT-20261104-01。過去の「未実装」「未解決」状態は当時の記録。現在のポータル保存記録・slot選択・QA表示契約は本ファイル末尾の「現行差分統合 v2.2」と固定ID Google Docsの同一追補を参照する。
1. 編集依頼の対象文書を要件定義書/仕様書/マニュアルに分類し、Google Docs fileId・GitHubパス・版とrevisionを確認する。
2. mainにある実装、未マージPR、ドキュメントの提案、実際の稼働実績を分ける。配信システムと関連するWeb資料は同一プロセスの一部だが、他文書だけの更新を完了と呼ばない。
3. 発行前に設定ファイルと実際のChatGPT定期タスク・Apps Scriptトリガーを個別確認する。コードにトリガー関数があるだけでは稼働とは言えない。
4. レポート原文の表示、Drive保存とreadback、receipt、図解manifest・PNG hash、GitHub、公開前後DOMを各工程で検証。本文と図解の状態を別々に記録する。
5. 失敗時は工程を止め、原本欠損を推測で補わず原因を記録する。PR #94/97のDraft機能を本番の成功実績に算入しない。
6. 書込後に同一ファイルを読戻し、3文書に間違った反映がないか検証する。GitHub PRレビューを経ずにmain・本番トリガー・Pages deployを変えない。

## 2026-10-13 実検証で確定した事実
- 実ChatGPTタスクは平日4枠のみ有効。土曜日旧タスクは無効。Apps Script実トリガーは接続元から照会不可。
- PR #95/#96/#98/#99/#100はmainへマージ済み（2026-10-13確認）。PR #94/#97はDraft・未マージ。
- PR #94のMOF検証はSTALE_DATA閾値の限定修正後、Actions run 38298392598でSUCCESS。ただしSheets/本番updateはSKIPPED。PR #97はデザインテストPASS、本番公開未確認。
- 2026-10-12 21:00 のDocはGoogle Driveに実在。旧Receiptにはstrict validator必須のtitle/status/publisher/driveFileId/driveUrl/savedAtが欠ける。保存主体や日時を推測補完しない。
- PR #98の公開workflowへの直接Receipt検査追加は撤回。新旧スキーマ移行と実テストまでは本番導入禁止。

## 2026-10-13 最終照合
- PR #99はmainにマージ済み。現行スケジュールは平日08/12/16/21のみ、土日なし。
- PR #94の修正後Actions run 38298392598はSUCCESS。Draft・未マージであり、本番データ書込を検証したものではない。
- この文書に記載するPR #98のReceipt強制ゲートは撤回済み。Docs保存証跡の旧スキーマ移行が未完了のため、公開ゲートの新設を完了とはしない。

## 2026-10-13 追加再照合・継続作業（PR #100反映後）
- PR #98およびPR #100のmainマージをGitHubのmerged検索で再確認した。上の「実検証で確定した事実」に残っていたPR #98未マージとの記述を訂正した。
- PR #100が実装したのは旧Receiptの分類および誤認防止であり、旧データからpublisher/savedAtを推測して補完する正式移行ではない。
- PR #94: Actions run 38298392598でtreasury-validationおよび候補検証のジョブがSUCCESS。sheets-test/nikkei-sheets-test/treasury-sheets-test/updateはSKIPPED。28項目の本番取得・Sheets保存・読み戻し・公開は成功と扱わない。Draft維持。
- PR #97: 合成入力による描画テスト成功と、実レポート入力の検証・Drive readback・本番公開は別の証拠として記録する。2026-10-09/12実レポートの必須source snapshot/数値レジストリ等の不足を推測で補わず、正式検証は未完了。Draft維持。
- Receipt正式移行には、既存Google Docsの実体ID・保存時刻・発行者を独立に照合し、schema-version付き新Receiptを生成・readbackする統合テストが必要。旧Receiptの欠損値を補作しない。公開の強制ゲートは移行完了・回帰テスト前に有効化しない。
- Apps Scriptのインストール済みトリガーは、プロジェクトの権限付き実行環境で実トリガー一覧・所有者・直近実行履歴を確認するまで未確認とする。ソース上の定義と実際の定期実行を区別する。
- 発行設定はmainのconfig/report_schedule.jsonで平日08:00/12:00/16:00/21:00、土日なし。旧時刻はlegacyStoredSlotsで履歴管理。

## 2026-10-16 追補（DOCSYNC-20261016-RPT）
1. 4枠の開始前に市場データ取得（12時は既存11:30〜11:55・5分刻み）、T-13/T-7/T-3の発行前証拠、reportId・context・snapshot・元データhashをrun/file実体で確認する。証拠欠落が発行時刻を過ぎたら遡及生成禁止。
2. ChatGPTタスク起動は成功判定の出発点にすぎない。指定会話本文全文、図解、Docs ID・revision・全文読戻し、PNG保存、GitHub正本、receipt、Pages DOM、通知到達を各工程独立記録する。Apps Scriptのインストール済みトリガーは別途実画面のログで確認。
3. Doc原本がない場合は本文生成/Docs保存の上流を調査する。Google Docs→GitHub同期は原本新規作成をしない。runがNO_NEW_REPORTSなら発行成功と報告しない。
4. 補充版は実作成時刻と対象枠を区別して利用者へ本文先出し→Doc保存→読戻し。HISTORICAL_ARCHIVEで非正式閲覧可能だが、snapshot/receipt欠落を隠さず正式PUBLISHEDへ昇格させない。
5. ポータル6市場の「取得不能」は最初にDocs本文と照合する。値があればparser/表示UI/キャッシュを調査し、価格・時刻・市場・限月・条件分離を回帰テストする。図解には別日数値や未検証値を加えない。
6. PR #152/#153/#154の改修はmain導入済み。4枠ライブE2E・通知・ドキュメント/図解保存の全成功までは復旧完了としない。

## MRFOLDER-20261019-01｜月別フォルダー直接保存の標準手順（2026-10-19 JST）
1. 予定発行枠はJST平日08/12/16/21時。本文をまずチャットへ出力。実行遅延や復旧枠で対象日付・時刻をずらさない。
2. 本文保存先「マーケットレポートYYYY年M月」、図解保存先「マーケットレポート図解YYYY年M月」をそれぞれ特定。2026年10月は本文1qDOwDACdzWsGYcMaEobciDP3dFOdJ4Vz、図解1Ma24qcksen9Ufqz1wIUYqSTdYFfpok2w。未知の月はDrive検索、一意性・権限確認後、必要に応じフォルダー作成。同名複数なら中断し競合を報告。
3. 同じ日時の既存ファイルID、タイトル、親、Docs版/内容を確認。正本の上書き・削除をせず、競合候補は「同名ファイル確認待ち」へ安全に分ける。タイトルに作成日時を入れ、元枠日時と混同しない。
4. DocはGoogle Docsネイティブ形式で対象月フォルダーへ直接保存。図解PNGは別フォルダーへ直接保存。未生成画像を保存済みと報告しない。
5. 保存後はDriveから独立にmetadataを読戻してfileId、name、mimeType、parentIds、URLを記録。Docはrevision/全文照合、PNGは画像実体と対象枠を確認。親不一致は不成功と扱い訂正の上再検証する。
6. ユーザー報告は本文表示、Docs保存/読戻し、PNG保存/読戻し、正式receipt、GitHub canonical、Pagesを分け、成功したファイル名・保存先フォルダー・URL・fileIdを示す。保存・権限不足は理由を明示し成功と呼ばない。
7. ChatGPTの稼働中タスク「平日マーケットレポート・本文優先配信」のプロンプトを2026-10-19に更新。次回の実行でフォルダー配置・保存・読戻しを観測するまで「自動保存E2E=UNKNOWN」。配信時刻、復旧枠、公開ゲートは変更していない。


## 現行差分統合 v2.1（2026-10-19、DOCCTRL-20261019-HISTORY）

Google Docs固定ID `1OUVDAMjv009VWlI48Jb8TVuzszy4TIkjgBrHlzbNxYg` に対応する固定パス。文書内で変更日・版・管理IDを更新し、別名の最新版を増やさない。

1. 設定・実行の分離：config/report_schedule.json、ChatGPT定期タスク、Apps Script実トリガーを個別確認。平日08/12/16/21（JST）、土日なし。旧Apps Script本発行・再試行/watchdogは再作成しない。06:30市場取得系は独立。
2. T-13/T-7/T-3の発行前証拠を実run・snapshot/context/source hash・実時刻で読戻す。時刻後の証拠捏造禁止。expired/failed/unknownを区別。
3. 指定ChatGPT会話への全文、同枠図解、月別親へのGoogle Docs全文保存・読戻し、PNG実体、canonical、receipt、latest/index、Pages DOM、通知を独立確認。部分成功を配信完了と呼ばない。
4. 08時表の28行×5列/previous_close/日付/市場種別、12/16/21時の実出来事の時刻・発表・値動き、重要イベントのJST発表日時・夏冬時間・図解/本文一致を毎回チェック。
5. 検証済み価格が公開カードで「取得不能」なら、原文上書きではなく市場別抽出・JSON同期・HTMLパーサー・DOMキャッシュを確認。10/04のJS構文障害、reports.json形式、latest/dashboard不整合の再発を検査。
6. `close-sheet-integrity.yml` の欠損監査と検証済み履歴の空セルのみ補完、日付重複・既存値/式無改変・Sheets読戻しを確認。JP33業種/US11セクター、WGCとGLD/IAU、BOJスポット出来高と為替価格は基準日・集計範囲を分離して監査。
7. 10/16・10/19救済版は非正規アーカイブ状態を維持し、発行前証拠・原本・receiptを遡及復元しない。過度な告知バナーを再表示しない。
8. Google Driveには本文は`マーケットレポートYYYY年M月`、画像は`マーケットレポート図解YYYY年M月`へ直接保存。親フォルダー重複は停止、DocID/版/全文・PNG実体/parentIds・公開URLを別々に読戻す。My Drive直下への保存を成功と呼ばない。
9. ChatGPTタスクプロンプトのフォルダー指示更新は実施履歴、定時E2E/通知は未証明。別々の結果として報告。
10. 要件・仕様・本文作成・運用・文書管理台帳に影響する変更は同一変更IDで整合。影響先のポータルデータ取得や専門モジュールを「配信と無関係」として除外しない。


## DRIVESOURCE-20261020-01｜Drive同名ファイルの最新保存版とGitHub公開正本の分離（2026-10-20 JST）
- ユーザー指定の「同一日時・同一種別はDrive保存日時が遅い方」を、Google Drive createdTime の降順で判定する。modifiedTimeは編集・移動等で変わるため保存日時の代わりにしない。対象は18件のGoogle Docsと3件のPNG、計21対象日時。Drive月別通常フォルダーには各日時1件を残し、古い候補は「同名ファイル確認待ち」に保全した。
- GitHub `data/drive-source-selection.json` がGoogle Drive実測の選定結果を保持する。レポート画面のDrive保存版リンクと `drive-source-selection.html` はこの一覧を参照する。ユーザーに選定版のID・リンク・検証状態を示すが、**これはGitHubの正規発行原本を無条件に書き換える仕様ではない**。
- 最新保存版の本文18件のうち10件は構造・分量を点検可能、8件は空文書または短文。後者を既存の公開済み全文に上書きしない。前者も発行前snapshot、Google Docs revision/全文一致、原本revision、receipt、公開整合の証拠が揃わなければ既存canonicalは変更せず「正式公開保留」とする。後から発行前証拠を捏造しない。
- 図解3件はDrive上の最新保存日時・PNG MIMEを確認。GitHub Pagesでの画像実体、SHA-256、manifest、snapshot/本文との対応が未検証のため図解正式READYへ昇格させない。旧ファイルは削除しない。
- 公開ポータルの参照ページは正式公開と保存版の区別を表示し、公開中の本文全文・最新レポート・dashboard・receipt・公開ゲートを黙って切り替えない。E2E、正式canonical改訂、PNG正式公開の状態は引き続きUNVERIFIED/BLOCKEDと明記する。
- 変更確認対象：本書、上記3システム固定文書、`report.html`、`assets/js/report-drive-source-reference.js`、`drive-source-selection.html`、`data/drive-source-selection.json`。Google Driveの固定ID文書側の同期とライブPages確認は別工程として記録する。


## MRF-0800-20261029 — proposed 08:00 issuance verification

This procedure describes an unmerged Draft integration. Do not use it to write production Docs or publish a portal until separately approved.

- Before a run, confirm the report date/slot, one generation-pinned production evidence object, source/snapshot/context hashes, and a frozen G2 fullText/bodyHash. Do not substitute the TEST_ONLY objects recorded in PR #183.
- Confirm the independent reviewer approved all three panel-12 scenario roles with exact body offsets and quotes, including the main/alternative branch and a concrete decision-changing invalidation trigger.
- Confirm the target monthly Docs folder ID and parent identity. The writer rejects duplicate titles, altered appProperties, a different existing body, and incomplete creation. Never clear a slot claim or create a replacement Doc without reconciliation.
- After save, record actual Docs ID/revision, exact full-text readback/hash, and Drive timestamps. The transaction stops unless the readback is text-exact to the frozen source and inside the configured slot window.
- Only then run the established importer and portal publication workflow. Verify canonical report, receipt, dashboard/latest projection, Pages deployment, and public DOM independently. Do not treat Docs save or fixture adapter PASS as publication.
- On any mismatch, stop before the next side effect, retain the claim/evidence, preserve diagnostics without logging report text or credentials, and escalate for identity reconciliation. No backfill or later-snapshot substitution.

External setup still required: production GCS evidence/claim IAM, approved Google OAuth/ADC scope and monthly-folder ACL, a trusted and authenticated G2/scenario-review producer, and a safe invocation/readback route for the existing importer/Pages workflow. These were not configured or exercised by this PR.


## MRF-0800-20261029 — existing portal handoff status

- Save the Drive file with source name `マーケットレポート_YYYY-MM-DD_08-00`; keep the separate report title on the first line of the body. Before saving, pass the same `validate_saved_body` contract used by the importer.
- The existing importer only sees slot evidence present in its checked-out repository path `data/report-evidence/`. Do not assume the PR #183 GCS bucket is reachable by that workflow; no GCS-to-importer handoff or WIF identity is configured by PR #188.
- Do not dispatch `publish-saved-google-docs-reports.yml` as a test: its apply path commits canonical report files to main and dispatches Pages. It requires a separately approved, evidence-bound staging or production operation.
- Current proof stops at offline Docs/portal adapter contract tests plus TEST_ONLY GCS evidence capture. Existing importer execution, canonical main readback, Pages deployment and browser DOM readback are NOT_RUN.



## MRF-0800-20261029 — local TEST_ONLY importer handoff

1. Keep the current PR checkout as the handoff tool, then create a second isolated checkout of the same PR branch in a sibling directory. The two checkout roots must be disjoint: neither may be an ancestor or descendant of the other. Do not use the main checkout as the staging root. The resolved evidence destination must remain inside the staging root; symlink or junction escapes are rejected before directory creation.
2. In the second checkout, create `.market-report-staging.json` with `schemaVersion: 1`, `mode: LOCAL_STAGING_ONLY`, `environment: TEST_ONLY`, the expected `report_id`, and `revision`. Do not place credentials in this file.
3. From the handoff-tool checkout, run `python -m scripts.reporting.importer_handoff` with `--staging-root`, TEST_ONLY project/bucket identifiers containing a standalone `test` token, an object name under the exact `test-only/` prefix, immutable generation, SHA-256, date, revision, and expected snapshot ID. Substring matches do not qualify. Accept only `LOCAL_STAGE_READBACK_PASS`; it records no publication status.
4. For a Docs read-only dry run, run the importer with `--root <second-checkout> --require-issuance-binding` and the existing read-only Docs credentials. Missing/mismatched appProperties must remain held. Review the dry-run output before considering `--apply`; apply modifies only that isolated checkout and must not be pushed or used for Pages.
5. Never dispatch `publish-saved-google-docs-reports.yml` for staging. It writes canonical files to main and dispatches Pages. No Google Docs write is part of this procedure.
6. The 2026-10-28 viewing/analysis document lacks a supplied pre-save G2 body/hash and same-run receipt. It cannot satisfy official issuance acceptance even if TEST_ONLY evidence is staged.

Current validation covers mocked exact-generation reads, create-only readback, identity/hash conflicts, and strict Docs binding. GCS/IAM, real Docs metadata, importer runtime, canonical readback, and portal/Pages remain NOT_RUN until independently observed.


## MRF-INGESTION-20261030-01｜取込ログの運用判定（2026-10-30 JST）
- CANONICAL_SOURCE_INGESTION_COMPLETE: sourceをappend-only canonicalへ取り込んだ。正式公開の証明ではない。
- SOURCE_ARCHIVED_ONLY: publication evidence/receiptが揃わず閲覧用archiveに保持した。公開成功として扱わず、後付け証拠を作成しない。
- DOC_READBACK_RECEIPT_RECORDED: Docs読戻しreceiptを記録した段階。Pages deploy・公開DOM・通知の確認は別途必要。
- ARCHIVED_SOURCE_PROMOTED_TO_CANONICAL: 既存archiveのcanonical状態をevidenceに基づき更新した段階。公開URLの確認は別途必要。
- Importerが最後まで実行したこと、canonical projection consistencyが通ったこと、Pages/public DOMが対象reportIdと一致したことを一つの「publication verified」へまとめない。
- この変更では本番Pages deploy、Google Drive書込み、既存report/receipt変更、スケジュール変更を行わない。

## DELIVERY-CLOSEOUT-20261101-01 — 保存本文の取込確認

- Docs取込前のsource validationで `01｜見出し` 等の明示番号見出しと、同一行に本文が続く明示的な結論ラベルを認識する。未ラベルの文を見出しとして推測しない。
- 不足判定が出た場合は保存原文の全文と見出し/body境界を調査する。過去本文の書換え、発行後Evidenceの補完、再発行昇格を行わない。
- 実装・5件のparser回帰テストは統合candidate上の検証。既存Docsの読戻し、正本登録、Pages公開および公開DOM一致は別工程であり、この変更だけでは成功としない。

## DELIVERY-CLOSEOUT-20261101-01 — 回顧アーカイブ検証

2026-10-16 12:00/16:00/21:00の回顧資料は通常の発行記録として扱わない。`scripts/validate_report_recovery.py` が原本未発見、回顧区分、および固定記録日時を検証したPASSを確認する。検証器の変更をPages workflowで実行する。統合candidateでは31件の保存本文・アーカイブ区分検証がPASS。公開DOMは別に確認する。

## 2026-11-04 現行障害対応・公開検証手順 v2.2｜REPORT-ARCHIVE-CONTENT-AUDIT-20261104-01
1. 画面の要求date/time、タイトル、選択ボタンを記録。Networkで `dashboard.json`、`reports.json`、`data/report-archive-manifest.json`、各archive JSONのHTTP statusを確認する。
2. manifest entryと個別JSONのschema、slot、本文、archive/source statusを検証する。取得失敗は対象path/date/time/statusを記録し、取得できたデータは表示する。一部失敗警告と全件失敗エラーを区別する。
3. 同一slotに正本と保存記録があれば正本優先。指定slotがない場合は欠落状態を確認し、他日時の本文が表示されないことを確認する。
4. 検証失敗recordは除外理由を残す。verifiedAtSlot、originalReportStatus、保存元本文/価格を手修正してはならない。正式証拠不足は閲覧記録として区別する。
5. 08:00は28×5の品質結果を確認。不合格なら画面に警告があり対象表が非表示、本文と保存statusは保持されることを確認する。既存のRECONSTRUCTED_UNVERIFIED quarantineは維持する。
6. 日付と時間帯の実在slot、URL date/time、本文見出しを照合する。11/02・11/03、10/30 21:00、日付移動、欠損slot・重複slotを自動テストと実ブラウザで検査する。
7. JS変更のcache query version、Pages deploy結果、HTTP/DOM、公開本文を読み戻す。古いキャッシュは確認後にcache bustする。原因確認前にdeployを繰り返さない。ログにtokenや認証情報を出さない。
8. 2026-11-04実績：68slot/18日分を公開ブラウザで照合。10/06 08:00 QA未達の警告表示・市場表抑制・本文維持を確認。Pages run 41836815631 SUCCESS。価格全件の外部ソース照合は対象外。
9. 未解決原本：10/22 12:00本文欠落、11/02 12:00状態メタデータ矛盾。元証拠を確認するまで発行状態を変更しない。

## MR-ISSUANCE-CONNECT-20261104-02 — controlled issuance adapter

Do not run the production adapter as part of PR CI or from a developer checkout. Production execution requires GitHub Actions on `refs/heads/main`, an independently protected environment supplying `REPORT_ISSUANCE_APPROVED=true` and explicit `REPORT_ISSUANCE_WRITE_ENABLED=true`, a least-privilege Docs/GCS identity for the same already-approved evidence/G2/Docs flow, `REPORT_ISSUANCE_GITHUB_TOKEN` capable of contents write plus Actions read whose GitHub-authored commit starts the existing Pages-on-push workflow, and the correct HTTPS `REPORT_PAGES_BASE_URL`. No credential or environment was configured by this change. The GitHub token must never be printed.

On a failed attempt, record stage, completed stages, commit SHA if observed, report/revision/body hash, receipt hash, Pages run ID and public URL, excluding secrets and report body. Before retry, reconcile main and receipt against the exact report identity. A Pages failure after verified canonical readback is retryable only after confirming the exact canonical and receipt still match; uncertain ref update/readback requires operator reconciliation. `PUBLISHED` requires public JSON body/hash readback, not a green deployment alone. TEST_ONLY CI remains distinct from production E2E.

### Controlled 08:00 entry and preflight

1. Keep the existing recurring task and four slot times unchanged. A declared trusted producer must create and freeze a G2 bundle before Docs save with reportId/revision, body SHA-256, frozen_at, human scenario review, evidenceId/snapshotId, and exact `evidence_ref: {"object": "...", "generation": <integer>}`. The producer adapter is implemented in this PR, but no existing task invokes it and no trusted GCP identity is connected; an existing Drive Doc is not a substitute.
2. On an authorized protected main Environment named `report-publication` only, run `python -m scripts.reporting.issuance_preflight` first. It also requires protected `REPORT_ISSUANCE_ENVIRONMENT=report-publication`. Inspect each check, including Environment reviewer count, Pages workflow, repository push access, Docs folder capability, exact Evidence generation, and the read-only claim-bucket permission probe. GitHub cannot expose the fine-grained token's exact contents-write grant through read-only APIs; until an authorized administrator has independently confirmed it and set protected `REPORT_ISSUANCE_CONTENTS_WRITE_VERIFIED=true`, the preflight remains `NOT_READY` and the production publisher also blocks.
3. The consumer can read a local bundle for input validation or an exact GCS G2 generation using `--g2-bundle-object`, `--g2-bundle-generation`, `--report-id`, `--revision`, `--evidence-object`, and `--evidence-generation`; production handoff must use the trusted producer's pinned GCS object. The CLI then reads the exact Evidence generation. Missing producer provenance, owner mismatch, or incomplete target inputs blocks. `--help` remains credential-free. A `BLOCKED` result is not success.
4. Before retry, compare canonical, receipt, and publication indexes byte-for-byte. A mismatched or one-sided pair, stale main with nonidentical files, or main ref update conflict requires reconciliation. Never overwrite an official report. An exact complete file set may be reused, after which the matching Pages run and actual rendered public page still must be checked.
5. Fixture CI keeps the site's existing `reports/` canonical files because archive/renderer code loads those siblings; it then builds `reports.json` as the public index array (`[report, ...]`) and adds the matching `reports/<reportId>.json` target. Chromium validates the isolated site. The validator requires a unique matching reportId and exact revision, date, time, fullText SHA-256, and rendered DOM. In production the Pages verifier runs the same script in public mode after JSON readback, fetching the actual HTTPS page and `reports.json`; unavailable Node/Playwright/Chromium or any identity/body mismatch blocks `PUBLISHED`. Fixture PASS does not establish production DOM success.

Preflight and CI do not configure protected Environments, create credentials, grant Drive/GCS/GitHub permission, modify the recurring task, write Docs/main, deploy Pages, or establish production E2E. Those require the existing independently authorized identity and operator approval.\n\n## MR-ISSUANCE-PRODUCTION-READINESS-20261105-01｜運用準備・未実施\n- main=d5db82e9bf88657b612ec41a471124b6c343cf84、PR #188 head=e5b967b3ead9a8c0e503f8251a38ec78edf1ea46を確認。mainのみの差分は本番配信コードではなくデータ/履歴であるためPRブランチへコピーしない。mergeabilityを維持し、意図しない履歴置換を避ける。\n- 08:00本番E2Eの開始条件：G2生成元が同一reportId/revision/evidence ID/snapshot ID/body hashを含むbundleをfreezeして受け渡すこと、管理者がreport-publication Environmentのrequired reviewersとbranch restrictionを設定・実確認すること、issuer identityとGCS evidence/claim, Docs月フォルダー, GitHub canonical/receipt, Pages/DOM読み取り権限を確認すること。\n- 試験は未来の営業日08:00枠1件に限定。Evidence/G2 freeze→Docs create/readback→strict import→canonical create-only commit→receipt readback→Pages deploy→JSON+DOM全文照合の証拠を同一run IDで保存し、工程ごとに結果とretryableを記録する。不一致は停止し、既存本文を上書きしない。\n- 本番Docs/GitHub/Pages書込み、merge、Secrets/Environment変更、定時タスク変更は未実施。固定ID Google Docsへの文書同期も未実施。

## MR-ISSUANCE-PRODUCTION-READINESS-20261105-01｜CI証拠追記
- CI code head 5538a8707f2179fcabde9ea5b4fa32239664a00e でissuance integration contract PASS：83 Python tests (17+39+16+11) とcompile/CLI smoke。https://github.com/matrixdiamond512-cell/Chat-GPT-Market-Report/actions/runs/41875493256
- isolated UI/DOM PASS：https://github.com/matrixdiamond512-cell/Chat-GPT-Market-Report/actions/runs/41875493440。その他8件も同じheadでPASS。これはActions隔離環境の結果で、本番Docs/GCS/GitHub canonical/receipt/PagesはNOT_RUN。
- main f43cc00f60d5a32fa96fa6cb4de440c7f971fc4a を2親同期commitに保持。main-only data/history変更はPR側の変更パスと重複なし。Google Docs固定IDへの同期はNOT_RUN。

## MR-ISSUANCE-ENTITY-20261105-02 — owner transition and G2 source

Source code defines Apps Script 08:30 handlers (autoPublishMarketReport0800/master 0830 path) that read existing Google Docs and publish the formal report. This is not a G2 freezer. The installed trigger list, task history, and external ChatGPT schedule remain UNKNOWN. No new timer or existing task was edited.

The PR adds a consumer for an exact pinned GCS G2 generation and explicit target identity/evidence reference. A genuine producer is still missing, so the production path remains BLOCKED_G2_PRODUCER_MISSING; do not create a test body or promote an existing Doc. Current ownership config stays apps_script_legacy for all slots. To transition 08:00 later: deploy and verify the Apps Script fail-closed guard while legacy remains owner; reconcile installed triggers and ensure no 08:30 run is active; confirm G2 producer provenance and protected Environment; approve an ownership-config update to g2_issuance_cli; then use one separately approved future slot and retain the full acceptance evidence. The other three slots remain untouched.

Merging this PR will also push report.html, assets/**, and a Pages workflow change. The existing deploy-pages.yml push/path filters include those paths, so a merge to main starts a Pages deployment workflow. Deployment and github-pages Environment approval have not been inspected or run here. Plan approval and monitoring before merge; do not treat CI success as deployment approval.

### MR-ISSUANCE-ENTITY-20261105-02 — current blocker and rollout order

Source inspection found Apps Script `buildWebReportFromGoogleDoc_()` reads an existing Google Doc and `publishMarketReportSlot_()` sends it to the legacy GitHub publisher; it does not freeze a G2 bundle or bind pre-save Evidence. The source declares an 08:30 main/retry path. The installed trigger inventory/history and external ChatGPT task settings are UNKNOWN. Current ownership config is apps_script_legacy for all four slots, so the CLI cannot own 08:00.

The preflight now keeps overall status NOT_READY unless a trusted G2 producer is implemented and registered, even if a supplied pinned object has matching content. Safe transition order: deploy/test the Apps Script guard while legacy remains owner; inspect installed triggers/history and ensure no old 08:30 attempt is active; establish producer identity and protected Environment/least-privilege access; separately approve the owner change; then run one future 08:00 slot through the protected path. Do not touch 12:00/16:00/21:00.

PR #188 changes report.html, assets and deploy-pages.yml, which match the existing main push/path filters. Merging it starts the Pages workflow. No Pages deployment or github-pages Environment approval was inspected or run; plan an authorized deployment review before merge.


Code/test evidence: on `642a5d104fa7adc212d4b136a943d0a0a34f6c96`, the 08:00 suite passed 95 Python tests (17+39+16+16+7), compile and CLI smoke. All ten related Actions passed. This demonstrates only automated contract/fixture checks. The producer adapter has no live task caller or configured writer identity; production preflight is NOT_READY with BLOCKED_G2_PRODUCER_MISSING. The exact evidence and run IDs are in the project-control evidence ledger.

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

ChatGPT定時タスクの生成本文をこの実行環境から取得するコネクタ/APIは確認できていないため、TrustedG2BundleProducerは呼出し可能なアダプターであり、タスクへ実接続済みの生成主体ではない。既存taskは08:00開始とされ、task出力が08:00〜08:40内に人手レビュー・freezeされれば新時刻契約には適合するが、実出力・完了時刻は未確認。

実運用代替案は二つある。第一案は、本文を生成する既存ChatGPT taskを維持し、運用者が本文/revision/reviewを非公開の承認済み実行環境へ受け渡し、protected workflowがEvidence generationを読んでG2をfreeze/storeし、そのgenerationを発行CLIに渡す手動運用。早期の限定試験に向くが、手動受渡し記録が必要。第二案は、taskがOIDC/Webhookを実際に出せることを確認した後、専用の受信実行主体を作り、その主体がWIFで同じproducerを呼ぶ自動運用。taskのWebhook能力が未確認で、追加serviceの保護・費用確認も要るため現時点では実装可能と断定しない。公開GitHubのdispatch inputsへレポート本文を直接貼り付ける方法は監査イベントへの本文露出があるため採用しない。

### 08:00 ownerの切替条件

Git上のApps Scriptは08:00枠を含むDocs→GitHub発行コード/08:30付近のretry handlerを定義する。これは実際のApps Script deployment、installed trigger一覧、 timezone、直近実行履歴の証拠ではない。実状態はUNKNOWN。owner configは08:00をapps_script_legacyのまま維持し、新CLIは競合ガードにより発行を停止する。切替は承認後、(1)現行deployment版・trigger/last executionを読取り確認、(2)08:00旧triggerと08:30 retryのみ停止し12/16/21を維持、(3)停止状態を再読戻し、(4)08:00 owner configを新方式へ変更、(5)protected新方式を起動、(6)未来の08:00 slot 1件を承認付きE2Eで照合、の順とする。確認できないtrigger/historyはUNKNOWNのまま所有権を切り替えない。

## MR-EVIDENCE-GCS-WINDOW-20261105-01｜Evidence freeze運用・障害分類
1. workflow実行開始時に明示report date/slotの組をJSTの15分窓で確認する。窓外は市場データ取得、GCS保存、GitHubミラー更新より前に停止する。GitHub Actions scheduleの遅延を、次の日の同slotとして再解釈しない。
2. 同一workflow内で現在枠のデータを検証し、Evidenceファイルを一度だけ生成してGCSへcreate-only保存する。その後、実際のgenerationを指定した別読戻しで本文・SHA-256・slot識別子・作成時刻を照合する。最後に同じ本文とGCS generationを指す監査用GitHub mirrorを作る。
3. GitHub mirrorだけが残った同一run内の部分失敗は、枠の15分窓内で保存済みbytesの時刻と内容を検証後にのみGCSへ再試行できる。GCSの作成済みobjectだけ残った場合は同一generationを読み戻してmirrorを再構築する。衝突や内容違いは `BLOCKED_GCS_EVIDENCE_CONFLICT` で停止し、削除・上書きしない。
4. 失敗分類は、履歴上runが見つからない場合 `SCHEDULE_NOT_OBSERVED`、遅延/窓外 `SCHEDULE_LATE`、入力の日付/slot違い `INPUT_SLOT_MISMATCH`、鮮度不足 `INPUT_STALE`、取得不能 `ACQUISITION_FAILED`、GCS/読戻し/mirror保存失敗 `EVIDENCE_WRITE_FAILED`。再試行は同一slot・同一bytes・窓内に限定する。
5. 2026-11-05 08:00枠の既存欠落Evidenceは後生成せず、参照/閲覧用Docsのままとする。Actions scheduleの稼働保証はなく、GCS接続、権限、実generation読戻しは本番preflightおよび承認付き試験までNOT_RUN。


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

## 2026-11-05 protected preflight運用手順（MR-PROTECTED-PREFLIGHT-WIF-20261105-01）
- 管理者は既存report-publication Environmentにrequired reviewersを設定し、Environment変数REPORT_ISSUANCE_WIF_PROVIDER、REPORT_ISSUANCE_READONLY_SERVICE_ACCOUNT、REPORT_EVIDENCE_PROJECT_ID、REPORT_EVIDENCE_BUCKET、REPORT_ISSUANCE_CLAIM_BUCKET、REPORT_ISSUANCE_DOCS_FOLDER_ID、REPORT_ISSUANCE_ROOT_FOLDER_ID、REPORT_ISSUANCE_G2_PRODUCER_SERVICE_ACCOUNT、REPORT_ISSUANCE_G2_BUNDLE_BUCKET、REPORT_PAGES_BASE_URLを設定する。
- 専用Google identityには対象Evidence/G2 generationの読取、Drive folder metadata読取、必要なAudit Logs読取、claim bucket権限の読取検査だけを付与する。service-account JSON keyを作成・登録しない。
- 最初にconfig modeを確認し、設定後はmainのprotected Environmentを通るauthenticated-readonlyだけを実行する。approval環境変数では承認済みとみなさない。preflightはGoogle Docs、Evidence、canonical、receipt、Pagesへ書き込まない。
- 本番設定・認証・権限はNOT_RUN。修正コードとCIのPASSは本番稼働成功を意味しない。
