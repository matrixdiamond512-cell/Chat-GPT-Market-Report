# A → B → D → C 実装報告

最終報告再確認（2026-10-06）: 以前の93件結果の後、G4 PNG命名と正式v1.8の不一致を発見し修正した。現在の最終コード候補は0e14412、Python78＋script16＝94テストPASS。PNG名は `マーケットレポート_<report_id>.png`。別枠名/未定義revision suffixは拒否する。以下のaf61a0a/93件の記述は前回受入時点の履歴であり、この追記と最新acceptance.jsonを現行結果とする。最終Git SHA・diff/stat/statusは外部evidence/final-report-verification.jsonを参照。

2026-10-06 JST。対象依頼はSOURCE_SPEC.md。今回の基盤実装・回帰確認を終了し、E〜Hへは進んでいない。

作業ブランチ: `codex/report-foundation-a-b-d-c`。開始時点: `600a533`。最終コード候補: `af61a0a`。push・deploy・PR作成は行っていない。

## 1. 変更ファイル一覧

末尾の自動生成一覧を参照。変更は正式仕様、基盤モジュール、限定的な既存入口/不具合修正、fixture、検証、作業記録に限定した。トップレベルの別EAリポジトリには変更していない。

## 2. commit一覧

末尾の一覧を参照。仕様、A、B、D、C、限定修正、検証修正を分割した。最終報告commitを含む完全な履歴は外部証拠フォルダの `commits.txt` に保存する。

## 3. ReportContext schema

`report_date`, `report_time`, `report_id`, `data_cutoff`, `previous_report_id`, `previous_business_day`, `revision`, `mode`。

frozen dataclass。対象日は明示入力。新規枠は平日08/12/16/21、土日newは拒否。historical/recoveryは明示mode。retryは保存済みContextを復元し、実行時計から再計算しない。data_cutoffはtimezone必須で対象時刻を超えられない。previous_report_idは対象より前、previous_business_dayは対象より前の平日を検証する。未指定の前営業日は平日カレンダーによる計算であり、日本/海外の祝日カレンダー確定を証明しない。祝日等の訂正は呼出元が明示する。

resolverは宣言cronを使い、unknown cron・push推測・manual autoを拒否する。独立市場取得の月〜土スケジュールは維持。取得windowはReportContext任意入力を追加し、過去Contextでライブ取得して履歴を付け替える要求を拒否する。GASにはfrozen入力検証と既存ファイル名parserへの任意Context照合を追加した。GASの旧Publisher全体への強制接続は今回の範囲外。

## 4. ExecutionContext schema

`attempt_id`, `execution_started_at`, `saved_at`, `published_at`, `verified_at`。後三者はnullable。timezoneと時刻順を検証する。対象日時とは別オブジェクトで保持し、CLI入力も分離した。10/2対象を10/4以降に処理してもReportContextの対象日は変わらない。

## 5. MarketDataSnapshot schema

`snapshot_id`, `report_id`, `revision`, `schema_version=1`, `captured_at`, `data_cutoff`, `markets`。

snapshot_idは固定内容全体のSHA-256から生成する。市場配列・source等のネストもdeep freeze。restore時にcontent identityを照合。既存取得payloadのgeneratedAt JST日付・reportSlot・reportDateを確認し、別日/別枠を拒否する。本文生成後の最新取得を行うAPIはない。新価格は新revision。retryは同じserialized snapshotを使用する。

独立dashboardのtop-level marketData更新機能は維持し、latestReport/reports本文オブジェクトへのライブ値の自動付加だけを除去した。ChatGPT入力の同時刻別日データ混入にも日付ガードを追加した。既存history/last-verified/morning-reference/readiness/source registry/validationを保持した。

## 6. ReportObject / Market schema

ReportObject: `report_id`, `report_date`, `report_time`, `revision`, `snapshot_id`, `title`, `full_text`, `sections`, `market_data_table`, `markets`, `previous_report_id`, `status`。

Market: `instrument`, `marketType`, `venue`, `contractMonth`, `priceValue`, `priceUnit`, `changeValue`, `changePct`, `direction`, `comparisonBasis`, `asOf`, `source`, `status`, `unavailableReason`, `displayText`, `outlook`。

数値はfinite number/null。0とnull、VALID/UNAVAILABLE/STALE/N/Aを区別。UNAVAILABLEはnull価格＋理由。観測directionは数値の符号から検証し、outlookと分離。source/asOf/unitを伝播し、G1で既存source registryの市場系列・単位・marketType・source id・範囲・鮮度を照合する。VALIDのdisplayTextにも対応する価格数値が必要。

full_textは原文そのまま保持する。sections/tableが原文と矛盾すればG2停止。今回の新契約はmarket sectionに `table_line()` の固定行を含む本文を受け入れる。旧自由文をこの形式へ自動変換しない。legacy adapterは元JSONを別途保持し、原文不足を要約で復元せず、LEGACY_UNVERIFIEDとして読み込む。新規公開合格には使えない。

## 7. Validation Gate一覧と接続

| Gate | 検証/停止条件 |
|---|---|
| G0 | Contextの明示日時、ID、mode、曜日、revision、前回、cutoff |
| G1 | snapshot/context一致、content identity、系列・数値・単位・鮮度・source・status・direction |
| G2 | 原文/sections/見出し/市場表/市場数値/タイトル日時/ID/revision/snapshot一致、保全枠のUNRESOLVED拒否 |
| G3 | 保存先と読戻しの同一Drive fileId・URL・実全文文字列。Chat原文保持。読取失敗/空/全文不一致を拒否 |
| G4 | 同じreportId/revision/body/snapshot、Drive実在と同一読取ID、filename、PNG signature/chunks/CRC/pixels |
| G5 | G0〜G4後だけManifest。PNGなしでGit/Pages許可を出さない |
| G6 | canonical/index/latest/dashboardの同一ReportObject、revision後退拒否、同revisionは完全同一既存objectがあるretryだけ、commit SHA |
| Actions境界 | 同一Git SHA・run ID・success証拠がないとPages許可を出さない |
| G7 | 同一SHAのPages deployment、対象ID/title/full body/市場価格/change/changePct/direction/reason/PNG、各操作・console・timeout・mobile |
| G8 | G0〜G7後だけReceipt。Manifest/hash・Git・Pages・DOM・時刻を保持してVERIFIED |

`Transaction.begin(context,snapshot)` とCLI `--prepare` は本文生成前のG0/G1。`generate_report(title, body_factory)` は合格済みのimmutable入力をproducerへ渡す。G1不合格ではproducerを呼ばない。既存本文の検証ではattach_reportへ進む。CLIは証拠を受け取って全ゲートへ接続する読取専用入口であり、ネットワーク書込・Git操作・deployを実装していない。

Gateが検証するDrive実文字列、PNG bytes、DOM値は外部consumerが観測して渡す契約。fixtureのPASSは実Driveレポート/実Pages公開の証明ではない。G3不一致でもnormalize前後と比較diffをエラー証拠へ残す。許容はCRLF/LFと末尾単一改行だけ。句点・文章・数値変更や空行collapseは吸収しない。

PNG初期検証は8-bit非interlaceのgrayscale/RGB/grayscale-alpha/RGBAを対象とし、未対応encodingはfail closed。異なる有効PNG encodingの拡張はPublisher統合時の確認事項。

## 8. SPEC_CONFLICT SC-01〜03

正式Driveの5つのtext/markdown文書を同じID/親フォルダのまま更新し、全文読戻しを保存した。10/6再確認でも更新日時・ID・フォルダは10/4の今回書込み結果と同じ。

現行順序: Drive全文検証 → PNG検証 → Publication Manifest → Git → Actions → Pages → 公開DOM検証 → Publication Receipt → VERIFIED。

Manifestは公開前の固定契約でREADY_FOR_PUBLICATION。report/date/time/revision/body hash/snapshot/Drive/PNG/created_at等を保持。Receiptは公開後の結果証拠でManifest/hash/Git SHA/Pages deployment/published_at/verified_at/URL/DOM status/final_statusを保持する。公開前bundleにReceiptを含めない。要件FR-07/08、共通順序、状態遷移、運用手順、統合付録を更新した。過去Receiptを変換・削除せず、旧v1.7の順序記述は履歴として現行契約に明確に従属させた。

## 9. 維持した既存挙動

市場取得・source registry・validation・history・last-verified・morning-reference・readiness・sheet exports、historical土曜08/07/09の読取、legacy本文読取、table.rows→markets→legacyのUI優先順位、structured 08表の追加行禁止、既存narrative parser、index/canonical parity、publication consistency。

変更した既存挙動は、誤った土曜新規08発行の許容、現在時計からのunknown cron/manual/push推測、本文へのmutable latest追加、全域regexの価格誤抽出、any(generator)処理漏れ、naive比較でのTypeError。これらは今回の明示要求による修正であり、古い誤挙動をテストに残していない。

## 10. 直接対応したP0

- P0-02: ローカルレンダラーと実08本文fixtureで金/BTCの「08」誤抽出を解消。market/outlook section内のラベル付き行のみを扱い、UNAVAILABLE理由を維持。実ローカルDOMでも確認。
- P0-03: 新基盤でPNG欠落→G4/G5 FAIL→Git/Pages許可なしを実装/CLI確認。既存PNG欠落履歴は未修復、ライブ公開経路への強制適用は未実施。
- P0-04: 日付事故の予防としてimmutable明示Context・cross-day snapshot拒否。過去復旧履歴は変更していない。
- P0-06: 新基盤はManifest/Git/同SHA Actions/DOM失敗を拒否する。既存deploy bypassそのものはE〜H未実施のため残る。

## 11. 未解消P0/P1・Known Limitations / Open Outcomes

- P0-01: `2026-10-02_21-00`はUNRESOLVED / UNVERIFIED / NEEDS_REVIEW。OLD/NEWを選択していない。G2はこの対象の公開を拒否する。原Chat本文未取得。
- P0-05: unsafe canonical writerは本番挙動を変更せず、TempDirectoryでrevision 3→1の危険な上書きを再現。修正済みとは扱わない。
- P0-03/06: 既存Publisher/Actions/Pagesはまだ新ゲートへ全面接続していない。ライブのPNGなし公開・Validation FAIL deployを止めたとは主張しない。
- P1-01〜04: 新入口では予防契約を実装。ただし旧GAS Publisher/後補修/旧projection経路すべての置換は未実施。既存21:00のWTI/BTC騰落率表示欠落も残る。
- P1-05/06: 限定修正と回帰PASS。全historicalの補完処理は実行していない。
- 旧08:00履歴は28-row契約を欠き、QA console FAIL。全履歴構造Validationも既知FAILのまま。新型fixtureのG7証拠を旧公開データのVERIFIEDへ転用しない。

今回の範囲内の必須実装/検証に未完了はない。上記は保全対象または次工程の未完了成果として継続記録する。

## 12. 実行したテスト / Regression Checks

固定候補af61a0aで再実行。再現入口: `scripts/run_foundation_regression.py --node <bundled node.exe> --evidence-dir <workspace review evidence>`。

全tests discovery、resolver/window/reconcile/fetch-market/sheet-exportの既存16テスト、GAS narrative、共通見出し/実08 fixture/優先順位/timeoutのNode vm、4 JS＋3 GAS syntax、Python AST syntax、本文生成前prepare CLI、G0〜G8 CLI、PNGなしCLI拒否、index142件、publication consistency、date-only/aware receipt境界、5文書全文照合、本番ハッシュ比較。

ローカル実browserで08:00/21:00表示、picker/time tabs/prev/next/reload、390px幅、5列/6市場行、横スクロール動作（scrollLeft 0→375、wrap 315px/scrollWidth1079px、body375pxでviewport390px内）を確認。browser viewportを復元し、作成tabとローカルテストserverを終了した。

## 13. PASS

Python unittest 77＋既存script 16 = 93件。GAS narrativeとUI fixture、syntax、prepare/全ゲートCLI、PNG欠落時の拒否、index、publication consistency、CLI timezone境界、正式5文書読戻し、本番未変更証拠がPASS。

PNGなしCLIは終了1が期待結果であり、拒否確認テストがPASS。実公開成功の意味ではない。

## 14. FAIL

既存production `validate_market_reports.py`: FAIL（既知の本文/構造不足）。旧08:00のMorningReportQA DOM/console: FAIL（28行欠落）。修復禁止の本番履歴に手を入れず、未解消として保持した。今回追加/維持したunit・fixture regressionの予期しないFAILは0。

## 15. NOT_RUN / Evidence Level Reached

本番Chat原文取得、本番report Docs書込/PNG生成、実Git登録/push、Actions実行/Pages deploy、実公開Receipt生成、ライブ全工程G0〜G8、unsafe writer本番修正はNOT_RUN（今回範囲外/禁止）。E〜H再編もNOT_RUN。

E0: syntax/schema。E1/E2: component/fixture integration。E3: executable CLIの合格・拒否。E4: ローカル実browserの表示/操作/スクロール。E5: 正式仕様Drive更新・読戻し。E5は仕様文書に限り、本番レポート公開の外部結果は未証明。

## 16. production data未変更の証拠

作業開始時918ファイルのSHA-256がすべて一致。最終回帰前後はpublication-receiptsを含む964ファイルで完全一致。`git diff 600a533 -- reports reports.json data images/reports publication-receipts` は空。unsafe writerの本体コードにも変更なし。レポートDrive Docs/PNG/過去Receipt更新・Pages変更のツール/コマンドを実行していない。外部書込は明示された正式5仕様文書のみ。

初期baselineに含まれなかったReceipt類は最終run前後のbyte hashとGit base差分でも確認した。原子レベルのlive remote全成果物再取得を行ったという証拠ではない。

## 17. 次にPhase Eへ進める条件 / Next Necessary Action

ユーザーが次工程を指示した時点で、ここに保全した仕様・固定契約・受入証拠を基準にEのPublisher integrationを開始する。開始前に別commit/別承認が必要なunsafe canonical writer修正を混ぜない。Manifest入力のみから同一Doc読戻し/PNG実取得・検証・Git/Actions/Pages/DOM証拠収集へ接続し、全既存publish/deploy入口のbypassを閉じる。UNKNOWN外部効果を再試行前に照合し、重複/rollback/recoveryを確認する。

`2026-10-02_21-00`は原Chat本文とDrive OLD/NEWの実全文・ID証拠による正本決定が別途完了するまで公開対象に含めない。まず非本番fixtureまたは明示した別対象で、実保存先と同じID、同じPNG、同じSHA、公開DOMからのReceiptまでをE5で確認する。今回の93テストPASSをその代替にしない。

ここで停止し、E〜Hへ自動移行しない。

## 変更ファイル（Git base差分）

- [.github/workflows/update-market-data.yml](C:/Users/atsuk/OneDrive/デスクトップ/ドキュメント/WEBマーケットレポート/work/market-report-foundation-20261004/.github/workflows/update-market-data.yml)
- [apps-script/MarketReportContext.gs](C:/Users/atsuk/OneDrive/デスクトップ/ドキュメント/WEBマーケットレポート/work/market-report-foundation-20261004/apps-script/MarketReportContext.gs)
- [apps-script/MarketReportStructuredImport.gs](C:/Users/atsuk/OneDrive/デスクトップ/ドキュメント/WEBマーケットレポート/work/market-report-foundation-20261004/apps-script/MarketReportStructuredImport.gs)
- [apps-script/MarketReportWebSync.gs](C:/Users/atsuk/OneDrive/デスクトップ/ドキュメント/WEBマーケットレポート/work/market-report-foundation-20261004/apps-script/MarketReportWebSync.gs)
- [assets/js/report-core-v3.js](C:/Users/atsuk/OneDrive/デスクトップ/ドキュメント/WEBマーケットレポート/work/market-report-foundation-20261004/assets/js/report-core-v3.js)
- [config/report_heading_registry.json](C:/Users/atsuk/OneDrive/デスクトップ/ドキュメント/WEBマーケットレポート/work/market-report-foundation-20261004/config/report_heading_registry.json)
- [config/report_schedule.json](C:/Users/atsuk/OneDrive/デスクトップ/ドキュメント/WEBマーケットレポート/work/market-report-foundation-20261004/config/report_schedule.json)
- [docs/project-control/DECISIONS.md](C:/Users/atsuk/OneDrive/デスクトップ/ドキュメント/WEBマーケットレポート/work/market-report-foundation-20261004/docs/project-control/DECISIONS.md)
- [docs/project-control/EVIDENCE_LEDGER.md](C:/Users/atsuk/OneDrive/デスクトップ/ドキュメント/WEBマーケットレポート/work/market-report-foundation-20261004/docs/project-control/EVIDENCE_LEDGER.md)
- [docs/project-control/IMPLEMENTATION_REPORT.md](C:/Users/atsuk/OneDrive/デスクトップ/ドキュメント/WEBマーケットレポート/work/market-report-foundation-20261004/docs/project-control/IMPLEMENTATION_REPORT.md)
- [docs/project-control/LESSONS.md](C:/Users/atsuk/OneDrive/デスクトップ/ドキュメント/WEBマーケットレポート/work/market-report-foundation-20261004/docs/project-control/LESSONS.md)
- [docs/project-control/OBJECTIVE_CARD.md](C:/Users/atsuk/OneDrive/デスクトップ/ドキュメント/WEBマーケットレポート/work/market-report-foundation-20261004/docs/project-control/OBJECTIVE_CARD.md)
- [docs/project-control/README.md](C:/Users/atsuk/OneDrive/デスクトップ/ドキュメント/WEBマーケットレポート/work/market-report-foundation-20261004/docs/project-control/README.md)
- [docs/project-control/SOURCE_SPEC.md](C:/Users/atsuk/OneDrive/デスクトップ/ドキュメント/WEBマーケットレポート/work/market-report-foundation-20261004/docs/project-control/SOURCE_SPEC.md)
- [docs/project-control/formal-drive-verification.json](C:/Users/atsuk/OneDrive/デスクトップ/ドキュメント/WEBマーケットレポート/work/market-report-foundation-20261004/docs/project-control/formal-drive-verification.json)
- [docs/project-control/spec-backups/マーケットレポート本文作成マニュアル_v1.8.md](C:/Users/atsuk/OneDrive/デスクトップ/ドキュメント/WEBマーケットレポート/work/market-report-foundation-20261004/docs/project-control/spec-backups/マーケットレポート本文作成マニュアル_v1.8.md)
- [docs/project-control/spec-backups/マーケットレポート配信システム_仕様書_v1.8.md](C:/Users/atsuk/OneDrive/デスクトップ/ドキュメント/WEBマーケットレポート/work/market-report-foundation-20261004/docs/project-control/spec-backups/マーケットレポート配信システム_仕様書_v1.8.md)
- [docs/project-control/spec-backups/マーケットレポート配信システム_文書体系・索引_v1.8.md](C:/Users/atsuk/OneDrive/デスクトップ/ドキュメント/WEBマーケットレポート/work/market-report-foundation-20261004/docs/project-control/spec-backups/マーケットレポート配信システム_文書体系・索引_v1.8.md)
- [docs/project-control/spec-backups/マーケットレポート配信システム_要件定義書_v1.8.md](C:/Users/atsuk/OneDrive/デスクトップ/ドキュメント/WEBマーケットレポート/work/market-report-foundation-20261004/docs/project-control/spec-backups/マーケットレポート配信システム_要件定義書_v1.8.md)
- [docs/project-control/spec-backups/マーケットレポート配信システム_運用マニュアル_v1.8.md](C:/Users/atsuk/OneDrive/デスクトップ/ドキュメント/WEBマーケットレポート/work/market-report-foundation-20261004/docs/project-control/spec-backups/マーケットレポート配信システム_運用マニュアル_v1.8.md)
- [docs/project-control/spec-readbacks/マーケットレポート本文作成マニュアル_v1.8.md](C:/Users/atsuk/OneDrive/デスクトップ/ドキュメント/WEBマーケットレポート/work/market-report-foundation-20261004/docs/project-control/spec-readbacks/マーケットレポート本文作成マニュアル_v1.8.md)
- [docs/project-control/spec-readbacks/マーケットレポート配信システム_仕様書_v1.8.md](C:/Users/atsuk/OneDrive/デスクトップ/ドキュメント/WEBマーケットレポート/work/market-report-foundation-20261004/docs/project-control/spec-readbacks/マーケットレポート配信システム_仕様書_v1.8.md)
- [docs/project-control/spec-readbacks/マーケットレポート配信システム_文書体系・索引_v1.8.md](C:/Users/atsuk/OneDrive/デスクトップ/ドキュメント/WEBマーケットレポート/work/market-report-foundation-20261004/docs/project-control/spec-readbacks/マーケットレポート配信システム_文書体系・索引_v1.8.md)
- [docs/project-control/spec-readbacks/マーケットレポート配信システム_要件定義書_v1.8.md](C:/Users/atsuk/OneDrive/デスクトップ/ドキュメント/WEBマーケットレポート/work/market-report-foundation-20261004/docs/project-control/spec-readbacks/マーケットレポート配信システム_要件定義書_v1.8.md)
- [docs/project-control/spec-readbacks/マーケットレポート配信システム_運用マニュアル_v1.8.md](C:/Users/atsuk/OneDrive/デスクトップ/ドキュメント/WEBマーケットレポート/work/market-report-foundation-20261004/docs/project-control/spec-readbacks/マーケットレポート配信システム_運用マニュアル_v1.8.md)
- [docs/マーケットレポート本文作成マニュアル_v1.8.md](C:/Users/atsuk/OneDrive/デスクトップ/ドキュメント/WEBマーケットレポート/work/market-report-foundation-20261004/docs/マーケットレポート本文作成マニュアル_v1.8.md)
- [docs/マーケットレポート配信システム_仕様書_v1.8.md](C:/Users/atsuk/OneDrive/デスクトップ/ドキュメント/WEBマーケットレポート/work/market-report-foundation-20261004/docs/マーケットレポート配信システム_仕様書_v1.8.md)
- [docs/マーケットレポート配信システム_文書体系・索引_v1.8.md](C:/Users/atsuk/OneDrive/デスクトップ/ドキュメント/WEBマーケットレポート/work/market-report-foundation-20261004/docs/マーケットレポート配信システム_文書体系・索引_v1.8.md)
- [docs/マーケットレポート配信システム_要件定義書_v1.8.md](C:/Users/atsuk/OneDrive/デスクトップ/ドキュメント/WEBマーケットレポート/work/market-report-foundation-20261004/docs/マーケットレポート配信システム_要件定義書_v1.8.md)
- [docs/マーケットレポート配信システム_運用マニュアル_v1.8.md](C:/Users/atsuk/OneDrive/デスクトップ/ドキュメント/WEBマーケットレポート/work/market-report-foundation-20261004/docs/マーケットレポート配信システム_運用マニュアル_v1.8.md)
- [scripts/build_chatgpt_report_input.py](C:/Users/atsuk/OneDrive/デスクトップ/ドキュメント/WEBマーケットレポート/work/market-report-foundation-20261004/scripts/build_chatgpt_report_input.py)
- [scripts/build_market_json.py](C:/Users/atsuk/OneDrive/デスクトップ/ドキュメント/WEBマーケットレポート/work/market-report-foundation-20261004/scripts/build_market_json.py)
- [scripts/build_reports.py](C:/Users/atsuk/OneDrive/デスクトップ/ドキュメント/WEBマーケットレポート/work/market-report-foundation-20261004/scripts/build_reports.py)
- [scripts/complete_report_schema.py](C:/Users/atsuk/OneDrive/デスクトップ/ドキュメント/WEBマーケットレポート/work/market-report-foundation-20261004/scripts/complete_report_schema.py)
- [scripts/reconcile_report_history.py](C:/Users/atsuk/OneDrive/デスクトップ/ドキュメント/WEBマーケットレポート/work/market-report-foundation-20261004/scripts/reconcile_report_history.py)
- [scripts/reporting/__init__.py](C:/Users/atsuk/OneDrive/デスクトップ/ドキュメント/WEBマーケットレポート/work/market-report-foundation-20261004/scripts/reporting/__init__.py)
- [scripts/reporting/context.py](C:/Users/atsuk/OneDrive/デスクトップ/ドキュメント/WEBマーケットレポート/work/market-report-foundation-20261004/scripts/reporting/context.py)
- [scripts/reporting/gates.py](C:/Users/atsuk/OneDrive/デスクトップ/ドキュメント/WEBマーケットレポート/work/market-report-foundation-20261004/scripts/reporting/gates.py)
- [scripts/reporting/report.py](C:/Users/atsuk/OneDrive/デスクトップ/ドキュメント/WEBマーケットレポート/work/market-report-foundation-20261004/scripts/reporting/report.py)
- [scripts/reporting/snapshot.py](C:/Users/atsuk/OneDrive/デスクトップ/ドキュメント/WEBマーケットレポート/work/market-report-foundation-20261004/scripts/reporting/snapshot.py)
- [scripts/resolve_market_report_slot.py](C:/Users/atsuk/OneDrive/デスクトップ/ドキュメント/WEBマーケットレポート/work/market-report-foundation-20261004/scripts/resolve_market_report_slot.py)
- [scripts/run_foundation_regression.py](C:/Users/atsuk/OneDrive/デスクトップ/ドキュメント/WEBマーケットレポート/work/market-report-foundation-20261004/scripts/run_foundation_regression.py)
- [scripts/run_market_data_window.py](C:/Users/atsuk/OneDrive/デスクトップ/ドキュメント/WEBマーケットレポート/work/market-report-foundation-20261004/scripts/run_market_data_window.py)
- [scripts/test_report_foundation_ui.js](C:/Users/atsuk/OneDrive/デスクトップ/ドキュメント/WEBマーケットレポート/work/market-report-foundation-20261004/scripts/test_report_foundation_ui.js)
- [scripts/test_resolve_market_report_slot.py](C:/Users/atsuk/OneDrive/デスクトップ/ドキュメント/WEBマーケットレポート/work/market-report-foundation-20261004/scripts/test_resolve_market_report_slot.py)
- [scripts/validate_drive_publication_receipt.py](C:/Users/atsuk/OneDrive/デスクトップ/ドキュメント/WEBマーケットレポート/work/market-report-foundation-20261004/scripts/validate_drive_publication_receipt.py)
- [scripts/validate_report_transaction.py](C:/Users/atsuk/OneDrive/デスクトップ/ドキュメント/WEBマーケットレポート/work/market-report-foundation-20261004/scripts/validate_report_transaction.py)
- [tests/fixtures/2026-10-02_08-00.json](C:/Users/atsuk/OneDrive/デスクトップ/ドキュメント/WEBマーケットレポート/work/market-report-foundation-20261004/tests/fixtures/2026-10-02_08-00.json)
- [tests/fixtures/2026-10-02_21-00.json](C:/Users/atsuk/OneDrive/デスクトップ/ドキュメント/WEBマーケットレポート/work/market-report-foundation-20261004/tests/fixtures/2026-10-02_21-00.json)
- [tests/test_market_snapshot.py](C:/Users/atsuk/OneDrive/デスクトップ/ドキュメント/WEBマーケットレポート/work/market-report-foundation-20261004/tests/test_market_snapshot.py)
- [tests/test_p0_foundation.py](C:/Users/atsuk/OneDrive/デスクトップ/ドキュメント/WEBマーケットレポート/work/market-report-foundation-20261004/tests/test_p0_foundation.py)
- [tests/test_report_context.py](C:/Users/atsuk/OneDrive/デスクトップ/ドキュメント/WEBマーケットレポート/work/market-report-foundation-20261004/tests/test_report_context.py)
- [tests/test_report_contract.py](C:/Users/atsuk/OneDrive/デスクトップ/ドキュメント/WEBマーケットレポート/work/market-report-foundation-20261004/tests/test_report_contract.py)
- [tests/test_report_object.py](C:/Users/atsuk/OneDrive/デスクトップ/ドキュメント/WEBマーケットレポート/work/market-report-foundation-20261004/tests/test_report_object.py)
- [tests/test_validation_gates.py](C:/Users/atsuk/OneDrive/デスクトップ/ドキュメント/WEBマーケットレポート/work/market-report-foundation-20261004/tests/test_validation_gates.py)
- [tests/transaction_fixture.py](C:/Users/atsuk/OneDrive/デスクトップ/ドキュメント/WEBマーケットレポート/work/market-report-foundation-20261004/tests/transaction_fixture.py)

## 実装・検証commit

```text
62617f3 docs: resolve publication manifest and receipt contract
8023dec refactor: add immutable explicit report context
988fd8d refactor: bind immutable report market snapshots
c849fe4 refactor: introduce immutable report object and numeric market contract
68a4a05 refactor: connect G0 through G8 publication validation gates
9508c21 fix: process every schema input and reject naive timestamps safely
94ebd04 fix: prevent clock prices and add contextual legacy entry boundaries
94730ef fix: close validation gaps found in foundation acceptance sweep
4f82530 test: preserve specification readbacks and reproducible acceptance evidence
af61a0a fix: validate snapshot before invoking report body generation
```

## 受入証拠

- [acceptance.json](C:/Users/atsuk/OneDrive/デスクトップ/ドキュメント/WEBマーケットレポート/review/market-report-foundation-20261004/evidence/acceptance.json)
- [production-proof.json](C:/Users/atsuk/OneDrive/デスクトップ/ドキュメント/WEBマーケットレポート/review/market-report-foundation-20261004/evidence/production-proof.json)
- [local-ui-evidence.json](C:/Users/atsuk/OneDrive/デスクトップ/ドキュメント/WEBマーケットレポート/review/market-report-foundation-20261004/evidence/local-ui-evidence.json)
- [mobile-390.png](C:/Users/atsuk/OneDrive/デスクトップ/ドキュメント/WEBマーケットレポート/review/market-report-foundation-20261004/evidence/mobile-390.png)
- [mobile-390-scrolled.png](C:/Users/atsuk/OneDrive/デスクトップ/ドキュメント/WEBマーケットレポート/review/market-report-foundation-20261004/evidence/mobile-390-scrolled.png)
