# マーケットレポート配信システム 要件定義書
2026-10-13 / PRレビュー用。3文書は独立。GitHub mainの静的確認・本番稼働・未マージPRは区別する。
対象：データ取得→検証→本文・図解→ChatGPT表示→Drive保存→GitHub→Portal公開→公開後検証。
REQ-01: 日時、出典、reportId、revision、本文・図解、保存と公開の証跡を追跡する。
REQ-02: ChatGPT実タスクは平日08/12/16/21が有効、土曜08は無効。main configはPR #99マージにより土曜発行なしへ修正済み。
REQ-03: 本文のPUBLISHEDと図解のNOT_READYは同時に存在できる。本文公開と全工程完了を混同しない。
REQ-04: 08:00の28項目5列表の品質検査を要求。実データの全取得成功とは別。
REQ-05: Google Docs保存receiptとinfographicManifestを区別し、公開前後の検証証拠を保全する。
REQ-06: Draft PR #94/97は本番実装済みと認めない。
REQ-07: 要件定義書、仕様書、運用マニュアルを別ファイルとし、書込対象IDの照合を必須にする。
未解決：実行中トリガー、全旧版条項比較、PR本番採用、最新CI・Drive・公開URLの実検証。

## 2026-10-16 公開連携復旧追補（PR提出前）
- 新規公開には対象枠の事前確定snapshot/context、完全一致Docs読み戻し、revision/body hash、保存時刻を結合した発行時receiptを要求する。
- 証拠が欠ける保存済み文書は原本アーカイブに保持するが、公開一覧/latest/dashboard/Pagesへ昇格させない。既存履歴は保持する。
- 10/14 12:00は取得可能な初版Revision 1が空で、本文のあるRevision 11は後刻作成のため、発行時原文として扱わない。10/14 08:00の見出し別名はPython回帰試験に合格したが、現在のDrive更新時刻が発行枠を超えるので公開承認とはしない。
- この追補の実装はPRであり、本番E2E成功は未確認。定期実行・公開URL本文読み戻しを確認するまで復旧完了としない。

## 2026-10-13 実検証で確定した事実
- 実ChatGPTタスクは平日4枠のみ有効。土曜日旧タスクは無効。Apps Script実トリガーは接続元から照会不可。
- PR #95/#96はマージ済み。PR #94/#97/#98はDraft・未マージ。
- PR #94のMOF検証はSTALE_DATA閾値の限定修正後、Actions run 38298392598でSUCCESS。ただしSheets/本番updateはSKIPPED。PR #97はデザインテストPASS、本番公開未確認。
- 2026-10-12 21:00 のDocはGoogle Driveに実在。旧Receiptにはstrict validator必須のtitle/status/publisher/driveFileId/driveUrl/savedAtが欠ける。保存主体や日時を推測補完しない。
- PR #98の公開workflowへの直接Receipt検査追加は撤回。新旧スキーマ移行と実テストまでは本番導入禁止。

## 2026-10-13 最終照合
- PR #99はmainにマージ済み。現行スケジュールは平日08/12/16/21のみ、土日なし。
- PR #94の修正後Actions run 38298392598はSUCCESS。Draft・未マージであり、本番データ書込を検証したものではない。
- この文書に記載するPR #98のReceipt強制ゲートは撤回済み。Docs保存証跡の旧スキーマ移行が未完了のため、公開ゲートの新設を完了とはしない。

## 2026-10-16 追補（DOCSYNC-20261016-RPT）
- REQ-08：平日4枠で、事前取得・証拠生成・ChatGPT本文生成/指定会話出力・Docs/図解保存・canonical/receipt・Pages DOM・通知到達を独立受入する。
- REQ-09：各枠T-13/T-7/T-3分で当日枠・鮮度15分以内の実データから証拠を固定し、T以後の欠損snapshot再構成を禁止する。PR #154でmain反映済み、全枠ライブ発行の成功は未確認。
- REQ-10：10/16 08:00後追い発行はHISTORICAL_ARCHIVE/verifiedAtSlot=falseで保存し、通常のPUBLISHED、canonical、receiptと区別する。PR #152は補充表示専用。
- REQ-11：主要6市場カードは補充原本にある銘柄固有の価格・市場種別・限月・観測時刻・理由・注目点・リスクを区別し、「取得不能」誤表示や条件の二重転記を防ぐ。PR #153で実装・DOM試験済み。12/16/21時は実際の出来事の時系列を記す。

## 2026-10-17 追補（PR #97 08:00 接続）
- REQ-12：本文は発行前に `G2_DRAFT_NOT_SAVED` の全文・SHA-256・report identity・snapshot/contextとともに固定し、その本文をDocs writerへ渡す。Docs保存後、Drive importerがGoogle Docs APIから読み戻した本文、revision、SHA-256と保存前artifactを照合し、本文またはidentity不一致なら図解描画と公開を停止する。保存前artifactの `capturedAt` はreceiptの `savedAt` 以下でなければならない。
- REQ-13：本文全文の保持と図解の情報量を分離する。全文hashは本文側で検証し、図解側は出典位置・snapshot参照付きの宣言済み要約factを検証する。16パネル全ての必須役割、snapshot数値、方向、単位、時刻、specとの一致を確認する。要約により図解に載らない説明は本文に完全保持する。
- REQ-14：パネル12はメインシナリオ・代替シナリオ・崩れる条件を必須とし、成立条件・想定展開・市場影響を出典位置に結ぶ。自動生成とは独立した人間の意味確認を必須とし、未承認は公開停止する。
- REQ-15：summary/view/specの生成は同一report identity/bodyHash/snapshotの入力から行う。要約文章と意味解釈をデータ欠落から自動捏造しない。未整備の人間入力や原文位置の曖昧さは停止理由として報告する。
- PR #97のstaging bridgeは未マージのため、通常08:00 producerからの自動起動は未稼働。default-branch workflowの追加が必要だが、本追補ではmain側・既存定時配信を変更しない。実市場のslot完走は未確認。
