# マーケットレポート配信システム 要件定義書
現行文書版：2.2｜改訂：2026-11-04 JST｜変更ID：REPORT-ARCHIVE-CONTENT-AUDIT-20261104-01。過去記録は各追記時点の履歴として保全する。現行のポータル保存記録・slot選択・品質表示要件は本ファイル末尾の「現行差分統合 v2.2」と固定ID Google Docsの同一追補を参照する。
対象：データ取得→検証→本文・図解→ChatGPT表示→Drive保存→GitHub→Portal公開→公開後検証。
REQ-01: 日時、出典、reportId、revision、本文・図解、保存と公開の証跡を追跡する。
REQ-02: ChatGPT実タスクは平日08/12/16/21が有効、土曜08は無効。main configはPR #99マージにより土曜発行なしへ修正済み。
REQ-03: 本文のPUBLISHEDと図解のNOT_READYは同時に存在できる。本文公開と全工程完了を混同しない。
REQ-04: 08:00の28項目5列表の品質検査を要求。実データの全取得成功とは別。
REQ-05: Google Docs保存receiptとinfographicManifestを区別し、公開前後の検証証拠を保全する。
REQ-06: Draft PR #94/97は本番実装済みと認めない。
REQ-07: 要件定義書、仕様書、運用マニュアルを別ファイルとし、書込対象IDの照合を必須にする。
未解決：実行中トリガー、全旧版条項比較、PR本番採用、最新CI・Drive・公開URLの実検証。

## 2026-10-16 公開連携復旧追補（PR提出前）
- 新規公開には対象枠の事前確定snapshot/context、完全一致Docs読み戻し、revision/body hash、保存時刻を結合した発行時receiptを要求する。
- 証拠が欠ける保存済み文書は原本アーカイブに保持するが、公開一覧/latest/dashboard/Pagesへ昇格させない。既存履歴は保持する。
- 10/14 12:00は取得可能な初版Revision 1が空で、本文のあるRevision 11は後刻作成のため、発行時原文として扱わない。10/14 08:00の見出し別名はPython回帰試験に合格したが、現在のDrive更新時刻が発行枠を超えるので公開承認とはしない。
- この追補の実装はPRであり、本番E2E成功は未確認。定期実行・公開URL本文読み戻しを確認するまで復旧完了としない。

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
- REQ-08：平日4枠で、事前取得・証拠生成・ChatGPT本文生成/指定会話出力・Docs/図解保存・canonical/receipt・Pages DOM・通知到達を独立受入する。
- REQ-09：各枠T-13/T-7/T-3分で当日枠・鮮度15分以内の実データから証拠を固定し、T以後の欠損snapshot再構成を禁止する。PR #154でmain反映済み、全枠ライブ発行の成功は未確認。
- REQ-10：10/16 08:00後追い発行はHISTORICAL_ARCHIVE/verifiedAtSlot=falseで保存し、通常のPUBLISHED、canonical、receiptと区別する。PR #152は補充表示専用。
- REQ-11：主要6市場カードは補充原本にある銘柄固有の価格・市場種別・限月・観測時刻・理由・注目点・リスクを区別し、「取得不能」誤表示や条件の二重転記を防ぐ。PR #153で実装・DOM試験済み。12/16/21時は実際の出来事の時系列を記す。

## MRFOLDER-20261019-01｜月別保存先の直接指定・保存読戻し（2026-10-19 JST）
- REQ-MF01: 定時の本文Google Docを作成する際、対象枠の日付（Asia/Tokyo）に対応する「マーケットレポートYYYY年M月」へ最初から保存する。図解PNGは別の「マーケットレポート図解YYYY年M月」へ直接保存する。My Drive直下への保存を成功と見なさない。
- REQ-MF02: 既存の同名ファイルとフォルダーはID・親・revision/実体を照合する。重複候補は削除・上書きせず隔離し、正本を自動決定しない。月フォルダーの複数候補も競合として停止する。
- REQ-MF03: Docs保存、PNG保存は各々、Google Drive読戻しでfileId、name、mimeType、parentIds、URLと本文全文一致（Docs）/実ファイル存在（PNG）を独立受入する。保存結果と公開receipt、Pages表示は別判定。
- REQ-MF04: ChatGPT定期タスクの保存先ルール更新は実施済み。ただし翌回の実発行を観測するまでは自動保存・読戻しのE2E実証はUNKNOWN。本文チャット出力を優先し、保存失敗でも偽装しない。


## 現行差分統合 v2.1（2026-10-19、DOCCTRL-20261019-HISTORY）

このファイルはGoogle Docs固定ID `102PMtKQ4DaXqV1G2RhE8vFtQ8qes-tvIvy2jYQda_xA` に対応するGitHub側の固定パスである。過去の日時付き・版付き文書はアーカイブ。旧PR/変更履歴中の状態を現在の実装事実とみなさない。

- 平日08:00/12:00/16:00/21:00（JST）の本文4本＋独立図解4枚。土日新規配信なし。06:30市場取得は別工程。
- 08:00の前営業日終値は `scripts/verify_morning_report_qa.py` の固定28項目×5列（項目、終値・値、前日比、騰落率、方向感）を正規順序で表示。CME円建て/ドル建て、東証プライム売買代金/売買高を各々別行。取引日と取得基準日を維持。
- 12/16/21時は実際に発生したイベントと市場反応をJST時刻順に説明する。16:00は寄付・前場・後場・大引け、セクター、騰落、先物、ドル円を含む。単なる市場時間割の記述は禁止。
- 全枠の重要イベントは独立項目に日付・曜日・発表時刻（JST、夏冬時間考慮）・出典URL・最終確認日時・影響市場・予定/結果を表示。時刻が取得できなければ理由を記載する。
- 六市場の価格とアウトルックを区別し、金スポット/COMEX、CME/OSE、WTI限月、BTC時刻を誤混同しない。金のボラ・ドル・原油相関、円出来高・実需/投機、株式・先物・裁定・金ETF世界月次フローを確認済みの基準日で扱う。
- 終値一覧の未公表・休場・空欄・記入済み未検証を分類し、検証済み履歴の空セルのみ補完、重複日付・既存数式の無断上書きを禁止する。JP33業種・米国11セクターETFの日時も確認する。
- ChatGPT投稿、Docs保存と全文読戻し、PNG保存と読戻し、GitHub canonical、receipt、Pages DOM、通知を独立判定。発行前証拠不在の補充版は閲覧用HISTORICAL_ARCHIVEとして扱い、遡及的に正規発行へ昇格させない。
- 対象月に本文 `マーケットレポートYYYY年M月`、図解 `マーケットレポート図解YYYY年M月` に直接保存する。保存先親・同名重複候補・ID・revision/全文・PNG実体を確認。保存指示更新は定時E2E完了を意味しない。
- 旧Crypto Fear & Greed必須化は後続の8月7日削除規程が優先。株式Fear & Greed、VIX、日経VIを主な心理指標とする。旧07:00・土曜発行・8:20転送型は現行設定ではない。
- 本文PUBLISHEDと図解NOT_READYは個別状態。図解なしで「全工程VERIFIED」と記さない。正式公開のPNG必須ゲートと個別状態の扱いは実装・証拠を照合し、勝手に緩和しない。

実市場4枠のE2E受入は個別run・保存・DOM・通知証拠がない限りUNKNOWN。これは文書差分整備と区別する。


## DRIVESOURCE-20261020-01｜Drive同名ファイルの最新保存版とGitHub公開正本の分離（2026-10-20 JST）
- ユーザー指定の「同一日時・同一種別はDrive保存日時が遅い方」を、Google Drive createdTime の降順で判定する。modifiedTimeは編集・移動等で変わるため保存日時の代わりにしない。対象は18件のGoogle Docsと3件のPNG、計21対象日時。Drive月別通常フォルダーには各日時1件を残し、古い候補は「同名ファイル確認待ち」に保全した。
- GitHub `data/drive-source-selection.json` がGoogle Drive実測の選定結果を保持する。レポート画面のDrive保存版リンクと `drive-source-selection.html` はこの一覧を参照する。ユーザーに選定版のID・リンク・検証状態を示すが、**これはGitHubの正規発行原本を無条件に書き換える仕様ではない**。
- 最新保存版の本文18件のうち10件は構造・分量を点検可能、8件は空文書または短文。後者を既存の公開済み全文に上書きしない。前者も発行前snapshot、Google Docs revision/全文一致、原本revision、receipt、公開整合の証拠が揃わなければ既存canonicalは変更せず「正式公開保留」とする。後から発行前証拠を捏造しない。
- 図解3件はDrive上の最新保存日時・PNG MIMEを確認。GitHub Pagesでの画像実体、SHA-256、manifest、snapshot/本文との対応が未検証のため図解正式READYへ昇格させない。旧ファイルは削除しない。
- 公開ポータルの参照ページは正式公開と保存版の区別を表示し、公開中の本文全文・最新レポート・dashboard・receipt・公開ゲートを黙って切り替えない。E2E、正式canonical改訂、PNG正式公開の状態は引き続きUNVERIFIED/BLOCKEDと明記する。
- 変更確認対象：本書、上記3システム固定文書、`report.html`、`assets/js/report-drive-source-reference.js`、`drive-source-selection.html`、`data/drive-source-selection.json`。Google Driveの固定ID文書側の同期とライブPages確認は別工程として記録する。

## 2026-11-04 現行差分統合 v2.2｜REPORT-ARCHIVE-CONTENT-AUDIT-20261104-01

- 保存記録は `data/report-archive-manifest.json` から取得し、対象JSONごとにschema/date/time/body/source statusを検証する。特定月をJavaScriptへ固定せず、manifestの一覧をもとに統合する。
- 正式発行データと閲覧用保存記録を区別。同一slotでは正式発行データを優先し、正式データの取得失敗だけで検証済み保存記録を破棄しない。利用可能データ確認は統合後に行う。
- 日付・時間帯ボタンとURLは実在するslotだけを選べる。指定slotがない場合は欠落表示とし、別日時の本文を代用しない。保存記録は正式発行へ自動昇格しない。
- 08:00必須28項目×5列QAに不合格の場合、警告を表示して未検証の市場表だけを隠す。本文と保存元の発行ステータスは変更しない。
- 部分取得失敗は取得済みデータと警告を表示し、全件失敗は原因と再試行案内を表示する。ログは対象ファイル、日時、HTTP status、検証結果を記録し、認証情報を出さない。
- 受入条件は11/02・11/03の各実在slot、10/30 21:00回帰、日付移動、URL指定、正本優先、取得失敗、不正アーカイブ除外、Pages公開後の実ブラウザ読み戻しとする。
- 実績：PR #193～#196 main統合、68slot/18日分の公開画面確認、Pages deploy run 41836815631 SUCCESS。PR #193/#194は日付・時刻を価格として誤認するアーカイブ表を抑止。PR #195/#196は08:00 QA未達を明示する。
- 未解決原本：10/22 12:00の復旧記録に12:00本文がなく、11/02 12:00の保存元状態情報に矛盾がある。元資料なしに修正・昇格しない。

## MR-CLOSE-SYNC-20261114-01（2026-11-14 JST）

対象日の保存成功は、実Sheetsの日付・更新値の再読込一致を必要とする。コード/CI、隔離タブ権限試験、実終値行受入、連続20対象営業日の運用受入を分離する。取得期限切れ・取得失敗・認証・書込・再読込・ログ失敗を区別し、未実行工程はNOT_RUN。古い市場snapshotを取得失敗の代用品として保存しない。既存の08時締切・28項目QA・公開資格・配信時刻を緩和しない。

### 実権限検証の追補（2026-11-14 02:38 JST）

MR-CLOSE-SYNC-20261114-01 / Draft PR #201 / code commit 0e35a3df80af3064001b3d9cd3d334ebccd98bd2。Actions run [43474764135](https://github.com/matrixdiamond512-cell/Chat-GPT-Market-Report/actions/runs/43474764135)のpermission-probe job SUCCESS、通常acquire job SKIPPED。結果artifactを別リクエストで取得・読戻し、対象spreadsheetIdが指定の終値一覧2026と一致、CLOSE_DATA_WRITE/READBACK_VERIFY/cleanupすべてSUCCESS、reportCellsModified=0を確認。既存Secretsのサービスアカウントを使用し、主体のfingerprintを証拠JSONに記録。これは本番ファイル内の隔離タブにおける権限・保存経路の実証に限定し、日付キー/終値・前日比の実行受入ではない。今回の条件では400/403は再現しなかったが全経路の解消とは断定しない。68ローカル試験と同code headのhosted checks SUCCESS。実終値行読戻し/定時性回復/20対象営業日/main統合/Google固定文書同期は未達・NOT_RUN、遅延の発生原因はUNKNOWNのまま。先行のNOT_RUN記録は当時の履歴として保持する。

### 日本語A1・数値の実検証（2026-11-14 02:42 JST）

MR-CLOSE-SYNC-20261114-01 / PR #201。run [43475352764](https://github.com/matrixdiamond512-cell/Chat-GPT-Market-Report/actions/runs/43475352764)、code30ddc2b59の日本語一時タブでliteral A1のbatch書込・数値123.456/文字列のURL読戻し・一時タブ削除後の一覧確認がSUCCESS。artifactを独立取得して対象シートID・同じ認証fingerprint・cleanup SUCCESS・既存reportCellsModified=0を照合。後続fb977a5aeで期限切れFETCH=NOT_RUNと取得成功/証拠不足FETCH=SUCCESSを分離し、失敗時にSheetsへ接続しない方針は維持。69関連ローカルテストPASS。実終値行・定時性回復・20営業日は引き続き未達、main未統合、Google固定文書同期NOT_RUN。新規取得元・列・トリガー・publisherなし。
