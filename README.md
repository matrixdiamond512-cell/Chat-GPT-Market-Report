# マーケットレポート作成・配信システム

**引き継ぎ・開発入口** — 作成日: 2026-10-20 JST

このリポジトリは、市場データ収集、マーケットレポートの検証・GitHubへの登録、Google Drive保存済み本文の取り込み、配信ポータルの表示・公開、GitHub Actionsによる更新と検証を管理します。**ソースコードが存在することと、定時の本文生成・Docs保存・PNG保存・Portal公開の実稼働成功は別です。**

## Codexで開発を引き継ぐ場合

1. [AGENTS.md](AGENTS.md) を読み、最優先で [配信システム文書管理規程](docs/system/DOCUMENT_CONTROL.md) を確認する。
2. [HANDOFF.md](HANDOFF.md) の別PCセットアップ、構成、現在の障害・PR・証拠基準を読む。
3. [正式要件](docs/system/requirements.md)、[正式仕様](docs/system/specification.md)、[運用マニュアル](docs/system/operations.md) を確認する。
4. [開発記録](docs/project-control/OBJECTIVE_CARD.md)、[意思決定](docs/project-control/DECISIONS.md)、[検証証拠](docs/project-control/EVIDENCE_LEDGER.md)、[Lessons](docs/project-control/LESSONS.md) と[Issues](https://github.com/matrixdiamond512-cell/Chat-GPT-Market-Report/issues)・[PR](https://github.com/matrixdiamond512-cell/Chat-GPT-Market-Report/pulls)・[Actions](https://github.com/matrixdiamond512-cell/Chat-GPT-Market-Report/actions) を照合する。

現行の `config/report_schedule.json` は、平日 **08:00 / 12:00 / 16:00 / 21:00 JST**、土日新規配信なし。ただし実際のChatGPT定時実行・Google Apps Scriptトリガー・外部保存先・公開内容は別途確認が必要です。

**開発を続けるPCでは、担当者本人のCodex/OpenAIアカウントを使用してください。** GitHubリポジトリを共有しても、過去のCodex会話、ローカルの未コミット変更、非公開の認証情報は自動で引き継がれません。pushにはリポジトリへの書込み権限が必要です。

**変更管理ID**: `HANDOFF-20261020-01`。このREADME/HANDOFFは開発引き継ぎ用です。定時実行・公開ゲート・Google Docs正式文書の仕様変更は行いません。
