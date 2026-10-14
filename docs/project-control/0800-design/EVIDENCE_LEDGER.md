# 08:00図解調査の証拠台帳

Run ID: 0800-design-investigation-20261013-0154JST
Timestamp: 2026-10-13 01:54 JST
Code version: main 38afca50113cfa9eef39df6b3e51f2acac9b01e7
Environment: Windows PowerShell; bundled Python 3.12 / Node; source isolated clone.

| Claim | Evidence | Level | Result | Limit |
|---|---|---|---|---|
| 既存生成CLIはspec/プロンプトまで | market_report.py、reporting/infographic.pyの実装と呼び出し検索 | E0 | PASS | 稼働ChatGPTタスクや未検索の外部生成元の不存在は証明しない |
| 現行公開受入はidentity/fact/renderer/PNGのmanifestを要求 | MarketReportWebSync.gs、schema、report-core-v3.js | E0 | PASS | 配備版と実外部実行はNOT_RUN |
| 既存図解の安全性baseline | unittest discover -s tests -p test_infographic_validation.py -v | E1/E2 | PASS 23/23 | 初回temp権限エラー5件。作業内TMP/TEMPに変更して再実行。コード修正なし |
| 独立公開状態baseline | unittest discover -s tests -p test_independent_publication_status.py -v | E1 | PASS 6/6 | 実公開を証明しない |
| manifest消費・mock Drive/Git・ポータル回帰 | node scripts/test_independent_publication.js | E2/E3 | PASS | モック環境に限定 |
| 10/09正式入力の可用性 | market_report.py validate-report --report reports/2026-10-09_08-00.json | E1 | FAIL / MARKET_DATA_SNAPSHOT_NOT_FOUND | 最初のゲートで停止。正式再生成BLOCKED |
| 10/12正式入力の可用性 | market_report.py validate-report --report reports/2026-10-12_08-00.json | E1 | FAIL / MARKET_DATA_SNAPSHOT_NOT_FOUND | 保存状態RECONSTRUCTED_UNVERIFIED。正式再生成BLOCKED |
| 新デザインの視認性・情報量・数値一致 | 未実装 | — | NOT_RUN | 画像未生成、768px/スマートフォン未検査 |
| 外部保存・本番生成接続 | 未実行 | — | NOT_RUN | 本番・配備設定・Drive内容未変更 |

Diagnostic disposition: KEEP 調査文書と入力契約不足の記録。恒久的な診断loggingやコード変更はなし。テスト用一時ファイルはコミット対象外。

Git checks: 調査・control文書の通常diff check PASS。原仕様書は元のMarkdown hard break（行末2空白）を含むため通常checkで指摘。原文を変えず、blank-at-eolだけ除外したcheckはPASS。原添付と保存コピーのSHA-256はともに27b33e88ce2dde7b177d7f1b448dab41d38d0b59508658aade2c1229bc630b3b。

External operation: `git push -u origin codex/0800-infographic-design`はauto-reviewが実行前に拒否。理由: 調査資料と貼り付け仕様書の未確認リポジトリへの開示について、今回の調査/報告指示から具体的承認が確認できない。Push未実行、PR未作成。別手段で送信していない。必要なユーザー承認は、対象GitHubリポジトリと今回資料の外部送信。

## 承認後の実装検証 — 2026-10-13 02:47 JST

Run ID: 0800-design-implementation-20261013-0247JST。ユーザーがHTML/SVG実装・manifest接続と対象GitHubへの限定資料送信/Draft PR作成を明示承認。初回auto-review拒否は履歴として保持する。

| Claim | Evidence | Level | Result | Limit |
|---|---|---|---|---|
| 16カード/6市場/142factsを元の文字・数値で描画 | 実headlessブラウザ、render-receipt.json、PNG目視 | E3/E4 | PASS | 合成fixtureのみ。OCR/実市場データ検証ではない |
| はみ出し・カード重なり・正負色 | native/mobile DOM検査、色のRGB実測 | E4 | PASS（各0件） | 任意の将来入力を保証しない。長文fixtureを含む |
| 768px表示 | 同じPNGを768pxで実描画した出力、上部等の切り出し目視 | E4 | PASS（最小文字14px） | 375pxへ標準PNGを縮小して合格としない |
| モバイル用の再配置 | 別PNG幅768px/1列、6市場は2列、目視 | E4 | PASS（ローカル出力） | 実スマートフォン端末はNOT_RUN |
| 再現性 | 同じ入力/環境で2回PNG生成 | E4 | PASS | 別OS/別ブラウザ/別フォント間のバイト一致は保証しない |
| 回帰 | Python unittest discover -s tests -q | E1〜E3 | PASS 135/135（新規22件） | 実外部サービスではない |
| 既存公開処理 | node scripts/test_independent_publication.js | E2/E3 | PASS | Drive/Git/portalはモック |
| producer→既存manifest consumer | mock正式manifestをPythonで構築し既存evaluateInfographicReadiness_へ入力 | E2 | READYを確認、identity/hash改変を拒否 | mock receipt・小さなtest PNGによる構造/契約試験。正式実画像検証ではない |
| 合成画像の公開防止 | 実PNGのDRAFT manifestを同consumerへ入力 | E2/E4 | PASS（NOT_READY） | 外部書込なし |
| 実10/09・10/12 | unchanged CLI/新投影のsnapshot不足テスト | E1 | BLOCKEDを維持 | 正規入力/正式画像比較なし |

標準PNG: 1536×6798、768px版: 768×3399、モバイル用: 768×11024。標準PNG SHA-256（二回一致）: f629c2555bb314c99c40caf639a7c0e4881db2d7b23761cbad7a14b79a615179。
保護範囲: 既存infographic.py、market_report.py、gates.py、取得/公開/ポータル/他時刻コードに差分なし。新規08:00コードとfixture・文書・レビュー用CIのみ。機密/認証値/端末固有パスの対象ファイル検索で該当なし。
Tests NOT_RUN: 正規実レポート、live Drive保存/再読取、live portal、稼働Apps Script配備確認、実スマートフォン、独立OCR/Vision。本番設定・本番画像・mainは変更していない。

GitHub external result: ユーザーの限定送信承認後にブランチ送信成功、Draft PR #97作成・再読取でOPEN/DRAFT/未マージを確認。
https://github.com/matrixdiamond512-cell/Chat-GPT-Market-Report/pull/97

Hosted CI: コードhead ea2071b1438e3bc646a61040100357869670686b のrun 38286902389で、依存導入、既存/新projectionテスト、実DRAFT PNGとmanifest接続、artifact uploadがすべてsuccess。
https://github.com/matrixdiamond512-cell/Chat-GPT-Market-Report/actions/runs/38286902389
Evidence: E4 Linux Chromiumでの合成描画・E2/E3モック契約試験。これによって実Drive/Portal/実レポートが合格になったわけではない。この後の変更はレビュー状態とCI結果の文書記録のみで、描画コード・fixture・PNGは同一。

## 参考画像に寄せた再設計 — 2026-10-13

Run ID: `0800-design-review-iteration-1-20261013`. 追加指示を**CORRECT**として反映。10/09図解を色だけでなく配置・密度・矢印・図解の基準にする。12:00/16:00/21:00、本番画像、snapshot/公開ゲートは対象外。

| Claim | Evidence | Level | Result | Limit |
|---|---|---|---|---|
| 改訂テンプレートに全142 factsを直接表示 | 実Edge PNG + render receipt `docs/examples/0800-design/redesign-review-v1/render-receipt.json` | E4 | PASS、文字列差0 | 合成fixtureのみ |
| 固定16カードと順序、PC 12列、No.13の6市場一列 | ブラウザDOM/座標検査 | E4 | PASS | 実データや全端末の視認性は未確認 |
| 768pxモバイル専用レイアウト | ブラウザDOMと実PNG | E4 | PASS、最小fact文字14px | 物理端末の利用感はNOT_RUN |
| 配色/カード重なり/テキストはみ出し | ブラウザ実測 | E4 | 色エラー0、重なり0、はみ出し0 | 見た目の好み/参考との近似度を機械判定していない |
| 10/09画像とのデザイン比較 | 参考画像と生成PNGの目視比較、[`0800-design-comparison-2026-10-13.md`](../../proposals/0800-design-comparison-2026-10-13.md) | E4 | 差異を記録、受け入れPENDING | 写真調の街並み、縦横比、カード余白等が異なる。ユーザー確認待ち |

レビュー版PNG: `1536×2639`, mobile `768×3391`, SHA-256 `e6da4fb062a4636284f24a828cad57ce2dae7c31253966e8eb66844c268f2cb7`。生成出力と入力は`docs/examples/0800-design/redesign-review-v1/`。すべてDRAFT/DEBUG_PREVIEWの合成fixture。正式画像・snapshot不足判定は変更していない。

回帰テスト: コードhead `28dfa96`（最新PR head `eb15e3f`は記録文書のみ）でPython **176/176 PASS**、`node scripts/test_independent_publication.js` **PASS**、renderer JavaScript構文 **PASS**。最新head上でfixtureからPNGを再生成し、SHA-256も保存PNGと一致。これらは回帰と構造の証拠で、デザイン品質の合格を意味しない。Hosted CI: **NOT_RUN/PENDING**（push後に該当runを確認できず）。Drive/Portal readback: NOT_RUN。

視覚検査: ユーザー受け入れ待ちで未完了。自己比較では全体の色/カード構造/図の種類は基準に近づいたが、画像は基準より縦長、街並みは模式SVG、No.05/06やNo.10/11の行高と余白が異なる。次の必要行動は、ユーザーの画像レビューを受けてデザイン差分を修正し、必要な場合のみ再レビューすること。

## 判読性レビュー版2 — 2026-10-13

Run ID: `0800-design-review-iteration-2-20261013`; direction: user clarified that the city illustration is unimportant and report content must be easier to read.

| Claim | Evidence | Level | Result | Limit |
|---|---|---|---|---|
| fixtureの142 factsと数値を一字も削らず描画 | `docs/examples/0800-design/readability-review-v2/render-receipt.json` の実Edge描画検査 | E4 | PASS、差異0 | 合成fixtureのみ。市場データの事実性は検証しない |
| 固定16項目、12列、No.13の6市場一列 | 同receiptのDOM/位置計測 | E4 | PASS、順序一致、横一列 | モバイルは専用再配置 |
| 判読性向上のため本文領域・文字サイズを優先 | CSS差分と版1/版2の実PNG目視 | E4 | 作成者目視: 市場データの値/時点と6市場の価格/条件が大きく追いやすい。ヘッダー図を縮小 | ユーザーによる視覚合否はPENDING |
| 描画異常と色分け | receipt | E4 | overflow 0、outside 0、重なり0、色エラー0 | 目視の好みや任意端末差を保証しない |
| 768px表示 | desktop fitted image + 768px responsive PNG | E4 | PASS、専用モバイルの最小fact文字15px | 実端末はNOT_RUN。縮小確認画像の文字が小さいことは確認用出力の性質 |
| regression | 最新コードで`python -m unittest discover -s tests -q`; `node scripts/test_independent_publication.js`; `node --check scripts/render_morning_png.js` | E1〜E3 | PASS 176/176 + publication regression PASS + syntax PASS | 外部Drive/Portalを検証しない |

版2: PNG `1536×2629`; responsive mobile `768×3352`; SHA-256 `89ba60b2962771ad6f4945549e3fab5c34ca84f767fce7b64feb56c328e1cc19`; artifacts `docs/examples/0800-design/readability-review-v2/`。4/12幅はNo.05/06/07、6/12幅はNo.08/09/11/12、全幅はNo.10/13、最後はNo.14/15が3/12・No.16が6/12。市場条件18px、価格22px、判定19px、見出し20px、市場データ値18px/時点16px。

BLOCKEDのまま: snapshot不足の10/09・10/12正式レポート生成。未実施: 実スマートフォン、Drive/Portal外部readback。デザイン受け入れは画像確認後に更新する。PRはDraftのまま維持し、main・本番・自動公開は変更しない。

## 保存本文レビュー候補 v3 — 2026-10-13

Run ID: `0800-source-content-review-20261013`; direction: 利用者は保存済み10/12本文を「未検証と明記」してデザイン確認に用いることを選択。以前の合成fixture画像では内容をレビューできないと訂正。

| Claim | Evidence | Level | Result | Limit |
|---|---|---|---|---|
| 保存済み本文を未検証プレビューに描画 | `scripts/build_morning_unverified_review.py` + `docs/examples/0800-design/content-review-2026-10-13/report.html` | E1/E3 | PASS、43表示fact。全画面に未検証/公開不可を明記 | 入力`RECONSTRUCTED_UNVERIFIED`。個々の表示fact一致は検査したが市場真実性は未確認 |
| 16カードの順序とPC複合グリッド | content-review `png/render-receipt.json` の実Edge DOM/位置 | E4 | PASS、01〜16、12列、No.13全幅で6市場一列 | 10/09との人手による正式合否は未確定 |
| PNGの表示品質/768px | 同receipt、PC PNG `1536×1470`、mobile PNG `768×2297` | E4 | PASS、fact差分0、文字切れ/外側描画/重なり/色エラー0、モバイル最小文字15px | 画面上での作成者目視のみ。物理端末NOT_RUN |
| 数値/文章の由来 | source `reports/2026-10-12_08-00.json`。参考画像の値は入力に使っていない | E2/E4 | PASS、表示factは保存本文から直接生成 | snapshot未照合。正式値とは扱わない |
| 正式生成ゲート | `python scripts/market_report.py validate-report --report reports/2026-10-12_08-00.json` | E1 | BLOCKED/FAIL `MARKET_DATA_SNAPSHOT_NOT_FOUND` | 条件緩和なし。レビュー用ビルダーはsnapshot/manifestを生成しない |
| regression | `python -m unittest discover -s tests -q` (`TEMP/TMP=.test-tmp-0800`); `node scripts/test_independent_publication.js`; `node --check scripts/render_morning_png.js`; `git diff --check` | E1〜E3 | PASS 176/176 + publication regression PASS + syntax/diff PASS | 外部Drive/Portal/hosted CIは未確認 |

差異: 10/09参考の写真調夜景は使わず、ヘッダーは簡素な濃紺。参考の画像比率はより横長。パネル表現・アイコンの種類、余白と密度は引き続き異なる。今回の16項目構成を優先したため内容見出しも異なる。候補: `docs/examples/0800-design/content-review-2026-10-13/`; PNG SHA-256 `ff76043361881e404866ca020fe804ab5ac9796ba700507f582eaf167193139d`。デザイン受け入れPENDING。正式再生成はBLOCKEDを維持。PR #97はDraftのまま。次の必要行動はこの画像に対するユーザーのデザイン確認。

## 2026-10-14 continuation — E2E body divergence and 08:00 fixed-layout fit

Run IDs: `e2e-body-identity-20261014-1600-audit`; `0800-fixed-layout-fit-20261014`.

| Claim | Evidence | Level / result | Limit |
|---|---|---|---|
| ChatGPT report and current Google Docs body differ before GitHub canonical registration | Read-only ChatGPT task history + current Docs text comparison; after stripping Markdown/whitespace/citation markers the normalized texts are 5,174 and 4,219 chars. First content difference follows the preamble; the ChatGPT `今日の最大の特徴は、日経平均の後場急反転です。` sentence is absent in Docs. | E5 / FAIL identity equality | Normalized character delta is not a semantic-loss count. Internal writer call is not exposed. |
| Docs revision sequence | Revision 1 contained a BOM only (2026-10-14 07:05:20Z); revision 7 contained the current body (07:06:16Z). | E5 / PASS observed history | Does not identify the client/transform between revisions. |
| GitHub registration stage | ChatGPT final status says GitHub body not registered; `reports/2026-10-14_16-00.json` on main returned 404; `data/latest-report.json` remains 2026-10-13 16:00. | E5 / PASS observed fail-closed state | No canonical 10/14 body exists to hash-compare. |
| 10/14 16:00 body-to-market-snapshot link | Latest main contains a verified 16:30:22 JST snapshot (commit `68562b0`, blob `ea9bea4d96d9be7c3cb9622fd1e67fc8e10f6189`); Docs revision 7 was present at 16:06:16 JST. A later 21:13 recovery snapshot overwrote the current history file. | E5 / source link NOT_PROVEN | Neither snapshot can be assumed to be the earlier ChatGPT body source without a shared snapshot/hash receipt. |
| New TEST ONLY report connects exact identity/body/snapshot through local rendering | Local `report.json` and approved-preview-v2 `source-report.json` share report_id/revision/snapshot_id/bodyHash; render contract PASS, DEBUG_PREVIEW, `publish_allowed=false`; publication manifest absent. | E2 / PASS local report-to-render; formal publication NOT_RUN | TEST ONLY; no Google Docs write/readback, real infographic manifest, GitHub canonical registration, or publication. |
| 08:00 fixed reference fit | Approved reference and tracked `layout.json`; saved source HTML panel-body character counts with 14px Meiryo width-aware and area-equivalent estimates in `REFERENCE-FIXED-FIT-ANALYSIS-20261014.md`, `overflow-estimates.json`, and `fit-calculation.json`. | E0 / LAYOUT_CONFLICT_DETECTED | Width-aware model gives minimum excesses: 06 +264, 07 +613, 08 +638, 10 +97, 11 +39, 12 +152, 13 +719, 14 +269, 15 +178, 16 +351 (3,320 total). The separate area model gives 2,241 total. Both are optimistic model estimates, not browser-measured exact clipping; icons, row/table padding and larger lead text reduce real capacity. |
| Visual acceptance and slot scope | Approved PNG overlay with rejected existing 08 baseline, plus saved 08 baseline dimensions 1536×2539 vs reference 1536×1024. | E4 / PENDING | Overlay documents old rejected output; no fixed-layout candidate was generated because source does not fit; no 12:00/16:00/21:00 design work was performed. |
| 10/13 four-slot snapshot history | Read-only GitHub `main` history at `4a9e70f`; acquisition JSONL and Git blobs for all four slots | E5 / PARTIAL RECOVERY | 12:00 on-window snapshot is recoverable at blob `8b093c6285f4154f249b99bd53f768fc67d3c7f2`, but has no canonical report/body identity/spec link. 08:00 snapshot is a 307.7-minute late recovery; 16:00 and 21:00 slot-labelled snapshots are after-slot. 16:00 canonical body hash exists but has no snapshot link. See `HISTORICAL-SNAPSHOT-AUDIT-20261013.md`. |
| Latest main integration regression | Same Python suite after latest merge commit `d259b652b71f73403a309aa06973dcbf758c7514`; `node scripts/test_independent_publication.js`; acquisition JSONL parse; code/test diff inspection | E1–E3 / PASS | Python 250/250; Node publication regression PASS; latest main additions were six expired acquisition-log rows and Japanese close data only (26 JSONL rows total; 24 expired, 2 verified). The 21:50:35 close reference is incomplete and not linked to the ChatGPT body. The current PR-head hosted check status is not reported yet. |

No publication, Drive write, main-branch write, gate weakening, withdrawn-source restoration, or other-slot design change occurred in this continuation. Latest main `040f5fd5be4f8111aed5a45cb6b5426bc501a66a` was merged into the PR branch at `d259b652b71f73403a309aa06973dcbf758c7514` with no conflict; its new commits update acquisition logs and Japanese close data only. The 21:50:35 JST close-reference package is incomplete and was not backfilled into the 16:00 body. The 10/13 acquisition history is documented separately. The first 10/14 body divergence is bounded to the ChatGPT-to-Docs handoff; exact internal cause remains UNKNOWN. Next action: resolve the source-content/approved-geometry fit conflict before producing an 08:00 acceptance candidate.

## 2026-10-14 continuation — latest main synchronization

Run ID: `latest-main-sync-20261014-c112aac`. GitHub PR #97 was read before changes: OPEN, Draft, unmerged; its description still referenced main `4a9e70f` and head `141a8fa`. `origin/main` advanced from `040f5fd` to `c112aac` through three commits (`a3a97ce`, `190571f`, `c112aac`). Their changed paths are verified Nikkei contributions, gold supply/demand, sector performance, and related stock-history datasets. No workflow, renderer, report contract, or publication gate changed. `git merge-tree` reported a clean merge; merge commit `06aa44ba64f34aa3e7038a070dc6468142e9d0c3` was created locally.

| Claim | Evidence | Level / result | Limit |
|---|---|---|---|
| Merged-tree Python tests | Bundled Python 3.12, `PYTHONPATH=.test-deps`, `python -m unittest discover -s tests -q` | E1–E3 / PASS 250/250 | Local suite only; no hosted CI claim. |
| Existing independent publication regression | Bundled Node, `node scripts/test_independent_publication.js` | E2/E3 / PASS | Mock/local test; no external publication. |
| Merged-tree whitespace check | `git diff --check` | E0 / PASS | Structural check only. |
| PR state before syncing new local merge | GitHub PR metadata | E5 / OPEN, Draft, unmerged | Local merge commit had not yet been pushed at evidence capture. |

The main data updates do not recover any historical source identity or link a snapshot to the 10/14 16:00 body. No later dataset was substituted for that snapshot. The measured 08:00 fit conflict and visual acceptance PENDING remain unchanged. No new PNG candidate or other-slot design was generated.

## 2026-10-14 continuation — latest main publication-data sync

Run ID: `latest-main-sync-20261014-0a6c952`. After pushing head `2ce1b12`, GitHub reported main had advanced by commits `0689089` and `0a6c952`. The first updates Nikkei 225 supply/demand data; the second syncs publication data. `data/dashboard.json` changed its generation time to 21:53:34 JST and retains `dataAsOf: 2026-10-13T16:00:00+09:00` and `currentReportKey: 2026-10-13_16-00`. It removed the 10/14 21:13 market snapshot from the nested report object; `infographic_status: NOT_READY` remains. Current independent market data remains a separate dashboard feed. No workflow, renderer, report contract, or gate changed. The user-facing PR source records are retained on the PR branch; no withdrawn report was restored.

The latest-main tree merged without conflict at `235713592294f9650e169589dca5d286876d079e`. On that merged tree, bundled Python `python -m unittest discover -s tests -q` passed **250/250**, `node scripts/test_independent_publication.js` passed, and `git diff --check` passed. These are local evidence; hosted checks for the newer post-merge head are pending. The 08:00 fixed-layout fit conflict remains unresolved; visual acceptance remains PENDING, and no new candidate or other-slot design was produced.

## 2026-10-14 — source-bound diagram summary and 08:00 visual candidate

Run ID: `0800-summary-layer-review-20261014-2329JST`; source branch was the PR #97 head `d52689bb662178c5e5722ebd5c4aed4f62d21258` before these local changes. GitHub PR #97 at start of this run was OPEN, Draft, unmerged, and matched that head.

| Claim | Evidence | Level / result | Limit |
|---|---|---|---|
| Diagram summary is separate from immutable report body | `scripts/reporting/infographic_summary.py`; authoring source `templates/infographic/approved/summary-content-0800.json`; exact input copy `summary-preview-0800-review6/source-report.json`; source SHA-256 `068a839f5480194896d2cc8de06b497ef377ed2c750c17784fe962b7d74f6167` | E2 / PASS structural link; 59 claims across all 16 panels | Input is a withdrawn historical observation, not a canonical report; no identity/snapshot link |
| Summary provenance and value checks | Claim refs store source codepoint offsets, actual source line, section and excerpt; validation checks source hash, exact span, display numeric tokens and units, direction terms, and critical basis/risk-role coverage by panel 1/4 | E1 / PASS scoped checks; 135 numeric tokens | Machine checks do not prove semantic entailment, causal faithfulness, completeness of judgment rationale, or that no new facts were introduced. Human review is REQUIRED/PENDING. |
| 08:00 review PNG and reference geometry | `summary-preview-0800-review6/png/preview-2026-10-13_08-00-summary.png`; SHA-256 `7cdc0c6ea289f629dde4f68de0a02667911258803634a1f8d6fc48aed31fff4c`; `comparison/visual-comparison.json` | E4 / PNG generated at 1536×1024; all 16 reference rectangles/order/width ratios match; Pillow wrapping reports no overflow | Browser render NOT_RUN; automated overflow covers Pillow line limits only, not claim-to-claim pixel overlap or actual display/device readability. Visual acceptance PENDING. |
| Regression | Bundled Python `python -m unittest discover -s tests -q`; `node scripts/test_independent_publication.js`; `node --check scripts/render_morning_png.js`; `git diff --check` | E1–E3 / PASS, Python 261/261; Node publication-path regression PASS; syntax/diff checks PASS | Mock/local only; no hosted CI or external service readback was observed. |
| Formal generation/publication | Candidate `validation.json` | BLOCKED / NOT_READY, `publish_allowed=false`, no publication manifest | `report_id`, `revision`, `snapshot_id`, `bodyHash`, and linked verified snapshot are missing; no withdrawn data restored. |

PR #97 remains OPEN/Draft. No 12:00/16:00/21:00 design, main merge, production release, Google Drive write, or publication occurred. The latest requested next action is human review of the single 08:00 candidate; only after visual approval should the remaining slots be considered.

## 2026-10-14 — latest main synchronization after summary preview

Run ID: `latest-main-sync-20261014-f8ad26`. GitHub compare found main advanced 14 commits beyond `0a6c9524f0b438eeb7985446358b716aeabea22f` to `f8ad26e21e01e490d4fe4e6fe2bc380f163969de`. The changes are event history/latest/upcoming, 2026-10-14 market/supply-demand archives, dashboard, and the `2026-10-13_16-00` report record. The compare listed no workflows, renderer, report contract, or publication-gate changes. `git merge-tree --write-tree HEAD origin/main` reported no conflicts; merge commit `ca73c24` integrates main into the PR branch (not main into production). Existing `NOT_READY` behavior and snapshot-to-report separation remain.

Post-sync local regression: Python 261/261 PASS; independent publication-path Node regression PASS; `node --check scripts/render_morning_png.js` PASS; `git diff --check` PASS. The PR branch still needs a push and GitHub post-push verification. PR #97 remains OPEN/Draft/unmerged; no main write, production publication, or Drive write was performed.

## 2026-10-14 — independent market data / canonical dashboard projection repair

Run ID: `dashboard-projection-canonical-copy-20261014`. Latest-main recovery CI first reported that `data/dashboard.json.currentReportKey` used the display-space form instead of the canonical key, and then—after correcting the key locally—that `dashboard.latestReport` was not the complete canonical latest report. Inspection traced the mutation path to `scripts/build_market_json.py::attach_market_data`: it added independent `marketData` inside both `latestReport` and `reports[0]`, while the fail-closed contract in `scripts/verify_publication_consistency.py` correctly requires an exact canonical report copy. The independent snapshot remains in the dashboard envelope (`marketData`) and in `data/market/latest.json`; no snapshot was linked to an unrelated body.

Repair: stopped injecting the independent snapshot into report objects, added a regression test for deep-copy immutability and envelope-only placement, and regenerated only the local dashboard projection from the already-canonical `data/latest-report.json` (including canonical report key and exact report copies). No gate or validator was weakened.

| Claim | Evidence | Level / result | Limit |
|---|---|---|---|
| Independent market-data addition preserves canonical dashboard report | `tests/test_build_market_json.py::test_market_data_stays_in_dashboard_envelope` | E1 / PASS | Unit-level builder test |
| Latest dashboard equals canonical report | `scripts/verify_publication_consistency.py` | E2 / PASS | Local repository data only |
| Report history parity | `scripts/validate_report_index.py` | E2 / PASS, 164 reports | Does not prove external dashboard readback |
| Regression suite | `python -m unittest discover -s tests -q` | E1–E3 / PASS, 262 tests | Local runtime only |
| Reconciliation and publication-path regressions | `scripts/test_reconcile_latest_report_market_data.py`; `node scripts/test_independent_publication.js`; renderer syntax check; `git diff --check` | E1–E3 / PASS | External services not called |

The previously built 08:00 summary PNG and comparison artifacts were preserved; no other time slot was redesigned. Visual acceptance remains PENDING and formal generation remains NOT_READY because no verified report identity/bodyHash/snapshot link exists for the historical source. Hosted checks for the repair are pending until the PR branch update is observed. No main merge, production publication, or Drive write occurred.
