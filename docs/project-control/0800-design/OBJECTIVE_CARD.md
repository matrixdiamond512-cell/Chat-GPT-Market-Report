# 08:00図解デザイン改善の作業記録

2026-10-13 JST / 状態: REDESIGN_ITERATION_2_READY; FIXTURE_RUNTIME_PASS; USER_VISUAL_REVIEW_PENDING

PRIMARY OBJECTIVE: 既存の情報・データ検証・公開処理を保ち、08:00図解で相場の要点、因果関係、推定/実測の資金フロー、6市場の方向と警戒条件を正確かつ再現可能に読める状態にする。

ACTIVE PROFILE: dashboard + data-tool。

ACCEPTANCE CRITERIA: 元仕様書の全条件（16項目固定、6市場、情報保持、意味別配色、数値一致、時点区別、文字欠損なし、768pxとスマートフォン視認性、ゲート維持、回帰、Draft区別）。10/09参考画像と比較して、配置・密度・図記号・判読性を人が評価し、ユーザーがデザインを確認するまで受け入れ完了としない。

CONSTRAINTS: 新ブランチとDraft PR。mainマージ・本番切替・公開画像上書きなし。取得、ニュース、numeric/source identity、公開ゲート、Drive保存、ポータル、他時刻は維持。旧作業フォルダーの既存差分を保護。

OUT OF SCOPE: 市場分析変更、他時刻デザイン、公開復旧、旧レポート値の推測補完。

FORBIDDEN SUBSTITUTE: AI生成の華やかな画像だけを再現可能テンプレートの完成と扱うこと。PUBLISHED/DRIVE_SAVEDやローカルテストを実入力/外部結果の合格と扱うこと。

INSTRUCTION UPDATE (CORRECT/CLARIFY): ユーザーは10/12改善見本がChatGPT画像生成由来であり、既存の描画テンプレートを前提にしないよう訂正した。初回調査後、HTML/SVGからPNGへの実装とmanifest接続、合成画像検証、対象リポジトリへの限定資料送信・Draft PR作成を明示承認した。APIキー/認証情報/個人情報/ローカル固有設定を送信しない。mainマージ・本番切替・自動公開の承認はない。

OPEN OUTCOMES:
- O-001 生成元・既存接続調査: コード調査済み。実稼働環境は未確認。
- O-002 再現可能な08:00描画テンプレート: IMPLEMENTED。既存ゲート不変、専用CLI追加。
- O-003 合成fixture・画像・768px検査: v1.2 PASS。16項目・6市場・142facts、元文字列完全一致、モバイル最小15px、はみ出し/重なり/色エラーなし。PNG 1536×2629、mobile 768×3352。実スマートフォン端末はNOT_RUN。
- O-004 10/09・10/12正式再生成: BLOCKED / 検証済みsnapshot等が不足。
- O-005 実装後回帰・manifest消費側: 最新コードでPython176/176、既存JS公開回帰PASS。新producer正式mockは既存consumerでREADY、合成実PNGのmanifestはNOT_READY。非本番Drive保存・外部readbackはNOT_RUN。
- O-006 比較画像・更新テンプレート仕様・運用追記: 新仕様/運用追記、DRAFT画像/入力/receiptを追加。参考とのデザイン・構成比較を文書化。実10/12全文/数値比較はBLOCKED。運用適用は未実施。
- O-007 Draft PRレビュー: https://github.com/matrixdiamond512-cell/Chat-GPT-Market-Report/pull/97 はOPEN/DRAFT/未マージ。今回head `6e335c8605d1fd0d5ff9e798ef48a4935c7769cd` を送信し、PR説明も保存本文プレビューを反映。GitHub連携で当該headのworkflow runは取得できず、hosted CIはUNKNOWN/未確認。デザインレビュー待ち。
- O-008 10/09デザインへの再設計: 12カラム、番号/アイコン、表/時系列/フロー/因果、6市場一列、モバイル別レイアウトを実装。新たな指示「街並みより内容の見やすさ」を反映し、市場データ/市場カードの文字を拡大、ヘッダー装飾を縮小。合成PNGの描画・データ照合はPASS。ユーザー視覚レビューと受け入れはPENDING。
- O-009 内容差異の再修正: 以前の合成本文は内容レビューに不適切との指摘を受け、利用者が選択した保存済み10/12 `fullText`から直接描画するレビュー専用経路を追加。入力は`RECONSTRUCTED_UNVERIFIED`、画面上に未検証/公開不可を明記、snapshot・公開manifestなし。12カラム構成を見直し、6市場をPC全幅一列、モバイルは密度の高いカードを全幅表示。実PNG検査PASS、デザイン受け入れはPENDING。

NEXT NECESSARY ACTION: ユーザーに`content-review-2026-10-13`の未検証レビューPNGを確認してもらい、見本との差や内容の並べ方について指示を受ける。正式再生成は正規snapshot/本文/specが揃った後に既存ゲートで検証する。本番接続は別承認後。

既存の他作業のobjective記録は変更しない。この記録は今回の08:00変更専用。

## Continuation update — 2026-10-14

Latest user direction takes precedence: retain infographic generation, keep visual acceptance `PENDING`, complete only 08:00, and do not expand the design to 12:00/16:00/21:00 before 08:00 visual approval. Main merge, production publication, and Google Drive writes remain out of scope.

OPEN OUTCOMES:
- O-010 2026-10-14 16:00 production E2E identity: FIRST DIVERGENCE LOCATED at the ChatGPT-to-Google-Docs body handoff (normalized body mismatch); exact internal writer call remains UNKNOWN. GitHub main registration did not occur; no 10/14 canonical file exists. See `E2E-20261014-1600-DIAGNOSIS.md`.
- O-011 Exact approved 1536×1024 fixed 08:00 layout: BLOCKED by a source-content/geometry fit conflict. Optimistic 14px Meiryo width-aware estimates show 3,320 minimum excess body characters across panels 06, 07, 08, 10, 11, 12, 13, 14, 15, and 16; a separate area model gives 2,241. Neither is browser-observed exact clipping. No content or layout was altered to hide overflow. See `REFERENCE-FIXED-FIT-ANALYSIS-20261014.md`.
- O-012 New-report identity connection: local TEST ONLY report uses one report_id/revision/bodyHash/snapshot_id through spec validation and DRAFT rendering. `DEBUG_PREVIEW`, `publish_allowed=false`, publication manifest NOT_CREATED; Drive/Portal/external E2E NOT_RUN. Not a formal production generation pass.
- O-013 Visual acceptance: PENDING. Current 08 PNG is a rejected 1536×2539 baseline; no new fixed-layout candidate is claimed. Other three slot designs remain untouched during this continuation.
- O-014 Historical 10/13 source/snapshot audit: PARTIAL RECOVERY. Git history has one on-window verified 12:00 market snapshot, but no canonical report/body identity/spec link. The 08:00, 16:00, and 21:00 retained snapshots were acquired after their slots; the 16:00 canonical body has an identity hash but no linked snapshot. No withdrawn report was restored. See `HISTORICAL-SNAPSHOT-AUDIT-20261013.md`.
- O-015 Latest-main integration: COMPLETE. Main `4a9e70f4cb3af0848259504740f53b53bb40a6b9` merged to PR branch at `7edd8a39059c26f51e5c9a79195ae82f708179f9`; merge-tree showed no conflicts, and the two PR CI workflows had no main-side changes. Latest main contains acquisition/snapshot history but still no 2026-10-14 16:00 canonical report. Full regression is pending after this merge.

NEXT NECESSARY ACTION: Present the measured 08:00 content/geometry conflict for user direction on how to preserve all information inside the approved panel geometry. Until resolved, do not claim a fixed-layout candidate or propagate design to the other slots. Run the existing regression suite after latest-main integration, then keep the stop gates and Draft/Open PR state.
