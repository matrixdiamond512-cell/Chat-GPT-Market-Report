# 08:00 発行時の原本・市場データ固定（Draft手順）

この手順はPR #97の**発行時証拠の読戻しからローカルDRAFT描画までの接続**を説明します。上流の市場データ証拠固定と保存済みDocs取込は既存GitHub Actionsが行います。PR #97のstaging bridgeはそのcanonical出力を受け取り、同一identity/evidence/Docs receipt/summary/specを検証してからローカルHTML/SVG描画へ渡します。Drive書込・ポータル公開は行いません。

## 入力元

- `context.json`：発行対象ID、revision、基準時刻を固定した `ReportContext.to_dict()` の原本
- `snapshot.json`：**その発行工程で取得・検証された** `MarketDataSnapshot.to_dict()` の原本。過去の価格表示やGoogle Docs本文から推測・再生成しない
- `body.txt`：チャット・Google Docsへ渡す前の同一版の全文原本。第一行は指定タイトルと完全一致
- タイトル：`マーケットレポート｜YYYY/MM/DD HH:MM` 等、その原本の第一行と同一の文字列

## 固定（08:00のみ）

```bash
PYTHONPATH=scripts python scripts/capture_morning_creation_evidence.py \
  --context context.json \
  --snapshot snapshot.json \
  --body body.txt \
  --title 'マーケットレポート｜2026/10/13 08:00' \
  --output report-g2.json
```

同じ発行実行で得た検証済み取得データを使う場合は、`--snapshot snapshot.json` の代わりに `--acquisition acquisition.json` を指定する。両方の同時指定は禁止。取得データの `generatedAt`、`reportDate`、`reportSlot` を対象contextと照合してからsnapshotを固定する。取得結果が別日のものや検証できない値なら公開可能な証拠とは扱わない。

G0/G1/G2全通過の場合だけ `report-g2.json` を排他的に作成する。戻り値 `G2_DRAFT_NOT_SAVED` は**保存成功でも公開成功でもない**。不一致、原本欠損、既存の出力先、規定外の市場データは停止し、出力を作成しない。

`report-g2.json` には `fullText`、`bodyHash`、`context`、`snapshot`、`report_id`、`revision`、`snapshot_id` と `validated_gates` が揃う。図解の表示原稿 `view` は別途原文に結び付けて作成し、preflightと既存のcanonical spec検証を通す必要がある。

正式な図解接続では、これらの識別子に加えて対象slotの `cutoff`、取得元、検証済みspecを同じrun transactionから照合する。図解を作る前に `main_scenario`・`alternative_scenario`・`invalidation_trigger` をそれぞれ1件必須とし、各役の `condition`・`development`・`market_impact` に別々の完全一致本文位置参照を付ける。`invalidation_trigger.condition` は判断変更を起こす具体的トリガーでなければならず、一般的リスク列挙では代用できない。引用範囲外の数値・単位・時刻・方向があれば停止する。人間の意味照合は自動検査と分離し、完了前はPENDINGを維持する。

ChatGPT・Google Docs・GitHubの本文は同じ `fullText` / `bodyHash` を使い、後段のdashboard同期は正本本文を再生成しない。market snapshotは発行本文と別のfeed領域に保持し、異なるslotや時点のmarket dataをcanonical report objectへ混在させない。readbackで本文、hash、identity、snapshot envelopeのいずれかが異なれば、生成・保存・公開を停止して差分を監査ログへ残す。

10/14 16:00の既知監査ではChatGPT→Google Docsの本文差異が最初に確認され、GitHub canonical登録は未実施だった。内部Docs writerの変換内容は不明であり、後日の `SOURCE_ARCHIVED` JSONは元の正規発行の復元ではない。正式rendererの非fixture modeは `--docs-readback` を必須にする。readback JSONには `document_id`、`document_revision_id`、同じ `report_id` と `revision`、読み戻した完全な `fullText` を入れ、rendererが本文文字列とSHA-256を比較する。欠落または不一致なら出力ディレクトリを作らずBLOCKEDにする。これはローカル入力検査であり、readbackデータを外部サービスが発行した証明は別途監査記録で確認する。

## 未実装の接続と禁止事項

- `scripts/run_morning_infographic_staging.py` は、canonical report、`data/report-evidence/` の不変証拠、`publication-receipts/` のDocs実読戻しreceipt、summary/view/spec、人間のpanel-12 reviewを入力に取るローカル接続口である。TEST_ONLY fixtureは `tests/test_morning_staging_bridge.py` のみで扱い、正式レポート入力として使わない。
- 正式コマンド例（2026-10-19は上流Actions完了後、GitHub mainを読戻したローカルcheckoutで実行する。`summary.json`、`view.json`、`spec.json`、`scenario-review.json` は当該report identityに結び付ける。シナリオ確認前に描画しない）：

```powershell
$date = '2026-10-19'
$slot = '08-00'
python scripts/run_morning_infographic_staging.py `
  --date $date `
  --report "reports/$date`_$slot.json" `
  --evidence "data/report-evidence/$date`_$slot-r1.json" `
  --receipt "publication-receipts/$date`_$slot.json" `
  --summary "review-input/$date`_$slot/summary.json" `
  --view "review-input/$date`_$slot/view.json" `
  --spec "review-input/$date`_$slot/spec.json" `
  --scenario-review "review-input/$date`_$slot/scenario-review.json" `
  --output "validation/$date`_$slot-local-draft"
```

Bridgeはreceipt発行元のDocs読み戻し結果を検証し、そのcanonical本文からローカルreadback adapterを作る。Google Docsへ新たにアクセスしたり、本文を再保存したりしたとは主張しない。検証bundleには入力evidence、receipt、report、readback、summary、view、spec、review、PNG hashと `publish_allowed=false` のvalidation manifestを保存する。入力不一致・不足時は出力ディレクトリを作らずBLOCKEDにする。

- **定時ジョブからPR rendererへの自動起動は未稼働**。このbridgeはPR #97の未マージコードであり、mainのpublisher/freeze workflowからは呼び出されない。`workflow_run`/`workflow_dispatch`定義はdefault branchに存在するworkflowが対象となるため、Draft PR内だけで10/19のActions自動起動を有効にはできない。mainマージまたはdefault branch側変更は依頼制約で禁止されているため、今回は有効化・外部Actions dispatchを行わない。
- 既存publisherはGoogle Docsを読み、receiptを発行してcanonicalへ登録するが、本文からの図解summary/view/specとpanel-12の人間による意味照合は自動作成しない。これらが同一identityで用意されない限り、10/19でもbridgeはfail-closedする。これは正式E2Eの未完了事項であり、合成テストで埋めない。
- 既に公開済みの10月9日・12日レポートに、後からsnapshotやbodyHashを捏造・埋め戻ししない
- `READY_FOR_CANONICAL_VALIDATION` はPNG正式公開の許可ではない
- Google Docs原本のDrive読み戻し一致（G3）、PNG（G4）、manifest（G5以降）が成功するまで、公開済み・保存完了と宣言しない
- 合成fixtureは本番データでも実運用の成功証拠でもない
