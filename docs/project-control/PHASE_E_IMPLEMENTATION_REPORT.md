# Phase E 設計＋dry-run 実装報告 — 2026-10-06

今回の承認範囲は完了。実接続・本番公開は未実施。Phase F以降には進んでいない。

基準commit：c6d1236a22443e7fdef2fde97de1aef4dca9da10。
最終テスト対象commit：c530715184e7928cbf99031983499ffa366d10a6。
branch：codex/report-foundation-a-b-d-c。すべてローカルcommit、pushなし。
最終報告だけのcommit SHA・最終stat/statusはリポジトリ外のfinal-verification.jsonとCHATGPT_PHASE_E_HANDOFF.mdに追記する。

## 1. Architecture / implemented

Explicit ReportContext＋immutable MarketDataSnapshot＋original ReportObject＋指定PNG bytesをG0〜G2で検証し、同一transactionをclaimする。PublisherはDocs保存→同じfileId全文再読取G3→PNG保存／同じfileId存在・bytes・identity検証G4→immutable Manifest G5→固定artifactだけのGit登録G6→明示されたfixtureのActions／Pages／DOM検証G7→Receipt G8を接続する。

実装はオフライン専用DryRunPublisher＋SQLite FixtureStore。実Drive／実Git／実Pages adapterはない。Storeへの保存効果とjournalのcheckpointは別々に永続化し、各効果の前にaction IDを記録する。別SQLite connectionのexclusive lockとUNIQUE制約で同時実行を抑止する。プロセス再起動後は同じaction IDと保存済みcontentを照合し、完了済み保存を繰り返さない。Receipt生成前の公開観測も永続化する。

Docを同名検索で選ぶ処理、市場再取得、latest参照、Doc／PNG再選択、Git実行、push、deploy、production JSON writerは実装していない。リトライ時の同じIDの再検証は行う。CLIには必須--dry-runしかなく、本番モードへの切替はない。fixture保存先はrepository外の明示的なpublisher-fixture-* directoryに限定する。

実Driveアダプターの設計：durable identity registry＋write-ahead intent＋artifact action metadataで対象を固定。PRESENT / ABSENT_PROVEN / AMBIGUOUS / UNKNOWNを区別し、空の検索結果だけで再作成しない。Gitの実アダプターはexpected parent/tree/blob/Manifest/action referenceを照合し、応答消失時に既存commitを確認する。これらは設計のみで、本番接続はNOT_RUN。

## 2. State machine

```text
WAITING → DOC_SAVED → DOC_VERIFIED → PNG_SAVED → PNG_VERIFIED
→ MANIFEST_READY → GIT_REGISTERED → PUBLISHED → VERIFIED
```

例外state：FAILED / UNKNOWN / NEEDS_REVIEW。例外時は最後の成功checkpointとpending_actionを保持する。不一致は停止。UNKNOWNは保存済みactionのSHA/contentを照合するまで再保存しない。照合不能はUNKNOWNを維持する。照合後は成功checkpointに復帰する。FAILED／NEEDS_REVIEWを無条件にリセットする操作はない。修正は新revisionまたは別途レビューしたrecoveryが必要。

初回の通常dry-runはGIT_REGISTEREDで止まりReceiptなし。明示的なsimulation=trueの公開fixtureを与えた場合に限ってG7／G8をテストできる。ここでのPUBLISHED／VERIFIEDはfixture stateであり本番公開の証拠ではない。

## 3. Schemas

### Identity / frozen envelope

```text
report_id: string
revision: positive integer
snapshot_id: string
body_hash: SHA-256(raw original full_text UTF-8)
transaction_id: "transaction-" + canonical_sha256(first four fields)
drive_file_id: pinned Doc ID after save
png_file_id: pinned PNG ID after save
manifest_id: pinned Manifest ID after G5

envelope = {context, snapshot, report, png_base64}
envelope_hash = canonical_sha256(envelope)
action_id = transaction_id + ":" + doc|png|manifest|git|receipt
```

同じreport_id＋revisionにsnapshot/bodyHash変更は拒否する。envelopeの別フィールドやPNG bytes変更も拒否。高いrevisionがclaimされた後の低いrevisionも拒否。ReportContext／ExecutionContext／MarketDataSnapshot／ReportObjectの既存schemaは変更していない。

### Doc / PNG

```text
Doc: file_id, report_id, revision, snapshot_id, body_hash, full_text, drive_url
PNG: file_id, report_id, revision, snapshot_id, body_hash, filename, png_base64
filename = マーケットレポート_<report_id>.png
```

Docはsaved/read fileIdとURL、metadata identity、fullText全文一致を確認。許可normalizationはCRLF→LFと末尾LFを1つ取り除く処理のみ。余分な空行、空白、句読点、数字を同一視しない。失敗時には全文比較diffをjournalに保持。

PNGはmodeled Drive存在、same saved/read fileId、4つのidentity、正式filename、PNG signature／chunk bounds／CRC／IHDR／IEND／zlib pixel構造、固定PNG hashを検証。synthetic 1×1 PNGなので実帳票の画像内容や実Drive存在は未証明。

### Publication Manifest（immutable）

```text
manifest_id, report_id, report_date, report_time,
revision, snapshot_id, body_hash,
drive_file_id, drive_url,
png_file_id, png_filename, png_hash,
created_at (timezone-aware), status=READY_FOR_PUBLICATION
```

manifest_id = manifest-＋ID追加前fieldsのcanonical SHA-256。
manifest_hash = IDを含むManifest全体のcanonical SHA-256。
created_atは初回に固定。公開前G5で生成し、公開後もManifestを変更しない。deep-frozen返却値とinsert-only effectの照合でimmutabilityを保持する。

### Git registration（simulation）

```text
manifest_id, manifest_hash,
bundle={manifest, manifest_hash, report, doc, png},
bundle_hash, git_commit_sha, simulation=true
```

fixture git_commit_shaは40hexのsynthetic content IDであり、実Git commitではない。実装コードのローカルcommit SHAとは別。lost responseでは既存Git actionのSHAとbundle全文を照合してからGIT_REGISTEREDへ進む。実commit／pushはNOT_RUN。

### Publication Receipt（immutable、公開検証後のみ）

```text
receipt_id,
manifest_id, manifest_hash,
report_id, revision,
git_commit_sha, pages_deployment_id,
published_at, verified_at,
portal_url, dom_validation_status=PASS, final_status=VERIFIED
```

receipt_id = receipt-＋G8 receipt fieldsのcanonical SHA-256。
snapshot/body/Doc/PNG identityはManifest hashを通じて結合する。Git／Actions／Pages／DOMが通る前に成功Receiptを生成しない。失敗・結果不明はjournalに記録する。実運用のFAILED／UNKNOWN receipt方針は未決定。

### Durable journal

```text
report_id, revision, transaction_id,
envelope, envelope_hash,
state, checkpoint, created_at, pending_action,
error, events, failure_evidence,
publication_evidence,
manifest, manifest_hash, git_commit_sha, receipt
```

完了checkpointなのにartifact／Manifest／SHA／公開観測／Receiptが欠けている場合は再作成せずNEEDS_REVIEW。公開観測変更も同様。全canonical hashはUTF-8／sort_keys／compact separators／ensure_ascii=False／allow_nan=False。

## 4. Changed files

追加：

- scripts/reporting/publisher.py — Publisher、identity、永続Store、recovery、state。
- scripts/publish_report_dry_run.py — offline専用CLI。
- scripts/run_phase_e_acceptance.py —再現可能acceptance、別fixture namespace、保護証拠。
- tests/publisher_fixture.py — synthetic input／公開観測。
- tests/test_publisher.py — 44テスト。
- docs/PHASE_E_PUBLISHER.md — architecture、state、全schema、実adapter設計、Phase F条件。
- docs/project-control/PHASE_E_SOURCE_SPEC.md — 今回指示全文。
- docs/project-control/PHASE_E_IMPLEMENTATION_REPORT.md — 本報告。

更新：OBJECTIVE_CARD.md、EVIDENCE_LEDGER.md、DECISIONS.md、LESSONS.md。
正式v1.8の5文書、既存runtime／G0〜G8、production writer、UI／workflow／GASは変更なし。

## 5. Commits

1. 3da7efaf69bd7decbead26f0de9007a2b3ff77fa — feat: add offline Phase E publisher and durable recovery fixtures
2. 146f2d65ef32f590344c21e9857d76989c0b46b9 — fix: reconcile publisher checkpoints and retain verified recovery evidence
3. c530715184e7928cbf99031983499ffa366d10a6 — test: preserve dry-run history across repeatable Phase E acceptance
4. 最終の報告／acceptance記録commitはfinal-verification.jsonに収録。

## 6. Tests / PASS・FAIL・NOT_RUN

最終run：phase-e-20261006T084037362696Z。Python 3.12.14。
Phase E追加44件PASS（下記）。tests/全122件PASS＋既存script16件PASS＝重複を数えず138件PASS。Phase E44件の単独実行は全122件の内数。

必須項目すべてPASS：duplicate Doc、same fileId readback、body mismatch停止、allowed／forbidden normalization、missing PNG停止、wrong PNG reportId停止、Docs／PNG／Manifest再開、lost Git response復旧、duplicate Manifest／Receipt、stale revision、changed snapshot／bodyHash拒否。

追加境界もPASS：別PNG metadata／bytes、checkpoint／Git／Manifest／Receipt破損、UNKNOWN照合不能と復旧、Receipt前再起動、固定公開観測、同時runner拒否、保存先保護、protected slot読み取り、no network／Git executable、CLI別プロセス再開。

CLIの独立シナリオ：

|停止／障害|再開結果|重複保存|
|---|---|---|
|Docs保存後|GIT_REGISTERED|Doc／PNG／Manifest／Git 各1|
|PNG保存後|GIT_REGISTERED|同上|
|Manifest作成後|GIT_REGISTERED、同じManifest／SHA|同上|
|Git response消失|UNKNOWN／checkpoint=MANIFEST_READYから既存SHA照合|Git1|
|Receipt直前|PUBLISHEDから保存済み観測でVERIFIED|Receipt1|

GAS narrative、Node UI foundation、index validator、publication consistency、date-only／aware receipt boundary、Python AST、scenario保存件数と同一ID比較：PASS。

FAIL：既存productionのvalidate_market_reports.py構造不備。productionを修正していないため保持。以前のMorningReportQA不足も今回修正なし／live再検査NOT_RUN。最初のOS sandbox tempでのunit実行はPermissionErrorによる環境FAIL、明示的なwritable tempで最終全件PASS。

NOT_RUN：実Drive Docs保存／同ID再読取、実PNG生成／Drive確認、実publication Git登録／push、Actions開始、Pages deploy、実DOM、実Receipt、Phase F〜H、従来回帰対象外scripts/test_*.py 13ファイル。これらをPASSとは報告しない。

Evidence上限：E3のoffline recovery／scenario behavior。実サービス結果E5の公開保証なし。

## 7. Production未変更の証拠

repository外のreview/phase-e-dry-run-20261006にbaseline／acceptance／production-proof／scenario-results／全command logを保存。

- 前回最終c6d1236を基準にJSON／PNG／receipt等824ファイルのSHA-256比較：mismatch0、追加0、テスト前後一致。
- reports、reports.json、data（latest-report.json／dashboard.jsonを含む）、images/reports、publication-receipts、.github、apps-script、assetsのGit差分：空。
- local mainとremote tracking refsの変化：0。fetch／push／deploy／本番接続なし。
- 2026-10-02_21-00.json SHA-256：54c2ca7aa962e7a37c3691236d0e01a6fcdedc2def7a326ce6bdb271872dcfa3（前回と同一）。
- protected slotはread-only adapter testだけ。UNRESOLVEDのまま。OLD／NEWのいずれも正本認定せず、Publisherで保存前に拒否。
- production Drive Docs／PNG／Receipt／Pagesへの外部操作0。今回は外部接続自体を行っていないので第三者による変更有無の検証はしていない。本作業で変更しなかった事実と全世界で不変だった保証を混同しない。
- fixture Git／Receiptはrepository外の専用SQLite内のみ。テスト中に既存unsafe writerを呼ぶ従来回帰もTemporaryDirectory内だけ。

## 8. Known limitations / open outcomes

今回のE-01〜E-05は承認されたoffline範囲でACCEPTED。旧live publisher／deploy bypass、protected canonical identity、unsafe writer、過去PNG／構造不足は未解消。fixtureのuniquenessとSQLite lockは実Drive／distributed runnerの保証ではない。DB削除後のidempotency保証はない。PNGは実帳票画像一致を証明しない。G6 projectionはfixtureのReportObject copiesで、Phase Fのproduction projectionではない。

## 9. Phase Fへ進める条件 / next necessary action

1. ユーザーがPhase Fの対象・禁止範囲を明示的に承認する。
2. Manifestからcanonical／index／latest／dashboardへのmapping、schema、rollback／same-revision rulesを決定する。
3. unsafe canonical writerの扱いを独立したレビュー対象にする。
4. 実adapterのdurable journal／lock／retentionと確実な照合手段、FAILED／UNKNOWN／NEEDS_REVIEW recovery方針を決める。
5. original Chat fullText取り込み、typed table body互換、PNG rendererのprovenance／encodingを決める。
6. protected 2026-10-02_21-00を引き続き除外する。正本確定は別タスク。
7. 先にnonproduction acceptanceを定義し、本番Drive／GitHub／Pagesへの書込み承認を別途扱う。

次の必要な行動は上記判断。今回はPhase E dry-runで停止。本番公開やPhase F実装の自動着手はしない。

## Appendix: 追加テスト44件（すべてPASS）

- test_body_mismatch_stop
- test_changed_body_hash_reject
- test_changed_png_bytes_reject_same_identity
- test_changed_snapshot_reject
- test_changed_verified_observations_require_review
- test_cli_process_restart_recovery
- test_complete_state_sequence_and_no_external_calls
- test_concurrent_runner_rejected
- test_corrupt_git_content_requires_review
- test_double_execution_creates_one_of_each
- test_duplicate_doc_prevention
- test_duplicate_manifest_prevention
- test_duplicate_receipt_prevention
- test_failed_actions_stops_receipt
- test_failed_dom_stops_receipt
- test_fixture_destination_safety
- test_invalid_png_bytes_stop
- test_invalid_publication_evidence_cannot_issue_receipt
- test_lost_doc_png_manifest_receipt_responses
- test_lost_git_response_recovery
- test_manifest_tampering_rejected
- test_missing_manifest_journal_stops_git
- test_missing_png_stop
- test_missing_saved_effect_cannot_be_recreated
- test_new_revision_and_lower_retry
- test_no_receipt_before_publication
- test_normalization_allowed
- test_normalization_forbidden
- test_protected_slot_read_only
- test_receipt_journal_tampering_without_new_observations_rejected
- test_receipt_restart_uses_persisted_observations
- test_retry_after_docs
- test_retry_after_manifest
- test_retry_after_png
- test_retry_before_receipt
- test_retry_timestamp_does_not_change_manifest
- test_same_file_id_readback
- test_stale_revision_reject
- test_terminal_failure_requires_review
- test_unknown_after_registered_restores_checkpoint
- test_unknown_after_verified_restores_checkpoint
- test_unknown_lookup_never_recommits
- test_wrong_png_report_id_stop
- test_wrong_png_revision_snapshot_body_and_file_id

## Appendix: 回帰対象外scriptテスト（NOT_RUN、13ファイル）

- test_build_completed_event_records.py
- test_clean_legacy_event_records.py
- test_fetch_economic_calendar.py
- test_jpx_arbitrage.py
- test_postprocess_economic_calendar.py
- test_repair_missing_event_results.py
- test_stock_automation_contract.py
- test_stock_freshness.py
- test_stock_source_parsers.py
- test_usdjpy_flow_summary.py
- test_usdjpy_tradersweb_levels.py
- test_validate_weekly_claims_result.py
- test_write_market_data_to_sheets.py
