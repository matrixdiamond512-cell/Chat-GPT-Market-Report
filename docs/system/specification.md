# マーケットレポート配信システム 仕様書
> **統合正本｜2026-10-15** 生成元証拠連携・公開前検証を含むマーケットレポート配信システムの有効な技術仕様は本ファイルに一本化する。旧「変更仕様書」は履歴・差分証拠であり、独立した実装基準ではない。履歴中の古い状態や旧コミットの記述は本書末尾の統合仕様・現在の実コード検証に優先しない。PR #130はDraft・未マージであり、本番承認を意味しない。

2026-10-13 / PRレビュー用。3文書は独立。GitHub mainの静的確認・本番稼働・未マージPRは区別する。
実装で確認した契約：config/report_schedule.jsonのmainはweekday=08/12/16/21、saturday=なし、sunday=なし（PR #99 mainマージ後）。実ChatGPTタスクも土曜なし。apps-script/MarketReportWebSync.gsは本文PUBLISHED/図解NOT_READYを許容し、図解READY時のmanifest・Drive PNG bytes hashを検査。scripts/verify_morning_report_qa.pyは08:00の28行データQA。scripts/validate_drive_publication_receipt.pyはdate/time/title、publisher=chatgpt、status=saved、driveFileId/URL、savedAtを検査。
図解manifestはreport_id、revision、snapshot_id、body_hash、manifest_id、drive_file_id、png_filename、png_sha256、manifest_hash、numeric_validation、renderer_status等を照合する。DEBUG_PREVIEWを正式画像として公開しない。
.github/workflows/build-reports.ymlは発行データ整合の検証。deploy-pages.ymlは公開前DOM、Pages deploy、公開後index/PNG/live DOM照合。PR #98で追加したReceipt validatorの公開ワークフロー直接呼出しは、実Receiptの旧型スキーマと不一致のため撤回済み。現時点で新ゲートは有効化されていない。
受入：既存のreceiptの実在とCIを確認する。mainにないPR #94/97の機能を現行機能として書かない。旧文書の一律PNG公開前必須ゲートとの不一致を残課題として明記する。

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

## 2026-10-15 canonical JSON v2互換仕様追補（v1.12 / Draft）

- 新規producer証拠のみ対象：`canonicalization_version=report-canonical-json/v2`。ASCII identifier keyの再帰ソート、UTF-8、bool/null/safe integer、配列順保持、孤立サロゲート禁止。Python floatは`{"decimal_v2":"100.0"}`等のタグ付き文字列とする。GASは未タグの金融数値を拒否。
- 旧`snapshot_id`はPythonの既存`snapshot.digest`に基づくv1のまま保存。v2の`context_digest_v2`、`snapshot_digest_v2`を別名でSHA-256照合。v1のMarketReportProducerProof署名／公開検証経路はこの段階では切替禁止。
- `canonical_v2_golden.py`から出す日本語・null・float（100.0/-0.0/1e-7）・offset日時・市場arrayの5ベクトルで、GAS v2 canonical bytes、hash、テスト専用HMACの一致を検証。snapshot原本v1 IDは保持し、変更不能。
- E4/D1のCI PASSは新方式のオフライン互換性に限る。production issuer/HMAC鍵分離、実ChatGPT原文取得、永続private store、Docs/Pages E2Eを代替しない。

## 2026-10-15 D2 preflightコード契約追補（Draft）
`scripts/reporting/d2_preflight.py`は`market-report-d2-preflight/v1`構造を純粋関数で検査する。必須契約：lane=api-shadow、eligibility=SHADOW_NOT_ELIGIBLE、dry_run_only=true、allow_publication=false、external_tools=[]、web_search_calls=0、固定モデル版、営業日の08/12/16/21、immutable-context-snapshot/v1、strict-json-schema/v1、max_attempts=max_runs=1、Decimal入力・出力単価とtoken上限、USD run/month cap、private/immutable/readback/store-retention、timeout UNKNOWN停止、独立承認記録参照。参照文字列は独立認証ではないため、`api_send_allowed=false`と`publication_allowed=false`は常に維持する。worker外部APIやpublisherへの資格情報は追加しない。


## 2026-10-15 D2 Responses API offline契約（Draft）
`scripts/reporting/d2_responses_contract.py`は一切のHTTP、API SDK、秘密鍵、publisher実装を含まない純粋な構築／検査モジュール。`model=gpt-5.4-mini-2026-03-17`、strict `text.format.json_schema`、`tools=[]`、`tool_choice=none`、`store=false`、max_output_tokens上限4000。模擬レスポンスの`status=completed`、`id`、`model`、`usage`、assistant output_text JSONを検査し、refusal/途中終了/多重tool call/非一致観測値/重複JSON keyを拒否。`tests/test_d2_responses_contract.py`8件をCIに追加。実市場の全数値と意味内容の検証は別ゲートで未実装。

## 2026-10-15 D2 raw bytes／normalized JSON分離仕様（Draft）
- `CapturedResponse.raw_response_sha256`は元の応答UTF-8バイト列が明示提供され、重複JSON key・不正UTF-8・非有限値を拒否したうえでパース済み`raw`と再正規化bytes一致を検査したときだけセットし、それ以外は`None`。
- `CapturedResponse.normalized_response_sha256`はdictの確定的JSONシリアライズから求める別ハッシュ。本文の`body_sha256`も独立。型上・意味上の区別を残し、旧snapshot IDやv2 canonical証拠を変更しない。
- `tests/test_d2_responses_contract.py`にbytesの空白・整形差、原本とパース値の食い違い、重複キー、不正UTF-8、非bytes拒否を追加。依然としてSDK・ネットワーク・本番書込はない。

## 2026-10-15 D2 private evidence adapter仕様（Draft）
- `scripts/reporting/d2_private_store.py`に`LocalPrivateEvidenceStore`を追加。明示したPOSIX絶対パス配下に`shadow/<run>/<attempt>.json`のみ保管し、Git worktree内は拒否。
- ディレクトリ0700／証拠ファイル0600、所有者・ハードリンク・symlinkを検査。O_EXCLによる一度限りのファイル生成、fsync後、別descriptorで独立読み戻し、byte長・SHA-256照合を行う。receipt契約は`d2-local-private-evidence/v1`。
- byte hashとローカルreceiptはOpenAI API受信の真正性、Cloud IAM、暗号化、遠隔readback、跨ホスト同時起動排他、publisher署名／E5を証明しない。production storeは別実装、監査・鍵・暗号化・権限の確認が必要。

## 2026-10-15 D2 numeric claims／source bundle仕様（Draft）
- `scripts/reporting/d2_numeric_claims.py`：`verified_source_bundle(context,snapshot)`で既存凍結snapshotから構築した参照バンドル（report_id、revision、snapshot_id、cutoff、系列、marketType、asOf、source ID/URL、unit、priceValue/changeValue/changePct）を生成。モデルが値・出典を増やすことはできない。バンドルSHAは旧snapshot IDとは別のオフライン記録。
- `audit_numeric_claims(context,snapshot,body,claims)`は本文の字句数値出現位置を網羅的に抽出し、`{start,literal,series,field,source_id,as_of}`との1:1対応を要求。値はDecimal比較、パーセント単位、負のゼロ、未取得フィールド、参照時刻・出典ID、重複・欠損を検査。日時・銘柄名の数字の限定例外以外はBLOCKED。未知の数値エビデンスを自主生成しない。
- `d2_responses_contract.py`はshadow-responses-json/v2のstrict schemaに`numeric_claims`を追加し、Responseの取得後に数字監査を行う。成功時も`CapturedResponse.publishable=false`。既存の旧schema出力はD2で自動補正しない。
- `shadow_worker.freeze_shadow_input`で登録済みsource IDと登録URLのペア一致を必須に変更。IDだけ正しくURLが偽装された入力はfail-closed。ニュース等の独立検証ソース・意味論・利用許諾は別工程。

## 2026-10-15 統合仕様 v1.13｜生成元証拠・D1/D2・公開ゲート（単一正本）
**正本**：本書 `docs/system/specification.md` および同一内容の正式Google Docs「マーケットレポート配信システム_仕様書_統合正式改訂_2026-10-13」。**設計・提案と本番実装の区別**：PR #130はOPEN/Draft/未マージ。本書に記載する機能には試験実装・未実装もあり、本番反映／ChatGPTタスク変更／API課金／過去レポート公開を一切承認しない。関連詳細設計・旧変更仕様書・GitHubコメントは履歴または実装検証資料であり独立の規範を作らない。

### A. 目的、対象システム、採用済み判断
レポート生成時の原文全文・対象時刻・市場観測・生成完了情報を、Docs保存本文、producerが認証した証拠、GitHub正本、公開receipt、latest/dashboard、Pages表示まで改ざん／取り違え検知可能な同一証拠連鎖で結ぶ。市場データ取得・検証・本文/図解・ChatGPT表示・Google Drive保存・GitHub/API/Apps Script公開・読戻しまで本システムの対象とする。
- GATE-F0：従来ChatGPTタスクから独立して実行IDと原文全文を正式取得する方法は`BLOCKED_UNAVAILABLE`（従来の調査記録）。「A：調査継続」「B：Responses API専用生成worker」のうちB（別系統のshadow検証）をPR #130で選択済み。ただしChatGPT原文をAPI生成物として偽装せず、ChatGPTタスクは停止しない。
- 既存PR #128（複合見出し認識・dashboardキー等）や最新版mainとの整合は別途検証。過去2026-10-14の欠損証拠は後付け生成せず公開保留。
- 内部report_idは`YYYY-MM-DD_HH-MM`、可視タイトルは`マーケットレポート｜YYYY/MM/DD（曜）HH:MM`。revisionはproducer管理の正整数でDocs更新時刻から推定しない。同一revision/異本文を拒否し、重複Docから根拠なしに正本を選ばない。

### B. 境界と不可変データ契約
**Producer**：明示日時の`ReportContext`（report_date, report_time, report_id, data_cutoff TZ付き, previous_report_id, previous_business_day, revision, mode）を生成し、観測値・検証結果・出典・asOf・cutoffを含む`MarketDataSnapshot`を凍結する。後から「latest」や当日別時刻値で補完しない。原文のraw UTF-8 bytes/原文ハッシュ/モデル応答ID/生成時刻・完了状態を固定する。
**保存担当**：producer原文をGoogle Docsへ保存し、docId、revision、保存・読戻し時刻、全文、raw/canonical SHAを保持。Docs側で期待原文を再生成しない。改行・Unicode・文末改行等の正規化規格を明示し、数値・句読点・見出しの改変や情報削除を伴う「正規化」は禁止。
**署名担当**：producer認証済みのimmutable context/snapshot/原文digest/Docs identity/issuer/署名方式と版を権限分離して署名。公開権限者は署名権限を兼ねない。従来のHMAC共有鍵や任意のchat_evidence_id文字列は、実ChatGPT原文真正性の独立証明ではない。production候補は非対称署名等の発行鍵・検証鍵分離。secretは公開repo/Docs/ログへ置かない。
**Publisher**：署名済み元証拠とDocsのdocId・revision・本文readback/hashを比較。通過するまでGitHub公開系writer呼出し0件。証拠をDocsや公開データから逆算して作らない。
**図解レーン**：PNG品質は本文公開と独立管理。ただしreport_id/revision/snapshot_id/body hashを整合し、図解NOT_READYを本文公開成功と混同しない。

### C. ハッシュ・canonical化
旧snapshot_id（v1）は変更せず履歴と原本照合を保存する。新証拠のみ`report-canonical-json/v2`：ASCII key再帰順ソート、配列順維持、UTF-8、null/bool/safe int、floatは発行元で`decimal_v2`型付き文字列とし、非有限数・unsafe整数・不正Unicodeを拒否。PythonとApps Scriptでcanonical bytes、SHA-256、**テスト専用**HMACをgolden fixture一致確認する。旧snapshot IDをv2へ付け替え／再署名しない。v2 digestは`context_digest_v2`/`snapshot_digest_v2`で別記録。独立issuer真正性は未達。
API原本の`raw_response_sha256`は実際に受け取った元JSON UTF-8 bytesを検証できた場合のみ保持し、未提供時はnull。`normalized_response_sha256`はパース済みobject再シリアライズの別SHA、`body_sha256`は原文本文のSHA。いずれのハッシュ単独もプロバイダー認証を証明しない。

### D. D1/D2 shadow workerと安全条件
D1：オフライン入力凍結、6市場のstatus/source/asOf/cutoff/単位/観測値照合、同枠・attempt重複拒否、タイムアウト結果UNKNOWNなら盲目的再送禁止、fixture証拠の保存／読戻し。生体・認証・公開接続の成功とは区別する。
D2-preflight：`market-report-d2-preflight/v1`の固定モデル版、単回slot・run・attempt、strict JSON、web/tool呼出しなし、token上限・USD run/month cap、外部承認の独立検証、private immutable store/IAM/retention/readback、データ利用権、timeout reconciliationを要求。ローカル承認文字列では認証にならず、`api_send_allowed=false`/`publication_allowed=false`を維持。
D2 Responses境界：候補`gpt-5.4-mini-2026-03-17`、`tools=[]`、`tool_choice=none`、`store=false`、`text.format=json_schema`（strict）、4000 output tokens cap。response ID/status=completed/model/usage/output_text/拒否/未完了/重複JSON key/不正バイトを検証。実APIの可用性・課金は未確認／未承認。
D2 local private evidence：`d2_private_store.py`はworktree外POSIX試作。owner・0700/0600、O_EXCL/O_NOFOLLOW、fsync、byte-exact別読戻し／SHA、重複・改ざん・危険なpathを停止。**クラウド暗号化、IAM、保持、監査、遠隔永続ストア、分散ロックは未提供**。
D2数値claim：`d2_numeric_claims.py`が固定snapshotからsource bundle（report/revision/snapshot/cutoff/market type/asOf/source IDと登録URL/値/単位）を再構成し、Responses出力`shadow-responses-json/v2`の`numeric_claims`を本文字句offsetと1:1照合。価格、変化量、騰落率、符号付きゼロ、％、欠損・重複・異常時刻・URLすり替えを拒否。**意味論の全文検証ではない**。6市場にない金利・株式指標・ニュース統計・PER/EPS・イベント数値等は新しい独立ソース契約なしに許可しない。必要データ項目を削除してPASSを偽装しない。

### E. 公開前検証と回帰（未公開状態は保持）
公開前順序：①report_id/slot/revision、②実producerの認証済み証拠・署名、③凍結context/snapshot/cutoff/source、④独立した原文の真正性とハッシュ、⑤Docs ID/revision/全文readback、⑥SOP見出し・内容/数値claim・シナリオ、⑦重複revision/異本文隔離、⑧writerによるGitHub保存。1件でも欠ければ`BLOCKED`として書込み0。
対象全経路：`publishWebReportObject_`、`publishMarketReportSlot_`（定時/retry/watchdog）、`archiveMarketReportFromDriveWithoutLatestRollback_`、Structured/Historical import、reports.jsonなどを独立書換するwriter。未接続のwriterを通行可能と見なさない。
公開受入はGitHub単一commitではなく、正本・reports.json・latest-report.json・dashboard.json・receipt・Google Docs・GitHub Pages実表示を同一report/revision/bodyHashで読戻し証明すること。負例はproof欠落、issuer不正、自己署名、原文未取得、Docs ID/revision違い、本文ハッシュ差、future source、二重登録、過去枠差替、偽装時刻／単位／source URL、watchdog bypass等を含め、writer 0/PUBLISHED 0をassertする。
E4＝合成データ・クロス言語golden・関連CIが最新HEADで成功。E5＝実際の生成→保存→署名→公開→Pages読戻しを08/12/16/21の4枠で独立検証。**E4はE5ではない。**

### F. 実装工程と現状（2026-10-15、PR #130 Draft）
| 工程 | 現状 | 出口条件 |
| --- | --- | --- |
| P0 GATE-F0 | ChatGPT直接取得はBLOCKED_UNAVAILABLE、B案shadow設計へ移行 | 取得不能の独立証拠保持・生成物の混同禁止 |
| P1 Immutable context/snapshot | D1/D2 offline実装、実市場source/利用許諾は未了 | 実データ6市場＋必要指標の一次sourceと採時刻確認 |
| P2 Producer原文→Docs | 未接続 | 独立原文・raw hash→Docs版と全文一致 |
| P3 署名／canonical互換 | v2 goldenはoffline確認、production issuer未実証 | 鍵・信頼境界分離と独立検証 |
| P4 全writer・PR #128/main整合 | PR #130 draft試験・未統合 | 新mainと各writerのfail-closed CI |
| P5 shadow→限定運用 | offlineのみ、API/key/private cloud承認なし | 実API手動1slot/監査/rollback/費用承認 |
| P6 本番E2E | 未実施、公開BLOCKED | 4時刻の原文/Doc/proof/receipt/Pages読戻し一致 |
誤った旧時点コミットや過去のCI成功を最新HEADの証拠として引用しない。失敗や取得不能は根拠・時刻・段階別に記録し、遡及補完・公開ゲート緩和を行わない。

### G. 単一正本・変更管理規則
1. 技術上の**有効仕様は本書1本**。機能追加・変更・削除・Codex向け実装指示は、まず本書の対応章へ統合し、変更理由・施行範囲・実装/CI/E2E状態・更新日時を改訂履歴へ追記する。旧変更仕様書を新しい別基準として起こさない。
2. 要件定義書には要求事項、運用マニュアルにはSOP・停止/復旧手順のみ反映し、同一機能の詳細定義を重複規定しない。Google Docsの正式仕様書と本GitHubファイルを同期し、改訂後に両方をreadbackする。
3. 詳細設計・試験記録・issue/PRコメント・過去の変更仕様書は**非規範の参照資料**として保存するが、それぞれ独立の「現在の仕様」として運用しない。矛盾があれば本書の最新版と実コード・検証証拠に基づき整理し、解決しない矛盾はBLOCKEDと記載する。
4. 本章は仕様文書統合であり、PRのmainマージ／本番デプロイ／有料API承認／既存ChatGPTタスクの変更ではない。

**改訂記録**：2026-10-15 JST／v1.13（Draft）／旧「生成元証拠連携・公開前検証変更仕様書」1〜11節とD1/D2の後続追加を統合、重複・旧時点情報は履歴扱い。旧文書は更新停止・アーカイブ。

### H. D2オフライン通し試験（v1.14／2026-10-15、非本番）
- `scripts/reporting/d2_offline_pipeline.py` を追加し、D2要求構築→実行前の固定slot claim永続化→**注入されたテスト用関数から**Responses形式のUTF-8原本bytesを1回だけ受信→private原本保存・別descriptor読戻し→Responses構造・市場数値監査→模擬モデル費用上限検査→不変の結果receipt保存・読戻しを連結する。ローカルPOSIX試験用ストア以外は拒否する。
- 一意slot claimは `shadow/slot-<report_id>-r<revision>/claim` に O_EXCL で先に書き込み、同じslotの再実行は別プロセス・別run IDでも実際にfixtureが呼ばれる前に拒否する。障害・UNKNOWN・不正応答後もclaimを削除せず、独立した明示的reconciliation手順が整うまで盲目的retryしない。これは**単一ローカルstaging領域内の排他**に限り、複数サーバー・別ボリュームの分散排他ではない。
- 原文bytesを保存・読戻ししてから検証し、valid, invalid, budget超過, malformed raw, timeoutそれぞれを `shadow/<run>/<attempt>-result` に独立記録。synthetic responseでも`api_send_allowed=false`、`publication_allowed=false`、`publishable=false`。不正値を修正して成功扱いにしない。
- `tests/test_d2_offline_pipeline.py` に無課金の通し試験10件を追加し、CIのD1 Offline Market Report Shadow Workerから実行する。受信raw bytesのhashとdict再正規化hashは別概念であり、前者は実際のHTTP原文真正性を証明しない。
- **注入したCallableそのものの通信禁止をPython型で強制できるわけではない**。本モジュールにHTTP client/SDKは実装しないが、実運用では別プロセスのネットワーク遮断・資格情報不付与・API利用権限の独立承認が不可欠。ローカルPOSIX領域は暗号化/IAM/証跡retention/遠隔readbackを保証せず、専用workerの本番稼働・API課金許可・外部公開の判定には利用しない。
- **改訂記録**：2026-10-15 v1.14（Draft）／正式仕様書にのみ追記。別の「変更仕様書」は作成・更新しない。PR #130 Draft維持、既存ChatGPTタスク/本番公開を変更しない。

### I. D2クラッシュ・中断の読み取り専用復旧診断（v1.15／2026-10-15、Draft）
- `scripts/reporting/d2_private_store.py`の`read_for_diagnostics(object_id,max_bytes)`は、危険なパス、symlink、owner/permission不正、サイズ上限超過を拒否して、既存のPOSIX staging候補bytesだけを読み込む。対象が存在しない場合はNone。**受信の真正性、保存時点の改ざん不存在、署名、実APIの実行有無、producerの正当性を認定しない**。独立receiptがない状態で再計算したhashを「検証済み原本」と称しない。
- `scripts/reporting/d2_reconciliation.py`の`reconcile_d2_offline(context,snapshot,store,run_id,attempt_id)`は、新規書込・再送・外部ネットワークなしで同一枠のclaim/raw/result存在と内容を照合する。全結果で`retry_allowed=false`、`api_send_allowed=false`、`publication_allowed=false`を固定する。診断結果は次の限定分類：
  - `UNRESOLVED_NO_CLAIM`：ローカル使用記録なし。ただし実行していない証明にはならない。
  - `INTERRUPTED_NEEDS_MANUAL_REVIEW`：claimだけ、rawのみ後続結果なし、またはタイムアウトUNKNOWN。手動調査前の再送禁止。
  - `OFFLINE_BLOCKED_RECORDED`：検証不合格の既存結果を保存済み。後付けでPASSに上げない。
  - `INCONSISTENT_UNTRUSTED`：claim/run/responseの構造矛盾、検証ハッシュの食い違い、欠損・改ざん・危険なファイル。停止。
  - `OFFLINE_CONSISTENT_UNATTESTED`：結果JSON、raw bytesと固定snapshotの再検証が整合。ただしローカル一致であってprovider真正性／publisher権限／E5の証明ではない。
- `tests/test_d2_reconciliation.py`の**15件**でクラッシュ窓（claim直後／raw保存後）、timeout、正常fixtureの反復読取、malformed・重複JSONキー、claim/raw/結果改ざん、孤立原本、symlink、サイズ制限、読み取り専用を検証。GitHub ActionsのD1 Offline Market Report Shadow Workerで実行し、従来の失敗時停止ルールを緩和しない。
- **限界**：POSIX一台の試作で、ネットワーク隔離／IAM／暗号化／遠隔不変証拠／認証済み外部タイムスタンプ／複数マシン跨り排他／失敗時の正式再送承認手続きは未整備。完全停止したプロセスが原本を一度も送信しなかったかをローカル証拠だけで証明できない。実API trial・production署名・E5公開は引き続きBLOCKED。
- **改訂記録**：2026-10-15 v1.15（Draft）／旧変更仕様書を更新せず、本正式仕様書1本へ統合。

### J. D2送信前の計画費用境界とpreflight正規化（v1.16／2026-10-15、Draft）
**発見した実装上の差異**：従前の `d2_offline_pipeline.py` では模擬応答が返った後にだけ費用を比較していたため、将来のAPI「送信前の支出上限」としては不十分だった。また従来 `d2_preflight.py` の任意モデル／任意の安価な単価申告／旧generic response契約は、実際の固定 `d2_responses_contract.py`（Responses v2）と一致していなかった。
**修正契約**：
1. 実行計画は `max_input_tokens`（正整数、上限12,000）、`max_output_tokens`（正整数、上限4,000）、`max_model_cost_usd`（正の10進数文字列）を必須の検査対象とする。計画時に固定モデルの参照単価から `planned_model_cost_usd = (max_input_tokens×入力単価＋max_output_tokens×出力単価)/1,000,000` をDecimalで算出し、費用上限超過または不正な型・値なら**slot claim作成およびfixture responder呼出し前に停止**する。
2. 合格した計画の上限値、上限費用、計画額は書換不可slot claimと結果receiptの双方に収録し、復旧診断でも一致と計画額再計算を検査する。応答で申告された実入力・出力token数が個別capを超過する場合、事後結果は`OFFLINE_BLOCKED`となり公開可能にはならない。
3. `d2_preflight.py`が受け付ける `model_snapshot` は `d2_responses_contract.MODEL` と同一、`response_contract` は `shadow-responses-json/v2` と同一に限定する。従来の `strict-json-schema/v1` 記載は旧仕様とし、採用しない。入力・出力単価は `d2_responses_contract` の固定オフライン参照料金と一致を要求し、安い値の自己申告を拒否する。
4. 固定のオフライン参考単価は当該2026-10-15設計時点の `gpt-5.4-mini-2026-03-17` 入力USD0.75/百万token・出力USD4.50/百万token。単価は実課金直前に公式価格を再取得して検証すること。別モデルへの切替は独立した正式仕様変更・費用再見積・回帰が必要。
5. **限界**：事前計画上の12,000入力tokenは実APIに投入される入力の実測上限ではない。OpenAI側の実token算出、予想外の追加請求、課金の継続状況、月間累積費用を、このoffline見積だけで制限・保証できない。実API試験前に独立token計測／モデル実在・正式料金確認／課金上限／手動承認／月間実測台帳／ネットワーク権限分離が必要。本モジュールは送信機能なし、publishable=false、D2 API送信・E5公開は引き続きBLOCKED。
6. 回帰：`tests/test_d2_offline_pipeline.py`で計画超過時の呼出し0・claim0、料金record整合、token cap失敗を検査。`tests/test_d2_preflight.py`で偽の単価、別モデル、旧schemaを拒否。`tests/test_d2_reconciliation.py`でclaim/resultの見積改ざんとtoken cap超過の再評価を検査。CIは新HEADで再実行し、旧run成功を流用しない。

**改訂記録**：2026-10-15 v1.16（Draft）／統合済み正式仕様書のみに契約追加。変更仕様書は更新しない。

### K. D2正規入力token計測・月間費用ゲートのオフライン契約（v1.17／2026-10-15、Draft）
**背景・外部一次資料**：
- OpenAI公式「Counting tokens」 https://developers.openai.com/api/docs/guides/token-counting は、\`POST /v1/responses/input_tokens\` を公開し、Responsesで使う入力・指示・schema・toolの形式を含めモデルへ渡すtoken数を事前に計測できることを明記。返値は \`{"object":"response.input_tokens","input_tokens":正整数}\`（空入力で0も型上許容）。計測エンドポイントへの接続には別途API権限が必要。本実装は通信せず、実カウントを実行していない。
- GPT-5.4 Mini公式モデルページ https://developers.openai.com/api/docs/models/gpt-5.4-mini の2026-10-15照合では、固定 \`gpt-5.4-mini-2026-03-17\` を掲載し、通常text input USD0.75／百万token、output USD4.50／百万token。キャッシュ等の割引は保守的見積に使わない。料金の変更・専用エンドポイント割増・追加tool/データ保存料金の有無は、実際の契約・実行直前に再照合が必要。
- OpenAI公式「Spend limits」 https://developers.openai.com/api/docs/guides/spend-limits によれば、月間アラートは**通信停止を保証しない**。OrganizationおよびProjectのhard spend limitが有効であれば429エラーで対象トラフィックを停止するが、反映遅延のため閾値を若干超えることがある。OpenAIの利用枠・信用枠とは区別する。

**実装契約・非課金**：
1. \`scripts/reporting/d2_token_count_contract.py\` は現行 \`d2_responses_contract.build_request\` に必要な固定 \`model/instructions/input/tools/tool_choice/text\` を変更なく射影し、\`POST /v1/responses/input_tokens\` に送る*予定の*payloadを生成する。実際には一切HTTP送信しない。作成要求全体のSHA-256および計測payloadのSHA-256を別々に固定。新たなcreate要求フィールド・別モデル・tools・schema変更・指示文変更・token上限変更なら照合を拒否。
2. \`review_count_fixture\` は元UTF-8バイト列の模擬 \`object=response.input_tokens, input_tokens=int\` をstrictに検査（重複JSON key、非有限値、boolean偽装、未知フィールド、UTF-8エラー拒否）、入力計測capを超えた場合はBLOCKED。入力計測結果を使った予定最大出力との保守的単回見積を計算してrun capと比較する。fixture合格は \`OFFLINE_COUNT_SHAPE_PASS_NOT_ATTESTED\` のみ。OpenAI計測レスポンス自体にrequest SHA/model情報や署名は含まれず、**計測結果とリクエストの真の結合は権限分離した外部transport証跡で別途検証する必要がある**。
3. \`scripts/reporting/d2_monthly_budget.py\` は同じ \`InputCountPlan\` のモデル費用上限と、暦月JSTに対応した「当月実績（外部監査待ち）＋未決済予約＋次の単回最大モデル費用」をDecimalで加算。利用者承認の月額cap／Project hard cap／Organization hard capの**最小値**を超えれば拒否。両方のhard limitが有効でない設定も拒否。全データは現段階では合成値で、\`OFFLINE_MONTHLY_ARITHMETIC_PASS_NOT_ATTESTED\`でも\`send_allowed=false\`、\`publication_allowed=false\`。実使用額・予約・費用上限の真正な認証、他の実行との競合排他、課金の数分遅延を解決していない。
4. \`d2_preflight.REQUIRED_EVIDENCE\`に、公式token計測とその通信認証・直近料金・Project/Organization hard limits・当月usage・pending reservation照合の外部証跡参照を追加。**参照文字列を埋めるだけでは第三者の認証にはならず、\`api_send_allowed=false\`を解除しない**。料金計測、hard cap、アカウント支出実額およびprivate IAMの独立検証が必要。
5. GitHub Actionsに\`test_d2_token_count_contract.py\`（14件）と\`test_d2_monthly_budget.py\`（11件）を追加。無課金fixtureで入力リクエスト変化、認証されないcount、数値偽装、計測超過、月跨ぎ、二重hard limit、月間支出超過・価格の型を検証。計測APIを実際に呼ばず、主張されたcountやbilling値を真正だと見なさない。
6. 追加処理は現在のD2 **offline review** 専用。正規で認証済みのcount取得、実API請求額台帳の独立readback、暗号化Private Store、承認と上限制御、実provider response真正性は未接続。既存ChatGPTタスクの設定、publisher、過去分は変更しない。PR #130 Draft・main未マージ・E5未達・本番公開BLOCKEDを継続。

**改訂履歴**：2026-10-15 v1.17（Draft）／正式仕様書の本章だけに仕様追加。旧変更仕様書はアーカイブ・更新停止のまま維持。

### L. D2入力計測→月間予算→合成生成の連結ゲート（v1.18／2026-10-15・Draft）
**実装対象**：`scripts/reporting/d2_offline_prepared_run.py` に `run_prepared_offline` を設け、独立していた D2 入力token-count契約・月間予算検査・Responses合成生成パイプラインを**一つのオフライン呼出し経路**に接続する。現段階では外部ネットワーク接続、OpenAI API認証、課金、実生成、本番Writer権限は存在しない。
**処理順序（前提失敗は生成関数呼出し0）**：
1. `ReportContext/MarketDataSnapshot` を検証し、固定model・instructions・input・JSON schemaを含む現行Responses要求を生成する。別の最新データを暗黙に取得しない。
2. その要求と完全なSHA対応を持つ `InputCountPlan` を構築し、外部認証ではない**合成原本bytes**のinput count結果を検査。boolean、余計なフィールド、重複JSON key、限度超過、旧countと要求改変を拒否する。
3. `MonthlySpendInputs.report_id` と生成対象の `report_id` を完全一致させてから、月額の実績模擬値・未決済予約・次回最大モデル費用を三つの上限と照合する。ProjectとOrganizationのhard capがどちらも有効でない値はBLOCKED。月額請求の暦境界とAPI利用料金の最新性は別途一次認証が必要。
4. 前提が揃った場合にのみ、証拠をPOSIX非公開領域の `shadow/<run>/<attempt>-inputcount`（count原文bytes）と `shadow/<run>/<attempt>-preparation`（原文SHA、要求SHA、model単回cap、count値、予算比較、報告ID、snapshot ID、実行ID、**未認証fixture宣言**）へ`O_EXCL`で永続化・byte-exactに独立読戻し。重複オブジェクトや改ざんは停止。
5. その後に限り既存 `exercise_d2_offline` へ進む。既存のslot claim、timeout UNKNOWN・盲目的再実行禁止、raw response保全、数値claim監査、モデル費用上限、結果receipt・読戻しを維持する。生成後に preparation のcreate-request SHAと実行claimの SHA、入力・出力token cap、model費用capを照合する。不一致を成功に修正しない。
**受入テスト**：`tests/test_d2_offline_prepared_run.py`の15件で、正常な合成fixture一連確認、事前のcount/予算/ID/limit異常による呼出し0、別promptによる要求SHA差、二重起動とtimeout、生成結果不正・証拠独立readbackを検査する。従来のD1/D2各moduleテストもCI回帰させる。
**証明できないこと**：合成入力token-countと月次金額は自己申告に過ぎず、OpenAIが返した本当の結果でも、認証済みの請求実績でもない。ローカルハッシュ・パイプライン合格はprovider真正性／料金hard cap実適用／複数ホスト予約原子性／production issuer署名／Google Docs・GitHub・Pages公開の証明ではない。すべて`api_send_allowed=false`、`publication_allowed=false`。E5・実API・本番公開は引き続きBLOCKED。アーカイブした変更仕様書を再開しない。
**改訂履歴**：2026-10-15 v1.18（Draft）。技術仕様の唯一の正本は本書。

### M. D2.2準備証拠と生成結果の読み取り専用全連結復旧照合（v1.19／2026-10-15・Draft）
**目的**：v1.18の`input count→月間予算→非公開証拠保存→合成生成→結果記録`を、処理中断・改ざん後に**追加の呼び出し・書込なし**で安全に再点検する。既存のD2.1 `d2_reconciliation.py` はslot claim/raw/resultの局所確認までで、`-inputcount`と`-preparation`が当該要求・計測・月額予算と一致することは保証していなかった。
**実装**：`scripts/reporting/d2_prepared_reconciliation.py` の `reconcile_prepared_offline(context,snapshot,store,monthly_inputs,run_id,attempt_id,instructions)` は、同一run/attemptについて `-inputcount`（模擬公式計測原文bytes）、`-preparation`（合成計測/予算証拠JSON）、`slot-<report_id>-r<revision>/claim`（枠の使用記録）、`-raw`（合成Responses生バイト列）、`-result`（結果receipt）を、`LocalPrivateEvidenceStore.read_for_diagnostics`で**読み取り専用・最大16MiB・所有者/permission/symlink検査付き**で読込。
検証順は①存在状態確認、②準備証拠JSONの厳格なキー・型・偽造許可フラグ拒否、③凍結Context/Snapshotと明示的なinstructionsから元の作成要求・計測用要求のSHAを再計算、④未認証count原本を重複key/UTF-8/型・閾値の観点で再検証、⑤呼出し元が指定した**同じ合成月額入力値**で月間予算を再計算し、計測数・費用・月額残・限度額とprep証拠が一致するか確認、⑥存在する場合は既存`reconcile_d2_offline`でclaim/raw/resultを再監査し、prepとの作成要求SHAとrun・capを突合する。照合のためにモデルを再呼出ししたり、結果を書き換えたりしてはならない。
**限定結果**：
- `UNRESOLVED_NO_PREPARATION`：このローカルstagingに5種類の証拠が存在しない。ただし本物のAPIが未送信である証明にはならない。
- `INTERRUPTED_NEEDS_MANUAL_REVIEW`：countだけ、prepまで、claimだけ、その後のtimeout/結果未記録など。手動照合まで自動retry禁止。
- `INCONSISTENT_UNTRUSTED`：孤立した下流記録、準備証拠欠落、count/予算改ざん、モデル入力・指示変更、slot claim・raw・結果の不一致、危険なファイルなど。停止。
- `OFFLINE_BLOCKED_RECORDED`：準備は一致するが合成生成結果はBLOCKED。後付けで成功へ昇格しない。
- `OFFLINE_CHAIN_CONSISTENT_UNATTESTED`：合成準備・局所claim/raw/resultの内容上の一致のみ。第三者証明・provider署名・実料金・クラウド監査・production E5とは無関係。
**不変条件**：全結果で`retry_allowed=false`、`api_send_allowed=false`、`publication_allowed=false`、`externally_attested=false`。呼出し時の`monthly_inputs`自体は外部請求基盤と独立照合していない。局所ファイルのSHAが計算上一致しても、保存以降の完全な改ざん耐性と外部真正性は証明不能。複数ホスト間の競合・原子的月額予約・IAM/secret manager・本番計測transport・OpenAI API生成は未着手の独立課題。
**テスト**：`tests/test_d2_prepared_reconciliation.py`に20件を追加し、成功fixtureの繰返し読込、countだけ・prepだけ・claim後のcrash・timeout、月額使用/上限変更、SHA改変、計測raw変更、モデル指示変更、下流BLOCKED、孤立・欠落・UTF-8/重複キー・symlink、重複起動、保存内容非変更と実行関数呼出し増分0を検証する。CI`shadow-worker-d1-offline-ci.yml`に組み込み、従来ゲートの弱体化なし。
**改訂履歴**：2026-10-15 v1.19（Draft）。正式技術仕様の正本は本書のみ。旧変更仕様書は別正本にしない。
