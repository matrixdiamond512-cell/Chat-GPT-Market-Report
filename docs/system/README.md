# 配信システムの正本識別と更新先
2026-10-13 / PRレビュー用。3文書は独立。GitHub mainの静的確認・本番稼働・未マージPRは区別する。
要件定義書: docs/system/requirements.md / Google Docs 102PMtKQ4DaXqV1G2RhE8vFtQ8qes-tvIvy2jYQda_xA
仕様書: docs/system/specification.md / Google Docs 1qL7f3yKwghuDb5PiAI3RhwFJUVUfLwGakC8z8EOJ9oI
運用マニュアル: docs/system/operations.md / Google Docs 1OUVDAMjv009VWlI48Jb8TVuzszy4TIkjgBrHlzbNxYg
関連Web資料だけを更新して本件が完了したと報告しない。編集前に対象の文書名・Google Drive fileId・GitHubパス・revision・変更要求IDを確認する。旧正本や他文書への自動変更は禁止。上記Google Docsは統合ドラフトであり現時点では正式正本と認定しない。

## 2026-10-13 実検証で確定した事実
- 実ChatGPTタスクは平日4枠のみ有効。土曜日旧タスクは無効。Apps Script実トリガーは接続元から照会不可。
- PR #95/#96はマージ済み。PR #94/#97/#98はDraft・未マージ。
- PR #94 最新該当Actionsの日本10年債MOF検証がFAIL、Sheets/更新jobはSKIPPED。PR #97はデザインテストPASS、本番公開未確認。
- 2026-10-12 21:00 のDocはGoogle Driveに実在。旧Receiptにはstrict validator必須のtitle/status/publisher/driveFileId/driveUrl/savedAtが欠ける。保存主体や日時を推測補完しない。
- PR #98の公開workflowへの直接Receipt検査追加は撤回。新旧スキーマ移行と実テストまでは本番導入禁止。
