/*
 * Six-market card normalization bridge.
 *
 * Every visible field in a market card is derived from one MarketCardData
 * object.  This keeps a report value, its timestamp, direction and
 * consistency judgement on the same source basis.
 */
(() => {
  "use strict";

  if (typeof renderMarketCards !== "function") return;

  /**
   * @typedef {Object} MarketCardData
   * @property {string} symbol
   * @property {string} displayName
   * @property {number|null} price
   * @property {string|null} priceText
   * @property {"snapshot"|"latest_report"|"previous_confirmed"|null} priceSourceType
   * @property {string|null} priceConfirmedAt
   * @property {"confirmed"|"fallback"|"missing"} priceStatus
   * @property {number|null} change
   * @property {number|null} changePct
   * @property {"snapshot"|"latest_report"|"previous_confirmed"|null} changeSourceType
   * @property {"confirmed"|"fallback"|"missing"} changeStatus
   * @property {string|null} directionLabel
   * @property {"numeric"|"textual"|"insufficient"} directionConfidence
   * @property {string|null} keyPoint
   * @property {string|null} riskText
   * @property {string|null} reasoningText
   * @property {"整合"|"一部整合"|"不整合"|"判定保留"} consistencyStatus
   * @property {string|null} consistencyReason
   */

  const SOURCE_TYPES = ["snapshot", "latest_report", "previous_confirmed"];
  const MISSING_TEXT = /^(?:取得不能|未取得|未確認|確認中|判定保留|記載なし|本文参照|個別記載なし|—|-|)$/;
  const SYMBOL_ALIASES = {
    gold: ["金", "ゴールド", "XAU/USD", "XAUUSD", "COMEX"],
    oil: ["WTI", "WTI原油", "原油"],
    nikkei: ["日経225先物", "日経先物", "日経平均"],
    usdjpy: ["USD/JPY", "USDJPY", "ドル円"],
    eurusd: ["EUR/USD", "EURUSD", "ユーロドル"],
    btc: ["BTCUSD", "BTC/USD", "BTC", "ビットコイン"]
  };
  const FALLBACK_DEFINITIONS = [
    { key: "gold", dataKey: "gold", label: "金", display: "金（XAU/USD）", unit: "USD/oz", icon: "Au", iconClass: "gold", route: "gold-supply-demand.html" },
    { key: "oil", dataKey: "wti", label: "原油", display: "WTI原油（CL）", unit: "USD/bbl", icon: "CL", iconClass: "oil", route: null },
    { key: "nikkei", dataKey: "nikkei225_futures_ose", label: "日経225先物", display: "日経225先物（大阪取引所）", unit: "円", icon: "NK", iconClass: "nikkei", route: "nikkei225-supply-demand.html" },
    { key: "usdjpy", dataKey: "usdjpy", label: "USD/JPY", display: "USD/JPY", unit: "円", icon: "$", iconClass: "", route: "usdjpy-supply-demand.html" },
    { key: "eurusd", dataKey: "eurusd", label: "EUR/USD", display: "EUR/USD", unit: "USD", icon: "€", iconClass: "", route: null },
    { key: "btc", dataKey: "btcusd", label: "BTCUSD", display: "BTCUSD", unit: "USD", icon: "BTC", iconClass: "btc", route: null }
  ];

  const definitions = typeof MARKET_DEFINITIONS !== "undefined"
    ? MARKET_DEFINITIONS
    : FALLBACK_DEFINITIONS;

  function asList(value) {
    if (typeof asArray === "function") return asArray(value);
    return Array.isArray(value) ? value : value ? [value] : [];
  }

  function text(value) {
    if (typeof textOf === "function") return String(textOf(value) || "");
    if (typeof value === "string") return value;
    if (!value || typeof value !== "object") return "";
    return String(value.text || value.summary || value.title || "");
  }

  function clean(value, max = 180) {
    const raw = String(value || "").replace(/\s+/g, " ").trim();
    if (!raw) return "";
    if (typeof cleanText === "function") return cleanText(raw, max);
    return Number.isFinite(max) && raw.length > max ? `${raw.slice(0, max)}...` : raw;
  }

  function number(value) {
    const parsed = Number(String(value ?? "").replace(/,/g, ""));
    return Number.isFinite(parsed) ? parsed : null;
  }

  function definitionFor(symbol) {
    const normalized = String(symbol || "").toLowerCase();
    return definitions.find((item) => item.key === normalized
      || item.dataKey === symbol
      || item.label === symbol
      || item.display === symbol)
      || definitions.find((item) => (SYMBOL_ALIASES[item.key] || []).some((alias) => alias.toLowerCase() === normalized))
      || FALLBACK_DEFINITIONS.find((item) => item.key === normalized)
      || FALLBACK_DEFINITIONS[0];
  }

  function missing(value) {
    return value === null || value === undefined || MISSING_TEXT.test(String(value).trim());
  }

  function aliasesFor(definition) {
    return SYMBOL_ALIASES[definition.key] || [definition.label, definition.display];
  }

  function hasAlias(value, definition) {
    const source = String(value || "");
    return aliasesFor(definition).some((alias) => source.toLowerCase().includes(alias.toLowerCase()));
  }

  function pricePattern(definition) {
    const aliases = aliasesFor(definition).map((alias) => alias.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).join("|");
    const prefix = `(?:${aliases})[^\\n。]{0,60}?`;
    const patterns = {
      gold: new RegExp(`${prefix}([1-9]\\d{0,2},\\d{3}(?:\\.\\d+)?|[3-9]\\d{3}(?:\\.\\d+)?)(?=\\s*(?:ドル|USD|/oz|$|[（(]))`, "i"),
      oil: new RegExp(`${prefix}([1-9]\\d{1,2}(?:\\.\\d+)?|1\\d{2}(?:\\.\\d+)?)(?=\\s*(?:ドル|USD|/bbl|$|[（(]))`, "i"),
      nikkei: new RegExp(`${prefix}([1-9]\\d{1,2},\\d{3}(?:\\.\\d+)?|[1-9]\\d{4,})(?=\\s*円)`, "i"),
      usdjpy: new RegExp(`${prefix}([1-9]\\d{2}(?:\\.\\d+)?)(?=\\s*円)`, "i"),
      eurusd: new RegExp(`${prefix}(1\\.\\d{3,5})(?=\\s*(?:ドル|USD|$|[（(]))`, "i"),
      btc: new RegExp(`${prefix}([1-9]\\d{1,2},\\d{3}(?:\\.\\d+)?|[1-9]\\d{4,})(?=\\s*(?:ドル|USD|$|[（(]))`, "i")
    };
    return patterns[definition.key] || patterns.gold;
  }

  function unlabeledPricePattern(definition) {
    const patterns = {
      gold: /([1-9]\d{0,2},\d{3}(?:\.\d+)?|[3-9]\d{3}(?:\.\d+)?)(?=\s*(?:ドル|USD|\/oz))/i,
      oil: /([1-9]\d{1,2}(?:\.\d+)?|1\d{2}(?:\.\d+)?)(?=\s*(?:ドル|USD|\/bbl))/i,
      nikkei: /([1-9]\d{1,2},\d{3}(?:\.\d+)?|[1-9]\d{4,})(?=\s*円)/i,
      usdjpy: /([1-9]\d{2}(?:\.\d+)?)(?=\s*円)/i,
      eurusd: /(1\.\d{3,5})(?=\s*(?:ドル|USD))/i,
      btc: /([1-9]\d{1,2},\d{3}(?:\.\d+)?|[1-9]\d{4,})(?=\s*(?:ドル|USD))/i
    };
    return patterns[definition.key] || patterns.gold;
  }

  function timestampFrom(value, reportDate = "") {
    const source = String(value || "");
    const timeMatch = source.match(/(?:^|[^\d])([01]?\d|2[0-3]):([0-5]\d)(?:\s*JST)?/);
    if (timeMatch) return `${String(timeMatch[1]).padStart(2, "0")}:${timeMatch[2]} JST`;
    const dateMatch = source.match(/(\d{4})[-/]?(\d{2})[-/]?(\d{2})[T\s]([01]?\d):([0-5]\d)/);
    if (dateMatch) return `${dateMatch[4].padStart(2, "0")}:${dateMatch[5]} JST`;
    if (reportDate && source) return "";
    return "";
  }

  function sourceTimestamp(item, reportDate, fallbackText = "") {
    return timestampFrom(
      item?.asOf || item?.lastVerifiedAt || item?.fetchedAt || item?.updatedAt || fallbackText,
      reportDate
    );
  }

  function parsePriceText(value, definition, allowUnlabeled = false) {
    const source = String(value || "");
    if (!source || /取得不能|未取得|未確認|確認できず/.test(source)) return null;
    const match = source.match(pricePattern(definition)) || (allowUnlabeled ? source.match(unlabeledPricePattern(definition)) : null);
    if (!match) return null;
    const raw = match[1];
    const parsed = number(raw);
    return parsed === null ? null : { value: parsed, display: raw, sourceText: source, time: timestampFrom(source) };
  }

  function parseChangeText(value) {
    const source = String(value || "").replace(/[−－]/g, "-");
    if (!source || /取得不能|未取得|未確認/.test(source)) return { change: null, changePct: null, sourceText: source };

    const pair = source.match(/([+-]?\d[\d,.]*)\s*(?:円|ドル|USD|pt)?\s*(?:\/|／|、)\s*([+-]?\d[\d,.]*)\s*(?:％|%)/);
    if (pair) return { change: number(pair[1]), changePct: number(pair[2]), sourceText: source };

    const labeled = source.match(/(?:前日比|変化|騰落率)[：:\s]*([+-]?\d[\d,.]*)\s*(?:円|ドル|USD|pt)?(?:\s*(?:\/|／|、)\s*([+-]?\d[\d,.]*)\s*(?:％|%))?/);
    if (labeled) {
      const first = number(labeled[1]);
      const second = labeled[2] === undefined ? null : number(labeled[2]);
      return { change: second === null ? first : first, changePct: second, sourceText: source };
    }

    const percent = source.match(/([+-]\d[\d,.]*)\s*(?:％|%)/)
      || source.match(/(?:前日比|騰落率|変化)[：:\s]*([+-]?\d[\d,.]*)\s*(?:％|%)/);
    if (percent) return { change: null, changePct: number(percent[1]), sourceText: source };

    return { change: null, changePct: null, sourceText: source };
  }

  function itemFromPayload(payload, definition) {
    if (!payload || typeof payload !== "object") return null;
    if (payload.markets && typeof payload.markets === "object") {
      return payload.markets[definition.dataKey]
        || payload.markets[definition.key]
        || Object.values(payload.markets).find((item) => item?.dashboardKey === definition.key);
    }
    if (payload.item && typeof payload.item === "object") return payload.item;
    if (payload.value !== undefined || payload.displayValue !== undefined) return payload;
    return null;
  }

  function matchingSnapshot(report, definition) {
    const candidates = [];
    const embedded = report?.marketData;
    if (embedded) candidates.push(embedded);
    try {
      if (typeof dashboardMeta !== "undefined" && dashboardMeta?.marketData) candidates.push(dashboardMeta.marketData);
    } catch (_error) {
      // The dashboard metadata is optional in standalone tests and local files.
    }

    return candidates
      .filter((payload) => {
        const slot = payload.reportSlot || payload.time;
        const date = String(payload.generatedAt || payload.date || "").slice(0, 10);
        const exact = slot === report?.time && date === report?.date;
        return exact || (payload === embedded && !payload.reportSlot && !payload.generatedAt);
      })
      .map((payload) => itemFromPayload(payload, definition))
      .find(Boolean) || null;
  }

  function marketFor(report, definition) {
    if (typeof reportMarket === "function") return reportMarket(report, definition) || {};
    return asList(report?.markets).find((market) => market?.name === definition.label || market?.name === definition.display) || {};
  }

  function reportCandidates(report, definition) {
    const market = marketFor(report, definition);
    const rows = [
      { value: market.price, allowUnlabeled: true, allowChange: true },
      { value: market.outlook, allowUnlabeled: true, allowChange: true },
      { value: market.material, allowUnlabeled: true, allowChange: true },
      { value: market.levels, allowUnlabeled: true, allowChange: true },
      { value: market.change, allowUnlabeled: false, allowChange: true },
      ...asList(report?.changes).map((value) => ({ value: text(value), allowUnlabeled: false, allowChange: false }))
    ];

    const body = String(report?.fullText || report?.rawText || report?.body || "").replace(/\r/g, "");
    if (body) rows.push(...body.split(/\n+/).map((value) => ({ value, allowUnlabeled: false, allowChange: false })));
    return rows.filter((row) => row.value);
  }

  function reportValues(report, definition) {
    const rows = reportCandidates(report, definition);
    let price = null;
    let change = { change: null, changePct: null, sourceText: "" };

    for (const row of rows) {
      const parsed = parsePriceText(row.value, definition, row.allowUnlabeled);
      if (!price && parsed) price = parsed;
      if (!row.allowChange && !hasAlias(row.value, definition)) continue;
      const parsedChange = parseChangeText(row.value);
      if (parsedChange.change !== null || parsedChange.changePct !== null) {
        change = { ...parsedChange, time: timestampFrom(row.value) };
        if (price && change.time) break;
      }
    }

    return { price, change, market: marketFor(report, definition) };
  }

  function snapshotValues(item, definition) {
    if (!item) return null;
    const value = number(item.value ?? item.displayValue);
    if (value === null) return null;
    let change = number(item.change);
    let changePct = number(item.changePercent);
    const previous = number(item.previousClose);
    if (change === null && previous !== null) change = value - previous;
    if (changePct === null && previous !== null && previous !== 0) changePct = ((value / previous) - 1) * 100;
    return {
      price: { value, display: item.displayValue || "", sourceText: "", time: sourceTimestamp(item) },
      change: { change, changePct, sourceText: item.changeText || "", time: sourceTimestamp(item) },
      fallback: Boolean(item.fallbackUsed || item.verificationStatus === "fallback"),
      item,
      definition
    };
  }

  function sourceReport(sources, type) {
    const candidate = sources?.[type];
    if (!candidate) return null;
    if (candidate.report) return candidate.report;
    if (candidate.latestReport) return candidate.latestReport;
    if (candidate.date || candidate.time || candidate.markets || candidate.fullText) return candidate;
    return null;
  }

  function sourcePayload(sources, type, definition) {
    const candidate = sources?.[type];
    if (!candidate) return null;
    return itemFromPayload(candidate, definition) || itemFromPayload(candidate?.marketData, definition);
  }

  function previousReportFor(report, definition) {
    try {
      if (typeof reports === "undefined" || !Array.isArray(reports)) return null;
      const currentKey = `${report?.date || ""} ${report?.time || ""}`;
      return reports
        .filter((candidate) => `${candidate?.date || ""} ${candidate?.time || ""}` < currentKey)
        .sort((a, b) => `${b?.date || ""} ${b?.time || ""}`.localeCompare(`${a?.date || ""} ${a?.time || ""}`))
        .map((candidate) => ({ report: candidate, values: reportValues(candidate, definition) }))
        .find((candidate) => candidate.values.price || candidate.values.change.change !== null || candidate.values.change.changePct !== null)
        || null;
    } catch (_error) {
      return null;
    }
  }

  function formatNumeric(value, definition) {
    if (value === null || value === undefined) return "";
    const abs = Math.abs(value);
    const digits = definition.key === "eurusd" || abs < 1 ? 5 : abs < 10 ? 3 : abs < 1000 ? 2 : 0;
    return Number(value).toLocaleString("ja-JP", {
      signDisplay: "always",
      minimumFractionDigits: digits,
      maximumFractionDigits: digits
    });
  }

  function formatPrice(value, definition) {
    if (value === null || value === undefined) return null;
    const digits = definition.key === "eurusd" ? 5
      : definition.key === "usdjpy" ? 3
        : definition.key === "nikkei" ? 0
          : definition.key === "btc" ? 2
            : 2;
    return Number(value).toLocaleString("ja-JP", { minimumFractionDigits: digits, maximumFractionDigits: digits });
  }

  function formatPercent(value) {
    if (value === null || value === undefined) return "";
    return Number(value).toLocaleString("ja-JP", {
      signDisplay: "always",
      minimumFractionDigits: 2,
      maximumFractionDigits: 2
    });
  }

  function directionFromNumeric(change, changePct) {
    const value = change !== null ? change : changePct;
    if (value === null) return { trend: "missing", label: null };
    if (value > 0) return { trend: "up", label: "上昇・強含み" };
    if (value < 0) return { trend: "down", label: "下落・弱含み" };
    return { trend: "flat", label: "中立" };
  }

  function directionFromText(value) {
    const source = clean(value, 90);
    if (!source || MISSING_TEXT.test(source)) return { trend: "missing", label: null };
    const trend = typeof trendFromText === "function"
      ? trendFromText(source)
      : /上昇|強|買/.test(source) ? "up" : /下落|弱|売/.test(source) ? "down" : "flat";
    return { trend, label: source };
  }

  function isUsableReason(value) {
    const source = clean(value, 220);
    return Boolean(source) && !MISSING_TEXT.test(source) && !/^対象\s*[：:]/.test(source);
  }

  function reasoningFor(report, definition, market) {
    const direct = [market?.outlook, market?.material, market?.positioning]
      .map((value) => clean(value, 160))
      .find(isUsableReason);
    if (direct) return direct;

    const body = String(report?.fullText || report?.rawText || report?.body || "").replace(/\r/g, "");
    const aliases = aliasesFor(definition);
    const line = body.split("\n").map((value) => clean(value, 180)).find((value) => {
      return aliases.some((alias) => value.toLowerCase().includes(alias.toLowerCase()))
        && /(?:材料|支え|需要|金利|地政学|供給|買|売|リスク|警戒|反応)/.test(value)
        && !/主要市場データ|前営業日終値/.test(value);
    });
    return isUsableReason(line) ? line : null;
  }

  function keyPointFor(market, reportData) {
    const direct = [market?.levels, market?.price, reportData?.price?.sourceText]
      .map((value) => clean(value, 120))
      .find((value) => isUsableReason(value) && /\d/.test(value));
    return direct || null;
  }

  function riskFor(market, report, definition) {
    const direct = [market?.risk, market?.breakCondition]
      .map((value) => clean(value, 120))
      .find(isUsableReason);
    if (direct) return direct;
    try {
      if (typeof riskForMarket === "function") {
        const value = clean(riskForMarket(report, definition), 120);
        if (isUsableReason(value)) return value;
      }
    } catch (_error) {
      // Fallback text is optional; missing risk is rendered as a neutral placeholder.
    }
    return null;
  }

  function consistencyFromReport(report, definition) {
    try {
      if (typeof consistencyForMarket === "function") return consistencyForMarket(report, definition);
    } catch (_error) {
      // Use the conservative hold state below when the legacy parser is absent.
    }
    return { verdict: "一部整合", cls: "partial", reason: "材料と値動きの個別判定がありません" };
  }

  function resolveConsistency(report, definition, card) {
    if (card.price === null || card.change === null && card.changePct === null || !card.reasoningText) {
      const missingParts = [
        card.price === null ? "主値" : "",
        card.change === null && card.changePct === null ? "前日比" : "",
        !card.reasoningText ? "材料" : ""
      ].filter(Boolean).join("・");
      return {
        verdict: "判定保留",
        cls: "pending",
        reason: `${missingParts || "判定"}が不足しているため判定保留`
      };
    }

    const result = consistencyFromReport(report, definition);
    return {
      verdict: /^(整合|一部整合|不整合)$/.test(result.verdict) ? result.verdict : "一部整合",
      cls: result.verdict === "整合" ? "match" : result.verdict === "不整合" ? "conflict" : "partial",
      reason: clean(result.reason || "材料と値動きの個別判定を確認", 240)
    };
  }

  function sourceLabel(sourceType, timestamp, reportTime) {
    const time = timestamp ? `（${timestamp}）` : "";
    if (sourceType === "snapshot") return `${reportTime || "対象時刻"}レポート採用値`;
    if (sourceType === "latest_report") return timestamp ? `補助確認値${time}` : `${reportTime || "対象時刻"}レポート採用値`;
    if (sourceType === "previous_confirmed") return `前回確認値${time}`;
    return `${reportTime || "対象時刻"}レポート採用値`;
  }

  function normalizedSource(sourceType, values, definition, reportDate) {
    if (!values) return {
      price: null,
      change: null,
      changePct: null,
      sourceType: null,
      status: "missing",
      changeStatus: "missing",
      confirmedAt: null
    };
    const isSnapshot = sourceType === "snapshot";
    const fallback = Boolean(values.fallback);
    const price = values.price || null;
    const change = values.change || { change: null, changePct: null, time: "" };
    const timestamp = price?.time || change?.time || sourceTimestamp(values.item, reportDate, price?.sourceText || "");
    return {
      price: price ? { value: price.value, display: price.display || formatPrice(price.value, definition) } : null,
      change: change.change,
      changePct: change.changePct,
      sourceType: SOURCE_TYPES.includes(sourceType) ? sourceType : null,
      status: price ? (isSnapshot && !fallback ? "confirmed" : "fallback") : "missing",
      changeStatus: change.change !== null || change.changePct !== null
        ? (isSnapshot && !fallback ? "confirmed" : "fallback")
        : "missing",
      confirmedAt: timestamp || null,
      fallback
    };
  }

  function buildMarketCard(symbol, reportTime, sources = {}) {
    const definition = definitionFor(symbol);
    const report = sources.report || sources.latestReport || (sources.currentReport || null);
    const reportDate = report?.date || "";

    const snapshotItem = sourcePayload(sources, "snapshot", definition)
      || matchingSnapshot(report, definition);
    const snapshotValuesResult = snapshotValues(snapshotItem, definition);
    const reportResult = reportValues(sourceReport(sources, "latestReport") || report, definition);

    const explicitPrevious = sourcePayload(sources, "previousConfirmed", definition);
    const previousPayloadValues = snapshotValues(explicitPrevious, definition);
    const previousReport = previousPayloadValues ? null : previousReportFor(report, definition);
    const previousValues = previousPayloadValues || (previousReport ? previousReport.values : null);

    const priceSource = snapshotValuesResult?.price
      ? normalizedSource(snapshotItem?.fallbackUsed || snapshotItem?.verificationStatus === "fallback" ? "previous_confirmed" : "snapshot", snapshotValuesResult, definition, reportDate)
      : reportResult.price
        ? normalizedSource("latest_report", reportResult, definition, reportDate)
        : previousValues
          ? normalizedSource("previous_confirmed", previousValues, definition, previousReport?.report?.date || reportDate)
          : normalizedSource(null, null, definition, reportDate);

    const changeSource = snapshotValuesResult && (snapshotValuesResult.change.change !== null || snapshotValuesResult.change.changePct !== null)
      ? normalizedSource(snapshotItem?.fallbackUsed || snapshotItem?.verificationStatus === "fallback" ? "previous_confirmed" : "snapshot", snapshotValuesResult, definition, reportDate)
      : reportResult.change.change !== null || reportResult.change.changePct !== null
        ? normalizedSource("latest_report", reportResult, definition, reportDate)
        : previousValues
          ? normalizedSource("previous_confirmed", previousValues, definition, previousReport?.report?.date || reportDate)
          : normalizedSource(null, null, definition, reportDate);

    const market = report ? marketFor(report, definition) : {};
    const numericDirection = directionFromNumeric(changeSource.change, changeSource.changePct);
    const textualDirection = directionFromText(market.direction || market.outlook || "");
    const direction = numericDirection.label
      ? { ...numericDirection, confidence: "numeric" }
      : textualDirection.label
        ? { ...textualDirection, confidence: "textual" }
        : { trend: "missing", label: null, confidence: "insufficient" };
    const reasoningText = report ? reasoningFor(report, definition, market) : null;

    const card = {
      symbol: definition.key,
      displayName: definition.display,
      price: priceSource.price?.value ?? null,
      priceText: priceSource.price?.display || null,
      priceSourceType: priceSource.sourceType,
      priceConfirmedAt: priceSource.confirmedAt,
      priceStatus: priceSource.price ? priceSource.status : "missing",
      change: changeSource.change,
      changePct: changeSource.changePct,
      changeSourceType: changeSource.sourceType,
      changeStatus: changeSource.changeStatus,
      directionLabel: direction.label,
      directionConfidence: direction.confidence,
      keyPoint: keyPointFor(market, reportResult),
      riskText: riskFor(market, report, definition),
      reasoningText,
      consistencyStatus: "判定保留",
      consistencyReason: null,
      trend: direction.trend,
      basisLabel: sourceLabel(priceSource.sourceType, priceSource.confirmedAt, reportTime),
      definition
    };

    const consistency = resolveConsistency(report, definition, card);
    card.consistencyStatus = consistency.verdict;
    card.consistencyReason = consistency.reason;
    return card;
  }

  function normalizeSources(symbol, reportTime, sources = {}) {
    const definition = definitionFor(symbol);
    const report = sources.report || sources.latestReport || null;
    return {
      report,
      snapshot: sourcePayload(sources, "snapshot", definition) || matchingSnapshot(report, definition),
      latestReport: sourceReport(sources, "latestReport") || report,
      previousConfirmed: sourcePayload(sources, "previousConfirmed", definition) || previousReportFor(report, definition),
      reportTime
    };
  }

  function changeDisplay(card) {
    if (card.change === null && card.changePct === null) return "前日比：確認中 / 騰落率：確認中";
    const parts = [];
    if (card.change !== null) parts.push(`前日比：${formatNumeric(card.change, card.definition)}`);
    else parts.push("前日比：確認中");
    if (card.changePct !== null) parts.push(`騰落率：${formatPercent(card.changePct)}%`);
    else parts.push("騰落率：確認中");
    return parts.join(" / ");
  }

  function renderMarketCardsNormalized(report) {
    const container = $("marketCards");
    if (!container) return;
    container.innerHTML = definitions.map((definition) => {
      const sources = normalizeSources(definition.key, report?.time, { report, latestReport: report });
      const card = buildMarketCard(definition.key, report?.time, sources);
      const trend = card.trend;
      const trendClass = trend === "up" ? "up" : trend === "down" ? "down" : trend === "missing" ? "missing" : "flat";
      const reasonLabel = trend === "down" ? "なぜ売られたか" : trend === "up" ? "なぜ買われたか" : "なぜ動いたか";
      const directionText = card.directionLabel
        ? `${card.directionLabel}${card.directionConfidence === "numeric" ? "" : "（本文ベース）"}`
        : "判定保留";
      const reason = card.reasoningText || "理由：本文に市場別理由がありません";
      const levels = card.keyPoint || "確認中";
      const risk = card.riskText || "確認中";
      const tag = definition.route ? "a" : "article";
      const href = definition.route ? ` href="${definition.route}"` : "";
      const aria = definition.route ? ` aria-label="${esc(definition.display)}の詳細へ"` : "";
      const price = card.priceText || "取得不能";
      const consistencyClass = card.consistencyStatus === "整合" ? "match"
        : card.consistencyStatus === "不整合" ? "conflict"
          : card.consistencyStatus === "判定保留" ? "pending" : "partial";
      return `<${tag} class="market-card"${href}${aria}>
        <span class="asset-icon ${esc(definition.iconClass || "")}">${esc(definition.icon || "")}</span>
        <span>
          <h3>${esc(definition.display)}</h3>
          <p class="market-value">${esc(price)}${definition.unit ? `<small>${esc(definition.unit)}</small>` : ""}</p>
          <p class="change-line ${trendClass}">${esc(changeDisplay(card))}</p>
          <p class="market-direction-line ${trendClass}">方向感：${esc(directionText)}</p>
          <p class="market-basis-line">表示基準：${esc(card.basisLabel)}</p>
          <dl>
            <dt class="${trend === "up" ? "positive-label" : trend === "down" ? "negative-label" : ""}">${esc(reasonLabel)}</dt><dd>${esc(reason)}</dd>
            <dt>注目点</dt><dd>${esc(levels)}</dd>
            <dt>リスク</dt><dd>${esc(risk)}</dd>
          </dl>
          <span class="consistency-badge ${consistencyClass}">材料と値動きの整合性：${esc(card.consistencyStatus)}</span>
          <p class="market-note">${esc(card.consistencyReason || "判定保留")}</p>
        </span>
        <span class="direction-mark ${trendClass}">${typeof directionMark === "function" ? directionMark(trend) : trend === "up" ? "↑" : trend === "down" ? "↓" : "→"}</span>
      </${tag}>`;
    }).join("");
  }

  window.MarketCardData = true;
  window.buildMarketCard = buildMarketCard;
  window.normalizeMarketCardSources = normalizeSources;
  window.renderMarketCardsNormalized = renderMarketCardsNormalized;
  window.__marketCardNormalizerInstalled = true;
  renderMarketCards = renderMarketCardsNormalized;

  // If the dashboard finished its first async render before this script was
  // evaluated, repaint the active report immediately with the normalized view.
  try {
    if (typeof selectedReport !== "undefined" && selectedReport) {
      renderMarketCardsNormalized(selectedReport);
    }
  } catch (error) {
    // The normal render path will retry once the report is selected.
  }
})();

