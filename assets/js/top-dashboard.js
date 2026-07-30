const REPORT_TIMES = ["07:00", "12:00", "16:00", "21:00"];

const MARKET_DEFINITIONS = [
  { key: "gold", label: "金", display: "金（XAU/USD）", icon: "Au", iconClass: "gold", patterns: [/金現物：/, /金価格：/, /金（XAU\/USD）：/], unit: "USD/oz" },
  { key: "oil", label: "原油", display: "WTI原油（CL）", icon: "Oil", iconClass: "oil", patterns: [/WTI原油：/, /原油（WTI）：/, /原油：/], unit: "USD/bbl" },
  { key: "nikkei", label: "日経225先物", display: "日経225先物（大阪取引所）", icon: "NK", iconClass: "nikkei", patterns: [/日経225先物.*：/], unit: "円" },
  { key: "usdjpy", label: "USD/JPY", display: "USD/JPY", icon: "$", iconClass: "", patterns: [/USD\/JPY：/], unit: "円" },
  { key: "eurusd", label: "EUR/USD", display: "EUR/USD", icon: "€", iconClass: "", patterns: [/EUR\/USD：/], unit: "USD" },
  { key: "btc", label: "BTCUSD", display: "BTCUSD", icon: "B", iconClass: "btc", patterns: [/BTCUSD：/, /BTC：/], unit: "USD" }
];

const FLOW_ASSETS = ["株式", "債券", "ドル", "円", "金", "原油", "暗号資産"];
const ROUTES = {
  "金": "gold-supply-demand.html",
  "原油": "index.html",
  "日経225先物": "nikkei225-supply-demand.html",
  "USD/JPY": "usdjpy-supply-demand.html",
  "EUR/USD": "index.html",
  "BTCUSD": "index.html"
};

let reports = [];
let selectedReport = null;

const $ = (id) => document.getElementById(id);

function esc(value = "") {
  return String(value).replace(/[&<>"']/g, (char) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    "\"": "&quot;",
    "'": "&#039;"
  })[char]);
}

function asArray(value) {
  return Array.isArray(value) ? value : value ? [value] : [];
}

function textOf(value) {
  if (typeof value === "string") return value;
  if (!value) return "";
  return value.text || value.summary || value.title || "";
}

function cleanText(value = "", max = 120) {
  const text = String(value).replace(/\s+/g, " ").trim();
  if (!text) return "";
  return text.length > max ? `${text.slice(0, max)}...` : text;
}

function uniq(values) {
  return [...new Set(values.filter(Boolean))];
}

function dateToJp(dateText) {
  const date = new Date(`${dateText}T00:00:00+09:00`);
  const weekdays = ["日", "月", "火", "水", "木", "金", "土"];
  if (Number.isNaN(date.getTime())) return dateText || "日付不明";
  const [year, month, day] = dateText.split("-");
  return `${Number(month)}/${Number(day)}(${weekdays[date.getDay()]})`;
}

function longDateToJp(dateText) {
  const date = new Date(`${dateText}T00:00:00+09:00`);
  const weekdays = ["日", "月", "火", "水", "木", "金", "土"];
  if (Number.isNaN(date.getTime())) return dateText || "日付不明";
  const [year, month, day] = dateText.split("-");
  return `${year}/${month}/${day}（${weekdays[date.getDay()]}）`;
}

function reportKey(report) {
  return `${report.date} ${report.time}`;
}

function allText(report) {
  return [
    report.theme,
    report.leadingMarket,
    report.mainScenario,
    report.alternativeScenario,
    report.breakConditions,
    ...asArray(report.changes).map(textOf),
    ...asArray(report.consistency).map(textOf),
    ...asArray(report.news).map(textOf),
    ...asArray(report.crossAssetFlow).map(textOf),
    ...asArray(report.positioning).map(textOf),
    ...asArray(report.events).map(textOf),
    ...asArray(report.riskManagement).map(textOf),
    ...asArray(report.markets).flatMap((market) => [
      market.name,
      market.direction,
      market.price,
      market.change,
      market.material,
      market.levels,
      market.risk
    ])
  ].filter(Boolean).join(" ");
}

function sourceLines(report) {
  return [
    ...asArray(report.changes).map(textOf),
    ...asArray(report.riskManagement).map(textOf),
    ...asArray(report.markets).flatMap((market) => [market.price, market.change, market.material, market.levels, market.risk])
  ].filter(Boolean);
}

function findMetricLine(report, definition) {
  return sourceLines(report).find((line) => definition.patterns.some((pattern) => pattern.test(line))) || "";
}

function parseMetric(report, definition) {
  const line = findMetricLine(report, definition);
  if (!line) {
    return { value: "取得不能", unit: "", change: "理由：JSONに対象項目なし", trend: "missing", raw: "" };
  }

  if (definition.key === "usdjpy") {
    const match = line.match(/終値\s*([\d,.]+).*?（\s*([+\-−]?\d[\d,.]*)、\s*([+\-−]?\d[\d,.]*％)/);
    if (match) {
      return {
        value: match[1],
        unit: definition.unit,
        change: `${normalizeMinus(match[2])}　${normalizeMinus(match[3])}`,
        trend: trendFromText(`${match[2]} ${match[3]}`),
        raw: line
      };
    }
  }

  if (definition.key === "oil") {
    const range = line.match(/約\s*([^、。]+?ドル)/);
    if (range) {
      return { value: range[1].replace("ドル", ""), unit: definition.unit, change: "前日比：取得不能", trend: "missing", raw: line };
    }
  }

  const metric = line.match(/：\s*([^（。]+?)(?:ドル|円|USD|pt|％|%)?（\s*([^、）]+)(?:、\s*([^）]+))?/);
  if (metric) {
    const value = metric[1].replace(/^(始値|高値|安値|終値)/, "").trim();
    const change = [metric[2], metric[3]].filter(Boolean).map(normalizeMinus).join("　");
    return {
      value,
      unit: definition.unit,
      change: change || "前日比：取得不能",
      trend: trendFromText(change),
      raw: line
    };
  }

  const simple = line.match(/：\s*([^。]+)/);
  return {
    value: simple ? cleanText(simple[1].replace("約", ""), 24) : "取得不能",
    unit: definition.unit,
    change: "前日比：取得不能",
    trend: "missing",
    raw: line
  };
}

function normalizeMinus(value = "") {
  return String(value).replace(/−/g, "-").trim();
}

function trendFromText(value = "") {
  const text = normalizeMinus(value);
  if (/\+|上昇|強|買い|流入|拡大/.test(text)) return "up";
  if (/-|下落|弱|売り|流出|縮小|警戒/.test(text)) return "down";
  return "flat";
}

function findOutlookSentence(report, definition) {
  const text = allText(report);
  const start = text.indexOf("個別見通し");
  const scoped = start >= 0 ? text.slice(start, start + 1600) : text;
  const label = definition.label.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const matches = [
    new RegExp(`${label}：([^。]+。?)`),
    new RegExp(`${definition.display.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}：([^。]+。?)`)
  ];
  for (const pattern of matches) {
    const match = scoped.match(pattern);
    if (match) return cleanText(match[1], 88);
  }
  const market = asArray(report.markets).find((item) => item.name === definition.label || item.name === definition.display);
  return cleanText(market?.material || market?.direction || "", 88);
}

function splitTheme(report) {
  const theme = cleanText(report.theme || "", 280);
  const sentences = theme.split(/。/).map((item) => item.trim()).filter(Boolean);
  return sentences.slice(0, 3).map((item) => `${item}。`);
}

function topList(items, limit = 3) {
  return asArray(items).map(textOf).filter(Boolean).map((item) => cleanText(item, 120)).slice(0, limit);
}

function renderList(id, values, fallback) {
  const rows = values.length ? values : [fallback];
  $(id).innerHTML = rows.map((item) => `<li>${esc(item)}</li>`).join("");
}

function renderHeader(report) {
  const titleDate = `${longDateToJp(report.date)} ${report.time || ""}`.trim();
  $("reportStatus").textContent = `表示中：${titleDate} / 更新元：reports.json`;
  document.title = `WEBマーケットレポート｜${titleDate}`;
}

function availableDates() {
  if (!reports.length) return [];
  const latest = new Date(`${reports[0].date}T00:00:00+09:00`);
  const lower = new Date(latest);
  lower.setDate(lower.getDate() - 31);
  return uniq(reports
    .map((report) => report.date)
    .filter((dateText) => {
      const date = new Date(`${dateText}T00:00:00+09:00`);
      return date >= lower && date <= latest;
    }))
    .sort();
}

function reportsForDate(dateText) {
  return reports.filter((report) => report.date === dateText).sort((a, b) => REPORT_TIMES.indexOf(a.time) - REPORT_TIMES.indexOf(b.time));
}

function selectReport(dateText, timeText) {
  const sameDate = reportsForDate(dateText);
  selectedReport = sameDate.find((report) => report.time === timeText) || sameDate.at(-1) || reports[0];
  render();
  const url = new URL(window.location.href);
  url.searchParams.set("date", selectedReport.date);
  url.searchParams.set("time", selectedReport.time);
  window.history.replaceState({}, "", url);
}

function renderControls(report) {
  const sameDate = reportsForDate(report.date);
  const times = new Set(sameDate.map((item) => item.time));
  $("timeTabs").innerHTML = REPORT_TIMES.map((time) => {
    const active = time === report.time ? " is-active" : "";
    const disabled = times.has(time) ? "" : " disabled";
    return `<button type="button" class="time-tab${active}" data-time="${esc(time)}"${disabled}>${esc(time)}</button>`;
  }).join("");
  $("timeTabs").querySelectorAll("button:not(:disabled)").forEach((button) => {
    button.addEventListener("click", () => selectReport(report.date, button.dataset.time));
  });

  $("dateInput").value = report.date;
  const dates = availableDates();
  $("dateInput").min = dates[0] || report.date;
  $("dateInput").max = dates.at(-1) || report.date;
  $("dateInput").onchange = () => {
    if (dates.includes($("dateInput").value)) selectReport($("dateInput").value, report.time);
    else selectReport(report.date, report.time);
  };

  const index = dates.indexOf(report.date);
  $("prevDate").disabled = index <= 0;
  $("nextDate").disabled = index < 0 || index >= dates.length - 1;
  $("prevDate").onclick = () => index > 0 && selectReport(dates[index - 1], report.time);
  $("nextDate").onclick = () => index >= 0 && index < dates.length - 1 && selectReport(dates[index + 1], report.time);

  renderDateStrip(dates, report);
}

function renderDateStrip(dates, report) {
  const items = compactDateStrip(dates, report.date);
  $("dateStrip").innerHTML = items.map((item) => {
    if (item === "...") return `<span class="date-ellipsis">...</span>`;
    const active = item === report.date ? " is-active" : "";
    return `<button type="button" class="date-button${active}" data-date="${esc(item)}">${esc(dateToJp(item))}</button>`;
  }).join("");
  $("dateStrip").querySelectorAll(".date-button").forEach((button) => {
    button.addEventListener("click", () => selectReport(button.dataset.date, report.time));
  });
}

function compactDateStrip(dates, currentDate) {
  if (dates.length <= 14) return dates;
  const latest = dates.slice(-6);
  const currentIndex = dates.indexOf(currentDate);
  const around = dates.slice(Math.max(0, currentIndex - 2), currentIndex + 3);
  const first = dates.slice(0, 3);
  return uniq([...first, "...", ...around, "...", ...latest]);
}

function renderMarketCards(report) {
  $("marketCards").innerHTML = MARKET_DEFINITIONS.map((definition) => {
    const metric = parseMetric(report, definition);
    const outlook = findOutlookSentence(report, definition) || "理由：マーケット別コメント未連携";
    const changeClass = metric.trend === "up" ? "up" : metric.trend === "down" ? "down" : metric.trend === "missing" ? "missing" : "flat";
    const href = ROUTES[definition.label] || "index.html";
    return `<a class="market-card" href="${href}" aria-label="${esc(definition.display)}">
      <span class="asset-icon ${definition.iconClass}">${esc(definition.icon)}</span>
      <span>
        <h2>${esc(definition.display)}</h2>
        <p class="market-value">${esc(metric.value)}${metric.unit ? `<small>${esc(metric.unit)}</small>` : ""}</p>
        <p class="change-line ${changeClass}">${esc(metric.change)}</p>
        <p class="reason-line">主因：${esc(outlook)}</p>
      </span>
    </a>`;
  }).join("");
}

function flowDirection(report, asset) {
  const flowText = asArray(report.crossAssetFlow).join(" ");
  const text = allText(report);
  const has = (pattern) => pattern.test(flowText) || pattern.test(text);
  const rules = {
    "株式": [/流出：[^。]*(米国株|株)/, /(株安|リスク縮小|VIX上昇)/],
    "債券": [/流入：[^。]*(短期|国債|現金)/, /米10年債.*上昇/],
    "ドル": [/ドル全面高にはなっておらず/, /ドル高/],
    "円": [/流入：[^。]*円買い戻し/, /円ショート縮小/],
    "金": [/流入：[^。]*金/, /金.*支え/],
    "原油": [/WTI|原油/, /供給|在庫|地政学/],
    "暗号資産": [/BTC.*限定的|BTCUSD/, /BTC.*弱含み/]
  };
  const patterns = rules[asset] || [];
  const matched = patterns.some((pattern) => has(pattern));
  if (!matched) return { direction: "取得不能", strength: "理由あり", compare: "未判定", reason: "JSONに明示なし", trend: "missing" };

  if (asset === "株式") return { direction: "流出", strength: "強い", compare: "拡大", reason: "米株安・VIX上昇", trend: "down" };
  if (asset === "債券") return { direction: "流入", strength: "中程度", compare: "拡大", reason: "短期資金・金利再評価", trend: "up" };
  if (asset === "ドル") return { direction: "中立", strength: "中程度", compare: "横ばい", reason: "ドル全面高ではない", trend: "flat" };
  if (asset === "円") return { direction: "流入", strength: "中程度", compare: "拡大", reason: "円ショート縮小", trend: "up" };
  if (asset === "金") return { direction: "流入", strength: "中程度", compare: "横ばい", reason: "安全資産需要", trend: "up" };
  if (asset === "原油") return { direction: "流入", strength: "弱い", compare: "横ばい", reason: "供給・地政学材料", trend: "up" };
  return { direction: "中立", strength: "中程度", compare: "横ばい", reason: "米株安に対する下落限定", trend: "flat" };
}

function renderFlow(report) {
  $("flowRows").innerHTML = FLOW_ASSETS.map((asset) => {
    const flow = flowDirection(report, asset);
    const directionClass = flow.trend === "up" ? "up" : flow.trend === "down" ? "down" : flow.trend === "missing" ? "missing" : "flat";
    return `<tr>
      <th>${esc(asset)}</th>
      <td class="${directionClass}">${esc(flow.direction)}</td>
      <td>${esc(flow.strength)}</td>
      <td class="${directionClass}">${esc(flow.compare)}</td>
      <td>${esc(flow.reason)}</td>
    </tr>`;
  }).join("");

  $("flowChain").innerHTML = [
    ["ドル", ""],
    ["金", "gold-node"],
    ["現金", ""],
    ["株式", "stock-node"],
    ["円", "yen-node"],
    ["海外資産", ""]
  ].map(([label, className], index, array) => {
    const node = `<span class="flow-node ${className}">${esc(label)}</span>`;
    return index < array.length - 1 ? `${node}<span class="flow-arrow">›</span>` : node;
  }).join("");
}

function renderNews(report) {
  const tags = ["金利・債券", "米国経済", "日本", "地政学", "株式"];
  const news = topList(report.news, 5);
  $("newsList").innerHTML = news.length ? news.map((item, index) => `<li><span class="news-time">確認</span><span>${esc(item)}</span><span class="tag">${esc(tags[index] || "材料")}</span></li>`).join("") : `<li><span class="news-time">取得不能</span><span>理由：ニュース項目がJSONにありません</span><span class="tag">未連携</span></li>`;
}

function renderRelations(report) {
  const relations = [
    ["USD/JPY", "vs 米10年", "取得不能", "時系列未連携"],
    ["ドル指数", "vs BTCUSD", relationFromText(report, /ドル.*BTC|BTC.*ドル/), "本文から推定方向"],
    ["S&P500", "vs BTCUSD", relationFromText(report, /米株.*BTC|BTC.*米株/), "本文から推定方向"],
    ["原油(WTI)", "vs ドル指数", relationFromText(report, /原油.*ドル|ドル.*原油/), "本文から推定方向"],
    ["VIX指数", "vs 日経225先物", relationFromText(report, /VIX.*日経|日経.*VIX/), "本文から推定方向"]
  ];
  $("relationGrid").innerHTML = relations.map(([name, pair, value, note]) => {
    const trend = value === "取得不能" ? "missing" : trendFromText(value);
    return `<div class="relation-card"><b>${esc(name)}</b><small>${esc(pair)}</small><span class="${trend}">${esc(value)}</span><small>${esc(note)}</small></div>`;
  }).join("");
}

function relationFromText(report, pattern) {
  return pattern.test(allText(report)) ? "方向確認" : "取得不能";
}

function renderPositions(report) {
  renderList("positionList", topList(report.positioning, 4), "理由：需給・ポジション項目がJSONにありません");
  const rows = ["株式", "原油", "ドル", "金", "BTC"];
  const headers = ["", "弱気", "中立", "強気"];
  const cell = (asset, side) => {
    return positionBias(report, asset) === side ? "•" : "";
  };
  $("positionMatrix").innerHTML = [
    ...headers.map((header) => `<span>${esc(header)}</span>`),
    ...rows.flatMap((asset) => [`<span>${esc(asset)}</span>`, ...headers.slice(1).map((side) => `<span class="dot">${cell(asset, side)}</span>`)])
  ].join("");
}

function positionBias(report, asset) {
  const text = allText(report);
  const rules = {
    "株式": [/株安|リスク縮小|上値が重い|戻り売り|VIX.*上昇/, /株.*上昇|押し目買い/],
    "原油": [/原油.*弱|原油.*下落|82ドル割れ/, /原油高|WTI.*高値|供給.*優先|在庫/],
    "ドル": [/ドル全面高にはなっておらず|ドル整理/, /ドル高|米金利.*上昇/],
    "金": [/金.*弱|金.*下落/, /金上昇|金.*支え|流入：金|安全資産/],
    "BTC": [/BTC.*弱|BTC.*下値|暗号資産.*流出/, /BTC.*底堅|BTC.*上昇/]
  };
  const [bearish, bullish] = rules[asset] || [];
  const isBearish = bearish?.test(text);
  const isBullish = bullish?.test(text);
  if (isBearish && !isBullish) return "弱気";
  if (isBullish && !isBearish) return "強気";
  return "中立";
}

function renderOutlooks(report) {
  $("outlookCards").innerHTML = MARKET_DEFINITIONS.map((definition) => {
    const metric = parseMetric(report, definition);
    const outlook = findOutlookSentence(report, definition);
    const direction = inferDirection(outlook || metric.change);
    const levels = extractLevels(outlook || allText(report), definition);
    const material = outlook || "理由：個別市場コメント未連携";
    const href = ROUTES[definition.label] || "index.html";
    return `<a class="outlook-card" href="${href}">
      <div class="outlook-head">
        <span class="asset-icon ${definition.iconClass}">${esc(definition.icon)}</span>
        <h2>${esc(definition.display)}</h2>
      </div>
      <dl>
        <dt>方向</dt><dd>${esc(direction)}</dd>
        <dt>材料</dt><dd>${esc(material)}</dd>
        <dt>戦略</dt><dd>${esc(cleanText(report.mainScenario || "取得不能", 64))}</dd>
        <dt>注目水準</dt><dd>${esc(levels)}</dd>
        <dt>リスク</dt><dd>${esc(cleanText(report.breakConditions || "取得不能", 58))}</dd>
      </dl>
    </a>`;
  }).join("");
}

function inferDirection(text = "") {
  if (/上昇|強|底堅い|買い|流入/.test(text)) return "上昇バイアス";
  if (/下落|弱|重い|売り|流出/.test(text)) return "下落バイアス";
  if (/中立|横ばい|上下/.test(text)) return "中立";
  return "取得不能";
}

function extractLevels(text = "", definition) {
  const start = text.indexOf(definition.label);
  const scoped = start >= 0 ? text.slice(start, start + 220) : text;
  const match = scoped.match(/上値\s*([0-9,.]+(?:～[0-9,.]+)?)(?:円|ドル)?、下値\s*([0-9,.]+(?:～[0-9,.]+)?)(?:円|ドル)?/);
  if (match) return `上値 ${match[1]}　下値 ${match[2]}`;
  return "取得不能";
}

function renderFootnote(report) {
  const missing = MARKET_DEFINITIONS
    .map((definition) => [definition.display, parseMetric(report, definition)])
    .filter(([, metric]) => metric.trend === "missing")
    .map(([name]) => name);
  $("dataFootnote").textContent = missing.length
    ? `表示中データ：${longDateToJp(report.date)} ${report.time}。未連携または取得不能：${missing.join("、")}。画像例の数値は固定せず、reports.jsonの値だけを表示しています。`
    : `表示中データ：${longDateToJp(report.date)} ${report.time}。reports.jsonの確認済み項目から表示しています。`;
}

function render() {
  const report = selectedReport || reports[0];
  if (!report) return;
  renderHeader(report);
  renderControls(report);
  renderMarketCards(report);
  renderList("themeList", splitTheme(report), "理由：相場テーマがJSONにありません");
  renderList("changeList", topList(report.changes, 2), "理由：前回からの変化がJSONにありません");
  renderList("consistencyList", topList(report.consistency, 3), "理由：整合性コメントがJSONにありません");
  $("leadingMarket").textContent = cleanText(report.leadingMarket || "取得不能。理由：主導市場コメントがJSONにありません", 170);
  renderFlow(report);
  renderNews(report);
  renderRelations(report);
  renderPositions(report);
  renderOutlooks(report);
  renderFootnote(report);
}

async function init() {
  try {
    const response = await fetch(`reports.json?ts=${Date.now()}`, { cache: "no-store" });
    if (!response.ok) throw new Error("reports.jsonを取得できませんでした");
    const data = await response.json();
    reports = asArray(data)
      .filter((report) => /^\d{4}-\d{2}-\d{2}$/.test(report.date || ""))
      .sort((a, b) => reportKey(b).localeCompare(reportKey(a)));

    if (!reports.length) throw new Error("表示できるレポートがありません");

    const params = new URLSearchParams(window.location.search);
    const date = params.get("date");
    const time = params.get("time");
    selectedReport = reports.find((report) => report.date === date && report.time === time) || reports[0];
    render();
  } catch (error) {
    $("reportStatus").textContent = "データ取得エラー";
    document.querySelector(".page-shell").innerHTML = `<div class="empty-state">${esc(error.message)}。理由：reports.jsonの公開または形式を確認してください。</div>`;
  }
}

init();
