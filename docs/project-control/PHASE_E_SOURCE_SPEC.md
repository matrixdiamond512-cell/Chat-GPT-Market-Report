# Phase E user specification — 2026-10-06

以下は今回のユーザー指示の全文。従来のSOURCE_SPEC.mdは保持する。分類ADD：Phase Eの設計＋dry-runだけを追加承認。本番禁止と既存未解決事項は継続。

次はPhase Eの「設計＋dry-run実装」だけを行ってください。

本番接続、本番Drive更新、Git push、Pages deploy、
production JSON更新はまだ禁止です。

目的は、
Google Docs / PNG / Publication Manifest / Git / Publication Receipt
を同一transaction identityで安全に結ぶPublisher層を設計・検証することです。

必須identity:
- report_id
- revision
- snapshot_id
- body_hash
- drive_file_id
- png_file_id
- manifest_id

実装要件:

1. Google Docs保存
- report_id + revisionで対象を固定
- 同名だけで正本判定しない
- 保存後にsame fileIdを再読取
- fullText全文比較
- 許可済みnormalizationだけ適用
- 不一致なら停止

2. PNG保存
- same report_id
- same revision
- same snapshot_id
- same body_hash
- Drive上の実在確認
- PNG bytes確認
- PNG欠落なら後続禁止

3. Publication Manifest
公開前に生成する。

最低限:
- manifest_id
- report_id
- revision
- snapshot_id
- body_hash
- drive_file_id
- drive_url
- png_file_id
- png_filename
- created_at
- status=READY_FOR_PUBLICATION

Manifest生成後は内容をimmutableにする。

4. Git登録
- Manifestに固定されたartifactだけを使用
- 新しい市場データを再取得しない
- Drive Docを再選択しない
- PNGを再選択しない
- commit SHAを取得
- responseが失われた場合は再commit前に既存SHA/contentを照合

5. Publication Receipt
公開前には生成しない。
Git/Pages/DOM検証後に生成する設計とする。

最低限:
- receipt_id
- manifest_id
- manifest_hash
- report_id
- revision
- git_commit_sha
- pages_deployment_id
- published_at
- verified_at
- portal_url
- dom_validation_status
- final_status

6. Retry / Recovery
以下の途中停止をfixtureで再現する。

- Docs保存後に停止
- PNG保存後に停止
- Manifest作成後に停止
- Git登録後response消失
- Receipt生成前に停止

再実行時に、
既に成功した工程を重複実行せず、
未完了地点から再開できること。

7. Idempotency
同じ
report_id + revision + snapshot_id + body_hash
で2回実行しても、

- 重複Doc
- 重複PNG
- 重複Manifest
- 重複Receipt
- 二重Git登録

を発生させない。

8. Error states
最低限:

WAITING
DOC_SAVED
DOC_VERIFIED
PNG_SAVED
PNG_VERIFIED
MANIFEST_READY
GIT_REGISTERED
PUBLISHED
VERIFIED
FAILED
UNKNOWN
NEEDS_REVIEW

9. 2026-10-02_21-00
この枠を本番fixtureとして変更しない。
OLD/NEW Drive IDのどちらも正本認定しない。
read-only fixtureとしてのみ利用。

10. テスト
最低限追加:

- duplicate Doc prevention
- same fileId readback
- body mismatch stop
- normalization allowed/forbidden
- missing PNG stop
- wrong PNG reportId stop
- retry after Docs
- retry after PNG
- retry after Manifest
- lost Git response recovery
- duplicate Manifest prevention
- duplicate Receipt prevention
- stale revision reject
- changed snapshot reject
- changed bodyHash reject

11. production safety
以下を変更しない:

- production Drive Docs
- production PNG
- production receipts
- reports/*.json
- reports.json
- latest-report.json
- dashboard.json
- GitHub main
- Pages

12. 最終報告
- Phase E architecture
- state machine
- schema
- changed files
- commits
- tests
- PASS / FAIL / NOT_RUN
- production未変更の証拠
- Phase Fへ進める条件

Phase E dry-runまでで停止してください。
