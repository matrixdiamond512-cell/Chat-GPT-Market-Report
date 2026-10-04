# マーケットレポート配信システム
# Codex向け 次工程実装指示
# 監査結果反映版
# 2026-10-04

今回の作業は、
「全面リファクタリング」ではありません。

監査で確認されたP0/P1問題の根本原因を潰すため、
正式仕様の矛盾解消と、
ReportContext / MarketDataSnapshot / ReportObject / Validation Gate
までを段階的に実装してください。

重要：
E〜HのPublisher / Projection / Portal / Scheduler再編へは、
今回まだ進まないでください。

==================================================
1. 正式仕様
==================================================

正式仕様はGoogle Driveの

「マーケットレポート配信システム_正式文書_v1.8」

にある以下5文書のみです。

1. マーケットレポート配信システム_要件定義書_v1.8
2. マーケットレポート配信システム_仕様書_v1.8
3. マーケットレポート本文作成マニュアル_v1.8
4. マーケットレポート配信システム_運用マニュアル_v1.8
5. マーケットレポート配信システム_文書体系・索引_v1.8

旧Version 2.x / 3.xマニュアル、
v1.6 / v1.7は正式仕様ではありません。

履歴確認用途に限定してください。

==================================================
2. 現行正式スケジュール
==================================================

新規レポート発行：

月〜金
08:00
12:00
16:00
21:00

土曜・日曜
レポート発行なし

06:30 JST
市場データ更新
※レポート発行とは別工程

07:00レポート
土曜09:00週間まとめ

は正式仕様ではありません。

==================================================
3. 監査で確認済みの重要問題
==================================================

以下を既知問題として扱ってください。

P0-01
2026-10-02 21:00のDrive ID分岐

canonical/index/latest/dashboard:
OLD = 1WIWiLE_kH7NsuAQYHxLYXcv9BoxbGh-0ClaVqNKohvQ

publication receipt:
NEW = 1nA_FsxdGvRLTDF46Qy_CdsPYVWJiutkycXOMTfG3JBo

OLDは現在404。
NEWは実在・本文非空。
ただしNEWとcanonical本文は完全一致していない。
元ChatGPT本文は未取得。

→ 今回、自動的にどちらかを正本にしないこと。

P0-02
08:00公開DOMで金/BTC価格が「08」と誤抽出される。

P0-03
PNGがない枠でも公開されている。

P0-04
過去に誤日付で10/2扱いされた4枠を撤回し10/1へ復旧した履歴がある。

P0-05
persist_report_index_to_canonical.pyに
revision防御なしの無条件上書き経路がある。

P0-06
構造Validation FAILでもPages deployできる公開経路が存在する。

P1-01
ReportContextがない。

P1-02
unknown cronを現在時刻から推測する。

P1-03
同じ時刻の別日MarketDataSnapshotをreportへ付ける可能性がある。

P1-04
公開後の市場表補修でChat/Doc/JSON差分が発生し得る。

P1-05
complete_report_schema.pyで最初の変更後に処理終了する。

P1-06
naive datetime / timezone-aware datetime比較でTypeError。

==================================================
4. 最初に正式仕様矛盾を解消する
==================================================

監査で確認されたSPEC_CONFLICT SC-01〜03を解消してください。

現状は、

A.
GitHub登録成功後にpublication receipt作成

という記述と、

B.
publication receiptを含むbundleを作成してからGitHub登録

という記述が混在しています。

この循環を解消するため、
以下の2段階へ正式仕様を統一してください。

--------------------------------------------------
Publication Manifest
--------------------------------------------------

公開前に生成する。

目的：
「これから何を公開するのか」を固定する。

最低限：

report_id
report_date
report_time
revision
body_hash
snapshot_id
drive_file_id
drive_url
png_file_id
png_filename
created_at

状態例：

READY_FOR_PUBLICATION

--------------------------------------------------
Publication Receipt
--------------------------------------------------

公開後に生成する。

目的：
「何が実際に公開されたのか」を証明する。

最低限：

report_id
revision
manifest_id
manifest_hash
git_commit_sha
pages_deployment_id
published_at
verified_at
portal_url
dom_validation_status
final_status

状態例：

PUBLISHED
VERIFIED
FAILED
UNKNOWN

重要：
receiptは公開前bundleの一部にしないでください。

流れを以下へ統一してください。

Drive本文検証
↓
PNG検証
↓
Publication Manifest生成
↓
GitHub登録
↓
GitHub Actions
↓
GitHub Pages
↓
公開DOM検証
↓
Publication Receipt生成
↓
VERIFIED

正式5文書すべてについて、
この順序へ統一してください。

ただし、
既存過去receiptを一括変換・削除しないでください。

==================================================
5. 2026-10-02 21:00の扱い
==================================================

この枠は監査対象として保全してください。

現時点の状態：

reportId:
2026-10-02_21-00

canonicalIdentity:
UNRESOLVED

publicationStatus:
UNVERIFIED

reviewStatus:
NEEDS_REVIEW

今回の実装で、

OLDを削除
NEWへ自動統一
canonicalを書換え
receiptを書換え
PNGを再生成

しないでください。

この枠は回帰テストfixtureとして利用して構いませんが、
本番データは変更しないでください。

==================================================
6. Phase A：ReportContext
==================================================

最優先で実装してください。

新しい共通ReportContextを導入してください。

推奨：

{
  "report_date": "YYYY-MM-DD",
  "report_time": "HH:MM",
  "report_id": "YYYY-MM-DD_HH-MM",
  "data_cutoff": "ISO8601+timezone",
  "previous_report_id": "...",
  "previous_business_day": "YYYY-MM-DD",
  "revision": 1
}

以下はReportContextへ入れず、
ExecutionContextへ分離してください。

attempt_id
execution_started_at
saved_at
published_at
verified_at

理由：

対象日時
と
実際の処理日時

を混同させないためです。

例：

10/2 21:00レポートを10/4に修復しても、

report_date = 2026-10-02
report_time = 21:00

を維持すること。

==================================================
7. ReportContextの必須ルール
==================================================

1.
入口で一度だけ生成する。

2.
以後readonly。

3.
retry時に再計算しない。

4.
現在時刻からreport_dateを推測しない。

5.
manual historical実行では
report_date / report_timeを必須入力にする。

6.
unknown cron mappingは推測せずfail closed。

7.
土曜・日曜の新規report発行を拒否する。

8.
既存履歴の読取・訂正はhistorical/recovery modeとして別扱い。

9.
全artifactが同じreport_idを参照する。

対象：

Chat
Docs
PNG
manifest
receipt
canonical
reports.json
latest
dashboard
portal

==================================================
8. Phase Aで修正候補
==================================================

重点対象：

scripts/resolve_market_report_slot.py
scripts/run_market_data_window.py
config/report_schedule.json
MarketReportWebSync.gs
StructuredImport.gs
workflow inputs

既存ロジックを破壊的に書き換えず、
ReportContextを共通入口へ追加する形を優先してください。

==================================================
9. Phase B：MarketDataSnapshot
==================================================

既存の市場データ基盤は維持してください。

既存：

data/market/latest.json
data/market/history/
last-verified
morning-reference
readiness
source registry
validation

これらを捨てないでください。

不足しているのは、

特定reportIdに固定されたimmutable snapshot

です。

新たに、

MarketDataSnapshot

を導入してください。

例：

{
  "snapshot_id": "...",
  "report_id": "2026-10-02_21-00",
  "schema_version": 1,
  "captured_at": "...",
  "data_cutoff": "...",
  "markets": [...]
}

==================================================
10. Snapshotの必須ルール
==================================================

1.
ReportContextへ紐付ける。

2.
immutable。

3.
本文生成後にlatestから勝手に更新しない。

4.
Docs保存時に再取得しない。

5.
PNG生成時に再取得しない。

6.
JSON生成時に別snapshotを付けない。

7.
Portal表示用に後から最新価格を混ぜない。

8.
新価格を使う場合は新revisionとして扱う。

9.
retryは同snapshot_idを使用する。

==================================================
11. Phase D：ReportObject
==================================================

Validation Gateの前に、
ReportObject契約を整理してください。

理由：

何を検証するのかを先に固定するためです。

ReportObjectには最低限：

report_id
report_date
report_time
revision
snapshot_id
title
full_text
sections
market_data_table
markets
previous_report_id
status

を持たせてください。

既存historical JSONは
一括書換えしないでください。

legacy adapterで読み込めるようにしてください。

==================================================
12. Market schema
==================================================

表示文字列と数値を分離してください。

推奨：

{
  "instrument": "WTI",
  "marketType": "FUTURES",
  "venue": null,
  "contractMonth": null,
  "priceValue": 89.47,
  "priceUnit": "USD/bbl",
  "changeValue": null,
  "changePct": -3.7,
  "direction": "DOWN",
  "comparisonBasis": "...",
  "asOf": "...",
  "source": [],
  "status": "VALID",
  "unavailableReason": null,
  "displayText": "89.47ドル"
}

重要：

計算は数値fieldで行う。

表示だけdisplayTextを使う。

0
null
UNAVAILABLE
STALE
N/A

を区別する。

directionは観測方向とoutlookを分離する。

==================================================
13. Phase C：Validation Gate
==================================================

ReportContext
↓
MarketDataSnapshot
↓
ReportObject

が固まったあとにValidation Gateを接続してください。

推奨Gate：

G0 Context
G1 Snapshot
G2 ReportObject
G3 Chat→Docs
G4 PNG
G5 Publication Manifest
G6 Git
G7 Pages/DOM
G8 Publication Receipt

==================================================
14. G0 Context
==================================================

確認：

report_date
report_time
report_id
曜日
mode
revision
previous_report_id
data_cutoff

不一致なら停止。

==================================================
15. G1 Snapshot
==================================================

確認：

価格
単位
基準日時
鮮度
source
status
UNAVAILABLE reason
change
changePct
direction符号
対象市場系列

不一致なら本文生成しない。

==================================================
16. G2 ReportObject
==================================================

確認：

必須section
fullText
snapshot_id
market table
headings
aliases
reportId
revision

本文構造とstructured dataが矛盾したら停止。

==================================================
17. G3 Chat→Docs
==================================================

ChatGPTに表示した本文原文を保持。

同一Drive fileIdへ保存。

保存後、
同じfileIdを再読取。

比較：

全文

許容normalizationのみ事前定義。

禁止：

文字数だけ
先頭一致だけ
hashだけ
要約比較

==================================================
18. normalization
==================================================

まず以下だけを候補にしてください。

改行コード統一
末尾の単一改行
Drive由来の無意味な空行

ただし、

句点追加
文章変更
表現変更
数値変更

を正規化で吸収しないでください。

normalize前後diffを保存してください。

==================================================
19. G4 PNG
==================================================

必須：

same reportId
same revision
same body
same snapshot

Drive上に実在。

filename一致。

PNG bytes検証。

別時間帯流用禁止。

PNGがなければGitHubへ進まない。

==================================================
20. G5 Publication Manifest
==================================================

manifestには、

report_id
revision
body_hash
snapshot_id
drive_file_id
png_file_id
artifact identities

を固定。

以後のPublisherはmanifestを入力にする。

==================================================
21. G6 Git
==================================================

確認：

canonical
reports.json
latest
dashboard

が同じ

report_id
revision
snapshot_id

を参照。

古いrevisionの上書きを拒否。

commit SHAを保存。

==================================================
22. G7 Pages / DOM
==================================================

同じcommit SHAの公開を確認。

確認：

title
reportId
本文
主要市場データ表
価格
前日比
騰落率
direction
取得不能理由
PNG
date picker
time tabs
prev/next
reload
console
loading timeout
mobile

誤価格「08」などを回帰fixtureへ追加。

==================================================
23. G8 Publication Receipt
==================================================

全公開検証後に初めてreceipt生成。

receiptには：

manifest
git SHA
Pages deployment
DOM validation

を保存。

VERIFIEDになる前にreceiptだけ作成しない。

==================================================
24. canonical writerの扱い
==================================================

今回はまだPhase Fへ進まないため、
canonical writerの全面整理はしないでください。

ただし、

persist_report_index_to_canonical.py

の無条件上書きはP0リスクなので、

今回のPhase A〜D〜Cのテストで
危険経路として明示してください。

本番挙動を変える場合は
別commit・別承認にしてください。

==================================================
25. UIのP0回帰fixture
==================================================

2026-10-02 08:00をfixtureとして使い、

Gold
BTC

が「08」にならないことをテストしてください。

fullText全域regexで最初の数値をpriceにしない。

UNAVAILABLE reasonをpriceとして扱わない。

marketDataTable.rows
↓
markets
↓
legacy

の優先順位は維持する。

legacy parserはsection内部だけを対象にする。

==================================================
26. PNG gate回帰
==================================================

以下を追加してください。

PNGなし
→ Publication Manifest FAIL
→ GitHub登録禁止
→ Pages deploy禁止

既存のPNG欠落履歴は書換えない。

新規発行policyとlegacy policyを分ける。

==================================================
27. timezone
==================================================

すべてのdatetimeをtimezone-awareへ統一してください。

Asia/Tokyo
または
UTC

を明示。

naive datetimeとaware datetimeを混在させない。

CLIでdate-onlyが来た場合、

安全にtimezone付き境界へ変換するか
明示エラーにする。

TypeErrorのまま落とさない。

==================================================
28. complete_report_schema.py
==================================================

any(generator)等によって
最初の変更後に処理終了する問題を修正してください。

ただし、
historical全件を書換えない。

まずunit testで
複数inputがすべて処理されることを確認してください。

==================================================
29. heading registry
==================================================

Python
GAS
JavaScript

で見出し辞書が分散しています。

今回は完全統一までやらなくてよいですが、

単一canonical heading registry

の設計を用意してください。

最低限、
テストfixtureを共通化してください。

対象：

今日の相場テーマ
前回からの変化
主要市場データ
重要ニュース
クロスアセット資金フロー
需給・ポジション
重要イベント
個別市場見通し
シナリオ
リスク管理
結論
など。

==================================================
30. market heading aliases
==================================================

以下を同じ市場表sectionとして扱うテストを追加。

主要市場データ
主要市場まとめ
市場データ
前営業日終値
終値一覧
主要価格

plain textでも認識すること。

==================================================
31. テスト必須項目
==================================================

Phase A：

explicit report_date
yesterday regeneration
reportId immutability
retry same context
unknown cron fail closed
day boundary
weekend new-report reject
historical explicit mode

Phase B：

snapshot same reportId
snapshot immutable
cross-day snapshot reject
UNAVAILABLE preservation
STALE preservation
source/asOf/unit propagation

Phase D：

legacy JSON adapter
market numeric schema
displayText separation
heading aliases
original fullText preservation

Phase C：

Drive ID consistency
Drive full-text
missing PNG
reportId mismatch
revision rollback
canonical/index mismatch
latest/dashboard mismatch
numeric direction mismatch
timezone mismatch
DOM price "08"
loading timeout
mobile table

==================================================
32. 既存テスト
==================================================

既存でPASSしているものは壊さない。

特に：

contract tests
resolver tests
intraday reconcile tests
window tests
Apps Script narrative parser
JS syntax checks
index validator
publication consistency

を回帰suiteへ残してください。

==================================================
33. 実装順
==================================================

今回：

Step 0
正式5文書のSPEC_CONFLICTを解消

Step 1
Phase A ReportContext

Step 2
Phase B MarketDataSnapshot

Step 3
Phase D ReportObject

Step 4
Phase C Validation Gate

Step 5
全回帰テスト

ここで停止してください。

Phase E
Phase F
Phase G
Phase H

には進まないでください。

==================================================
34. commit方針
==================================================

小さなcommitへ分割してください。

例：

1.
docs: resolve publication manifest/receipt contract

2.
refactor: add immutable report context

3.
test: cover historical date and report id immutability

4.
refactor: bind immutable market snapshot

5.
refactor: introduce report object schema

6.
refactor: add validation gates

7.
test: add P0 regression fixtures

大規模1commitは禁止。

==================================================
35. production data禁止事項
==================================================

今回、

reports/*.json
reports.json
latest-report.json
dashboard.json
publication receipts
Drive Docs
Drive PNG
GitHub Pages公開データ

を本番更新しないでください。

production JSONを再生成しない。

既存artifactを書換えない。

fixtureコピーでテストしてください。

==================================================
36. 実装後に必ず報告する内容
==================================================

1.
変更ファイル一覧

2.
commit一覧

3.
ReportContext schema

4.
ExecutionContext schema

5.
MarketDataSnapshot schema

6.
ReportObject schema

7.
Validation Gate一覧

8.
SPEC_CONFLICTの解消内容

9.
既存挙動で維持したもの

10.
P0のどれを直接解消したか

11.
まだ未解消のP0/P1

12.
実行したテスト

13.
PASS

14.
FAIL

15.
NOT_RUN

16.
production dataを変更していない証拠

17.
次にPhase Eへ進める条件

==================================================
37. 完了条件
==================================================

今回の完了は、

「全面リファクタリング完了」

ではありません。

完了条件は：

- v1.8 SPEC_CONFLICT解消
- ReportContext導入
- report_date明示
- reportId immutable
- unknown cron fail closed
- MarketDataSnapshot固定
- ReportObject導入
- 数値market schema導入
- Validation Gate接続
- P0回帰test追加
- 既存回帰PASS
- production data未変更

です。

==================================================
38. 最重要原則
==================================================

Accuracy
> Consistency
> Reproducibility
> Recoverability
> Automation
> Convenience

です。

現在ある正常機能を捨てず、
正本・対象日時・市場データ・本文を
一つのtransaction identityへ結びつけることを最優先にしてください。

不明な点を推測で決めない。

特に2026-10-02_21-00の正本は、
今回決定しないでください。