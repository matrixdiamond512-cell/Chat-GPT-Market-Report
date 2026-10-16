# 08:00 発行時の原本・市場データ固定（Draft手順）

この手順はPR #97の**ローカルでの発行時証拠固定**を説明するものです。既存の配信タスクへの自動接続、Google Drive保存・読み戻し、ポータル公開は実装・検証済みではありません。

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

- 08時の定時発行ジョブによる自動呼び出しは未実装。スケジューラが持つ既存の実際の取得結果と原本文を、同じ実行IDに結び付ける必要がある
- 既に公開済みの10月9日・12日レポートに、後からsnapshotやbodyHashを捏造・埋め戻ししない
- `READY_FOR_CANONICAL_VALIDATION` はPNG正式公開の許可ではない
- Google Docs原本のDrive読み戻し一致（G3）、PNG（G4）、manifest（G5以降）が成功するまで、公開済み・保存完了と宣言しない
- 合成fixtureは本番データでも実運用の成功証拠でもない
