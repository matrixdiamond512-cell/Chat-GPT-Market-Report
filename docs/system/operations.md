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

### 受領・欠落・再試行

1. 現行ChatGPTタスクを保持する。ユーザー確認では「平日マーケットレポート・本文優先配信」が有効。タスク/会話IDはローカル監査ログに保持し、実行履歴の独立取得は未了。11/11 16時の本文表示と下流未達はユーザー確認情報として分類する。
2. 生成時は本文を先に確定し、同一原本から各時間帯の独立図解を作る。必須項目・実出来事・6市場・時点/出典を省略しない。公式な自動引渡しを実証できなければ、人による内容確認/引渡しを境界として記録。自動投稿・無人生成を実施したと書かない。
3. cost gateを実行し、受領済みの実原本だけをbundleに置く。`python scripts/verify_zero_cost_delivery.py` はローカルのみのPASS。`--production` はaccount quota/billing/rights/ownership未確認のためBLOCKEDで終了する。本番を有効化するスイッチはない。
4. `python scripts/run_report_delivery.py --report-id 2026-11-12_08-00 --source-bundle logs/zero-cost-delivery/actual-source-bundles/2026-11-12_08-00` のように対象を明示。成功exit 0でもSHADOW_STAGEDまで。exit 2の欠落/不正理由を保存し、原文や数値を編集して無理に通過させない。
5. 検証不合格/途中失敗後は同一原本で再実行。同revisionで違う内容、格納済み実体の欠落は自動修復せず競合を確認。新revisionは正規の改訂手続きと原本証拠が必要。別枠から入力を流用しない。
6. `logs/zero-cost-delivery/` に今回の取得時刻、全文/ハッシュ、cost gate、テスト、公開HTTP/DOM観測、shadow実測を保持。`logs/` はGit追跡外。公開PRへ会話情報/アカウント情報/無審査の市場本文を混入させない。

### 切替と戻し（未実施・事前条件付き）

- コード上のwriter/呼出元/cron/credential名とWeb参照は固定 `docs/project-control/DELIVERY_PATH_INVENTORY.json` に記録。静的候補は実行証明ではない。旧GAS導入版/実トリガー・権限主体・履歴を確認し、予定slotごとの停止対象と所有者を確定するまでは旧writerを無効化しない。市場データ/専門分析ページの系統を停止対象にしない。
- まず外部非本番の固定保存先/URLと費用上限を独立確認して、4枠の原本→保存→読戻し→単一publisher→公開後QAをshadow受入する。実原本が欠けた11/12の補充版を当日定時証拠へ昇格させない。現時点では非本番Drive/公開アダプターも未接続。
- 本番切替前に同一reportIdの全writerに共有所有権/停止確認を適用できる実装をレビューし、旧経路が書けないことを確認。新旧同時書込での試験は禁止。今のlegacy所有権設定は宣言のみで既存GASを制御できないため、設定値を変更するだけの切替は禁止。
- 切替候補SHA、旧所有者/設定/トリガー、原本ID/版、最終正常receipt、再開位置、戻す担当者/手順を事前記録する。切替後は5営業日20枠の実本文/PNG/保存/DOM/通知を工程別観測。失敗で計数を再開。
- ロールバックは新writerを停止・停止確認→旧所有者を一つだけ復元→同一原本/receipt/公開pointerを読戻す順序。過去のcanonical、receipt、枠前証拠を巻き戻したり後付けしない。現在のshadowは本番writerを持たないため、実運用の切替/ロールバック成功はNOT_RUN。

### 無課金の確認範囲

GitHub APIで対象repoはpublicを確認。標準runnerのpublic実行は現行の[GitHub料金説明](https://docs.github.com/en/billing/concepts/product-billing/github-actions)で無料、larger runnerは別料金。今回の候補に有料runner/新schedule/追加依存/請求設定はない。保存枠/将来条件まで無制限とは扱わない。

[Google Docs API limits](https://developers.google.com/workspace/docs/api/limits) はproject毎分read 3000/write 600、user毎分read 300/write 60。 [Drive API limits](https://developers.google.com/workspace/drive/api/guides/limits) は標準利用無償だが将来の超過課金計画を明記し、日次project thresholdも定義する。現在のプロジェクト課金状態/使用量は未確認のため外部本番アダプターはBLOCKED_COST_UNVERIFIED。単なる無料枠存在を安全な課金上限の代わりにしない。

[ChatGPT公式の定期タスク説明](https://learn.chatgpt.com/docs/automations)は利用可能な接続ツールと会話内タスクを説明するが、今回のアカウントで指定会話/画像/保存を全自動保証する証拠ではない。公式手段が一般に不存在と断定せず、CAPABILITY_BLOCKED（当環境の未実証）とする。

公開市場データのURLが無料閲覧できることと再配布許可は別。[JPX利用条件](https://www.jpx.co.jp/term-of-use/)は二次利用/再配信の許諾条件を定める。既存Yahoo/Stooq/日経/Cboe等も対象データ別の利用/再配布条件が未確認。新しい取得源・再配布・有料代替は導入せず、権利/費用不明の新公開はブロックする。既存の市場取得を本作業で停止/起動しない。


### MR-ZEROCOST-20261113-01｜本文作成マニュアル・実タスクへの追補候補（適用保留）

既存タスク/正本を勝手に更新しない。以下は経路切替受入後、固定ID本文マニュアル/図解マニュアルを読める認可主体が必要差分だけ適用するための候補であり、実タスクへ反映済みではない。

> 平日の08:00・12:00・16:00・21:00 JSTは、承認済み詳細本文1本と同枠の独立図解1枚を成果物目標とする。「図解を作成した場合のみ」という任意条件で全工程成功としない。本文を確定した後、同一reportId/revision/snapshot/bodyHashから図解を作る。08時本文28行×5列・図解16項目、他枠の基準図/実出来事時系列・6市場を維持する。追加課金が生じるAPIは使わない。生成/表示/保存/引渡しが実行できなければ、当該工程をBLOCKED/未達として記録し、実行できた工程の実物を示す。本文をまず指定会話に表示する現行目標を保持し、人が確認・引渡しした場合はその主体と実時刻を明記する。receipt/枠前証拠/過去の保存時刻を補作しない。


## MR-SOURCE-HANDOFF-20261113-01｜非本番の実保存・原本受渡し境界（2026-11-13 JST）

非本番の実保存試験を実施：`マーケットレポート配信検証（非本番）` に `原本受渡し・保存試験（非本番）` を保存し、Doc ID・親・全文SHA・Docs revisionを読戻した。これは本文コピー保存の成功で、当日定時発行やChatGPT会話からの自動引渡しではない。

当面の一本の運用境界は、生成元の指定ChatGPT会話で本文/図解を確定し、同会話の公式Drive actionで保存するか、人が確認した原本を既存connectorへ引き渡すこと。別会話のCodexから指定ChatGPT会話を非公式に抽出しない。タスク有効表示・一般的なconnected tools対応だけで同会話のwrite権限を推定しない。

原本を受け取った後は、文字を編集せず入力SHAを先に記録→対象非本番親へ保存→metadata/全文/revisionを読戻す順序。TXT→Docs変換は末尾改行が増える実測あり。不一致なら停止し差分/版を保存。新規試験Docの余分な1文字と確定した場合だけrequiredRevisionId付きで修正し、再照合する。元Doc/正式原本の無断編集やhash基準緩和をしない。

生成元会話側のGoogle Drive保存actionの有無/失敗ログは確認待ち。原本TXTと実PNGの受領前に正式bundle/receiptを作らない。PNG未取得のため保存試験もNOT_RUN（別の画像を図解として代用しない）。現在のタスク/Google正本は保持、切替/公開/通知の受入は保留。

[ChatGPT公式タスク説明](https://learn.chatgpt.com/docs/automations)はweb taskが会話のconnected toolsを使える旨を説明するが、対象タスクが今回の保存actionを実行できる証拠ではない。今回のDrive標準操作は[Google Drive APIの標準利用無追加料金という説明](https://developers.google.com/workspace/drive/api/guides/limits)の範囲で既存接続だけを使用し、AI API/課金設定/利用枠引上げを導入しない。将来の超過課金やアカウント全体の本番無課金まで保証したとは扱わない。
