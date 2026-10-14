# 08:00 approved-reference fixed-layout fit analysis

Run ID: `0800-fixed-layout-fit-20261014`
Disposition: `LAYOUT_CONFLICT_DETECTED`; visual acceptance remains `PENDING`.

## Scope and source status

This analysis is limited to 08:00. The approved reference is 1536×1024, SHA-256 `7a0df07274b2321f1772974abab036aed9b2298103e7f6399fb395c93c922fc5`. Panel rectangles, order, and widths are in [`layout.json`](../../../templates/infographic/approved/layout.json). No panel was moved or resized. The source used for the 08:00 comparison is explicitly `RECONSTRUCTED_UNVERIFIED / DEBUG_PREVIEW`; it lacks the original report identity, body hash, and historical snapshot linkage and is not a formal source.

The existing 08:00 PNG is 1536×2539. It is a rejected vertical baseline, not the new fixed-layout candidate. The [overlay](../../../validation/0800-reference-fixed-analysis-20261014/reference-overlay-existing-08-rejected-baseline.png) aligns its top 1024 pixels with the approved image only to show the mismatch; it does not represent a fixed-layout redesign or a passing comparison.

## Fixed geometry capacity check

Visible body text was counted from the saved 08:00 HTML by panel. Two explicit, optimistic capacity calculations are preserved so their assumptions remain reviewable. The width-aware estimate uses 14px Meiryo glyph widths, wraps the visible text to each reference panel width, and limits lines to the available height after the 32px heading and 10px padding. A simpler area-equivalent model assumes 14px full-width CJK characters and 17.08px line pitch. Both give all remaining space to text and omit icons, illustrations, table-cell padding, row gaps, and larger lead text. Their excess values are lower-bound estimates, not exact browser-observed clipping counts. Inputs and outputs are in [`overflow-estimates.json`](../../../validation/0800-reference-fixed-analysis-20261014/overflow-estimates.json) and [`fit-calculation.json`](../../../validation/0800-reference-fixed-analysis-20261014/fit-calculation.json).

| Panel | Reference size | Body chars | Optimistic capacity | Minimum excess |
|---:|---:|---:|---:|---:|
| 01 | 438×243 | 104 | 358 | 0 |
| 02 | 332×243 | 115 | 268 | 0 |
| 03 | 385×243 | 102 | 313 | 0 |
| 04 | 353×243 | 127 | 286 | 0 |
| 05 | 477×245 | 177 | 394 | 0 |
| 06 | 398×245 | 336 | 327 | 9 |
| 07 | 375×245 | 752 | 308 | 444 |
| 08 | 263×245 | 747 | 213 | 534 |
| 09 | 544×219 | 180 | 393 | 0 |
| 10 | 544×219 | 297 | 393 | 0 |
| 11 | 423×219 | 212 | 304 | 0 |
| 12 | 497×99 | 210 | 115 | 95 |
| 13 | 1021×99 | 769 | 240 | 529 |
| 14 | 465×96 | 330 | 102 | 228 |
| 15 | 680×96 | 231 | 150 | 81 |
| 16 | 366×96 | 400 | 79 | 321 |

The width-aware Meiryo estimate gives these per-panel **minimum excess characters**: 06 +264, 07 +613, 08 +638, 10 +97, 11 +39, 12 +152, 13 +719, 14 +269, 15 +178, and 16 +351 (3,320 in total). Panels 01–05 and 09 have no estimated excess. This model wraps to panel width and is the more relevant of the two estimates, but remains a calculation rather than a browser clipping measurement. The simpler area model in the table above yields lower values (2,241 total), which shows the result is sensitive to capacity assumptions; it also flags panels 06–08 and 12–16. Both models ignore required graphical/table space, so neither establishes that the full body fits. The constraints “1536×1024, fixed approved rectangles/order/width ratios, all text and numbers, minimum readable type” therefore cannot be accepted as jointly satisfied by this source.

## Visual differences observed in the rejected baseline

- The generated image is 1515px taller than the reference; lower panels are outside the reference canvas.
- The previous render uses naturally sized grid rows rather than the measured per-panel fixed heights.
- The reference uses a compact five-row composition, large illustrative icons, compact tables, and six side-by-side market cards. The rejected output has large content-driven rows and different visual density; panels 07/08 and 13/16 exceed their reference-area budgets before icon/table space is counted.
- The reference's event schedule is a compact panel 15 table; the existing render uses a much taller table/row structure.

No content, numeric values, panel order, widths, or existing gates were changed to make the estimate pass. No layout was propagated to 12:00, 16:00, or 21:00. A 08:00 candidate image is not presented as complete because the present input cannot fit the approved boxes without violating at least one of the user's constraints. Visual acceptance remains `PENDING`.

## Evidence and limit

| Claim | Evidence | Level / result | Limit |
|---|---|---|---|
| Reference dimensions/hash and per-panel rectangles | Approved PNG and tracked `layout.json` | E0 / PASS | Rectangle positions are exact configuration; visual design approval remains human |
| Existing 08:00 output differs from reference canvas | PNG dimensions, render receipt, overlay | E4 / FAIL for visual acceptance | Existing output is rejected baseline only |
| Multiple panels cannot fit at readable minimum under optimistic width-aware and area models | Saved source HTML text counts and two explicit 14px capacity calculations | E0 / BLOCKED | Character excesses are estimates, not pixel-exact browser overflow; exact rendered overflow depends on the approved renderer/font and graphical content |
| Other slots unchanged | Work scope and artifact paths checked | E0 / PASS | No new 12:00/16:00/21:00 design work was performed |
