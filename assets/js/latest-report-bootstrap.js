(() => {
  "use strict";

  const MAX_ATTEMPTS = 80;
  const LATEST_REPORT_PATH = "data/latest-report.json";
  let attempts = 0;
  let overrideLoaded = false;

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

  async function mergeLatestOverride() {
    if (overrideLoaded) return;
    overrideLoaded = true;

    try {
      const response = await fetch(`${LATEST_REPORT_PATH}?ts=${Date.now()}`, { cache: "no-store" });
      if (!response.ok) return;
      const payload = await response.json();
      const candidate = payload?.latestReport || payload?.report || payload;
      if (!candidate || !/^\d{4}-\d{2}-\d{2}$/.test(candidate.date || "") || !/^\d{2}:\d{2}$/.test(candidate.time || "")) return;

      let list = [];
      try {
        list = Array.isArray(reports) ? reports : [];
      } catch (error) {
        list = [];
      }

      const merged = new Map(list.map((item) => [keyOf(item), item]));
      const previous = merged.get(keyOf(candidate)) || {};
      merged.set(keyOf(candidate), {
        ...previous,
        ...candidate,
        fullText: candidate.fullText || previous.fullText || ""
      });

      reports = [...merged.values()]
        .filter((item) => item && /^\d{4}-\d{2}-\d{2}$/.test(item.date || ""))
        .sort((a, b) => keyOf(b).localeCompare(keyOf(a)));
    } catch (error) {
      console.warn("latest report override load failed", error);
    }
  }

  async function chooseLatest() {
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

    await mergeLatestOverride();

    try {
      list = Array.isArray(reports) ? reports : [];
    } catch (error) {
      list = [];
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
