# WEBマーケットレポート現行仕様書

版: 2026-08-12

## 1. 共通データ契約

### 1.1 状態

| 状態 | 意味 | 採点 |
| --- | --- | --- |
| `verified` | 取得元と値を確認済み | 可 |
| `calculated` | 確認済み入力から算出した代理値 | 可。ただし実測値と明確に区別 |
| `stale` | 直前の正常値を保持しているが期限切れ | 不可 |
| `degraded` | 一部条件を満たさない参考値 | 原則不可 |
| `unavailable` | 取得または検証不能 | 不可 |

`null` と `0` は区別する。非確認値を `0` に変換しない。

### 1.2 基準日

全ての値は可能な限り `asOf`、`updatedAt`、`sourceName`、`sourceUrl`、`frequency` を持つ。頻度や基準日が異なるデータは同一時点のフローとして断定しない。

## 2. USD/JPY実需・投機フロー

### 2.1 生成処理

- 生成スクリプト: `scripts/build_usdjpy_flow_summary.py`
- 出力: `data/usdjpy-flow-summary.json`
- 表示: `assets/js/usdjpy-flow-summary.js`
- 更新ワークフロー: `.github/workflows/update-usdjpy-supply-demand.yml`
- PDF解析依存: `pypdf==6.1.1`

### 2.2 公式データ取得

貿易統計は税関の報道発表一覧から最新の月次確速PDFを探索し、輸出、輸入、収支を抽出する。収支は `輸出 - 輸入` で再計算し、PDFの表示値と検算する。

証券投資は財務省の `week.pdf` から最新週の対外・対内合計を抽出する。正は取得超、負は処分超である。

取得失敗時は `officialFlows` に保存した直前値を再利用し、各ドライバーを `stale`、スコアを `null` とする。エラーは `diagnostics.officialFlowFetchError` に保存する。

### 2.3 スコア

- スコア範囲: -5から+5
- 正: USD買い・JPY売り方向
- 負: USD売り・JPY買い方向
- 実需はカレンダー以外の利用可能項目が3件以上必要
- 投機は利用可能項目が2件以上必要
- CFTCは基準日から7日以内だけ利用

代理値は名称に `代理` を含め、説明文に限界を記載する。

## 3. 重要イベント終了記録

### 3.1 生成処理

- 入力: `data/events/completed.json`
- 生成スクリプト: `scripts/build_completed_event_records.py`
- 出力: `data/events/completed-records.json`
- 表示: `events.html`
- 更新: `.github/workflows/update-economic-calendar.yml`、5分間隔

### 3.2 保存スキーマ

各レコードは次を持つ。

```text
event_id
release_datetime_jst
country
event_name
importance
previous
forecast
actual
surprise
result_judgement
initial_market_reaction
market_reaction_conclusion
reaction_type
details
related_markets
source.name
source.url
updated_at
```

対象は `status=released` かつ重要度2以上で、実績が確認できたイベント。並び順は `release_datetime_jst` の降順。

### 3.3 数値検証

- 数値形式と単位を解析し、結果と予想の単位が一致した場合だけ `結果 - 予想` を計算する。
- `%` の差は `pt` として保存する。
- 単位不一致またはパーセント値の明白な尺度不一致は、`actual=取得不能`、`surprise=取得不能`、`result_judgement=判定不能` とする。
- 値が存在しないイベントは記録対象外。
- 定性的イベントは `resultType=qualitative` の場合だけ定性的結果を許可する。

### 3.4 市場反応

市場反応は入力イベントの `marketReactionRecord` だけを確認済み記録として採用する。

```json
{
  "marketReactionRecord": {
    "initial": "ドル高・米金利上昇・株安",
    "conclusion": "初動後は一部巻き戻した。",
    "type": "一部巻き戻し"
  }
}
```

この値がない場合は、初動と結論を `反応確認困難`、反応タイプを `未判定` とする。`resultComparison`、発表前シナリオ、価格の理論方向から市場反応を生成してはならない。

### 3.5 非対応機能

次は保存、生成、表示しない。

- 発表前5分、発表直前、5分後、30分後、1時間後の価格
- 1時間変化
- イベント単位の複数市場分足取得
- 空の分足市場反応表
- 架空価格または理論反応による補完

### 3.6 UI

- 白背景
- PCは横長表
- モバイルも表形式を維持し、横スクロール対応
- 初期期間は過去7日
- 今日、過去7日、過去30日の切替
- 詳細行はボタンで展開し、文章を省略しない

## 4. ゴールドETFフロー

- GLDとIAUは個別に基準日と更新日時を保存する。
- `historyDaily` は両ETFの基準日が一致する行だけで構成する。
- 日次合計と累積グラフは `historyDaily` を使用する。
- 同一基準日の履歴が不足する場合、GLD単独履歴を暫定表示できるが、合算値として表示しない。
- 世界金ETFはWGCの週次・月次値として別枠管理する。
- 更新失敗時は過去の検証済み履歴を破棄しない。

## 5. 日経225オプション・建玉

- オプション分析は権利行使価格別Call/Put建玉、建玉増減、Put/Call、IV、SQまでの営業日を入力とする。
- 分析結果は方向予想ではなく、ヘッジ圧力が変化しやすい価格帯として表示する。
- 建玉残高と新規建玉増減を区別する。
- データ基準日が異なる場合はその旨を表示し、同日比較として扱わない。
- 限月切替時は参加者別建玉の単純差分を停止する。

## 6. テストと公開条件

変更時は少なくとも次を確認する。

1. Python構文検査。
2. 対象パーサーの固定サンプルテスト。
3. 既存の経済カレンダーまたは需給テスト。
4. 生成JSONの構文検査。
5. 非確認項目にスコアが入っていないこと。
6. 公開JSONの `pageId`、件数、最新基準日。
7. GitHub Actionsの更新処理とPages配信が成功していること。

## 7. 変更履歴

### 2026-08-12

- USD/JPYの実需・投機フロー総合判定を追加。
- オーダー、ストップ、オプション・NYカットの分析結果を投機フローへ統合。
- CFTC期限切れ除外を追加。
- 東京市場出来高の日銀PDF取得を修正。
- 貿易統計、対外・対内証券投資の公式取得を接続。
- 公開実額のない仲値、企業・資本フロー、金利反応を代理指標として明示。
- ゴールドETFフロー履歴グラフと同一基準日合算を復旧。
- 日経225のオプション需給分析、建玉分析、同一基準日比較を整備。
- 重要イベントの終了イベント記録表を追加し、分足市場反応表を廃止。
