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

- 追加予算0円。OpenAI/他社AI API、無料枠を含む課金可能サービス、有料データ/クラウド/スケジューラー、カード登録を導入しない。変更前・PR前・本番切替前にコストゲートを実施し、不明条件は `BLOCKED_COST_UNVERIFIED`。既存契約や無料公開URLだけを根拠に将来の無課金を保証しない。
- 採用候補は経路Aの一つ：現行ChatGPTで承認品質の本文・図解を作成/確認 → 正式な手段または明示した人の確認で原本を引渡し → 単一の受領/検証/publisher。生成元、指定会話投稿、自動引渡しは公式機能と実アカウントの結果を独立確認する。今回のコードは生成器ではない。
- 平日08/12/16/21時の本文各1本＋独立図解各1枚を維持。08時28行×5列、前営業日終値、08時図解の承認済み16項目の順序、他枠の実出来事時系列、6市場の条件/反証を削らない。旧文のPNG独立状態は部分状態として保持するが、図解欠落の枠を全工程受入へ数えない。
- 原文・PNGがない場合は `WAITING_FOR_SOURCE_ARTIFACT`。定型文、別日時の価格、架空のニュースや簡易グラフで正式版を代替しない。画像基準図へアクセスできなければ `BLOCKED_REFERENCE_IMAGE`、内容/視覚QAを分離し、fixture署名で実画像を合格にしない。
- reportId/revision/snapshot/bodyHash/sourceDocIDを同一原本に固定。市場取得処理はdashboard直下のライブ市場カードのみ更新し、保存済みlatestReport/reportsのmarketDataを上書きしない。
- shadow候補は本番書込アダプターを持たず、旧経路を保全する。4枠の実原本/Docs/PNG/readback/正式receipt/公開後DOMが検証できるまで本番writer切替不可。切替後の5営業日20枠には本文と図解の両方の実物証拠を要求し、失敗で連続計数を再開。ローカル試験を計数に含めない。
- Google Docs正本6文書の読取/図解基準照合は403/404でブロック。本文作成マニュアル/図解マニュアルを未読のまま改稿せず、既存GitHub契約の構造検証合格を承認品質の全達成と呼ばない。

変更対象：本要件、specification.md、operations.md、DOCUMENT_CONTROL.md、EVIDENCE_LEDGER、DELIVERY_PATH_INVENTORY.json、HANDOFF、コスト設定/検査、shadow入口/CI、原本不変writer。Google固定IDの同期はBLOCKED_EXTERNAL_ACCESS。詳細検証は同IDの台帳へ記録。


## MR-SOURCE-HANDOFF-20261113-01｜非本番の実保存・原本受渡し境界（2026-11-13 JST）

出典：ユーザーのPR200共同レビュー後指示。既存ChatGPT→原本引渡し→Drive保存を優先し、今回新しいpublisher/recovery/watchdog/有料APIは追加しない。

既存Google Drive connectorを使った非本番本文保存は実測した。新規フォルダ/Docの作成、親MIME、全文SHA、Docs revisionの独立readbackを確認できた範囲に限り保存試験PASS。指定ChatGPT定期タスクからの原本引渡し、同枠PNG、正式receipt、Portal、通知は別工程で、未接続/未検証を保持する。

既存Docの補充本文をコピーした試験を、指定会話の本文表示や定時生成成功へ昇格させない。TXT変換での余分な改行もhash不一致として記録し、新規試験Docだけをrevision付きで限定修正した。原本本文や合格基準は変更しない。本文・図解の品質/全4枠/事前証拠/公開資格は既存要件のまま。


### MR-SOURCE-HANDOFF-20261113-01｜21時枠の早期実行・未発行終了（2026-11-13 JST）

ユーザーが提供した21時枠の履歴では、予定21:00に対し20:55:04開始/20:55:16終了、runtime completedだが未発行で、Drive保存actionは呼ばれていない。これはDrive HTTP失敗と区別する。予定枠前の実行を配信成功に数えず、予定時刻到達後の原文生成・保存・readbackが未実施なら未達を保持する。早期実行の理由/継続実行可否は独立調査対象で、今回taskの変更/停止は行わない。

タスクIDと各run ID/実行会話を結び付け、指定表示先の会話とrun会話を別フィールドとして照合する。会話IDが変化しただけで表示先が正式に変更されたと認定しない。既存仕様の指定チャット表示要件は削らない。


## MR-TASK-DIAG-20261113-01｜保存プロンプト3,954文字の診断（2026-11-13 JST）

出典：ユーザー添付「現行定期タスク診断資料」21:57 JST。保存プロンプトを明示マーカーから抽出し、LF表現で3,954文字（UTF-16も同数）、SHA501ce01e9a49a1ef742af95aee66d6b5e0e001d03f3e8ae49ab4a8466943757fを確認。これは提供資料との一致であり、プラットフォームからの独立exportではない。

現行指示には同一実行の原文保持/チャット表示/全文保存/readbackと、枠前証拠欠落でも通常保存を継続する規定が既にある。『保存指示がない』を原因としない。確認できた差異は、(1)予定前起動から枠時刻までの公式な継続/再開手順が未規定、(2)09/13/17/22時の復旧がプロンプトにある一方、実スケジュールにはないとの診断、(3)PNGを任意扱いする文言。4枠の詳細本文/独立図解を維持し、実task提供toolを確認せず保存や生成の成功を推定しない。

実task/prompt/schedule/有効状態を今回変更しない。早期発火の原因と継続機能の実在は未確定。スケジュールを増やすだけで復旧したと扱わず、既存経路を増殖させない。


## MR-SOURCE-HANDOFF-RECOVERY-20261113-01（2026-11-13 JST）
出典: 23:34 JST指示書 / Draft PR #200。既存タスク・Google固定正本・main・本番設定は変更なし。影響: requirements/specification/operations/DOCUMENT_CONTROL、台帳、HANDOFF。Google固定ID文書・本文/図解マニュアルへの同期は未実施（権限/承認待ち）。承認済み本文・図解品質は維持。

既存verify_scheduled_report_delivery.pyへ任意の`--run-observation`を追加。予定/実開始/実終了・情報基準/原本作成時刻を分離し、completedだけを成功とせず本文/PNG/Docs/受渡しとlocal canonicalを別判定する。新しい監視job・schedule・writerなし。観測ファイルを自動取得する接続は未実装、現行監視へrun情報が自動注入されるわけではない。時刻またぎ・早期終了・PNG欠落・canonical欠落・異なる予定枠・timezone欠落を回帰検証。既存32件＋配信検証9件=41件PASS（合成試験を含み、実E2Eではない）。

実物読戻し: 11/13 16時Docの全文・親・MIME・時刻を取得、revisionはnull、実runとの結合UNKNOWN。実PNGは未受領。取得0件を不存在とは断定しない。実本文を既存shadowへ渡すとWAITING_FOR_SOURCE_ARTIFACT、欠けた6ファイルを明示、productionWrites=0。証拠: `docs/project-control/evidence/source-handoff-recovery.json`。前回の非本番2495文字保存成功は維持、新しい保存成功へ水増ししない。今回のPNG保存・bundle受入・公開・通知は未実施。

公式継続/遅延再開/強制実行は、この接続で提供されるautomation操作(view/create/update/delete)では実証できない。BLOCKED_PLATFORM_CAPABILITY。原因不明の早期起動を平台障害と断定せず、sleep/未予約復旧を対策としない。通常ChatGPTのDrive操作可用性はユーザー報告、定期runのtool一覧/主体/呼出traceは取得不能。CodexのDoc読戻しと以前の非本番書込は実測、GAS/Actionsの認証・導入版はUNKNOWN。確認にはユーザーが許可した実runのaction履歴と原本文・実PNGが必要。無課金の自動会話転送は実証済み公開接続なし。人手受渡しは非本番試験に限り許容、自動配信成功に数えない。

最小プロンプト差分は `docs/project-control/task-prompt-change.patch.md`（未適用）。本番切替/rollbackは既存operationsの承認gateを維持。4枠＋20枠の実受入は未達。費用PASS_LOCAL_ONLYは契約/本番費用保証ではない。


### 2026-11-14 JST 観測追補 — MR-SOURCE-HANDOFF-RECOVERY-20261113-01
出典: ユーザーの別接続revision照会とコミット535e5dd提示 / PR #200。今回の新規実証は証拠JSONのfollowupObservationsを参照。Codexのget_document（全文/fields指定）とget_document_textはいずれもrevision=null。ユーザー報告revisionを今回の独立読戻し本文へ転記して成功扱いしない。共有操作権限falseをrevision欠落の原因とは断定しない。

現在のDoc本文4640文字は以前の読戻しhashと一致。GitHub535e5ddの保存版は同じDoc ID・月親・提示revision、verifiedAtSlot=false。ただしfullTextは4548文字・1行、Docの92個のLFを全削除した文字列とだけ一致する。全文byte/hashの一致条件はFAIL。改行を無視してPASSにせず、改行を失わせた操作主体・処理はUNKNOWNとする。今回mainの保存版は修正していない。将来の承認済み取込ではDocの原文改行を保全し、readback hashとarchive hashを独立照合する。

16時固有run ID/会話参照/保存actionログはユーザー側でも取得不能。21時runを流用しない。TASK_RUN_BINDING_UNKNOWNを維持。対象実PNGは未受領（検索で見つかった非レポート画像は除外）、PNG保存/byte読戻し/正式公開はNOT_RUN。必要な次証拠は許可された実runの対象Doc ID付き保存action結果と同runのPNG原本。既存タスク・固定Google文書・本番・未適用prompt候補は変更なし。要件/本文・図解品質の変更なし、コード変更・追加機械試験なし。固定Google Docs同期は未実施。


## MR-BODY-INTEGRITY-20261114-01（2026-11-14 JST）
出典: ユーザーの改行保全指示 / Draft PR #200 / 535e5ddの保存版と実Doc読戻し。変更対象: report_source_contract.py、sync_reports_from_drive.py、回帰tests、既存shadow CI。本番・タスク・Google Docs原本・正式資格gateは未変更。

実装: Docs textRunを無変換抽出し、空行・日本語・Markdown見出し・先頭BOMを保持。既存paragraph_textはLFを保持しており、既存のBOM削除だけを廃止した。535e5ddはJSON登録のみで実行コード/ツールtraceを含まず、92LFを脱落させた実関数/実行主体はUNKNOWN。BOM削除を92LF欠落原因と偽認しない。既存save_jsonへ書込前の本文hash/JSON変換後/ファイル読戻しの一致gateを追加。review専用archive_body_candidateは元Doc ID・元本文hash・変更前archive hash・一意な枠を要求し、全文を変更なしに設定、status/revisionを保全。新しいpublisher/監視なし。

非本番候補: docs/project-control/evidence/archive-body-candidate.json（535e5dd時点の完全archiveを基準）。16時fullTextとdriveTextLengthの2項目だけ変更。4640文字/92LF、読戻しSHA 3d4bdc1b0d85edbdb2e59d662683192d2fbdfa4d8ab5a0546e1500749bcbae04。source Docは読取りのみ、archiveの既存revisionは維持するが、そのrevisionと今回の本文を結ぶ独立証明は引き続きUNKNOWN。現在mainに追加変更があれば候補をそのまま上書きせず再照合する。候補は本番ファイルではなく正式発行でもない。

検証: 従来41件＋9件=50件PASS。実本文候補のディスク保存/読戻しはPASS。改行脱落・変更前hash不一致・別Doc・複数tabを拒否。証拠はbody-integrity-verification.jsonとbody-integrity-tests.txt。16時run結合・PNG・正式publicationは未検証。Google固定ID要件/仕様/本文作成/運用/図解/台帳は未同期、既存詳細品質はNO_CHANGE。影響文書: requirements/specification/operations/DOCUMENT_CONTROL/EVIDENCE_LEDGER。main merge/本番データ修正は承認待ち。


## MR-PORTAL-PREVIEW-20261114-01（2026-11-14 JST）
出典: ユーザーの3段階実証指示 / PR #200。新たに動いた工程: 11/13 16時の実本文4640文字・92LFを新規非本番Docへ実書込→独立全文/親/MIME/revision読戻し→既存save_jsonによるreports[]保存→HTTP読戻し→既存report.htmlの実ブラウザー表示。原文SHA一致、16見出し/全非空行を可視本文へ照合、画面PNG2枚。証拠: portal-preview.json、portal-preview-top.png、portal-preview-body.png（図解原本ではなくポータル画面証拠）。新規試験Docだけを書き、元Doc・main・本番・タスクは無変更。

実表示での阻害条件はreport-core-v3.jsの参考閲覧種別判定: DRIVE_RECOVERY_DOCUMENTがunsupportedだった。既存の同一Doc/revision/文字数/欠損証拠/非正式判定を維持して当該種別のみ受理。正式ゲートは不変。save_jsonはトップ本文に加えてreports[]等の全fullTextを再帰走査し、保存前/JSON変換後/ディスク読戻しで文字列とUTF-8 SHAを照合。原文無改変のまま51 Python/9 Node試験PASS。画面DOMはMarkdown描画なので原文byte hash一致とは呼ばず、JSON原文hash一致と全非空行の可視照合を別記する。

3954文字の保存promptは置換2箇所+末尾追記のみの4897文字candidateとしてtask-prompt-candidate.txtへ保持、差分はtask-prompt-change.patch.md。PNG各枠1枚、早期終了未発行、取得できるrun/Doc/revision/hashを記録、能力不足はUNKNOWN/BLOCKED、既存詳細品質とGitHub責任を無断削除しない。実適用は承認待ち。

次の設定枠は11/16（月）08:00 JST、週末発行なし。未来runの観測はNOT_RUN。現在の公式接続にrun強制実行/過去16時action trace/自動会話転送はなく、実PNG未受領。無課金の可能な代替は許可された通常ChatGPT実行で公式Drive保存を実証し、その実本文とPNGファイルを人手で受領する非本番経路（完全自動化の証明ではない）。原本が無いまま画像生成/保存成功や自動受渡しを捏造しない。

shadow停止はrun_report_delivery.runのrequired7ファイル確認。続くvalidate_bundleはbody/SOP、08時QA、validate_receipt/verify_slot_evidence、親/Doc ID、実PNGとmanifest同版byte hashを要求。11/13欠損evidenceを後作成しないため正式資格経路は停止したまま、通常Docs保存と参考表示だけを実証。新publisher/監視は追加しない。

本番参考アーカイブ修正の適用条件: 明示承認→最新mainの対象Doc/slot/変更前hashと競合再照合→原Docのrevision付き再読戻しと原文hash→当該fullText/文字数だけ変更→reports[]保存前後hash→ブラウザー参考表示→非正式状態維持を確認。既存候補の全archiveをそのままmainへ上書きしない。rollbackは直前blobへ対象差分だけ戻し、他枠/後続編集を保全。publisher切替とは別承認。

公開テスト記録の実行コマンドはpython -m unittestへ修正。過去commit履歴の絶対パス残存は未解消、force push/履歴改変なし。今回のログ生成も公開コマンドからユーザー絶対パスを除外。影響: requirements/specification/operations/DOCUMENT_CONTROL/台帳とprompt候補。固定Google文書の本文/図解品質はNO_CHANGE、同期未実施。PNG/正式publication/全4枠の本番受入は未達。
