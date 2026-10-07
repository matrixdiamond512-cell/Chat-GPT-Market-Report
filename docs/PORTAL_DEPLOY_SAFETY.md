# Market Report Portal Deploy Safety and Title Boundary

## Canonical title and body boundary

`report.title` is the canonical Portal title. The renderer always displays that value when present. It removes only an exact matching title prefix from `fullText`; if the title and body were concatenated without a newline, the remaining text stays in the report body. A title-like phrase later in the body is not split.

The Google Docs converter parses `report.title` from the source, then passes the normalized source and that title through `normalizeReportCanonicalText_`. This adds one newline only when the source begins with the exact title and the next character is not already a newline. The resulting `fullText` is the text used for `bodyHash`. Google Docs readback applies the same helper to both the readback and expected text before comparing content and hash. The HMAC payload and source SHA contract are unchanged; new reports use the canonicalized body text for their existing source hash.

This does not rewrite legacy `reports/*.json`. The browser regression fixture models a malformed title/body boundary and verifies exact title display, visible body remainder, embedded title-like text, and the six-row market table.

## GitHub Pages triggers and gates

The `push` trigger on `main` is limited to Portal pages, assets, report/index data, dashboard/image/receipt inputs, and the workflow's directly used validation scripts. Documentation, signer-only, Apps Script-only, and test-only changes do not match those paths. Existing `workflow_run` sources remain enabled.

For a Pages deployment, the workflow validates in this order:

1. Canonical report index and report integrity.
2. Dashboard asset normalization and cache-busting.
3. Install the browser validator and serve the normalized working tree locally.
4. Render the malformed-title fixture, then all latest-date slots in the local Portal DOM.
5. Upload the static artifact and deploy to GitHub Pages only if all local checks pass.
6. Verify public report/index/image readback and run the same DOM validator against the live Portal.

The DOM validator requires exact `.report-title.textContent === report.title`, a visible body, a market section and table with at least six rows, completed loading state, no page errors, and no console errors. A mismatch is a failure; no title check is relaxed or skipped.

The current local artifact has a separate existing 08:00 QA failure: `reports/2026-10-07_08-00.json` has no structured `marketDataTable.rows` or `dataDate`, while the existing MorningReportQA contract expects 28 previous-close rows and the rendered DOM has six rows. This change does not alter report data or relax that contract. The strict current-artifact check remains in the Pages predeploy workflow and fails closed before artifact upload/deployment until the independent report issue is resolved. The `Market Report UI Renderer Regression Validation` workflow checks the malformed-title browser fixture and renderer contracts. `Current Report Strict DOM Validation` runs separately against actual PR report data without a fixture and preserves any data-quality failure. The deploy workflow uses the same strict no-fixture check before upload.

Deploy completion alone is not publication completion. The live DOM check remains mandatory after deploy. A live failure is reported as deployed-but-live-validation-failed and does not become a PASS or completion claim.

## Scope and limits

This change does not edit historical report JSON, `reports.json`, market values, receipts, Drive documents, Apps Script production settings, secrets, or the deployed Portal. CI and local fixtures prove component and integration behavior only; production publication acceptance still requires an explicitly authorized deployment and successful live readback.
