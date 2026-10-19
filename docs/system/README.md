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
