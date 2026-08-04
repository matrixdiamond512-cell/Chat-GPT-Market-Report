const REPORT_TIMES = ["07:00", "12:00", "16:00", "21:00"];

const MARKET_DEFINITIONS = [
  {
    key: "gold",
    label: "金",
    display: "金（XAU/USD）",
    icon: "Au",
    iconClass: "gold",
    patterns: [/金現物：/, /金価格：/, /金（XAU\/USD）：/, /金：/],
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
let dashboardCalendarEvents = [];
let dashboardCalendarMeta = null;

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
  return String(value).replace(/[−－]/g, "-").trim();
}

const TEMPERATURE_MINI_DEFINITIONS = [
  {
    id: "market.vix",
    label: "VIX",
    subtitle: "恐怖指数（米国・S&P500）",
    accent: "blue",
    max: 50,
    thresholds: [
      [15, "正常圏（落ち着き）"],
      [25, "警戒圏"],
      [35, "注意圏"],
      [Infinity, "危険圏"]
    ],
    ranges: [
      { range: "0-15", label: "正常", tone: "calm" },
      { range: "15-25", label: "警戒", tone: "watch" },
      { range: "25-35", label: "注意", tone: "caution" },
      { range: "35-", label: "危険", tone: "danger" }
    ],
    patterns: [/VIX(?:指数)?[：:\s]+(取得不能[^。\n]*|[0-9,.]+)/i]
  },
  {
    id: "market.nikkei_vi",
    label: "日経VI",
    subtitle: "恐怖指数（日経225）",
    accent: "purple",
    max: 50,
    thresholds: [
      [15, "正常圏（落ち着き）"],
      [25, "警戒圏"],
      [35, "注意圏"],
      [Infinity, "危険圏"]
    ],
    ranges: [
      { range: "0-15", label: "正常", tone: "calm" },
      { range: "15-25", label: "警戒", tone: "watch" },
      { range: "25-35", label: "注意", tone: "caution" },
      { range: "35-", label: "危険", tone: "danger" }
    ],
    patterns: [/日経VI[：:\s]+(取得不能[^。\n]*|[0-9,.]+)/]
  },
  {
    id: "sentiment.cnn_fear_greed",
    label: "Fear & Greed",
    subtitle: "市場心理指数（CNN）",
    accent: "green",
    max: 100,
    thresholds: [
      [24, "EXTREME FEAR"],
      [49, "FEAR"],
      [50, "NEUTRAL"],
      [74, "GREED"],
      [Infinity, "EXTREME GREED"]
    ],
    ranges: [
      { range: "0-24", label: "E.FEAR", tone: "danger" },
      { range: "25-49", label: "FEAR", tone: "caution" },
      { range: "50", label: "NEUTRAL", tone: "neutral" },
      { range: "51-74", label: "GREED", tone: "calm" },
      { range: "75-", label: "E.GREED", tone: "greed" }
    ],
    patterns: [/Fear\s*&\s*Greed(?:\s*Index)?[：:\s]+(取得不能[^。\n]*|[0-9,.]+)/i]
  }
];

const MARKET_SEGMENT_RE = /(?:^|\s)(金（XAU\/USD）|金現物|金価格|金|WTI原油|原油（WTI）|原油|日経225先物(?:（[^）]+）)?|USD\/JPY|EUR\/USD|BTCUSD|BTC|VIX|日経VI)：/g;

function splitMarketSegments(value = "") {
  const text = cleanText(value, 4000);
  const matches = [...text.matchAll(MARKET_SEGMENT_RE)];
  if (!matches.length) return [text];
  return matches.map((match, index) => {
    const start = match.index + (match[0].startsWith(" ") ? 1 : 0);
    const end = matches[index + 1]?.index ?? text.length;
    return text.slice(start, end).trim();
  }).filter(Boolean);
}

function isDefinitionLine(line, definition) {
  return definition.patterns.some((pattern) => pattern.test(line));
}

function lineAfterLabel(line = "") {
  const index = line.indexOf("：");
  return index >= 0 ? line.slice(index + 1).trim() : line.trim();
}

function extractPriceValue(line, definition) {
  const after = lineAfterLabel(normalizeMinus(line))
    .replace(/\d{1,2}:\d{2}時点/g, "")
    .replace(/前日比.*$/, "")
    .replace(/約/g, "")
    .trim();
  if (!after || /取得不能|未確認/.test(after)) return "";

  const patterns = {
    gold: /([1-9]\d{0,2},\d{3}(?:\.\d+)?|[3-9]\d{3}(?:\.\d+)?)(?=\s*(?:ドル|USD|、|,|（|\s|$))/,
    oil: /([1-9]\d(?:\.\d+)?|1\d{2}(?:\.\d+)?)(?=\s*(?:ドル|USD|、|,|（|\s|$))/,
    nikkei: /([1-9]\d{1,2},\d{3}(?:\.\d+)?|[1-9]\d{4,})(?=\s*(?:円|、|,|（|\s|$))/,
    usdjpy: /([1-9]\d{2}(?:\.\d+)?)(?=\s*(?:円|、|,|（|～|\s|$))/,
    eurusd: /(1\.\d{3,5})(?=\s*(?:ドル|USD|、|,|（|\s|$))/,
    btc: /([1-9]\d{1,2},\d{3}(?:\.\d+)?|[1-9]\d{4,})(?=\s*(?:ドル|USD|、|,|（|\s|$))/
  };

  const match = after.match(patterns[definition.key]);
  return match ? match[1] : "";
}

function extractChangeText(line = "", market = {}) {
  const candidates = [market.change, line].filter(Boolean).map(normalizeMinus);
  for (const text of candidates) {
    const withLabel = text.match(/前日比\s*([+\-]?\d[\d,.]*)\s*(?:円|ドル|USD|pt)?\s*、\s*([+\-]?\d[\d,.]*\s*(?:％|%)?)/);
    if (withLabel) {
      return `${withLabel[1]}　${withLabel[2].replace("%", "％")}`;
    }

    const inParen = text.match(/[（(]\s*([+\-]?\d[\d,.]*)\s*(?:円|ドル|USD|pt)?\s*、\s*([+\-]?\d[\d,.]*\s*(?:％|%)?)/);
    if (inParen) {
      return `${inParen[1]}　${inParen[2].replace("%", "％")}`;
    }

    const signedPair = text.match(/([+\-]\d[\d,.]*)\s*(?:円|ドル|USD|pt)?\s*、\s*([+\-]\d[\d,.]*\s*(?:％|%))/);
    if (signedPair) {
      return `${signedPair[1]}　${signedPair[2].replace("%", "％")}`;
    }

    const single = text.match(/前日比\s*([+\-]?\d[\d,.]*)\s*(?:円|ドル|USD|pt)?/);
    if (single) {
      return single[1];
    }
  }
  return "";
}

function metricSourceValues(report, definition) {
  const market = reportMarket(report, definition);
  return [
    market?.price,
    market?.change,
    market?.material,
    market?.positioning,
    market?.levels,
    market?.risk,
    market?.mainScenario,
    market?.alternativeScenario,
    ...sourceLines(report),
    ...asArray(report.positioning).map(textOf),
    ...asArray(report.crossAssetFlow).map(textOf)
  ];
}

function metricSegments(report, definition) {
  return uniq(metricSourceValues(report, definition)
    .filter(Boolean)
    .flatMap(splitMarketSegments)
    .map((line) => cleanText(line, 240))
    .filter((line) => isDefinitionLine(line, definition)));
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
    report.fullText,
    report.rawText,
    report.body,
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

function extractFullTextSection(report, headingPatterns, stopPatterns, max = 220) {
  const text = String(report.fullText || report.rawText || report.body || "");
  if (!text) return "";
  const normalized = text.replace(/\r/g, "").trim();

  for (const headingPattern of headingPatterns) {
    const headingMatch = normalized.match(headingPattern);
    if (!headingMatch) continue;

    const start = (headingMatch.index || 0) + headingMatch[0].length;
    let section = normalized.slice(start).replace(/^[\s:：・-]+/, "").trim();
    let stopIndex = section.length;

    for (const stopPattern of stopPatterns) {
      const stopMatch = section.match(stopPattern);
      if (stopMatch && stopMatch.index > 0) {
        stopIndex = Math.min(stopIndex, stopMatch.index);
      }
    }

    section = section.slice(0, stopIndex).trim();
    const lines = section
      .split(/\n+/)
      .map((line) => line.replace(/^[・\-*]\s*/, "").trim())
      .filter(Boolean)
      .filter((line) => !/^\d{1,2}[.．]\s/.test(line));

    const cleaned = cleanText(lines.join(" "), max);
    if (cleaned) return cleaned;
  }

  return "";
}

function breakConditionsFromReport(report, max = 180) {
  const explicit = cleanText(report.breakConditions || report.breakCondition || report.scenarioBreakConditions || "", max);
  if (explicit) return explicit;

  const fromFullText = extractFullTextSection(
    report,
    [
      /\n\s*(?:\d{1,2}[.．]\s*)?シナリオが崩れる条件(?:・リスク管理)?\s*\n/,
      /\n\s*(?:\d{1,2}[.．]\s*)?崩れる条件(?:・リスク管理)?\s*\n/,
      /\n\s*(?:\d{1,2}[.．]\s*)?シナリオが崩れる条件(?:・リスク管理)?[:：]\s*/
    ],
    [
      /\n\s*(?:\d{1,2}[.．]\s*)?(?:翌東京時間への引き継ぎ|次の時間帯への引き継ぎ|引き継ぎ|結論|最終判断)\s*\n/,
      /\n\s*(?:メインシナリオ|代替シナリオ|今日の結論)\s*\n/
    ],
    max
  );
  if (fromFullText) return fromFullText;

  const marketBreaks = asArray(report.markets)
    .map((market) => cleanText(market.breakCondition || "", 90))
    .filter(Boolean);
  return marketBreaks.length ? marketBreaks.slice(0, 3).join(" / ") : "";
}

function temperatureValueFromReport(report, definition) {
  const text = allText(report);
  for (const pattern of definition.patterns) {
    const match = text.match(pattern);
    if (!match) continue;
    const raw = match[1] || "";
    if (/取得不能|未確認|確認できず/.test(raw)) {
      return { value: null, label: "取得不能", note: cleanText(raw, 48) };
    }
    const value = Number(String(raw).replace(/,/g, ""));
    if (Number.isFinite(value)) return { value, label: temperatureBandLabel(value, definition), note: "" };
  }
  return { value: null, label: "未取得", note: "本文に数値なし" };
}

function temperatureBandLabel(value, definition) {
  const found = definition.thresholds.find(([limit]) => value <= limit);
  return found ? found[1] : "判定保留";
}

function temperaturePercent(value, definition) {
  if (!Number.isFinite(value)) return 0;
  return Math.max(0, Math.min(100, (value / definition.max) * 100));
}

function renderTemperatureMini(report) {
  const container = $("temperatureMiniCards");
  if (!container) return;
  container.innerHTML = TEMPERATURE_MINI_DEFINITIONS.map((definition) => {
    const metric = temperatureValueFromReport(report, definition);
    const pct = temperaturePercent(metric.value, definition);
    const valueText = Number.isFinite(metric.value)
      ? metric.value.toLocaleString("ja-JP", { maximumFractionDigits: metric.value >= 10 ? 1 : 2 })
      : "未取得";
    const title = Number.isFinite(metric.value)
      ? `${definition.label}: ${valueText} / ${metric.label}`
      : `${definition.label}: ${metric.label}`;
    const rangeItems = definition.ranges.map((item) => `<span class="temperature-range-chip range-${item.tone}">
      <b>${esc(item.range)}</b>${esc(item.label)}
    </span>`).join("");
    return `<article class="temperature-mini-card temperature-${definition.accent}" title="${esc(title)}">
      <div class="temperature-mini-head">
        <div>
          <h3>${esc(definition.label)}</h3>
          <p>${esc(definition.subtitle)}</p>
        </div>
        <strong>${esc(valueText)}</strong>
      </div>
      <div class="temperature-mini-bar" aria-hidden="true">
        <span style="width:${pct}%"></span>
      </div>
      <div class="temperature-mini-foot">
        <b>${esc(metric.label)}</b>
        <span>${esc(metric.note || `${dateToJp(report.date)} ${report.time}`)}</span>
      </div>
      <div class="temperature-card-ranges" aria-label="${esc(definition.label)}の判定レンジ">
        ${rangeItems}
      </div>
    </article>`;
  }).join("");
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
  return metricSegments(report, definition).find((line) => (
    /取得不能|未確認/.test(line) || extractPriceValue(line, definition)
  )) || "";
}

function parseMetric(report, definition) {
  const market = reportMarket(report, definition) || {};
  const line = findMetricLine(report, definition);
  if (!line) {
    return {
      value: "取得不能",
      unit: "",
      change: cleanText(market?.direction || "理由：JSONに価格項目なし", 38),
      trend: trendFromText(market?.direction || ""),
      raw: ""
    };
  }

  const value = extractPriceValue(line, definition);
  const change = extractChangeText(line, market);
  if (value) {
    return {
      value,
      unit: definition.unit,
      change: change || "前日比：取得不能",
      trend: trendFromText(change || market.direction || line),
      raw: line
    };
  }

  return {
    value: "取得不能",
    unit: "",
    change: cleanText(lineAfterLabel(line) || market.direction || "理由：価格として読める数値なし", 38),
    trend: /取得不能|未確認/.test(line) ? "missing" : trendFromText(market.direction || line),
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
      if (sentences.length) return cleanText(`${sentences.join("。")}。`, 160);
    }
  }

  const market = reportMarket(report, definition);
  return cleanText(market?.material || market?.direction || "", 140);
}

function marketReason(report, definition, metric) {
  const market = reportMarket(report, definition);
  const direct = [market?.material, market?.positioning].find((item) => (
    item &&
    item !== "本文参照" &&
    item.length <= 150 &&
    !/前営業日終値|主要市場データ|Dow：|VIX：|Fear & Greed/.test(item)
  ));
  if (direct) return cleanText(direct, 150);
  const outlook = findOutlookSentence(report, definition);
  if (outlook) return outlook;
  if (metric.raw && metric.raw.length <= 180) return cleanText(metric.raw.replace(/^.*?：/, ""), 150);
  return cleanText(market?.material || "理由：本文に市場別理由がありません", 150);
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
  return { verdict, cls, reason: cleanText(text, 140) };
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
  if (usable) return cleanText(raw, 110);
  const text = allText(report);
  const rules = {
    gold: /米10年債|金利/.test(text) ? "米金利上昇・ドル高" : "金利材料の急変",
    oil: /82ドル割れ/.test(text) ? "82ドル割れで短期ロング解消" : "在庫・地政学材料の反転",
    nikkei: /61,900/.test(text) ? "61,900円割れ・円急騰" : "米株安と円高の同時進行",
    usdjpy: /163.20/.test(text) ? "163.20円割れ・日銀後の円急騰" : "日銀会合後の円買い",
    eurusd: /ドル/.test(text) ? "ドル材料の急変" : "欧州材料の悪化",
    btc: /VIX|米株/.test(text) ? "VIX上昇・米株安" : "リスクオフ再燃"
  };
  return rules[definition.key] || cleanText(report.breakConditions || "理由：市場別リスク記載なし", 110);
}

function splitTheme(report) {
  const theme = cleanText(report.theme || "", 250);
  const sentences = theme.split(/。/).map((item) => item.trim()).filter(Boolean);
  return sentences.slice(0, 3).map((item) => `${item}。`);
}

function topList(items, limit = 3, max = 120) {
  return asArray(items).map(textOf).filter(Boolean).map((item) => cleanText(item, max)).slice(0, limit);
}

function proseSegments(value = "", limit = 4, max = 180) {
  const text = cleanText(value, 2400);
  if (!text) return [];
  const sentences = text.match(/[^。！？!?]+[。！？!?]?/g) || [text];
  return sentences
    .map((item) => cleanText(item, max))
    .filter(Boolean)
    .slice(0, limit);
}

function proseItems(values, limit = 4, max = 180) {
  return asArray(values)
    .map(textOf)
    .filter(Boolean)
    .flatMap((item) => proseSegments(item, 4, max))
    .slice(0, limit);
}

function proseHtml(value, limit = 4, max = 180) {
  const parts = proseSegments(value, limit, max);
  return parts.map((part) => `<p>${esc(part)}</p>`).join("");
}

function renderProseList(id, values, fallback) {
  const element = $(id);
  const items = values.filter(Boolean);
  element.classList.add("prose-list");
  element.innerHTML = items.length
    ? items.map((value) => `<li>${proseHtml(value, 2, 180) || `<p>${esc(value)}</p>`}</li>`).join("")
    : `<li class="missing"><p>${esc(fallback)}</p></li>`;
}

function renderProseBlock(id, value, fallback, limit = 4, max = 180) {
  const element = $(id);
  const html = proseHtml(value || "", limit, max);
  element.classList.add("prose-block");
  element.innerHTML = html || `<p class="missing">${esc(fallback)}</p>`;
}

function splitNewsSentences(value = "") {
  return cleanText(value, 1200)
    .split(/。|\n|(?=\d{1,2}:\d{2}\s)/)
    .map((item) => cleanText(item.replace(/^[・\-\s]+/, ""), 120))
    .filter((item) => item.length >= 10);
}

function fallbackNewsItems(report) {
  const explicit = topList(report.news, 5, 78);
  if (explicit.length) return explicit;

  const keyword = /原油|WTI|金利|米10年|米2年|日銀|FOMC|FRB|CPI|PCE|ISM|雇用|介入|USD\/JPY|円|ドル|Nasdaq|S&P|日経|BTC|金|中東|イラン|OPEC|決算|AI|PMI|VIX/;
  const candidates = [
    report.theme,
    ...asArray(report.changes).map(textOf),
    ...asArray(report.consistency).map(textOf),
    ...asArray(report.events).map(textOf),
    ...asArray(report.markets).flatMap((market) => [
      market.material,
      market.risk,
      market.breakCondition
    ])
  ]
    .filter(Boolean)
    .flatMap(splitNewsSentences)
    .filter((item) => keyword.test(item));

  return uniq(candidates).slice(0, 5).map((item) => cleanText(item, 78));
}

function handoverSectionLines(fullText = "") {
  const lines = String(fullText || "")
    .split(/\n+/)
    .map((line) => cleanText(line.replace(/^[・\-\s]+/, ""), 180))
    .filter(Boolean);
  const start = lines.findIndex((line) => /次の時間帯への引き継ぎ|NY時間への引き継ぎ|欧州時間への引き継ぎ|東京時間への引き継ぎ/.test(line));
  if (start < 0) return [];

  const found = [];
  for (let i = start + 1; i < lines.length; i += 1) {
    const line = lines[i];
    if (/^\d{1,2}[.．]\s/.test(line) && found.length) break;
    if (/^(最重要チェックポイント|チェックポイント)[:：]?/.test(line)) break;
    if (/^(次の時間帯への引き継ぎ|NY時間への引き継ぎ|欧州時間への引き継ぎ|東京時間への引き継ぎ)$/.test(line)) continue;
    found.push(line);
    if (found.length >= 5) break;
  }

  return found.flatMap(splitNewsSentences).map((item) => cleanText(item, 88)).filter(Boolean);
}

function fallbackHandoverItems(report) {
  const explicit = topList(report.handover, 3, 88);
  if (explicit.length) return explicit;

  const fromFullText = handoverSectionLines(report.fullText);
  if (fromFullText.length) return uniq(fromFullText).slice(0, 3);

  const keyword = /USD\/JPY|円|ドル|日経|Nasdaq|S&P|BTC|金|原油|WTI|米10年|金利|ISM|FOMC|FRB|日銀|欧州|NY|東京|イベント|リスク|注目/;
  const candidates = [
    report.mainScenario,
    report.alternativeScenario,
    ...asArray(report.changes).map(textOf),
    report.theme,
    ...asArray(report.events).map(textOf),
    ...asArray(report.riskManagement).map(textOf),
    report.breakConditions
  ]
    .filter(Boolean)
    .flatMap(splitNewsSentences)
    .filter((item) => keyword.test(item));

  return uniq(candidates).slice(0, 3).map((item) => cleanText(item, 88));
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

function splitFlowAssets(value = "") {
  return cleanText(value, 360)
    .replace(/^(?:資金)?流入(?:候補)?[：:]/, "")
    .replace(/^資金流出・巻き戻し候補[：:]/, "")
    .replace(/^(?:資金)?流出(?:候補)?[：:]/, "")
    .replace(/。.*$/, "")
    .split(/[、,，]/)
    .map((item) => cleanText(item.replace(/^(候補|主な候補)\s*/, ""), 26))
    .filter(Boolean);
}

function explicitFlowItems(report, type) {
  const rows = asArray(report.crossAssetFlow).map(textOf).map((value) => cleanText(value, 420)).filter(Boolean);
  const pattern = type === "in"
    ? /^(?:資金)?流入(?:候補)?[：:]/
    : /^(?:資金)?流出(?:候補)?[：:]|^資金流出・巻き戻し候補[：:]/;
  return rows
    .filter((row) => pattern.test(row))
    .flatMap(splitFlowAssets);
}

function inferredFlowItems(report, trend) {
  return FLOW_ASSETS
    .map((asset) => ({ asset, flow: flowDirection(report, asset) }))
    .filter((item) => item.flow.trend === trend)
    .map((item) => item.asset);
}

function flowFeatures(report) {
  const rows = asArray(report.crossAssetFlow).map(textOf).map((value) => cleanText(value, 420)).filter(Boolean);
  const features = rows
    .filter((row) => !/^(?:資金)?流入(?:候補)?[：:]|^(?:資金)?流出(?:候補)?[：:]|^資金流出・巻き戻し候補[：:]/.test(row))
    .flatMap((row) => row.split("。"))
    .map((row) => cleanText(row, 54))
    .filter(Boolean);
  return features.length ? features.slice(0, 3) : ["本文のクロスアセット資金フローから自動判定しています"];
}

// More tolerant parser for the dashboard cross-asset flow cards.
// It accepts "流入:", "資金が流入している資産:", "売られている資産:" and mixed one-line flow summaries.
function flowLabelAlternatives_(type) {
  return type === "in"
    ? [
        "資金が流入している資産",
        "資金流入資産",
        "資金流入候補",
        "資金流入",
        "流入資産",
        "流入候補",
        "流入",
        "買われている資産",
        "買われる資産",
        "買い候補"
      ]
    : [
        "資金が流出している資産",
        "資金流出・巻き戻し候補",
        "資金流出資産",
        "資金流出候補",
        "資金流出",
        "流出資産",
        "流出候補",
        "流出",
        "売られている資産",
        "売られる資産",
        "売り候補",
        "巻き戻し候補"
      ];
}

function escapeFlowRegex_(value) {
  return String(value).replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function flowLabelRegex_(type) {
  return new RegExp("(" + flowLabelAlternatives_(type).map(escapeFlowRegex_).join("|") + ")\\s*[：:]", "g");
}

function allFlowLabelsRegex_() {
  return new RegExp(
    "(" +
      flowLabelAlternatives_("in").concat(flowLabelAlternatives_("out")).map(escapeFlowRegex_).join("|") +
    ")\\s*[：:]",
    "g"
  );
}

function splitFlowAssets(value = "") {
  return cleanText(value, 900)
    .replace(allFlowLabelsRegex_(), "")
    .split(/[、,\n\r]/)
    .map((item) => cleanText(
      item
        .replace(/^[・\-–—\s]+/, "")
        .replace(/^(主な資産|候補|資産|市場)\s*[：:]?\s*/, "")
        .replace(/。.*$/, ""),
      42
    ))
    .filter((item) => item && !/^(なし|取得不能|不明)$/.test(item))
    .filter((item) => item.length <= 42);
}

function flowSegments_(row, type) {
  const text = cleanText(row, 1200);
  const labels = [];
  const allPattern = allFlowLabelsRegex_();
  let match;

  while ((match = allPattern.exec(text)) !== null) {
    const label = match[1];
    const labelType = flowLabelAlternatives_("in").includes(label) ? "in" : "out";
    labels.push({ type: labelType, index: match.index, end: allPattern.lastIndex });
  }

  if (!labels.length) return [];

  return labels
    .filter((label) => label.type === type)
    .map((label) => {
      const next = labels.find((candidate) => candidate.index > label.index);
      return text.slice(label.end, next ? next.index : text.length);
    });
}

function explicitFlowItems(report, type) {
  const rows = asArray(report.crossAssetFlow)
    .map(textOf)
    .map((value) => cleanText(value, 1200))
    .filter(Boolean);

  return uniq(rows.flatMap((row) => flowSegments_(row, type)).flatMap(splitFlowAssets));
}

function flowFeatures(report) {
  const rows = asArray(report.crossAssetFlow)
    .map(textOf)
    .map((value) => cleanText(value, 1200))
    .filter(Boolean);
  const labeledSegments = rows.flatMap((row) => flowSegments_(row, "in").concat(flowSegments_(row, "out")));
  const labeledText = labeledSegments.join(" ");
  const features = rows
    .map((row) => row.replace(labeledText, ""))
    .flatMap((row) => row.split(/[。\n\r]/))
    .map((row) => cleanText(row, 120))
    .filter(Boolean)
    .filter((row) => !allFlowLabelsRegex_().test(row));

  return features.length ? uniq(features).slice(0, 4) : ["本文のクロスアセット資金フローから自動判定しています。"];
}

function semanticFlowItems(report, type) {
  const text = [
    ...asArray(report.crossAssetFlow).map(textOf),
    report.theme,
    report.changes,
    report.consistency,
    report.positioning,
    report.leadingMarket
  ].flatMap(asArray).map(textOf).join(" ");
  const checks = type === "in"
    ? [
        [/米国債|債券.*買|金利.*低下|利回り.*低下/, "債券（米国）"],
        [/金.*買|ゴールド.*上昇|安全資産|質への逃避/, "金"],
        [/円高|円買い|円ショート.*巻き戻し|キャリー.*巻き戻し/, "円"],
        [/米国株.*上昇|S&P.*上昇|Nasdaq.*上昇|リスクオン/, "米国株"],
        [/BTC.*上昇|暗号資産.*流入|BTC.*流入/, "暗号資産"],
        [/原油.*上昇|WTI.*上昇/, "原油"]
      ]
    : [
        [/原油急落|原油安|原油.*下落|WTI.*急落|WTI.*下落|原油.*売/, "原油"],
        [/エネルギー株.*(売|下落|逆風)|原油安.*エネルギー株/, "エネルギー株"],
        [/輸出株.*(売|下落|逆風)|円高.*輸出株|日本輸出株/, "日本輸出株"],
        [/AI.*(売|弱|警戒|下落)|半導体.*(売|弱|警戒|下落)/, "AI・半導体株の一部"],
        [/円ショート|ドルロング|キャリー.*巻き戻し/, "円ショート・ドルロング"],
        [/金.*下落|ゴールド.*下落|金.*売/, "金"],
        [/BTC.*下落|暗号資産.*流出|BTC.*売/, "暗号資産"],
        [/株.*下落|米国株.*売|株式.*流出/, "株式"]
      ];

  return checks.filter(([pattern]) => pattern.test(text)).map(([, label]) => label);
}

function renderFlowList(id, items, type, emptyText) {
  const node = $(id);
  if (!node) return;
  const symbol = type === "out" ? "↓" : type === "feature" ? "・" : "↑";
  const cls = type === "out" ? "out" : type === "feature" ? "feature" : "in";
  const values = uniq(items).slice(0, 6);
  node.innerHTML = values.length
    ? values.map((item) => `<li><span class="flow-symbol ${cls}">${symbol}</span><span>${esc(item)}</span></li>`).join("")
    : `<li class="flow-empty"><span class="flow-symbol feature">・</span><span>${esc(emptyText)}</span></li>`;
}

function renderFlow(report) {
  const inflow = explicitFlowItems(report, "in");
  const outflow = explicitFlowItems(report, "out");
  const inferredIn = uniq(inferredFlowItems(report, "up").concat(semanticFlowItems(report, "in")));
  const inferredOut = uniq(inferredFlowItems(report, "down").concat(semanticFlowItems(report, "out")));
  const inItems = inflow.length ? inflow : inferredIn;
  const outItems = outflow.length ? outflow : inferredOut;
  const featureItems = flowFeatures(report);

  if ($("flowInItems") || $("flowOutItems") || $("flowFeatureItems")) {
    renderFlowList("flowInItems", inItems, "in", "流入資産がJSONにありません");
    renderFlowList("flowOutItems", outItems, "out", "流出資産がJSONにありません");
    renderFlowList("flowFeatureItems", featureItems, "feature", "フローの特徴がJSONにありません");
    return;
  }

  if ($("flowRows")) {
    $("flowRows").innerHTML = [
      ...inItems.map((item) => ({ asset: item, direction: "流入", cls: "up" })),
      ...outItems.map((item) => ({ asset: item, direction: "流出", cls: "down" }))
    ].map((item) => `<tr>
      <th>${esc(item.asset)}</th>
      <td class="${item.cls}">${esc(item.direction)}</td>
      <td>本文</td>
      <td class="${item.cls}">更新</td>
      <td>クロスアセット資金フローから抽出</td>
    </tr>`).join("");
  }

  if ($("flowSummary")) {
    $("flowSummary").textContent = featureItems.join(" ");
  }
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
  const news = fallbackNewsItems(report);
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

function importanceStars(value, title = "") {
  const numeric = Number(value);
  if (Number.isFinite(numeric)) return "★".repeat(Math.max(1, Math.min(3, numeric)));
  const text = `${value || ""} ${title}`;
  if (/high|最重要|重要度3|★★★|FOMC|日銀|PCE|CPI|雇用/.test(text)) return "★★★";
  if (/low|低|重要度1|★$/.test(text)) return "★";
  return "★★";
}

function normalizeCalendarEvent(event) {
  const title = cleanText(event?.title || event?.event || event?.name || "", 56);
  const datetime = String(event?.datetimeJst || event?.datetime || "");
  const date = String(event?.date || datetime.slice(0, 10) || "").trim();
  const time = String(event?.time || datetime.slice(11, 16) || "").trim();
  const timingLabel = cleanText(event?.timingLabel || event?.timing || event?.when || "", 16);
  if (!title || !/^\d{4}-\d{2}-\d{2}$/.test(date)) return null;

  return {
    date,
    time: /^\d{1,2}:\d{2}$/.test(time) ? time.padStart(5, "0") : timingLabel || "未定",
    title,
    country: cleanText(event?.country || event?.region || regionFromEvent(title), 14),
    importance: importanceStars(event?.importance, title),
    forecast: cleanText(event?.forecast ?? event?.estimate ?? event?.consensus ?? "", 32),
    previous: cleanText(event?.previous ?? event?.prev ?? "", 32),
    actual: cleanText(event?.actual ?? event?.result ?? "", 32),
    resultComparison: cleanText(event?.resultComparison || event?.surprise || "", 42),
    resultExplanation: cleanText(event?.resultExplanation || event?.marketReaction || "", 80),
    status: cleanText(event?.status || "", 20),
    category: cleanText(event?.category || "", 28),
    detail: cleanText(event?.reason || event?.sourceNote || "", 56)
  };
}

function calendarRowsForReport(report) {
  const baseDate = new Date(`${report.date}T${report.time || "00:00"}:00+09:00`);
  const recentPastLimit = new Date(baseDate.getTime() - 3 * 24 * 3600000);
  const rows = dashboardCalendarEvents
    .filter((event) => event.category !== "monitoring_headline")
    .filter((event) => {
      const hasResult = Boolean(event.actual || event.resultComparison || event.resultExplanation || event.status === "released");
      if (event.date > report.date) return true;
      if (event.date < report.date) {
        const eventDate = new Date(`${event.date}T${/^\d{2}:\d{2}$/.test(event.time || "") ? event.time : "00:00"}:00+09:00`);
        return hasResult && !Number.isNaN(eventDate.getTime()) && eventDate >= recentPastLimit;
      }
      if (/^\d{2}:\d{2}$/.test(event.time || "") && /^\d{2}:\d{2}$/.test(report.time || "")) {
        return event.time >= report.time || hasResult || event.status === "needs_result";
      }
      return true;
    })
    .sort((a, b) => {
      const aSame = a.date === report.date ? 0 : a.date > report.date ? 1 : 2;
      const bSame = b.date === report.date ? 0 : b.date > report.date ? 1 : 2;
      if (aSame !== bSame) return aSame - bSame;
      return `${a.date} ${a.time}`.localeCompare(`${b.date} ${b.time}`);
    });
  const sameDate = rows.filter((event) => event.date === report.date);
  return (sameDate.length ? sameDate : rows).slice(0, 6);
}

function calendarUnavailableNotice() {
  const status = dashboardCalendarMeta?.status || "";
  if (!status || status === "ok" || status === "report_only") return "";
  if (status === "not_configured") return "\u5916\u90e8\u30ab\u30ec\u30f3\u30c0\u30fc\u306f\u4f7f\u308f\u305a\u3001\u672c\u6587\u30a4\u30d9\u30f3\u30c8\u304b\u3089\u8868\u793a";
  if (status === "auth_error") return "Trading Economics API\u8a8d\u8a3c\u30a8\u30e9\u30fc";
  if (status === "partial") return "\u5916\u90e8\u30ab\u30ec\u30f3\u30c0\u30fc\u3092\u4e00\u90e8\u53d6\u5f97\u3067\u304d\u307e\u305b\u3093";
  return "\u5916\u90e8\u30ab\u30ec\u30f3\u30c0\u30fc\u53d6\u5f97\u30a8\u30e9\u30fc";
}

function eventDetail(row) {
  const forecast = row.forecast && !/手入力待ち|未取得|該当なし/.test(row.forecast) ? `予想 ${row.forecast}` : "";
  const previous = row.previous && !/手入力待ち|未取得|該当なし/.test(row.previous) ? `前回 ${row.previous}` : "";
  const parts = [
    forecast,
    previous,
    row.actual ? `結果 ${row.actual}` : "",
    row.resultComparison ? `比較 ${row.resultComparison}` : "",
    row.resultExplanation ? `説明 ${row.resultExplanation}` : "",
    row.detail || ""
  ].filter(Boolean);
  if (parts.length) return `<small class="event-detail">${esc(parts.join(" / "))}</small>`;
  const notice = calendarUnavailableNotice();
  if (notice) return `<small class="event-detail">${esc(notice)}</small>`;
  return "";
}

function normalizeEventTime(value = "") {
  const match = String(value || "").match(/\b([01]?\d|2[0-3]):([0-5]\d)\b/);
  return match ? `${match[1].padStart(2, "0")}:${match[2]}` : "";
}

function normalizeEventDate(value = "", fallbackDate = "") {
  const text = String(value || "");
  const iso = text.match(/(\d{4})[-/](\d{1,2})[-/](\d{1,2})/);
  if (iso) return `${iso[1]}-${iso[2].padStart(2, "0")}-${iso[3].padStart(2, "0")}`;
  const monthDay = text.match(/(?:^|[^\d])(\d{1,2})\/(\d{1,2})(?:[^\d]|$)/);
  if (monthDay && /^\d{4}-\d{2}-\d{2}$/.test(fallbackDate || "")) {
    return `${fallbackDate.slice(0, 4)}-${monthDay[1].padStart(2, "0")}-${monthDay[2].padStart(2, "0")}`;
  }
  return /^\d{4}-\d{2}-\d{2}$/.test(fallbackDate || "") ? fallbackDate : "";
}

function splitEventText(value = "") {
  const text = cleanText(value, 1200)
    .replace(/^今後の重要イベント[:：\s]*/, "")
    .replace(/。$/, "");
  if (!text) return [];

  const numbered = text
    .replace(/(?:^|\s)(\d+[.)．]|[①-⑳])/g, "\n$1")
    .split(/\n+/)
    .map((item) => item.trim())
    .filter(Boolean);
  const chunks = numbered.length > 1 ? numbered : [text];

  return chunks
    .flatMap((item) => item.length >= 56 && /、/.test(item) ? item.split(/、/) : [item])
    .map((item) => item.replace(/[。,\s]+$/, "").trim())
    .filter((item) => item.length >= 2);
}

function isDashboardEventItem(item = "") {
  if (/今日の相場テーマ|6市場の見通し|メインシナリオ|代替シナリオ|特に注目する材料|総合判断|最終判断/.test(item)) {
    return false;
  }
  if (/^(金|原油|WTI原油|日経225先物|USD\/JPY|EUR\/USD|BTCUSD|BTC)[:：\s]/.test(item)) {
    return false;
  }
  return /\b[0-2]\d:[0-5]\d\b|FOMC|FRB|PCE|CPI|雇用|ISM|PMI|GDP|政策|会見|決算|在庫|OPEC|協議|ホルムズ|介入|日銀|指標|経済・物価|発言|観測/.test(item);
}

function dashboardEventItems(report) {
  return uniq([
    ...asArray(report.events),
    ...asArray(report.importantEvents),
    ...asArray(report.calendarEvents)
  ]
    .map(textOf)
    .flatMap(splitEventText)
    .map((item) => cleanText(item, 46))
    .filter(isDashboardEventItem))
    .slice(0, 6);
}

function eventTitleFromText(item = "") {
  return cleanText(String(item)
    .replace(/^\d{4}[-/]\d{1,2}[-/]\d{1,2}\s*/, "")
    .replace(/^\d{1,2}\/\d{1,2}\s*/, "")
    .replace(/^\b[0-2]?\d:[0-5]\d\s*/, "")
    .replace(/^(米国|日本|欧州|中国|複数)\s+/, "")
    .replace(/^随時\s*/, "")
    .replace(/^予定確認\s*/, ""), 56);
}

function reportEventRowFromText(item, report) {
  const title = eventTitleFromText(item);
  if (!title) return null;
  const time = normalizeEventTime(item);
  const date = normalizeEventDate(item, report.date);
  return {
    date,
    time: time || (/協議|再開|発言|観測|方針|地政学|介入/.test(item) ? "随時" : "予定確認"),
    title,
    country: regionFromEvent(item),
    importance: importanceFromEvent(item),
    next: fallbackEventNextText(item)
  };
}

function reportEventRowFromObject(event, report) {
  if (!event || typeof event !== "object") return null;
  const rawTitle = event.title || event.event || event.name || event.text || event.summary || "";
  const title = cleanText(rawTitle, 56);
  if (!title) return null;

  const rawDate = event.date || event.datetimeJst || event.datetime || event.time || "";
  const rawTime = event.time || event.datetimeJst || event.datetime || "";
  const date = normalizeEventDate(rawDate, report.date);
  const time = normalizeEventTime(rawTime) || cleanText(event.timing || event.when || "", 16) || "予定確認";
  const detail = [
    event.impact || event.markets || event.marketImpact ? `影響：${cleanText(asArray(event.impact || event.markets || event.marketImpact).join("・"), 42)}` : "",
    event.forecast || event.consensus ? `予想 ${cleanText(event.forecast || event.consensus, 24)}` : "",
    event.previous ? `前回 ${cleanText(event.previous, 24)}` : "",
    event.note ? cleanText(event.note, 46) : ""
  ].filter(Boolean).join(" / ");

  return {
    date,
    time,
    title,
    country: cleanText(event.country || event.region || regionFromEvent(title), 14),
    importance: importanceStars(event.importance || event.priority, title),
    next: cleanText(event.next || event.countdown || "", 18),
    detail
  };
}

function reportEventRows(report) {
  const sourceEvents = [
    ...asArray(report.events),
    ...asArray(report.importantEvents),
    ...asArray(report.calendarEvents)
  ];
  const rows = sourceEvents.flatMap((item) => {
    if (item && typeof item === "object") {
      const row = reportEventRowFromObject(item, report);
      return row ? [row] : [];
    }
    return splitEventText(textOf(item))
      .map((text) => cleanText(text, 46))
      .filter(isDashboardEventItem)
      .map((text) => reportEventRowFromText(text, report))
      .filter(Boolean);
  });

  const seen = new Set();
  return rows.filter((row) => {
    const key = `${row.time}|${row.country}|${row.title}`;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  }).slice(0, 6);
}

function reportEventDateTime(row, report) {
  if (!row?.time || !/^\d{2}:\d{2}$/.test(row.time)) return null;
  const date = row.date || report.date;
  const timestamp = new Date(`${date}T${row.time}:00+09:00`);
  return Number.isNaN(timestamp.getTime()) ? null : timestamp;
}

function isFutureTimedReportRow(row, baseReport) {
  const eventDate = reportEventDateTime(row, baseReport);
  if (!eventDate) return false;
  const baseDate = new Date(`${baseReport.date}T${baseReport.time || "00:00"}:00+09:00`);
  if (Number.isNaN(baseDate.getTime())) return true;
  return eventDate.getTime() >= baseDate.getTime();
}

function dedupeReportEventRows(rows) {
  const seen = new Set();
  return rows.filter((row) => {
    const key = `${row.date || ""}|${row.time || ""}|${row.country || ""}|${row.title || ""}`;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

function mergedReportEventRows(report) {
  const currentRows = reportEventRows(report);
  const sameDayRows = reports
    .filter((item) => item.date === report.date && item !== report)
    .flatMap((item) => reportEventRows(item));
  const futureTimedRows = sameDayRows
    .filter((row) => isFutureTimedReportRow(row, report))
    .sort((a, b) => {
      const aDate = reportEventDateTime(a, report);
      const bDate = reportEventDateTime(b, report);
      return (aDate?.getTime() || 0) - (bDate?.getTime() || 0);
    });
  const currentTimedRows = currentRows.filter((row) => reportEventDateTime(row, report));
  const currentFloatingRows = currentRows.filter((row) => !reportEventDateTime(row, report));

  return dedupeReportEventRows([
    ...currentTimedRows,
    ...futureTimedRows,
    ...currentFloatingRows
  ]).slice(0, 6);
}

function eventTiming(report, item) {
  const time = item.match(/\b([0-2]\d:[0-5]\d)\b/)?.[1];
  const date = item.match(/(\d{4}[-/]\d{1,2}[-/]\d{1,2}|\d{1,2}\/\d{1,2})/)?.[1];
  if (date && time) return `${date} ${time}`;
  if (time) return `${dateToJp(report.date)} ${time}`;
  if (/協議|再開|発言|観測|方針|地政学|介入/.test(item)) return "随時";
  return "予定確認";
}

function fallbackEventNextText(item) {
  if (/協議|再開|発言|観測|方針|地政学|介入/.test(item)) return "継続監視";
  if (/\b[0-2]\d:[0-5]\d\b/.test(item)) return "時刻指定";
  return "時刻未定";
}

function calendarEventTiming(row) {
  if (row.time === "随時" || row.time === "予定確認") return row.time;
  const date = dateToJp(row.date);
  return row.time && row.time !== "未定" ? `${date} ${row.time}` : `${date} 未定`;
}

function calendarNextText(row, report) {
  if (row.status === "released" || row.actual || row.resultComparison || row.resultExplanation) return "結果保存";
  if (row.status === "needs_result") return "結果待ち";
  if (row.time === "随時") return "継続監視";
  if (row.time === "予定確認") return "時刻未定";
  if (!row.time || row.time === "未定") return "時刻未定";
  const eventDate = new Date(`${row.date}T${row.time}:00+09:00`);
  const baseDate = new Date(`${report.date}T${report.time || "00:00"}:00+09:00`);
  if (Number.isNaN(eventDate.getTime()) || Number.isNaN(baseDate.getTime())) return "予定確認";
  const diff = eventDate.getTime() - baseDate.getTime();
  if (diff <= 0) return "発表済み";
  const hours = Math.floor(diff / 3600000);
  if (hours >= 24) return `${Math.floor(hours / 24)}日後`;
  return `${hours}時間後`;
}

function eventDisplayName(item = "") {
  return cleanText(item.replace(/^\b[0-2]\d:[0-5]\d\s*/, ""), 46);
}

function reportEventTiming(row, report) {
  if (row.time && /^\d{2}:\d{2}$/.test(row.time)) {
    return `${dateToJp(row.date || report.date)} ${row.time}`;
  }
  return row.time || "予定確認";
}

function isTimedEventRow(row) {
  return /^\d{2}:\d{2}$/.test(row?.time || "");
}

function reportEventNextText(row, report) {
  if (row.time && /^\d{2}:\d{2}$/.test(row.time)) return calendarNextText(row, report);
  if (row.next) return row.next;
  return fallbackEventNextText(row.title);
}

function renderEvents(report) {
  const calendarRows = calendarRowsForReport(report);
  if (calendarRows.length) {
    $("eventRows").innerHTML = calendarRows.map((row) => `<tr>
      <td>${esc(calendarEventTiming(row))}</td>
      <td><span class="event-title">${esc(row.title)}</span>${eventDetail(row)}</td>
      <td>${esc(row.country || regionFromEvent(row.title))}</td>
      <td>${esc(row.importance)}</td>
      <td>${esc(calendarNextText(row, report))}</td>
    </tr>`).join("");
    return;
  }

  const reportRows = mergedReportEventRows(report).filter(isTimedEventRow);
  if (reportRows.length) {
    $("eventRows").innerHTML = reportRows.map((row) => `<tr>
      <td>${esc(reportEventTiming(row, report))}</td>
      <td><span class="event-title">${esc(row.title)}</span>${eventDetail(row)}</td>
      <td>${esc(row.country || regionFromEvent(row.title))}</td>
      <td>${esc(row.importance)}</td>
      <td>${esc(reportEventNextText(row, report))}</td>
    </tr>`).join("");
    return;
  }

  const events = dashboardEventItems(report).filter((item) => /\b[0-2]\d:[0-5]\d\b/.test(item));
  $("eventRows").innerHTML = events.length ? events.map((item, index) => {
    const notice = calendarUnavailableNotice();
    const fallbackNote = index === 0 && notice
      ? `<small class="event-detail">${esc(notice)}\u3002\u672c\u6587\u30a4\u30d9\u30f3\u30c8\u304b\u3089\u8868\u793a</small>`
      : "";
    return `<tr>
      <td>${esc(eventTiming(report, item))}</td>
      <td><span class="event-title">${esc(eventDisplayName(item))}</span>${fallbackNote}</td>
      <td>${esc(regionFromEvent(item))}</td>
      <td>${esc(importanceFromEvent(item))}</td>
      <td>${esc(fallbackEventNextText(item))}</td>
    </tr>`;
  }).join("") : `<tr><td>予定なし</td><td>時刻が確定している重要イベントはありません</td><td>-</td><td>-</td><td>-</td></tr>`;
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
  const risk = cleanText(topList(report.riskManagement, 1, 90)[0] || breakConditionsFromReport(report, 110) || "", 86);
  const parts = [];
  if (lead) parts.push(`主導市場：${lead}`);
  if (main) parts.push(`基本姿勢：${main}`);
  if (risk) parts.push(`リスク管理：${risk}`);
  return parts.join("。") || "理由：結論に必要な項目がJSONにありません";
}

function renderScenarios(report) {
  renderProseBlock("mainScenario", report.mainScenario, "理由：メインシナリオがJSONにありません", 3, 180);
  renderProseBlock("alternativeScenario", report.alternativeScenario, "理由：代替シナリオがJSONにありません", 3, 180);
  const breakText = breakConditionsFromReport(report, 180);
  renderProseBlock("breakConditions", breakText, "理由：崩れる条件を本文から取得できませんでした", 4, 180);
  $("breakConditions").classList.toggle("missing", !breakText);
  renderList("handoverList", fallbackHandoverItems(report), "理由：引き継ぎ項目がJSONにありません");
  renderProseBlock("conclusionText", conclusionFrom(report), "理由：結論に必要な項目がJSONにありません", 4, 180);
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
  renderTemperatureMini(report);
  renderProseList("themeList", proseItems([report.theme], 5, 180), "理由：相場テーマがJSONにありません");
  renderProseList("changeList", proseItems(report.changes, 4, 170), "理由：前回からの変化がJSONにありません");
  renderProseBlock("leadingMarket", report.leadingMarket, "取得不能。理由：主導市場コメントがJSONにありません", 4, 180);
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
    const calendar = await loadDashboardEventCalendar();
    dashboardCalendarMeta = calendar;
    dashboardCalendarEvents = asArray(calendar.events).map(normalizeCalendarEvent).filter(Boolean);

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

async function loadDashboardEventCalendar() {
  try {
    const response = await fetch(`data/events.json?ts=${Date.now()}`, { cache: "no-store" });
    if (!response.ok) throw new Error(`data/events.json HTTP ${response.status}`);
    return await response.json();
  } catch (error) {
    try {
      const response = await fetch(`economic-calendar.json?ts=${Date.now()}`, { cache: "no-store" });
      if (!response.ok) throw new Error(`economic-calendar.json HTTP ${response.status}`);
      return await response.json();
    } catch (fallbackError) {
      return { status: "unavailable", events: [], error: `${error.message} / ${fallbackError.message}` };
    }
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
