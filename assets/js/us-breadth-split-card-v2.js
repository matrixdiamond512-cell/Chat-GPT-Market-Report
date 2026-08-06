(() => {
  "use strict";

  const DATA_PATH = "data/market/us-stock-breadth.json";
  let payloadCache = null;
  let rendering = false;

  function esc(value) {
    return String(value ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/\"/g, "&quot;")
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

  function exchangeBlock(name, row) {
    const adv = Number(row?.advancers || 0);
    const dec = Number(row?.decliners || 0);
    const flat = Number(row?.unchanged || 0);
    const total = adv + dec + flat;
    const upRate = total > 0 ? adv / total : 0;
    const flatRate = total > 0 ? flat / total : 0;
    return `
      <section class="us-breadth-exchange" aria-label="${esc(name)}の市場内部">
        <div class="us-breadth-exchange-head">
          <strong>${esc(name)}</strong>
          <span>A/D比 ${esc(ratio(row?.advanceDeclineRatio))}</span>
        </div>
        <div class="us-breadth-number-grid">
          <div><b>${esc(fmt(adv))}</b><small>値上がり</small></div>
          <div><b>${esc(fmt(flat))}</b><small>変わらず</small></div>
          <div><b>${esc(fmt(dec))}</b><small>値下がり</small></div>
        </div>
        <div class="us-breadth-bar">
          <span class="up" style="width:${upRate * 100}%"></span>
          <span class="flat" style="width:${flatRate * 100}%"></span>
          <span class="down"></span>
        </div>
      </section>`;
  }

  function installStyle() {
    if (document.getElementById("usBreadthSplitStyleV2")) return;
    const style = document.createElement("style");
    style.id = "usBreadthSplitStyleV2";
    style.textContent = `
      #usBreadthSplitCardV2{display:grid;gap:10px;border:1px solid #cfd9e8;border-radius:10px;padding:12px;background:#fff}
      #usBreadthSplitCardV2 .us-breadth-split-title{display:flex;justify-content:space-between;align-items:flex-start;gap:12px}
      #usBreadthSplitCardV2 h3{margin:0;color:#0d2b54;font-size:17px}
      #usBreadthSplitCardV2 .subtitle{margin:2px 0 0;font-size:11px;color:#50627a}
      #usBreadthSplitCardV2 .us-breadth-judgement{padding:4px 8px;border-radius:6px;background:#eef3fb;font-weight:700;font-size:12px;white-space:nowrap}
      #usBreadthSplitCardV2 .us-breadth-exchanges{display:grid;grid-template-columns:1fr 1fr;gap:10px}
      #usBreadthSplitCardV2 .us-breadth-exchange{border:1px solid #d8e2ef;border-radius:8px;padding:9px;background:#fff}
      #usBreadthSplitCardV2 .us-breadth-exchange-head{display:flex;justify-content:space-between;align-items:center;margin-bottom:7px}
      #usBreadthSplitCardV2 .us-breadth-exchange-head strong{font-size:15px;color:#0d2b54}
      #usBreadthSplitCardV2 .us-breadth-exchange-head span{font-size:11px;color:#52657c}
      #usBreadthSplitCardV2 .us-breadth-number-grid{display:grid;grid-template-columns:repeat(3,1fr);text-align:center;gap:6px}
      #usBreadthSplitCardV2 .us-breadth-number-grid b{display:block;font-size:18px;color:#0b2c58}
      #usBreadthSplitCardV2 .us-breadth-number-grid small{display:block;font-size:10px;color:#52657c}
      #usBreadthSplitCardV2 .us-breadth-bar{height:8px;display:flex;overflow:hidden;border-radius:999px;background:#d83245;margin-top:8px}
      #usBreadthSplitCardV2 .us-breadth-bar .up{background:#17883a}
      #usBreadthSplitCardV2 .us-breadth-bar .flat{background:#e5b225}
      #usBreadthSplitCardV2 .us-breadth-bar .down{background:#d83245;flex:1}
      #usBreadthSplitCardV2 .us-breadth-foot{display:flex;justify-content:space-between;gap:10px;font-size:11px;color:#52657c}
      @media(max-width:700px){#usBreadthSplitCardV2 .us-breadth-exchanges{grid-template-columns:1fr}#usBreadthSplitCardV2 .us-breadth-foot{display:block}}
    `;
    document.head.appendChild(style);
  }

  function hideCombinedUsCard(container) {
    [...container.children].forEach((node) => {
      if (node.id === "usBreadthSplitCardV2") return;
      const text = (node.textContent || "").replace(/\s+/g, " ");
      if (text.includes("アメリカ株の広がり")) node.style.display = "none";
    });
  }

  function ensureCard(payload) {
    if (rendering) return;
    const container = document.getElementById("environmentSummary") || document.getElementById("temperatureMiniCards");
    const nyse = payload?.exchanges?.NYSE;
    const nasdaq = payload?.exchanges?.NASDAQ;
    if (!container || !nyse || !nasdaq) return;

    rendering = true;
    installStyle();
    hideCombinedUsCard(container);

    let card = document.getElementById("usBreadthSplitCardV2");
    if (!card) {
      card = document.createElement("article");
      card.id = "usBreadthSplitCardV2";
      container.prepend(card);
    }

    card.innerHTML = `
      <div class="us-breadth-split-title">
        <div>
          <h3>アメリカ株の広がり</h3>
          <p class="subtitle">NYSE・NASDAQを別々に表示</p>
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
    rendering = false;
  }

  async function start() {
    try {
      const response = await fetch(`${DATA_PATH}?v=20260807-0225-${Date.now()}`, { cache: "no-store" });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      payloadCache = await response.json();
      ensureCard(payloadCache);

      const observer = new MutationObserver(() => {
        if (payloadCache) ensureCard(payloadCache);
      });
      observer.observe(document.body, { childList: true, subtree: true });
      window.addEventListener("us-stock-breadth-loaded", () => ensureCard(payloadCache));
      window.setInterval(() => ensureCard(payloadCache), 1000);
    } catch (error) {
      console.warn("US breadth split card v2 failed", error);
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", start, { once: true });
  } else {
    start();
  }
})();
