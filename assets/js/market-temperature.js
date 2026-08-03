const STATUS_META = {
  normal: { label: "平常", cls: "normal", color: "#008453" },
  caution: { label: "注意", cls: "caution", color: "#f0aa00" },
  warning: { label: "警戒", cls: "warning", color: "#f06a00" },
  stress: { label: "ストレス", cls: "stress", color: "#e00022" },
  imbalance: { label: "不整合", cls: "imbalance", color: "#7b46c5" },
  unavailable: { label: "算出準備中", cls: "unavailable", color: "#9aa8ba" }
};

const $ = (selector, root = document) => root.querySelector(selector);

function esc(value = "") {
  return String(value).replace(/[&<>"']/g, (char) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    "\"": "&quot;",
    "'": "&#039;"
  })[char]);
}

function arr(value) {
  return Array.isArray(value) ? value : value ? [value] : [];
}

function textOf(value) {
  if (typeof value === "string") return value;
  if (!value) return "";
  return value.text || value.summary || value.title || value.name || "";
}

function cleanText(value = "", max = 120) {
  const text = String(value).replace(/\s+/g, " ").replace(/^[・\s]+/, "").trim();
  if (!text) return "";
  return text.length > max ? `${text.slice(0, max)}...` : text;
}

function latestReport(reports) {
  const list = Array.isArray(reports) ? [...reports] : [];
  list.sort((a, b) => `${b.date || ""} ${b.time || ""}`.localeCompare(`${a.date || ""} ${a.time || ""}`));
  return list[0] || null;
}

function reportText(report) {
  if (!report) return "";
  return [
    report.title,
    report.theme,
    arr(report.changes).map(textOf).join(" "),
    report.leadingMarket,
    arr(report.crossAssetFlow).map(textOf).join(" "),
    arr(report.positioning).map(textOf).join(" "),
    report.mainScenario,
    report.alternativeScenario,
    report.breakConditions,
    arr(report.handover).map(textOf).join(" "),
    report.fullText
  ].filter(Boolean).join(" ");
}

function findValue(text, patterns) {
  for (const pattern of patterns) {
    const match = text.match(pattern);
    if (!match) continue;
    const raw = match[1] || "";
    if (/取得不能|未確認|確認できず/.test(raw)) return { missing: true, reason: raw };
    const value = Number(String(raw).replace(/,/g, ""));
    if (Number.isFinite(value)) return { value };
  }
  return null;
}

function getMetricFromReport(metric, report) {
  const text = reportText(report);
  const id = metric.id;
  const resultById = {
    "market.vix": () => findValue(text, [/VIX[：:\s]+(取得不能[^。\n]*|[0-9,.]+)/]),
    "market.nikkei_vi": () => findValue(text, [/日経VI[：:\s]+(取得不能[^。\n]*|[0-9,.]+)/]),
    "sentiment.cnn_fear_greed": () => findValue(text, [/Fear\s*&\s*Greed(?:\s*Index)?[：:\s]+(取得不能[^。\n]*|[0-9,.]+)/i]),
    "rates.us_10y": () => findValue(text, [/米10年債利回り[：:\s]*([0-9,.]+)%?/, /米10年[：:\s]*([0-9,.]+)%/]),
    "rates.jp_10y": () => findValue(text, [/日本10年国債利回り[：:\s]+(取得不能[^。\n]*|[0-9,.]+)%?/])
  };
  const found = resultById[id]?.();
  if (!found) return null;
  if (found.missing) return {
    ...metric,
    value: null,
    status: "missing",
    missingReason: found.reason || metric.missingReason,
    sourceName: `${metric.sourceName} / 最新マーケットレポート本文`
  };
  return {
    ...metric,
    value: found.value,
    status: "report",
    asOf: report ? `${report.date || ""} ${report.time || ""}`.trim() : null,
    sourceName: `${metric.sourceName} / 最新マーケットレポート本文`,
    missingReason: ""
  };
}

function metricRiskScore(metric) {
  if (metric.status === "missing" || metric.value == null || metric.value === "") return null;
  const value = Number(metric.value);
  if (!Number.isFinite(value)) return null;
  switch (metric.id) {
    case "market.vix":
      if (value >= 30) return 86;
      if (value >= 24) return 72;
      if (value >= 20) return 60;
      if (value >= 15) return 38;
      return 18;
    case "market.nikkei_vi":
      if (value >= 35) return 86;
      if (value >= 28) return 72;
      if (value >= 22) return 58;
      if (value >= 16) return 36;
      return 18;
    case "sentiment.cnn_fear_greed":
      return Math.max(0, Math.min(100, 100 - value));
    case "rates.us_10y":
      if (value >= 5) return 78;
      if (value >= 4.6) return 64;
      if (value >= 4.2) return 50;
      if (value >= 3.8) return 36;
      return 24;
    case "rates.jp_10y":
      if (value >= 1.5) return 72;
      if (value >= 1.2) return 58;
      if (value >= 0.9) return 44;
      return 26;
    default:
      return null;
  }
}

function statusFromScore(score) {
  if (!Number.isFinite(score)) return STATUS_META.unavailable;
  if (score <= 25) return STATUS_META.normal;
  if (score <= 50) return STATUS_META.caution;
  if (score <= 75) return STATUS_META.warning;
  return STATUS_META.stress;
}

function formatValue(metric) {
  if (metric.status === "missing" || metric.value == null || metric.value === "") return "取得不能";
  const value = Number(metric.value);
  if (Number.isFinite(value)) {
    const digits = Math.abs(value) >= 100 ? 0 : Math.abs(value) >= 10 ? 2 : 3;
    return `${value.toLocaleString("ja-JP", { maximumFractionDigits: digits })}${metric.unit || ""}`;
  }
  return cleanText(metric.value, 18);
}

function riskMark(score) {
  if (!Number.isFinite(score)) return { mark: "-", cls: "missing", title: "取得不能" };
  if (score >= 56) return { mark: "↑", cls: "up", title: "リスク上昇" };
  if (score <= 30) return { mark: "↓", cls: "down", title: "リスク低下" };
  return { mark: "→", cls: "flat", title: "中立" };
}

function reportDerivedCategoryScore(id, report) {
  const text = reportText(report);
  if (!text) return null;
  if (id === "flows") {
    let score = 38;
    if (/米国債|金|円/.test(text) && /流入|買い|安全資産/.test(text)) score += 10;
    if (/ドル高|資金調達|流動性/.test(text)) score += 8;
    if (/株高|リスクオン|大型テック/.test(text)) score -= 6;
    return Math.max(20, Math.min(70, score));
  }
  if (id === "positioning") {
    let score = 42;
    if (/円ショート|円キャリー|巻き戻し|ショートカバー/.test(text)) score += 18;
    if (/介入|急反転|ポジション/.test(text)) score += 8;
    return Math.max(25, Math.min(76, score));
  }
  if (id === "credit" && /信用|クレジット|HY|スプレッド/.test(text)) return 55;
  if (id === "options" && /VIX|ヘッジ|オプション|ボラティリティ/.test(text)) return 50;
  return null;
}

function buildCategories(config, report) {
  return arr(config.categories).map((category) => {
    const metrics = arr(category.metrics).map((metric) => {
      const hydrated = metric.value == null ? getMetricFromReport(metric, report) || metric : metric;
      const score = metricRiskScore(hydrated);
      return { ...hydrated, riskScore: score };
    });
    const metricScores = metrics.map((metric) => metric.riskScore).filter(Number.isFinite);
    const derivedScore = metricScores.length
      ? Math.round(metricScores.reduce((sum, value) => sum + value, 0) / metricScores.length)
      : reportDerivedCategoryScore(category.id, report);
    const sourceType = metricScores.length ? "取得済み指標" : Number.isFinite(derivedScore) ? "本文判定" : "未連携";
    return {
      ...category,
      metrics,
      score: Number.isFinite(derivedScore) ? derivedScore : null,
      statusMeta: statusFromScore(derivedScore),
      sourceType
    };
  });
}

function weightedOverall(categories, weights) {
  let total = 0;
  let denom = 0;
  categories.forEach((category) => {
    if (!Number.isFinite(category.score)) return;
    const weight = Number(weights?.[category.id]) || 1;
    total += category.score * weight;
    denom += weight;
  });
  if (!denom) return { score: null, used: 0, total: categories.length };
  return { score: Math.round(total / denom), used: categories.filter((category) => Number.isFinite(category.score)).length, total: categories.length };
}

function gaugeHtml(score, label, extraClass = "") {
  const meta = statusFromScore(score);
  const angle = Number.isFinite(score) ? `${Math.max(0, Math.min(100, score)) * 1.8}deg` : "0deg";
  const value = Number.isFinite(score) ? score : "--";
  return `<div class="gauge ${extraClass}" style="--angle:${angle};--gauge-color:${meta.color}" role="img" aria-label="${esc(label)} ${esc(meta.label)} ${esc(value)}点">
    <div class="gauge-value">${esc(value)}<small>/100</small></div>
  </div>`;
}

function statusBadge(meta) {
  return `<span class="status-label status-${meta.cls}">${esc(meta.label)}</span>`;
}

function metricRows(metrics) {
  return metrics.slice(0, 5).map((metric) => {
    const mark = riskMark(metric.riskScore);
    const title = [
      `取得元: ${metric.sourceName || "未設定"}`,
      metric.asOf ? `基準: ${metric.asOf}` : "",
      metric.missingReason ? `理由: ${metric.missingReason}` : ""
    ].filter(Boolean).join(" / ");
    return `<div class="metric-row" title="${esc(title)}">
      <span class="metric-name">${esc(metric.label)}</span>
      <span class="metric-value">${esc(formatValue(metric))}</span>
      <span class="risk-mark risk-${mark.cls}" aria-label="${esc(mark.title)}">${esc(mark.mark)}</span>
    </div>`;
  }).join("");
}

function axisText(report, field, fallback) {
  if (!report) return fallback;
  if (field === "theme") return cleanText(report.theme || fallback, 58);
  if (field === "change") return cleanText(arr(report.changes).map(textOf)[0] || fallback, 54);
  if (field === "leader") return cleanText(report.leadingMarket || fallback, 54);
  if (field === "break") return cleanText(report.breakConditions || fallback, 62);
  return fallback;
}

function watchItems(data, report) {
  const base = arr(data.watchPoints);
  const breakText = report?.breakConditions || "";
  const breakItems = breakText
    ? breakText.split(/[。、\n]/).map((item) => cleanText(item, 40)).filter(Boolean).slice(0, 2)
    : [];
  return [
    ...base,
    ...breakItems.map((text) => ({ text, impact: "中", source: "マーケットレポート本文", status: "本文判定" }))
  ].slice(0, 7);
}

function render(data, reports) {
  const root = $("[data-temperature-root]");
  const report = latestReport(reports);
  const categories = buildCategories(data, report);
  const overall = weightedOverall(categories, data.weights);
  const overallMeta = statusFromScore(overall.score);
  const reportStamp = report ? `${report.date || ""} ${report.time || ""}`.trim() : "レポート未取得";
  const generated = data.generatedAt ? data.generatedAt.replace("T", " ").replace("+09:00", " JST") : "取得不能";

  $("#pageUpdated").textContent = `最終更新 ${reportStamp || generated}`;

  root.innerHTML = `
    <section class="page-head">
      <div>
        <h2>${esc(data.pageTitle || "市場温度ダッシュボード")}</h2>
        <p>${esc(data.subtitle || "市場内部の温度を確認します")}</p>
      </div>
      <span class="data-pill">${esc(data.meta?.sourceStatus || "データ状態確認中")} / 算出対象 ${overall.used}/${overall.total}</span>
    </section>

    <section class="top-grid">
      <article class="overall-panel">
        <div>
          <p class="overall-title">総合判定</p>
          <h3 class="overall-status">${esc(overallMeta.label)}</h3>
          <p class="overall-summary">${esc(Number.isFinite(overall.score) ? "取得できた指標と本文判定から市場温度を暫定算出しています。" : "公式指標の連携待ちです。取得不能値は0として扱いません。")}</p>
          <p class="score-note">${esc(data.meta?.scoringNote || "")}</p>
        </div>
        <div class="gauge-box">
          ${gaugeHtml(overall.score, "総合市場温度", "overall-gauge")}
          ${statusBadge(overallMeta)}
        </div>
      </article>

      <article class="panel axis-card">
        <h3>今日の相場テーマ</h3>
        <p>${esc(axisText(report, "theme", data.judgementAxes?.theme || "取得不能"))}</p>
      </article>
      <article class="panel axis-card">
        <h3>前回からの変化</h3>
        <p>${esc(axisText(report, "change", data.judgementAxes?.change || "取得不能"))}</p>
      </article>
      <article class="panel axis-card">
        <h3>主導市場</h3>
        <p>${esc(axisText(report, "leader", data.judgementAxes?.leader || "取得不能"))}</p>
      </article>
      <article class="panel axis-card">
        <h3>シナリオが崩れる条件</h3>
        <p>${esc(axisText(report, "break", arr(data.judgementAxes?.breakConditions)[0] || "取得不能"))}</p>
      </article>
    </section>

    <section class="category-grid" aria-label="6分野の市場温度">
      ${categories.map((category) => `
        <article class="panel temp-card">
          <div class="card-head">
            <h3 class="card-title"><span class="letter">${esc(category.letter || "")}</span>${esc(category.label)}</h3>
            <a class="detail-link" href="${esc(category.detailUrl || "index.html")}">詳細へ</a>
          </div>
          <div class="gauge-box">
            ${gaugeHtml(category.score, category.label)}
            ${statusBadge(category.statusMeta)}
            <span class="data-pill">${esc(category.sourceType)}</span>
          </div>
          <div class="metric-list">${metricRows(category.metrics)}</div>
          <p class="card-summary">${esc(category.summary || "")}</p>
        </article>
      `).join("")}
    </section>

    <section class="lower-grid">
      <article class="panel">
        <h3 class="section-title">市場間のつながり（因果の流れ）</h3>
        <div class="causal-flow">
          ${arr(data.causalFlow).map((step) => `
            <div class="flow-step">
              <b>${esc(step.title)}</b>
              <span>${esc(step.subtitle)}</span>
              <small>${esc(step.note)}</small>
            </div>
          `).join("")}
        </div>
      </article>
      <article class="panel">
        <h3 class="section-title">次の監視ポイント</h3>
        <ul class="watch-list">
          ${watchItems(data, report).map((item) => `
            <li title="${esc(`${item.source || ""} / ${item.status || ""}`)}">
              <span class="box-mark" aria-hidden="true"></span>
              <span>${esc(item.text)}</span>
              <span class="impact">影響度：${esc(item.impact || "中")}</span>
            </li>
          `).join("")}
        </ul>
      </article>
    </section>

    <section class="legend-row" aria-label="市場温度ステータスの見方">
      <b>温度ステータスの見方</b>
      ${arr(data.legend).map((item) => {
        const key = item.label === "平常" ? "normal" : item.label === "注意" ? "caution" : item.label === "警戒" ? "warning" : item.label === "ストレス" ? "stress" : "imbalance";
        return `<span class="legend-item"><span class="legend-dot dot-${key}"></span>${esc(item.label)}（${esc(item.range)}）</span>`;
      }).join("")}
    </section>
    <p class="data-note">※ 本ページは投資判断の参考情報です。未連携の指標は推測で補完せず、取得不能または提供準備中として表示します。</p>
  `;
}

async function loadPage() {
  const root = $("[data-temperature-root]");
  try {
    const [dataResponse, reportsResponse] = await Promise.all([
      fetch(`data/market-temperature.json?v=${Date.now()}`, { cache: "no-store" }),
      fetch(`reports.json?v=${Date.now()}`, { cache: "no-store" })
    ]);
    if (!dataResponse.ok) throw new Error(`market-temperature.json HTTP ${dataResponse.status}`);
    const data = await dataResponse.json();
    const reports = reportsResponse.ok ? await reportsResponse.json() : [];
    render(data, reports);
  } catch (error) {
    root.innerHTML = `<section class="error-panel">市場温度データを表示できません。理由：${esc(error.message)}。data/market-temperature.jsonを確認してください。</section>`;
    $("#pageUpdated").textContent = "読み込み失敗";
  }
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", loadPage, { once: true });
} else {
  loadPage();
}
