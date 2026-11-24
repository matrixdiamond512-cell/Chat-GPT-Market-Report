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


## PORTAL-CONTENT-COMPLETENESS-20261116-01（2026-11-16 JST）

両画面は `data/report-archive-manifest.json` の同じ保存本文一覧と `assets/js/report-archive-source.js` の表示専用アダプターを使用する。Doc ID/URL、revision、本文長、日時、出典フォルダーを確認し、形式差（fileId/revision/URL形式/BOM）で有効な本文を落とさない。元本文と正式公開状態を変更しない。後日再構成版は定時原本に昇格せず、参考価格と実測資金フローを混同しない。

Driveから10枠を追加回復し、保存本文91枠を検証。見出し別の主導市場・シナリオ・結論・時系列表示を修正。未取得値を推測せず、残る原本欠落5枠は `data/report-content-gaps.json` に記録する（10/20 08、10/22 12、11/04 08、11/06 08・12）。10/20 08と10/22 12は復旧メモ、11/06 12は空Doc。

検証：Nodeの対象20テストPASS（E2、実保存本文を使ったアダプター/選択/表示回帰）。公開ブラウザは変更前を観測。変更後の公開DOM・Pages反映はNOT_RUN。Google Docs固定ID文書への同期は未実施。定時配信・正式原本・receipt・スケジュールは本変更の対象外。


## 公開済み保存本文の全件・両画面監査｜2026-11-17 JST（PORTAL-ARCHIVE-DUALVIEW-AUDIT-20261117-01）

- 監査対象は固定91枠ではなく `data/report-archive-manifest.json` 内の全保存枠（2026-11-17時点で92枠）。基準数91未満への後退は異常とし、翌日以降に追加された枠も自動で対象へ含める。
- `scripts/validate_full_saved_archive_dom.js` はGitHub Pagesの公開JSONを元ファイルと一致照合し、全保存枠の `report.html` と `index.html` を実ブラウザで個別に開いて、指定日時・タイトル・本文表示・出典・正式公開優先順位・欠落状態の混同を検査する。数値の外部市場データ照合と正式発行証拠の新規作成は**実施しない**。
- `.github/workflows/full-archive-91-dual-view-audit.yml` はPR・手動・mainの監査コード変更時に実行し、通常のPagesデプロイが成功した後にも別ワークフローで読み取り専用監査を実行する。監査結果はJSONの各slot PASS/FAILと代替出典の選択件数をGitHub Actions artifactへ30日保存する。
- 初回公開画面監査の記録：2026-11-17 JST、GitHub Actions run `43906236040`、保存元92/92・本文画面92/92・ダッシュボード92/92・出典の取り違え0・失敗0（PR候補の検証）。最終mainへの反映後はmain上の監査を独立して確認する。
- 原本のない5枠は `data/report-content-gaps.json` のまま維持。正式発行status、receipt、本文・価格、Google Docs本文、PR #204/#206、Sheets/Cloud Runはこの監査で変更しない。

## REPORT-SLOT-WINDOW-20261117-01｜発行前証拠・市場取得の時間外起動時（2026-11-17）
1. まず対象workflowのGitHub Actions run ID、event.schedule、実開始JST、対象枠、実失敗step、stdout/stderrを採取する。2026-11-17のrun `43958040721` は06:14 JSTに21:00枠として起動し、実取得済みでも `acquisition is outside the allowed pre-draft cutoff window` で証拠固定に失敗した。
2. 市場取得が `BLOCKED_FUTURE_ACQUISITION_WINDOW` の場合は次枠までsleepしない。前日のcronの遅延を今日の将来枠に転用しない。証拠runが `BLOCKED_LIVE_EVIDENCE_OUTSIDE_PRE_SLOT_WINDOW` / `BLOCKED_LIVE_EVIDENCE_AFTER_SLOT` なら発行前証拠は未成立と報告する。
3. 既存の正常取得と正式証拠があるかGitHub mainを実読戻しする。欠落なら本文・Google Docs・参考閲覧保存を別工程で続行し、正式receipt/canonicalへ偽昇格させない。チャット主タスクの早期実行もユーザー可視本文無しなら未発行と判定し、15分後の復旧で同一枠だけを点検する。
4. 検証を分離：ユニット回帰、PR CI、main反映、次の平日4枠の発行前証拠読戻し、Docs、Pages DOM、PNG、通知。設定変更をもって定時発行成功と主張しない。

## REPORT-SLOT-QUEUE-20261117-02｜11月17日定時配信障害への対処と未解決（2026-11-17 JST）

1. 08:00証拠ワークフロー run `44019617757` は13:48 JST頃に実行され、`BLOCKED_LIVE_EVIDENCE_AFTER_SLOT` で停止。08:00 final refresh run `44019745595` は時刻外取得として拒否。時刻外の拒否は正当で、過去evidenceの再生成は禁止。
2. Google Docs importer run `44021644786` は `monthly_folder_access=False`、`REPORT_SOURCE_MISSING 2026-11-17 12:00` で失敗。Google Drive `マーケットレポート2026年11月`（folder ID `1vnZ7JgQTbqVSvoTIaY-1GlEroSzNLXkP`）の配信用サービスアカウント共有を、正当な所有者権限で付与し、次回の実runで直接子の読戻しを検証する。TEST_ONLYの別サービスアカウントを本番用と取り違えない。
3. 本修正ではデータ取得・証拠固定workflowsのconcurrencyを枠ごとに独立させる。各枠内の先行・予備・健全性jobの直列性は保つ。コードの修正はGitHub cronの起動保証、権限付与、正式レポート発行の証明とは別。
4. 受入はPR CI→main反映→実予定時刻のmarket latest/証拠main readback→Docs importer folder access→publication receipt→canonical/index→Pages DOMの順に個別確認する。未実証の段階を完了扱いしない。

## MR-STABILITY-REPAIR-20261117-03（2026-11-17 JST / 修正候補）
BLOCKED_MONTHLY_FOLDER_ACCESSでは管理者がsecretのclient_emailだけを安全に確認し、TEST_ONLYと区別した本番認証主体の共有権限を点検する。秘密鍵/JSONをログやチャットへ出さない。本文folder 1vnZ7JgQTbqVSvoTIaY-1GlEroSzNLXkP、PNGfolder 1h7ft4COBO2jcWVBMFeAKLr1Fq9sdBj58。importerは読取専用、保存producerの書込権限とは別。権限変更は事前承認後に管理者が実施し、本番SAで再読取して確認。過去枠の証拠を再生成しない。
検証: 新規7件を含む65回帰テストPASS（E1/E2）。本番SAのfolder読戻し・初期4枠・10営業日40枠は未実施。コード/CI成功を全面復旧としない。

## MR-DELIVERY-STABILITY-20261118-01｜定時運用・再発時確認手順（2026-11-18 11:58 JST）
1. 対象枠のGitHub main `data/report-evidence/<reportId>-r1.json` と取得時刻、現時刻<T、T-15分内の取得、reportSlot・source hash・context/snapshot不変性を検証する。取得連動workflow `freeze-report-evidence-on-acquisition.yml` のSUCCESS/NO_OPもbyte読戻しの有無で区別。
2. ChatGPT主タスクのcompletedだけでなく、実際のレポート本文全文・日時・時系列・6市場を確認。Docsは正しい月フォルダーの1件に保存し全文とrevisionを読み戻す。15分後復旧は既存PNGを完全一致ファイル名で検索し、ある場合は再生成・上書きせず、実体と品質を別判定する。
3. 定時健康監視 `check-scheduled-report-delivery.yml` が枠+45分で正式receipt/canonical/index/latest・図解READY/manifestを確認。PNGがあるだけ、Docsがあるだけ、Pages参考アーカイブが表示されるだけなら未達とする。コード検査は遠隔画像の実byteや視覚品質を保証しないため、別途Driveの画像byte/SHA、数値、文字切れ、本文と因果の一致を確認する。
4. 証拠欠損時は参考閲覧を維持しつつ正式receipt/index/latestへ偽昇格させない。GitHub cronが全て遅延した時は独立schedulerが必要。秘密鍵・JSONや本番権限を拡大しない。
5. 主な確認実績：PR #215/#216 CI PASS、main反映。11/18 12:00証拠はrun44226581259のNO_OP/main実byte読戻しPASS。4枠本番正式発行/図解QA/10営業日40枠は未受入。固定Google Docs同変更IDへ追記済み。

## MR-DELIVERY-STABILITY-20261118-02｜早期実行・公開整合（2026-11-18 12:11 JST）
1. ChatGPT主タスクはscheduled_for、実開始、実終了、ユーザー可視本文・図解、Docs保存を別判定。11/18 12:00のような約3分前の実開始と枠前終了は、completedでも正常定時配信とはしない。
2. 「閲覧用分析版」「遅延分析版」「非正式分析版」「正式公開保留」は正式publicationへの昇格を拒否、archive保全。証拠の事後補作やタスク内sleepで時刻保証を装わない。
3. dashboard.latestReportの独立marketData投影はroot側dashboard.marketDataと完全一致する場合だけ認め、正式reportの日時・本文・他フィールドの変更を認めない。PR #218 main 5420fed6600bda41aa8be45eae7eee8768242bdd、CI run44228487454/44228487434 PASS。
4. 早期起動自体はGitHubコードで修復できない。枠後の復旧と、正式発行の実証を分ける。4枠E2Eと図解品質は未受入。

## REPORT-PIPELINE-REDESIGN-20261118-01｜vNextの安全な導入・切替（2026-11-18 JST / 設計案・未実装）
1. 現行のChatGPT主タスク・15分後復旧タスク、GitHub Actions、Apps Scriptの実発行トリガーを棚卸しする。現行の運用を無断停止しない。原文・画像・receipt・アーカイブは保存し、既存の正常ロジックを再実装しない。
2. 新Controller・永続state・PNG renderer・Docs/Drive writerを別環境に実装。まず合成データで4枠、境界T-15/T、早期・遅延・重複起動、APIエラー、Drive権限拒否・重複、GitHub競合、Pages staleを模擬する。責任主体と監視ログを各工程で記録。
3. 本番書込用SA・Cloudプロジェクト/予算/外部APIキーはユーザー/管理者承認を得てから設定し、秘密鍵をチャットやGitHubに開示しない。データ取得後の本文/画像は完全一致の同一reportId・revision・hashでのみ公開へ進む。画像は一時sandboxだけに置かず保存プログラムから月別Driveへ直接アップロード・byte読戻し。
4. 新方式はまず影稼働とし、旧タスクや正式公開を二重実行しない。1枠の実E2E・全4枠の実E2E・10営業日40枠観測、本文/PNG/Docs/PagesとChatGPTチャットの表示を個別受入。外部APIから既存ChatGPT会話への自動投稿は未実証であり、技術的に接続できない場合は満足したふりをしない。
5. 本番切替は別途ユーザー承認後に実施。切替スイッチ・旧経路へのロールバックを保持。障害時はfail-closedでPARTIAL/BLOCKEDを通知し、既に成功した工程を再生成しない。


## MR-INFOGRAPHIC-DRIVE-20261121-01｜図解Drive保存障害の復旧手順（2026-11-21 JST）
1. 対象slotに対して主タスク・独立図解（+10分）・未発行復旧（+15分）の実行記録を確認し、`completed` と保存成功を混同しない。2026-11-20 21時枠は主タスクDocs/PNG未実行、独立図解がBLOCKED_FILE_REFERENCE、復旧はDocsのみ保存。Drive PNGは翌11/21 00:53に実存在を確認したため、定時保存はFAILと判定する。
2. `マーケットレポート図解YYYY年M月` の対象PNGを完全一致の名前で検索し、0件なら保存・復旧対象、1件ならfileId/親/MIME/実バイトを検査し、2件以上ならAMBIGUOUSとして停止。既存画像の上書きや別枠画像への差替えは禁止。
3. 新規図解を生成した同じタスク内で、実PNGパスからexportしたsource_file_refを`files__manage_library`で既存月別Drive folderへアップロードする（`overwrite=false`）。標準のGoogle_Drive upload_fileにローカルsandboxパスを渡して再試行しない。保存成功後は同一fileIdをGoogle Drive APIで再読取する。
4. 独立図解タスクがcompletedであってもPNG保存が0件なら、復旧タスクはその別タスクのsandboxを使えると仮定せず、競合がなく原本文が存在するときのみ復旧版画像を生成して保存する。本文外の情報を補わない。正式snapshot/manifest/receiptがなければ正式READYにしない。
5. +45分のGitHub Actions監視で `scripts/verify_drive_infographic_upload.py` の `DRIVE_PNG_VERIFIED`（PNG実体）と既存の `verify_scheduled_report_delivery.py --require-infographic`（canonical+receipt+manifest）をそれぞれ確認。前者のFAILを後者のSUCCESSで代用しない。故障した場合はmissing, duplicate, folder, bytes, auth の原因別に通知。
6. 単体実証: 2026-11-21テストPNGのGoogle Drive保存/再読取PASS、テストファイルはごみ箱。GitHubコードはPR #226。CI、main反映、次の08/12/16/21時全枠でのPNG保存、内容QA、Pages DOM、通知は未検証。GitHub監視だけでは画像生成やDrive保存そのものを実行しないことを明記。

## MR-DRIVE-SCHEDULE-DATE-20261121-02｜遅延実行と45分後復旧の運用
1. 定時監視の障害は、GitHub Actions作成/実行UTC時刻、cronの予定UTC時刻、対象レポートJST日付、実際の検索先フォルダーを照合する。`today()`の結果だけで障害日を確定しない。
2. 2026-11-21のGitHub Actions実ログ（run 44772805142）はGitHub時刻で16:23 UTC開始、直近cronは11/20 07:45 UTC（同日16:45 JST）。旧コードは11/21のPNGを検索して失敗。修正後は11/20を対象にする。
3. 45分監視はPNGが欠ける場合、競合実行・当該Docs本文を検査して同セッションで復旧PNGを生成し、exact source_file_ref経由Drive保存を試行。Drive読戻し確認を必須とし、復旧遅延を隠さない。
4. 本修正の単体テストPASSと本番マージだけで毎枠E2E成功とはしない。次の4枠で原本、PNG、Docs、manifest、公開DOM、通知を別々に実測する。

## MR-WATCHDOG-MIDNIGHT-20261121-03｜21時翌日遅延の扱い
- Github予定runが21:05〜21:30 JSTの枠で開始したのに翌日0〜数時台にずれた場合、`now.hour < 21` を根拠に成功終了してはいけない。実予定枠が特定できれば前日の21時報告を検査、特定できなければFAILEDとし通知する。
- GitHub Actions監視の成功はPNG Drive保存・実チャット配信・Pages DOMを代替しない。


## MR-AUDIT-CAPA-20261124-01｜独立監査Phase 0（2026-11-24 JST）

出典: ユーザー添付の是正指示書第8節および独立監査報告。基準main `579fa000fc84f6875f220962c5f17ea01138c68e`、作業branch `codex/audit-capa-phase0`。監査原文・是正台帳・実装順序・影響文書・承認操作・費用/リスク/rollback・AT対応は [是正台帳](../project-control/AUDIT_CAPA.md) に集約。NC-01〜07/RC-1〜5/AT-01〜12の原定義は保全原本を維持。

今回変更はPhase 0の証拠保全と計画記録。実装、本文/図解構成、平日4枠、production data、原本、トリガー、Pages設定は変更していない。ローカルと公開HTTPで旧dataAsOf/誤正常表示・SOURCE_ARCHIVED HTTP200を再確認、BTC対象回帰は2件中1FAIL。全suite/修正後本番/独立再監査はNOT_RUN。固定Google Docs同IDへの同期はアクセス検証未達でNOT_RUN。計画承認後に対象Phaseの実装と影響文書を同時更新する。関連Issue #103/#176/#205/#222、未マージPR #201/#204/#206と重複させない。新規PR未作成。


## MR-AUDIT-CAPA-20261124-01｜Phase 1A・1B ローカル実装（2026-11-24 JST）

ユーザーの「進めてください」により、Phase 1A/1Bのローカル実装・検証を承認。基準main `579fa000fc84f6875f220962c5f17ea01138c68e`、branch `codex/audit-capa-phase0`。関連 #103/#222、既存PR #201/#204/#206の取得/保存実装を変更しない。GitHub push/PR/main適用・Pages設定/公開・Drive/GAS/タスク/課金変更は未実施。

予定枠の鮮度を `config/report_schedule.json` から共有判定し、遅延/欠損時は `status=degraded`・`isStale=true`・理由と期待/公開枠を記録。同期のUPDATED/NO_OPは投影の変更有無であり、定時配信成功ではない。独立市場データの異常を保持し、同じ原本の再同期でも予定枠を再評価する。本文/図解の構成・分析項目、平日08/12/16/21 JST・土日なし、既存publication gateは維持。

Pagesは `config/pages_public_files.json` の静的ファイル一覧・限定した履歴collection・既存archive manifest・公開資格のあるcanonicalから組立。docs/scripts/apps-script/receipt/枠前証拠/診断用dataは既定非公開。公開ファイル追加は許可リストのレビューを必要とする。公開リポジトリraw/履歴の閲覧可否は別問題であり、Pages除外で解消したと主張しない。

ローカル検証と制約は `docs/project-control/AUDIT_CAPA.md` のPhase 1追補および `phase1-evidence.json` に記録。hosted CI、本番設定切替、変更後live Pages、固定Google Docs同期、通知実到達、独立再監査はNOT_RUN。固定Docs5件のmetadata読取404は権限/接続上の制約であり不存在の証明ではない。

### Phase 1検証と本番適用の境界

ローカル回帰: `python -m unittest discover -s tests -p test_audit_phase1.py -v`、既存のdashboard/publication eligibility/report contract/scheduled delivery/deployment verificationの関連回帰、`node --test tests/report-delivery-health.test.cjs`。Windowsのzoneinfoにはtzdataを隔離依存として導入した。テスト用固定時刻はfixtureに限定する。

本番適用前に現main/重複PR/固定Docs revisionを再確認し、許可リスト成果物の依存・除外をレビューする。Pages modeがlegacyなら新workflowは停止する設計。設定切替を承認した後だけ管理者がworkflowへ切替え、検証済みallowlist artifactを配信する。legacyへ自動復帰しない。失敗時は最後の検証済みartifactへ戻し、停止警告を保持する。公開リポジトリraw/履歴は別途公開方針の判断が必要。

本番SOURCE_ARCHIVED HTTP404と両画面live DOMを確認するまでAT-04は合格にしない。通知はPhase 1Cの別工程であり、今回の失敗検知CLIは通知到達を保証しない。固定Docsがアクセス不能の間は同期NOT_RUNを保持する。


## MR-AUDIT-CAPA-20261124-01｜Phase 1A・1B PR準備（2026-11-24 JST）

ユーザーのPR準備指示に基づき専用branch `codex/audit-capa-phase1ab` をmain `437a63c23bb7f979fd663c824dec1fa8a5941d1d` から作成。開始時31ファイルはPhase 0保全資料/台帳とPhase 1A/1Bに対応し、無関係な未コミット変更なし。元branchの履歴を保持、全31ファイルのSHA-256を切替後に照合。既存packed-refs.lockは変更せず、branch/HEADを独立確認。upstream変更11データファイルとの重複なし。

同じ60件Python/32件Nodeを再実行し合格。全テスト名・環境・ログは `docs/project-control/archive/independent-audit/pr-validation.json` と `pr-python-tests.log` / `pr-node-tests.log`。許可リストartifactは1,074ファイル、430参照を検査して新規欠落0。元sourceにも存在しないdata/reports.json参照2件は残課題として区別（pr-public-dependencies.json）。同じ60/32件と依存検査を既存health CIへ接続、新規の監視タスクは追加しない。

今回許可された外部操作は専用branchのpushと独立レビュー用PR作成。mainへのマージ、Pages設定/配備、Drive固定ID/原本、GAS/ChatGPTタスク、課金/権限拡大は実施しない。コード/文書のGitHub取得を受入とし、本番復旧や独立監査合格と表現しない。PR/最終HEAD/hosted CIの実測はPR本文とレビュー提出記録を参照する。


PR公開範囲追補（MR-AUDIT-CAPA-20261124-01 / 2026-11-24 JST）: 自動承認レビューにより原監査・詳細証跡・全ログの一括公開pushは拒否されたため、これらはローカルに保全してPR対象外とする。公開証拠はaudit-source-index.json（原資料のhash/既存Drive参照）、pr-validation.json（60/32件のテスト名・結果・環境）、pr-public-dependencies.jsonに限定。元の詳細ログ/phase0・phase1-evidence/棚卸しの記載はローカル保全記録であり、GitHub公開済みの意味ではない。コード・固定文書の修正範囲は不変。
