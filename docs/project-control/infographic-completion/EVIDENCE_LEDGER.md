# 再開・固定16パネルの証拠台帳

Run ID: `infographic-completion-resume-20261014`。Timestamp: `AUDIT.json`のUTC時刻（表示日は2026-10-14 JST）。環境: Windows、Python 3.12、Edge 155.0.4283.45、device scale 1、locale ja-JP / Asia-Tokyo。

| Claim | Evidence | Level | Result | Limit |
|---|---|---|---|---|
| 保存済み成果を再利用 | PR初期head 8d98868、ローカル92c738eと4時刻キャッシュを発見 | E0/E5 | PASS | 切断前の未保存メモリは復元不能 |
| 最新mainの安全な取り込み | a47ca3e、3ec46ff、a3c3ec6をmerge。43f97b3の撤回を保持。旧08:00 workflow削除に合わせ承認デザイン専用workflowを追加 | E0 | PASS | mainへのマージ/公開なし |
| 共通CI競合の両側を保持 | 92c738eの両親との差分を確認。共通2ファイルはorigin/mainと同一。公開ゲート回帰、CI内Node3ブロック、PR#97の公開前検証を実行 | E0/E1/E3/E5 | PASS | 外部データ復旧・正式公開を証明しない |
| 添付デザイン正本の同一性 | ZIPとPNGのSHA-256一致。AUDIT.json/layout.json | E0 | PASS | 正本内の誤値は採用しない |
| 全本文・数値の転記 | 原文位置の全非見出し文字被覆、Decimal raw値/符号、DOM各fact/token完全一致 | E2/E4 | PASS / 数値トークン1076件 | 市場価格の真実性・独立クロスチェックではない。日時/条件値も含む |
| 4時刻の描画 | source-lock/HTML/render-contract/PNG/render-receipt | E4 | PASS、16パネル・6市場、文字切れ/外側描画/カード重なり/色エラー各0 | 3時刻は撤回済み履歴。物理端末NOT_RUN |
| 768px専用表示 | mobile PNG/receipt | E4 | PASS、最小fact文字14px | PC PNGを縮小しただけの画像とは別。実スマートフォンはNOT_RUN |
| 確定できるイベント予定 | BLS/Census公式日程、Census PDFのEDT表記、日付別DST変換 | E2/E5 | CPI/PPI/小売予定時刻を追補確認 | 原本作成時の確認・発表実績を証明しない。銀行時刻/重要度/影響市場の確定は未完了 |
| 数値/限月/時刻/本文/時系列/15番/正本の負例 | test_approved_layout.py、実ブラウザ負例 | E1/E3/E4 | PASS / 誤記・15番欠落・重なりはPNG保存前に拒否 | 独立市場データの照合範囲ではない |
| 既存renderer回帰 | 保存済み10/12レビューHTMLを再描画 | E4 | PASS、43facts、PNG hash `ff76043361881e404866ca020fe804ab5ac9796ba700507f582eaf167193139d`一致 | 元ファイル未上書き |
| Python回帰 | unittest discover -s tests -q | E1–E3 | PASS 237件（新19件） | 初回213件は依存不足5error/旧土曜期待1FAIL。jpholiday/tzdata導入、現在の週末新規停止にテストを整合 |
| 既存公開・署名・原本復旧・watchdog回帰 | TEST_RESULTS.json、共通CI3ブロック、Drive PNG readback fileId不一致負例 | E1–E3 | PASS | Drive/Git/Portalはモック。実公開NOT_RUN |
| 正式生成 | 4時刻preflight.json | E0/E1 | BLOCKED | 市場snapshot・identity・既存本文/spec契約不足。3時刻は現在の原本欠損 |
| 正本との視覚比較 | comparison PNG/各時刻の詳細切り出し、作成者目視 | E4 | PENDING / 差異あり | 配置骨格は同じでも縦長・図記号・密度等の再現が未完了。視覚合格としない |

各時刻のサイズ・ハッシュ・source statusは `docs/examples/approved-infographic/review-20261014-withdrawal-aware/render-summary.json`。4時刻の原文hash/revision/snapshot欠損と市場履歴取得時刻は `AUDIT.json`。

正式生成・独立市場検証・正式manifest接続・現行4時刻原本からの受入・実端末・Drive/Portal保存/再読取は未完了。完了報告は禁止。

Diagnostic disposition: KEEP ローカルの試行画像と初回browser sandbox failure。コミットは最新レビュー画像・正式停止監査・必要テストに限定。恒久的loggingや設定回避を追加しない。

## 継続受入 run — 2026-10-14

Run ID: `infographic-acceptance-20261014`; environment: Windows, Python 3.12, Edge 155.0.4283.45.

| Claim | Evidence | Level | Result | Limit |
|---|---|---|---|---|
| 4時刻の設計比較 | 承認PNGと4 PNGの全体画像を目視比較、contact sheetを保存 | E4 | NOT_ACCEPTED | 縦長、空白、図像密度、パネル4の視覚差が残る |
| 4枚の描画 | 各最終render-receipt.json | E4 | Renderer PASS / numeric UNVERIFIED / DEBUG_PREVIEW | 正式受入またはsource number検証を示さない |
| 新しい市場snapshot取得 | 新規10/14 16:00 acquisition payloadとtyped snapshot | E1/E2 | required 6 instruments verified, no fallback/missing required | secondary 16 errors; external truth independently unverified; no canonical/Drive write |
| 新規report/spec正式接続 | `reports/2026-10-14_16-00.json`, G0/G1/G2, source-locked spec/prompt and strict preflight | E1/E2 | PASS; 30 structured panels, 49 numeric tokens; exact line-hash provenance for body facts; snapshot-field provenance for price/change/changePct | test-only body; no event ingestion; no real investment assessment |
| 新規approved projection / local manifest | commit-pinned current Git source, `panel-manifest.json`, numeric registry, render contract and Edge receipt | E4 | Renderer PASS; 16 panels, 6 primary markets, no overflow/outside/overlap; local panel manifest created | `DEBUG_PREVIEW`, numeric validation `UNVERIFIED`, publication manifest NOT_CREATED; G3/G4 NOT_RUN |
| 回帰テスト | `python -m unittest discover -s tests -q` and 3 Node regressions on 2026-10-14 | E1–E3 | PASS 240/240 + independent publication/Apps Script gate/source-recovery tests PASS | Hosted CI on latest code pending rerun |
| GitHub/Driveの最終副作用 | current PR metadata and actions | E5 | no merge/publish/Drive save action taken | PR OPEN/Draft reconfirm after latest push; G3/G4 NOT_RUN |

正式受入資料と4時刻PNG: `docs/examples/approved-infographic/ACCEPTANCE-20261014.md`; comparison: `docs/examples/approved-infographic/review-20261014-design-final/comparison-contact-sheet.png`。旧4時刻の原本/snapshot不足は前段の監査結果を維持し、後日snapshotで穴埋めしない。

## Latest main + canonical test isolation — 2026-10-14 05:20 UTC

| Claim | Evidence | Level | Result | Limit |
|---|---|---|---|---|
| 最新main統合と停止ゲート維持 | `origin/main` `931dd9b53a04b85a32ee59a8ca61bf4a3fb51188`; merge `b4422cac20987b2eb2dfc970995478afb01ff62a`; conflict diffs for requirements/test contract | E0/E1 | PASS | PR branch merge only; no main merge/deploy |
| publication workflow safeguards | Main-only triggers checked in build-reports/deploy-pages/sync workflows; exact latest/canonical/index/dashboard verifier retained | E0/E2 | PASS | No externally triggered workflow executed |
| canonical index stability | `verify_publication_consistency.py`, `validate_report_index.py`, then `build_reports.py` | E1/E2 | PASS; 164 indexed/canonical entries, zero builder worktree changes | Does not prove external publication |
| TEST ONLY report isolation | source byte SHA `8d044ab59c6a0406e57af391dce707fe92f0fdf3b71f68738bb87123eb3eaae3`; moved from canonical `reports/` to `new-report-test/source-report.json` | E0/E1 | PASS | Existing render evidence points to the source commit where the test was generated |
| post-integration regressions | Python unittest discovery; 3 Node publication, Apps Script gate, and 16:00 source-recovery regressions | E1–E3 | PASS 250/250 + Node 3/3 | Hosted CI on final head not yet checked |
| PR scope/state | local merged head `b4422ca`; no merge/deploy/Drive save invoked | E0 | Draft/open intent retained | GitHub status must be reconfirmed after push |
