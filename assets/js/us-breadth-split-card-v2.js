(() => {
  "use strict";

  const DATA_PATH = "data/market/us-stock-breadth.json";
  let payload = null;
  let installed = false;

  const htmlEscape = (value) => String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");

  const numberText = (value) => {
    const number = Number(value);
    return Number.isFinite(number) ? number.toLocaleString("ja-JP") : "－";
  };

  const ratioText = (value) => {
    const number = Number(value);
    return Number.isFinite(number) ? number.toFixed(2) : "－";
  };

  function exchangeHtml(name, row) {
    const advancers = Number(row?.advancers);
    const decliners = Number(row?.decliners);
    const unchanged = Number(row?.unchanged);
    const safeAdvancers = Number.isFinite(advancers) ? advancers : 0;
    const safeDecliners = Number.isFinite(decliners) ? decliners : 0;
    const safeUnchanged = Number.isFinite(unchanged) ? unchanged : 0;
    const total = safeAdvancers + safeDecliners + safeUnchanged;
    const advPct = total > 0 ? safeAdvancers / total * 100 : 0;
    const flatPct = total > 0 ? safeUnchanged / total * 100 : 0;
    const decPct = Math.max(0, 100 - advPct - flatPct);

    return `<section class="us-exchange-breadth" aria-label="${htmlEscape(name)}の市場内部">
      <div class="us-exchange-head">
        <strong>${htmlEscape(name)}</strong>
        <span>騰落比 ${htmlEscape(ratioText(row?.advanceDeclineRatio))}倍</span>
      </div>
      <div class="breadth-values">
        <span><b>${htmlEscape(numberText(row?.advancers))}</b>値上がり</span>
        <span><b>${htmlEscape(numberText(row?.unchanged))}</b>変わらず</span>
        <span><b>${htmlEscape(numberText(row?.decliners))}</b>値下がり</span>
      </div>
      <div class="breadth-bar" aria-label="値上がり ${advPct.toFixed(0)}%、変わらず ${flatPct.toFixed(0)}%、値下がり ${decPct.toFixed(0)}%">
        <span class="breadth-up" style="width:${advPct}%"></span>
        <span class="breadth-flat" style="width:${flatPct}%"></span>
        <span class="breadth-down" style="width:${decPct}%"></span>
      </div>
    </section>`;
  }

  function installStyles() {
    if (document.getElementById("usBreadthDirectStyle")) return;
    const style = document.createElement("style");
    style.id = "usBreadthDirectStyle";
    style.textContent = `
      .us-breadth-direct-card{grid-column:span 2}
      .us-breadth-direct-card .us-breadth-exchanges{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:10px}
      .us-breadth-direct-card .us-exchange-breadth{border:1px solid #d8e2ef;border-radius:8px;padding:10px;background:#fff}
      .us-breadth-direct-card .us-exchange-head{display:flex;justify-content:space-between;gap:8px;align-items:center;margin-bottom:8px}
      .us-breadth-direct-card .us-exchange-head strong{font-size:15px;color:#0d2b54}
      .us-breadth-direct-card .us-exchange-head span{font-size:11px;color:#52657c}
      .us-breadth-direct-card .us-breadth-foot{display:flex;justify-content:space-between;gap:10px;margin-top:9px;font-size:11px;color:#52657c}
      @media(max-width:700px){.us-breadth-direct-card{grid-column:span 1}.us-breadth-direct-card .us-breadth-exchanges{grid-template-columns:1fr}.us-breadth-direct-card .us-breadth-foot{display:block}}
    `;
    document.head.appendChild(style);
  }

  function splitUsBreadthHtml() {
    const nyse = payload?.exchanges?.NYSE;
    const nasdaq = payload?.exchanges?.NASDAQ;
    if (!nyse || !nasdaq) return "";

    const combinedRate = Number(payload?.combinedAdvanceRate);
    const combinedText = Number.isFinite(combinedRate)
      ? `${(combinedRate * 100).toFixed(1)}%`
      : "－";

    return `<article class="temperature-mini-card breadth-card us-breadth-direct-card temperature-tone-fear">
      <div class="temperature-mini-head">
        <div><h3>アメリカ株の広がり</h3><p>NYSE・NASDAQを個別表示</p></div>
        <b class="breadth-status">${htmlEscape(payload?.judgement || "判定保留")}</b>
      </div>
      <div class="us-breadth-exchanges">
        ${exchangeHtml("NYSE", nyse)}
        ${exchangeHtml("NASDAQ", nasdaq)}
      </div>
      <div class="us-breadth-foot">
        <span>合算値上がり比率 ${htmlEscape(combinedText)}</span>
        <span>基準 ${htmlEscape(payload?.marketDate || "－")}</span>
      </div>
      <p class="temperature-source">NYSE・NASDAQ市場内部データ｜詳細は株式市場分析</p>
    </article>`;
  }

  function installRenderer() {
    if (installed || !payload) return false;
    if (typeof renderBreadthCard !== "function") return false;

    const originalRenderBreadthCard = renderBreadthCard;
    renderBreadthCard = function patchedRenderBreadthCard(region, report) {
      if (region === "us") {
        const html = splitUsBreadthHtml();
        if (html) return html;
      }
      return originalRenderBreadthCard(region, report);
    };

    installed = true;
    installStyles();
    if (typeof renderTemperatureMini === "function" && typeof selectedReport !== "undefined" && selectedReport) {
      renderTemperatureMini(selectedReport);
    }
    return true;
  }

  async function start() {
    try {
      const response = await fetch(`${DATA_PATH}?ts=${Date.now()}`, { cache: "no-store" });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      payload = await response.json();

      let attempts = 0;
      const timer = window.setInterval(() => {
        attempts += 1;
        if (installRenderer() || attempts >= 80) window.clearInterval(timer);
      }, 100);
    } catch (error) {
      console.warn("NYSE/NASDAQ split renderer failed", error);
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", start, { once: true });
  } else {
    start();
  }
})();
