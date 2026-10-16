# WEBマーケットレポート運用マニュアル

## 選択レポートの閲覧
- `index.html` で日付と時刻を一度選ぶ。6市場サマリー直後に同じスロットの本文が続けて表示される。
- 本文は別ページやiframeではなく同じDOMに表示され、日時選択は一組だけを使う。
- 公開または履歴archiveの適格性を確認できない場合は本文表示を停止する。修復履歴は正式発行原本とは区別して表示する。
- 旧ブックマークの `report.html?date=...&time=...` は同じ日時を保持して `index.html#report-detail` に移動する。


最終更新: 2026-08-12 JST

## 1. 基本方針

- 画面の数値は、基準日・更新日時・取得状態を確認して利用する。
- `取得不能` は `0` と同義ではない。空欄、推測値、架空値で補完しない。
- `算出値` は公開実額ではなく代理指標である。名称と注記を維持する。
- 更新に失敗した場合は、直前の正常値を `期限切れ` として残し、最新値として採点しない。
- 日次、週次、月次データを同一時点のデータとして扱わない。

## 2. USD/JPY需給分析

### 2.1 実需フロー

`usdjpy-supply-demand.html` の「実需 × 投機 フロー総合判定」で、次を確認する。

| 項目 | 種別 | 読み方 |
| --- | --- | --- |
| 仲値フロー（東京価格代理） | 算出値 | 日銀の日次東京市場価格の始値から終値までの変化。仲値の実額ではない |
| 東京市場出来高 | 確認済み | 日銀「外国為替市況」のUSD/JPYスポット出来高と価格方向を併用 |
| ゴトー日 | カレンダー | 該当日を表示するだけで、反応未確認なら加点しない |
| 企業・資本フロー（公表値代理） | 算出値 | 対外証券投資と対内証券投資の差。企業の当日実額ではない |
| 貿易統計 | 確認済み | 財務省貿易統計の輸出、輸入、収支。月次の構造要因 |
| 対外証券投資 | 確認済み | 財務省週次統計。取得超は外貨需要候補だが為替ヘッジは不明 |
| 対内証券投資 | 確認済み | 財務省週次統計。取得超は円需要候補だが為替ヘッジは不明 |
| 月末・期末 | カレンダー | 該当性だけを表示し、方向未確認なら加点しない |

公式取得先:

- 貿易統計: `https://www.customs.go.jp/toukei/shinbun/happyou.htm`
- 対外・対内証券投資: `https://www.mof.go.jp/policy/international_policy/reference/itn_transactions_in_securities/week.pdf`
- 東京市場出来高: `https://www.boj.or.jp/statistics/market/forex/fxdaily/fxlist/index.htm`

### 2.2 投機フロー

- CFTC円先物は基準日から7日を超えると `期限切れ` となり、スコアから除外される。
- オーダー、ストップ、オプション・NYカットは取得した水準と分析結果を表示する。
- 金利差と短期価格反応はUSD/JPYと米日2年金利変化の同時反応を示す代理値で、因果関係を断定しない。
- 実需、投機とも最低必要項目数を満たさない場合は、総合判定を保留する。

### 2.3 更新確認

GitHub Actionsの `Update USDJPY supply demand page` を確認する。正常時は以下が更新される。

- `data/usdjpy-supply-demand.json`
- `data/usdjpy-flow-summary.json`
- `data/usdjpy-supply-demand-archive/`

`data/usdjpy-flow-summary.json` の `diagnostics.officialFlowFetchError` が `null` なら、貿易統計と証券投資の取得は正常である。

## 3. 東京市場USD/JPYスポット出来高

- 正本は `data/usdjpy-volume.json`。
- 日銀PDFの対象日と公表日を区別する。
- 最新PDFだけでなく、日銀一覧に存在する未反映日を取得対象にする。
- スワップ出来高をスポット出来高として使用しない。
- 20日平均はデータがそろった場合だけ算出する。

GASを使う手動同期は [USD/JPY出来高ページ GAS同期メモ](usdjpy-volume-gas-sync.md) を参照する。

## 4. 重要イベント

### 4.1 発表前

`events.html` では、予定日時、国・地域、重要度、市場予想、前回値、確認対象市場、一般的な発表前シナリオを確認する。シナリオは理論上の目安であり、実際の市場反応ではない。

### 4.2 終了イベント記録

「終了した重要イベント｜結果・市場反応」は、重要度2以上で発表済みのイベントを新しい順に表示する。

- 初期表示: 過去7日
- 切替: 今日、過去7日、過去30日
- 基本列: 発表日時、国・地域、イベント、重要度、前回、市場予想、結果、予想差、判定、市場の初動、市場反応の結論、詳細
- `詳細を見る`: 指標情報、反応タイプ、関連市場、出所、更新日時を展開
- スマートフォン: 表形式を維持し、横スクロールで閲覧

市場反応は、確認済みの記録がある場合だけ表示する。理論的な方向から作成しない。確認できない場合は `反応確認困難` とする。

### 4.3 結果の品質管理

- 結果と市場予想の単位が一致する場合だけ予想差を算出する。
- パーセント指標は差を `pt` で表示する。
- CPIの予想が `%` なのに実績が指数水準であるなど、単位または尺度が不一致なら結果を `取得不能`、判定を `判定不能` とする。
- 実績のないイベントは終了イベント記録へ追加しない。
- 分足価格、発表前5分、直前、5分後、30分後、1時間後、1時間変化は保存・表示しない。

### 4.4 更新確認

GitHub Actionsの `Update economic calendar` は5分ごとに動作する。正常時は次を確認する。

- `data/events/latest.json`: 履歴を含む正本
- `data/events/upcoming.json`: 今後7日分
- `data/events/completed.json`: 発表済みイベント
- `data/events/completed-records.json`: 終了イベント記録表用
- `data/events/history/YYYY-MM-DD.json`: 日付別履歴

## 5. ゴールド需給

- GLDとIAUの日次合計は、両ETFの基準日が一致した日だけ使用する。
- 基準日が一致しない値を合算しない。
- 同一基準日の履歴が不足する間は、GLD履歴を暫定表示し、暫定であることを明記する。
- 世界金ETFは週次・月次であり、GLD・IAUの日次値と頻度を分けて表示する。
- 日次棒グラフと累積フローは `data/gold-etf-flow-history.json` に保存された履歴から描画する。

## 6. 日経225需給

- 先物は価格と建玉の組み合わせで、新規買い、買い戻し、新規売り、手仕舞いを判定する。
- オプション需給はCall/Put建玉集中、OI増減、IV、Put/Call、SQ残存日数を組み合わせて分析する。
- Call建玉を常に上値抵抗、Put建玉を常に下値支持とは決めない。
- 参加者別建玉と日次取引高は、同一基準日にそろえた分析と最新日次表示を混同しない。
- 限月が切り替わった場合は単純な前週差を表示しない。

## 7. 障害時の確認順序

1. 公開ページを再読み込みする。
2. カードの基準日、更新時刻、状態を確認する。
3. 対応する公開JSONを確認する。
4. GitHub Actionsの直近実行結果とログを確認する。
5. 公式取得元に最新資料が存在するか確認する。
6. 取得失敗時に直前値が保持され、`0` に変換されていないことを確認する。

手動修正値やサンプル値で公開画面を埋めない。パーサーを修正した場合は、固定サンプルのテストと実際の最新資料の両方で検証する。

## 2026-10-16 公開同期の復旧確認（PR提出前）

- `SOURCE_ARCHIVED`はDocs原本の保全状態であり、公開成功ではない。snapshot/context証跡がない、Docsが発行後に変更された、本文hashまたはrevisionが一致しない場合は公開しない。
- importer実行後はActionsログで`PUBLICATION_HELD`または公開処理結果を確認し、mainの正本・`reports.json`・`data/latest-report.json`・`data/dashboard.json`を照合する。
- receipt v2と公開データの整合ゲートが合格してからPagesへ進む。Pages deploy後に公開URLを再読込し、当該reportId・全文hashを正本と照合する。
- 2026-10-14の保存済みDocsは発行後変更または発行時本文欠落があるため、復旧テストのために再利用・補完・公開しない。
- 実定期runと公開URLのE4/E5証拠が得られるまでは`PENDING_LIVE_RUN`とし、システム復旧完了を表示しない。

## PR #97 08:00図解のDraft接続手順

1. 新規通常08:00 runのcontext、同一run acquisition/snapshot、元本文を用意する。補充版・後刻値・撤回済み本文で代用しない。
2. Google Docs保存前に `capture_morning_creation_evidence.py` でG0/G1/G2を検証し、`G2_DRAFT_NOT_SAVED` artifactを一度だけ排他的に保存する。artifact内の本文をwriterへ渡し、後から作り直さない。
3. Docs保存後、既存importerによるAPI読戻し本文、Docs revision、bodyHashを確認する。保存前artifactと本文全文・SHA-256・identity・snapshot/contextが一致しなければ停止する。receiptのsavedAtより後のcapturedAtも拒否される。
4. 同一runのcanonical report/evidence/receipt/G2本文を使い `prepare_morning_infographic_inputs.py` を実行する。summary/viewのauthoringは原文根拠を指定した人手入力が必要で、曖昧なアンカーは出典位置にマップせず停止する。
   CLIが終了コード0を返し、`summary.json`・`view.json`・`spec.json`・`input-manifest.json`の4点ができたことを確認する。manifestのcapture/save時刻とreport_id・revision・bodyHash・snapshot_idを入力receipt/G2 artifactと照合する。異常終了時に出力先が作られていないことも確認し、fixture成功を実データE2Eと混同しない。
5. 生成summary/view/specの数値・方向・時刻・条件を本文およびsnapshotに照合する。パネル12のメイン/代替/崩れる条件について成立条件・展開・市場影響を人が本文と照合し、identity・本文hash・summary hashに結びつけた別レビューを作る。未承認ならrendererを実行しない。
6. 全証拠が一致した場合だけローカルDRAFT rendererを起動し、異常系も検証する。公開manifest・Drive保存・portal公開はこのDraft接続では行わない。

このPRの変更は未マージのため定時発行から自動では起動しない。次の通常枠で実データE2Eを行う前に、default branchにTEST_ONLY staging workflowを接続する設計・承認が必要である。現状のTEST_ONLY fixture PASSは実データE2Eや本番復旧の証拠ではない。

## 選択レポートの閲覧
- `index.html` で日付と時刻を一度選ぶ。6市場サマリーの直後に、同じ選択スロットの本文と条件を満たす正式図解が続けて表示される。
- 本文欄の状態が「市場サマリーと同一本文・identityを確認」となり、表示日時が上の選択値と一致することを確認する。不一致時は本文を表示せず、欄に停止理由を示す。
- 過去の保存・修復記録には履歴archiveの注意書きが表示される。後日作成の文章や市場値を正式な発行原本として扱わない。
- 旧ブックマークの `report.html?date=...&time=...` は同じ日時を保持して `index.html#report-detail` に移動する。本文欄側に別の日時コントロールはない。
