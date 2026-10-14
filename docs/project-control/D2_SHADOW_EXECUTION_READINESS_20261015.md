# D2手動API shadow実行：事前判定・候補比較（2026-10-15）

状態：**PREPARATION ONLY / NO CREDENTIALS / NO CHARGE / NOT APPROVED**
対象：PR #130（Draft、main未マージ）、現行ChatGPT定期タスクは稼働維持。
関連：OPENAI_API_REPORT_WORKER_DETAILED_DESIGN_2026-10-15.md、P0_DECISION_B_SHADOW_WORKER_20261015.md。

## D1で確認済み
- fixture-onlyの無課金worker。MarketDataSnapshot凍結・cutoff・source照合・正常／異常API模擬応答、タイムアウト未確定時の盲目的retry禁止、同slot競合、試験用private readbackを確認。
- 新v2 canonicalizationについてPython/GASが5ベクトルのUTF-8・SHA-256・テスト専用HMACを照合。変更不可能な旧v1 snapshot IDは保存し、新v2 digestにそのv1 IDを含めてID差替えを拒否。
- 本番PRのv1 issuer・証拠ゲートは変更せず、D1成功はAPI実行の合格ではない。

## 候補環境（比較段階、選定なし）
| 選択肢 | メリット | 制限・条件 |
|---|---|---|
| Google Cloud Run Job（手動トリガー）＋Private GCS＋Secret Manager | 手動1回実行、 IAMとstaging分離、暗号化と保持設定 | Google Cloud project・請求・IAM設定が必要。費用と利用権の確認を要する |
| ローカルPCの専用Python CLI＋暗号化private保存 | 最初の試験の導入が簡素。API利用量・応答が明確 | 電源・障害・監査ログ・秘密鍵バックアップと実行環境の一貫性を別途担保 |
| GitHub Actions手動dispatch＋独立private store | 既存CIを再利用しやすい | PR/forkでsecretsに触れさせない対策必須。GitHubを原文の公開保管先にしない |

推奨は**最初は手動1slotのsandbox環境での実証**。本番publisherの権限は一切付けない。採用環境は利用者の費用・保管・運用許可後に選ぶ。

## 料金・停止条件（正式な予算ではない）
ベースライン：1run入力12,000 tokens・出力4,000 tokens、web search 0回、初回自動retryなし。詳細設計に記録済みの単価による参考値はGPT-5.4 miniで$0.027/run、GPT-5.6 Terraで$0.072/run。実応答に必要なトークン数が違えば料金も変動する。別途private store、クラウド実行、将来のweb search、外部市場データ、税・為替を計上。
D2の予算承認では、model ID、output token上限、入力size上限、試験run数、最大試行数、月額cap、API projectのusage cap、timeout UNKNOWN時の課金照合を明示する。capが不明・変更不可なら送信しない。

## D2実施に必要な入力／証拠
1. 選択したモデル名と固定バージョン、Responses API呼出し仕様・strict schema・要求/応答のshape。
2. 実データadapterの接続先・利用許諾・出典と時刻・必須観測項目。D1の架空データを実運用値として出さない。
3. 専用API projectと最小権限キー、秘密の外部保管先。GitHub public branch、Google Docs本文、ログにはキーを置かない。
4. 暗号化済みprivate保管先のobject version/読み戻し/immutable receipt、retention・削除・権限・監査ログの合意。
5. 実行前確定のReportContext/MarketDataSnapshotと数値照合policy、引用根拠とニュース材料の固定source bundle。
6. タイムアウト処理、重複run/attempt防止、UNKNOWNの場合の運用手順と責任者。
7. 観測証拠：response_id/status/usage、原文raw bytes/hash、private readback/hash、入力との全数値照合、下流write 0、PUBLISHED 0。

## D2判定
未承認＝BLOCKED。すべて埋まった段階でユーザーによる費用・保存・API試行承認を取得する。その後もD2は **手動1slotだけ** 実行し、次枠への自動スケジュール移行、Apps Script本番公開、既存ChatGPTタスク停止、mainマージは別途判断する。

## 2026-10-15 D2事前判定コード追補（無課金・実行不可）
PR #130に`scripts/reporting/d2_preflight.py`（標準ライブラリのみ・外部ネットワークなし）と`tests/test_d2_preflight.py`を追加。モデル版の固定、対象slotの週日・日付、immutable context/snapshot入力契約、Responses strict schema指定、外部toolsゼロ、1run×1attempt、入力/出力token cap、USDのDecimal料金計算、run/month cap、private immutable byte-exact readback、保持日数、timeout UNKNOWN停止、外部認証記録の存在を検査する。

**全条件に形式上合格しても`api_send_allowed=false`／`publication_allowed=false`。** ローカルのJSON参照文字列を費用やアクセス権限の実承認とは見なさない。実際のOpenAI project、利用モデルID、料金、Secrets、IAM、保持期間、外部データ利用権、実API送信の明示承認を独立に確認するまではBLOCKED。テストは合成例に基づくため、モデルsnapshot文字列や料金を実契約の確定値と見なさない。

無課金D2 preflight検査：`python -m unittest discover -s tests -p 'test_d2_preflight.py' -v`、`python -m scripts.reporting.d2_preflight`。同PRのD1 offline CIに追加し、実行証跡はGitHub Actionsに残す。本番publisherを起動させる構成・資格情報・公開書込を含めない。
