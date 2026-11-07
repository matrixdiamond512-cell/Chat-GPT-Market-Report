# 終値一覧の系列定義契約

作成日: 2026-10-12  
適用先: PR #94 の既存「終値一覧」列への個人用保存経路  
状態: 確定した列定義と未確定の旧セル来歴を分離して管理する

## 不変条件

- 既存列、行、数式、表示形式、条件付き書式を変えない。自動処理は既存セルへ無条件に上書きしない。
- 比較キーは数値だけではない。少なくとも対象日、source ID、source series ID、観測定義、締め時刻、単位を保持する。
- 系列や締め時刻が不明な値は同値と認定しない。表示精度による丸め一致は、同じ系列・定義・日付が確認できる場合だけ記録する。
- この契約は既存列を維持するための保存規則であり、異なる系列を既存列へ追加する許可ではない。

## 日経225評価指標

### 予想PER列・予想PBR列

既存「日経225予想PER」「日経225予想PBR」列は、**加重平均系列**を継続する。日経公式の2026-10-09履歴には加重平均 PER 17.37 / PBR 1.90 と指数ベース PER 22.87 / PBR 2.83 が別系列として掲載され、公式ガイドも計算定義を区別している。

- 加重平均PER: 構成銘柄の時価総額合計 ÷ 予想利益合計。
- 指数ベースPER: 日経平均 ÷ 指数ベースEPS。
- 加重平均PBRと指数ベースPBRもそれぞれ集計加重値と指数÷BPSの系列であり、相互に置換しない。
- 既存列への自動保存は、market record に `valuationBasis=weighted_average` と `sourceSeriesId` が明示され、同じ対象日の値として検証されたPER/PBRだけ許可する。
- `index_based`、未指定、その他のbasisは既存PER/PBR列へ保存しない。レポートでは別basisとして保持できるが、既存列に混ぜない。

### 予想EPS列

既存値 3,974.15 の生産列側の取得系列・未丸めPERとの関係・算出式は未確定。指数ベースEPS候補 3,018.4049 は同日の公式指数終値 ÷ 指数ベースPERから得た値であり、既存値を説明する証拠ではない。従って既存EPS列の自動書き込みは定義確定まで無効にする。既存値・履歴は保持し、公式指数ベースEPSは別定義の値として扱う。

## 為替列

### USD/JPY

既存セルの記録にはYahoo Finance日足fallbackと2026-10-09 07:28 JSTの取得時刻が残るが、その日足の締め時刻・内部系列は特定できていない。Tokyo 17:00 JSTの日本銀行公表bid/ask midpointと表示精度上整合することは、旧値がその系列から取得された証明ではない。TradingView候補は17:00 New Yorkの日次境界であり、東京17時値と同一系列ではない。

### EUR/USD

既存セル 1.1202 は系列IDと観測時刻が残っておらず、来歴不明として扱う。比較候補にはECB参照レート（欧州日中の固定時刻）とTradingViewの17:00 New York日次境界があり、異なる観測系列である。値の近さで旧セルの由来を推定しない。

### 為替共通の保存規則

新規FX recordは `sourceSeriesId`、`observationDefinition`、`sessionCloseAt`、単位、公開精度を明示する。市場ごとの値を勝手に東京17時またはNY17時へ変換せず、同じ系列・締め時刻を継続使用する。既存の非空欄セルは、保存ログに同じ定義のCONFIRMED lineageがあるときだけ完全一致として維持できる。来歴欠如、系列差、締め時刻差、値差はCONFLICTとし、行書き込み前に停止する。

## 米10年債利回り列

候補として確認した米財務省系列は Daily Treasury Par Yield Curve の10-year constant-maturity par yield (`daily_treasury_yield_curve:BC_10YEAR`)、単位は%、公表精度は小数2桁、観測基準時刻は米東部時間15:30のpar-curve観測として記録する。この系列の2026-10-09公表値は5.24%。一方、既存値5.242の保存元・公表系列は確定しておらず、二次サイトのmarket-yield close 5.243に近いことからTreasury CMTと同一とは扱わない。

- 新規セルへの候補記録は、source ID、series ID、観測定義、15:30 America/New_York cutoff、%、公表精度2桁、対象日をすべて残す。
- 非空欄セルとの完全一致・丸め一致は、保存ログに対象日と上記の同じ系列metadataがCONFIRMEDで記録される場合だけ許可する。
- 丸め一致は両データの公表小数桁を使う。同系列確認の代わりに固定許容誤差を使わない。
- 旧値5.242は来歴が確認できるまで保持し、新規5.24で上書きしない。

## 実装上の状態コード

- `EXACT_MATCH`: 数値と確認済みの定義・系列・対象日がすべて一致。既存精度を保持。
- `PRECISION_MATCH`: 系列・定義・対象日が同一で、双方の公表小数桁に丸めた値が一致。既存精度を保持。
- `DEFINITION_MISMATCH`: valuation basis等が既存列の定義と異なる。
- `DEFINITION_PENDING`: 必須のseries ID、観測定義、締め時刻などが欠ける。
- `CONFLICT`: 日付、系列、締め時刻、単位、精度または値が同一性確認条件を満たさない。

「終値一覧」の列構造は変更しない。新しい確定市場日データを受け取ったら、書き込み前にこれらの規則でdry-runし、対象セルと差分が安全だと確認できるまで実書き込みを行わない。

## 根拠

- 日経公式PER履歴: https://indexes.nikkei.co.jp/nkave/archives/data?list=per
- 日経公式PBR履歴: https://indexes.nikkei.co.jp/nkave/archives/data?list=pbr
- 日経指数ガイド: https://indexes.nikkei.co.jp/nkave/archives/file/users_guide_jp.pdf
- Treasury公式Daily Treasury Par Yield Curve: https://home.treasury.gov/resource-center/data-chart-center/interest-rates/pages/xml
- 旧セル来歴と2026-10-09の候補照合: `docs/project-control/EVIDENCE_LEDGER.md` の「競合6件の系列・時刻比較と新規日dry-run判定」。
