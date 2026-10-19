# 配信システム文書管理規程

現行版: 2.0
改訂日: 2026-10-19 JST
変更ID: DOCCTRL-20261019-01
本規程は新しい要件定義書や仕様書の別冊ではなく、既存の文書を固定IDで管理する手順を定める。

## Google Drive 正式文書（固定名・固定ID）
| 文書名 | Google Docs ID | GitHub対応 |
|---|---|---|
| 要件定義書 | `102PMtKQ4DaXqV1G2RhE8vFtQ8qes-tvIvy2jYQda_xA` | `docs/system/requirements.md` |
| システム仕様書 | `1qL7f3yKwghuDb5PiAI3RhwFJUVUfLwGakC8z8EOJ9oI` | `docs/system/specification.md` |
| 本文作成マニュアル | `1M9LzxKgg8Y50uHSzE1OhML-lU-ufPhvh79xj_m1jWYQ` | 本文・図解ルール（参照） |
| 運用マニュアル | `1OUVDAMjv009VWlI48Jb8TVuzszy4TIkjgBrHlzbNxYg` | `docs/system/operations.md` |
| 文書管理台帳 | `1F5vH9_O0LUC9Dki0CNm1JDNVfg7gMYMcUCIxgeanE5g` | このファイル |

Google Drive 親フォルダー: https://drive.google.com/drive/folders/16tITmW93FFEeSYEOh3y7UNZiwvMktNWY

## 強制ルール
1. 既存の固定ID Google Docsを更新する。日付、Version、統合、改訂、最新版などをファイル名に加えた別ファイルの作成を禁止する。本文内の改訂履歴と Google Docsの版履歴を用いる。
2. GitHub配信正本も `docs/system/requirements.md`、`specification.md`、`operations.md` の固定パスだけ更新する。新規の `*_vN.md`、`*_最新版.md`、`*_変更仕様書.md` などを作成しない。検討内容はissue/PR、過去版はGit履歴で管理。
3. 作業開始前に変更要求ID、対象文書ID、GitHubパス、変更対象節、現行revision、関連PRを照合。Docsを更新する前に影響文書マトリクスを作成する。
4. 共通ルールの変更は、要件・仕様・本文作成・運用・台帳のうち影響する文書へ同じ変更要求IDと日付で反映する。ポータル側への変更だけで配信システム側を更新したことにしない。
5. 仕様変更と「GitHub main実装済み」「CI成功」「ChatGPTタスク起動」「Docs本文読戻し」「PNG」「publication receipt」「Pages全文・DOM」「通知到達」は必ず別ステータスで記録。現時点で検証できない項目はUNKNOWN。
6. 編集後に正本IDから読み戻し、名称、内容、最新版の表記、他文書との整合、GitHub差分を確認。未解決差異は文書管理台帳へ記入し、全件完了と偽らない。
7. 配信スケジュール等は記録ではなく現行main実装と実行ログを照合。古い障害履歴、未マージ案、OpenAI API shadow計画を現行機能に昇格させない。
8. 旧文書は削除せずDriveの`99_旧版アーカイブ`で保存。バックアップ、出典と旧版である表示、参照整合が確認されていないものは無断で廃棄しない。

## 2026-10-19 時点の既知の未解決
- 旧PNG必須公開ゲートと現行の本文PUBLISHED・図解NOT_READY独立状態の業務受入の整合。
- 10/17以後の実装・運用の全件差分監査。
- 定時4枠の本文、図解、Docs、receipt、Pages、通知到達のE2E確認。
- 旧文書の全件条項照合（長文3冊と2.x〜3.x群）。これらは履歴として保存する。
