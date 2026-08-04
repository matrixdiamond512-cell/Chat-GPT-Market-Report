const fs = require("fs");

const reportsPayload = JSON.parse(fs.readFileSync("reports.json", "utf8"));
const existingPayload = JSON.parse(fs.readFileSync("data/events.json", "utf8"));
const reports = (Array.isArray(reportsPayload) ? reportsPayload : reportsPayload.reports || [])
  .filter((report) => /^\d{4}-\d{2}-\d{2}$/.test(String(report.date || "")) && /^\d{2}:\d{2}$/.test(String(report.time || "")))
  .sort((a, b) => `${b.date} ${b.time}`.localeCompare(`${a.date} ${a.time}`));

if (!reports.length) throw new Error("reports.jsonに有効なレポートがありません。");

const generatedAt = formatJst(new Date());
const latest = reports[0];

function asArray(value) {
  if (Array.isArray(value)) return value;
  return value ? [value] : [];
}

function clean(value, max = 160) {
  const text = String(value ?? "")
    .replace(/\s+/g, " ")
    .replace(/^[・\s]+/, "")
    .trim();
  return max && text.length > max ? `${text.slice(0, max)}...` : text;
}

function isDate(value) {
  return /^\d{4}-\d{2}-\d{2}$/.test(String(value || ""));
}

function normalizeTime(value) {
  const match = String(value || "").match(/\b([01]?\d|2[0-3]):([0-5]\d)\b/);
  return match ? `${match[1].padStart(2, "0")}:${match[2]}` : "";
}

function dateFromText(text, fallbackDate) {
  const iso = String(text || "").match(/(\d{4})[-/](\d{1,2})[-/](\d{1,2})/);
  if (iso) return `${iso[1]}-${iso[2].padStart(2, "0")}-${iso[3].padStart(2, "0")}`;
  const monthDay = String(text || "").match(/(?:^|[^\d])(\d{1,2})\/(\d{1,2})(?:[^\d]|$)/);
  if (monthDay && isDate(fallbackDate)) {
    return `${fallbackDate.slice(0, 4)}-${monthDay[1].padStart(2, "0")}-${monthDay[2].padStart(2, "0")}`;
  }
  return fallbackDate;
}

function titleFromText(text) {
  return clean(String(text || "")
    .replace(/^\d{4}[-/]\d{1,2}[-/]\d{1,2}\s*/, "")
    .replace(/^\d{1,2}\/\d{1,2}\s*/, "")
    .replace(/^\b[0-2]?\d:[0-5]\d\s*/, "")
    .replace(/^(米国|日本|欧州|中国|複数)\s+/, "")
    .replace(/^随時\s*/, "")
    .replace(/^予定確認\s*/, ""), 90);
}

function countryFromText(text) {
  if (/米|FOMC|FRB|PCE|CPI|雇用|ISM|JOLTS|ADP|AMD|Caterpillar|McDonald|Pfizer/.test(text)) return "米国";
  if (/日銀|日本|東京|介入/.test(text)) return "日本";
  if (/ECB|ユーロ|欧州|ドイツ/.test(text)) return "欧州";
  if (/中国/.test(text)) return "中国";
  return "複数";
}

function importanceFromText(text) {
  const numeric = Number(text);
  if (Number.isFinite(numeric)) return Math.max(1, Math.min(3, Math.round(numeric)));
  if (/FOMC|日銀|PCE|CPI|米雇用統計|政策|会見|JOLTS/.test(String(text))) return 3;
  if (/ADP|PMI|ISM|GDP|在庫|決算|求人件数|耐久財|貿易収支|製造業新規受注/.test(String(text))) return 2;
  return 1;
}

function categoryFromText(text, time) {
  if (time) return "scheduled_event";
  if (/随時|協議|ホルムズ|介入|発言|観測|OPEC/.test(text)) return "monitoring_headline";
  return "scheduled_check";
}

function timingLabelFromText(text, time) {
  if (time) return "";
  if (/随時|協議|ホルムズ|介入|発言|観測|OPEC/.test(text)) return "随時";
  return "予定確認";
}

function affectedMarkets(text) {
  if (/原油|OPEC|イラン|ホルムズ|在庫/.test(text)) return ["原油", "金", "米金利", "USD/JPY", "株式"];
  if (/日銀|介入|円/.test(text)) return ["USD/JPY", "日経225先物", "日本株", "日本金利"];
  if (/FRB|FOMC|PCE|CPI|雇用|ISM|GDP|JOLTS|ADP|求人件数/.test(text)) return ["米金利", "USD/JPY", "米国株", "日経225先物", "金"];
  if (/決算|AMD|Caterpillar|McDonald|Pfizer|Microsoft|Meta|Apple|Amazon/.test(text)) return ["米国株", "日経225先物", "USD/JPY"];
  return ["USD/JPY", "株式", "金利"];
}

function watchPoints(text) {
  if (/原油|OPEC|イラン|ホルムズ|在庫/.test(text)) return ["WTIの反応", "米10年債利回り", "金の安全資産需要", "株価指数先物"];
  if (/日銀|介入|円/.test(text)) return ["USD/JPYの初動", "日本金利", "日経225先物", "輸出株"];
  if (/FRB|FOMC|PCE|CPI|雇用|ISM|GDP|JOLTS|ADP|求人件数/.test(text)) return ["米2年債利回り", "USD/JPY", "米株先物", "金・BTC"];
  if (/決算|AMD|Caterpillar|McDonald|Pfizer|Microsoft|Meta|Apple|Amazon/.test(text)) return ["発表後の株価反応", "Nasdaq先物", "日経225先物", "ドル円"];
  return ["発表時刻の確認", "米金利", "USD/JPY", "株価指数先物"];
}

function isEventText(text) {
  if (/今日の相場テーマ|6市場の見通し|メインシナリオ|代替シナリオ|総合判断|最終判断/.test(text)) return false;
  if (/^(金|原油|WTI原油|日経225先物|USD\/JPY|EUR\/USD|BTCUSD|BTC)[:：\s]/.test(text)) return false;
  return /\b[0-2]?\d:[0-5]\d\b|FOMC|FRB|PCE|CPI|雇用|ISM|PMI|GDP|政策|会見|決算|在庫|OPEC|協議|ホルムズ|介入|日銀|指標|発言|観測|求人件数/.test(text);
}

function isGenericEventTitle(title) {
  return /今週のADP雇用統計と米雇用統計|米求人件数など米労働市場指標/.test(String(title || ""));
}

function splitEventText(value) {
  const text = clean(value, 1200).replace(/^今後の重要イベント[:：\s]*/, "").replace(/。$/, "");
  if (!text) return [];
  const numbered = text
    .replace(/(?:^|\s)(\d+[.)．]|[①-⑳])/g, "\n$1")
    .split(/\n+/)
    .map((item) => item.trim())
    .filter(Boolean);
  const chunks = numbered.length > 1 ? numbered : [text];
  return chunks
    .flatMap((item) => item.length >= 48 && /、/.test(item) ? item.split(/、/) : [item])
    .map((item) => item.replace(/[。,、\s]+$/, "").trim())
    .filter((item) => item.length >= 2);
}

function nextWeekday(baseDate, weekday) {
  const date = new Date(`${baseDate}T00:00:00+09:00`);
  let diff = weekday - date.getDay();
  if (diff <= 0) diff += 7;
  date.setDate(date.getDate() + diff);
  return formatDate(date);
}

function expandSpecificEvents(text, report) {
  const rows = [];
  if (/水曜日/.test(text) && /ADP/.test(text) && /雇用統計/.test(text)) {
    rows.push(`${nextWeekday(report.date, 3)} 予定確認 ADP雇用統計`);
  }
  if (/金曜日/.test(text) && /米雇用統計|雇用統計/.test(text)) {
    rows.push(`${nextWeekday(report.date, 5)} 予定確認 米雇用統計`);
  }
  if (/決算|AMD|Caterpillar|McDonald|McDonald’s|Pfizer|Eli Lilly|Microsoft|Meta|Apple|Amazon/.test(text)) {
    ["AMD", "Caterpillar", "McDonald", "McDonald’s", "Pfizer", "Eli Lilly", "Microsoft", "Meta", "Apple", "Amazon"].forEach((name) => {
      if (text.includes(name)) rows.push(`${report.date} 予定確認 ${name.replace("McDonald’s", "McDonald")}決算`);
    });
  }
  return rows;
}

function applyDetailToExisting(text, rows) {
  if (!/JOLTS求人件数/.test(text) || !/前回/.test(text)) return false;
  const target = [...rows].reverse().find((event) => /JOLTS求人件数/.test(event.title || ""));
  if (!target) return false;
  target.reason = clean(text, 160);
  const previous = String(text).match(/前回\s*([0-9.,]+万人?)/);
  if (previous) target.previous = previous[1];
  return true;
}

function blank(value) {
  if (Array.isArray(value)) return value.length === 0;
  if (value && typeof value === "object") return false;
  const text = String(value ?? "").trim();
  return !text || text === "—" || text === "-";
}

function stableId(event) {
  const key = [event.date || "", event.time || event.timingLabel || "", event.country || "", clean(event.title || "", 120).toLowerCase()].join("|");
  let hash = 0;
  for (let i = 0; i < key.length; i += 1) {
    hash = ((hash << 5) - hash) + key.charCodeAt(i);
    hash |= 0;
  }
  return `event-${Math.abs(hash).toString(36)}`;
}

function refreshStatus(event) {
  if (!event.createdAt) event.createdAt = generatedAt;
  event.updatedAt = generatedAt;
  event.isTimed = Boolean(event.time);
  event.isImportantEvent = event.category !== "monitoring_headline";
  const eventMillis = event.time ? new Date(`${event.date}T${event.time}:00+09:00`).getTime() : 0;
  if (!blank(event.actual) || !blank(event.resultComparison) || !blank(event.resultExplanation)) {
    event.status = "released";
  } else if (event.category === "monitoring_headline") {
    event.status = "monitoring";
  } else if (event.time && eventMillis < Date.now()) {
    event.status = "needs_result";
  } else if (!event.time) {
    event.status = "scheduled_check";
  } else {
    event.status = "scheduled";
  }
  return event;
}

function normalizeExistingEvent(event) {
  if (!event || typeof event !== "object") return null;
  const date = String(event.date || String(event.datetimeJst || "").slice(0, 10) || "").trim();
  const time = normalizeTime(event.time || String(event.datetimeJst || "").slice(11, 16) || "");
  const title = clean(event.title || event.name || event.event || "", 90);
  if (!isDate(date) || !title) return null;
  const normalized = {
    ...event,
    date,
    time,
    datetimeJst: time ? `${date}T${time}:00+09:00` : "",
    timingLabel: time ? "" : clean(event.timingLabel || event.time || "予定確認", 16),
    title,
    country: clean(event.country || event.region || countryFromText(title), 20),
    importance: importanceFromText(event.importance || title),
    category: event.category || (time ? "scheduled_event" : "scheduled_check"),
    affectedMarkets: asArray(event.affectedMarkets || event.affected || affectedMarkets(title)),
    watchPoints: asArray(event.watchPoints || watchPoints(title)),
    postReleaseReactions: asArray(event.postReleaseReactions || event.reactions),
    comparison: asArray(event.comparison)
  };
  normalized.id = event.id || stableId(normalized);
  return refreshStatus(normalized);
}

function eventFromText(text, report, rows) {
  text = clean(text, 360);
  if (!text || !isEventText(text)) return null;
  if (applyDetailToExisting(text, rows)) return null;
  const time = normalizeTime(text);
  const date = dateFromText(text, report.date);
  const title = titleFromText(text);
  if (!title || !isDate(date)) return null;
  const event = {
    date,
    time,
    datetimeJst: time ? `${date}T${time}:00+09:00` : "",
    timingLabel: timingLabelFromText(text, time),
    country: countryFromText(text),
    title,
    category: categoryFromText(text, time),
    importance: importanceFromText(text),
    forecast: "未取得",
    previous: "未取得",
    actual: "",
    resultComparison: "",
    resultExplanation: "",
    affectedMarkets: affectedMarkets(text),
    reason: clean(text, 160),
    sourceType: "market_report_extraction",
    sourceReportKey: `${report.date} ${report.time}`,
    sourceNote: "マーケットレポート本文から抽出",
    watchPoints: watchPoints(text),
    postReleaseReactions: [],
    comparison: []
  };
  event.id = stableId(event);
  return refreshStatus(event);
}

function mergeEvent(existing, incoming) {
  if (!existing) return incoming;
  const merged = { ...existing };
  Object.entries(incoming).forEach(([key, value]) => {
    if (!blank(value)) merged[key] = value;
  });
  ["forecast", "previous", "actual", "resultComparison", "resultExplanation", "marketReaction", "resultSavedAt", "resultSource", "resultUpdatedAt"].forEach((field) => {
    if (!blank(existing[field]) && blank(incoming[field])) merged[field] = existing[field];
  });
  ["postReleaseReactions", "comparison"].forEach((field) => {
    if (Array.isArray(existing[field]) && existing[field].length && (!Array.isArray(incoming[field]) || !incoming[field].length)) {
      merged[field] = existing[field];
    }
  });
  if (existing.conclusion && !incoming.conclusion) merged.conclusion = existing.conclusion;
  return refreshStatus(merged);
}

function eventRowsFromReport(report) {
  const rows = [];
  const values = [
    ...asArray(report.events),
    ...asArray(report.importantEvents),
    ...asArray(report.calendarEvents)
  ];
  values.forEach((item) => {
    if (item && typeof item === "object") {
      const event = normalizeExistingEvent({ ...item, date: item.date || report.date });
      if (event) rows.push(event);
      return;
    }
    splitEventText(item).forEach((chunk) => {
      const expanded = expandSpecificEvents(chunk, report);
      (expanded.length ? expanded : [chunk]).forEach((text) => {
        const event = eventFromText(text, report, rows);
        if (event) rows.push(event);
      });
    });
  });
  return rows;
}

function formatDate(date) {
  const parts = new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Tokyo", year: "numeric", month: "2-digit", day: "2-digit" }).formatToParts(date);
  const values = Object.fromEntries(parts.map((part) => [part.type, part.value]));
  return `${values.year}-${values.month}-${values.day}`;
}

function formatJst(date) {
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Tokyo",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false
  }).formatToParts(date);
  const values = Object.fromEntries(parts.map((part) => [part.type, part.value]));
  return `${values.year}-${values.month}-${values.day}T${values.hour}:${values.minute}:${values.second}+09:00`;
}

function dateLabel(date) {
  const parsed = new Date(`${date}T00:00:00+09:00`);
  const weekdays = ["日", "月", "火", "水", "木", "金", "土"];
  return `${date.replace(/-/g, "/")}（${weekdays[parsed.getDay()]}）`;
}

const byId = new Map();
asArray(existingPayload.events).map(normalizeExistingEvent).filter(Boolean).forEach((event) => {
  byId.set(event.id, event);
});

reports.slice(0, 120).forEach((report) => {
  eventRowsFromReport(report).forEach((event) => {
    byId.set(event.id, mergeEvent(byId.get(event.id), event));
  });
});

const events = [...byId.values()]
  .filter((event) => !isGenericEventTitle(event.title))
  .sort((a, b) => `${b.date} ${b.time || b.timingLabel || ""} ${b.title}`.localeCompare(`${a.date} ${a.time || a.timingLabel || ""} ${a.title}`))
  .slice(0, 260);

const dayMap = new Map();
events.forEach((event) => {
  const day = dayMap.get(event.date) || {
    date: event.date,
    label: dateLabel(event.date),
    eventCount: 0,
    releasedCount: 0,
    needsResultCount: 0
  };
  day.eventCount += 1;
  if (event.status === "released") day.releasedCount += 1;
  if (event.status === "needs_result") day.needsResultCount += 1;
  dayMap.set(event.date, day);
});

const days = [...dayMap.values()].sort((a, b) => b.date.localeCompare(a.date));
const latestKey = `${latest.date} ${latest.time}`;
const payload = {
  schemaVersion: "1.1.0",
  pageId: "events",
  generatedAt,
  publishedAt: generatedAt,
  dataAsOf: `${latest.date}T${latest.time}:00+09:00`,
  status: "ok",
  mode: "daily_history",
  currentReportKey: latestKey,
  retention: {
    mode: "append_and_merge",
    maxEvents: 260,
    preserveResultFields: true
  },
  days,
  events,
  sources: [
    {
      id: "MARKET_REPORTS_JSON",
      name: "マーケットレポート本文の構造化JSON",
      path: "reports.json",
      asOf: latestKey,
      status: "ok",
      note: "重要イベントは本文から抽出し、予想・結果・説明は履歴として保存します。"
    },
    {
      id: "MANUAL_RESULT_FIELDS",
      name: "市場予想・結果・発表後説明の補完欄",
      type: "manual",
      status: "available",
      note: "既存JSONに入力済みの結果、比較、説明は新しい抽出で空欄上書きしません。"
    }
  ],
  errors: []
};

fs.writeFileSync("data/events.json", `${JSON.stringify(payload, null, 2)}\n`);
console.log(JSON.stringify({
  generatedAt,
  currentReportKey: latestKey,
  days: days.length,
  events: events.length,
  firstDays: days.slice(0, 5)
}, null, 2));
