# マーケット分析ダッシュボード 時間帯別市場時系列表示機能

- 対象：マーケット分析ポータル／マーケット分析ダッシュボード
- レポート時刻：08:00、12:00、16:00、21:00（JST）
- 指示日：2026-10-16

## 目的

選択したレポートに対応する市場時間について、確認できた出来事、出来事の時刻、市場反応と反応の観測時刻、相場への意味、次の注目点、出典を独立した時系列パネルに表示する。出来事と反応の因果関係は、根拠で確認できる範囲に限って表現する。

## 時刻別の時間帯と段階

| レポート | 対象 | 時系列段階 |
| --- | --- | --- |
| 08:00 | 昨夜NY市場 | NY開場前 → 寄り付き → 序盤 → 中盤 → 終盤・引け → 東京への引き継ぎ |
| 12:00 | 東京市場前場 | 寄り付き前 → 寄り付き → 前場序盤 → 中盤 → 前引け |
| 16:00 | 東京市場全体 | 午前の振り返り → 後場開始 → 後場中盤 → 大引け → 欧州への引き継ぎ |
| 21:00 | 欧州市場 | 欧州開場前 → 寄り付き → 序盤 → 中盤 → NYへの引き継ぎ |

特に08:00では、実際のNY市場での指標・ニュース・米国株・米金利・ドル・金・原油・BTC等の反応を対象とする。相場見通しだけで実際の時系列を代替しない。

## 表示契約

`timeline`は各レポート本文内の別構造フィールドとし、次の識別子に結び付ける。

```json
{
  "schemaVersion": "market-timeline/v1",
  "reportId": "YYYY-MM-DD_HH-MM",
  "reportDate": "YYYY-MM-DD",
  "reportTime": "HH:MM",
  "reportRevision": "source revision",
  "sourceBodyHash": "SHA-256 of the exact canonical fullText",
  "evidenceStatus": "SAVED_SOURCE_BODY | AFTER_ISSUANCE_AMENDMENT",
  "amendmentDate": null,
  "publicationStatus": "the source report status",
  "sourceDocumentId": "source document id",
  "sourceDocumentRevision": "source revision/readback metadata",
  "events": [
    {
      "phase": "slot-specific phase",
      "timeLabel": "source wording for event/market period",
      "occurredAt": "source-stated timestamp or null",
      "timePrecision": "source-stated | time-not-recorded",
      "reactionObservedAt": "source-stated observation time or null",
      "event": "confirmed event",
      "reaction": "observed market reaction and values",
      "meaning": "bounded interpretation",
      "nextWatch": "next check",
      "sources": ["source reference"]
    }
  ]
}
```

The source text must explicitly distinguish `出来事`, `反応`, `意味`, `出典`, and `次の注目点` (or `次は`). The importer verifies report/date/time/revision/body hash before accepting the structured field. A source without exact timing keeps `occurredAt` or `reactionObservedAt` null and must disclose that the time was not recorded.

Scheduled but unpublished events are not actual events. Do not infer prices, timestamps, sources, or causation. Missing values remain visibly missing.

## Dashboard requirements

- Place a separate panel immediately below the six-market summary in `index.html`.
- Keep the existing date/time report selector as the source for the current-report timeline.
- Keep the existing upcoming-events table unchanged and separate from the actual-event timeline.
- Show 2026-10-15 saved amendments in a distinct retrospective archive selector. Never merge archived or snapshot-blocked records into the public report selector, latest report, dashboard projection, or publication eligibility list.
- Verify each retrospective sidecar against the saved canonical report's date, slot, revision, body hash, source document ID, and exact full-text SHA-256 before display.
- State clearly that the 2026-10-16 additions are later amendments and do not establish the 2026-10-15 issuance-time snapshot or receipt.
- Preserve market cards, positioning, flows, news, scenarios, upcoming events, report controls, and publication gates.
- Support narrow smartphone layouts without horizontal overflow or hidden required fields.

## 2026-10-15 preserved source state

The four saved reports remain unchanged. Their observed statuses are 08:00 `SOURCE_ARCHIVED`, 12:00 `SOURCE_ARCHIVED`, 16:00 `BLOCKED_SNAPSHOT_MISSING`, and 21:00 `SOURCE_ARCHIVED`. Their timeline sidecars must reference each saved revision and exact body hash, and use `AFTER_ISSUANCE_AMENDMENT` with amendment date 2026/10/16. These annotations do not create historical snapshots, publication receipts, or publication eligibility.

## 12 acceptance checks

1. All four slots use the specified ordered phase lists.
2. The current timeline panel appears immediately below the six-market summary.
3. Changing the current report date or time updates its corresponding timeline without changing the separate upcoming-events table.
4. Every timeline item separates event, reaction, meaning, next watch, and source.
5. Event time and market-reaction observation time are distinct fields.
6. Unrecorded times remain null and are visibly described as unrecorded.
7. Future scheduled events are not rendered as events that occurred.
8. New report timelines bind to report ID, date, time, revision, exact body hash, source document, and evidence metadata.
9. Each 2026-10-15 amendment displays under its matching slot and is labeled as a 2026-10-16 retrospective amendment.
10. The 2026-10-15 source bodies, hashes, revisions, publication statuses, snapshots, and receipts remain unchanged; existing publication eligibility still rejects archived/blocked records.
11. Missing or mismatched source identity fails closed with a readable reason.
12. Smartphone-width rendering preserves all fields, wraps long source text, and retains the four amendment tabs; existing dashboard features remain present.

## Scope and release boundary

This change adds dashboard display and source structuring only. It does not create missing issuance-time evidence or receipts, alter historical source bodies, promote archived reports, merge to `main`, or deploy GitHub Pages. The PR remains open for review until accepted by its reviewers.
