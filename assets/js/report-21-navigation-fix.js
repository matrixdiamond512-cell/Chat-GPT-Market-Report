/* Reset the SOP layout guard only when the selected date/time actually changes. */
(() => {
  "use strict";

  function currentKey() {
    try {
      const report = selectedReport || null;
      if (!report) return "";
      return `${report.date || ""} ${report.time || ""}`;
    } catch (error) {
      return "";
    }
  }

  function resetWhenSelectionChanges() {
    const app = document.getElementById("app");
    if (!app) return;
    const activeKey = currentKey();
    const appliedKey = app.dataset.manual21Key || "";
    if (appliedKey && appliedKey !== activeKey) {
      delete app.dataset.manual21Key;
      app.classList.remove("manual21-applied", "manual21-qa-blocked");
    }
  }

  function start() {
    const app = document.getElementById("app");
    if (!app) return;
    new MutationObserver(resetWhenSelectionChanges).observe(app, { childList: true, subtree: true });
    resetWhenSelectionChanges();
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start, { once: true });
  else start();
})();
