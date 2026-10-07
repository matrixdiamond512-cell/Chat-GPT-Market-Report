# Market Report Infographic Validator / Workflow
## Codex実装仕様書 v1.0

作成日: 2026-10-07
対象:
- ChatGPT マーケットレポート
- マーケットレポート図解
- Google Drive保存
- GitHub / Market Report Portal公開

---

# 0. この仕様の目的

マーケットレポート作成・図解作成において、
AIがマニュアルを「覚えていること」や「注意すること」に依存しない。

以下を機械的に保証する仕組みを実装する。

1. 正しい時刻の本文が完成している
2. 本文のデータが検証されている
3. その時刻の本文だけから図解仕様が作られている
4. 図解仕様がマニュアルに適合している
5. 禁止要素を含む図解を生成させない
6. 生成後の画像も検査する
7. PASSした成果物だけを正式版とする
8. PASSした成果物だけGoogle Driveへ保存する
9. 本文と保存物を照合する
10. 検証済み本文だけGitHubへ登録する
11. publication receipt作成後にPortalを更新する
12. 公開ページを読み戻して確認する
13. 全工程PASSまでは「完了」と表示しない

最重要原則:

> Generate first, trust later ではなく、
> Validate → Generate → Validate → Publish とする。

---

# 1. 解決する問題

現在の運用では、詳細なマニュアルが存在していても、
生成時に以下の事故が発生する。

- 本文より先に図解を生成する
- 12:00 / 16:00 / 21:00を混ぜる
- 12:00なのに昨夜のNY時系列を入れる
- 本文に存在しない数値を図解に追加する
- 数値を別時刻の値へ置き換える
- 価格方向を間違える
- 装飾的な折れ線グラフを追加する
- ゲージを追加する
- 意味のないチャートを追加する
- 必須セクションを省略する
- 時系列の順序を変える
- 本文と図解の内容が一致しない
- 誤字、文字切れ、数値切れが発生する
- 検証前の画像をGoogle Driveへ保存する
- Google Docs検証前にGitHubへ登録する
- Portalを確認していないのに「反映済み」と表示する
- 未実行工程を「完了」と報告する

これらをプロンプト上の注意事項だけで防止しない。

Validatorによって防止する。

---

# 2. 基本アーキテクチャ

以下の固定パイプラインを実装する。

STAGE 01
Market Data Validation

        ↓ PASS

STAGE 02
Report Body Validation

        ↓ PASS

STAGE 03
Infographic Specification Builder

        ↓

STAGE 04
Infographic Pre-Generation Validator

        ↓ PASS

STAGE 05
Image Generation

        ↓

STAGE 06
Infographic Post-Generation Validator

        ↓ PASS

STAGE 07
Google Docs Save

        ↓

STAGE 08
Google Docs Readback Validation

        ↓ PASS

STAGE 09
Infographic Google Drive Save

        ↓ PASS

STAGE 10
GitHub Registration

        ↓

STAGE 11
Publication Receipt

        ↓

STAGE 12
Portal Publish

        ↓

STAGE 13
Portal Readback Validation

        ↓ PASS

STAGE 14
Final Completion Gate

各stage:

PASS
WATCH
FAIL
NOT_RUN
NOT_APPLICABLE

を持つ。

FAILが存在する場合、
後続stageへ進んではならない。

例外:
人間が明示的に
--force
を指定した場合のみ許可する。

ただし --force 使用時は
「正式版」として扱わない。

---

# 3. 対象レポート

基本時刻:

08:00
12:00
16:00
21:00

各レポートを完全に独立した成果物として扱う。

report_id:

YYYY-MM-DD_HH-MM

例:

2026-10-06_12-00
2026-10-06_16-00
2026-10-06_21-00

禁止:

12:00 + 16:00 + 21:00 を
1つの図解にまとめること。

複数時刻の本文を
同一図解のsourceに指定すること。

---

# 4. Source Lock

図解作成前に必ずsource reportをLOCKする。

例:

source_report:
  id: 2026-10-06_12-00
  title: マーケットレポート｜2026/10/06（火）12:00
  sha256: ...
  locked: true

図解作成後までsourceを変更してはならない。

sourceが変更された場合:

SOURCE_CHANGED_AFTER_LOCK

としてFAIL。

図解を再生成する。

---

# 5. Report Body Validation

本文には最低限以下が必要。

共通:

- タイトル
- 作成基準日時
- 総合判断
- 今日の相場テーマ
- 前回からの変化
- 材料と値動きの整合性
- 今日の主導市場
- 重要ニュース
- 金利
- クロスアセット資金フロー
- 需給・ポジション
- 今後のイベント
- 主要6市場の見通し
- メインシナリオ
- 代替シナリオ
- シナリオが崩れる条件
- 次時間帯への引き継ぎ
- 結論
- クロスチェック結果

主要6市場:

Gold
WTI
Nikkei 225 Futures (OSE)
USD/JPY
EUR/USD
BTCUSD

不足した場合:

MISSING_REQUIRED_REPORT_SECTION

FAIL。

---

# 6. 時刻別ルール

## 6.1 08:00

08:00はNY市場終了後の朝レポート。

必須:

- 昨夜のNY市場
- NY市場時系列
- Dow
- S&P500
- Nasdaq
- Russell 2000
- Nikkei cash
- CME Nikkei futures
- OSE Nikkei futures
- USDJPY
- EURUSD
- Gold
- WTI
- BTCUSD
- VIX
- Nikkei VI
- US 10Y
- Japan 10Y
- Fear & Greed
- Nikkei forecast EPS
- PER/PBR
- 25-day MA deviation
- 200-day MA deviation

NY時系列:

開始前
→ 開場
→ 中盤
→ 終盤
→ 東京への引き継ぎ

---

## 6.2 12:00

12:00は東京市場前場レポート。

絶対禁止:

「昨夜のNY市場の時系列」を
12:00図解の中心時系列として使用すること。

必須時系列:

08:00時点
→ 09:00寄り付き
→ 09:30前後
→ 10:00〜11:00
→ 11:30前引け
→ 12:00時点の判断

必須比較:

12:00 vs 08:00

確認対象:

- Nikkei 225
- TOPIX
- OSE Nikkei futures
- USDJPY
- EURUSD
- Gold
- WTI
- BTCUSD
- rates
- market breadth
- flows
- positioning

最後:

16:00への引き継ぎ

---

## 6.3 16:00

16:00は東京後場・大引けレポート。

必須比較:

16:00 vs 12:00

必須時系列:

12:00
→ 12:30後場寄り
→ 13:00〜14:00
→ 15:00前後
→ 大引け
→ 16:00判断

確認対象:

- Nikkei close
- TOPIX close
- OSE Nikkei futures
- market breadth
- turnover
- USDJPY
- EURUSD
- Gold
- WTI
- BTCUSD
- US yields
- Japan yields

最後:

21:00への引き継ぎ

---

## 6.4 21:00

21:00は欧州時間〜NY時間への移行レポート。

必須比較:

21:00 vs 16:00

中心:

- 欧州市場
- EURUSD
- 欧州債券
- US Treasury
- US equity futures
- OSE Nikkei night session
- USDJPY
- Gold
- WTI
- BTCUSD

最後:

次回08:00への引き継ぎ

---

# 7. Infographic Design Manual

最重要。

図解は、

「投資判断のための情報ダッシュボード」

である。

ポスターや広告ではない。

原則:

TABLE FIRST
TEXT PANEL SECOND
ARROW / ICON THIRD
CHART LAST

---

# 8. 禁止デザイン

以下を原則禁止する。

## HARD FAIL

- 装飾目的の折れ線グラフ
- 装飾目的の棒グラフ
- 装飾目的の円グラフ
- メーター
- スピードメーター型ゲージ
- 半円ゲージ
- 意味のない波形
- 架空の価格チャート
- 架空のローソク足
- 本文に存在しない時系列グラフ
- 3Dチャート
- 飾り目的の金融チャート
- 不要な人物
- 投資家の人物イラスト
- トレーダーの人物イラスト

ERROR:

DECORATIVE_CHART_DETECTED

または

UNSUPPORTED_VISUAL_ELEMENT

---

# 9. 推奨デザイン

使用する:

- 表
- 数値カード
- 短評
- 矢印
- アイコン
- 色分けパネル
- フロー図
- 時系列ボックス
- PASS/WATCH/FAIL表示
- 上昇/下落矢印
- 市場間因果関係
- 重要度表示
- シナリオパネル

例:

米金利低下
   ↓
ドル上値抑制
   ↓
Gold支援
   ↓
Nasdaq高PER株支援
   ↓
日経AI・半導体支援

このような因果関係を優先する。

---

# 10. 数値使用ルール

図解に使用できる数値は、

SOURCE LOCKされた本文に存在する数値のみ。

禁止:

- AIによる補完
- Webから勝手に追加
- 別時刻レポートから転記
- 前日の値を当日値として使用
- 「だいたい」の数値への変換
- 小数点の勝手な丸め
- 価格方向の推測

数値ごとに内部的に:

value
unit
timestamp
source_section

を保持する。

例:

{
  "instrument": "Nikkei225",
  "value": 70683.98,
  "unit": "JPY",
  "timestamp": "2026-10-06 close",
  "source_section": "総合判断"
}

---

# 11. Numerical Integrity Validator

図解仕様内の全数値を抽出する。

source reportから全数値を抽出する。

比較:

infographic_numbers ⊆ source_numbers

でなければFAIL。

ERROR:

NUMBER_NOT_FOUND_IN_SOURCE

さらに、

instrument
value
direction
timestamp

を可能な範囲で比較。

例:

本文:

Nikkei 70,683.98
+737.12
+1.05%

図解:

Nikkei 70,687.98

→ FAIL

ERROR:

NUMERIC_DRIFT

今回実際に発生したタイプの事故なので
必ず検出対象とする。

---

# 12. Direction Validator

価格と方向を別々に検査する。

例:

previous = 69946.86
current = 70683.98

current > previous

なら

UP

図解がDOWNならFAIL。

ERROR:

DIRECTION_MISMATCH

---

# 13. Time-Slot Contamination Validator

source report以外の時刻の内容が
図解へ混入していないか検査する。

例:

12:00図解に

「16:00終値」
「21:00 NY」
「大引け」

が入った場合FAIL。

ただし本文自身が将来監視点として
記載しているものは許可する。

ERROR:

TIME_SLOT_CONTAMINATION

---

# 14. Timeline Validator

時刻別の固定timelineを検査する。

12:00:

08:00
09:00
09:30
10:00〜11:00
11:30
12:00

16:00:

12:00
12:30
13:00〜14:00
15:00
大引け
16:00

順序が違えばFAIL。

ERROR:

INVALID_TIMELINE

---

# 15. Infographic Pre-Generation Validator

画像生成前に以下を検査。

例:

[PASS] correct report ID
[PASS] correct date
[PASS] correct time
[PASS] source locked
[PASS] required sections
[PASS] correct timeline
[PASS] six markets
[PASS] cross asset flow
[PASS] positioning
[PASS] scenarios
[PASS] break conditions
[PASS] next-session handover
[PASS] no decorative charts
[PASS] no gauges
[PASS] no unsupported numbers

全PASSのみ:

READY_FOR_IMAGE_GENERATION

1つでもFAIL:

IMAGE_GENERATION_BLOCKED

---

# 16. Image Generation Prompt Builder

自由文プロンプトを直接書かない。

Validator済みJSONから
画像生成promptを構築する。

例:

infographic_spec.json

{
  "report_id": "...",
  "title": "...",
  "layout": "high_information_grid",
  "allow_charts": false,
  "allow_gauges": false,
  "allow_people": false,
  "panels": [...]
}

Prompt Builderは必ず以下を入れる。

NO decorative charts.
NO line charts.
NO gauges.
NO invented price graphs.
NO people.
Use tables, text panels, arrows, icons and
color-coded information blocks.

---

# 17. Post-Generation Visual Validator

ここが重要。

画像生成AIへの指示だけを信用しない。

生成されたPNG/JPEGをVisionで再解析する。

検査:

- 折れ線チャートが存在しないか
- 棒グラフが存在しないか
- ゲージが存在しないか
- 架空チャートが存在しないか
- 人物が存在しないか
- タイトルが正しいか
- 日付が正しいか
- 時刻が正しいか
- 必須セクションがあるか
- timelineが正しいか
- 数値がsourceと一致するか
- 文字切れがないか
- 見出しと本文が対応しているか
- 重大な誤字がないか

結果:

PASS
WATCH
FAIL

FAILの場合:

画像を正式成果物にしてはならない。

自動再生成:

最大3回。

3回FAIL:

MANUAL_REVIEW_REQUIRED

---

# 18. Visual OCRについて

OCRを主要検証手段にしない。

可能であればVisionモデルで
画像内容を直接検証する。

OCRは補助的に使用する。

---

# 19. Artifact State

画像には状態を持たせる。

DRAFT
VALIDATING
FAILED
VERIFIED
PUBLISHED

Google Driveへ正式保存できるのは:

VERIFIED

のみ。

---

# 20. Google Drive保存

本文:

マーケットレポート2026年10月

図解:

マーケットレポート図解2026年10月

図解ファイル名:

マーケットレポート_YYYY-MM-DD_HH-MM.png

例:

マーケットレポート_2026-10-06_12-00.png

Google Drive保存後:

Drive file ID
URL
folder ID
filename
mime type

を検証。

---

# 21. Google Docs Validation

本文保存後、

必ずGoogle Docsを読み戻す。

比較対象:

- title
- date/time
- sections
- numbers
- report body

一致しなければ:

GOOGLE_DOC_READBACK_FAILED

GitHubへ進まない。

---

# 22. GitHub Publication Gate

Google Docs Validation PASS
かつ
Infographic Validation PASS

の場合のみGitHubへ進む。

Repository:

matrixdiamond512-cell/Chat-GPT-Market-Report

report:

reports/YYYY-MM-DD_HH-MM.json

publication receipt:

publication-receipts/YYYY-MM-DD_HH-MM.json

latest:

data/latest-report.json

---

# 23. Portal Validation

GitHub更新後にPortalを実際に読み戻す。

検査:

- date
- time
- title
- sections
- important numbers
- latest-report ID

公開トリガーを実行しただけでは

PORTAL_PUBLISHED

としてはならない。

公開ページ読み戻しPASSのみ:

PORTAL_VERIFIED

---

# 24. Final Completion Gate

以下がすべてPASSであること。

Report Body      PASS
Infographic       PASS
Google Docs       PASS
Drive Image       PASS
GitHub            PASS
Receipt           PASS
Portal            PASS

その場合のみ:

COMPLETE

を返す。

---

# 25. 完了表示

最終出力は必ず以下。

マーケットレポート｜YYYY/MM/DD HH:MM

チャット本文:
PASS / FAIL

図解:
PASS / FAIL

Google Docs:
PASS / FAIL

図解 Google Drive:
PASS / FAIL

GitHub:
PASS / FAIL

publication receipt:
PASS / FAIL

Portal:
PASS / FAIL

Overall:
COMPLETE / INCOMPLETE

未実行をPASSにしてはならない。

---

# 26. 「完了」という言葉の制限

以下の場合、

「完了」
「保存完了」
「公開完了」

を表示してはならない。

- readbackしていない
- source比較していない
- image validationしていない
- GitHub未登録
- receipt未作成
- Portal未確認

---

# 27. Fail Fast

重大な問題がある場合は
その場で停止する。

例:

wrong date
wrong report time
empty body
missing source
source hash mismatch
numeric drift
wrong timeline
decorative chart
Google Docs mismatch

---

# 28. Failure Reason

すべてのFAILには
machine-readableなfailure_reasonを付ける。

例:

DECORATIVE_CHART_DETECTED
NUMERIC_DRIFT
DIRECTION_MISMATCH
TIME_SLOT_CONTAMINATION
INVALID_TIMELINE
MISSING_REQUIRED_SECTION
GOOGLE_DOC_READBACK_FAILED
PORTAL_READBACK_FAILED

---

# 29. Audit Log

各reportについて保存。

validation/
  YYYY-MM-DD_HH-MM/
      report_validation.json
      infographic_spec.json
      pre_validation.json
      post_validation.json
      publication_validation.json

これにより、

「なぜこの画像が正式版になったか」

を後から確認できる。

---

# 30. Regression Tests

今回までに実際に発生した事故を
必ずRegression Test化する。

TEST 01
12:00 + 16:00 + 21:00を1枚にまとめる
→ FAIL

TEST 02
12:00に昨夜NY時系列を入れる
→ FAIL

TEST 03
12:00に装飾的折れ線チャート
→ FAIL

TEST 04
本文70,683.98
画像70,687.98
→ FAIL

TEST 05
本文作成前に画像生成
→ FAIL

TEST 06
Google Docsが空
→ FAIL

TEST 07
Google Docs本文がsourceと違う
→ FAIL

TEST 08
Portalを読み戻していない
→ INCOMPLETE

TEST 09
receipt未作成
→ INCOMPLETE

TEST 10
本文に存在しない価格を画像へ追加
→ FAIL

TEST 11
16:00図解に12:00用timeline
→ FAIL

TEST 12
画像生成AIが指示を無視して
折れ線チャートを追加
→ Post Validation FAIL

---

# 31. CLI

以下を追加。

market-report validate-report

market-report build-infographic-spec

market-report validate-infographic-spec

market-report validate-image

market-report publish

market-report full-validation

例:

market-report full-validation \
  --report-id 2026-10-06_12-00

---

# 32. Dry Run

必須。

market-report full-validation \
  --report-id ... \
  --dry-run

dry-runでは:

- Driveへ書かない
- GitHubへ書かない
- Portalへ公開しない

検証結果だけ出す。

---

# 33. Idempotency

同一report_idで再実行しても
重複成果物を大量生成しない。

既存成果物がある場合:

- SHA比較
- 同一なら再利用
- 異なるならreplace候補
- 勝手にduplicateを作らない

---

# 34. Manual Override

人間が意図的に例外を許可できる。

ただし:

--force

を使った場合、

validation_status:

OVERRIDDEN

とする。

PASSにはしない。

---

# 35. AGENTS.mdへの追加

以下の趣旨を
repository rootのAGENTS.mdへ追加する。

## Market Report Safety Rules

- Never publish an infographic before validating its
  source report.
- Never combine different report time slots.
- Never invent market numbers.
- Never use decorative financial charts or gauges.
- Never mark an artifact complete before readback.
- Never publish to GitHub before Google Docs validation.
- Never mark Portal as published before public readback.
- Treat each report time slot as an independent artifact.
- A generated image is DRAFT until post-generation
  validation passes.
- Validation failure must block publication.

---

# 36. 既存機能への影響

既存の:

- Market Report Portal
- reports JSON
- publication receipt
- latest-report
- Google Drive
- Google Docs

の形式を可能な限り維持する。

破壊的変更を避ける。

新しいValidatorを
既存workflowの前段に追加する。

---

# 37. 実装優先順位

P0:

Source Lock
Report Validation
Time-Slot Validator
Numeric Integrity
Pre-Generation Validator
Post-Generation Validator
Final Completion Gate

P1:

Google Docs Readback
Drive image validation
GitHub gate
Portal readback
Audit log

P2:

Automatic retry
Visual text overflow detection
Advanced typo detection
Dashboard UI

---

# 38. Acceptance Criteria

v1.0完成条件:

1.
本文がない状態で画像生成できない。

2.
異なる時刻の本文を混ぜられない。

3.
本文にない数値を図解へ追加するとFAIL。

4.
価格数値が1桁でも違えば検出できる。

5.
価格方向の不一致を検出できる。

6.
12:00 / 16:00のtimeline違反を検出できる。

7.
装飾的チャート・ゲージを検出できる。

8.
生成後画像を再検証する。

9.
FAIL画像をDriveへ正式保存しない。

10.
Google Docs読み戻しFAILならGitHubへ進まない。

11.
Portal読み戻し前にCOMPLETEにならない。

12.
Regression Tests 01〜12がすべてPASS。

13.
既存Portalを壊さない。

14.
同一report_id再実行で不要なduplicateを作らない。

---

# 39. 実装後にCodexが必ず報告する内容

実装後、以下を報告すること。

1. 変更ファイル一覧
2. 新規ファイル一覧
3. 各Validatorの役割
4. Validation stage一覧
5. Failure Reason一覧
6. Regression Test結果
7. 既存Portalへの影響
8. Google Drive/GitHub publication gateの動作
9. 未実装項目
10. 既知の制限
11. 実際のサンプルreportを使ったFull Validation結果

単に
「実装しました」
で終了してはならない。

---

# 40. 最終原則

このシステムの目的は、

「AIにマニュアルを守らせる」

ことではない。

「AIがマニュアルを守らなかった場合、
その成果物を正式版として通さない」

ことである。

品質管理の基本思想:

Generate
↓
Inspect
↓
Validate
↓
Accept / Reject
↓
Publish

人間が毎日同じ修正指示を出さなくても、
同じ品質基準を再現できることを
このシステムの最終目的とする。

## Trusted Vision Signer v1.0 ADD

The signer accepts provider output only when it has exactly the thirteen required checks and each verdict is `PASS`, `FAIL`, or `UNCERTAIN`. Only all-PASS output is mapped to the existing boolean attestation and signed. FAIL and UNCERTAIN never receive a VERIFIED signature. The provider remains an interface; the fixture implementation does not inspect pixels and has the fixed `fixture-test-only` identity. The source body hash is exact raw UTF-8 SHA-256. The existing Python/Apps Script canonical HMAC fields and ordering remain unchanged.

The CLI requires `--dry-run`, creates only a new local review artifact, rejects production output paths and overwrite attempts, and has no publication action. External provider execution, production key configuration, Apps Script deployment, remote readback and publication acceptance remain outside this implementation and NOT_RUN. See `docs/TRUSTED_VISION_SIGNER.md` for the operator contract.
