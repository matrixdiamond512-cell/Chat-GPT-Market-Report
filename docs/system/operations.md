# マーケットレポート配信システム 運用マニュアル
現行文書版：2.1｜改訂：2026-10-19 JST｜変更ID：DOCCTRL-20261019-HISTORY。過去に記載した「PRレビュー用」「未実装」「未解決」はその時点の履歴。現在の確定業務契約は本ファイル末尾の「現行差分統合 v2.1」と固定ID Google Docs v2.1を参照。GitHub main静的確認と実稼働成功は別判定。
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


## ARCH-20261020-REPORT-CONTINUITY｜新アーキテクチャ設計変更案（2026-10-20 JST、未承認・未実装）
本章は設計提案であり、現行v2.1の実行・正式公開・履歴・証拠ゲートを変更する発効規程ではない。Google Cloud・OpenAI APIのプロビジョニング、ChatGPTタスク設定変更、PR #165マージ、過去枠の証拠生成・正式昇格は未承認。段階的な受入・明示的な切替承認までは現行運用と発行条件を維持する。
### 設計案の運用手順（切替承認前は実行しない）
1. 準備: 運用者がGoogle Cloudのプロジェクト/課金予算/最小権限/Secret Manager・Cloud Scheduler・Cloud Run・Cloud Storage利用条件を確認。指定ChatGPT会話への投稿可否と代替閲覧経路を明示的に判定する。未解決事項を実装可能と表示しない。
2. 定時枠固定: 予定枠日時（Asia/Tokyo）、schedule event ID、sourceScheduleTime、reportIdを記録。遅延時は元のscheduledAtを保持し、nowからreportIdを再決定しない。
3. 事前取得: 市場データの出典、単位、限月、値・前日比・騰落率・方向・asOf、15分鮮度を照合。T以前の値だけをslot evidence候補にする。欠損を未確認ではなく取得不能（理由）で記録し、推測値に置換しない。
4. 証拠の固定: immutable storeにcreate-only保存。server createdAtとgeneration、bytes SHA、原本contextHash/snapshotHash/sourceHashを読戻し確認し、T後取得・T後新規固定なら非適格。GitHub main事前読戻しを別方式に置き換える判断は、正式に改訂された受入要件に従う。
5. 原稿作成: 証拠eligibleなら正式候補の原稿を生成。証拠未取得でも独立検証可能なデータがあれば閲覧専用draftを生成し、対象枠・実作成時刻・非正式状態と情報欠損を明記する。正式発行へ自動昇格禁止。生成不可のときはfailureStageを記録して再試行対象とする。
6. 保存と配信: Google Docs/PNGを対象月の正しい親へ保存し、ID/metadata/revision/全文及びPNG byte/hashを再検証。指定ChatGPT会話への本文/図解表示と通知到達を独立に確認する。Docsやポータルを閲覧可能にしても「指定チャットへの配信済み」とは報告しない。
7. 正式公開: 発行時evidence・Docs原本全文・revision・図解・receipt・canonical・reports.json/latest/dashboard・Pages live DOMを現行受入ゲートで検証。SOURCE_ARCHIVED等を自動昇格せず、公開の成功は必ずlive readbackで判定。
8. 障害処理: GitHub Actions遅延、T跨ぎ、外部スケジューラ重複、競合、欠損、Docs権限不足、PNG不整合、Pages失敗に応じてステータスのみを記録。以前成功した成果物を不必要に作り直さず、同一IDと同一ハッシュで安全に再開する。
9. 異常報告: 対象枠ごとにscheduledAt、actualStartedAt、取得、evidence、draft、chat、Docs、PNG、canonical、receipt、Pages、notificationの各SUCCESS/FAIL/UNKNOWN、URL、失敗理由をユーザーへ表示。「作成した」「保存した」「公開した」を混同しない。
10. 本番切替: 認証・課金条件、5営業日×4枠のE2E、障害注入、旧新重複公開防止、ロールバックを記録。正式な承認が出るまではCloud側の本番スケジュールを稼働させず、現在のChatGPTタスク・Apps Scriptトリガー・GitHub workflowを変更しない。
### 事故時の判定表
証拠だけ欠落→閲覧用draft作成可能（検証できた事実のみ）、公式公開BLOCKED。
ChatGPTタスク未起動→独立原稿/Docs/ポータル閲覧経路を検証、指定会話はUNKNOWN/FAIL、全工程VERIFIED不可。
Docs失敗→原稿保持・保存再試行、公式公開BLOCKED。
図解失敗→本文と画像を独立記録、全工程VERIFIED不可・正式公開は承認済みゲートを維持。
実枠T超過→T後新規証拠の後付け禁止、日時明記の非正式補充に限定。
GitHub push失敗→immutable evidenceを保持し、main読戻しによる照合後に安全に再試行。
### 未決・禁止
採用までの未決: 実行基盤の料金/権限、既存ChatGPT会話への自動配信API、正式保管先変更の承認、現行PNG必須ゲートと状態分離の競合解消。設計提案段階で、旧定期タスク、原本、履歴、正式公開ゲート、PR #165のマージ状態を変更してはならない。
