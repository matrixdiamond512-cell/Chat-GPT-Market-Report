# 配信システム文書管理規程

現行版: 2.3
改訂日: 2026-11-17 JST
変更ID: REPORT-SLOT-WINDOW-20261117-01
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

## 2026-11-04 改訂記録｜REPORT-ARCHIVE-CONTENT-AUDIT-20261104-01

- 対象固定Google Docs：要件定義書 ID `102PMtKQ4DaXqV1G2RhE8vFtQ8qes-tvIvy2jYQda_xA` revision `AHj4eMQ4aATq9nIBs5IK1h2cWbicH4qM-GESxHj18sKXWL4-c5GmT_q9X2r2vOVNcftJAB6xZ3vgBFtYzzDyKIzdm5xGSzKuZ_A4onsF8N4`; システム仕様書 ID `1qL7f3yKwghuDb5PiAI3RhwFJUVUfLwGakC8z8EOJ9oI` revision `AHj4eMQYKTJWnqv7gPwXTq7q8n1bivxpZXDDiFTAZde2kr7V2J0v-kAGpNt66qOmuLN5j-ZmhukWlmGnveT2PYbu7EmDnqiuxw6C9VCkJfE`; 運用マニュアル ID `1OUVDAMjv009VWlI48Jb8TVuzszy4TIkjgBrHlzbNxYg` revision `AHj4eMQMINuad4YxThu6BGcWJWXF6c_lQWpcuWTU4mRmgqOM7Hwewj-QKQOdzOXfhD8xJuV_1p3JiwusxeRNelGjwJYhaM_gNPkdeooWkoc`; 文書管理台帳 ID `1F5vH9_O0LUC9Dki0CNm1JDNVfg7gMYMcUCIxgeanE5g` revision `AHj4eMRRPYfcfxG-ZAFWkNnuS1mROzpCaF3OJEWII0UMfs15zQbeK7AIS_H8l_BfLbHuJMBymrcxHPo0TVIGT4G_iQMnckxp08d7S5xiRPw`. 各文書は同じIDから読み戻し、変更見出しと対象本文を確認した。
- GitHub固定パス：`docs/system/requirements.md`、`docs/system/specification.md`、`docs/system/operations.md`。PR #197で更新し、PR #193～#196の表示修正・QA表示要件を同一変更IDで反映する。
- 受入根拠：PR #193～#196 main統合、UI/アーカイブCI成功、Pages deploy run 41836815631成功、公開画面の68slot/18日分読み戻し。
- 未解決原本：2026-10-22 12:00本文欠落、2026-11-02 12:00 source status矛盾。状態値を書き換えない。市場価格を全件外部照合した結果とは主張しない。


## PORTAL-CONTENT-COMPLETENESS-20261116-01（2026-11-16 JST）

両画面は `data/report-archive-manifest.json` の同じ保存本文一覧と `assets/js/report-archive-source.js` の表示専用アダプターを使用する。Doc ID/URL、revision、本文長、日時、出典フォルダーを確認し、形式差（fileId/revision/URL形式/BOM）で有効な本文を落とさない。元本文と正式公開状態を変更しない。後日再構成版は定時原本に昇格せず、参考価格と実測資金フローを混同しない。

Driveから10枠を追加回復し、保存本文91枠を検証。見出し別の主導市場・シナリオ・結論・時系列表示を修正。未取得値を推測せず、残る原本欠落5枠は `data/report-content-gaps.json` に記録する（10/20 08、10/22 12、11/04 08、11/06 08・12）。10/20 08と10/22 12は復旧メモ、11/06 12は空Doc。

検証：Nodeの対象20テストPASS（E2、実保存本文を使ったアダプター/選択/表示回帰）。公開ブラウザは変更前を観測。変更後の公開DOM・Pages反映はNOT_RUN。Google Docs固定ID文書への同期は未実施。定時配信・正式原本・receipt・スケジュールは本変更の対象外。


## REPORT-SLOT-WINDOW-20261117-01｜対象時刻保全・時刻外取得防止（2026-11-17 JST）
- 調査根拠：GitHub Actions run `43958040721` では実行開始06:14 JSTに21:00として市場データ取得が走り、発行前証拠の15分鮮度条件不一致で失敗。将来枠の市場データを書き換え得る経路を特定。
- 変更範囲：`.github/workflows/freeze-report-slot-evidence.yml`、`scripts/persist_report_slot_evidence.py`、`scripts/run_market_data_window.py`、2本の回帰テスト、固定パス要件・仕様・運用・文書管理台帳。本文作成マニュアルの形式要件には変更なし。
- 実装方法：誤った実行窓を取り込み前に遮断する。T-15/Tの前後条件以外、発行枠、過去evidence、正式receipt、Drive本文、PNG、canonical、ポータル表示を改変しない。
- 検証状態：PRブランチの静的実装。ユニットCI・main反映・次回定時E2E・公開DOM・通知は別途検証するまで未確認。関連PRおよび結果はGit履歴で追跡する。
- 未解決：GitHub Actionsスケジューラー自体の長時間遅延・スキップはコードだけで保証できない。枠前の正当な実行が一度もなければ正式証拠は欠落し、後から補作しない。

## REPORT-SLOT-QUEUE-20261117-02｜定時処理待ち行列分離（2026-11-17 JST）

- 変更理由：GitHub Actionsのcron大幅遅延・跨枠の全体concurrencyと、Google Drive11月フォルダーの配信用サービスアカウント参照不能を11月17日ログで確認。
- GitHub対象：`.github/workflows/freeze-report-slot-evidence.yml`、`.github/workflows/market-data-intraday-{anchor,fallback,health}.yml`、`tests/test_report_slot_evidence.py`、要件/仕様/運用/本台帳の固定パス。Docs原本と価格、receipt、既存GitHub Pages本文は変更対象外。
- 変更内容：同一枠の直列化は維持し、異なる予定枠どうしの待ち行列だけを分離。証拠作成許可時間・正式公開条件は不変。
- 未解決：本番サービスアカウントの正確なIDはGitHub secretに保管されており本変更では参照しない。Driveフォルダー共有の実施・確認、GitHubの定時起動保証、次回4枠E2E、Google Docs固定ID正本への同期は別作業であり現時点で未検証。

## MR-STABILITY-REPAIR-20261117-03（2026-11-17 JST / 修正候補）
影響: 要件・仕様・運用・本台帳の固定パス/固定Docs。本文作成マニュアルの形式要件は不変（参照済）。原因資料: run43958040721/44019617757/44019745595/44021644786/44044688511、最新main b2d5973。PR #213を保持。変更はfolder fail-closed/parent readback/CI回帰のみ。権限付与・保存原本・PNG・canonical・receipt・本番スケジュールは変更しない。固定Docs同期・PR CI/main反映・実4枠/10営業日受入は各別に記録する。
検証: 新規7件を含む65回帰テストPASS（E1/E2）。本番SAのfolder読戻し・初期4枠・10営業日40枠は未実施。コード/CI成功を全面復旧としない。

## MR-DELIVERY-STABILITY-20261118-01｜変更台帳・実装検証（2026-11-18 11:58 JST）
- 変更対象：固定Google Docs 要件定義書/システム仕様書/運用マニュアル/文書管理台帳 と、GitHub mainの固定パス `docs/system/requirements.md`、`specification.md`、`operations.md`、本規程。本文作成マニュアルの形式要件は変更していない。新しい別冊正本は作らない。
- コード反映：PR #215 https://github.com/matrixdiamond512-cell/Chat-GPT-Market-Report/pull/215 （receipt/図解付き定時health、main dbc95b8cf613ecf6ef990149e58d66bb6f7bac78）、PR #216 https://github.com/matrixdiamond512-cell/Chat-GPT-Market-Report/pull/216 （データ取得完了起点で枠前証拠固定、main da71661a25a8dce65b0a75e8e27c6e9d10342504）。関連CI成功とmainファイル読み戻しを確認。
- 本番証跡：2026-11-18 12:00証拠READY_FOR_DRAFT、run44226581259でorigin/main readback PASS（NO_OP）。11/18 08:00のPNGがDriveに存在しても視覚QA/公式manifestは未受入。Google Drive読取権限問題は本番SAの読取診断成功済みで、新規権限要求はしていない。
- 状態：コード反映=IMPLEMENTED、CI=PASS、12時枠事前証拠=LIVE_READBACK_PASS、全4枠E2E=NOT_ACCEPTED、10営業日40枠=NOT_STARTED、画像正式品質検証=NOT_ACCEPTED。未検証の工程を完了と呼ばない。

## MR-DELIVERY-STABILITY-20261118-02｜追加変更記録（2026-11-18 12:11 JST）
- 固定Google Docs要件定義書/システム仕様書/運用マニュアル/文書管理台帳に同じ変更IDを追記・読戻し成功。GitHub固定文書にも同じ追補。
- PR #218 https://github.com/matrixdiamond512-cell/Chat-GPT-Market-Report/pull/218 はmain 5420fed6600bda41aa8be45eae7eee8768242bdd。参考閲覧版の正式receipt昇格禁止、独立dashboard市場データの限定的整合判定、publication-evidence CIを実装。CI run44228487454 / 44228487434 PASS。
- 11/18 12:00主タスクは11:56:57〜11:57:38 JSTに早期終了、本文表示のみ。PNG/Docs/正式公開未達。プラットフォームの時刻保証・継続40枠の本番受入は未完了。過去の原本や証拠を捏造・上書きしない。

## REPORT-PIPELINE-REDESIGN-20261118-01｜再設計の変更管理（2026-11-18 JST）
- 区分：提案・設計文書のみ。Cloud Run/Scheduler/Workflows/外部テキストAPI/Drive writerは未実装、未デプロイ、未承認。既存タスク、GitHub main配信プログラム、正式発行ゲートは変更しない。
- 正本は固定Docs IDs：要件定義書 102PMtKQ4DaXqV1G2RhE8vFtQ8qes-tvIvy2jYQda_xA、仕様書 1qL7f3yKwghuDb5PiAI3RhwFJUVUfLwGakC8z8EOJ9oI、本文作成マニュアル 1M9LzxKgg8Y50uHSzE1OhML-lU-ufPhvh79xj_m1jWYQ、運用マニュアル 1OUVDAMjv009VWlI48Jb8TVuzszy4TIkjgBrHlzbNxYg、台帳 1F5vH9_O0LUC9Dki0CNm1JDNVfg7gMYMcUCIxgeanE5g。同一変更IDで追記・読み戻し済み。
- GitHub固定文書は docs/system/requirements.md、specification.md、operations.md、DOCUMENT_CONTROL.md のみ追記対象。本PRのマージは「設計案の記録」であって「実装済み」ではない。
- 受入条件：書込権限/費用/チャット配信経路の実証→コーディネーター/PNG renderer/Drive uploader実装→1枠E2E→4枠E2E→10営業日40枠→承認に基づく切替。過去のsource/evidence/receiptは一切補造・変更しない。


## MR-INFOGRAPHIC-DRIVE-20261121-01｜図解PNG保存経路障害・再発防止（2026-11-21 JST）
- 根拠: 11/20 21:00主タスクのGoogle Docs/PNG未実行、21:10独立PNG保存BLOCKED_FILE_REFERENCE、21:15復旧でGoogle Docsのみ保存。11/21 00:53に対象PNGのDrive実体（2,413,109 bytes）を確認。定刻のPNG保存失敗を後追い保存の成功で帳消しにしない。
- 対象変更: ChatGPTの稼働中3タスクのPNG受渡し/復旧条件、GitHub PR #226（`sync-latest-report-watchdog.yml`、`check-scheduled-report-delivery.yml`、`verify_drive_infographic_upload.py`、該当テスト）、固定GitHub文書 `requirements.md`・`specification.md`・`operations.md`・本書。Google Docs固定IDの該当3文書/台帳も同期対象。本文作成マニュアルの分析項目・図解レイアウト変更なし。
- 検証: テストPNG 2,140 bytesのFiles Library経由Drive保存、Google Drive metadata読戻しPASS（片付け済み）。3タスクの設定更新SUCCESS。GitHubコードはPR #226ブランチ反映のみで、CI/main/毎枠実E2E/正式PNG品質・manifest/Pages DOM/通知の受入はUNKNOWN。サービスアカウント秘密情報や原本は変更しない。
- 未解決: 別のChatGPT実行環境からのsource_file_ref利用が毎回成功するか、GitHub Actionsの実行遅延/通知、正式出版ゲートの通過、10営業日40枠の連続成功。コードの改善だけを正式発行完了とは表現しない。

## MR-DRIVE-SCHEDULE-DATE-20261121-02｜監視対象日誤判定の修復記録
- 発見: 2026-11-21、GitHub run 44772805142（cron `45 7 * * 1-5`）がJST日付跨ぎで起動し、実行日を誤用してDrive PNGを0件と誤判定。
- 更新: scheduled_dateから対象JST日付を決定し、Drive実体/正式canonicalの双方を同じ日付で検査する改修、遅延回帰テスト、45分後の自動復旧タスク指示（原本・競合確認、読戻し必須）。
- 事実確認: PR #226 main反映 `749eba4e233ae87852abd3021fa48276f4cac71c`、本修正は別PR・CI・main/定時実E2Eを別々に判定する。過去の正式receiptや画像品質は補造しない。

## MR-WATCHDOG-MIDNIGHT-20261121-03｜公開watchdogの跨日検査漏れ修復
- GitHub Actionsの21時枠が翌日へ遅延した場合の無検証終了分岐を撤去。共有cron対象日判定、Python/JS回帰、requirements/specification/operations/台帳を同一変更要求IDで反映。正式publication receiptを捏造しない。


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
