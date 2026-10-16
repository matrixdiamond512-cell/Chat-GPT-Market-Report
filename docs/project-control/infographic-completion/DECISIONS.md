# 判断と復旧処理

- D-C1: 既存CLIとSourceLock/market/body/specゲート、既存PNG renderer、旧SVGアイコンを再利用。承認16パネル配置は別の編集可能なlayout/CSSへ分離し、旧08:00投影・公開契約を変更しない。正式manifestは作らない。正式投影の接続は型付き原本契約が揃った後に再評価する。
- D-C2: 計算した観測hashは `source_observed_sha256` とし、原本の `bodyHash` に補填しない。本文の数値をDecimalで抽出してもsnapshotを作らない。SOURCE_TEXT_ONLYは転記の証拠として限定する。
- D-C3: 共有CI2件は保存済みmergeの両親を比較し、最新mainの本文検証・historical quarantineとPRの既存公開/manifest回帰が残ることを確認。最終ファイルはmainと同一。CI成功のため検証を無条件skipする変更なし。
- D-C4: 最新main 43f97b3で撤回された08/12/21の本文をreportsへ戻さない。既に取得したGit履歴をsource commit付きのDRAFTレビューとして保持し、画像上に撤回済みと明示。正式原本が別途確認された場合のみ再検証する。
- D-C5: v20は保存mainとの差分がイベント追補だけであることを確認。21:30を無条件採用せずBLS/Censusで再照合し、本文は上書きしない。銀行時刻は未確定。追補は原本のas-of時点の証拠ではない。
- D-C6: v1.8の「PNG必須の公開前順序」と10/09の独立本文/図解レーンには規範上の差異がある。最新ユーザー指示に従い、実装済みの独立状態管理と全既存停止ゲートを保持。今回の文書追補はDRAFT描画に限定し、旧条項・稼働公開順序・配備設定を変更しない。
- D-C7: 全文を失わず文字サイズを保持するため高さを拡張。承認画像の縦横比・写真調アイコン・図記号密度の再現は未完了として記録。構造チェックや生成成功で視覚受入を代用しない。
- D-C8 (2026-10-17): User's later explicit instruction that the infographic summarizes the report supersedes earlier full-text character coverage on the PNG. Preserve and hash the full report body; require every declared infographic fact to resolve to exact source offsets and validate all numerical/snapshot bindings. No report text is removed.
- D-C9 (2026-10-17): G2 capture timestamp plus body/hash/identity snapshot-context are checked against importer readback and receipt save time. This timestamp provides order evidence, not a cryptographic signature. The Google Docs writer is still not wired to pass the single captured artifact as its only body input; this remains an upstream integration outcome.
- D-C10 (2026-10-17): Do not modify default-branch scheduled workflows or merge PR #97 to activate automatic renderer invocation without separate approval. Proposed minimal future hook: default-branch TEST_ONLY workflow after publisher/readback completion, pass only same-run artifacts into a pinned PR renderer, emit local/staging artifacts with `publish_allowed=false`, and keep human scenario review as a blocking input.

必要な復旧処理:

1. 撤回された3時刻は、作成時の真正な全文を指定Docs/生成履歴から確認する。12:00の再構成文は真正な原文の代わりにしない。正規の原文hash/revisionを照合してから現行原本へ戻す工程が必要。今回、その外部書き込みは行っていない。
2. 各時刻の型付き市場snapshotを、商品ID・取引所/限月・価格種別・単位・観測時刻・比較基準・独立出典と同じ取引identityへ結ぶ。既存market/historyのgeneratedAtは08=11:37、12=18:34、16=23:28、21=23:05で各cutoffを超えており、そのまま図解原本へ流用できない。過去時点の保存データを照合し、存在しなければ取得不能を保持する。
3. 既存本文ゲートのMISSING_REQUIRED_REPORT_SECTIONと、今回原本の見出し/構造との差を列挙し、仕様に基づく正式adapter/原本修正を検証する。見出しを黙って追加してPASSにしない。
4. snapshot/原文/正式specが揃った後、今回の全セルを型付きレジストリへ結ぶ正式投影とmanifest adapterを受入する。現在は既存公開consumerへ渡せる正式manifestを出力しない。
5. 承認画像との残る視覚差、焦点4項目/条件3項目・イベントの重要度/影響市場の根拠、実端末可読性を確認する。Drive/Portal readbackや公開は別途承認された非本番/本番手順で行う。
