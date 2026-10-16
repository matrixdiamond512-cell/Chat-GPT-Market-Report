# 08:00図解テンプレート v1.1（デザインレビュー版）

2026-10-13 JST。実装ブランチでのレビュー用。main未マージ、本番未切替。

## 実装と入力契約

基本入口は`python scripts/render_morning_infographic.py render`。fixture以外の正式モードは、readbackのpreflightに加えて不変slot evidence、Docs importerのpublication receipt、source-bound summary、scenario review、同一仕様specを必須にする。実データを使う場合は`python scripts/run_morning_infographic_staging.py`がこれらを一つのtransactionとして検証した後、既存Python/HTML/SVG/Playwright rendererを呼ぶ。Google Docsを新たに読みに行く機能ではなく、検証済みimporter receiptのsourceを明示的に引き継ぐ。画像生成AI、ニュース取得、市場データ取得、外部保存、自動公開は実行しない。

- `--report`: 既存report/context/immutable snapshot。正式入力にはrevision、snapshot_id（またはsnapshotId）、bodyHashも必要。
- `--view`: `time=08:00`、同じreport_id/revision/snapshot_id/body_hash、facts、header、順序固定cards。
- 各factは`id,text,source_section,start,end`。`fullText[start:end]`とtextを完全一致させる。1つの本文行内の出典範囲を使用し、長い段落・複数行は必要数のfactsに分ける。本文の非見出し情報を全て被覆し、未使用factや出典の違う節への参照を拒否する。
- 6市場の価格・時刻は`snapshot_field = {instrument,field}`でsnapshotに結び付ける。価格/前日比/率はDecimalで比較し、時刻はasOfを完全一致させる。
- 6市場は金、WTI、OSE日経225先物、USD/JPY、EUR/USD、BTCUSDの順序固定。価格・asOf・方向・根拠・強気/弱気条件は必須。
- 正式モードは`--spec`も必須。既存`validate_market_data`、`validate_report`、`validate_spec`を変更せず実行する。表示投影はそのspecの検証済み表示文字列の範囲を超えて追加できない。時刻だけは検証済みsnapshotのasOfをそのまま表示する。
- 正式モードでは`--slot-evidence`、`--publication-receipt`、`--summary`、`--scenario-review`も必須。単独renderer呼び出しでもこの契約を検査し、どれか不足ならPNG作成前に停止する。scenario reviewは人間が原文と3役割の条件/展開/市場影響を照合した記録であり、summaryの構造検査だけでは代替できない。
- `--fixture`にはreportとview双方の`synthetic_fixture=true`が必要。既存market/body検査と新しいsource/数値/構成検査は実行するが、正式spec判定の代用にはしない。出力は常にDRAFT/DEBUG_PREVIEW。正式モードとの混用は拒否する。

現在の旧specゲートはtyped numberをsnapshot価格と照合するため、全ての閾値・バリュエーション・騰落率を含む任意の実本文がそのまま通るとは限らない。このゲートは緩和していない。入力が通らなければ正式生成を停止する。mock用正式契約テストは価格だけを扱う互換入力で、実レポートの合格証拠ではない。

## 表示仕様

固定16項目と6市場、意味別12色、濃紺の大型タイトル、重要4カード、時系列帯、列を分離したテーブル、流入/流出図、ニュース波及、メイン/上振れ/下振れの独立経路、最終結論/データ状態の分離を実装した。

上昇は#E91E63、下落は#0875E1、中立は#738095。流入は#00A86B、流出は#DF3046。価格変化と予測方向とフローを別のフィールド・クラスに分ける。方向の強さは元の「中立〜やや強気」等を保持する。方向未判定は「?」とする。

流入/流出は実測または推定の出典説明が必須。推定には「市場反応からの推定」と破線、因果未確定には「想定経路」と破線を表示する。矢印だけで因果や実流量を断定しない。国旗・金塊・原油ドラム・BTC・警戒・金融機関・時計はローカルSVGで描画する。

標準PNGは幅1536pxで高さ可変。本文最小28px、768px縮小時に最小14px。テキストを省略するellipsisや固定行数制限は使用しない。原文はHTML escapeし、外部リソース読込はブロックする。モバイル用は同じ情報を幅768px・縦1列（6市場は2列）へ再配置して別PNGを生成する。標準PNGを375pxへ単純縮小したものを可読性合格と扱わず、モバイル用を用いる。

## ローカルでの合成試験

必要: Python 3.12、Node 24、Playwright 1.62.1。テストだけPillowを使用する。CJKフォントも用意する。環境内の認証情報は不要。

```powershell
npm install --prefix tools/morning-renderer --ignore-scripts
npx --prefix tools/morning-renderer playwright install chromium
$env:NODE_PATH = (Resolve-Path tools/morning-renderer/node_modules).Path
python -m pip install pillow
python tests/morning_fixture.py validation/0800-review/input
python scripts/render_morning_infographic.py render --report validation/0800-review/input/report.json --view validation/0800-review/input/view.json --fixture --output validation/0800-review/render
python -m unittest discover -s tests -p test_morning_layout.py -v
```

インストール済みブラウザを使う場合だけ`--browser <executable>`を指定する。実行端末の絶対パスやNODE_PATH設定はコード・成果物へ保存しない。出力先が既にあると停止するため、再実行には新しいレビュー出力先を使う。既存画像を上書きしない。

出力はHTML、render-contract.json、PNG3種類、render-receipt.json。receiptは元HTML/view/PNGハッシュ、描画fact ID、元文字列との比較、カード順序・6市場、はみ出し・重なり・色・最小文字サイズ、ブラウザ版を含む。PASSはこれらのローカル検査範囲を示し、外部公開・独立OCRの合格を示さない。

同じ入力・同じブラウザ/フォント環境では2回のPNG SHA-256一致を確認した。別OS・ブラウザ・フォント環境でも同じバイト列になるとは保証しない。CIはpinしたPlaywrightのChromiumとNoto CJKで独立に描画試験する。

## manifest producerと既存公開ゲートの接続

```powershell
python scripts/render_morning_infographic.py manifest --report validation/0800-review/input/report.json --view validation/0800-review/input/view.json --fixture --png validation/0800-review/render/png/morning-0800.png --receipt validation/0800-review/render/png/render-receipt.json --drive-file-id mock-drive-file --drive-readback validation/0800-review/render/png/morning-0800.png --png-filename fixture.png --output validation/0800-review/DRAFT-manifest.json --report-output validation/0800-review/bound-report.json
```

これは合成試験で、Drive保存を行っていない。正式モードでは`--fixture`を外し、検証済み`--spec`、実際に保存したDrive file IDと同じファイルから読み戻したPNGを渡す。正式PNG名は`マーケットレポート_<report_id>.png`。描画receipt、source/view identity、PNG byte/hash、readback byteが一致しなければmanifestは作らない。

`--report-output`は元のreportに`infographicManifest`を添えた新しいローカルコピーを作る。元本文・bodyHash・revision・snapshotは変更しない。既存`evaluateInfographicReadiness_`と`publishInfographicAfterBody_`がこの契約を消費する。ローカルのreadbackファイル自体はDrive file IDの外部出所を証明しないため、既存公開処理がその指定file IDを実際に再読取し、MIME・名前・PNGハッシュ等を検査する段階を省略しない。

正式manifestの構造はmockでREADYとして受け入れられ、identity/hash改変は拒否された。実描画から作った合成manifestはDEBUG_PREVIEWとしてNOT_READYになることを確認した。正式manifestの作成は承認済み公開や実Drive保存成功を意味しない。このCLIは公開処理を呼ばない。

## レビュー用成果物と比較

`docs/examples/0800-design/`に架空の入力、DRAFT PNG3種類、拡大確認用の切り出し、実描画receipt、DRAFT manifestを保存した。元の参考画像から価格を転記していない。

| 比較 | 今回の結果 |
|---|---|
| 10/09のデザイン | 濃紺/鮮やかな青・赤・オレンジ・緑・黄、番号円、国旗/商品アイコン、方向、テーブル、フロー/因果矢印を採用。厳密な同じ画像レイアウトではなく、可読性と全文保持に合わせ縦拡張 |
| 10/12の構成 | 依頼の16項目・6市場・根拠/条件/時点/欠損を保持する表示契約と被覆検査を実装。合成入力142factsを全表示 |
| 10/12実本文との情報量・数値比較 | BLOCKED。正規snapshot/context等がないため実画像を再生成していない。実本文と完全一致したという主張はしない |

## 運用マニュアル追記（レビュー用）

08:00図解は専用コマンドで手動レビュー生成し、既存運用は自動切替しない。本文と同じidentityを固定し、全facts・出典時点・数値・描画receiptを確認する。取得不能と検証済みと公開状態を別に表示する。合成成果物はDRAFT/DEBUG_PREVIEWとして保存し、正式画像や本番保存先へ登録しない。

実レポートは既存specゲートを含めて検証する。欠損snapshot・不足spec・未描画facts・文字切れの場合は図解を生成/公開しない。本文公開と図解公開の独立した既存状態管理を保つ。Drive保存後は指定file IDの再読取からmanifestを作り、既存ゲートに渡す。PNGが既存の公開画像と競合した場合は上書きせずレビューに戻す。

mainマージ、本番配備、定期タスクや自動公開への接続は別途ユーザー承認後に行う。

## 2026-10-13 デザイン再設計レビュー版

10/09参考画像に合わせ、PC表示を12カラムの複合グリッドに変更した。上段4枚、時系列/指数/市場データの比較列、金利・資金フロー、材料波及、全幅のシナリオ因果図、全幅を使う6市場一列、最後の3パネルという順で構成する。カード幅は3・4・6・12カラムを使用し、行の高さをカード内容に合わせる。画面上のカード番号順はPCとモバイルの両方で検査する。

市場データは市場名・基準値・変化・基準時点を行ごとに結び、指数表の騰落を赤/青/灰で色分けする。時系列は時刻帯、資金フローは資産アイコン付きの往復矢印、材料・シナリオは横向きの因果経路、No.13は6市場を同じ一列に配置する。モバイル幅では独立した2列/1列構成へ組み替え、No.13の市場カードも複数行に再配置する。

レビュー用fixtureは長文ニュース、各市場の価格/方向/根拠/上下条件、複数行テーブル、欠損注記、3シナリオを含む。2026-10-13時点の合成PNGは1536×2639、モバイル版は768×3391。142 factsは全て元本文と完全一致した。配色/文字切れ/配置の自動検査は通過しているが、参考画像との差異は残る。特に完成画像は10/09参考より縦長で、ヘッダーの街並みはSVGの模式図、カード内余白と一部の密度も異なる。見た目の合否はこの機械検査では確定せず、ユーザーの画像レビュー待ちとする。

今回のレビューPNGは[`redesign-review-v1`](examples/0800-design/redesign-review-v1/)に保存した。すべてDRAFT/DEBUG_PREVIEWの架空データであり、数値は参考画像から転記していない。10/09の正式画像と実データの一致確認やsnapshot検査の代わりにしない。

## 2026-10-13 判読性レビュー版2

利用者レビューを受け、街並みの描き込みよりレポート内容の読みやすさを優先した。ヘッダーの模式図は小さく薄くし、本文の表示面積を増やした。PCではNo.05/06/07を各4/12幅、No.08/09/11/12を各6/12幅、材料波及No.10と6市場No.13を全幅、最後はNo.14/15を各3/12幅、No.16を6/12幅とした。6市場の価格・判定・根拠・強弱条件の文字を15〜20pxへ拡大し、市場データ行も54px以上、値と基準時点は18px/16pxにした。画面幅768pxのモバイル書き出しでは最低表示文字15pxを確保した。

版2のPNGは[`readability-review-v2`](examples/0800-design/readability-review-v2/)に保存した。1536×2629のPC PNG、768px縮小確認画像、幅768px専用モバイルPNGを含む。142 factsを全件表示しており、数値と文章は合成fixtureから直接描画している。PNG SHA-256は`89ba60b2962771ad6f4945549e3fab5c34ca84f767fce7b64feb56c328e1cc19`。自動検査と作成者の目視は実施したが、デザイン受け入れは利用者の確認待ち。実レポートのsnapshot不足によるBLOCKEDは継続する。

## 2026-10-13 保存済み10/12本文によるレビュー候補

利用者の指摘「見本と違い、内容も違う」を受け、参考画像の値は一切流用せず、保存済み`reports/2026-10-12_08-00.json`の`fullText`からレビュー画像を再生成する専用スクリプトを追加した。入力の状態は`RECONSTRUCTED_UNVERIFIED`であるため、出力には「未検証・公開不可」を明記し、report view・snapshot・公開manifestを作らない。これは正式レポート生成経路から分離された目視レビュー専用である。

PCは12カラムの可変グリッドとし、No.01〜04を4枚、No.05/06とNo.07/08をそれぞれ2枚、No.09〜12を4枚、No.13を全幅、No.14〜16を3枚に配置する。No.13は6市場を同一行に並べる。モバイル幅768pxでは密度の高いNo.07/08とNo.16を全幅、6市場を3列2行に組み替える。No.05は時刻帯、No.06は指数比較表、No.09は推定/実測を明示したフロー枠、No.10は材料から値動きへの矢印、No.04/15は赤い警戒、No.14/16は引継ぎ/検証アイコンを使う。

[`content-review-2026-10-13`](examples/0800-design/content-review-2026-10-13/)のPNGは1536×1470、幅768pxモバイル版は768×2297。ブラウザ検査は43表示fact、16項目の順序、12カラム、6市場全幅一列、768px専用レイアウト、文字切れ/カード重なり/色エラー0を確認した。PNG SHA-256は`ff76043361881e404866ca020fe804ab5ac9796ba700507f582eaf167193139d`。個々の表示factは保存済み本文から直接描画している。

参考画像との差異は残る。ヘッダーの写真調の東京夜景/富士山は再現せず、濃紺の簡素なヘッダーと明るいカード背景を使う。参考よりカード角丸・帯・アイコンが簡素で、PC画像も参考の横長比率より縦に長い。参考の見出しと今回の16項目は内容構成が異なるため、カード名は今回の固定項目を優先している。数値・文章の正確性はsnapshot照合されておらず、この画像を正式レポートとして扱わない。デザインの合否は利用者の目視確認後に決める。
