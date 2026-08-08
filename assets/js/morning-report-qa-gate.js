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
  const REQUIRED_SIX = new Set([
    "COMEX金先物", "WTI原油", "日経225先物（大阪取引所）",
    "USD/JPY", "EUR/USD", "BTCUSD"
  ]);
  const NUMBER_PREFIX = /^[①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳㉑㉒㉓㉔㉕㉖㉗㉘]\s*/;
  const BAD_MARKERS = [
    "主要市場データ入力に該当行なし",
    "最終修正版本文に該当行なし",
    "undefined",
    "null"
  ];
  let referencePayload = null;
  let referencePromise = null;

  function enforce(report) {
    return Boolean(report && report.time === "08:00" && String(report.date || "") >= ENFORCE_FROM);
  }

  function normalizeLabel(value = "") {
    const label = String(value).replace(NUMBER_PREFIX, "").trim();
    const aliases = {
      "日経225先物・大阪取引所": "日経225先物（大阪取引所）",
      "日経225先物(大阪取引所)": "日経225先物（大阪取引所）",
      "日経225 25日乖離率": "日経225 25日移動平均乖離率",
      "日経225 200日乖離率": "日経225 200日移動平均乖離率"
    };
    return aliases[label] || label;
  }

  function reportText(report) {
    return String(report?.fullText || report?.rawText || report?.body || "").replace(/\r/g, "");
  }

  function rows(report) {
    const lines = reportText(report).split("\n").map((line) => line.trim()).filter(Boolean);
    const start = lines.findIndex((line) => /主要市場データ/.test(line));
    if (start < 0) return [];
    let end = lines.findIndex((line, index) => index > start && /^3[.．]\s*/.test(line));
    if (end < 0) end = lines.length;
    const block = lines.slice(start + 1, end);
    const result = [];
    for (let i = 0; i < block.length; i += 1) {
      if (!NUMBER_PREFIX.test(block[i]) || i + 4 >= block.length) continue;
      result.push({
        label: normalizeLabel(block[i]),
        value: block[i + 1] || "",
        change: block[i + 2] || "",
        rate: block[i + 3] || "",
        direction: block[i + 4] || ""
      });
      i += 4;
    }
    return result;
  }

  async function loadReference() {
    if (referencePromise) return referencePromise;
    referencePromise = (async () => {
      try {
        const response = await fetch(`data/market/morning-reference.json?ts=${Date.now()}`, { cache: "no-store" });
        if (response.ok) referencePayload = await response.json();
      } catch (error) {
        console.warn("MorningReportQA reference load failed", error);
      }
      return referencePayload;
    })();
    return referencePromise;
  }

  function validate(report) {
    if (!enforce(report)) return { ready: true, enforced: false, reasons: [], rows: [] };

    const parsed = rows(report);
    const reasons = [];
    if (parsed.length !== 28) reasons.push(`28項目必須: ${parsed.length}行`);

    const labels = parsed.map((row) => row.label);
    if (new Set(labels).size !== labels.length) reasons.push("重複行あり");
    if (labels.length && labels.join("\u0000") !== ITEMS.join("\u0000")) reasons.push("28項目の順序または名称が不一致");

    const byLabel = new Map(parsed.map((row) => [row.label, row]));
    parsed.forEach((row) => {
      const cells = [row.value, row.change, row.rate, row.direction];
      const joined = cells.join(" | ");
      if (cells.some((cell) => !String(cell || "").trim())) reasons.push(`${row.label}: 5列の空欄あり`);
      if (BAD_MARKERS.some((marker) => joined.includes(marker))) reasons.push(`${row.label}: 行ずれ/パーサー異常`);
      if (row.value === "取得不能") reasons.push(`${row.label}: 理由のない取得不能`);
      if (!/取得不能|未公表/.test(row.value) && row.direction === "取得不能") reasons.push(`${row.label}: 値ありなのに方向感が取得不能`);
    });

    REQUIRED_SIX.forEach((label) => {
      const row = byLabel.get(label);
      if (!row) reasons.push(`${label}: 6市場必須行なし`);
      else if (/取得不能|未公表/.test(row.value)) reasons.push(`${label}: 6市場必須値が利用不能`);
    });

    if (referencePayload?.reportDate === report.date && referencePayload?.reportSlot === report.time) {
      Object.entries(referencePayload.items || {}).forEach(([label, ref]) => {
        const row = byLabel.get(label);
        if (!row || !ref || typeof ref !== "object") return;
        const status = String(ref.status || "");
        if (status.startsWith("verified") && ref.value != null && ref.value !== "" && /取得不能/.test(row.value)) {
          reasons.push(`${label}: 検証済み値 ${ref.value} があるのに取得不能`);
        }
      });
    }

    return { ready: reasons.length === 0, enforced: true, reasons: [...new Set(reasons)], rows: parsed };
  }

  window.MorningReportQA = { loadReference, validate, rows, expectedItems: ITEMS.slice() };
})();
