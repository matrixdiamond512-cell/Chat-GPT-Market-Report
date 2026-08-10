(() => {
  "use strict";

  const INTERNAL_MISSING_RE = /JSONにありません|前回からの変化[^。\n]*(?:ありません|取得不能)/;
  const CHANGE_HEADING_RE = /^\s*(?:【\s*)?(?:\d{1,2}\s*[.．、)]\s*)?前回から(?:の)?(?:変化|市場解釈の変化)(?:\s*】)?\s*$/;
  const NEXT_SECTION_RE = /^\s*(?:【[^】]+】|\d{1,2}\s*[.．、)]\s*\S.+)$/;

  function currentReportSafe() {
    try {
      return typeof selectedReport !== "undefined" ? selectedReport : null;
    } catch (_error) {
      return null;
    }
  }

  function cleanLine(value) {
    return String(value || "")
      .replace(/^\s*[・●■◆▶→-]\s*/, "")
      .replace(/\s+/g, " ")
      .trim();
  }

  function extractChangesFromFullText(report) {
    const fullText = String(report?.fullText || "").replace(/\r/g, "");
    if (!fullText) return [];

    const lines = fullText.split("\n");
    const start = lines.findIndex((line) => CHANGE_HEADING_RE.test(String(line || "").trim()));
    if (start < 0) return [];

    const values = [];
    for (let index = start + 1; index < lines.length; index += 1) {
      const raw = String(lines[index] || "");
      const trimmed = raw.trim();
      if (!trimmed) continue;
      if (NEXT_SECTION_RE.test(trimmed)) break;

      const cleaned = cleanLine(trimmed);
      if (cleaned && !INTERNAL_MISSING_RE.test(cleaned)) values.push(cleaned);
      if (values.length >= 6) break;
    }
    return values;
  }

  function normalizedStructuredChanges(report) {
    const raw = Array.isArray(report?.changes)
      ? report.changes
      : report?.changes
        ? [report.changes]
        : [];

    return raw
      .map((value) => {
        if (typeof value === "string") return cleanLine(value);
        if (!value || typeof value !== "object") return "";
        return cleanLine(value.text || value.summary || value.title || "");
      })
      .filter((value) => value && !INTERNAL_MISSING_RE.test(value));
  }

  function renderItems(list, items) {
    const fragment = document.createDocumentFragment();
    items.forEach((item) => {
      const li = document.createElement("li");
      const paragraph = document.createElement("p");
      paragraph.textContent = item;
      li.appendChild(paragraph);
      fragment.appendChild(li);
    });
    list.classList.add("prose-list");
    list.replaceChildren(fragment);
  }

  let applying = false;

  function applyChangeFallback() {
    if (applying) return;
    const list = document.getElementById("changeList");
    if (!list) return;

    const card = list.closest("article.panel");
    const report = currentReportSafe();
    const structured = normalizedStructuredChanges(report);
    const currentText = String(list.textContent || "").trim();
    const showsInternalError = INTERNAL_MISSING_RE.test(currentText);

    if (structured.length) {
      if (card) card.hidden = false;
      if (showsInternalError || !currentText) {
        applying = true;
        renderItems(list, structured);
        applying = false;
      }
      return;
    }

    const extracted = extractChangesFromFullText(report);
    if (extracted.length) {
      if (report) report.changes = extracted.slice();
      if (card) card.hidden = false;
      applying = true;
      renderItems(list, extracted);
      applying = false;
      return;
    }

    // Internal data-pipeline messages must never be shown to dashboard users.
    if (showsInternalError || !currentText) {
      applying = true;
      list.replaceChildren();
      if (card) card.hidden = true;
      applying = false;
    }
  }

  function start() {
    const list = document.getElementById("changeList");
    if (!list) return;

    applyChangeFallback();
    const observer = new MutationObserver(() => applyChangeFallback());
    observer.observe(list, { childList: true, subtree: true, characterData: true });

    document.addEventListener("change", () => setTimeout(applyChangeFallback, 0));
    document.addEventListener("click", () => setTimeout(applyChangeFallback, 0));
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", start, { once: true });
  } else {
    start();
  }
})();
