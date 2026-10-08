# Report and infographic publication status separation

The report body and infographic are independent publication lanes. Body validation, canonical report creation, report index/dashboard synchronization, and Portal body verification determine `report_status`. A valid body is recorded as `PUBLISHED` before optional infographic processing begins.

`infographic_status` is `READY`, `NOT_READY`, or `FAILED_VALIDATION`. Missing infographic facts, a missing manifest, absent optional OCR/Vision, or an unavailable renderer cannot roll back or block a published body. A failed infographic is omitted from the Portal.

The production Apps Script accepts an infographic only from a manifest pinned to the report ID, revision, snapshot ID, and body hash. It reads the exact `drive_file_id`, checks PNG signature and SHA-256, then registers the image. It does not choose an image by name or update time. The Portal renders only `READY` formal infographic metadata with matching body/report identity, manifest and PNG hashes, and successful numeric/renderer checks. `DEBUG_PREVIEW` is excluded.

OCR and Vision are optional QA and do not gate `READY`; structured fact coverage, numeric validation, renderer validation, manifest identity, and PNG identity/hash remain required. If body validation fails, infographic processing is not invoked.
