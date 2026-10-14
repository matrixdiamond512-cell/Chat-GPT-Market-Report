# OpenAI API 専用レポート生成worker — 非公開shadow設計

- 状態: **DESIGN ONLY / API呼出し・実装・デプロイ未実施**
- 設計日: 2026-10-15 JST
- 選択: B。既存ChatGPTタスクは継続し、新workerは当初shadow試験だけに使う。
- 関連: [GATE-F0調査記録](../project-control/GATE_F0_INVESTIGATION_20261015.md)、PR #130。
- 受入の境界: この文書やshadow試験の成功だけで生成元接続・本番公開完了とはしない。

## 決定事項

1. 現行のChatGPT定期タスクは停止・変更せず、利用者がチャットでレポートを読める状態を維持する。
2. 新しいworkerは別のproducer lane `api-shadow` として扱う。同じ論理slotの `report_id` を記録しても、ChatGPT laneとの成果物を統合・上書き・自動選択しない。
3. 初期workerは専用の非公開stagingだけに書く。Google Docs/Drive、Sheets、GitHub正本、`reports.json`、latest/dashboard、公開receipt、Pagesへの資格情報・書込経路を与えない。既存ChatGPT taskの設定済み挙動は維持し、新workerから二重登録を起こさない。
4. 実運用署名schema、canonicalization、鍵管理がP3で確定するまでは、shadow証跡を本番issuerのproducer-proofとして扱わない。公開publisherはfail-closedのままにする。
5. API費用と保管先の選択は未承認。具体的なAPI呼出し、鍵作成、定期起動、外部保存はこの設計段階では行わない。

## 現行実装から再利用する境界

mainにある既存Pythonは、対象slotを明示する不変 `ReportContext` と、取得値をfreezeしてdigestを持つ `MarketDataSnapshot` を提供する（`scripts/reporting/context.py`, `scripts/reporting/snapshot.py`）。

- contextの `report_id` は `YYYY-MM-DD_HH-MM`。時刻は `08:00/12:00/16:00/21:00` のいずれか。
- `data_cutoff` と各値の `asOf` を検証し、slot後や別日のデータを紐付けない。
- snapshotを一度固定した後、モデル再試行で市場データを取り直さない。再試行は同じcontext/snapshotを参照し、異なるAPI応答は別attemptとして残す。
- Python digestのserializationはGAS側 `marketReportProofCanonical_` と互換とはまだ証明されていない。shadow内の記録と本番proofを混同せず、Python/GAS golden fixturesが通る前に共通署名対象として使わない。

## 構成案

```text
JST slot trigger (初期は手動shadow起動)
  -> worker run/attempt ID発行
  -> ReportContext作成
  -> 既存の承認済み取得経路から市場値を取得・検証
  -> MarketDataSnapshotをfreezeし、contextとdigest照合
  -> Responses API (strict JSON Schema、モデルへの外部toolなし)
  -> response ID/status/model/usage/raw responseを捕捉
  -> schema・市場値・見出し・本文SOPを検証
  -> raw本文のSHA-256と実行receiptを計算
  -> 非公開stagingへのみ保存（SHADOW_NOT_ELIGIBLE）
```

モデルにWeb searchや任意function callingを許可すると入力snapshot外の最新値取得や副作用が混入するため、初期shadowでは許可しない。必要なニュース/イベント情報はworkerが取得前に出典と時刻を確認し、固定snapshotまたは別の固定済みsource bundleとしてモデル入力に含める。本文の数値は固定入力との照合に失敗したら停止する。

Responses APIのStructured Outputsを `text.format.type=json_schema`, `strict=true` で利用し、本文、所定見出し、slot identityを表す出力schemaを定義する。schema準拠だけでは数値正確性・原文真正性を証明しないため、worker側の意味検証を必須とする。refusal、`incomplete`、空本文、schema外出力はすべてBLOCKEDで保存し、下流公開へ渡さない。[Structured Outputs guide](https://developers.openai.com/api/docs/guides/structured-outputs)

Responses APIの応答に含まれる `id`、`status`、`model`、`output`、`usage` と本文を、worker実行内で受け取ったまま保存する。Workerが後から自己申告したresponse IDだけでは足りない。API request/responseを受けた実行ログ、受信時刻、raw response hash、API request IDが取得できる場合はそのIDも同じreceiptに結び付ける。[Responses API reference](https://developers.openai.com/api/reference/python/resources/responses)、[API response example](https://developers.openai.com/api/docs/libraries/openai-cli)

## Shadow record契約案

非公開storeのprimary keyは `shadow_run_id`（UUID）とし、`report_id` 単独では上書きしない。最低限、以下を同一run recordへ記録する。

- `lane=api-shadow`, `eligibility=SHADOW_NOT_ELIGIBLE`, `shadow_run_id`, `attempt_id`, `report_id`, `revision`, `mode`
- ReportContext全文、Context digest、snapshot全文、snapshot_id、schema version、cutoff、captured_at、各marketのsource/status/asOf
- API request start/end、Responses API `response_id`、`status`、model snapshot、usage、response API request ID（取得できる場合）
- prompt/template hash、schema hash、worker code commit、request JSON hash、raw response JSONとhash
- producer出力 `body_text` のUTF-8 raw SHA-256、別管理のcanonical hash/version（正規化契約確定後のみ）、検証結果とBLOCKED reason
- private storage object ID/version、保存時刻、access/audit log参照
- signingについては、shadow専用issuerまたは未署名receiptと明記。実運用鍵/署名と共用しない。

raw API response・本文は非公開stagingに保管する。通常ログには本文・API key・署名秘密を出さず、run ID、status、hash、エラーコードのみを記録する。raw/canonical hashは各々のbyte範囲とencodingが定義されるまでcanonical hashを生成しない。

## 非重複登録の制御

| 系統 | 初期shadowでの役割 | Google Docs/Sheets/GitHub/Pages書込 |
|---|---|---|
| 既存ChatGPT task | 現行の利用者向け出力を継続 | 現設定を維持 |
| API worker | 同一slotのshadow生成・比較用内部証跡 | **禁止。資格情報を配布しない** |
| Apps Script publisher | 現行fail-closedゲートを維持 | 実producer proofがないrunは拒否 |

workerのネットワーク/credential allowlistはOpenAI API、承認済み市場データsource、専用private stagingに限定する。stagingからGoogle Docsや公開レポートへのcopy/relayを自動化しない。Shadow runが成功しても `PUBLISHED`、正式receipt、公開statusを出さない。ChatGPT taskとworkerの本文を同じDocsへ連結・追記することも禁止。

## 冪等性・再試行・版管理

- schedule slotは明示的JSTで求め、run IDはslot identityから独立して一意発行する。
- 同一 `shadow_run_id` の再処理は保存済みsnapshotとrequest hashを再利用する。モデル再生成は同attemptを上書きせず新attemptで記録する。
- 同一 `report_id/revision/lane` で異なるbody hashが生じたら競合として隔離し、どちらも正本にしない。
- revisionはproducerの明示的な単調増加値。Drive mtime、実行時刻、最新indexから推測しない。
- 同slotのChatGPT本文は比較ラベルに留め、API本文の証拠・hash・署名に流用しない。比較対象取得が正式に許可されていない間は比較せず、worker自身のAPI出力だけを記録する。

## 権限・鍵・費用

API keyは専用のAPI project/service identityから発行し、限定権限・有効期限・rotation・利用上限を設定してsecret managerから実行時に注入する。公開GitHub、ソース、Docs、タスク指示、ログに保存しない。OpenAIの推奨も、keyの非公開、secret manager、権限管理、rotation、usage監視を求めている。[API key safety](https://help.openai.com/en/articles/5112595-best-practices-for-api-key-safet)

本番proofが必要となる段階では、publisherは公開鍵のみで検証し、署名秘密鍵はKMS/HSM等の署名担当に分離する設計候補とする。shadow keyを使う場合はproduction verifierから受理されない別issuer/key IDにする。最終アルゴリズム・key custody・署名対象canonicalizationはP3のdecision gateで確定する。既存PR #130の共有HMAC keyを「独立署名」とは扱わない。

費用はモデルとtoken量に依存する従量課金である。月額を先に断定せず、代表的な1 slot shadowで `input_tokens`, `output_tokens`, 再試行数を計測してから、次の式で最大費用を提示する。

```text
月額上限 = 予定run数 × (入力token数×入力単価 + 出力token数×出力単価) / 1,000,000
          + 検索tool利用料 + private storage/compute費
```

現行の価格は選択model/処理tierにより変わるため、model選択と予算上限は実API実験前に別途承認する。[OpenAI API pricing](https://developers.openai.com/api/docs/pricing)

## 段階と受入条件

### D0 — 設計（本書）

完了条件: B選択・ChatGPT並行維持・worker非公開専用・二重登録防止が明記されている。**完了**。

### D1 — local/offline contract

実APIを呼ばず、固定test fixtureでcontext/snapshot/hash/strict schema/app-level validation/duplicate conflict/fail-closedをテストする。fixturesはテスト専用とし本番proofに昇格しない。Python/GAS golden testsは日本語、小数、`100.0`、null、負数、日時、市場配列を含む。

### D2 — 1 slotの手動API shadow

実API費用上限、専用project/key、private store、保持期間、data source、対象slotの承認を得てから一度実行する。API応答全文とresponse ID/statusを保存してreadback/hashを照合する。Google Docs/Sheets/GitHub/Pages writer呼出し・receipt・`PUBLISHED`状態が0件であることを確認する。

### D3 — 4枠の限定shadow観測

D2受入後、承認された期間だけ08:00/12:00/16:00/21:00をChatGPT taskと並行観測する。各枠のworker raw evidence、cutoff/source整合、費用、失敗/再試行、非公開保存readbackを評価する。現行ChatGPT taskの停止・変更はしない。

### D4 — 将来のproducer接続判断（本番未承認）

D1-D3だけでは本番proof issuer/署名、Apps Script接続、公開権限を与えない。D4以降はschema/canonicalization/key separation/cross-language golden testと実環境権限レビューを別decision recordで確定し、別途明示承認を得る。8/12/16/21の本番E2E E5が揃う前に復旧完了を宣言しない。

## Shadow受入の必須否定確認

すべてのshadow testで、GitHub canonical/index/latest/dashboard、Docs/Sheets、receipt、Pagesに対するwrite countが0であることを実装・監視の両面で確認する。missing snapshot、cutoff超過、source不明、response incomplete/refusal、schema違反、本文内数値不一致、署名不正、API timeout、同revision hash競合、重複slot、staging readback不一致は全てBLOCKEDとする。

現時点ではD1コード・D2実行・API予算・private storage・API project/keyは未作成/未承認。次の実装工程はD1のlocal-only contractであり、API利用を始める前にD1差分と費用上限・保存先をレビュー可能にする。
