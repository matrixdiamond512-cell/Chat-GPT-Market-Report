# 独立監査 是正処置管理台帳・実装計画

変更要求ID: **MR-AUDIT-CAPA-20261124-01** / 変更日: 2026-11-24 JST / 状態: Phase 0調査記録および承認済Phase 1A/1Bローカル実装。本番未適用。

## 今回の適用範囲

ユーザー依頼は添付資料に従った是正。添付指示書第8節はPhase 0（証拠保全、現状確定、全不適合の台帳、実装計画）のみを今回対象とし、本番設定変更・大規模実装を除外している。資料中の将来の是正案を本番操作の承認と解釈しない。実装コード、production data、発行枠、Drive原本、GAS、IAM、請求は変更していない。

監査原文は [保全原本](https://drive.google.com/file/d/1WQpGyeDiOR6Sd5zpogC5i8qJzOpFr5et/view)、指示書は [保全原本](https://drive.google.com/file/d/1H_mGR-MeJh82vxKKui6TOTeMKR3dxA6Z/view)。NC/RC/ATの原文・IDは改変しない。本台帳の原因評価は開発側の追跡記録であり独立監査の上書きではない。[取得証跡・SHA-256](archive/independent-audit/audit-source-index.json)。資料の既存Drive保全先: folder `1br5KcaWm5lUkW2bdtwr7FNh6cts8KV_3`、監査file `1WQpGyeDiOR6Sd5zpogC5i8qJzOpFr5et`、指示file `1H_mGR-MeJh82vxKKui6TOTeMKR3dxA6Z`。監査全文のconnector読戻し成功、raw bytes一致はNOT_RUN。重複ファイルを作成していない。

## Phase 0で確認した現状と限界

- 開始時branch `codex/close-sync-recovery-20261114`、HEAD `6dd95b980`、clean、PR #201 OPEN/Draft。未コミット変更なし。既存branchを保全し、`origin/main`から `codex/audit-capa-phase0` を作成した。既存packed-refs.lockの警告あり、削除せず保持。切替後HEADとbranchを別コマンドで確認済み。
- 監査対象 `3b7a9c8452bf11f04eee9a2093ed13d7e22206fd`、fetchしたmain `579fa000fc84f6875f220962c5f17ea01138c68e`。差分は市場データ9ファイルのみ、配信コード変更なし。以後のmain更新は実装前に再照合する。
- 現行configは平日08/12/16/21 JST、土日なし。ChatGPTの実設定・実行履歴とGAS本番トリガーは今回照会できずUNKNOWN。コード存在だけで稼働停止や廃止可を断定しない。
- 公開HTTPの再取得: latest/dashboardはdataAsOf=`2026-10-13T16:00:00+09:00`、dashboard=`ok`/`isStale=false`。`reports/2026-11-20_16-00.json`はHTTP 200、SOURCE_ARCHIVED。DOM/画像描画はNOT_RUN。
- GitHub Pages APIはlegacy/main直配信。リポジトリvisibility=PUBLIC。Pagesから除外してもGitHub raw/履歴からの閲覧は残る。公開許諾・データ分類の確認と公開対象の許可リストが必要。無断非公開化や履歴削除はしない。
- reports JSONはtemplateを除き186、PNG6（最新10/01 12時）、receipt62（最新10/13 21時）、枠前evidence2。109 workflowsをローカル棚卸し（詳細一覧は公開対象外）。一時用途候補も依存・実行責任者未確認のまま廃止しない。
- 最新参照ログ: publish run 45301898178は08時REPORT_SOURCE_MISSING。deploy run 45320232165はgithub-pages artifact 0件で失敗。監査記載の旧deploy失敗と別原因として扱い、legacyだけで全失敗を説明しない。sync run 45306919797はSUCCESSだが配信成功とは認定しない。
- Drive管理folder `16tITmW93FFEeSYEOh3y7UNZiwvMktNWY`と監査指定folder `1h7ft4COBO2jcWVBMFeAKLr1Fq9sdBj58`はconnector metadata 404。11月本文/図解folder検索0件、広域検索では監査folderと8月folderのみ。404/検索0件はファイル不存在の証明ではない。実サービスアカウントとの主体差・権限はUNKNOWN。
- `python -m unittest discover -s tests -p test_repair_btc_24h_change_numeric.py`: 2件中1件FAIL（None != 81854.0）、1件PASS。修正前不具合を再現。全Python/Node試験はNOT_RUN。監査時の試験数を今回結果に流用しない。

## 是正処置台帳

以下の各NC表はPhase 0時点の基準記録。最新実装状態は末尾のPhase 1追補を参照。本番検証=NOT_RUN、独立再監査=NOT_RUN。担当は実装担当/運用管理者/独立監査者で分離し、具体担当者は実装承認時に確定する。

### NC-01（重大度: Critical）正式公開ポータルが 42 日前（2026-10-13 16:00）で完全停止、かつ `dashboard.json` が「正常・非陳腐化」と虚偽報告

| 項目 | 記録 |
|---|---|
| 不適合ID | NC-01 |
| 客観的証拠 | 公開HTTPで旧dataAsOfと正常フラグを再現。 詳細は保全監査原本の同ID節。 |
| 根本原因 | RC-4 — 予定枠鮮度が全体ヘルスへ伝播しない点は再現、cron遅延の内部原因は未確定。 |
| 暫定処置 | 旧版参照と停止を明記する表示案を準備。現在の公開画面は未修正。 |
| 恒久是正処置 | 直近予定枠をscheduleから算出しstale/degradedを伝播。NO_OPとDELIVEREDを分離、異常時通知。 |
| 対象コード・設定 | scripts/sync_latest_report_publication.py; scripts/build_market_json.py; assets/js/top-dashboard.js; check-scheduled-report-delivery.yml; sync-latest-report-watchdog.yml |
| 関連Issue・PR | #103 / #222; PR #188との監視契約を比較 |
| 実装状況 | NOT_STARTED / 承認待ち |
| テスト結果 | BTC回帰は修正前FAIL（NC-07）。他の受入試験はNOT_RUN。 |
| 本番検証結果 | NOT_RUN（現状読取は上節参照、修正後受入ではない） |
| 独立監査結果 | 原監査FAIL / 是正後再監査NOT_RUN |
| 残存リスク | 古い本文の閲覧と最新発行成功を混同させない。 |
| 完了条件 | AT-03 / AT-09 / AT-10を原基準どおり実証し、関連NCの独立再監査で受理されること。 |

### NC-02（重大度: Critical）枠前証拠（Pre-draft Evidence）の凍結が構造的に破綻し、全期間で 2 件しか生成されていない

| 項目 | 記録 |
|---|---|
| 不適合ID | NC-02 |
| 客観的証拠 | evidence2件、取得ログの時刻窓拒否は監査原本参照。 詳細は保全監査原本の同ID節。 |
| 根本原因 | RC-1 — cron遅延と窓拒否の整合は支持。109本の負荷が直接原因という推定は未実証。 |
| 暫定処置 | 15分ゲートを維持し欠損を明示、過去枠を補作しない。 |
| 恒久是正処置 | 既存Cloud Run/OIDC/GCS実装を比較し直接実行1枠で取得・不変保存・main読戻し。claimで重複防止。 |
| 対象コード・設定 | scripts/persist_report_slot_evidence.py; scripts/run_market_data_window.py; freeze-report-slot-evidence.yml; freeze-report-evidence-on-acquisition.yml; PR #206 cloud_run_market_close_job.py |
| 関連Issue・PR | #176 / #205; PR #175/#180/#181/#182/#183/#188/#203/#204/#206（全件未マージを本番扱いしない） |
| 実装状況 | NOT_STARTED / 承認待ち |
| テスト結果 | BTC回帰は修正前FAIL（NC-07）。他の受入試験はNOT_RUN。 |
| 本番検証結果 | NOT_RUN（現状読取は上節参照、修正後受入ではない） |
| 独立監査結果 | 原監査FAIL / 是正後再監査NOT_RUN |
| 残存リスク | 外部基盤でも権限・遅延・commit確定までの時間に失敗し得る。 |
| 完了条件 | AT-05 / AT-11 / AT-12を原基準どおり実証し、関連NCの独立再監査で受理されること。 |

### NC-03（重大度: Critical）図解 PNG の Drive→GitHub/Portal 同期パイプラインが不在（全 186 件中 READY が 0 件）

| 項目 | 記録 |
|---|---|
| 不適合ID | NC-03 |
| 客観的証拠 | PNG6枚・正式READYゼロは監査記録、実PNGファイル数は再確認。 詳細は保全監査原本の同ID節。 |
| 根本原因 | RC-2 — Python本文経路とGAS画像経路の分断はコードで支持。GAS実稼働停止はUNKNOWN。 |
| 暫定処置 | 画像存在と品質を別状態として扱いREADYの代用にしない。 |
| 恒久是正処置 | GAS機能/トリガーを保全後、Drive byte取得→本文対応→品質証跡→hash→manifest→GitHub→Pagesの単一経路へ。 |
| 対象コード・設定 | scripts/sync_reports_from_drive.py; scripts/verify_drive_infographic_upload.py; apps-script/MarketReportWebSync.gs; images/reports/; infographic manifest |
| 関連Issue・PR | #103 / #222; PR #73/#97の品質・描画契約を再利用検討 |
| 実装状況 | NOT_STARTED / 承認待ち |
| テスト結果 | BTC回帰は修正前FAIL（NC-07）。他の受入試験はNOT_RUN。 |
| 本番検証結果 | NOT_RUN（現状読取は上節参照、修正後受入ではない） |
| 独立監査結果 | 原監査FAIL / 是正後再監査NOT_RUN |
| 残存リスク | PNGヘッダ・解像度だけでは数値/視覚品質を証明できない。 |
| 完了条件 | AT-07 / AT-08 / AT-09を原基準どおり実証し、関連NCの独立再監査で受理されること。 |

### NC-04（重大度: High）本文・日時・画像・保存先の不一致（2026-11-20〜11-24 実測クロスチェック結果）

| 項目 | 記録 |
|---|---|
| 不適合ID | NC-04 |
| 客観的証拠 | 日付・保存先・品質不一致は監査原文の11/20〜24クロスチェック表。今回Drive直接再検証不可。 詳細は保全監査原本の同ID節。 |
| 根本原因 | RC-2 / RC-3 — 生成/保存/公開のidentity分断を仮説として保持、個別原本原因はUNKNOWN。 |
| 暫定処置 | 不一致・重複は停止し既存原本を保護。 |
| 恒久是正処置 | reportId/revision/bodyHash/imageHashを各工程で共有し、親folder/revision/全本文/byteの独立読戻しを結合。 |
| 対象コード・設定 | scripts/report_source_contract.py; scripts/sync_reports_from_drive.py; scripts/reporting/publication_evidence.py; receipt; producer writer |
| 関連Issue・PR | #103 / #176 / #222; PR #183/#188のwriter接続を比較 |
| 実装状況 | NOT_STARTED / 承認待ち |
| テスト結果 | BTC回帰は修正前FAIL（NC-07）。他の受入試験はNOT_RUN。 |
| 本番検証結果 | NOT_RUN（現状読取は上節参照、修正後受入ではない） |
| 独立監査結果 | 原監査FAIL / 是正後再監査NOT_RUN |
| 残存リスク | 原本権限がないまま原因を断定しない。 |
| 完了条件 | AT-02 / AT-06 / AT-07 / AT-08を原基準どおり実証し、関連NCの独立再監査で受理されること。 |

### NC-05（重大度: High）参考閲覧用アーカイブのマニフェスト更新漏れと日別スキーマ崩壊

| 項目 | 記録 |
|---|---|
| 不適合ID | NC-05 |
| 客観的証拠 | manifestは11/18まで、11/19以降のキー差は原本と実装を照合対象化。 詳細は保全監査原本の同ID節。 |
| 根本原因 | RC-3 — 複数の手書き出力と単一schema不在を支持。11/18状態矛盾は訂正根拠が必要。 |
| 暫定処置 | 不正schemaの正式昇格を止め、原本を保持。 |
| 恒久是正処置 | 単一archive writerでschema検証とmanifest更新を一処理にし、全slotのJS normalize通過をCI化。既存補充は出典読戻し後のみ正規化。 |
| 対象コード・設定 | assets/js/report-archive-source.js; assets/js/report-core-v3.js; data/report-archive-manifest.json; archive writer（追加候補） |
| 関連Issue・PR | #103; PR #193〜196（マージ済み表示契約）を維持 |
| 実装状況 | NOT_STARTED / 承認待ち |
| テスト結果 | BTC回帰は修正前FAIL（NC-07）。他の受入試験はNOT_RUN。 |
| 本番検証結果 | NOT_RUN（現状読取は上節参照、修正後受入ではない） |
| 独立監査結果 | 原監査FAIL / 是正後再監査NOT_RUN |
| 残存リスク | 失われたrevisionや原本を推測補完せず、参考表示のまま扱う。 |
| 完了条件 | AT-02 / AT-09を原基準どおり実証し、関連NCの独立再監査で受理されること。 |

### NC-06（重大度: High）GitHub Pages の配信方式競合により、非公開 canonical ファイルが外部露出

| 項目 | 記録 |
|---|---|
| 不適合ID | NC-06 |
| 客観的証拠 | Pages API legacy、PUBLIC repo、SOURCE_ARCHIVED HTTP200を再確認。最新deployはartifact欠損。 詳細は保全監査原本の同ID節。 |
| 根本原因 | RC-5 — 配信方式競合は実設定で確認。latest artifact欠損原因は別途調査。 |
| 暫定処置 | 公開対象棚卸し・許可リスト案を先行、現行公開範囲未変更。 |
| 恒久是正処置 | copytree除外型から明示許可リストへ。artifact生成/受渡しを修復後workflow配信一本化しHTTP404とDOMを検証。GitHub raw公開リスクも評価。 |
| 対象コード・設定 | scripts/prepare_pages_site.py; .github/workflows/deploy-pages.yml; Pages repository setting |
| 関連Issue・PR | #103; PR #90の既存デプロイ安全性案を比較 |
| 実装状況 | NOT_STARTED / 承認待ち |
| テスト結果 | BTC回帰は修正前FAIL（NC-07）。他の受入試験はNOT_RUN。 |
| 本番検証結果 | NOT_RUN（現状読取は上節参照、修正後受入ではない） |
| 独立監査結果 | 原監査FAIL / 是正後再監査NOT_RUN |
| 残存リスク | 設定切替だけではraw/history露出を防げない。旧legacyへの単純復帰は再露出する。 |
| 完了条件 | AT-04 / AT-09を原基準どおり実証し、関連NCの独立再監査で受理されること。 |

### NC-07（重大度: Medium）バリデーション不整合・市場データ欠損・既存ユニットテストの破損

| 項目 | 記録 |
|---|---|
| 不適合ID | NC-07 |
| 客観的証拠 | Markdown照合コードの不整合とBTC回帰FAILを再現。404/ゼロ差は監査の既存snapshot証拠。 詳細は保全監査原本の同ID節。 |
| 根本原因 | RC-3 / RC-4（市場取得はRC-1関連） — タイトル正規化不一致はコードで確認。ゼロ差は真の変化ゼロと比較基準誤りを分離して検証する。 |
| 暫定処置 | 検証ゲートを緩和せず、UNAVAILABLEと休場/ゼロを区別。 |
| 恒久是正処置 | 許容するMarkdown見出しだけ正規化し禁止タグ/必須節を検査。raw hashと正規化hashを明示。前営業日/セッション/限月/単位検証、BTC parserとmissing整形を修復。 |
| 対象コード・設定 | scripts/report_source_contract.py; scripts/fetch_market_data.py; scripts/build_market_json.py; scripts/repair_btc_24h_change.py; config/market_data_sources.json |
| 関連Issue・PR | #205 / #176 / #103; PR #201→#204→#206のstack維持、#94との取得器重複比較 |
| 実装状況 | NOT_STARTED / 承認待ち |
| テスト結果 | BTC回帰は修正前FAIL（NC-07）。他の受入試験はNOT_RUN。 |
| 本番検証結果 | NOT_RUN（現状読取は上節参照、修正後受入ではない） |
| 独立監査結果 | 原監査FAIL / 是正後再監査NOT_RUN |
| 残存リスク | 有効なゼロ差を一律排除しない。raw本文hash契約の無断置換を避ける。 |
| 完了条件 | AT-01 / AT-02 / AT-03 / AT-05を原基準どおり実証し、関連NCの独立再監査で受理されること。 |

## 承認に供する実装順序・費用・リスク・ロールバック

以下は提案であり未実装。各Phaseのコードレビュー用branch/PRと本番適用を分離する。新規修復プロジェクトや重複Issueは作らず#103を全体追跡、#176を上流、#205を取得/Cloud Run、#222を画像/通知の追跡先とする。外部へのコメント投稿は今回未実施。

| 順序 | 実装単位・変更対象 | 事前条件と試験 | 承認が必要な操作 | 費用・リスク | ロールバック |
|---|---|---|---|---|---|
| Phase 1A | NC-01: schedule由来の期待枠、stale/degraded、NO_OPと実配信成功の状態分離、Portal警告 | 平日各枠前後、週末、月曜朝、未公開/同一旧版、独立market feedを回帰。AT-03 | まずローカルコード/fixture。main適用・公開は別承認 | 新規クラウド費用なし。既存CI使用量。古い正常フラグの復活に注意 | code revert。ただし停止告知を保持し誤正常表示へ戻さない |
| Phase 1B | NC-06: Pages許可リスト、artifact生成/受渡し、実配信方式一本化計画 | 非公開JSON/証跡/運用資料を含まないartifactの全ファイル検査、assets依存・本文DOM回帰。AT-04 | Pages workflow設定切替・deploy、repo公開方針の変更 | CI/hosting既存枠。切替停止・raw閲覧リスク | 最後に検査済みallowlist artifactを再配信。legacyへの自動復帰禁止 |
| Phase 1C | NC-01/03: 独立監視・通知 | 通知先/経路/責任者とSLAを確定し隔離FAILを発生、実到達証拠。AT-10 | 実通知送信・通知先/secret設定・外部監視基盤 | 通知サービス料金は未見積、無料枠を保証しない。誤通知/秘匿情報流出 | notifier無効化・既存監視継続、運用者の手動監視へ |
| Phase 2A | NC-04/05/07: 本文タイトル・禁止タグ・必須節・hash契約、単一archive writer+manifest | raw本文保全、正規化を共有、raw/normalized hashを別名管理、schema/JS normalize全件回帰。AT-01/02 | 本文作成タスク更新、既存Drive/参考archiveの変更は別承認 | ローカルは追加費用なし。hash移行/原本喪失/誤昇格リスク | writer停止、Git差分revert。原本/revisionを保持し本番データを一括巻戻ししない |
| Phase 2B | NC-03/04: PNG取得・品質・保存・転送・公開の工程統合 | GASの本番機能/実トリガー保全が前提。identityとbytes/品質の独立判定、AT-06〜09 | Drive書込・GAS廃止/トリガー変更・PNG正式公開・認証権限変更 | 品質判定/renderer/APIの料金未見積。必要機能欠落/二重保存リスク | 新経路停止、既存機能保全、未検証画像はREADYにしない |
| Phase 3A | NC-02/07: #205/#206を再利用して28項目×既存取得器×session×保存列を固定、404/前日比較を是正 | #201→#204→#206の差分と#94の重複評価、取得元別LIVE sampleとcalendar fixture。AT-01/05 | 本番Sheets書込・source契約/有料API追加 | ソース利用条件・API料金未確認。誤営業日/同一値比較/限月混同 | 未検証値をUNAVAILABLE、既存行/式を保持。新取得器停止 |
| Phase 3B | NC-02: OIDC Scheduler→Run直接実行の隔離1枠、create-only claim・重複防止・GCS世代固定readback | 既存Cloud Run試験を流用、T-15〜T未満・起動遅延<2分・main確定を各段階計測。AT-05 | GCP配備、Scheduler/Run/IAM/Secrets/課金資源変更。枠時刻変更はしない | 実構成/region/頻度/retention確定後に見積、現時点UNKNOWN | 新job停止、旧cronは実証と承認まで無効化しない。競合時はfail closed |
| Phase 3C | 109 workflowsの依存・所有者・必要性・廃止可否の確定 | workflow-inventory.csvを担当者確認、workflow_run/dispatch/共有script/外部caller含む依存確認 | 有効化/無効化・cron変更 | 必要経路の誤廃止・duplicate。件数だけで遅延原因を断定しない | 1件ずつrevert、窓外の遡及実行禁止 |
| Phase 4 | 原AT-01〜12の段階受入 | 単体→1枠live→平日4枠→10営業日40枠。手動復旧枠と自動成功枠を別集計 | 本番live試験・故障注入は隔離枠のみ、切替承認 | 40枠の観測期間が必要、休日定義は既存平日slotsと市場休場を区別 | 問題Phaseを停止、履歴/原因/復旧証拠保持、無障害連続観測を別管理 |

推奨する次の承認単位はPhase 1A/1Bのローカルコード・fixture・レビュー用差分まで。本番適用、Pages設定変更、通知送信は含まない。計画承認時に担当、対象commit、費用上限、通知先、試験枠を確定する。

## 影響文書マトリクス

Phase 0は実装仕様/本文構成を変えず、下記固定パスへ同一IDで本台帳と未実施状態を追記。日付/版付き要件・仕様・運用書は追加しない。

| 文書 | 固定GitHubパス / 固定Docs ID | 今回変更・今後の影響 |
|---|---|---|
| 要件 | docs/system/requirements.md / 102PMtKQ4DaXqV1G2RhE8vFtQ8qes-tvIvy2jYQda_xA | Phase 0追跡。Phase 1鮮度・公開範囲、Phase 2 identity、Phase 3定時性、Phase 4受入 |
| 仕様 | docs/system/specification.md / 1qL7f3yKwghuDb5PiAI3RhwFJUVUfLwGakC8z8EOJ9oI | Phase 0追跡。共有schema/hash/工程状態/許可リストを実装と同時更新 |
| 本文作成指示 | docs/system/README.mdの参照 / 1M9LzxKgg8Y50uHSzE1OhML-lU-ufPhvh79xj_m1jWYQ | 本文構成・図解構成・分析項目は変更なし。Phase 2でタイトル/禁止タグ/必須節/保存前検証を同時反映 |
| 運用 | docs/system/operations.md / 1OUVDAMjv009VWlI48Jb8TVuzszy4TIkjgBrHlzbNxYg | Phase 0限界、段階承認、工程別証跡、通知/rollback/観測を同時更新 |
| 文書台帳 | docs/system/DOCUMENT_CONTROL.md / 1F5vH9_O0LUC9Dki0CNm1JDNVfg7gMYMcUCIxgeanE5g | 原本保全/同ID/未同期を記録 |
| 引継ぎ・証跡 | HANDOFF.md / docs/project-control/EVIDENCE_LEDGER.md | baseline、branch、原監査/再確認/未実施を区別 |

固定Docsの現revision/全文読戻し・同ID追記はNOT_RUN。アクセスできない文書を更新済みと扱わず、履歴のrevisionを現revisionに流用しない。管理folderの404だけで各固定Docsの不存在を推定しない。

## 受入管理

原監査RC-1〜RC-5の定義は保全原本第4節、AT-01〜AT-12の定義は第7節をそのまま基準とする。ID/原基準の改訂なし。

| AT | 是正との対応 | 今回の状態 | 合格証跡の保存先/必要証拠 |
|---|---|---|---|
| AT-01 | NC-07 | FAIL: 対象2tests中1FAIL。全suite NOT_RUN | commitと依存lock、Python/Node全件ログ |
| AT-02 | NC-04/05/07 | NOT_RUN | 契約/全archive schema/JS normalize結果 |
| AT-03 | NC-01/07 | NOT_RUN（現状不具合再現） | 予定枠境界fixture・生成JSON |
| AT-04 | NC-06 | FAIL: legacy / SOURCE_ARCHIVED HTTP200 | 設定API、allowlist artifact、live HTTP404 |
| AT-05 | NC-02/07 | NOT_RUN | Scheduler/Run開始、FETCH、T前main commit・hash |
| AT-06 | NC-04 | NOT_RUN | 実Docs ID/親/revision/文字数/本文hash |
| AT-07 | NC-03/04 | NOT_RUN | PNG byte/hash/品質評価者証跡/Drive親 |
| AT-08 | NC-03/04 | NOT_RUN | canonical/receipt/3投影のidentity/hash一致 |
| AT-09 | NC-01/03/05/06 | NOT_RUN | 両画面DOM・本文一致・自然画像寸法・画像hash・console |
| AT-10 | NC-01/03 | NOT_RUN | 隔離故障時刻/検知/実到達・受信確認 |
| AT-11 | 全NC | NOT_STARTED | 同一平日4枠、各工程の独立証拠 |
| AT-12 | 全NC | NOT_STARTED | 10営業日40枠の自動成功と復旧を別集計 |

AT-12原文の「40/40」または「障害復旧実証」は原文のまま保持するが、復旧実証を40枠連続無障害と表現しない。受入者に判定区分を提示する。独立監査の再実施は開発者の自己判定で代替しない。

## 未解決事項・引継ぎ

実装承認、Drive本番原本/固定Docsの現在revisionと同期、GAS実トリガー/実行履歴、ChatGPT実タスク/通知履歴、通知先とSLA、GCP現在構成/費用、workflow責任者、raw公開許諾、最新deploy artifact欠損の詳細原因が未解決。GitHubへのpush/PR/main統合は未実施。コード修正完了、全テスト合格、本番復旧、独立監査合格はいずれも主張しない。


## Phase 1A・1Bの実装・検証記録（2026-11-24 JST）

同一変更ID MR-AUDIT-CAPA-20261124-01。ユーザーの後続承認によりローカル実装へ進んだ。現在の作業branchは `codex/audit-capa-phase0`、基準SHAは前記main。提出対象はコード・回帰・固定文書と保全資料。市場データ、レポート本文、PNG、receipt、枠前証拠は未変更。

| 対象 | 最新状態 | 実装/制約 |
|---|---|---|
| NC-01 / RC-4 | LOCAL_IMPLEMENTED | 共通schedule鮮度、NO_OPとdelivery状態分離、診断保存後の鮮度failure、両画面毎分警告。通知はPhase 1CでNOT_STARTED |
| NC-06 / RC-5 | LOCAL_IMPLEMENTED / PRODUCTION_NOT_CHANGED | 明示許可リスト、private tree除外、公開資格維持、Pages modeの読取ガード、同run artifact_id読戻し。設定はlegacyのまま、AT-04 live 404未達 |
| NC-07のmissing整形 | LOCAL_IMPLEMENTED | missingRequired空配列時にmissing=を出さない。他のparser/市場取得/本文契約は未着手 |
| NC-02/03/04/05、NC-07残項目 | NOT_STARTED | Phase 2/3と既存Issue/PRで継続 |

変更コード: scripts/report_delivery_health.py、sync_latest_report_publication.py、build_market_json.py、prepare_pages_site.py、verify_pages_artifact.py、config/pages_public_files.json、両HTML、共通警告JS/CSS、既存sync/deploy/health CI。固定要件/仕様/運用/文書台帳/本文作成参照索引/HANDOFF/Evidence Ledgerを同IDで追補。本文作成の内容・分析・レイアウト変更なし、固定Docs同期は404によりNOT_RUN。

[Phase 1証拠](archive/independent-audit/pr-validation.json)はローカル成果物/DOMと回帰を区別。AT-03相当の境界/再同期/独立market回帰を実施。AT-04はローカル隔離のみで、本番mode変更・HTTP404は未実施。AT-09全体（画像/正式新枠/公開URL）はNOT_RUN。ローカルDOMは既存本文の表示と遅延警告の両立確認に限定。

rolloutは未実施。今後は差分レビュー→固定Docs同期→明示された本番適用承認→Pages mode切替/許可リストartifact配信→live HTTP/DOM読戻し。GitHubへのpush/PR作成は今回未実施。新通知先、IAM/GCP/請求、GAS/ChatGPT実タスクは変更していない。修正前のBTC回帰FAILと監査原本の判定は保持する。

### ローカル検証結果

- 関連Python回帰60件PASS（新規11件を含む。schedule境界、NO_OPからの陳腐化、独立異常の保持、公開隔離、artifact ID・workflow順序、既存publication/receipt契約）。全Python suiteの合格を示すものではない。
- ポータルNode回帰32件PASS（既存29件＋新規3件）。変更した3本のworkflowはYAML構文読取成功。
- 実リポジトリから許可リストartifactを組立。docs/scripts/apps-script/receipt/evidence等を除外、SOURCE_ARCHIVEDをコピーせず、元ファイルは保持。HTML静的依存確認で実参照の欠損なし（テンプレート文字列2件は動的URL）。
- ローカルEdgeの両ページで遅延警告、現在枠のfixtureでは非表示、メタデータ503では未確認警告を確認。選択した過去正式本文のタイトルと表示、dashboard読込は別途DOM記録を参照。初回の読込後dashboard待機は誤ったdatePickerセレクターでtimeout、実HTMLのdateInputへ訂正して再検証。試験失敗を本番障害の原因としない。
- Windows依存のtzdata不足を隔離target導入で解消して再実行。Playwrightも隔離導入、既存Edgeをheadless使用。作業用依存は.gitignore対象、公開artifactにも含まない。

本番適用/Pages mode切替/実artifact upload-readback/変更後live DOM/通知/独立監査はNOT_RUN。今回のローカル結果だけでNCをクローズしない。


## MR-AUDIT-CAPA-20261124-01｜Phase 1A・1B PR準備（2026-11-24 JST）

ユーザーのPR準備指示に基づき専用branch `codex/audit-capa-phase1ab` をmain `437a63c23bb7f979fd663c824dec1fa8a5941d1d` から作成。開始時31ファイルはPhase 0保全資料/台帳とPhase 1A/1Bに対応し、無関係な未コミット変更なし。元branchの履歴を保持、全31ファイルのSHA-256を切替後に照合。既存packed-refs.lockは変更せず、branch/HEADを独立確認。upstream変更11データファイルとの重複なし。

同じ60件Python/32件Nodeを再実行し合格。全テスト名・環境・ログは `docs/project-control/archive/independent-audit/pr-validation.json` と `pr-python-tests.log` / `pr-node-tests.log`。許可リストartifactは1,074ファイル、430参照を検査して新規欠落0。元sourceにも存在しないdata/reports.json参照2件は残課題として区別（pr-public-dependencies.json）。同じ60/32件と依存検査を既存health CIへ接続、新規の監視タスクは追加しない。

今回許可された外部操作は専用branchのpushと独立レビュー用PR作成。mainへのマージ、Pages設定/配備、Drive固定ID/原本、GAS/ChatGPTタスク、課金/権限拡大は実施しない。コード/文書のGitHub取得を受入とし、本番復旧や独立監査合格と表現しない。PR/最終HEAD/hosted CIの実測はPR本文とレビュー提出記録を参照する。

### 独立レビューの対象と本番反映手順

1. 変更要求ID・全NCとの対応、92件のテスト名と実行範囲をレビューする。全Python suiteの合格とは認定しない。
2. 期待枠境界（JST平日08/12/16/21、週末、月曜朝）、同原本NO_OPでも遅延を再評価すること、独立market healthを誤解除しないことを確認する。
3. 許可リスト静的ファイル・履歴collection・archive manifestの公開許諾と欠落を確認する。Pagesから除外してもPUBLIC repoのraw/履歴には残る。
4. build_type=workflowの読取ガードとartifact ID/name/size/expiry/同run照合を確認する。upload成功後にlistが空になる内部原因はUNKNOWNで、今回のガードを根本原因解消とは呼ばない。
5. 本PRを独立レビューする。本番反映の明示承認後に固定Docs同期/現revision読戻し、main統合、Pages mode切替と配備を管理者が段階実行する。legacyのまま新workflowを動かすと意図どおり停止するため、切替順序を事前確定する。
6. 非公開canonicalのlive HTTP404、両画面DOM/本文/画像、異常表示を別々に読み戻す。Docs/PNG永続保存と再試行はPhase 2、通知到達はPhase 1C、定時4枠/40枠と独立再監査は未実施。

ロールバック: 本番未適用の現在はPRを戻せばよい。承認後の本番で問題が出た場合は変更SHAをrevertし、最後に検証済みの許可リストartifactを再配信する。legacyへの自動復帰や停止警告の撤去は行わない。原本・receipt・evidenceを変更/再構成しない。


### 公開PRへの証拠範囲（自動承認レビューを受けた縮小）

公開リポジトリへ監査原文・詳細issue/runtime証跡・全ログ・workflow棚卸しをまとめて転送する操作は、自動承認レビューが公開範囲不明確として拒否した。これらは削除せずローカルに保持し、本PRから除外する。原資料は既存Driveの固定ファイルを参照し、audit-source-index.jsonには名称/byte数/SHA-256と既存Driveリンクだけを収録する。元のPhase 0/1検証記録は実施時の履歴であり、そこにあるローカル証跡名をGitHubへ公開済みと解釈しない。

独立レビュー用に公開する証拠はpr-validation.json（全60/32テスト名・結果・環境・コマンド）とpr-public-dependencies.json（公開assetの430参照・新規欠落0・既存欠落2）に限定する。詳細な機械ログ、監査原文、workflow inventoryはローカル保全。是正台帳・仕様/運用の既存固定文書は本修正の説明に必要な差分だけを含める。raw市場本文、資格情報、ユーザー実タスク内容を追加公開しない。


### PR提出記録（MR-AUDIT-CAPA-20261124-01 / 2026-11-24 JST）

独立レビュー用Draft PR: https://github.com/matrixdiamond512-cell/Chat-GPT-Market-Report/pull/229 。専用branch `codex/audit-capa-phase1ab`、実装/ローカル試験対象commit `f2bcebd4cd24d548ccb5eceabdcef418e768d4fe`。GitHub APIでAUDIT_CAPA.mdのblobを独立取得しローカルGit blobと一致確認。公開30ファイル、監査原文・詳細runtime/issue証跡・全ログ・棚卸しはローカル保全で非提出。PRはOPEN/Draft・未マージ。hosted CIの最終状態はPRの同head Checksで確認し、ローカル92件の合格とは分離する。今回はPages設定/配備・Drive正本・ChatGPTタスクを変更しない。


## MR-AUDIT-CAPA-20261124-01｜PR #229 レビュー6034576678への修正（2026-11-24 JST）

対象head a8e01a4322a6d37d2ad3c377dbfbac6e587bf0c2のREQUEST_CHANGESを直接読戻した。P1対応としてreportDeliveryをslotFreshness（日時のみ）、formalPublication（canonical/receipt/indexの実読取照合）、pagesDisplay（NOT_VERIFIED）へ分離。MARKET_REPORTS_JSON.statusを鮮度から正常にせず、正式証拠のverified/unverified/failedへ変更。現在枠でもreceipt欠落・SOURCE_ARCHIVED・Docs読戻し失敗・latestReport欠落では配信成功/警告解除にしない。Pages表示は静的JSONやCI成功から昇格させない。

既存Python60件/Node32件に加え、Python8件/Node2件の負例・証拠の正例を合格。review-validation.jsonにテスト名/環境/結果を記録。原監査・詳細ログはローカル保全を継続し公開しない。AT-04の本番mode変更/非公開URL404は引き続きNOT_RUN、独立再レビューと本番適用は別判定。Phase 2は保存前の原本保全・Docs/PNG独立再試行の接続点を調査し、read-only importerだけではwriter障害を直せないことを確認。既存writer候補を再利用評価し、別branchのローカル実装として進める。


P2追加検証: 許可リストartifact上の主要11画面（dashboard/report/stocks/events/rates/USDJPY/gold/Nikkei需給/裁定/USDJPY出来高/Drive参照）で動的fetchを実行。今回観測した新規404・source既存404・pageerrorは0。両画面に現在枠かつreceipt未確認のdashboard fixtureを与えても警告が表示されることをDOMで確認。review-dynamic-smoke.jsonはローカル検証の要約であり、本番切替受入・全動的分岐の網羅を意味しない。


レビューP1補強（同変更ID / 2026-11-24 JST）: slotFreshness.scope=TIMESTAMP_ONLYを明記。正式本文のcanonical/receipt/indexが合格してもPagesはNOT_VERIFIEDのまま、dashboard全体はokへ昇格せずpartial/PAGES_DISPLAY_UNVERIFIEDとする。正式本文証拠と全工程配信成功を区別する追加正例を含め、既存92件＋追加10件を再実行して合格。Phase 2ローカル基盤は別branch codex/audit-capa-phase2-storage、commit 28165dbcb6714cfe0419d18acc7467546cf3a571に保全し、PR #229へ含めない。実writer接続・本番保存は未修復。
## MR-AUDIT-CAPA-20261124-01｜Phase 2原本保全・再試行基盤の着手（2026-11-24 JST）

別ローカルbranch `codex/audit-capa-phase2-storage`、基準はPR #229レビュー対応commit b246008126ffdb39b163a05bd9067a70fd9342fa。scripts/reporting/delivery_spool.pyとtests/test_delivery_spool.pyを追加。実Google/GitHub adapter、タスク、trigger、Pages、課金、固定Docsは未接続/未変更。この変更をPR #229へ混入させず、push/PR作成もしていない。

外部writer呼出し前に原文UTF-8 bytesをSQLiteへcommitし、同一reportId/revisionでの改変を拒否。生成PNGも本文hashへ結び付けて保全。Docs/PNGのcheckpointを独立させ、一方の保存失敗で他方の成功や原本を失わない。writerがreferenceを返した後の読戻し失敗ではそのreferenceだけを再読込し、再作成しない。writer timeout/成否不明ではUNKNOWNとして二重作成を遮断し、再開は外部writerによる照合/復旧手順が必要。転送readbackを正式publication/PNG品質/Pages合格へ昇格しない。

ローカルfixture6件PASS: 再起動後の原本保持・同revision上書き拒否、Docs失敗時の本文保持/二重write拒否、readbackだけの再試行、Docs失敗時のPNG独立保存、成功工程の再実行抑止、PNG不変性と品質未判定。初回はSQLite connection解放漏れをWindowsで検出し、closeを保証するcontext managerへ修正後に全件PASS。

残課題: provider側の冪等key/重複照合、UNKNOWN復旧、月別folder/親ID/Docs全文revision読戻し、PNGの視覚数値品質、既存producerとの接続、本番の永続ストレージ配置と実権限検証。同期ドライブ上のSQLiteやコンテナ一時FSを本番保存先と決めたものではなく、保存backendは未選定。本モジュールだけで11/24のDocs/PNG保存障害が修復したとは主張しない。次は既存producer入力→永続原本→認証済writer/readbackの接続を隔離環境で実装・受入する。

### Phase 2実writer接続PR準備（2026-11-24 JST）

ユーザー指定のPhase 2優先順位に基づき、公開済み基盤 `28165dbcb6714cfe0419d18acc7467546cf3a571` から専用branch `codex/phase2-google-writer` を作成。PR #229のP1修正は未取込であり、Phase 2差分は #229 branchをbaseにした独立stacked PRとして提出する。Docs本文とPNGのDrive writer、Drive読戻し、隔離TEST_ONLY folder制限、CLI、モックCIを追加。成功済みlaneは再利用し、作成結果不明時は照合できるまで重複作成を停止する。本文生成、発行時刻/枠、正式公開、Pages、GAS、既存Drive原本は変更しない。

CI run `45349333730` はspool 14件、writer mock 6件をPASS、CLIは1/2件PASS。残る失敗はspool pathの拒否文とテストregexの不一致。実装fail-closed文言に合わせるテスト修正、および固定文書への要件/運用/仕様追記をローカル作業中。この修正のCIはNOT_RUN。Google Docs/PNGのPython実writerによる実Drive保存・読戻しは未実施であり、connector試験でも代替しない。独立レビュー後に利用可能な隔離フォルダーと認証主体を確認して別受入とする。PR作成後もmerge、本番書込み、本番切替は行わない。
