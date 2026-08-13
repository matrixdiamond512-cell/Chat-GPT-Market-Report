(() => {
  "use strict";

  const MAX_ATTEMPTS = 80;
  const LATEST_REPORT_PATH = "data/latest-report.json";
  let attempts = 0;
  let overrideLoaded = false;

  function keyOf(item) {
    return `${item?.date || ""} ${item?.time || ""}`;
  }

  function qaResult(item) {
    try {
      if (window.MorningReportQA && typeof window.MorningReportQA.validate === "function") {
        return window.MorningReportQA.validate(item);
      }
    } catch (error) {
      console.warn("morning report QA evaluation failed", error);
    }
    return { ready: true, enforced: false, reasons: [] };
  }

  function isPublishable(item) {
    const qa = qaResult(item);
    if (!qa.ready) {
      console.error("08:00 report blocked by publication QA", keyOf(item), qa.reasons);
      window.morningReportQaBlocked = { report: item, ...qa };
      return false;
    }
    return true;
  }

  function latestReport(list) {
    return list
      .filter((item) => item && /^\d{4}-\d{2}-\d{2}$/.test(item.date || "") && /^\d{2}:\d{2}$/.test(item.time || ""))
      .filter(isPublishable)
      .slice()
      .sort((a, b) => keyOf(b).localeCompare(keyOf(a)))[0] || null;
  }

  function shouldKeepHistoricalSelection(latest) {
    const params = new URLSearchParams(location.search);
    const requestedDate = params.get("date");
    return Boolean(requestedDate && requestedDate < latest.date);
  }

  function fullTextScore(value) {
    const text = String(value || "").replace(/\r/g, "");
    if (!text.trim()) return 0;
    const bracketHeadings = (text.match(/^【[^\n】]{2,60}】\s*$/gm) || []).length;
    const numberedHeadings = (text.match(/^\s*\d{1,2}[．.]\s*[^\n]+$/gm) || []).length;
    const requiredHits = [
      /今日の相場テーマ/,
      /主要市場データ|主要市場まとめ/,
      /材料と値動きの整合性/,
      /主導市場/,
      /クロスアセット資金フロー/,
      /需給・ポジション/,
      /個別(?:市場)?見通し|6市場の(?:個別)?見通し/,
      /シナリオ/,
      /崩れる条件/,
      /結論|最終判断/
    ].filter((pattern) => pattern.test(text)).length;
    return bracketHeadings * 4 + numberedHeadings * 4 + requiredHits * 3 + Math.min(10, Math.floor(text.length / 800));
  }

  function chooseFullText(previous, candidate) {
    const priorText = String(previous?.fullText || previous?.rawText || previous?.body || "");
    const nextText = String(candidate?.fullText || candidate?.rawText || candidate?.body || "");
    if (!priorText.trim()) return nextText;
    if (!nextText.trim()) return priorText;
    const priorScore = fullTextScore(priorText);
    const nextScore = fullTextScore(nextText);
    if (nextScore < priorScore) {
      console.warn("short/incomplete latest-report fullText rejected; preserving richer history body", { priorScore, nextScore });
      return priorText;
    }
    return nextText;
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
      const proposed = {
        ...previous,
        ...candidate,
        fullText: chooseFullText(previous, candidate)
      };

      if (!isPublishable(proposed)) {
        console.error("latest-report override rejected by QA", keyOf(proposed));
        return;
      }

      merged.set(keyOf(candidate), proposed);
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

    try {
      if (window.MorningReportQA && typeof window.MorningReportQA.loadReference === "function") {
        await window.MorningReportQA.loadReference();
      }
    } catch (error) {
      console.warn("morning report QA reference initialization failed", error);
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
