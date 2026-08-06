(() => {
  "use strict";

  const byId = (id) => document.getElementById(id);
  const clean = (value) => String(value || "").replace(/\s+/g, " ").trim();
  const asArray = (value) => Array.isArray(value) ? value.filter(Boolean) : (value ? [value] : []);
  const unusable = (value) => {
    const text = clean(value);
    return !text || /^(取得不能|未取得|未判定|JSONにありません|理由：.*ありません|予定なし|時刻が確定している重要イベントはありません)[。\s]*$/.test(text);
  };

  function currentReport() {
    if (typeof selectedReport !== "undefined" && selectedReport) return selectedReport;
    if (typeof reports !== "undefined" && Array.isArray(reports) && reports.length) return reports[0];
    return null;
  }

  function fullText(report) {
    return String(report?.fullText || report?.rawText || report?.body || "").replace(/\r/g, "");
  }

  function extractSection(report, names) {
    const text = fullText(report);
    if (!text) return [];
    const lines = text.split(/\n+/).map((line) => line.trim());
    const start = lines.findIndex((line) => names.some((name) => new RegExp(`^(?:\\d{1,2}[.．]\\s*)?${name}(?:[（(].*?[）)])?[：:]?$`).test(line)));
    if (start < 0) return [];
    const out = [];
    for (let i = start + 1; i < lines.length; i += 1) {
      const line = lines[i];
      if (!line) continue;
      if (/^\d{1,2}[.．]\s+/.test(line)) break;
      if (names.some((name) => line === name)) continue;
      out.push(line.replace(/^[・\-–—]\s*/, ""));
      if (out.length >= 8) break;
    }
    return out.filter(Boolean);
  }

  function firstUseful(...values) {
    for (const value of values.flat()) {
      const text = clean(value);
      if (!unusable(text)) return text;
    }
    return "";
  }

  function hide(node) {
    if (node) node.style.display = "none";
  }

  function show(node) {
    if (node) node.style.display = "";
  }

  function setProse(id, text) {
    const node = byId(id);
    if (!node) return false;
    if (!text) return false;
    node.innerHTML = `<p>${text.replace(/</g, "&lt;").replace(/>/g, "&gt;")}</p>`;
    return true;
  }

  function fillLeadingMarket(report) {
    const node = byId("leadingMarket");
    const card = node?.closest("article");
    if (!node || !card) return;
    const existing = clean(node.textContent);
    if (!unusable(existing)) return show(card);
    const section = extractSection(report, ["今日の主導市場", "主導市場"]);
    const fallback = firstUseful(section, report?.leadingMarket, asArray(report?.consistency), report?.theme);
    if (fallback) {
      setProse("leadingMarket", fallback);
      show(card);
    } else hide(card);
  }

  function fillPositioning(report) {
    const list = byId("positionList");
    const card = list?.closest("article");
    if (!list || !card) return;
    const existing = [...list.querySelectorAll("li")].map((li) => clean(li.textContent)).filter((v) => !unusable(v));
    if (existing.length) return show(card);
    let items = extractSection(report, ["需給・ポジション", "ポジションの偏り"]);
    if (!items.length) items = asArray(report?.positioning).map(clean).filter((v) => !unusable(v));
    if (!items.length) {
      items = asArray(report?.markets).map((m) => clean(m?.positioning)).filter((v) => !unusable(v));
    }
    if (!items.length) return hide(card);
    list.innerHTML = items.slice(0, 8).map((item) => `<li>${item.replace(/</g, "&lt;").replace(/>/g, "&gt;")}</li>`).join("");
    show(card);
  }

  function parseEventLine(line, report) {
    const text = clean(line);
    if (!text) return null;
    const time = text.match(/\b([0-2]\d:[0-5]\d)\b/)?.[1] || "時刻未定";
    const title = clean(text.replace(/\b[0-2]\d:[0-5]\d\b/, "").replace(/^[・\-–—\s]+/, ""));
    if (!title) return null;
    return { time, title, date: report?.date || "" };
  }

  function fillEvents(report) {
    const body = byId("eventRows");
    const panel = body?.closest("section");
    if (!body || !panel) return;
    const existingRows = [...body.querySelectorAll("tr")].filter((tr) => {
      const text = clean(tr.textContent);
      return text && !/予定なし|時刻が確定している重要イベントはありません/.test(text);
    });
    if (existingRows.length) return show(panel);
    let lines = extractSection(report, ["今後のイベント", "今後の重要イベント", "重要イベント"]);
    if (!lines.length) lines = asArray(report?.events).map(clean).filter(Boolean);
    const rows = lines.map((line) => parseEventLine(line, report)).filter(Boolean);
    if (!rows.length) return hide(panel);
    body.innerHTML = rows.slice(0, 8).map((row) => `<tr><td>${row.time}</td><td><span class="event-title">${row.title.replace(/</g, "&lt;").replace(/>/g, "&gt;")}</span></td><td>-</td><td>-</td><td>-</td></tr>`).join("");
    show(panel);
  }

  function fillScenario(report, id, field, headings) {
    const node = byId(id);
    const card = node?.closest("article");
    if (!node || !card) return;
    const existing = clean(node.textContent);
    if (!unusable(existing)) return show(card);
    const section = extractSection(report, headings);
    const fallback = firstUseful(section, report?.[field]);
    if (fallback) {
      setProse(id, fallback);
      show(card);
    } else hide(card);
  }

  function guardMarketCards() {
    const wrap = byId("marketCards");
    const section = wrap?.closest("section");
    if (!wrap || !section) return;
    const cards = [...wrap.querySelectorAll(".market-card")];
    let visible = 0;
    cards.forEach((card) => {
      const value = clean(card.querySelector(".market-value")?.textContent);
      const reason = clean(card.querySelector("dd")?.textContent);
      const useful = !unusable(value) || !unusable(reason);
      card.style.display = useful ? "" : "none";
      if (useful) visible += 1;
    });
    section.style.display = visible ? "" : "none";
  }

  function guardFlow(report) {
    const panel = byId("flowInItems")?.closest("article");
    if (!panel) return;
    const useful = [...panel.querySelectorAll("li")].some((li) => !unusable(li.textContent) && !/JSONにありません|自動判定しています/.test(li.textContent));
    if (useful) return show(panel);
    const lines = extractSection(report, ["クロスアセット資金フロー", "資金フロー"]);
    if (!lines.length && !asArray(report?.crossAssetFlow).length) return hide(panel);
    show(panel);
  }

  function guardTemperature() {
    const section = byId("market-environment");
    if (!section) return;
    const cards = [...section.querySelectorAll(".temperature-mini-card,.environment-card,.temperature-card")];
    if (!cards.length) return hide(section);
    const useful = cards.some((card) => !unusable(card.textContent) && !/読み込み中|未取得|取得不能/.test(card.textContent));
    section.style.display = useful ? "" : "none";
  }

  function apply() {
    const report = currentReport();
    if (!report) return;
    fillLeadingMarket(report);
    fillPositioning(report);
    fillEvents(report);
    fillScenario(report, "mainScenario", "mainScenario", ["メインシナリオ"]);
    fillScenario(report, "alternativeScenario", "alternativeScenario", ["代替シナリオ"]);
    fillScenario(report, "breakConditions", "breakConditions", ["崩れる条件", "シナリオが崩れる条件"]);
    guardMarketCards();
    guardFlow(report);
    guardTemperature();
  }

  let scheduled = false;
  const schedule = () => {
    if (scheduled) return;
    scheduled = true;
    window.setTimeout(() => {
      scheduled = false;
      apply();
    }, 80);
  };

  const observer = new MutationObserver(schedule);
  observer.observe(document.documentElement, { childList: true, subtree: true, characterData: true });
  window.addEventListener("load", schedule);
  window.addEventListener("popstate", schedule);
  window.setInterval(schedule, 1500);
})();