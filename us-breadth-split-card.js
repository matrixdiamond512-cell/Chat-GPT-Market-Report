(() => {
  "use strict";

  const DATA_PATH = "data/market/us-stock-breadth.json";
  let cachedPayload = null;
  let renderQueued = false;

  function esc(value) {
    return String(value ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  function fmt(value) {
    const number = Number(value);
    return Number.isFinite(number) ? number.toLocaleString("ja-JP") : "—";
  }

  function ratio(value) {
    const number = Number(value);
    return Number.isFinite(number) ? number.toFixed(2) : "—";
  }

  function rate(value) {
    const number = Number(value);
    return Number.isFinite(number) ? `${(number * 100).toFixed(1)}%` : "—";
  }

  function findUsBreadthCard() {
    const headings = [...document.querySelectorAll("h2, h3")];
    const heading = headings.find((node) => node.textContent.trim() === "アメリカ株の広がり");
    if (!heading) return null;
    return heading.closest("article")
      || heading.closest(".environment-summary-card")
      || heading.closest(".panel")
      || heading.parentElement;
  }

  function exchangeBlock(name, row) {
    const total = Number(row?.advancers || 0) + Number(row?.decliners || 0) + Number(row?.unchanged || 0);
    const advanceRate = total > 0 ? Number(row.advancers || 0) / total : null;
    return `
      <section class="us-breadth-exchange" aria-label="${esc(name)}の市場内部">
        <div class="us-breadth-exchange-head">
          <strong>${esc(name)}</strong>
          <span>A/D比 ${esc(ratio(row?.advanceDeclineRatio))}</span>
        </div>
        <div class="us-breadth-number-grid">
          <div><b>${esc(fmt(row?.advancers))}</b><small>値上がり</small></div>
          <div><b>${esc(fmt(row?.unchanged))}</b><small>変わらず</small></div>
          <div><b>${esc(fmt(row?.decliners))}</b><small>値下がり</small></div>
        </div>
        <div class="us-breadth-bar" role="img" aria-label="${esc(name)} 値上がり比率 ${esc(rate(advanceRate))}">
          <span class="up" style="width:${Number.isFinite(advanceRate) ? advanceRate * 100 : 0}%"></span>
          <span class="flat" style="width:${total > 0 ? Number(row?.unchanged || 0) / total * 100 : 0}%"></span>
          <span class="down"></span>
        </div>
      </section>`;
  }

  function installStyle() {
    if (document.getElementById("usBreadthSplitStyle")) return;
    const style = document.createElement("style");
    style.id = "usBreadthSplitStyle";
    style.textContent = `
      .us-breadth-split-card{display:grid!important;gap:10px}
      .us-breadth-split-title{display:flex;justify-content:space-between;align-items:flex-start;gap:12px}
      .us-breadth-split-title h2,.us-breadth-split-title h3{margin:0}
      .us-breadth-split-title p{margin:2px 0 0;font-size:12px;color:#50627a}
      .us-breadth-judgement{padding:4px 8px;border-radius:6px;background:#eef3fb;font-weight:700;font-size:12px;white-space:nowrap}
      .us-breadth-exchanges{display:grid;grid-template-columns:1fr 1fr;gap:10px}
      .us-breadth-exchange{border:1px solid #d8e2ef;border-radius:8px;padding:9px;background:#fff}
      .us-breadth-exchange-head{display:flex;justify-content:space-between;align-items:center;margin-bottom:7px}
      .us-breadth-exchange-head strong{font-size:15px;color:#0d2b54}
      .us-breadth-exchange-head span{font-size:11px;color:#52657c}
      .us-breadth-number-grid{display:grid;grid-template-columns:repeat(3,1fr);text-align:center;gap:6px}
      .us-breadth-number-grid b{display:block;font-size:18px;color:#0b2c58}
      .us-breadth-number-grid small{display:block;font-size:10px;color:#52657c}
      .us-breadth-bar{height:8px;display:flex;overflow:hidden;border-radius:999px;background:#d83245;margin-top:8px}
      .us-breadth-bar .up{background:#17883a}.us-breadth-bar .flat{background:#e5b225}.us-breadth-bar .down{background:#d83245;flex:1}
      .us-breadth-foot{display:flex;justify-content:space-between;gap:10px;font-size:11px;color:#52657c}
      @media(max-width:700px){.us-breadth-exchanges{grid-template-columns:1fr}.us-breadth-foot{display:block}.us-breadth-foot span{display:block;margin-top:3px}}
    `;
    document.head.appendChild(style);
  }

  function render(payload) {
    const card = findUsBreadthCard();
    const nyse = payload?.exchanges?.NYSE;
    const nasdaq = payload?.exchanges?.NASDAQ;
    if (!card || !nyse || !nasdaq) return false;
    if (card.dataset.usBreadthSplitKey === `${payload.marketDate}|${nyse.advancers}|${nasdaq.advancers}`
      && card.querySelector(".us-breadth-exchanges")) return true;

    installStyle();
    card.classList.add("us-breadth-split-card");
    card.dataset.usBreadthSplitKey = `${payload.marketDate}|${nyse.advancers}|${nasdaq.advancers}`;
    card.innerHTML = `
      <div class="us-breadth-split-title">
        <div>
          <h2>アメリカ株の広がり</h2>
          <p>NYSE・NASDAQを別々に表示</p>
        </div>
        <span class="us-breadth-judgement">${esc(payload.judgement || "判定なし")}</span>
      </div>
      <div class="us-breadth-exchanges">
        ${exchangeBlock("NYSE", nyse)}
        ${exchangeBlock("NASDAQ", nasdaq)}
      </div>
      <div class="us-breadth-foot">
        <span>合算値上がり比率 ${esc(rate(payload.combinedAdvanceRate))}</span>
        <span>基準 ${esc(payload.marketDate || "—")}</span>
      </div>`;
    return true;
  }

  function scheduleRender() {
    if (!cachedPayload || renderQueued) return;
    renderQueued = true;
    window.requestAnimationFrame(() => {
      renderQueued = false;
      render(cachedPayload);
    });
  }

  function watchDashboardRerenders() {
    const root = document.getElementById("environmentSummary") || document.body;
    const observer = new MutationObserver(() => scheduleRender());
    observer.observe(root, { childList: true, subtree: true });
    window.addEventListener("popstate", scheduleRender);
    window.addEventListener("us-stock-breadth-loaded", scheduleRender);
  }

  async function loadAndRender() {
    try {
      const response = await fetch(`${DATA_PATH}?ts=${Date.now()}`, { cache: "no-store" });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      cachedPayload = await response.json();
      installStyle();
      watchDashboardRerenders();
      let attempts = 0;
      const timer = window.setInterval(() => {
        attempts += 1;
        if (render(cachedPayload) || attempts >= 120) window.clearInterval(timer);
      }, 250);
    } catch (error) {
      console.warn("US breadth split card load failed", error);
    }
  }

  loadAndRender();
})();
