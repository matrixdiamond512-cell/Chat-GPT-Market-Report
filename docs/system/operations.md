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

## 2026-10-15 オフラインv2ハッシュ検証・D2着手判定（v1.12 / Draft）

- 作業ブランチ`codex/producer-bound-publish-gate-20261015`のPR #130で`python -m unittest discover -s tests -p 'test_canonical_v2.py' -v`と`node scripts/test_canonical_v2_golden.js`、従来D1テストおよびApps Script回帰をGitHub Actionsで検証する。Python/GAS 5ベクトル一致・snapshot v1 ID維持・改ざん拒否を確認する。
- 実行時はAPI key、Apps Script本番、Docs/Sheets/GitHub/Pages writerを使わない。v2 helperはまだ公開ゲートに接続しない。旧v1を自動移行せず、10月14日各レポートの公開保留を継続する。
- D2の起動前に、OpenAI API projectと費用上限の個別承認、private store/IAM/retention/readback、source adapter/全数値検証、モデル版・request timeout/retry、producer専用署名鍵/検証鍵分離を確認する。未達項目は`BLOCKED`で記録し実API送信しない。
- 既存ChatGPTタスクと時刻設定は変更しない。GitHub PR #130はDraft・未マージ、本番E5は未達。スケジュール／デプロイ／main統合は別途安全審査のうえ実施。

## 2026-10-15 D2事前検証手順追補（Draft）
PR #130の`python -m unittest discover -s tests -p 'test_d2_preflight.py' -v`と`python -m scripts.reporting.d2_preflight`をD1 CIで実行する。無設定時は`MISSING_MANIFEST`と`EXTERNAL_ATTESTATIONS_NOT_VERIFIED`でBLOCKED。合成manifestで形式上PASSでも実API送信と公開は許可されない。実API Projectと鍵、モデル実在/費用、private保存先・IAM/保持期間、source利用権、認証済み承認レコードを確認できるまでD2実行禁止。ログ/PR/Docsに秘密情報を貼らない。旧タスク・本番停止・Draft PRを維持する。


## 2026-10-15 D2 Responses API offline検査・運用境界（Draft）
`python -m unittest discover -s tests -p 'test_d2_responses_contract.py' -v`で、Responses APIの模擬レスポンス8件を通信なしで検証する。候補モデルsnapshotはOpenAI公式確認の`gpt-5.4-mini-2026-03-17`。出力はモデル応答構造の形式検査であり、実API呼出しの証明ではない。OpenAI project/API key・保存先・費用上限・独立承認が揃うまで送信しない。既存ChatGPTタスクは変更せず、Apps Script・GitHub本番公開も停止したままとする。

## 2026-10-15 D2受信原本確認の運用追補（Draft）
- CIで`python -m unittest discover -s tests -p 'test_d2_responses_contract.py' -v`を実行し、raw response bytesとnormalized JSONのdigestが別物であること、原本不一致／重複キー／不正UTF-8時の停止を確認する。
- 今後の有料D2試験では、実際に受信したレスポンスの原本bytesを非公開で保存し、保存オブジェクトの再読み戻しとのbyte-exact比較まで確認する。dictから再生成したJSON bytesを「API原本」として保存・署名しない。
- 原本バイト列のhashだけでは真正性は立証できない。外部送信権限、実API課金承認、private store、ソース利用権・原文↔Docs照合・全数値意味検証が未達ならAPI送信・公開ともBLOCKED。

## 2026-10-15 D2 immutable evidence stagingのoffline運用（Draft）
- `python -m unittest discover -s tests -p 'test_d2_private_store.py' -v`を既存D1 CIで実行する。CIには試験用の一時ディレクトリと無害なfixture bytesのみ使用し、実市場データ・API secrets・レポート原本を保存しない。
- 専用private rootはPOSIX環境で外部管理された暗号化済みvolume上に配置する設計。現実の暗号化・IAM・保持期間・監査・分散lockは未設定のため、試作コードのみでD2実API試験を許可しない。
- ファイル上書き・読戻し不一致・危険なpath/owner/mode/linkは即時停止し、欠落証拠を再生成して成功と扱わない。

## 2026-10-15 D2数字照合ゲート運用追補（Draft）
- CI実行：`python -m unittest discover -s tests -p 'test_d2_numeric_claims.py' -v`、`python -m unittest discover -s tests -p 'test_d2_responses_contract.py' -v`、既存D1テストを実行。本文に根拠なしの数値、数字位置重複、不正な単位、別出典ID、cutoff以降の観測、誤ったsource URL等が含まれた場合は生成結果を隔離・停止する。
- 模擬出力の数字を検査し合格しても実報告の数値監査完了やE5承認とは呼ばない。現在の適用範囲は凍結6市場の`priceValue/changeValue/changePct`と限定的な字句解析。ニュース統計・PER/EPS・金利・日時・他市場の数値は根拠バンドル未接続のため遮断する。必要項目を削除して合格に偽装してはならない。
- source bundleはスナップショットに含まれる主張の再照合用であり、取得先の独立認証・法的データ使用権・自然言語の意味照合の代わりではない。実API課金、永続private store接続、署名、公開は実施しない。

## 2026-10-15 正式仕様書の単一正本運用手順
1. 仕様追加/変更/削除時は最初に `docs/system/specification.md` と正式Google Docsの同一版「統合仕様」を更新する。**独立した変更仕様書を作成・継続更新しない**。詳細設計/PRコメントは検証ログに限り、正本にはしない。
2. 旧変更仕様書は【アーカイブ・統合済・更新停止】に変更済み。参照・旧版復元は許可するが、現行手順の根拠は正本からのみ取り、変更内容の重複記載を禁ずる。
3. 要件定義書は要求、運用マニュアルは検証/停止/復旧の手順を分担し、具体的な契約（schema、API、署名、数値照合、全writer）は仕様書へ集約。設計差分に応じて3文書の整合を確認する。
4. 編集前後のGoogle Docs revision、GitHub blob SHA、ファイル名、章名、適用範囲、検証結果を確認する。未確認・Draft・本番採用済みの区別を維持し、GitHub/Google Docsのreadback後にのみ更新済みと報告する。
5. 2026-10-15の変更は文書統合のみで、PR #130をmainにマージせず、APIキー/有料API送信/実トリガー/Apps Script本番配備/過去分公開を変更しない。

## 2026-10-15 文書一本化後の運用手順
技術仕様の正本は `docs/system/specification.md` とGoogle Docs正式仕様書の1組のみ。旧変更仕様書はアーカイブ・更新停止とし、今後別の変更仕様書を作成して仕様を二重管理しない。仕様変更時は正本の関連章・改訂履歴を更新してから、要件定義書（要求）と本マニュアル（実施・検証手順）に必要な差分のみ反映する。実装詳細ノートは参考・証拠記録に限る。改訂はGitHub blob SHAとGoogle Docs revisionを確認し、readbackまで終えて初めて更新済みと報告する。現行PR #130 Draft・未マージ、本番公開停止は変えない。
