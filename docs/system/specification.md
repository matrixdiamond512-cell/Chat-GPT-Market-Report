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

## 2026-10-15 canonical JSON v2互換仕様追補（v1.12 / Draft）

- 新規producer証拠のみ対象：`canonicalization_version=report-canonical-json/v2`。ASCII identifier keyの再帰ソート、UTF-8、bool/null/safe integer、配列順保持、孤立サロゲート禁止。Python floatは`{"decimal_v2":"100.0"}`等のタグ付き文字列とする。GASは未タグの金融数値を拒否。
- 旧`snapshot_id`はPythonの既存`snapshot.digest`に基づくv1のまま保存。v2の`context_digest_v2`、`snapshot_digest_v2`を別名でSHA-256照合。v1のMarketReportProducerProof署名／公開検証経路はこの段階では切替禁止。
- `canonical_v2_golden.py`から出す日本語・null・float（100.0/-0.0/1e-7）・offset日時・市場arrayの5ベクトルで、GAS v2 canonical bytes、hash、テスト専用HMACの一致を検証。snapshot原本v1 IDは保持し、変更不能。
- E4/D1のCI PASSは新方式のオフライン互換性に限る。production issuer/HMAC鍵分離、実ChatGPT原文取得、永続private store、Docs/Pages E2Eを代替しない。

## 2026-10-15 D2 preflightコード契約追補（Draft）
`scripts/reporting/d2_preflight.py`は`market-report-d2-preflight/v1`構造を純粋関数で検査する。必須契約：lane=api-shadow、eligibility=SHADOW_NOT_ELIGIBLE、dry_run_only=true、allow_publication=false、external_tools=[]、web_search_calls=0、固定モデル版、営業日の08/12/16/21、immutable-context-snapshot/v1、strict-json-schema/v1、max_attempts=max_runs=1、Decimal入力・出力単価とtoken上限、USD run/month cap、private/immutable/readback/store-retention、timeout UNKNOWN停止、独立承認記録参照。参照文字列は独立認証ではないため、`api_send_allowed=false`と`publication_allowed=false`は常に維持する。worker外部APIやpublisherへの資格情報は追加しない。
