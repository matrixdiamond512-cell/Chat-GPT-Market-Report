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

## 2026-10-16 追補（DOCSYNC-20261016-RPT）
1. 4枠の開始前に市場データ取得（12時は既存11:30〜11:55・5分刻み）、T-13/T-7/T-3の発行前証拠、reportId・context・snapshot・元データhashをrun/file実体で確認する。証拠欠落が発行時刻を過ぎたら遡及生成禁止。
2. ChatGPTタスク起動は成功判定の出発点にすぎない。指定会話本文全文、図解、Docs ID・revision・全文読戻し、PNG保存、GitHub正本、receipt、Pages DOM、通知到達を各工程独立記録する。Apps Scriptのインストール済みトリガーは別途実画面のログで確認。
3. Doc原本がない場合は本文生成/Docs保存の上流を調査する。Google Docs→GitHub同期は原本新規作成をしない。runがNO_NEW_REPORTSなら発行成功と報告しない。
4. 補充版は実作成時刻と対象枠を区別して利用者へ本文先出し→Doc保存→読戻し。HISTORICAL_ARCHIVEで非正式閲覧可能だが、snapshot/receipt欠落を隠さず正式PUBLISHEDへ昇格させない。
5. ポータル6市場の「取得不能」は最初にDocs本文と照合する。値があればparser/表示UI/キャッシュを調査し、価格・時刻・市場・限月・条件分離を回帰テストする。図解には別日数値や未検証値を加えない。
6. PR #152/#153/#154の改修はmain導入済み。4枠ライブE2E・通知・ドキュメント/図解保存の全成功までは復旧完了としない。
