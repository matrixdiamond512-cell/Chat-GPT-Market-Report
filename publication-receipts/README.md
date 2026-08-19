# Google Drive publication receipts

From the 2026-08-19 21:00 JST report onward, the portal build must not publish a scheduled market report unless the report has first been saved to Google Drive by ChatGPT and a matching receipt exists here.

Receipt filename:

`YYYY-MM-DD_HH-MM.json`

Required fields:

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

The normal build rejects a missing receipt, a mismatched report slot/title, a non-Google-Docs URL, a file ID/URL mismatch, a save timestamp before the report slot, or any publisher other than `chatgpt`.

This receipt is intentionally separate from `reports.json`. Its purpose is to prevent a ChatGPT-side Drive-save omission from being silently masked by downstream portal recovery or report regeneration.
