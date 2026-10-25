# P1 Shadow Cloud Run: 403診断と安全な再試験

対象：PR #182 の `p1-report-shadow-ingress`。2026-10-26 JST 時点で、Google Cloud側の実機ログは HTTP 403、Cloud Scheduler `slot-0800-t13` は `PAUSED`、`SHADOW_STORAGE_ENABLED=false`。この文書は原因確定を主張せず、再現可能な切り分け手順を記録する。

## 確認済みの事実と未確認事項

- Google Cloud Schedulerのサービスエージェントに `roles/cloudscheduler.serviceAgent` のプロジェクトIAM割当てがある。
- 専用Scheduler呼出元に、対象Cloud Runサービス限定で `roles/run.invoker` を割り当て済み。
- Cloud Runログに POST/403 があるが、従来のアプリケーションは拒否理由をCloud Loggingへ書かなかった。
- Gunicorn 26.2.0は従来 `/.gunicorn` 作成時のPermission deniedを出した。Cloud Run環境変数 `GUNICORN_CMD_ARGS=--no-control-socket` で修正後は、新リビジョンの確認ログに同エラーが見えなかった。しかしHTTP 403は継続した。
- 上記だけでは、Google Cloud Run IAM入口の403とアプリ側の403を区別できない。

## 実装した診断

`scripts/report_continuity_ingress.py` のすべてのアプリ応答に、1行のJSON形式 `P1_INGRESS_RESULT` をstderrへ出す（Cloud Run Loggingで参照）。キーは `event`、`severity`、`httpStatus`、`reason` のみ。JWT、Bearer値、メール、ジョブ名、Schedulerヘッダー、取得データ、処理本文、例外本文は一切記録しない。

403では固定コード `JOB_NOT_ALLOWLISTED` または `CALLER_NOT_AUTHORIZED` が現れる。Cloud RunのIAM層で拒否され、WSGIアプリまで到達しなかった場合にはこのアプリログは出ない。ただしログ未出力だけでは断定せず、時刻・リビジョン・ログ伝播も照合する。

`Dockerfile` で `GUNICORN_CMD_ARGS=--no-control-socket` を設定し、非rootコンテナがルート直下へソケットを作ろうとする問題を恒久的に回避する。

## 安全な検証順序

1. PRのCIが通ること。Dockerのローカル起動ログで制御ソケットのエラーがないことを確認する。
2. **別途明示された実機デプロイ手順と承認により**固定SHAからコンテナをビルド・配備する。既存の `SHADOW_STORAGE_ENABLED=false`、Cloud Run認証必須、専用Invoker権限、Schedulerの `PAUSED` を維持する。
3. 新リビジョンの配置を確認後に、別途承認された単発Scheduler試験をする。停止状態を最終確認するまでは後続を進めない。
4. Cloud Loggingのリクエストログ（`run.googleapis.com/requests`）と、アプリログ（`jsonPayload.event="P1_INGRESS_RESULT"`）を同一時刻・同一リビジョンで対照する。
5. アプリログの `reason` が `JOB_NOT_ALLOWLISTED` ならヘッダーの受け渡し・許可リスト整合性、`CALLER_NOT_AUTHORIZED` ならOIDCクレーム照合を調査。アプリログが無ければIAM入口側・ログ遅延・リビジョンを精査する。
6. 過去/臨時の手動Scheduler実行は本来の07:47 JSTのスケジュールではない。`400 SCHEDULE_NOT_ALLOWED` または `409 SCHEDULE_EXPIRED` は認証に成功した可能性を示すが、正常な08:00枠の200成功とは区別する。

診断ログ検索例（デプロイ後、参照のみ）：

```bash
gcloud logging read \
  'resource.type="cloud_run_revision" AND resource.labels.service_name="p1-report-shadow-ingress" AND jsonPayload.event="P1_INGRESS_RESULT"' \
  --project=market-report-p1-shadow --freshness=1h --limit=20 \
  --format='table(timestamp,resource.labels.revision_name,jsonPayload.httpStatus,jsonPayload.reason)'
```

## 安全条件

- ジョブを不用意に `ENABLED` にしない。既存 `PAUSED` を維持。
- `SHADOW_STORAGE_ENABLED` を `true` に変更しない。
- `allUsers`、`allAuthenticatedUsers` にInvokerを付与しない。
- IDトークン、アクセス権、秘密鍵、本人情報をデバッグ出力しない。
- まだ認証成功、HTTP200、GCS書込みの成功を宣言しない。
