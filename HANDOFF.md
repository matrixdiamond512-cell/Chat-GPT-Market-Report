# マーケットレポート作成・配信システム — Codex開発引き継ぎ書

作成日: 2026-10-20 JST  
変更要求ID: `HANDOFF-20261020-01`  
リポジトリ: `matrixdiamond512-cell/Chat-GPT-Market-Report`  
文書の役割: 別PC・別担当者の正規Codexアカウントから開発作業を安全に再開するための案内。**要件定義書・仕様書・運用マニュアルの代替ではない。**

> この文書は2026-10-20時点の照会結果のスナップショットです。既存PR・Actions・Docs・公開Pagesの状態は変わります。作業のたびにmain実装・証拠・実際の配信を再確認してください。過去のCodex会話やPC内の未コミット変更は自動移行されません。各担当者は自分自身のGitHubとCodex/OpenAIアカウントを利用してください。

## 1. 作業開始前に読む順番

1. [`AGENTS.md`](AGENTS.md): Codexの必須規則。**最初に `docs/system/DOCUMENT_CONTROL.md` を読むこと。**
2. [`docs/system/DOCUMENT_CONTROL.md`](docs/system/DOCUMENT_CONTROL.md): 固定パス、固定Google Docs ID、変更ID、記録、照合と公開資格の区別。
3. [`docs/system/README.md`](docs/system/README.md) と次の現行固定文書:
   - [`docs/system/requirements.md`](docs/system/requirements.md) — 配信要件
   - [`docs/system/specification.md`](docs/system/specification.md) — システム仕様
   - [`docs/system/operations.md`](docs/system/operations.md) — 運用マニュアル
4. [`docs/project-control/OBJECTIVE_CARD.md`](docs/project-control/OBJECTIVE_CARD.md)、[`DECISIONS.md`](docs/project-control/DECISIONS.md)、[`LESSONS.md`](docs/project-control/LESSONS.md)、[`EVIDENCE_LEDGER.md`](docs/project-control/EVIDENCE_LEDGER.md): 目的、採否、既知の失敗、根拠と未実施。
5. [オープンIssues](https://github.com/matrixdiamond512-cell/Chat-GPT-Market-Report/issues)・[PR](https://github.com/matrixdiamond512-cell/Chat-GPT-Market-Report/pulls)・[Actions](https://github.com/matrixdiamond512-cell/Chat-GPT-Market-Report/actions): **最新**の実装・作業中・障害・検証状態。

旧版 `docs/マーケットレポート配信システム_*_v*.md` は履歴です。新しい版付き要件・仕様・運用文書は増やさず、固定ID/パスの正式文書を所定の変更管理で更新してください。Google Docs正本を更新するときは、指定ID・親フォルダー・revisionと関連文書の整合を読み戻す必要があります。

## 2. 実装の構成（読んでから変更）

| 領域 | 主要箇所 | 注意 |
|---|---|---|
| 発行枠 | `config/report_schedule.json` | 現在は平日 **08:00 / 12:00 / 16:00 / 21:00 JST**、土日発行なし。設定だけで実際の定時動作は証明できない |
| 市場取得・検証 | `scripts/fetch_market_data.py`, `scripts/run_market_data_window.py`, `scripts/verify_morning_report_qa.py` | 実測の基準日、方向、出典、欠損理由と08時28項目×5列の照合 |
| 事前evidence | `.github/workflows/freeze-report-slot-evidence.yml`, `scripts/persist_report_slot_evidence.py`, `data/report-evidence/` | 枠の前に固定する証拠。枠を過ぎてから遡及作成しない |
| 本文・図解 | `docs/system/requirements.md`, `docs/system/specification.md`, `docs/INFOGRAPHIC_VALIDATOR.md` | ChatGPT側の生成とリポジトリ内の取り込みは別工程。コードだけで配信を実証しない |
| Google Docs取込 | `.github/workflows/publish-saved-google-docs-reports.yml`, `scripts/sync_reports_from_drive.py` | 保存済みDocsの取得・検証であり、元のGoogle Docs/図解の新規生成を保証しない |
| 発行正本 | `reports/`, `reports.json`, `data/latest-report.json`, `publication-receipts/` | reportId/revision/snapshot/body hash/receiptの同一性を守る |
| Portal | `index.html`, `report.html`, `dashboard-*.js`, `.github/workflows/deploy-pages.yml` | Pagesのデプロイ成功と公開URLのDOM/本文/画像一致は別 |
| 定期監視 | `.github/workflows/check-scheduled-report-delivery.yml`, `sync-latest-report-watchdog.yml` | 通知・公開成功を推測で代用しない |
| テスト | `tests/`, `scripts/test_*.py`, `scripts/test_*.js`, `.github/workflows/*-ci.yml` | 対象機能に合うコマンド、実行環境、結果をPRに記録 |

特に08時28行/5列のデータ仕様、先物限月、JSTイベント時刻/DST、価格の上昇下降、取得不能と0の区別、米欧市場と東証の休場を無断で緩めない。

## 3. 発行・保存・検証の状態を分離する

定時実行について、次の全工程を**別々の状態**として確認します。

```text
市場データ取得/時点照合
  → 枠前のsnapshot/context/evidence凍結
  → ChatGPT本文・図解の生成とチャット内表示
  → Docs本文・PNGの月別Google Drive保存
  → 保存後のfileId/親フォルダー/全文・byte/hash読戻し
  → GitHub正本・receipt・インデックス整合
  → Pages deploy
  → ライブPortal本文/図解の再取得・一致確認
  → 通知・ユーザー到達（検証できる場合）
```

`SOURCE_ARCHIVED`、`HISTORICAL_ARCHIVE`、`RECONSTRUCTED_UNVERIFIED`、`BLOCKED` 等を後から `PUBLISHED` に変更しない。**本文PUBLISHEDと図解NOT_READYは別状態**。全工程合格と表現できるのは各段階の実証がある場合だけ。CI/fixture合格もライブE2E成功を意味しない。

過去の欠落した発行前証拠、未保存のPNG、本文を推測で復元しない。正規receiptと参考表示、Driveの最新保存版と正式公開原本の違いを維持する。

## 4. 2026-10-20時点の確認済み状況・継続先

- `main`照会時点HEAD: `79bda6f164893da638b70f3412f0112949782ee9`（Drive保存版参照をポータルに追加したコミット）。**本作業はこのSHAに対する開発用文書のみの追加を意図**。
- 既存本番配信監査: [Issue #103](https://github.com/matrixdiamond512-cell/Chat-GPT-Market-Report/issues/103)。2026-10-13時点の監査記録。現在の問題かどうかは再照合。
- [PR #172](https://github.com/matrixdiamond512-cell/Chat-GPT-Market-Report/pull/172): 2026-10-20時点OPENのPages復旧候補。未マージを本番適用と見なさない。
- [PR #170](https://github.com/matrixdiamond512-cell/Chat-GPT-Market-Report/pull/170): レポート再設計の仕様ドラフト。新しい自動生成機能・API課金・本番トリガーが承認/実装されたと見なさない。
- [Issue #173](https://github.com/matrixdiamond512-cell/Chat-GPT-Market-Report/issues/173): **別PCでの実機引き継ぎ・権限・差分管理の受入確認**（この文書の直接フォローアップ）。
- 2026-10-20のGitHub Actions確認時、[Publish saved Google Docs market reports](https://github.com/matrixdiamond512-cell/Chat-GPT-Market-Report/actions/runs/39394319272) が失敗、[Deploy WEB Market Report to GitHub Pages](https://github.com/matrixdiamond512-cell/Chat-GPT-Market-Report/actions/runs/39394141146) が失敗。**原因は本書では未確定**。結果を調査せず再発防止済みと主張しない。新たなrun/修正PRを確認。
- 定時4枠の元本文→Docs→GitHub→Pages→通知の総合ライブE2Eは、2026-10-20時点の本書の調査では未確認。

## 5. 別PCの導入（Windows）

1. 各担当者が自分のCodex/OpenAIアカウントでCodexへログインする。既存のChatGPT会話やアカウントの利用枠は他人へ移せない。
2. GitHubアカウントを用意する。Publicリポジトリの閲覧/cloneは通常可能だが、**push/PR運用とActions操作には適切な権限が必要**。書込み用の共同開発権限は所有者から個別付与する。
3. リポジトリをcloneしてブランチと最新HEADを確認する。

```powershell
git clone https://github.com/matrixdiamond512-cell/Chat-GPT-Market-Report.git
cd Chat-GPT-Market-Report
git status --short
git log -1 --oneline
git branch --show-current
```

4. Codexにまず `AGENTS.md` と `HANDOFF.md` を読ませる。既存の本番ワークフローやDocs/Sheets/Pagesを書き換える指示は出さず、IssueとPRを確認して作業計画を立てる。
5. `git switch -c docs/<topic>` のような専用ブランチで小さな変更を行い、検証結果付きPRを作る。他PCへ戻ったら `git status` で未コミット変更を保護した後、必要なブランチで `git pull --ff-only` など安全な方法で同期する。

**PCローカルでのみ存在する秘密情報、Apps Script設定、トリガー、認証、Drive権限、未コミット変更はGitHubのcloneでコピーされない。** トークン/秘密鍵をチャット・Issue・PR・ログに貼らない。必要なアクセスは権限管理者による別手続きを使う。

## 6. Codexに渡す初回指示の例

> AGENTS.md → docs/system/DOCUMENT_CONTROL.md → README.md → HANDOFF.md → docs/system/requirements.md、specification.md、operations.md → docs/project-control の4資料を読み、現行main、Open Issues/PR、直近Actionsを照合してください。特にIssue #103、#173、PR #172、#170を確認し、実装済みと未マージ、CI合格と本番到達を区別してください。最初は調査のみ。レポート生成、Google Drive書込み、既存reports/・data/・publication-receipts/、Actions schedule、Pages、本番Secretsを変更せず、変更要求IDと証拠範囲を付けて提案してください。発行前evidenceや未確認値を後付け生成しないでください。

## 7. 変更管理・PR運用

- タスクごとに変更要求ID、変更日(JST)、対象文書ID・GitHubパス、既存revision/commit、関連Issue/PRを記録。
- ユーザー向け配信要件/仕様/運用の変更は、`docs/system`固定パスとGoogle Drive固定ID文書・本文作成マニュアル・台帳の影響を先に評価し、必要箇所を同期する。この引き継ぎ書自体は**開発用案内のみ**であり、正式仕様の先行改訂ではない。
- 変更は原則PR経由。既存PRとの重複・競合を確認し、production JSON/PNG/receiptをドキュメントPRへ含めない。
- 各PRに**テストの実行コマンドと結果、未実行、外部依存、Apps Script/Docs/Pages実稼働の確認状況**を必ず分離して書く。
- 完了の主張には、該当工程の**実際の読み戻し**が必要。Google Docs保存・PNG・GitHub登録・receipt・Pages URLがそれぞれ別工程であることを維持。
- 他PCに引き継ぐ際、必ずbranch名/HEAD SHA/未push変更/PR/Issue/結果ログ/残課題を更新する。強制push・無断上書き・履歴改変を避ける。

---
この文書の最終更新: 2026-10-20 JST。文書管理の根拠は `docs/system/DOCUMENT_CONTROL.md`。配信システム本体の変更、Google Docsの正式正本の書換え、外部サービスの設定変更は、この引き継ぎ整備だけでは実施しない。


## MR-AUDIT-CAPA-20261124-01｜独立監査Phase 0（2026-11-24 JST）

出典: ユーザー添付の是正指示書第8節および独立監査報告。基準main `579fa000fc84f6875f220962c5f17ea01138c68e`、作業branch `codex/audit-capa-phase0`。監査原文・是正台帳・実装順序・影響文書・承認操作・費用/リスク/rollback・AT対応は [是正台帳](docs/project-control/AUDIT_CAPA.md) に集約。NC-01〜07/RC-1〜5/AT-01〜12の原定義は保全原本を維持。

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
