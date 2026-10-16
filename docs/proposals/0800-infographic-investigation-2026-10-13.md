# 08:00図解の生成・検証・公開接続調査と実装提案

調査日: 2026-10-13 JST。調査対象: main `38afca50113cfa9eef39df6b3e51f2acac9b01e7`。
状態: PROPOSED / 実装未承認。専用ブランチ: `codex/0800-infographic-design`。

追記: この文書は初回調査時点の記録。以後ユーザーが実装・限定資料送信・Draft PRを承認し、専用描画/manifest producerを追加した。現行仕様・入力制限・画像/検証は`docs/0800-infographic-template.md`と専用EVIDENCE_LEDGERを参照する。

## 結論

既存リポジトリには図解の仕様検証、画像生成用プロンプトの構築、外部で生成したPNGの検証・公開受入処理がある。ただし、固定16項目の08:00画像を描画するテンプレート、描画実行、現在の公開受入用manifestの生成までを接続する実装は確認できなかった。存在する汎用プロンプトを、添付画像の生成元や08:00テンプレートと扱わない。

ユーザーの確認によれば10/12改善イメージはChatGPTの画像生成機能で作成された。10/09と10/12改善前の生成元は未特定。今回の検索で見つからなかったことは、他環境にも生成元が存在しないという証明ではない。

推奨案は、既存の取得・検証・公開処理を保ち、その間に08:00専用の決定的なHTML/SVG描画テンプレートとPNG出力を追加すること。画像生成AIに文字・価格を再描画させる経路を正式な数値描画には使用しない。実装と接続は承認後に行う。

## 調査範囲と根拠

- 現在の作業フォルダーは古いmainと多数の未コミット変更を含んでいたため、別フォルダーに最新mainを取得した。元の作業ファイルは変更していない。
- 最新mainのscripts、apps-script、schemas、assets、docs、workflowsを調査。保存済み`.pr94-work`とGoogle Drive側の過去ソースも確認した。
- Drive側の`recovery_market_report_infographics.py`は10/01の復旧用で、固定日付・データ・異なる構成を持つ。今回の画像の生成元とは確認できず、流用しない。
- `numeric_registry`と`source_snapshot`という名前の機能は、調査した現行ソース内では確認できなかった。既存のMarketDataSnapshot、構造化市場行、source lockを関連機能として区別し、同等性や28項目の完全被覆を実装済みとは主張しない。
- コードの存在・ローカルテストの結果と、稼働中Apps ScriptやChatGPT定期タスクの実行状況は別。稼働環境の配備版・設定・外部保存結果は今回未検証。

## Phase 1: 現行実装の所在

| 調査項目 | 確認した実装・状態 |
|---|---|
| 生成入口 | `scripts/market_report.py`の`build-infographic-spec`、`validate-infographic-spec`、`build-infographic-prompt`。JSON検証・プロンプト出力まで。画像モデルや描画エンジンの実行は未接続 |
| 08:00テンプレート | `scripts/reporting/infographic.py`に08:00の時系列定義があるが、固定16項目の描画テンプレートはない |
| 配色 | 汎用プロンプトは色分けブロックを指示するのみ。08:00専用の意味別パレットはない。ポータルCSSの配色は画像内の配色ではない |
| 16項目 | 同ファイルの`REQUIRED_SECTIONS`は17個の本文概念。`build_spec()`は本文の解析結果と数値カードから可変数のpanelsを作る。依頼の固定16カードとは別 |
| 数値・文章描画 | `build_generation_prompt()`は検証後のJSONを文字列化する。PNG文字描画、文字幅測定、折り返し、カード配置は未実装 |
| 品質検証 | 同ファイルにG0/G1再利用、本文・source lock・数値provenance・時系列・方向検証、PNG/Vision検証。`scripts/reporting/gates.py`には別の段階的トランザクションゲートがある |
| 公開状態 | Python ReportObjectはDRAFT。現行Apps Scriptは本文PUBLISHED/BLOCKEDと図解READY/NOT_READY/FAILED_VALIDATIONを分離。汎用のAPPROVED状態管理は確認できない。人の承認とREADYを同一視しない |
| 保存先・消費先 | Apps Scriptはmanifestが指定したDrive PNGをfile IDで読み出し、`images/reports/<date>_<HH-MM>.png`へ登録。`assets/js/report-core-v3.js`が同じreport/revision/snapshot/body/manifest/PNG hashを検証して表示。レンダラーからDriveへの保存処理は確認できない |

## 接続状況

```text
Pythonの検証済みreport/context/snapshot
  → infographic spec検証 → 画像生成用プロンプト
  → [画像描画・生成実行が未接続]
  → [現行公開用manifest producerが未接続]

Apps Script本文検証 → 同じGoogle Docsの全文・hash再読取
  → 本文公開・公開結果確認
  → evaluateInfographicReadiness_(report.infographicManifest)
  → Driveの指定PNG・hash検証
  → 画像/正本/一覧/dashboardのGitトランザクション
  → ポータルのREADY・identity・実PNG hash検証 → 表示
```

`scripts/reporting/gates.py`の`create_manifest()`は段階的トランザクション用の別manifestを作る。現行Apps Scriptが要求するfact coverage、numeric_validation、renderer_statusを持つ`infographicManifest`のproducerとは同一視できない。

現行Apps Scriptの図解受入は`required_fact_ids`、`rendered_fact_ids`、`missing_fact_ids`、`numeric_validation`、`renderer_status`等を要求する。新レンダラーがあるだけではこの契約は満たせない。Drive保存・file ID取得後のmanifest連結を含めて検証する必要がある。

Pythonの既存`validate_image()`は署名付きVisionの判定を含む。一方、10/09の仕様変更を反映したApps Script公開経路はVisionを任意QAとする。異なる経路なので片方のPASSで他方のPASSを代用しない。どちらの既存判定も今回変更しない。

## 実レポート入力の状態

| 入力 | 保存された状態 | 足りない契約 | 実行結果 |
|---|---|---|---|
| `reports/2026-10-09_08-00.json` | report_status=PUBLISHED、infographic_status=NOT_READY、marketDataTableは28行 | context、immutable snapshot、revision、snapshot_id、bodyHash、pinned sourceDocument、正式画像metadata/manifestがない | 既存CLI validate-reportはFAIL / MARKET_DATA_SNAPSHOT_NOT_FOUND |
| `reports/2026-10-12_08-00.json` | report_status=RECONSTRUCTED_UNVERIFIED、infographic_status=DRIVE_SAVED、marketDataTableはない | 同上。検証済み正本として採用できない | 既存CLI validate-reportはFAIL / MARKET_DATA_SNAPSHOT_NOT_FOUND |

PUBLISHEDという保存済みフラグは、図解CLIの入力合格や今回の外部公開確認を証明しない。DRIVE_SAVEDも現在の公開schemaのREADYとは異なる。検証が最初のsnapshot検査で停止したため、後続検査がすべて不合格であると推定していない。

添付画像や別チャットの文章から価格を転記して欠損を埋めない。正規の検証済み本文・snapshot・版を入手できるまでは、この2日付の正式再生成はBLOCKEDとする。

## 承認を求める実装案

### 範囲

追加候補は`templates/infographic/0800/{template.html,theme.css,icons.svg}`、`scripts/reporting/morning_layout.py`、PNG出力用の`scripts/render_morning_infographic.py`、入力schema、合成fixtureとテスト。名前は実装時に既存配置へ合わせる。既存CLIに入口を追加する場合も08:00専用の明示コマンドとし、既存の他時刻の経路を切り替えない。

取得・ニュース・数値照合・snapshot・bodyHash・report identity/revision・公開ゲート・Drive保存・ポータルコードは変更対象外。既存manifestの受入契約に出力を合わせる。必要な値が欠けるときは生成/公開を制限し、ゲートを緩和しない。互換性上どうしても既存ゲート変更が必要になった場合は、その差分を別途提示する。

### 入力と描画の分離

検証済み本文と構造化値から、出典付き表示factsの読み取り専用投影を作る。入力はreport ID、revision、snapshot ID、本文hash、schema versionを固定する。既存の本文17概念はそのまま検証し、その後の表示投影だけを固定16カードへ割り当てる。元のspecを16カードに書き換えて検証を通す方式は採らない。

価格・比較値・シナリオ閾値・時刻・商品識別子を型で区別する。価格はDecimalと元の表示文字列を保ち、桁・単位・比較基準を勝手に丸めない。条件の閾値をsnapshot価格として注釈することも禁止する。旧`validate_spec()`にはtyped numberをsnapshot価格と一致させる制約があるため、PER/EPS・閾値・28項目の入力を自動で扱えるとはまだ言えない。この互換性を合成fixtureで先に確認し、未対応factsは明示的に停止する。

方向予測と前日価格変化を別フィールドにする。方向、判断の強さ、根拠、強気/弱気条件は本文・検証済み分析から取り、騰落率から予測を生成しない。流入/流出には実測/推定/取得不能を必須化し、推定の経路は破線と「市場反応からの推定」、未確認の因果経路は「想定経路」を表示する。

### 固定カードと描画形式

| No. | 表示領域 | 形式 |
|---|---|---|
| 01 | 総合判断 | 結論と大きな方向表示 |
| 02 | 今日の焦点 | 本文にある4ポイントを番号付きで表示 |
| 03 | 相場テーマ | 材料アイコンとテーマ |
| 04 | 重要3条件 | 出典付き閾値を警戒色で強調 |
| 05 | NY市場の時系列 | 段階別の帯、実際の市場日付 |
| 06 | NY主要指数 | 終値・比較値・騰落率の独立列 |
| 07 | 主要市場データ | 商品・市場・基準日時ごとの行 |
| 08 | 金利・ボラティリティ・日本株評価 | 系列・算定方式を区別した表 |
| 09 | クロスアセット資金フロー | 左流入候補/中央矢印/右流出候補、実測と推定を区別 |
| 10 | ニュース・材料と波及 | ニュース→直接市場→金利/為替→株式/暗号資産。裏付けのない段階は断定しない |
| 11 | 需給・ポジション、SQ/MSQ | 事実・未取得・偏りの判断を分離 |
| 12 | シナリオの因果関係 | メイン・上振れ・下振れの別経路 |
| 13 | 6市場の短期見通し | 金/WTI/OSE/USDJPY/EURUSD/BTCUSDの固定順。値・時刻・方向・根拠・強気/弱気条件 |
| 14 | 次の時間帯への引き継ぎ | 次時間帯の監視点 |
| 15 | リスク管理・崩れる条件 | 見方を変える条件を強調 |
| 16 | 結論・データ検証 | 結論と検証済み/取得不能/公開不可の小領域を分離 |

No.13は見出しを1回だけ表示し、子カードに13の番号を重複表示しない。四つ/三つの焦点や6市場の根拠等が元入力にないときは作らず、欠損として記録する。情報を捨ててカード数を合わせない。

### デザイン・再現性

08:00専用CSS変数で仕様書の12色を管理する。上昇ピンク/赤、下落青、中立グレー、流入緑、流出赤、警戒赤、結論黄。濃紺の大型ヘッダー、重要カードの背景差、番号円、機能を持つSVGアイコン、方向/フロー/因果それぞれ異なる矢印を使う。参考画像の文字・数字はコピーしない。

HTMLへ元の日本語をそのまま挿入し、固定フォントと固定ブラウザ版でPNGへ出力する。文字はHTML、アイコンはローカルSVGとし、emojiフォント依存や外部画像読込を避ける。固定高・行数上限・ellipsis・overflow隠蔽を使わず、高さを実測して拡張する。テーブル列の幅と方向表示を先に確保し、長文を折り返す。

ポータルの画像はwidth:100%/height:autoで表示され、レポートページの最大幅は1120px。横幅の最終値は実装fixtureで選定し、縦方向の拡張を許容する。768px表示で本文・数値が読めることに加え、375/390pxのスマートフォンでも実画像を確認する。768pxでの合格だけでモバイル合格にしない。縮小で読めない場合は列数・余白・幅と高さを再配分し、文字縮小で隠さない。

manifestには必要fact ID、描画fact ID、欠損、元のidentity、PNG hash、実施済みの数値/レイアウト検査結果を結び付ける。`numeric_validation=PASS`や`renderer_status=PASS`を出力しただけで合格としない。Drive file IDは実際の保存・再読取から得る。合成fixture画像はDRAFT/DEBUG_PREVIEWとし、正式画像metadataを作らない。

### 検証・導入順

1. 入力契約とsource→表示fact→16カードの被覆を合成データで検証する。
2. 08:00専用テーマ・テンプレート・PNG描画を実装し、全カード、6市場、正負/中立、長文、取得不能、推定フロー、条件閾値、異なる時刻を検査する。
3. 元の値・文字列との照合、DOMのはみ出し/重なり検査、PNGと768px/スマートフォン表示の目視確認を行う。
4. 正規の検証済み入力が揃った場合だけ10/09・10/12を再生成し、情報量・数値・時点とデザインを比較する。揃わない場合はBLOCKEDのまま残す。
5. 既存数値/本文/公開状態/他時刻/保存/ポータルの回帰と、manifest消費側の試験を実施する。外部試験は指定の非本番保存先で行い、未実施はNOT_RUNとする。
6. Draft PRにコード・比較画像・検証結果をまとめる。ユーザー承認までmainへマージせず、本番自動生成を切り替えない。

## 今回の検証結果

- 既存図解検証テスト: 23/23 PASS。初回はWindows sandboxの既定tempディレクトリで5件のPermissionError。ソース変更なしでTMP/TEMPを作業内へ指定すると23件通過。
- 本文/図解の独立公開状態テスト: 6/6 PASS。
- `scripts/test_independent_publication.js`: PASS。Apps Scriptのmanifest、指定Driveファイル、既存画像競合、Gitトランザクション、ポータル表示のモック回帰。実サービス実行ではない。
- 10/09・10/12の実入力CLI検証: 両方FAIL（snapshot契約不足）。正式生成はBLOCKED。
- 新テンプレート、合成画像、768px/スマートフォン画像検査、実画像比較: NOT_RUN。今回の作業は調査・提案のみ。
- 稼働Apps Script配備版、ChatGPT定期タスクの設定接続、Drive/ポータル実保存・公開: NOT_RUN。
- 証拠水準: 接続のコード確認E0、既存ローカル回帰E1〜E3（モック範囲）。新テンプレートのE4/E5証拠はない。

## 運用マニュアル追記案（未適用）

08:00図解は、検証済み本文・同じ版のsnapshotとidentityを固定してから専用テンプレートで生成する。入力・必須fact・描画検証が不足する場合は図解をNOT_READYまたはFAILED_VALIDATIONとし、既存の本文公開経路とは独立に報告する。合成・デザイン見本にはDRAFT/DEBUG_PREVIEWを表示し、正式PNGと区別する。正式登録は既存manifestゲートとDrive再読取に従う。公開済み画像との内容競合は上書きせずレビューへ戻す。

## 未解決事項・次の必要行動

実装案のユーザー承認、正規の10/09・10/12入力入手、17概念/16表示カードとtyped数値契約の互換性検証、非本番Drive接続、稼働生成元/配備版の確認が残る。承認前に新しい生成経路の実装や運用切替を行わない。

調査文書4ファイルはローカル専用ブランチに保存した。GitHubブランチ送信は実行前のauto-reviewで拒否され、Draft PRは未作成。調査資料・原仕様書を`matrixdiamond512-cell/Chat-GPT-Market-Report`へ送信する開示承認を待つ。コード・本番・mainは変更していない。
