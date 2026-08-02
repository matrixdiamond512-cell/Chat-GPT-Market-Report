const REPORT_TIMES = ["07:00", "12:00", "16:00", "21:00"];

const MARKET_DEFINITIONS = [
  {
    key: "gold",
    label: "金",
    display: "金（XAU/USD）",
    icon: "Au",
    iconClass: "gold",
    patterns: [/金現物：/, /金価格：/, /金（XAU\/USD）：/],
    unit: "USD/oz",
    route: "gold-supply-demand.html"
  },
  {
    key: "oil",
    label: "原油",
    display: "WTI原油（CL）",
    icon: "CL",
    iconClass: "oil",
    patterns: [/WTI原油：/, /原油（WTI）：/, /原油：/],
    unit: "USD/bbl",
    route: null
  },
  {
    key: "nikkei",
    label: "日経225先物",
    display: "日経225先物（大阪取引所）",
    icon: "NK",
    iconClass: "nikkei",
    patterns: [/日経225先物.*：/],
    unit: "円",
    route: "nikkei225-supply-demand.html"
  },
  {
    key: "usdjpy",
    label: "USD/JPY",
    display: "USD/JPY",
    icon: "$",
    iconClass: "",
    patterns: [/USD\/JPY：/],
    unit: "円",
    route: "usdjpy-supply-demand.html"
  },
  {
    key: "eurusd",
    label: "EUR/USD",
    display: "EUR/USD",
    icon: "€",
    iconClass: "",
    patterns: [/EUR\/USD：/],
    unit: "USD",
    route: null
  },
  {
    key: "btc",
    label: "BTCUSD",
    display: "BTCUSD",
    icon: "BTC",
    iconClass: "btc",
    patterns: [/BTCUSD：/, /BTC：/],
    unit: "USD",
    route: null
  }
];

const FLOW_ASSETS = ["株式", "債券（米国）", "ドル", "円", "商品（原油・金）", "暗号資産"];

let reports = [];
let selectedReport = null;
let dashboardMeta = null;

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
  const text = String(value)
    .replace(/\s+/g, " ")
    .replace(/^[・\s]+/, "")
    .trim();
  if (!text) return "";
  return text.length > max ? `${text.slice(0, max)}...` : text;
}

function uniq(values) {
  return [...new Set(values.filter(Boolean))];
}

function normalizeMinus(value = "") {
  return String(value).replace(/−/g, "-").trim();
}

function dateToJp(dateText) {
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
    ...asArray(report.handover).map(textOf),
    ...asArray(report.riskManagement).map(textOf),
    ...asArray(report.markets).flatMap((market) => [
      market.name,
      market.direction,
      market.price,
      market.change,
      market.material,
      market.positioning,
      market.levels,
      market.risk,
      market.breakCondition
    ])
  ].filter(Boolean).join(" ");
}

function sourceLines(report) {
  return [
    ...asArray(report.changes).map(textOf),
    ...asArray(report.news).map(textOf),
    ...asArray(report.riskManagement).map(textOf),
    ...asArray(report.markets).flatMap((market) => [
      market.price,
      market.change,
      market.material,
      market.levels,
      market.risk
    ])
  ].filter(Boolean);
}

function trendFromText(value = "") {
  const text = normalizeMinus(value);
  if (/\+|上昇|強|買い|流入|拡大|改善|支え|反発/.test(text)) return "up";
  if (/-|下落|弱|売り|流出|縮小|警戒|悪化|重い|割れ/.test(text)) return "down";
  return "flat";
}

function directionMark(trend) {
  if (trend === "up") return "↑";
  if (trend === "down") return "↓";
  return "→";
}

function reportMarket(report, definition) {
  return asArray(report.markets).find((market) => (
    market.name === definition.label ||
    market.name === definition.display ||
    (definition.key === "oil" && market.name === "原油") ||
    (definition.key === "gold" && market.name === "金")
  ));
}

function findMetricLine(report, definition) {
  return sourceLines(report).find((line) => definition.patterns.some((pattern) => pattern.test(line))) || "";
}

function parseMetric(report, definition) {
  const line = findMetricLine(report, definition);
  if (!line) {
    const market = reportMarket(report, definition);
    return {
      value: "取得不能",
      unit: "",
      change: cleanText(market?.direction || "理由：JSONに価格項目なし", 38),
      trend: trendFromText(market?.direction || ""),
      raw: ""
    };
  }

  if (definition.key === "usdjpy") {
    const match = line.match(/終値\s*([\d,.]+).*?（\s*([+\-−]?\d[\d,.]*)、\s*([+\-−]?\d[\d,.]*％)/);
    if (match) {
      const change = `${normalizeMinus(match[2])}　${normalizeMinus(match[3])}`;
      return {
        value: match[1],
        unit: definition.unit,
        change,
        trend: trendFromText(change),
        raw: line
      };
    }
  }

  if (definition.key === "oil") {
    const range = line.match(/約\s*([^、。]+?ドル)/);
    if (range) {
      return {
        value: range[1].replace("ドル", ""),
        unit: definition.unit,
        change: "前日比：取得不能",
        trend: trendFromText(line),
        raw: line
      };
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
      trend: trendFromText(change || line),
      raw: line
    };
  }

  const simple = line.match(/：\s*([^。]+)/);
  return {
    value: simple ? cleanText(simple[1].replace("約", ""), 24) : "取得不能",
    unit: definition.unit,
    change: "前日比：取得不能",
    trend: trendFromText(line),
    raw: line
  };
}

function findOutlookSentence(report, definition) {
  const text = allText(report);
  const start = text.indexOf("個別見通し");
  const scoped = start >= 0 ? text.slice(start, start + 1800) : text;
  const labels = uniq([definition.label, definition.display, definition.key === "oil" ? "WTI原油" : ""]);

  for (const label of labels) {
    const index = scoped.indexOf(`${label}：`);
    if (index >= 0) {
      const after = scoped.slice(index + label.length + 1);
      const nextMarket = after.search(/\s(?:金|WTI原油|日経225先物|USD\/JPY|EUR\/USD|BTCUSD)：/);
      const segment = nextMarket >= 0 ? after.slice(0, nextMarket) : after;
      const sentences = segment.split(/。/).map((item) => item.trim()).filter(Boolean).slice(0, 2);
      if (sentences.length) return cleanText(`${sentences.join("。")}。`, 78);
    }
  }

  const market = reportMarket(report, definition);
  return cleanText(market?.material || market?.direction || "", 64);
}

function marketReason(report, definition, metric) {
  const outlook = findOutlookSentence(report, definition);
  if (outlook) return outlook;
  if (metric.raw) return cleanText(metric.raw.replace(/^.*?：/, ""), 68);
  const market = reportMarket(report, definition);
  return cleanText(market?.material || "理由：本文に市場別理由がありません", 68);
}

function consistencyForMarket(report, definition) {
  const lines = asArray(report.consistency).map(textOf).filter(Boolean);
  const aliases = {
    gold: ["金"],
    oil: ["原油", "WTI"],
    nikkei: ["株", "日経", "米株"],
    usdjpy: ["ドル", "円", "USD/JPY"],
    eurusd: ["EUR/USD", "ユーロ"],
    btc: ["BTC", "暗号"]
  }[definition.key] || [definition.label];

  const found = lines.find((line) => aliases.some((alias) => line.includes(alias)));
  const text = found || "理由：整合性コメントに個別記載なし";
  let verdict = "一部整合";
  let cls = "partial";
  if (/不整合|反対方向/.test(text)) {
    verdict = "不整合";
    cls = "conflict";
  } else if (/整合的|整合/.test(text)) {
    verdict = "整合";
    cls = "match";
  }
  return { verdict, cls, reason: cleanText(text, 44) };
}

function extractLevels(report, definition) {
  const market = reportMarket(report, definition);
  const source = [findOutlookSentence(report, definition), market?.levels, findMetricLine(report, definition)].filter(Boolean).join(" ");
  const scoped = source.slice(0, 260);
  const match = scoped.match(/上値\s*([0-9,.]+(?:～[0-9,.]+)?)(?:円|ドル)?[、\s]+下値\s*([0-9,.]+(?:～[0-9,.]+)?)(?:円|ドル)?/);
  if (match) return `上値 ${match[1]}　下値 ${match[2]}`;
  const range = scoped.match(/([0-9,.]+(?:～[0-9,.]+)?)(?:円|ドル|％|％?台)/);
  return range ? `注目 ${range[0]}` : "取得不能";
}

function riskForMarket(report, definition) {
  const market = reportMarket(report, definition);
  const raw = market?.risk || market?.breakCondition || "";
  const usable = raw && raw.length < 170 && !/個別見通し|ヘッダーなし|TSV|マーケットレポート/.test(raw);
  if (usable) return cleanText(raw, 42);
  const text = allText(report);
  const rules = {
    gold: /米10年債|金利/.test(text) ? "米金利上昇・ドル高" : "金利材料の急変",
    oil: /82ドル割れ/.test(text) ? "82ドル割れで短期ロング解消" : "在庫・地政学材料の反転",
    nikkei: /61,900/.test(text) ? "61,900円割れ・円急騰" : "米株安と円高の同時進行",
    usdjpy: /163.20/.test(text) ? "163.20円割れ・日銀後の円急騰" : "日銀会合後の円買い",
    eurusd: /ドル/.test(text) ? "ドル材料の急変" : "欧州材料の悪化",
    btc: /VIX|米株/.test(text) ? "VIX上昇・米株安" : "リスクオフ再燃"
  };
  return rules[definition.key] || cleanText(report.breakConditions || "理由：市場別リスク記載なし", 42);
}

function splitTheme(report) {
  const theme = cleanText(report.theme || "", 250);
  const sentences = theme.split(/。/).map((item) => item.trim()).filter(Boolean);
  return sentences.slice(0, 3).map((item) => `${item}。`);
}

function topList(items, limit = 3, max = 120) {
  return asArray(items).map(textOf).filter(Boolean).map((item) => cleanText(item, max)).slice(0, limit);
}

function renderList(id, values, fallback) {
  const rows = values.length ? values : [fallback];
  $(id).innerHTML = rows.map((item) => `<li>${esc(item)}</li>`).join("");
}

function renderHeader(report) {
  const created = `${dateToJp(report.date)} ${report.time || ""}`.trim();
  const generated = dashboardMeta && dashboardMeta.generatedAt
    ? dashboardMeta.generatedAt.replace("T", " ").replace("+09:00", "")
    : report.time || "取得不能";
  $("reportStatus").textContent = `作成日時：${created}　更新：${generated}`;
  document.title = `WEBマーケットレポート｜${created}`;
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
  return reports
    .filter((report) => report.date === dateText)
    .sort((a, b) => REPORT_TIMES.indexOf(a.time) - REPORT_TIMES.indexOf(b.time));
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

  const dates = availableDates();
  $("dateInput").value = report.date;
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
}

function renderMarketCards(report) {
  $("marketCards").innerHTML = MARKET_DEFINITIONS.map((definition) => {
    const metric = parseMetric(report, definition);
    const trend = metric.trend;
    const trendClass = trend === "up" ? "up" : trend === "down" ? "down" : trend === "missing" ? "missing" : "flat";
    const reasonLabel = trend === "down" ? "なぜ売られたか" : trend === "up" ? "なぜ買われたか" : "なぜ動いたか";
    const consistency = consistencyForMarket(report, definition);
    const reason = marketReason(report, definition, metric);
    const levels = extractLevels(report, definition);
    const risk = riskForMarket(report, definition);
    const tag = definition.route ? "a" : "article";
    const href = definition.route ? ` href="${definition.route}"` : "";
    const aria = definition.route ? ` aria-label="${esc(definition.display)}の詳細へ"` : "";
    return `<${tag} class="market-card"${href}${aria}>
      <span class="asset-icon ${definition.iconClass}">${esc(definition.icon)}</span>
      <span>
        <h3>${esc(definition.display)}</h3>
        <p class="market-value">${esc(metric.value)}${metric.unit ? `<small>${esc(metric.unit)}</small>` : ""}</p>
        <p class="change-line ${trendClass}">${esc(metric.change)}</p>
        <dl>
          <dt>${esc(reasonLabel)}</dt><dd>${esc(reason)}</dd>
          <dt>注目点</dt><dd>${esc(levels)}</dd>
          <dt>リスク</dt><dd>${esc(risk)}</dd>
        </dl>
        <span class="consistency-badge ${consistency.cls}">材料と値動きの整合性：${esc(consistency.verdict)}</span>
        <p class="market-note">${esc(consistency.reason)}</p>
      </span>
      <span class="direction-mark ${trendClass}">${directionMark(trend)}</span>
    </${tag}>`;
  }).join("");
}

function flowDirection(report, asset) {
  const flowText = asArray(report.crossAssetFlow).join(" ");
  const text = allText(report);
  const has = (pattern) => pattern.test(flowText) || pattern.test(text);

  if (asset === "株式") {
    if (has(/流出：[^。]*(米国株|株)|株安|VIX上昇|リスク縮小/)) {
      return { direction: "流出", strength: "強い", compare: "悪化", reason: "米株安・VIX上昇", basis: "本文から推定", trend: "down" };
    }
  }
  if (asset === "債券（米国）") {
    if (has(/米10年債|金利|国債|短期資金/)) {
      return { direction: "流入", strength: "中程度", compare: "強化", reason: "金利再評価・短期資金", basis: "本文から推定", trend: "up" };
    }
  }
  if (asset === "ドル") {
    if (has(/ドル全面高にはなっておらず|ドル整理/)) {
      return { direction: "流入", strength: "やや強い", compare: "強化", reason: "金利差維持・リスク選好", basis: "本文から推定", trend: "up" };
    }
    if (has(/ドル高/)) return { direction: "流入", strength: "中程度", compare: "強化", reason: "米金利上昇", basis: "本文から推定", trend: "up" };
  }
  if (asset === "円") {
    if (has(/円ショート縮小|円買い戻し|日銀会合/)) {
      return { direction: "流入", strength: "やや強い", compare: "強化", reason: "日銀会合前の円買い戻し", basis: "本文から推定", trend: "up" };
    }
  }
  if (asset === "商品（原油・金）") {
    if (has(/金|原油|WTI|供給|在庫|地政学/)) {
      return { direction: "流入", strength: "強い", compare: "強化", reason: "安全資産需要・供給不安", basis: "本文から推定", trend: "up" };
    }
  }
  if (asset === "暗号資産") {
    if (has(/BTC.*限定的|BTCUSD|暗号資産/)) {
      return { direction: "流入", strength: "やや強い", compare: "強化", reason: "ETF資金・リスク選好", basis: "本文から推定", trend: "up" };
    }
  }
  return { direction: "取得不能", strength: "未判定", compare: "未判定", reason: "JSONに明示なし", basis: "未連携", trend: "missing" };
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
      <td>${esc(flow.reason)} / ${esc(flow.basis)}</td>
    </tr>`;
  }).join("");

  const flowItems = topList(report.crossAssetFlow, 2, 112);
  $("flowSummary").textContent = flowItems.length
    ? flowItems.join(" ")
    : "理由：クロスアセット資金フローがJSONにありません";
}

function newsImpact(text) {
  const value = text || "";
  if (/金利|FOMC|FRB|PCE|CPI|雇用/.test(value)) return { tag: "金利↓", cls: "up", path: "米金利低下・上昇がドルと金を左右" };
  if (/原油|WTI|在庫|地政学|中東/.test(value)) return { tag: "原油↑", cls: "up", path: "原油材料がインフレ警戒へ波及" };
  if (/株|Nasdaq|S&P|VIX|半導体|決算/.test(value)) return { tag: "株↓", cls: "down", path: "株式リスク選好に直接影響" };
  if (/日銀|円|USD\/JPY/.test(value)) return { tag: "ドル円↑", cls: "up", path: "日銀・円需給がUSD/JPYへ波及" };
  return { tag: "材料", cls: "", path: "影響経路は本文確認" };
}

function renderNews(report) {
  const news = topList(report.news, 5, 78);
  $("newsList").innerHTML = news.length ? news.map((item) => {
    const time = item.match(/\b([0-2]\d:[0-5]\d)\b/)?.[1] || "確認";
    const impact = newsImpact(item);
    return `<li>
      <span class="news-time">${esc(time)}</span>
      <span>${esc(item)}<span class="news-impact">伝播経路：${esc(impact.path)}</span></span>
      <span class="tag ${impact.cls}">${esc(impact.tag)}</span>
    </li>`;
  }).join("") : `<li><span class="news-time">取得不能</span><span>理由：ニュース項目がJSONにありません</span><span class="tag">未連携</span></li>`;
}

function renderPositions(report) {
  renderList("positionList", topList(report.positioning, 3, 78), "理由：需給・ポジション項目がJSONにありません");
  const rows = ["株式", "原油", "ドル", "金", "BTC"];
  const headers = ["", "弱気", "中立", "強気"];
  const cell = (asset, side) => positionBias(report, asset) === side ? "•" : "";
  $("positionMatrix").innerHTML = [
    ...headers.map((header) => `<span>${esc(header)}</span>`),
    ...rows.flatMap((asset) => [`<span>${esc(asset)}</span>`, ...headers.slice(1).map((side) => `<span class="dot">${cell(asset, side)}</span>`)])
  ].join("");
}

function positionBias(report, asset) {
  const text = allText(report);
  const rules = {
    "株式": [/株安|リスク縮小|上値が重い|戻り売り|VIX.*上昇/, /株.*上昇|押し目買い|買い戻し/],
    "原油": [/原油.*弱|原油.*下落|82ドル割れ/, /原油高|WTI.*高値|供給.*優先|在庫/],
    "ドル": [/ドル全面高にはなっておらず|ドル整理/, /ドル高|米金利.*上昇|金利差/],
    "金": [/金.*弱|金.*下落/, /金上昇|金.*支え|流入：金|安全資産/],
    "BTC": [/BTC.*弱|BTC.*下値|暗号資産.*流出/, /BTC.*底堅|BTC.*上昇|ETF/]
  };
  const [bearish, bullish] = rules[asset] || [];
  const isBearish = bearish?.test(text);
  const isBullish = bullish?.test(text);
  if (isBearish && !isBullish) return "弱気";
  if (isBullish && !isBearish) return "強気";
  return "中立";
}

function regionFromEvent(text) {
  if (/米|FOMC|FRB|PCE|CPI|雇用|ISM/.test(text)) return "米国";
  if (/日銀|日本|東京/.test(text)) return "日本";
  if (/ECB|ユーロ|欧州|ドイツ/.test(text)) return "欧州";
  if (/中国/.test(text)) return "中国";
  return "複数";
}

function importanceFromEvent(text) {
  if (/FOMC|日銀|PCE|CPI|雇用|政策|会見/.test(text)) return "★★★";
  if (/PMI|ISM|GDP|在庫|決算/.test(text)) return "★★";
  return "★";
}

function renderEvents(report) {
  const events = topList(report.events, 5, 90);
  $("eventRows").innerHTML = events.length ? events.map((item, index) => {
    const time = item.match(/\b([0-2]\d:[0-5]\d)\b/)?.[1] || (index === 0 ? report.time || "確認" : "確認");
    return `<tr>
      <td>${esc(`${dateToJp(report.date)} ${time}`)}</td>
      <td>${esc(item)}</td>
      <td>${esc(regionFromEvent(item))}</td>
      <td>${esc(importanceFromEvent(item))}</td>
      <td>取得不能</td>
    </tr>`;
  }).join("") : `<tr><td>取得不能</td><td>理由：重要イベント項目がJSONにありません</td><td>未連携</td><td>-</td><td>-</td></tr>`;
}

function lensItems(report) {
  const text = allText(report);
  const metricLine = (pattern) => sourceLines(report).find((line) => pattern.test(line));
  const usRate = metricLine(/米10年債利回り/);
  const jpRate = metricLine(/日本10年債利回り/);
  const stock = topList(report.consistency, 1, 90)[0] || "株式市場の詳細は株式市場分析ページで確認";
  const commodity = topList(report.crossAssetFlow, 2, 90).find((line) => /金|原油|WTI/.test(line)) || "商品市場の方向は金・原油カードで確認";
  const fx = /ドル全面高にはなっておらず/.test(text) ? "ドルは全面高ではなく、円需給と日銀材料が焦点" : "ドル円とユーロドルの反応を同時確認";
  const crypto = /BTC/.test(text) ? "BTCは株式リスク選好とETF資金の継続を確認" : "暗号資産はBTCカードで確認";
  const watch = [
    "米PCEデフレーターの結果",
    "中東情勢・原油在庫の方向",
    "日銀会合後の円需給"
  ];

  return [
    ["金利・債券市場", "%", [usRate || "米10年債利回り：取得不能", jpRate || "日本10年債利回り：取得不能", "金利低下ならリスク資産を支援"]],
    ["株式市場", "株", [stock, "株式市場分析ページでセクターと寄与度を確認", "利確確定売りには注意"]],
    ["商品市場（原油・金）", "CL", [commodity, "原油は供給不安、金は金利と安全資産需要を確認", "両市場とも地政学リスクに反応"]],
    ["為替市場", "FX", [fx, "USD/JPYは金利差と円需給を確認", "EUR/USDはドル材料と欧州材料を分けて確認"]],
    ["暗号資産市場", "BTC", [crypto, "12万ドル台定着が次の焦点", "規制・マクロ悪化には注意"]],
    ["今日の注目ポイント", "P", watch]
  ];
}

function renderMarketLens(report) {
  $("marketLensCards").innerHTML = lensItems(report).map(([title, icon, items]) => `<article class="panel market-lens-card">
    <h2><span class="lens-icon">${esc(icon)}</span>${esc(title)}</h2>
    <ul>${items.map((item) => `<li>${esc(item)}</li>`).join("")}</ul>
  </article>`).join("");
}

function conclusionFrom(report) {
  const lead = cleanText(report.leadingMarket || "", 70);
  const main = cleanText(report.mainScenario || "", 86);
  const risk = cleanText(topList(report.riskManagement, 1, 90)[0] || report.breakConditions || "", 86);
  const parts = [];
  if (lead) parts.push(`主導市場：${lead}`);
  if (main) parts.push(`基本姿勢：${main}`);
  if (risk) parts.push(`リスク管理：${risk}`);
  return parts.join("。") || "理由：結論に必要な項目がJSONにありません";
}

function renderScenarios(report) {
  $("mainScenario").textContent = cleanText(report.mainScenario || "理由：メインシナリオがJSONにありません", 138);
  $("alternativeScenario").textContent = cleanText(report.alternativeScenario || "理由：代替シナリオがJSONにありません", 138);
  $("breakConditions").textContent = cleanText(report.breakConditions || "理由：崩れる条件がJSONにありません", 138);
  renderList("handoverList", topList(report.handover, 3, 88), "理由：引き継ぎ項目がJSONにありません");
  $("conclusionText").textContent = conclusionFrom(report);
}

function renderFootnote(report) {
  const missing = MARKET_DEFINITIONS
    .map((definition) => [definition.display, parseMetric(report, definition)])
    .filter(([, metric]) => metric.value === "取得不能")
    .map(([name]) => name);
  $("dataFootnote").textContent = missing.length
    ? `本レポートは投資判断の参考情報であり、特定の投資を推奨するものではありません。表示中：${dateToJp(report.date)} ${report.time}。未連携または取得不能：${missing.join("、")}。`
    : `本レポートは投資判断の参考情報であり、特定の投資を推奨するものではありません。表示中：${dateToJp(report.date)} ${report.time}。`;
}

function render() {
  const report = selectedReport || reports[0];
  if (!report) return;
  renderHeader(report);
  renderControls(report);
  renderMarketCards(report);
  renderList("themeList", splitTheme(report), "理由：相場テーマがJSONにありません");
  renderList("changeList", topList(report.changes, 2, 96), "理由：前回からの変化がJSONにありません");
  $("leadingMarket").textContent = cleanText(report.leadingMarket || "取得不能。理由：主導市場コメントがJSONにありません", 170);
  renderFlow(report);
  renderNews(report);
  renderPositions(report);
  renderEvents(report);
  renderMarketLens(report);
  renderScenarios(report);
  renderFootnote(report);
}

async function init() {
  try {
    const data = await loadDashboardReports();
    reports = asArray(data.reports)
      .filter((report) => /^\d{4}-\d{2}-\d{2}$/.test(report.date || ""))
      .sort((a, b) => reportKey(b).localeCompare(reportKey(a)));
    dashboardMeta = data.meta || null;

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

async function loadDashboardReports() {
  const errors = [];
  try {
    const response = await fetch(`data/dashboard.json?ts=${Date.now()}`, { cache: "no-store" });
    if (!response.ok) throw new Error(`data/dashboard.json HTTP ${response.status}`);
    const payload = await response.json();
    const dashboardReports = normalizeDashboardReports(payload);
    if (dashboardReports.length) {
      return {
        reports: dashboardReports,
        meta: {
          generatedAt: payload.generatedAt || "",
          dataAsOf: payload.dataAsOf || "",
          status: payload.status || ""
        }
      };
    }
    throw new Error("data/dashboard.jsonに表示できるレポートがありません");
  } catch (error) {
    errors.push(error.message);
  }

  try {
    const response = await fetch(`reports.json?ts=${Date.now()}`, { cache: "no-store" });
    if (!response.ok) throw new Error(`reports.json HTTP ${response.status}`);
    const payload = await response.json();
    const reportList = normalizeDashboardReports(payload);
    if (reportList.length) return { reports: reportList, meta: { status: "fallback-reports-json" } };
    throw new Error("reports.jsonに表示できるレポートがありません");
  } catch (error) {
    errors.push(error.message);
  }

  throw new Error(`ダッシュボードJSONを取得できませんでした。理由：${errors.join(" / ")}`);
}

function normalizeDashboardReports(payload) {
  if (Array.isArray(payload)) return payload;
  if (!payload || typeof payload !== "object") return [];
  if (Array.isArray(payload.reports)) return payload.reports;
  if (payload.latestReport) return [payload.latestReport];
  if (payload.currentReport) return [payload.currentReport];
  return [];
}

init();
