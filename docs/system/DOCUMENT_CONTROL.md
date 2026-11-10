# 配信システム文書管理規程

現行版: 2.2
改訂日: 2026-11-04 JST
変更ID: REPORT-ARCHIVE-CONTENT-AUDIT-20261104-01
本規程は新しい要件定義書や仕様書の別冊ではなく、既存の文書を固定IDで管理する手順を定める。v2.0の旧未解決一覧は当時の履歴であり、末尾の現行追補v2.2、文書管理台帳の固定ID索引、GitHub mainの対応パスが現行正本。

## Google Drive 正式文書（固定名・固定ID）
| 文書名 | Google Docs ID | GitHub対応 |
|---|---|---|
| 要件定義書 | `102PMtKQ4DaXqV1G2RhE8vFtQ8qes-tvIvy2jYQda_xA` | `docs/system/requirements.md` |
| システム仕様書 | `1qL7f3yKwghuDb5PiAI3RhwFJUVUfLwGakC8z8EOJ9oI` | `docs/system/specification.md` |
| 本文作成マニュアル | `1M9LzxKgg8Y50uHSzE1OhML-lU-ufPhvh79xj_m1jWYQ` | 本文・図解ルール（参照） |
| 運用マニュアル | `1OUVDAMjv009VWlI48Jb8TVuzszy4TIkjgBrHlzbNxYg` | `docs/system/operations.md` |
| 文書管理台帳 | `1F5vH9_O0LUC9Dki0CNm1JDNVfg7gMYMcUCIxgeanE5g` | このファイル |

Google Drive 親フォルダー: https://drive.google.com/drive/folders/16tITmW93FFEeSYEOh3y7UNZiwvMktNWY

## 強制ルール
1. 既存の固定ID Google Docsを更新する。日付、Version、統合、改訂、最新版などをファイル名に加えた別ファイルの作成を禁止する。本文内の改訂履歴と Google Docsの版履歴を用いる。
2. GitHub配信正本も `docs/system/requirements.md`、`specification.md`、`operations.md` の固定パスだけ更新する。新規の `*_vN.md`、`*_最新版.md`、`*_変更仕様書.md` などを作成しない。検討内容はissue/PR、過去版はGit履歴で管理。
3. 作業開始前に変更要求ID、対象文書ID、GitHubパス、変更対象節、現行revision、関連PRを照合。Docsを更新する前に影響文書マトリクスを作成する。
4. 共通ルールの変更は、要件・仕様・本文作成・運用・台帳のうち影響する文書へ同じ変更要求IDと日付で反映する。ポータル側への変更だけで配信システム側を更新したことにしない。
5. 仕様変更と「GitHub main実装済み」「CI成功」「ChatGPTタスク起動」「Docs本文読戻し」「PNG」「publication receipt」「Pages全文・DOM」「通知到達」は必ず別ステータスで記録。現時点で検証できない項目はUNKNOWN。
6. 編集後に正本IDから読み戻し、名称、内容、最新版の表記、他文書との整合、GitHub差分を確認。未解決差異は文書管理台帳へ記入し、全件完了と偽らない。
7. 配信スケジュール等は記録ではなく現行main実装と実行ログを照合。古い障害履歴、未マージ案、OpenAI API shadow計画を現行機能に昇格させない。
8. 旧文書は削除せずDriveの`99_旧版アーカイブ`で保存。バックアップ、出典と旧版である表示、参照整合が確認されていないものは無断で廃棄しない。

## 2026-10-19 時点の既知の未解決
- 旧PNG必須公開ゲートと現行の本文PUBLISHED・図解NOT_READY独立状態の業務受入の整合。
- 10/17以後の実装・運用の全件差分監査。
- 定時4枠の本文、図解、Docs、receipt、Pages、通知到達のE2E確認。
- 旧文書の全件条項照合（長文3冊と2.x〜3.x群）。これらは履歴として保存する。

## 変更記録 MRFOLDER-20261019-01（2026-10-19 JST）
対象：GitHub `docs/system/requirements.md`、`specification.md`、`operations.md`、固定IDのGoogle Docs要件定義書・システム仕様書・本文作成マニュアル・運用マニュアル・文書管理台帳。
理由：My Drive直下に本文41件/PNG6件と本文フォルダー混在PNG3件があり、月別直接保存および結果の独立読戻しが必要。
実施：月別整理と重複保留フォルダーへの退避、稼働中ChatGPT定期タスクプロンプトへのフォルダー・重複防止・metadata読戻し指示追加。
未実証：次回の定時レポートでDocs/PNGが作成時から適切な月別親フォルダーを持つこと、完全本文読戻し・図解実体検証、GitHub/Pages等の一気通貫確認。実証できるまでE2E=UNKNOWNとする。


## 旧版差分照合と共通契約 v2.1（2026-10-19、DOCCTRL-20261019-HISTORY）

Google Drive正式文書は要件定義書、システム仕様書、本文作成マニュアル、運用マニュアルの4固定IDと文書管理台帳（前節の表）。名前とIDを変えず改訂。GitHubも`docs/system/requirements.md`、`specification.md`、`operations.md`、本ファイルの固定パスを改訂し、版付き・日付付き文書を増殖させない。

### 旧変更の採否判定
- 旧作成運用マニュアル2.x～3.40の92ファイル、統合前ドラフト16ファイル、配信v1.6～v1.9群と10/19 mainを照合対象にした。3.40は大部分の累積変更を収録するが枝分かれした旧版に個別追補がある。版番号だけで正本を決めず、実装日・後続廃止・mainコードとの整合で分類。
- 採用：平日4枠、08時28×5、12/16/21時実出来事、イベントJST時刻、六市場の銘柄/限月分離、定時evidence、原文と図解、月別Drive親の読戻し、Sheets欠損監査/空セル限定補充、日本33業種・US11セクター履歴、WGC世界月次とGLD/IAU、BOJ出来高/価格日足の出典分離。
- 廃止・歴史：07時・土曜配信、旧08:20等転送型、Crypto Fear & Greedの必須心理指標化（後日削除）、10/13時点の土曜08時main衝突（PR #99解消）、過去のDraft/未実装状態の主張、図解Mermaid限定。
- 運用で峻別：通常の本文個別公開PUBLISHEDと図解NOT_READYを同一視しないが、全工程VERIFIEDには図解PNG・manifestの実証が必要。公開資格gateは無断で緩和せず、差異は現行コードとlive evidenceで判断。
- 非canonical閲覧：10/16・10/19過去補充版、アーカイブ表示、日付タブを正規publication receiptや当時のsnapshotへ遡及昇格させない。ポータルの不要バナー復活禁止。
- 本文専門ページのUI/配色・数式・GASファイル名などの細部はGitHub mainの対象実装へ参照を固定し、アーカイブの旧個別規定をそのまま新しいレポート本文必須項目へ昇格させない。ただしデータ・分析・公開の連携事項は配信システム変更管理に含める。
- 2026-10-19時点の確認不能：ChatGPTの次枠自動保存と通知の実着、すべての4枠のライブE2E。これは「過去の文書に差分がある」こととは別の実稼働受入試験。


## DRIVESOURCE-20261020-01｜Drive同名ファイルの最新保存版とGitHub公開正本の分離（2026-10-20 JST）
- ユーザー指定の「同一日時・同一種別はDrive保存日時が遅い方」を、Google Drive createdTime の降順で判定する。modifiedTimeは編集・移動等で変わるため保存日時の代わりにしない。対象は18件のGoogle Docsと3件のPNG、計21対象日時。Drive月別通常フォルダーには各日時1件を残し、古い候補は「同名ファイル確認待ち」に保全した。
- GitHub `data/drive-source-selection.json` がGoogle Drive実測の選定結果を保持する。レポート画面のDrive保存版リンクと `drive-source-selection.html` はこの一覧を参照する。ユーザーに選定版のID・リンク・検証状態を示すが、**これはGitHubの正規発行原本を無条件に書き換える仕様ではない**。
- 最新保存版の本文18件のうち10件は構造・分量を点検可能、8件は空文書または短文。後者を既存の公開済み全文に上書きしない。前者も発行前snapshot、Google Docs revision/全文一致、原本revision、receipt、公開整合の証拠が揃わなければ既存canonicalは変更せず「正式公開保留」とする。後から発行前証拠を捏造しない。
- 図解3件はDrive上の最新保存日時・PNG MIMEを確認。GitHub Pagesでの画像実体、SHA-256、manifest、snapshot/本文との対応が未検証のため図解正式READYへ昇格させない。旧ファイルは削除しない。
- 公開ポータルの参照ページは正式公開と保存版の区別を表示し、公開中の本文全文・最新レポート・dashboard・receipt・公開ゲートを黙って切り替えない。E2E、正式canonical改訂、PNG正式公開の状態は引き続きUNVERIFIED/BLOCKEDと明記する。
- 変更確認対象：本書、上記3システム固定文書、`report.html`、`assets/js/report-drive-source-reference.js`、`drive-source-selection.html`、`data/drive-source-selection.json`。Google Driveの固定ID文書側の同期とライブPages確認は別工程として記録する。


## MRF-0800-20261029 — change record

- Source: user request to restore the weekday 08:00 issuance path; TEST_ONLY Cloud Shell outputs for 2026-10-28; independent Draft PR based on main observed at e70751bc4a202c84f4322df8748a08775d836458.
- Affected canonical files: docs/system/requirements.md, docs/system/specification.md, docs/system/operations.md; root AGENTS.md; project-control objective/evidence/decision/lesson records. Existing fixed Google Docs IDs were not written.
- Code scope: proposed fail-closed G2/evidence/Docs/portal transaction adapter and offline contract workflow. No main, production, Drive, or Pages changes.
- Verification: external TEST_ONLY GCS generation readbacks were operator-provided and all three passed; new code tests require hosted Actions. Docs API, production GCS, existing canonical importer, and public portal E2E are NOT_RUN.
- Open outcomes: connect trusted G2/body freeze and independent scenario review; configure production identities/folders/buckets; implement approved invocation of the existing importer; run external E2E and live DOM verification. Do not report production recovery complete.


- MRF-0800-20261029 continuation: corrected Drive filename compatibility with the existing source importer and added existing-body validation before Docs save. Inspection found the remaining handoff boundary: main importer consumes `data/report-evidence/` from its checkout; TEST_ONLY/production GCS evidence is not automatically provided. The existing manual-dispatch workflow applies canonical data to main and dispatches Pages. No dispatch or external write was run. Portal E2E remains NOT_RUN.



## MRF-0800-20261029 change record — isolated importer staging

Affected stable paths: `AGENTS.md`, `docs/system/requirements.md`, `docs/system/specification.md`, `docs/system/operations.md`, `scripts/reporting/importer_handoff.py`, `scripts/sync_reports_from_drive.py`, `tests/test_importer_handoff.py`, and `.github/workflows/0800-issuance-contract.yml`. Verification: hosted issuance, delivery-health, and frozen-cutoff Actions all PASS on code head `2642412`. Limits: only offline/mock contract verification; TEST_ONLY cloud handoff, Google Docs readback, canonical importer runtime, and public portal remain NOT_RUN. No Google Docs or main/Pages write occurred.


## MRF-0800-BRIDGE-20261030-01 — isolated importer bridge contract test (2026-10-30 JST)
Source: user-directed continuation of Issue #176 / Draft PR #188. Changed `tests/test_importer_handoff.py` only for code behavior; project evidence records updated in `docs/project-control/{OBJECTIVE_CARD,EVIDENCE_LEDGER,DECISIONS,LESSONS}.md` and `HANDOFF.md`. Test composes pinned-generation TEST_ONLY staging → existing importer `publication_evidence(..., require_issuance_binding=True)` → exact Docs revision/body/evidence/snapshot binding, including a tampered-body-hash hold. Formal requirements/specification/body-authoring/operations/Google Docs fixed-ID contents: NO_CHANGE (test-only verification; no delivery contract or production behavior changed). Local focused suites: 12/12 handoff and 12/12 issuance pipeline PASS; py_compile and diff check PASS. Exact-head hosted CI pending until push. Fake GCS/Google modules only; actual GCS, Docs, poll/apply, portal and schedule remain NOT_RUN.


## MRF-0800-BRIDGE-20261030-01 — staging prerequisite recheck (2026-10-30 JST)

Source: user-directed continuation of Issue #176 / Draft PR #188, current main `ec3e38b56397686c781e61de7efe97baeec48544`, code head `7a1b751923dc40c1cfae26e980f49bc10f7b82c9`. Affected paths: `docs/project-control/OBJECTIVE_CARD.md`, `docs/project-control/EVIDENCE_LEDGER.md`, and `HANDOFF.md`; this control record. Formal requirements, system specification, authoring manual, operations, fixed-ID Google Docs, code and production artifacts: NO_CHANGE. No credentials or report body copied into records.

Verification: read-only local and Drive prerequisite recheck; importer `--apply` was NOT_RUN because no staging root/marker, no staged evidence, and no usable GCS authentication was observed; the existing 2026-10-28 Doc is labeled `閲覧用分析版` and does not provide a matching pre-save G2 body/hash or same-run receipt. Strict `appProperties` binding remains UNKNOWN. Evidence ledger and HANDOFF record the exact evidence and limits. No external writes, main change, or Pages deploy occurred.

Unresolved: provision/authorize an isolated TEST_ONLY identity and exact-generation object; provide one coherent issuance-bound G2/Docs readback; stage into a separate marked checkout; run strict dry-run and only then `--apply` if every binding passes. PR #188 and PR #189 remain separate Drafts; their shared importer changes have not received combined validation.


## 変更記録 MRF-INGESTION-20261030-01（2026-10-30 JST）
対象: GitHub固定パス docs/system/requirements.md、specification.md、operations.md、本規程、scripts/sync_reports_from_drive.py、scripts/reporting/ingestion_outcome.py、tests/test_ingestion_outcome.py、.github/workflows/market-report-sync-recovery-ci.yml、project-control記録、HANDOFF.md。
理由: Importerがarchive-onlyのsourceについても VERIFIED_REPORT_INGESTION_AND_PUBLICATION と出力し、取込と正式公開の状態を誤って一つに見せていたため。
変更: stageごとの明示ログへ置換し、archive-only・Docs読戻しreceipt・未認識statusを独立表示。該当する回帰テストをCI対象に追加。
制約: main merge、Google Drive正式文書更新、本番Docs/PNG/receipt/report変更、Pages deploy、schedule/Cloud設定変更なし。
検証: Python 3.13.14でworkflow対象の6モジュール38 tests PASS、追加証拠回帰3モジュール24 tests PASS、py_compile PASS。test_report_contract.py / test_publication_evidence.pyはWindows環境にIANA tzdataがなくZoneInfoNotFoundErrorでBLOCKED。Hosted CIはPR作成後。E3–E5本番E2EはNOT_RUN。
未解決: CI最終head確認、PR review/merge、Google Drive固定ID文書への同期判定、将来slotでのlive Docs/canonical/Pages acceptance。


## MRF-INGESTION-20261030-01 evidence-link correction (CORRECT, 2026-10-30 JST)
The four-slot HANDOFF matrix originally linked 2026-10-29 report JSON paths at main `52e99701f3bc71a77bdde31729e0f887f44a9135`, where those paths were absent. Repointed its read-only evidence links to current main `ec3e38b56397686c781e61de7efe97baeec48544`, where the four JSON files are present and each has `SOURCE_ARCHIVED` / `infographic_status=NOT_VERIFIED`; the four receipt paths are absent. No requirements, pipeline behavior, reports, receipts, Docs, PNGs, Pages, or external services were changed.


## MRF-0800-IMPORTER-COMBO-20261030-01 — integrated importer validation record (2026-10-30 JST)

Source: user-directed continuation of Issue #176 and Draft PRs #188/#189. Base/current main `ec3e38b56397686c781e61de7efe97baeec48544`; integrated PR #188 head at validation `d8394400dac2935f338d4d2ae9c068db689526eb`. Affected stable paths: `scripts/sync_reports_from_drive.py`, `scripts/reporting/ingestion_outcome.py`, `tests/test_ingestion_outcome.py`, `.github/workflows/market-report-sync-recovery-ci.yml`, and the previously added #188 issuance modules/tests/workflow; formal GitHub docs `requirements.md`, `specification.md`, `operations.md`; project records and `HANDOFF.md`. The body-authoring manual and fixed-ID Google Docs were not changed.

Verification: exact-head hosted issuance, sync recovery, frozen-cutoff and delivery-health runs 40989666087 / 40989665981 / 40989666048 / 40989666122 all SUCCESS; logs confirm 12 + 12 importer contract tests and 4 ingestion-outcome tests. E2 fixture/integration evidence only. Unresolved: actual TEST_ONLY GCS staging, matching Docs issuance binding, isolated importer run, canonical receipt, Pages/public DOM and scheduled-slot acceptance remain BLOCKED / NOT_RUN. PR #189's changes are incorporated into PR #188 for combined review; both drafts remain open and unmerged. No production/Drive/main/Pages writes occurred.

## MRF-0800-STAGING-BOUNDARY-20261030-01 — isolated TEST_ONLY staging safety review (2026-10-30 JST)

Source: user-directed continuation and static review of PR #188 at code head b936d9ddeb56608ad2b04d0c01488f9852496aa6; base main ec3e38b56397686c781e61de7efe97baeec48544.
Affected fixed paths: docs/system/requirements.md, docs/system/specification.md, docs/system/operations.md, scripts/reporting/importer_handoff.py, tests/test_importer_handoff.py, this control record, project-control records, and HANDOFF.md. Fixed-ID Google Docs were not edited.
Change: require importer and staging roots to be disjoint in both directions; require a standalone `test` token in GCS project and bucket names plus the exact `test-only/` object prefix; verify resolved destination containment before and after directory creation. Add regression coverage for ancestor-root overlap, substring false positives, invalid object prefixes, and symlink escape.
Verification: code/test head 4125df20409bcb0337677ba12ec2e87590b2d8db. Hosted issuance contract 40990908975, synchronization recovery 40990909005, frozen-cutoff 40990908966, and delivery-health 40990908970 all SUCCESS. Issuance logs show 12 issuance tests and 16 importer-handoff tests PASS. Evidence level E2, limited to hosted CI and fake adapters.
Limits/unresolved: no independently authenticated GCS read, issuance-bound G2/Docs readback, staging invocation, importer --apply, canonical/receipt write, Pages deployment, or public DOM verification. PR #189 remains OPEN/Draft with duplicate importer changes. No production, Drive, main, or Pages write occurred.

## DELIVERY-CLOSEOUT-20261101-01 — source parser and importer integration candidate (2026-11-01 JST)

Affected GitHub fixed paths: `docs/system/requirements.md`, `docs/system/specification.md`, `docs/system/operations.md`, this control record, `scripts/report_source_contract.py`, `scripts/sync_latest_report_publication.py`, `scripts/sync_reports_from_drive.py`, the sync recovery workflow, and focused parser tests. The body-authoring manual requires no change because this candidate accepts existing source forms without changing generation rules.

Candidate includes PR #188 issuance integration, PR #189 truthful importer status helper, and the minimal required parser behavior from PR #187. Implementation remains on a local branch until exact-head hosted CI/review and existing merge approvals. Fixed Drive Docs IDs (requirements `102PMtKQ4DaXqV1G2RhE8vFtQ8qes-tvIvy2jYQda_xA`, specification `1qL7f3yKwghuDb5PiAI3RhwFJUVUfLwGakC8z8EOJ9oI`, operations `1OUVDAMjv009VWlI48Jb8TVuzszy4TIkjgBrHlzbNxYg`) were not written/read back; no external document update is claimed. The existing publication gates and reports/receipts/PNG were not changed.

2026-11-01 update: PR #172's still-needed retrospective identity/timestamp checks and Pages workflow path trigger are also included in the candidate. Local recovery validation passed on all 31 archived slots. Exact-head hosted CI passed for the preceding code head; this final #172 patch remains pending exact-head hosted CI. Fixed-ID Drive Docs and GitHub main remain unmodified; the updated candidate stays OPEN/Draft pending review. Production GCS/Docs, schedule history, canonical receipts, Pages public DOM, notifications, and ten-workday observation remain NOT_RUN.

## 2026-11-04 改訂記録｜REPORT-ARCHIVE-CONTENT-AUDIT-20261104-01

- 対象固定Google Docs：要件定義書 ID `102PMtKQ4DaXqV1G2RhE8vFtQ8qes-tvIvy2jYQda_xA` revision `AHj4eMQ4aATq9nIBs5IK1h2cWbicH4qM-GESxHj18sKXWL4-c5GmT_q9X2r2vOVNcftJAB6xZ3vgBFtYzzDyKIzdm5xGSzKuZ_A4onsF8N4`; システム仕様書 ID `1qL7f3yKwghuDb5PiAI3RhwFJUVUfLwGakC8z8EOJ9oI` revision `AHj4eMQYKTJWnqv7gPwXTq7q8n1bivxpZXDDiFTAZde2kr7V2J0v-kAGpNt66qOmuLN5j-ZmhukWlmGnveT2PYbu7EmDnqiuxw6C9VCkJfE`; 運用マニュアル ID `1OUVDAMjv009VWlI48Jb8TVuzszy4TIkjgBrHlzbNxYg` revision `AHj4eMQMINuad4YxThu6BGcWJWXF6c_lQWpcuWTU4mRmgqOM7Hwewj-QKQOdzOXfhD8xJuV_1p3JiwusxeRNelGjwJYhaM_gNPkdeooWkoc`; 文書管理台帳 ID `1F5vH9_O0LUC9Dki0CNm1JDNVfg7gMYMcUCIxgeanE5g` revision `AHj4eMRRPYfcfxG-ZAFWkNnuS1mROzpCaF3OJEWII0UMfs15zQbeK7AIS_H8l_BfLbHuJMBymrcxHPo0TVIGT4G_iQMnckxp08d7S5xiRPw`. 各文書は同じIDから読み戻し、変更見出しと対象本文を確認した。
- GitHub固定パス：`docs/system/requirements.md`、`docs/system/specification.md`、`docs/system/operations.md`。PR #197で更新し、PR #193～#196の表示修正・QA表示要件を同一変更IDで反映する。
- 受入根拠：PR #193～#196 main統合、UI/アーカイブCI成功、Pages deploy run 41836815631成功、公開画面の68slot/18日分読み戻し。
- 未解決原本：2026-10-22 12:00本文欠落、2026-11-02 12:00 source status矛盾。状態値を書き換えない。市場価格を全件外部照合した結果とは主張しない。

## MR-ISSUANCE-CONNECT-20261104-02 追補｜2026-11-05 JST

影響文書：固定パス `docs/system/requirements.md`、`docs/system/specification.md`、`docs/system/operations.md`。既存Google Docs固定IDは要件定義 `102PMtKQ4DaXqV1G2RhE8vFtQ8qes-tvIvy2jYQda_xA`、仕様 `1qL7f3yKwghuDb5PiAI3RhwFJUVUfLwGakC8z8EOJ9oI`、運用 `1OUVDAMjv009VWlI48Jb8TVuzszy4TIkjgBrHlzbNxYg`。今回はこの環境からDocsを更新していないため、Docs本文読戻しはNOT_RUN。

変更理由：PR #188の発行接続を定時入口・main create-only再試行・画面DOM照合・本番read-only preflightまで具体化する。GitHub仕様/要件/運用の固定パスとproject-control記録へ同一変更IDで追記。Node構文/画面回帰と差分検査PASS。コードを既存PR branchへ追加済み。PythonとHosted CIはWindowsローカルでは未実行で、更新後SHAのActions実行中。実績はこの追補だけで本番成功へ昇格しない。

追加実装：Pages verifierが公開JSON照合後にpublic-mode Chromium DOM検証を必須実行し、reportId/date/time/title/body不一致やDOM実行環境欠落で停止する。08:00入口/Docs/GitHub/Pages失敗時のstageと累積completed stagesを返す。CIのpublic-mode fixtureはローカルに隔離したsiteを使う。実行結果は最終PR SHAのActionsで更新し、固定Docsの書込み・読戻しは引き続き未実施。

## MR-ISSUANCE-CONNECT-20261104-02 CI補正｜2026-11-05 JST

- 修正理由：preflightテストが管理者attestation済みのGitHub checkを`UNKNOWN`と誤期待し、公開DOM CIでは単一オブジェクトをreports.jsonへ置いていた。実行手順も直接スクリプト起動の表記が残っていた。
- 対象：同じ固定パスの要件定義・仕様・運用マニュアル。管理者確認済みpreflightを`READY/PASS`、未確認を`NOT_READY/UNKNOWN`とする別テストを維持し、`python -m scripts.run_0800_issuance`、公開索引配列、reportId/revision/body hash/DOM一致を明記。
- Actions追跡：旧head `cc3f8ff0` のrun `41864195550` はpreflight期待値不一致、`41864195592` は単一オブジェクトを配列として読めなかったためFAIL。head `748d5c7f` では契約スイート/CLI smokeが成功し、UI DOM fixtureで追加の404が発覚。画面rendererが同時に読む `reports/<reportId>.json` が隔離siteになかったため、fixture routeと隔離siteの双方で正本detailを用意する修正を追加した。最終headの再検証結果を別途記録する。
- 再検証補正：head `362a0042` では画面loaderが既存の2026-09-18 4枠canonicalも要求していたが、隔離siteへ対象fixtureだけを置いていたため404になった。次のheadで既存の`reports/` corpusをコピーし、対象canonicalを追加する。失敗URL/statusを出力し、任意favicon 404だけ除外する。その他のHTTP errorは引き続きDOM validationを止める。
- CLI補正：bundleの日時・G2/evidence参照をクラウド接続前に検証する純粋関数へ分離し、認証設定のないモジュール実行でも不正日付が`BLOCKED`になる回帰テストを追加した。新headの契約CIで検証する。
- 証拠水準：隔離テストと最終head Actionsの結果を個別に記録する。待機中・未開始のActionsはPASSと扱わない。固定ID Google Docsは今回も更新・読戻ししていない（NOT_RUN）。
- 制限：本番Docs/main/receipt/Pages書込み、Secrets・Environment・定時タスク変更、PR mergeは行わない。将来の08:00承認付きE2Eが必要。\n\n## MR-ISSUANCE-PRODUCTION-READINESS-20261105-01｜変更記録（2026-11-05 JST）\n対象固定パス：docs/system/requirements.md、docs/system/specification.md、docs/system/operations.md、docs/system/DOCUMENT_CONTROL.md。PR #188のpreflightで環境変数自己申告をEnvironment reviewer保護証拠と扱わず、実API reviewer規則の確認と当該run承認の証拠水準を分離する。手動workflow_dispatchは読取り専用・単一対象・Secretsなしとし、G2生成元の未接続を明記する。\nコード/CI検証は本変更SHAでのActions完了後に記録する。本番G2/Docs/canonical/receipt/Pages E2EはNOT_RUN。Google Docs固定IDへの同期は未実施。

## MR-ISSUANCE-PRODUCTION-READINESS-20261105-01｜CI証拠追記
- CI code head 5538a8707f2179fcabde9ea5b4fa32239664a00e でissuance integration contract PASS：83 Python tests (17+39+16+11) とcompile/CLI smoke。https://github.com/matrixdiamond512-cell/Chat-GPT-Market-Report/actions/runs/41875493256
- isolated UI/DOM PASS：https://github.com/matrixdiamond512-cell/Chat-GPT-Market-Report/actions/runs/41875493440。その他8件も同じheadでPASS。これはActions隔離環境の結果で、本番Docs/GCS/GitHub canonical/receipt/PagesはNOT_RUN。
- main f43cc00f60d5a32fa96fa6cb4de440c7f971fc4a を2親同期commitに保持。main-only data/history変更はPR側の変更パスと重複なし。Google Docs固定IDへの同期はNOT_RUN。


## MR-EVIDENCE-GCS-WINDOW-20261105-01｜変更記録
- 理由: 2026-11-05 03:52 JSTに動いたschedule runが当日の21:00枠として処理され、許可窓・データcutoffの判定前に後追い取得へ進む経路を修正する。GCS正本とGitHub監査mirrorのgeneration結合も実装する。
- 固定パス: `scripts/persist_report_slot_evidence.py`, `.github/workflows/freeze-report-slot-evidence.yml`, `tests/test_report_slot_evidence.py`、およびrequirements/specification/operationsとproject-control決定・証拠台帳。
- テスト: 隔離テスト追加済み。実行結果はPR headのGitHub Actions確認後に追記する。実GCS権限・create-only write・generation readbackはNOT_RUN。
- 未解決: Actions scheduleは期限内実行を保証しない。今回の修正は窓外runを閉じるが、独立schedulerは設計/費用/管理者承認が未了。2026-11-05 08:00 Evidenceは事後生成しない。Drive固定ID文書への同期はNOT_RUN。

## MR-EVIDENCE-GCS-WINDOW-20261105-01｜CI検証追記
- Code/test head 4c533ff4ab50e9673d1dddf7b5ee9c8f63f6aa9a: [08:00 issuance contract run 41939360238](https://github.com/matrixdiamond512-cell/Chat-GPT-Market-Report/actions/runs/41939360238) PASS。Python 3.12 compileとCLI smoke、契約unittest 136件（18+40+16+18+9+17+18）を確認。Evidence時刻境界とGCS fake tests 18件を含む。
- [frozen-cutoff regression run 41939360170](https://github.com/matrixdiamond512-cell/Chat-GPT-Market-Report/actions/runs/41939360170) PASS、31 tests。[delivery health run 41939360118](https://github.com/matrixdiamond512-cell/Chat-GPT-Market-Report/actions/runs/41939360118) PASS。[UI/DOM run 41939360203](https://github.com/matrixdiamond512-cell/Chat-GPT-Market-Report/actions/runs/41939360203) PASS。同期復旧、Dashboard eligibility/health、Apps Script validation、Drive selection QA、historical recovery QAも同headでPASS。
- CI初回はテストファイルの改行混入を検出。その後、必須Evidence作成時刻をpipeline/importer/G2のfixtureへ追加し、GCS conflictテストを有効JSONへ修正して通過。公開ゲートの条件は緩和していない。
- 証拠水準はCI隔離契約E2まで。実GCS service account/bucket権限、実create-only object、production generation readback、11月6日発行前EvidenceはNOT_RUN。成功扱いにしない。


## Change record — MR-EVIDENCE-GCS-WIF-SLOT-ISOLATION-20261105-01

- 対象: 固定パスの要件定義書、仕様書、運用マニュアル、Evidence Ledger、DECISIONS。
- 理由: PR #188のEvidence生成にGCS要件と15分実行窓が全4枠へ適用され、既存12:00・16:00・21:00運用へ不要な依存を加える危険を除去するため。
- 文書上の変更: GCS create-only / pinned-generationは08:00限定。残る3枠は既存GitHubローカルEvidenceと締切前ガードを維持。GCSは専用SAを通じたOIDC/WIFを使用し、権限と実環境未確認を記録。
- 証拠水準: 対象コードhead bc9d7cd7fca9aa52c1e6ffe7269788204d2b49d1 の契約テスト141件と関連10 ActionsはSUCCESS（E2 hosted isolated/regression）。実サービスのIAM/WIF、GCS書込み、scheduled runはNOT_RUNであり、READYを意味しない。


### Verification update — code head bc9d7cd7fca9aa52c1e6ffe7269788204d2b49d1

- Python 3.12 hosted CI: issuance contract suites PASS (18+40+16+18+9+17+23 = 141 tests); the 23-test Evidence suite includes 08:00 missing-GCS BLOCKED, non-08:00 cutoff-only behavior, immutable same-report conflict, late-run/date mismatch, GCS create-only/idempotent retry/conflict, and local-mirror retry/recovery cases.
- The initial run on 4cfad54 failed 3 assertions in the new/affected Evidence suite. Logs showed a now=None keyword-shape expectation mismatch in the mocked 08:00 guard and a historical non-08:00 fixture whose post-write live-clock recheck correctly rejected it. The helper now preserves the no-argument live call shape; the historical-fixture test isolates the clock guard while asserting immutable conflict behavior. No gate was weakened.
- Exact code-head Actions: issuance [41946722018](https://github.com/matrixdiamond512-cell/Chat-GPT-Market-Report/actions/runs/41946722018), frozen cutoff [41946722116](https://github.com/matrixdiamond512-cell/Chat-GPT-Market-Report/actions/runs/41946722116), delivery health [41946721817](https://github.com/matrixdiamond512-cell/Chat-GPT-Market-Report/actions/runs/41946721817), UI/DOM [41946722003](https://github.com/matrixdiamond512-cell/Chat-GPT-Market-Report/actions/runs/41946722003), Apps Script validation [41946721888](https://github.com/matrixdiamond512-cell/Chat-GPT-Market-Report/actions/runs/41946721888), sync recovery [41946721981](https://github.com/matrixdiamond512-cell/Chat-GPT-Market-Report/actions/runs/41946721981), dashboard health [41946722110](https://github.com/matrixdiamond512-cell/Chat-GPT-Market-Report/actions/runs/41946722110), dashboard eligibility [41946722083](https://github.com/matrixdiamond512-cell/Chat-GPT-Market-Report/actions/runs/41946722083), historical recovery [41946721805](https://github.com/matrixdiamond512-cell/Chat-GPT-Market-Report/actions/runs/41946721805), saved-source QA [41946721978](https://github.com/matrixdiamond512-cell/Chat-GPT-Market-Report/actions/runs/41946721978): all SUCCESS.
- Evidence level: E2 hosted isolated tests and workflow regression. GCS used a fake adapter in tests; real OIDC/WIF trust, IAM, GCS object/generation, production schedule and 08:00 issuance are NOT_RUN. PR #188 remains Draft/open/unmerged; no main, Docs, receipt, Pages, Secrets or schedule writes occurred.

## 2026-11-05 固定文書変更記録（MR-PROTECTED-PREFLIGHT-WIF-20261105-01）
- 対象：固定IDの要件定義書、システム仕様書、運用マニュアル、本台帳。GitHub側の固定パスはdocs/system/requirements.md、specification.md、operations.md、DOCUMENT_CONTROL.md、project-control/EVIDENCE_LEDGER.md。別版文書は作成しない。
- Google Docs既存固定IDを更新し、更新後に本文markerを読戻し確認した。要件定義書、仕様書、運用マニュアル、台帳のDocs本番接続設定・権限は今回の変更対象外。
- PR #188のpreflightコード/CIはPASS。本番Environment承認、production WIF、実Docs/GCS権限、本番E2EはNOT_RUN。


## 2026-11-05 record correction — MR-PROTECTED-PREFLIGHT-WIF-20261105-01

The GitHub Environment `report-publication` was absent in the read-only Environment inventory (only `apps-script-production` and `github-pages` were listed). Previous entries describing it as existing are superseded by this correction. PR #188 now checks Environment existence and a required-reviewer rule through an unauthenticated read-only job; the authenticated WIF job is conditional on that check and cannot start when the Environment is absent, unprotected, or unreadable.

At head `e8e96bf1acce7bb101f0ff9a9c9ac0b057f3371a`, the issuance contract [42032888516](https://github.com/matrixdiamond512-cell/Chat-GPT-Market-Report/actions/runs/42032888516) and all nine other related Actions succeeded; the issuance run reports preflight 21/21. Evidence level: E2 hosted CI/static workflow assertions. Live protected Environment, production WIF preflight, and production issuance remain NOT_RUN / NOT_READY. Admin must create `report-publication`, configure required reviewers and scope policy, then request a separate approved preflight.



## 2026-11-06 変更記録 — MR-ENV-WIF-ISSUANCE-PREFLIGHT-20261106-01

- 変更理由: reviewer数だけで本番Environment保護を判断していたpreflightをfail-closedにし、08:00発行前認証の誤通過を防ぐ。Chromium依存インストールの既知の遅延も検証対象にする。
- 対象固定パス: `docs/system/requirements.md`、`docs/system/specification.md`、`docs/system/operations.md`、`docs/system/DOCUMENT_CONTROL.md`、`docs/project-control/EVIDENCE_LEDGER.md`、`.github/workflows/0800-issuance-production-preflight.yml`、`.github/workflows/report-21-ui-validation.yml`、`scripts/reporting/issuance_preflight.py`、`tests/test_issuance_preflight.py`。
- 変更内容: reviewer有効性、自己承認防止、main限定、管理者バイパス状態を認証前に検査。秘密値は取得せず、GitHub Variables一覧はAPIが値を含むため照会しない。GitHub書込み権限は自己申告を証拠にせずUNKNOWNのまま。UI strict timeout 25分を維持し、headless shell installで試験する。
- 検証: 記録時点では変更headのHosted CI待ち。最終Actions URLとSHAは作業報告で証拠範囲を分けて記載する。固定ID Google Docsは未更新・未読戻し。本番Environment/WIF/IAM/Docs/GCS/receipt/Pagesは未実施。


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


## MR-G2-TASK-HANDOFF-20261111-01 — hosted verification

Exact executable/test head `2df1e9b36cb72554fd5c40bb72bd0ecf4dc494c7`: all ten requested PR CI systems independently read as completed/success. UI jobs validate and strict-current-report both SUCCESS; validate includes the dynamically generated task/G2/canonical fixture and real Playwright public-mode body/identity check.

| System | Exact-head Actions run |
|---|---|
| 08:00 issuance contract | https://github.com/matrixdiamond512-cell/Chat-GPT-Market-Report/actions/runs/42871996353 |
| Frozen cutoff | https://github.com/matrixdiamond512-cell/Chat-GPT-Market-Report/actions/runs/42871996348 |
| Apps Script prepublish | https://github.com/matrixdiamond512-cell/Chat-GPT-Market-Report/actions/runs/42871996605 |
| Sync recovery | https://github.com/matrixdiamond512-cell/Chat-GPT-Market-Report/actions/runs/42871996379 |
| Delivery health | https://github.com/matrixdiamond512-cell/Chat-GPT-Market-Report/actions/runs/42871996376 |
| Dashboard health | https://github.com/matrixdiamond512-cell/Chat-GPT-Market-Report/actions/runs/42871996990 |
| Dashboard eligibility | https://github.com/matrixdiamond512-cell/Chat-GPT-Market-Report/actions/runs/42871996476 |
| Historical recovery | https://github.com/matrixdiamond512-cell/Chat-GPT-Market-Report/actions/runs/42871996492 |
| Saved-source QA | https://github.com/matrixdiamond512-cell/Chat-GPT-Market-Report/actions/runs/42871996405 |
| UI / DOM | https://github.com/matrixdiamond512-cell/Chat-GPT-Market-Report/actions/runs/42871996799 |

Local renderer regressions: 6/6 PASS. Local Python contracts: 168 tests (167 PASS, one Windows symlink privilege SKIP); updated isolated index/Pages test 7/7 PASS. Earlier UI failures 42870725218 and 42871382048 remain in history and are superseded only for this code head.

Acceptance: integration candidate PASS at captured main 24fef1aa5750e1e2d87e26f6139727a0bdd9aff9; isolated simulated chain plus hosted real browser PASS; actual task-to-host connection BLOCKED_G2_TASK_HANDOFF; production Environment BLOCKED (self-review prevention disabled), production WIF/IAM UNKNOWN; production issuance NOT_READY. All owners remain legacy. No production write, merge, Draft removal, schedule/trigger/permission change, notification or retroactive Evidence generation occurred. Fixed-ID Google Docs synchronization, live fault injection, and ten-business-day operation remain NOT_RUN. This verification addition changes documentation only; verify its final head separately.


## MR-G2-TASK-HANDOFF-20261111-02 — 2026-11-11 JST, local-only continuation

Source: PR #188 at ebec70b4ffc0b02a9c839c8ea4b6acf061bdb567 and user's explicit decision to defer further external access. Affected canonical paths: requirements.md, specification.md, operations.md, DOCUMENT_CONTROL.md and project-control/EVIDENCE_LEDGER.md. Existing histories and fixed Docs IDs remain unchanged.

Requirement: invalid report/slot/revision, unsupported input types, invalid or expired freeze time must stop before invoking the Evidence reader. Preserve the 08:00–08:40 contract, independent pinned Evidence validation, existing producer and owner gates. Uncertain reads and invalid storage receipts must never produce G2_FROZEN success.

Implementation: task_output_handoff validates nonblank string invocation identifiers, exact integer schema/generation/revision, string Evidence identifiers, explicit target identity and timezone-aware live execution/freeze bounds before Evidence I/O. The producer still rechecks time after readback. Malformed envelope/JSON/snapshot shapes become TASK_OUTPUT_EVIDENCE_INVALID; unclassified reader errors become retryable TASK_OUTPUT_EVIDENCE_READ_FAILED at TASK_EVIDENCE_READ. Invalid G2 receipt types are blocked. No network endpoint, task authentication implementation, scheduler, credential discovery or production write path is added.

Verification: local Python 3.13 ten-suite run, 172 tests: 171 PASS and one Windows directory-symlink privilege SKIP. Task handoff 11/11 PASS, including no reader invocation for expired/invalid input, malformed readback, timeout and invalid storage receipt. Renderer 6/6 PASS; git diff --check PASS. No external CI was run for this local change, and no previous-head CI success is attributed to it.

Access observations before the user's hold: ChatGPT task page redirected to auth/login, so installed task settings/history were not inspected. The Google Drive connector could search existing files, but get_document for fixed document-control ID 1F5vH9_O0LUC9Dki0CNm1JDNVfg7gMYMcUCIxgeanE5g returned HTTP 403 PERMISSION_DENIED; canonical-folder listing and Apps Script MIME search returned no accessible entries. Search results included archived versioned Markdown copies; they were not promoted to canonical or modified. This proves only this connection's access limit, not the absence of the files or project. gcloud/clasp were not available on PATH. No fixed-ID document revision was read or updated.

Operation: user deferred external access. Do not push, inspect additional external services, change permissions, task schedules/triggers, production owners or publish as part of this continuation. Preserve local changes for later review. Live task handoff remains BLOCKED_G2_TASK_HANDOFF, production E2E and live recovery NOT_RUN, fixed Docs sync NOT_RUN, production NOT_READY. Resumption requires the user's instruction to resume external access and authorized access to the actual task/runtime and canonical Docs; account login/access is separate from release approval.
