# マーケットレポート配信システム 要件定義書
現行文書版：2.1｜改訂：2026-10-19 JST｜変更ID：DOCCTRL-20261019-HISTORY。過去に記載した「PRレビュー用」「未実装」「未解決」はその時点の履歴。現在の確定業務契約は本ファイル末尾の「現行差分統合 v2.1」と固定ID Google Docs v2.1を参照。GitHub main静的確認と実稼働成功は別判定。
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


## MRF-0800-20261029 — 08:00 issuance integration contract (Draft proposal)

- Keep one weekday 08:00 report identity/revision bound to one immutable, generation-pinned acquisition snapshot, the complete pre-save G2 body and its SHA-256, a human-reviewed scenario record, Google Docs document/revision/full-text readback, and the existing portal canonical/readback identity.
- Reject stale or post-cutoff evidence, TEST_ONLY evidence in the production path, any changed body/snapshot/identity, missing scenario review, ambiguous duplicate Docs, duplicate-slot identity conflicts, or a Docs/portal readback mismatch. Never publish after a failed stage.
- Exact retries may proceed only when report ID, revision, body hash, evidence ID, and snapshot ID match the durable create-only slot claim.
- TEST_ONLY acquisition on 2026-10-28 is limited evidence of the upstream acquisition/store path. It does not satisfy Docs, canonical, or portal acceptance. This requirement is proposed in a separate Draft PR and is not yet active on main.
- 12:00/16:00/21:00 schedules and existing publication gates remain outside the implementation scope. No production write or deployment was performed.


## MRF-0800-20261029 — importer handoff clarification

- The Google Drive file name must follow the existing source importer key, `マーケットレポート_YYYY-MM-DD_08-00`; the report title remains the first line of the body. The writer now keeps those identities distinct and validates the body with the existing saved-report contract before Docs creation.
- The existing portal importer reads pre-slot evidence from the checked-out `data/report-evidence/` path. A GCS generation alone is not visible to that importer. Until a protected, exact-generation GCS-to-importer handoff is implemented and proven, canonical portal publication remains NOT_RUN.



## MRF-0800-20261029 — isolated importer staging contract

- A TEST_ONLY GCS evidence object may be copied only by exact object generation and SHA-256 into a separately marked LOCAL_STAGING_ONLY checkout; create-only identical retries are allowed, conflicting bytes or identity stop.
- The existing importer may run against that isolated checkout only when the caller explicitly opts into strict issuance binding. Docs appProperties must match report_id, revision, body_hash, evidence_id, and snapshot_id; otherwise the report remains held/archived.
- The default scheduled importer path is unchanged. Staging code must not write Google Drive, GitHub main, or Pages. TEST_ONLY evidence and local staging output are not production issuance evidence.
