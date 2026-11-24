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


## PORTAL-CONTENT-COMPLETENESS-20261116-01（2026-11-16 JST）

両画面は `data/report-archive-manifest.json` の同じ保存本文一覧と `assets/js/report-archive-source.js` の表示専用アダプターを使用する。Doc ID/URL、revision、本文長、日時、出典フォルダーを確認し、形式差（fileId/revision/URL形式/BOM）で有効な本文を落とさない。元本文と正式公開状態を変更しない。後日再構成版は定時原本に昇格せず、参考価格と実測資金フローを混同しない。

Driveから10枠を追加回復し、保存本文91枠を検証。見出し別の主導市場・シナリオ・結論・時系列表示を修正。未取得値を推測せず、残る原本欠落5枠は `data/report-content-gaps.json` に記録する（10/20 08、10/22 12、11/04 08、11/06 08・12）。10/20 08と10/22 12は復旧メモ、11/06 12は空Doc。

検証：Nodeの対象20テストPASS（E2、実保存本文を使ったアダプター/選択/表示回帰）。公開ブラウザは変更前を観測。変更後の公開DOM・Pages反映はNOT_RUN。Google Docs固定ID文書への同期は未実施。定時配信・正式原本・receipt・スケジュールは本変更の対象外。

## REPORT-SLOT-WINDOW-20261117-01｜定時データ取得・発行前証拠の対象時刻保全（2026-11-17）
- GitHub Actionsの遅延起動を「現在時刻の別枠の新規実行」として扱わない。取得処理は指定枠の最初の試行時刻より最大15分前〜予定枠90分後の範囲外では、データ、監査ログ、証拠を書き換えず終了する。
- 発行前証拠ワークフローは予定枠15分前から予定時刻**未満**だけ実行を許可する。範囲外のrunは欠落として可視化し、将来枠のデータ取得も発行後の遡及作成も禁止する。
- タスク本文、Google Docs、参考閲覧ポータルは正式publicationとは別扱い。GitHub Actionsがタイムリーに起動する保証はないため、証拠の実readbackと定時E2Eは独立受入する。既存の平日08/12/16/21時を変更しない。

## REPORT-SLOT-QUEUE-20261117-02｜定時実行の時間帯分離（2026-11-17 JST）

- 発行前証拠固定および市場データ一次・補助・健全性確認の実行待ち行列は、平日08:00/12:00/16:00/21:00の対象枠を分離し、遅延した別枠のjobが次枠を妨げないこと。同一枠の複数処理の直列性は維持する。
- 時刻外実行のデータ書込禁止、発行前15分証拠、スロット固定、事後捏造禁止、正式publication gateは一切緩和しない。
- GitHub Actions cron自体の大幅遅延と、Google Drive月別フォルダーへの配信用サービスアカウント権限不足は、行列分離だけでは解消しない。定時発行E2Eが確認できるまで未完了と記録する。

## MR-STABILITY-REPAIR-20261117-03（2026-11-17 JST / 修正候補）
月別直接保存と原本保全を維持する。サービスアカウントが正式月別フォルダーを一意に参照できない場合、他folderやDrive全体の同名Docを代替原本にせずBLOCKEDとする。本文生成・図解・証拠・正式公開の要件は変更しない。
検証: 新規7件を含む65回帰テストPASS（E1/E2）。本番SAのfolder読戻し・初期4枠・10営業日40枠は未実施。コード/CI成功を全面復旧としない。

## MR-DELIVERY-STABILITY-20261118-01｜発行・図解の再発検知と証拠多重化（2026-11-18 11:58 JST）
- 平日08:00/12:00/16:00/21:00の本文・図解・Docs・receipt/canonical・Pagesを工程別に判定する。Docs保存、PNG実在、GitHub Actions successはそれだけで正式発行成功とは扱わない。
- 2026-10-16以降の新規正式発行は対象reportId/revision/bodyHash、正しい枠前snapshot/context、真正なDocs全文読戻しreceiptの一致が必要。図解はREADY時のみbody/hash/snapshotに結びつくmanifest、数字・renderer検証を必須とし、Drive画像byteおよび内容一致は別に検証する。
- 証拠固定経路を追加してもT-15分からT直前の厳格な期限、既存証拠の不変性、過去枠の事後捏造禁止を維持する。本文・画像・参考閲覧・正式公開は独立の状態。
- 実装：PR #215 main dbc95b8cf613ecf6ef990149e58d66bb6f7bac78、PR #216 main da71661a25a8dce65b0a75e8e27c6e9d10342504、関連CI PASS。11/18 12:00枠前証拠のmain読戻しはPASS。4枠正式発行の本番継続受入・10営業日40枠は未完了。固定ID Google Docsへの同変更ID追記済み。

## MR-DELIVERY-STABILITY-20261118-02｜早期実行と誤昇格への追加要件（2026-11-18 12:11 JST）
- 11/18 12:00主タスクは11:56:57〜11:57:38 JSTに早期終了。閲覧用分析版本文は可視表示されたがPNG/Docs/公開未実行。定時発行成功扱いしない。
- 正しい枠前証拠があっても原本文が「閲覧用分析版」「遅延分析版」「非正式分析版」「正式公開保留」と自己表示する場合、正式publicationへ昇格させない。参考閲覧は継続可能。
- 正規latestReportとdashboard.latestReportに許す差は、独立のdashboard.marketDataと完全一致するmarketData投影だけとする。本文/日時/余計な属性の差異は拒否。
- 実装：PR #218、main 5420fed6600bda41aa8be45eae7eee8768242bdd。CI run44228487454/44228487434 SUCCESS。早期起動そのものと全工程E2Eは未受入。固定ID Google Docsへ同変更ID反映済み。

## REPORT-PIPELINE-REDESIGN-20261118-01｜発行システムvNext再設計要件（2026-11-18 JST / 設計案・未実装）
- 設計目的：ChatGPTタスクの単一実行で本文・図解・Docs・GitHub/Pagesまで完走する依存を撤廃し、各工程を独立した再試行可能な処理とする。現行の平日08:00/12:00/16:00/21:00 JST、土日なし、朝28項目×5列、主要6市場、12/16/21の実出来事時系列、Google Drive月別原本/公開ポータルを維持する。
- 必須機能：枠前の不変snapshot、reportId一意の実行台帳、本文構造QA、固定JSON→決定論的PNGレンダリング、月別Docs/PNGの別保存・実読戻し、独立receipt/manifest/Pages DOM検証、失敗工程だけの冪等再試行、通知とチャット表示の独立受入。
- 安全：過去証拠の事後生成と非正式報告の正式昇格は禁止。GitHub ActionsやChatGPTタスクのcompleted、Docs/PNGの単なる存在を正式発行成功としない。既存タスクの停止・本番権限変更・外部API利用は本案の範囲外。
- 重要な未検証依存：既存ChatGPTチャットへの外部生成本文/画像の自動挿入経路は実証されていない。チャット可視表示契約を維持し、未実証なら独立にUNKNOWNとし全工程VERIFIEDとしない。Google Cloud予算・権限・書込用SAの承認、1枠実E2E、4枠実E2E、10営業日40枠の受入も未実施。
- 本文作成マニュアル含むGoogle Docs固定ID正本5件に同変更ID・未実装明記で設計案を追記済み。


## MR-INFOGRAPHIC-DRIVE-20261121-01｜図解PNG実保存・定時障害検知（2026-11-21 JST）
- 各枠の画像生成とDrive保存は別工程とし、画像のチャット表示や一時sandboxファイルの存在をDrive保存の証明としない。生成PNGは生成した同一実行環境から月別正式フォルダーに保存し、同名画像の重複・上書きを防ぐ。
- Drive保存SUCCESSの最低条件は同一reportIdの画像についてファイル名、MIME=image/png、月別親フォルダー、非空バイトの実読戻し。品質QA、正式manifest、本文対応、receipt、Pages表示は別の受入工程とする。
- +45分の独立した健康監視でGoogle DriveからPNG実体を再取得し、欠落・重複・誤配置・破損をFAILとする。canonicalやmanifestが欠落してもPNG保存の障害を独立に可視化する。
- 同一枠の主タスク/独立図解タスクが終了していてもDrive PNGが0件なら、未発行復旧タスクは競合確認後に対象本文を根拠として復旧生成・保存できる。事後生成を当時の正式画像と偽らず、元原本を上書きしない。
- 11/20 21時枠の遅延実績は本番受入FAIL、11/21の代替経路単体試験はPASS。次回4枠E2E・正式図解品質・公開DOM・通知は未受入。PR #226は修正候補でありmain実装済みの意味ではない。

## MR-DRIVE-SCHEDULE-DATE-20261121-02｜定時監視の対象日固定・再試行
- GitHub Actionsのschedule実行が遅延してJST日付を跨いでも、監視対象は「実行した日」ではなくスケジュールに対応する対象営業日とする。対象日はUTC cronの直近有効発火予定時刻からJSTへ変換し、同一の対象日をPNGと正式report/manifestの両検査に用いる。
- 予定時刻から18時間を超える遅延・対象日を一意に復元できないケースは失敗として報告し、別営業日のレポートを検査して成功/失敗を偽装しない。
- 45分後の独立監視はmissingの場合に、原本本文一致・二重処理なしを検査したうえで画像復旧・Drive再保存を試行する。成功しても定時成功とはしない。

## MR-WATCHDOG-MIDNIGHT-20261121-03｜公開watchdogのfail-open防止
- 定時公開watchdogの対象JST日付を、GitHub Actionsの実行時現在日でなく発火予定cronから導出する。21時枠が実行時刻で21時より前になったとして無検証正常終了する経路は禁止。
- 遅延で対象日が不確実な場合はFAILとして原因を通知し、形式上の成功で欠損を隠さない。


## MR-AUDIT-CAPA-20261124-01｜独立監査Phase 0（2026-11-24 JST）

出典: ユーザー添付の是正指示書第8節および独立監査報告。基準main `579fa000fc84f6875f220962c5f17ea01138c68e`、作業branch `codex/audit-capa-phase0`。監査原文・是正台帳・実装順序・影響文書・承認操作・費用/リスク/rollback・AT対応は [是正台帳](../project-control/AUDIT_CAPA.md) に集約。NC-01〜07/RC-1〜5/AT-01〜12の原定義は保全原本を維持。

今回変更はPhase 0の証拠保全と計画記録。実装、本文/図解構成、平日4枠、production data、原本、トリガー、Pages設定は変更していない。ローカルと公開HTTPで旧dataAsOf/誤正常表示・SOURCE_ARCHIVED HTTP200を再確認、BTC対象回帰は2件中1FAIL。全suite/修正後本番/独立再監査はNOT_RUN。固定Google Docs同IDへの同期はアクセス検証未達でNOT_RUN。計画承認後に対象Phaseの実装と影響文書を同時更新する。関連Issue #103/#176/#205/#222、未マージPR #201/#204/#206と重複させない。新規PR未作成。


## MR-AUDIT-CAPA-20261124-01｜Phase 1A・1B ローカル実装（2026-11-24 JST）

ユーザーの「進めてください」により、Phase 1A/1Bのローカル実装・検証を承認。基準main `579fa000fc84f6875f220962c5f17ea01138c68e`、branch `codex/audit-capa-phase0`。関連 #103/#222、既存PR #201/#204/#206の取得/保存実装を変更しない。GitHub push/PR/main適用・Pages設定/公開・Drive/GAS/タスク/課金変更は未実施。

予定枠の鮮度を `config/report_schedule.json` から共有判定し、遅延/欠損時は `status=degraded`・`isStale=true`・理由と期待/公開枠を記録。同期のUPDATED/NO_OPは投影の変更有無であり、定時配信成功ではない。独立市場データの異常を保持し、同じ原本の再同期でも予定枠を再評価する。本文/図解の構成・分析項目、平日08/12/16/21 JST・土日なし、既存publication gateは維持。

Pagesは `config/pages_public_files.json` の静的ファイル一覧・限定した履歴collection・既存archive manifest・公開資格のあるcanonicalから組立。docs/scripts/apps-script/receipt/枠前証拠/診断用dataは既定非公開。公開ファイル追加は許可リストのレビューを必要とする。公開リポジトリraw/履歴の閲覧可否は別問題であり、Pages除外で解消したと主張しない。

ローカル検証と制約は `docs/project-control/AUDIT_CAPA.md` のPhase 1追補および `phase1-evidence.json` に記録。hosted CI、本番設定切替、変更後live Pages、固定Google Docs同期、通知実到達、独立再監査はNOT_RUN。固定Docs5件のmetadata読取404は権限/接続上の制約であり不存在の証明ではない。


## MR-AUDIT-CAPA-20261124-01｜Phase 1A・1B PR準備（2026-11-24 JST）

ユーザーのPR準備指示に基づき専用branch `codex/audit-capa-phase1ab` をmain `437a63c23bb7f979fd663c824dec1fa8a5941d1d` から作成。開始時31ファイルはPhase 0保全資料/台帳とPhase 1A/1Bに対応し、無関係な未コミット変更なし。元branchの履歴を保持、全31ファイルのSHA-256を切替後に照合。既存packed-refs.lockは変更せず、branch/HEADを独立確認。upstream変更11データファイルとの重複なし。

同じ60件Python/32件Nodeを再実行し合格。全テスト名・環境・ログは `docs/project-control/archive/independent-audit/pr-validation.json` と `pr-python-tests.log` / `pr-node-tests.log`。許可リストartifactは1,074ファイル、430参照を検査して新規欠落0。元sourceにも存在しないdata/reports.json参照2件は残課題として区別（pr-public-dependencies.json）。同じ60/32件と依存検査を既存health CIへ接続、新規の監視タスクは追加しない。

今回許可された外部操作は専用branchのpushと独立レビュー用PR作成。mainへのマージ、Pages設定/配備、Drive固定ID/原本、GAS/ChatGPTタスク、課金/権限拡大は実施しない。コード/文書のGitHub取得を受入とし、本番復旧や独立監査合格と表現しない。PR/最終HEAD/hosted CIの実測はPR本文とレビュー提出記録を参照する。


PR公開範囲追補（MR-AUDIT-CAPA-20261124-01 / 2026-11-24 JST）: 自動承認レビューにより原監査・詳細証跡・全ログの一括公開pushは拒否されたため、これらはローカルに保全してPR対象外とする。公開証拠はaudit-source-index.json（原資料のhash/既存Drive参照）、pr-validation.json（60/32件のテスト名・結果・環境）、pr-public-dependencies.jsonに限定。元の詳細ログ/phase0・phase1-evidence/棚卸しの記載はローカル保全記録であり、GitHub公開済みの意味ではない。コード・固定文書の修正範囲は不変。


### PR提出記録（MR-AUDIT-CAPA-20261124-01 / 2026-11-24 JST）

独立レビュー用Draft PR: https://github.com/matrixdiamond512-cell/Chat-GPT-Market-Report/pull/229 。専用branch `codex/audit-capa-phase1ab`、実装/ローカル試験対象commit `f2bcebd4cd24d548ccb5eceabdcef418e768d4fe`。GitHub APIでAUDIT_CAPA.mdのblobを独立取得しローカルGit blobと一致確認。公開30ファイル、監査原文・詳細runtime/issue証跡・全ログ・棚卸しはローカル保全で非提出。PRはOPEN/Draft・未マージ。hosted CIの最終状態はPRの同head Checksで確認し、ローカル92件の合格とは分離する。今回はPages設定/配備・Drive正本・ChatGPTタスクを変更しない。


## MR-AUDIT-CAPA-20261124-01｜PR #229 レビュー6034576678への修正（2026-11-24 JST）

対象head a8e01a4322a6d37d2ad3c377dbfbac6e587bf0c2のREQUEST_CHANGESを直接読戻した。P1対応としてreportDeliveryをslotFreshness（日時のみ）、formalPublication（canonical/receipt/indexの実読取照合）、pagesDisplay（NOT_VERIFIED）へ分離。MARKET_REPORTS_JSON.statusを鮮度から正常にせず、正式証拠のverified/unverified/failedへ変更。現在枠でもreceipt欠落・SOURCE_ARCHIVED・Docs読戻し失敗・latestReport欠落では配信成功/警告解除にしない。Pages表示は静的JSONやCI成功から昇格させない。

既存Python60件/Node32件に加え、Python8件/Node2件の負例・証拠の正例を合格。review-validation.jsonにテスト名/環境/結果を記録。原監査・詳細ログはローカル保全を継続し公開しない。AT-04の本番mode変更/非公開URL404は引き続きNOT_RUN、独立再レビューと本番適用は別判定。Phase 2は保存前の原本保全・Docs/PNG独立再試行の接続点を調査し、read-only importerだけではwriter障害を直せないことを確認。既存writer候補を再利用評価し、別branchのローカル実装として進める。


レビューP1補強（同変更ID / 2026-11-24 JST）: slotFreshness.scope=TIMESTAMP_ONLYを明記。正式本文のcanonical/receipt/indexが合格してもPagesはNOT_VERIFIEDのまま、dashboard全体はokへ昇格せずpartial/PAGES_DISPLAY_UNVERIFIEDとする。正式本文証拠と全工程配信成功を区別する追加正例を含め、既存92件＋追加10件を再実行して合格。Phase 2ローカル基盤は別branch codex/audit-capa-phase2-storage、commit 28165dbcb6714cfe0419d18acc7467546cf3a571に保全し、PR #229へ含めない。実writer接続・本番保存は未修復。
## MR-AUDIT-CAPA-20261124-01｜Phase 2原本保全・再試行基盤の着手（2026-11-24 JST）

別ローカルbranch `codex/audit-capa-phase2-storage`、基準はPR #229レビュー対応commit b246008126ffdb39b163a05bd9067a70fd9342fa。scripts/reporting/delivery_spool.pyとtests/test_delivery_spool.pyを追加。実Google/GitHub adapter、タスク、trigger、Pages、課金、固定Docsは未接続/未変更。この変更をPR #229へ混入させず、push/PR作成もしていない。

外部writer呼出し前に原文UTF-8 bytesをSQLiteへcommitし、同一reportId/revisionでの改変を拒否。生成PNGも本文hashへ結び付けて保全。Docs/PNGのcheckpointを独立させ、一方の保存失敗で他方の成功や原本を失わない。writerがreferenceを返した後の読戻し失敗ではそのreferenceだけを再読込し、再作成しない。writer timeout/成否不明ではUNKNOWNとして二重作成を遮断し、再開は外部writerによる照合/復旧手順が必要。転送readbackを正式publication/PNG品質/Pages合格へ昇格しない。

ローカルfixture6件PASS: 再起動後の原本保持・同revision上書き拒否、Docs失敗時の本文保持/二重write拒否、readbackだけの再試行、Docs失敗時のPNG独立保存、成功工程の再実行抑止、PNG不変性と品質未判定。初回はSQLite connection解放漏れをWindowsで検出し、closeを保証するcontext managerへ修正後に全件PASS。

残課題: provider側の冪等key/重複照合、UNKNOWN復旧、月別folder/親ID/Docs全文revision読戻し、PNGの視覚数値品質、既存producerとの接続、本番の永続ストレージ配置と実権限検証。同期ドライブ上のSQLiteやコンテナ一時FSを本番保存先と決めたものではなく、保存backendは未選定。本モジュールだけで11/24のDocs/PNG保存障害が修復したとは主張しない。次は既存producer入力→永続原本→認証済writer/readbackの接続を隔離環境で実装・受入する。
