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


## MRF-0800-BRIDGE-20261030-01 continuation
Added a composed offline test in `tests/test_importer_handoff.py`: pinned TEST_ONLY generation → isolated file readback → actual importer `publication_evidence` strict-binding path → Docs revision/body/evidence/snapshot match; a wrong body hash returns HOLD. Local handoff and issuance suites pass 12/12 each. Current task branch is based on PR #188 head `0a37e8c35d8669110aa95560054e2ab275a56569`; latest main `ec3e38b56397686c781e61de7efe97baeec48544` is 152 commits ahead, with no changed-file path overlap observed. Keep PR #188 Draft and unmerged; resync/review main drift before readiness. After pushing, wait for exact-head issuance/frozen-cutoff/delivery-health CI. External GCS/Docs/Portal production transaction remains NOT_RUN.


## MRF-0800-BRIDGE-20261030-01 — current continuation state (2026-10-30 10:23 JST)

Branch: `codex/0800-main-issuance-e2e-20261029`; source PR #188; code head before this documentation update `7a1b751923dc40c1cfae26e980f49bc10f7b82c9); base/current main `ec3e38b56397686c781e61de7efe97baeec48544`. Exact-head issuance contract run 40981647510, frozen-cutoff run 40981647421, and delivery-health run 40981647442 were SUCCESS. PR #189 remains a separate OPEN/Draft branch and both PRs touch `scripts/sync_reports_from_drive.py`; their combined behavior has not been merged/tested.

Staging gate recheck: current checkout has no staging marker, `data/report-evidence/` has 0 files, and the checked sibling staging path is absent. `gcloud` is unavailable, `GOOGLE_APPLICATION_CREDENTIALS` is unset, and the standard Windows gcloud ADC file is absent. These observations mean no usable GCS authentication was available in this environment; they do not prove credentials are absent elsewhere.

Read-only Google Drive recheck of Doc `1laY8WojdqX5kUNJj35PIXlNnikXqH_F7NntuNPuhOYA` returned revision `AHj4eMRVs5vDnuQa4YLl1GD72hFIH1tg8Vqsc4PUep97iqrGsHghlhh5TBDzEPgkgYyJ54wLhmnxFBfMgqydAJiYY1zXUmC12ne2kgChMAc`; body says `閲覧用分析版` and pre-issuance evidence is absent. No matching frozen G2 body/hash or same-run Docs save receipt was available. Connector did not expose `appProperties`; strict binding is UNKNOWN.

Status: isolated real importer execution and `--apply` BLOCKED / NOT_RUN. Do not use this Doc or fabricate a historic source. No external write or production operation was performed. Resume only after an authorized TEST_ONLY identity/object, exact-generation/hash details, matching Docs issuance properties, and a separate marked `LOCAL_STAGING_ONLY` checkout are available. Stage exact bytes, inspect strict-binding dry-run, and apply only on a full binding PASS.


## Handoff addendum — MRF-INGESTION-20261030-01 (2026-10-30 JST)
- Base: GitHub main 52e99701f3bc71a77bdde31729e0f887f44a9135; branch codex/report-ingestion-stage-truth-20261030.
- Scope: correct importer stage labels; add four focused offline contract tests and run them through the existing sync recovery CI.
- No main merge, production Pages deployment, Google Drive write, receipt/report/PNG mutation, schedule or Cloud setting change.
- Local Python 3.13.14: 38 workflow-scope tests PASS across the six runnable modules; 24 additional evidence regression tests PASS; `py_compile` PASS. `test_report_contract.py` and `test_publication_evidence.py` are BLOCKED at import because this Windows runtime has no IANA `tzdata` (`ZoneInfoNotFoundError: Asia/Tokyo`). Exact-head hosted CI and PR readback remain open.
- Full live 08:00/12:00/16:00/21:00 acceptance, external task state, Drive fixed-ID formal-document synchronization, Pages public DOM readback, and notification acceptance remain NOT_RUN.
- Draft PR #189 is OPEN / Draft / unmerged. On code head `71fce84ddfa814a3b0c66bbc0545d36e78bfec1a`, hosted runs 40968791396 (sync recovery), 40968791427 (frozen cutoff), and 40968791433 (delivery health) all PASS. A documentation-only update is now being added, so final PR-head CI must be rechecked. Then hand off the remaining externally gated stages.


## MRF-INGESTION-20261030-01 acceptance matrix — 2026-10-30 JST

**Production acceptance is NOT_RUN / incomplete.** The rows below record the last read-only snapshot inspected during this task for 2026-10-29; they are not evidence of a new live run. A report JSON existing in `reports/` proves only an archive record.

| Report slot | Data + pre-issue evidence | Body QA + Docs full readback | GitHub canonical + valid receipt | Pages deploy + public body readback | PNG + exact body provenance | Overall |
|---|---|---|---|---|---|---|
| 2026-10-29 08:00 | NOT_VERIFIED | Report archived; body QA / Docs full-text readback NOT_VERIFIED | `SOURCE_ARCHIVED`; receipt missing in inspected snapshot | NOT_VERIFIED; shared Pages workflow later timed out | PNG exists; content/body match NOT_VERIFIED | BLOCKED / NOT_ACCEPTED |
| 2026-10-29 12:00 | NOT_VERIFIED | Report archived; body QA / Docs full-text readback NOT_VERIFIED | `SOURCE_ARCHIVED`; receipt missing in inspected snapshot | NOT_VERIFIED; shared Pages workflow later timed out | PNG exists; content/body match NOT_VERIFIED | BLOCKED / NOT_ACCEPTED |
| 2026-10-29 16:00 | NOT_VERIFIED | Report archived; body QA / Docs full-text readback NOT_VERIFIED | `SOURCE_ARCHIVED`; receipt missing in inspected snapshot | NOT_VERIFIED; shared Pages workflow later timed out | PNG exists; content/body match NOT_VERIFIED | BLOCKED / NOT_ACCEPTED |
| 2026-10-29 21:00 | NOT_VERIFIED | Report archived; body QA / Docs full-text readback NOT_VERIFIED | `SOURCE_ARCHIVED`; receipt missing in inspected snapshot | NOT_VERIFIED; shared Pages workflow later timed out | PNG exists; content/body match NOT_VERIFIED | BLOCKED / NOT_ACCEPTED |

Evidence links (latest main read-only recheck at ec3e38b56397686c781e61de7efe97baeec48544): [08:00 JSON](https://github.com/matrixdiamond512-cell/Chat-GPT-Market-Report/blob/ec3e38b56397686c781e61de7efe97baeec48544/reports/2026-10-29_08-00.json), [12:00 JSON](https://github.com/matrixdiamond512-cell/Chat-GPT-Market-Report/blob/ec3e38b56397686c781e61de7efe97baeec48544/reports/2026-10-29_12-00.json), [16:00 JSON](https://github.com/matrixdiamond512-cell/Chat-GPT-Market-Report/blob/ec3e38b56397686c781e61de7efe97baeec48544/reports/2026-10-29_16-00.json), [21:00 JSON](https://github.com/matrixdiamond512-cell/Chat-GPT-Market-Report/blob/ec3e38b56397686c781e61de7efe97baeec48544/reports/2026-10-29_21-00.json); [PR #189](https://github.com/matrixdiamond512-cell/Chat-GPT-Market-Report/pull/189); [Pages timeout run 40966149397](https://github.com/matrixdiamond512-cell/Chat-GPT-Market-Report/actions/runs/40966149397). PR #189 checks (40968927389 / 40968927469 / 40968927385) establish hosted code regression only, not production acceptance.

**Acceptance still required per slot:** immutable pre-slot snapshot/context/evidence and source readback; complete body QA; Docs file identity and full-text/hash readback; matching canonical reportId/revision/hash and valid receipt; successful Pages deploy and public URL body readback; PNG file readback with matching body revision/hash plus visual/content review; idempotent rerun and failure-path proof. Run separate approved production validation for each slot; do not backfill missing historical evidence.
