# マーケットレポート配信システム 仕様書
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

## 2026-10-14 継続追補（3文書共通版 v1.10）
- `config/report_heading_registry.json` の厳密な同義語一覧を `reporting.report.py` のセクション分類、`report_source_contract.py`、同期SOP、21:00形式検査、Apps Script見出し検証で共有・整合する。08:00「金利・為替・クロスアセットの因果関係」をクロスアセット章、12:00「主要6市場の短期見通し（条件付き）」を6市場見通しとして扱う。
- 見出し一致は独立行でのみ成立する。セクション終了は次の明示的見出しで判定し、クロスアセット本文は最小長と文終端、6市場見通しは6市場行と各市場の本文量を要求する。本文中の単語だけ、空見出し、見出し語だけの短文は不合格。
- Google Docs native source経路でも保存本文の基本検査後にslot SOP全体を適用する。構造化snapshotの必須条件は別契約として維持し、同一report_id/revision/context/body hashでsnapshotを結べないレポートを公開しない。
- `report_status` と `infographic_status` は独立。図解QA保留は本文品質の代替判定に使わない。本文はsnapshot・原本・公開ゲートに従い、receipt/Pages readbackの完了は個別証拠で判定する。
- PR #128（head `2c1e9b2`）は未マージ。ローカルの関連57テストはPASS、164件の履歴検証PASS。GitHub Actions最終結果と本番Pages反映は未確定であり、ライブ受入はPENDING。

## 2026-10-14 14:36 JST 継続追補 v1.10
- PR #128のheadは`4cb2dce385300c51447d7c4a8ed316bc4637ab8a`。最終headの関連Actions 8件（sync recovery、morning source check、market validation、dashboard health、21h source validation、heading compatibility、Apps Script pre-publish、report structure）はSUCCESS。Apps Script回帰テストの合成fixtureが市場行の本文量不足で一度失敗したため、ゲートを緩めず6市場の説明をfixtureへ追加して再実行した。CIはPASS、PRは未マージ。
- 08:00/12:00の実Docs本文は修正後Python native-Docs経路でPASS。原文は編集していない。08:00 snapshotは10:24:21 JST生成でレポート識別情報と結合されず、12:00 snapshotも未確認。どちらも過去データ再構成をせず公開保留。
- 3つのGoogle Drive正式文書に同一v1.10追補を追記し、revision guarded write後の読み戻しで全件確認した。次の16:00 runおよび08/12/16/21の本番E2Eは未検証。復旧完了は未達。
