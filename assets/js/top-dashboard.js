const REPORT_TIMES = ["08:00", "12:00", "16:00", "21:00"];

const MARKET_DEFINITIONS = [
  {
    key: "gold",
    dataKey: "gold",
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
    dataKey: "wti",
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
    dataKey: "nikkei225_futures_ose",
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
    dataKey: "usdjpy",
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
    dataKey: "eurusd",
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
    dataKey: "btcusd",
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

// Capture the requested slot before any asynchronous bootstrap may rewrite the URL.
const initialSlotParams = new URLSearchParams(window.location.search);
const initialRequestedDate = initialSlotParams.get("date");
const initialRequestedTime = initialSlotParams.get("time");
window.MarketReportInitialRequestedSlot =
  /^\d{4}-\d{2}-\d{2}$/.test(initialRequestedDate || "") &&
  /^(08:00|12:00|16:00|21:00)$/.test(initialRequestedTime || "")
    ? { date: initialRequestedDate, time: initialRequestedTime } : null;

let reports = [];
let selectedReport = null;
let dashboardMeta = null;
let dashboardCalendarEvents = [];
let dashboardCalendarMeta = null;
let stockAnalysisData = null;

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
  return Number.isFinite(max) && max > 0 && text.length > max ? `${text.slice(0, max)}...` : text;
}

function uniq(values) {
  return [...new Set(values.filter(Boolean))];
}

function normalizeMinus(value = "") {
  return String(value).replace(/[−－]/g, "-").trim();
}

function finiteNumber(value) {
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
}

function shortDateTime(value = "") {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return cleanText(value, 18);
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  const hour = String(date.getHours()).padStart(2, "0");
  const minute = String(date.getMinutes()).padStart(2, "0");
  return `${month}/${day} ${hour}:${minute}`;
}

function marketDataFor(report, definition) {
  const key = definition.dataKey || definition.key;
  const latestData = dashboardMeta?.marketData;
  const generatedDate = String(latestData?.generatedAt || "").slice(0, 10);
  const latestMatchesReport = Boolean(
    !isDashboardHistoricalArchive(report) && latestData
    && REPORT_TIMES.includes(latestData.reportSlot)
    && latestData.reportSlot === report?.time
    && generatedDate === report?.date
  );
  const latestItem = latestMatchesReport ? latestData?.markets?.[key] : null;
  const reportItem = report?.marketData?.markets?.[key];
  return latestItem || reportItem || null;
}

function marketDataChange(item) {
  const value = finiteNumber(item?.value);
  const previous = finiteNumber(item?.previousClose);
  const storedChange = finiteNumber(item?.change);
  const storedPercent = finiteNumber(item?.changePercent);
  const change = value !== null && previous !== null ? value - previous : storedChange;
  const changePercent = value !== null && previous !== null && previous !== 0
    ? ((value / previous) - 1) * 100
    : storedPercent;
  return { change, changePercent };
}

function formatMarketDataChange(item) {
  const { change, changePercent } = marketDataChange(item);
  if (change === null && changePercent === null) {
    return item?.fallbackUsed ? "前回確認値" : cleanText(item?.changeText || "前日比：取得不能", 42);
  }
  const value = finiteNumber(item?.value);
  const absValue = value !== null ? Math.abs(value) : null;
  const fractionDigits = absValue !== null && absValue < 10 ? 5 : absValue !== null && absValue < 1000 ? 2 : 0;
  const parts = [];
  if (change !== null) {
    parts.push(change.toLocaleString("ja-JP", {
      signDisplay: "always",
      minimumFractionDigits: fractionDigits,
      maximumFractionDigits: fractionDigits
    }));
  }
  if (changePercent !== null && Math.abs(changePercent) <= 100) {
    parts.push(`${changePercent.toLocaleString("ja-JP", {
      signDisplay: "always",
      minimumFractionDigits: 2,
      maximumFractionDigits: 2
    })}%`);
  }
  return parts.join(" / ") || cleanText(item?.changeText || "", 42) || (item?.fallbackUsed ? "前回確認値" : "前日比：取得不能");
}

function trendFromMarketData(item) {
  if (!item) return "missing";
  if (item.verificationStatus === "unavailable") return "missing";
  const { change, changePercent } = marketDataChange(item);
  const value = change ?? changePercent;
  if (value > 0) return "up";
  if (value < 0) return "down";
  return "flat";
}

function marketDataStatusText(item) {
  if (!item) return "";
  if (item.verificationStatus === "fallback") {
    return `前回確認値：${shortDateTime(item.lastVerifiedAt || item.asOf)}`;
  }
  if (item.verificationStatus === "verified") {
    return `確認済み：${cleanText(item.sourceName || item.sourceId || "市場データ", 22)}`;
  }
  return `取得失敗：${cleanText(item.error || item.note || "理由未確認", 26)}`;
}

function metricFromMarketData(report, definition) {
  const item = marketDataFor(report, definition);
  if (!item) return null;
  const value = finiteNumber(item.value);
  if (value === null) {
    return {
      value: "取得不能",
      unit: "",
      change: cleanText(item.error || item.note || "理由：市場データを取得できませんでした", 44),
      trend: "missing",
      raw: "marketData",
      sourceNote: marketDataStatusText(item),
      sourceClass: "missing"
    };
  }
  return {
    value: item.displayValue || value.toLocaleString("ja-JP", { maximumFractionDigits: 5 }),
    unit: item.unit || definition.unit,
    change: formatMarketDataChange(item),
    trend: trendFromMarketData(item),
    raw: "marketData",
    sourceNote: marketDataStatusText(item),
    sourceClass: item.fallbackUsed ? "fallback" : "verified"
  };
}

const TEMPERATURE_MINI_DEFINITIONS = [
  {
    id: "market.vix",
    label: "VIX",
    subtitle: "恐怖指数（米国・S&P500）",
    accent: "blue",
    max: 50,
    ranges: [
      { range: "0-15", label: "安定", tone: "extreme-greed" },
      { range: "15-20", label: "落ち着き", tone: "greed" },
      { range: "20-25", label: "注意", tone: "neutral" },
      { range: "25-35", label: "警戒", tone: "fear" },
      { range: "35-", label: "強い警戒", tone: "extreme-fear" }
    ],
    patterns: [/VIX(?:指数)?[：:\s]+(取得不能[^。\n]*|[0-9,.]+)/i]
  },
  {
    id: "market.nikkei_vi",
    label: "日経VI",
    subtitle: "恐怖指数（日経225）",
    accent: "purple",
    max: 60,
    ranges: [
      { range: "0-15", label: "安定", tone: "extreme-greed" },
      { range: "15-20", label: "落ち着き", tone: "greed" },
      { range: "20-25", label: "注意", tone: "neutral" },
      { range: "25-35", label: "警戒", tone: "fear" },
      { range: "35-", label: "強い警戒", tone: "extreme-fear" }
    ],
    patterns: [/日経VI[：:\s]+(取得不能[^。\n]*|[0-9,.]+)/]
  },
  {
    id: "sentiment.cnn_fear_greed",
    label: "Fear & Greed（株式）",
    subtitle: "市場心理指数（CNN）",
    accent: "green",
    max: 100,
    ranges: [
      { range: "0-24", label: "E.FEAR", tone: "extreme-fear" },
      { range: "25-44", label: "FEAR", tone: "fear" },
      { range: "45-55", label: "NEUTRAL", tone: "neutral" },
      { range: "56-74", label: "GREED", tone: "greed" },
      { range: "75-", label: "E.GREED", tone: "extreme-greed" }
    ],
    patterns: [/Fear\s*&\s*Greed(?:\s*Index)?[：:\s]+(取得不能[^。\n]*|[0-9,.]+)/i]
  },
  {
    id: "sentiment.crypto_fear_greed",
    label: "Crypto Fear & Greed",
    subtitle: "暗号資産心理（CoinMarketCap）",
    accent: "crypto",
    max: 100,
    ranges: [
      { range: "0-24", label: "E.FEAR", tone: "extreme-fear" },
      { range: "25-44", label: "FEAR", tone: "fear" },
      { range: "45-55", label: "NEUTRAL", tone: "neutral" },
      { range: "56-74", label: "GREED", tone: "greed" },
      { range: "75-", label: "E.GREED", tone: "extreme-greed" }
    ],
    patterns: [/Crypto\s+Fear\s*&\s*Greed[：:\s]+(取得不能[^。\n]*|[0-9,.]+)/i]
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
  const weekdays = ["日", "月", "火", "水", "木", "金", "土"];
  const parts = String(dateText || "").split("-");
  if (parts.length !== 3 || parts.some(part => !/^\d+$/.test(part))) return dateText || "日付不明";
  const [year, month, day] = parts;
  const date = new Date(Date.UTC(Number(year), Number(month) - 1, Number(day)));
  if (Number.isNaN(date.getTime())) return dateText || "日付不明";
  return `${year}/${month}/${day}（${weekdays[date.getUTCDay()]}）`;
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
  const marketDataKey = {
    "market.vix": "vix",
    "market.nikkei_vi": "nikkei_vi",
    "sentiment.cnn_fear_greed": "fear_greed",
    "sentiment.crypto_fear_greed": "crypto_fear_greed"
  }[definition.id];
  const item = marketDataFor(report, { key: marketDataKey, dataKey: marketDataKey });
  if (item) {
    const value = finiteNumber(item.value);
    if (value !== null) {
      const { change } = marketDataChange(item);
      return {
        value,
        label: temperatureBandLabel(value, definition) || item.classification || "",
        note: marketDataStatusText(item),
        change,
        asOf: item.asOf || item.lastVerifiedAt || "",
        sourceName: item.sourceName || item.sourceId || ""
      };
    }
    return {
      value: null,
      label: "取得不能",
      note: cleanText(item.error || item.note || "市場データ未取得", 48)
    };
  }

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
  return temperatureBand(value, definition).label;
}

function temperatureBand(value, definition) {
  if (!Number.isFinite(value)) return { label: "判定保留", tone: "unknown" };
  if (definition.id === "sentiment.cnn_fear_greed" || definition.id === "sentiment.crypto_fear_greed") {
    if (value <= 24) return { label: "EXTREME FEAR", tone: "extreme-fear" };
    if (value <= 44) return { label: "FEAR", tone: "fear" };
    if (value <= 55) return { label: "NEUTRAL", tone: "neutral" };
    if (value <= 74) return { label: "GREED", tone: "greed" };
    return { label: "EXTREME GREED", tone: "extreme-greed" };
  }
  if (value <= 15) return { label: "安定", tone: "extreme-greed" };
  if (value <= 20) return { label: "落ち着き", tone: "greed" };
  if (value <= 25) return { label: "注意", tone: "neutral" };
  if (value <= 35) return { label: "警戒", tone: "fear" };
  return { label: "強い警戒", tone: "extreme-fear" };
}

function temperatureTone(value, definition) {
  return temperatureBand(value, definition).tone;
}

function temperaturePercent(value, definition) {
  if (!Number.isFinite(value)) return 0;
  return Math.max(0, Math.min(100, (value / definition.max) * 100));
}

function parseDateOnly(value = "") {
  const match = String(value).match(/(\d{4})[-/]?(\d{2})[-/]?(\d{2})/);
  if (!match) return null;
  const date = new Date(`${match[1]}-${match[2]}-${match[3]}T00:00:00+09:00`);
  return Number.isNaN(date.getTime()) ? null : date;
}

function stockBreadthFor(region, report) {
  const rows = asArray(stockAnalysisData?.marketInternals?.[region]?.rows);
  const row = rows.find((item) => /値上がり.*値下がり|上昇銘柄.*下落銘柄/.test(String(item?.[0] || "")));
  const dataDate = parseDateOnly(stockAnalysisData?.dataAsOf || stockAnalysisData?.updatedAt);
  const reportDate = parseDateOnly(report?.date);
  const ageDays = dataDate && reportDate ? Math.abs(reportDate - dataDate) / 86400000 : Infinity;
  if (!row || ageDays > 4) {
    return {
      status: "unavailable",
      reason: row && dataDate
        ? `株式市場分析の基準日 ${dateToJp(dataDate.toISOString().slice(0, 10))} は表示日と一致しません`
        : "株式市場分析の騰落データが未連携です"
    };
  }
  const numbers = String(row[1] || "").match(/[\d,]+/g)?.map((value) => Number(value.replace(/,/g, ""))) || [];
  const advancers = numbers[0];
  const decliners = numbers[1];
  const unchanged = numbers[2] ?? null;
  if (!Number.isFinite(advancers) || !Number.isFinite(decliners)) {
    return { status: "unavailable", reason: "値上がり・値下がり銘柄数を確認できません" };
  }
  const total = advancers + decliners + (unchanged || 0);
  return {
    status: "available",
    advancers,
    decliners,
    unchanged,
    total,
    ratio: decliners > 0 ? advancers / decliners : null,
    asOf: dataDate?.toISOString().slice(0, 10) || "",
    source: stockAnalysisData?.sourceStatus || "株式市場分析"
  };
}

function breadthTone(data) {
  if (data.status !== "available" || !Number.isFinite(data.ratio)) return "unknown";
  if (data.ratio >= 2) return "extreme-greed";
  if (data.ratio >= 1.25) return "greed";
  if (data.ratio >= 0.8) return "neutral";
  if (data.ratio >= 0.5) return "fear";
  return "extreme-fear";
}

function breadthLabel(data) {
  const tone = breadthTone(data);
  return {
    "extreme-greed": "値上がりが広く優勢",
    greed: "値上がり優勢",
    neutral: "拮抗",
    fear: "値下がり優勢",
    "extreme-fear": "値下がりが広く優勢",
    unknown: "判定保留"
  }[tone];
}

function renderBreadthCard(region, report) {
  const data = stockBreadthFor(region, report);
  const isUs = region === "us";
  const title = isUs ? "アメリカ株の広がり" : "日本株の広がり";
  const detail = isUs ? "NYSE・NASDAQ等の市場内部" : "東証プライムの市場内部";
  if (data.status !== "available") {
    return `<article class="temperature-mini-card breadth-card temperature-tone-unknown">
      <div class="temperature-mini-head"><div><h3>${title}</h3><p>${detail}</p></div><strong>未取得</strong></div>
      <p class="breadth-missing">${esc(data.reason)}</p>
      <p class="temperature-source">株式市場分析ページの検証済みデータを参照</p>
    </article>`;
  }
  const tone = breadthTone(data);
  const unchanged = Number.isFinite(data.unchanged) ? data.unchanged.toLocaleString("ja-JP") : "－";
  const advPct = data.total ? (data.advancers / data.total) * 100 : 0;
  const flatPct = data.total && Number.isFinite(data.unchanged) ? (data.unchanged / data.total) * 100 : 0;
  const decPct = Math.max(0, 100 - advPct - flatPct);
  return `<article class="temperature-mini-card breadth-card temperature-tone-${tone}">
    <div class="temperature-mini-head">
      <div><h3>${title}</h3><p>${detail}</p></div><b class="breadth-status">${breadthLabel(data)}</b>
    </div>
    <div class="breadth-values">
      <span><b>${data.advancers.toLocaleString("ja-JP")}</b>値上がり</span>
      <span><b>${unchanged}</b>変わらず</span>
      <span><b>${data.decliners.toLocaleString("ja-JP")}</b>値下がり</span>
    </div>
    <div class="breadth-bar" aria-label="値上がり ${advPct.toFixed(0)}%、変わらず ${flatPct.toFixed(0)}%、値下がり ${decPct.toFixed(0)}%">
      <span class="breadth-up" style="width:${advPct}%"></span>
      <span class="breadth-flat" style="width:${flatPct}%"></span>
      <span class="breadth-down" style="width:${decPct}%"></span>
    </div>
    <div class="temperature-mini-foot"><b>騰落比 ${Number.isFinite(data.ratio) ? data.ratio.toFixed(2) : "－"}倍</b><span>基準 ${esc(dateToJp(data.asOf))}</span></div>
    <p class="temperature-source">${esc(data.source)}｜詳細は株式市場分析</p>
  </article>`;
}

function environmentVerdict(metrics, report) {
  const values = Object.fromEntries(metrics.map(({ definition, metric }) => [definition.id, metric.value]));
  const usable = Object.values(values).filter(Number.isFinite).length;
  if (usable < 3) {
    return {
      label: "判定保留",
      tone: "unknown",
      reason: `必須データ4項目中${usable}項目取得。欠損を推測で補いません。`
    };
  }
  let riskOn = 0;
  let riskOff = 0;
  if (Number.isFinite(values["market.vix"])) {
    if (values["market.vix"] <= 20) riskOn++;
    if (values["market.vix"] >= 25) riskOff++;
  }
  if (Number.isFinite(values["market.nikkei_vi"])) {
    if (values["market.nikkei_vi"] <= 20) riskOn++;
    if (values["market.nikkei_vi"] >= 25) riskOff++;
  }
  for (const id of ["sentiment.cnn_fear_greed", "sentiment.crypto_fear_greed"]) {
    if (!Number.isFinite(values[id])) continue;
    if (values[id] >= 56) riskOn++;
    if (values[id] <= 44) riskOff++;
  }
  if (riskOff >= 3) return { label: "リスクオフ", tone: "extreme-fear", reason: "複数の心理・ボラティリティ指標が警戒方向で一致しています。" };
  if (riskOff >= 2) return { label: "警戒", tone: "fear", reason: "複数指標に警戒が見られます。専門ページの根拠を確認してください。" };
  if (riskOn >= 3) return { label: "ややリスクオン", tone: "greed", reason: "株式・暗号資産の心理とボラティリティはおおむね良好です。" };
  return { label: "中立", tone: "neutral", reason: "指標の方向が分かれており、一方向の判断は避けます。" };
}

function renderEnvironmentSummary(report, metrics) {
  const container = $("environmentSummary");
  if (!container) return;
  const verdict = environmentVerdict(metrics, report);
  const available = metrics.filter(({ metric }) => Number.isFinite(metric.value));
  const views = available.slice(0, 3).map(({ definition, metric }) => `${definition.label}は${metric.label}`);
  const crypto = metrics.find(({ definition }) => definition.id === "sentiment.crypto_fear_greed")?.metric;
  if (Number.isFinite(crypto?.value) && (crypto.value <= 24 || crypto.value >= 75)) {
    views.push(`暗号資産心理は${crypto.value >= 75 ? "過熱" : "強い恐怖"}に注意`);
  }
  const conditions = [
    "VIXまたは日経VIが次の警戒帯へ移る",
    "株式の値上がり・値下がり優勢が反転する",
    "Crypto Fear & Greedが極端な恐怖・強欲へ入る"
  ];
  container.innerHTML = `<article class="environment-verdict tone-${verdict.tone}">
      <span>総合判定</span><strong>${esc(verdict.label)}</strong><p>${esc(verdict.reason)}</p>
    </article>
    <article class="environment-note"><h3>今日の見方</h3><ul>${(views.length ? views : ["取得済み指標が不足しています"]).map((item) => `<li>${esc(item)}</li>`).join("")}</ul></article>
    <article class="environment-note"><h3>判定が変わる条件</h3><ul>${conditions.map((item) => `<li>${esc(item)}</li>`).join("")}</ul></article>`;
}

function renderTemperatureMini(report) {
  const container = $("temperatureMiniCards");
  if (!container) return;
  const metrics = TEMPERATURE_MINI_DEFINITIONS.map((definition) => ({
    definition,
    metric: temperatureValueFromReport(report, definition)
  }));
  const cards = metrics.map(({ definition, metric }) => {
    const pct = temperaturePercent(metric.value, definition);
    const tone = temperatureTone(metric.value, definition);
    const valueText = Number.isFinite(metric.value)
      ? metric.value.toLocaleString("ja-JP", { maximumFractionDigits: metric.value >= 10 ? 1 : 2 })
      : "未取得";
    const title = Number.isFinite(metric.value)
      ? `${definition.label}: ${valueText} / ${metric.label}`
      : `${definition.label}: ${metric.label}`;
    const rangeItems = definition.ranges.map((item) => `<span class="temperature-range-chip range-${item.tone}">
      <b>${esc(item.range)}</b>${esc(item.label)}
    </span>`).join("");
    const changeText = Number.isFinite(metric.change)
      ? `前日から${metric.change > 0 ? "+" : ""}${metric.change.toLocaleString("ja-JP", { maximumFractionDigits: 1 })}`
      : "前日変化：取得不能";
    const basisText = metric.asOf ? `基準 ${shortDateTime(metric.asOf)}` : "基準日時：取得不能";
    return `<article class="temperature-mini-card temperature-${definition.accent} temperature-tone-${tone}" title="${esc(title)}">
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
        <span>${esc(changeText)}</span>
      </div>
      <p class="temperature-source">${esc(basisText)}｜${esc(metric.note || "取得元未確認")}</p>
      <div class="temperature-card-ranges" aria-label="${esc(definition.label)}の判定レンジ">
        ${rangeItems}
      </div>
    </article>`;
  });
  const breadthCards = [renderBreadthCard("us", report), renderBreadthCard("japan", report)];
  container.innerHTML = [...cards, ...breadthCards].join("");
  renderEnvironmentSummary(report, metrics);
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
  const verifiedMetric = metricFromMarketData(report, definition);
  if (verifiedMetric) return verifiedMetric;

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
  const market = reportMarket(report, definition);
  if (isUsableMarketText(market?.outlook, definition)) {
    return cleanText(market.outlook, 160);
  }

  const text = allText(report);
  const sectionLabels = ["6市場の見通し", "個別市場の見通し", "個別市場見通し", "個別見通し"];
  const starts = sectionLabels.map((label) => text.indexOf(label)).filter((index) => index >= 0);
  const start = starts.length ? Math.min(...starts) : -1;
  const scoped = start >= 0 ? text.slice(start, start + 1800) : text;
  const aliases = {
    gold: ["金", "ゴールド", "XAU/USD"],
    oil: ["WTI", "WTI原油", "原油"],
    nikkei: ["日経225先物", "日経225先物（大阪取引所）", "日経先物"],
    usdjpy: ["USD/JPY", "ドル円", "USDJPY"],
    eurusd: ["EUR/USD", "ユーロドル", "EURUSD"],
    btc: ["BTCUSD", "BTC/USD", "BTC", "ビットコイン"]
  }[definition.key] || [];
  const labels = uniq([definition.label, definition.display, ...aliases]);

  for (const label of labels) {
    const index = scoped.indexOf(`${label}：`);
    if (index >= 0) {
      const after = scoped.slice(index + label.length + 1);
      const nextMarket = after.search(/\s(?:金|ゴールド|WTI|WTI原油|原油|日経225先物|USD\/JPY|ドル円|EUR\/USD|ユーロドル|BTCUSD|BTC)：/);
      const segment = nextMarket >= 0 ? after.slice(0, nextMarket) : after;
      const sentences = segment.split(/。/).map((item) => item.trim()).filter(Boolean).slice(0, 2);
      if (sentences.length) return cleanText(`${sentences.join("。")}。`, 160);
    }
  }

  if (isUsableMarketText(market?.material, definition)) return cleanText(market.material, 140);
  return cleanText(market?.direction || "", 140);
}

function marketReason(report, definition, metric) {
  const market = reportMarket(report, definition);
  const direct = [market?.outlook, market?.material, market?.positioning].find((item) => (
    isUsableMarketText(item, definition) && item.length <= 150
  ));
  if (direct) return cleanText(direct, 150);
  const outlook = findOutlookSentence(report, definition);
  if (outlook) return outlook;
  if (metric.raw && metric.raw.length <= 180) return cleanText(metric.raw.replace(/^.*?：/, ""), 150);
  return cleanText(market?.material || "理由：本文に市場別理由がありません", 150);
}

function isUsableMarketText(value, definition) {
  const item = cleanText(value || "", 220);
  if (!item) return false;
  if (/^(本文参照|個別記載なし|個別見通し参照|記載なし)$/.test(item)) return false;
  if (/^対象\s*[：:]/.test(item)) return false;
  if (/前営業日終値|主要市場データ|Dow：|VIX：|Fear & Greed/.test(item)) return false;
  const mentioned = mentionedMarketsInDashboardText(item);
  if (mentioned.length >= 3) return false;
  if (mentioned.length && !mentioned.includes(definition.key)) return false;
  return true;
}

function mentionedMarketsInDashboardText(value) {
  const text = String(value || "");
  const groups = {
    gold: ["金", "ゴールド", "XAU/USD", "XAUUSD"],
    oil: ["WTI原油", "原油", "WTI", "Brent", "ブレント"],
    nikkei: ["日経225先物", "日経先物", "日経平均"],
    usdjpy: ["USD/JPY", "USDJPY", "ドル円"],
    eurusd: ["EUR/USD", "EURUSD", "ユーロドル"],
    btc: ["BTCUSD", "BTC/USD", "BTC", "ビットコイン"]
  };
  return Object.entries(groups)
    .filter(([, aliases]) => aliases.some((alias) => dashboardAliasMentioned(text, alias)))
    .map(([key]) => key);
}

function dashboardAliasMentioned(value, alias) {
  if (alias === "金") {
    let index = value.indexOf("金");
    while (index >= 0) {
      const previous = value[index - 1] || "";
      const next = value[index + 1] || "";
      if (!/[米資]/.test(previous) && next !== "利") return true;
      index = value.indexOf("金", index + 1);
    }
    return false;
  }
  return new RegExp(escapeFlowRegex_(alias), "i").test(value);
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
  // The market cards already grow with their content. Keep the complete
  // consistency explanation instead of adding a misleading "..." suffix.
  return { verdict, cls, reason: cleanText(text, Infinity) };
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

function hasCurrentReportEvent(report, pattern) {
  const eventText = asArray(report.events).map(textOf).join(" ");
  return pattern.test(eventText);
}

function hasUnconfirmedBojTimingText(report, text) {
  if (!/日銀.{0,18}(?:会合|決定会合).{0,12}(?:前|後)/.test(String(text || ""))) return false;
  return !hasCurrentReportEvent(report, /日銀|金融政策決定会合/);
}

function riskForMarket(report, definition) {
  const market = reportMarket(report, definition);
  const raw = market?.risk || market?.breakCondition || "";
  const usable = raw
    && raw.length < 170
    && !/個別見通し|ヘッダーなし|TSV|マーケットレポート/.test(raw)
    && !hasUnconfirmedBojTimingText(report, raw);
  if (usable) return cleanText(raw, 110);
  const text = allText(report);
  const rules = {
    gold: /米10年債|金利/.test(text) ? "米金利上昇・ドル高" : "金利材料の急変",
    oil: /82ドル割れ/.test(text) ? "82ドル割れで短期ロング解消" : "在庫・地政学材料の反転",
    nikkei: /61,900/.test(text) ? "61,900円割れ・円急騰" : "米株安と円高の同時進行",
    usdjpy: /163.20/.test(text) ? "163.20円割れ・円急騰" : "米金利急低下・円買い戻し",
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
    .map((item) => cleanText(item.replace(/^[・\-\s]+/, ""), Infinity))
    .filter((item) => item.length >= 10);
}

function fallbackNewsItems(report) {
  const explicit = uniq(
    asArray(report.news)
      .map(textOf)
      .filter(Boolean)
      .flatMap(splitNewsSentences)
  ).slice(0, 5);
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

  return uniq(candidates).slice(0, 5).map((item) => cleanText(item, Infinity));
}

function handoverSectionLines(fullText = "") {
  const lines = String(fullText || "")
    .split(/\n+/)
    .map((line) => cleanText(line.replace(/^[・\-\s]+/, ""), Infinity))
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

  return found.flatMap(splitNewsSentences).map((item) => cleanText(item, Infinity)).filter(Boolean);
}

function fallbackHandoverItems(report) {
  const explicit = topList(report.handover, 3, Infinity);
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

  return uniq(candidates).slice(0, 3).map((item) => cleanText(item, Infinity));
}

function renderList(id, values, fallback) {
  const rows = values.length ? values : [fallback];
  $(id).innerHTML = rows.map((item) => `<li>${esc(item)}</li>`).join("");
}


/* Historical archive is display-only and never passes formal publication gates. */
function isDashboardHistoricalArchive(r) {
  if (!r || r.archiveStatus !== "HISTORICAL_ARCHIVE" || r.verifiedAtSlot !== false) return false;
  if (!/^\d{4}-\d{2}-\d{2}$/.test(String(r.date || "")) || !REPORT_TIMES.includes(r.time)) return false;
  if (typeof r.fullText !== "string" || r.fullText.length < 250) return false;
  if (!String(r.title || "").startsWith("マーケットレポート｜") || !r.fullText.replace(/^#{1,3}\s+/, "").startsWith(r.title)) return false;
  if (!r.title.includes(r.date.replace(/-/g, "/")) || !r.title.endsWith(r.time)) return false;
  if (typeof r.archiveNotice !== "string" || r.archiveNotice.length < 15) return false;
  if (r.originalReportStatus === "PUBLISHED" || r.report_status === "PUBLISHED") return false;
  const legacyOriginal = /^[a-f0-9]{64}$/.test(String(r.originalBodyHash || "")) && !!r.sourceDocument?.id;
  const sourceDocReadback = ["DRIVE_SAVED_DOCUMENT", "DRIVE_RECOVERY_DOCUMENT"].includes(r.archiveType)
    && r.originalReportStatus === "DRIVE_DOC_READBACK_NOT_SLOT_VERIFIED"
    && !!r.sourceDocument?.id && !!r.driveRevisionId && r.driveTextLength === r.fullText.length
    && Array.isArray(r.missingAtSlotEvidence) && r.missingAtSlotEvidence.length > 0;
  const reconstructed = ["ORIGINAL_NOT_FOUND", "RECONSTRUCTED_UNVERIFIED"].includes(r.originalReportStatus)
    && ["PARTIAL_ORIGINAL_WITH_RETROSPECTIVE_ADDENDUM", "RECONSTRUCTED_SOURCE", "RETROSPECTIVE_REPORT"].includes(r.archiveType)
    && !r.sourceDocument?.id && typeof r.archiveSource === "string" && r.archiveSource.length > 10
    && r.missingAtSlotEvidence === true;
  return legacyOriginal || sourceDocReadback || reconstructed;
}
function isDashboardReconstructedArchive(r) {
  return ["ORIGINAL_NOT_FOUND", "RECONSTRUCTED_UNVERIFIED"].includes(r?.originalReportStatus);
}

function archiveSectionBody(report, pattern) {
  const lines = String(report.fullText || "").replace(/\r/g, "").split("\n");
  const header = line => {
    const m=String(line||"").trim().match(/^(?:\d{1,2}(?:補)?[．.]\s*|#{1,4}\s*|【)(.+?)(?:】)?$/);
    if (m) {
      const title=m[1].replace(/】$/, "").trim();
      // Bracketed column headers inside a numbered market-data section are data,
      // not new sections. Do not truncate the 08:00 previous-close table.
      if (/^【/.test(String(line||"").trim())
          && !/^(?:総合判断|今日の相場テーマ|前回からの変化|主要市場データ|主要市場の現状|材料と値動きの整合性|今日の主導市場|重要ニュース|重要ニュース・材料|クロスアセット資金フロー|需給・ポジション|今後のイベント|主要6市場の短期見通し|6市場の短期見通し|メインシナリオ|代替シナリオ|シナリオが崩れる条件|次の時間帯への引き継ぎ|08:00からの変化|16:00からの変化)$/.test(title)) return "";
      return title;
    }
    const bare=String(line||"").trim();
    if (/^(?:総合判断|主要市場データ|今日の相場テーマ|前回からの変化|市場別価格・見通し.*|クロスアセット資金フロー|需給・ポジション|重要ニュース|材料と値動きの整合性|今日の主導市場|メインシナリオ|代替シナリオ|崩れる条件|次の時間帯への引き継ぎ|NY市場の流れ)$/.test(bare)) return bare;
    return "";
  };
  const at = lines.findIndex(line => {
    const title=header(line);
    return title && pattern.test(title);
  });
  if (at < 0) return "";
  let end = lines.findIndex((line,i) => i>at && header(line));
  if (end < 0) end = lines.length;
  // A '【総合判断】...' paragraph may include its explanation on the heading line.
  const line=lines[at].trim(),inline=line.match(/^【[^】]+】\s*(.+)$/)?.[1]||"";
  return [inline,...lines.slice(at+1,end)].filter(Boolean).join("\n").trim();
}


/*
 * Strict per-asset extraction from a late-saved, read-back morning report.
 * Not a publication gate: values remain historical references, NEVER live
 * snapshots. Scope to the exact supplemental document to avoid changing
 * the existing archives' different (often incomplete) source formats.
 */
function verifiedSupplementalArchiveQuotes(record) {
  if (record?.date !== "2026-10-16" || record?.time !== "08:00"
      || record?.archiveType !== "DRIVE_SAVED_DOCUMENT"
      || record?.originalReportStatus !== "DRIVE_DOC_READBACK_NOT_SLOT_VERIFIED"
      || record?.verifiedAtSlot !== false
      || record?.sourceDocument?.id !== "1JBfE0AsvW5Ob_nA2lKDTLFAlYMhc8XbhasqwQ4oixdw") return null;
  const body = String(record.fullText || "").replace(/\r/g, "");
  const priceSection = body.match(/【2[.．]\s*前営業日終値・市場データ】([\s\S]*?)(?=\n【3[.．]|$)/)?.[1] || "";
  const outlookSection = body.match(/【6[.．]\s*主要6市場の短期見通し[^】]*】([\s\S]*?)(?=\n【7[.．]|$)/)?.[1] || "";
  if (!priceSection || !outlookSection) return null;
  const config = {
    gold: {
      line: /^商品（10\/15NY終値）：COMEX金12月限([\d,]+(?:\.\d+)?)ドル（([+-][\d,]+(?:\.\d+)?)ドル）[^\n]*$/m,
      marketName: "金先物（COMEX 12月限）", sourceLabel: "10/15 NY終値・COMEX金12月限",
      outlook: /^金：[^\n]+$/m, low: 2500, high: 10000
    },
    oil: {
      line: /^商品（10\/15NY終値）：[^\n]*WTI11月限([\d,]+(?:\.\d+)?)ドル（([+-][\d,]+(?:\.\d+)?)ドル）[^\n]*$/m,
      marketName: "WTI原油先物（11月限）", sourceLabel: "10/15 NY終値・WTI11月限",
      outlook: /^WTI：[^\n]+$/m, low: 30, high: 300
    },
    nikkei: {
      line: /^大阪日経225先物（2026年12月限）：[^\n]*10\/16 06:00夜間終値([\d,]+)円（前日清算値比([+-][\d,]+)円、([+-][\d.]+)%）[^\n]*$/m,
      marketName: "日経225先物（大阪・夜間）", sourceLabel: "10/16 06:00夜間終値・OSE12月限",
      outlook: /^大阪日経225先物：[^\n]+$/m, low: 30000, high: 120000
    },
    usdjpy: {
      line: /^為替（10\/15NY終値）：USD\/JPY\s*([\d,]+(?:\.\d+)?)円（([+-][\d,]+(?:\.\d+)?)円）[^\n]*$/m,
      marketName: "USD/JPY", sourceLabel: "10/15 NY終値・USD/JPY",
      outlook: /^USD\/JPY：[^\n]+$/m, low: 90, high: 220
    },
    eurusd: {
      line: /^為替（10\/15NY終値）：[^\n]*EUR\/USD\s*([\d,]+(?:\.\d+)?)ドル（([+-][\d,]+(?:\.\d+)?)）[^\n]*$/m,
      marketName: "EUR/USD", sourceLabel: "10/15 NY終値・EUR/USD",
      outlook: /^EUR\/USD：[^\n]+$/m, low: 0.7, high: 1.8
    },
    btc: {
      line: /^BTC\/USD：10\/16 07:33頃の参考値([\d,]+(?:\.\d+)?)ドル[^\n]*$/m,
      marketName: "BTC/USD（07:33参考）", sourceLabel: "10/16 07:33頃の参考値・BTC/USD（終値ではない）",
      outlook: /^BTC\/USD：[^\n]+$/m, low: 15000, high: 300000
    }
  };
  const quotes = {};
  for (const [key, spec] of Object.entries(config)) {
    const line = priceSection.match(spec.line);
    const outlook = outlookSection.match(spec.outlook)?.[0] || "";
    if (!line || !outlook) continue;
    const price = Number(line[1].replace(/,/g, ""));
    const change = line[2] === undefined ? null : Number(line[2].replace(/,/g, ""));
    if (!Number.isFinite(price) || price < spec.low || price > spec.high
        || (change !== null && (!Number.isFinite(change) || Math.abs(change) > price * 0.5))) continue;
    // Direction is driven exclusively by measured change, not a forecast.
    const changePct = key === "nikkei" ? Number(line[3]) : null;
    const clauses = outlook.replace(/^[^：:]+[：:]/, "").split("。").map(s=>s.trim()).filter(Boolean);
    const reason = clauses.find(s=>/短期は|上昇警戒|自律反発|金利|ドル安|買い材料|反発は確認/.test(s) && !/強気条件|弱気条件/.test(s)) || "";
    // A saved sentence may contain both "強気条件＝..." and "弱気条件＝..."
    // separated only by a Japanese comma (BTC has this format).
    const conditions = outlook
      .replace(/、(?=(?:強気条件|弱気条件|ドル高条件|ドル安条件)＝)/g, "。")
      .split("。").map(s=>s.trim()).filter(Boolean);
    const strong = conditions.find(s=>/^(?:強気条件|ドル高条件)＝/.test(s)) || "";
    const weak = conditions.find(s=>/^(?:弱気条件|ドル安条件)＝/.test(s)) || "";
    quotes[key] = {
      value: line[1],
      change, changePct: Number.isFinite(changePct) ? changePct : null,
      originalLine: line[0], sourceLabel: spec.sourceLabel,
      marketName: spec.marketName, sourceKind: "SUPPLEMENTAL_DOC_LINE",
      observedAt: spec.sourceLabel, reason, keyPoint: strong,
      risk: weak, outlook,
      direction: change === null ? "比較基準未確認" : change > 0 ? "前日比上昇" : change < 0 ? "前日比下落" : "前日比横ばい"
    };
  }
  return quotes;
}

function archiveDashboardSummary(record) {
  const section = pattern => archiveSectionBody(record, pattern);
  const split = text => String(text || "").split("\n").map(s => s.trim()).filter(Boolean);
  const summary = section(/総合判断|今日の相場テーマ/);
  const timeline = section(/時系列/);
  const mainPrices = section(/前営業日終値・主要市場データ|主要市場データ/);
  const outlook = section(/主要6市場の短期見通し|6市場の個別見通し|主要6市場の|主要6市場の短期|個別6市場の/);
  const wholeText=String(record.fullText||"").replace(/\r/g,"");
  const blockByAsset = label => {
    const lines=wholeText.split("\n");
    const i=lines.findIndex(v=>v.trim()==="【"+label+"】");
    if(i<0)return "";
    let end=lines.findIndex((v,j)=>j>i && (/^【[^】]+】/.test(v.trim())||v.trim()==="主要市場データ"));
    return lines.slice(i+1,end<0?lines.length:end).join("\n");
  };
  const specificBlockLabels={gold:"金",oil:"原油",nikkei:"日経225先物",usdjpy:"USD/JPY",eurusd:"EUR/USD",btc:"BTCUSD"};
  const extractBlockPrice = (block,label) => {
    const p=block.match(/^価格[：:]\s*(.+)$/m)?.[1]||"";
    const m=p.match(/([\d,]+(?:\.\d+)?)(?=\s*(?:USD|円|ドル|（|\())/);
    if(!m)return null;
    const prev=block.match(/^前日比[：:]\s*(.+)$/m)?.[1]||"";
    return {value:m[1],line:label+"： "+p,previous:prev,outlook:block.match(/^メインシナリオ[：:]\s*(.+)$/m)?.[1]||block.match(/^材料[：:]\s*(.+)$/m)?.[1]||""};
  };
  const fallbackQuote = (key) => {
    const patterns={
      gold:/^(?:金(?:スポット|現物|先物)?|COMEX金先物|ゴールド)[：:]\s*(?:現物金\s*)?(?:約\s*)?([\d,]+(?:\.\d+)?)/m,
      oil:/^(?:WTI原油(?:先物)?|WTI|原油)[：:]\s*(?:約\s*)?([\d,]+(?:\.\d+)?)/m,
      nikkei:/^(?:日経225先物(?:（[^）]+）)?|大阪日経225先物(?:12月限)?|日経先物)[：:]\s*(?:約\s*)?([\d,]+(?:\.\d+)?)/m,
      usdjpy:/^USD\/JPY[：:]\s*(?:約\s*)?([\d,]+(?:\.\d+)?)/m,
      eurusd:/^EUR\/USD[：:]\s*(?:約\s*)?([\d,]+(?:\.\d+)?)/m,
      btc:/^BTCUSD[：:]\s*(?:約\s*)?([\d,]+(?:\.\d+)?)/m
    };
    const found=patterns[key]?.exec(wholeText);
    if(found)return {value:found[1],line:wholeText.slice(found.index,found.index+230).split("\n")[0].slice(0,210)};
    // Numbered five-column morning closes: label on one line, value on next.
    const re={
      gold:/^\d{1,2}[.．]\s*(?:COMEX金先物|金現物|金スポット)\s*$/m,
      oil:/^\d{1,2}[.．]\s*(?:WTI原油|WTI)\s*$/m,
      nikkei:/^\d{1,2}[.．]\s*日経225先物(?:（[^）]+）)?\s*$/m,
      usdjpy:/^\d{1,2}[.．]\s*USD\/JPY\s*$/m,
      eurusd:/^\d{1,2}[.．]\s*EUR\/USD\s*$/m,
      btc:/^\d{1,2}[.．]\s*BTCUSD\s*$/m
    };
    const five=re[key]?.exec(wholeText);
    if(five){
      const next=wholeText.slice(five.index+five[0].length).split("\n").map(v=>v.trim()).filter(Boolean)[0]||"";
      const val=next.match(/^(?:約\s*)?([\d,]+(?:\.\d+)?)/)?.[1];
      if(val && !/取得不能/.test(next))return {value:val,line:five[0]+"｜"+next};
    }
    return null;
  };
  const marketSpecs = [
    { key: "gold", name: "金", quote: /(?:金スポット|金先物GC=F)\s*[：:]?\s*(?:約\s*)?([\d,]+(?:\.\d+)?)/, outlook: /^(?:金(?:（XAU\/USD）)?)[：:]\s*(.+)$/m },
    { key: "oil", name: "原油", quote: /(?:WTI原油先物CL=F|WTI原油|WTI)\s*[：:]?\s*([\d,]+(?:\.\d+)?)/, outlook: /^WTI(?:原油)?[：:]\s*(.+)$/m },
    { key: "nikkei", name: "日経225先物", quote: /(?:大阪日経225先物12月限(?:・夜間終値)?|日経225先物（大阪取引所(?:・12月限)?）)\s*[：:]?\s*([\d,]+(?:\.\d+)?)/, outlook: /^日経225先物（大阪(?:取引所)?）[：:]\s*(.+)$/m },
    { key: "usdjpy", name: "USD/JPY", quote: /USD\/JPY\s*[：:]?\s*([\d,]+(?:\.\d+)?)/, outlook: /^USD\/JPY[：:]\s*(.+)$/m },
    { key: "eurusd", name: "EUR/USD", quote: /EUR\/USD\s*[：:]?\s*([\d,]+(?:\.\d+)?)/, outlook: /^EUR\/USD[：:]\s*(.+)$/m },
    { key: "btc", name: "BTCUSD", quote: /BTCUSD\s*[：:]?\s*(?:約\s*)?([\d,]+(?:\.\d+)?)/, outlook: /^BTCUSD[：:]\s*(.+)$/m }
  ];
  const archiveQuotes = {};
  const markets = [];
  for (const spec of marketSpecs) {
    const blocked=isDashboardReconstructedArchive(record);
    const m=blocked ? null : spec.quote.exec(mainPrices);
    const block=blocked ? "" : blockByAsset(specificBlockLabels[spec.key]||"");
    const fromBlock=blocked ? null : extractBlockPrice(block,spec.name);
    const direct=blocked ? null : fallbackQuote(spec.key);
    const raw = blocked ? "原本欠損（事後再分析版：定時の確定価格なし）"
      : m ? mainPrices.slice(m.index, m.index + 260).split(/[。\n]/)[0].trim()
      : fromBlock?.line || direct?.line || "";
    const outlookLine = outlook.match(spec.outlook)?.[1] || fromBlock?.outlook || "";
    const changePair = raw.match(/([+-]\d[\d,.]*)\s*(?:円|ドル|USD)?\s*[,、/]\s*([+-]\d[\d,.]*)\s*%/);
    const pct = changePair ? Number(changePair[2].replace(/,/g, "")) : null;
    const pctOnly = !changePair && raw.match(/([+-]\d+(?:\.\d+)?)\s*%/) || (!changePair && fromBlock?.previous.match(/([+-]\d+(?:\.\d+)?)\s*%/));
    // Missing current-session quotes remain labeled as historical references.
    const atSource = raw.match(/(?:10\/\d{1,2}[^）]{0,55}|\b\d{1,2}:\d{2}[^）]{0,35})/);
    const observedAt = atSource ? atSource[0].slice(0, 56) : "原本の基準時刻を確認";
    const candidate = blocked ? null : m?.[1] || fromBlock?.value || direct?.value || null;
    const numeric = candidate === null ? null : Number(String(candidate).replace(/,/g, ""));
    const allowed = {
      gold: [2500, 10000], oil: [30, 300], nikkei: [30000, 120000],
      usdjpy: [90, 220], eurusd: [0.7, 1.8], btc: [15000, 300000]
    }[spec.key];
    // Reject numbers from clock times, dates, ordinal headings, or a different asset.
    const value = Number.isFinite(numeric) && allowed && numeric >= allowed[0] && numeric <= allowed[1]
      ? candidate : null;
    const outlookDesc = String(outlookLine).trim();
    archiveQuotes[spec.key] = {
      value, observedAt,
      originalLine: value ? raw : "取得不能（原本に対応する市場の価格がないか、数値形式を安全に解釈できないため）",
      change: value && changePair ? Number(changePair[1].replace(/,/g, "")) : null,
      changePct: !value ? null : pct !== null ? pct : pctOnly ? Number(pctOnly[1]) : null,
      outlook: outlookDesc
    };
    markets.push({
      name: spec.name,
      price: raw || "取得不能（当該資料に価格欄なし）",
      direction: outlookDesc.split("。")[0] || "方向判断は保存原本参照",
      outlook: outlookDesc,
      material: outlookDesc,
      risk: outlookDesc
    });
  }
  const confirmedSupplementalQuotes = verifiedSupplementalArchiveQuotes(record);
  if (confirmedSupplementalQuotes) Object.assign(archiveQuotes, confirmedSupplementalQuotes);
  // Prefer slot-bound market facts attached to the saved body. The archive is
  // historical/display-only, so never synthesize them from live market data.
  const bodyMarketKeys = {
    gold: "gold", oil: "wti", nikkei: "nikkei225_futures_ose",
    usdjpy: "usdjpy", eurusd: "eurusd", btc: "btcusd"
  };
  if (!isDashboardReconstructedArchive(record) && record.marketData?.markets) {
    for (const [key, dataKey] of Object.entries(bodyMarketKeys)) {
      const item = record.marketData.markets[dataKey];
      if (!item || !["verified", "reference", "unavailable", "conflict"].includes(item.verificationStatus)) continue;
      const stateLabel = item.verificationStatus === "reference" ? "参考値"
        : item.verificationStatus === "verified" ? "確認済み"
          : item.verificationStatus === "conflict" ? "数値矛盾・照合保留" : "取得不能";
      const value = Number.isFinite(Number(item.value)) ? Number(item.value) : null;
      const name = item.displayName || ({gold:"金",oil:"原油",nikkei:"日経225先物",usdjpy:"USD/JPY",eurusd:"EUR/USD",btc:"BTCUSD"}[key]);
      const observedAt = String(item.observationTimeJst || item.asOf || "観測時刻不明");
      const sourceName = String(item.sourceName || "本文内で取得元未特定");
      const priceType = String(item.priceType || item.marketType || "価格種別本文参照");
      const displayValue = String(item.displayValue || (value === null ? "" : value));
      const originalLine = item.verificationStatus === "conflict" ? "同一条件の価格に矛盾。照合保留。"
        : item.verificationStatus === "unavailable" ? "本文に採用可能な確認値なし。"
          : `${stateLabel}：${priceType} ${displayValue}${item.unit ? ` ${item.unit}` : ""}｜観測：${observedAt}｜出典：${sourceName}`;
      archiveQuotes[key] = {
        value: ["unavailable", "conflict"].includes(item.verificationStatus) ? null : value,
        displayValue: item.displayValue || null,
        change: Number.isFinite(item.change) ? item.change : null,
        changePct: Number.isFinite(item.changePercent) ? item.changePercent : null,
        changeText: String(item.changeText || ""), observedAt, priceType,
        contractMonth: String(item.contractMonth || ""), sourceName,
        verificationStatus: item.verificationStatus, originalLine,
        sourceKind: "BODY_MARKET_DATA", marketName: String(name),
        direction: String(item.direction || "不明"), outlook: String(item.outlook || ""),
        material: String(item.material || ""), levels: String(item.levels || ""), risk: String(item.risk || "")
      };
    }
  }
  const explicitRows = Array.isArray(record.archiveTimelineRows) ? record.archiveTimelineRows : [];
  const timelineRows = explicitRows.length ? explicitRows.filter(row => row && typeof row.text === "string" && row.text.trim())
    .slice(0, 20).map(row => ({
      time: String(row.time || "時間帯"), text: String(row.text),
      reaction: String(row.reaction || ""), region: String(row.region || "当時の市場"),
      importance: String(row.importance || "出来事"), next: String(row.next || "保存本文の時系列")
    })) : split(timeline)
    .filter(s => s.includes("｜出来事：") && /株|市場|金利|発表|決算|取引|先物|ニュース/.test(s))
    .slice(0, 12)
    .map(s => ({ time: s.match(/\b[0-2]?\d:[0-5]\d\b/)?.[0] || "時間帯", text: s }));
  const originalNews = split(section(/重要ニュース|ニュースと影響市場|ニュースと波及/));
  const news = originalNews.length ? originalNews : timelineRows.slice(0, 4).map(r => r.text);
  const main = section(/メインシナリオ/);
  const scenarios = section(/メイン・代替シナリオ/);
  const adapted = {
    ...record,
    // A record in this state is NEVER treated as officially published.
    report_status: "HISTORICAL_ARCHIVE_DISPLAY_ONLY",
    historicalArchiveDisplayOnly: true,
    archiveQuotes,
    archiveTimelineRows: timelineRows,
    markets,
    theme: (split(summary).slice(0, 3).join(" ") || split(section(/今日の相場テーマ/)).slice(0, 3).join(" ") || split(wholeText).slice(1, 4).filter(v=>!/^(?:作成|復旧作成|対象時点|情報基準|保存復旧|復旧版)/.test(v)).join(" ")).slice(0, 560),
    changes: record.time === "12:00"
      ? split(summary).slice(0, 2)
      : split(section(/版からの変化|からの変化/)).slice(0, 5),
    consistency: split(section(/材料と値動きの整合性/)).slice(0, 5),
    leadingMarket: split(section(/主導市場・クロスアセット|材料と値動きの整合性・主導市場|今日の主導市場/)).slice(0, 3).join(" ") || split(summary)[0] || "",
    crossAssetFlow: split(section(/クロスアセット資金フロー|主導市場・クロスアセット/)).slice(0, 6),
    news,
    positioning: split(section(/需給・ポジション/)).slice(0, 6),
    mainScenario: split(main || scenarios).slice(0, 5).join(" "),
    alternativeScenario: split(section(/代替シナリオ/) || scenarios).slice(0, 5).join(" "),
    breakConditions: split(section(/崩れる条件/)).slice(0, 5).join(" "),
    riskManagement: split(section(/リスク管理|崩れる条件/)).slice(0, 5),
    handover: split(section(/引き継ぎ/)).slice(0, 5)
  };

  // The Oct 19 documents were read back from the owner's October Drive folder.
  // Render their contents in existing dashboard cards/date slots, never as formal
  // publication and never by inheriting current-day or different-slot quotes.
  if (record.date === "2026-10-19" &&
      record.archiveType === "DRIVE_SAVED_DOCUMENT" &&
      record.originalReportStatus === "DRIVE_DOC_READBACK_NOT_SLOT_VERIFIED" &&
      record.sourceDocument?.id &&
      record.verifiedAtSlot === false &&
      record.archiveDashboardFields &&
      typeof record.archiveDashboardFields === "object") {
    const details = record.archiveDashboardFields;
    const summaryStrings = ["theme", "leadingMarket", "mainScenario", "alternativeScenario", "breakConditions"];
    const summaryArrays = ["changes", "consistency", "crossAssetFlow", "news", "positioning", "handover"];
    for (const key of summaryStrings) {
      if (typeof details[key] === "string" && details[key].trim()) adapted[key] = details[key];
    }
    for (const key of summaryArrays) {
      if (Array.isArray(details[key]) && details[key].every(v => typeof v === "string"))
        adapted[key] = details[key].filter(Boolean).slice(0, 12);
    }
    // A per-asset reference is displayable only if the corresponding market
    // statement is actually present in the saved Google Doc, or is explicitly
    // a missing value. Never derive sign from the forecast/outlook text.
    const specs = [
      ["gold", "金"], ["oil", "原油"], ["nikkei", "日経225先物"],
      ["usdjpy", "USD/JPY"], ["eurusd", "EUR/USD"], ["btc", "BTCUSD"]
    ];
    const marketRecords = [];
    for (const [key, name] of specs) {
      const quote = details.archiveReferenceQuotes?.[key];
      if (!quote || typeof quote !== "object") continue;
      const referenceLine = String(quote.originalLine || "").trim();
      const numeric = quote.value == null ? null : Number(String(quote.value).replace(/,/g, ""));
      if (!referenceLine || (numeric !== null && !Number.isFinite(numeric))) continue;
      if (numeric !== null && !record.fullText.includes(referenceLine)) continue;
      // For a missing value, display the missing status, never a numeric estimate.
      const safeQuote = {
        ...quote,
        value: numeric === null ? null : quote.value,
        change: Number.isFinite(quote.change) ? quote.change : null,
        changePct: Number.isFinite(quote.changePct) ? quote.changePct : null,
        originalLine: numeric === null && !record.fullText.includes(referenceLine)
          ? "取得不能（保存した本文に当該時刻の確定値なし）" : referenceLine,
        sourceKind: "SUPPLEMENTAL_DOC_LINE",
        sourceLabel: String(quote.sourceLabel || "保存本文の時刻付き参考値"),
        marketName: String(quote.marketName || name)
      };
      adapted.archiveQuotes[key] = safeQuote;
      marketRecords.push({
        name,
        price: safeQuote.originalLine,
        direction: String(safeQuote.direction || "方向確認できず"),
        outlook: String(safeQuote.outlook || ""),
        material: String(safeQuote.reason || ""),
        levels: String(safeQuote.keyPoint || ""),
        risk: String(safeQuote.risk || "")
      });
    }
    if (marketRecords.length === 6) adapted.markets = marketRecords;
  }
  return adapted;
}
function renderDashboardArchive(report) {
  // No extra box: historical report contents are presented in the normal
  // dashboard cards, news/event table, flows, positioning and scenarios.
  document.getElementById("historicalArchiveDetails")?.remove();
}

function renderHeader(report) {
  const created = `${dateToJp(report.date)} ${report.time || ""}`.trim();
  const generated = dashboardMeta && dashboardMeta.generatedAt
    ? dashboardMeta.generatedAt.replace("T", " ").replace("+09:00", "")
    : report.time || "取得不能";
  $("reportStatus").textContent = isDashboardHistoricalArchive(report)
    ? `保存済み本文（正式発行と区別）：${created}　｜　事後改訂あり`
    : `作成日時：${created}　更新：${generated}`;
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
        ${metric.sourceNote ? `<p class="market-source-line ${esc(metric.sourceClass || "")}">${esc(metric.sourceNote)}</p>` : ""}
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
      return { direction: "流入", strength: "やや強い", compare: "強化", reason: "円買い戻し・金利差縮小警戒", basis: "本文から推定", trend: "up" };
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
      const hasResult = Boolean(event.actual || event.resultComparison || event.status === "released");
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
  const hasResult = Boolean(row.actual || row.resultComparison || row.status === "released");
  const forecast = row.forecast && !/手入力待ち|未取得|該当なし/.test(row.forecast) ? `予想 ${row.forecast}` : "";
  const previous = row.previous && !/手入力待ち|未取得|該当なし/.test(row.previous) ? `前回 ${row.previous}` : "";
  const parts = [
    forecast,
    previous,
    row.actual ? `結果 ${row.actual}` : "",
    row.resultComparison ? `比較 ${row.resultComparison}` : "",
    hasResult && row.resultExplanation ? `説明 ${row.resultExplanation}` : "",
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
  if (row.status === "released" || row.actual || row.resultComparison) return "結果保存";
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
  const eventPanelHeading = document.querySelector(".event-panel .section-title-row h2");
  if (eventPanelHeading) eventPanelHeading.textContent = report?.historicalArchiveDisplayOnly
    ? "当日の市場時系列（実際に起きた出来事と市場反応）"
    : "今後の重要イベント（簡易）";
  if (report?.historicalArchiveDisplayOnly) {
    const slot = String(report.date || "") + " " + String(report.time || "");
    const sourceRows = window.MarketReportArchiveTimelineBySlot?.[slot] || [];
    const rows = sourceRows.length ? sourceRows
      : (Array.isArray(report.archiveTimelineRows) ? report.archiveTimelineRows : []);
    $("eventRows").innerHTML = rows.length ? rows.map(row => `<tr><td>${esc(row.time)}</td><td><span class="event-title">${esc(row.text)}</span>${row.reaction ? `<div class="event-detail">市場反応：${esc(row.reaction)}</div>` : ""}</td><td>${esc(row.region || "当時の市場")}</td><td>${esc(row.importance || "出来事")}</td><td>${esc(row.next || "保存本文の時系列")}</td></tr>`).join("")
      : '<tr><td>取得不能</td><td>保存本文に時系列情報なし</td><td>—</td><td>—</td><td>—</td></tr>';
    return;
  }
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
  if (report?.historicalArchiveDisplayOnly) {
    const li = (pattern, fallback) => String(archiveSectionBody(report, pattern) || fallback).split("。").slice(0, 3);
    const quote = key => report.archiveQuotes?.[key]?.originalLine || "保存原本の記載なし";
    return [
      ["金利・債券市場", "%", li(/金利・為替・債券|金利・為替・株式/, "同時刻の金利観測値なし")],
      ["株式市場", "株", li(/市場内部|市場の広がり|材料と値動きの整合性/, "株式の値動きは原本参照")],
      ["商品市場（原油・金）", "CL", [quote("gold"), quote("oil")]],
      ["為替市場", "FX", [quote("usdjpy"), quote("eurusd")]],
      ["暗号資産市場", "BTC", [quote("btc")]],
      ["今日の注目ポイント", "P", report.handover?.slice(0, 3).length ? report.handover.slice(0, 3) : ["次時間帯への引き継ぎは保存本文参照"]]
    ];
  }
  const text = allText(report);
  const metricLine = (pattern) => sourceLines(report).find((line) => pattern.test(line));
  const usRate = metricLine(/米10年債利回り/);
  const jpRate = metricLine(/日本10年債利回り/);
  const stock = topList(report.consistency, 1, 90)[0] || "株式市場の詳細は株式市場分析ページで確認";
  const commodity = topList(report.crossAssetFlow, 2, 90).find((line) => /金|原油|WTI/.test(line)) || "商品市場の方向は金・原油カードで確認";
  const fx = /ドル全面高にはなっておらず/.test(text) ? "ドルは全面高ではなく、円需給と米金利差が焦点" : "ドル円とユーロドルの反応を同時確認";
  const crypto = /BTC/.test(text) ? "BTCは株式リスク選好とETF資金の継続を確認" : "暗号資産はBTCカードで確認";
  const watch = [
    "米PCEデフレーターの結果",
    "中東情勢・原油在庫の方向",
    "USD/JPYの急変と円需給"
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
  const lead = cleanText(report.leadingMarket || "", Infinity);
  const main = cleanText(report.mainScenario || "", Infinity);
  const risk = cleanText(topList(report.riskManagement, 1, Infinity)[0] || breakConditionsFromReport(report, Infinity) || "", Infinity);
  const parts = [];
  if (lead) parts.push(`主導市場：${lead}`);
  if (main) parts.push(`基本姿勢：${main}`);
  if (risk) parts.push(`リスク管理：${risk}`);
  return parts.join("。") || "理由：結論に必要な項目がJSONにありません";
}

function renderScenarios(report) {
  renderProseBlock("mainScenario", report.mainScenario, "理由：メインシナリオがJSONにありません", 3, Infinity);
  renderProseBlock("alternativeScenario", report.alternativeScenario, "理由：代替シナリオがJSONにありません", 3, Infinity);
  const breakText = breakConditionsFromReport(report, 180);
  renderProseBlock("breakConditions", breakText, "理由：崩れる条件を本文から取得できませんでした", 4, Infinity);
  $("breakConditions").classList.toggle("missing", !breakText);
  renderList("handoverList", fallbackHandoverItems(report), "理由：引き継ぎ項目がJSONにありません");
  renderProseBlock("conclusionText", conclusionFrom(report), "理由：結論に必要な項目がJSONにありません", 4, Infinity);
}

function renderFootnote(report) {
  if (report?.historicalArchiveDisplayOnly) {
    const foot = $("dataFootnote");
    foot.textContent = isDashboardReconstructedArchive(report)
      ? "原本欠損・事後再分析版：当時の定時本文・価格・方向を復元したものではありません。参考情報としてのみ閲覧してください。"
      : "Google Drive保存本文の閲覧用記録。元の発行時点のsnapshot・receiptとの照合は未完了です。価格は本文の各観測時刻の参考値です。";
    return;
  }
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
  renderDashboardArchive(report);
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
      .filter((report) => window.MarketReportPublicationPolicy.isEligible(report) || isDashboardHistoricalArchive(report))
      .filter((report) => /^\d{4}-\d{2}-\d{2}$/.test(report.date || ""))
      .sort((a, b) => reportKey(b).localeCompare(reportKey(a)));
    dashboardMeta = data.meta || null;
    const calendar = await loadDashboardEventCalendar();
    dashboardCalendarMeta = calendar;
    dashboardCalendarEvents = asArray(calendar.events).map(normalizeCalendarEvent).filter(Boolean);
    stockAnalysisData = await loadStockAnalysisData();

    if (!reports.length) throw new Error("表示できるレポートがありません");

    const params = new URLSearchParams(window.location.search);
    const initial = window.MarketReportInitialRequestedSlot;
    const date = initial?.date || params.get("date");
    const time = initial?.time || params.get("time");
    const exactRequestedReport = reports.find((report) => report.date === date && report.time === time);
    selectedReport = exactRequestedReport || reports[0];
    if (!exactRequestedReport && date && time && selectedReport) {
      const canonicalUrl = new URL(window.location.href);
      canonicalUrl.searchParams.set("date", selectedReport.date);
      canonicalUrl.searchParams.set("time", selectedReport.time);
      window.history.replaceState({}, "", canonicalUrl);
    }
    render();
  } catch (error) {
    $("reportStatus").textContent = "データ取得エラー";
    document.querySelector(".page-shell").innerHTML = `<div class="empty-state">${esc(error.message)}。理由：reports.jsonの公開または形式を確認してください。</div>`;
  }
}

async function loadDashboardEventCalendar() {
  const paths = ["data/events/upcoming.json", "data/events/latest.json", "data/events.json", "economic-calendar.json"];
  const errors = [];
  for (const path of paths) {
    try {
      const response = await fetch(`${path}?ts=${Date.now()}`, { cache: "no-store" });
      if (!response.ok) throw new Error(`${path} HTTP ${response.status}`);
      return await response.json();
    } catch (error) {
      errors.push(error.message);
    }
  }
  return { status: "unavailable", events: [], error: errors.join(" / ") };
}

async function loadDashboardReports() {
  const errors = [];
  let dashboardPayload = null;
  let dashboardReports = [];
  let historyReports = [];

  try {
    const response = await fetch(`data/dashboard.json?ts=${Date.now()}`, { cache: "no-store" });
    if (!response.ok) throw new Error(`data/dashboard.json HTTP ${response.status}`);
    dashboardPayload = await response.json();
    dashboardReports = normalizeDashboardReports(dashboardPayload);
  } catch (error) {
    errors.push(error.message);
  }

  // dashboard.json は最新1件だけに軽量化する。
  // 過去分とGoogle Docs由来のfullTextは reports.json から結合する。
  try {
    const response = await fetch(`reports.json?ts=${Date.now()}`, { cache: "no-store" });
    if (!response.ok) throw new Error(`reports.json HTTP ${response.status}`);
    const payload = await response.json();
    historyReports = normalizeDashboardReports(payload);
  } catch (error) {
    errors.push(error.message);
  }

  const publishedList = window.MarketReportPublicationPolicy.merge(historyReports, dashboardReports);
  let archives = [];
  try {
    const response = await fetch("data/report-recovery-2026-10.json?ts=" + Date.now(), { cache: "no-store" });
    if (!response.ok) throw new Error("archive HTTP " + response.status);
    const payload = await response.json();
    if (payload?.kind !== "HISTORICAL_ARCHIVE_NOT_OFFICIAL_PUBLICATION" || !Array.isArray(payload.reports)) throw new Error("archive schema");
    // Reject incomplete entries individually. A bad unrelated October record must
    // never hide other fully sourced slots (e.g. the four Oct 15 reports).
    const eligibleRecords = payload.reports.filter(isDashboardHistoricalArchive);
    if (eligibleRecords.length < payload.reports.length) {
      console.warn("[dashboard historical archive] skipped unsupported records:",
        payload.reports.length - eligibleRecords.length);
    }
    // Preserve the original slot-bound chronology independently from the summary adapter.
    window.MarketReportArchiveTimelineBySlot = Object.fromEntries(
      eligibleRecords.filter(r => Array.isArray(r.archiveTimelineRows) && r.archiveTimelineRows.length)
        .map(r => [r.date + " " + r.time, r.archiveTimelineRows])
    );
    archives = eligibleRecords.map(archiveDashboardSummary);
  } catch (error) {
    console.warn("[dashboard historical archive] read unavailable", error.message);
    errors.push("保存記録: " + error.message);
    archives = [];
  }
  const bySlot = new Map(archives.map(r => [r.date + " " + r.time, r]));
  // Formal verified publication is always authoritative when the same slot exists.
  publishedList.forEach(r => bySlot.set(r.date + " " + r.time, r));
  const reportList = [...bySlot.values()];
  // User-owned Google Docs kept in the canonical monthly folder, read back at
  // the revision recorded in each archive file. Never grant formal-publication status.
  const driveArchivePaths = [
    "data/dashboard-drive-archive-2026-10-01-05.json",
    "data/dashboard-drive-archive-2026-10-06-07.json",
    "data/dashboard-drive-archive-2026-10-09-12.json",
    "data/dashboard-drive-archive-2026-10-external.json",
    "data/dashboard-drive-archive-2026-10-19.json",
    "data/dashboard-drive-archive-2026-10-26.json",
    "data/dashboard-drive-archive-2026-10-27.json",
    "data/dashboard-drive-archive-2026-10-28.json",
    "data/dashboard-drive-archive-2026-10-29.json"
  ];
  const drivePayloads = await Promise.all(driveArchivePaths.map(async path => {
    try {
      const response = await fetch(path + "?ts=" + Date.now(), { cache: "no-store" });
      if (!response.ok) throw new Error(path + " HTTP " + response.status);
      const payload = await response.json();
      const expectedFolder = path.includes("-external.json")
        ? "CROSS_FOLDER_VERIFIED_GOOGLE_DOCS"
        : "1qDOwDACdzWsGYcMaEobciDP3dFOdJ4Vz";
      if (payload?.kind !== "HISTORICAL_ARCHIVE_NOT_OFFICIAL_PUBLICATION"
          || payload?.sourceFolderId !== expectedFolder
          || !Array.isArray(payload.reports)) throw new Error("source archive schema mismatch");
      return payload.reports.filter(isDashboardHistoricalArchive).map(archiveDashboardSummary);
    } catch (error) {
      console.warn("[dashboard Drive archive] unavailable", path, error.message);
      return [];
    }
  }));
  const bySlotDrive = new Map(drivePayloads.flat().map(r => [r.date + " " + r.time, r]));
  // Owner-folder archives may not replace formal, validated publication.
  reportList.forEach(r => bySlotDrive.set(r.date + " " + r.time, r));
  const combinedReportList = [...bySlotDrive.values()];

  if (!reportList.length) {
    throw new Error(`ダッシュボードJSONを取得できませんでした。理由：${errors.join(" / ")}`);
  }

  const embeddedMarketData = dashboardPayload?.marketData || dashboardPayload?.latestReport?.marketData || null;
  const independentMarketData = await loadIndependentMarketData();
  const marketData = newerMarketData(embeddedMarketData, independentMarketData);
  const marketDataReportKey = REPORT_TIMES.includes(marketData?.reportSlot)
    ? `${String(marketData?.generatedAt || "").slice(0, 10)} ${marketData.reportSlot}`
    : "";
  const enrichedReports = combinedReportList.map((report) => {
    const key = `${report.date || ""} ${report.time || ""}`;
    if (marketData && !isDashboardHistoricalArchive(report) && key === marketDataReportKey && !report.marketData) {
      return { ...report, marketData };
    }
    return report;
  });

  return {
    reports: enrichedReports,
    meta: {
      generatedAt: dashboardPayload?.generatedAt || "",
      dataAsOf: dashboardPayload?.dataAsOf || "",
      status: dashboardPayload?.status || (historyReports.length ? "fallback-reports-json" : ""),
      marketData,
      marketDataUpdatedAt: dashboardPayload?.marketDataUpdatedAt || marketData?.generatedAt || ""
    }
  };
}

async function loadIndependentMarketData() {
  try {
    const response = await fetch(`data/market/latest.json?ts=${Date.now()}`, { cache: "no-store" });
    if (!response.ok) return null;
    const payload = await response.json();
    if (!payload || typeof payload !== "object" || payload.overallStatus === "blocked") return null;
    if (!payload.markets || typeof payload.markets !== "object") return null;
    return payload;
  } catch (error) {
    return null;
  }
}

async function loadStockAnalysisData() {
  try {
    const response = await fetch(`data/stocks.json?ts=${Date.now()}`, { cache: "no-store" });
    if (!response.ok) return null;
    const payload = await response.json();
    return payload && typeof payload === "object" ? payload : null;
  } catch (error) {
    return null;
  }
}

function newerMarketData(...candidates) {
  return candidates
    .filter((item) => item && typeof item === "object")
    .sort((a, b) => String(b.generatedAt || "").localeCompare(String(a.generatedAt || "")))[0]
    || null;
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
