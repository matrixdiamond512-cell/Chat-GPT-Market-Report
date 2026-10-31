# 配信システム文書管理規程

現行版: 2.1
改訂日: 2026-10-19 JST
変更ID: DOCCTRL-20261019-HISTORY
本規程は新しい要件定義書や仕様書の別冊ではなく、既存の文書を固定IDで管理する手順を定める。v2.0の旧未解決一覧は当時の履歴であり、末尾のv2.1照合結果と文書管理台帳の123件索引が現在の正本。

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


## 変更記録 MRF-INGESTION-20261030-01（2026-10-30 JST）
対象: GitHub固定パス docs/system/requirements.md、specification.md、operations.md、本規程、scripts/sync_reports_from_drive.py、scripts/reporting/ingestion_outcome.py、tests/test_ingestion_outcome.py、.github/workflows/market-report-sync-recovery-ci.yml、project-control記録、HANDOFF.md。
理由: Importerがarchive-onlyのsourceについても VERIFIED_REPORT_INGESTION_AND_PUBLICATION と出力し、取込と正式公開の状態を誤って一つに見せていたため。
変更: stageごとの明示ログへ置換し、archive-only・Docs読戻しreceipt・未認識statusを独立表示。該当する回帰テストをCI対象に追加。
制約: main merge、Google Drive正式文書更新、本番Docs/PNG/receipt/report変更、Pages deploy、schedule/Cloud設定変更なし。
検証: Python 3.13.14でworkflow対象の6モジュール38 tests PASS、追加証拠回帰3モジュール24 tests PASS、py_compile PASS。test_report_contract.py / test_publication_evidence.pyはWindows環境にIANA tzdataがなくZoneInfoNotFoundErrorでBLOCKED。Hosted CIはPR作成後。E3–E5本番E2EはNOT_RUN。
未解決: CI最終head確認、PR review/merge、Google Drive固定ID文書への同期判定、将来slotでのlive Docs/canonical/Pages acceptance。


## MRF-INGESTION-20261030-01 evidence-link correction (CORRECT, 2026-10-30 JST)
The four-slot HANDOFF matrix originally linked 2026-10-29 report JSON paths at main `52e99701f3bc71a77bdde31729e0f887f44a9135`, where those paths were absent. Repointed its read-only evidence links to current main `ec3e38b56397686c781e61de7efe97baeec48544`, where the four JSON files are present and each has `SOURCE_ARCHIVED` / `infographic_status=NOT_VERIFIED`; the four receipt paths are absent. No requirements, pipeline behavior, reports, receipts, Docs, PNGs, Pages, or external services were changed.
