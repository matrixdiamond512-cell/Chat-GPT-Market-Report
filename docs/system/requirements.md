# マーケットレポート配信システム 要件定義書
2026-10-13 / PRレビュー用。3文書は独立。GitHub mainの静的確認・本番稼働・未マージPRは区別する。
対象：データ取得→検証→本文・図解→ChatGPT表示→Drive保存→GitHub→Portal公開→公開後検証。
REQ-01: 日時、出典、reportId、revision、本文・図解、保存と公開の証跡を追跡する。
REQ-02: ChatGPT実タスクは平日08/12/16/21が有効、土曜08は無効。main configはPR #99マージにより土曜発行なしへ修正済み。
REQ-03: 本文のPUBLISHEDと図解のNOT_READYは同時に存在できる。本文公開と全工程完了を混同しない。
REQ-04: 08:00の28項目5列表の品質検査を要求。実データの全取得成功とは別。
REQ-05: Google Docs保存receiptとinfographicManifestを区別し、公開前後の検証証拠を保全する。
REQ-06: Draft PR #94/97は本番実装済みと認めない。
REQ-07: 要件定義書、仕様書、運用マニュアルを別ファイルとし、書込対象IDの照合を必須にする。
未解決：実行中トリガー、全旧版条項比較、PR本番採用、最新CI・Drive・公開URLの実検証。

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
- PR #128では、実原文の見出し同義表現を、実際の見出し行に限ってPython/GAS双方で認識し、必須セクション本文の不足を引き続き拒否する。公開条件の緩和や原文変更は行わない。PRは未マージであり、本番反映済みとは扱わない。
- 08:00 Google Docs 2件は5,933文字の本文が完全一致するが、別ID・別revisionである。1枠の重複登録はしない。12:00はDocs原文5,815文字。過去の「見出し欠落」という記録を訂正し、正しい見出し行が存在することと、スナップショット証拠が別途欠けることを分ける。
- 08:00の確認済みmarket-historyは10:24 JST生成で、report ID/revision/snapshot ID/context/body hashがなく、08:00レポートのsnapshotとは認定しない。12:00用snapshot履歴は確認できない。いずれも過去の市場データから再構成しない。
- GitHub作業ブランチ上の12:00レポートは `BLOCKED_SNAPSHOT_MISSING`、図解は `DRIVE_SAVED_QA_PENDING`。図解状態は本文公開状態と独立する。保存receiptの `saved` は公開receipt/Pages成功ではない。ChatGPT内部の正確な停止処理・エラー文は未取得でUNKNOWN。
- 3文書共通の受入未完了事項：08/12/16/21の次回各定期実行について、原本・bound snapshot・GitHub正本・公開receipt・各JSON・Pages本文readbackを工程別に確認する。1枠成功だけで復旧完了にしない。

## 2026-10-14 14:36 JST 継続追補 v1.10
- PR #128のvalidator/test commit `4cb2dce385300c51447d7c4a8ed316bc4637ab8a` の関連Actions 8件はすべてSUCCESS。Apps Script suiteの最初の失敗は合成fixtureの市場本文量不足であり、公開ゲートを変更せずfixtureのみ説明的なテキストへ修正した。文書更新は後続commit `5420f316038dba58ea0e867fdceedfd0f1a2f26c` に含む。PRは未マージ。
- 3つの既定Google Drive正式文書へ同一の追補をrevision guard付きで追記し、読み戻しを確認した。次回16:00の実行結果および08/12/16/21の反復本番E2Eは未確認で、全枠受入は未達。

## 2026-10-14 ダッシュボードキー整合・本番停止追補 v1.11
- 本番21:30の実トリガー `runMarketReportMaster2130` は公開前SOPの複合見出し判定で停止した。GitHub書込以前の失敗でありPNG生成は直接原因ではない。PR #128の見出しエイリアス修正と厳格な本文内容検査は維持し、原文は改変しない。
- 同期回帰CI失敗の原因として、`apps-script/DashboardJsonSync.gs` が `currentReportKey` に日時表示形式 `YYYY-MM-DD HH:MM` を生成する一方、`scripts/report_identity.py` と `verify_publication_consistency.py` は正規キー `YYYY-MM-DD_HH-MM` を要求していた。PR #128でApps Script側を正規キーへ修正し、`sources[].asOf` の読みやすい表示時刻と `dataAsOf` のタイムゾーン付き時刻は従来どおり保持する。
- 同一PRに `scripts/test_dashboard_report_key_contract.js` を追加し、`market-report-sync-recovery-ci.yml` の回帰検証に組み込んだ。コード修正コミット `fdf71abad8bf976627f0b9a828826f8e4213117f` の関連Actions 8系統はSUCCESS。再発防止はコード/CIの合格までであり、Apps Script本番環境への反映・本番再実行を意味しない。
- 2026-10-14 08/12/16/21のレポートはsnapshot/contextと本文hashの受入証拠が不足するため公開保留を維持する。過去データを後付けせず、ChatGPT本文↔Google Docs↔GitHub本文の同一性とreceipt/Pages全文readbackを時刻ごとに検証する。PR #129は停止記録であり公開成功ではない。
