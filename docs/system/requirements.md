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

- A TEST_ONLY GCS evidence object may be copied only by exact object generation and SHA-256 into a separately marked LOCAL_STAGING_ONLY checkout whose root is disjoint from the importer checkout (neither is an ancestor of the other). Require a standalone `test` token in both project and bucket identifiers and an exact `test-only/` object-name prefix; substring matches do not qualify. Create-only identical retries are allowed; conflicting bytes or identity stop. Resolve and verify the destination path remains inside staging root before creating directories; reject symlink or junction escapes.
- The existing importer may run against that isolated checkout only when the caller explicitly opts into strict issuance binding. Docs appProperties must match report_id, revision, body_hash, evidence_id, and snapshot_id; otherwise the report remains held/archived.
- The default scheduled importer path is unchanged. Staging code must not write Google Drive, GitHub main, or Pages. TEST_ONLY evidence and local staging output are not production issuance evidence.


## MRF-INGESTION-20261030-01｜取込状態と公開状態の分離（2026-10-30 JST）
- REQ-12: 保存済みDocsのGitHub取込結果は、canonical保存、発行前evidence/Docs読戻しreceipt、Pages配備、公開後DOM読戻しを別段階で記録する。SOURCE_ARCHIVEDのみの取込を正式publication成功として報告しない。
- REQ-12a: evidence不足の本文は閲覧用canonical archiveに保存できるが、記録は「SOURCE_ARCHIVED_ONLY」とし、publication eligibilityを獲得しない。
- REQ-12b: Docs readback receiptがある場合もPages配備・公開DOM確認とは別状態とする。
- 適用範囲：GitHub取込ログと対応するCI。既存レポート、receipt、Docs、PNG、release schedule、publication gateの変更を含まない。

## DELIVERY-CLOSEOUT-20261101-01 — 保存本文の見出し認識（統合candidate）

- 保存本文の明示見出しとして `01｜見出し`、`第1: 見出し`、既存の番号付き形式を認識する。`結論：本文`、`最終判断：本文`、`まとめ：本文`はラベル以降の同じ段落本文を結論sectionとして保持する。
- 見出しではない説明文を見出しへ昇格しない。パース後も元の本文を改変しない。
- この認識修正は保存本文の取り込みに関するもの。28×5表、必須section、発行前Evidence、Docs読戻し、canonical/Receipt、Pagesの公開ゲートは変えず、過去枠の再発行資格を与えない。
- 適用状態: latest-main基点の統合candidate上で実装・ローカル回帰確認。GitHub mainへの反映と固定ID Google Docsの更新/読戻しは未実施。

DELIVERY-CLOSEOUT-20261101-01 追加受入条件: 回顧アーカイブ対象（2026-10-16 12:00/16:00/21:00）は、原本未発見・回顧レポートの区分・記録日時が一致する場合のみ履歴アーカイブとして扱う。正式公開枠へ昇格させず、検証スクリプト変更をPages workflowの対象パスへ含める。candidateで31件を検証しPASS。mainと固定Google Docsへの反映は未完了。

## 2026-11-04 現行差分統合 v2.2｜REPORT-ARCHIVE-CONTENT-AUDIT-20261104-01

- 保存記録は `data/report-archive-manifest.json` から取得し、対象JSONごとにschema/date/time/body/source statusを検証する。特定月をJavaScriptへ固定せず、manifestの一覧をもとに統合する。
- 正式発行データと閲覧用保存記録を区別。同一slotでは正式発行データを優先し、正式データの取得失敗だけで検証済み保存記録を破棄しない。利用可能データ確認は統合後に行う。
- 日付・時間帯ボタンとURLは実在するslotだけを選べる。指定slotがない場合は欠落表示とし、別日時の本文を代用しない。保存記録は正式発行へ自動昇格しない。
- 08:00必須28項目×5列QAに不合格の場合、警告を表示して未検証の市場表だけを隠す。本文と保存元の発行ステータスは変更しない。
- 部分取得失敗は取得済みデータと警告を表示し、全件失敗は原因と再試行案内を表示する。ログは対象ファイル、日時、HTTP status、検証結果を記録し、認証情報を出さない。
- 受入条件は11/02・11/03の各実在slot、10/30 21:00回帰、日付移動、URL指定、正本優先、取得失敗、不正アーカイブ除外、Pages公開後の実ブラウザ読み戻しとする。
- 実績：PR #193～#196 main統合、68slot/18日分の公開画面確認、Pages deploy run 41836815631 SUCCESS。PR #193/#194は日付・時刻を価格として誤認するアーカイブ表を抑止。PR #195/#196は08:00 QA未達を明示する。
- 未解決原本：10/22 12:00の復旧記録に12:00本文がなく、11/02 12:00の保存元状態情報に矛盾がある。元資料なしに修正・昇格しない。

## MR-ISSUANCE-CONNECT-20261104-02 — issuance transaction acceptance

- The existing PR #188 path must bind the same report ID/revision, immutable generation/hash-pinned pre-slot evidence, G2 body SHA-256, Docs ID/revision/full-text readback, canonical report, publication receipt, GitHub main commit, Pages workflow and actual public report JSON body.
- Formal importer invocation is scoped to the exact 08:00 report title and Docs ID; ordinary scheduled three-day import and TEST_ONLY staging guards remain unchanged. A duplicate matching Docs name, changed revision, partial canonical/receipt pair, conflicting same report identity, failed GitHub readback, failed Pages workflow, or public body mismatch blocks `PUBLISHED`.
- Identical retries may reuse an exact existing canonical report/receipt and must not create another main commit. If main commit completed but Pages/public readback did not, record partial completion and reconcile the exact commit/files before retrying Pages.
- Mock/isolated test success is TEST_ONLY. Production acceptance requires a separate authorized 08:00 E2E; this implementation does not change the four weekday schedules or grant retroactive publication eligibility.

### Invocation and public-index regression criteria

- Invoke the 08:00 module as `python -m scripts.run_0800_issuance`; `--help` must run without credentials, while missing input and invalid slot data fail closed as `BLOCKED` before creating cloud clients.
- Isolated public-mode DOM validation must use the public `reports.json` array shape, retain the existing `reports/` canonical corpus requested by page loaders, and serve the exact `reports/<reportId>.json` target source. It must require exactly one target reportId row and compare revision, date, time, fullText/body SHA-256, and the rendered report DOM before accepting the page.
- The read-only preflight returns overall `READY` only when each required check is `PASS`; an unverified GitHub `contents:write` scope stays `UNKNOWN` and yields overall `NOT_READY`. An explicit independent administrator attestation may move that check to `PASS`; it does not bypass the protected Environment or write gate.

### Follow-up acceptance: invocation, create-only, DOM, preflight

- The protected 08:00 entry point accepts only today's weekday 08:00 slot within the existing 40-minute window, requires a G2 bundle plus an explicit GCS object name and generation, reads that exact generation, and calls existing `run_issuance()`. It does not select a latest object or change the scheduled task definition.
- GitHub canonical JSON and publication receipt are a create-only atomic pair. Any existing mismatch or one-sided pair, stale main head with nonmatching files, compare-and-swap rejection, or uncertain commit readback blocks publication. A stale main head may be reconciled only when the entire target canonical/receipt/index file set is byte-identical, in which case retry reuses that commit without creating a second commit.
- `PUBLISHED` requires rendered report DOM identity (report ID/date/time/title) and source body represented by the verified SHA-256. Public JSON validation and rendered UI validation are separate checks.
- The Pages verifier must run the public-mode DOM validator against the actual HTTPS `report.html`/`reports.json` after the exact commit's deploy succeeds. If Chromium/Playwright is unavailable or the DOM identity/body differs, issuance remains blocked.
- The production publisher requires GitHub Actions `refs/heads/main`, the named `report-publication` Environment context, its approval gate, an administrator attestation of the separately supplied token's contents-write permission, and the existing explicit write gate; developer checkouts and other Environments remain blocked.
- A read-only preflight reports observable GitHub repository push access, active Pages workflow, protected Environment reviewers, Docs folder capability, exact Evidence generation access, and claim-bucket create permission through the provider's non-mutating permission-check endpoint. GitHub's read APIs cannot certify a fine-grained token's exact contents-write grant; that remains UNKNOWN and prevents overall READY until an authorized administrator attests it using protected `REPORT_ISSUANCE_CONTENTS_WRITE_VERIFIED=true`. Credentials are never emitted.
- These are code/isolated acceptance criteria only; they do not prove scheduled-task linkage or production Docs, main, receipt, Pages, or public DOM.\n\n## MR-ISSUANCE-PRODUCTION-READINESS-20261105-01｜本番接続準備（2026-11-05 JST）\n- GitHub上で確認したPR #188 headは e5b967b3ead9a8c0e503f8251a38ec78edf1ea46、mainは d5db82e9bf88657b612ec41a471124b6c343cf84。mainのみの31コミットは市場データ・履歴JSONの追加更新で、PR headは mergeable。履歴保全のためforce同期やデータファイル取り込みを行わず、通常のPR merge base解決に委ねる。\n- 現行Apps Script Master Schedulerは平日枠ごとに publishMarketReportSlot_ を呼ぶ。PR #188 CLIが要求するG2 bundleとevidence_ref.object/generationを生成・渡すコードは確認できず、ChatGPT定時タスクの実体から当CLIへの接続も未確認。正規G2 bundleなしに発行しない。\n- protected execution preflightは REPORT_ISSUANCE_APPROVED 等の自己申告値を承認証拠にしない。GitHub Environment APIが返すrequired_reviewers規則とmain ref/Environment名を別に検査し、当該runの承認実績は NOT_INFERRED とする。\n- 追加する手動 workflow は workflow_dispatch/read-only、対象ID・revision・evidence object/generationを明示し、write permission/発行Secretsを与えない。Environmentが実保護されているかは未確認。\n- 2026-11-05時点のpreflightは実Google/GCS/GitHub発行権限・対象G2同一性・Pages/DOM環境を確定できないため本番試験 NOT_READY。固定ID Google Docsの同期は未実施。\n\n受入手順：将来の平日08:00枠1件のみを指定し、(1)実取得時刻とEvidence generation/hash、(2)G2 freeze時刻/body SHA、(3)Docs fileId/revision/全文読戻し、(4)canonical commit SHA、(5)receipt書込みと読戻し、(6)Pages run、(7)公開JSONとDOM本文全文照合、(8)失敗stage/completed stages/retryableを保存する。既存slot衝突・不一致では停止し、承認なしのwrite/dispatchを行わない。

## MR-ISSUANCE-PRODUCTION-READINESS-20261105-01｜CI証拠追記
- CI code head 5538a8707f2179fcabde9ea5b4fa32239664a00e でissuance integration contract PASS：83 Python tests (17+39+16+11) とcompile/CLI smoke。https://github.com/matrixdiamond512-cell/Chat-GPT-Market-Report/actions/runs/41875493256
- isolated UI/DOM PASS：https://github.com/matrixdiamond512-cell/Chat-GPT-Market-Report/actions/runs/41875493440。その他8件も同じheadでPASS。これはActions隔離環境の結果で、本番Docs/GCS/GitHub canonical/receipt/PagesはNOT_RUN。
- main f43cc00f60d5a32fa96fa6cb4de440c7f971fc4a を2親同期commitに保持。main-only data/history変更はPR側の変更パスと重複なし。Google Docs固定IDへの同期はNOT_RUN。

## MR-ISSUANCE-ENTITY-20261105-02 — G2 producer/handoff acceptance

A production G2 must be frozen by a declared producer before Docs save. Its exact GCS bucket/object/generation must bind reportId, revision, fullText SHA-256, frozen_at, Evidence object/generation, evidenceId, and snapshotId. Reading an existing Docs file is not evidence that this pre-save G2 existed. Repository inspection found no producer that creates this bundle: Apps Script reads an existing Google Doc and publishes it; the scheduled ChatGPT task is external and its configuration was not inspectable. Until that producer and its trusted write identity are connected, issuance is BLOCKED_G2_PRODUCER_MISSING.

## MR-ISSUANCE-ENTITY-20261105-02 — trusted G2 producer requirement

A valid production G2 requires a declared producer that freezes the exact fullText, reportId/revision, fullText SHA-256, freeze timestamp, and exact pre-slot Evidence object/generation, evidenceId and snapshotId before Docs creation. The protected runtime must verify producer provenance as well as object bytes/generation. Existing Google Docs are downstream saved copies and cannot establish that source. Until the producer adapter is invoked by a verified task actor and its trusted writer identity is confirmed, report BLOCKED_G2_PRODUCER_MISSING; matching bundle fields alone do not permit preflight READY.

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

## MR-EVIDENCE-GCS-WINDOW-20261105-01｜発行前Evidenceの時刻・正本要件
- 対象枠のJST実行時刻は枠開始15分前以上かつ枠時刻未満に限る。workflow scheduleと手動実行は同じ条件を適用し、対象日を実行日から推測して遅延イベントを翌日同時刻へ付け替えない。
- この判定はmarket-data acquisition・GCS保存より前に行う。締切後・対象日違い・週末は `BLOCKED_SCHEDULE_WINDOW_MISMATCH`、遅延は `SCHEDULE_LATE` として停止する。
- GCSはEvidenceの正本とし、`if_generation_match=0` で作成する。保存後、固定generationを指定して再読戻し、本文バイト列/SHA-256、reportId、revision、Evidence ID、snapshot ID、元データhash、Evidence作成時刻、GCS作成時刻を検証する。既存オブジェクトの内容不一致は上書きせず停止する。
- GitHubのEvidenceファイルとGCS参照sidecarは監査用ミラーであり、GCS generationの読戻しがない限りREADYとしない。ミラーのみの成功を正本保存とみなさない。
- Actions scheduleの欠落/遅延は自身のjobから確実に判定できないため、実行履歴上の未観測は `SCHEDULE_NOT_OBSERVED`、起動後の時間窓逸脱は `SCHEDULE_LATE` に分ける。実GCS権限・実generation読戻しは本番接続検証までNOT_RUN。


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

## 2026-11-05 保護付きpreflight認証追補（MR-PROTECTED-PREFLIGHT-WIF-20261105-01）
- 認証付きread-only preflightは、保護Environment上でGitHub OIDC Workload Identity Federationを用い、指定された専用read-only Google service accountで実行する。service-account JSON keyは使用しない。
- WIF設定または実認証主体が未確認、Environment必須reviewer・対象Evidence/G2 generation・Docs保存先権限・GitHub権限・Pages/DOM依存が不足または未確認ならNOT_READYとする。設定診断は認証・外部接続を行わずREADYを返さない。
- PR #188のコード/契約テストはPASS。実際の本番Environment認証・本番Google権限確認はNOT_RUN。


## 2026-11-05 — MR-PROTECTED-PREFLIGHT-WIF-20261105-01 correction

- Read-only inspection found the GitHub Environment `report-publication` absent (the environment list contained only `apps-script-production` and `github-pages`). Prior wording that implied it already existed is corrected by this record.
- The authenticated preflight is blocked unless a separate unauthenticated GitHub API job confirms that `report-publication` exists and has at least one required reviewer. Missing/unreadable/unprotected Environment causes the WIF job to be skipped before authentication.
- Code head `e8e96bf1acce7bb101f0ff9a9c9ac0b057f3371a`; exact-head issuance contract [42032888516](https://github.com/matrixdiamond512-cell/Chat-GPT-Market-Report/actions/runs/42032888516) passed (preflight suite 21 tests). This is CI evidence only. Environment configuration and production authenticated preflight remain NOT_RUN / NOT_READY. Admin must create and protect the Environment before a future preflight.



## 2026-11-06 — MR-ENV-WIF-ISSUANCE-PREFLIGHT-20261106-01

- 認証付きpreflightの前段ゲートは、Environmentの実在とRequired reviewersの有効な対象、Prevent self-review有効、Environment管理者バイパス無効、deployment branch policyが`main`のみであることを確認する。GitHub APIの失敗・欠落・未対応フィールドはBLOCKED/UNKNOWNとし、認証を開始しない。
- 本番のEnvironment、WIF/IAM、Docs/GCS/canonical/receipt/Pages権限が未確認の場合はNOT_READYを維持する。自己申告変数やEnvironment設定値だけで実承認・権限をPASSにしない。
- GitHub variable-list APIが値を返すためpreflightでは呼び出さず、Environment variableの全一覧は未確認とする。必要な設定値は保護付きread-only preflight内で不足の有無だけを表示し、値をログへ出さない。
- CI変更と隔離テストは本番E2Eの証拠ではない。Google Docs固定ID同期、本番Environment/WIF/IAMと正式発行は未実施。


## MR-G2-TASK-HANDOFF-20261111-01 — 2026-11-11 JST

Source: user integration instructions and PR #188; prior head `b8ba8817f78294d9314f4fe20413b4b5b3dc4cbd`.
Affected canonical paths: requirements.md, specification.md, operations.md, DOCUMENT_CONTROL.md; project-control objective, decisions, lessons and evidence ledger. Google Docs fixed IDs remain unchanged; their current revisions and runtime access were not available, so synchronization/readback is NOT_RUN. Body-authoring changes are specified below for the fixed body-authoring manual, pending authorized access.

- Scope: task-output intake boundary plus an isolated chain; no production release. `task_output_handoff.freeze_task_output` reuses `TrustedG2BundleProducer.freeze_and_store`. Caller authentication must occur in an authorized host, outside task JSON. `VerifiedTaskInvocation` is a typed host contract, not an authentication implementation or a GCS provenance attestation.
- Body-authoring handoff contract: schemaVersion=1, report (date/time/report_id/revision), full_text with terminal newline, body_sha256, evidence_ref (object/generation/evidence_id/snapshot_id), frozen_at and scenario_review. Preserve full text and review quote offsets exactly. No Docs-derived substitute, inferred review, historical Evidence reconstruction or deadline extension is allowed.
- Independently configured evidence_reader reads the pinned generation; request-supplied Evidence bytes are ignored. The existing producer validates its exact bytes/hash/time/report/revision and persists G2 create-only. Return g2_ref object/generation/SHA-256, report/revision, Evidence reference and diagnostic invocation identity. Publication and notification remain NOT_RUN.
- Actual task-to-host authentication, callback/output access, installed Apps Script deployment/triggers and Google Docs permissions are UNKNOWN. The official scheduled-task documentation describes schedules/chat context and supported app events, but does not establish this account's task-to-GCS interface: https://learn.chatgpt.com/docs/automations . Therefore live task handoff is BLOCKED_G2_TASK_HANDOFF. No undocumented API or invented task webhook is used.
- Evidence must precede 08:00; review/freeze must remain within 08:00–08:40. The existing issuance CLI continues to enforce ownership and protected production gates. All four configured slots remain apps_script_legacy; weekday 08:00/12:00/16:00/21:00 and no weekend slots are unchanged.
- Isolation: task input -> exact Evidence -> immutable G2 -> fake Docs -> fake canonical/Receipt/Pages -> exact HTMLParser text; UI CI additionally feeds this generated canonical into the real report renderer and Playwright public-mode DOM validator. External stores/adapters remain simulated; this is not TEST ONLY live-service or production proof.
- Local verification: Python 3.13, ten targeted suites (task handoff, pipeline, portal, importer handoff, preflight, G2 handoff/producer, Evidence and WIF read/create-only), 168 tests, 167 PASS / 1 SKIP. Hosted final-head CI and browser DOM remain pending at this record's creation; older head successes are not reused.
- Read-only Environment API: report-publication exists and has a required reviewer, but prevent_self_review=false. Custom branch policy is enabled; exact branch inventory and admin bypass remain unverified. Protected preflight is not ready. Production WIF/IAM/GCS audit principal/Docs write scopes/GitHub write scopes are UNKNOWN; authenticated preflight and production E2E NOT_RUN. No configuration was changed.


### MR-G2-TASK-HANDOFF-20261111-01 — DOM regression correction

Head 8054d6286 passed nine related CI systems and strict-current-report, but UI validate run 42870725218 failed the dynamically generated body with one missing source line. Its log proves the task handoff chain succeeded and the real renderer dropped the market-section prose when no price rows were parseable. Preserve that original prose via renderRichText instead of replacing it with an empty-table message; no fabricated table or relaxed eligibility/DOM gate. Added a focused renderer regression. Final corrected-head Actions are pending; do not reuse the failed run as PASS. Environment exact deployment branch inventory was independently read as one main branch; prevent_self_review=false remains a blocker. The one local Python skip was the Windows directory-symlink privilege test, not an issuance success.


### MR-G2-TASK-HANDOFF-20261111-01 — title parsing correction and isolated index binding

The first renderer correction alone did not resolve UI run 42871382048. Local replay of the exact generated canonical proved legacyMarketRowsFromFullText interpreted the Friday title `(金)08:00` as gold price `08`. Exclude the exact canonical title before legacy price extraction; preserve original prose when no actual price rows remain. A Friday-title regression now exercises this path. The isolated chain also projects its own report into temporary indexes and uses the real GitHubPagesVerifier over fake storage/HTTP instead of accepting a fake Pages success; the generated canonical remains the input to hosted real-browser DOM validation. External live services remain NOT_RUN. Final-head CI must be checked independently.
