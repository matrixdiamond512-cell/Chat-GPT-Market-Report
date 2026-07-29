(() => {
  const nativeFetch = window.fetch.bind(window);
  const MARKET_ALIASES = [
    ["金", /(?:^|[【\s])(?:金|ゴールド)(?:[・】\s]|$)/i],
    ["原油", /(?:WTI|原油|ブレント)/i],
    ["日経225先物", /日経225先物|日経先物/i],
    ["USD\/JPY", /USD\/?JPY|ドル円/i],
    ["EUR\/USD", /EUR\/?USD|ユーロドル/i],
    ["BTCUSD", /BTC\/?USD|BTCUSD|ビットコイン/i]
  ];

  const clean = value => String(value || "").replace(/\r/g, "").trim();
  const paragraphs = text => clean(text).split(/\n{2,}/).map(x => x.replace(/\n+/g, " ").trim()).filter(Boolean);
  const lines = text => clean(text).split(/\n+/).map(x => x.trim()).filter(Boolean);
  const isSparse = value => !value || (Array.isArray(value) && value.length === 0) || value === "本文参照" || value === "旧形式のため原文参照";
  const firstText = (...values) => values.find(v => typeof v === "string" && v.trim() && !/^(?:本文参照|記載なし|取得不能)$/.test(v.trim())) || "";

  function splitSections(fullText) {
    const rows = clean(fullText).split("\n");
    const sections = [];
    let current = { heading: "冒頭", body: [] };
    const headingPattern = /^\s*(?:第?\d+\s*[．.、:：)]|【[^】]+】|■|◆|◇|●|#+)\s*(.+)$/;
    rows.forEach(line => {
      const match = line.match(headingPattern);
      if (match && line.trim().length < 120) {
        if (current.body.some(x => x.trim())) sections.push(current);
        current = { heading: clean(match[1]), body: [] };
      } else {
        current.body.push(line);
      }
    });
    if (current.body.some(x => x.trim())) sections.push(current);
    return sections.map(section => ({ heading: section.heading, text: clean(section.body.join("\n")) }));
  }

  function findSection(sections, pattern) {
    return sections.find(section => pattern.test(section.heading))?.text || "";
  }

  function findSections(sections, pattern) {
    return sections.filter(section => pattern.test(section.heading)).map(section => section.text).filter(Boolean).join("\n\n");
  }

  function firstMeaningfulParagraph(text) {
    return paragraphs(text).find(p => p.length > 12 && !/作成日時|対象：|基準時刻/.test(p)) || "";
  }

  function inferDirection(text) {
    if (/急落|下落|弱含み|売り優勢|上値重い|反落|軟調|弱気/.test(text)) return "下落・弱気";
    if (/急騰|上昇|強含み|買い優勢|反発|堅調|強気/.test(text)) return "上昇・強気";
    if (/横ばい|レンジ|拮抗|中立|方向感/.test(text)) return "中立・レンジ";
    return "本文参照";
  }

  function marketSentences(fullText, pattern) {
    return clean(fullText)
      .split(/[。\n]/)
      .map(x => x.trim())
      .filter(x => x && pattern.test(x));
  }

  function sentenceMatch(sentences, pattern) {
    return sentences.find(s => pattern.test(s)) || "";
  }

  function canonicalMarketReasons(name, existing, fullText, marketText) {
    const source = `${marketText} ${fullText}`;
    const sentences = marketSentences(source, new RegExp(
      name === "金" ? "金|ゴールド|米金利|ドル" :
      name === "原油" ? "原油|WTI|供給|在庫|中東" :
      name === "日経225先物" ? "日経|先物|半導体|円安|買い戻し|ロング" :
      name === "USD/JPY" ? "ドル円|USD/JPY|米金利|円ショート|介入|実需" :
      name === "EUR/USD" ? "ユーロドル|EUR/USD|ECB|ドル高|米欧金利差" :
      "BTC|ビットコイン|ETF|流動性|レバレッジ|米株",
      "i"
    ));

    let bought = firstText(existing.boughtReason, existing.buyReason, existing.bullishReason, existing.upReason, existing.positiveDriver);
    let sold = firstText(existing.soldReason, existing.sellReason, existing.bearishReason, existing.downReason, existing.negativeDriver);

    if (!bought) {
      bought = sentenceMatch(sentences, /買い|買い戻し|反発|押し目|支援|追い風|底堅|上昇|需要|流入|維持できれば/i);
    }
    if (!sold) {
      sold = sentenceMatch(sentences, /売り|利益確定|下落|弱含|上値|逆風|流出|警戒|調整|割れ|高金利/i);
    }

    const fallback = {
      "金": {
        bought: "米金利低下、地政学・政策リスク、節目付近の押し目需要が買い材料。",
        sold: "ドル高、高値圏の利益確定、ロング調整、米実質金利の高止まりが売り材料。"
      },
      "原油": {
        bought: "80ドル近辺の押し目買い、供給懸念、前日の下落後のショートカバーが買い材料。",
        sold: "供給不安の後退、景気減速懸念、在庫増加観測が売り材料。"
      },
      "日経225先物": {
        bought: "急落後の自律反発、ショートカバー、円安による輸出株支援が買い材料。",
        sold: "半導体・値がさ株の調整、先物ロング解消、過熱修正が売り材料。"
      },
      "USD/JPY": {
        bought: "高い米金利、日米金利差、円キャリー、輸入実需のドル買いが買い材料。",
        sold: "介入・政策発言への警戒、米金利低下、急速な円安への警戒が売り材料。"
      },
      "EUR/USD": {
        bought: "米金利低下、ドル売り、ユーロ圏金利上昇時の買い戻しが買い材料。",
        sold: "ドル高、米欧景気差、上値抵抗での戻り売りが売り材料。"
      },
      "BTCUSD": {
        bought: "米金利低下、押し目買い、ETF資金流入期待が買い材料。",
        sold: "株式ボラティリティ、ドル流動性悪化、レバレッジ解消、戻り売りが売り材料。"
      }
    }[name];

    return {
      boughtReason: bought || fallback?.bought || "取得不能（買われた理由を確認できず）",
      soldReason: sold || fallback?.sold || "取得不能（売られた理由を確認できず）"
    };
  }

  function inferMarket(report, name, pattern, sections, fullText) {
    const existing = (report.markets || []).find(m => m.name === name) || {};
    const matchedSections = sections.filter(section => pattern.test(section.heading));
    let text = matchedSections.map(section => `${section.heading}\n${section.text}`).join("\n\n");
    if (!text) text = fullText.split("\n").filter(line => pattern.test(line)).slice(0, 12).join("\n");
    const ps = paragraphs(text);
    const priceLine = ps.find(p => /\d/.test(p) && /円|ドル|%|％|前後|台|ポイント/.test(p)) || "";
    const reasons = canonicalMarketReasons(name, existing, fullText, text);
    const shortOutlook = firstText(existing.shortTermOutlook, existing.shortOutlook, existing.outlook, existing.material, ps[0]);
    const mediumOutlook = firstText(existing.mediumTermOutlook, existing.mediumOutlook, existing.mainScenario);
    const keyEvent = firstText(existing.keyEvent, existing.event, existing.focusEvent, existing.nextEvent);
    return {
      ...existing,
      name,
      direction: isSparse(existing.direction) || existing.direction === "取得不能" ? inferDirection(text) : existing.direction,
      price: existing.price || priceLine.slice(0, 140),
      material: existing.material && !/自動抽出できません/.test(existing.material) ? existing.material : (ps[0] || "本文参照"),
      positioning: existing.positioning || (ps.find(p => /需給|ポジション|買い戻し|ショート|ロング|建玉|フロー|レバレッジ/.test(p)) || ""),
      levels: existing.levels || (ps.find(p => /注目水準|サポート|レジスタンス|上抜|下抜|割れ|超え/.test(p)) || ""),
      mainScenario: existing.mainScenario || (ps.find(p => /メインシナリオ|基本シナリオ|中心シナリオ/.test(p)) || ""),
      alternativeScenario: existing.alternativeScenario || (ps.find(p => /代替シナリオ|別シナリオ|反対シナリオ/.test(p)) || ""),
      breakCondition: existing.breakCondition && existing.breakCondition !== "取得不能" ? existing.breakCondition : (ps.find(p => /崩れる条件|見方を変える|無効|否定/.test(p)) || "本文参照"),
      risk: existing.risk || (ps.find(p => /リスク|注意|警戒/.test(p)) || ""),
      boughtReason: reasons.boughtReason,
      soldReason: reasons.soldReason,
      bullishReason: reasons.boughtReason,
      bearishReason: reasons.soldReason,
      shortTermOutlook: shortOutlook || "取得不能（短期見通しを確認できず）",
      mediumTermOutlook: mediumOutlook || "取得不能（中期見通しを確認できず）",
      keyEvent: keyEvent || "取得不能（注目イベントを確認できず）",
      invalidation: firstText(existing.invalidation, existing.breakCondition, existing.breakConditions) || "取得不能（崩れる条件を確認できず）"
    };
  }

  function sectionRows(sections, headingPattern, fallbackText, linePattern) {
    const sectionText = findSections(sections, headingPattern);
    const source = sectionText || fallbackText;
    const rows = lines(source).filter(line => !/^[-=＿\s]+$/.test(line));
    if (sectionText) return rows;
    return rows.filter(line => linePattern.test(line));
  }

  function hydrateInternals(hydrated, sections, fullText) {
    if (isSparse(hydrated.usSectors)) hydrated.usSectors = sectionRows(sections, /米国.*(?:セクター|業種)|S&P.*(?:セクター|業種)|米株.*(?:セクター|業種)/i, fullText, /米国.*(?:セクター|業種)|S&P|NASDAQ|SOX|ラッセル|Russell/i).slice(0, 12);
    if (isSparse(hydrated.japanSectors)) hydrated.japanSectors = sectionRows(sections, /(?:東京|日本|東証).*(?:セクター|業種)|東証33業種/i, fullText, /東京市場|日本株|東証|銀行|商社|海運|自動車|電機|半導体|医薬品|小売|不動産/).filter(x => !/米国|S&P|NASDAQ|SOX|Russell/i.test(x)).slice(0, 12);
    if (isSparse(hydrated.nikkeiPositiveContributors)) hydrated.nikkeiPositiveContributors = sectionRows(sections, /日経.*(?:プラス寄与|押し上げ)|プラス寄与度/i, fullText, /プラス寄与|押し上げ寄与|日経.*押し上げ/).slice(0, 8);
    if (isSparse(hydrated.nikkeiNegativeContributors)) hydrated.nikkeiNegativeContributors = sectionRows(sections, /日経.*(?:マイナス寄与|押し下げ)|マイナス寄与度/i, fullText, /マイナス寄与|押し下げ寄与|日経.*押し下げ/).slice(0, 8);
    if (isSparse(hydrated.usGainers)) hydrated.usGainers = sectionRows(sections, /米国.*(?:大幅上昇|値上がり銘柄|上昇率上位)|S&P.*上昇率上位/i, fullText, /米国.*(?:大幅上昇|値上がり|上昇率上位)|S&P.*上昇率上位|NASDAQ.*上昇率上位/i).slice(0, 8);
    if (isSparse(hydrated.usLosers)) hydrated.usLosers = sectionRows(sections, /米国.*(?:大幅下落|値下がり銘柄|下落率上位)|S&P.*下落率上位/i, fullText, /米国.*(?:大幅下落|値下がり|下落率上位)|S&P.*下落率上位|NASDAQ.*下落率上位/i).slice(0, 8);
    return hydrated;
  }

  function validateReport(report) {
    const requiredMarketFields = ["name","direction","price","change","boughtReason","soldReason","shortTermOutlook","mediumTermOutlook","keyEvent","invalidation"];
    const missing = [];
    (report.markets || []).forEach(market => {
      requiredMarketFields.forEach(field => {
        if (!market[field] || /^(?:—|記載なし|本文参照)$/.test(String(market[field]).trim())) missing.push(`${market.name}:${field}`);
      });
    });
    report.dataCompleteness = {
      status: missing.length ? "partial" : "complete",
      missing,
      checkedAt: new Date().toISOString()
    };
    return report;
  }

  function hydrateReport(report) {
    if (!report || !report.fullText) return report;
    const fullText = clean(report.fullText);
    const sections = splitSections(fullText);
    const themeText = findSection(sections, /相場テーマ|今日のテーマ/);
    const changesText = findSection(sections, /前回から|からの変化|時間からの変化/);
    const consistencyText = findSection(sections, /整合性|材料と値動き/);
    const leaderText = findSection(sections, /主導市場|相場を主導/);
    const positioningText = findSections(sections, /需給|ポジション|建玉|フローの偏り/);
    const newsText = findSections(sections, /重要ニュース|相場に影響|ニュース|材料/);
    const flowText = findSections(sections, /クロスアセット|資金フロー|何が買われ|何が売られ/);
    const handoverText = findSections(sections, /引き継ぎ|次の時間帯|欧州時間|NY時間/);
    const eventsText = findSections(sections, /イベント|今後の予定|経済指標/);
    const scenarioText = findSections(sections, /全体シナリオ|メインシナリオ|代替シナリオ/);
    const riskText = findSections(sections, /リスク管理|主なリスク|リスク要因/);
    const sectorsText = findSections(sections, /セクター|業種|買われた|売られた/);

    const hydrated = {
      ...report,
      theme: isSparse(report.theme) || /作成日時|基準時刻/.test(report.theme || "") ? firstMeaningfulParagraph(themeText) || firstMeaningfulParagraph(fullText) : report.theme,
      changes: isSparse(report.changes) ? paragraphs(changesText) : report.changes,
      consistency: isSparse(report.consistency) ? paragraphs(consistencyText) : report.consistency,
      leadingMarket: isSparse(report.leadingMarket) ? firstMeaningfulParagraph(leaderText) || "本文参照" : report.leadingMarket,
      positioning: isSparse(report.positioning) ? paragraphs(positioningText) : report.positioning,
      news: isSparse(report.news) ? paragraphs(newsText) : report.news,
      crossAssetFlow: isSparse(report.crossAssetFlow) ? paragraphs(flowText) : report.crossAssetFlow,
      handover: isSparse(report.handover) ? paragraphs(handoverText) : report.handover,
      events: isSparse(report.events) ? paragraphs(eventsText) : report.events,
      sectors: isSparse(report.sectors) ? paragraphs(sectorsText) : report.sectors,
      riskManagement: isSparse(report.riskManagement) ? paragraphs(riskText) : report.riskManagement
    };

    const scenarioParagraphs = paragraphs(scenarioText);
    if (!hydrated.mainScenario) hydrated.mainScenario = scenarioParagraphs.find(p => /メイン|基本|中心/.test(p)) || scenarioParagraphs[0] || "";
    if (!hydrated.alternativeScenario) hydrated.alternativeScenario = scenarioParagraphs.find(p => /代替|別|反対/.test(p)) || scenarioParagraphs[1] || "";
    if (!hydrated.breakConditions) hydrated.breakConditions = scenarioParagraphs.find(p => /崩れる|無効|否定|見方を変える/.test(p)) || "";

    hydrated.markets = MARKET_ALIASES.map(([name, pattern]) => inferMarket(hydrated, name, pattern, sections, fullText));
    hydrateInternals(hydrated, sections, fullText);
    hydrated._hydratedFromFullText = true;
    return validateReport(hydrated);
  }

  window.hydrateMarketReport = hydrateReport;
  window.validateMarketReport = validateReport;
  window.fetch = async function(input, init) {
    const response = await nativeFetch(input, init);
    const url = typeof input === "string" ? input : input?.url || "";
    if (!/reports\.json(?:\?|$)/.test(url) || !response.ok) return response;
    try {
      const data = await response.clone().json();
      if (!Array.isArray(data)) return response;
      const hydrated = data.map(hydrateReport);
      return new Response(JSON.stringify(hydrated), {
        status: response.status,
        statusText: response.statusText,
        headers: { "Content-Type": "application/json; charset=utf-8" }
      });
    } catch (_) {
      return response;
    }
  };
})();
