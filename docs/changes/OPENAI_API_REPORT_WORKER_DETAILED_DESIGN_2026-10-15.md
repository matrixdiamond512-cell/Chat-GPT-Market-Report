# OpenAI API 専用レポートworker — 詳細設計・費用検証追補

- 日付: 2026-10-15 JST
- 状態: **DESIGN ONLY**。API呼出し、鍵発行、スケジュール登録、Docs/Sheets/GitHub/Pages書込は未実施。
- 関連: [非公開shadow設計](./OPENAI_API_REPORT_WORKER_SHADOW_DESIGN_2026-10-15.md)、[B案決定](../project-control/P0_DECISION_B_SHADOW_WORKER_20261015.md)、PR #130。
- api-shadowは独立した生成物。ChatGPTタスクの原文・証拠・署名を代用しない。

## 1. 実行境界と責任分担

| コンポーネント | 責任 | 初期shadow権限 |
|---|---|---|
| 既存ChatGPT定期タスク | 既存どおりチャットにレポートを表示 | 設定を変更しない |
| Scheduler | JSTの対象slot起動、run/attempt採番 | 最初は手動起動。自動定期起動なし |
| Market-data adapter | 承認済み取得経路から値とsource/asOf/statusを取得 | 読取のみ。取得元未確定値は欠損扱い |
| Context/snapshot freezer | context・cutoff・市場データを固定 | 再生成でも一度保存した入力を再利用 |
| Report producer | 固定入力から本文生成、Responses API応答とusageを保存 | 専用API project/key。外向きwriter資格情報なし |
| Validator | JSON schema、slot、見出し、数値参照を検査 | 不一致は隔離してBLOCKED |
| Private evidence store | request/response、本文、hash、状態を保管・readback | 専用private領域のみ。保存先・保持期間はD2前に承認 |
| Docs/GitHub/Pages publisher | 将来の公開処理 | **shadow workerには存在させない**。PR #130のfail-closedを維持 |

既存タスクはチャット出力を継続する。API workerは同じslotを影で生成しても、既存タスクと同じDocsへの登録、Docs追記、Sheets履歴、GitHub正本・receipt、dashboard、Pagesのいずれも行わない。二系統の結果を自動選択・連結・上書きしない。

## 2. run契約と保存レコード

### Identity

- report_id: 既存契約の YYYY-MM-DD_HH-MM。slotの業務識別子。
- lane=api-shadow、run_mode=shadow、eligibility=SHADOW_NOT_ELIGIBLEを必須とし、既存ReportContext.mode=newは変更しない。
- shadow_run_id: runごとのUUID。各再試行は別attempt_idとし、以前のrecordを上書きしない。
- 内部一意制約: (report_id, revision, lane, attempt_id)。二重起動は一意制約またはadvisory lockで拒否する。同じreport_id/revision/laneに異なる本文hashがあれば双方を隔離する。

### Minimum record

~~~json
{
  "schema_version": "market-report-shadow/v1",
  "lane": "api-shadow",
  "run_mode": "shadow",
  "eligibility": "SHADOW_NOT_ELIGIBLE",
  "shadow_run_id": "uuid",
  "attempt_id": "uuid",
  "report_id": "2026-10-15_16-00",
  "revision": 1,
  "context": {"report_id": "2026-10-15_16-00", "mode": "new", "timezone": "Asia/Tokyo"},
  "context_sha256": "hex",
  "snapshot_id": "opaque-id",
  "snapshot_sha256": "hex",
  "cutoff": "RFC3339 timestamp with offset",
  "source_observations": [
    {"series": "example", "value": 0, "unit": "unit", "basis_date": "YYYY-MM-DD",
     "source": "provider and URL", "as_of": "RFC3339", "status": "verified"}
  ],
  "producer": {
    "provider": "OpenAI", "endpoint": "v1/responses", "model": "pinned model ID",
    "prompt_sha256": "hex", "schema_sha256": "hex",
    "request_sha256": "hex", "response_id": "provider ID or null",
    "response_status": "completed|incomplete|failed|unknown",
    "usage": {"input_tokens": 0, "output_tokens": 0},
    "body_utf8_sha256": "hex or null"
  },
  "validation": {"status": "PASS|BLOCKED", "reasons": []},
  "storage": {"object_id": "opaque", "version": "immutable version", "readback_sha256": "hex"},
  "created_at": "RFC3339 timestamp"
}
~~~

このrecordは公開producer-proof schemaではない。Responses APIのID・応答内容・usageはworkerが受信した値を保存し、応答のないIDを捏造しない。本文SHA-256はUTF-8生本文bytesに対して計算する。canonical hashは正規化仕様とPython/GAS golden test確定後まで生成しない。現行snapshot digestもPython/GAS互換が証明されるまで、issuer証明や公開ゲート入力に転用しない。

## 3. 状態遷移と失敗処理

~~~text
QUEUED -> CONTEXT_FROZEN -> SNAPSHOT_FROZEN -> REQUESTED
       -> RESPONSE_CAPTURED -> VALIDATED -> PRIVATE_STORED -> READBACK_VERIFIED
~~~

- 入力欠損、cutoff超過、source不明、schema違反、本文の市場数値不一致、refusal/incomplete、hash不一致、private readback不一致はBLOCKED。
- API timeoutで受領結果が分からない場合はUNKNOWN_PROVIDER_RESULTとして停止する。前attemptを照合する前に再送しない。再試行は同じ凍結snapshotを参照する新attemptにする。
- 保存後の本文やsnapshotを編集しない。修正は新revision/runとして残す。
- 成功状態はSHADOW_VALIDATEDのみ。PUBLISHED、公開receipt、Docs ID、GitHub commit/PR、Pages URLをshadow成功記録として出さない。

## 4. Responses API入力と検査

初期リクエストはv1/responsesのみを使い、built-in web search、function calling、その他の外部toolを指定しない。市場値・ニュース・イベントはAPI呼出し前に取得・出典確認し、固定snapshotまたは固定source bundleに含める。API出力は本文・見出し・参照市場観測IDを含むstrict JSON Schemaにする。Structured Outputsは形状を検査する補助で、事実性・出典の正しさはworkerの別検査で判定する。

- モデル名と利用可能なsnapshotを実験開始前に固定し、記録する。暗黙のlatest更新を避ける。
- 本文の各数値を入力観測と照合する。入力にない数値を補完しない。
- JSON parse不能、required field欠落、空本文、必要見出し欠落、slotと本文の識別子不一致はBLOCKED。
- 事前トークン上限と最大出力token数を設ける。上限超過入力は切り詰めず、API送信前に拒否する。
- prompt/schema/modelを変えた比較は別run metadataにし、同じrunを書き換えない。

## 5. Shadow用アクセス制御

- 実行主体に渡すのはOpenAI API、承認済み入力データ取得、専用private stagingの最小権限だけ。
- Google Docs/Drive/Sheets、GitHub Contents/PR、Pages、Apps Scriptへのtoken・OAuth scope・secretを置かない。下流writerを呼ぶライブラリやpublisher設定もworkerへ含めない。
- GitHub Actionsを使う場合もfork/PR contextにAPI keyを渡さない。D1はnetworkなしのfixtureテスト。
- 通常ログはrun/attempt ID、status、hash、usage、エラーコードのみ。本文、API key、署名秘密を出さない。
- private store選定までは実API shadowを開始しない。D2前に保存先、暗号化、IAM、保持期間、削除、readback方法を決める。
- shadow証跡を本番issuer署名へ昇格しない。将来の署名器にはpublisherとの権限分離、公開鍵のみの検証、key rotation/失効の別レビューが必要。

## 6. 費用検証（2026-10-15に公式OpenAI Docsを確認）

### 固定仮定

80 run/月（平日20日×1日4slot）、1 runあたりinput 12,000 tokens、output 4,000 tokens。標準処理、短文脈料金、cached inputなし。USD建てのモデル入出力分。

計算式: (input_tokens × input_price + output_tokens × output_price) / 1,000,000。

| Model | Input / 1M | Output / 1M | 1 run | 80 runs |
|---|---:|---:|---:|---:|
| GPT-5.4 mini | $0.75 | $4.50 | $0.027 | $2.16 |
| GPT-5.6 Terra | $2.00 | $12.00 | $0.072 | $5.76 |

公式モデルページの単価はGPT-5.4 miniが$0.75/$4.50、GPT-5.6 Terraが$2/$12 per 1M tokens。Responses API自体のendpoint追加料金はなく、利用tokenを選択モデル単価で課金する体系。[GPT-5.4 mini](https://developers.openai.com/api/docs/models/gpt-5.4-mini) · [GPT-5.6 Terra](https://developers.openai.com/api/docs/models/gpt-5.6-terra) · [API pricing](https://developers.openai.com/api/docs/pricing)

### Searchを使う別シナリオ

初期shadowは検索toolを使わない。将来1 runに3回のWeb searchを追加する場合、公表単価$10/1,000 callsから検索呼出し料だけで$0.03/run、$2.40/80 runs。検索結果content tokensもモデル入力単価で課金されるため、基本合計の下限目安はGPT-5.4 miniで$4.56/月、GPT-5.6 Terraで$8.16/月。検索content tokens、再試行、market data、compute/storage、税、為替は別。[OpenAI API pricing](https://developers.openai.com/api/docs/pricing)

### 運用上限と計測式

上記は仮定の試算で、予算承認額ではない。D2の前に選択modelの入力・出力上限、tool call上限、最大attempt数、全runの月次上限を決める。各runのAPI usageから実費を記録する。

~~~text
actual_run_cost =
  (input_tokens × input_rate + output_tokens × output_rate) / 1,000,000
  + web_search_calls × $0.01
  + other tool charges

monthly_observed_cost = Σ actual_run_cost for all attempts
~~~

初期設定では自動再試行をしない。上限到達時は新しいResponses API requestを送らずBLOCKED。timeout後の課金結果が不明ならUNKNOWNとして照合し、二重送信を避ける。課金実行、API project/key作成、secret登録、定期起動は別承認が必要。

## 7. D1/D2検証と合格条件

### D1 — 無課金・offline契約テスト（次工程）

架空の固定fixtureを使う。テスト値を本番候補・producer proof・正式snapshotに昇格しない。

| Case | Input/condition | Expected |
|---|---|---|
| 正常slot | ReportContext + snapshot fixture | 構造検査PASS、shadow状態 |
| cutoff超過 | slot後のsource asOf | API前にBLOCKED |
| 欠損/参考値 | required観測欠損または参考status | 値を埋めずBLOCKED |
| schema/refusal | 不正JSON、必須field欠落、refusal/incomplete | BLOCKED、公開writer 0回 |
| 数値の創作 | 出力値がsnapshotと対応しない | BLOCKED、private隔離 |
| response timeout | 応答ID/完了状態不明 | UNKNOWN、盲目的再送なし |
| 重複起動 | 同slot/revision/lane二重要求 | 一意制約で拒否 |
| 異なる本文hash | 同slot/revision/lane衝突 | 両runを隔離 |
| readback/hash | private object readbackがbyte不一致 | BLOCKED |
| shadow境界 | あらゆる結果 | Docs/Sheets/GitHub/Pages/receipt write mockが0 |

Python↔GAS golden test計画は、日本語UTF-8、小数/整数表現（100.0/100）、null、負数、offset日時、配列順序を含め、入力canonical bytesとcontext/snapshot SHA-256を照合する。規格未確定のまま既存hashを置換しない。

### D2 — 手動1 slot実API shadow（別承認後のみ）

D1レビュー、費用上限、専用API project/key、private store/IAM/retention、入力source、slot、担当を確定した後に限り、APIを1回手動実行する。受入条件はresponse ID/status/usage・生本文・hash保存、private store readback一致、source/cutoff/本文数値検査PASS、下流write 0件。費用や結果が不明なら次slotを起動しない。

## 8. decision gateと未解決事項

| Gate | 成果 | 現状態 |
|---|---|---|
| D0 | B案・並行運用・shadow境界の設計 | 設計記録あり |
| D1 | local/offline契約テスト | fixture-only 15件PASS・hash差分検査PASS（本番署名互換は未達） |
| D2 | 手動1 slot API shadow | 未承認・未実施 |
| D3 | 限定4枠観測 | 未実施 |
| Publisher接続 | trusted producer proof・Docs全文readback・全writer E2E | 未実装・本番停止 |

残る決定はworker実行環境、private storeと保持期間、公式市場データadapter/利用権、model snapshot、費用上限、D2対象slot。決定前にAPI利用・自動起動・外部保存へ進まない。PR #130はOPEN/Draft/unmergedを維持し、PR #128との統合は行わない。

## 9. D1実装結果（2026-10-15追補）

PR #130のDraftブランチに `scripts/reporting/shadow_worker.py`、`tests/test_shadow_worker_offline.py`、`scripts/reporting/shadow_hash_golden.py`、`scripts/test_shadow_hash_golden.js`、`.github/workflows/shadow-worker-d1-offline-ci.yml` を追加した。実APIクライアント、外部保存先、scheduler、Docs/Sheets/GitHub/Pagesのwriterや資格情報は含めない。

検証：`D1 Offline Market Report Shadow Worker` run **38607844317** / job **116003214257** SUCCESS。15件のPython unit testsがPASS。凍結snapshot、source/asOf/cutoff、タイトル・SOP見出し、観測値参照、refusal/未完了/timeout、private readbackハッシュ、同一attempt、別runによる二重slot、同revision異本文の隔離、下流writeなしを確認した。関連既存Actionsも同headで8/8 SUCCESS。

**互換性の停止条件を維持**：Python/GAS golden vectorsは2ケースが完全一致し、`100.0`、`-0.0`、`1e-7`に相当する3ケースでcanonicalization差分を検知した。テストのSUCCESSは「相違を検出し、署名の本番転用を防止できる」ことを意味し、ハッシュ互換が解消された証明ではない。既存snapshot_idとproducer proofの自動変換・再署名は行わない。

D1の到達範囲は固定fixtureとin-memory storeの契約。外部の永続ストレージに対する原子的な重複防止、実市場adapterの網羅（特に08時追加必須データ）、全文中の**あらゆる**数値を結び付ける意味検証、正式なResponses API strict schema/usage制御、Python/GAS完全ハッシュ互換、実API実行は未達であり、D2の受入には使えない。ChatGPT定期タスクと本番公開を変更せずPR #130はDraft維持。


## 10. Python／Apps Script共通canonical JSON v2（2026-10-15実装追補）

**状態：OFFLINE_VERIFIED／本番接続は未承認。** D1の既存GAS `marketReportProofCanonical_` およびPython `snapshot.digest` はv1のまま変更していない。バージョン付きの新規証拠用実装としてPython `scripts/reporting/canonical_v2.py` とGAS `marketReportProofCanonicalV2_`／`marketReportProofVerifyV2EvidenceDigests_` を追加した。呼出し元のv1本番公開ゲートへの切替は行っていない。

v2識別子：`report-canonical-json/v2`。JSON object keyはASCII識別子とし、辞書キーを昇順ソート、UTF-8でエンコード、配列順は保持、null/bool/安全な整数を許容、孤立サロゲート・NaN/無限大・unsafe integerを拒否する。Python floatはJSON数値に直接せず、`{"decimal_v2":"100.0"}`、`{"decimal_v2":"-0.0"}`、`{"decimal_v2":"1e-07"}` のような型付き表記で固定し、GAS側は金融数値のuntagged表現を拒否する。小数文字列は最初にPython producerが決めて記録し、JavaScriptで再構成・丸めをしない。

既存 `snapshot_id=snapshot-<v1 digest>` は**原型のまま保持**し、新規証拠は別フィールド `snapshot_digest_v2` と `context_digest_v2` に独立SHA-256を追加する。GASはv2の型付きsnapshot／contextの内容と新しいdigestを照合し、Python v1 snapshot_idをGAS側で作り直さない。v1 IDの原本検証はproducer側の既存 `MarketDataSnapshot` で実施する。v2検証が正しくてもissuerの真正性やChatGPT task原文取得の欠落を自動解決しない。

ゴールデンfixture：`scripts/reporting/canonical_v2_golden.py`・`scripts/test_canonical_v2_golden.js`。日本語・絵文字・改行・null・100.0・-0.0・1e-7・日時offsetを含む5ベクトルのcanonical UTF-8文字列、SHA-256、テスト専用HMAC一致を確認し、snapshot/context v2 digestとlegacy snapshot ID維持を検証。不正版／改ざん／untagged金融数値／異常小数文字列を拒否。`tests/test_canonical_v2.py` は型・unsafe値・配列順序・旧snapshot ID維持を確認。

関連GitHub Actions（初期コードHEAD `84c1a264feb8bbce2b0745199093736ea357e696`）8/8 SUCCESS、うち D1 offline run `38609373349` SUCCESS。これはv2形式の**オフライン相互運用性検査**であり、本番署名に使用できる証明ではない。独立issuer・private store・API key・API workerの実レスポンス取得は引き続き未実装。

## 11. D2移行前の具体的チェック項目（未承認）

- モデルと計測上限：初回1 slot、モデルIDの固定、入力／出力最大tokens、上限超過時の送信停止、timeout時のUNKNOWN照合手順、API responsesの保存形式と実費集計。
- API資源：専用OpenAI API project/keyと権限、secret managerによる注入、費用上限（月額および1run）、再試行なしの初期設定。APIキーはGitHub・Google Docsに書かない。
- private store：保存先候補はGCP Cloud Storage（保持／Object Versioning・IAM制御）等。暗号化・署名担当とpublisherの権限分離、オブジェクト単位の作成専用条件、保持期間、監査ログ、読戻しの方法を比較。候補であって選定完了ではない。
- 実データ：08:00など時刻別必須市場観測、source/asOfの確認、法的・利用規約上の利用権、ニュースと全数値の意味検証方法を事前検証。
- 監視：SHADOW_NOT_ELIGIBLEを維持し、Docs/Sheets/GitHub/Pages/publisherの資格情報ゼロ、外部writerコールゼロ、API費用・status・usage・hashを記録。
- 合格後であってもD2は手動・単一slotの**有料API実行を別承認**とし、公開／旧ChatGPTタスク停止／PR本番統合は別判断とする。


## 12. Responses API実接続前のoffline境界（2026-10-15実装追補）

2026-10-15、OpenAI公式の[GPT-5.4 Miniモデル情報](https://developers.openai.com/api/docs/models/gpt-5.4-mini)から**固定スナップショットID `gpt-5.4-mini-2026-03-17`**、標準テキストtoken単価（入力 $0.75 / 1M、出力 $4.50 / 1M）を確認した。これは候補モデルであり、利用者のAPI projectでの利用権限・課金設定確認は未実施。従前の `gpt-5.4-mini-2026-10-01` は実在を確認していない仮fixtureだったため、D2 fixtureでは確認済みsnapshot IDへ変更した。

`scripts/reporting/d2_responses_contract.py`にネットワーク通信を持たないResponses request/response契約を実装。既存のimmutable context/snapshotと確認済みmarket sourceを読み取り、`tools=[]`、`tool_choice=none`、`store=false`、`text.format={type:json_schema, strict:true}`、`max_output_tokens<=4000`のリクエストを構築する。プロバイダー応答の `id`、`status=completed`、`model`、`usage`、`output[type=message].content[type=output_text]`から生JSON文字列と本文を抽出。複数message/tool call、refusal/incomplete、ID/model不一致、不正usage、重複JSONキー、非有限値、誤report_id、凍結データにない観測値をfail-closedに拒否。正式API response IDを自己生成するコードはない。

`tests/test_d2_responses_contract.py`の8件はオフラインの合成provider応答のみで実行。公式APIの[Create a model response](https://developers.openai.com/api/reference/resources/responses/methods/create)および[Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs)に基づくshapeでテストする。出力の事実性を全数値について証明したわけではなく、プロバイダー応答の構造上の整合と既存D1検証に限る。

新モジュールにはOpenAI SDK・HTTP client・実API key・クラウド保存・Scheduler・Docs／GitHub publisherは存在しない。実APIの送信を可能にする実行器は追加しておらず、D2`d2_preflight.py`の`api_send_allowed=false`を維持。API project/key、秘密のprivate store、データソース利用権、費用上限・実送信の明示承認が揃う前に有料APIを実行しない。

## 2026-10-15 D2 raw provider response hash の意味修正（Draft）
APIレスポンスをdictから`json_bytes(raw)`で再シリアライズしたdigestは「raw HTTP response bytes」のdigestではなかった。D2 offline contractで2者を区別し、`normalized_response_sha256`は正規化JSONのdigest、`raw_response_sha256`は元のUTF-8 byte列が提供され、dictと内容照合できた場合のみ存在するよう変更。内容相違、JSON重複キー、不正UTF-8、非有限値をrejectし、空白差によるraw digest差と正規化digest一致をfixtureで確認する。これは受信バイト完全性の基礎であり、API由来の証明、独立private readback、本番署名・公開許可ではない。

## 2026-10-15 D2 offline evidence store試作（実API・本番デプロイなし）
`LocalPrivateEvidenceStore`はD1 MemoryEvidenceStoreの代替本番基盤ではなく、POSIX staging上でprivate evidenceの保存・再起動後readbackの基本条件を検証するもの。明示root、worktree外、ディレクトリ0700、ファイル0600、O_EXCL、O_NOFOLLOW、fsync、SHA-256、同一ID保存拒否、所有者／hardlink検査を実装した。`tests/test_d2_private_store.py`をCIへ接続し、tamper・unsafe path/mode・symlink・duplicate・receipt不一致をfail-closed確認する。暗号化・IAM・retention・cross-host mutex・実API原本受信・独立staging cloud readbackは別工程で、これらが未実証なら本番公開不可。
