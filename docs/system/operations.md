# マーケットレポート配信システム 運用マニュアル
2026-10-13 / PRレビュー用。3文書は独立。GitHub mainの静的確認・本番稼働・未マージPRは区別する。
1. 編集依頼の対象文書を要件定義書/仕様書/マニュアルに分類し、Google Docs fileId・GitHubパス・版とrevisionを確認する。
2. mainにある実装、未マージPR、ドキュメントの提案、実際の稼働実績を分ける。配信システムと関連するWeb資料は同一プロセスの一部だが、他文書だけの更新を完了と呼ばない。
3. 発行前に設定ファイルと実際のChatGPT定期タスク・Apps Scriptトリガーを個別確認する。コードにトリガー関数があるだけでは稼働とは言えない。
4. レポート原文の表示、Drive保存とreadback、receipt、図解manifest・PNG hash、GitHub、公開前後DOMを各工程で検証。本文と図解の状態を別々に記録する。
5. 失敗時は工程を止め、原本欠損を推測で補わず原因を記録する。PR #94/97のDraft機能を本番の成功実績に算入しない。
6. 書込後に同一ファイルを読戻し、3文書に間違った反映がないか検証する。GitHub PRレビューを経ずにmain・本番トリガー・Pages deployを変えない。

## 2026-10-13 実検証で確定した事実
- 実ChatGPTタスクは平日4枠のみ有効。土曜日旧タスクは無効。Apps Script実トリガーは接続元から照会不可。
- PR #95/#96/#98/#99/#100はmainへマージ済み（2026-10-13確認）。PR #94/#97はDraft・未マージ。
- PR #94のMOF検証はSTALE_DATA閾値の限定修正後、Actions run 38298392598でSUCCESS。ただしSheets/本番updateはSKIPPED。PR #97はデザインテストPASS、本番公開未確認。
- 2026-10-12 21:00 のDocはGoogle Driveに実在。旧Receiptにはstrict validator必須のtitle/status/publisher/driveFileId/driveUrl/savedAtが欠ける。保存主体や日時を推測補完しない。
- PR #98の公開workflowへの直接Receipt検査追加は撤回。新旧スキーマ移行と実テストまでは本番導入禁止。

## 2026-10-13 最終照合
- PR #99はmainにマージ済み。現行スケジュールは平日08/12/16/21のみ、土日なし。
- PR #94の修正後Actions run 38298392598はSUCCESS。Draft・未マージであり、本番データ書込を検証したものではない。
- この文書に記載するPR #98のReceipt強制ゲートは撤回済み。Docs保存証跡の旧スキーマ移行が未完了のため、公開ゲートの新設を完了とはしない。

## 2026-10-13 追加再照合・継続作業（PR #100反映後）
- PR #98およびPR #100のmainマージをGitHubのmerged検索で再確認した。上の「実検証で確定した事実」に残っていたPR #98未マージとの記述を訂正した。
- PR #100が実装したのは旧Receiptの分類および誤認防止であり、旧データからpublisher/savedAtを推測して補完する正式移行ではない。
- PR #94: Actions run 38298392598でtreasury-validationおよび候補検証のジョブがSUCCESS。sheets-test/nikkei-sheets-test/treasury-sheets-test/updateはSKIPPED。28項目の本番取得・Sheets保存・読み戻し・公開は成功と扱わない。Draft維持。
- PR #97: 合成入力による描画テスト成功と、実レポート入力の検証・Drive readback・本番公開は別の証拠として記録する。2026-10-09/12実レポートの必須source snapshot/数値レジストリ等の不足を推測で補わず、正式検証は未完了。Draft維持。
- Receipt正式移行には、既存Google Docsの実体ID・保存時刻・発行者を独立に照合し、schema-version付き新Receiptを生成・readbackする統合テストが必要。旧Receiptの欠損値を補作しない。公開の強制ゲートは移行完了・回帰テスト前に有効化しない。
- Apps Scriptのインストール済みトリガーは、プロジェクトの権限付き実行環境で実トリガー一覧・所有者・直近実行履歴を確認するまで未確認とする。ソース上の定義と実際の定期実行を区別する。
- 発行設定はmainのconfig/report_schedule.jsonで平日08:00/12:00/16:00/21:00、土日なし。旧時刻はlegacyStoredSlotsで履歴管理。

## 2026-10-14 継続追補（3文書共通版 v1.10）
- 08:00/12:00原本を再検証する時は、原本本文を変更せず、Docs ID・revision・本文全文readback・body hashを記録する。重複Docsは本文一致だけで二重登録しない。
- 10/14確認結果：08:00は2 Docs（同一5,933文字）、12:00は1 Doc（5,815文字）。修正前のPython SOPは08:00の因果関係見出し、12:00の条件付き6市場見出しを検出できなかった。修正後のPython native-Docs経路で両原文を読取専用検査しPASS。Apps Scriptにも同じ別名と本文量条件を適用する。本文のキーワードのみ、空見出し、説明本文のない市場行は拒否する。
- snapshot調査：08:00 slotラベルのmarket-historyは2026-10-14 10:24:21 JST生成で、レポート時刻後かつレポートID/revision/context/body hashへの結合なし。12:00 snapshot履歴なし。新しいsnapshotを過去レポートへ付け替えず、両枠は公開保留のままにする。
- GitHubのChatGPT作業ブランチには12:00 JSON（`BLOCKED_SNAPSHOT_MISSING` / `DRIVE_SAVED_QA_PENDING`）とstatus=`saved` receiptがある。Drive本文は空行正規化後にJSON本文と一致するが、Docs readback SHA-256 `f4e898a5…` とJSON記録bodyHash `62aaa648…` は一致しない。厳密な本文ハッシュreadbackは未合格。main・reports.json・dashboard・Pagesへの登録は確認できない。
- 12:00タスク出力には本文全文・Docs保存/読戻し・作業ブランチJSONとreceipt作成の報告がある。08:00本文出力と重複Docsは確認。ChatGPT task内部の工程ログ・最初の実行エラーは取得できずUNKNOWN。Apps Script OAuthとChatGPTタスクGitHub接続を混同しない。
- 次回の08/12/16/21各実行ごとに、開始時刻と完全な本文、Docs revision/readback hash、事前snapshot/context、GitHub正本と公開receipt、reports.json/latest/dashboard、Pages表示と本文readbackを記録する。証拠が欠ければその段階で公開を保留し、4枠すべての反復成功まで復旧完了としない。

## 2026-10-14 14:36 JST 継続追補 v1.10
- PR #128 `4cb2dce385300c51447d7c4a8ed316bc4637ab8a` の関連Actions 8件はSUCCESS。回帰テスト用Apps Script合成本文の6市場説明を充実させて再実行した。production gate・Apps Scriptトリガー・本番スケジュールは変更していない。PRは未マージ。
- 次の16:00実行では生成時刻と本文全文、Docs保存readbackと本文hash、発行前snapshot/contextの結合、GitHub正本/receipt、reports.json・latest・dashboard、Pages全文readbackを時刻付きで確認する。欠落工程はUNKNOWNまたはBLOCKEDとして記録し、他の時間帯へ成功を外挿しない。
- 08:00の後刻10:24 snapshotと12:00 snapshot不在は継続ブロッカー。現在値から過去snapshotを作らず、保存receiptをpublication receiptと見なさない。
