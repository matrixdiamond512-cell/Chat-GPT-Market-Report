> **文書差分反映 v2.1（2026-10-19、DOCCTRL-20261019-HISTORY）**  
> 旧2.x〜3.40、配信v1.6〜1.9、2026-10-13〜19の文書・コード差異を固定文書へ整理。旧GitHub版付き文書は履歴専用の案内へ更新。正式Google Docsは同じ固定IDで追記済み。月別Drive保存先、08時28×5、12/16/21時実出来事、重要イベント時刻、欠損監査、非正式補充表示の区別を同期。最新の正式管理規程は [DOCUMENT_CONTROL.md](./DOCUMENT_CONTROL.md)。これは4枠の実稼働E2E達成を示すものではない。
>
> **正式文書管理（2026-10-19、DOCCTRL-20261019-01）**
> Google Driveの固定名・固定IDの4文書と文書管理台帳へ統一した。正本ID・改訂手順は [DOCUMENT_CONTROL.md](./DOCUMENT_CONTROL.md) を参照。旧記録中の「統合ドラフトで正式正本ではない」は当時の状態であり、現行の文書指定に優先しない。GitHub mainのコード適用と定時実行の成功は別途検証する。
>
# 配信システムの正本識別と更新先
2026-10-13 / PRレビュー用。3文書は独立。GitHub mainの静的確認・本番稼働・未マージPRは区別する。
要件定義書: docs/system/requirements.md / Google Docs 102PMtKQ4DaXqV1G2RhE8vFtQ8qes-tvIvy2jYQda_xA
仕様書: docs/system/specification.md / Google Docs 1qL7f3yKwghuDb5PiAI3RhwFJUVUfLwGakC8z8EOJ9oI
運用マニュアル: docs/system/operations.md / Google Docs 1OUVDAMjv009VWlI48Jb8TVuzszy4TIkjgBrHlzbNxYg
関連Web資料だけを更新して本件が完了したと報告しない。編集前に対象の文書名・Google Drive fileId・GitHubパス・revision・変更要求IDを確認する。旧正本や他文書への自動変更は禁止。上記Google Docsは統合ドラフトであり現時点では正式正本と認定しない。

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
- この追補はマーケットレポート配信システムの要件・仕様・運用に関するもので、WEBポータルだけの文書修正では完了としない。関連するGitHub版（docs/マーケットレポート配信システム_要件定義書_v1.9.md、同仕様書・運用マニュアル）、本文作成マニュアル・索引、Google Driveに既存の統合正式改訂3文書を同じDOCSYNC IDで追補する。
- 対象実装：PR #152（10/16 08:00後追いDocs本文の非正式アーカイブ）、#153（主要6市場カードの価格・条件の誤表示修正）、#154（08/12/16/21時のT-13/T-7/T-3分証拠凍結再試行）。既存の本文生成、定時通知、全工程E2E成功は検証未了。
- 各記録は「GitHubに存在する設定」「CIテスト合格」「実定期枠の稼働」「Docs原本の読戻し」「canonical/receipt」「公開Pagesの閲覧」を分ける。旧ページにある過去のPRステータスは当時の履歴として保持する。


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
