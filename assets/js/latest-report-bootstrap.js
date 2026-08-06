(() => {
  "use strict";

  const MAX_ATTEMPTS = 80;
  let attempts = 0;

  function keyOf(item) {
    return `${item?.date || ""} ${item?.time || ""}`;
  }

  function latestReport(list) {
    return list
      .filter((item) => item && /^\d{4}-\d{2}-\d{2}$/.test(item.date || "") && /^\d{2}:\d{2}$/.test(item.time || ""))
      .slice()
      .sort((a, b) => keyOf(b).localeCompare(keyOf(a)))[0] || null;
  }

  function shouldKeepHistoricalSelection(latest) {
    const params = new URLSearchParams(location.search);
    const requestedDate = params.get("date");
    return Boolean(requestedDate && requestedDate < latest.date);
  }

  function chooseLatest() {
    attempts += 1;

    let list = [];
    try {
      list = Array.isArray(reports) ? reports : [];
    } catch (error) {
      list = [];
    }

    if (!list.length) {
      if (attempts < MAX_ATTEMPTS) setTimeout(chooseLatest, 250);
      return;
    }

    const latest = latestReport(list);
    if (!latest || shouldKeepHistoricalSelection(latest)) return;

    let current = null;
    try {
      current = selectedReport || null;
    } catch (error) {
      current = null;
    }

    if (!current || keyOf(current) !== keyOf(latest)) {
      try {
        if (typeof selectReport === "function") {
          selectReport(latest.date, latest.time);
          return;
        }
      } catch (error) {
        console.warn("latest report selection failed", error);
      }
    }

    const url = new URL(location.href);
    url.searchParams.set("date", latest.date);
    url.searchParams.set("time", latest.time);
    history.replaceState(null, "", url);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", chooseLatest, { once: true });
  } else {
    chooseLatest();
  }
})();
