# GATE-F0 調査記録

- 調査ID: `gate-f0-20261015`
- 調査日時: 2026-10-15 02:02 JST
- 対象: ChatGPT定期タスク「Deliver weekday market reports」
- 基準PR: #130。調査開始時のPR head: `37e246e1c8a8680db645ae86f3f75ccb8b13d8b7`
- 判定: **BLOCKED_UNAVAILABLE**
- 公開判定: **BLOCKEDのまま**。Apps Scriptデプロイ、GitHub公開、過去レポート復旧は行っていない。

## P0の確認内容

Codex接続で利用可能なタスク一覧・会話読取を使い、対象のChatGPT会話を読み取った。

- 会話一覧では対象タスクを `kind=chatgpt`、タイトル「Deliver weekday market reports」として確認できる。会話IDは `6aceb99f-b3dc-83ee-85c7-cb838e3b50db`。
- `read_thread` は直近のuser turn ID、turn status、started/completed時刻と一部のmessage IDを返す。
- assistant出力の本文は `::chatgpt-content-reference{... source_message_id=...}` 参照に置換され、本文全文は返らない。attachmentsも空だった。したがって、対象時刻の生成原文をこの連携から取得できず、UTF-8 raw SHA-256を算出できない。
- 旧会話 `6ac82287-9580-83e8-9e5b-874b27d92d7c` でも同じ形式で、本文は取得できなかった。
- この接続で見えるturn/message IDや時刻は照合の索引としては使えるが、原文全文・生成完了状態との機械的な結び付けを証明するrecordではない。本文参照を解決する別ツール、ChatGPTタスクのrun export API、またはproducerからの署名付きreceiptは利用可能なツール一覧で確認できなかった。
- Google Docsの本文、GitHubレポート、手入力コピー、会話の自己申告から本文を再構成・逆算していない。

## GATE-F0証拠の状態

| 必須項目 | 状態 | 備考 |
|---|---|---|
| 実行/turn ID | 一部取得 | 会話・turn/message IDは取得できるが、実生成runの正式IDとの対応は確認できない |
| 原文全文 | **未取得** | assistant本文がcontent-referenceに置換される |
| 生成日時・完了状態 | 一部取得 | turnの時刻/statusは見えるが、独立した生成recordとして本文と結合されていない |
| 原文SHA-256 | **未計算** | 原文全文なし。値を作らない |
| 表示原文との独立照合 | **未実証** | 照合対象となる原文本文を取得できない |
| Docs保存本文とのreadback比較 | **未実施** | Docsからproofを後付けすることは禁止されているため |
| 正式な出力連携の仕様・権限 | **未確認** | 現在のconnectorはメタデータ/content-referenceまで |

この判定は「ChatGPTに原文が存在しない」という意味ではない。**利用中の正式な接続から、真正性検証に必要な原文を取り出せない**という意味である。原文のSHA-256、署名値、producer proofは発行していない。

## 再現手順

1. Codexのthread一覧から上記会話IDとタイトルを確認する。
2. `read_thread(threadId, turnLimit=10, includeOutputs=true)` を呼ぶ。
3. assistant messageの本文フィールドを確認する。実データでは本文の代わりに `chatgpt-content-reference` が返る。
4. 同じ会話で過去ページがある場合はcursorで遡り、必要な各08:00/12:00/16:00/21:00実行について同じ形式か確認する。
5. content-referenceを解決して原文全文・message ID・時刻・完了状態を返す正式なconnector/APIが提供され、権限と取得ログを保存できた場合にのみ再判定する。
6. Docsや公開済みレポートからは原文証拠を作らない。

## 採否と代替案

現行ChatGPTタスクをproducerとして使うGATE-F0は、現状 **BLOCKED_UNAVAILABLE**。後続P1〜P6、本番デプロイ、過去分公開には進まない。

### A. 現行ChatGPTタスクの正式な出力連携を調査継続

ChatGPT/Workspaceの管理者またはOpenAIサポートへ、実行run ID、assistant message ID、原文全文、生成開始/完了時刻、最終status、原文revision/hashを機械可読で取得できる正式なAPI/connectorがあるか確認する。併せて対象ユーザー/Workspaceに必要な読み取り権限があるか確認する。

- 既存タスク・生成運用を維持できる可能性がある。
- 連携の有無・利用可能プラン・権限・出力の不変性は未確認で、現段階では採用可否を決められない。
- 解決経路がなければBLOCKEDを維持する。

### B. OpenAI APIを使う専用生成workerへの移行案を設計

worker自身がReportContextと固定snapshotを作り、API応答のresponse/message ID、完了状態、全文、時刻、モデル/設定を同一実行で保存する。Docs保存readback・producer専用署名・publisherの検証専用権限を接続する。既存ChatGPTタスクを自動で置換しない。

- 追加費用: APIはモデル/入出力token等に基づく従量課金。必要なモデル、本文量、snapshot/context量、再試行数を測るまで月額・1レポート費用は算定しない。価格表は[OpenAI API pricing](https://developers.openai.com/api/docs/pricing)を参照。
- 権限/鍵: 専用API projectと限定API key、secret manager、Docs/GitHubの最小権限、署名鍵とpublisher検証鍵の分離が必要。
- 定時運用: JST 08/12/16/21起動、休日/遅延/retry、監視、失敗時停止、重複防止、rollbackをworker側に実装・運用する必要がある。
- 再現性: API response ID、model/version、prompt/config、context/snapshot、取得時刻、raw/canonical hashを固定保存する。ただし同一入力で同一文章を保証するものではなく、証拠と再現性の範囲を仕様化する。
- 保存先: 生成時の不変証拠receipt、原文、Docs ID/revision/readback、snapshotをアクセス制御された保管先に保存し、GitHub公開リポジトリには秘密鍵を置かない。
- Responses APIにはresponse itemのID/status/contentを含む出力イベントがあるが、これは新しいAPI workerがそのAPI実行の出力を捕捉する設計根拠であり、既存ChatGPTタスクの履歴を遡って取得できる根拠ではない。[Responses streaming API reference](https://platform.openai.com/docs/api-reference/responses-streaming/response/web_search_call)

ChatGPT Tasksの公式ヘルプは、権限に応じてタスク詳細やPrevious runsから結果を確認する手順を説明しているが、この説明から既存タスクの機械可読な全文export APIは確認できなかった。[OpenAI Help: Creating and managing team tasks in ChatGPT](https://help.openai.com/en/articles/20001540-creating-and-managing-team-tasks-in-chatgpt)

## 次の判断

**A（正式連携の調査継続）** または **B（専用API worker案の設計）** の選択と、Bの場合に既存ChatGPTタスクを並行維持するかを承認待ちとする。承認後も、本番デプロイや公開は別の明示承認・E4/E5受入を満たすまで行わない。
