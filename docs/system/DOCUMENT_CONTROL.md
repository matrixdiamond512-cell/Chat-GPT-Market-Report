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

## 2026-11-04 改訂記録｜REPORT-ARCHIVE-CONTENT-AUDIT-20261104-01

- 対象固定Google Docs：要件定義書 ID `102PMtKQ4DaXqV1G2RhE8vFtQ8qes-tvIvy2jYQda_xA` revision `AHj4eMQ4aATq9nIBs5IK1h2cWbicH4qM-GESxHj18sKXWL4-c5GmT_q9X2r2vOVNcftJAB6xZ3vgBFtYzzDyKIzdm5xGSzKuZ_A4onsF8N4`; システム仕様書 ID `1qL7f3yKwghuDb5PiAI3RhwFJUVUfLwGakC8z8EOJ9oI` revision `AHj4eMQYKTJWnqv7gPwXTq7q8n1bivxpZXDDiFTAZde2kr7V2J0v-kAGpNt66qOmuLN5j-ZmhukWlmGnveT2PYbu7EmDnqiuxw6C9VCkJfE`; 運用マニュアル ID `1OUVDAMjv009VWlI48Jb8TVuzszy4TIkjgBrHlzbNxYg` revision `AHj4eMQMINuad4YxThu6BGcWJWXF6c_lQWpcuWTU4mRmgqOM7Hwewj-QKQOdzOXfhD8xJuV_1p3JiwusxeRNelGjwJYhaM_gNPkdeooWkoc`; 文書管理台帳 ID `1F5vH9_O0LUC9Dki0CNm1JDNVfg7gMYMcUCIxgeanE5g` revision `AHj4eMRRPYfcfxG-ZAFWkNnuS1mROzpCaF3OJEWII0UMfs15zQbeK7AIS_H8l_BfLbHuJMBymrcxHPo0TVIGT4G_iQMnckxp08d7S5xiRPw`. 各文書は同じIDから読み戻し、変更見出しと対象本文を確認した。
- GitHub固定パス：`docs/system/requirements.md`、`docs/system/specification.md`、`docs/system/operations.md`。PR #197で更新し、PR #193～#196の表示修正・QA表示要件を同一変更IDで反映する。
- 受入根拠：PR #193～#196 main統合、UI/アーカイブCI成功、Pages deploy run 41836815631成功、公開画面の68slot/18日分読み戻し。
- 未解決原本：2026-10-22 12:00本文欠落、2026-11-02 12:00 source status矛盾。状態値を書き換えない。市場価格を全件外部照合した結果とは主張しない。

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

## MR-ZEROCOST-20261113-01 — ローカル実装候補と影響マトリクス（2026-11-13 JST）

出典：ユーザー03:16改訂指示書、後続の追加課金ゼロ/品質維持/現タスク保全指示、提示画像。調査base/main取得SHA `f94229ba1c135215623881faf4f5417509c252ab`、branch `codex/zero-cost-delivery`。関連PR #188（Draft、head `860ec370af7633a8ccadf393a474ee2614ce5430`）と重複を照合し、`build_market_json.py` の既存修正blobを再利用。今回のPR/hosted CI/main merge/本番切替はNOT_RUN。前回からの未コミット文書7件を保全し、同じ固定パスへ追記した。

| 対象正本 | 今回の対象節/差分 | 現行revision・同期/読戻し |
|---|---|---|
| 要件 `102PMtKQ4DaXqV1G2RhE8vFtQ8qes-tvIvy2jYQda_xA` / requirements.md | 追加0円、全4枠の品質/図解、単一責任・受入範囲 | GitHub候補追記、Google Docs取得403/fetch404、revision UNKNOWN、同期BLOCKED_EXTERNAL_ACCESS |
| 仕様 `1qL7f3yKwghuDb5PiAI3RhwFJUVUfLwGakC8z8EOJ9oI` / specification.md | 無課金gate、固定原本bundle、隔離journal、live市場writer分離 | 同上 |
| 本文作成 `1M9LzxKgg8Y50uHSzE1OhML-lU-ufPhvh79xj_m1jWYQ` | 詳細分析は維持。毎枠の独立図解と原本引渡し/未達表示の運用整合が必要 | 403/fetch404。内容変更/同期せず、既存品質を縮小しない。必要追補はoperationsの提案差分を参照 |
| 図解 `1XKWLVmxuINqq4Zq_zVsfzJqpI-kzKUCpw9q-i1OqpFU` | 08時16項目/9月基準図を維持、本文同一性/実画像QA | 403/fetch404。基準図未取得、BLOCKED_REFERENCE_IMAGE。想像による再設計なし |
| 運用 `1OUVDAMjv009VWlI48Jb8TVuzszy4TIkjgBrHlzbNxYg` / operations.md | 受領/保留/同一原本再開、条件付き新旧切替/戻し、費用根拠 | GitHub候補追記、Google同期BLOCKED_EXTERNAL_ACCESS |
| 台帳 `1F5vH9_O0LUC9Dki0CNm1JDNVfg7gMYMcUCIxgeanE5g` / DOCUMENT_CONTROL.md | 本マトリクス、変更ID/証拠/未解決 | GitHub候補追記、Google同期BLOCKED_EXTERNAL_ACCESS |

実測・検証：同IDのEVIDENCE_LEDGERと固定DELIVERY_PATH_INVENTORY.json、追跡外logs/zero-cost-deliveryを参照。ローカル試験32件PASS、実本文4枠shadowはすべてWAITING_FOR_SOURCE_ARTIFACT、公開4枠DOMは対象データなし。全工程VERIFIED/完成/切替済みとは報告しない。

未解決：Google正本6文書の実revision/本文/基準図、Drive本文の親とrevision、PNG実体、独立タスクrunログ/指定会話、GAS導入版/トリガー、Actions認証主体、公式自動受渡し、外部非本番保存/公開経路、課金/再配布条件、全4枠実地受入、単一writer切替、20枠連続運用。ログ/原本/履歴を削除して未解決を隠さない。


### MR-ZEROCOST-20261113-01｜レビュー公開状態の追補（2026-11-13 JST）

関連PRを [Draft #200](https://github.com/matrixdiamond512-cell/Chat-GPT-Market-Report/pull/200) に固定。review branchはcodex/zero-cost-delivery、初回共有commit62485d557491d821f82ebff86f96ef7f7ebc0d29。GitHubで差分・台帳・32件の証拠ファイルをreadbackし、同head CI successを確認。main統合/Google固定ID同期/本番運用受入とは別ステータス。本文/図解/保存/公開の既存未達とBLOCKEDは解消したと扱わない。詳細はEVIDENCE_LEDGER同ID。
