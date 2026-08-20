/* 08:00 report publication QA gate. */
(() => {
  "use strict";

  const ENFORCE_FROM = "2026-08-08";
  const ITEMS = [
    "NYダウ", "NASDAQ総合", "S&P500", "Russell 2000", "日経225現物",
    "CME日経225先物・円建て", "CME日経225先物・ドル建て", "日経225先物（大阪取引所）",
    "USD/JPY", "EUR/USD", "COMEX金先物", "WTI原油", "BTCUSD", "VIX", "日経VI",
    "Fear & Greed Index", "米10年債利回り", "日本10年国債利回り", "日経225予想PER",
    "日経225 PBR", "日経225予想EPS", "日経225 25日移動平均乖離率",
    "日経225 200日移動平均乖離率", "東証プライム売買代金", "東証プライム売買高",
    "東証プライム値上がり銘柄数", "東証プライム値下がり銘柄数", "東証プライム25日騰落レシオ"
  ];
  const REQUIRED_SIX = new Set(["COMEX金先物", "WTI原油", "日経225先物（大阪取引所）", "USD/JPY", "EUR/USD", "BTCUSD"]);
  const NUMBER_PREFIX = /^[①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳㉑㉒㉓㉔㉕㉖㉗㉘]\s*/;
  const BAD_MARKERS = ["主要市場データ入力に該当行なし", "最終修正版本文に該当行なし", "undefined", "null"];
  let referencePayload = null;
  let referencePromise = null;

  function enforce(report) { return Boolean(report && report.time === "08:00" && String(report.date || "") >= ENFORCE_FROM); }
  function normalizeLabel(value = "") {
    const label = String(value).replace(NUMBER_PREFIX, "").trim();
    return ({
      "日経225先物・大阪取引所": "日経225先物（大阪取引所）",
      "日経225先物(大阪取引所)": "日経225先物（大阪取引所）",
      "日経225 25日乖離率": "日経225 25日移動平均乖離率",
      "日経225 200日乖離率": "日経225 200日移動平均乖離率"
    })[label] || label;
  }
  function reportText(report) { return String(report?.fullText || report?.rawText || report?.body || "").replace(/\r/g, ""); }

  function structuredRows(report) {
    const rows = report?.marketDataTable?.rows;
    if (!Array.isArray(rows)) return [];
    return rows.map((row) => ({
      label: normalizeLabel(row?.label ?? row?.item ?? row?.name ?? ""),
      value: String(row?.value ?? ""),
      change: String(row?.change ?? ""),
      rate: String(row?.rate ?? row?.changePercent ?? ""),
      direction: String(row?.direction ?? "")
    }));
  }

  function textRows(report) {
    const lines = reportText(report).split("\n").map((line) => line.trim()).filter(Boolean);
    const start = lines.findIndex((line) => /主要市場データ/.test(line));
    if (start < 0) return [];
    let end = lines.findIndex((line, index) => index > start && /^3[.．]\s*/.test(line));
    if (end < 0) end = lines.length;
    const block = lines.slice(start + 1, end), result = [];
    for (let i = 0; i < block.length; i += 1) {
      if (!NUMBER_PREFIX.test(block[i]) || i + 4 >= block.length) continue;
      result.push({ label: normalizeLabel(block[i]), value: block[i+1] || "", change: block[i+2] || "", rate: block[i+3] || "", direction: block[i+4] || "" });
      i += 4;
    }
    return result;
  }

  function rows(report) {
    const structured = structuredRows(report);
    return structured.length ? structured : textRows(report);
  }

  function effectiveRows(report, parsed) {
    if (!referencePayload || referencePayload.reportDate !== report?.date || referencePayload.reportSlot !== report?.time) return parsed;
    const items = referencePayload.items || {};
    return parsed.map((row) => {
      const ref = items[row.label];
      if (!ref || typeof ref !== "object" || !String(ref.status || "").startsWith("verified") || ref.value == null || ref.value === "") return row;
      return {
        ...row,
        value: String(ref.value),
        change: ref.change == null ? row.change : String(ref.change),
        rate: ref.rate == null ? row.rate : String(ref.rate),
        direction: ref.direction == null ? row.direction : String(ref.direction)
      };
    });
  }

  async function loadReference() {
    if (referencePromise) return referencePromise;
    referencePromise = (async () => {
      try {
        const response = await fetch(`data/market/morning-reference.json?ts=${Date.now()}`, { cache: "no-store" });
        if (response.ok) referencePayload = await response.json();
      } catch (error) { console.warn("MorningReportQA reference load failed", error); }
      return referencePayload;
    })();
    return referencePromise;
  }

  function hasReasonedUnavailable(value) {
    const text = String(value || "").trim();
    return /^取得不能（.+）$/.test(text) || /^未公表（.+）$/.test(text);
  }

  function validate(report) {
    if (!enforce(report)) return { ready: true, enforced: false, reasons: [], rows: [] };
    const parsed = effectiveRows(report, rows(report));
    const reasons = [];
    if (parsed.length !== 28) reasons.push(`28項目必須: ${parsed.length}行`);
    const labels = parsed.map((row) => row.label);
    if (new Set(labels).size !== labels.length) reasons.push("重複行あり");
    if (labels.length && labels.join("\u0000") !== ITEMS.join("\u0000")) reasons.push("28項目の順序または名称が不一致");
    const byLabel = new Map(parsed.map((row) => [row.label, row]));
    parsed.forEach((row) => {
      const cells = [row.value, row.change, row.rate, row.direction], joined = cells.join(" | ");
      if (cells.some((cell) => !String(cell || "").trim())) reasons.push(`${row.label}: 5列の空欄あり`);
      if (BAD_MARKERS.some((marker) => joined.includes(marker))) reasons.push(`${row.label}: 行ずれ/パーサー異常`);
      if (row.value === "取得不能") reasons.push(`${row.label}: 理由のない取得不能`);
      if (/取得不能|未公表/.test(row.value) && !hasReasonedUnavailable(row.value)) reasons.push(`${row.label}: 取得不能/未公表の理由なし`);
      if (!/取得不能|未公表/.test(row.value) && row.direction === "取得不能") reasons.push(`${row.label}: 値ありなのに方向感が取得不能`);
    });
    REQUIRED_SIX.forEach((label) => {
      const row = byLabel.get(label);
      if (!row) reasons.push(`${label}: 6市場必須行なし`);
      else if (/取得不能|未公表/.test(row.value) && !hasReasonedUnavailable(row.value)) reasons.push(`${label}: 6市場必須値の取得不能理由なし`);
    });
    return { ready: reasons.length === 0, enforced: true, reasons: [...new Set(reasons)], rows: parsed };
  }

  const PREVIOUS_CLOSE_HEADERS = ["項目", "終値・値", "前日比", "騰落率", "方向感"];
  const REQUIRED_DOM_LABELS = ["COMEX金先物", "WTI原油", "日経225先物（大阪取引所）", "USD/JPY", "EUR/USD", "BTCUSD"];
  function domTable(report, root = document) {
    const tables = [...root.querySelectorAll(".sop-section .market-table")];
    return tables.find((table) => {
      const heading = table.closest(".sop-section")?.querySelector("h2")?.textContent || "";
      return /主要市場データ|前営業日終値/.test(heading);
    }) || null;
  }
  function closeDataDate(report) {
    return String(report?.marketDataTable?.dataDate || report?.dataProvenance?.closeSheet?.dataDate || "").trim();
  }
  function validateRendered(report, root = document) {
    if (!enforce(report)) return { ready: true, enforced: false, reasons: [], sourceRows: 0, domRows: 0 };
    const reasons = [];
    const source = structuredRows(report);
    const table = domTable(report, root);
    if (source.length !== 28) reasons.push(`marketDataTable source rows: ${source.length}行`);
    if (!table) return { ready: false, enforced: true, reasons: [...new Set([...reasons, "主要市場データのDOM tableなし"])], sourceRows: source.length, domRows: 0 };
    const headers = [...table.querySelectorAll("thead th")].map((cell) => cell.textContent.trim());
    const domRows = [...table.querySelectorAll("tbody tr")];
    if (domRows.length !== 28) reasons.push(`DOM tbody rows: ${domRows.length}行`);
    if (headers.length !== 5 || headers.join(String.fromCharCode(0)) !== PREVIOUS_CLOSE_HEADERS.join(String.fromCharCode(0))) reasons.push(`08:00ヘッダー不一致: ${headers.join(" / ")}`);
    const labels = domRows.map((row) => row.querySelector("th")?.textContent.trim() || "");
    REQUIRED_DOM_LABELS.forEach((label) => { if (!labels.includes(label)) reasons.push(`${label}: DOM必須行なし`); });
    ["現在値・確認値", "市場・指標", "方向・状態"].forEach((forbidden) => { if (headers.includes(forbidden)) reasons.push(`禁止ヘッダー: ${forbidden}`); });
    const tableText = table.textContent || "";
    if (tableText.includes("前回21:00比")) reasons.push("主要市場データ表に前回21:00比あり");
    const dataDate = closeDataDate(report);
    const normalizedDataDate = dataDate.split("/").join("-");
    if (!dataDate) reasons.push("前営業日終値のdataDateなし");
    else if (/^[0-9]{4}-[0-9]{2}-[0-9]{2}$/.test(normalizedDataDate) && normalizedDataDate >= String(report.date || "")) reasons.push(`dataDateがreport.date以降: ${dataDate}`);
    const result = { ready: reasons.length === 0, enforced: true, reasons: [...new Set(reasons)], sourceRows: source.length, domRows: domRows.length, headers, labels };
    return result;
  }
  function runRenderedQA(report) {
    const result = validateRendered(report);
    window.MorningReportQA.lastRendered = result;
    document.documentElement.dataset.morningReportQa = result.ready ? "pass" : "fail";
    if (result.ready) console.info("[MorningReportQA] DOM PASS", result);
    else console.error("[MorningReportQA] DOM FAIL", result);
    return result;
  }
  window.MorningReportQA = { loadReference, validate, validateRendered, runRenderedQA, rows, effectiveRows, expectedItems: ITEMS.slice() };
  window.addEventListener("market-report-rendered", (event) => runRenderedQA(event.detail?.report));
  if (window.MarketReportLastRendered) runRenderedQA(window.MarketReportLastRendered);
})();
