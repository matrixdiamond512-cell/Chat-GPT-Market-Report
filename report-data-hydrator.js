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
  const isSparse = value => !value || (Array.isArray(value) && value.length === 0) || value === "本文参照" || value === "旧形式のため原文参照";

  function splitSections(fullText) {
    const lines = clean(fullText).split("\n");
    const sections = [];
    let current = { heading: "冒頭", body: [] };
    const headingPattern = /^\s*(?:第?\d+\s*[．.、:：)]|【[^】]+】|■|◆|◇|●)\s*(.+)$/;
    lines.forEach(line => {
      const match = line.match(headingPattern);
      if (match && line.trim().length < 100) {
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

  function inferMarket(report, name, pattern, sections, fullText) {
    const existing = (report.markets || []).find(m => m.name === name) || {};
    const matchedSections = sections.filter(section => pattern.test(section.heading));
    let text = matchedSections.map(section => `${section.heading}\n${section.text}`).join("\n\n");
    if (!text) {
      const lines = fullText.split("\n").filter(line => pattern.test(line));
      text = lines.slice(0, 12).join("\n");
    }
    const ps = paragraphs(text);
    const priceLine = ps.find(p => /\d/.test(p) && /円|ドル|%|％|前後|台|ポイント/.test(p)) || "";
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
      risk: existing.risk || (ps.find(p => /リスク|注意|警戒/.test(p)) || "")
    };
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
    hydrated._hydratedFromFullText = true;
    return hydrated;
  }

  window.hydrateMarketReport = hydrateReport;
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
