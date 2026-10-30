# Google Drive publication receipts

From the 2026-08-19 21:00 JST report onward, the portal build must not publish a scheduled market report unless its Google Docs source passes exact body readback and the report is bound to immutable, pre-draft snapshot/context evidence. The Drive ingestion workflow writes a version 2 receipt only after those checks pass. It does not repair source text or promote a source when evidence is missing.

Receipt filename:

`YYYY-MM-DD_HH-MM.json`

Required fields:

Version 1 receipts (legacy) contain only the fields below. They are not sufficient to promote a new source or to claim a strict readback/snapshot match.

```json
{
  "date": "2026-08-19",
  "time": "21:00",
  "title": "マーケットレポート｜2026/08/19（水）21:00",
  "status": "saved",
  "publisher": "chatgpt",
  "driveFileId": "GOOGLE_DOC_FILE_ID",
  "driveUrl": "https://docs.google.com/document/d/GOOGLE_DOC_FILE_ID/edit",
  "savedAt": "2026-08-19T21:05:00+09:00"
}
```

New verified Docs publications use schema version 2 and additionally bind the Google Docs revision, exact UTF-8 body SHA-256, report ID/revision, snapshot ID, context/snapshot hashes, source creation/modification time, and readback status. `publisher` is `google-drive-ingestion`, the process that actually reads and verifies the document. Missing or mismatched proof keeps the canonical source at `SOURCE_ARCHIVED` and out of public projections.

The strict v2 receipt enforcement epoch is 2026-10-16. Earlier `DOC_READBACK_PASS` history is retained under its original, weaker receipt contract; it is not retroactively represented as snapshot-verified. Any `DOC_READBACK_PASS` from 2026-10-16 onward must include `publicationEvidence` and a matching v2 receipt or consistency validation fails.

The normal build rejects a missing receipt, a mismatched report slot/title, a non-Google-Docs URL, a file ID/URL mismatch, a save timestamp before the report slot, or any publisher other than `chatgpt`.

This receipt is intentionally separate from `reports.json`. Its purpose is to prevent a ChatGPT-side Drive-save omission from being silently masked by downstream portal recovery or report regeneration.
