# 08:00図解デザイン改善の作業記録

2026-10-13 JST / 状態: INVESTIGATED; PROPOSED; IMPLEMENTATION_PENDING_APPROVAL

PRIMARY OBJECTIVE: 既存の情報・データ検証・公開処理を保ち、08:00図解で相場の要点、因果関係、推定/実測の資金フロー、6市場の方向と警戒条件を正確かつ再現可能に読める状態にする。

ACTIVE PROFILE: dashboard + data-tool。

ACCEPTANCE CRITERIA: 元仕様書の全条件（16項目固定、6市場、情報保持、意味別配色、数値一致、時点区別、文字欠損なし、768pxとスマートフォン視認性、ゲート維持、回帰、Draft区別）。現在の調査成果の受入は生成元と検証/公開接続の事実を示し、未存在機能を捏造せず具体的実装案を提示すること。

CONSTRAINTS: 新ブランチとDraft PR。mainマージ・本番切替・公開画像上書きなし。取得、ニュース、numeric/source identity、公開ゲート、Drive保存、ポータル、他時刻は維持。旧作業フォルダーの既存差分を保護。

OUT OF SCOPE: 市場分析変更、他時刻デザイン、公開復旧、旧レポート値の推測補完。

FORBIDDEN SUBSTITUTE: AI生成の華やかな画像だけを再現可能テンプレートの完成と扱うこと。PUBLISHED/DRIVE_SAVEDやローカルテストを実入力/外部結果の合格と扱うこと。

INSTRUCTION UPDATE (CORRECT/CLARIFY): ユーザーは10/12改善見本がChatGPT画像生成由来であり、既存の描画テンプレートを前提にしないよう訂正した。生成元がなければ接続調査と実装方針提案を行う。新規描画実装は提案承認待ち。元の最終成果は撤回されていない。

OPEN OUTCOMES:
- O-001 生成元・既存接続調査: コード調査済み。実稼働環境は未確認。
- O-002 再現可能な08:00描画テンプレート: PROPOSED / 実装未承認。
- O-003 合成fixture・画像・768px/スマートフォン検査: NOT_RUN。
- O-004 10/09・10/12正式再生成: BLOCKED / 検証済みsnapshot等が不足。
- O-005 実装後回帰・manifest消費側・非本番外部保存: NOT_RUN。既存ローカルbaseline試験のみPASS。
- O-006 比較画像・更新テンプレート仕様・運用追記: 具体案を調査文書へ記載。画像比較・運用適用は未実施。
- O-007 Draft PRレビュー: 調査・提案だけを提出。実装案の承認後に必要実装を進める。

NEXT NECESSARY ACTION: 提案へのユーザー承認を受け、最初に合成入力でcanonical specと16カード投影の互換性を検証する。正規入力不足を別outcomeとして保持する。

既存の他作業のobjective記録は変更しない。この記録は今回の08:00変更専用。
