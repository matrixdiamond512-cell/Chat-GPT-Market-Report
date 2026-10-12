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

G0/G1/G2全通過の場合だけ `report-g2.json` を排他的に作成する。戻り値 `G2_DRAFT_NOT_SAVED` は**保存成功でも公開成功でもない**。不一致、原本欠損、既存の出力先、規定外の市場データは停止し、出力を作成しない。

`report-g2.json` には `fullText`、`bodyHash`、`context`、`snapshot`、`report_id`、`revision`、`snapshot_id` と `validated_gates` が揃う。図解の表示原稿 `view` は別途原文に結び付けて作成し、preflightと既存のcanonical spec検証を通す必要がある。

## 未実装の接続と禁止事項

- 08時の定時発行ジョブによる自動呼び出しは未実装。スケジューラが持つ既存の実際の取得結果と原本文を、同じ実行IDに結び付ける必要がある
- 既に公開済みの10月9日・12日レポートに、後からsnapshotやbodyHashを捏造・埋め戻ししない
- `READY_FOR_CANONICAL_VALIDATION` はPNG正式公開の許可ではない
- Google Docs原本のDrive読み戻し一致（G3）、PNG（G4）、manifest（G5以降）が成功するまで、公開済み・保存完了と宣言しない
- 合成fixtureは本番データでも実運用の成功証拠でもない
