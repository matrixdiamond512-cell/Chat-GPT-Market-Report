/* Reset the 21:00 layout guard when the user leaves the 21:00 tab. */
(() => {
  "use strict";

  function resetWhenOutside21() {
    const app = document.getElementById("app");
    if (!app) return;
    let report = null;
    try {
      report = selectedReport || null;
    } catch (error) {
      report = null;
    }
    if (!report || String(report.time || "") !== "21:00") {
      delete app.dataset.manual21Key;
      app.classList.remove("manual21-applied");
    }
  }

  function start() {
    const app = document.getElementById("app");
    if (!app) return;
    new MutationObserver(resetWhenOutside21).observe(app, { childList: true, subtree: true });
    resetWhenOutside21();
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start, { once: true });
  else start();
})();
