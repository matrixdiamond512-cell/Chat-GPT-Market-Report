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

## 2026-10-15 生成元証拠v2の要件追補（v1.12 / Draft）

- D1の非公開API-shadow用source証拠は、旧Python v1 snapshot IDを変更せず、別の`report-canonical-json/v2`形式で追加digestを保持すること。旧証拠や既存レポートを自動再署名しない。
- float値はJSON数値としての情報喪失を避けるため、生成元で型付きdecimal_v2文字列へ変換し、Python/GASでcanonical bytesおよびSHA-256一致を確認する。原文・market dataの真正性と署名権限は別途検証する。
- D1成功はE4相当のoff-line契約検証のみ。API費用、非公開永続保存先、issuer鍵、D2実運用は未承認。既存ChatGPTタスクは稼働継続、PR #130 Draft、本番レポート公開はBLOCKEDのまま。
- 変更実装：PR #130の`scripts/reporting/canonical_v2.py`、`apps-script/MarketReportProducerProof.gs`のv2 helper、およびgoldenテスト。変更仕様書のv2追補と対応づける。

## 2026-10-15 D2事前判定要件追補（Draft）
有料API実行の前に、固定モデル版・1slot/1attempt・入力/出力token上限・USD費用上限・private immutable store・readback・データ利用権・実承認の独立証拠が必須。文書内の宣言だけを実承認と見なさず、未確認ならAPI送信／公開とも禁止する。PR #130に`d2_preflight.py`とオフラインテストを追加した。ChatGPT既存タスク稼働・本番公開停止・PR Draft未マージは不変。


## 2026-10-15 D2 Responses API受信契約（Draft）
OpenAI API worker実行前のオフライン契約として固定モデルsnapshot、凍結market context/snapshot、出力strict JSON schema、toolsなし、応答ID/status/model/usage検証、原文/raw応答SHA記録を必須とする。公式資料で確認した候補IDは`gpt-5.4-mini-2026-03-17`。ただし利用プロジェクトへのアクセス、真のAPI応答は未確認。検証用モデル応答からChatGPT定期タスクの原文を推定してはならない。D2実課金・private store・publisherは未実装であり、公開停止・PR Draftは維持。

## 2026-10-15 D2原本バイト完全性要件（Draft／追補）
- API受信の証拠は「元の受信JSONバイト列のSHA-256」と「パース済みJSONを再正規化したSHA-256」を混同しない。前者は元バイト列が取得・照合できた場合にのみ記録し、ない場合はnullとして扱う。
- 非公開保存する原本のbytes、応答ID、usage、hash、保存先オブジェクトバージョン、独立readbackを一緒に照合する。ハッシュ単独はOpenAIからの真正な応答であることの証明ではない。
- D2手動shadow実API試験を承認する条件、本番producer署名、E5公開ゲートは従来どおり未成立。PR #130はDraft・本番公開停止を維持する。

## 2026-10-15 D2非公開永続証拠のオフライン試験要件（Draft）
- D1の試験用メモリストアに加え、D2では再起動をまたぐbyte-exact読み戻し・保存時の不変性・改ざん拒否・安全なroot/path/権限検査を試験する。ただし同実装はローカルPOSIXのstaging試作で、クラウドprivate store／暗号化／独立運用主体／分散排他は未提供。
- GitHub公開ワークツリーへの証拠保存は禁止。原本bytesのSHAと保存読戻しを突合し、同object IDへの重複保存やパス横断・シンボリックリンク・危険なアクセス権限を拒否する。
- 実API呼び出しとpublishの許可判定は変更しない。D2有料試験は別途承認、実本番配信はBLOCKEDを維持。

## 2026-10-15 D2数値・出典照合ゲート要件（Draft）
- API shadow応答で、本文の価格等の数字をモデル自身の出典申告だけで承認しない。取得済みのReportContext／MarketDataSnapshotを再検証し、検証済みソースID・登録URL・観測時刻・cutoff・market type・数量単位・値（priceValue/changeValue/changePct）に結び付ける。
- Responses出力JSONは従来のshadow-responses-json/v1から検証用v2へ拡張し、`numeric_claims`（文字位置、原文、系列、フィールド、出典ID、観測時刻）を必須とする。タイトル行と登録銘柄識別子内の数字のみ限定的にメタデータ扱いとし、その他の数値記載は全出現箇所の照合が必要。
- 対応する証拠がないニュース・金利・PER/EPS・移動平均・イベントの数値等は、推測・モデル申告で穴埋めせずBLOCKED。v1は字句・参照照合であり自然言語の意味的整合性や取得元の真正性・許諾を保証しない。
- D2実API試験、本番発行者署名、Docs/Pages公開、既存タスク変更は未許可。

## 2026-10-15 正本一本化・文書統制要件
要件定義書・正式仕様書・運用マニュアルの3種は役割別に維持するが、**システムの技術仕様として有効な正本は `docs/system/specification.md`（Google Docs正式仕様書と同期）1本だけ**。旧「変更仕様書」は2026-10-15に統合・更新停止してアーカイブ扱いとし、別の実装基準として使用しない。新たな仕様変更は統合仕様書の該当章と単一の改訂履歴へ反映し、要件/運用への必要な差分だけを同一版で反映する。旧PR・履歴は証拠として残すが現在の仕様との矛盾時に優先しない。PR #130 Draft、main未マージ・本番公開停止は不変。

## 2026-10-15 技術仕様の単一正本管理
マーケットレポート配信システムの有効な技術仕様は `docs/system/specification.md` と同内容の正式Google Docs仕様書に一本化する。旧変更仕様書は統合済みの履歴で、独立の実装基準ではない。今後の変更内容は正式仕様書の該当章に統合し、要件定義書には要件、運用マニュアルには運用・検証手順のみ同期する。3種の文書は役割別に残すが、技術契約の正本を複数作らない。2026-10-15の統合はPR #130のmainマージ、API課金・本番公開の承認ではない。

## 2026-10-15 D2一連試験の受入要件（v1.14）
D2の個別構成部品を接続したオフライン通し試験を必須とする。固定ReportContextとMarketDataSnapshotから要求を生成し、呼出し前のslot占有証拠、原本bytes保全と独立readback、本文・数値と出典照合、費用cap、fail-closed、timeout UNKNOWN後の再試行禁止、結果receiptの一致を検査する。実API・外部書込を必要としない合成fixture試験はE4用でありE5ではない。既存タスク・main・本番公開を変更せず、実API実行の独立承認を要する。正式仕様は統合仕様書v1.14が唯一の技術上の正本。

## 2026-10-15 D2中断証拠の再照合要件（v1.15）
D2オフラインstagingにおいて、slot claim／raw bytes／結果receiptを再起動後に読み取り専用で照合する機能を要求する。claimだけ・rawだけ・タイムアウト・不正ファイル・不一致・ローカル整合を判別し、**すべての状態で自動再送、API送信、本番公開を不許可**とする。独立した受信真正性、外部IAM/retention、provider実行有無、原本署名がない場合は、ローカルhashを検証済み本番証拠へ昇格させない。技術契約は正式仕様書v1.15だけを正本とする。

## 2026-10-15 D2費用事前停止・契約一致の要件（v1.16）
専用API shadowの本番前準備には、外部送信前の入力・出力token計画capと固定モデル料金に基づく費用上限照合が必要。計画超過時はclaimと応答関数を開始せず、応答の申告usage超過も停止する。モデル・schema・料金を申告者がすり替えて事前審査を通過できないよう、D2 Responses実契約とpreflightを同一にする。計画上限はAPIの実測上限・課金保証ではなく、独立料金確認、token計測、月間費用台帳、利用承認と権限分離は未実施の外部必須条件。規範は統合正式仕様書v1.16に集約。
