/* Structured reason fallback for six-market dashboard cards. */
(() => {
  "use strict";

  const ALIASES = {
    gold: ["金", "ゴールド", "XAU", "COMEX"],
    oil: ["WTI", "原油", "Brent", "ホルムズ", "イラン"],
    nikkei: ["日経225先物", "日経先物", "日経225", "日本株"],
    usdjpy: ["USD/JPY", "USDJPY", "ドル円", "円", "ドル"],
    eurusd: ["EUR/USD", "EURUSD", "ユーロ", "ドル"],
    btc: ["BTCUSD", "BTC", "Bitcoin", "ビットコイン", "暗号資産"]
  };

  const KEYWORDS = {
    gold: /金|ゴールド|地政学|財政|通貨価値|ドル安|金利|ヘッジ/,
    oil: /WTI|原油|Brent|ホルムズ|イラン|供給|地政学|在庫|OPEC|ショートカバー|インフレヘッジ/,
    nikkei: /日経|日本株|米株|Nasdaq|半導体|円|金利|原油|先物/,
    usdjpy: /USD\/JPY|ドル円|円|ドル|日米金利差|米金利|日銀|介入|実需|キャリー/,
    eurusd: /EUR\/USD|ユーロ|ドル|ECB|Fed|米金利|ドル安|ドル高/,
    btc: /BTC|Bitcoin|ビットコイン|暗号資産|ETF|ドル|流動性|ショートカバー|規制/
  };

  function arr(v) { return Array.isArray(v) ? v : v ? [v] : []; }
  function txt(v) {
    if (typeof v === "string") return v;
    if (!v || typeof v !== "object") return "";
    return String(v.text || v.summary || v.title || "");
  }
  function clean(v, max = 220) {
    const s = String(v || "").replace(/\s+/g, " ").trim();
    return s.length > max ? `${s.slice(0, max)}…` : s;
  }
  function symbolFromCard(card) {
    const h = clean(card?.querySelector("h3")?.textContent || "", 80);
    if (/WTI|原油/.test(h)) return "oil";
    if (/日経/.test(h)) return "nikkei";
    if (/USD\/JPY|ドル円/.test(h)) return "usdjpy";
    if (/EUR\/USD|ユーロ/.test(h)) return "eurusd";
    if (/BTC|ビットコイン/.test(h)) return "btc";
    return "gold";
  }
  function marketFor(report, symbol) {
    return arr(report?.markets).find((m) => {
      const s = `${m?.name || ""} ${m?.symbol || ""}`;
      return (ALIASES[symbol] || []).some((a) => s.toLowerCase().includes(a.toLowerCase()));
    }) || {};
  }
  function candidateLines(report, symbol) {
    const market = marketFor(report, symbol);
    const lines = [];
    [market.material, market.positioning, market.reason, market.outlook].forEach((v) => v && lines.push(clean(v)));
    [report?.news, report?.crossAssetFlow, report?.positioning, report?.consistency, report?.changes, report?.rates]
      .forEach((group) => arr(group).forEach((v) => lines.push(clean(txt(v)))));
    const body = String(report?.fullText || report?.rawText || report?.body || "").replace(/\r/g, "");
    if (body) body.split(/\n+/).forEach((v) => lines.push(clean(v)));
    return lines.filter(Boolean);
  }
  function score(line, symbol) {
    let s = 0;
    const lower = line.toLowerCase();
    (ALIASES[symbol] || []).forEach((a) => { if (lower.includes(a.toLowerCase())) s += 5; });
    if ((KEYWORDS[symbol] || /.^/).test(line)) s += 3;
    if (/支え|背景|ため|懸念|供給|需要|資金流入|資金流出|買い|売り|上昇|下落|地政学|金利|インフレ|ショートカバー|実需/.test(line)) s += 2;
    if (/主要市場データ|前営業日終値|確認値|取得不能/.test(line)) s -= 4;
    return s;
  }
  function reasonFor(report, symbol) {
    const lines = candidateLines(report, symbol)
      .map((line) => ({ line, score: score(line, symbol) }))
      .filter((x) => x.score >= 5)
      .sort((a, b) => b.score - a.score);
    if (!lines.length) return "";
    if (symbol === "oil") {
      const geo = lines.find((x) => /ホルムズ|イラン|供給|地政学/.test(x.line));
      const flow = lines.find((x) => /資金流入|ショートカバー|インフレヘッジ/.test(x.line));
      if (geo && flow && geo.line !== flow.line) return clean(`${geo.line} ${flow.line}`, 260);
    }
    return clean(lines[0].line, 260);
  }
  function consistencyFor(report, symbol, reason) {
    const lines = arr(report?.consistency).map(txt).filter(Boolean);
    const exact = lines.find((line) => score(line, symbol) >= 5);
    if (exact) {
      if (/不整合|逆行|反して/.test(exact)) return { verdict: "不整合", reason: clean(exact, 240) };
      if (/一部|ただし|一方/.test(exact)) return { verdict: "一部整合", reason: clean(exact, 240) };
      return { verdict: "整合", reason: clean(exact, 240) };
    }
    if (reason) return { verdict: "整合", reason: "本文・構造化データに市場別材料があり、表示方向との因果関係を確認" };
    return null;
  }
  function patchCards(report) {
    const cards = document.querySelectorAll("#marketCards .market-card");
    if (!cards.length || !report) return;
    cards.forEach((card) => {
      const symbol = symbolFromCard(card);
      const dds = card.querySelectorAll("dl dd");
      if (!dds.length) return;
      const current = clean(dds[0].textContent || "", 300);
      const bad = !current || /本文に市場別理由がありません|個別記載なし|確認中|判定保留/.test(current);
      const reason = reasonFor(report, symbol);
      if (bad && reason) dds[0].textContent = reason;

      const consistency = consistencyFor(report, symbol, reason || (!bad ? current : ""));
      if (!consistency) return;
      const badge = card.querySelector(".consistency-badge");
      const note = card.querySelector(".market-note");
      if (badge) {
        badge.textContent = `材料と値動きの整合性：${consistency.verdict}`;
        badge.classList.remove("match", "partial", "conflict", "pending");
        badge.classList.add(consistency.verdict === "整合" ? "match" : consistency.verdict === "不整合" ? "conflict" : "partial");
      }
      if (note) note.textContent = consistency.reason;
    });
  }

  const baseRender = typeof renderMarketCards === "function" ? renderMarketCards : null;
  if (baseRender) {
    const patchedRender = function(report) {
      baseRender(report);
      patchCards(report);
    };
    try { renderMarketCards = patchedRender; } catch (_e) {}
    window.renderMarketCards = patchedRender;
  }
  window.patchDashboardMarketCardReasons = patchCards;

  try {
    if (typeof selectedReport !== "undefined" && selectedReport) patchCards(selectedReport);
  } catch (_e) {}
})();
