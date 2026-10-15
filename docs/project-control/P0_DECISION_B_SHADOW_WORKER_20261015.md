# GATE-F0に対する方針決定：B案（専用API生成worker・並行運用）

日付：2026-10-15 JST
参照：docs/project-control/GATE_F0_INVESTIGATION_20261015.md
変更仕様書：docs/changes/マーケットレポート配信システム_生成元証拠連携・公開前検証_変更仕様書_2026-10-15.md
対象PR：#130（OPEN / Draft維持）、#128（未マージ）
決定種別：**設計着手**。API実行・課金開始・mainマージ・Apps Scriptデプロイ・本番公開の承認ではない。

## 1. 決定
- **B：OpenAI Responses APIを使う専用生成workerの設計に進む。**
- 既存ChatGPTタスク「Deliver weekday market reports」は**当面有効のまま並行運用**し、現行のチャット本文表示を維持する。
- 新workerは当初**shadow / dry-run**。生成した結果を本番Docsフォルダー、公開用GitHub main、公開receipt、Pagesのいずれにも自動書き込まない。
- 既存タスク生成本文とworker生成本文は別の生成物であり、文字列一致を前提としない。ChatGPTタスク本文からworkerの原文証拠を代用・再構成しない。
- 旧タスク側の公開復旧はGATE-F0未達につきBLOCKEDのまま。新workerも実証拠・品質検証なしで公開を始めない。
- A案の公式API/connectorが後に見つかった場合は比較材料として再評価するが、B設計をAの調査終了待ちで止めない。

## 2. 非公開workerの構成案
1. Scheduler：Asia/Tokyoの平日08:00、12:00、16:00、21:00を対象。既存タスクおよび他枠（土曜など）の設定を一切変更しない。時刻別run ID、idempotency key、retry、失敗ログを維持。
2. Verified data ingester：市場値、基準日、情報源、観測時刻、取得状況を信頼できるデータ源から取り込む。データ取得の検証前に「取得済み」と判断しない。外部API/市場データの有料契約は別途確認。
3. Context / snapshot freezer：既存の scripts/reporting/context.py、scripts/reporting/snapshot.py を使い、report_id=YYYY-MM-DD_HH-MM、revision、data_cutoff、snapshot_id、market observations、source URLs、asOfを生成**前**に固定。後付け修正は禁止。
4. OpenAI Responses producer：固定snapshotと必要なニュース・材料、既存レポート見出しSOPを入力。モデル名/版・prompt版・応答ID・status・開始/完了時刻・usage・出力全文をproducerが直接保存。取得不能・未完了・出力欠損はBLOCKED。Structured Outputsはスキーマ整合に使うが、数値の真偽は独立検証する。
5. Evidence ledger / private staging：原文UTF-8 SHA-256、raw/canonical差分、context/snapshot digest、実行ログ、Docs出力予定ID等を非公開の不変ストレージに保存。検証できないChatGPT由来IDを自己申告しない。
6. Trusted issuer：署名器はpublisherと発行権限を分離する。PR #130のHMAC共有秘密の限界を解消するまでE5として扱わない。署名鍵・API key・Google Drive認証情報を公開GitHub、Docs、ログへ記載しない。
7. Drive writer / readback：まず専用staging領域への書込・全文読戻し・Docs revision・producer原文の同一性を検証。本番Driveフォルダーを汚染しない。
8. Publisher integration：PR #130の全writer fail-closedを維持し、真正なissuer証明を受け入れる設計。最初はGitHubへのwrite APIをmockするdry-runで検証。PR #128との統合は最新版mainで競合解消・CI完走後。

## 3. 並行運用と二重公開の防止
- **既存ChatGPTタスク**：従来のチャット表示を維持。生成元証拠が取れないため、現在の公開ゲートを緩めず本番ポータル公開はBLOCKED。既存タスクを自動無効化しない。
- **API worker**：同じ時刻のレポートを作る場合も `shadow_runs/` 名前空間等の専用staging領域に保存。本番レポートの `reports/...`、`reports.json`、`latest-report.json`、`dashboard.json` には書き込まない。
- 時刻枠ごとに `production_producer` は1つしか選べない設定とし、cutover時にロック・revision/取得元・承認ログを必須とする。切替後も既存タスクをチャット表示用に残す場合は**別系統の分析結果**であることをUI/運用ルール上区別する。ChatGPTチャットへのAPI生成本文の自動配信は可能と決めつけない。
- 既存の2026-10-14レポートをAPI workerの生成物に見せ替えてย้อนหลัง公開しない。

## 4. 概算費用・上限管理（例示であり見積確定ではない）
モデル単価は2026-10-15時点のOpenAI公式料金ページを確認して採用。シナリオは **1回 input 12,000 tokens、output 4,000 tokens、月80回（平日20日×4枠）**、標準価格、キャッシュ割引なし。
- gpt-5.4-mini：input $0.75 / 1M、output $4.50 / 1M → **約$0.027/回、約$2.16/月（モデル入出力のみ）**。
- gpt-5.6-terra：input $2 / 1M、output $12 / 1M → **約$0.072/回、約$5.76/月（モデル入出力のみ）**。
- OpenAI web searchを使うなら公表単価は約$10/1,000 calls（$0.01/call）＋検索結果トークン。仮に3 calls/回なら月$2.40程度を上乗せ。外部データ料、クラウド実行・保管、再試行、検索結果トークン、税、為替は別。実レポートのinput/output token数・検索回数を実測して再算定する。
- まず低コスト案（gpt-5.4-mini）を品質比較の候補にするが、相場判断の正確性・見出し充足・価格検証で合格しなければ上位モデルを比較する。
- 機密情報やAPI keyを本番用として設定しない。**費用上限と実API呼出しの承認があるまで、有料API実行・スケジューラ起動は行わない。**
- 料金参照：https://developers.openai.com/api/docs/pricing
- 出力契約参照：https://developers.openai.com/api/docs/guides/structured-outputs

## 5. Codexへの直近の作業指示（設計のみ）
A. PR #130上で `worker` のディレクトリと運用環境・実行ID／payload schema案を具体化し、公開ゲートと正確に対応するフィールド契約を提示する。
B. Python↔Apps Scriptのsnapshot/context SHA計算の差分をgolden fixturesでテストできる計画にする。float・日本語・日時・null等を含める。正本hashの過去改変は禁止。
C. producer実行結果とimmutable dataの保管方法、署名器の権限分離、Docs readback、全経路のfail-closed、GitHub証跡を設計。
D. shadowモードでの無書込テスト、原文ハッシュ負例、重複枠・retry競合テスト、費用計測項目を明文化する。
E. 本番Docsへの保存／公開／既存タスク停止／API課金開始は別途承認を取得する。現在のPR #130はDraftのまま。PR #128の統合・main書込み・Apps Script本番配備は未実施。
